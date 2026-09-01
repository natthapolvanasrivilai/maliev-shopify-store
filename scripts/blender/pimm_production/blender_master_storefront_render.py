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


RELEASE_ID = "pimm-master-20260901-r05"
RESULT_MARKER = "PIMM_MASTER_STOREFRONT_RENDER_JSON="
HDRI_PATH = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\assets\hdri\studio_kontrast_04_4k.exr"
)
HDRI_SHA256 = "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06"
EXPECTED_MASTER_NAMES = {
    "30G": "PIMM-30G-MASTER.blend",
    "50G": "PIMM-50G-MASTER.blend",
}
EXPECTED_OBJECT_COUNT = 556
FOOT_TOLERANCE = 0.0002
SHOT_NAMES = ("hero", "overview", "controls", "tooling", "configuration")


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


def _emissive_material(bpy: Any, name: str, color: tuple[float, float, float, float], strength: float) -> Any:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def _cyclorama_material(bpy: Any) -> Any:
    """White wall with a shadow-receiving matte floor and seamless transition."""
    material = bpy.data.materials.new("PIMM_WHITE_CYCLORAMA_MAT")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    diffuse = nodes.new("ShaderNodeBsdfPrincipled")
    diffuse.inputs["Base Color"].default_value = (0.82, 0.82, 0.82, 1.0)
    diffuse.inputs["Roughness"].default_value = 0.84
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    emission.inputs["Strength"].default_value = 3.5
    geometry = nodes.new("ShaderNodeNewGeometry")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    map_range = nodes.new("ShaderNodeMapRange")
    map_range.inputs["From Min"].default_value = 0.0
    map_range.inputs["From Max"].default_value = 1.0
    map_range.inputs["To Min"].default_value = 1.0
    map_range.inputs["To Max"].default_value = 0.0
    map_range.clamp = True
    mix = nodes.new("ShaderNodeMixShader")
    links.new(geometry.outputs["Normal"], separate.inputs["Vector"])
    links.new(separate.outputs["Z"], map_range.inputs["Value"])
    links.new(map_range.outputs["Result"], mix.inputs[0])
    links.new(diffuse.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], output.inputs["Surface"])
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
    extent = max(width, depth, height)

    # A real seamless sweep: the foot pads remain on z=0 and the curved wall
    # removes the synthetic horizon line while still receiving physical shadows.
    y_front = center[1] - extent * 5.5
    y_back = center[1] + extent * 1.6
    radius = extent * 0.9
    arc_center_y = y_back - radius
    arc_center_z = radius
    profile = [(y_front, 0.0), (arc_center_y, 0.0)]
    profile.extend(
        (
            arc_center_y + radius * math.sin(index * math.pi / 48.0),
            arc_center_z - radius * math.cos(index * math.pi / 48.0),
        )
        for index in range(1, 25)
    )
    profile.append((y_back, bounds_max[2] + extent * 3.2))
    half_width = extent * 7.0
    vertices = []
    for y, z in profile:
        vertices.extend(((center[0] - half_width, y, z), (center[0] + half_width, y, z)))
    faces = [(index * 2, index * 2 + 1, index * 2 + 3, index * 2 + 2) for index in range(len(profile) - 1)]
    mesh = bpy.data.meshes.new("PIMM_WHITE_CYCLORAMA_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    cyclorama = bpy.data.objects.new("PIMM_WHITE_CYCLORAMA", mesh)
    collection.objects.link(cyclorama)
    cyclorama.data.materials.append(_cyclorama_material(bpy))

    target = (center[0], center[1], bounds_min[2] + height * 0.5)
    _add_area_light(
        bpy, collection, "KEY_SOFTBOX",
        (center[0] - extent * 1.5, center[1] - extent * 1.1, bounds_min[2] + height * 1.45),
        target, 110.0, extent * 1.3, "RECTANGLE",
    )
    _add_area_light(
        bpy, collection, "FILL_SOFTBOX",
        (center[0] + extent * 1.8, center[1] - extent * 0.7, bounds_min[2] + height * 0.7),
        target, 10.0, extent * 1.6, "RECTANGLE",
    )
    _add_area_light(
        bpy, collection, "OVERHEAD_SCRIM",
        (center[0], center[1] - extent * 0.2, bounds_min[2] + height * 2.6),
        target, 8.0, extent * 2.8, "RECTANGLE",
    )
    _add_area_light(
        bpy, collection, "BACKGROUND_WASH",
        (center[0], center[1] - extent * 0.4, bounds_min[2] + height * 1.9),
        (center[0], center[1] + extent * 1.5, bounds_min[2] + height * 0.4),
        1_000.0, extent * 3.0, "RECTANGLE",
    )

    # Camera-invisible emitter cards create the long, real softbox streaks
    # that reveal curvature in polished shafts and the cylinder shell.
    for name, x, y, z, card_width, card_height, strength in (
        ("REFLECTION_CARD_LEFT", -1.7, -0.9, 0.55, 0.65, 3.2, 7.0),
        ("REFLECTION_CARD_RIGHT", 1.8, -0.6, 0.50, 0.55, 3.0, 5.0),
        ("REFLECTION_WALL_CAMERA", 0.0, -4.8, 1.0, 7.5, 4.5, 2.0),
    ):
        bpy.ops.mesh.primitive_plane_add(
            size=1.0,
            location=(center[0] + extent * x, center[1] + extent * y, bounds_min[2] + extent * z),
        )
        card = bpy.context.object
        card.name = name
        for owner in list(card.users_collection):
            owner.objects.unlink(card)
        collection.objects.link(card)
        card.scale = (extent * card_width, extent * card_height, 1.0)
        _look_at(card, target)
        card.rotation_euler.rotate_axis("X", math.radians(180.0))
        card.data.materials.append(_emissive_material(bpy, f"{name}_MAT", (1.0, 1.0, 1.0, 1.0), strength))
        for attribute, value in (
            ("visible_camera", False),
            ("visible_shadow", False),
            ("visible_diffuse", False),
            ("visible_transmission", False),
        ):
            if hasattr(card, attribute):
                setattr(card, attribute, value)

    for name, x, y, z, card_width, card_height in (
        ("NEGATIVE_FILL_LEFT", -1.05, 0.60, 0.35, 0.70, 3.2),
        ("NEGATIVE_FILL_RIGHT", 1.10, 0.55, 0.35, 0.60, 3.2),
    ):
        bpy.ops.mesh.primitive_plane_add(
            size=1.0,
            location=(center[0] + extent * x, center[1] + extent * y, bounds_min[2] + extent * z),
        )
        flag = bpy.context.object
        flag.name = name
        for owner in list(flag.users_collection):
            owner.objects.unlink(flag)
        collection.objects.link(flag)
        flag.scale = (extent * card_width, extent * card_height, 1.0)
        _look_at(flag, target)
        flag.rotation_euler.rotate_axis("X", math.radians(180.0))
        flag.data.materials.append(_material(bpy, f"{name}_MAT", (0.01, 0.01, 0.012, 1.0), 1.0))
        for attribute, value in (
            ("visible_camera", False),
            ("visible_shadow", False),
            ("visible_diffuse", False),
            ("visible_transmission", False),
        ):
            if hasattr(flag, attribute):
                setattr(flag, attribute, value)


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
        target_z, lens, fstop = height * 0.50, 95.0, 11.0
        camera_offset = (0.0, -2.88, -0.03)
    elif shot == "overview":
        aspect = (resolution, int(resolution * 0.82))
        target_z, lens, fstop = height * 0.50, 85.0, 11.0
        camera_offset = (-0.62, -2.25, 0.04)
    elif shot == "controls":
        aspect = (resolution, int(resolution * 0.78))
        target_z, lens, fstop = height * 0.70, 105.0, 8.0
        camera_offset = (-0.20, -1.40, 0.06)
    elif shot == "tooling":
        aspect = (resolution, int(resolution * 0.78))
        target_z, lens, fstop = height * 0.04, 105.0, 8.0
        camera_offset = (0.0, -1.30, 0.65)
    else:
        aspect = (resolution, int(resolution * 1.2))
        target_z, lens, fstop = height * 0.48, 90.0, 11.0
        camera_offset = (0.24, -2.84, 0.01)

    target = (center[0] + (width * 0.08 if shot == "controls" else 0.0), center[1], bounds_min[2] + target_z)
    extent = max(width, depth, height)
    location = (
        target[0] + extent * camera_offset[0],
        target[1] + extent * camera_offset[1],
        target[2] + extent * camera_offset[2],
    )
    data = bpy.data.cameras.new("CAM_STOREFRONT")
    data.type = "PERSP"
    data.lens = lens
    data.sensor_width = 36.0
    data.clip_start = 0.1
    data.clip_end = 20_000.0
    data.dof.use_dof = True
    data.dof.aperture_fstop = fstop
    data.dof.aperture_blades = 11
    camera = bpy.data.objects.new("CAM_STOREFRONT", data)
    collection.objects.link(camera)
    camera.location = location
    _look_at(camera, target)
    focus = bpy.data.objects.new("CAM_STOREFRONT_FOCUS", None)
    focus.location = target
    collection.objects.link(focus)
    data.dof.focus_object = focus
    bpy.context.scene.camera = camera
    return camera, aspect


def _configure_render(bpy: Any, width: int, height: int, samples: int, output: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
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
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.008
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 10
    scene.cycles.glossy_bounces = 6
    scene.render.use_persistent_data = True
    try:
        preferences = bpy.context.preferences.addons["cycles"].preferences
        preferences.refresh_devices()
        available = {device.type for device in preferences.devices}
        backend = "OPTIX" if "OPTIX" in available else "CUDA" if "CUDA" in available else None
        if backend is not None:
            preferences.compute_device_type = backend
            for device in preferences.devices:
                device.use = device.type == backend
            scene.cycles.device = "GPU"
    except Exception:
        scene.cycles.device = "CPU"
    scene.view_settings.look = "AgX - High Contrast"
    scene.view_settings.exposure = -0.15
    scene.view_settings.gamma = 1.0

    if not HDRI_PATH.is_file() or sha256_file(HDRI_PATH) != HDRI_SHA256:
        raise ValueError(f"approved studio HDRI is missing or changed: {HDRI_PATH}")
    world = scene.world or bpy.data.worlds.new("PIMM_STOREFRONT_WORLD")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld")
    coordinates = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value[2] = math.radians(18.0)
    environment = nodes.new("ShaderNodeTexEnvironment")
    environment.name = "PIMM_APPROVED_STUDIO_HDRI"
    environment.image = bpy.data.images.load(str(HDRI_PATH), check_existing=True)
    environment.interpolation = "Linear"
    ambient = nodes.new("ShaderNodeBackground")
    ambient.name = "PIMM_HDRI_LIGHTING"
    ambient.inputs["Strength"].default_value = 0.35
    camera_background = nodes.new("ShaderNodeBackground")
    camera_background.name = "PIMM_WHITE_CAMERA_BACKGROUND"
    camera_background.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    camera_background.inputs["Strength"].default_value = 1.0
    light_path = nodes.new("ShaderNodeLightPath")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(coordinates.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], environment.inputs["Vector"])
    links.new(environment.outputs["Color"], ambient.inputs["Color"])
    links.new(light_path.outputs["Is Camera Ray"], mix.inputs[0])
    links.new(ambient.outputs["Background"], mix.inputs[1])
    links.new(camera_background.outputs["Background"], mix.inputs[2])
    links.new(mix.outputs["Shader"], output.inputs["Surface"])

    # Subtle optical imperfections keep the render photographic without
    # compromising catalogue accuracy: mild barrel distortion, restrained
    # lateral chromatic aberration, and a tiny bloom around emissive displays.
    compositor = bpy.data.node_groups.new("PIMM_STOREFRONT_COMPOSITOR", "CompositorNodeTree")
    compositor.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    compositor_nodes = compositor.nodes
    compositor_links = compositor.links
    render_layers = compositor_nodes.new("CompositorNodeRLayers")
    render_layers.scene = scene
    lens = compositor_nodes.new("CompositorNodeLensdist")
    lens.inputs["Distortion"].default_value = 0.0025
    lens.inputs["Dispersion"].default_value = 0.0005
    lens.inputs["Fit"].default_value = True
    glare = compositor_nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Fog Glow"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = 1.4
    glare.inputs["Size"].default_value = 0.35
    glare.inputs["Strength"].default_value = 0.035
    composite = compositor_nodes.new("NodeGroupOutput")
    compositor_links.new(render_layers.outputs["Image"], lens.inputs["Image"])
    compositor_links.new(lens.outputs["Image"], glare.inputs["Image"])
    compositor_links.new(glare.outputs["Image"], composite.inputs["Image"])
    scene.compositing_node_group = compositor


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
