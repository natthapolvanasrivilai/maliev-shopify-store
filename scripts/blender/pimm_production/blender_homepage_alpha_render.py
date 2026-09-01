"""Render one authoritative PIMM master onto a shared transparent homepage frame.

The source Blend file stays read-only. Both models use the same perspective,
camera distance, target height, output aspect ratio, and z=0 contact plane so
their relative scale remains truthful when the storefront places them together.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence


sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_master_storefront_render import (  # noqa: E402
    EXPECTED_MASTER_NAMES,
    FOOT_TOLERANCE,
    _configure_render,
    _install_studio,
    _look_at,
    _runtime_collection,
    _validate_master,
    _world_bounds,
    sha256_file,
)


RELEASE_ID = "maliev-homepage-pimm-20260901-r02"
RESULT_MARKER = "MALIEV_HOMEPAGE_ALPHA_RENDER_JSON="
FRAME_HEIGHT_M = 1014.5
FRAME_WIDTH = 1200
FRAME_HEIGHT = 1500


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", choices=tuple(EXPECTED_MASTER_NAMES), required=True)
    parser.add_argument("--expected-master-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=128)
    parser.add_argument("--replace-working-output", action="store_true")
    return parser.parse_args(argv)


def _shared_camera(
    bpy: Any,
    collection: Any,
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
) -> Any:
    center_x = (bounds_min[0] + bounds_max[0]) / 2
    center_y = (bounds_min[1] + bounds_max[1]) / 2
    target = (center_x, center_y, FRAME_HEIGHT_M * 0.5)
    location = (center_x, center_y - FRAME_HEIGHT_M * 2.90, target[2] - FRAME_HEIGHT_M * 0.03)

    data = bpy.data.cameras.new("CAM_HOMEPAGE_SHARED")
    data.type = "PERSP"
    data.lens = 95.0
    data.sensor_width = 36.0
    data.clip_start = 0.1
    data.clip_end = 20_000.0
    data.dof.use_dof = True
    data.dof.aperture_fstop = 11.0
    data.dof.aperture_blades = 11
    camera = bpy.data.objects.new("CAM_HOMEPAGE_SHARED", data)
    collection.objects.link(camera)
    camera.location = location
    _look_at(camera, target)

    focus = bpy.data.objects.new("CAM_HOMEPAGE_SHARED_FOCUS", None)
    focus.location = target
    collection.objects.link(focus)
    data.dof.focus_object = focus
    bpy.context.scene.camera = camera
    return camera


def render(bpy: Any, arguments: argparse.Namespace) -> dict[str, object]:
    meshes, provenance = _validate_master(bpy, arguments.machine, arguments.expected_master_sha256)
    bounds_min, bounds_max = _world_bounds(meshes)
    if abs(bounds_min[2]) > FOOT_TOLERANCE:
        raise ValueError(f"published assembly does not meet the shared z=0 ground plane: {bounds_min[2]}")

    runtime = _runtime_collection(bpy)
    _install_studio(bpy, runtime, bounds_min, bounds_max)
    cyclorama = bpy.data.objects.get("PIMM_WHITE_CYCLORAMA")
    if cyclorama is None:
        raise ValueError("runtime studio did not create its physical ground surface")
    cyclorama.is_shadow_catcher = True
    _shared_camera(bpy, runtime, bounds_min, bounds_max)

    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{RELEASE_ID}-{arguments.machine.lower()}-alpha.png"
    if output.exists() and not arguments.replace_working_output:
        raise FileExistsError(f"refusing to overwrite homepage alpha render: {output}")

    _configure_render(bpy, FRAME_WIDTH, FRAME_HEIGHT, arguments.samples, output)
    scene = bpy.context.scene
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.exposure = 0.35
    scene.compositing_node_group = None
    bpy.ops.render.render(write_still=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Blender did not create homepage alpha render: {output}")

    return {
        "schema": "maliev.homepage-pimm-alpha-render/v1",
        "release_id": RELEASE_ID,
        "machine": arguments.machine,
        "provenance": provenance,
        "output": {
            "path": str(output),
            "width": FRAME_WIDTH,
            "height": FRAME_HEIGHT,
            "sha256": sha256_file(output),
        },
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
