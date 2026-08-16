"""Immutable, hash-bound owner decisions for reviewed PIMM proof renders."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Mapping

from .io_contract import sha256_file


_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_DECISIONS = frozenset({"approved", "rejected"})
_APPROVAL_SCHEMA = "pimm-owner-approval/v1"


def _canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest().upper()


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a 64-character SHA-256")
    return value.upper()


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _create_immutable_json(path: Path, payload: Mapping[str, object]) -> None:
    """Create a decision exactly once using the platform exclusive-create primitive."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_BINARY)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _proof_output_paths(proof_manifest_path: Path, proof: Mapping[str, object]) -> dict[str, str]:
    outputs = proof.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("proof manifest must contain output evidence")
    result: dict[str, str] = {}
    for item in outputs:
        entry = _mapping(item, "proof output")
        path = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(path, str) or not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise ValueError("proof output path must be a canonical relative path")
        result[path] = _sha(digest, f"proof output {path} SHA-256")
    if len(result) != len(outputs):
        raise ValueError("proof manifest contains duplicate output paths")
    return dict(sorted(result.items()))


def _extract_approval_evidence(proof_manifest_path: Path) -> tuple[dict[str, str], dict[str, object], str, dict[str, str]]:
    proof = json.loads(proof_manifest_path.read_text(encoding="utf-8"))
    proof = _mapping(proof, "proof manifest")
    if proof.get("schema") != "pimm-proof-manifest/v1" or proof.get("status") != "pass":
        raise ValueError("proof manifest must be a passing pimm-proof-manifest/v1")
    generation = proof.get("generation_id")
    if not isinstance(generation, str) or not generation.startswith("proof-"):
        raise ValueError("proof manifest generation_id must be a proof generation")
    render = _mapping(proof.get("render"), "proof render")
    fingerprints = _mapping(render.get("fingerprints"), "proof fingerprints")
    before = _mapping(fingerprints.get("before"), "proof before fingerprints")
    source = _mapping(before.get("source"), "proof source fingerprint")
    authored = _mapping(render.get("authored_settings"), "proof authored settings")
    before_settings = _mapping(authored.get("before"), "proof authored settings before")
    after_settings = _mapping(authored.get("after"), "proof authored settings after")
    if before_settings != after_settings:
        raise ValueError("proof authored settings drifted before owner approval")
    image_settings = _mapping(render.get("image_settings"), "proof image settings")
    dimensions = render.get("actual_dimensions")
    if not isinstance(dimensions, list) or len(dimensions) != 2 or not all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in dimensions):
        raise ValueError("proof actual_dimensions must contain two positive integers")
    alpha_mode = image_settings.get("color_mode")
    if not isinstance(alpha_mode, str) or alpha_mode != "RGBA":
        raise ValueError("proof image settings must require RGBA alpha")
    samples = render.get("samples")
    if not isinstance(samples, int) or isinstance(samples, bool) or samples <= 0:
        raise ValueError("proof render samples must be a positive integer")
    contact_sheet = proof_manifest_path.parent / "contact-sheet.png"
    if not contact_sheet.is_file():
        raise ValueError("proof contact sheet is required for owner approval")
    inputs = {
        "source_sha256": _sha(source.get("sha256"), "proof source SHA-256"),
        "master_sha256": _sha(proof.get("master_sha256"), "proof master SHA-256"),
        "material_library_sha256": _sha(proof.get("material_library_sha256"), "proof material library SHA-256"),
        "scene_sha256": _sha(proof.get("scene_sha256"), "proof scene SHA-256"),
        "proof_manifest_sha256": sha256_file(proof_manifest_path),
        "proof_contract_sha256": _sha(render.get("proof_contract_sha256"), "proof contract SHA-256"),
        "contact_sheet_sha256": sha256_file(contact_sheet),
    }
    render_settings: dict[str, object] = {
        "camera_sha256": _canonical_json_sha256(before_settings.get("camera")),
        "lights_sha256": _canonical_json_sha256(before_settings.get("lights")),
        "world_sha256": _canonical_json_sha256(before_settings.get("world")),
        "compositor_sha256": _canonical_json_sha256(before_settings.get("compositor")),
        "render_settings_sha256": _canonical_json_sha256(before_settings.get("render")),
        "composition_sha256": _canonical_json_sha256(proof.get("qa")),
        "output_dimensions": dimensions,
        "alpha_mode": alpha_mode,
        "proof_samples": samples,
    }
    return inputs, render_settings, generation, _proof_output_paths(proof_manifest_path, proof)


