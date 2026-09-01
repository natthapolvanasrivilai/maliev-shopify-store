"""Finalize transparent PIMM homepage renders and build the catalogue lineup."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


RELEASE_ID = "maliev-homepage-pimm-20260901-r01"
MASTER_RECORDS = {
    "30g": {
        "filename": "PIMM-30G-MASTER.blend",
        "sha256": "98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA",
        "foot_contact_spread_m": 0.000009354237340623,
    },
    "50g": {
        "filename": "PIMM-50G-MASTER.blend",
        "sha256": "CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90",
        "foot_contact_spread_m": 0.000009354237340623,
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("render has no visible alpha content")
    if bbox[3] < int(image.height * 0.70):
        raise ValueError(f"render does not reach the grounded lower frame: {bbox}")
    return bbox


def _save_webp(image: Image.Image, output: Path) -> dict[str, object]:
    image.save(output, format="WEBP", lossless=True, method=6)
    with Image.open(output) as check:
        if check.mode != "RGBA" or check.getchannel("A").getextrema() != (0, 255):
            raise ValueError(f"storefront derivative lost useful alpha: {output}")
        width, height = check.size
    return {
        "filename": output.name,
        "sha256": sha256_file(output),
        "width": width,
        "height": height,
        "alpha": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument("--asset-dir", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.asset_dir.mkdir(parents=True, exist_ok=True)

    sources = {}
    records = []
    for model in ("30g", "50g"):
        source = arguments.render_dir / f"{RELEASE_ID}-{model}-alpha.png"
        with Image.open(source) as opened:
            image = opened.convert("RGBA")
        if image.size != (1200, 1500):
            raise ValueError(f"unexpected shared render frame for {model}: {image.size}")
        _alpha_bbox(image)
        sources[model] = image
        output = arguments.asset_dir / f"{RELEASE_ID}-{model}-alpha.webp"
        records.append(_save_webp(image, output))

    bboxes = {model: _alpha_bbox(image) for model, image in sources.items()}
    tallest = max(bbox[3] - bbox[1] for bbox in bboxes.values())
    scale = 930 / tallest
    lineup = Image.new("RGBA", (1086, 1448), (0, 0, 0, 0))
    baseline = 1420
    centers = {"30g": 318, "50g": 770}
    for model in ("30g", "50g"):
        image = sources[model]
        resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
        bbox = resized.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError(f"resized {model} render lost alpha")
        x = round(centers[model] - (bbox[0] + bbox[2]) / 2)
        y = baseline - bbox[3]
        lineup.alpha_composite(resized, (x, y))

    lineup_output = arguments.asset_dir / f"{RELEASE_ID}-lineup-alpha.webp"
    records.append(_save_webp(lineup, lineup_output))
    manifest = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "renderer": "scripts/blender/pimm_production/blender_homepage_alpha_render.py",
        "finalizer": "scripts/blender/pimm_production/compose_homepage_pimm_assets.py",
        "masters": MASTER_RECORDS,
        "assets": records,
    }
    manifest_path = arguments.asset_dir / "maliev-homepage-pimm-assets.v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
