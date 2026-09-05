"""Strict, read-only controller and animation contracts for PIMM masters."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
import json
from pathlib import Path
import re
import sys
from typing import Any, Literal

try:
    from .io_contract import atomic_write_json, sha256_file
    from .paths import ASSET_ROOT, require_within
except ImportError:  # Blender executes checked-in scripts as __main__.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within

from scripts.blender.master_assets.pimm_material_library import MATERIAL_SPECS


MachineName = Literal["30G", "50G"]
_MACHINE_VALUES: dict[str, list[str]] = {"30G": ["300", "300"], "50G": ["350", "350"]}
_CONTRACT_ROOT = Path(__file__).resolve().parent / "contracts" / "machines"
_CANDIDATE_ROOT = ASSET_ROOT / "manifests" / "machine-contract-candidates"
_CONTROLLER_TERMS = ("controller", "display", "segment", "rex-c100", "process value", "set value")
_BASE_CONTROLLER_KEYS = {
    "display_values",
    "geometry_mode",
    "allow_font",
    "allow_image_overlay",
    "inactive_segments_required",
}
_SEGMENT_KEYS = {"stable_object_id", "material_id", "object_type", "active"}
_CONTROL_KEYS = {
    "stable_object_id",
    "human_part_name",
    "control_id",
    "transform_channel",
    "axis",
    "minimum",
    "maximum",
    "neutral",
    "start",
    "operating",
    "final",
    "hose_cable_dependency",
    "collision_note",
}
_TRANSFORM_CHANNELS = {"location", "rotation_euler", "scale"}
_AXIS_INDICES = {"X": 0, "Y": 1, "Z": 2}
_MATERIAL_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SHARED_MATERIAL_ROLE_ALIASES = frozenset(
    {
        *(material_id.casefold() for material_id in MATERIAL_SPECS),
        *(f"PIMM_{material_id}".casefold() for material_id in MATERIAL_SPECS),
    }
)


def load_machine_contract(machine: MachineName) -> dict[str, object]:
    """Load one checked-in machine contract after checking its declared identity."""

    if machine not in _MACHINE_VALUES:
        raise ValueError(f"unsupported machine contract: {machine}")
    path = _CONTRACT_ROOT / f"{machine.lower()}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"machine contract is not an object: {path}")
    errors = validate_machine_contract(payload)
    if errors:
        raise ValueError(f"invalid machine contract {path}: {'; '.join(errors)}")
    return payload


def _mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_approved_segments(controller: Mapping[str, object]) -> list[str]:
    segments = controller.get("approved_segments")
    if segments is None:
        return []
    if not isinstance(segments, list) or not segments:
        return ["controller approved_segments must be a nonempty list when present"]

    allowlist = controller.get("approved_machine_local_material_ids")
    approved_material_ids = {
        material_id for material_id in allowlist if _is_nonempty_string(material_id)
    } if isinstance(allowlist, list) else set()
    errors: list[str] = []
    stable_ids: set[str] = set()
    active_count = 0
    inactive_count = 0
    for index, segment in enumerate(segments):
        entry = _mapping(segment)
        if entry is None or set(entry) != _SEGMENT_KEYS:
            errors.append(
                f"controller approved_segments[{index}] must contain stable_object_id, material_id, object_type, and active"
            )
            continue
        stable_id = entry["stable_object_id"]
        if not _is_nonempty_string(stable_id):
            errors.append(f"controller approved_segments[{index}] stable_object_id must be a nonempty string")
        elif stable_id in stable_ids:
            errors.append(f"controller approved_segments[{index}] duplicates stable_object_id: {stable_id}")
        else:
            stable_ids.add(stable_id)
        material_id = entry["material_id"]
        if not _is_nonempty_string(material_id):
            errors.append(f"controller approved_segments[{index}] material_id must be a nonempty string")
        elif material_id.casefold().removeprefix("pimm_") == "unassigned":
            errors.append(f"controller approved_segments[{index}] material_id cannot be UNASSIGNED")
        elif isinstance(allowlist, list) and material_id not in approved_material_ids:
            errors.append(
                f"controller approved_segments[{index}] material_id is not in approved_machine_local_material_ids"
            )
        if entry["object_type"] != "MESH":
            errors.append(f"controller approved_segments[{index}] object_type must be MESH")
        if not isinstance(entry["active"], bool):
            errors.append(f"controller approved_segments[{index}] active must be boolean")
        elif entry["object_type"] == "MESH":
            if entry["active"]:
                active_count += 1
            else:
                inactive_count += 1
    if active_count == 0:
        errors.append("approved controller segment map requires at least one active segment")
    if controller.get("inactive_segments_required") is True and inactive_count == 0:
        errors.append("approved controller segment map requires at least one inactive segment")
    return errors


def _validate_material_allowlist(controller: Mapping[str, object]) -> list[str]:
    allowlist = controller.get("approved_machine_local_material_ids")
    if allowlist is None:
        return []
    if not isinstance(allowlist, list) or not allowlist:
        return ["controller approved_machine_local_material_ids must be a nonempty list when present"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, material_id in enumerate(allowlist):
        if not _is_nonempty_string(material_id):
            errors.append(f"controller approved_machine_local_material_ids[{index}] must be a nonempty string")
            continue
        normalized = material_id.casefold()
        if material_id != material_id.strip() or _MATERIAL_ID.fullmatch(material_id) is None:
            errors.append(
                f"controller approved_machine_local_material_ids[{index}] must be one canonical uppercase material ID"
            )
        if normalized.removeprefix("pimm_") == "unassigned":
            errors.append(f"controller approved_machine_local_material_ids[{index}] cannot be UNASSIGNED")
        elif normalized in _SHARED_MATERIAL_ROLE_ALIASES:
            errors.append(
                f"controller approved_machine_local_material_ids[{index}] overlaps the shared material catalog: {material_id}"
            )
        if normalized in seen:
            errors.append(f"controller approved_machine_local_material_ids[{index}] is duplicated: {material_id}")
        else:
            seen.add(normalized)
    return errors


def _validate_control_map(controls: list[object]) -> list[str]:
    errors: list[str] = []
    for index, control in enumerate(controls):
        entry = _mapping(control)
        if entry is None or set(entry) != _CONTROL_KEYS:
            errors.append(f"allowed_controls[{index}] must contain the complete owner approval record")
            continue
        for key in (
            "stable_object_id",
            "human_part_name",
            "control_id",
            "hose_cable_dependency",
            "collision_note",
        ):
            if not _is_nonempty_string(entry[key]):
                errors.append(f"allowed_controls[{index}] {key} must be a nonempty string")
        if entry["transform_channel"] not in _TRANSFORM_CHANNELS:
            errors.append(f"allowed_controls[{index}] transform_channel must be location, rotation_euler, or scale")
        if entry["axis"] not in _AXIS_INDICES:
            errors.append(f"allowed_controls[{index}] axis must be X, Y, or Z")
        values = [entry[key] for key in ("minimum", "maximum", "neutral", "start", "operating", "final")]
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            errors.append(f"allowed_controls[{index}] limits and poses must be numbers")
            continue
        minimum, maximum, neutral, start, operating, final = values
        if minimum > maximum:
            errors.append(f"allowed_controls[{index}] minimum cannot exceed maximum")
        for name, value in (("neutral", neutral), ("start", start), ("operating", operating), ("final", final)):
            if value < minimum or value > maximum:
                errors.append(f"allowed_controls[{index}] {name} must be within minimum and maximum")
    return errors


def validate_machine_contract(payload: Mapping[str, object]) -> list[str]:
    """Return semantic errors; accepted payloads are safe, exact machine contracts."""

    errors: list[str] = []
    if set(payload) != {"schema_version", "machine", "controller", "animation"}:
        errors.append("machine contract must contain exactly schema_version, machine, controller, and animation")
        return errors
    if payload["schema_version"] != 1:
        errors.append("machine contract schema_version must be 1")
    machine = payload["machine"]
    if machine not in _MACHINE_VALUES:
        errors.append("machine contract machine must be 30G or 50G")
    controller = _mapping(payload["controller"])
    if controller is None:
        errors.append("machine contract controller must be an object")
        return errors
    controller_keys = set(controller)
    optional_controller_keys = {"approved_segments", "approved_machine_local_material_ids"}
    if not _BASE_CONTROLLER_KEYS.issubset(controller_keys) or controller_keys - (_BASE_CONTROLLER_KEYS | optional_controller_keys):
        errors.append(
            "controller must contain only the required physical display fields and optional approved_segments or approved_machine_local_material_ids"
        )
        return errors
    if machine in _MACHINE_VALUES and controller.get("display_values") != _MACHINE_VALUES[machine]:
        errors.append(f"{machine} controller display_values must be {_MACHINE_VALUES[machine]!r}")
    if controller.get("geometry_mode") != "physical-seven-segment-mesh":
        errors.append("controller geometry_mode must be physical-seven-segment-mesh")
    if controller.get("allow_font") is not False:
        errors.append("controller allow_font must be false")
    if controller.get("allow_image_overlay") is not False:
        errors.append("controller allow_image_overlay must be false")
    if controller.get("inactive_segments_required") is not True:
        errors.append("controller inactive_segments_required must be true")
    errors.extend(_validate_material_allowlist(controller))
    errors.extend(_validate_approved_segments(controller))

    animation = _mapping(payload["animation"])
    if animation is None or set(animation) != {"status", "allowed_controls"}:
        errors.append("animation must contain exactly status and allowed_controls")
        return errors
    status = animation["status"]
    controls = animation["allowed_controls"]
    if status not in {"blocked_pending_owner_motion_map", "enabled_owner_approved"}:
        errors.append("animation status must be blocked_pending_owner_motion_map or enabled_owner_approved")
    if not isinstance(controls, list):
        errors.append("animation allowed_controls must be a list")
    elif status == "blocked_pending_owner_motion_map" and controls:
        errors.append("blocked_pending_owner_motion_map animation must have an empty allowed_controls map")
    elif status == "enabled_owner_approved" and not controls:
        errors.append("enabled_owner_approved animation requires a nonempty allowed_controls map")
    elif status == "enabled_owner_approved":
        if not isinstance(controller.get("approved_segments"), list) or not controller["approved_segments"]:
            errors.append("enabled_owner_approved animation requires a nonempty controller approved_segments map")
        if not isinstance(controller.get("approved_machine_local_material_ids"), list) or not controller[
            "approved_machine_local_material_ids"
        ]:
            errors.append(
                "enabled_owner_approved animation requires a nonempty controller approved_machine_local_material_ids allowlist"
            )
        errors.extend(_validate_control_map(controls))
    return errors


def animation_is_authorized(payload: Mapping[str, object]) -> bool:
    """Return true only for a valid, explicitly owner-approved control map."""

    animation = _mapping(payload.get("animation"))
    return (
        not validate_machine_contract(payload)
        and animation is not None
        and animation.get("status") == "enabled_owner_approved"
        and bool(animation.get("allowed_controls"))
    )


def _property(object_value: object, names: Sequence[str]) -> object | None:
    getter = getattr(object_value, "get", None)
    for name in names:
        if callable(getter):
            value = getter(name, None)
            if value is not None:
                return value
        value = getattr(object_value, name, None)
        if value is not None:
            return value
    return None


def _candidate_text(object_value: object) -> str:
    assembly_path = _assembly_path(object_value)
    return " ".join(
        str(value)
        for value in (
            getattr(object_value, "name", ""),
            _property(
                object_value,
                ("pimm_original_cad_name", "pimm_cad_name", "cad_name", "original_name"),
            ),
            *assembly_path,
        )
        if value
    ).casefold()


def _is_controller_candidate(object_value: object) -> bool:
    return any(term in _candidate_text(object_value) for term in _CONTROLLER_TERMS)


def _material_ids(object_value: object) -> list[str]:
    identifiers: list[str] = []
    for slot in getattr(object_value, "material_slots", ()):
        material = getattr(slot, "material", None)
        getter = getattr(material, "get", None)
        identifier = getter("pimm_material_id", None) if callable(getter) else None
        if (
            isinstance(identifier, str)
            and identifier == identifier.strip()
            and _MATERIAL_ID.fullmatch(identifier) is not None
        ):
            identifiers.append(identifier)
    return sorted(set(identifiers))


def _bounds(object_value: object) -> list[float]:
    vertices = getattr(object_value, "bound_box", ())
    if not vertices:
        return []
    try:
        coordinates = [[float(value) for value in vertex] for vertex in vertices]
    except (TypeError, ValueError):
        return []
    if not coordinates or any(len(vertex) != 3 for vertex in coordinates):
        return []
    return [
        min(vertex[0] for vertex in coordinates),
        min(vertex[1] for vertex in coordinates),
        min(vertex[2] for vertex in coordinates),
        max(vertex[0] for vertex in coordinates),
        max(vertex[1] for vertex in coordinates),
        max(vertex[2] for vertex in coordinates),
    ]


def _collection_path(object_value: object) -> list[str]:
    stored = _property(object_value, ("pimm_collection_path", "collection_path"))
    if stored and isinstance(stored, (list, tuple)) and all(_is_nonempty_string(value) for value in stored):
        return list(stored)
    assembly_path = _assembly_path(object_value)
    if assembly_path:
        return assembly_path
    return sorted(
        collection.name
        for collection in getattr(object_value, "users_collection", ())
        if _is_nonempty_string(getattr(collection, "name", None))
    )


def _assembly_path(object_value: object) -> list[str]:
    value = _property(object_value, ("pimm_assembly_path",))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, (list, tuple)) and all(_is_nonempty_string(item) for item in value):
        return list(value)
    return []


def discover_controller_candidates(objects: Iterable[object]) -> list[dict[str, object]]:
    """Read candidate controller objects without assigning, selecting, or changing them."""

    candidates: list[dict[str, object]] = []
    for object_value in objects:
        if not _is_controller_candidate(object_value):
            continue
        stable_id = _property(object_value, ("pimm_stable_id", "stable_object_id", "stable_id"))
        cad_name = _property(
            object_value,
            ("pimm_original_cad_name", "pimm_cad_name", "cad_name", "original_name"),
        )
        candidates.append(
            {
                "stable_object_id": stable_id if _is_nonempty_string(stable_id) else None,
                "cad_name": cad_name if _is_nonempty_string(cad_name) else None,
                "object_name": str(getattr(object_value, "name", "")),
                "object_type": str(getattr(object_value, "type", "")),
                "material_ids": _material_ids(object_value),
                "bounds": _bounds(object_value),
                "collection_path": _collection_path(object_value),
            }
        )
    return sorted(candidates, key=lambda candidate: (str(candidate["stable_object_id"]), str(candidate["object_name"])))


def _animated(object_value: object) -> bool:
    return getattr(object_value, "animation_data", None) is not None


def _keyframes(fcurve: object) -> list[tuple[float, float]] | None:
    try:
        return [
            (float(point.co[0]), float(point.co[1]))
            for point in getattr(fcurve, "keyframe_points", ())
        ]
    except (AttributeError, IndexError, TypeError, ValueError):
        return None


def _validate_control_animation(object_value: object, control: Mapping[str, object]) -> list[str]:
    """Validate every actual F-curve against one owner-approved transform record."""

    name = str(getattr(object_value, "name", ""))
    animation_data = getattr(object_value, "animation_data", None)
    action = getattr(animation_data, "action", None)
    fcurves = list(getattr(action, "fcurves", ()) if action is not None else ())
    drivers = list(getattr(animation_data, "drivers", ()) if animation_data is not None else ())
    errors: list[str] = []
    if drivers:
        errors.append(f"approved animation has drivers outside the owner-approved F-curve record: {name}")
    if not fcurves:
        errors.append(f"approved animation requires one F-curve: {name}")
        return errors

    expected_channel = control["transform_channel"]
    expected_axis = _AXIS_INDICES[control["axis"]]
    matching_curves: list[object] = []
    for fcurve in fcurves:
        if getattr(fcurve, "data_path", None) != expected_channel:
            errors.append(f"approved animation has unexpected transform channel: {name}")
        elif getattr(fcurve, "array_index", None) != expected_axis:
            errors.append(f"approved animation axis mismatch: {name}")
        else:
            matching_curves.append(fcurve)
    if len(fcurves) != 1 or len(matching_curves) != 1:
        if not errors:
            errors.append(f"approved animation must contain exactly one approved transform channel: {name}")
        return errors

    keyframes = _keyframes(matching_curves[0])
    if keyframes is None or len(keyframes) != 3:
        return [*errors, f"approved animation must contain start/operating/final keys: {name}"]
    frames = [frame for frame, _ in keyframes]
    values = [value for _, value in keyframes]
    if frames != sorted(frames) or len(set(frames)) != len(frames):
        errors.append(f"approved animation key frames are not in start/operating/final order: {name}")
    minimum = control["minimum"]
    maximum = control["maximum"]
    if any(value < minimum or value > maximum for value in values):
        errors.append(f"approved animation key value is outside limits: {name}")
    expected_values = [control["start"], control["operating"], control["final"]]
    if values != expected_values:
        errors.append(f"approved animation key poses do not match start/operating/final: {name}")
    return errors


def validate_controller_scene(bpy: Any, contract: Mapping[str, object]) -> list[str]:
    """Read a scene for forbidden animation/display substitutions and approved mappings."""

    errors = validate_machine_contract(contract)
    if errors:
        return errors
    objects = list(bpy.data.objects)
    animation = _mapping(contract["animation"])
    allowed_controls = animation["allowed_controls"] if animation else []
    controls_by_stable_id = {
        control["stable_object_id"]: control
        for control in allowed_controls
        if isinstance(control, Mapping) and _is_nonempty_string(control.get("stable_object_id"))
    }
    for object_value in objects:
        if _animated(object_value):
            name = getattr(object_value, "name", "")
            stable_id = _property(object_value, ("pimm_stable_id", "stable_object_id", "stable_id"))
            if not controls_by_stable_id:
                errors.append(f"animation is blocked but scene object is animated: {name}")
            elif stable_id not in controls_by_stable_id:
                errors.append(f"animated scene object is not owner-approved: {name}")
            else:
                errors.extend(_validate_control_animation(object_value, controls_by_stable_id[stable_id]))
    candidates = discover_controller_candidates(objects)
    for candidate in candidates:
        if candidate["object_type"] == "EMPTY" and getattr(
            next(obj for obj in objects if getattr(obj, "name", "") == candidate["object_name"]),
            "empty_display_type",
            None,
        ) == "IMAGE":
            errors.append(f"controller/display candidate cannot be an image overlay: {candidate['object_name']}")
        elif candidate["object_type"] != "MESH":
            errors.append(f"controller/display candidate must be a physical MESH: {candidate['object_name']}")

    controller = _mapping(contract["controller"])
    approved_segments = controller.get("approved_segments") if controller else None
    if not isinstance(approved_segments, list):
        return errors
    by_stable_id = {candidate["stable_object_id"]: candidate for candidate in candidates}
    for segment in approved_segments:
        entry = _mapping(segment)
        if entry is None:
            continue
        stable_id = entry["stable_object_id"]
        candidate = by_stable_id.get(stable_id)
        if candidate is None:
            errors.append(f"approved controller segment is missing from scene: {stable_id}")
            continue
        if candidate["object_type"] != "MESH":
            errors.append(f"approved controller segment must be a MESH: {stable_id}")
        if entry["material_id"] not in candidate["material_ids"]:
            errors.append(f"approved controller segment material mismatch: {stable_id}")
    return errors


def write_candidate_report(bpy: Any, machine: MachineName, report_path: Path) -> dict[str, object]:
    """Atomically write a read-only candidate report beneath the approved manifest root."""

    contract = load_machine_contract(machine)
    if contract["machine"] != machine:
        raise ValueError(f"contract identity mismatch for {machine}")
    destination = require_within(report_path, _CANDIDATE_ROOT)
    if destination.suffix.lower() != ".json":
        raise ValueError("candidate report must be a JSON file")
    master_path = Path(bpy.data.filepath)
    if not master_path.is_file():
        raise ValueError(f"opened Blender file is not a master file: {master_path}")
    dirty_before = bool(bpy.data.is_dirty)
    before_hash = sha256_file(master_path)
    candidates = discover_controller_candidates(bpy.data.objects)
    after_hash = sha256_file(master_path)
    if before_hash != after_hash:
        raise RuntimeError("read-only candidate discovery changed the master fingerprint")
    report = {
        "schema": "pimm-machine-controller-candidates/v1",
        "machine": machine,
        "master": {
            "path": str(master_path),
            "sha256_before": before_hash,
            "sha256_after": after_hash,
            "dirty_before": dirty_before,
            "dirty_after": bool(bpy.data.is_dirty),
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
        "owner_approval_required": True,
        "animation_status": contract["animation"]["status"],
        "allowed_controls": contract["animation"]["allowed_controls"],
    }
    atomic_write_json(destination, report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Run only under background Blender to emit one candidate report."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", choices=sorted(_MACHINE_VALUES), required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args(argv)
    import bpy

    report = write_candidate_report(bpy, arguments.machine, arguments.report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
