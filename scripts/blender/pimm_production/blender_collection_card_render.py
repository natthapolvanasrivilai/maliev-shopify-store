"""Render a fixed collection-card turntable from an authoritative PIMM master.

The opened master remains read-only. This worker creates an ephemeral studio and
rotates a temporary stage around the published machine to produce the three
locked collection views.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Sequence

try:
    from . import blender_master_storefront_render as storefront
except ImportError:  # Blender executes this checked-in file outside package mode.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production import blender_master_storefront_render as storefront


RELEASE_ID = "maliev-pimm-collection-20260901-r01"
RESULT_MARKER = "MALIEV_PIMM_COLLECTION_RENDER_JSON="
OUTPUT_DIMENSIONS = (1200, 1600)
ANGLE_DEGREES = {"front": 0.0, "left": -12.0, "right": 12.0}
MASTER_HASHES = {
    "30G": "98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA",
    "50G": "CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90",
}
RENDER_SIDECAR_SCHEMA = "maliev.pimm-collection-card-render/v1"


def _render_sidecar_path(output_dir: Path, machine: str) -> Path:
    return output_dir / f"{RELEASE_ID}-{machine.lower()}-render.v1.json"


def _write_render_sidecar(
    output_dir: Path,
    machine: str,
    provenance: dict[str, object],
    outputs: list[dict[str, object]],
) -> Path:
    """Persist the renderer evidence that publication validates before copying bytes."""
    sidecar = _render_sidecar_path(output_dir, machine)
    if sidecar.exists():
        raise FileExistsError(f"refusing to overwrite collection render sidecar: {sidecar}")
    payload = {
        "schema": RENDER_SIDECAR_SCHEMA,
        "release_id": RELEASE_ID,
        "machine": machine,
        "provenance": provenance,
        "outputs": outputs,
    }
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sidecar


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", choices=tuple(MASTER_HASHES), required=True)
    parser.add_argument("--expected-master-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, required=True)
    parser.add_argument("--scale", type=float, default=1.0)
    arguments = parser.parse_args(argv)
    if arguments.samples < 1:
        parser.error("--samples must be at least 1")
    if arguments.scale <= 0:
        parser.error("--scale must be greater than 0")
    return arguments


def _collection_camera(
    bpy: Any,
    collection: Any,
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
    scale: float,
) -> tuple[Any, tuple[float, float, float]]:
    """Create one vertical camera, shared unchanged by all collection angles."""
    center = tuple((bounds_min[index] + bounds_max[index]) / 2 for index in range(3))
    width = bounds_max[0] - bounds_min[0]
    depth = bounds_max[1] - bounds_min[1]
    height = bounds_max[2] - bounds_min[2]
    extent = max(width, depth, height) * scale
    target = (center[0], center[1], bounds_min[2] + height * 0.48)
    location = (target[0], target[1] - extent * 3.15, target[2] + height * 0.04)

    data = bpy.data.cameras.new("CAM_COLLECTION_CARD")
    data.type = "PERSP"
    data.lens = 95.0
    data.sensor_width = 36.0
    data.clip_start = 0.1
    data.clip_end = 20_000.0
    data.dof.use_dof = True
    data.dof.aperture_fstop = 11.0
    data.dof.aperture_blades = 11
    camera = bpy.data.objects.new("CAM_COLLECTION_CARD", data)
    collection.objects.link(camera)
    camera.location = location
    storefront._look_at(camera, target)
    focus = bpy.data.objects.new("CAM_COLLECTION_CARD_FOCUS", None)
    focus.location = target
    collection.objects.link(focus)
    data.dof.focus_object = focus
    bpy.context.scene.camera = camera
    return camera, target


def _collection_stage(
    bpy: Any,
    collection: Any,
    meshes: Sequence[Any],
    center: tuple[float, float, float],
) -> Any:
    """Parent published meshes to a temporary origin so all views turn identically."""
    stage = bpy.data.objects.new("PIMM_COLLECTION_STAGE", None)
    collection.objects.link(stage)
    stage.location = center
    bpy.context.view_layer.update()
    for mesh in meshes:
        world_matrix = mesh.matrix_world.copy()
        mesh.parent = stage
        mesh.matrix_world = world_matrix
    return stage


def _configure_collection_render(bpy: Any, samples: int, output: Path) -> None:
    """Reuse the approved world, cyclorama lighting, and Cycles quality settings."""
    storefront._configure_render(
        bpy, OUTPUT_DIMENSIONS[0], OUTPUT_DIMENSIONS[1], samples, output
    )
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = OUTPUT_DIMENSIONS
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    scene.render.film_transparent = False


def render(bpy: Any, arguments: argparse.Namespace) -> dict[str, object]:
    if arguments.expected_master_sha256.upper() != MASTER_HASHES[arguments.machine]:
        raise ValueError(
            f"expected master SHA does not match locked {arguments.machine} master"
        )
    meshes, provenance = storefront._validate_master(
        bpy, arguments.machine, arguments.expected_master_sha256
    )
    bounds_min, bounds_max = storefront._world_bounds(meshes)
    center = tuple((bounds_min[index] + bounds_max[index]) / 2 for index in range(3))
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    sidecar = _render_sidecar_path(output_dir, arguments.machine)
    if sidecar.exists():
        raise FileExistsError(f"refusing to overwrite collection render sidecar: {sidecar}")

    runtime = storefront._runtime_collection(bpy)
    # The shared storefront cyclorama has a 1,000-extents floor span, exceeding
    # this collection contract's minimum 30 extents laterally and cameraward.
    storefront._install_studio(bpy, runtime, bounds_min, bounds_max)
    _collection_camera(bpy, runtime, bounds_min, bounds_max, arguments.scale)
    stage = _collection_stage(bpy, runtime, meshes, center)
    outputs = []
    for angle, degrees in ANGLE_DEGREES.items():
        output = output_dir / f"{RELEASE_ID}-{arguments.machine.lower()}-{angle}.png"
        if output.exists():
            raise FileExistsError(f"refusing to overwrite collection render: {output}")
        stage.rotation_euler[2] = math.radians(ANGLE_DEGREES[angle])
        _configure_collection_render(bpy, arguments.samples, output)
        bpy.ops.render.render(write_still=True)
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Blender did not create collection render: {output}")
        outputs.append({
            "angle": angle,
            "angle_degrees": degrees,
            "path": str(output),
            "width": OUTPUT_DIMENSIONS[0],
            "height": OUTPUT_DIMENSIONS[1],
            "sha256": storefront.sha256_file(output),
        })
    sidecar = _write_render_sidecar(output_dir, arguments.machine, provenance, outputs)
    return {
        "schema": RENDER_SIDECAR_SCHEMA,
        "release_id": RELEASE_ID,
        "machine": arguments.machine,
        "provenance": provenance,
        "outputs": outputs,
        "render_sidecar": str(sidecar),
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
