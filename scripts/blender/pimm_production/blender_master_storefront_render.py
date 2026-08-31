"""Render a clean storefront still set directly from an authoritative PIMM master.

The opened master is treated as read-only. Cameras, lights, and the studio floor
exist only in the current background Blender process; this script never saves a
Blend file and never reads a legacy scene or render.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Sequence


RELEASE_ID = "pimm-master-20260831-r02"
RESULT_MARKER = "PIMM_MASTER_STOREFRONT_RENDER_JSON="
EXPECTED_MASTER_NAMES = {
    "30G": "PIMM-30G-MASTER.blend",
    "50G": "PIMM-50G-MASTER.blend",
}
EXPECTED_OBJECT_COUNT = 556
FOOT_TOLERANCE = 0.0002
SHOT_NAMES = ("hero", "three-quarter", "controls", "tooling")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", choices=tuple(EXPECTED_MASTER_NAMES), required=True)
    parser.add_argument("--expected-master-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--shot", choices=SHOT_NAMES, action="append")
    parser.add_argument("--resolution", type=int, default=1600)
    parser.add_argument("--samples", type=int, default=96)
    parser.add_argument("--replace-working-output", action="store_true")
    return parser.parse_args(argv)


def _world_bounds(objects: Sequence[Any]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    from mathutils import Vector

    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    if not points:
        raise ValueError("PIMM_PUBLISHED contains no renderable mesh bounds")
    return (
        tuple(min(point[axis] for point in points) for axis in range(3)),
        tuple(max(point[axis] for point in points) for axis in range(3)),
    )


def _validate_master(bpy: Any, machine: str, expected_sha256: str) -> tuple[list[Any], dict[str, object]]:
    from mathutils import Vector

    source = Path(bpy.data.filepath).resolve()
    if source.name != EXPECTED_MASTER_NAMES[machine]:
        raise ValueError(f"opened file is not the authoritative {machine} master: {source}")
    actual_sha256 = sha256_file(source)
    if actual_sha256 != expected_sha256.upper():
        raise ValueError(f"authoritative master SHA drift: expected {expected_sha256}, got {actual_sha256}")
    published = bpy.data.collections.get("PIMM_PUBLISHED")
    if published is None:
        raise ValueError("authoritative master has no PIMM_PUBLISHED collection")
    meshes = [obj for obj in published.all_objects if obj.type == "MESH"]
    if len(meshes) != EXPECTED_OBJECT_COUNT:
        raise ValueError(f"PIMM_PUBLISHED must contain {EXPECTED_OBJECT_COUNT} meshes; found {len(meshes)}")
    feet = [obj for obj in meshes if "__nylon-feet__" in obj.name.lower()]
    if len(feet) != 4:
        raise ValueError(f"authoritative master must expose four nylon foot pads; found {len(feet)}")
    levels = [min((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box) for obj in feet]
    spread = max(levels) - min(levels)
    if spread > FOOT_TOLERANCE or max(abs(level) for level in levels) > FOOT_TOLERANCE:
        raise ValueError(f"foot contact plane is invalid: levels={levels}, spread={spread}")
    return meshes, {
        "master_path": str(source),
        "master_sha256": actual_sha256,
        "published_meshes": len(meshes),
        "foot_contact_levels": levels,
        "foot_contact_spread": spread,
    }


def _runtime_collection(bpy: Any) -> Any:
    existing = bpy.data.collections.get("PIMM_STOREFRONT_RUNTIME")
    if existing is not None:
        for obj in list(existing.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(existing)
    collection = bpy.data.collections.new("PIMM_STOREFRONT_RUNTIME")
    bpy.context.scene.collection.children.link(collection)
    return collection


def _look_at(obj: Any, target: tuple[float, float, float]) -> None:
    from mathutils import Vector

    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def _material(bpy: Any, name: str, color: tuple[float, float, float, float], roughness: float) -> Any:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    return material


def _add_area_light(
    bpy: Any,
    collection: Any,
    name: str,
    location: tuple[float, float, float],
    target: tuple[float, float, float],
    energy: float,
    size: float,
    shape: str = "DISK",
) -> None:
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = shape
    data.size = size
    if shape == "RECTANGLE":
        data.size_y = size * 1.6
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = location
    _look_at(obj, target)


def _install_studio(
    bpy: Any,
    collection: Any,
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
) -> None:
    center = tuple((bounds_min[index] + bounds_max[index]) / 2 for index in range(3))
    width = bounds_max[0] - bounds_min[0]
    depth = bounds_max[1] - bounds_min[1]
    height = bounds_max[2] - bounds_min[2]
    bpy.ops.mesh.primitive_plane_add(size=100_000.0, location=(center[0], center[1], 0.0))
    floor = bpy.context.object
    floor.name = "PIMM_STUDIO_FLOOR"
    for owner in list(floor.users_collection):
        owner.objects.unlink(floor)
    collection.objects.link(floor)
    floor.data.materials.append(_material(bpy, "PIMM_STUDIO_FLOOR_MAT", (0.46, 0.52, 0.60, 1.0), 0.88))

    target = (center[0], center[1], bounds_min[2] + height * 0.5)
    scale = 6.0
    _add_area_light(
        bpy, collection, "KEY_SOFTBOX",
        (center[0] - width * 2.0, center[1] - depth * 3.4, bounds_min[2] + height * 1.15),
        target, 900_000.0 * scale, max(height * 0.9, 700.0), "RECTANGLE",
    )
    _add_area_light(
        bpy, collection, "FILL_SOFTBOX",
        (center[0] + width * 2.0, center[1] - depth * 2.5, bounds_min[2] + height * 0.7),
        target, 280_000.0 * scale, max(height * 0.7, 600.0), "RECTANGLE",
    )
    _add_area_light(
        bpy, collection, "BASE_BOUNCE",
        (center[0], center[1] - depth * 2.8, bounds_min[2] + height * 0.18),
        (center[0], center[1], bounds_min[2] + height * 0.25),
        240_000.0 * scale, max(width * 1.8, 800.0), "RECTANGLE",
    )
    _add_area_light(
        bpy, collection, "RIM_LEFT",
        (center[0] - width * 1.7, center[1] + depth * 2.0, bounds_min[2] + height * 0.8),
        target, 320_000.0 * scale, max(height * 0.35, 320.0), "RECTANGLE",
    )
    _add_area_light(
        bpy, collection, "RIM_RIGHT",
        (center[0] + width * 1.7, center[1] + depth * 2.0, bounds_min[2] + height * 0.7),
        target, 240_000.0 * scale, max(height * 0.3, 280.0), "RECTANGLE",
    )


def _shot_camera(
    bpy: Any,
    collection: Any,
    shot: str,
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
    resolution: int,
) -> tuple[Any, tuple[int, int]]:
    center = tuple((bounds_min[index] + bounds_max[index]) / 2 for index in range(3))
    width = bounds_max[0] - bounds_min[0]
    depth = bounds_max[1] - bounds_min[1]
    height = bounds_max[2] - bounds_min[2]
    if shot == "hero":
        aspect = (resolution, int(resolution * 1.2))
        azimuth, elevation, target_z, ortho_scale = 0.0, 2.5, height * 0.50, height * 1.10
    elif shot == "three-quarter":
        aspect = (resolution, int(resolution * 0.82))
        azimuth, elevation, target_z, ortho_scale = -28.0, 6.0, height * 0.50, height * 1.30
    elif shot == "controls":
        aspect = (resolution, int(resolution * 0.78))
        azimuth, elevation, target_z, ortho_scale = -8.0, 1.5, height * 0.70, height * 0.46
    else:
        aspect = (resolution, int(resolution * 0.78))
        azimuth, elevation, target_z, ortho_scale = 0.0, 1.5, height * 0.36, height * 0.47

    target = (center[0] + (width * 0.08 if shot == "controls" else 0.0), center[1], bounds_min[2] + target_z)
    radius = max(width, depth, height) * 3.0
    azimuth_radians = math.radians(azimuth)
    elevation_radians = math.radians(elevation)
    location = (
        target[0] + math.sin(azimuth_radians) * radius * math.cos(elevation_radians),
        target[1] - math.cos(azimuth_radians) * radius * math.cos(elevation_radians),
        target[2] + math.sin(elevation_radians) * radius,
    )
    data = bpy.data.cameras.new("CAM_STOREFRONT")
    data.type = "ORTHO"
    data.ortho_scale = ortho_scale
    data.lens = 70.0
    data.clip_start = 1.0
    data.clip_end = 20_000.0
    camera = bpy.data.objects.new("CAM_STOREFRONT", data)
    collection.objects.link(camera)
    camera.location = location
    _look_at(camera, target)
    bpy.context.scene.camera = camera
    return camera, aspect


def _configure_render(bpy: Any, width: int, height: int, samples: int, output: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.filepath = str(output)
    scene.render.use_file_extension = True
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene, "eevee"):
        optional_eevee_settings = {
            "taa_render_samples": samples,
            "use_gtao": True,
            "gtao_distance": 3.0,
            "gtao_factor": 1.25,
        }
        for name, value in optional_eevee_settings.items():
            if hasattr(scene.eevee, name):
                setattr(scene.eevee, name, value)
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.65
    scene.view_settings.gamma = 1.0
    world = scene.world or bpy.data.worlds.new("PIMM_STOREFRONT_WORLD")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.45, 0.52, 0.62, 1.0)
    background.inputs["Strength"].default_value = 0.40


def render(bpy: Any, arguments: argparse.Namespace) -> dict[str, object]:
    meshes, provenance = _validate_master(bpy, arguments.machine, arguments.expected_master_sha256)
    bounds_min, bounds_max = _world_bounds(meshes)
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = tuple(arguments.shot or SHOT_NAMES)
    outputs = []
    for shot in selected:
        runtime = _runtime_collection(bpy)
        _install_studio(bpy, runtime, bounds_min, bounds_max)
        _camera, dimensions = _shot_camera(bpy, runtime, shot, bounds_min, bounds_max, arguments.resolution)
        output = output_dir / f"{RELEASE_ID}-{arguments.machine.lower()}-{shot}.png"
        if output.exists() and not arguments.replace_working_output:
            raise FileExistsError(f"refusing to overwrite storefront render: {output}")
        _configure_render(bpy, dimensions[0], dimensions[1], arguments.samples, output)
        bpy.ops.render.render(write_still=True)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Blender did not create storefront render: {output}")
        outputs.append({
            "shot": shot,
            "path": str(output),
            "width": dimensions[0],
            "height": dimensions[1],
            "sha256": sha256_file(output),
        })
    return {
        "schema": "maliev.pimm-master-storefront-render/v1",
        "release_id": RELEASE_ID,
        "machine": arguments.machine,
        "provenance": provenance,
        "outputs": outputs,
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else sys.argv[1:]
    )
    import bpy

    result = render(bpy, arguments)
    print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