def validate_approval_payload(payload: Mapping[str, object], current_inputs: Mapping[str, str]) -> list[str]:
    """Return fail-closed approval schema and supplied input-drift errors."""

    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("approval schema_version must be 1")
    decision = payload.get("decision")
    if decision not in _DECISIONS:
        errors.append("approval decision must be approved or rejected")
    if not isinstance(payload.get("owner"), str) or not str(payload.get("owner")).strip():
        errors.append("approval owner is required")
    inputs = payload.get("inputs")
    if not isinstance(inputs, Mapping):
        errors.append("approval inputs are required")
        return errors
    labels = {
        "source_sha256": "source SHA-256",
        "master_sha256": "master SHA-256",
        "material_library_sha256": "material library SHA-256",
        "scene_sha256": "scene SHA-256",
        "proof_manifest_sha256": "proof manifest SHA-256",
        "proof_contract_sha256": "proof contract SHA-256",
        "contact_sheet_sha256": "contact sheet SHA-256",
    }
    for key, label in labels.items():
        expected = inputs.get(key)
        if expected is not None and (not isinstance(expected, str) or _SHA256.fullmatch(expected) is None):
            errors.append(f"approval {label} is invalid")
        actual = current_inputs.get(key)
        if actual is not None and isinstance(expected, str) and actual.upper() != expected.upper():
            errors.append(f"{label} drift")
    return errors


def validate_approval(approval_path: Path, current_inputs: Mapping[str, str]) -> list[str]:
    """Validate the immutable approval and its proof pixels against current evidence."""

    try:
        payload = json.loads(Path(approval_path).read_text(encoding="utf-8"))
        payload = _mapping(payload, "approval")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"approval cannot be read: {error}"]
    errors = validate_approval_payload(payload, current_inputs)
    proof_path_raw = payload.get("proof_manifest_path")
    if not isinstance(proof_path_raw, str):
        return errors + ["approval proof manifest path is required"]
    proof_path = Path(proof_path_raw)
    if not proof_path.is_file():
        return errors + ["approval proof manifest is missing"]
    expected_inputs = payload.get("inputs")
    assert isinstance(expected_inputs, Mapping)
    try:
        actual_inputs, _, _, output_hashes = _extract_approval_evidence(proof_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return errors + [f"proof evidence cannot be read: {error}"]
    for key, expected in expected_inputs.items():
        actual = actual_inputs.get(str(key))
        if actual is not None and actual != expected:
            errors.append(f"{key.replace('_', ' ')} drift")
    recorded_outputs = payload.get("proof_output_sha256")
    if not isinstance(recorded_outputs, Mapping):
        errors.append("approval proof output hashes are required")
    else:
        for relative, expected in recorded_outputs.items():
            path = proof_path.parent / str(relative)
            actual = output_hashes.get(str(relative))
            if not path.is_file() or actual != expected or sha256_file(path) != expected:
                errors.append("proof pixel SHA-256 drift")
                break
    return errors


def record_decision(proof_manifest: Path, shot_id: str, decision: str, owner: str, notes: str) -> Path:
    """Append a hash-bound owner decision; existing decisions are never overwritten."""

    if decision not in _DECISIONS:
        raise ValueError("decision must be approved or rejected")
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("owner is required")
    if not isinstance(notes, str):
        raise ValueError("notes must be a string")
    inputs, render_settings, generation_id, output_hashes = _extract_approval_evidence(Path(proof_manifest))
    proof = json.loads(Path(proof_manifest).read_text(encoding="utf-8"))
    proof_outputs = _mapping(proof, "proof manifest").get("outputs")
    if not isinstance(proof_outputs, list) or shot_id not in {item.get("shot_id") for item in proof_outputs if isinstance(item, Mapping)}:
        raise ValueError("shot_id is not present in proof manifest outputs")
    approval_dir = Path(proof_manifest).parent / "approvals" / shot_id
    existing = sorted(approval_dir.glob("approval-r*.json")) if approval_dir.exists() else []
    revision = len(existing) + 1
    destination = approval_dir / f"approval-r{revision:02d}.json"
    if destination.exists():
        raise ValueError("approval revision already exists; decisions are immutable")
    prior = sha256_file(existing[-1]) if existing else None
    prior_path = str(existing[-1].resolve()) if existing else None
    payload: dict[str, object] = {
        "schema": _APPROVAL_SCHEMA,
        "schema_version": 1,
        "revision": revision,
        "prior_approval_sha256": prior,
        "prior_approval_path": prior_path,
        "decision": decision,
        "owner": owner.strip(),
        "notes": notes,
        "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "shot_id": shot_id,
        "proof_manifest_path": str(Path(proof_manifest).resolve()),
        "proof_generation_id": generation_id,
        "inputs": inputs,
        "render_settings": render_settings,
        "proof_output_sha256": output_hashes,
    }
    _create_immutable_json(destination, payload)
    return destination


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record")
    record.add_argument("--proof-manifest", type=Path, required=True)
    record.add_argument("--shot-id", required=True)
    record.add_argument("--decision", choices=sorted(_DECISIONS), required=True)
    record.add_argument("--owner", required=True)
    record.add_argument("--notes", required=True)
    arguments = parser.parse_args()
    if arguments.command == "record":
        print(record_decision(arguments.proof_manifest, arguments.shot_id, arguments.decision, arguments.owner, arguments.notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
