"""Build the immutable 2 x 2 review sheet for editorial preview concepts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from typing import Mapping

from .editorial_concept_contract import EDITORIAL_CAMPAIGN_PATH, load_editorial_campaign
from .io_contract import sha256_file
from .paths import require_within


SHEET_WIDTH = 2560
SHEET_HEIGHT = 1800
CELL_WIDTH = SHEET_WIDTH // 2
CELL_HEIGHT = SHEET_HEIGHT // 2
IMAGE_BOX_HEIGHT = 610
PADDING = 28
MANIFEST_SCHEMA = "maliev.pimm-editorial-preview-campaign/v1"
CONTACT_SHEET_NAME = "sheet-editorial-concepts.png"

_CAMPAIGN = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH)


@dataclass(frozen=True)
class EditorialContactSheetResult:
    """Hash-bound geometry and labels for one generated review sheet."""

    path: Path
    sha256: str
    width: int
    height: int
    cells: tuple[dict[str, object], ...]


def _font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    windows_fonts = Path("C:/Windows/Fonts")
    candidates = (
        windows_fonts / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        windows_fonts / ("arialbd.ttf" if bold else "arial.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow versions before scalable load_default.
        return ImageFont.load_default()


def _load_manifest(path: Path) -> Mapping[str, object]:
    def reject_nonfinite(value: str) -> object:
        raise ValueError(f"contact sheet manifest contains nonfinite numeric evidence: {value}")

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_nonfinite,
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"editorial preview manifest JSON is invalid: {error}") from error

    def reject_decoded_nonfinite(value: object, evidence_path: str = "$") -> None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(
                "contact sheet manifest contains nonfinite numeric evidence "
                f"at {evidence_path}"
            )
        if isinstance(value, Mapping):
            for key, item in value.items():
                reject_decoded_nonfinite(item, f"{evidence_path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                reject_decoded_nonfinite(item, f"{evidence_path}[{index}]")

    reject_decoded_nonfinite(payload)
    if not isinstance(payload, Mapping) or payload.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("contact sheet requires an editorial preview campaign manifest")
    shots = payload.get("shots")
    if not isinstance(shots, list) or len(shots) != 4:
        raise ValueError("contact sheet requires exactly four editorial preview shots")
    expected_ids = [shot.shot_id for shot in _CAMPAIGN.shots]
    if [item.get("shot_id") if isinstance(item, Mapping) else None for item in shots] != expected_ids:
        raise ValueError("contact sheet shots must preserve the exact campaign order")
    return payload


def _verified_inputs(
    manifest: Mapping[str, object], manifest_root: Path
) -> list[tuple[Mapping[str, object], Path]]:
    from PIL import Image

    verified: list[tuple[Mapping[str, object], Path]] = []
    for item in manifest["shots"]:
        if not isinstance(item, Mapping):
            raise ValueError("contact sheet shot record must be an object")
        relative = item.get("output_relative_path")
        if not isinstance(relative, str) or Path(relative).name != relative:
            raise ValueError("contact sheet shot output must be one local PNG filename")
        source = require_within(manifest_root / relative, manifest_root)
        if not source.is_file() or source.suffix.lower() != ".png":
            raise ValueError(f"contact sheet source PNG is missing: {source}")
        if sha256_file(source) != str(item.get("output_sha256", "")).upper():
            raise ValueError(f"contact sheet source hash mismatch: {source}")
        with Image.open(source) as image:
            if image.size != (item.get("output_width"), item.get("output_height")):
                raise ValueError(f"contact sheet source dimensions mismatch: {source}")
            image.verify()
        verified.append((item, source))
    return verified


def _label_values(record: Mapping[str, object]) -> dict[str, str]:
    render = record.get("render")
    authority = record.get("authority")
    set_record = record.get("set")
    if not all(isinstance(value, Mapping) for value in (render, authority, set_record)):
        raise ValueError("contact sheet shot evidence is incomplete")
    scene_hash = str(authority.get("scene_sha256", ""))
    set_signature = str(set_record.get("geometry_signature", ""))
    if len(scene_hash) != 64 or len(set_signature) != 64:
        raise ValueError("contact sheet scene and set signatures must be complete SHA-256 values")
    return {
        "shot_id": str(record["shot_id"]),
        "machine": str(record["machine"]),
        "lens": f"{float(record['focal_length_mm']):g} mm",
        "f_stop": f"f/{float(record['aperture_fstop']):g}",
        "render_engine": str(render.get("engine", "")),
        "set_signature": set_signature,
        "scene_hash_prefix": scene_hash[:12],
        "contact_state": str(record.get("contact_status", "")),
        "master_fingerprint_state": str(record.get("master_fingerprint_status", "")),
        "asset_provenance_state": str(record.get("asset_provenance_status", "")),
    }


def _assert_text_fits(draw: object, cell_left: int, cell_top: int, lines: list[tuple[str, object, int]]) -> None:
    right = cell_left + CELL_WIDTH - PADDING
    bottom = cell_top + CELL_HEIGHT - PADDING
    for text, font, y in lines:
        bounds = draw.textbbox((cell_left + PADDING, y), text, font=font)
        if bounds[2] > right or bounds[3] > bottom:
            raise ValueError(f"contact sheet label does not fit its equal cell: {text}")


def build_editorial_contact_sheet(
    manifest_path: Path,
    output_path: Path,
    *,
    private_staging_root: Path | None = None,
) -> EditorialContactSheetResult:
    """Verify all four PNGs, label every decision field, and save once."""

    from PIL import Image, ImageDraw, ImageOps

    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"editorial preview manifest is missing: {manifest_path}")
    output_root = manifest_path.parent
    output_path = require_within(Path(output_path), output_root)
    if output_path.exists():
        raise ValueError(f"editorial contact sheet already exists: {output_path}")
    if output_path.name != CONTACT_SHEET_NAME:
        raise ValueError("editorial contact sheet output filename is not canonical")
    manifest = _load_manifest(manifest_path)
    if private_staging_root is None:
        if isinstance(manifest.get("generation_id"), str):
            raise ValueError("contact-sheet writes are forbidden after generation authority exists")
    else:
        private_root = Path(private_staging_root).resolve()
        if (
            private_root != output_root
            or not private_root.name.startswith(".editorial-preview-")
            or not private_root.name.endswith(".pending")
        ):
            raise ValueError("contact sheet private staging context is invalid")
    verified = _verified_inputs(manifest, output_root)

    sheet = Image.new("RGB", (SHEET_WIDTH, SHEET_HEIGHT), (231, 233, 236))
    draw = ImageDraw.Draw(sheet)
    title_font = _font(23, bold=True)
    body_font = _font(19)
    hash_font = _font(17)
    cells: list[dict[str, object]] = []
    for index, (record, source) in enumerate(verified):
        column = index % 2
        row = index // 2
        left = column * CELL_WIDTH
        top = row * CELL_HEIGHT
        draw.rectangle(
            (left, top, left + CELL_WIDTH - 1, top + CELL_HEIGHT - 1),
            fill=(246, 247, 248),
            outline=(128, 134, 143),
            width=2,
        )
        image_box = (
            left + PADDING,
            top + PADDING,
            left + CELL_WIDTH - PADDING,
            top + IMAGE_BOX_HEIGHT,
        )
        draw.rectangle(image_box, fill=(220, 223, 226), outline=(171, 176, 183), width=1)
        with Image.open(source) as loaded:
            preview = ImageOps.contain(
                loaded.convert("RGB"),
                (image_box[2] - image_box[0] - 2, image_box[3] - image_box[1] - 2),
                method=Image.Resampling.LANCZOS,
            )
        image_left = image_box[0] + (image_box[2] - image_box[0] - preview.width) // 2
        image_top = image_box[1] + (image_box[3] - image_box[1] - preview.height) // 2
        sheet.paste(preview, (image_left, image_top))

        labels = _label_values(record)
        label_top = top + IMAGE_BOX_HEIGHT + 22
        lines: list[tuple[str, object, int]] = [
            (labels["shot_id"], title_font, label_top),
            (
                f"machine={labels['machine']}  lens={labels['lens']}  "
                f"aperture={labels['f_stop']}  engine={labels['render_engine']}",
                body_font,
                label_top + 39,
            ),
            (f"set={labels['set_signature']}", hash_font, label_top + 76),
            (
                f"scene={labels['scene_hash_prefix']}  contact={labels['contact_state']}  "
                f"master={labels['master_fingerprint_state']}  "
                f"provenance={labels['asset_provenance_state']}",
                body_font,
                label_top + 112,
            ),
            (
                f"framing={record.get('framing_status')}  clipping={record.get('clipping_status')}  "
                f"pixels={record['output_width']}x{record['output_height']}  "
                f"image={str(record['output_sha256'])[:12]}",
                body_font,
                label_top + 149,
            ),
        ]
        _assert_text_fits(draw, left, top, lines)
        for text, font, y in lines:
            draw.text((left + PADDING, y), text, fill=(24, 29, 36), font=font)
        cells.append(
            {
                "index": index,
                "left": left,
                "top": top,
                "width": CELL_WIDTH,
                "height": CELL_HEIGHT,
                "source_relative_path": record["output_relative_path"],
                "source_sha256": record["output_sha256"],
                "source_dimensions": [record["output_width"], record["output_height"]],
                "labels": labels,
            }
        )

    temporary = output_path.with_name(f".{output_path.name}.tmp")
    if temporary.exists():
        raise ValueError(f"editorial contact sheet temporary output already exists: {temporary}")
    try:
        sheet.save(temporary, format="PNG", optimize=False)
        os.rename(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    with Image.open(output_path) as written:
        if written.size != (SHEET_WIDTH, SHEET_HEIGHT):
            raise ValueError("editorial contact sheet dimensions changed during save")
        written.verify()
    return EditorialContactSheetResult(
        path=output_path,
        sha256=sha256_file(output_path),
        width=SHEET_WIDTH,
        height=SHEET_HEIGHT,
        cells=tuple(cells),
    )
