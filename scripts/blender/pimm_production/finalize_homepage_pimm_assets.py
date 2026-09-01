"""Publish homepage WebPs from already-composed Blender pair renders."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


RELEASE_ID = "maliev-homepage-pimm-20260901-r05"
GROUND_SHADOW_MAX_ALPHA = 220
GROUND_SHADOW_FULL_WEIGHT_ALPHA = 128
GROUND_SHADOW_OPACITY = 0.42
GROUND_SHADOW_START_RATIO = 0.82
GROUND_SHADOW_END_RATIO = 0.985
GROUND_SHADOW_EDGE_RATIO = 0.06
GROUND_SHADOW_LEFT_OUTSET_RATIO = 0.08
GROUND_SHADOW_RIGHT_OUTSET_RATIO = 0.05
PLACEMENTS = {
    "hero-desktop": (1800, 1200),
    "hero-mobile": (1200, 1500),
    "catalogue": (1086, 1448),
    "navigation": (900, 900),
}
COMPOSITION_IDS = {
    "hero-desktop": "hero-pair-45",
    "hero-mobile": "hero-pair-45",
    "catalogue": "catalogue-stagger-minus32",
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


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def _soften_ground_shadow(image: Image.Image, placement: str) -> Image.Image:
    """Keep contact shadows while feathering the broad catcher before frame edges."""
    if not placement.startswith("hero-"):
        alpha = image.getchannel("A").point(lambda value: 0 if value < 64 else value)
        image.putalpha(alpha)
        return image

    softened = image.copy()
    pixels = softened.load()
    width, height = softened.size
    subject_bbox = softened.getchannel("A").point(
        lambda value: 255 if value >= GROUND_SHADOW_MAX_ALPHA else 0
    ).getbbox()
    if subject_bbox is None:
        raise ValueError(f"{placement} render has no opaque machine subject")
    subject_left, _subject_top, subject_right, _subject_bottom = subject_bbox
    start_y = round(height * GROUND_SHADOW_START_RATIO)
    end_y = round(height * GROUND_SHADOW_END_RATIO)
    edge_width = max(1, round(width * GROUND_SHADOW_EDGE_RATIO))
    shadow_left = max(0, subject_left - round(width * GROUND_SHADOW_LEFT_OUTSET_RATIO))
    shadow_right = min(width - 1, subject_right + round(width * GROUND_SHADOW_RIGHT_OUTSET_RATIO))
    fade_height = max(1, end_y - start_y)
    weight_range = max(1, GROUND_SHADOW_MAX_ALPHA - GROUND_SHADOW_FULL_WEIGHT_ALPHA)

    for y in range(start_y, height):
        vertical_fade = 1.0 - _smoothstep((y - start_y) / fade_height)
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0 or alpha >= GROUND_SHADOW_MAX_ALPHA:
                continue
            shadow_weight = _smoothstep((GROUND_SHADOW_MAX_ALPHA - alpha) / weight_range)
            edge_fade = min(
                _smoothstep((x - shadow_left) / edge_width),
                _smoothstep((shadow_right - x) / edge_width),
            )
            retained = (1.0 - shadow_weight) + shadow_weight * GROUND_SHADOW_OPACITY * vertical_fade * edge_fade
            new_alpha = round(alpha * retained)
            pixels[x, y] = (red, green, blue, new_alpha if new_alpha >= 3 else 0)
    return softened


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument("--asset-dir", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.asset_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for placement, dimensions in PLACEMENTS.items():
        source = arguments.render_dir / f"{RELEASE_ID}-{placement}-alpha.png"
        with Image.open(source) as opened:
            image = opened.convert("RGBA")
        if image.size != dimensions:
            raise ValueError(f"unexpected Blender render dimensions for {placement}: {image.size}")
        image = _soften_ground_shadow(image, placement)
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
