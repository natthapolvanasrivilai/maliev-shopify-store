"""Publish homepage WebPs from already-composed Blender pair renders."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


RELEASE_ID = "maliev-homepage-pimm-20260901-r12"
PLACEMENTS = {
    "hero-desktop": (1800, 1200),
    "hero-mobile": (1200, 1500),
    "catalogue": (1086, 1448),
    "navigation": (900, 900),
}
COMPOSITION_IDS = {
    "hero-desktop": "hero-pair-left-minus45",
    "hero-mobile": "hero-pair-left-minus45",
    "catalogue": "catalogue-copy-safe-46-left-minus30",
    "navigation": "navigation-compact-18",
}
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
    bbox = image.getchannel("A").point(lambda value: 255 if value >= 64 else 0).getbbox()
    if bbox is None:
        raise ValueError("render has no visible alpha content")
    return bbox


def _bounds_record(image: Image.Image) -> dict[str, object]:
    left, top, right, bottom = _alpha_bbox(image)
    return {
        "pixels": [left, top, right, bottom],
        "top_ratio": round(top / image.height, 5),
        "bottom_ratio": round((image.height - bottom) / image.height, 5),
        "left_ratio": round(left / image.width, 5),
        "right_ratio": round((image.width - right) / image.width, 5),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument("--asset-dir", type=Path, required=True)
    parser.add_argument("--source-release-id", default=RELEASE_ID)
    arguments = parser.parse_args()
    arguments.asset_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for placement, dimensions in PLACEMENTS.items():
        source = arguments.render_dir / f"{arguments.source_release_id}-{placement}-alpha.png"
        with Image.open(source) as opened:
            image = opened.convert("RGBA")
        if image.size != dimensions:
            raise ValueError(f"unexpected Blender render dimensions for {placement}: {image.size}")
        output = arguments.asset_dir / f"{RELEASE_ID}-{placement}-alpha.webp"
        image.save(output, format="WEBP", lossless=True, method=6)
        with Image.open(output) as check:
            if check.mode != "RGBA" or check.getchannel("A").getextrema() != (0, 255):
                raise ValueError(f"storefront derivative lost useful alpha: {output}")
        records.append({
            "filename": output.name,
            "sha256": sha256_file(output),
            "width": dimensions[0],
            "height": dimensions[1],
            "alpha": True,
            "placement": placement,
            "composition_id": COMPOSITION_IDS[placement],
            "alpha_bbox": _bounds_record(image),
        })

    manifest = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "source_render_release_id": arguments.source_release_id,
        "shadow_source": "Blender Cycles shadow catcher; no post-render alpha edits",
        "renderer": "scripts/blender/pimm_production/blender_homepage_alpha_render.py",
        "finalizer": "scripts/blender/pimm_production/finalize_homepage_pimm_assets.py",
        "composition": "Purpose-staged 30G and 50G pair renders from one Blender scene per placement",
        "masters": MASTER_RECORDS,
        "assets": records,
    }
    (arguments.asset_dir / "maliev-homepage-pimm-assets.v1.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
