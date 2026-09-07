"""Immutable owner approval and campaign contract for editorial native finals."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Mapping

from .blender_editorial_preview import validate_accepted_editorial_generation
from .io_contract import sha256_file
from .paths import require_within


APPROVED_GENERATION_ID = "editorial-preview-20260830T120711.840572Z-63746b40-bca60b04"
RELEASE_ID = "editorial-release-2026-08-30-r01"
APPROVAL_SCHEMA = "maliev.pimm-editorial-owner-approval/v1"
FINAL_CONTRACT_SCHEMA = "maliev.pimm-editorial-final-contract/v1"
APPROVAL_NAME = "approval-r01.json"
FINAL_CONTRACT_NAME = "campaign-contract-r01.json"
EXPECTED_ACCEPTED_HASHES = {
    "manifest_sha256": "7483C2BE95B5C7A82E039C5CDD50945238D5553259E670B494D33460055FD936",
    "report_sha256": "BB2F4AAC6A585C8F7B7BA2CCFBA90496FA7E2F5A5DE6649E912B7115CB70C6D5",
    "visual_disposition_sha256": "04548BE2EDFBB9C2D0F2408F65EC060458641C14BFC856D43EEE4944B021A4D4",
    "contact_sheet_sha256": "C9C007B537EE84441D0F3A6A59FE946B086D831436A75A3A88095963F354FB04",
}
ALLOWED_SCENE_MUTATIONS = [
    "resolution_x", "resolution_y", "resolution_percentage", "cycles.samples",
    "cycles.use_denoising", "render.filepath", "image_settings.file_format",
    "image_settings.color_mode", "image_settings.color_depth",
]
_APPROVAL_FIELDS = {
    "schema", "revision", "generation_id", "decision", "owner", "notes",
    "approved_at", "manifest", "report", "visual_disposition", "contact_sheet", "shots",
}
_CONTRACT_FIELDS = {
    "schema", "revision", "release_id", "generation_id", "approval", "samples", "denoise",
    "landscape_dimensions", "portrait_dimensions", "archive_format", "delivery_format",
    "web_derivative_format", "allowed_scene_mutations", "shots", "authorized_at",
}
_GENERATION = re.compile(r"^editorial-preview-[A-Za-z0-9T.\-]+$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _exclusive_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _load_exact_json(path: Path, label: str) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is unreadable: {error}") from error


def _authority_json(shot: Mapping[str, object]) -> dict[str, object]:
    authority = shot["authority"]
    if not isinstance(authority, Mapping):
        raise ValueError("accepted shot authority is invalid")
    return dict(authority)


def _accepted_snapshot(asset_root: Path, generation_id: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    if generation_id != APPROVED_GENERATION_ID:
        raise ValueError("release r01 requires the exact owner-approved editorial generation")
    accepted = validate_accepted_editorial_generation(asset_root, generation_id)
    for field, expected in EXPECTED_ACCEPTED_HASHES.items():
        if accepted[field] != expected:
            raise ValueError(f"approved accepted-generation {field} drift")
    shots = []
    for shot in accepted["shots"]:
        shots.append({
            "shot_id": shot["shot_id"],
            "output_relative_path": shot["output_relative_path"],
            "output_path": str(shot["output_path"]),
            "output_sha256": shot["output_sha256"],
            "dimensions": [shot["output_width"], shot["output_height"]],
            "authority": _authority_json(shot),
            "visual_review": dict(shot["visual_review"]),
        })
    return accepted, shots


def record_editorial_owner_approval(
    asset_root: Path,
    generation_id: str,
    *,
    owner: str,
    notes: str,
) -> Path:
    """Exclusively record revision one against all accepted bytes and authorities."""

    asset_root = Path(asset_root).resolve()
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("approval owner is required")
    if not isinstance(notes, str) or not notes.strip():
        raise ValueError("approval notes are required")
    if not isinstance(generation_id, str) or _GENERATION.fullmatch(generation_id) is None:
        raise ValueError("accepted generation ID is invalid")
    accepted, shots = _accepted_snapshot(asset_root, generation_id)
    payload = {
        "schema": APPROVAL_SCHEMA,
        "revision": 1,
        "generation_id": generation_id,
        "decision": "approved",
        "owner": owner.strip(),
        "notes": notes.strip(),
        "approved_at": _utc_now(),
        "manifest": {"path": str(accepted["manifest_path"]), "sha256": accepted["manifest_sha256"]},
        "report": {"path": str(accepted["report_path"]), "sha256": accepted["report_sha256"]},
        "visual_disposition": {"path": str(accepted["visual_disposition_path"]), "sha256": accepted["visual_disposition_sha256"]},
        "contact_sheet": {"path": str(accepted["contact_sheet_path"]), "sha256": accepted["contact_sheet_sha256"]},
        "shots": shots,
    }
    parent = require_within(
        asset_root / "renders" / "approvals" / "editorial-concepts-v1" / generation_id,
        asset_root,
    )
    destination = parent / APPROVAL_NAME
    _exclusive_json(destination, payload)
    validate_editorial_owner_approval(destination, asset_root)
    return destination


def validate_editorial_owner_approval(path: Path, asset_root: Path) -> dict[str, object]:
    """Validate approval schema, exact accepted bytes, and held current authority."""

    asset_root = Path(asset_root).resolve()
    path = require_within(Path(path).resolve(), asset_root)
    payload = _load_exact_json(path, "editorial owner approval")
    if set(payload) != _APPROVAL_FIELDS:
        raise ValueError("editorial owner approval fields are invalid")
    if payload.get("schema") != APPROVAL_SCHEMA or payload.get("revision") != 1:
        raise ValueError("editorial owner approval schema or revision is invalid")
    if payload.get("decision") != "approved":
        raise ValueError("editorial owner approval decision is not approved")
    if not isinstance(payload.get("owner"), str) or not str(payload["owner"]).strip():
        raise ValueError("approval owner is required")
    if not isinstance(payload.get("notes"), str) or not str(payload["notes"]).strip():
        raise ValueError("approval notes are required")
    timestamp = payload.get("approved_at")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise ValueError("approval UTC timestamp is invalid")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("approval UTC timestamp is invalid") from error
    generation_id = str(payload.get("generation_id"))
    accepted, shots = _accepted_snapshot(asset_root, generation_id)
    expected = {
        "manifest": (accepted["manifest_path"], accepted["manifest_sha256"]),
        "report": (accepted["report_path"], accepted["report_sha256"]),
        "visual_disposition": (accepted["visual_disposition_path"], accepted["visual_disposition_sha256"]),
        "contact_sheet": (accepted["contact_sheet_path"], accepted["contact_sheet_sha256"]),
    }
    for field, (expected_path, expected_sha) in expected.items():
        record = payload.get(field)
        if not isinstance(record, Mapping) or set(record) != {"path", "sha256"}:
            raise ValueError(f"approval {field} binding is invalid")
        if Path(str(record["path"])).resolve() != expected_path or record["sha256"] != expected_sha:
            raise ValueError(f"approval {field} hash or path drift")
        if sha256_file(expected_path) != expected_sha:
            raise ValueError(f"approval {field} current hash drift")
    if payload.get("shots") != shots:
        raise ValueError("approval four-shot image/hash/authority binding drift")
    return payload


def authorize_editorial_final_release(approval_path: Path, asset_root: Path, release_id: str) -> Path:
    """Create one exclusive campaign final contract without modifying scene contracts."""

    asset_root = Path(asset_root).resolve()
    if release_id != RELEASE_ID:
        raise ValueError("editorial native final release ID is not authorized")
    approval_path = require_within(Path(approval_path).resolve(), asset_root)
    approval = validate_editorial_owner_approval(approval_path, asset_root)
    payload = {
        "schema": FINAL_CONTRACT_SCHEMA,
        "revision": 1,
        "release_id": release_id,
        "generation_id": approval["generation_id"],
        "approval": {"path": str(approval_path), "sha256": sha256_file(approval_path)},
        "samples": 256,
        "denoise": True,
        "landscape_dimensions": [3840, 2160],
        "portrait_dimensions": [2400, 3000],
        "archive_format": "OPEN_EXR",
        "delivery_format": "PNG",
        "web_derivative_format": "WEBP",
        "allowed_scene_mutations": list(ALLOWED_SCENE_MUTATIONS),
        "shots": approval["shots"],
        "authorized_at": _utc_now(),
    }
    destination = require_within(
        asset_root / "renders" / "final-contracts" / release_id / FINAL_CONTRACT_NAME,
        asset_root,
    )
    _exclusive_json(destination, payload)
    validate_editorial_final_contract(destination, asset_root)
    return destination


def validate_editorial_final_contract(path: Path, asset_root: Path) -> dict[str, object]:
    """Reopen a contract and its approval while all accepted authorities are current."""

    asset_root = Path(asset_root).resolve()
    path = require_within(Path(path).resolve(), asset_root)
    payload = _load_exact_json(path, "editorial final contract")
    if set(payload) != _CONTRACT_FIELDS:
        raise ValueError("editorial final contract fields are invalid")
    if payload.get("schema") != FINAL_CONTRACT_SCHEMA or payload.get("revision") != 1:
        raise ValueError("editorial final contract schema or revision is invalid")
    if payload.get("release_id") != RELEASE_ID:
        raise ValueError("editorial final contract release ID is invalid")
    approval_record = payload.get("approval")
    if not isinstance(approval_record, Mapping) or set(approval_record) != {"path", "sha256"}:
        raise ValueError("editorial final contract approval binding is invalid")
    approval_path = require_within(Path(str(approval_record["path"])).resolve(), asset_root)
    if sha256_file(approval_path) != approval_record.get("sha256"):
        raise ValueError("editorial final contract approval hash drift")
    approval = validate_editorial_owner_approval(approval_path, asset_root)
    expected_policy = {
        "samples": 256, "denoise": True, "landscape_dimensions": [3840, 2160],
        "portrait_dimensions": [2400, 3000], "archive_format": "OPEN_EXR",
        "delivery_format": "PNG", "web_derivative_format": "WEBP",
        "allowed_scene_mutations": ALLOWED_SCENE_MUTATIONS,
    }
    for field, expected in expected_policy.items():
        if payload.get(field) != expected:
            raise ValueError(f"editorial final contract {field} drift")
    if payload.get("generation_id") != approval.get("generation_id") or payload.get("shots") != approval.get("shots"):
        raise ValueError("editorial final contract accepted generation binding drift")
    return payload
