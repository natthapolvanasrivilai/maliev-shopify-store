"""Author a native 8:11, 24 fps fixture-mounting bento scene and proof frames."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy


SOURCE_FPS = 12
DELIVERY_FPS = 24
SOURCE_END = 456
DELIVERY_END = 912
PROOF_SOURCE_FRAMES = (1, 69, 138, 153, 189, 279, 312, 456)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def action_fcurves(action):
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                yield from channelbag.fcurves


def scale_animation_time(scale: float) -> int:
    point_count = 0
    for action in bpy.data.actions:
        for curve in action_fcurves(action):
            for point in curve.keyframe_points:
                for coordinate in (point.co, point.handle_left, point.handle_right):
                    coordinate.x = 1 + ((coordinate.x - 1) * scale)
                point_count += 1
            curve.update()
    return point_count


def delivery_frame(source_frame: int) -> int:
    return 1 + ((source_frame - 1) * (DELIVERY_FPS // SOURCE_FPS))


def configure_scene(args) -> dict:
    scene = bpy.context.scene
    if scene.frame_start != 1 or scene.frame_end != SOURCE_END:
        raise RuntimeError(f"unexpected source frame range {scene.frame_start}..{scene.frame_end}")
    if scene.render.fps != SOURCE_FPS or scene.render.fps_base != 1:
        raise RuntimeError(f"unexpected source fps {scene.render.fps}/{scene.render.fps_base}")
    if scene.camera is None or scene.camera.name != "CAM_STOREFRONT":
        raise RuntimeError("CAM_STOREFRONT is not the active camera")

    scaled_points = scale_animation_time(DELIVERY_FPS / SOURCE_FPS)
    scene.frame_end = DELIVERY_END
    scene.render.fps = DELIVERY_FPS
    scene.render.fps_base = 1
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.use_persistent_data = True

    camera = scene.camera
    camera.data.sensor_fit = "VERTICAL"
    camera.data.shift_y = args.shift_y

    return {
        "resolution": [args.width, args.height],
        "aspect_ratio": "8:11",
        "fps": DELIVERY_FPS,
        "frames": DELIVERY_END,
        "duration_seconds": DELIVERY_END / DELIVERY_FPS,
        "samples": args.samples,
        "camera": camera.name,
        "camera_lens_mm": camera.data.lens,
        "camera_sensor_fit": camera.data.sensor_fit,
        "camera_shift_y": camera.data.shift_y,
        "scaled_keyframe_points": scaled_points,
    }


def render_proof_frames(output_dir: Path) -> list[dict]:
    scene = bpy.context.scene
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for source_frame in PROOF_SOURCE_FRAMES:
        frame = delivery_frame(source_frame)
        output = frames_dir / f"pose-{frame:04d}.png"
        scene.frame_set(frame)
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)
        rendered.append({"source_frame": source_frame, "frame": frame, "filename": output.name, "sha256": sha256(output)})
    return rendered


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--width", type=int, default=400)
    parser.add_argument("--height", type=int, default=550)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--shift-y", type=float, default=-0.28)
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(arguments)


def main():
    args = parse_args()
    if args.width * 11 != args.height * 8:
        raise RuntimeError("output must use the native 8:11 bento aspect ratio")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    source_hash = sha256(args.source)
    contract = configure_scene(args)
    scene_path = args.output_dir / "pimm-30g--fixture-mounting-portrait--front.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path), check_existing=False)
    rendered = render_proof_frames(args.output_dir)
    result = {
        "schema": "maliev.pimm-fixture-bento-portrait-proof/v1",
        "source": {"path": str(args.source), "sha256": source_hash},
        "scene": {"path": str(scene_path), "sha256": sha256(scene_path)},
        "contract": contract,
        "proof_frames": rendered,
        "production_publish_authorized": False,
    }
    (args.output_dir / "proof.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("FIXTURE_BENTO_PROOF " + json.dumps(result))


if __name__ == "__main__":
    main()
