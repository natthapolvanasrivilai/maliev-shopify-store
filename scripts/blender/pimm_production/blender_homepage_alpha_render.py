"""Render purpose-staged 30G and 50G pairs for each homepage location.

The opened 30G master and appended 50G master remain read-only. Each content
location receives a separate physical staging and camera contract so a crop of
the hero can never silently become catalogue or navigation media.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Sequence


sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_master_storefront_render import (  # noqa: E402
    EXPECTED_OBJECT_COUNT,
    FOOT_TOLERANCE,
    _configure_render,
    _install_studio,
    _look_at,
    _runtime_collection,
    _validate_master,
    sha256_file,
)


RELEASE_ID = "maliev-homepage-pimm-20260901-r07"
RESULT_MARKER = "MALIEV_HOMEPAGE_PAIR_RENDER_JSON="
SECONDARY_MASTER_NAME = "PIMM-50G-MASTER.blend"
APPEND_FOOT_TOLERANCE = 0.001
PAIR_GAP_RATIO = 0.04
HERO_ROTATION_DEGREES = 45.0
CATALOGUE_ROTATION_DEGREES = -32.0
CATALOGUE_DEPTH_STAGGER_RATIO = 0.14
CATALOGUE_PAIR_GAP_RATIO = 0.04
CATALOGUE_COPY_SAFE_RATIO = 0.36
CATALOGUE_CAMERA_DISTANCE_MULTIPLIER = 1.30
CATALOGUE_CAMERA_SHIFT_X = 0.02
CATALOGUE_CAMERA_SHIFT_Y = 0.20
NAVIGATION_ROTATION_DEGREES = 18.0
PLACEMENTS = {
    "hero-desktop": (1800, 1200),
    "hero-mobile": (1200, 1500),
    "catalogue": (1086, 1448),
    "navigation": (900, 900),
}
STAGING = {
    "hero-desktop": {
        "composition_id": "hero-pair-45",
        "rotation_degrees": HERO_ROTATION_DEGREES,
        "reverse_order": False,
        "depth_stagger_ratio": 0.0,
    },
    "hero-mobile": {
        "composition_id": "hero-pair-45",
        "rotation_degrees": HERO_ROTATION_DEGREES,
        "reverse_order": False,
        "depth_stagger_ratio": 0.0,
    },
    "catalogue": {
        "composition_id": "catalogue-copy-safe-minus32",
        "rotation_degrees": CATALOGUE_ROTATION_DEGREES,
        "reverse_order": True,
        "depth_stagger_ratio": CATALOGUE_DEPTH_STAGGER_RATIO,
        "pair_gap_ratio": CATALOGUE_PAIR_GAP_RATIO,
    },
    "navigation": {
        "composition_id": "navigation-compact-18",
        "rotation_degrees": NAVIGATION_ROTATION_DEGREES,
        "reverse_order": False,
        "depth_stagger_ratio": -0.08,
        "pair_gap_ratio": 0.02,
    },
}
for _hero_placement in ("hero-desktop", "hero-mobile"):
    STAGING[_hero_placement]["pair_gap_ratio"] = PAIR_GAP_RATIO


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-primary-sha256", required=True)
    parser.add_argument("--secondary-master", type=Path, required=True)
    parser.add_argument("--expected-secondary-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--placement", choices=tuple(PLACEMENTS), action="append")
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--replace-working-output", action="store_true")
    return parser.parse_args(argv)


def _validate_collection(bpy: Any, collection: Any, machine: str) -> tuple[list[Any], dict[str, object]]:
    from mathutils import Vector

    meshes = [obj for obj in collection.all_objects if obj.type == "MESH"]
    if len(meshes) != EXPECTED_OBJECT_COUNT:
        raise ValueError(f"{machine} appended collection must contain {EXPECTED_OBJECT_COUNT} meshes; found {len(meshes)}")
    if not all(
        obj.name.startswith(f"{machine}__") or obj.name.startswith("PIMM50_MASTER_")
        for obj in meshes
    ):
        raise ValueError(f"{machine} appended collection contains foreign machine objects")
    feet = [obj for obj in meshes if "__nylon-feet__" in obj.name.lower()]
    if len(feet) != 4:
        raise ValueError(f"{machine} appended collection must expose four nylon feet; found {len(feet)}")
    levels = [min((obj.matrix_world @ Vector(corner)).z for corner in obj.bound_box) for obj in feet]
    spread = max(levels) - min(levels)
    if spread > APPEND_FOOT_TOLERANCE or max(abs(level) for level in levels) > APPEND_FOOT_TOLERANCE:
        raise ValueError(f"{machine} foot contact plane is invalid: levels={levels}, spread={spread}")
    return meshes, {"published_meshes": len(meshes), "foot_contact_levels": levels, "foot_contact_spread": spread}


def _append_secondary_master(
    bpy: Any, path: Path, expected_sha256: str
) -> tuple[list[Any], dict[str, object], Any]:
    source = path.resolve(strict=True)
    if source.name != SECONDARY_MASTER_NAME:
        raise ValueError(f"secondary master must be {SECONDARY_MASTER_NAME}: {source}")
    actual_sha256 = sha256_file(source)
    if actual_sha256 != expected_sha256.upper():
        raise ValueError(f"secondary master SHA drift: expected {expected_sha256.upper()}, got {actual_sha256}")
    with bpy.data.libraries.load(str(source), link=False) as (available, requested):
        if not available.scenes:
            raise ValueError("secondary master has no scene to preserve published transforms")
        if "PIMM_PUBLISHED" not in available.collections:
            raise ValueError("secondary master has no PIMM_PUBLISHED collection")
        requested.scenes = [available.scenes[0]]
        requested.collections = ["PIMM_PUBLISHED"]
    collection = requested.collections[0]
    collection.name = "PIMM_50G_HOMEPAGE_SOURCE"
    bpy.context.scene.collection.children.link(collection)
    bpy.context.view_layer.update()
    meshes, provenance = _validate_collection(bpy, collection, "50G")
    provenance.update({"master_path": str(source), "master_sha256": actual_sha256})
    return meshes, provenance, collection


def _stage_collection_root(bpy: Any, runtime: Any, collection: Any, name: str) -> Any:
    if not list(collection.all_objects):
        raise ValueError(f"cannot stage empty collection: {collection.name}")
    collection.instance_offset = (0.0, 0.0, 0.0)
    parents = [bpy.context.scene.collection, *bpy.data.collections]
    for parent in parents:
        if collection.name in parent.children:
            parent.children.unlink(collection)
    root = bpy.data.objects.new(name, None)
    root.instance_type = "COLLECTION"
    root.instance_collection = collection
    runtime.objects.link(root)
    return root


def _flatten_published_meshes(bpy: Any, meshes: Sequence[Any], name: str) -> tuple[Any, list[Any]]:
    collection = bpy.data.collections.new(name)
    duplicates = []
    for source in meshes:
        duplicate = source.copy()
        duplicate.parent = None
        duplicate.matrix_world = source.matrix_world.copy()
        collection.objects.link(duplicate)
        duplicates.append(duplicate)
    return collection, duplicates


def _hide_master_working_scene(bpy: Any) -> None:
    for obj in bpy.context.scene.objects:
        obj.hide_render = True


def _instance_bounds(meshes: Sequence[Any], root: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    from mathutils import Vector

    points = [root.matrix_world @ obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    return (
        tuple(min(point[axis] for point in points) for axis in range(3)),
        tuple(max(point[axis] for point in points) for axis in range(3)),
    )


def _stage_machine(
    meshes: Sequence[Any], root: Any, target_x: float, target_y: float, rotation_degrees: float
) -> None:
    from mathutils import Matrix

    bounds_min, bounds_max = _instance_bounds(meshes, root)
    center_x = (bounds_min[0] + bounds_max[0]) / 2
    center_y = (bounds_min[1] + bounds_max[1]) / 2
    pivot = Matrix.Translation((center_x, center_y, 0.0))
    rotation = Matrix.Rotation(math.radians(rotation_degrees), 4, "Z")
    placement = Matrix.Translation((target_x - center_x, target_y - center_y, -bounds_min[2]))
    transform = placement @ pivot @ rotation @ pivot.inverted()
    root.matrix_world = transform @ root.matrix_world


def _translate_machine(root: Any, x: float, y: float = 0.0) -> None:
    from mathutils import Matrix

    root.matrix_world = Matrix.Translation((x, y, 0.0)) @ root.matrix_world


def _place_pair_for_placement(
    bpy: Any,
    placement: str,
    primary_meshes: Sequence[Any],
    primary_root: Any,
    secondary_meshes: Sequence[Any],
    secondary_root: Any,
) -> None:
    staging = STAGING[placement]
    rotation_degrees = float(staging["rotation_degrees"])
    _stage_machine(primary_meshes, primary_root, 0.0, 0.0, rotation_degrees)
    _stage_machine(secondary_meshes, secondary_root, 0.0, 0.0, rotation_degrees)
    bpy.context.view_layer.update()
    primary_min, primary_max = _instance_bounds(primary_meshes, primary_root)
    secondary_min, secondary_max = _instance_bounds(secondary_meshes, secondary_root)
    primary_width = primary_max[0] - primary_min[0]
    secondary_width = secondary_max[0] - secondary_min[0]
    gap = (primary_width + secondary_width) * float(staging["pair_gap_ratio"])
    max_depth = max(primary_max[1] - primary_min[1], secondary_max[1] - secondary_min[1])
    depth_stagger = max_depth * float(staging["depth_stagger_ratio"])
    if staging["reverse_order"]:
        _translate_machine(secondary_root, -gap / 2.0 - secondary_max[0], depth_stagger)
        _translate_machine(primary_root, gap / 2.0 - primary_min[0], -depth_stagger)
    else:
        _translate_machine(primary_root, -gap / 2.0 - primary_max[0], depth_stagger)
        _translate_machine(secondary_root, gap / 2.0 - secondary_min[0], -depth_stagger)
    bpy.context.view_layer.update()


def _placement_camera(
    bpy: Any,
    collection: Any,
    placement: str,
    dimensions: tuple[int, int],
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
) -> Any:
    width = bounds_max[0] - bounds_min[0]
    height = bounds_max[2] - bounds_min[2]
    aspect = dimensions[0] / dimensions[1]
    lens = 72.0 if placement == "catalogue" else 80.0 if placement == "navigation" else 85.0
    horizontal_fov = 2.0 * math.atan(36.0 / (2.0 * lens))
    vertical_fov = 2.0 * math.atan((36.0 / aspect) / (2.0 * lens))
    framing_multiplier = (
        CATALOGUE_CAMERA_DISTANCE_MULTIPLIER
        if placement == "catalogue"
        else 1.10
        if placement == "hero-desktop"
        else 1.06
    )
    distance = max(
        width / (2.0 * math.tan(horizontal_fov / 2.0)),
        height / (2.0 * math.tan(vertical_fov / 2.0)),
    ) * framing_multiplier
    target = (
        (bounds_min[0] + bounds_max[0]) / 2,
        (bounds_min[1] + bounds_max[1]) / 2,
        bounds_min[2] + height * (0.46 if placement == "catalogue" else 0.49),
    )

    data = bpy.data.cameras.new(f"CAM_HOMEPAGE_{placement.upper()}")
    data.type = "PERSP"
    data.lens = lens
    data.shift_x = (
        -0.18
        if placement == "hero-desktop"
        else CATALOGUE_CAMERA_SHIFT_X
        if placement == "catalogue"
        else 0.0
    )
    data.shift_y = CATALOGUE_CAMERA_SHIFT_Y if placement == "catalogue" else 0.0
    data.sensor_width = 36.0
    data.sensor_fit = "HORIZONTAL"
    data.clip_start = 0.1
    data.clip_end = distance * 2.5
    data.dof.use_dof = True
    data.dof.aperture_fstop = 11.0
    data.dof.aperture_blades = 11
    camera = bpy.data.objects.new(data.name, data)
    collection.objects.link(camera)
    camera_height = 0.13 if placement == "catalogue" else 0.075 if placement == "navigation" else 0.04
    camera.location = (target[0], target[1] - distance, target[2] + height * camera_height)
    _look_at(camera, target)

    focus = bpy.data.objects.new(f"{data.name}_FOCUS", None)
    focus.location = target
    collection.objects.link(focus)
    data.dof.focus_object = focus
    bpy.context.scene.camera = camera
    return camera


def render(bpy: Any, arguments: argparse.Namespace) -> dict[str, object]:
    primary_source_meshes, primary_provenance = _validate_master(bpy, "30G", arguments.expected_primary_sha256)
    secondary_source_meshes, secondary_provenance, _secondary_source_collection = _append_secondary_master(
        bpy, arguments.secondary_master, arguments.expected_secondary_sha256
    )
    primary_collection, primary_meshes = _flatten_published_meshes(
        bpy, primary_source_meshes, "PIMM_30G_HOMEPAGE"
    )
    secondary_collection, secondary_meshes = _flatten_published_meshes(
        bpy, secondary_source_meshes, "PIMM_50G_HOMEPAGE"
    )
    _hide_master_working_scene(bpy)
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = tuple(arguments.placement or PLACEMENTS)
    outputs = []
    scene = bpy.context.scene
    for placement in selected:
        runtime = _runtime_collection(bpy)
        primary_root = _stage_collection_root(bpy, runtime, primary_collection, "PIMM_30G_HOMEPAGE_STAGE")
        secondary_root = _stage_collection_root(bpy, runtime, secondary_collection, "PIMM_50G_HOMEPAGE_STAGE")
        _place_pair_for_placement(
            bpy, placement, primary_meshes, primary_root, secondary_meshes, secondary_root
        )
        primary_min, primary_max = _instance_bounds(primary_meshes, primary_root)
        secondary_min, secondary_max = _instance_bounds(secondary_meshes, secondary_root)
        bounds_min = tuple(min(primary_min[axis], secondary_min[axis]) for axis in range(3))
        bounds_max = tuple(max(primary_max[axis], secondary_max[axis]) for axis in range(3))
        if abs(bounds_min[2]) > FOOT_TOLERANCE:
            raise ValueError(f"paired machines do not meet the shared z=0 plane: {bounds_min[2]}")

        _install_studio(bpy, runtime, bounds_min, bounds_max)
        cyclorama = next((obj for obj in runtime.objects if obj.name.startswith("PIMM_WHITE_CYCLORAMA")), None)
        if cyclorama is None:
            raise ValueError("runtime studio did not create its physical ground surface")
        cyclorama.is_shadow_catcher = True

        native_dimensions = PLACEMENTS[placement]
        dimensions = tuple(max(1, round(value * arguments.scale)) for value in native_dimensions)
        camera = _placement_camera(bpy, runtime, placement, dimensions, bounds_min, bounds_max)
        output = output_dir / f"{RELEASE_ID}-{placement}-alpha.png"
        if output.exists() and not arguments.replace_working_output:
            raise FileExistsError(f"refusing to overwrite homepage pair render: {output}")
        _configure_render(bpy, dimensions[0], dimensions[1], arguments.samples, output)
        scene.render.film_transparent = True
        scene.render.image_settings.color_mode = "RGBA"
        scene.view_settings.exposure = 0.35
        scene.compositing_node_group = None
        bpy.ops.render.render(write_still=True)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Blender did not create homepage pair render: {output}")
        outputs.append({
            "placement": placement,
            "path": str(output),
            "width": dimensions[0],
            "height": dimensions[1],
            "sha256": sha256_file(output),
            "composition_id": STAGING[placement]["composition_id"],
        })

    return {
        "schema": "maliev.homepage-pimm-pair-render/v1",
        "release_id": RELEASE_ID,
        "composition": "Purpose-staged 30G and 50G pair renders from one Blender scene per placement",
        "masters": {"30g": primary_provenance, "50g": secondary_provenance},
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
