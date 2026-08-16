"""Fail-closed authorization and local QA boundary for native PIMM final renders."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from .approval_manifest import validate_approval


_RELEASE_ID = re.compile(r"^release-[0-9]{4}-[0-9]{2}-[0-9]{2}-r[0-9]{2}$")
_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_DELIVERABLES = frozenset({"exr", "png", "webp"})


@dataclass(frozen=True)
class FinalAuthorization:
    """A validated, approval-bound final-render execution envelope."""

    approval_path: Path
    final_contract_path: Path
    release_id: str
    shot_id: str
    generation_id: str
    output_root: PurePosixPath


def _load(path: Path, label: str) -> Mapping[str, object]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} cannot be read: {error}") from error
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be an object")
    return payload


def _contract_errors(approval: Mapping[str, object], final: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    if final.get("schema") != "pimm-final-render-contract/v1":
        errors.append("final contract schema is invalid")
    release_id = final.get("release_id")
    if not isinstance(release_id, str) or _RELEASE_ID.fullmatch(release_id) is None:
        errors.append("final release ID is invalid")
    shot_id = final.get("shot_id")
    if shot_id != approval.get("shot_id"):
        errors.append("shot ID drift")
    if final.get("generation_id") != approval.get("proof_generation_id"):
        errors.append("proof generation drift")
    approved_inputs = approval.get("inputs")
    final_inputs = final.get("inputs")
    if not isinstance(approved_inputs, Mapping) or not isinstance(final_inputs, Mapping):
        errors.append("final inputs are required")
    elif dict(final_inputs) != dict(approved_inputs):
        errors.append("approved input SHA-256 drift")
    approved_settings = approval.get("render_settings")
    final_settings = final.get("render_settings")
    if not isinstance(approved_settings, Mapping) or not isinstance(final_settings, Mapping):
        errors.append("final render settings are required")
    else:
        labels = {
            "camera_sha256": "camera SHA-256 drift",
            "lights_sha256": "lights SHA-256 drift",
            "world_sha256": "world SHA-256 drift",
            "compositor_sha256": "compositor SHA-256 drift",
            "render_settings_sha256": "render settings SHA-256 drift",
            "composition_sha256": "composition SHA-256 drift",
            "output_dimensions": "output dimensions drift",
            "alpha_mode": "alpha mode drift",
        }
        for key, message in labels.items():
            if final_settings.get(key) != approved_settings.get(key):
                errors.append(message)
    samples = final.get("samples")
    proof_samples = approved_settings.get("proof_samples") if isinstance(approved_settings, Mapping) else None
    if not isinstance(samples, int) or isinstance(samples, bool) or not isinstance(proof_samples, int) or samples <= proof_samples:
        errors.append("final render requires an explicit sampling increase")
    output_root = final.get("output_root")
    if not isinstance(release_id, str) or output_root != f"renders/final/{release_id}":
        errors.append("final output root must be a new immutable renders/final/<release-id> directory")
    deliverables = final.get("deliverables")
    if not isinstance(deliverables, list) or set(deliverables) != _DELIVERABLES or len(deliverables) != len(_DELIVERABLES):
        errors.append("final deliverables must contain exactly float EXR, transparent PNG, and transparent WebP")
    return errors


def authorize_final_render(approval_path: Path, final_contract_path: Path) -> FinalAuthorization:
    """Authorize only an explicit sample increase over a current approved proof."""

    approval = _load(approval_path, "approval")
    if approval.get("decision") != "approved" or not isinstance(approval.get("owner"), str) or not approval["owner"].strip():
        raise ValueError("owner approval required")
    inputs = approval.get("inputs")
    if not isinstance(inputs, Mapping):
        raise ValueError("owner approval required: immutable inputs missing")
    approval_errors = validate_approval(approval_path, {str(key): str(value) for key, value in inputs.items()})
    final = _load(final_contract_path, "final contract")
    errors = approval_errors + _contract_errors(approval, final)
    if errors:
        raise ValueError("final render authorization failed: " + "; ".join(errors))
    return FinalAuthorization(
        approval_path=Path(approval_path).resolve(),
        final_contract_path=Path(final_contract_path).resolve(),
        release_id=str(final["release_id"]),
        shot_id=str(final["shot_id"]),
        generation_id=str(final["generation_id"]),
        output_root=PurePosixPath(str(final["output_root"])),
    )
