"""Author and render the 30G pneumatic-input bento animation proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


FPS = 24
FRAME_END = 288
KNOB_ID = "30G-17d7471e4d56f8a8"
GAUGE_NEEDLE_ID = "30G-623a1bfb6905b6f3"
MALE_COUPLER_ID = "30G-96016700baf3c097"
PROOF_FRAMES = (1, 48, 78, 90, 126, 162, 180, 216, 252, 288)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def by_stable_id(stable_id: str):
    matches = [obj for obj in bpy.data.objects if obj.get("pimm_stable_id") == stable_id]
    if len(matches) != 1:
        raise RuntimeError(f"expected one object for {stable_id}, found {len(matches)}")
    return matches[0]


def material(name: str, color: tuple[float, float, float, float], metallic: float, roughness: float):
    value = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    value.diffuse_color = color
    value.use_nodes = True
    principled = value.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Roughness"].default_value = roughness
    return value


def insert_key(obj, data_path: str, frame: int):
    obj.keyframe_insert(data_path=data_path, frame=frame)


def set_linear_interpolation(obj):
    action = obj.animation_data.action if obj.animation_data else None
    if not action:
        return
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                for curve in channelbag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = "BEZIER"
                        key.easing = "AUTO"


def add_needle(gauge_center: Vector):
    mesh = bpy.data.meshes.new("PNEUMATIC_GAUGE_NEEDLE_MESH")
    mesh.from_pydata(
        [(0.0, 0.0, -1.25), (14.4, 0.0, 0.0), (0.0, 0.0, 1.25), (-3.0, 0.0, 0.0)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.materials.append(material("PNEUMATIC_GAUGE_BLACK", (0.015, 0.018, 0.022, 1.0), 0.15, 0.28))
    needle = bpy.data.objects.new("PNEUMATIC_GAUGE_NEEDLE", mesh)
    bpy.context.collection.objects.link(needle)
    needle.location = gauge_center

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=2.15, location=gauge_center)
    hub = bpy.context.object
    hub.name = "PNEUMATIC_GAUGE_NEEDLE_HUB"
    hub.scale.y = 0.42
    hub.data.materials.append(mesh.materials[0])
    return needle, hub


def look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def import_coupler(path: Path, male_coupler):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [obj for obj in bpy.data.objects if obj not in before]
    root = bpy.data.objects.new("PNEUMATIC_FEMALE_COUPLER_ROOT", None)
    bpy.context.collection.objects.link(root)
    for obj in imported:
        if obj.parent is None:
            obj.parent = root
    # The master scene uses millimetres, and Blender's glTF importer performs the
    # metre-to-scene-unit conversion on import. A second 1000x scale would push
    # the STEP assembly far outside the camera frustum.
    root.scale = (1.0, 1.0, 1.0)
    root.rotation_euler.z = math.radians(90.0)

    if not male_coupler.material_slots or male_coupler.material_slots[0].material is None:
        raise RuntimeError("male quick coupler has no authoritative material")
    coupler_material = male_coupler.material_slots[0].material
    rubber = bpy.data.materials.get("PIMM_RUBBER_BLACK") or material(
        "PIMM_RUBBER_BLACK", (0.012, 0.014, 0.016, 1.0), 0.0, 0.63
    )
    for obj in imported:
        if obj.type != "MESH":
            continue
        obj.data.materials.clear()
        obj.data.materials.append(rubber if "hose" in obj.name.lower() else coupler_material)
    return root


def configure_animation(coupler_path: Path) -> dict:
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    scene.render.fps_base = 1

    knob = by_stable_id(KNOB_ID)
    original_needle = by_stable_id(GAUGE_NEEDLE_ID)
    male_coupler = by_stable_id(MALE_COUPLER_ID)
    original_needle.hide_render = True

    gauge_center = Vector((-90.0, -164.72, 530.5))
    needle, hub = add_needle(gauge_center)
    coupler = import_coupler(coupler_path, male_coupler)

    coupler.location = (-300.0, -120.0, 530.5)
    insert_key(coupler, "location", 1)
    insert_key(coupler, "location", 24)
    coupler.location.x = -150.0
    insert_key(coupler, "location", 64)
    insert_key(coupler, "location", 264)
    coupler.location.x = -300.0
    insert_key(coupler, "location", 288)

    knob_base = knob.location.copy()
    knob.rotation_mode = "XYZ"
    knob.location = knob_base
    knob.rotation_euler.z = 0.0
    insert_key(knob, "location", 1)
    insert_key(knob, "rotation_euler", 1)
    insert_key(knob, "location", 78)
    insert_key(knob, "rotation_euler", 90)
    knob.location.z = knob_base.z + 1.5
    insert_key(knob, "location", 90)
    knob.rotation_euler.z = math.radians(145.0)
    insert_key(knob, "rotation_euler", 126)
    insert_key(knob, "location", 162)
    knob.location.z = knob_base.z
    insert_key(knob, "location", 180)
    insert_key(knob, "location", 216)
    knob.location.z = knob_base.z + 1.5
    insert_key(knob, "location", 228)
    knob.rotation_euler.z = 0.0
    insert_key(knob, "rotation_euler", 252)
    knob.location.z = knob_base.z
    insert_key(knob, "location", 264)
    insert_key(knob, "rotation_euler", 288)

    needle.rotation_mode = "XYZ"
    needle.rotation_euler.y = math.radians(135.0)
    insert_key(needle, "rotation_euler", 1)
    insert_key(needle, "rotation_euler", 126)
    needle.rotation_euler.y = math.radians(-63.0)
    insert_key(needle, "rotation_euler", 162)
    insert_key(needle, "rotation_euler", 228)
    needle.rotation_euler.y = math.radians(135.0)
    insert_key(needle, "rotation_euler", 252)
    insert_key(needle, "rotation_euler", 288)

    for animated in (coupler, knob, needle):
        set_linear_interpolation(animated)

    return {
        "fps": FPS,
        "frames": FRAME_END,
        "duration_seconds": FRAME_END / FPS,
        "male_coupler": male_coupler.name,
        "female_coupler_material": male_coupler.material_slots[0].material.name,
        "hose_material": "PIMM_RUBBER_BLACK",
        "female_coupler_final_root": [-150.0, -120.0, 530.5],
        "knob_lift_mm": 1.5,
        "regulated_pressure_mpa": 0.6,
        "sequence": [
            "needle holds at 0 MPa",
            "female coupler inserts while pressure remains at 0 MPa",
            "regulator knob lifts 1.5 mm and rotates",
            "needle moves to 0.6 MPa",
            "regulator knob returns to its locked height",
        ],
        "loop_reset": "unlock, return to 0 MPa, relock, disconnect",
    }


def configure_render(width: int, height: int):
    if width * 11 != height * 8:
        raise RuntimeError("output must use the native 8:11 bento aspect ratio")
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False

    world = scene.world or bpy.data.worlds.new("PNEUMATIC_WORLD")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.79, 0.80, 0.82, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7

    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)

    camera_data = bpy.data.cameras.new("CAM_PNEUMATIC_INPUT_BENTO")
    camera = bpy.data.objects.new("CAM_PNEUMATIC_INPUT_BENTO", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 240.0
    camera.data.lens = 70.0
    camera.data.clip_start = 1.0
    camera.data.clip_end = 4000.0
    camera.location = (-130.0, -900.0, 470.0)
    look_at(camera, Vector((-130.0, -120.0, 470.0)))
    scene.camera = camera

    light_specs = (
        ("PNEUMATIC_KEY", (-270.0, -430.0, 690.0), 1050.0, 280.0),
        ("PNEUMATIC_FILL", (40.0, -330.0, 590.0), 720.0, 240.0),
        ("PNEUMATIC_RIM", (-80.0, 60.0, 650.0), 900.0, 180.0),
    )
    for name, location, energy, size in light_specs:
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(light)
        light.location = location
        look_at(light, Vector((-120.0, -120.0, 540.0)))


def render_proof(output_dir: Path) -> list[dict]:
    scene = bpy.context.scene
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for frame in PROOF_FRAMES:
        path = frames_dir / f"pose-{frame:04d}.png"
        scene.frame_set(frame)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        records.append({"frame": frame, "filename": path.name, "sha256": sha256(path)})
    return records


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coupler", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--width", type=int, default=400)
    parser.add_argument("--height", type=int, default=550)
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(arguments)


def main():
    args = parse_args()
    if not args.coupler.is_file():
        raise FileNotFoundError(args.coupler)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    configure_render(args.width, args.height)
    contract = configure_animation(args.coupler)
    scene_path = args.output_dir / "pimm-30g--pneumatic-input-proof.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path), check_existing=False)
    proof_frames = render_proof(args.output_dir)
    result = {
        "schema": "maliev.pimm-pneumatic-input-proof/v1",
        "source": {"path": str(args.coupler), "sha256": sha256(args.coupler)},
        "scene": {"path": str(scene_path), "sha256": sha256(scene_path)},
        "contract": {**contract, "resolution": [args.width, args.height], "aspect_ratio": "8:11"},
        "proof_frames": proof_frames,
        "production_publish_authorized": False,
    }
    manifest = args.output_dir / "proof.json"
    manifest.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("PNEUMATIC_INPUT_PROOF=" + json.dumps(result))


if __name__ == "__main__":
    main()
