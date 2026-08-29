"""Read-only Blender validation for linked PIMM render-scene ownership."""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Mapping, Sequence

try:
    from .campaign_contract import CAMPAIGN_ID, load_campaign, shot_policy, validate_campaign
    from .blender_static_product_scene import (
        CameraPose,
        FootContactPlane,
        SHOT_CONFIGS,
        ShotConfig,
        TargetResolution,
        camera_pose,
        composition_evidence,
        foot_contact_evidence,
        frame_coordinates,
        load_target_manifest,
        load_foot_contact_planes,
        resolve_target_bounds,
    )
    from .blender_scene_template import comparison_link_plan
    from .external_asset_manifest import validate_external_assets
    from .io_contract import sha256_file
    from .machine_contract import load_machine_contract, validate_controller_scene
    from .paths import ASSET_ROOT, require_within
    from .published_artwork import ARTWORK_SPECS_BY_MACHINE, validate_published_artwork
    from .scene_contract import (
        PUBLISHED_STABLE_ID_COUNT_PROPERTY,
        PUBLISHED_STABLE_ID_SHA256_PROPERTY,
        SceneContract,
        canonical_scene_contract_json,
        stable_id_evidence,
        validate_scene_contract,
    )
    from .shot_compositions import (
        CAMPAIGN_PATH,
        MANAGED_REFLECTION_CARD_NAMES,
        composition_for,
        validate_workshop_support_assets,
    )
except ImportError:  # Blender may execute this checked-in script directly.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production.campaign_contract import (
        CAMPAIGN_ID,
        load_campaign,
        shot_policy,
        validate_campaign,
    )
    from scripts.blender.pimm_production.blender_static_product_scene import (
        CameraPose,
        FootContactPlane,
        SHOT_CONFIGS,
        ShotConfig,
        TargetResolution,
        camera_pose,
        composition_evidence,
        foot_contact_evidence,
        frame_coordinates,
        load_target_manifest,
        load_foot_contact_planes,
        resolve_target_bounds,
    )
    from scripts.blender.pimm_production.blender_scene_template import (
        comparison_link_plan,
    )
    from scripts.blender.pimm_production.external_asset_manifest import (
        validate_external_assets,
    )
    from scripts.blender.pimm_production.io_contract import sha256_file
    from scripts.blender.pimm_production.machine_contract import (
        load_machine_contract,
        validate_controller_scene,
    )
    from scripts.blender.pimm_production.shot_compositions import (
        CAMPAIGN_PATH,
        MANAGED_REFLECTION_CARD_NAMES,
        composition_for,
        validate_workshop_support_assets,
    )
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
    from scripts.blender.pimm_production.published_artwork import (
        ARTWORK_SPECS_BY_MACHINE,
        validate_published_artwork,
    )
    from scripts.blender.pimm_production.scene_contract import (
        PUBLISHED_STABLE_ID_COUNT_PROPERTY,
        PUBLISHED_STABLE_ID_SHA256_PROPERTY,
        SceneContract,
        canonical_scene_contract_json,
        stable_id_evidence,
        validate_scene_contract,
    )

from scripts.blender.master_assets.pimm_material_library import MATERIAL_SPECS


VALIDATION_MARKER = "PIMM_SCENE_VALIDATION_JSON="
_MATERIAL_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
_APPROVED_SHARED_MATERIAL_IDS = frozenset(MATERIAL_SPECS) - {"UNASSIGNED"}


def _library_path(bpy: Any, library: object | None) -> Path | None:
    lexical = _library_lexical_path(bpy, library)
    return lexical.resolve() if lexical is not None else None


def _library_lexical_path(
    bpy: Any,
    library: object | None,
) -> Path | None:
    if library is None:
        return None
    filepath = str(getattr(library, "filepath", ""))
    if not filepath:
        return None
    if filepath.startswith("//"):
        abspath = getattr(getattr(bpy, "path", None), "abspath", None)
        if callable(abspath):
            return Path(os.path.abspath(str(abspath(filepath))))
        scene_path = Path(os.path.abspath(str(getattr(bpy.data, "filepath", ""))))
        return Path(os.path.abspath(scene_path.parent / filepath[2:]))
    return Path(os.path.abspath(filepath))


def _library_authority_record(bpy: Any, library: object) -> dict[str, object]:
    """Capture Blender's raw/lexical library spelling and its canonical target."""

    raw = str(getattr(library, "filepath", ""))
    lexical = _library_lexical_path(bpy, library)
    if not raw or lexical is None:
        raise ValueError("linked Blender library filepath is empty")
    try:
        canonical = lexical.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"linked Blender library target is unreadable: {lexical}") from error
    parent = getattr(library, "parent", None)
    parent_canonical = _library_path(bpy, parent)
    return {
        "raw_filepath": raw,
        "lexical_path": str(lexical),
        "canonical_path": str(canonical),
        "parent_canonical_path": (
            str(parent_canonical) if parent_canonical is not None else None
        ),
    }


def _datablock_library_path(bpy: Any, datablock: object | None) -> Path | None:
    return _library_path(bpy, getattr(datablock, "library", None))


def _property(datablock: object, name: str, default: object = None) -> object:
    getter = getattr(datablock, "get", None)
    return getter(name, default) if callable(getter) else default


