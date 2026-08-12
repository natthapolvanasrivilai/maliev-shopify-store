"""Build the dedicated PIMM 50G multi-scene product-story project.

Run with Blender 5.2 in background mode while opening the corrected master:
  blender -b <corrected-master.blend> -P create_pimm50_product_story.py -- --render-proofs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SOURCE_BLEND = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-keynote-reveal-v2-regulator-materials.blend")
TARGET_BLEND = SOURCE_BLEND.with_name("PIMM-50g-product-story-v1.blend")
OUTPUT_DIR = SOURCE_BLEND.parent / "renders" / "pimm50-product-story-v1"
SOURCE_SHA256 = "C19DDA7902BE63A2B28A77D3EF349D17555642399A9589B9A06EFCC05EAB882A"
EXPECTED_MACHINE_OBJECTS = 481
PRODUCT_COLLECTION = "Machine_50g"
PREFIX = "PIMM50_STORY_"

LAYOUTS = {
    "desktop": (1800, 1600),
    "mobile": (1350, 1800),
}

CHAPTERS = {
    "REVEAL": {"slug": "reveal", "yaw": -10.0, "target_z": 0.51, "distance": 3.05},
    "OVERVIEW": {"slug": "overview", "yaw": -11.0, "target_z": 0.50, "distance": 3.05},
    "CAPACITY": {"slug": "capacity", "yaw": -16.0, "target_z": 0.73, "distance": 2.80},
    "MELT_ZONE": {"slug": "melt-zone", "yaw": -12.0, "target_z": 0.52, "distance": 2.70},
    "HEATING": {"slug": "heating", "yaw": -20.0, "target_z": 0.65, "distance": 2.80},
    "MOLD_SPACE": {"slug": "mold-space", "yaw": -12.0, "target_z": 0.27, "distance": 2.85},
    "COMPARISON": {"slug": "comparison", "yaw": -8.0, "target_z": 0.49, "distance": 3.30},
    "PURCHASE": {"slug": "purchase", "yaw": -11.0, "target_z": 0.50, "distance": 3.00},
}

SCENE_NAMES = (
    "PIMM50_STORY_REVEAL_DESKTOP", "PIMM50_STORY_REVEAL_MOBILE",
    "PIMM50_STORY_OVERVIEW_DESKTOP", "PIMM50_STORY_OVERVIEW_MOBILE",
    "PIMM50_STORY_CAPACITY_DESKTOP", "PIMM50_STORY_CAPACITY_MOBILE",
    "PIMM50_STORY_MELT_ZONE_DESKTOP", "PIMM50_STORY_MELT_ZONE_MOBILE",
    "PIMM50_STORY_HEATING_DESKTOP", "PIMM50_STORY_HEATING_MOBILE",
    "PIMM50_STORY_MOLD_SPACE_DESKTOP", "PIMM50_STORY_MOLD_SPACE_MOBILE",
    "PIMM50_STORY_COMPARISON_DESKTOP", "PIMM50_STORY_COMPARISON_MOBILE",
    "PIMM50_STORY_PURCHASE_DESKTOP", "PIMM50_STORY_PURCHASE_MOBILE",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-proofs", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def assert_source_immutable() -> tuple[str, int]:
    current = Path(bpy.data.filepath).resolve()
    if current != SOURCE_BLEND.resolve():
        raise RuntimeError(f"Open the corrected master, not {current}")
    source_hash = sha256(SOURCE_BLEND)
    if source_hash != SOURCE_SHA256:
        raise RuntimeError(f"Corrected master hash drifted: {source_hash}")
    collection = bpy.data.collections.get(PRODUCT_COLLECTION)
    if collection is None or len(collection.all_objects) != EXPECTED_MACHINE_OBJECTS:
        raise RuntimeError("Machine_50g object contract failed")
    return source_hash, SOURCE_BLEND.stat().st_mtime_ns


def remove_owned_data() -> None:
    for scene in list(bpy.data.scenes):
        if scene.name.startswith(PREFIX):
            bpy.data.scenes.remove(scene)
    for obj in list(bpy.data.objects):
        if obj.name.startswith(PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)


def point_camera(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def configure_scene(scene: bpy.types.Scene, layout: str) -> None:
    resolution = LAYOUTS[layout]
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.use_file_extension = True
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.15


def create_scenes() -> dict[str, dict[str, bpy.types.Scene]]:
    desktop_source = bpy.data.scenes["PIMM50_Keynote_Desktop"]
    mobile_source = bpy.data.scenes["PIMM50_Keynote_Mobile"]
    scenes: dict[str, dict[str, bpy.types.Scene]] = {}
    for chapter, spec in CHAPTERS.items():
        scenes[chapter] = {}
        for layout, template in (("desktop", desktop_source), ("mobile", mobile_source)):
            scene = template.copy()
            scene.name = f"{PREFIX}{chapter}_{layout.upper()}"
            camera = template.camera.copy()
            camera.data = template.camera.data.copy()
            camera.name = f"{scene.name}_CAMERA"
            scene.collection.objects.link(camera)
            scene.camera = camera
            target = Vector((0.015, 0.0, float(spec["target_z"])))
            distance = float(spec["distance"]) * (0.91 if layout == "mobile" else 1.0)
            yaw = math.radians(float(spec["yaw"]))
            camera.location = Vector((math.sin(yaw) * distance, -math.cos(yaw) * distance, target.z + (0.06 if layout == "desktop" else 0.03)))
            camera.data.lens = 70.0 if layout == "desktop" else 88.0
            camera.data.shift_x = 0.0
            camera.data.dof.use_dof = False
            point_camera(camera, target)
            configure_scene(scene, layout)
            scene["pimm50_story_chapter"] = chapter.lower()
            scene["pimm50_story_layout"] = layout
            scenes[chapter][layout] = scene
    return scenes


def render_proofs(scenes: dict[str, dict[str, bpy.types.Scene]]) -> list[str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for chapter, layouts in scenes.items():
        slug = CHAPTERS[chapter]["slug"]
        for layout, scene in layouts.items():
            output = OUTPUT_DIR / f"pimm50-story-{slug}-{layout}.png"
            scene.render.filepath = str(output)
            bpy.context.window.scene = scene
            bpy.ops.render.render(write_still=True, scene=scene.name)
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError(f"Proof render missing: {output}")
            outputs.append(str(output))
    return outputs


def main() -> None:
    args = parse_args()
    source_hash, source_mtime = assert_source_immutable()
    remove_owned_data()
    scenes = create_scenes()
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET_BLEND), check_existing=False)
    summary = {
        "source": str(SOURCE_BLEND),
        "source_sha256": source_hash,
        "source_mtime_ns": source_mtime,
        "target": str(TARGET_BLEND),
        "machine_objects": len(bpy.data.collections[PRODUCT_COLLECTION].all_objects),
        "scenes": sorted(scene.name for scene in bpy.data.scenes if scene.name.startswith(PREFIX)),
    }
    if args.render_proofs:
        summary["proofs"] = render_proofs(scenes)
        bpy.ops.wm.save_as_mainfile(filepath=str(TARGET_BLEND), check_existing=False)
    if sha256(SOURCE_BLEND) != source_hash or SOURCE_BLEND.stat().st_mtime_ns != source_mtime:
        raise RuntimeError("Corrected source changed during product-story build")
    print("PIMM50_PRODUCT_STORY_SUMMARY_BEGIN")
    print(json.dumps(summary, indent=2))
    print("PIMM50_PRODUCT_STORY_SUMMARY_END")


if __name__ == "__main__":
    main()
