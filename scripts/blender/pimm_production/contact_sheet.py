"""Build immutable labelled Pillow contact sheets from proof manifests."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Mapping

from .io_contract import atomic_write_json, sha256_file
from .paths import require_within


CELL_WIDTH = 340
CELL_HEIGHT = 310
IMAGE_BOX_HEIGHT = 240
HEADER_HEIGHT = 92
PADDING = 14


def _short_hash(value: object) -> str:
    return str(value)[:12]


def build_contact_sheet(manifest_path: Path, output_path: Path) -> Path:
    """Verify proof hashes, label every cell, and save one contact sheet."""

    from PIL import Image, ImageDraw, ImageFont

    manifest_path = Path(manifest_path).resolve()
    output_root = manifest_path.parent
    output_path = require_within(Path(output_path), output_root)
    evidence_path = output_path.with_name("contact-sheet.json")
    if output_path.exists() or evidence_path.exists():
        raise ValueError("contact sheet output and evidence paths must not preexist")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping) or manifest.get("schema") != "pimm-proof-manifest/v1":
        raise ValueError("contact sheet requires a pimm-proof-manifest/v1 object")
    raw_entries = manifest.get("outputs")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("proof manifest outputs must be a nonempty list")
    entries = sorted(raw_entries, key=lambda item: (item["shot_id"], item["background"]))

    verified: list[tuple[Mapping[str, object], Path]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("proof manifest output entry must be an object")
        relative = entry.get("path")
        if not isinstance(relative, str) or Path(relative).name != relative:
            raise ValueError("proof manifest output path must be one local filename")
        source = require_within(output_root / relative, output_root)
        if not source.is_file():
            raise ValueError(f"proof image is missing: {source}")
        actual_hash = sha256_file(source)
        if actual_hash != str(entry.get("sha256", "")).upper():
            raise ValueError(f"proof image hash mismatch: {source}")
        with Image.open(source) as image:
            if image.size != (entry.get("width"), entry.get("height")):
                raise ValueError(f"proof image dimensions mismatch: {source}")
        verified.append((entry, source))

    columns = min(3, len(verified))
    rows = math.ceil(len(verified) / columns)
    width = PADDING * 2 + columns * CELL_WIDTH
    height = HEADER_HEIGHT + PADDING + rows * CELL_HEIGHT
    sheet = Image.new("RGB", (width, height), (238, 239, 241))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    header = (
        f"{manifest['generation_id']}  status={manifest['status']}  "
        f"scene={_short_hash(manifest['scene_sha256'])}  "
        f"master={_short_hash(manifest['master_sha256'])}  "
        f"material={_short_hash(manifest['material_library_sha256'])}"
    )
    settings = (
        f"stage={manifest['stage']}  resolution={manifest['resolution_percentage']}%  "
        f"samples={manifest['samples']}  denoise={manifest['denoise']}"
    )
    draw.text((PADDING, 18), header, fill=(18, 21, 25), font=font)
    draw.text((PADDING, 42), settings, fill=(48, 54, 61), font=font)
    draw.line((PADDING, 70, width - PADDING, 70), fill=(132, 138, 145), width=1)

    cells: list[dict[str, object]] = []
    for index, (entry, source) in enumerate(verified):
        column = index % columns
        row = index // columns
        left = PADDING + column * CELL_WIDTH
        top = HEADER_HEIGHT + row * CELL_HEIGHT
        draw.rectangle(
            (left, top, left + CELL_WIDTH - PADDING, top + CELL_HEIGHT - PADDING),
            fill=(255, 255, 255),
            outline=(182, 186, 191),
        )
        with Image.open(source) as original:
            preview = original.convert("RGBA").copy()
            preview.thumbnail(
                (CELL_WIDTH - PADDING * 2, IMAGE_BOX_HEIGHT - PADDING),
                Image.Resampling.LANCZOS,
            )
        image_left = left + (CELL_WIDTH - PADDING - preview.width) // 2
        image_top = top + PADDING + (IMAGE_BOX_HEIGHT - PADDING - preview.height) // 2
        backdrop = Image.new("RGB", preview.size, (246, 246, 246))
        if preview.mode == "RGBA":
            backdrop.paste(preview, mask=preview.getchannel("A"))
        else:
            backdrop.paste(preview)
        sheet.paste(backdrop, (image_left, image_top))
        label_top = top + IMAGE_BOX_HEIGHT + 3
        label = f"{entry['shot_id']}  |  {entry['background']}"
        evidence = (
            f"{entry['width']}x{entry['height']}  sha256={_short_hash(entry['sha256'])}"
        )
        draw.text((left + PADDING, label_top), label, fill=(20, 23, 28), font=font)
        draw.text((left + PADDING, label_top + 19), evidence, fill=(68, 73, 80), font=font)
        cells.append(
            {
                "index": index,
                "shot_id": entry["shot_id"],
                "background": entry["background"],
                "dimensions": [entry["width"], entry["height"]],
                "output_sha256": entry["sha256"],
                "cell": {"left": left, "top": top, "width": CELL_WIDTH, "height": CELL_HEIGHT},
            }
        )

    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        sheet.save(temporary, format="PNG")
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    evidence: dict[str, object] = {
        "schema": "pimm-proof-contact-sheet/v1",
        "generation_id": manifest["generation_id"],
        "status": manifest["status"],
        "manifest_path": manifest_path.name,
        "manifest_sha256": sha256_file(manifest_path),
        "contact_sheet_path": output_path.name,
        "contact_sheet_sha256": sha256_file(output_path),
        "header": {
            "scene_sha256": manifest["scene_sha256"],
            "master_sha256": manifest["master_sha256"],
            "material_library_sha256": manifest["material_library_sha256"],
            "resolution_percentage": manifest["resolution_percentage"],
            "samples": manifest["samples"],
        },
        "cells": cells,
    }
    atomic_write_json(evidence_path, evidence)
    return output_path
