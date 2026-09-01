"""Publish PIMM collection-card PNGs and lossless WebP storefront derivatives."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
import struct
from typing import Any, Sequence

from PIL import Image


RELEASE_ID = "maliev-pimm-collection-20260901-r01"
OUTPUT_DIMENSIONS = (1200, 1600)
ANGLE_DEGREES = {"front": 0.0, "left": -12.0, "right": 12.0}
MASTERS = {
    "30g": {
        "filename": "PIMM-30G-MASTER.blend",
        "sha256": "98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA",
    },
    "50g": {
        "filename": "PIMM-50G-MASTER.blend",
        "sha256": "CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90",
    },
}
RENDERER_PATH = "scripts/blender/pimm_production/blender_collection_card_render.py"
FINALIZER_PATH = "scripts/blender/pimm_production/finalize_collection_card_assets.py"
MANIFEST_FILENAME = "maliev-pimm-collection-assets.v1.json"
SHADOW_SOURCE = "Blender Cycles physical studio floor; no post-render shadow compositing"
RENDER_SIDECAR_SCHEMA = "maliev.pimm-collection-card-render/v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _png_ihdr(source: Path) -> tuple[int, int, int, int]:
    with source.open("rb") as stream:
        header = stream.read(33)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR" or len(header) != 33:
        raise ValueError(f"collection render has no valid PNG IHDR: {source}")
    if struct.unpack(">I", header[8:12])[0] != 13:
        raise ValueError(f"collection render has an invalid PNG IHDR length: {source}")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", header[16:29]
    )
    if (bit_depth, color_type) != (16, 2):
        raise ValueError(
            "collection render must be 16-bit RGB PNG "
            f"(IHDR bit depth 16, color type 2): {source}"
        )
    if (compression, filtering, interlace) not in ((0, 0, 0), (0, 0, 1)):
        raise ValueError(f"collection render has unsupported PNG IHDR settings: {source}")
    return width, height, bit_depth, color_type


def _validate_source(source: Path) -> tuple[int, int, str]:
    if not source.is_file():
        raise FileNotFoundError(f"missing required collection render: {source}")
    width, height, _bit_depth, _color_type = _png_ihdr(source)
    with Image.open(source) as image:
        if image.format != "PNG":
            raise ValueError(f"collection render is not a PNG: {source}")
        if image.mode != "RGB":
            raise ValueError(f"collection render is not RGB: {source}")
        dimensions = image.size
    if dimensions != OUTPUT_DIMENSIONS:
        raise ValueError(
            "unexpected collection render dimensions: "
            f"expected {OUTPUT_DIMENSIONS}, got {dimensions} for {source}"
        )
    if dimensions != (width, height):
        raise ValueError(f"collection render PNG dimensions disagree with IHDR: {source}")
    return width, height, sha256_file(source)


def _render_sidecar_path(render_dir: Path, model: str) -> Path:
    return render_dir / f"{RELEASE_ID}-{model}-render.v1.json"


def _read_sidecar(render_dir: Path, model: str) -> dict[str, object]:
    sidecar_path = _render_sidecar_path(render_dir, model)
    if not sidecar_path.is_file():
        raise FileNotFoundError(f"missing required collection render sidecar: {sidecar_path}")
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid collection render sidecar JSON: {sidecar_path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"collection render sidecar must contain an object: {sidecar_path}")
    return payload


def _validated_sidecar_records(render_dir: Path, model: str) -> list[dict[str, object]]:
    sidecar = _read_sidecar(render_dir, model)
    if sidecar.get("schema") != RENDER_SIDECAR_SCHEMA:
        raise ValueError(f"collection render sidecar schema drift for {model}")
    if sidecar.get("release_id") != RELEASE_ID:
        raise ValueError(f"collection render sidecar release drift for {model}")
    if sidecar.get("machine") != model.upper():
        raise ValueError(f"collection render sidecar machine drift for {model}")
    provenance = sidecar.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError(f"collection render sidecar provenance is missing for {model}")
    master = MASTERS[model]
    if provenance.get("master_sha256") != master["sha256"]:
        raise ValueError(f"collection render sidecar master SHA drift for {model}")
    master_path = provenance.get("master_path")
    if not isinstance(master_path, str) or Path(master_path).name != master["filename"]:
        raise ValueError(f"collection render sidecar master identity drift for {model}")
    outputs = sidecar.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != len(ANGLE_DEGREES):
        raise ValueError(f"collection render sidecar outputs are incomplete for {model}")
    records: list[dict[str, object]] = []
    seen_angles: set[str] = set()
    for output in outputs:
        if not isinstance(output, dict):
            raise ValueError(f"collection render sidecar output is invalid for {model}")
        angle = output.get("angle")
        if not isinstance(angle, str) or angle not in ANGLE_DEGREES or angle in seen_angles:
            raise ValueError(f"collection render sidecar angle drift for {model}")
        seen_angles.add(angle)
        if output.get("angle_degrees") != ANGLE_DEGREES[angle]:
            raise ValueError(f"collection render sidecar angle degrees drift for {model}-{angle}")
        if (output.get("width"), output.get("height")) != OUTPUT_DIMENSIONS:
            raise ValueError(f"collection render sidecar dimensions drift for {model}-{angle}")
        source = render_dir / f"{RELEASE_ID}-{model}-{angle}.png"
        recorded_path = output.get("path")
        if not isinstance(recorded_path, str) or Path(recorded_path).name != source.name:
            raise ValueError(f"collection render sidecar source path drift for {model}-{angle}")
        width, height, actual_sha256 = _validate_source(source)
        if output.get("sha256") != actual_sha256:
            raise ValueError(f"collection render sidecar source PNG SHA drift for {model}-{angle}")
        records.append({
            "model": model,
            "angle": angle,
            "angle_degrees": ANGLE_DEGREES[angle],
            "source": source,
            "width": width,
            "height": height,
            "sha256": actual_sha256,
        })
    if seen_angles != set(ANGLE_DEGREES):
        raise ValueError(f"collection render sidecar angle set drift for {model}")
    return records


def publish(render_dir: Path, asset_dir: Path, samples: int) -> dict[str, object]:
    """Validate all six native renders and write their portable collection manifest."""
    if samples < 1:
        raise ValueError("samples must be at least 1")
    render_dir = render_dir.resolve()
    asset_dir = asset_dir.resolve()
    source_records = [
        record
        for model in ("30g", "50g")
        for record in _validated_sidecar_records(render_dir, model)
    ]
    asset_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for source_record in source_records:
        model = str(source_record["model"])
        angle = str(source_record["angle"])
        basename = f"{RELEASE_ID}-{model}-{angle}"
        source = Path(source_record["source"])
        native = asset_dir / f"{basename}.png"
        storefront = asset_dir / f"{basename}.webp"
        shutil.copyfile(source, native)
        with Image.open(native) as image:
            image.save(storefront, format="WEBP", lossless=True, method=6)
        records.append({
            "model": model,
            "angle": angle,
            "angle_degrees": source_record["angle_degrees"],
            "native": {
                "filename": native.name,
                "width": source_record["width"],
                "height": source_record["height"],
                "sha256": sha256_file(native),
            },
            "storefront": {
                "filename": storefront.name,
                "width": source_record["width"],
                "height": source_record["height"],
                "sha256": sha256_file(storefront),
            },
        })
    manifest: dict[str, object] = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "renderer": RENDERER_PATH,
        "finalizer": FINALIZER_PATH,
        "masters": MASTERS,
        "samples": samples,
        "shadow_source": SHADOW_SOURCE,
        "assets": records,
    }
    manifest_path = asset_dir / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument("--asset-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, required=True)
    arguments = parser.parse_args(argv)
    publish(arguments.render_dir, arguments.asset_dir, arguments.samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
