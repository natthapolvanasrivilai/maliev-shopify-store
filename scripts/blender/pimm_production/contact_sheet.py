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


def _campaign_review_items(
    group_name: str,
    members: list[Mapping[str, object]],
) -> list[tuple[Mapping[str, object], str | None]]:
    """Return presentation frames; literal crops remain evidence, not hero content."""

    return [(shot, None) for shot in members]


def _write_campaign_group_sheet(
    manifest: Mapping[str, object],
    members: list[Mapping[str, object]],
    name: str,
    asset_root: Path,
    output_path: Path,
) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    review_items = _campaign_review_items(name, members)
    columns = min(3, len(review_items))
    rows = math.ceil(len(review_items) / columns)
    cell_w, cell_h, header_h = 520, 430, 112
    sheet = Image.new("RGB", (columns * cell_w, header_h + rows * cell_h), (235, 237, 240))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 18), f"PIMM proof campaign | {manifest['generation_id']} | {name}", fill=(12, 16, 22), font=font)
    draw.text((18, 44), f"status={manifest['status']}  shots={len(members)}  fingerprints_unchanged={manifest['fingerprints_unchanged']}", fill=(45, 51, 60), font=font)
    draw.text((18, 68), "Preview resolution only - presentation frames show complete component assemblies", fill=(45, 51, 60), font=font)
    for index, (shot, crop_name) in enumerate(review_items):
        left = (index % columns) * cell_w
        top = header_h + (index // columns) * cell_h
        if crop_name is None:
            relative_image = shot["outputs"]["white"]
            expected_hash = shot["output_hashes"]["white"]
        else:
            relative_image = shot["crops"][crop_name]
            expected_hash = shot["crop_hashes"][crop_name]
        image_path = require_within(asset_root / relative_image, asset_root)
        if sha256_file(image_path) != expected_hash:
            raise ValueError(f"campaign sheet input hash mismatch: {shot['shot_id']}")
        with Image.open(image_path) as loaded:
            preview = loaded.convert("RGB")
            preview.thumbnail((cell_w - 28, 315), Image.Resampling.LANCZOS)
        x = left + (cell_w - preview.width) // 2
        y = top + 10 + (315 - preview.height) // 2
        sheet.paste(preview, (x, y))
        margins = shot["alpha_margins"]
        labels = [
            shot["shot_id"] + (f" | 100% {crop_name}" if crop_name else ""),
            f"{shot['output_width']}x{shot['output_height']} ({shot['aspect']})  {shot['lens_mm']}mm  f/{shot['f_stop']}",
            f"gen={manifest['generation_id']}  scene={shot['scene_sha256'][:12]}",
            f"product={margins['product']} shadow={margins['shadow']}  contact={shot['contact_status']}",
        ]
        for line, label in enumerate(labels):
            draw.text((left + 14, top + 330 + line * 20), label, fill=(18, 22, 28), font=font)
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise ValueError(f"campaign contact sheet already exists: {output_path}")
    temporary = output_path.with_suffix(".png.tmp")
    sheet.save(temporary, format="PNG")
    os.replace(temporary, output_path)
    return output_path


def build_campaign_component_detail_sheet(
    manifest_path: Path,
    output_path: Path,
) -> Path:
    """Build a separate immutable review sheet from complete detail frames."""

    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "maliev.pimm-campaign-proof/v1":
        raise ValueError("campaign contact sheets require a campaign proof manifest")
    shots = manifest.get("shots")
    if not isinstance(shots, list) or len(shots) != 22:
        raise ValueError("campaign contact sheets require exactly 22 shots")
    members = [shot for shot in shots if shot["purpose"] == "detail"]
    return _write_campaign_group_sheet(
        manifest, members, "detail-components", manifest_path.parent, output_path
    )


def build_campaign_contact_sheets(
    manifest_path: Path,
    output_root: Path,
) -> list[Path]:
    """Build the immutable campaign index and review-family sheets."""

    manifest_path = Path(manifest_path).resolve()
    output_root = Path(output_root).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "maliev.pimm-campaign-proof/v1":
        raise ValueError("campaign contact sheets require a campaign proof manifest")
    shots = manifest.get("shots")
    if not isinstance(shots, list) or len(shots) != 22:
        raise ValueError("campaign contact sheets require exactly 22 shots")

    groups = {
        "campaign": shots,
        "model-30g": [shot for shot in shots if "30G" in shot["machines"]],
        "model-50g": [shot for shot in shots if "50G" in shot["machines"]],
        "hero": [shot for shot in shots if shot["purpose"] == "hero"],
        "editorial": [shot for shot in shots if shot["purpose"] in {"editorial", "comparison"}],
        "detail": [shot for shot in shots if shot["purpose"] == "detail"],
        "workshop": [shot for shot in shots if shot["purpose"] == "workshop"],
    }
    written: list[Path] = []
    for name, members in groups.items():
        if not members:
            continue
        path = output_root / f"sheet-{name}.png"
        written.append(_write_campaign_group_sheet(manifest, members, name, output_root, path))
    return written


def _short_hash(value: object) -> str:
    return str(value)[:12]


def build_contact_sheet(
    manifest_path: Path,
    output_path: Path,
    *,
    evidence_path: Path | None = None,
    published_manifest_name: str | None = None,
    published_output_name: str | None = None,
) -> Path:
    """Verify proof hashes, label every cell, and save one contact sheet."""

    from PIL import Image, ImageDraw, ImageFont

    manifest_path = Path(manifest_path).resolve()
    output_root = manifest_path.parent
    output_path = require_within(Path(output_path), output_root)
    evidence_path = (
        output_path.with_name("contact-sheet.json")
        if evidence_path is None
        else require_within(Path(evidence_path), output_root)
    )
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
        "manifest_path": published_manifest_name or manifest_path.name,
        "manifest_sha256": sha256_file(manifest_path),
        "contact_sheet_path": published_output_name or output_path.name,
        "contact_sheet_sha256": sha256_file(output_path),
        "header": {
            "stage": manifest["stage"],
            "denoise": manifest["denoise"],
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
