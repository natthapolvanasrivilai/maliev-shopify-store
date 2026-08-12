"""Build the dedicated transparent PIMM 50G light-studio project.

Run with Blender 5.2 while opening the immutable corrected source blend::

    blender -b PIMM-50g-keynote-reveal-v2-regulator-materials.blend \
      -P create_pimm50_light_studio.py -- --render-proofs

The builder saves only the dedicated target. It owns data whose names start
with ``PIMM50_LIGHT_`` and verifies the source hash and timestamp before and
after the build.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from array import array
from pathlib import Path
from typing import Iterable

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


SOURCE_BLEND = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders"
    r"\PIMM-50g-keynote-reveal-v2-regulator-materials.blend"
)
TARGET_BLEND = SOURCE_BLEND.with_name("PIMM-50g-light-studio-v1.blend")
OUTPUT_DIR = SOURCE_BLEND.parent / "renders" / "pimm50-light-studio-v1"
SOURCE_SHA256 = "C19DDA7902BE63A2B28A77D3EF349D17555642399A9589B9A06EFCC05EAB882A"
EXPECTED_MACHINE_OBJECTS = 481
PRODUCT_COLLECTION = "Machine_50g"
PREFIX = "PIMM50_LIGHT_"

FRAME_START = 1
FRAME_END = 48
FPS = 24
RENDER_SAMPLES = 48
COMPLETE_MACHINE_ALPHA_MARGIN = 0.08
ALPHA_THRESHOLD = 1.0 / 255.0
CONTACT_SHADOW_MAX_ALPHA = 0.18
CONTACT_SHADOW_RADIUS_X = 0.34
CONTACT_SHADOW_RADIUS_Y = 0.25

HERO_ANIMATION_SCENE = "PIMM50_LIGHT_HERO_ANIMATION"
HEATING_ANIMATION_SCENE = "PIMM50_LIGHT_HEATING_ANIMATION"
HEATING_POSTER_COLLECTION = "PIMM50_LIGHT_HEATING_POSTER_MACHINE"
HEATING_ANIMATION_COLLECTION = "PIMM50_LIGHT_HEATING_ANIMATION_MACHINE"

DISPLAY_MATERIALS = (
    "MAT_Display_LED_Red",
    "MAT_Display_LED_Green",
)
DISPLAY_GEOMETRY_CONTRACT = {
    "50g_314_Body2": ("MAT_Display_Black_Glass",),
    "50g_315_Body20": ("MAT_Display_LED_Red",),
    "50g_316_Body20_1": ("MAT_Display_LED_Green",),
    "50g_355_Body2_1": ("MAT_Display_Black_Glass",),
}

SCENE_SPECS = {
    "HERO": {
        "resolution": (1400, 1400),
        "target": (0.016, -0.018, 0.507),
        "distance": 1.95,
        "yaw": -17.0,
        "elevation": 0.08,
        "lens": 72.0,
        "fit": "machine",
        "complete_machine": True,
    },
    "CAPACITY": {
        "resolution": (1200, 1200),
        "target": (-0.010, 0.000, 0.835),
        "distance": 0.82,
        "yaw": -17.0,
        "elevation": 0.025,
        "lens": 82.0,
        "fit": ((-0.185, -0.180, 0.665), (0.165, 0.170, 1.015)),
        "complete_machine": False,
    },
    "MELT_ZONE": {
        "resolution": (1200, 1200),
        "target": (0.000, 0.000, 0.190),
        "distance": 0.45,
        "yaw": -20.0,
        "elevation": 0.015,
        "lens": 78.0,
        "fit": ((-0.060, -0.060, 0.080), (0.060, 0.060, 0.300)),
        "complete_machine": False,
    },
    "HEATING": {
        "resolution": (1200, 1200),
        "target": (0.187, -0.102, 0.590),
        "distance": 0.34,
        "yaw": 0.0,
        "elevation": 0.000,
        "lens": 88.0,
        "fit": ((0.145, -0.125, 0.505), (0.225, -0.070, 0.670)),
        "complete_machine": False,
    },
    "MOLD_SPACE": {
        "resolution": (1200, 1200),
        "target": (0.000, -0.005, 0.205),
        "distance": 0.82,
        "yaw": -9.0,
        "elevation": 0.035,
        "lens": 72.0,
        "fit": ((-0.185, -0.180, -0.005), (0.185, 0.160, 0.415)),
        "complete_machine": False,
    },
    "PURCHASE": {
        "resolution": (1400, 1400),
        "target": (0.016, -0.018, 0.507),
        "distance": 1.95,
        "yaw": -9.0,
        "elevation": 0.06,
        "lens": 74.0,
        "fit": "machine",
        "complete_machine": True,
    },
}

STILL_SCENES = tuple(f"{PREFIX}{name}" for name in SCENE_SPECS)
ANIMATION_SCENES = (
    HERO_ANIMATION_SCENE,
    HEATING_ANIMATION_SCENE,
)
EXPECTED_SCENES = STILL_SCENES + ANIMATION_SCENES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-proofs", action="store_true")
    parser.add_argument("--inspect-target", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def material_slots(obj: bpy.types.Object) -> tuple[str | None, ...]:
    return tuple(slot.material.name if slot.material else None for slot in obj.material_slots)


def matrix_values(obj: bpy.types.Object) -> tuple[float, ...]:
    return tuple(float(value) for row in obj.matrix_world for value in row)


def machine_contract_snapshot(collection: bpy.types.Collection) -> dict[str, object]:
    return {
        obj.name: {
            "matrix": matrix_values(obj),
            "materials": material_slots(obj),
            "hide_render": bool(obj.hide_render),
        }
        for obj in collection.all_objects
    }


def assert_source_immutable() -> tuple[str, int, bpy.types.Collection, dict[str, object]]:
    current = Path(bpy.data.filepath).resolve()
    if current != SOURCE_BLEND.resolve():
        raise RuntimeError(f"Open the corrected source blend, not {current}")
    source_hash = sha256(SOURCE_BLEND)
    if source_hash != SOURCE_SHA256:
        raise RuntimeError(f"Corrected source hash drifted: {source_hash}")
    source_mtime = SOURCE_BLEND.stat().st_mtime_ns
    collection = bpy.data.collections.get(PRODUCT_COLLECTION)
    if collection is None or len(collection.all_objects) != EXPECTED_MACHINE_OBJECTS:
        raise RuntimeError("Machine_50g 481-object contract failed")
    for object_name, expected_materials in DISPLAY_GEOMETRY_CONTRACT.items():
        obj = bpy.data.objects.get(object_name)
        if obj is None or material_slots(obj) != expected_materials:
            raise RuntimeError(f"Authentic controller geometry drifted: {object_name}")
    return source_hash, source_mtime, collection, machine_contract_snapshot(collection)


def remove_owned_data() -> None:
    """Remove only prior light-studio data, leaving every source datablock intact."""

    for scene in list(bpy.data.scenes):
        if scene.name.startswith(PREFIX):
            bpy.data.scenes.remove(scene)
    for obj in list(bpy.data.objects):
        if obj.name.startswith(PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        if collection.name.startswith(PREFIX):
            bpy.data.collections.remove(collection)

    owned_datablock_groups = (
        bpy.data.materials,
        bpy.data.worlds,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.meshes,
    )
    for group in owned_datablock_groups:
        for datablock in list(group):
            if datablock.name.startswith(PREFIX) and datablock.users == 0:
                group.remove(datablock)


def product_corners(collection: bpy.types.Collection) -> list[Vector]:
    corners: list[Vector] = []
    for obj in collection.all_objects:
        if obj.type == "MESH":
            corners.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not corners:
        raise RuntimeError("Machine_50g contains no mesh bounds")
    return corners


def box_corners(bounds: tuple[tuple[float, float, float], tuple[float, float, float]]) -> list[Vector]:
    minimum, maximum = bounds
    return [
        Vector((x, y, z))
        for x in (minimum[0], maximum[0])
        for y in (minimum[1], maximum[1])
        for z in (minimum[2], maximum[2])
    ]


def point_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def create_camera(
    collection: bpy.types.Collection,
    scene_name: str,
    spec: dict[str, object],
) -> bpy.types.Object:
    target = Vector(spec["target"])
    distance = float(spec["distance"])
    yaw = math.radians(float(spec["yaw"]))
    camera_data = bpy.data.cameras.new(f"{scene_name}_CAMERA_DATA")
    camera_data.lens = float(spec["lens"])
    camera_data.dof.use_dof = False
    camera = bpy.data.objects.new(f"{scene_name}_CAMERA", camera_data)
    collection.objects.link(camera)
    camera.location = target + Vector(
        (math.sin(yaw) * distance, -math.cos(yaw) * distance, float(spec["elevation"]))
    )
    point_at(camera, target)
    camera["pimm50_light_target"] = tuple(target)
    return camera


def fit_camera_to_points(
    scene: bpy.types.Scene,
    camera: bpy.types.Object,
    target: Vector,
    points: Iterable[Vector],
    margin: float,
) -> dict[str, float]:
    points = list(points)
    direction = (camera.location - target).normalized()
    for _ in range(100):
        camera.update_tag()
        bpy.context.view_layer.update()
        projections = [world_to_camera_view(scene, camera, point) for point in points]
        x_min = min(point.x for point in projections)
        x_max = max(point.x for point in projections)
        y_min = min(point.y for point in projections)
        y_max = max(point.y for point in projections)
        if (
            x_min >= margin
            and x_max <= 1.0 - margin
            and y_min >= margin
            and y_max <= 1.0 - margin
            and all(point.z > 0.0 for point in projections)
        ):
            return {"left": x_min, "right": 1.0 - x_max, "bottom": y_min, "top": 1.0 - y_max}
        distance = (camera.location - target).length * 1.025
        camera.location = target + direction * distance
        point_at(camera, target)
    raise RuntimeError(f"Could not fit {scene.name} camera within {margin:.1%} margin")


def create_world() -> bpy.types.World:
    world = bpy.data.worlds.new(f"{PREFIX}WORLD")
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.58, 0.61, 0.65, 1.0)
    background.inputs["Strength"].default_value = 0.05
    return world


def configure_cycles_device() -> dict[str, object]:
    preferences = bpy.context.preferences.addons["cycles"].preferences
    attempts: list[str] = []
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            preferences.compute_device_type = backend
            preferences.get_devices()
        except (TypeError, RuntimeError) as error:
            attempts.append(f"{backend}: {error}")
            continue
        devices = list(preferences.devices)
        matching = [device for device in devices if device.type == backend]
        if matching:
            for device in devices:
                device.use = device in matching
            return {
                "mode": "GPU",
                "backend": backend,
                "devices": [
                    {"name": device.name, "type": device.type, "use": bool(device.use)}
                    for device in devices
                ],
            }
    return {"mode": "CPU", "backend": None, "devices": [], "attempts": attempts}


def configure_scene(
    scene: bpy.types.Scene,
    resolution: tuple[int, int],
    world: bpy.types.World,
    device_mode: str,
) -> None:
    scene.render.engine = "CYCLES"
    scene.cycles.device = device_mode
    scene.cycles.samples = RENDER_SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.03
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    scene.render.use_file_extension = True
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.render.fps = FPS
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.20
    scene.view_settings.gamma = 1.0
    scene.world = world


def make_area_light(
    collection: bpy.types.Collection,
    name: str,
    location: Vector,
    target: Vector,
    energy: float,
    size: float,
) -> bpy.types.Object:
    light_data = bpy.data.lights.new(f"{name}_DATA", "AREA")
    light_data.energy = energy
    light_data.color = (1.0, 1.0, 1.0)
    light_data.shape = "DISK"
    light_data.size = size
    light_data.use_shadow = True
    light = bpy.data.objects.new(name, light_data)
    collection.objects.link(light)
    light.location = location
    point_at(light, target)
    return light


def create_lighting(
    collection: bpy.types.Collection,
    scene_name: str,
    target: Vector,
    closeup: bool,
) -> dict[str, bpy.types.Object]:
    scale = 0.62 if closeup else 1.0
    return {
        "key": make_area_light(
            collection,
            f"{scene_name}_KEY",
            target + Vector((-1.15, -1.45, 1.25)) * scale,
            target,
            720.0,
            1.45 * scale,
        ),
        "fill": make_area_light(
            collection,
            f"{scene_name}_FILL",
            target + Vector((1.20, -0.85, 0.78)) * scale,
            target,
            180.0,
            1.75 * scale,
        ),
        "rim": make_area_light(
            collection,
            f"{scene_name}_RIM",
            target + Vector((0.75, 1.05, 1.12)) * scale,
            target,
            460.0,
            1.10 * scale,
        ),
    }


def create_shadow_catcher(
    collection: bpy.types.Collection,
    scene_name: str,
    material: bpy.types.Material,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{scene_name}_SHADOW_MESH")
    segments = 64
    vertices = [(0.0, 0.015, -0.004)] + [
        (
            math.cos((index / segments) * math.tau) * CONTACT_SHADOW_RADIUS_X,
            0.015 + math.sin((index / segments) * math.tau) * CONTACT_SHADOW_RADIUS_Y,
            -0.004,
        )
        for index in range(segments)
    ]
    faces = [(0, index + 1, ((index + 1) % segments) + 1) for index in range(segments)]
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    ground = bpy.data.objects.new(f"{scene_name}_SHADOW_CATCHER", mesh)
    collection.objects.link(ground)
    ground.visible_shadow = False
    ground["pimm50_light_contact_shadow_fade"] = True
    return ground


def create_shadow_material() -> bpy.types.Material:
    material = bpy.data.materials.new(f"{PREFIX}SHADOW_MATERIAL")
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (0.22, 0.24, 0.27, 1.0)
    principled.inputs["Roughness"].default_value = 1.0
    texture = nodes.new("ShaderNodeTexCoord")
    texture.name = f"{PREFIX}SHADOW_COORDINATES"
    distance = nodes.new("ShaderNodeVectorMath")
    distance.name = f"{PREFIX}SHADOW_RADIAL_DISTANCE"
    distance.operation = "DISTANCE"
    distance.inputs[1].default_value = (0.5, 0.5, 0.0)
    fade = nodes.new("ShaderNodeMapRange")
    fade.name = f"{PREFIX}SHADOW_ALPHA_FADE"
    fade.clamp = True
    fade.interpolation_type = "SMOOTHERSTEP"
    fade.inputs["From Min"].default_value = 0.04
    fade.inputs["From Max"].default_value = 0.50
    fade.inputs["To Min"].default_value = CONTACT_SHADOW_MAX_ALPHA
    fade.inputs["To Max"].default_value = 0.0
    links.new(texture.outputs["Generated"], distance.inputs[0])
    links.new(distance.outputs["Value"], fade.inputs["Value"])
    links.new(fade.outputs["Result"], principled.inputs["Alpha"])
    return material


def create_scene(
    scene_name: str,
    spec: dict[str, object],
    product_collection: bpy.types.Collection,
    world: bpy.types.World,
    shadow_material: bpy.types.Material,
    device_mode: str,
    machine_points: list[Vector],
) -> dict[str, object]:
    scene = bpy.data.scenes.new(scene_name)
    scene.collection.children.link(product_collection)
    studio = bpy.data.collections.new(f"{scene_name}_STUDIO")
    scene.collection.children.link(studio)
    configure_scene(scene, tuple(spec["resolution"]), world, device_mode)
    bpy.context.window.scene = scene
    camera = create_camera(studio, scene_name, spec)
    scene.camera = camera
    target = Vector(spec["target"])
    fit_points = machine_points if spec["fit"] == "machine" else box_corners(spec["fit"])
    fit_margin = 0.16 if bool(spec["complete_machine"]) else 0.10
    geometric_margins = fit_camera_to_points(scene, camera, target, fit_points, fit_margin)
    lights = create_lighting(studio, scene_name, target, not bool(spec["complete_machine"]))
    ground = create_shadow_catcher(studio, scene_name, shadow_material)
    scene["pimm50_light_focus"] = scene_name.removeprefix(PREFIX).lower()
    scene["pimm50_light_product_collection"] = product_collection.name
    scene["pimm50_light_complete_machine"] = bool(spec["complete_machine"])
    return {
        "scene": scene,
        "camera": camera,
        "lights": lights,
        "ground": ground,
        "product_collection": product_collection,
        "geometric_margins": geometric_margins,
    }


def create_heating_product_copy(
    source_collection: bpy.types.Collection,
    variant: str,
) -> tuple[bpy.types.Collection, dict[str, bpy.types.Material], list[str]]:
    collection_name = {
        "POSTER": HEATING_POSTER_COLLECTION,
        "ANIMATION": HEATING_ANIMATION_COLLECTION,
    }[variant]
    collection = bpy.data.collections.new(collection_name)
    display_materials = {
        source_name: bpy.data.materials[source_name].copy() for source_name in DISPLAY_MATERIALS
    }
    for source_name, material in display_materials.items():
        suffix = source_name.removeprefix("MAT_Display_").upper()
        material.name = f"{PREFIX}HEATING_{variant}_DISPLAY_{suffix}"

    copies: dict[bpy.types.Object, bpy.types.Object] = {}
    display_geometry: list[str] = []
    for source_obj in sorted(source_collection.all_objects, key=lambda obj: obj.name):
        duplicate = source_obj.copy()
        duplicate.name = f"{collection_name}_{source_obj.name}"
        duplicate["pimm50_light_source_object"] = source_obj.name
        collection.objects.link(duplicate)
        copies[source_obj] = duplicate
        if source_obj.type != "MESH":
            continue
        source_materials = material_slots(source_obj)
        if not set(DISPLAY_MATERIALS).intersection(source_materials):
            continue
        duplicate.data = source_obj.data.copy()
        duplicate.data.name = f"{duplicate.name}_MESH"
        for index, material in enumerate(duplicate.data.materials):
            if material and material.name in display_materials:
                duplicate.data.materials[index] = display_materials[material.name]
        display_geometry.append(source_obj.name)

    for source_obj, duplicate in copies.items():
        if source_obj.parent in copies:
            duplicate.parent = copies[source_obj.parent]
    if not display_geometry:
        raise RuntimeError("No authentic controller display geometry was copied")
    return collection, display_materials, display_geometry


def animate_controller_materials(materials: dict[str, bpy.types.Material]) -> None:
    for source_name, material in materials.items():
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is None:
            raise RuntimeError(f"Controller material lost Principled BSDF: {source_name}")
        emission = principled.inputs.get("Emission Strength")
        if emission is None:
            raise RuntimeError(f"Controller material lost emission socket: {source_name}")
        base_color = principled.inputs.get("Base Color")
        emission_color = principled.inputs.get("Emission Color")
        if base_color is None or emission_color is None:
            raise RuntimeError(f"Controller material lost authored display colors: {source_name}")
        final_base = tuple(base_color.default_value)
        final_emission = tuple(emission_color.default_value)
        for frame, color_factor, strength in (
            (FRAME_START, 0.025, 0.0),
            (18, 0.38, 1.10),
            (FRAME_END, 1.0, 4.0),
        ):
            base_color.default_value = tuple(
                channel * color_factor if index < 3 else channel
                for index, channel in enumerate(final_base)
            )
            emission_color.default_value = tuple(
                channel * color_factor if index < 3 else channel
                for index, channel in enumerate(final_emission)
            )
            base_color.keyframe_insert(data_path="default_value", frame=frame)
            emission_color.keyframe_insert(data_path="default_value", frame=frame)
            emission.default_value = strength
            emission.keyframe_insert(data_path="default_value", frame=frame)
        material["pimm50_light_actual_display_geometry"] = True


def animate_hero_lighting(animation: dict[str, object], poster: dict[str, object]) -> None:
    for role, light in animation["lights"].items():
        final_energy = poster["lights"][role].data.energy
        for frame, factor in ((FRAME_START, 0.20), (18, 0.62), (FRAME_END, 1.0)):
            light.data.energy = final_energy * factor
            light.data.keyframe_insert(data_path="energy", frame=frame)
        light["pimm50_light_animation_channel"] = "studio_light_energy"
    animation["scene"].frame_set(FRAME_END)


def snapshot_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return tuple(snapshot_value(item) for item in value)
    except TypeError:
        return str(value)


def rna_scalar_snapshot(value: object, exclude: set[str] | None = None) -> dict[str, object]:
    excluded = {
        "rna_type",
        "name",
        "name_full",
        "id_type",
        "session_uid",
        "is_evaluated",
        "users",
        "use_fake_user",
        "use_extra_user",
        "is_embedded_data",
        "is_linked_packed",
        "is_missing",
        "is_runtime_data",
        "is_editable",
        "tag",
        "is_library_indirect",
        "is_updated",
        "is_updated_data",
        "use_nodes",
    }
    if exclude:
        excluded.update(exclude)
    snapshot: dict[str, object] = {}
    for prop in value.bl_rna.properties:
        if prop.identifier in excluded or prop.type not in {
            "BOOLEAN",
            "INT",
            "FLOAT",
            "ENUM",
            "STRING",
        }:
            continue
        try:
            snapshot[prop.identifier] = snapshot_value(getattr(value, prop.identifier))
        except (AttributeError, RuntimeError, TypeError):
            continue
    return snapshot


def node_tree_snapshot(node_tree: bpy.types.NodeTree | None) -> dict[str, object] | None:
    if node_tree is None:
        return None
    return {
        f"{node.bl_idname}:{node.name}": {
            socket.name: snapshot_value(socket.default_value)
            for socket in node.inputs
            if hasattr(socket, "default_value")
        }
        for node in sorted(node_tree.nodes, key=lambda item: (item.bl_idname, item.name))
    }


def evaluate_scene(scene: bpy.types.Scene, frame: int) -> bpy.types.Depsgraph:
    bpy.context.window.scene = scene
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    return bpy.context.evaluated_depsgraph_get()


def collection_transform_snapshot(
    collection: bpy.types.Collection,
    depsgraph: bpy.types.Depsgraph,
) -> dict[str, object]:
    return {
        str(obj.get("pimm50_light_source_object", obj.name)): {
            "matrix": matrix_values(obj.evaluated_get(depsgraph)),
            "hide_render": bool(obj.hide_render),
            "visible_camera": bool(obj.visible_camera),
            "visible_diffuse": bool(obj.visible_diffuse),
            "visible_glossy": bool(obj.visible_glossy),
            "visible_shadow": bool(obj.visible_shadow),
            "visible_transmission": bool(obj.visible_transmission),
            "visible_volume_scatter": bool(obj.visible_volume_scatter),
        }
        for obj in collection.all_objects
    }


def camera_projection_snapshot(
    build: dict[str, object],
    depsgraph: bpy.types.Depsgraph,
) -> dict[str, object]:
    camera = build["camera"].evaluated_get(depsgraph)
    return {
        "matrix": matrix_values(camera),
        "projection": rna_scalar_snapshot(camera.data),
        "dof": rna_scalar_snapshot(camera.data.dof),
        "stereo": rna_scalar_snapshot(camera.data.stereo),
        "hide_render": bool(camera.hide_render),
        "visible_camera": bool(camera.visible_camera),
        "visible_shadow": bool(camera.visible_shadow),
    }


def render_output_snapshot(scene: bpy.types.Scene) -> dict[str, object]:
    render = scene.render
    cycles = scene.cycles
    return {
        "engine": render.engine,
        "resolution": (
            render.resolution_x,
            render.resolution_y,
            render.resolution_percentage,
        ),
        "pixel_aspect": (render.pixel_aspect_x, render.pixel_aspect_y),
        "border": (
            render.use_border,
            render.use_crop_to_border,
            render.border_min_x,
            render.border_min_y,
            render.border_max_x,
            render.border_max_y,
        ),
        "film": (
            render.film_transparent,
            cycles.film_transparent_glass,
            cycles.film_transparent_roughness,
        ),
        "image_settings": rna_scalar_snapshot(render.image_settings),
        "fps": (render.fps, render.fps_base),
        "cycles": {
            "device": cycles.device,
            "samples": cycles.samples,
            "use_denoising": cycles.use_denoising,
            "use_adaptive_sampling": cycles.use_adaptive_sampling,
            "adaptive_threshold": cycles.adaptive_threshold,
            "use_light_tree": cycles.use_light_tree,
        },
    }


def lighting_snapshot(
    build: dict[str, object],
    depsgraph: bpy.types.Depsgraph,
) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for role, source_light in build["lights"].items():
        light = source_light.evaluated_get(depsgraph)
        snapshot[role] = {
            "matrix": matrix_values(light),
            "data": rna_scalar_snapshot(light.data),
            "cycles": rna_scalar_snapshot(light.data.cycles),
            "hide_render": bool(light.hide_render),
            "visible_camera": bool(light.visible_camera),
            "visible_diffuse": bool(light.visible_diffuse),
            "visible_glossy": bool(light.visible_glossy),
            "visible_shadow": bool(light.visible_shadow),
            "visible_transmission": bool(light.visible_transmission),
            "visible_volume_scatter": bool(light.visible_volume_scatter),
        }
    return snapshot


def world_snapshot(scene: bpy.types.Scene) -> dict[str, object]:
    world = scene.world
    if world is None:
        return {"world": None}
    return {
        "settings": rna_scalar_snapshot(world),
        "cycles": rna_scalar_snapshot(world.cycles),
        "uses_nodes": world.node_tree is not None,
        "nodes": node_tree_snapshot(world.node_tree),
    }


def shadow_snapshot(
    build: dict[str, object],
    depsgraph: bpy.types.Depsgraph,
) -> dict[str, object]:
    ground = build["ground"].evaluated_get(depsgraph)
    material = ground.data.materials[0]
    return {
        "matrix": matrix_values(ground),
        "hide_render": bool(ground.hide_render),
        "visible_camera": bool(ground.visible_camera),
        "visible_diffuse": bool(ground.visible_diffuse),
        "visible_glossy": bool(ground.visible_glossy),
        "visible_shadow": bool(ground.visible_shadow),
        "visible_transmission": bool(ground.visible_transmission),
        "visible_volume_scatter": bool(ground.visible_volume_scatter),
        "material_settings": rna_scalar_snapshot(material),
        "material_nodes": node_tree_snapshot(material.node_tree),
    }


def color_management_snapshot(scene: bpy.types.Scene) -> dict[str, object]:
    curve_mapping = scene.view_settings.curve_mapping
    curve_snapshot = None
    if scene.view_settings.use_curve_mapping and curve_mapping is not None:
        curve_snapshot = {
            "settings": rna_scalar_snapshot(curve_mapping),
            "curves": tuple(
                tuple(
                    (
                        float(point.location.x),
                        float(point.location.y),
                        point.handle_type,
                    )
                    for point in curve.points
                )
                for curve in curve_mapping.curves
            ),
        }
    linear_colorspace = getattr(
        scene.render.image_settings, "linear_colorspace_settings", None
    )
    return {
        "view": rna_scalar_snapshot(scene.view_settings),
        "display": rna_scalar_snapshot(scene.display_settings),
        "sequencer": rna_scalar_snapshot(scene.sequencer_colorspace_settings),
        "sequencer_colorspace_name": scene.sequencer_colorspace_settings.name,
        "image": rna_scalar_snapshot(scene.render.image_settings),
        "linear_colorspace_name": (
            linear_colorspace.name if linear_colorspace is not None else None
        ),
        "curve_mapping": curve_snapshot,
    }


def scene_parity_snapshot(build: dict[str, object], frame: int) -> dict[str, object]:
    scene = build["scene"]
    depsgraph = evaluate_scene(scene, frame)
    return {
        "camera": camera_projection_snapshot(build, depsgraph),
        "render": render_output_snapshot(scene),
        "lighting": lighting_snapshot(build, depsgraph),
        "world": world_snapshot(scene),
        "shadow": shadow_snapshot(build, depsgraph),
        "color_management": color_management_snapshot(scene),
        "product": collection_transform_snapshot(build["product_collection"], depsgraph),
    }


def assert_animation_poster_parity(
    animation: dict[str, object],
    poster: dict[str, object],
) -> None:
    animation_snapshot = scene_parity_snapshot(animation, FRAME_END)
    poster_snapshot = scene_parity_snapshot(poster, FRAME_START)
    if animation_snapshot != poster_snapshot:
        differing = [
            key
            for key in animation_snapshot
            if animation_snapshot[key] != poster_snapshot[key]
        ]
        raise RuntimeError(
            f"{animation['scene'].name} final parity drifted from "
            f"{poster['scene'].name}: {differing}"
        )


def assert_poster_materials_unanimated(
    build: dict[str, object],
    materials: dict[str, bpy.types.Material],
) -> None:
    collection = build["product_collection"]
    used_materials = {
        material.name: material
        for obj in collection.all_objects
        if getattr(obj, "data", None) is not None
        and hasattr(obj.data, "materials")
        for material in obj.data.materials
        if material is not None
    }
    used_materials.update({material.name: material for material in materials.values()})
    scene = build["scene"]
    scene_objects = [
        build["camera"],
        build["ground"],
        *build["lights"].values(),
    ]
    datablocks: list[object] = [
        scene,
        scene.world,
        collection,
        *scene_objects,
        *(obj.data for obj in scene_objects),
        *collection.all_objects,
        *used_materials.values(),
    ]
    datablocks.extend(
        obj.data for obj in collection.all_objects if getattr(obj, "data", None) is not None
    )
    datablocks.extend(
        material.node_tree
        for material in used_materials.values()
        if material.node_tree is not None
    )
    animated = [
        getattr(datablock, "name", type(datablock).__name__)
        for datablock in datablocks
        if getattr(datablock, "animation_data", None) is not None
    ]
    if animated:
        raise RuntimeError(f"Heating poster contains animation data: {animated}")


def display_material_snapshot(
    materials: dict[str, bpy.types.Material],
) -> dict[str, object]:
    return {
        source_name: {
            "settings": rna_scalar_snapshot(material),
            "nodes": node_tree_snapshot(material.node_tree),
        }
        for source_name, material in sorted(materials.items())
    }


def assert_heating_material_parity_at_final(
    animation_scene: bpy.types.Scene,
    poster_materials: dict[str, bpy.types.Material],
    animation_materials: dict[str, bpy.types.Material],
) -> None:
    evaluate_scene(animation_scene, FRAME_END)
    poster_snapshot = display_material_snapshot(poster_materials)
    animation_snapshot = display_material_snapshot(animation_materials)
    if poster_snapshot != animation_snapshot:
        differing = {
            source_name: {
                key: (
                    poster_snapshot[source_name][key],
                    animation_snapshot[source_name][key],
                )
                for key in poster_snapshot[source_name]
                if poster_snapshot[source_name][key] != animation_snapshot[source_name][key]
            }
            for source_name in poster_snapshot
            if poster_snapshot[source_name] != animation_snapshot[source_name]
        }
        raise RuntimeError(
            f"Heating poster materials drifted from animation frame 48: {differing}"
        )


def assert_scene_contract(
    builds: dict[str, dict[str, object]],
    original_collection: bpy.types.Collection,
    original_snapshot: dict[str, object],
    poster_materials: dict[str, bpy.types.Material],
    animation_materials: dict[str, bpy.types.Material],
) -> None:
    actual_scenes = sorted(scene.name for scene in bpy.data.scenes if scene.name.startswith(PREFIX))
    if actual_scenes != sorted(EXPECTED_SCENES):
        raise RuntimeError(f"Light-studio scene contract failed: {actual_scenes}")
    for build in builds.values():
        scene = build["scene"]
        if scene.render.image_settings.file_format != "PNG":
            raise RuntimeError(f"{scene.name} must render PNG")
        if scene.render.image_settings.color_mode != "RGBA" or not scene.render.film_transparent:
            raise RuntimeError(f"{scene.name} must render transparent RGBA")
        if scene.view_settings.look != "AgX - Medium High Contrast":
            raise RuntimeError(f"{scene.name} color look drifted")
        if not build["ground"].get("pimm50_light_contact_shadow_fade", False):
            raise RuntimeError(f"{scene.name} contact shadow must use a finite alpha fade")
    if any(obj.type == "FONT" for obj in bpy.data.objects if obj.name.startswith(PREFIX)):
        raise RuntimeError("Controller digits must use actual mesh geometry, not text objects")
    if machine_contract_snapshot(original_collection) != original_snapshot:
        raise RuntimeError("Original Machine_50g transforms or material slots changed in memory")

    if builds["HEATING"]["product_collection"] is builds["HEATING_ANIMATION"]["product_collection"]:
        raise RuntimeError("Heating poster and animation must use isolated product collections")
    if {
        material.as_pointer() for material in poster_materials.values()
    }.intersection(material.as_pointer() for material in animation_materials.values()):
        raise RuntimeError("Heating poster and animation must use isolated display materials")
    assert_poster_materials_unanimated(builds["HEATING"], poster_materials)
    assert_heating_material_parity_at_final(
        builds["HEATING_ANIMATION"]["scene"], poster_materials, animation_materials
    )
    assert_animation_poster_parity(builds["HERO_ANIMATION"], builds["HERO"])
    assert_animation_poster_parity(builds["HEATING_ANIMATION"], builds["HEATING"])


def alpha_bounds(path: Path) -> dict[str, object]:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        width, height = image.size
        if image.channels != 4:
            raise RuntimeError(f"Proof is not RGBA: {path}")
        pixels = array("f", [0.0]) * (width * height * image.channels)
        image.pixels.foreach_get(pixels)
        alpha_indices = [
            pixel_index
            for pixel_index, value_index in enumerate(range(3, len(pixels), image.channels))
            if pixels[value_index] > ALPHA_THRESHOLD
        ]
        if not alpha_indices:
            raise RuntimeError(f"Proof has no non-transparent pixels: {path}")
        x_values = [index % width for index in alpha_indices]
        y_values = [index // width for index in alpha_indices]
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        margins = {
            "left": x_min,
            "top": height - 1 - y_max,
            "right": width - 1 - x_max,
            "bottom": y_min,
        }
        corners = {
            "bottom_left": float(pixels[3]),
            "bottom_right": float(pixels[(width - 1) * image.channels + 3]),
            "top_left": float(pixels[((height - 1) * width) * image.channels + 3]),
            "top_right": float(pixels[((height * width) - 1) * image.channels + 3]),
        }
        return {
            "width": width,
            "height": height,
            "bbox_top_left_xyxy": [x_min, margins["top"], x_max, height - 1 - y_min],
            "margins_px": margins,
            "alpha_pixel_fraction": round(len(alpha_indices) / (width * height), 6),
            "corner_alpha": corners,
            "rectangular_alpha": all(value > ALPHA_THRESHOLD for value in corners.values()),
        }
    finally:
        bpy.data.images.remove(image)


def assert_complete_machine_margin(scene_name: str, bounds: dict[str, object]) -> None:
    required_x = math.ceil(bounds["width"] * COMPLETE_MACHINE_ALPHA_MARGIN)
    required_y = math.ceil(bounds["height"] * COMPLETE_MACHINE_ALPHA_MARGIN)
    margins = bounds["margins_px"]
    if (
        margins["left"] < required_x
        or margins["right"] < required_x
        or margins["top"] < required_y
        or margins["bottom"] < required_y
    ):
        raise RuntimeError(
            f"{scene_name} alpha breathing room is below 8%: {margins}, "
            f"required x={required_x}, y={required_y}"
        )


def assert_finite_alpha_bounds(
    scene_name: str,
    bounds: dict[str, object],
    complete_machine: bool,
) -> None:
    if bounds["rectangular_alpha"]:
        raise RuntimeError(f"{scene_name} proof has rectangular alpha")
    if not 0.0 < bounds["alpha_pixel_fraction"] < 1.0:
        raise RuntimeError(
            f"{scene_name} proof alpha is not finite: {bounds['alpha_pixel_fraction']}"
        )
    if complete_machine:
        assert_complete_machine_margin(scene_name, bounds)


def render_one(
    scene: bpy.types.Scene,
    output: Path,
    frame: int,
    complete_machine: bool,
) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.window.scene = scene
    scene.frame_set(frame)
    scene.render.filepath = str(output)
    started = time.perf_counter()
    bpy.ops.render.render(write_still=True, scene=scene.name)
    elapsed = time.perf_counter() - started
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Proof render missing: {output}")
    bounds = alpha_bounds(output)
    assert_finite_alpha_bounds(scene.name, bounds, complete_machine)
    return {
        "scene": scene.name,
        "frame": frame,
        "path": str(output),
        "elapsed_seconds": round(elapsed, 3),
        "alpha": bounds,
    }


def render_proofs(builds: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    proofs: list[dict[str, object]] = []
    for name in SCENE_SPECS:
        build = builds[name]
        frame = FRAME_START
        output = OUTPUT_DIR / "proofs" / f"pimm50-light-{name.lower().replace('_', '-')}.png"
        proofs.append(
            render_one(
                build["scene"],
                output,
                frame,
                bool(SCENE_SPECS[name]["complete_machine"]),
            )
        )

    for name, slug in (("HERO_ANIMATION", "hero"), ("HEATING_ANIMATION", "heating")):
        for frame in (FRAME_START, FRAME_END):
            output = OUTPUT_DIR / "frames" / slug / f"pimm50-light-{slug}-f{frame:03d}.png"
            proofs.append(
                render_one(
                    builds[name]["scene"],
                    output,
                    frame,
                    name == "HERO_ANIMATION",
                )
            )
    return proofs


def build_summary(
    builds: dict[str, dict[str, object]],
    source_hash: str,
    source_mtime: int,
    device: dict[str, object],
    poster_display_geometry: list[str],
    animation_display_geometry: list[str],
    poster_materials: dict[str, bpy.types.Material],
    animation_materials: dict[str, bpy.types.Material],
    proofs: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "blender_version": bpy.app.version_string,
        "source": str(SOURCE_BLEND),
        "source_sha256": source_hash,
        "source_mtime_ns": source_mtime,
        "source_unchanged": (
            sha256(SOURCE_BLEND) == source_hash and SOURCE_BLEND.stat().st_mtime_ns == source_mtime
        ),
        "target": str(TARGET_BLEND),
        "product_collection": PRODUCT_COLLECTION,
        "machine_objects": len(bpy.data.collections[PRODUCT_COLLECTION].all_objects),
        "scenes": sorted(scene.name for scene in bpy.data.scenes if scene.name.startswith(PREFIX)),
        "render_device": device,
        "render": {
            name: {
                "scene": build["scene"].name,
                "camera": build["camera"].name,
                "resolution": [
                    build["scene"].render.resolution_x,
                    build["scene"].render.resolution_y,
                ],
                "engine": build["scene"].render.engine,
                "samples": build["scene"].cycles.samples,
                "film_transparent": build["scene"].render.film_transparent,
                "color_mode": build["scene"].render.image_settings.color_mode,
                "look": build["scene"].view_settings.look,
                "camera_matrix": matrix_values(build["camera"]),
                "geometric_margins": build["geometric_margins"],
            }
            for name, build in builds.items()
        },
        "animations": {
            "hero": {
                "scene": builds["HERO_ANIMATION"]["scene"].name,
                "frames": [FRAME_START, FRAME_END],
                "channels": "studio area-light energy only",
                "poster_parity": True,
            },
            "heating": {
                "scene": builds["HEATING_ANIMATION"]["scene"].name,
                "frames": [FRAME_START, FRAME_END],
                "channels": "emission strength on copied actual display-geometry materials",
                "poster_parity": True,
                "poster_collection": builds["HEATING"]["product_collection"].name,
                "animation_collection": builds["HEATING_ANIMATION"]["product_collection"].name,
                "collections_isolated": (
                    builds["HEATING"]["product_collection"]
                    is not builds["HEATING_ANIMATION"]["product_collection"]
                ),
                "poster_materials_unanimated": all(
                    material.animation_data is None
                    and (
                        material.node_tree is None
                        or material.node_tree.animation_data is None
                    )
                    for material in poster_materials.values()
                ),
                "poster_source_display_geometry": poster_display_geometry,
                "animation_source_display_geometry": animation_display_geometry,
                "source_display_materials": list(DISPLAY_MATERIALS),
                "poster_material_names": sorted(
                    material.name for material in poster_materials.values()
                ),
                "animation_material_names": sorted(
                    material.name for material in animation_materials.values()
                ),
            },
        },
        "proofs": proofs,
    }


def rehydrate_persisted_builds() -> dict[str, dict[str, object]]:
    scene_by_key = {
        name: bpy.data.scenes[f"{PREFIX}{name}"] for name in SCENE_SPECS
    }
    scene_by_key["HERO_ANIMATION"] = bpy.data.scenes[HERO_ANIMATION_SCENE]
    scene_by_key["HEATING_ANIMATION"] = bpy.data.scenes[HEATING_ANIMATION_SCENE]
    builds: dict[str, dict[str, object]] = {}
    for name, scene in scene_by_key.items():
        builds[name] = {
            "scene": scene,
            "camera": scene.camera,
            "lights": {
                role: bpy.data.objects[f"{scene.name}_{role.upper()}"]
                for role in ("key", "fill", "rim")
            },
            "ground": bpy.data.objects[f"{scene.name}_SHADOW_CATCHER"],
            "product_collection": bpy.data.collections[
                scene["pimm50_light_product_collection"]
            ],
        }
    return builds


def persisted_heating_materials(variant: str) -> dict[str, bpy.types.Material]:
    return {
        source_name: bpy.data.materials[
            f"{PREFIX}HEATING_{variant}_DISPLAY_"
            f"{source_name.removeprefix('MAT_Display_').upper()}"
        ]
        for source_name in DISPLAY_MATERIALS
    }


def inspect_persisted_target() -> None:
    if Path(bpy.data.filepath).resolve() != TARGET_BLEND.resolve():
        raise RuntimeError(f"Open the persisted target blend, not {bpy.data.filepath}")
    builds = rehydrate_persisted_builds()
    source_collection = bpy.data.collections[PRODUCT_COLLECTION]
    poster_materials = persisted_heating_materials("POSTER")
    animation_materials = persisted_heating_materials("ANIMATION")
    assert_scene_contract(
        builds,
        source_collection,
        machine_contract_snapshot(source_collection),
        poster_materials,
        animation_materials,
    )
    print("PIMM50_LIGHT_STUDIO_PERSISTED_INSPECTION_BEGIN")
    print(
        json.dumps(
            {
                "target": str(TARGET_BLEND),
                "scenes": sorted(build["scene"].name for build in builds.values()),
                "poster_collection": builds["HEATING"]["product_collection"].name,
                "animation_collection": builds["HEATING_ANIMATION"][
                    "product_collection"
                ].name,
                "collections_isolated": (
                    builds["HEATING"]["product_collection"]
                    is not builds["HEATING_ANIMATION"]["product_collection"]
                ),
                "poster_materials_unanimated": all(
                    material.animation_data is None
                    and material.node_tree.animation_data is None
                    for material in poster_materials.values()
                ),
                "animation_materials_animated": all(
                    material.node_tree.animation_data is not None
                    for material in animation_materials.values()
                ),
                "frame_48_comprehensive_parity": True,
            },
            indent=2,
        )
    )
    print("PIMM50_LIGHT_STUDIO_PERSISTED_INSPECTION_END")


def main() -> None:
    args = parse_args()
    if args.inspect_target:
        inspect_persisted_target()
        return
    source_hash, source_mtime, source_collection, source_snapshot = assert_source_immutable()
    remove_owned_data()
    device = configure_cycles_device()
    world = create_world()
    shadow_material = create_shadow_material()
    machine_points = product_corners(source_collection)
    (
        heating_poster_collection,
        poster_display_materials,
        poster_display_geometry,
    ) = create_heating_product_copy(source_collection, "POSTER")
    (
        heating_animation_collection,
        animation_display_materials,
        animation_display_geometry,
    ) = create_heating_product_copy(
        source_collection, "ANIMATION"
    )

    builds: dict[str, dict[str, object]] = {}
    for name, spec in SCENE_SPECS.items():
        product = heating_poster_collection if name == "HEATING" else source_collection
        builds[name] = create_scene(
            f"{PREFIX}{name}",
            spec,
            product,
            world,
            shadow_material,
            device["mode"],
            machine_points,
        )

    builds["HERO_ANIMATION"] = create_scene(
        HERO_ANIMATION_SCENE,
        SCENE_SPECS["HERO"],
        source_collection,
        world,
        shadow_material,
        device["mode"],
        machine_points,
    )
    builds["HEATING_ANIMATION"] = create_scene(
        HEATING_ANIMATION_SCENE,
        SCENE_SPECS["HEATING"],
        heating_animation_collection,
        world,
        shadow_material,
        device["mode"],
        machine_points,
    )
    animate_hero_lighting(builds["HERO_ANIMATION"], builds["HERO"])
    animate_controller_materials(animation_display_materials)
    assert_scene_contract(
        builds,
        source_collection,
        source_snapshot,
        poster_display_materials,
        animation_display_materials,
    )

    TARGET_BLEND.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET_BLEND), check_existing=False)
    proofs = render_proofs(builds) if args.render_proofs else []
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET_BLEND), check_existing=False)

    if sha256(SOURCE_BLEND) != source_hash or SOURCE_BLEND.stat().st_mtime_ns != source_mtime:
        raise RuntimeError("Corrected source changed during light-studio build")
    summary = build_summary(
        builds,
        source_hash,
        source_mtime,
        device,
        poster_display_geometry,
        animation_display_geometry,
        poster_display_materials,
        animation_display_materials,
        proofs,
    )
    print("PIMM50_LIGHT_STUDIO_SUMMARY_BEGIN")
    print(json.dumps(summary, indent=2))
    print("PIMM50_LIGHT_STUDIO_SUMMARY_END")


if __name__ == "__main__":
    main()
