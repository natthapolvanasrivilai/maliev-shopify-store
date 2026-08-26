"""Build and optionally render the PIMM 30G direct-operation animation.

Run this script only against the dedicated working copy of the inspected scene:

    blender -b PIMM-30g-direct-operation-toggle-v1.blend \
      -P create_pimm30_direct_operation_toggle.py -- --save --render desktop

The authentic product meshes and materials are inputs. The builder creates two
fully dedicated scenes and duplicates their objects so the valve/plunger
animation cannot leak into any scene used by another slide. It owns only scenes
and objects carrying the ``PIMM30_DIRECT_OPERATION_`` prefix. It is idempotent
and never adds screen-space labels. The real controller segment geometry and
the established studio lighting are baked from the neutral master at its
verified 300/300 presentation frame, then remain unchanged for the clip.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PREFIX = "PIMM30_DIRECT_OPERATION_"
OWNER_PROPERTY = "pimm30_direct_operation_owned"

# Inspected directly in PIMM-30g-product-story-v14-pressure-framing.blend.
# Blender's metric scale is 1.0, so this is the full verified 200 mm stroke.
STROKE_METERS = 0.20
VALVE_HANDLE_NAME = "30g_Body3_5_Opaque_50_50_50_0"
AIRTAC_DECAL_NAME = "AirTAC_Decal_30g"
SHADOW_CATCHER_NAME = "PIMM30_Hero_ShadowCatcher"
# The authentic decal plane sits only 0.23 mm ahead of the valve body. Cycles
# can lose it to depth precision at this close presentation framing, so move
# the real decal (and its existing texture/material) another 0.75 mm toward
# both direct-operation cameras. This is geometry, never a screen overlay.
AIRTAC_DECAL_CAMERA_OFFSET_METERS = 0.00075
# The handle mesh origin is at world zero. Its mounting face is the local
# Y-max plane (-0.12195 m), so the spindle centre must sit on that face. The
# former -0.111 m value orbited the handle around a point 10.95 mm outside the
# real mount and made the command sweep visibly slide instead of hinge.
VALVE_PIVOT = Vector((0.1, -0.12195, 0.5355))
PLUNGER_OBJECT_NAMES = (
    "30g_045_Body1_101",
    "30g_046_Body1_102",
    "30g_048_Body1_104",
    "30g_050_Body1_106",
)

FPS = 24
FRAME_START = 1
EXTEND_ACTUATOR_START_FRAME = 13
EXTEND_COMMAND_FRAME = 21
EXTEND_PLUNGER_START_FRAME = 25
EXTENDED_FRAME = 43
RETRACT_ACTUATOR_START_FRAME = 49
RETRACT_COMMAND_FRAME = 59
RETRACT_PLUNGER_START_FRAME = 63
RETRACTED_FRAME = 75
FRAME_END = 80
VALVE_ANGLE_DEGREES = 15.0
STUDIO_REFERENCE_FRAME = 80

SOURCE_SCENE_NAMES = {
    "desktop": "PIMM30_Story_Desktop",
    "mobile": "PIMM30_Story_Mobile",
}
SCENE_NAMES = {
    "desktop": "PIMM30_DIRECT_OPERATION_DESKTOP_SCENE",
    "mobile": "PIMM30_DIRECT_OPERATION_MOBILE_SCENE",
}
CAMERA_NAMES = {
    "desktop": "PIMM30_DIRECT_OPERATION_DESKTOP_CAMERA",
    "mobile": "PIMM30_DIRECT_OPERATION_MOBILE_CAMERA",
}
CAMERA_TRANSFORMS = {
    "desktop": {
        "location": (0.572026, -1.684486, 0.742009),
        "rotation": (1.463210, 0.0, 0.292147),
        "lens": 74.0,
        "shift_y": -0.10,
    },
    "mobile": {
        "location": (0.300000, -0.780000, 0.640000),
        "rotation": (1.463210, 0.0, 0.292147),
        "lens": 66.0,
        "shift_y": -0.08,
    },
}
KEY_LIGHT_NAME = "STORY_Key_5600K"
FILL_LIGHT_NAME = "STORY_Fill_5600K"
RESOLUTIONS = {
    "desktop": (1200, 1440),
    "mobile": (1080, 1920),
}
OUTPUT_ROOT = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders"
    r"\renders\product-story\direct-operation-toggle-v1"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", action="store_true", help="Save the working blend.")
    parser.add_argument(
        "--render",
        choices=("desktop", "mobile", "all"),
        help="Render the requested transparent PNG sequence.",
    )
    parser.add_argument(
        "--proofs",
        action="store_true",
        help="Render only the mechanically important endpoint proof frames.",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Render a low-resolution desktop motion proof before final output.",
    )
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def remove_owned_data() -> None:
    for scene in list(bpy.data.scenes):
        if scene.get(OWNER_PROPERTY) or scene.name.startswith(PREFIX):
            bpy.data.scenes.remove(scene)
    for obj in list(bpy.data.objects):
        if obj.get(OWNER_PROPERTY) or obj.name.startswith(PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)


def restore_source_mechanics() -> None:
    """Remove animation previously written onto globally shared source objects."""
    bpy.context.scene.frame_set(FRAME_START)
    valve = bpy.data.objects.get(VALVE_HANDLE_NAME)
    if valve is None:
        raise RuntimeError(f"Required authentic object is missing: {VALVE_HANDLE_NAME}")
    valve.animation_data_clear()
    valve.location = (0.0, 0.0, 0.0)
    valve.rotation_mode = "XYZ"
    valve.rotation_euler = (0.0, 0.0, 0.0)
    for name in PLUNGER_OBJECT_NAMES:
        part = bpy.data.objects.get(name)
        if part is None:
            raise RuntimeError(f"Required authentic object is missing: {name}")
        part.animation_data_clear()
        part.location.z = 0.0


def clone_scene(label: str) -> tuple[bpy.types.Scene, dict[str, bpy.types.Object]]:
    """Create an isolated direct-operation scene from a neutral master scene."""
    source = bpy.data.scenes.get(SOURCE_SCENE_NAMES[label])
    if source is None:
        raise RuntimeError(f"Missing neutral source scene: {SOURCE_SCENE_NAMES[label]}")
    bpy.context.window.scene = source
    source.frame_set(STUDIO_REFERENCE_FRAME)

    scene = bpy.data.scenes.new(SCENE_NAMES[label])
    scene[OWNER_PROPERTY] = True
    scene.world = source.world.copy() if source.world else None
    if scene.world:
        scene.world.animation_data_clear()
        if scene.world.node_tree:
            scene.world.node_tree.animation_data_clear()
    scene.view_settings.view_transform = source.view_settings.view_transform
    scene.view_settings.look = source.view_settings.look
    scene.view_settings.exposure = source.view_settings.exposure
    scene.view_settings.gamma = source.view_settings.gamma
    object_map: dict[bpy.types.Object, bpy.types.Object] = {}
    objects_by_source_name: dict[str, bpy.types.Object] = {}

    for source_object in source.objects:
        if source_object.type == "CAMERA":
            continue
        clone = source_object.copy()
        clone.name = f"{PREFIX}{label.upper()}__{source_object.name}"
        clone[OWNER_PROPERTY] = True
        clone["pimm30_direct_operation_source"] = source_object.name
        # Bake the master scene at its verified studio/300°C frame. This keeps
        # lighting and controller segments physically authentic and constant,
        # while the dedicated scene owns only the new mechanical motion.
        clone.animation_data_clear()
        clone.matrix_basis = source_object.matrix_basis.copy()
        clone.hide_render = source_object.hide_render
        if source_object.type == "LIGHT" and source_object.data:
            clone.data = source_object.data.copy()
            clone.data.animation_data_clear()
        scene.collection.objects.link(clone)
        object_map[source_object] = clone
        objects_by_source_name[source_object.name] = clone

    # Preserve the neutral source hierarchy while ensuring every parent target
    # resolves to another object owned by this dedicated scene.
    for source_object, clone in object_map.items():
        clone.parent = object_map.get(source_object.parent)
        clone.matrix_parent_inverse = source_object.matrix_parent_inverse.copy()
        for constraint in clone.constraints:
            if hasattr(constraint, "target") and constraint.target in object_map:
                constraint.target = object_map[constraint.target]

    camera_data = bpy.data.cameras.new(f"{CAMERA_NAMES[label]}_DATA")
    camera = bpy.data.objects.new(CAMERA_NAMES[label], camera_data)
    camera[OWNER_PROPERTY] = True
    scene.collection.objects.link(camera)
    transform = CAMERA_TRANSFORMS[label]
    camera.location = transform["location"]
    camera.rotation_mode = "XYZ"
    camera.rotation_euler = transform["rotation"]
    camera.data.lens = transform["lens"]
    camera.data.shift_y = transform["shift_y"]
    scene.camera = camera
    return scene, objects_by_source_name


def keyframe_vector(
    obj: bpy.types.Object, data_path: str, frame: int, value: tuple[float, ...]
) -> None:
    setattr(obj, data_path, value)
    obj.keyframe_insert(data_path=data_path, frame=frame)


def set_smooth_motion(obj: bpy.types.Object) -> None:
    action = obj.animation_data.action if obj.animation_data else None
    if action is None:
        return
    # Blender 5 stores keyed channels in layered action slots. Keyframes made
    # through ``keyframe_insert`` already use smooth Bezier interpolation, so
    # older flat actions can be refined here while layered actions keep their
    # correct defaults.
    curves = getattr(action, "fcurves", ())
    for curve in curves:
        for point in curve.keyframe_points:
            point.interpolation = "BEZIER"
            point.easing = "EASE_IN_OUT"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"


def create_valve_pivot(
    scene: bpy.types.Scene, valve_handle: bpy.types.Object
) -> bpy.types.Object:
    """Parent the handle to a fixed spindle so its motion is rotation-only."""
    world_matrix = valve_handle.matrix_world.copy()
    valve_pivot = bpy.data.objects.new(f"{PREFIX}VALVE_SPINDLE", None)
    valve_pivot[OWNER_PROPERTY] = True
    scene.collection.objects.link(valve_pivot)
    valve_pivot.matrix_world.translation = VALVE_PIVOT
    valve_pivot.rotation_mode = "XYZ"

    valve_handle.parent = valve_pivot
    valve_handle.matrix_parent_inverse = valve_pivot.matrix_world.inverted()
    valve_handle.matrix_world = world_matrix
    return valve_pivot


def require_clone(
    objects_by_source_name: dict[str, bpy.types.Object], name: str
) -> bpy.types.Object:
    obj = objects_by_source_name.get(name)
    if obj is None:
        raise RuntimeError(f"Dedicated scene is missing authentic source object: {name}")
    return obj


def preserve_airtac_decal(
    objects_by_source_name: dict[str, bpy.types.Object],
) -> bpy.types.Object:
    """Keep the authentic AIRTAC decal legible without replacing its material."""
    decal = require_clone(objects_by_source_name, AIRTAC_DECAL_NAME)
    decal.hide_render = False
    decal_world = decal.matrix_world.copy()
    decal_world.translation.y -= AIRTAC_DECAL_CAMERA_OFFSET_METERS
    decal.matrix_world = decal_world
    return decal


def preserve_transparent_stage(
    objects_by_source_name: dict[str, bpy.types.Object],
) -> None:
    """Remove the hero ground plane from this cropped mechanical close-up."""
    shadow_catcher = require_clone(objects_by_source_name, SHADOW_CATCHER_NAME)
    shadow_catcher.hide_render = True


def build_animation(
    scene: bpy.types.Scene, objects_by_source_name: dict[str, bpy.types.Object]
) -> tuple[bpy.types.Object, tuple[bpy.types.Object, ...]]:
    bpy.context.window.scene = scene
    preserve_airtac_decal(objects_by_source_name)
    preserve_transparent_stage(objects_by_source_name)
    valve_handle = require_clone(objects_by_source_name, VALVE_HANDLE_NAME)
    valve_handle.animation_data_clear()
    valve_pivot = create_valve_pivot(scene, valve_handle)
    for frame, angle in (
        (FRAME_START, 0.0),
        (EXTEND_ACTUATOR_START_FRAME, 0.0),
        (EXTEND_COMMAND_FRAME, math.radians(VALVE_ANGLE_DEGREES)),
        (EXTENDED_FRAME, math.radians(VALVE_ANGLE_DEGREES)),
        (RETRACT_ACTUATOR_START_FRAME, math.radians(VALVE_ANGLE_DEGREES)),
        (RETRACT_COMMAND_FRAME, math.radians(-VALVE_ANGLE_DEGREES)),
        (RETRACTED_FRAME, math.radians(-VALVE_ANGLE_DEGREES)),
        (FRAME_END, 0.0),
    ):
        keyframe_vector(
            valve_pivot,
            "rotation_euler",
            frame,
            (angle, 0.0, 0.0),
        )
    set_smooth_motion(valve_pivot)

    plunger_parts = tuple(
        require_clone(objects_by_source_name, name) for name in PLUNGER_OBJECT_NAMES
    )
    for part in plunger_parts:
        part.animation_data_clear()
    for object_name in PLUNGER_OBJECT_NAMES:
        part = require_clone(objects_by_source_name, object_name)
        base_location = part.location.copy()
        retracted_z = base_location.z
        bpy.context.scene.frame_set(EXTENDED_FRAME)
        extended_z = retracted_z - STROKE_METERS
        for frame, z_value in (
            (FRAME_START, retracted_z),
            (EXTEND_PLUNGER_START_FRAME, retracted_z),
            (EXTENDED_FRAME, extended_z),
            (RETRACT_PLUNGER_START_FRAME, extended_z),
            (RETRACTED_FRAME, retracted_z),
            (FRAME_END, retracted_z),
        ):
            keyframe_vector(
                part,
                "location",
                frame,
                (base_location.x, base_location.y, z_value),
            )
        bpy.context.scene.frame_set(RETRACTED_FRAME)
        part.location.z = retracted_z
        set_smooth_motion(part)

    return valve_handle, plunger_parts


def configure_scene(
    label: str,
    scene: bpy.types.Scene,
    objects_by_source_name: dict[str, bpy.types.Object],
) -> bpy.types.Scene:
    camera = scene.camera
    if camera is None or camera.name != CAMERA_NAMES[label]:
        raise RuntimeError(f"Missing dedicated {label} camera")

    scene.camera = camera
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    scene.render.resolution_x, scene.render.resolution_y = RESOLUTIONS[label]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = str(OUTPUT_ROOT / label / "frame_")

    # Focus the presentation on the hand valve and moving plunger, while the
    # lower machine exits below the composition instead of competing with the
    # actual operation. The complete cylinder and 200 mm stroke stay visible.
    camera.data.lens = CAMERA_TRANSFORMS[label]["lens"]
    camera.data.shift_y = CAMERA_TRANSFORMS[label]["shift_y"]

    # Cycles preserves the authentic brushed-metal response. Twenty-four
    # denoised samples are sufficient for this clean transparent studio pass.
    scene.render.engine = "CYCLES"
    scene.cycles.device = "GPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.use_persistent_data = True
    # Lighting, world, view transform and exposure are inherited unchanged
    # from the established studio reference frame. Do not restyle this slide.
    require_clone(objects_by_source_name, KEY_LIGHT_NAME)
    require_clone(objects_by_source_name, FILL_LIGHT_NAME)
    scene.render.image_settings.color_depth = "8"
    return scene


def render(
    label: str,
    scene: bpy.types.Scene,
    objects_by_source_name: dict[str, bpy.types.Object],
    proofs_only: bool,
    review_only: bool,
) -> None:
    configure_scene(label, scene, objects_by_source_name)
    OUTPUT_ROOT.joinpath(label).mkdir(parents=True, exist_ok=True)
    bpy.context.window.scene = scene
    if review_only:
        review_root = OUTPUT_ROOT / "review" / label
        review_root.mkdir(parents=True, exist_ok=True)
        scene.render.resolution_percentage = 25
        scene.cycles.samples = 4
        scene.render.filepath = str(review_root / "frame_")
        bpy.ops.render.render(animation=True, scene=scene.name)
    elif proofs_only:
        # Fast approval proof: show both completed valve commands before their
        # corresponding plunger response, plus both stroke endpoints.
        scene.render.resolution_percentage = 50
        scene.cycles.samples = 8
        for frame in (
            FRAME_START,
            EXTEND_COMMAND_FRAME,
            EXTENDED_FRAME,
            RETRACT_COMMAND_FRAME,
            RETRACTED_FRAME,
        ):
            scene.frame_set(frame)
            scene.render.filepath = str(OUTPUT_ROOT / label / f"proof_{frame:04d}.png")
            bpy.ops.render.render(write_still=True, scene=scene.name)
    else:
        scene.render.filepath = str(OUTPUT_ROOT / label / "frame_")
        bpy.ops.render.render(animation=True, scene=scene.name)


def main() -> None:
    args = parse_args()
    remove_owned_data()
    restore_source_mechanics()
    dedicated_scenes = {
        label: clone_scene(label) for label in SCENE_NAMES
    }
    for label, (scene, objects_by_source_name) in dedicated_scenes.items():
        build_animation(scene, objects_by_source_name)
        configure_scene(label, scene, objects_by_source_name)
        scene.frame_set(FRAME_START)

    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    if args.render:
        labels = tuple(SCENE_NAMES) if args.render == "all" else (args.render,)
        for label in labels:
            scene, objects_by_source_name = dedicated_scenes[label]
            render(label, scene, objects_by_source_name, args.proofs, args.review)


if __name__ == "__main__":
    main()
