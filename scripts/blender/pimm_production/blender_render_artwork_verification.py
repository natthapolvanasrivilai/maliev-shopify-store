"""Render full-frame and close-up evidence for governed PIMM artwork."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Iterable, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
from scripts.blender.pimm_production.published_artwork import (
    ARTWORK_SPECS_BY_MACHINE,
    capture_published_artwork,
)
from scripts.blender.pimm_production.scene_contract import SceneContract


MARKER = "PIMM_ARTWORK_RENDER_JSON="


def crop_border(
    projected_points: Iterable[tuple[float, float]],
    *,
    padding: float = 0.5,
    minimum_span: float = 0.08,
) -> tuple[float, float, float, float]:
    """Return a padded, clamped Blender border from normalized image points."""

    points = list(projected_points)
    if not points:
        raise ValueError("at least one projected point is required")
    x_min = min(point[0] for point in points)
    x_max = max(point[0] for point in points)
    y_min = min(point[1] for point in points)
    y_max = max(point[1] for point in points)
    x_span = max(x_max - x_min, minimum_span)
    y_span = max(y_max - y_min, minimum_span)
    x_center = (x_min + x_max) / 2.0
    y_center = (y_min + y_max) / 2.0
    half_x = x_span * (1.0 + 2.0 * padding) / 2.0
    half_y = y_span * (1.0 + 2.0 * padding) / 2.0
    return tuple(
        round(value, 8)
        for value in (
            max(0.0, x_center - half_x),
            min(1.0, x_center + half_x),
            max(0.0, y_center - half_y),
            min(1.0, y_center + half_y),
        )
    )


def _projected_object_border(bpy: object, obj: object) -> tuple[float, float, float, float]:
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    scene = bpy.context.scene
    camera = scene.camera
    points = []
    for corner in obj.bound_box:
        projected = world_to_camera_view(scene, camera, obj.matrix_world @ Vector(corner))
        if projected.z > 0:
            points.append((float(projected.x), float(projected.y)))
    return crop_border(points, padding=0.75, minimum_span=0.08)


def _render(
    bpy: object,
    output: Path,
    *,
    width: int,
    height: int,
    samples: int,
    border: tuple[float, float, float, float] | None,
) -> dict[str, object]:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = str(output)
    scene.render.use_file_extension = True
    scene.render.use_border = border is not None
    scene.render.use_crop_to_border = border is not None
    if border is not None:
        scene.render.border_min_x, scene.render.border_max_x, scene.render.border_min_y, scene.render.border_max_y = border
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    if not output.is_file():
        raise RuntimeError(f"Blender did not write verification render: {output}")
    return {
        "path": str(output),
        "sha256": sha256_file(output),
        "bytes": output.stat().st_size,
        "width": width,
        "height": height,
        "samples": samples,
        "border": list(border) if border is not None else None,
        "engine": scene.render.engine,
    }


def render_verification(
    bpy: object,
    machine: str,
    contract_path: Path,
    output_root: Path,
) -> dict[str, object]:
    from scripts.blender.pimm_production.blender_scene_validator import (
        validate_open_render_scene,
    )

    contract = SceneContract.from_json(contract_path)
    errors = validate_open_render_scene(
        bpy, contract, contract_snapshot_sha256=sha256_file(contract_path)
    )
    if errors:
        raise RuntimeError("scene validation failed: " + "; ".join(errors))
    published = bpy.data.collections.get("PIMM_PUBLISHED")
    records, capture_errors = capture_published_artwork(published, machine)
    if capture_errors or len(records) != 2:
        raise RuntimeError("artwork capture failed: " + "; ".join(capture_errors))

    destination = require_within(output_root.resolve(), ASSET_ROOT / "renders" / "verification")
    outputs = [
        _render(
            bpy,
            destination / f"pimm-{machine.lower()}--hero--front--artwork.png",
            width=1800,
            height=2200,
            samples=32,
            border=None,
        )
    ]
    for spec in ARTWORK_SPECS_BY_MACHINE[machine]:
        obj = bpy.data.objects.get(spec.object_name)
        if obj is None:
            raise RuntimeError(f"linked artwork object is missing: {spec.object_name}")
        border = _projected_object_border(bpy, obj)
        outputs.append(
            _render(
                bpy,
                destination / f"pimm-{machine.lower()}--{spec.role}.png",
                width=5400,
                height=6600,
                samples=48,
                border=border,
            )
        )
    return {
        "schema_version": 1,
        "machine": machine,
        "scene": str(Path(bpy.data.filepath).resolve()),
        "scene_sha256": sha256_file(Path(bpy.data.filepath).resolve()),
        "contract": str(contract_path.resolve()),
        "artwork": records,
        "renders": outputs,
    }


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", choices=tuple(ARTWORK_SPECS_BY_MACHINE), required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    import bpy

    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else sys.argv[1:]
    )
    report = render_verification(
        bpy, arguments.machine, arguments.contract, arguments.output_root
    )
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(MARKER + json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