def _reachable_collections(scene: object) -> set[object]:
    reachable: set[object] = set()
    stack = list(getattr(getattr(scene, "collection", None), "children", ()))
    stack.extend(
        collection
        for obj in getattr(scene, "objects", ())
        for collection in (getattr(obj, "instance_collection", None),)
        if collection is not None
    )
    while stack:
        collection = stack.pop()
        if collection in reachable:
            continue
        reachable.add(collection)
        stack.extend(getattr(collection, "children", ()))
    return reachable


def _master_authorities(contract: SceneContract) -> dict[str, Path]:
    machines = contract.machines or ((contract.machine,) if contract.machine else ())
    return {
        machine: (ASSET_ROOT / "masters" / f"PIMM-{machine}-MASTER.blend").resolve()
        for machine in machines
    }


def _combined_master_sha256(authorities: Mapping[str, Path]) -> str:
    rows = [f"{machine}:{sha256_file(path)}" for machine, path in authorities.items()]
    return hashlib.sha256(("\n".join(rows) + "\n").encode("ascii")).hexdigest().upper()


def _external_asset_provenance(
    asset_root: Path | None = None,
) -> tuple[dict[str, Mapping[str, object]], list[str]]:
    asset_root = ASSET_ROOT if asset_root is None else asset_root
    path = asset_root / "manifests" / "external-assets-v1.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, [f"external asset manifest cannot be read: {path}: {error}"]
    campaign = load_campaign(CAMPAIGN_PATH)
    errors = validate_external_assets(payload, set(campaign.by_shot_id))
    assets = payload.get("assets", ()) if isinstance(payload, Mapping) else ()
    provenance: dict[str, Mapping[str, object]] = {}
    for record in assets:
        if not isinstance(record, Mapping) or not isinstance(
            record.get("asset_version_id"), str
        ):
            continue
        asset_id = str(record["asset_version_id"])
        if asset_id in provenance:
            errors.append(f"external asset_version_id must be unique: {asset_id}")
            continue
        provenance[asset_id] = record
        relative = record.get("local_relative_path")
        expected_sha256 = record.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_sha256, str):
            continue
        try:
            local_path = require_within(asset_root / relative, asset_root / "assets")
        except ValueError as error:
            errors.append(f"external asset path is invalid: {asset_id}: {error}")
            continue
        if not local_path.is_file():
            errors.append(f"external asset is missing: {asset_id}: {local_path}")
            continue
        actual_sha256 = sha256_file(local_path)
        if actual_sha256 != expected_sha256.upper():
            errors.append(
                f"external asset SHA-256 mismatch: {asset_id}: "
                f"expected {expected_sha256.upper()}, found {actual_sha256}"
            )
    return provenance, errors


def _validate_workshop_runtime_state(
    scene: object,
    shot_id: str,
    workshop_support_records: Sequence[Mapping[str, object]],
    asset_root: Path | None = None,
) -> list[str]:
    """Bind every reopened workshop prop to the exact current provenance set."""

    asset_root = ASSET_ROOT if asset_root is None else asset_root
    provenance, errors = _external_asset_provenance(asset_root)
    errors.extend(
        validate_workshop_support_assets(
            composition_for(shot_id),
            workshop_support_records,
            provenance,
        )
    )
    expected_evidence = json.dumps(
        [
            {
                "asset_version_id": asset_id,
                "local_relative_path": record["local_relative_path"],
                "sha256": str(record["sha256"]).upper(),
            }
            for asset_id, record in provenance.items()
            if shot_id in record.get("intended_shot_ids", ())
        ],
        separators=(",", ":"),
        sort_keys=True,
    )
    if _property(scene, "pimm_workshop_support_evidence") != expected_evidence:
        errors.append(
            "workshop scene evidence must equal the exact expected provenance asset set"
        )
    return errors


def _validate_complete_product(
    published: object | None, contract: SceneContract
) -> list[str]:
    if published is None:
        return []
    errors: list[str] = []
    published_meshes = [
        obj
        for obj in getattr(published, "all_objects", ())
        if getattr(obj, "type", None) == "MESH"
    ]
    identifier_rows: list[str] = []
    artwork_names = {
        spec.object_name for spec in ARTWORK_SPECS_BY_MACHINE[contract.machine]
    }
    missing_provenance: list[str] = []
    for product in published_meshes:
        stable_id = _property(product, "pimm_stable_id")
        if (not isinstance(stable_id, str) or not stable_id) and str(
            getattr(product, "name", "")
        ) not in artwork_names:
            missing_provenance.append(str(getattr(product, "name", "")))
        elif isinstance(stable_id, str) and stable_id:
            identifier_rows.append(stable_id)
    actual_ids = set(identifier_rows)
    if missing_provenance:
        errors.append(
            "PIMM_PUBLISHED contains MESH objects without stable provenance: "
            + ", ".join(sorted(missing_provenance))
        )
    if len(identifier_rows) != len(actual_ids):
        errors.append("PIMM_PUBLISHED contains duplicate stable IDs")
    expected_count = _property(published, PUBLISHED_STABLE_ID_COUNT_PROPERTY)
    expected_sha256 = _property(published, PUBLISHED_STABLE_ID_SHA256_PROPERTY)
    if (
        not isinstance(expected_count, int)
        or isinstance(expected_count, bool)
        or expected_count <= 0
        or not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(character not in "0123456789ABCDEF" for character in expected_sha256)
    ):
        errors.append(
            "PIMM_PUBLISHED embedded stable-ID evidence is absent or invalid"
        )
        return errors
    actual_count, actual_sha256 = stable_id_evidence(actual_ids)
    if actual_count != expected_count or actual_sha256 != expected_sha256:
        errors.append(
            "PIMM_PUBLISHED does not match embedded stable-ID evidence "
            f"(expected_count={expected_count}, actual_count={actual_count}, "
            f"expected_sha256={expected_sha256}, actual_sha256={actual_sha256})"
        )
    _, artwork_errors = validate_published_artwork(published, contract.machine)
    errors.extend(artwork_errors)
    return errors


