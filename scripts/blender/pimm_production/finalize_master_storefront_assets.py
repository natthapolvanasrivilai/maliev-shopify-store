"""Publish lossless storefront derivatives and a hash-locked PIMM render manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image


RELEASE_ID = "pimm-master-20260901-r05"
ROLES = ("configuration", "controls", "hero", "overview", "tooling")
MASTERS = {
    "30g": {"filename": "PIMM-30G-MASTER.blend", "sha256": "98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA", "mesh_count": 556, "foot_count": 4, "foot_contact_spread_m": 0.000009355},
    "50g": {"filename": "PIMM-50G-MASTER.blend", "sha256": "CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90", "mesh_count": 556, "foot_count": 4, "foot_contact_spread_m": 0.000009355},
    "material_library": {"filename": "PIMM-MATERIAL-LIBRARY.blend", "sha256": "F511A97A32CEA33B633CCE852FA04A4999663C64F41A3E69151923C862AD2F1B"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument("--asset-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=256)
    args = parser.parse_args()
    args.asset_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for model in ("30g", "50g"):
        for role in ROLES:
            filename = f"{RELEASE_ID}-{model}-{role}"
            source = args.render_dir / f"{filename}.png"
            native = args.asset_dir / f"{filename}.png"
            storefront = args.asset_dir / f"{filename}.webp"
            shutil.copyfile(source, native)
            with Image.open(native) as image:
                image.save(storefront, format="WEBP", lossless=True, method=6)
                width, height = image.size
            records.append({
                "model": model,
                "role": role,
                "native": {"filename": native.name, "width": width, "height": height, "sha256": sha256_file(native)},
                "storefront": {"filename": storefront.name, "width": width, "height": height, "sha256": sha256_file(storefront)},
            })
    manifest = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "renderer": "scripts/blender/pimm_production/blender_master_storefront_render.py",
        "lighting": {"engine": "Cycles", "samples": args.samples, "hdri_filename": "studio_kontrast_04_4k.exr", "hdri_sha256": "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06", "camera": "perspective 85-105mm with physical depth of field"},
        "masters": MASTERS,
        "assets": records,
    }
    (args.asset_dir / "pimm-master-storefront-assets.v1.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
