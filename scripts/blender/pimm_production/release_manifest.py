"""Atomic, immutable PIMM final-release manifest construction."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from .io_contract import atomic_write_json, sha256_file


_RELEASE_ID = re.compile(r"^release-[0-9]{4}-[0-9]{2}-[0-9]{2}-r[0-9]{2}$")
_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_MIME_BY_SUFFIX = {".exr": "image/x-exr", ".png": "image/png", ".webp": "image/webp", ".mp4": "video/mp4"}


def _validate_media(path: Path, dimensions: list[object], mime_type: str) -> None:
    """Verify declared local media facts rather than trusting manifest declarations."""

    if mime_type == "image/x-exr":
        header = path.read_bytes()[:4]
        if header != b"v/1\x01":
            raise ValueError("final output EXR header is not genuine")
        return
    from PIL import Image
    with Image.open(path) as image:
        image.load()
        expected_format = "PNG" if mime_type == "image/png" else "WEBP"
        if image.format != expected_format or list(image.size) != dimensions or image.mode != "RGBA":
            raise ValueError("final output declared dimensions, MIME type, or alpha mode drift")
        if image.getchannel("A").getextrema()[1] == 0:
            raise ValueError("final output alpha contains no visible product")


def _load(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"final output manifest cannot be read: {error}") from error
    if not isinstance(payload, Mapping):
        raise ValueError("final output manifest must be an object")
    return payload


def _safe_output_root(value: object, release_id: str) -> str:
    expected = f"renders/final/{release_id}"
    if value != expected:
        raise ValueError("proof/archive/mutable output path is forbidden")
    path = PurePosixPath(expected)
    if path.is_absolute() or ".." in path.parts or any(part in {"proofs", "proof", "archive", "archives", "mutable"} for part in path.parts):
        raise ValueError("proof/archive/mutable output path is forbidden")
    return expected


def _validate_manifest(path: Path, release_id: str) -> tuple[str, str, list[dict[str, object]]]:
    payload = _load(path)
    if payload.get("schema") != "pimm-final-output-manifest/v1":
        raise ValueError("final output manifest schema is invalid")
    if payload.get("release_id") != release_id:
        raise ValueError("final output manifest release ID drift")
    generation = payload.get("generation_id")
    shot_id = payload.get("shot_id")
    if not isinstance(generation, str) or not generation.startswith("proof-") or not isinstance(shot_id, str) or not shot_id:
        raise ValueError("final output manifest generation or shot is invalid")
    _safe_output_root(payload.get("output_root"), release_id)
    approval = payload.get("approval_sha256")
    if not isinstance(approval, str) or _SHA256.fullmatch(approval) is None:
        raise ValueError("final output approval SHA-256 is invalid")
    required = payload.get("required_deliverables")
    if not isinstance(required, list) or set(required) != {"exr", "png", "webp"} or len(required) != 3:
        raise ValueError("final output manifest has absent EXR or contracted transparent deliverable")
    outputs = payload.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("final output manifest outputs are required")
    observed_suffixes: set[str] = set()
    records: list[dict[str, object]] = []
    for item in outputs:
        if not isinstance(item, Mapping):
            raise ValueError("final output entry must be an object")
        logical_id, relative, digest, dimensions, alpha, mime = (
            item.get("logical_asset_id"), item.get("path"), item.get("sha256"), item.get("dimensions"), item.get("alpha"), item.get("mime_type")
        )
        relative_path = PurePosixPath(relative) if isinstance(relative, str) else None
        if not isinstance(logical_id, str) or not logical_id or relative_path is None or relative_path.is_absolute() or ".." in relative_path.parts or len(relative_path.parts) != 1:
            raise ValueError("final output asset identity/path is invalid")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ValueError("final output SHA-256 is invalid")
        if not isinstance(dimensions, list) or len(dimensions) != 2 or not all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in dimensions):
            raise ValueError("final output dimensions are invalid")
        if alpha is not True:
            raise ValueError("final output must preserve transparent alpha")
        expected_mime = _MIME_BY_SUFFIX.get(relative_path.suffix.lower())
        if expected_mime != mime:
            raise ValueError("final output MIME type does not match its immutable path")
        actual = path.parent / Path(*relative_path.parts)
        if not actual.is_file() or actual.is_symlink() or sha256_file(actual) != digest.upper():
            raise ValueError("final output bytes or SHA-256 drift")
        _validate_media(actual, dimensions, str(mime))
        observed_suffixes.add(relative_path.suffix.lower().lstrip("."))
        records.append({
            "logical_asset_id": logical_id,
            "path": str(actual.resolve()),
            "sha256": digest.upper(),
            "dimensions": dimensions,
            "alpha": alpha,
            "mime_type": mime,
            "generation_id": generation,
            "approval_sha256": approval.upper(),
            "release_id": release_id,
            "shot_id": shot_id,
        })
    if not {"exr", "png", "webp"}.issubset(observed_suffixes):
        raise ValueError("absent EXR or contracted transparent deliverable")
    return generation, shot_id, records


def build_release_manifest(release_id: str, approved_outputs: Sequence[Path]) -> Path:
    """Validate complete immutable final families and publish their release marker last."""

    if _RELEASE_ID.fullmatch(release_id) is None:
        raise ValueError("release ID must match release-YYYY-MM-DD-rNN")
    if not approved_outputs:
        raise ValueError("approved final outputs are required")
    all_records: list[dict[str, object]] = []
    generations: set[str] = set()
    shot_ids: set[str] = set()
    release_roots: set[Path] = set()
    for raw_path in approved_outputs:
        path = Path(raw_path).resolve()
        release_root = path.parents[1]
        if release_root.name != release_id or release_root.parent.name != "final":
            raise ValueError("proof/archive/mutable output path is forbidden")
        release_roots.add(release_root)
        generation, shot_id, records = _validate_manifest(path, release_id)
        generations.add(generation)
        shot_ids.add(shot_id)
        all_records.extend(records)
    if len(generations) != 1:
        raise ValueError("mixed proof generations are forbidden")
    if len(release_roots) != 1:
        raise ValueError("release output roots must be one immutable directory")
    logical_ids = [str(record["logical_asset_id"]) for record in all_records]
    if len(logical_ids) != len(set(logical_ids)):
        raise ValueError("duplicate logical asset ID")
    release_root = next(iter(release_roots))
    destination = release_root / "release-manifest.json"
    if destination.exists():
        raise ValueError("release manifest already exists; releases are immutable")
    payload: dict[str, object] = {
        "schema": "pimm-final-release-manifest/v1",
        "release_id": release_id,
        "generation_id": next(iter(generations)),
        "shot_ids": sorted(shot_ids),
        "assets": sorted(all_records, key=lambda record: str(record["logical_asset_id"])),
    }
    # The release manifest is deliberately the final atomic pass marker.
    atomic_write_json(destination, payload)
    return destination
