"""Build unique, tightly art-directed homepage composites from master renders."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


RELEASE_ID = "maliev-homepage-pimm-20260901-r02"
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
    if bbox[3] < int(image.height * 0.70):
        raise ValueError(f"render does not reach the grounded lower frame: {bbox}")
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


def _save_webp(image: Image.Image, output: Path, placement: str) -> dict[str, object]:
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
        "placement": placement,
        "alpha_bbox": _bounds_record(image),
    }


def _visible(image: Image.Image) -> Image.Image:
    return image.crop(_alpha_bbox(image))


def _sanitize_alpha(image: Image.Image) -> Image.Image:
    clean = image.copy()
    alpha = clean.getchannel("A").point(lambda value: 0 if value < 64 else value)
    clean.putalpha(alpha)
    return clean


def _composite_pair(sources: dict[str, Image.Image], size: tuple[int, int], height_ratio: float, centers: tuple[float, float]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    visible = {model: _visible(image) for model, image in sources.items()}
    target_height = round(size[1] * height_ratio)
    baseline = size[1] - round(size[1] * 0.015)
    for model, center_ratio in zip(("30g", "50g"), centers, strict=True):
        image = visible[model]
        scale = target_height / image.height
        resized = image.resize((round(image.width * scale), target_height), Image.Resampling.LANCZOS)
        x = round(size[0] * center_ratio - resized.width / 2)
        canvas.alpha_composite(resized, (x, baseline - resized.height))
    return canvas


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
            image = _sanitize_alpha(opened.convert("RGBA"))
        if image.size != (1200, 1500):
            raise ValueError(f"unexpected shared render frame for {model}: {image.size}")
        _alpha_bbox(image)
        sources[model] = image
    compositions = {
        "hero-desktop": _composite_pair(sources, (1800, 1200), 0.96, (0.58, 0.84)),
        "hero-mobile": _composite_pair(sources, (1200, 1500), 0.96, (0.34, 0.72)),
        "catalogue": _composite_pair(sources, (1086, 1448), 0.96, (0.30, 0.72)),
        "navigation": _composite_pair(sources, (900, 900), 0.96, (0.18, 0.77)),
    }
    for placement, image in compositions.items():
        output = arguments.asset_dir / f"{RELEASE_ID}-{placement}-alpha.webp"
        records.append(_save_webp(image, output, placement))
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