def _validate_materials(
    bpy: Any,
    product: object,
    expected_master: Path,
    expected_material_library: Path,
    material_registry: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    name = str(getattr(product, "name", ""))
    if getattr(product, "override_library", None) is not None or _property(
        product, "pimm_product_material_override"
    ) is True:
        errors.append(f"approved product material override is forbidden: {name}")
    materials = [
        material
        for material in (
            getattr(slot, "material", None)
            for slot in getattr(product, "material_slots", ())
        )
        if material is not None
    ]
    if not materials:
        errors.append(f"approved product has no exact material datablock: {name}")
    for material in materials:
        scope = _property(material, "pimm_material_scope", "unknown")
        origin = _datablock_library_path(bpy, material)
        material_name = str(getattr(material, "name", ""))
        material_id = _property(material, "pimm_material_id")
        if (
            not isinstance(material_id, str)
            or material_id != material_id.strip()
            or _MATERIAL_ID.fullmatch(material_id) is None
            or material_id == "UNASSIGNED"
        ):
            errors.append(
                f"product material requires exact pimm_material_id: {name}/{material_name}"
            )
        else:
            prior = material_registry.setdefault(material_id, material)
            if prior is not material:
                errors.append(
                    f"pimm_material_id must identify one exact material datablock: {material_id}"
                )
            if scope == "shared" and material_name != f"PIMM_{material_id}":
                errors.append(
                    f"shared material name/pimm_material_id mismatch: {name}/{material_name}"
                )
            if (
                scope == "shared"
                and material_id not in _APPROVED_SHARED_MATERIAL_IDS
            ):
                errors.append(
                    f"shared pimm_material_id is outside the canonical material catalog: "
                    f"{name}/{material_id}"
                )
        if scope == "shared" and origin != expected_material_library:
            errors.append(
                f"linked product material made local or resolved outside material library: {name}/{material_name} origin={origin}"
            )
        elif scope == "machine-local" and origin != expected_master:
            errors.append(
                f"machine-local product material did not resolve through master: {name}/{material_name}"
            )
        elif scope not in {"shared", "machine-local"}:
            errors.append(f"product material scope is not approved: {name}/{material_name}")
    return errors


def _validate_static_camera_clip_range(
    camera: Any, contract: SceneContract, errors: list[str]
) -> None:
    """Require the open camera to retain the clip range pinned by a static contract."""

    setup = contract.static_render_setup
    if setup is None:
        return
    camera_setup = setup.get("camera")
    if not isinstance(camera_setup, Mapping):
        return
    camera_data = getattr(camera, "data", None)
    if camera_data is None:
        return
    if getattr(camera_data, "clip_start", None) != camera_setup.get("clip_start"):
        errors.append("static product camera near clip does not match contract")
    if getattr(camera_data, "clip_end", None) != camera_setup.get("clip_end"):
        errors.append("static product camera far clip does not match contract")


def _numeric_triplet(value: object) -> tuple[float, float, float] | None:
    try:
        values = tuple(float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if len(values) != 3 or not all(math.isfinite(item) for item in values):
        return None
    return values


def _close_triplet(
    actual: tuple[float, float, float],
    expected: tuple[float, float, float],
    tolerance: float = 1e-5,
) -> bool:
    return all(abs(left - right) <= tolerance for left, right in zip(actual, expected))


def _validate_campaign_camera_and_composition(
    camera: object,
    scene: object,
    contract: SceneContract,
    target: TargetResolution,
) -> list[str]:
    errors: list[str] = []
    config = SHOT_CONFIGS[contract.scene_id]
    composition = composition_for(contract.scene_id)
    camera_data = getattr(camera, "data", None)
    placement = composition.subject_placement
    if camera_data is None:
        return ["campaign managed camera must contain exact camera data"]
    dof = getattr(camera_data, "dof", None)
    if (
        getattr(camera_data, "lens", None) != config.focal_length_mm
        or getattr(camera_data, "sensor_width", None) != 36.0
        or getattr(dof, "aperture_fstop", None) != config.aperture_fstop
        or getattr(camera_data, "clip_start", None) != 1.0
        or getattr(camera_data, "clip_end", None) != 10000.0
        or getattr(camera_data, "shift_x", None) != 0.5 - placement.center_x
        or getattr(camera_data, "shift_y", None) != placement.center_y - 0.5
    ):
        errors.append("campaign managed camera optics, clip, or shift drifted")

    raw_target = _property(scene, "pimm_static_target_evidence")
    try:
        target_payload = json.loads(raw_target) if isinstance(raw_target, str) else None
    except json.JSONDecodeError:
        target_payload = None
    expected_target_payload = {
        "schema_version": 1,
        "scene_id": config.scene_id,
        "selection_basis": "pimm_stable_id",
        "groups": {name: list(values) for name, values in target.groups.items()},
        "stable_ids": list(target.stable_ids),
        "bounds_min": list(target.bounds_min),
        "bounds_max": list(target.bounds_max),
    }
    if target_payload != expected_target_payload:
        errors.append(
            "campaign target evidence does not match reopened product geometry"
        )
    bounds_min = target.bounds_min
    bounds_max = target.bounds_max
    expected_pose = camera_pose(bounds_min, bounds_max, config)
    expected_evidence = composition_evidence(config, target, expected_pose)
    raw_composition = _property(scene, "pimm_shot_composition")
    try:
        actual_evidence = (
            json.loads(raw_composition) if isinstance(raw_composition, str) else None
        )
    except json.JSONDecodeError:
        actual_evidence = None
    if actual_evidence != expected_evidence:
        errors.append("embedded campaign composition evidence drifted")

    actual_location = _numeric_triplet(getattr(camera, "location", None))
    if actual_location is None or not _close_triplet(
        actual_location, expected_pose.location
    ):
        errors.append("campaign managed camera orbit or working distance drifted")
        return errors
    expected_forward = tuple(
        (expected_pose.target[index] - actual_location[index])
        / math.dist(actual_location, expected_pose.target)
        for index in range(3)
    )
    try:
        try:
            from mathutils import Vector

            forward_value = camera.matrix_world.to_quaternion() @ Vector(
                (0.0, 0.0, -1.0)
            )
        except ImportError:
            forward_value = camera.matrix_world.to_quaternion() @ (0.0, 0.0, -1.0)
        actual_forward = _numeric_triplet(forward_value)
    except (AttributeError, TypeError, ValueError):
        actual_forward = None
    if actual_forward is None:
        errors.append("campaign managed camera transform is unreadable")
    else:
        length = math.sqrt(sum(value * value for value in actual_forward))
        normalized = tuple(value / length for value in actual_forward) if length else actual_forward
        if not _close_triplet(normalized, expected_forward):
            errors.append("campaign managed camera optical axis missed the governed target")
    working_distance = math.dist(actual_location, expected_pose.target)
    machine_height = bounds_max[2] - bounds_min[2]
    if working_distance + 1e-5 < (
        machine_height * composition.minimum_working_distance_heights
    ):
        errors.append("campaign managed camera violates minimum working distance")
    if contract.purpose != "detail" and abs(actual_location[2] - expected_pose.target[2]) > 1e-5:
        errors.append("full-machine campaign camera must remain eye-level")
    actual_pose = CameraPose(
        location=actual_location,
        target=expected_pose.target,
        pitch_degrees=composition.camera_elevation_degrees,
    )
    try:
        coordinates = frame_coordinates(bounds_min, bounds_max, actual_pose, config)
    except ValueError:
        coordinates = ()
    if not coordinates or any(
        x < placement.clearance_left
        or x > 1.0 - placement.clearance_right
        or y < placement.clearance_top
        or y > 1.0 - placement.clearance_bottom
        for x, y in coordinates
    ):
        errors.append("campaign target violates normalized safe-area placement")
    protected = composition.protected_copy_rect
    if protected is not None and any(
        protected.contains(x, y) for x, y in coordinates
    ):
        errors.append("campaign target overlaps the protected-copy rectangle")
    return errors


def _validate_comparison_runtime_state(
    bpy: Any,
    config: ShotConfig,
    contacts: Mapping[str, FootContactPlane],
    asset_root: Path | None = None,
) -> list[str]:
    """Validate both immutable instances and their common physical floor."""

    errors: list[str] = []
    try:
        plan = comparison_link_plan(
            composition_for(config.scene_id),
            {machine: contact.z for machine, contact in contacts.items()},
        )
    except ValueError as error:
        return [str(error)]
    asset_root = ASSET_ROOT if asset_root is None else asset_root
    expected_masters = {
        machine: (asset_root / "masters" / f"PIMM-{machine}-MASTER.blend").resolve()
        for machine in config.machines
    }
    expected_collections: dict[str, object] = {}
    for machine, master_path in expected_masters.items():
        candidates = [
            collection
            for collection in getattr(bpy.data, "collections", ())
            if str(getattr(collection, "name", "")).startswith("PIMM_PUBLISHED")
            and _datablock_library_path(bpy, collection) == master_path
        ]
        if len(candidates) != 1:
            errors.append(
                f"comparison {machine} must resolve exactly one linked PIMM_PUBLISHED collection"
            )
            continue
        expected_collections[machine] = candidates[0]

    collection_instances = [
        obj
        for obj in getattr(bpy.data, "objects", ())
        if getattr(obj, "instance_type", None) == "COLLECTION"
    ]
    expected_names = {item.instance_name for item in plan}
    if {str(getattr(obj, "name", "")) for obj in collection_instances} != expected_names:
        errors.append("comparison scene must contain both unique managed instances")
    for item in plan:
        named_instances = [
            instance
            for instance in collection_instances
            if str(getattr(instance, "name", "")) == item.instance_name
        ]
        if len(named_instances) != 1:
            errors.append(
                f"comparison {item.machine} must contain exactly one named scene-owned instance"
            )
            continue
        instance = named_instances[0]
        if getattr(instance, "instance_collection", None) is not expected_collections.get(
            item.machine
        ):
            errors.append(
                f"comparison {item.machine} instance must use its expected linked PIMM_PUBLISHED collection"
            )
        location = _numeric_triplet(getattr(instance, "location", None))
        rotation = _numeric_triplet(getattr(instance, "rotation_euler", None))
        scale = _numeric_triplet(getattr(instance, "scale", None))
        if (
            location != (item.offset_x, item.offset_y, item.offset_z)
            or rotation != (0.0, 0.0, 0.0)
            or scale != (1.0, 1.0, 1.0)
            or _property(instance, "pimm_comparison_machine") != item.machine
            or _property(instance, "pimm_scene_transform_ownership")
            != "scene-owned"
            or _property(instance, "pimm_source_contact_z")
            != item.source_contact_z
            or _property(instance, "pimm_resolved_ground_z")
            != item.resolved_ground_z
        ):
            errors.append(
                f"comparison {item.machine} instance must retain its exact identity-scale common-floor transform"
            )
    expected_evidence = json.dumps(
        {
            machine: foot_contact_evidence(machine, contact)
            for machine, contact in contacts.items()
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if _property(
        bpy.context.scene, "pimm_comparison_contact_evidence"
    ) != expected_evidence:
        errors.append("comparison scene contact evidence must bind both foot reports")
    return errors


def _validate_campaign_runtime_state(
    bpy: Any,
    contract: SceneContract,
    asset_root: Path = ASSET_ROOT,
) -> list[str]:
    """Validate exact reopened runtime state for one governed campaign scene."""

    campaign = load_campaign(CAMPAIGN_PATH)
    campaign_errors = validate_campaign(campaign)
    if campaign_errors:
        return ["campaign validation failed: " + "; ".join(campaign_errors)]
    try:
        policy = shot_policy(campaign, contract.scene_id)
    except ValueError:
        return []

    errors: list[str] = []
    config = SHOT_CONFIGS[contract.scene_id]
    try:
        target_manifest = load_target_manifest(
            asset_root / "manifests" / "PIMM-static-shot-targets-v1.json",
            asset_root=asset_root,
        )
        reopened_target = resolve_target_bounds(
            bpy,
            config,
            target_manifest,
            asset_root=asset_root,
        )
    except (OSError, TypeError, ValueError) as error:
        reopened_target = None
        errors.append(
            f"campaign target cannot be resolved from reopened product geometry: {error}"
        )
    objects = list(getattr(bpy.data, "objects", ()))
    cameras = [obj for obj in objects if getattr(obj, "type", None) == "CAMERA"]
    if (
        len(cameras) != 1
        or getattr(cameras[0], "name", None) != contract.camera_name
        or getattr(bpy.context.scene, "camera", None) is not cameras[0]
    ):
        errors.append("campaign scene must contain exactly one managed camera")
    elif reopened_target is not None:
        errors.extend(
            _validate_campaign_camera_and_composition(
                cameras[0], bpy.context.scene, contract, reopened_target
            )
        )

    setup = contract.static_render_setup
    lighting = setup.get("lighting") if isinstance(setup, Mapping) else None
    expected_lights = tuple(
        lighting.get("required_light_names", ())
        if isinstance(lighting, Mapping)
        else ()
    )
    actual_lights = tuple(
        sorted(
            str(getattr(obj, "name", ""))
            for obj in objects
            if getattr(obj, "type", None) == "LIGHT"
        )
    )
    if actual_lights != tuple(sorted(expected_lights)):
        errors.append("campaign scene light names must equal the exact managed rig")

    actual_cards = tuple(
        sorted(
            str(getattr(obj, "name", ""))
            for obj in objects
            if getattr(obj, "type", None) == "MESH"
            and str(getattr(obj, "name", "")) in MANAGED_REFLECTION_CARD_NAMES
        )
    )
    if actual_cards != tuple(sorted(MANAGED_REFLECTION_CARD_NAMES)):
        errors.append("campaign scene reflection-card names must equal the exact managed rig")

    actions = list(getattr(bpy.data, "actions", ()))
    animated = getattr(bpy.context.scene, "animation_data", None) is not None or any(
        getattr(obj, "animation_data", None) is not None for obj in objects
    )
    if actions or animated:
        errors.append("campaign scene animation is forbidden")
    if policy.purpose == "comparison":
        try:
            contacts = load_foot_contact_planes(config, asset_root=asset_root)
        except (OSError, TypeError, ValueError) as error:
            errors.append(f"comparison contact reports cannot be loaded: {error}")
        else:
            errors.extend(
                _validate_comparison_runtime_state(
                    bpy, config, contacts, asset_root
                )
            )

    render = bpy.context.scene.render
    if getattr(render, "engine", None) != "CYCLES":
        errors.append("campaign scene render engine must equal Cycles")
    if (
        getattr(render, "resolution_x", None) != policy.width
        or getattr(render, "resolution_y", None) != policy.height
        or getattr(render, "resolution_percentage", None) != 100
        or getattr(render, "film_transparent", None) is not policy.alpha
        or getattr(render, "use_border", None) is not False
        or getattr(render, "use_crop_to_border", None) is not False
    ):
        errors.append("campaign scene render settings must match exact output policy")
    view = bpy.context.scene.view_settings
    if (
        getattr(view, "view_transform", None) != "AgX"
        or getattr(view, "look", None) != "AgX - Medium High Contrast"
        or getattr(view, "exposure", None) != 0.0
        or getattr(view, "gamma", None) != 1.0
    ):
        errors.append("campaign scene color settings must match exact AgX policy")
    output_path = Path(bpy.path.abspath(render.filepath)).resolve()
    expected_output = (
        Path(asset_root)
        / "renders"
        / "proofs"
        / "unapproved"
        / CAMPAIGN_ID
        / contract.scene_id
        / contract.scene_id
    ).resolve()
    if output_path != expected_output:
        errors.append("campaign scene must use the exact managed proof output path")
    return errors


def validate_open_render_scene(
    bpy: Any,
    contract: SceneContract,
    *,
    contract_snapshot_sha256: str | None = None,
) -> list[str]:
    """Inspect the open file without mutation and return all ownership errors."""

    errors = list(validate_scene_contract(contract))
    if errors:
        return errors
    errors.extend(_validate_campaign_runtime_state(bpy, contract, ASSET_ROOT))

    embedded_payload = _property(
        bpy.context.scene, "pimm_scene_contract_payload"
    )
    embedded_snapshot_sha256 = _property(
        bpy.context.scene, "pimm_scene_contract_snapshot_sha256"
    )
    if embedded_payload != canonical_scene_contract_json(contract):
        errors.append("embedded scene contract payload does not match validation snapshot")
    if (
        not isinstance(embedded_snapshot_sha256, str)
        or len(embedded_snapshot_sha256) != 64
        or any(
            character not in "0123456789ABCDEF"
            for character in embedded_snapshot_sha256
        )
    ):
        errors.append("embedded scene contract snapshot SHA-256 is absent or invalid")
    elif (
        contract_snapshot_sha256 is not None
        and embedded_snapshot_sha256 != contract_snapshot_sha256.upper()
    ):
        errors.append("embedded scene contract snapshot SHA-256 does not match snapshot")

    machines = contract.machines or ((contract.machine,) if contract.machine else ())
    for machine in machines:
        machine_contract = load_machine_contract(machine)
        errors.extend(validate_controller_scene(bpy, machine_contract))
        animation = machine_contract["animation"]
        if (
            contract.animation_contract is not None
            and animation["status"] != "enabled_owner_approved"
        ):
            errors.append(
                "scene animation_contract is present while the machine motion map remains blocked"
            )

    expected_masters = _master_authorities(contract)
    expected_material_library = (
        ASSET_ROOT / Path(contract.material_library_path)
    ).resolve()
    for expected_master in expected_masters.values():
        if not expected_master.is_file():
            errors.append(f"expected master is missing: {expected_master}")
    if all(path.is_file() for path in expected_masters.values()):
        actual_master_sha256 = (
            sha256_file(next(iter(expected_masters.values())))
            if len(expected_masters) == 1
            else _combined_master_sha256(expected_masters)
        )
        if actual_master_sha256 != contract.master_sha256.upper():
            errors.append(
                "master SHA-256 mismatch: "
                + ", ".join(str(path) for path in expected_masters.values())
            )
    if not expected_material_library.is_file():
        errors.append(f"expected material library is missing: {expected_material_library}")
    elif sha256_file(expected_material_library) != contract.material_library_sha256.upper():
        errors.append(
            f"material-library SHA-256 mismatch: {expected_material_library}"
        )

    opened_path = Path(str(getattr(bpy.data, "filepath", "")))
    try:
        require_within(opened_path, ASSET_ROOT / "scenes")
    except ValueError as error:
        errors.append(f"open render scene is outside managed scene root: {error}")

    library_paths = {
        path
        for path in (_library_path(bpy, library) for library in bpy.data.libraries)
        if path is not None
    }
    for expected_master in expected_masters.values():
        if expected_master not in library_paths:
            errors.append(f"missing expected master library link: {expected_master}")
    if expected_material_library not in library_paths:
        errors.append(
            f"missing expected material-library dependency: {expected_material_library}; found={sorted(str(path) for path in library_paths)}"
        )
    unexpected_library_paths = library_paths - {
        *expected_masters.values(),
        expected_material_library,
    }
    if unexpected_library_paths:
        errors.append(
            "render scene contains linked libraries outside the exact master/material-library "
            f"authority: {sorted(str(path) for path in unexpected_library_paths)}"
        )

    published_by_machine: dict[str, object] = {}
    reachable = _reachable_collections(bpy.context.scene)
    for machine, expected_master in expected_masters.items():
        candidates = [
            collection
            for collection in bpy.data.collections
            if str(getattr(collection, "name", "")).startswith(contract.master_collection)
            and _datablock_library_path(bpy, collection) == expected_master
        ]
        published = candidates[0] if len(candidates) == 1 else None
        if published is None:
            errors.append(
                f"render scene must link exactly one PIMM_PUBLISHED collection from the expected {machine} master"
            )
            continue
        published_by_machine[machine] = published
        if not list(getattr(published, "all_objects", ())):
            errors.append(f"linked {machine} PIMM_PUBLISHED collection is empty")
        if published not in reachable:
            errors.append(
                f"linked {machine} PIMM_PUBLISHED is not reachable from the active scene hierarchy"
            )
        machine_contract = replace(contract, machine=machine, machines=None)
        errors.extend(_validate_complete_product(published, machine_contract))

    environment_objects = [
        obj
        for obj in bpy.data.objects
        if getattr(obj, "type", None) == "MESH"
        and _property(obj, "pimm_scene_environment_role") is not None
    ]
    environment_meshes: set[object] = set()
    environment_materials: set[object] = set()
    if len(environment_objects) > 1:
        errors.append("render scene may contain only one authored environment mesh")
    for environment in environment_objects:
        mesh = getattr(environment, "data", None)
        materials = list(getattr(mesh, "materials", ())) if mesh is not None else []
        role = _property(environment, "pimm_scene_environment_role")
        valid = (
            role == "shadow-catcher"
            and str(getattr(environment, "name", "")) == "PIMM_SCENE_SHADOW_CATCHER"
            and _datablock_library_path(bpy, environment) is None
            and mesh is not None
            and str(getattr(mesh, "name", "")) == "PIMM_SCENE_SHADOW_CATCHER"
            and _datablock_library_path(bpy, mesh) is None
            and _property(mesh, "pimm_scene_environment_role") == role
            and getattr(environment, "is_shadow_catcher", False) is True
            and len(materials) == 1
            and str(getattr(materials[0], "name", ""))
            == "PIMM_SCENE_SHADOW_CATCHER_MATERIAL"
            and _datablock_library_path(bpy, materials[0]) is None
            and _property(materials[0], "pimm_scene_environment_role") == role
            and _property(materials[0], "pimm_material_id")
            == "SCENE_SHADOW_CATCHER"
            and _property(materials[0], "pimm_material_scope") is None
            and _property(environment, "pimm_stable_id") is None
        )
        if not valid:
            errors.append(
                f"authored scene environment is not the exact shadow catcher: {getattr(environment, 'name', '')}"
            )
            continue
        environment_meshes.add(mesh)
        environment_materials.add(materials[0])

    support_objects = [
        obj
        for obj in bpy.data.objects
        if getattr(obj, "type", None) == "MESH"
        and _property(obj, "pimm_scene_support_ownership") is not None
    ]
    support_meshes: set[object] = set()
    support_materials: set[object] = set()
    workshop_support_records: list[dict[str, object]] = []
    reflection_names = {
        str(getattr(obj, "name", ""))
        for obj in support_objects
        if _property(obj, "pimm_scene_support_role") == "reflection-card"
    }
    if reflection_names and reflection_names != set(MANAGED_REFLECTION_CARD_NAMES):
        errors.append("scene reflection-card geometry must use the exact managed names")
    for support in support_objects:
        name = str(getattr(support, "name", ""))
        mesh = getattr(support, "data", None)
        materials = list(getattr(mesh, "materials", ())) if mesh is not None else []
        role = _property(support, "pimm_scene_support_role")
        product_like = any(
            _property(support, property_name) is not None
            for property_name in (
                "pimm_stable_id",
                "pimm_artwork_id",
                "pimm_machine",
                "pimm_asset_role",
                "pimm_product_material_override",
            )
        ) or any(
            _property(material, "pimm_material_id") is not None
            or _property(material, "pimm_material_scope")
            in {"shared", "machine-local"}
            for material in materials
        )
        valid_local = (
            _property(support, "pimm_scene_support_ownership") == "scene-support"
            and _datablock_library_path(bpy, support) is None
            and mesh is not None
            and _datablock_library_path(bpy, mesh) is None
            and _property(mesh, "pimm_scene_support_ownership") == "scene-support"
            and bool(materials)
            and all(_datablock_library_path(bpy, material) is None for material in materials)
            and all(
                _property(material, "pimm_scene_support_ownership") == "scene-support"
                for material in materials
            )
            and not product_like
        )
        if role == "reflection-card":
            valid_local = (
                valid_local
                and len(materials) == 1
                and name in MANAGED_REFLECTION_CARD_NAMES
            )
        elif contract.purpose == "workshop":
            valid_local = valid_local and isinstance(
                _property(support, "pimm_external_asset_version_id"), str
            )
            raw_member_names = _property(
                support, "pimm_external_asset_member_names"
            )
            try:
                member_names = (
                    json.loads(raw_member_names)
                    if isinstance(raw_member_names, str)
                    else None
                )
            except json.JSONDecodeError:
                member_names = None
            workshop_support_records.append(
                {
                    "name": name,
                    "ownership": _property(
                        support, "pimm_scene_support_ownership"
                    ),
                    "asset_version_id": _property(
                        support, "pimm_external_asset_version_id"
                    ),
                    "local_relative_path": _property(
                        support, "pimm_external_asset_local_relative_path"
                    ),
                    "sha256": _property(support, "pimm_external_asset_sha256"),
                    "member_count": _property(
                        support, "pimm_external_asset_member_count"
                    ),
                    "member_names": member_names,
                }
            )
        else:
            valid_local = False
        if not valid_local:
            errors.append(f"scene support mesh is unowned or unauthorized: {name}")
            continue
        support_meshes.add(mesh)
        support_materials.update(materials)

    if contract.purpose == "workshop":
        errors.extend(
            _validate_workshop_runtime_state(
                bpy.context.scene,
                contract.scene_id,
                workshop_support_records,
                ASSET_ROOT,
            )
        )

    products = sorted(
        (
            obj
            for obj in bpy.data.objects
            if getattr(obj, "type", None) == "MESH"
            and obj not in environment_objects
            and obj not in support_objects
        ),
        key=lambda obj: str(getattr(obj, "name", "")),
    )
    expected_products = {
        product
        for published in published_by_machine.values()
        for product in getattr(published, "all_objects", ())
    }
    material_registry: dict[str, object] = {}
    # Validate every used material datablock, not only object slots. Geometry
    # Nodes and node-socket pointers can contribute a material to rendering
    # without placing it in ``Object.material_slots``.
    for material in getattr(bpy.data, "materials", ()):
        if int(getattr(material, "users", 0)) <= 0:
            continue
        if material in environment_materials or material in support_materials:
            continue
        material_name = str(getattr(material, "name", ""))
        material_id = _property(material, "pimm_material_id")
        if (
            not isinstance(material_id, str)
            or material_id != material_id.strip()
            or _MATERIAL_ID.fullmatch(material_id) is None
            or material_id == "UNASSIGNED"
        ):
            errors.append(
                f"used material requires exact pimm_material_id: {material_name}"
            )
            continue
        prior = material_registry.setdefault(material_id, material)
        if prior is not material:
            errors.append(
                f"pimm_material_id must identify one exact material datablock: {material_id}"
            )
        origin = _datablock_library_path(bpy, material)
        if origin == expected_material_library:
            if material_id not in _APPROVED_SHARED_MATERIAL_IDS:
                errors.append(
                    "material-library pimm_material_id is outside the canonical shared "
                    f"catalog: {material_name}/{material_id}"
                )
            elif material_name != f"PIMM_{material_id}":
                errors.append(
                    "shared material name/pimm_material_id mismatch: "
                    f"{material_name}/{material_id}"
                )
        elif origin in set(expected_masters.values()) and material_id in _APPROVED_SHARED_MATERIAL_IDS:
            errors.append(
                "shared material resolved from master instead of material library: "
                f"{material_name}/{material_id}"
            )
        elif origin not in {*expected_masters.values(), expected_material_library}:
            errors.append(
                "used material is scene-local or outside the exact master/material-library "
                f"authority: {material_name}/{material_id} origin={origin}"
            )
    for product in products:
        name = str(getattr(product, "name", ""))
        object_library = _datablock_library_path(bpy, product)
        mesh = getattr(product, "data", None)
        mesh_library = _datablock_library_path(bpy, mesh)
        expected_master = next(
            (path for path in expected_masters.values() if path == object_library),
            None,
        )
        if expected_master is None:
            errors.append(
                f"scene-local MESH object is forbidden; private machine mesh: {name}"
            )
        elif product not in expected_products:
            errors.append(f"master MESH is outside PIMM_PUBLISHED: {name}")
        if mesh_library != expected_master:
            errors.append(
                f"scene-local MESH datablock is forbidden; private machine mesh: {name}"
            )
        errors.extend(
            _validate_materials(
                bpy,
                product,
                expected_master,
                expected_material_library,
                material_registry,
            )
        )

    for mesh in bpy.data.meshes:
        if mesh in environment_meshes or mesh in support_meshes:
            continue
        if _datablock_library_path(bpy, mesh) not in set(expected_masters.values()):
            name = str(getattr(mesh, "name", ""))
            message = f"scene-local MESH datablock is forbidden: {name}"
            if message not in errors:
                errors.append(message)

    camera = bpy.data.objects.get(contract.camera_name)
    if camera is None or getattr(camera, "type", None) != "CAMERA":
        errors.append(f"required camera is missing: {contract.camera_name}")
    else:
        if getattr(bpy.context.scene, "camera", None) != camera:
            errors.append(f"required camera is not active: {contract.camera_name}")
        if _datablock_library_path(bpy, camera) is not None or _datablock_library_path(
            bpy, getattr(camera, "data", None)
        ) is not None:
            errors.append(f"required camera must be scene-local: {contract.camera_name}")
        _validate_static_camera_clip_range(camera, contract, errors)

    render = bpy.context.scene.render
    output_path = Path(bpy.path.abspath(render.filepath)).resolve()
    try:
        require_within(output_path, ASSET_ROOT / "renders")
    except ValueError as error:
        errors.append(f"output is outside managed render root: {error}")
    if render.resolution_x != contract.output_contract["width"]:
        errors.append("render width does not match output_contract")
    if render.resolution_y != contract.output_contract["height"]:
        errors.append("render height does not match output_contract")
    if render.resolution_percentage != 100:
        errors.append("render resolution_percentage must equal 100")
    if render.film_transparent is not contract.output_contract["alpha"]:
        errors.append("render alpha does not match output_contract")

    units = bpy.context.scene.unit_settings
    if units.system != "METRIC" or units.length_unit != "MILLIMETERS":
        errors.append("render scene units must be Metric/Millimeters")
    if abs(float(units.scale_length) - 0.001) > 1e-7:
        errors.append("render scene scale_length must equal 0.001")
    return errors


def _fixture_asset_root(path: Path) -> Path:
    resolved = path.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if resolved == temporary_root:
        raise ValueError("fixture asset root cannot equal the system temporary root")
    try:
        resolved.relative_to(temporary_root)
    except ValueError as error:
        raise ValueError(
            "fixture asset root must be beneath the system temporary root"
        ) from error
    return resolved


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--fixture-asset-root", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    global ASSET_ROOT

    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else []
    )
    if arguments.fixture_asset_root is not None:
        ASSET_ROOT = _fixture_asset_root(arguments.fixture_asset_root)
    contract = SceneContract.from_json(arguments.contract)
    contract_snapshot_sha256 = sha256_file(arguments.contract)
    import bpy

    errors = validate_open_render_scene(
        bpy,
        contract,
        contract_snapshot_sha256=contract_snapshot_sha256,
    )
    print(VALIDATION_MARKER + json.dumps(errors, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
