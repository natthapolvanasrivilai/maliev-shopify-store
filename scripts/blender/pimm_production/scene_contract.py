"""Fail-closed contract for one PIMM linked render scene."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Mapping


_FIELDS = {
    "schema_version",
    "scene_id",
    "machine",
    "purpose",
    "master_path",
    "master_sha256",
    "master_collection",
    "material_library_path",
    "material_library_sha256",
    "camera_name",
    "complete_product",
    "animation_contract",
    "output_contract",
}
_SCENE_ID = re.compile(r"^pimm-(30g|50g)--[a-z0-9-]+(?:--[a-z0-9-]+)*$")
_SLUG = re.compile(r"^[a-z0-9-]+$")
_CAMERA = re.compile(r"^CAM_[A-Z0-9_]+$")
_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_OUTPUT_FIELDS = {"width", "height", "alpha"}
PUBLISHED_STABLE_ID_COUNT_PROPERTY = "pimm_published_stable_id_count"
PUBLISHED_STABLE_ID_SHA256_PROPERTY = "pimm_published_stable_id_sha256"


@dataclass(frozen=True)
class SceneContract:
    """Exact identity, ownership, camera, and output contract for a scene."""

    schema_version: int
    scene_id: str
    machine: str
    purpose: str
    master_path: str
    master_sha256: str
    master_collection: str
    material_library_path: str
    material_library_sha256: str
    camera_name: str
    complete_product: bool
    animation_contract: str | None
    output_contract: dict[str, object]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "SceneContract":
        """Construct from an exact mapping without silently dropping fields."""

        if set(payload) != _FIELDS:
            missing = sorted(_FIELDS - set(payload))
            extra = sorted(set(payload) - _FIELDS)
            raise ValueError(
                "scene contract must contain exactly the required fields "
                f"(missing={missing}, extra={extra})"
            )
        output = payload["output_contract"]
        if not isinstance(output, Mapping):
            raise ValueError("scene contract output_contract must be an object")
        return cls(
            schema_version=payload["schema_version"],
            scene_id=payload["scene_id"],
            machine=payload["machine"],
            purpose=payload["purpose"],
            master_path=payload["master_path"],
            master_sha256=payload["master_sha256"],
            master_collection=payload["master_collection"],
            material_library_path=payload["material_library_path"],
            material_library_sha256=payload["material_library_sha256"],
            camera_name=payload["camera_name"],
            complete_product=payload["complete_product"],
            animation_contract=payload["animation_contract"],
            output_contract=dict(output),
        )

    @classmethod
    def from_json(cls, path: Path) -> "SceneContract":
        """Load an exact UTF-8 JSON scene contract."""

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("scene contract JSON root must be an object")
        return cls.from_mapping(payload)

    def to_mapping(self) -> dict[str, object]:
        """Return the deterministic JSON-ready field mapping."""

        return asdict(self)


def canonical_scene_contract_json(contract: SceneContract) -> str:
    """Return the canonical payload embedded in a contracted render scene."""

    return json.dumps(
        contract.to_mapping(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def stable_id_evidence(stable_ids: Iterable[str]) -> tuple[int, str]:
    """Return deterministic unique stable-ID count and SHA-256 evidence."""

    identifiers = sorted(set(stable_ids))
    payload = ("\n".join(identifiers) + "\n").encode("utf-8")
    return len(identifiers), hashlib.sha256(payload).hexdigest().upper()


def _canonical_relative(value: object, expected: str) -> bool:
    if not isinstance(value, str) or value != expected:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in value


def validate_scene_contract(contract: SceneContract) -> list[str]:
    """Return semantic errors; an empty list is the render-scene schema gate."""

    errors: list[str] = []
    if contract.schema_version != 1:
        errors.append("scene contract schema_version must be 1")
    if contract.machine not in {"30G", "50G"}:
        errors.append("scene contract machine must be 30G or 50G")
    match = _SCENE_ID.fullmatch(contract.scene_id) if isinstance(contract.scene_id, str) else None
    if match is None:
        errors.append("scene contract scene_id must match the canonical PIMM scene pattern")
    elif contract.machine in {"30G", "50G"} and match.group(1) != contract.machine.lower():
        errors.append("scene contract scene_id machine must match machine")
    if not isinstance(contract.purpose, str) or _SLUG.fullmatch(contract.purpose) is None:
        errors.append("scene contract purpose must be a lowercase slug")
    elif isinstance(contract.scene_id, str) and f"--{contract.purpose}" not in contract.scene_id:
        errors.append("scene contract purpose must be represented in scene_id")

    if contract.machine in {"30G", "50G"}:
        expected_master = f"masters/PIMM-{contract.machine}-MASTER.blend"
        if not _canonical_relative(contract.master_path, expected_master):
            errors.append(f"scene contract canonical master_path must equal {expected_master}")
    elif not isinstance(contract.master_path, str):
        errors.append("scene contract master_path must be a string")
    if (
        not isinstance(contract.master_sha256, str)
        or _SHA256.fullmatch(contract.master_sha256) is None
    ):
        errors.append("scene contract master_sha256 must be 64 hexadecimal characters")
    if contract.master_collection != "PIMM_PUBLISHED":
        errors.append("scene contract master_collection must equal PIMM_PUBLISHED")
    if not _canonical_relative(
        contract.material_library_path, "masters/PIMM-MATERIAL-LIBRARY.blend"
    ):
        errors.append(
            "scene contract canonical material_library_path must equal masters/PIMM-MATERIAL-LIBRARY.blend"
        )
    if (
        not isinstance(contract.material_library_sha256, str)
        or _SHA256.fullmatch(contract.material_library_sha256) is None
    ):
        errors.append(
            "scene contract material_library_sha256 must be 64 hexadecimal characters"
        )
    if not isinstance(contract.camera_name, str) or _CAMERA.fullmatch(contract.camera_name) is None:
        errors.append("scene contract camera_name must use the CAM_ managed name")
    if contract.complete_product is not True:
        errors.append("scene contract complete_product must be true")
    if contract.animation_contract is not None and (
        not isinstance(contract.animation_contract, str)
        or not contract.animation_contract.strip()
    ):
        errors.append("scene contract animation_contract must be null or a nonempty string")

    output = contract.output_contract
    if set(output) != _OUTPUT_FIELDS:
        errors.append("scene contract output_contract must contain exactly width, height, and alpha")
    width = output.get("width")
    height = output.get("height")
    alpha = output.get("alpha")
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        errors.append("scene contract output_contract width must be a positive integer")
    if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
        errors.append("scene contract output_contract height must be a positive integer")
    if not isinstance(alpha, bool):
        errors.append("scene contract output_contract alpha must be boolean")
    return errors


def load_authoritative_product_ids(
    asset_root: Path, machine: str
) -> tuple[set[str], list[str]]:
    """Load exact solid IDs from the authoritative import manifest."""

    path = asset_root / "manifests" / f"PIMM-{machine}-import-manifest.json"
    if not path.is_file():
        return set(), [f"authoritative import manifest is missing: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return set(), [f"authoritative import manifest cannot be read: {path}: {error}"]
    if not isinstance(payload, Mapping) or payload.get("schema_version") != 1:
        return set(), [f"authoritative import manifest schema_version must be 1: {path}"]
    solids = payload.get("solids")
    if not isinstance(solids, list) or not solids:
        return set(), [f"authoritative import manifest solids must be a nonempty list: {path}"]
    identifiers: list[str] = []
    errors: list[str] = []
    for index, solid in enumerate(solids):
        stable_id = solid.get("stable_id") if isinstance(solid, Mapping) else None
        if not isinstance(stable_id, str) or not stable_id.strip():
            errors.append(
                f"authoritative import manifest solids[{index}] lacks stable_id: {path}"
            )
        else:
            identifiers.append(stable_id)
    if len(set(identifiers)) != len(identifiers):
        errors.append(f"authoritative import manifest contains duplicate stable IDs: {path}")
    return set(identifiers), errors
