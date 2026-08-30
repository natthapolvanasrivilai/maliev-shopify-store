"""Render four marker-authoritative PIMM editorial previews as one atomic generation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version as package_version
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence
import uuid

try:
    from . import blender_editorial_scene
    from .editorial_concept_contract import (
        EDITORIAL_CAMPAIGN_PATH,
        EDITORIAL_CAMPAIGN_ID,
        EditorialConceptShot,
        load_editorial_campaign,
        validate_editorial_campaign,
    )
    from .editorial_contact_sheet import (
        MANIFEST_SCHEMA,
        SHEET_HEIGHT,
        SHEET_WIDTH,
        build_editorial_contact_sheet,
    )
    from .external_asset_manifest import validate_external_assets
    from .io_contract import atomic_write_json, sha256_file
    from .paths import ASSET_ROOT, require_within
    from .tool_policy import validate_tool_lock
except ImportError:  # Blender executes this checked-in file outside package mode.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production import blender_editorial_scene
    from scripts.blender.pimm_production.editorial_concept_contract import (
        EDITORIAL_CAMPAIGN_PATH,
        EDITORIAL_CAMPAIGN_ID,
        EditorialConceptShot,
        load_editorial_campaign,
        validate_editorial_campaign,
    )
    from scripts.blender.pimm_production.editorial_contact_sheet import (
        MANIFEST_SCHEMA,
        SHEET_HEIGHT,
        SHEET_WIDTH,
        build_editorial_contact_sheet,
    )
    from scripts.blender.pimm_production.external_asset_manifest import validate_external_assets
    from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
    from scripts.blender.pimm_production.tool_policy import validate_tool_lock


RESULT_MARKER = "PIMM_EDITORIAL_PREVIEW_JSON="
SHOT_SCHEMA = "maliev.pimm-editorial-preview-shot/v1"
REPORT_SCHEMA = "maliev.pimm-editorial-preview-report/v1"
FAILURE_SCHEMA = "maliev.pimm-editorial-preview-failure/v1"
PUBLICATION_SCHEMA = "maliev.pimm-editorial-publication/v1"
SCENE_SCHEMA = "maliev.pimm-editorial-scene/v1"
PROOF_LIBRARY_ID = "editorial-concepts-v1"
CONTACT_SHEET_NAME = "sheet-editorial-concepts.png"
MANIFEST_NAME = "campaign-manifest.json"
REPORT_NAME = "campaign-report.json"
EXPECTED_SAMPLES = 32
EXPECTED_DENOISE = True
EXPECTED_VIEW_TRANSFORM = "AgX"
EXPECTED_LOOK = "AgX - Medium High Contrast"
EXPECTED_PILLOW_VERSION = "12.2.0"
_SHA256_HEX = frozenset("0123456789ABCDEF")
_PROVENANCE_FIELDS = (
    "source_url",
    "asset_version_id",
    "license",
    "local_relative_path",
    "sha256",
    "intended_shot_ids",
    "machine_master_modified",
)
_BOUNCE_FIELDS = (
    "max_bounces",
    "diffuse_bounces",
    "glossy_bounces",
    "transmission_bounces",
    "volume_bounces",
    "transparent_max_bounces",
)

_CAMPAIGN = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH)
_CAMPAIGN_ERRORS = validate_editorial_campaign(_CAMPAIGN)
if _CAMPAIGN_ERRORS:
    raise ValueError("editorial campaign validation failed: " + "; ".join(_CAMPAIGN_ERRORS))


@dataclass(frozen=True)
class CompletionAuthority:
    """One Task 4 marker-last scene/contract pair and every immutable dependency."""

    shot_id: str
    scene_path: Path
    contract_path: Path
    completion_marker_path: Path
    scene_sha256: str
    contract_sha256: str
    completion_marker_sha256: str
    transaction_id: str
    master_path: Path
    master_sha256: str
    material_library_path: Path
    material_library_sha256: str
    external_manifest_path: Path
    external_manifest_sha256: str
    external_assets: tuple[dict[str, object], ...]
    contract: dict[str, object]


@dataclass(frozen=True)
class EditorialPreviewResult:
    """Published result for one four-shot immutable preview generation."""

    status: str
    generation_id: str
    output_root: Path
    manifest_path: Path
    manifest_sha256: str
    report_path: Path
    report_sha256: str
    contact_sheet_path: Path
    contact_sheet_sha256: str
    shot_count: int


class EditorialPreviewFailure(RuntimeError):
    """Campaign failure that identifies its preserved rejected evidence."""

    def __init__(
        self,
        message: str,
        *,
        generation_id: str,
        rejected_root: Path | None,
    ) -> None:
        super().__init__(message)
        self.generation_id = generation_id
        self.rejected_root = rejected_root


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json_bytes(path: Path, label: str) -> tuple[dict[str, object], bytes, str]:
    try:
        payload_bytes = path.read_bytes()
    except OSError as error:
        raise ValueError(f"{label} is missing or unreadable: {path}") from error
    try:
        payload = json.loads(payload_bytes, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} JSON is invalid: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{label} root must be an object: {path}")
    return payload, payload_bytes, hashlib.sha256(payload_bytes).hexdigest().upper()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and not set(value.upper()).difference(_SHA256_HEX)
    )


def _relative_asset_path(asset_root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{label} must be a nonempty POSIX relative path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        raise ValueError(f"{label} must remain inside the asset root")
    return require_within(asset_root.joinpath(*relative.parts), asset_root)


def _resolved_marker_path(value: object, expected: Path, label: str) -> None:
    if not isinstance(value, str) or Path(value).resolve() != expected.resolve():
        raise ValueError(f"completion marker {label} does not bind the authoritative path")


def _contract_errors(
    asset_root: Path,
    shot: EditorialConceptShot,
    contract: Mapping[str, object],
    expected_scene: Path,
    expected_marker: Path,
) -> list[str]:
    errors: list[str] = []
    expected_render = {
        "engine": "CYCLES",
        "width": shot.width,
        "height": shot.height,
        "resolution_percentage": 100,
        "preview_samples": EXPECTED_SAMPLES,
        "denoise": EXPECTED_DENOISE,
        "view_transform": EXPECTED_VIEW_TRANSFORM,
        "look": EXPECTED_LOOK,
        "alpha": False,
    }
    checks = (
        (contract.get("schema") == SCENE_SCHEMA, "scene contract schema is not authoritative"),
        (contract.get("campaign_id") == EDITORIAL_CAMPAIGN_ID, "scene contract campaign changed"),
        (contract.get("scene_id") == shot.shot_id, "scene contract shot identity changed"),
        (contract.get("machine") == shot.machine, "scene contract machine changed"),
        (contract.get("concept") == shot.concept, "scene contract concept changed"),
        (contract.get("input_policy") == "link-only-immutable", "scene input policy changed"),
        (contract.get("preview_only") is True, "scene contract must remain preview-only"),
        (contract.get("final_authorized") is False, "scene contract must not authorize finals"),
        (contract.get("render") == expected_render, "scene render settings changed"),
    )
    errors.extend(message for valid, message in checks if not valid)
    camera = contract.get("camera")
    if not isinstance(camera, Mapping):
        errors.append("scene camera contract is missing")
    elif (
        camera.get("focal_length_mm") != shot.focal_length_mm
        or camera.get("aperture_fstop") != shot.aperture_fstop
    ):
        errors.append("scene camera lens or f-stop changed")
    try:
        scene_path = _relative_asset_path(asset_root, contract.get("scene_path"), "scene_path")
        if scene_path != expected_scene:
            errors.append("scene contract path changed")
    except ValueError as error:
        errors.append(str(error))
    publication = contract.get("publication")
    if not isinstance(publication, Mapping):
        errors.append("scene publication contract is missing")
    else:
        if publication.get("schema") != PUBLICATION_SCHEMA:
            errors.append("scene publication schema changed")
        if publication.get("authority") != "marker-last-sha256-pair":
            errors.append("scene publication authority changed")
        try:
            marker_path = _relative_asset_path(
                asset_root,
                publication.get("completion_marker_path"),
                "completion_marker_path",
            )
            if marker_path != expected_marker:
                errors.append("scene completion marker path changed")
        except ValueError as error:
            errors.append(str(error))
        transaction = publication.get("transaction_id")
        if (
            not isinstance(transaction, str)
            or len(transaction) != 32
            or any(character not in "0123456789abcdef" for character in transaction)
        ):
            errors.append("scene publication transaction ID is invalid")
    set_record = contract.get("set")
    if not isinstance(set_record, Mapping):
        errors.append("scene set evidence is missing")
    else:
        for field in (
            "geometry_signature",
            "light_signature",
            "scene_geometry_signature",
            "scene_light_signature",
        ):
            if not _is_sha256(set_record.get(field)):
                errors.append(f"scene set {field} is invalid")
        if not isinstance(set_record.get("shadow_intent"), str) or not set_record.get("shadow_intent"):
            errors.append("scene set shadow intent is missing")
    return errors


def _provenance_without_asset_id(record: Mapping[str, object]) -> dict[str, object]:
    return {field: record.get(field) for field in _PROVENANCE_FIELDS}


def _load_completion_authority(
    asset_root: Path, shot: EditorialConceptShot
) -> CompletionAuthority:
    """Recompute one completion marker and every dependency from current bytes."""

    asset_root = Path(asset_root).resolve()
    scene_path = require_within(
        asset_root / "scenes" / PROOF_LIBRARY_ID / f"{shot.shot_id}.blend",
        asset_root / "scenes" / PROOF_LIBRARY_ID,
    )
    contract_path = require_within(
        asset_root / "scenes" / "contracts" / PROOF_LIBRARY_ID / f"{shot.shot_id}.json",
        asset_root / "scenes" / "contracts" / PROOF_LIBRARY_ID,
    )
    marker_path = require_within(
        contract_path.with_name(f"{shot.shot_id}.complete.json"),
        asset_root / "scenes" / "contracts" / PROOF_LIBRARY_ID,
    )
    for label, path in (
        ("editorial scene", scene_path),
        ("editorial scene contract", contract_path),
        ("editorial completion marker", marker_path),
    ):
        if not path.is_file():
            raise ValueError(f"{label} is missing: {path}")
    contract, _contract_bytes, contract_sha = _load_json_bytes(
        contract_path, "editorial scene contract"
    )
    marker, _marker_bytes, marker_sha = _load_json_bytes(
        marker_path, "editorial completion marker"
    )
    errors = _contract_errors(asset_root, shot, contract, scene_path, marker_path)
    publication = contract.get("publication")
    transaction_id = (
        str(publication.get("transaction_id")) if isinstance(publication, Mapping) else ""
    )
    if marker.get("schema") != PUBLICATION_SCHEMA:
        errors.append("completion marker schema changed")
    if marker.get("status") != "complete":
        errors.append("completion marker status is not complete")
    if marker.get("scene_id") != shot.shot_id:
        errors.append("completion marker scene identity changed")
    if marker.get("transaction_id") != transaction_id:
        errors.append("completion marker transaction does not match the contract")
    paths = marker.get("paths")
    if not isinstance(paths, Mapping):
        errors.append("completion marker paths are missing")
    else:
        for field, expected in (
            ("scene_published", scene_path),
            ("contract_published", contract_path),
            ("completion_marker", marker_path),
        ):
            try:
                _resolved_marker_path(paths.get(field), expected, field)
            except ValueError as error:
                errors.append(str(error))

    scene_sha = sha256_file(scene_path)
    if marker.get("scene_sha256") != scene_sha:
        errors.append("completion marker scene hash does not match current bytes")
    if marker.get("contract_sha256") != contract_sha:
        errors.append("completion marker contract hash does not match current bytes")

    master = contract.get("master")
    material = contract.get("material_library")
    if not isinstance(master, Mapping) or not isinstance(material, Mapping):
        raise ValueError("; ".join([*errors, "master or material authority is missing"]))
    master_path = _relative_asset_path(asset_root, master.get("path"), "master.path")
    material_path = _relative_asset_path(
        asset_root, material.get("path"), "material_library.path"
    )
    if master.get("path") != f"masters/PIMM-{shot.machine}-MASTER.blend":
        errors.append("master path does not match the shot machine")
    if material.get("path") != "masters/PIMM-MATERIAL-LIBRARY.blend":
        errors.append("material-library path changed")
    if not master_path.is_file() or not material_path.is_file():
        errors.append("master or material-library file is missing")
    master_sha = sha256_file(master_path) if master_path.is_file() else ""
    material_sha = sha256_file(material_path) if material_path.is_file() else ""
    if master.get("sha256") != master_sha:
        errors.append("master hash does not match current bytes")
    if material.get("sha256") != material_sha:
        errors.append("material-library hash does not match current bytes")

    external_manifest_path = require_within(
        asset_root / "manifests" / "external-assets-v1.json",
        asset_root / "manifests",
    )
    external_manifest, _external_bytes, external_manifest_sha = _load_json_bytes(
        external_manifest_path, "external asset manifest"
    )
    provenance_errors = validate_external_assets(
        external_manifest, {item.shot_id for item in _CAMPAIGN.shots}
    )
    errors.extend(f"external provenance: {error}" for error in provenance_errors)
    manifest_assets = external_manifest.get("assets")
    if not isinstance(manifest_assets, list):
        manifest_assets = []
    contract_external = contract.get("external_assets")
    if not isinstance(contract_external, list):
        errors.append("scene contract external assets must be a list")
        contract_external = []
    external_records: list[dict[str, object]] = []
    observed_ids: set[str] = set()
    for index, item in enumerate(contract_external):
        if not isinstance(item, Mapping):
            errors.append(f"scene external_assets[{index}] must be an object")
            continue
        asset_id = item.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id or asset_id in observed_ids:
            errors.append(f"scene external_assets[{index}] asset_id is missing or duplicated")
            continue
        observed_ids.add(asset_id)
        provenance = _provenance_without_asset_id(item)
        if provenance not in manifest_assets:
            errors.append(f"external provenance record is not exact for {asset_id}")
        if shot.shot_id not in provenance.get("intended_shot_ids", []):
            errors.append(f"external provenance is not scoped to {shot.shot_id}: {asset_id}")
        try:
            local_path = _relative_asset_path(
                asset_root, provenance.get("local_relative_path"), f"external {asset_id} path"
            )
        except ValueError as error:
            errors.append(str(error))
            continue
        if not local_path.is_file():
            errors.append(f"external asset is missing: {asset_id}")
            actual_sha = ""
        else:
            actual_sha = sha256_file(local_path)
            if provenance.get("sha256") != actual_sha:
                errors.append(f"external asset hash changed: {asset_id}")
        external_records.append(
            {
                "asset_id": asset_id,
                **provenance,
                "absolute_path": str(local_path),
                "actual_sha256": actual_sha,
                "status": "pass" if actual_sha == provenance.get("sha256") else "fail",
            }
        )
    if errors:
        raise ValueError("; ".join(dict.fromkeys(errors)))

    authority = CompletionAuthority(
        shot_id=shot.shot_id,
        scene_path=scene_path,
        contract_path=contract_path,
        completion_marker_path=marker_path,
        scene_sha256=scene_sha,
        contract_sha256=contract_sha,
        completion_marker_sha256=marker_sha,
        transaction_id=transaction_id,
        master_path=master_path,
        master_sha256=master_sha,
        material_library_path=material_path,
        material_library_sha256=material_sha,
        external_manifest_path=external_manifest_path,
        external_manifest_sha256=external_manifest_sha,
        external_assets=tuple(external_records),
        contract=contract,
    )
    current = {
        "scene": sha256_file(scene_path),
        "contract": sha256_file(contract_path),
        "marker": sha256_file(marker_path),
        "master": sha256_file(master_path),
        "material": sha256_file(material_path),
        "external_manifest": sha256_file(external_manifest_path),
        **{
            f"external:{record['asset_id']}": sha256_file(Path(str(record["absolute_path"])))
            for record in external_records
        },
    }
    expected = {
        "scene": authority.scene_sha256,
        "contract": authority.contract_sha256,
        "marker": authority.completion_marker_sha256,
        "master": authority.master_sha256,
        "material": authority.material_library_sha256,
        "external_manifest": authority.external_manifest_sha256,
        **{
            f"external:{record['asset_id']}": record["actual_sha256"]
            for record in external_records
        },
    }
    if current != expected:
        raise ValueError("completion authority changed while it was being fingerprinted")
    return authority


def _validate_blender_authority(asset_root: Path, blender: Path) -> dict[str, object]:
    """Bind the executing Blender path and bytes to the approved local tool lock."""

    blender = Path(blender).resolve()
    if not blender.is_file():
        raise ValueError(f"Blender runtime is missing: {blender}")
    lock_path = require_within(
        Path(asset_root).resolve() / "manifests" / "free-tools-lock.json",
        Path(asset_root).resolve() / "manifests",
    )
    lock, _bytes, lock_sha = _load_json_bytes(lock_path, "free tool lock")
    errors = validate_tool_lock(lock)
    if errors:
        raise ValueError("free tool lock is invalid: " + "; ".join(errors))
    records = lock.get("tools")
    blender_records = [
        item for item in records if isinstance(item, Mapping) and item.get("id") == "blender"
    ] if isinstance(records, list) else []
    if len(blender_records) != 1:
        raise ValueError("free tool lock must contain exactly one Blender record")
    record = blender_records[0]
    if Path(str(record.get("path"))).resolve() != blender:
        raise ValueError("requested Blender path does not match the tool lock")
    actual_sha = sha256_file(blender)
    if record.get("sha256") != actual_sha:
        raise ValueError("requested Blender hash does not match the tool lock")
    if record.get("version") != "5.2.0":
        raise ValueError("editorial previews require the locked Blender 5.2.0 runtime")
    pillow = package_version("Pillow")
    if pillow != EXPECTED_PILLOW_VERSION:
        raise ValueError(
            f"editorial contact sheets require Pillow {EXPECTED_PILLOW_VERSION}, got {pillow}"
        )
    return {
        "status": "pass",
        "path": str(blender),
        "sha256": actual_sha,
        "version": str(record["version"]),
        "lock_path": str(lock_path),
        "lock_sha256": lock_sha,
        "pillow_version": pillow,
    }


def _authority_worker_record(authority: CompletionAuthority) -> dict[str, object]:
    return {
        "scene_path": str(authority.scene_path),
        "scene_sha256": authority.scene_sha256,
        "contract_path": str(authority.contract_path),
        "contract_sha256": authority.contract_sha256,
        "completion_marker_path": str(authority.completion_marker_path),
        "completion_marker_sha256": authority.completion_marker_sha256,
        "transaction_id": authority.transaction_id,
        "master": {
            "path": str(authority.master_path),
            "sha256": authority.master_sha256,
            "status": "pass",
        },
        "material_library": {
            "path": str(authority.material_library_path),
            "sha256": authority.material_library_sha256,
            "status": "pass",
        },
        "external_assets": [
            {
                key: value
                for key, value in record.items()
                if key != "absolute_path"
            }
            for record in authority.external_assets
        ],
    }


def _validate_contact_evidence(contact: object) -> None:
    if not isinstance(contact, Mapping) or contact.get("status") != "pass":
        raise ValueError("contact status is not pass")
    measurements = contact.get("measurements")
    if not isinstance(measurements, Mapping):
        raise ValueError("contact measurements are missing")
    stable_ids = measurements.get("stable_ids")
    bottoms = measurements.get("pad_bottoms")
    feet = measurements.get("feet")
    if (
        not isinstance(stable_ids, list)
        or len(stable_ids) != 4
        or len(set(stable_ids)) != 4
        or not isinstance(bottoms, list)
        or len(bottoms) != 4
        or not isinstance(feet, list)
        or len(feet) != 4
    ):
        raise ValueError("contact evidence must measure four unique feet")
    tolerance = float(measurements.get("tolerance", math.inf))
    if tolerance != 0.0002:
        raise ValueError("contact tolerance changed")
    if (
        measurements.get("outlier_stable_ids") not in ([], ())
        or float(measurements.get("spread", math.inf)) > tolerance
    ):
        raise ValueError("contact spread or outlier evidence failed")
    if any(
        not isinstance(item, Mapping)
        or abs(float(item.get("delta_to_plane", math.inf))) > tolerance
        for item in feet
    ):
        raise ValueError("contact per-foot measurements failed")


def _validate_worker_result(
    shot: EditorialConceptShot,
    authority: CompletionAuthority,
    result: Mapping[str, object],
    output_path: Path,
) -> None:
    """Reject a worker unless every render, authority, and acceptance gate is present."""

    from PIL import Image

    if result.get("schema") != SHOT_SCHEMA or result.get("status") != "pass":
        raise ValueError("worker status or schema is not pass")
    if result.get("shot_id") != shot.shot_id:
        raise ValueError("worker shot identity changed")
    if not isinstance(result.get("process_id"), int) or int(result["process_id"]) <= 0:
        raise ValueError("fresh Blender process identity is missing")
    if result.get("cache_reuse") is not False:
        raise ValueError("cache reuse is forbidden")
    if Path(str(result.get("output_path"))).resolve() != output_path.resolve():
        raise ValueError("worker output path changed")
    if not output_path.is_file():
        raise ValueError("worker output PNG is missing")
    actual_hash = sha256_file(output_path)
    if result.get("output_sha256") != actual_hash:
        raise ValueError("worker output hash does not match current pixels")
    if (result.get("output_width"), result.get("output_height")) != (
        shot.width,
        shot.height,
    ):
        raise ValueError("output dimensions do not match the contract")
    with Image.open(output_path) as image:
        if image.size != (shot.width, shot.height):
            raise ValueError("output dimensions do not match actual pixels")
        if image.format != "PNG":
            raise ValueError("worker output must be PNG")
        image.verify()

    render = result.get("render")
    if not isinstance(render, Mapping):
        raise ValueError("render settings are missing")
    expected_render = {
        "engine": "CYCLES",
        "samples": EXPECTED_SAMPLES,
        "denoise": True,
        "width": shot.width,
        "height": shot.height,
        "resolution_percentage": 100,
        "view_transform": EXPECTED_VIEW_TRANSFORM,
        "look": EXPECTED_LOOK,
        "exposure": 0.0,
        "gamma": 1.0,
        "film_transparent": False,
        "file_format": "PNG",
        "color_mode": "RGB",
        "color_depth": "8",
        "use_persistent_data": False,
    }
    for key, expected in expected_render.items():
        if render.get(key) != expected:
            label = "samples" if key == "samples" else f"render {key}"
            raise ValueError(f"{label} do not match the preview contract")
    bounce_limits = render.get("bounce_limits")
    if not isinstance(bounce_limits, Mapping) or set(bounce_limits) != set(_BOUNCE_FIELDS):
        raise ValueError("render bounce limits are incomplete")
    if any(not isinstance(bounce_limits[key], int) or bounce_limits[key] < 0 for key in _BOUNCE_FIELDS):
        raise ValueError("render bounce limits are invalid")
    if not str(render.get("blender_version", "")).startswith("5.2"):
        raise ValueError("render did not use Blender 5.2")
    if not all(isinstance(render.get(key), str) and render.get(key) for key in ("started_at", "finished_at")):
        raise ValueError("render timestamps are missing")
    if not isinstance(render.get("seconds"), (int, float)) or float(render["seconds"]) < 0:
        raise ValueError("render duration is invalid")
    dimensions = render.get("dimension_evidence")
    if (
        not isinstance(dimensions, Mapping)
        or dimensions.get("dimension_authority") != "written-png-ihdr"
        or dimensions.get("png_dimensions") != [shot.width, shot.height]
    ):
        raise ValueError("output dimensions lack written-PNG authority")

    worker_authority = result.get("authority")
    if not isinstance(worker_authority, Mapping):
        raise ValueError("scene hash and completion authority evidence are missing")
    expected_authority = _authority_worker_record(authority)
    for key in (
        "scene_path",
        "scene_sha256",
        "contract_path",
        "contract_sha256",
        "completion_marker_path",
        "completion_marker_sha256",
        "transaction_id",
        "master",
        "material_library",
        "external_assets",
    ):
        if worker_authority.get(key) != expected_authority[key]:
            label = "scene hash" if key == "scene_sha256" else f"authority {key}"
            raise ValueError(f"{label} does not match completion authority")
    if worker_authority.get("blender_scene_validation") != "pass":
        raise ValueError("fresh Blender scene authority validation did not pass")
    if not isinstance(worker_authority.get("checked_at"), str):
        raise ValueError("fresh Blender scene authority timestamp is missing")
    if result.get("master_fingerprint_status") != "pass":
        raise ValueError("master fingerprint status is not pass")
    if result.get("asset_provenance_status") != "pass":
        raise ValueError("provenance status is not pass")
    if result.get("fingerprints_unchanged") is not True:
        raise ValueError("protected fingerprints changed during render")

    _validate_contact_evidence(result.get("contact"))
    framing = result.get("framing")
    if (
        not isinstance(framing, Mapping)
        or framing.get("status") != "pass"
        or framing.get("complete_machine_framed") is not True
        or framing.get("support_rectangle_framed") is not True
        or float(framing.get("safe_margin_minimum", -math.inf)) < 0.02
    ):
        raise ValueError("framing evidence is not pass")
    clipping = result.get("clipping")
    if not isinstance(clipping, Mapping) or clipping.get("status") != "pass":
        raise ValueError("clipping evidence is not pass")
    if clipping.get("machine") != "pass":
        raise ValueError("machine clipping status is not pass")
    if clipping.get("designed_shadow") != "pass":
        raise ValueError("shadow clipping status is not pass")
    if (
        clipping.get("props") != "pass"
        or clipping.get("support_intersections") not in ([], ())
        or clipping.get("hidden_foot_stable_ids") not in ([], ())
    ):
        raise ValueError("prop clipping, collision, or foot occlusion status is not pass")

    set_record = result.get("set")
    contract_set = authority.contract.get("set")
    if not isinstance(set_record, Mapping) or not isinstance(contract_set, Mapping):
        raise ValueError("set signatures are missing")
    if (
        set_record.get("geometry_signature") != contract_set.get("scene_geometry_signature")
        or set_record.get("light_signature") != contract_set.get("scene_light_signature")
        or set_record.get("shadow_intent") != contract_set.get("shadow_intent")
    ):
        raise ValueError("set signatures do not match the completed scene")


def _image_metrics(path: Path) -> dict[str, object]:
    from PIL import Image, ImageStat

    with Image.open(path) as loaded:
        image = loaded.convert("RGB")
        grayscale = image.convert("L")
        extrema = grayscale.getextrema()
        stats = ImageStat.Stat(grayscale)
        histogram = grayscale.histogram()
        total = image.width * image.height
        clipped_dark = sum(histogram[:2])
        clipped_light = sum(histogram[254:])
        entropy = float(grayscale.entropy())
    if extrema[1] - extrema[0] < 8 or entropy < 0.25:
        raise ValueError(f"rendered pixels are blank or lack usable tonal structure: {path.name}")
    return {
        "mode": "RGB",
        "luma_minimum": int(extrema[0]),
        "luma_maximum": int(extrema[1]),
        "luma_mean": round(float(stats.mean[0]), 6),
        "luma_standard_deviation": round(float(stats.stddev[0]), 6),
        "entropy": round(entropy, 6),
        "clipped_dark_fraction": round(clipped_dark / total, 9),
        "clipped_light_fraction": round(clipped_light / total, 9),
        "actual_pixel_inspection_required": True,
    }


def _validate_rendered_png_dimensions(
    path: Path,
    expected_width: int,
    expected_height: int,
    *,
    render_result_size: Sequence[int] | None,
) -> dict[str, object]:
    """Use the written PNG IHDR as authority; headless Blender reports 0 x 0."""

    try:
        with path.open("rb") as stream:
            header = stream.read(24)
    except OSError as error:
        raise ValueError(f"rendered PNG is missing or unreadable: {path}") from error
    if (
        len(header) != 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        raise ValueError("rendered output does not contain a valid PNG IHDR")
    width = int.from_bytes(header[16:20], byteorder="big", signed=False)
    height = int.from_bytes(header[20:24], byteorder="big", signed=False)
    if (width, height) != (expected_width, expected_height):
        raise ValueError(
            f"written PNG dimensions do not match the contract: "
            f"{width}x{height} != {expected_width}x{expected_height}"
        )
    observed = [int(value) for value in render_result_size] if render_result_size else None
    return {
        "dimension_authority": "written-png-ihdr",
        "png_dimensions": [width, height],
        "render_result_size": observed,
    }


def _worker_command(
    blender: Path,
    asset_root: Path,
    staging: Path,
    shot: EditorialConceptShot,
    authority: CompletionAuthority,
    output_path: Path,
) -> list[str]:
    return [
        str(blender),
        "--factory-startup",
        "-b",
        str(authority.scene_path),
        "--python-exit-code",
        "1",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--render-shot",
        "--asset-root",
        str(asset_root),
        "--staging-root",
        str(staging),
        "--shot-id",
        shot.shot_id,
        "--contract",
        str(authority.contract_path),
        "--completion-marker",
        str(authority.completion_marker_path),
        "--output",
        str(output_path),
        "--expected-scene-sha256",
        authority.scene_sha256,
        "--expected-contract-sha256",
        authority.contract_sha256,
        "--expected-marker-sha256",
        authority.completion_marker_sha256,
    ]


def _parse_worker(completed: subprocess.CompletedProcess[str], shot_id: str) -> dict[str, object]:
    markers = [
        line.removeprefix(RESULT_MARKER)
        for line in completed.stdout.splitlines()
        if line.startswith(RESULT_MARKER)
    ]
    if completed.returncode != 0 or len(markers) != 1:
        raise ValueError(
            f"editorial Blender worker failed for {shot_id}: exit={completed.returncode}; "
            f"stdout={completed.stdout[-3000:]}; stderr={completed.stderr[-3000:]}"
        )
    try:
        payload = json.loads(markers[0], object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise ValueError(f"editorial Blender worker emitted invalid JSON for {shot_id}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"editorial Blender worker emitted a non-object for {shot_id}")
    return payload


def _normalized_shot_record(
    shot: EditorialConceptShot,
    authority: CompletionAuthority,
    worker: Mapping[str, object],
    output_path: Path,
) -> dict[str, object]:
    return {
        **worker,
        "machine": shot.machine,
        "concept": shot.concept,
        "focal_length_mm": shot.focal_length_mm,
        "aperture_fstop": shot.aperture_fstop,
        "output_relative_path": output_path.name,
        "output_sha256": sha256_file(output_path),
        "output_width": shot.width,
        "output_height": shot.height,
        "render_source": "fresh-blender",
        "contact_status": "pass",
        "framing_status": "pass",
        "clipping_status": "pass",
        "master_fingerprint_status": "pass",
        "asset_provenance_status": "pass",
        "pixel_metrics": _image_metrics(output_path),
        "completion_authority": {
            "schema": PUBLICATION_SCHEMA,
            "transaction_id": authority.transaction_id,
            "completion_marker_sha256": authority.completion_marker_sha256,
            "status": "complete",
        },
    }


def _generation_id(authorities: Sequence[CompletionAuthority]) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    digest = hashlib.sha256(
        json.dumps(
            [
                {
                    "shot_id": item.shot_id,
                    "scene_sha256": item.scene_sha256,
                    "contract_sha256": item.contract_sha256,
                    "marker_sha256": item.completion_marker_sha256,
                }
                for item in authorities
            ],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:8]
    return f"editorial-preview-{timestamp}-{digest}-{uuid.uuid4().hex[:8]}"


def _authority_summary(authority: CompletionAuthority) -> dict[str, object]:
    return {
        "shot_id": authority.shot_id,
        "scene_path": str(authority.scene_path),
        "scene_sha256": authority.scene_sha256,
        "contract_path": str(authority.contract_path),
        "contract_sha256": authority.contract_sha256,
        "completion_marker_path": str(authority.completion_marker_path),
        "completion_marker_sha256": authority.completion_marker_sha256,
        "transaction_id": authority.transaction_id,
        "master_path": str(authority.master_path),
        "master_sha256": authority.master_sha256,
        "material_library_path": str(authority.material_library_path),
        "material_library_sha256": authority.material_library_sha256,
        "external_manifest_path": str(authority.external_manifest_path),
        "external_manifest_sha256": authority.external_manifest_sha256,
        "external_assets": list(authority.external_assets),
        "status": "complete-authority-pass",
    }


def _same_authority(left: CompletionAuthority, right: CompletionAuthority) -> bool:
    return left == right


def _preserve_failed_staging(
    staging: Path,
    rejected_parent: Path,
    generation_id: str,
    final: Path,
    created_at: str,
    shots: Sequence[Mapping[str, object]],
    error: Exception,
) -> Path | None:
    if not staging.is_dir():
        return None
    failure = {
        "schema": FAILURE_SCHEMA,
        "status": "rejected",
        "generation_id": generation_id,
        "created_at": created_at,
        "failed_at": _utc_now(),
        "error_type": type(error).__name__,
        "error": str(error),
        "intended_final_path": str(final),
        "completed_shot_ids": [str(item.get("shot_id")) for item in shots],
        "partial_output_hashes": {
            path.name: sha256_file(path)
            for path in sorted(staging.glob("*.png"))
            if path.is_file()
        },
    }
    try:
        atomic_write_json(staging / "campaign-failure.json", failure)
    except Exception:
        pass
    rejected_parent.mkdir(parents=True, exist_ok=True)
    rejected = rejected_parent / generation_id
    if rejected.exists():
        rejected = rejected_parent / f"{generation_id}-{uuid.uuid4().hex[:8]}"
    try:
        os.rename(staging, rejected)
    except OSError:
        return None
    return rejected


def _validate_generation_files(
    staging: Path,
    manifest_path: Path,
    report_path: Path,
    contact_sheet_path: Path,
    shots: Sequence[Mapping[str, object]],
) -> None:
    from PIL import Image

    expected_names = {
        *(str(item["output_relative_path"]) for item in shots),
        MANIFEST_NAME,
        REPORT_NAME,
        CONTACT_SHEET_NAME,
    }
    observed_names = {path.name for path in staging.iterdir() if path.is_file()}
    if observed_names != expected_names:
        raise ValueError(
            f"staged generation file set is not exact: missing={sorted(expected_names - observed_names)}, "
            f"extra={sorted(observed_names - expected_names)}"
        )
    if any(path.is_dir() for path in staging.iterdir()):
        raise ValueError("staged editorial generation must not contain hidden cache directories")
    manifest, _bytes, manifest_sha = _load_json_bytes(manifest_path, "campaign manifest")
    report, _report_bytes, _report_sha = _load_json_bytes(report_path, "campaign report")
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("status") != "pass":
        raise ValueError("staged campaign manifest is not passing")
    if report.get("schema") != REPORT_SCHEMA or report.get("status") != "pass":
        raise ValueError("staged campaign report is not passing")
    if report.get("campaign_manifest_sha256") != manifest_sha:
        raise ValueError("campaign report does not bind the staged manifest")
    if report.get("contact_sheet_sha256") != sha256_file(contact_sheet_path):
        raise ValueError("campaign report does not bind the staged contact sheet")
    with Image.open(contact_sheet_path) as image:
        if image.size != (SHEET_WIDTH, SHEET_HEIGHT):
            raise ValueError("campaign contact sheet dimensions are invalid")
        image.verify()
    if len({str(item["set"]["light_signature"]) for item in shots}) != 4:
        raise ValueError("editorial concepts collapse to the same lighting signature")


def render_editorial_preview_campaign(
    asset_root: Path, blender: Path
) -> EditorialPreviewResult:
    """Render and atomically publish exactly four fresh marker-authoritative previews."""

    asset_root = Path(asset_root).resolve()
    blender = Path(blender).resolve()
    if not asset_root.is_dir():
        raise ValueError(f"editorial asset root is missing: {asset_root}")
    initial_authorities = [
        _load_completion_authority(asset_root, shot) for shot in _CAMPAIGN.shots
    ]
    if len(initial_authorities) != 4 or len({item.shot_id for item in initial_authorities}) != 4:
        raise ValueError("editorial preview campaign requires exactly four completion authorities")
    generation_id = _generation_id(initial_authorities)
    proof_parent = asset_root / "renders" / "proofs" / PROOF_LIBRARY_ID
    proof_parent.mkdir(parents=True, exist_ok=True)
    staging = require_within(proof_parent / f".{generation_id}.pending", proof_parent)
    final = require_within(proof_parent / generation_id, proof_parent)
    rejected_parent = require_within(proof_parent / "rejected", proof_parent)
    if staging.exists() or final.exists():
        raise ValueError("fresh editorial preview generation path already exists")
    staging.mkdir()
    created_at = _utc_now()
    shot_records: list[dict[str, object]] = []
    try:
        campaign_blender_authority: dict[str, object] | None = None
        for shot, initial in zip(_CAMPAIGN.shots, initial_authorities, strict=True):
            current = _load_completion_authority(asset_root, shot)
            if not _same_authority(initial, current):
                raise ValueError(f"completion authority drifted before render: {shot.shot_id}")
            blender_authority = _validate_blender_authority(asset_root, blender)
            if campaign_blender_authority is None:
                campaign_blender_authority = blender_authority
            elif blender_authority != campaign_blender_authority:
                raise ValueError("Blender authority changed between editorial renders")
            output_path = require_within(staging / f"{shot.shot_id}.png", staging)
            if output_path.exists():
                raise ValueError(f"fresh editorial output already exists: {output_path}")
            command = _worker_command(
                blender, asset_root, staging, shot, current, output_path
            )
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            worker = _parse_worker(completed, shot.shot_id)
            _validate_worker_result(shot, current, worker, output_path)
            after = _load_completion_authority(asset_root, shot)
            if not _same_authority(current, after):
                raise ValueError(f"protected authority changed during render: {shot.shot_id}")
            shot_records.append(
                _normalized_shot_record(shot, current, worker, output_path)
            )
        if len(shot_records) != 4:
            raise ValueError("editorial campaign did not produce exactly four passing renders")
        process_ids = {int(item["process_id"]) for item in shot_records}
        if len(process_ids) != 4:
            raise ValueError("editorial renders did not use four distinct fresh Blender processes")
        if len({str(item["set"]["light_signature"]) for item in shot_records}) != 4:
            raise ValueError("editorial concepts do not have four distinct lighting signatures")

        assert campaign_blender_authority is not None
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "status": "pass",
            "generation_id": generation_id,
            "campaign_id": EDITORIAL_CAMPAIGN_ID,
            "created_at": created_at,
            "completed_at": _utc_now(),
            "preview_only": True,
            "final_authorized": False,
            "output_root": f"renders/proofs/{PROOF_LIBRARY_ID}/{generation_id}",
            "cache_reuse": False,
            "fresh_blender_processes": len(process_ids),
            "render_source": "fresh-blender",
            "scene_authority_passes": 4,
            "completion_authority_passes": 4,
            "contact_passes": sum(item["contact_status"] == "pass" for item in shot_records),
            "framing_passes": sum(item["framing_status"] == "pass" for item in shot_records),
            "clipping_passes": sum(item["clipping_status"] == "pass" for item in shot_records),
            "master_fingerprint_passes": sum(
                item["master_fingerprint_status"] == "pass" for item in shot_records
            ),
            "asset_provenance_passes": sum(
                item["asset_provenance_status"] == "pass" for item in shot_records
            ),
            "blender_authority": campaign_blender_authority,
            "contact_sheet_path": CONTACT_SHEET_NAME,
            "manual_visual_inspection": {
                "status": "required",
                "scope": "each preview and the contact sheet at actual pixels",
                "automated_pass_is_aesthetic_approval": False,
            },
            "shots": shot_records,
        }
        manifest_path = staging / MANIFEST_NAME
        atomic_write_json(manifest_path, manifest)
        sheet = build_editorial_contact_sheet(
            manifest_path, staging / CONTACT_SHEET_NAME
        )
        report = {
            "schema": REPORT_SCHEMA,
            "status": "pass",
            "generation_id": generation_id,
            "campaign_id": EDITORIAL_CAMPAIGN_ID,
            "created_at": created_at,
            "completed_at": _utc_now(),
            "preview_only": True,
            "final_authorized": False,
            "cache_reuse": False,
            "campaign_manifest_path": MANIFEST_NAME,
            "campaign_manifest_sha256": sha256_file(manifest_path),
            "contact_sheet_path": CONTACT_SHEET_NAME,
            "contact_sheet_sha256": sheet.sha256,
            "contact_sheet_dimensions": [sheet.width, sheet.height],
            "contact_sheet_cells": list(sheet.cells),
            "completion_authorities": [
                _authority_summary(item) for item in initial_authorities
            ],
            "shots": shot_records,
            "validation": {
                "shot_count": 4,
                "fresh_blender_processes": 4,
                "scene_authority_passes": 4,
                "contact_passes": 4,
                "framing_passes": 4,
                "clipping_passes": 4,
                "master_fingerprint_passes": 4,
                "asset_provenance_passes": 4,
                "distinct_light_signatures": 4,
                "manual_visual_inspection_required": True,
                "automated_pass_is_aesthetic_approval": False,
            },
        }
        report_path = staging / REPORT_NAME
        atomic_write_json(report_path, report)

        for shot, initial in zip(_CAMPAIGN.shots, initial_authorities, strict=True):
            final_authority = _load_completion_authority(asset_root, shot)
            if not _same_authority(initial, final_authority):
                raise ValueError(f"protected authority changed before publication: {shot.shot_id}")
        if _validate_blender_authority(asset_root, blender) != campaign_blender_authority:
            raise ValueError("Blender authority changed before publication")
        _validate_generation_files(
            staging,
            manifest_path,
            report_path,
            staging / CONTACT_SHEET_NAME,
            shot_records,
        )
        result = EditorialPreviewResult(
            status="pass",
            generation_id=generation_id,
            output_root=final,
            manifest_path=final / MANIFEST_NAME,
            manifest_sha256=sha256_file(manifest_path),
            report_path=final / REPORT_NAME,
            report_sha256=sha256_file(report_path),
            contact_sheet_path=final / CONTACT_SHEET_NAME,
            contact_sheet_sha256=sha256_file(staging / CONTACT_SHEET_NAME),
            shot_count=4,
        )
        os.rename(staging, final)
        return result
    except Exception as error:
        rejected = _preserve_failed_staging(
            staging,
            rejected_parent,
            generation_id,
            final,
            created_at,
            shot_records,
            error,
        )
        raise EditorialPreviewFailure(
            str(error), generation_id=generation_id, rejected_root=rejected
        ) from error


def _render_shot_worker(
    bpy: Any,
    *,
    asset_root: Path,
    staging_root: Path,
    shot: EditorialConceptShot,
    contract_path: Path,
    completion_marker_path: Path,
    output_path: Path,
    expected_scene_sha256: str,
    expected_contract_sha256: str,
    expected_marker_sha256: str,
) -> dict[str, object]:
    """Validate the freshly opened scene, then perform one and only one Cycles render."""

    asset_root = asset_root.resolve()
    staging_root = staging_root.resolve()
    output_path = require_within(output_path, staging_root)
    canonical_proof_root = asset_root / "renders" / "proofs" / PROOF_LIBRARY_ID
    require_within(staging_root, canonical_proof_root)
    if output_path.exists():
        raise ValueError("fresh worker output already exists")
    authority = _load_completion_authority(asset_root, shot)
    if authority.contract_path != contract_path.resolve():
        raise ValueError("worker contract path is not the completion-authoritative contract")
    if authority.completion_marker_path != completion_marker_path.resolve():
        raise ValueError("worker marker path is not the completion-authoritative marker")
    if (
        authority.scene_sha256 != expected_scene_sha256
        or authority.contract_sha256 != expected_contract_sha256
        or authority.completion_marker_sha256 != expected_marker_sha256
    ):
        raise ValueError("completion authority changed before fresh Blender validation")
    if Path(str(bpy.data.filepath)).resolve() != authority.scene_path:
        raise ValueError("fresh Blender process did not open the completion-authoritative scene")
    if not str(bpy.app.version_string).startswith("5.2"):
        raise ValueError(f"fresh Blender authority is not 5.2: {bpy.app.version_string}")

    snapshot, collection_errors = blender_editorial_scene._collect_runtime_snapshot(
        bpy, authority.contract
    )
    scene_errors = [
        *collection_errors,
        *blender_editorial_scene._validate_editorial_runtime_snapshot(
            snapshot, authority.contract
        ),
    ]
    if scene_errors:
        raise ValueError("fresh Blender scene authority failed: " + "; ".join(scene_errors))
    immediate = _load_completion_authority(asset_root, shot)
    if immediate != authority:
        raise ValueError("completion authority changed during fresh Blender validation")
    checked_at = _utc_now()

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = shot.width
    scene.render.resolution_y = shot.height
    scene.render.resolution_percentage = 100
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    scene.render.use_persistent_data = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = str(output_path)
    scene.cycles.samples = EXPECTED_SAMPLES
    scene.cycles.use_denoising = EXPECTED_DENOISE
    scene.view_settings.view_transform = EXPECTED_VIEW_TRANSFORM
    scene.view_settings.look = EXPECTED_LOOK
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    render_started = _utc_now()
    started = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    elapsed = time.perf_counter() - started
    render_finished = _utc_now()
    if not output_path.is_file():
        raise ValueError("Cycles did not create the contracted editorial preview")
    result_image = bpy.data.images.get("Render Result")
    dimension_evidence = _validate_rendered_png_dimensions(
        output_path,
        shot.width,
        shot.height,
        render_result_size=(
            tuple(int(value) for value in result_image.size)
            if result_image is not None
            else None
        ),
    )
    after = _load_completion_authority(asset_root, shot)
    if after != authority:
        raise ValueError("protected authority changed during Cycles render")

    contact = snapshot["contact"]
    framing = snapshot["camera"]
    supports = snapshot["support_bounds"]
    intersections = [
        str(item.get("name"))
        for item in supports
        if isinstance(item, Mapping) and item.get("intersects_machine") is True
    ]
    hidden_feet = sorted(
        {
            str(stable_id)
            for item in supports
            if isinstance(item, Mapping)
            for stable_id in item.get("hides_foot_stable_ids", [])
        }
    )
    bounce_limits = {
        field: int(getattr(scene.cycles, field)) for field in _BOUNCE_FIELDS
    }
    worker_authority = _authority_worker_record(authority)
    worker_authority.update(
        {
            "checked_at": checked_at,
            "blender_scene_validation": "pass",
        }
    )
    set_contract = authority.contract["set"]
    return {
        "schema": SHOT_SCHEMA,
        "status": "pass",
        "shot_id": shot.shot_id,
        "process_id": os.getpid(),
        "cache_reuse": False,
        "output_path": str(output_path),
        "output_sha256": sha256_file(output_path),
        "output_width": shot.width,
        "output_height": shot.height,
        "render": {
            "engine": scene.render.engine,
            "samples": int(scene.cycles.samples),
            "denoise": bool(scene.cycles.use_denoising),
            "width": int(scene.render.resolution_x),
            "height": int(scene.render.resolution_y),
            "resolution_percentage": int(scene.render.resolution_percentage),
            "view_transform": scene.view_settings.view_transform,
            "look": scene.view_settings.look,
            "exposure": float(scene.view_settings.exposure),
            "gamma": float(scene.view_settings.gamma),
            "film_transparent": bool(scene.render.film_transparent),
            "file_format": scene.render.image_settings.file_format,
            "color_mode": scene.render.image_settings.color_mode,
            "color_depth": scene.render.image_settings.color_depth,
            "use_persistent_data": bool(scene.render.use_persistent_data),
            "bounce_limits": bounce_limits,
            "blender_version": str(bpy.app.version_string),
            "started_at": render_started,
            "finished_at": render_finished,
            "seconds": round(elapsed, 6),
            "dimension_evidence": dimension_evidence,
        },
        "authority": worker_authority,
        "contact": {"status": "pass", "measurements": contact},
        "framing": {"status": "pass", **framing},
        "clipping": {
            "status": "pass",
            "machine": "pass",
            "designed_shadow": "pass",
            "props": "pass",
            "support_intersections": intersections,
            "hidden_foot_stable_ids": hidden_feet,
            "designed_shadow_evidence": {
                "shadow_intent": set_contract["shadow_intent"],
                "full_frame_rendered": True,
                "manual_actual_pixel_review_required": True,
            },
        },
        "set": {
            "geometry_signature": set_contract["scene_geometry_signature"],
            "light_signature": set_contract["scene_light_signature"],
            "shadow_intent": set_contract["shadow_intent"],
        },
        "asset_provenance_status": "pass",
        "master_fingerprint_status": "pass",
        "fingerprints_unchanged": True,
    }


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--render-campaign", action="store_true")
    mode.add_argument("--render-shot", action="store_true")
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--blender", type=Path, default=Path(r"D:\Blender 5.2\blender.exe"))
    parser.add_argument("--staging-root", type=Path)
    parser.add_argument("--shot-id")
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--completion-marker", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-scene-sha256")
    parser.add_argument("--expected-contract-sha256")
    parser.add_argument("--expected-marker-sha256")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else sys.argv[1:]
    )
    if arguments.render_campaign:
        if arguments.asset_root is None:
            raise ValueError("--render-campaign requires --asset-root")
        result = render_editorial_preview_campaign(arguments.asset_root, arguments.blender)
        print(
            RESULT_MARKER
            + json.dumps(
                {
                    "status": result.status,
                    "generation_id": result.generation_id,
                    "output_root": str(result.output_root),
                    "manifest_path": str(result.manifest_path),
                    "manifest_sha256": result.manifest_sha256,
                    "report_path": str(result.report_path),
                    "report_sha256": result.report_sha256,
                    "contact_sheet_path": str(result.contact_sheet_path),
                    "contact_sheet_sha256": result.contact_sheet_sha256,
                    "shot_count": result.shot_count,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0

    required = (
        arguments.asset_root,
        arguments.staging_root,
        arguments.shot_id,
        arguments.contract,
        arguments.completion_marker,
        arguments.output,
        arguments.expected_scene_sha256,
        arguments.expected_contract_sha256,
        arguments.expected_marker_sha256,
    )
    if any(value is None for value in required):
        raise ValueError("--render-shot requires every authority and output argument")
    shot = _CAMPAIGN.by_shot_id.get(str(arguments.shot_id))
    if shot is None:
        raise ValueError(f"unknown editorial shot: {arguments.shot_id}")
    import bpy

    result = _render_shot_worker(
        bpy,
        asset_root=arguments.asset_root,
        staging_root=arguments.staging_root,
        shot=shot,
        contract_path=arguments.contract,
        completion_marker_path=arguments.completion_marker,
        output_path=arguments.output,
        expected_scene_sha256=str(arguments.expected_scene_sha256),
        expected_contract_sha256=str(arguments.expected_contract_sha256),
        expected_marker_sha256=str(arguments.expected_marker_sha256),
    )
    print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
