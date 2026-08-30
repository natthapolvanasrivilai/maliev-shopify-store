"""Author and validate governed preview-only PIMM editorial Blender scenes."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence
import uuid

try:
    from . import editorial_sets
    from .blender_scene_validator import _library_path
    from .blender_static_product_scene import (
        MASTER_FOOT_CONTACT_TOLERANCE,
        SHOT_CONFIGS,
        _InstancedStableMesh,
        _stable_product_objects,
        bounds_for_objects,
        foot_contact_evidence,
        resolve_live_foot_contact_planes,
    )
    from .editorial_concept_contract import (
        EDITORIAL_CAMPAIGN_ID,
        EDITORIAL_CAMPAIGN_PATH,
        EditorialConceptShot,
        load_editorial_campaign,
        validate_editorial_campaign,
    )
    from .io_contract import sha256_file
    from .paths import ASSET_ROOT, require_within
    from .scene_contract import stable_id_evidence
except ImportError:  # Blender executes checked-in scripts outside package mode.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production import editorial_sets
    from scripts.blender.pimm_production.blender_scene_validator import _library_path
    from scripts.blender.pimm_production.blender_static_product_scene import (
        MASTER_FOOT_CONTACT_TOLERANCE,
        SHOT_CONFIGS,
        _InstancedStableMesh,
        _stable_product_objects,
        bounds_for_objects,
        foot_contact_evidence,
        resolve_live_foot_contact_planes,
    )
    from scripts.blender.pimm_production.editorial_concept_contract import (
        EDITORIAL_CAMPAIGN_ID,
        EDITORIAL_CAMPAIGN_PATH,
        EditorialConceptShot,
        load_editorial_campaign,
        validate_editorial_campaign,
    )
    from scripts.blender.pimm_production.io_contract import sha256_file
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
    from scripts.blender.pimm_production.scene_contract import stable_id_evidence


RESULT_MARKER = "PIMM_EDITORIAL_SCENE_JSON="
VALIDATION_MARKER = "PIMM_EDITORIAL_VALIDATION_JSON="
SCHEMA = "maliev.pimm-editorial-scene/v1"
PUBLICATION_SCHEMA = "maliev.pimm-editorial-publication/v1"
SCENE_LIBRARY_ID = "editorial-concepts-v1"
CAMERA_NAME = "CAM_EDITORIAL"
MASTER_COLLECTION = "PIMM_PUBLISHED"
SENSOR_WIDTH_MM = 36.0
CLIP_START = 1.0
_CONTRACT_FIELDS = {
    "schema", "campaign_id", "scene_id", "machine", "concept", "scene_path",
    "master", "material_library", "contact", "camera", "render", "set",
    "external_assets", "input_policy", "preview_only", "final_authorized",
    "publication",
}


_CAMPAIGN = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH)
_CAMPAIGN_ERRORS = validate_editorial_campaign(_CAMPAIGN)
if _CAMPAIGN_ERRORS:
    raise ValueError("editorial campaign validation failed: " + "; ".join(_CAMPAIGN_ERRORS))


def _scene_relative_path(shot: EditorialConceptShot) -> str:
    return f"scenes/{SCENE_LIBRARY_ID}/{shot.shot_id}.blend"


def _scene_path(shot: EditorialConceptShot) -> Path:
    return ASSET_ROOT / Path(_scene_relative_path(shot))


def _contract_path(shot: EditorialConceptShot) -> Path:
    return (
        ASSET_ROOT
        / "scenes"
        / "contracts"
        / SCENE_LIBRARY_ID
        / f"{shot.shot_id}.json"
    )


def _completion_path(shot: EditorialConceptShot) -> Path:
    return _contract_path(shot).with_name(f"{shot.shot_id}.complete.json")


def _master_relative_path(machine: str) -> str:
    return f"masters/PIMM-{machine}-MASTER.blend"


def _master_path(machine: str) -> Path:
    return ASSET_ROOT / Path(_master_relative_path(machine))


def _material_path() -> Path:
    return ASSET_ROOT / "masters" / "PIMM-MATERIAL-LIBRARY.blend"


def _patch_relative_path(machine: str) -> str:
    return f"manifests/patches/PIMM-{machine}-foot-refresh.json"


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _contract_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _light_signature(lights: Sequence[object]) -> str:
    payload = [asdict(light) for light in lights]
    return _sha256_bytes(_canonical_json({"lights": payload}).encode("utf-8"))


def _set_contract(
    shot: EditorialConceptShot,
    external_assets: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    # Task 3 exposes only the construction entrypoint. Its immutable internal spec is
    # the safe preparation-time authority; authoring still calls the public builder.
    spec = editorial_sets._SETS[shot.concept]
    background_roles = {
        "warm-grey-floor", "warm-grey-wall", "window-gobo", "accent-slab",
        "graphite-floor", "graphite-wall", "black-flag-left", "black-flag-right",
    }
    support_allowlist = [
        {
            "name": item.name,
            "role": item.role,
            "object_type": "MESH",
            "source": "task-3-procedural",
            "framing_eligible": item.role not in background_roles,
            "contact_plane": "floor" in item.role,
        }
        for item in spec.geometry
    ]
    if not any(item["contact_plane"] for item in support_allowlist):
        support_allowlist.append({
            "name": "PIMM_SCENE_SUPPORT_EDITORIAL_CONTACT_PLANE",
            "role": "contact-plane",
            "object_type": "MESH",
            "source": "authoring-contact",
            "framing_eligible": False,
            "contact_plane": True,
        })
    for record in external_assets:
        asset_id = str(record["asset_id"])
        is_hdri = asset_id == "university_workshop"
        support_allowlist.append({
            "name": (
                "PIMM_SCENE_SUPPORT_WORKSHOP_HDRI_ENVIRONMENT"
                if is_hdri
                else f"PIMM_SCENE_SUPPORT_EXTERNAL_{asset_id.upper()}"
            ),
            "role": (
                "workshop-environment"
                if is_hdri
                else f"external-{asset_id.replace('_', '-')}"
            ),
            "object_type": "EMPTY",
            "source": "task-3-external",
            "framing_eligible": not is_hdri,
            "contact_plane": False,
        })
    coverage = {
        "architectural-daylight": (0.22, 0.75, 0.18),
        "dark-engineering": (0.20, 0.75, 0.18),
        "modern-workshop": (0.16, 0.65, 0.10),
        "process-still-life": (0.22, 0.35, 0.08),
    }[shot.concept]
    return {
        "concept": shot.concept,
        "geometry_signature": editorial_sets._geometry_signature(spec.geometry),
        "geometry_names": [item.name for item in spec.geometry],
        "geometry_roles": sorted({item.role for item in spec.geometry}),
        "light_signature": _light_signature(spec.lights),
        "light_roles": [item.role for item in spec.lights],
        "shadow_intent": spec.shadow_intent,
        "feature_counts": [[name, count] for name, count in editorial_sets._feature_counts(spec.geometry)],
        "support_allowlist": support_allowlist,
        "coverage_policy": {
            "minimum_machine_width_ratio": coverage[0],
            "minimum_machine_height_ratio": coverage[1],
            "minimum_machine_area_ratio": coverage[2],
            "minimum_safe_margin": 0.02,
        },
        "scene_geometry_signature": None,
        "scene_light_signature": None,
    }


def _external_contract(shot: EditorialConceptShot) -> list[dict[str, object]]:
    return [
        {
            "asset_id": record.asset_id,
            "source_url": record.source_url,
            "asset_version_id": record.asset_version_id,
            "license": record.license,
            "local_relative_path": record.local_relative_path,
            "sha256": record.sha256,
            "intended_shot_ids": list(record.intended_shot_ids),
            "machine_master_modified": record.machine_master_modified,
        }
        for record in editorial_sets._external_records(shot)
    ]


def _require_exact_shot(shot: EditorialConceptShot) -> None:
    expected = _CAMPAIGN.by_shot_id.get(shot.shot_id)
    if expected is None or expected != shot:
        raise ValueError(f"shot is not the exact approved editorial shot: {shot.shot_id}")


def prepare_editorial_contract(shot: EditorialConceptShot) -> dict[str, object]:
    """Prepare one exact preview contract without publishing either output file."""

    _require_exact_shot(shot)
    master = require_within(_master_path(shot.machine), ASSET_ROOT / "masters")
    material = require_within(_material_path(), ASSET_ROOT / "masters")
    patch = require_within(ASSET_ROOT / Path(_patch_relative_path(shot.machine)), ASSET_ROOT / "manifests")
    for label, path in (("master", master), ("material library", material), ("foot patch", patch)):
        if not path.is_file():
            raise FileNotFoundError(f"editorial {label} is missing: {path}")
    external_assets = _external_contract(shot)
    transaction_id = uuid.uuid4().hex
    return {
        "schema": SCHEMA,
        "campaign_id": EDITORIAL_CAMPAIGN_ID,
        "scene_id": shot.shot_id,
        "machine": shot.machine,
        "concept": shot.concept,
        "scene_path": _scene_relative_path(shot),
        "master": {
            "path": _master_relative_path(shot.machine),
            "sha256": sha256_file(master),
            "collection": MASTER_COLLECTION,
            "link_policy": "linked-read-only",
        },
        "material_library": {
            "path": "masters/PIMM-MATERIAL-LIBRARY.blend",
            "sha256": sha256_file(material),
            "link_policy": "linked-read-only-indirect",
        },
        "contact": {
            "gate": shot.contact_gate,
            "authority": "live-linked-master-four-nylon-feet",
            "patch_path": _patch_relative_path(shot.machine),
            "patch_sha256": sha256_file(patch),
            "tolerance": MASTER_FOOT_CONTACT_TOLERANCE,
        },
        "camera": {
            "name": CAMERA_NAME,
            "focal_length_mm": shot.focal_length_mm,
            "aperture_fstop": shot.aperture_fstop,
            "sensor_width_mm": SENSOR_WIDTH_MM,
            "aim": "machine-midline-eye-level",
            "verticals": "upright",
            "distance_solver": "full-machine-plus-prop-safe-framing-rectangle",
        },
        "render": {
            "engine": shot.render_engine,
            "width": shot.width,
            "height": shot.height,
            "resolution_percentage": 100,
            "preview_samples": shot.preview_samples,
            "denoise": shot.denoise,
            "view_transform": "AgX",
            "look": shot.color_management,
            "alpha": False,
        },
        "set": _set_contract(shot, external_assets),
        "external_assets": external_assets,
        "input_policy": _CAMPAIGN.input_policy,
        "preview_only": True,
        "final_authorized": False,
        "publication": {
            "schema": PUBLICATION_SCHEMA,
            "transaction_id": transaction_id,
            "completion_marker_path": (
                f"scenes/contracts/{SCENE_LIBRARY_ID}/{shot.shot_id}.complete.json"
            ),
            "authority": "marker-last-sha256-pair",
        },
    }


def _contract_errors(contract: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    if set(contract) != _CONTRACT_FIELDS:
        errors.append("editorial contract has unexpected fields")
        return errors
    shot_id = contract.get("scene_id")
    shot = _CAMPAIGN.by_shot_id.get(shot_id) if isinstance(shot_id, str) else None
    if shot is None:
        errors.append("editorial contract scene_id is not approved")
        return errors
    try:
        expected = prepare_editorial_contract(shot)
    except (OSError, ValueError) as error:
        return [str(error)]
    if contract.get("final_authorized") is not False:
        errors.append("final_authorized must remain false")
    if contract.get("preview_only") is not True:
        errors.append("editorial contract must remain preview-only")
    actual_master = contract.get("master")
    if not isinstance(actual_master, Mapping) or actual_master.get("sha256") != expected["master"]["sha256"]:
        errors.append("linked master SHA-256 does not match the current protected input")
    actual_material = contract.get("material_library")
    if not isinstance(actual_material, Mapping) or actual_material.get("sha256") != expected["material_library"]["sha256"]:
        errors.append("material-library SHA-256 does not match the current protected input")
    publication = contract.get("publication")
    expected_publication = expected["publication"]
    if not isinstance(publication, Mapping):
        errors.append("editorial publication metadata is missing")
    else:
        transaction_id = publication.get("transaction_id")
        if (
            publication.get("schema") != PUBLICATION_SCHEMA
            or publication.get("authority") != expected_publication["authority"]
            or publication.get("completion_marker_path") != expected_publication["completion_marker_path"]
            or not isinstance(transaction_id, str)
            or len(transaction_id) != 32
            or any(character not in "0123456789abcdef" for character in transaction_id)
        ):
            errors.append("editorial publication metadata is invalid")
    actual_set = contract.get("set")
    expected_set = expected["set"]
    if not isinstance(actual_set, Mapping):
        errors.append("editorial set contract is missing")
    else:
        for key, value in expected_set.items():
            if key in {"scene_geometry_signature", "scene_light_signature"}:
                signature = actual_set.get(key)
                if signature is not None and (
                    not isinstance(signature, str)
                    or len(signature) != 64
                    or any(character not in "0123456789ABCDEF" for character in signature)
                ):
                    errors.append(f"editorial set {key} is invalid")
            elif actual_set.get(key) != value:
                errors.append("editorial contract set does not match the exact approved shot")
                break
        if set(actual_set) != set(expected_set):
            errors.append("editorial contract set has unexpected fields")
    for key in _CONTRACT_FIELDS - {
        "master", "material_library", "final_authorized", "preview_only",
        "publication", "set",
    }:
        if contract.get(key) != expected.get(key):
            errors.append(f"editorial contract {key} does not match the exact approved shot")
    return list(dict.fromkeys(errors))


def _validate_editorial_runtime_snapshot(
    snapshot: Mapping[str, object], contract: Mapping[str, object]
) -> list[str]:
    """Validate a normalized read-only snapshot captured from an open Blender scene."""

    errors = _contract_errors(contract)
    if snapshot.get("scene_id") != contract.get("scene_id") or snapshot.get("scene_path_matches") is not True:
        errors.append("open editorial scene path or identity does not match the contract")
    if snapshot.get("embedded_contract_matches") is not True or snapshot.get("embedded_contract_sha256_matches") is not True:
        errors.append("embedded editorial contract payload or SHA-256 does not match")
    if snapshot.get("final_authorized") is not False:
        errors.append("final_authorized must remain false in the open scene")
    if snapshot.get("master_library_count") != 1:
        errors.append("scene must contain exactly one linked master collection")
    if snapshot.get("material_library_present") is not True:
        errors.append("scene is missing the linked material-library authority")
    if snapshot.get("unexpected_library_paths"):
        errors.append("scene contains a linked library outside governed authorities")
    if snapshot.get("library_overrides"):
        errors.append("linked machine or support library overrides are forbidden")
    if snapshot.get("local_product_copies"):
        errors.append("local product copies are forbidden")

    camera = snapshot.get("camera")
    expected_camera = contract.get("camera")
    if not isinstance(camera, Mapping) or not isinstance(expected_camera, Mapping):
        errors.append("editorial camera evidence is missing")
    else:
        if camera.get("active") is not True or camera.get("scene_local") is not True:
            errors.append("contracted editorial camera must be active and scene-local")
        if camera.get("focal_length_mm") != expected_camera.get("focal_length_mm"):
            errors.append("editorial camera focal length does not match Task 1")
        if camera.get("aperture_fstop") != expected_camera.get("aperture_fstop") or camera.get("sensor_width_mm") != SENSOR_WIDTH_MM:
            errors.append("editorial camera optics do not match the contract")
        if camera.get("verticals_upright") is not True:
            errors.append("architectural verticals are not upright")
        if camera.get("eye_level_midline") is not True:
            errors.append("camera does not aim at machine-midline eye level")
        if camera.get("complete_machine_framed") is not True:
            errors.append("complete linked machine is not inside the camera frame")
        if camera.get("support_rectangle_framed") is not True:
            errors.append("prop-safe support framing rectangle is not inside the camera frame")
        set_contract = contract.get("set")
        coverage = set_contract.get("coverage_policy") if isinstance(set_contract, Mapping) else None
        if isinstance(coverage, Mapping):
            if (
                float(camera.get("machine_frame_width_ratio", -math.inf))
                < float(coverage["minimum_machine_width_ratio"])
                or float(camera.get("machine_frame_height_ratio", -math.inf))
                < float(coverage["minimum_machine_height_ratio"])
                or float(camera.get("machine_frame_area_ratio", -math.inf))
                < float(coverage["minimum_machine_area_ratio"])
            ):
                errors.append("linked machine is not visually dominant in the projected frame")
            if float(camera.get("safe_margin_minimum", -math.inf)) < float(coverage["minimum_safe_margin"]):
                errors.append("machine and framing-eligible props violate the projected safe margin")

    render = snapshot.get("render")
    expected_render = contract.get("render")
    if not isinstance(render, Mapping) or not isinstance(expected_render, Mapping):
        errors.append("editorial render evidence is missing")
    else:
        for key in (
            "engine", "width", "height", "resolution_percentage", "preview_samples",
            "denoise", "view_transform", "look",
        ):
            if render.get(key) != expected_render.get(key):
                errors.append(f"editorial render {key} does not match the preview contract")

    contact = snapshot.get("contact")
    if not isinstance(contact, Mapping):
        errors.append("exactly four measured feet are required")
    else:
        stable_ids = contact.get("stable_ids")
        bottoms = contact.get("pad_bottoms")
        feet = contact.get("feet")
        if (
            not isinstance(stable_ids, list) or len(stable_ids) != 4 or len(set(stable_ids)) != 4
            or not isinstance(bottoms, list) or len(bottoms) != 4
            or not isinstance(feet, list) or len(feet) != 4
        ):
            errors.append("exactly four measured feet are required with stable IDs and bottoms")
        if contact.get("outlier_stable_ids") not in ([], ()) or float(contact.get("spread", math.inf)) > MASTER_FOOT_CONTACT_TOLERANCE:
            errors.append("all four feet must share the common contact plane")
        if isinstance(feet, list) and any(abs(float(item.get("delta_to_plane", math.inf))) > MASTER_FOOT_CONTACT_TOLERANCE for item in feet if isinstance(item, Mapping)):
            errors.append("per-foot measurements do not match the common contact plane")
    plane = snapshot.get("contact_plane")
    if not isinstance(plane, Mapping) or plane.get("count") != 1 or plane.get("covers_all_feet") is not True:
        errors.append("one scene-owned contact plane must cover all four feet")

    supports = snapshot.get("support_bounds")
    if not isinstance(supports, list):
        errors.append("support-bound evidence is missing")
    else:
        for support in supports:
            if not isinstance(support, Mapping):
                errors.append("support-bound evidence is malformed")
                continue
            if support.get("intersects_machine") is True:
                errors.append(f"prop/support intersects linked machine bounds: {support.get('name')}")
            if support.get("hides_foot_stable_ids"):
                errors.append(f"prop/support hides linked machine feet: {support.get('name')}")

    actual_set = snapshot.get("set")
    if (
        not isinstance(actual_set, Mapping)
        or not actual_set.get("scene_geometry_signature")
        or not actual_set.get("scene_light_signature")
    ):
        errors.append("editorial set signature evidence is missing")
    elif actual_set != contract.get("set"):
        errors.append("editorial set signatures do not match the contract")
    if snapshot.get("external_provenance") != contract.get("external_assets"):
        errors.append("exact external provenance is missing or changed")
    publication = snapshot.get("publication")
    if not isinstance(publication, Mapping) or publication.get("complete") is not True:
        errors.append("completed scene/contract publication marker is missing")
    elif not all(publication.get(key) is True for key in (
        "transaction_id_matches", "scene_sha256_matches", "contract_sha256_matches",
    )):
        errors.append("completed scene/contract publication marker does not match the pair")
    return list(dict.fromkeys(errors))


def _legacy_contact_config(machine: str) -> object:
    return next(config for config in SHOT_CONFIGS.values() if config.machine == machine)


def _bounds_mapping(bounds: tuple[tuple[float, float, float], tuple[float, float, float]]) -> dict[str, list[float]]:
    return {"minimum": list(bounds[0]), "maximum": list(bounds[1])}


def _object_bounds(obj: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    if getattr(obj, "type", None) == "MESH" and getattr(obj, "bound_box", None):
        try:
            from mathutils import Vector

            points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        except ImportError:
            points = [obj.matrix_world @ corner for corner in obj.bound_box]
        return (
            tuple(min(float(point[axis]) for point in points) for axis in range(3)),
            tuple(max(float(point[axis]) for point in points) for axis in range(3)),
        )
    collection = getattr(obj, "instance_collection", None)
    if getattr(obj, "instance_type", None) == "COLLECTION" and collection is not None:
        wrapped = [
            _InstancedStableMesh(source=member, matrix_world=obj.matrix_world @ member.matrix_world)
            for member in getattr(collection, "all_objects", ())
            if getattr(member, "type", None) == "MESH" and getattr(member, "bound_box", None)
        ]
        measured = [_object_bounds(item) for item in wrapped]
        measured = [item for item in measured if item is not None]
        return (
            tuple(min(item[0][axis] for item in measured) for axis in range(3)),
            tuple(max(item[1][axis] for item in measured) for axis in range(3)),
        ) if measured else None
    return None


def _overlap_positive(
    left: tuple[tuple[float, float, float], tuple[float, float, float]],
    right: tuple[tuple[float, float, float], tuple[float, float, float]],
    tolerance: float = 1e-6,
) -> bool:
    return all(
        min(left[1][axis], right[1][axis]) - max(left[0][axis], right[0][axis]) > tolerance
        for axis in range(3)
    )


def _foot_measurements(bpy: Any, machine: str, contact: object) -> list[dict[str, object]]:
    objects = _stable_product_objects(bpy)
    feet: list[dict[str, object]] = []
    for stable_id, bottom in zip(contact.stable_ids, contact.pad_bottoms, strict=True):
        bounds = bounds_for_objects([objects[stable_id]])
        feet.append({
            "stable_id": stable_id,
            "bottom_z": float(bottom),
            "center_x": (bounds[0][0] + bounds[1][0]) / 2.0,
            "center_y": (bounds[0][1] + bounds[1][1]) / 2.0,
            "delta_to_plane": float(bottom) - float(contact.z),
        })
    return feet


def _contact_payload(bpy: Any, machine: str) -> dict[str, object]:
    contact = resolve_live_foot_contact_planes(bpy, _legacy_contact_config(machine))[machine]
    payload = foot_contact_evidence(machine, contact)
    payload["selection_basis"] = "live-linked-master-four-nylon-feet"
    payload.pop("patch_path", None)
    payload["tolerance"] = MASTER_FOOT_CONTACT_TOLERANCE
    payload["spread"] = max(contact.pad_bottoms) - min(contact.pad_bottoms)
    payload["feet"] = _foot_measurements(bpy, machine, contact)
    return payload


def _support_objects(bpy: Any) -> list[Any]:
    return [
        obj for obj in bpy.context.scene.objects
        if obj.get("pimm_scene_support_ownership") == "scene-support"
    ]


def _support_bounds(bpy: Any) -> list[tuple[Any, tuple[tuple[float, float, float], tuple[float, float, float]]]]:
    result = []
    for obj in _support_objects(bpy):
        bounds = _object_bounds(obj)
        if bounds is not None:
            result.append((obj, bounds))
    return result


def _numeric_sequence(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        return [round(float(item), 9) for item in value]
    except (TypeError, ValueError):
        return None


def _matrix_sequence(value: Any) -> list[list[float]] | None:
    if value is None:
        return None
    try:
        return [[round(float(item), 9) for item in row] for row in value]
    except (TypeError, ValueError):
        return None


def _material_signature_record(material: Any) -> dict[str, object]:
    record: dict[str, object] = {
        "name": str(getattr(material, "name", "")),
        "library": str(getattr(getattr(material, "library", None), "filepath", "")),
        "diffuse_color": _numeric_sequence(getattr(material, "diffuse_color", None)),
        "properties": sorted(
            (str(key), str(value)) for key, value in getattr(material, "items", lambda: ())()
            if str(key).startswith("pimm_")
        ),
    }
    node_tree = getattr(material, "node_tree", None)
    shader = node_tree.nodes.get("Principled BSDF") if node_tree else None
    if shader is not None:
        record["principled"] = {
            key: _numeric_sequence(socket.default_value)
            if hasattr(socket.default_value, "__iter__")
            else round(float(socket.default_value), 9)
            if socket.default_value is not None
            else None
            for key, socket in sorted(shader.inputs.items())
            if key in {"Base Color", "Roughness", "Metallic", "Transmission Weight", "Alpha"}
        }
    return record


def _scene_geometry_signature(bpy: Any, allowed_names: set[str]) -> str:
    """Fingerprint reopened support datablocks, transforms, and identifying materials."""

    records: list[dict[str, object]] = []
    for obj in sorted(
        (item for item in bpy.context.scene.objects if str(getattr(item, "name", "")) in allowed_names),
        key=lambda item: str(item.name),
    ):
        data = getattr(obj, "data", None)
        materials = list(getattr(data, "materials", ())) if data is not None else []
        instance = getattr(obj, "instance_collection", None)
        records.append({
            "name": str(obj.name),
            "type": str(getattr(obj, "type", "")),
            "role": obj.get("pimm_scene_support_role"),
            "ownership": obj.get("pimm_scene_support_ownership"),
            "framing_eligible": obj.get("pimm_editorial_framing_eligible"),
            "contact_plane": obj.get("pimm_editorial_contact_plane"),
            "location": _numeric_sequence(getattr(obj, "location", None)),
            "rotation_euler": _numeric_sequence(getattr(obj, "rotation_euler", None)),
            "scale": _numeric_sequence(getattr(obj, "scale", None)),
            "matrix_world": _matrix_sequence(getattr(obj, "matrix_world", None)),
            "data_name": str(getattr(data, "name", "")),
            "vertex_count": len(getattr(data, "vertices", ())) if data is not None else 0,
            "polygon_count": len(getattr(data, "polygons", getattr(data, "faces", ()))) if data is not None else 0,
            "materials": [_material_signature_record(material) for material in materials if material is not None],
            "instance_type": str(getattr(obj, "instance_type", "")),
            "instance_collection": str(getattr(instance, "name", "")),
            "instance_library": str(_library_path(bpy, getattr(instance, "library", None)) or ""),
        })
    return _sha256_bytes(_canonical_json({"objects": records}).encode("utf-8"))


def _scene_light_signature(bpy: Any) -> str:
    """Fingerprint full reopened light/world data rather than embedded signature text."""

    records: list[dict[str, object]] = []
    for obj in sorted(
        (item for item in bpy.context.scene.objects if getattr(item, "type", None) == "LIGHT"),
        key=lambda item: str(item.name),
    ):
        data = obj.data
        records.append({
            "name": str(obj.name),
            "role": obj.get("pimm_editorial_light_role"),
            "type": str(getattr(data, "type", "")),
            "energy": round(float(getattr(data, "energy", 0.0)), 9),
            "color": _numeric_sequence(getattr(data, "color", None)),
            "shape": str(getattr(data, "shape", "")),
            "size": round(float(getattr(data, "size", 0.0)), 9),
            "size_y": round(float(getattr(data, "size_y", 0.0)), 9),
            "angle": round(float(getattr(data, "angle", 0.0)), 9),
            "shadow_soft_size": round(float(getattr(data, "shadow_soft_size", 0.0)), 9),
            "location": _numeric_sequence(getattr(obj, "location", None)),
            "rotation_euler": _numeric_sequence(getattr(obj, "rotation_euler", None)),
            "scale": _numeric_sequence(getattr(obj, "scale", None)),
            "matrix_world": _matrix_sequence(getattr(obj, "matrix_world", None)),
        })
    world = bpy.context.scene.world
    if world is not None:
        node_tree = getattr(world, "node_tree", None)
        background = node_tree.nodes.get("Background") if node_tree else None
        strength_socket = background.inputs.get("Strength") if background else None
        node_values = getattr(getattr(node_tree, "nodes", None), "_items", {}).values() if node_tree else ()
        try:
            node_values = list(node_tree.nodes) if node_tree else []
        except TypeError:
            pass
        environment_images = sorted(
            str(getattr(getattr(node, "image", None), "filepath", ""))
            for node in node_values
            if getattr(node, "image", None) is not None
        ) if node_tree else []
        records.append({
            "name": str(getattr(world, "name", "")),
            "role": world.get("pimm_editorial_light_role"),
            "external_version": world.get("pimm_external_asset_version_id"),
            "external_sha256": world.get("pimm_external_sha256"),
            "strength": round(float(strength_socket.default_value), 9) if strength_socket and strength_socket.default_value is not None else None,
            "environment_images": environment_images,
        })
    return _sha256_bytes(_canonical_json({"lights": records}).encode("utf-8"))


_LOCAL_RENDERABLE_TYPES = {"MESH", "CURVE", "SURFACE", "FONT", "VOLUME"}
_PRODUCT_PROPERTIES = {
    "pimm_stable_id", "pimm_artwork_id", "pimm_machine", "pimm_asset_role",
    "pimm_product_material_override",
}


def _has_product_identity(obj: Any) -> bool:
    datablocks = [obj, getattr(obj, "data", None)]
    data = getattr(obj, "data", None)
    datablocks.extend(getattr(data, "materials", ()) if data is not None else ())
    instance = getattr(obj, "instance_collection", None)
    instance_objects = list(getattr(instance, "all_objects", ())) if instance is not None else []
    datablocks.extend(instance_objects)
    for member in instance_objects:
        member_data = getattr(member, "data", None)
        datablocks.append(member_data)
        datablocks.extend(getattr(member_data, "materials", ()) if member_data is not None else ())
    return any(
        datablock is not None and any(datablock.get(key) is not None for key in _PRODUCT_PROPERTIES)
        for datablock in datablocks
    )


def _scene_object_allowlist_errors(
    bpy: Any, allowlist: Sequence[Mapping[str, object]]
) -> list[str]:
    expected = {str(record["name"]): record for record in allowlist}
    actual_supports = {
        str(obj.name): obj for obj in bpy.context.scene.objects
        if obj.get("pimm_scene_support_ownership") == "scene-support"
    }
    errors: list[str] = []
    for name, record in expected.items():
        obj = actual_supports.get(name)
        if obj is None:
            errors.append(f"expected scene-support object is missing: {name}")
            continue
        if getattr(obj, "type", None) != record["object_type"]:
            errors.append(f"scene-support object type changed: {name}")
        if obj.get("pimm_scene_support_role") != record["role"]:
            errors.append(f"scene-support role changed: {name}")
        if obj.get("pimm_editorial_framing_eligible") is not record["framing_eligible"]:
            errors.append(f"scene-support framing eligibility changed: {name}")
        if obj.get("pimm_editorial_contact_plane") is not record["contact_plane"]:
            errors.append(f"scene-support contact-plane authority changed: {name}")
        if _has_product_identity(obj):
            errors.append(f"scene-support carries forbidden product ownership or stable ID: {name}")
    for name in sorted(set(actual_supports) - set(expected)):
        errors.append(f"unexpected scene-support object: {name}")
    for obj in bpy.context.scene.objects:
        if (
            getattr(obj, "type", None) in _LOCAL_RENDERABLE_TYPES
            and _library_path(bpy, getattr(obj, "library", None)) is None
            and str(obj.name) not in expected
        ):
            errors.append(f"unexpected local renderable object: {obj.name}")
            if _has_product_identity(obj):
                errors.append(f"unexpected local renderable has product ownership or stable ID: {obj.name}")
    return errors


def _collection_reachable(scene_collection: Any, target: Any) -> bool:
    pending = list(getattr(scene_collection, "children", ()))
    seen: set[int] = set()
    while pending:
        collection = pending.pop()
        if collection is target:
            return True
        marker = id(collection)
        if marker in seen:
            continue
        seen.add(marker)
        pending.extend(getattr(collection, "children", ()))
    return False


def _frame_contains_bounds(bpy: Any, camera: Any, bounds: tuple[tuple[float, float, float], tuple[float, float, float]]) -> bool:
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    for x in (bounds[0][0], bounds[1][0]):
        for y in (bounds[0][1], bounds[1][1]):
            for z in (bounds[0][2], bounds[1][2]):
                coordinate = world_to_camera_view(bpy.context.scene, camera, Vector((x, y, z)))
                if coordinate.z <= 0.0 or not (0.01 <= coordinate.x <= 0.99 and 0.01 <= coordinate.y <= 0.99):
                    return False
    return True


def _project_bounds(
    bpy: Any,
    camera: Any,
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> dict[str, object]:
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    projected = [
        world_to_camera_view(bpy.context.scene, camera, Vector((x, y, z)))
        for x in (bounds[0][0], bounds[1][0])
        for y in (bounds[0][1], bounds[1][1])
        for z in (bounds[0][2], bounds[1][2])
    ]
    minimum = [min(float(point[axis]) for point in projected) for axis in (0, 1)]
    maximum = [max(float(point[axis]) for point in projected) for axis in (0, 1)]
    width = maximum[0] - minimum[0]
    height = maximum[1] - minimum[1]
    return {
        "minimum": minimum,
        "maximum": maximum,
        "depth_min": min(float(point.z) for point in projected),
        "depth_max": max(float(point.z) for point in projected),
        "width_ratio": width,
        "height_ratio": height,
        "area_ratio": width * height,
        "safe_margin_minimum": min(minimum[0], minimum[1], 1.0 - maximum[0], 1.0 - maximum[1]),
    }


def _projected_occlusion(
    support: Mapping[str, object], foot: Mapping[str, object], tolerance: float = 1e-6
) -> bool:
    support_min = support["minimum"]
    support_max = support["maximum"]
    foot_min = foot["minimum"]
    foot_max = foot["maximum"]
    overlaps = all(
        min(float(support_max[axis]), float(foot_max[axis]))
        - max(float(support_min[axis]), float(foot_min[axis])) > tolerance
        for axis in (0, 1)
    )
    return overlaps and float(support["depth_min"]) < float(foot["depth_min"]) - tolerance


def _provenance_record(datablock: Any) -> dict[str, object] | None:
    version = datablock.get("pimm_external_asset_version_id")
    if not isinstance(version, str):
        return None
    intended = datablock.get("pimm_external_intended_shot_ids")
    try:
        intended_ids = json.loads(intended) if isinstance(intended, str) else None
    except json.JSONDecodeError:
        intended_ids = None
    source = str(datablock.get("pimm_external_source_url", ""))
    return {
        "asset_id": source.rstrip("/").rsplit("/", 1)[-1],
        "source_url": source,
        "asset_version_id": version,
        "license": datablock.get("pimm_external_license"),
        "local_relative_path": datablock.get("pimm_external_local_relative_path"),
        "sha256": datablock.get("pimm_external_sha256"),
        "intended_shot_ids": intended_ids,
        "machine_master_modified": datablock.get("pimm_external_machine_master_modified"),
    }


def _collect_runtime_snapshot(bpy: Any, contract: Mapping[str, object]) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    machine = str(contract["machine"])
    master_path = (ASSET_ROOT / Path(str(contract["master"]["path"]))).resolve()
    material_path = (ASSET_ROOT / Path(str(contract["material_library"]["path"]))).resolve()
    allowed_external = {
        (ASSET_ROOT / Path(str(record["local_relative_path"]))).resolve()
        for record in contract["external_assets"]
        if str(record["local_relative_path"]).lower().endswith(".blend")
    }
    library_paths = {
        path for path in (_library_path(bpy, library) for library in bpy.data.libraries)
        if path is not None
    }
    master_collections = [
        collection for collection in bpy.data.collections
        if str(getattr(collection, "name", "")).startswith(MASTER_COLLECTION)
        and _library_path(bpy, getattr(collection, "library", None)) == master_path
    ]
    if len(master_collections) == 1 and not _collection_reachable(scene.collection, master_collections[0]):
        errors.append("linked PIMM_PUBLISHED is not reachable from the active scene")
    overrides = [
        str(getattr(item, "name", ""))
        for group in (bpy.data.objects, bpy.data.collections, bpy.data.meshes, bpy.data.materials)
        for item in group
        if getattr(item, "override_library", None) is not None
    ]
    allowlist = contract["set"]["support_allowlist"]
    errors.extend(_scene_object_allowlist_errors(bpy, allowlist))
    expected_support_names = {str(record["name"]) for record in allowlist}
    local_product = [
        str(obj.name) for obj in bpy.data.objects
        if getattr(obj, "type", None) in _LOCAL_RENDERABLE_TYPES
        and str(obj.name) not in expected_support_names
        and _library_path(bpy, getattr(obj, "library", None)) is None
    ]
    products = _stable_product_objects(bpy)
    machine_products = {key: value for key, value in products.items() if key.startswith(f"{machine}-")}
    machine_bounds = bounds_for_objects(machine_products.values())
    count, stable_sha = stable_id_evidence(machine_products)
    contact = _contact_payload(bpy, machine)
    feet_by_id = {
        stable_id: bounds_for_objects([products[stable_id]])
        for stable_id in contact["stable_ids"]
    }
    camera = bpy.data.objects.get(str(contract["camera"]["name"]))
    support_records = []
    for obj, bounds in _support_bounds(bpy):
        hidden = []
        for stable_id, foot_bounds in feet_by_id.items():
            projected_support = _project_bounds(bpy, camera, bounds) if camera is not None else None
            projected_foot = _project_bounds(bpy, camera, foot_bounds) if camera is not None else None
            if (
                projected_support is not None
                and projected_foot is not None
                and _projected_occlusion(projected_support, projected_foot)
                and obj.get("pimm_editorial_contact_plane") is not True
            ):
                hidden.append(stable_id)
        support_records.append({
            "name": str(obj.name),
            "role": obj.get("pimm_scene_support_role"),
            **_bounds_mapping(bounds),
            "intersects_machine": _overlap_positive(bounds, machine_bounds),
            "hides_foot_stable_ids": hidden,
        })
    planes = [obj for obj in _support_objects(bpy) if obj.get("pimm_editorial_contact_plane") is True]
    plane_bounds = _object_bounds(planes[0]) if len(planes) == 1 else None
    plane_covers = bool(plane_bounds) and all(
        plane_bounds[0][0] <= foot["center_x"] <= plane_bounds[1][0]
        and plane_bounds[0][1] <= foot["center_y"] <= plane_bounds[1][1]
        for foot in contact["feet"]
    )

    camera_data = getattr(camera, "data", None)
    target_raw = scene.get("pimm_editorial_camera_target")
    try:
        target = tuple(float(value) for value in json.loads(target_raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        target = (math.inf, math.inf, math.inf)
    vertical = camera.matrix_world.to_quaternion() @ __import__("mathutils").Vector((0.0, 1.0, 0.0)) if camera else None
    forward = camera.matrix_world.to_quaternion() @ __import__("mathutils").Vector((0.0, 0.0, -1.0)) if camera else None
    supports_with_bounds = [
        bounds for obj, bounds in _support_bounds(bpy)
        if obj.get("pimm_editorial_framing_eligible") is True
    ]
    support_rectangle = (
        (
            tuple(min(bounds[0][axis] for bounds in supports_with_bounds) for axis in range(3)),
            tuple(max(bounds[1][axis] for bounds in supports_with_bounds) for axis in range(3)),
        )
        if supports_with_bounds else machine_bounds
    )
    actual_provenance: dict[str, dict[str, object]] = {}
    for datablock in [*scene.objects, *([scene.world] if scene.world is not None else [])]:
        record = _provenance_record(datablock)
        if record is not None:
            prior = actual_provenance.setdefault(str(record["asset_version_id"]), record)
            if prior != record:
                errors.append("conflicting external provenance records in open scene")
    set_payload = dict(contract["set"])
    set_payload["scene_geometry_signature"] = _scene_geometry_signature(
        bpy, expected_support_names
    )
    set_payload["scene_light_signature"] = _scene_light_signature(bpy)
    opened = Path(str(bpy.data.filepath)).resolve()
    final_path = (ASSET_ROOT / Path(str(contract["scene_path"]))).resolve()
    candidate_ok = opened.parent == final_path.parent and opened.name.startswith(f".{final_path.stem}.") and opened.suffix == ".blend"
    expected_contract_sha = _sha256_bytes(_contract_bytes(contract))
    machine_projection = _project_bounds(bpy, camera, machine_bounds) if camera is not None else {}
    framing_projection = _project_bounds(bpy, camera, support_rectangle) if camera is not None else {}
    transaction_id = contract["publication"]["transaction_id"]
    publication = {
        "complete": False,
        "transaction_id_matches": scene.get("pimm_publication_transaction_id") == transaction_id,
        "scene_sha256_matches": False,
        "contract_sha256_matches": False,
    }
    if candidate_ok:
        publication.update({
            "complete": True,
            "scene_sha256_matches": True,
            "contract_sha256_matches": True,
        })
    elif opened == final_path:
        marker_path = (ASSET_ROOT / Path(str(contract["publication"]["completion_marker_path"]))).resolve()
        contract_path = _contract_path(_CAMPAIGN.by_shot_id[str(contract["scene_id"])]).resolve()
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            marker = None
        if isinstance(marker, Mapping):
            publication.update({
                "complete": marker.get("schema") == PUBLICATION_SCHEMA and marker.get("scene_id") == contract["scene_id"],
                "transaction_id_matches": marker.get("transaction_id") == transaction_id and publication["transaction_id_matches"],
                "scene_sha256_matches": marker.get("scene_sha256") == sha256_file(opened),
                "contract_sha256_matches": contract_path.is_file() and marker.get("contract_sha256") == sha256_file(contract_path),
            })
    snapshot = {
        "scene_id": scene.get("pimm_editorial_scene_id"),
        "scene_path_matches": opened == final_path or candidate_ok,
        "embedded_contract_matches": scene.get("pimm_editorial_contract_payload") == _canonical_json(contract),
        "embedded_contract_sha256_matches": scene.get("pimm_editorial_contract_sha256") == expected_contract_sha,
        "final_authorized": scene.get("pimm_final_authorized"),
        "master_library_count": len(master_collections),
        "material_library_present": material_path in library_paths,
        "unexpected_library_paths": sorted(str(path) for path in library_paths - {master_path, material_path, *allowed_external}),
        "library_overrides": overrides,
        "local_product_copies": local_product,
        "linked_product_count": len(machine_products),
        "stable_id_count": count,
        "stable_id_sha256": stable_sha,
        "machine_bounds": _bounds_mapping(machine_bounds),
        "camera": {
            "active": scene.camera is camera,
            "scene_local": camera is not None and getattr(camera, "library", None) is None and getattr(camera_data, "library", None) is None,
            "focal_length_mm": float(camera_data.lens) if camera_data else None,
            "aperture_fstop": float(camera_data.dof.aperture_fstop) if camera_data else None,
            "sensor_width_mm": float(camera_data.sensor_width) if camera_data else None,
            "verticals_upright": bool(vertical) and abs(float(vertical.z) - 1.0) <= 1e-6 and abs(float(forward.z)) <= 1e-6,
            "eye_level_midline": camera is not None and abs(float(camera.location.z) - target[2]) <= 1e-5 and abs(target[2] - ((machine_bounds[0][2] + machine_bounds[1][2]) / 2.0)) <= 1e-5,
            "complete_machine_framed": camera is not None and _frame_contains_bounds(bpy, camera, machine_bounds),
            "support_rectangle_framed": camera is not None and _frame_contains_bounds(bpy, camera, support_rectangle),
            "machine_frame_width_ratio": machine_projection.get("width_ratio"),
            "machine_frame_height_ratio": machine_projection.get("height_ratio"),
            "machine_frame_area_ratio": machine_projection.get("area_ratio"),
            "safe_margin_minimum": min(
                float(machine_projection.get("safe_margin_minimum", -math.inf)),
                float(framing_projection.get("safe_margin_minimum", -math.inf)),
            ),
        },
        "render": {
            "engine": scene.render.engine,
            "width": scene.render.resolution_x,
            "height": scene.render.resolution_y,
            "resolution_percentage": scene.render.resolution_percentage,
            "preview_samples": scene.cycles.samples,
            "denoise": scene.cycles.use_denoising,
            "view_transform": scene.view_settings.view_transform,
            "look": scene.view_settings.look,
        },
        "contact": contact,
        "contact_plane": {
            "count": len(planes),
            "z": plane_bounds[0][2] if plane_bounds else None,
            "covers_all_feet": plane_covers and plane_bounds is not None and abs(plane_bounds[0][2] - float(contact["contact_z"])) <= 1e-6 and abs(plane_bounds[1][2] - float(contact["contact_z"])) <= 1e-6,
        },
        "support_bounds": support_records,
        "set": set_payload,
        "external_provenance": [
            actual_provenance[str(record["asset_version_id"])]
            for record in contract["external_assets"]
            if str(record["asset_version_id"]) in actual_provenance
        ] + [
            record for version, record in actual_provenance.items()
            if version not in {str(item["asset_version_id"]) for item in contract["external_assets"]}
        ],
        "publication": publication,
    }
    return snapshot, errors


def validate_open_editorial_scene(bpy: Any, contract: Mapping[str, object]) -> list[str]:
    """Return all errors for an already-open editorial scene without mutation."""

    try:
        snapshot, collection_errors = _collect_runtime_snapshot(bpy, contract)
    except Exception as error:
        return [f"editorial scene inspection failed: {error}"]
    return list(dict.fromkeys([*collection_errors, *_validate_editorial_runtime_snapshot(snapshot, contract)]))


def _flatten_contact_plane(obj: Any, contact_z: float, machine_bounds: tuple[tuple[float, float, float], tuple[float, float, float]]) -> None:
    for vertex in obj.data.vertices:
        vertex.co.z = 0.0
    width = machine_bounds[1][0] - machine_bounds[0][0] + 20_000.0
    depth = machine_bounds[1][1] - machine_bounds[0][1] + 20_000.0
    current = _object_bounds(obj)
    if current is None:
        raise ValueError("editorial contact plane has no bounds")
    current_width = current[1][0] - current[0][0]
    current_depth = current[1][1] - current[0][1]
    obj.scale.x *= width / current_width
    obj.scale.y *= depth / current_depth
    obj.location.x = (machine_bounds[0][0] + machine_bounds[1][0]) / 2.0
    obj.location.y = (machine_bounds[0][1] + machine_bounds[1][1]) / 2.0
    obj.location.z = contact_z
    obj["pimm_editorial_contact_plane"] = True


def _translate_group(objects: Sequence[Any], delta_x: float) -> None:
    for obj in objects:
        obj.location.x += delta_x


def _scale_and_place_group(
    objects: Sequence[Any], scale: float, center_x: float, minimum_y: float
) -> None:
    bounds = _group_bounds(objects)
    source_center = tuple((bounds[0][axis] + bounds[1][axis]) / 2.0 for axis in range(3))
    source_min_y = bounds[0][1]
    delta_y = minimum_y - (source_center[1] + (source_min_y - source_center[1]) * scale)
    for obj in objects:
        obj.location.x = center_x + (float(obj.location.x) - source_center[0]) * scale
        obj.location.y = float(obj.location.y) + delta_y + (float(obj.location.y) - source_center[1]) * (scale - 1.0)
        obj.location.z = source_center[2] + (float(obj.location.z) - source_center[2]) * scale
        obj.scale = tuple(float(value) * scale for value in obj.scale)


def _group_bounds(objects: Sequence[Any]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    measured = [bounds for obj in objects if (bounds := _object_bounds(obj)) is not None]
    if not measured:
        raise ValueError("editorial support group has no bounds")
    return (
        tuple(min(bounds[0][axis] for bounds in measured) for axis in range(3)),
        tuple(max(bounds[1][axis] for bounds in measured) for axis in range(3)),
    )


def _place_supports(
    bpy: Any,
    shot: EditorialConceptShot,
    evidence: object,
    machine_bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
    contact_z: float,
    allowlist: Sequence[Mapping[str, object]],
) -> None:
    expected = {str(record["name"]): record for record in allowlist}
    for obj in _support_objects(bpy):
        record = expected.get(str(obj.name))
        if record is not None:
            obj["pimm_editorial_framing_eligible"] = bool(record["framing_eligible"])
            obj["pimm_editorial_contact_plane"] = bool(record["contact_plane"])
    bpy.context.view_layer.update()
    geometry = [bpy.data.objects.get(item.name) for item in evidence.geometry]
    if any(obj is None for obj in geometry):
        raise ValueError("editorial set builder did not create every contracted support")
    floors = [obj for obj in geometry if "floor" in str(obj.get("pimm_scene_support_role", ""))]
    if floors:
        if len(floors) != 1:
            raise ValueError("editorial scene must have one contact floor")
        _flatten_contact_plane(floors[0], contact_z, machine_bounds)
    else:
        width = machine_bounds[1][0] - machine_bounds[0][0] + 20_000.0
        depth = machine_bounds[1][1] - machine_bounds[0][1] + 20_000.0
        spec = editorial_sets._geometry(
            "EDITORIAL_CONTACT_PLANE", "contact-plane", "box",
            (
                (machine_bounds[0][0] + machine_bounds[1][0]) / 2.0,
                (machine_bounds[0][1] + machine_bounds[1][1]) / 2.0,
                contact_z,
            ),
            (width, depth, 0.0),
            (0.12, 0.13, 0.15, 1.0),
            0.72,
        )
        plane = editorial_sets._install_geometry(bpy, spec)
        plane["pimm_editorial_contact_plane"] = True
        plane["pimm_editorial_framing_eligible"] = False

    left_edge = machine_bounds[0][0] - 2_500.0
    right_edge = machine_bounds[1][0] + 2_500.0
    if shot.concept in {"modern-workshop", "process-still-life"}:
        procedural = [obj for obj in geometry if obj not in floors]
        machine_center_x = (machine_bounds[0][0] + machine_bounds[1][0]) / 2.0
        _scale_and_place_group(
            procedural,
            0.35 if shot.concept == "modern-workshop" else 0.40,
            machine_center_x,
            machine_bounds[1][1] + 220.0,
        )
        bpy.context.view_layer.update()
        external = [obj for obj in _support_objects(bpy) if getattr(obj, "instance_type", None) == "COLLECTION"]
        for obj in external:
            bounds = _object_bounds(obj)
            if bounds is None:
                raise ValueError("external editorial support has no bounds")
            obj.location.x += machine_center_x - ((bounds[0][0] + bounds[1][0]) / 2.0)
            obj.location.y += machine_bounds[1][1] + 420.0 - bounds[0][1]
    else:
        walls = [obj for obj in geometry if "wall" in str(obj.get("pimm_scene_support_role", ""))]
        for wall in walls:
            bounds = _object_bounds(wall)
            wall.location.y += machine_bounds[1][1] + 5_000.0 - bounds[0][1]
            wall.location.z = (machine_bounds[0][2] + machine_bounds[1][2]) / 2.0
        left = [
            obj for obj in geometry if obj not in floors + walls
            and ("left" in str(obj.get("pimm_scene_support_role", "")) or float(obj.location.x) < 0.0)
        ]
        right = [obj for obj in geometry if obj not in floors + walls + left]
        if left:
            bounds = _group_bounds(left)
            _translate_group(left, left_edge - bounds[1][0])
        if right:
            bounds = _group_bounds(right)
            _translate_group(right, right_edge - bounds[0][0])
    bpy.context.view_layer.update()


def _configure_camera(
    bpy: Any,
    shot: EditorialConceptShot,
    machine_bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> tuple[Any, tuple[float, float, float], dict[str, object]]:
    from mathutils import Vector

    support_bounds = [
        bounds for obj, bounds in _support_bounds(bpy)
        if obj.get("pimm_editorial_framing_eligible") is True
    ]
    combined = (
        tuple(min([machine_bounds[0][axis], *[bounds[0][axis] for bounds in support_bounds]]) for axis in range(3)),
        tuple(max([machine_bounds[1][axis], *[bounds[1][axis] for bounds in support_bounds]]) for axis in range(3)),
    )
    target = (
        (machine_bounds[0][0] + machine_bounds[1][0]) / 2.0,
        (machine_bounds[0][1] + machine_bounds[1][1]) / 2.0,
        (machine_bounds[0][2] + machine_bounds[1][2]) / 2.0,
    )
    tan_horizontal = SENSOR_WIDTH_MM / (2.0 * shot.focal_length_mm)
    tan_vertical = tan_horizontal / (shot.width / shot.height)
    horizontal = max(abs(combined[0][0] - target[0]), abs(combined[1][0] - target[0]))
    vertical = max(abs(combined[0][2] - target[2]), abs(combined[1][2] - target[2]))
    near_distance = max(horizontal / tan_horizontal, vertical / tan_vertical) * 1.08
    location = (target[0], combined[0][1] - near_distance, target[2])
    data = bpy.data.cameras.new(CAMERA_NAME)
    camera = bpy.data.objects.new(CAMERA_NAME, data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    data.lens = shot.focal_length_mm
    data.sensor_width = SENSOR_WIDTH_MM
    data.sensor_fit = "HORIZONTAL"
    data.clip_start = CLIP_START
    data.clip_end = max(2_000_000.0, (combined[1][1] - location[1]) * 1.5)
    data.dof.use_dof = True
    data.dof.aperture_fstop = shot.aperture_fstop
    data.dof.focus_distance = math.dist(location, target)
    bpy.context.scene.camera = camera
    bpy.context.view_layer.update()
    support_rectangle = (
        (
            tuple(min(bounds[0][axis] for bounds in support_bounds) for axis in range(3)),
            tuple(max(bounds[1][axis] for bounds in support_bounds) for axis in range(3)),
        )
        if support_bounds else machine_bounds
    )
    return camera, target, {
        "machine_bounds": _bounds_mapping(machine_bounds),
        "support_rectangle": _bounds_mapping(support_rectangle),
        "combined_bounds": _bounds_mapping(combined),
        "location": list(location),
        "target": list(target),
        "near_distance": near_distance,
    }


def author_editorial_scene(
    bpy: Any, shot: EditorialConceptShot, contract: Mapping[str, object]
) -> dict[str, object]:
    """Author one in-memory scene from linked protected inputs; publication is separate."""

    _require_exact_shot(shot)
    contract_errors = _contract_errors(contract)
    if contract_errors:
        raise ValueError("invalid editorial contract: " + "; ".join(contract_errors))
    master = _master_path(shot.machine).resolve()
    with bpy.data.libraries.load(str(master), link=True, relative=False) as (available, requested):
        if MASTER_COLLECTION not in available.collections:
            raise ValueError(f"current master is missing {MASTER_COLLECTION}: {master}")
        requested.collections = [MASTER_COLLECTION]
    linked = next((item for item in requested.collections if item is not None), None)
    if linked is None:
        raise ValueError("linked PIMM_PUBLISHED collection did not resolve")
    bpy.context.scene.collection.children.link(linked)
    bpy.context.view_layer.update()
    contact = resolve_live_foot_contact_planes(bpy, _legacy_contact_config(shot.machine))[shot.machine]
    products = _stable_product_objects(bpy)
    machine_products = {key: value for key, value in products.items() if key.startswith(f"{shot.machine}-")}
    machine_bounds = bounds_for_objects(machine_products.values())
    set_evidence = editorial_sets.build_editorial_set(bpy, shot)
    set_contract = contract["set"]
    if not isinstance(set_contract, dict):
        raise ValueError("editorial set contract must be mutable during authoring")
    _place_supports(
        bpy, shot, set_evidence, machine_bounds, contact.z,
        set_contract["support_allowlist"],
    )
    camera, target, framing = _configure_camera(bpy, shot, machine_bounds)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001
    scene.render.engine = "CYCLES"
    scene.cycles.samples = shot.preview_samples
    scene.cycles.use_denoising = shot.denoise
    scene.render.resolution_x = shot.width
    scene.render.resolution_y = shot.height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.filepath = str(
        ASSET_ROOT / "renders" / "proofs" / "unapproved" / EDITORIAL_CAMPAIGN_ID / shot.shot_id / shot.shot_id
    )
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = shot.color_management
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("PIMM_EDITORIAL_WORLD")
    allowed_names = {str(record["name"]) for record in set_contract["support_allowlist"]}
    set_contract["scene_geometry_signature"] = _scene_geometry_signature(bpy, allowed_names)
    set_contract["scene_light_signature"] = _scene_light_signature(bpy)
    set_payload = dict(set_contract)
    scene["pimm_editorial_scene_id"] = shot.shot_id
    scene["pimm_editorial_contract_payload"] = _canonical_json(contract)
    scene["pimm_editorial_contract_sha256"] = _sha256_bytes(_contract_bytes(contract))
    scene["pimm_publication_transaction_id"] = contract["publication"]["transaction_id"]
    scene["pimm_editorial_set_evidence"] = _canonical_json(set_payload)
    scene["pimm_editorial_camera_target"] = json.dumps(list(target), separators=(",", ":"))
    scene["pimm_editorial_framing_evidence"] = _canonical_json(framing)
    scene["pimm_foot_contact_evidence"] = _canonical_json(_contact_payload(bpy, shot.machine))
    count, identifier_sha = stable_id_evidence(machine_products)
    scene["pimm_product_stable_id_evidence"] = _canonical_json({"count": count, "sha256": identifier_sha})
    scene["pimm_machine_bounds"] = _canonical_json(_bounds_mapping(machine_bounds))
    scene["pimm_final_authorized"] = False
    return {
        "scene_id": shot.shot_id,
        "camera": camera.name,
        "framing": framing,
        "contact": _contact_payload(bpy, shot.machine),
        "stable_ids": {"count": count, "sha256": identifier_sha},
    }


def _preserve_rejected(paths: Sequence[Path], shot_id: str) -> list[str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    root = ASSET_ROOT / "scenes" / "rejected" / EDITORIAL_CAMPAIGN_ID / timestamp
    root.mkdir(parents=True, exist_ok=False)
    preserved = []
    for path in paths:
        if path.exists():
            destination = root / path.name.lstrip(".")
            os.rename(path, destination)
            preserved.append(str(destination))
    if not preserved:
        marker = root / f"{shot_id}.txt"
        marker.write_text("candidate failed before Blender produced a scene\n", encoding="utf-8")
        preserved.append(str(marker))
    return preserved


def _atomic_json_write(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = path.with_name(f".{path.name}.{uuid.uuid4().hex}.candidate")
    with candidate.open("xb") as stream:
        stream.write(_contract_bytes(payload))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(candidate, path)


def _commit_publication_pair(
    *,
    scene_candidate: Path,
    contract_candidate: Path,
    transaction_candidate: Path,
    scene_destination: Path,
    contract_destination: Path,
    marker_destination: Path,
    marker_payload: Mapping[str, object],
    interrupt: Callable[[str], None] | None = None,
) -> None:
    """Publish the pair, then its sole consumer authority marker last."""

    callback = interrupt or (lambda _stage: None)
    if any(path.exists() for path in (scene_destination, contract_destination, marker_destination)):
        raise FileExistsError("editorial publication destination already exists")
    os.rename(contract_candidate, contract_destination)
    callback("contract-published")
    os.rename(scene_candidate, scene_destination)
    callback("scene-published")
    _atomic_json_write(marker_destination, marker_payload)
    callback("marker-published")


def _completion_marker_matches(
    scene_path: Path, contract_path: Path, marker_path: Path
) -> bool:
    if not (scene_path.is_file() and contract_path.is_file() and marker_path.is_file()):
        return False
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(marker, Mapping)
        and isinstance(contract, Mapping)
        and marker.get("schema") == PUBLICATION_SCHEMA
        and marker.get("scene_id") == contract.get("scene_id")
        and marker.get("transaction_id") == contract.get("publication", {}).get("transaction_id")
        and marker.get("scene_sha256") == sha256_file(scene_path)
        and marker.get("contract_sha256") == sha256_file(contract_path)
    )


def _recover_incomplete_publication(
    scene_path: Path,
    contract_path: Path,
    marker_path: Path,
    transaction_path: Path,
    rejected_root: Path,
) -> dict[str, object]:
    """Archive, never delete, any pair that lacks a matching marker-last commit."""

    if _completion_marker_matches(scene_path, contract_path, marker_path):
        return {"status": "complete", "paths": [str(scene_path), str(contract_path), str(marker_path)]}
    existing = [
        path for path in (scene_path, contract_path, marker_path, transaction_path)
        if path.exists()
    ]
    for authority_path in (marker_path, transaction_path):
        existing.extend(
            path for path in authority_path.parent.glob(f".{authority_path.name}.*.candidate")
            if path not in existing
        )
    if not existing:
        return {"status": "empty", "paths": []}
    revision = rejected_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ-incomplete-pair")
    revision.mkdir(parents=True, exist_ok=False)
    archived: list[str] = []
    for source in existing:
        destination = revision / source.name.lstrip(".")
        os.rename(source, destination)
        archived.append(str(destination))
    return {"status": "recovered_to_rejected", "paths": archived}


def _interpret_fresh_validation_process(completed: Any) -> list[str]:
    emitted = [
        line.removeprefix(VALIDATION_MARKER)
        for line in str(completed.stdout).splitlines()
        if line.startswith(VALIDATION_MARKER)
    ]
    if completed.returncode != 0:
        return [
            "fresh Blender validation process failed "
            f"(exit={completed.returncode}, stdout={str(completed.stdout).strip()}, "
            f"stderr={str(completed.stderr).strip()})"
        ]
    if len(emitted) != 1:
        return ["fresh Blender validation did not emit exactly one result"]
    try:
        result = json.loads(emitted[0])
    except json.JSONDecodeError as error:
        return [f"fresh Blender validation emitted invalid JSON: {error}"]
    return result if isinstance(result, list) and all(isinstance(item, str) for item in result) else ["fresh Blender validation result is invalid"]


def _run_fresh_editorial_validation(scene_path: Path, contract_path: Path) -> list[str]:
    """Reopen one candidate in a fresh Blender 5.2 process with this validator."""

    import bpy

    command = [
        str(Path(bpy.app.binary_path).resolve()), "--factory-startup", "-b", str(scene_path),
        "--python-exit-code", "1", "-P", str(Path(__file__).resolve()), "--",
        "--validate-scene", "--contract", str(contract_path.resolve()),
    ]
    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return _interpret_fresh_validation_process(completed)


def _author_and_publish(bpy: Any, shot: EditorialConceptShot) -> dict[str, object]:
    scene_destination = require_within(_scene_path(shot), ASSET_ROOT / "scenes" / SCENE_LIBRARY_ID)
    contract_destination = require_within(_contract_path(shot), ASSET_ROOT / "scenes" / "contracts" / SCENE_LIBRARY_ID)
    marker_destination = require_within(_completion_path(shot), ASSET_ROOT / "scenes" / "contracts" / SCENE_LIBRARY_ID)
    transaction_candidate = contract_destination.with_name(f".{contract_destination.stem}.transaction.json")
    recovery = _recover_incomplete_publication(
        scene_destination,
        contract_destination,
        marker_destination,
        transaction_candidate,
        ASSET_ROOT / "scenes" / "rejected" / EDITORIAL_CAMPAIGN_ID,
    )
    if recovery["status"] == "complete":
        return {
            "status": "blocked_existing_publication",
            "errors": ["completed editorial scene/contract publication is never replaced"],
            "scene_path": str(scene_destination),
            "contract_path": str(contract_destination),
            "completion_marker_path": str(marker_destination),
        }
    contract = prepare_editorial_contract(shot)
    protected_paths = [_master_path("30G"), _master_path("50G"), _material_path()]
    before = {str(path): sha256_file(path) for path in protected_paths}
    scene_destination.parent.mkdir(parents=True, exist_ok=True)
    contract_destination.parent.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    scene_candidate = scene_destination.with_name(f".{scene_destination.stem}.{nonce}.candidate.blend")
    contract_candidate = contract_destination.with_name(f".{contract_destination.stem}.{nonce}.candidate.json")
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.preferences.filepaths.use_relative_paths = False
        authoring = author_editorial_scene(bpy, shot, contract)
        contract_bytes = _contract_bytes(contract)
        with contract_candidate.open("xb") as stream:
            stream.write(contract_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        contract_candidate.chmod(stat.S_IREAD)
        bpy.ops.wm.save_as_mainfile(
            filepath=str(scene_candidate), check_existing=False, relative_remap=False
        )
        if not scene_candidate.is_file():
            raise RuntimeError("Blender did not save the editorial scene candidate")
        errors = _run_fresh_editorial_validation(scene_candidate, contract_candidate)
        after = {str(path): sha256_file(path) for path in protected_paths}
        if after != before:
            errors.append("scene authoring changed a protected master/material fingerprint")
        if sha256_file(contract_candidate) != _sha256_bytes(contract_bytes):
            errors.append("editorial contract candidate changed during fresh validation")
        if errors:
            rejected = _preserve_rejected((scene_candidate, contract_candidate), shot.shot_id)
            return {"status": "rejected", "errors": errors, "rejected_paths": rejected, "fingerprints_before": before, "fingerprints_after": after}
        if any(path.exists() for path in (scene_destination, contract_destination, marker_destination, transaction_candidate)):
            raise FileExistsError("editorial publication destination appeared during validation")
        scene_sha = sha256_file(scene_candidate)
        contract_sha = sha256_file(contract_candidate)
        transaction = {
            "schema": PUBLICATION_SCHEMA,
            "status": "staged",
            "scene_id": shot.shot_id,
            "transaction_id": contract["publication"]["transaction_id"],
            "scene_sha256": scene_sha,
            "contract_sha256": contract_sha,
        }
        _atomic_json_write(transaction_candidate, transaction)
        marker = dict(transaction)
        marker["status"] = "complete"
        _commit_publication_pair(
            scene_candidate=scene_candidate,
            contract_candidate=contract_candidate,
            transaction_candidate=transaction_candidate,
            scene_destination=scene_destination,
            contract_destination=contract_destination,
            marker_destination=marker_destination,
            marker_payload=marker,
        )
        final_errors = _run_fresh_editorial_validation(scene_destination, contract_destination)
        if final_errors:
            rejected = _preserve_rejected(
                (scene_destination, contract_destination, marker_destination, transaction_candidate),
                shot.shot_id,
            )
            return {
                "status": "rejected",
                "errors": final_errors,
                "rejected_paths": rejected,
                "fingerprints_before": before,
                "fingerprints_after": after,
            }
        return {
            "status": "published_preview_scene",
            "errors": [],
            "scene_path": str(scene_destination),
            "scene_sha256": sha256_file(scene_destination),
            "contract_path": str(contract_destination),
            "contract_sha256": contract_sha,
            "completion_marker_path": str(marker_destination),
            "completion_marker_sha256": sha256_file(marker_destination),
            "publication_transaction_id": contract["publication"]["transaction_id"],
            "fresh_validation": True,
            "authoring": authoring,
            "fingerprints_before": before,
            "fingerprints_after": after,
        }
    except Exception as error:
        rejected_sources = [
            path for path in (
                scene_candidate, contract_candidate, transaction_candidate,
                scene_destination, contract_destination, marker_destination,
            ) if path.exists()
        ]
        rejected = _preserve_rejected(rejected_sources, shot.shot_id)
        return {"status": "rejected", "errors": [str(error)], "rejected_paths": rejected, "fingerprints_before": before, "fingerprints_after": {str(path): sha256_file(path) for path in protected_paths}}


def _load_contract(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("editorial contract root must be an object")
    return payload


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-contract", action="store_true")
    mode.add_argument("--author-scene", action="store_true")
    mode.add_argument("--validate-scene", action="store_true")
    parser.add_argument("--shot-id")
    parser.add_argument("--contract", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else sys.argv[1:]
    )
    if arguments.prepare_contract:
        if not arguments.shot_id:
            raise ValueError("--prepare-contract requires --shot-id")
        shot = _CAMPAIGN.by_shot_id.get(arguments.shot_id)
        if shot is None:
            raise ValueError(f"unknown editorial shot: {arguments.shot_id}")
        contract = prepare_editorial_contract(shot)
        result = {"status": "contract_prepared_not_published", "contract": contract, "contract_sha256": _sha256_bytes(_contract_bytes(contract))}
        print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
        return 0
    if arguments.author_scene:
        if not arguments.shot_id:
            raise ValueError("--author-scene requires --shot-id")
        shot = _CAMPAIGN.by_shot_id.get(arguments.shot_id)
        if shot is None:
            raise ValueError(f"unknown editorial shot: {arguments.shot_id}")
        import bpy
        result = _author_and_publish(bpy, shot)
        print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
        return 0 if result.get("status") == "published_preview_scene" else 1
    if arguments.contract is None:
        raise ValueError("--validate-scene requires --contract")
    contract = _load_contract(arguments.contract)
    import bpy
    errors = validate_open_editorial_scene(bpy, contract)
    print(VALIDATION_MARKER + json.dumps(errors, sort_keys=True), flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
