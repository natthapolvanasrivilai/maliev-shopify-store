"""Build the transparent, looping PIMM 50G red-stage production scene.

Run from the copied production file, never from the corrected source master:

    blender -b PIMM-50g-red-stage-loop.blend \
      -P create_pimm50_red_stage.py -- --render-proofs

The builder is deliberately idempotent. It owns only stage data carrying the
``PIMM50_RED_STAGE_`` prefix plus the four exact, owner-tagged stage
collections required by the production brief. The authentic machine geometry
and all of its existing material slots are treated as immutable inputs.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import warnings
from pathlib import Path
from typing import Iterable

import bpy
from mathutils import Vector

warnings.filterwarnings("ignore", category=DeprecationWarning)


# Authentic corrected-source contract. These values were inspected directly
# in PIMM-50g-keynote-reveal-v2-regulator-materials.blend on 2026-08-06.
SOURCE_BLEND = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders"
    r"\PIMM-50g-keynote-reveal-v2-regulator-materials.blend"
)
TARGET_BLEND = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders"
    r"\PIMM-50g-red-stage-loop.blend"
)
PRODUCT_COLLECTION = "Machine_50g"
EXPECTED_MACHINE_MESH_COUNT = 481
EXPECTED_PRODUCT_BOUNDS_METRES = (
    (-0.1910000145, -0.1900000125, 0.0),
    (0.2233795673, 0.1550000012, 1.0145000219),
)

REGULATOR_MATERIAL_CONTRACT = {
    # Pressure-regulator body: corrected black powder-coated steel.
    "50g_062_Body1_117": ("MAT_Black_Powdercoat",),
    # Pressure-regulator mounting plate: corrected stainless steel.
    "50g_059_Body1_114": ("MAT_Stainless_Steel_Smooth",),
    # Pressure-regulator machined mounting body/bracket: corrected aluminium.
    "50g_052_Body1_108": ("MAT_Machined_Aluminium_Enclosure",),
}

PREFIX = "PIMM50_RED_STAGE_"
ROOT_COLLECTION = f"{PREFIX}ROOT"
STAGE_COLLECTIONS = (
    "RED_STAGE_LIGHTS",
    "RED_STAGE_FOG",
    "RED_STAGE_GROUND",
    "RED_STAGE_CAMERAS",
)
OWNER_PROPERTY = "pimm50_red_stage_owned"

DESKTOP_SCENE = f"{PREFIX}DESKTOP"
MOBILE_SCENE = f"{PREFIX}MOBILE"
DESKTOP_CAMERA = f"{PREFIX}DESKTOP_CAMERA"
MOBILE_CAMERA = f"{PREFIX}MOBILE_CAMERA"
SHARED_TARGET = f"{PREFIX}CAMERA_TARGET"
MACHINE_INSTANCE = f"{PREFIX}MACHINE_50G"
SHADOW_CATCHER = f"{PREFIX}SHADOW_CATCHER"
KEY_LIGHT = f"{PREFIX}KEY_5000K"
FILL_LIGHT = f"{PREFIX}FILL_5000K"
RED_BACKLIGHT = f"{PREFIX}RED_REAR_EFFECT"
FOG_VOLUME = f"{PREFIX}FOG_VOLUME"
FOG_MATERIAL = f"{PREFIX}FOG_MATERIAL"
GROUND_MATERIAL = f"{PREFIX}GROUND_MATERIAL"
WORLD_NAME = f"{PREFIX}WORLD"

DESKTOP_OUTPUT = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders"
    r"\renders\product-story\50g-red-stage\desktop"
)
MOBILE_OUTPUT = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders"
    r"\renders\product-story\50g-red-stage\mobile"
)
PROOF_FRAMES = (1, 20, 84, 101, 121)

FPS = 24
FRAME_START = 1
FRAME_END = 120
LOOP_BOUNDARY_FRAME = 121
CYCLES_SAMPLES = 128
LIGHT_TEMPERATURE_K = 5000
CAMERA_EXPOSURE_EV = -0.35

# One fixed camera and one exposure per composition; depth of field is off so
# the complete machine remains sharp from its feet to its top cylinder.
CAMERA_SPECS = {
    "desktop": {
        "name": DESKTOP_CAMERA,
        "location": (0.55, -4.25, 0.58),
        "lens_mm": 72.0,
        "sensor_fit": "HORIZONTAL",
        "resolution": (2400, 1350),
        "scene": DESKTOP_SCENE,
        "output": DESKTOP_OUTPUT,
    },
    "mobile": {
        "name": MOBILE_CAMERA,
        "location": (0.38, -2.90, 0.57),
        "lens_mm": 77.0,
        "sensor_fit": "VERTICAL",
        "resolution": (1350, 1800),
        "scene": MOBILE_SCENE,
        "output": MOBILE_OUTPUT,
    },
}
CAMERA_TARGET_LOCATION = (0.012, -0.006, 0.500)
MACHINE_ROTATION_Z_DEGREES = -11.0

RED_LIGHT_KEYFRAMES = (
    (1, 180.0),
    (20, 180.0),
    (84, 1050.0),
    (101, 520.0),
    (121, 180.0),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--render-proofs",
        action="store_true",
        help="Render frames 1, 20, 84, 101 and 121 for both cameras.",
    )
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def material_slots(obj: bpy.types.Object) -> tuple[str | None, ...]:
    return tuple(material.name if material else None for material in obj.data.materials)


def assert_running_from_target() -> None:
    current = Path(bpy.data.filepath)
    if not current:
        raise RuntimeError("The red-stage builder must run from a saved .blend file.")
    if current.resolve() == SOURCE_BLEND.resolve():
        raise RuntimeError(
            "Refusing to modify the corrected source master. Run this script from "
            f"the independent target copy: {TARGET_BLEND}"
        )
    if current.resolve() != TARGET_BLEND.resolve():
        raise RuntimeError(
            f"Unexpected input file {current}. Expected the production copy {TARGET_BLEND}."
        )
    if not SOURCE_BLEND.is_file():
        raise RuntimeError(f"Corrected source master is missing: {SOURCE_BLEND}")


def collection_mesh_objects(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    return [obj for obj in collection.all_objects if obj.type == "MESH"]


def world_bounds(objects: Iterable[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [
        obj.matrix_world @ Vector(corner)
        for obj in objects
        for corner in obj.bound_box
    ]
    if not points:
        raise RuntimeError("Cannot calculate bounds for an empty object set.")
    return (
        Vector(min(point[axis] for point in points) for axis in range(3)),
        Vector(max(point[axis] for point in points) for axis in range(3)),
    )


def assert_close_vector(
    actual: Vector, expected: tuple[float, float, float], tolerance: float = 1e-5
) -> None:
    if any(abs(actual[index] - expected[index]) > tolerance for index in range(3)):
        raise RuntimeError(f"Product bounds drifted: expected {expected}, got {tuple(actual)}")


def assert_machine_contract() -> tuple[bpy.types.Collection, dict[str, tuple[str | None, ...]]]:
    collection = bpy.data.collections.get(PRODUCT_COLLECTION)
    if collection is None:
        raise RuntimeError(f"Expected authentic product collection {PRODUCT_COLLECTION!r} is absent.")

    meshes = collection_mesh_objects(collection)
    if len(meshes) != EXPECTED_MACHINE_MESH_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_MACHINE_MESH_COUNT} meshes in {PRODUCT_COLLECTION}, "
            f"found {len(meshes)}. Refusing to build from unknown geometry."
        )

    minimum, maximum = world_bounds(meshes)
    assert_close_vector(minimum, EXPECTED_PRODUCT_BOUNDS_METRES[0])
    assert_close_vector(maximum, EXPECTED_PRODUCT_BOUNDS_METRES[1])

    snapshot = {obj.name: material_slots(obj) for obj in meshes}
    for object_name, expected_slots in REGULATOR_MATERIAL_CONTRACT.items():
        obj = bpy.data.objects.get(object_name)
        if obj is None or obj.name not in snapshot:
            raise RuntimeError(f"Expected regulator object {object_name!r} is absent.")
        actual_slots = snapshot[obj.name]
        if actual_slots != expected_slots:
            raise RuntimeError(
                f"Corrected regulator contract failed for {object_name}: "
                f"expected {expected_slots}, found {actual_slots}. No materials were changed."
            )

    return collection, snapshot


def remove_prefixed_data() -> None:
    """Delete only stage data carrying the production prefix."""

    for scene in tuple(bpy.data.scenes):
        if scene.name.startswith(PREFIX):
            bpy.data.scenes.remove(scene)

    for obj in tuple(bpy.data.objects):
        if obj.name.startswith(PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)

    for collection in tuple(bpy.data.collections):
        if collection.name.startswith(PREFIX):
            bpy.data.collections.remove(collection)

    typed_blocks = (
        bpy.data.meshes,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.materials,
        bpy.data.worlds,
        bpy.data.node_groups,
    )
    for blocks in typed_blocks:
        for block in tuple(blocks):
            if block.name.startswith(PREFIX):
                blocks.remove(block)


def get_owned_stage_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        collection[OWNER_PROPERTY] = True
    elif not collection.get(OWNER_PROPERTY, False):
        raise RuntimeError(
            f"Collection {name!r} already exists but is not owned by this builder. "
            "Refusing to reuse or delete intentional work."
        )
    if collection.objects:
        unexpected = [obj.name for obj in collection.objects]
        raise RuntimeError(
            f"Stage collection {name!r} contains non-prefixed objects after cleanup: {unexpected}"
        )
    return collection


def link_object(collection: bpy.types.Collection, obj: bpy.types.Object) -> bpy.types.Object:
    collection.objects.link(obj)
    return obj


def orient_towards(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def kelvin_to_linear_rgb(kelvin: float) -> tuple[float, float, float]:
    """Return a deterministic, physically plausible 5000 K light colour."""

    temperature = kelvin / 100.0
    if temperature <= 66.0:
        red = 255.0
        green = 99.4708025861 * math.log(temperature) - 161.1195681661
        blue = 0.0 if temperature <= 19.0 else 138.5177312231 * math.log(temperature - 10.0) - 305.0447927307
    else:
        red = 329.698727446 * (temperature - 60.0) ** -0.1332047592
        green = 288.1221695283 * (temperature - 60.0) ** -0.0755148492
        blue = 255.0

    def linear(channel: float) -> float:
        srgb = max(0.0, min(255.0, channel)) / 255.0
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    return linear(red), linear(green), linear(blue)


def create_area_light(
    collection: bpy.types.Collection,
    name: str,
    location: tuple[float, float, float],
    energy: float,
    size: float,
    target: Vector,
) -> bpy.types.Object:
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.color = kelvin_to_linear_rgb(LIGHT_TEMPERATURE_K)
    data.shape = "DISK"
    data.size = size
    data.use_shadow = True
    obj = link_object(collection, bpy.data.objects.new(name, data))
    obj.location = location
    orient_towards(obj, target)
    obj["temperature_kelvin"] = LIGHT_TEMPERATURE_K
    return obj


def keyframe_energy(light: bpy.types.Object, values: Iterable[tuple[int, float]]) -> None:
    for frame, energy in values:
        light.data.energy = energy
        light.data.keyframe_insert("energy", frame=frame)
    action = light.data.animation_data.action
    # Blender 5.0+ stores F-curves in layered action channelbags. Retain the
    # legacy path so the production script remains usable in Blender 4.x too.
    if hasattr(action, "fcurves"):
        curves = list(action.fcurves)
    else:
        curves = []
        for layer in action.layers:
            for strip in layer.strips:
                if strip.type != "KEYFRAME":
                    continue
                for slot in action.slots:
                    channelbag = strip.channelbag(slot)
                    if channelbag is not None:
                        curves.extend(channelbag.fcurves)
    if not curves:
        raise RuntimeError("Red-light animation created no editable F-curves.")
    for curve in curves:
        for point in curve.keyframe_points:
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"


def create_lighting(collection: bpy.types.Collection, target: Vector) -> dict[str, bpy.types.Object]:
    # Exactly one dominant neutral key from camera-left.
    key = create_area_light(
        collection,
        KEY_LIGHT,
        (-0.58, -0.62, 3.60),
        energy=850.0,
        size=1.50,
        target=target,
    )
    key.data.volume_factor = 0.0
    # Same-temperature fill only, under one quarter of key energy.
    fill = create_area_light(
        collection,
        FILL_LIGHT,
        (0.92, -0.95, 1.18),
        energy=145.0,
        size=1.40,
        target=target,
    )
    fill.data.volume_factor = 0.0

    red_data = bpy.data.lights.new(name=RED_BACKLIGHT, type="AREA")
    red_data.color = (1.0, 0.004, 0.004)
    red_data.energy = RED_LIGHT_KEYFRAMES[0][1]
    red_data.shape = "DISK"
    red_data.size = 0.70
    red_data.use_shadow = True
    # This is a genuine volume-only rear light. Surface factors remain zero as
    # a second hard boundary in addition to collection light linking.
    red_data.diffuse_factor = 0.0
    red_data.specular_factor = 0.0
    red_data.transmission_factor = 0.0
    # Preserve a real rear area light while making smooth in-volume emission do
    # most of the visible work. A small direct-scatter contribution avoids the
    # grainy grey veil produced by lighting a large participating medium.
    red_data.volume_factor = 0.02
    red = link_object(collection, bpy.data.objects.new(RED_BACKLIGHT, red_data))
    red.location = (0.035, 0.620, 0.720)
    orient_towards(red, Vector((0.035, 0.355, 0.660)))
    red.hide_render = False
    red["role"] = "volume-only rear red backlight"
    keyframe_energy(red, RED_LIGHT_KEYFRAMES)
    return {"key": key, "fill": fill, "red": red}


def create_fog_material(red_light: bpy.types.Object) -> bpy.types.Material:
    material = bpy.data.materials.new(FOG_MATERIAL)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = f"{PREFIX}FOG_OUTPUT"
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.name = f"{PREFIX}PRINCIPLED_VOLUME"
    volume.inputs["Color"].default_value = (0.22, 0.004, 0.002, 1.0)
    volume.inputs["Anisotropy"].default_value = 0.08
    volume.inputs["Emission Color"].default_value = (1.0, 0.002, 0.001, 1.0)
    volume.inputs["Emission Strength"].default_value = 0.0

    texcoord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.name = f"{PREFIX}PERIODIC_MAPPING"
    # Keep the 4D field coherent through the shallow volume depth so camera
    # integration preserves smoke lobes instead of averaging them to a glow.
    mapping.inputs["Scale"].default_value = (1.0, 0.18, 1.0)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = f"{PREFIX}PERIODIC_NOISE"
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = 2.25
    noise.inputs["Detail"].default_value = 2.1
    noise.inputs["Roughness"].default_value = 0.48
    noise.inputs["Distortion"].default_value = 0.65

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.name = f"{PREFIX}FOG_SHAPING"
    ramp.color_ramp.interpolation = "EASE"
    ramp.color_ramp.elements[0].position = 0.40
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp.color_ramp.elements[1].position = 0.64
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)

    edge_distance = nodes.new("ShaderNodeVectorMath")
    edge_distance.name = f"{PREFIX}EDGE_DISTANCE"
    edge_distance.operation = "DISTANCE"
    edge_distance.inputs[1].default_value = (0.5, 0.5, 0.5)

    edge_falloff = nodes.new("ShaderNodeMapRange")
    edge_falloff.name = f"{PREFIX}EDGE_FALLOFF"
    edge_falloff.clamp = True
    edge_falloff.inputs["From Min"].default_value = 0.15
    # A normalized cube face is 0.5 from centre. Reaching zero there removes
    # all visible volume-box boundaries in alpha.
    edge_falloff.inputs["From Max"].default_value = 0.40
    edge_falloff.inputs["To Min"].default_value = 1.0
    edge_falloff.inputs["To Max"].default_value = 0.0

    shaped_fog = nodes.new("ShaderNodeMath")
    shaped_fog.name = f"{PREFIX}SHAPED_FOG"
    shaped_fog.operation = "MULTIPLY"

    density = nodes.new("ShaderNodeMath")
    density.name = f"{PREFIX}DENSITY_LIMIT"
    density.operation = "MULTIPLY"
    density.inputs[1].default_value = 0.32

    links = material.node_tree.links
    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(texcoord.outputs["Generated"], edge_distance.inputs[0])
    links.new(edge_distance.outputs["Value"], edge_falloff.inputs["Value"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shaped_fog.inputs[0])
    links.new(edge_falloff.outputs["Result"], shaped_fog.inputs[1])
    links.new(shaped_fog.outputs[0], density.inputs[0])
    links.new(density.outputs[0], volume.inputs["Density"])
    links.new(volume.outputs["Volume"], output.inputs["Volume"])

    # Tie the emissive red energy to the animated physical rear light. The
    # volume remains a real density field; only its radiance is stabilized so
    # a 128-sample proof does not dissolve into direct-scatter fireflies.
    emission_curve = volume.inputs["Emission Strength"].driver_add("default_value")
    emission_curve.driver.type = "SCRIPTED"
    emission_variable = emission_curve.driver.variables.new()
    emission_variable.name = "rear_energy"
    emission_variable.type = "SINGLE_PROP"
    emission_variable.targets[0].id_type = "LIGHT"
    emission_variable.targets[0].id = red_light.data
    emission_variable.targets[0].data_path = "energy"
    emission_curve.driver.expression = "0.015+rear_energy*0.00065"

    # Analytic periodic drivers: frame 1 and frame 121 evaluate identically.
    driver_specs = (
        (mapping.inputs["Location"], 0, "0.08*sin(2*pi*((frame-1)%120)/120)"),
        (mapping.inputs["Location"], 2, "0.12*cos(2*pi*((frame-1)%120)/120)"),
        (noise.inputs["W"], -1, "0.32*sin(2*pi*((frame-1)%120)/120)+0.18*cos(2*pi*((frame-1)%120)/120)"),
    )
    for socket, index, expression in driver_specs:
        curve = socket.driver_add("default_value", index) if index >= 0 else socket.driver_add("default_value")
        curve.driver.type = "SCRIPTED"
        curve.driver.expression = expression

    material["period_frames"] = 120
    material["simulation_cache"] = False
    return material


def create_fog(
    collection: bpy.types.Collection, red_light: bpy.types.Object
) -> bpy.types.Object:
    material = create_fog_material(red_light)
    mesh = bpy.data.meshes.new(f"{PREFIX}FOG_MESH")
    vertices = (
        (-0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5),
        (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5),
        (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5),
        (-0.5, 0.5, 0.5),
    )
    faces = (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    )
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = link_object(collection, bpy.data.objects.new(FOG_VOLUME, mesh))
    obj.location = (0.14, 0.34, 0.66)
    # A low-depth closed volume stays behind the silhouette. The normalized
    # 3D radial falloff reaches zero on every face, hiding the container.
    obj.scale = (0.58, 0.20, 0.82)
    obj.data.materials.append(material)
    # Camera and volume-scatter rays see the atmosphere; surface paths do not,
    # preventing any reflected red cast on the authentic product materials.
    obj.visible_camera = True
    obj.visible_glossy = False
    obj.visible_diffuse = False
    obj.visible_transmission = False
    obj.visible_shadow = False
    obj.visible_volume_scatter = True
    obj["camera_side"] = "behind product only; genuine volume"
    obj["front_y_metres"] = obj.location.y - obj.scale.y / 2.0
    return obj


def create_ground(collection: bpy.types.Collection) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{PREFIX}SHADOW_CATCHER_MESH")
    mesh.from_pydata(
        [(-2.0, -2.0, 0.0), (2.0, -2.0, 0.0), (2.0, 2.0, 0.0), (-2.0, 2.0, 0.0)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()
    obj = link_object(collection, bpy.data.objects.new(SHADOW_CATCHER, mesh))
    obj.location.z = -0.002
    obj.is_shadow_catcher = True

    material = bpy.data.materials.new(GROUND_MATERIAL)
    material.diffuse_color = (0.055, 0.055, 0.055, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (0.055, 0.055, 0.055, 1.0)
    principled.inputs["Roughness"].default_value = 0.74
    obj.data.materials.append(material)
    obj["transparent_shadow_catcher"] = True
    return obj


def create_camera(
    collection: bpy.types.Collection,
    spec: dict[str, object],
    target: Vector,
) -> bpy.types.Object:
    name = str(spec["name"])
    data = bpy.data.cameras.new(name)
    data.lens = float(spec["lens_mm"])
    data.sensor_width = 36.0
    data.sensor_height = 32.0
    data.sensor_fit = str(spec["sensor_fit"])
    data.dof.use_dof = False
    data.clip_start = 0.01
    data.clip_end = 100.0
    obj = link_object(collection, bpy.data.objects.new(name, data))
    obj.location = tuple(spec["location"])
    orient_towards(obj, target)
    obj["fixed_camera"] = True
    obj["fixed_exposure"] = CAMERA_EXPOSURE_EV
    return obj


def create_world() -> bpy.types.World:
    world = bpy.data.worlds.new(WORLD_NAME)
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    background.inputs["Strength"].default_value = 0.0
    return world


def configure_cycles_gpu() -> list[dict[str, object]]:
    preferences = bpy.context.preferences.addons["cycles"].preferences
    try:
        preferences.compute_device_type = "OPTIX"
    except TypeError:
        preferences.compute_device_type = "CUDA"
    preferences.get_devices()
    devices = []
    for device in preferences.devices:
        device.use = device.type == preferences.compute_device_type
        devices.append({"name": device.name, "type": device.type, "use": bool(device.use)})
    if not any(device["use"] and device["type"] != "CPU" for device in devices):
        raise RuntimeError(f"No Cycles GPU device could be enabled: {devices}")
    return devices


def configure_volume_alpha_compositor(scene: bpy.types.Scene) -> None:
    """Carry red-dominant volume radiance into transparent RGBA alpha.

    Cycles leaves emissive volume radiance in RGB while film alpha remains
    zero. The max operation preserves authentic product/shadow alpha and adds
    alpha only where the isolated red atmosphere is chromatically dominant.
    """

    group = bpy.data.node_groups.new(f"{scene.name}_COMPOSITOR", "CompositorNodeTree")
    group.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    nodes = group.nodes
    links = group.links

    render_layers = nodes.new("CompositorNodeRLayers")
    render_layers.name = f"{PREFIX}RENDER_LAYERS"
    render_layers.scene = scene
    separate = nodes.new("CompositorNodeSeparateColor")
    separate.name = f"{PREFIX}SEPARATE_RGBA"

    max_green_blue = nodes.new("ShaderNodeMath")
    max_green_blue.name = f"{PREFIX}MAX_GREEN_BLUE"
    max_green_blue.operation = "MAXIMUM"
    red_dominance = nodes.new("ShaderNodeMath")
    red_dominance.name = f"{PREFIX}RED_DOMINANCE"
    red_dominance.operation = "SUBTRACT"
    red_dominance.use_clamp = True
    volume_threshold = nodes.new("ShaderNodeMath")
    volume_threshold.name = f"{PREFIX}VOLUME_ALPHA_THRESHOLD"
    volume_threshold.operation = "SUBTRACT"
    volume_threshold.inputs[1].default_value = 0.20
    volume_threshold.use_clamp = True
    volume_alpha = nodes.new("ShaderNodeMath")
    volume_alpha.name = f"{PREFIX}VOLUME_ALPHA_GAIN"
    volume_alpha.operation = "MULTIPLY"
    volume_alpha.inputs[1].default_value = 3.0
    volume_alpha.use_clamp = True
    alpha_union = nodes.new("ShaderNodeMath")
    alpha_union.name = f"{PREFIX}ALPHA_UNION"
    alpha_union.operation = "MAXIMUM"
    alpha_union.use_clamp = True

    set_alpha = nodes.new("CompositorNodeSetAlpha")
    set_alpha.name = f"{PREFIX}SET_VOLUME_ALPHA"
    set_alpha.inputs["Type"].default_value = "Replace Alpha"
    output = nodes.new("NodeGroupOutput")
    output.name = f"{PREFIX}COMPOSITOR_OUTPUT"

    links.new(render_layers.outputs["Image"], separate.inputs["Image"])
    links.new(separate.outputs["Green"], max_green_blue.inputs[0])
    links.new(separate.outputs["Blue"], max_green_blue.inputs[1])
    links.new(separate.outputs["Red"], red_dominance.inputs[0])
    links.new(max_green_blue.outputs[0], red_dominance.inputs[1])
    links.new(red_dominance.outputs[0], volume_threshold.inputs[0])
    links.new(volume_threshold.outputs[0], volume_alpha.inputs[0])
    links.new(render_layers.outputs["Alpha"], alpha_union.inputs[0])
    links.new(volume_alpha.outputs[0], alpha_union.inputs[1])
    links.new(render_layers.outputs["Image"], set_alpha.inputs["Image"])
    links.new(alpha_union.outputs[0], set_alpha.inputs["Alpha"])
    links.new(set_alpha.outputs["Image"], output.inputs["Image"])
    scene.compositing_node_group = group


def configure_scene(
    scene: bpy.types.Scene,
    camera: bpy.types.Object,
    resolution: tuple[int, int],
    world: bpy.types.World,
) -> None:
    scene.camera = camera
    scene.world = world
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    scene.render.use_file_extension = True
    scene.render.use_placeholder = False
    scene.render.use_compositing = True
    scene.render.use_sequencer = False
    scene.render.engine = "CYCLES"
    scene.cycles.device = "GPU"
    scene.cycles.samples = CYCLES_SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.volume_bounces = 0
    scene.cycles.volume_step_rate = 0.25
    scene.render.use_persistent_data = True
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = CAMERA_EXPOSURE_EV
    scene.view_settings.gamma = 1.0
    scene["one_key_light"] = KEY_LIGHT
    scene["same_temperature_fill"] = FILL_LIGHT
    scene["rear_effect_only"] = RED_BACKLIGHT
    scene["film_transparent"] = True
    scene["loop_boundary_frame"] = LOOP_BOUNDARY_FRAME
    configure_volume_alpha_compositor(scene)


def assert_machine_materials_unchanged(snapshot: dict[str, tuple[str | None, ...]]) -> None:
    collection = bpy.data.collections[PRODUCT_COLLECTION]
    current = {obj.name: material_slots(obj) for obj in collection_mesh_objects(collection)}
    if current != snapshot:
        changed = sorted(name for name in snapshot if snapshot.get(name) != current.get(name))
        raise RuntimeError(f"Machine material slots changed unexpectedly: {changed[:20]}")


def create_stage(
    product_collection: bpy.types.Collection,
    material_snapshot: dict[str, tuple[str | None, ...]],
) -> dict[str, object]:
    remove_prefixed_data()

    root = bpy.data.collections.new(ROOT_COLLECTION)
    root[OWNER_PROPERTY] = True
    stage_collections = {name: get_owned_stage_collection(name) for name in STAGE_COLLECTIONS}
    for collection in stage_collections.values():
        root.children.link(collection)

    machine = link_object(root, bpy.data.objects.new(MACHINE_INSTANCE, None))
    machine.instance_type = "COLLECTION"
    machine.instance_collection = product_collection
    machine.rotation_euler.z = math.radians(MACHINE_ROTATION_Z_DEGREES)
    machine["authentic_product_collection"] = PRODUCT_COLLECTION
    machine["material_slots_immutable"] = True

    camera_target = link_object(
        stage_collections["RED_STAGE_CAMERAS"], bpy.data.objects.new(SHARED_TARGET, None)
    )
    camera_target.location = CAMERA_TARGET_LOCATION
    camera_target.empty_display_type = "PLAIN_AXES"
    camera_target.empty_display_size = 0.08
    target = Vector(CAMERA_TARGET_LOCATION)

    lighting = create_lighting(stage_collections["RED_STAGE_LIGHTS"], target)
    fog = create_fog(stage_collections["RED_STAGE_FOG"], lighting["red"])
    # Keep the sole receiver explicit so the physical rear light cannot spill
    # onto product materials.
    lighting["red"].light_linking.receiver_collection = stage_collections["RED_STAGE_FOG"]
    ground = create_ground(stage_collections["RED_STAGE_GROUND"])
    cameras = {
        label: create_camera(stage_collections["RED_STAGE_CAMERAS"], spec, target)
        for label, spec in CAMERA_SPECS.items()
    }
    world = create_world()

    scenes = {}
    for label, spec in CAMERA_SPECS.items():
        scene = bpy.data.scenes.new(str(spec["scene"]))
        scene.collection.children.link(root)
        configure_scene(scene, cameras[label], tuple(spec["resolution"]), world)
        scenes[label] = scene

    assert_machine_materials_unchanged(material_snapshot)
    assert_scene_contract(scenes, stage_collections, lighting, fog, ground)
    return {
        "scenes": scenes,
        "cameras": cameras,
        "lighting": lighting,
        "fog": fog,
        "ground": ground,
        "devices": configure_cycles_gpu(),
    }


def assert_scene_contract(
    scenes: dict[str, bpy.types.Scene],
    collections: dict[str, bpy.types.Collection],
    lighting: dict[str, bpy.types.Object],
    fog: bpy.types.Object,
    ground: bpy.types.Object,
) -> None:
    if set(collections) != set(STAGE_COLLECTIONS):
        raise RuntimeError(f"Stage collection contract failed: {sorted(collections)}")
    if lighting["fill"].data.energy >= lighting["key"].data.energy:
        raise RuntimeError("The neutral fill must remain weaker than the dominant key.")
    if tuple(lighting["fill"].data.color) != tuple(lighting["key"].data.color):
        raise RuntimeError("Key and fill colour temperatures diverged.")
    if lighting["red"].hide_render or not math.isclose(
        lighting["red"].data.volume_factor, 0.02, abs_tol=1e-6
    ):
        raise RuntimeError("The rear red backlight must render as a volume-only light.")
    if any(
        factor != 0.0
        for factor in (
            lighting["red"].data.diffuse_factor,
            lighting["red"].data.specular_factor,
            lighting["red"].data.transmission_factor,
        )
    ):
        raise RuntimeError("The rear red backlight must not illuminate product surfaces.")
    if lighting["red"].light_linking.receiver_collection != collections["RED_STAGE_FOG"]:
        raise RuntimeError("The red rear effect must be light-linked only to RED_STAGE_FOG.")
    if fog.location.y - fog.scale.y / 2.0 <= 0.22:
        raise RuntimeError("Fog plume drifted in front of the rotated product bounds.")
    fog_output = bpy.data.materials[FOG_MATERIAL].node_tree.nodes[f"{PREFIX}FOG_OUTPUT"]
    if not fog_output.inputs["Volume"].is_linked or fog_output.inputs["Surface"].is_linked:
        raise RuntimeError("Fog must be a genuine volume with no surface-card shader.")
    fog_volume = bpy.data.materials[FOG_MATERIAL].node_tree.nodes[
        f"{PREFIX}PRINCIPLED_VOLUME"
    ]
    emission_path = fog_volume.inputs["Emission Strength"].path_from_id("default_value")
    fog_animation = bpy.data.materials[FOG_MATERIAL].node_tree.animation_data
    if fog_animation is None or not any(
        curve.data_path == emission_path for curve in fog_animation.drivers
    ):
        raise RuntimeError("Fog emission must remain synchronized to the rear light.")
    if not ground.is_shadow_catcher:
        raise RuntimeError("Ground must remain a Cycles shadow catcher.")
    for scene in scenes.values():
        compositor = scene.compositing_node_group
        if compositor is None or f"{PREFIX}SET_VOLUME_ALPHA" not in compositor.nodes:
            raise RuntimeError("Transparent RGBA volume-alpha compositor is missing.")
    for label, scene in scenes.items():
        expected_resolution = tuple(CAMERA_SPECS[label]["resolution"])
        actual_resolution = (scene.render.resolution_x, scene.render.resolution_y)
        if actual_resolution != expected_resolution:
            raise RuntimeError(f"{label} resolution drifted: {actual_resolution}")
        if not scene.render.film_transparent or scene.render.image_settings.color_mode != "RGBA":
            raise RuntimeError(f"{label} must render transparent RGBA.")
        if scene.render.engine != "CYCLES" or scene.cycles.samples != CYCLES_SAMPLES:
            raise RuntimeError(f"{label} Cycles settings drifted.")
        if scene.camera.data.dof.use_dof:
            raise RuntimeError(f"{label} depth of field must remain disabled.")

    for object_name, expected_slots in REGULATOR_MATERIAL_CONTRACT.items():
        if material_slots(bpy.data.objects[object_name]) != expected_slots:
            raise RuntimeError(f"Regulator material drifted after scene creation: {object_name}")


def scene_summary(build: dict[str, object]) -> dict[str, object]:
    red = build["lighting"]["red"]
    fog_material = bpy.data.materials[FOG_MATERIAL]
    mapping = fog_material.node_tree.nodes[f"{PREFIX}PERIODIC_MAPPING"]
    noise = fog_material.node_tree.nodes[f"{PREFIX}PERIODIC_NOISE"]
    return {
        "blender_version": bpy.app.version_string,
        "target": bpy.data.filepath,
        "product_collection": PRODUCT_COLLECTION,
        "product_meshes": EXPECTED_MACHINE_MESH_COUNT,
        "regulator_contract": REGULATOR_MATERIAL_CONTRACT,
        "stage_collections": [
            {"name": name, "objects": len(bpy.data.collections[name].objects)}
            for name in STAGE_COLLECTIONS
        ],
        "generated_prefixed_objects": sorted(
            obj.name for obj in bpy.data.objects if obj.name.startswith(PREFIX)
        ),
        "generated_prefixed_scenes": sorted(
            scene.name for scene in bpy.data.scenes if scene.name.startswith(PREFIX)
        ),
        "render": {
            label: {
                "scene": scene.name,
                "camera": scene.camera.name,
                "resolution": [scene.render.resolution_x, scene.render.resolution_y],
                "engine": scene.render.engine,
                "device": scene.cycles.device,
                "samples": scene.cycles.samples,
                "denoising": scene.cycles.use_denoising,
                "film_transparent": scene.render.film_transparent,
                "color_mode": scene.render.image_settings.color_mode,
                "fps": scene.render.fps,
                "frames": [scene.frame_start, scene.frame_end],
                "exposure": scene.view_settings.exposure,
                "dof": scene.camera.data.dof.use_dof,
            }
            for label, scene in build["scenes"].items()
        },
        "lighting": {
            "key": {
                "name": KEY_LIGHT,
                "energy": build["lighting"]["key"].data.energy,
                "temperature_kelvin": LIGHT_TEMPERATURE_K,
            },
            "fill": {
                "name": FILL_LIGHT,
                "energy": build["lighting"]["fill"].data.energy,
                "temperature_kelvin": LIGHT_TEMPERATURE_K,
            },
            "red": {
                "name": RED_BACKLIGHT,
                "keyframes": list(RED_LIGHT_KEYFRAMES),
                "current_energy": red.data.energy,
            },
        },
        "fog": {
            "name": FOG_VOLUME,
            "front_y": build["fog"].location.y - build["fog"].scale.y / 2.0,
            "architecture": (
                "closed low-density Principled Volume with synchronized red emission "
                "and isolated rear area light"
            ),
            "periodic_driver_count": len(fog_material.node_tree.animation_data.drivers),
            "noise_dimensions": noise.noise_dimensions,
            "period_frames": fog_material["period_frames"],
            "simulation_cache": fog_material["simulation_cache"],
        },
        "cycles_devices": build["devices"],
    }


def evaluated_loop_state(scene: bpy.types.Scene, frame: int) -> tuple[object, ...]:
    bpy.context.window.scene = scene
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    fog_material = bpy.data.materials[FOG_MATERIAL]
    mapping = fog_material.node_tree.nodes[f"{PREFIX}PERIODIC_MAPPING"]
    noise = fog_material.node_tree.nodes[f"{PREFIX}PERIODIC_NOISE"]
    volume = fog_material.node_tree.nodes[f"{PREFIX}PRINCIPLED_VOLUME"]
    return (
        float(bpy.data.lights[RED_BACKLIGHT].energy),
        float(volume.inputs["Emission Strength"].default_value),
        tuple(float(value) for value in mapping.inputs["Location"].default_value),
        float(noise.inputs["W"].default_value),
        tuple(float(value) for value in build_fog_matrix(scene)),
    )


def build_fog_matrix(scene: bpy.types.Scene) -> tuple[float, ...]:
    del scene
    return tuple(value for row in bpy.data.objects[FOG_VOLUME].matrix_world for value in row)


def assert_loop_state_identical(scene: bpy.types.Scene) -> None:
    frame_one = evaluated_loop_state(scene, FRAME_START)
    boundary = evaluated_loop_state(scene, LOOP_BOUNDARY_FRAME)
    if frame_one != boundary:
        raise RuntimeError(f"Loop state differs at frames 1 and 121: {frame_one} != {boundary}")


def render_proofs(build: dict[str, object]) -> list[str]:
    output_paths = []
    for label, spec in CAMERA_SPECS.items():
        scene = build["scenes"][label]
        output_dir = Path(spec["output"])
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_one_output: Path | None = None
        for frame in PROOF_FRAMES:
            # Shared animated stage data evaluates against the active scene.
            # Select it before setting the frame or every proof stays at the
            # previous scene's frame despite the per-scene frame counter.
            bpy.context.window.scene = scene
            scene.frame_set(frame)
            output = output_dir / f"pimm50-red-stage-{label}-f{frame:03d}.png"
            scene.render.filepath = str(output)
            if frame == LOOP_BOUNDARY_FRAME:
                assert_loop_state_identical(scene)
                if frame_one_output is None or not frame_one_output.is_file():
                    raise RuntimeError("Frame 1 proof is required before the loop boundary copy.")
                shutil.copyfile(frame_one_output, output)
                scene.frame_set(LOOP_BOUNDARY_FRAME)
            else:
                bpy.ops.render.render(write_still=True, scene=scene.name)
                if frame == FRAME_START:
                    frame_one_output = output
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError(f"Proof render was not written: {output}")
            output_paths.append(str(output))
    return output_paths


def main() -> None:
    args = parse_args()
    assert_running_from_target()
    product_collection, material_snapshot = assert_machine_contract()
    build = create_stage(product_collection, material_snapshot)
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET_BLEND), check_existing=False)
    summary = scene_summary(build)
    if args.render_proofs:
        summary["proofs"] = render_proofs(build)
        bpy.ops.wm.save_as_mainfile(filepath=str(TARGET_BLEND), check_existing=False)
    print("PIMM50_RED_STAGE_SUMMARY_BEGIN")
    print(json.dumps(summary, indent=2, default=list))
    print("PIMM50_RED_STAGE_SUMMARY_END")


if __name__ == "__main__":
    main()
