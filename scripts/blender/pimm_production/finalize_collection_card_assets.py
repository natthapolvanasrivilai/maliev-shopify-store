"""Publish PIMM collection-card PNGs and lossless WebP storefront derivatives."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _validate_source(source: Path) -> tuple[int, int]:
    if not source.is_file():
        raise FileNotFoundError(f"missing required collection render: {source}")
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
    return dimensions


def publish(render_dir: Path, asset_dir: Path, samples: int) -> dict[str, object]:
    """Validate all six native renders and write their portable collection manifest."""
    if samples < 1:
        raise ValueError("samples must be at least 1")
    render_dir = render_dir.resolve()
    asset_dir = asset_dir.resolve()
    asset_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for model in ("30g", "50g"):
        for angle, degrees in ANGLE_DEGREES.items():
            basename = f"{RELEASE_ID}-{model}-{angle}"
            source = render_dir / f"{basename}.png"
            width, height = _validate_source(source)
            native = asset_dir / f"{basename}.png"
            storefront = asset_dir / f"{basename}.webp"
            shutil.copyfile(source, native)
            with Image.open(native) as image:
                image.save(storefront, format="WEBP", lossless=True, method=6)
            records.append({
                "model": model,
                "angle": angle,
                "angle_degrees": degrees,
                "native": {
                    "filename": native.name,
                    "width": width,
                    "height": height,
                    "sha256": sha256_file(native),
                },
                "storefront": {
                    "filename": storefront.name,
                    "width": width,
                    "height": height,
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
