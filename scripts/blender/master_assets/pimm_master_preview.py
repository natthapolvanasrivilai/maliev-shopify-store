"""Render a non-mutating Workbench overview of an open PIMM master."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(blender_args())


def main() -> None:
    import bpy
    from mathutils import Vector

    args = parse_args()
    products = [obj for obj in bpy.data.objects if obj.get("pimm_stable_id")]
    if not products:
        raise RuntimeError("open file contains no PIMM master objects")
    points = [obj.matrix_world @ Vector(corner) for obj in products for corner in obj.bound_box]
    minimum = Vector(tuple(min(point[index] for point in points) for index in range(3)))
    maximum = Vector(tuple(max(point[index] for point in points) for index in range(3)))
    center = (minimum + maximum) * 0.5
    extent = maximum - minimum

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.show_specular_highlight = True
    scene.render.resolution_x = 900
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.92, 0.92, 0.92)

    camera_data = bpy.data.cameras.new("PIMM_PREVIEW_CAMERA_DATA")
    camera = bpy.data.objects.new("PIMM_PREVIEW_CAMERA", camera_data)
    scene.collection.objects.link(camera)
    view_distance = max(extent.length * 1.8, 1.0)
    camera.location = center + Vector((extent.x * 0.75, -view_distance, extent.z * 0.32))
    direction = center - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(extent.z * 1.18, extent.x * 1.35, 0.1)
    camera_data.clip_start = max(extent.length / 100_000.0, 0.001)
    camera_data.clip_end = view_distance * 4.0
    scene.camera = camera
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(args.output)
    bpy.ops.render.render(write_still=True)
    print(
        "PIMM_MASTER_PREVIEW "
        f"objects={len(products)} bounds_min={tuple(round(x, 6) for x in minimum)} "
        f"bounds_max={tuple(round(x, 6) for x in maximum)} output={args.output}"
    )


if __name__ == "__main__":
    main()
