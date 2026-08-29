"""Define fail-closed contract payloads for governed PIMM static product scenes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from statistics import median
import sys
from typing import Any, Mapping, Sequence
import uuid

try:
    from .blender_static_hero_scene import (
        CameraPose,
        DEFAULT_EXPOSURE,
        DEFAULT_LIGHT_TEMPERATURE_KELVIN,
        DEFAULT_LOOK,
        DEFAULT_SENSOR_WIDTH_MM,
        _center_and_size,
        _install_environment,
        _install_lights,
        _install_world_environment,
        _point_at,
        studio_environment_specs,
        studio_light_specs,
        studio_world_environment_spec,
    )
    from .blender_scene_template import comparison_link_plan, _run_fresh_validation
    from .campaign_contract import load_campaign, validate_campaign
    from .external_asset_manifest import validate_external_assets
    from .io_contract import atomic_write_json, sha256_file
    from .paths import ASSET_ROOT, require_within
    from .scene_contract import (
        SceneContract,
        canonical_scene_contract_json,
        validate_scene_contract,
    )
    from .shot_compositions import (
        CAMPAIGN_PATH,
        COMPLETE_PRODUCT_BOUNDS,
        MANAGED_REFLECTION_CARD_NAMES,
        STABLE_ID_GROUPS,
        ShotComposition,
        composition_for,
    )
except ImportError:  # Blender executes checked-in scripts outside package mode.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production.blender_static_hero_scene import (
        CameraPose,
        DEFAULT_EXPOSURE,
        DEFAULT_LIGHT_TEMPERATURE_KELVIN,
        DEFAULT_LOOK,
        DEFAULT_SENSOR_WIDTH_MM,
        _center_and_size,
        _install_environment,
        _install_lights,
        _install_world_environment,
        _point_at,
        studio_environment_specs,
        studio_light_specs,
        studio_world_environment_spec,
    )
    from scripts.blender.pimm_production.blender_scene_template import (
        comparison_link_plan,
        _run_fresh_validation,
    )
    from scripts.blender.pimm_production.campaign_contract import (
        load_campaign,
        validate_campaign,
    )
    from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
    from scripts.blender.pimm_production.external_asset_manifest import (
        validate_external_assets,
    )
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
    from scripts.blender.pimm_production.scene_contract import (
        SceneContract,
        canonical_scene_contract_json,
        validate_scene_contract,
    )
    from scripts.blender.pimm_production.shot_compositions import (
        CAMPAIGN_PATH,
        COMPLETE_PRODUCT_BOUNDS,
        MANAGED_REFLECTION_CARD_NAMES,
        STABLE_ID_GROUPS,
        ShotComposition,
        composition_for,
    )


RESULT_MARKER = "PIMM_STATIC_PRODUCT_SCENE_JSON="
MASTER_COLLECTION = "PIMM_PUBLISHED"
STATIC_CAMERA_CLIP_START = 1.0
STATIC_CAMERA_CLIP_END = 10000.0
MANAGED_LIGHT_NAMES = (
    "KEY_SOFTBOX",
    "FILL_SOFTBOX",
    "BASE_BOUNCE",
    "STRIP_LEFT",
    "STRIP_RIGHT",
)
FOOT_CONTACT_REPORT_SCHEMA = "maliev.pimm-foot-contact-report/v1"
FOOT_CONTACT_TOLERANCE = 1e-6
_FOOT_CONTACT_REPORT_FIELDS = {
    "schema",
    "scene_id",
    "scene_contract_sha256",
    "master_sha256",
    "patch_sha256",
    "contact_evidence",
    "tolerance",
    "passed",
}
_FOOT_CONTACT_EVIDENCE_FIELDS = {
    "schema_version",
    "machine",
    "selection_basis",
    "patch_path",
    "contact_z",
    "pad_bottoms",
    "stable_ids",
    "outlier_stable_ids",
}


@dataclass(frozen=True)
class ShotConfig:
    """Immutable camera and output requirements for one static PIMM still."""

    scene_id: str
    machines: tuple[str, ...]
    purpose: str
    view: str
    focal_length_mm: float
    aperture_fstop: float
    output_width: int
    output_height: int
    alpha: bool
    animation_contract: None = None

    @property
    def machine(self) -> str | None:
        """Return the one machine for single-product shots, otherwise ``None``."""

        return self.machines[0] if len(self.machines) == 1 else None


@dataclass(frozen=True)
class SceneSupportSpec:
    """Scene-owned finite geometry used only to light or support the product."""

    name: str
    role: str
    center: tuple[float, float, float]
    width: float
    depth: float
    height: float
    base_color: tuple[float, float, float, float]
    roughness: float


@dataclass(frozen=True)
class TargetResolution:
    """Resolved target geometry plus the stable-ID evidence used to select it."""

    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]
    groups: dict[str, tuple[str, ...]]
    stable_ids: tuple[str, ...]


@dataclass(frozen=True)
class FootContactPlane:
    """Physical studio-floor evidence derived from the four nylon foot pads."""

    z: float
    pad_bottoms: tuple[float, ...]
    stable_ids: tuple[str, ...]
    outlier_stable_ids: tuple[str, ...]


@dataclass(frozen=True)
class WorkshopSupportRecord:
    """One hash-verified scene-local support asset authorized for a workshop shot."""

    asset_version_id: str
    path: Path
    local_relative_path: str
    sha256: str


@dataclass(frozen=True)
class _InstancedStableMesh:
    """Read-only bounds view of a linked mesh beneath a scene-owned instance."""

    source: Any
    matrix_world: Any

    @property
    def type(self) -> str:
        return str(self.source.type)

    @property
    def bound_box(self) -> Any:
        return self.source.bound_box

    def get(self, name: str, default: object = None) -> object:
        return self.source.get(name, default)


def _single_machine(config: ShotConfig) -> str:
    machine = config.machine
    if machine is None:
        raise ValueError(f"shot requires one machine: {config.scene_id}")
    return machine


def resolve_foot_contact_plane(
    patch_payload: Mapping[str, object], expected_machine: str
) -> FootContactPlane:
    """Resolve a robust floor height without trusting one malformed foot occurrence."""

    if patch_payload.get("kind") != "PIMM_FOOT_GEOMETRY_PATCH":
        raise ValueError("foot patch kind must be PIMM_FOOT_GEOMETRY_PATCH")
    if patch_payload.get("machine") != expected_machine:
        raise ValueError(
            f"foot patch machine mismatch: expected {expected_machine}, "
            f"got {patch_payload.get('machine')}"
        )
    solids = patch_payload.get("solids")
    if not isinstance(solids, list):
        raise ValueError("foot patch solids must be a list")
    pads = [
        solid
        for solid in solids
        if isinstance(solid, Mapping) and solid.get("original_name") == "nylon feet"
    ]
    if len(pads) != 4:
        raise ValueError("foot patch must contain exactly four nylon foot pads")

    stable_ids: list[str] = []
    bottoms: list[float] = []
    for pad in pads:
        stable_id = pad.get("stable_id")
        if not isinstance(stable_id, str) or not stable_id.strip():
            raise ValueError("every nylon foot pad must have a nonempty stable_id")
        geometry = pad.get("geometry")
        bounds = geometry.get("bounds") if isinstance(geometry, Mapping) else None
        if not isinstance(bounds, list) or len(bounds) != 6:
            raise ValueError(f"nylon foot pad {stable_id} must have six finite bounds")
        try:
            numeric_bounds = tuple(float(value) for value in bounds)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"nylon foot pad {stable_id} must have six finite bounds"
            ) from error
        if not all(math.isfinite(value) for value in numeric_bounds):
            raise ValueError(f"nylon foot pad {stable_id} must have six finite bounds")
        stable_ids.append(stable_id)
        bottoms.append(numeric_bounds[2])
    if len(set(stable_ids)) != 4:
        raise ValueError("nylon foot pad stable_ids must be unique")

    contact_z = float(median(bottoms))
    outliers = tuple(
        stable_id
        for stable_id, bottom in zip(stable_ids, bottoms, strict=True)
        if abs(bottom - contact_z) > FOOT_CONTACT_TOLERANCE
    )
    return FootContactPlane(
        z=contact_z,
        pad_bottoms=tuple(bottoms),
        stable_ids=tuple(stable_ids),
        outlier_stable_ids=outliers,
    )


def contact_environment_specs(
    specs: Sequence[Any], contact_z: float
) -> tuple[Any, ...]:
    """Move only the studio shadow catcher to the validated contact height."""

    corrected = tuple(
        replace(spec, z=float(contact_z))
        if getattr(spec, "role", None) == "shadow-catcher"
        else spec
        for spec in specs
    )
    if sum(getattr(spec, "role", None) == "shadow-catcher" for spec in corrected) != 1:
        raise ValueError("studio environment must contain exactly one shadow-catcher")
    return corrected


@dataclass(frozen=True)
class ValidatedTargetManifest:
    """Immutable handle proving a canonical target manifest passed strict loading."""

    path: Path
    sha256: str
    canonical_json: str


_CAMPAIGN = load_campaign(CAMPAIGN_PATH)
_CAMPAIGN_ERRORS = validate_campaign(_CAMPAIGN)
if _CAMPAIGN_ERRORS:
    raise ValueError("campaign validation failed: " + "; ".join(_CAMPAIGN_ERRORS))

SHOT_CONFIGS = {
    policy.shot_id: ShotConfig(
        scene_id=policy.shot_id,
        machines=policy.machines,
        purpose=policy.purpose,
        view=composition_for(policy.shot_id).camera_view,
        focal_length_mm=policy.focal_length_mm,
        aperture_fstop=policy.aperture_fstop,
        output_width=policy.width,
        output_height=policy.height,
        alpha=policy.alpha,
    )
    for policy in _CAMPAIGN.shots
}

_FRAME_MARGIN = 0.05


def _target_manifest_path(asset_root: Path | None = None) -> Path:
    root = ASSET_ROOT if asset_root is None else asset_root
    return root / "manifests" / "PIMM-static-shot-targets-v1.json"


def orbit_camera_pose(
    bounds_min: Sequence[float],
    bounds_max: Sequence[float],
    distance: float,
    azimuth_degrees: float,
    elevation_degrees: float,
) -> CameraPose:
    """Return a deterministic camera orbit around the center of valid bounds."""

    center, _size = _center_and_size(bounds_min, bounds_max)
    if float(distance) <= 0:
        raise ValueError("camera distance must be positive")
    azimuth = math.radians(float(azimuth_degrees))
    elevation = math.radians(float(elevation_degrees))
    horizontal = float(distance) * math.cos(elevation)
    return CameraPose(
        location=(
            center[0] + horizontal * math.sin(azimuth),
            center[1] - horizontal * math.cos(azimuth),
            center[2] + float(distance) * math.sin(elevation),
        ),
        target=center,
        pitch_degrees=float(elevation_degrees),
    )


def bounds_for_objects(
    objects: Sequence[Any],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return world bounds for one nonempty group of stable-ID mesh objects."""

    if not objects:
        raise ValueError("stable target group must contain at least one object")
    points: list[Sequence[float]] = []
    for obj in objects:
        stable_id = obj.get("pimm_stable_id")
        if not isinstance(stable_id, str) or not stable_id.strip():
            raise ValueError("stable target object is missing pimm_stable_id")
        if getattr(obj, "type", None) != "MESH":
            raise ValueError(f"stable target object is not a mesh: {stable_id}")
        try:
            from mathutils import Vector

            points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
        except ImportError:
            points.extend(obj.matrix_world @ corner for corner in obj.bound_box)
    if not points:
        raise ValueError("stable target group has no bounded geometry")
    return (
        tuple(min(float(point[index]) for point in points) for index in range(3)),
        tuple(max(float(point[index]) for point in points) for index in range(3)),
    )


def _validate_target_manifest_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "shots"}:
        raise ValueError("target manifest must contain exactly schema_version and shots")
    if payload["schema_version"] != 1 or not isinstance(payload["shots"], dict):
        raise ValueError("target manifest schema_version must be 1 and shots must be an object")
    shots = payload["shots"]
    detail_configs = [config for config in SHOT_CONFIGS.values() if config.purpose == "detail"]
    if set(shots) != {config.scene_id for config in detail_configs}:
        raise ValueError("target manifest shots must exactly match the governed detail shots")
    for config in detail_configs:
        shot = shots[config.scene_id]
        if not isinstance(shot, dict) or set(shot) != {"groups"}:
            raise ValueError(f"target manifest {config.scene_id} must contain exactly groups")
        groups = shot["groups"]
        expected_groups = tuple(composition_for(config.scene_id).target_groups)
        if not isinstance(groups, dict) or set(groups) != set(expected_groups):
            raise ValueError(
                f"target manifest {config.scene_id} groups must equal {list(expected_groups)}"
            )
        for group_name in expected_groups:
            identifiers = groups[group_name]
            exact_identifiers = list(
                composition_for(config.scene_id).target_groups[group_name]
            )
            if (
                not isinstance(identifiers, list)
                or not identifiers
                or not all(
                    isinstance(identifier, str) and identifier == identifier.strip() and identifier
                    for identifier in identifiers
                )
                or len(set(identifiers)) != len(identifiers)
                or identifiers != exact_identifiers
            ):
                raise ValueError(
                    f"target manifest {config.scene_id} {group_name} must equal the composition stable-ID list"
                )
    return payload


def load_target_manifest(
    path: Path, *, asset_root: Path | None = None
) -> ValidatedTargetManifest:
    """Load only the canonical v1 stable-ID target manifest and validate every shot."""

    root = ASSET_ROOT if asset_root is None else asset_root
    canonical_root = root / "manifests"
    try:
        resolved = require_within(Path(path), canonical_root)
    except ValueError as error:
        raise ValueError(f"canonical target manifest path is required: {path}") from error
    canonical = _target_manifest_path(root).resolve()
    if resolved != canonical:
        raise ValueError(f"canonical target manifest path is required: {canonical}")
    try:
        manifest_bytes = resolved.read_bytes()
        payload = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"target manifest cannot be read: {resolved}: {error}") from error
    validated = _validate_target_manifest_payload(payload)
    canonical_json = json.dumps(
        validated,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return ValidatedTargetManifest(
        path=canonical,
        sha256=hashlib.sha256(manifest_bytes).hexdigest().upper(),
        canonical_json=canonical_json,
    )


def _validated_target_manifest_payload(
    manifest: ValidatedTargetManifest,
    *,
    asset_root: Path | None = None,
) -> dict[str, object]:
    if not isinstance(manifest, ValidatedTargetManifest):
        raise ValueError("authoring requires a validated canonical target manifest")
    refreshed = load_target_manifest(manifest.path, asset_root=asset_root)
    if refreshed != manifest:
        raise ValueError("validated canonical target manifest changed after loading")
    payload = json.loads(manifest.canonical_json)
    return _validate_target_manifest_payload(payload)


def _stable_product_objects(bpy: Any) -> dict[str, Any]:
    by_stable_id: dict[str, Any] = {}
    scene_objects = list(bpy.context.scene.objects)
    candidates: list[Any] = [
        obj for obj in scene_objects if getattr(obj, "type", None) == "MESH"
    ]
    for instance in scene_objects:
        collection = getattr(instance, "instance_collection", None)
        if getattr(instance, "instance_type", None) != "COLLECTION" or collection is None:
            continue
        for obj in getattr(collection, "all_objects", ()):
            if getattr(obj, "type", None) != "MESH":
                continue
            candidates.append(
                _InstancedStableMesh(
                    source=obj,
                    matrix_world=instance.matrix_world @ obj.matrix_world,
                )
            )
    for obj in candidates:
        if getattr(obj, "type", None) != "MESH":
            continue
        stable_id = obj.get("pimm_stable_id")
        if not isinstance(stable_id, str) or not stable_id.strip():
            continue
        if stable_id in by_stable_id:
            raise ValueError(f"linked scene contains duplicate stable target ID: {stable_id}")
        by_stable_id[stable_id] = obj
    if not by_stable_id:
        raise ValueError("linked scene contains no stable target product meshes")
    return by_stable_id


def resolve_target_bounds(
    bpy: Any,
    config: ShotConfig,
    target_manifest: ValidatedTargetManifest,
    *,
    asset_root: Path | None = None,
) -> TargetResolution:
    """Resolve complete-product or semantic detail bounds without display names."""

    _validate_shot_config(config)
    target_payload = _validated_target_manifest_payload(
        target_manifest, asset_root=asset_root
    )
    by_stable_id = _stable_product_objects(bpy)
    composition = composition_for(config.scene_id)
    if composition.target_mode == COMPLETE_PRODUCT_BOUNDS:
        stable_ids = tuple(sorted(by_stable_id))
        groups = {"complete_product": stable_ids}
    else:
        shots = target_payload["shots"]
        shot = shots.get(config.scene_id) if isinstance(shots, dict) else None
        source_groups = shot.get("groups") if isinstance(shot, dict) else None
        expected_groups = tuple(composition.target_groups)
        if not isinstance(source_groups, dict) or set(source_groups) != set(expected_groups):
            raise ValueError(f"stable target groups are invalid for {config.scene_id}")
        groups = {
            name: tuple(source_groups[name])
            for name in expected_groups
            if isinstance(source_groups[name], list) and source_groups[name]
        }
        if set(groups) != set(expected_groups):
            raise ValueError(f"stable target groups are incomplete for {config.scene_id}")
        missing_by_group = {
            name: [stable_id for stable_id in stable_ids if stable_id not in by_stable_id]
            for name, stable_ids in groups.items()
        }
        missing_by_group = {name: values for name, values in missing_by_group.items() if values}
        if missing_by_group:
            artwork_groups = {"gauge_decal", "airtac_artwork"}
            missing_artwork = sorted(artwork_groups & set(missing_by_group))
            if missing_artwork:
                raise ValueError(
                    "missing artwork target stable IDs: "
                    + ", ".join(
                        stable_id
                        for group in missing_artwork
                        for stable_id in missing_by_group[group]
                    )
                )
            raise ValueError(f"missing stable target IDs: {missing_by_group}")
        stable_ids = tuple(sorted({item for values in groups.values() for item in values}))
    bounds_min, bounds_max = bounds_for_objects([by_stable_id[item] for item in stable_ids])
    return TargetResolution(bounds_min, bounds_max, groups, stable_ids)


def _subtract(left: Sequence[float], right: Sequence[float]) -> tuple[float, float, float]:
    return tuple(float(left[index]) - float(right[index]) for index in range(3))


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(float(left[index]) * float(right[index]) for index in range(3))


def _cross(left: Sequence[float], right: Sequence[float]) -> tuple[float, float, float]:
    return (
        float(left[1]) * float(right[2]) - float(left[2]) * float(right[1]),
        float(left[2]) * float(right[0]) - float(left[0]) * float(right[2]),
        float(left[0]) * float(right[1]) - float(left[1]) * float(right[0]),
    )


def _normalize(vector: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(_dot(vector, vector))
    if length <= 0:
        raise ValueError("camera direction must have positive length")
    return tuple(float(value) / length for value in vector)


def _camera_basis(pose: CameraPose) -> tuple[tuple[float, float, float], ...]:
    forward = _normalize(_subtract(pose.target, pose.location))
    right = _normalize(_cross(forward, (0.0, 0.0, 1.0)))
    up = _normalize(_cross(right, forward))
    return right, up, forward


def _bounds_corners(
    bounds_min: Sequence[float], bounds_max: Sequence[float]
) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (float(x), float(y), float(z))
        for x in (bounds_min[0], bounds_max[0])
        for y in (bounds_min[1], bounds_max[1])
        for z in (bounds_min[2], bounds_max[2])
    )


def frame_coordinates(
    bounds_min: Sequence[float],
    bounds_max: Sequence[float],
    pose: CameraPose,
    config: ShotConfig,
) -> tuple[tuple[float, float], ...]:
    """Project target-bound corners to normalized camera-frame coordinates."""

    right, up, forward = _camera_basis(pose)
    horizontal_tangent = DEFAULT_SENSOR_WIDTH_MM / (2.0 * config.focal_length_mm)
    sensor_height = DEFAULT_SENSOR_WIDTH_MM * config.output_height / config.output_width
    vertical_tangent = sensor_height / (2.0 * config.focal_length_mm)
    placement = composition_for(config.scene_id).subject_placement
    offset_x = placement.center_x - 0.5
    offset_y = placement.center_y - 0.5
    projected: list[tuple[float, float]] = []
    for corner in _bounds_corners(bounds_min, bounds_max):
        relative = _subtract(corner, pose.location)
        depth = _dot(relative, forward)
        if depth <= 0:
            raise ValueError("contracted target lies behind the camera")
        projected.append(
            (
                0.5 + offset_x + _dot(relative, right) / (2.0 * depth * horizontal_tangent),
                0.5 + offset_y + _dot(relative, up) / (2.0 * depth * vertical_tangent),
            )
        )
    return tuple(projected)


def stable_geometry_camera_depth_range(
    bpy: Any, pose: CameraPose
) -> tuple[float, float]:
    """Return near/far camera depths for every stable product bounding-box corner."""

    _right, _up, forward = _camera_basis(pose)
    depths: list[float] = []
    for obj in _stable_product_objects(bpy).values():
        try:
            from mathutils import Vector

            points = (obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
        except ImportError:
            points = (obj.matrix_world @ corner for corner in obj.bound_box)
        depths.extend(_dot(_subtract(point, pose.location), forward) for point in points)
    if not depths:
        raise ValueError("stable product geometry has no camera-depth evidence")
    return min(depths), max(depths)


def camera_pose(
    bounds_min: Sequence[float], bounds_max: Sequence[float], config: ShotConfig
) -> CameraPose:
    """Frame one governed target with deterministic optics and orbit geometry."""

    _validate_shot_config(config)
    center, _size = _center_and_size(bounds_min, bounds_max)
    composition = composition_for(config.scene_id)
    azimuth = composition.camera_azimuth_degrees
    elevation = composition.camera_elevation_degrees
    unit_pose = orbit_camera_pose(bounds_min, bounds_max, 1.0, azimuth, elevation)
    right, up, forward = _camera_basis(unit_pose)
    horizontal_tangent = DEFAULT_SENSOR_WIDTH_MM / (2.0 * config.focal_length_mm)
    sensor_height = DEFAULT_SENSOR_WIDTH_MM * config.output_height / config.output_width
    vertical_tangent = sensor_height / (2.0 * config.focal_length_mm)
    placement = composition.subject_placement
    usable_half_width = min(
        placement.center_x - placement.clearance_left,
        1.0 - placement.clearance_right - placement.center_x,
    )
    usable_half_height = min(
        placement.center_y - placement.clearance_top,
        1.0 - placement.clearance_bottom - placement.center_y,
    )
    if usable_half_width <= 0.0 or usable_half_height <= 0.0:
        raise ValueError("normalized subject placement leaves no usable camera frame")
    distance = 1.0
    for corner in _bounds_corners(bounds_min, bounds_max):
        offset = _subtract(corner, center)
        along = _dot(offset, forward)
        distance = max(
            distance,
            abs(_dot(offset, right)) / (2.0 * usable_half_width * horizontal_tangent)
            - along,
            abs(_dot(offset, up)) / (2.0 * usable_half_height * vertical_tangent)
            - along,
        )
    distance *= 1.001
    distance = max(
        distance,
        _size[2] * composition.minimum_working_distance_heights,
    )
    return orbit_camera_pose(bounds_min, bounds_max, distance, azimuth, elevation)


def profile_rig_specs(
    bounds_min: Sequence[float],
    bounds_max: Sequence[float],
    pose: CameraPose,
    config: ShotConfig,
) -> tuple[tuple[Any, ...], tuple[SceneSupportSpec, ...]]:
    """Return the exact broad light rig and finite scene-owned support geometry."""

    _validate_shot_config(config)
    center, size = _center_and_size(bounds_min, bounds_max)
    width, depth, height = size
    profile = composition_for(config.scene_id).studio_profile
    energy_scale = {"dark": 0.72, "workshop": 0.86}.get(profile, 1.0)
    lights = tuple(
        replace(spec, energy=spec.energy * energy_scale)
        for spec in studio_light_specs(bounds_min, bounds_max)
    )
    horizontal_tangent = DEFAULT_SENSOR_WIDTH_MM / (2.0 * config.focal_length_mm)
    catcher_half_width = (
        STATIC_CAMERA_CLIP_END * horizontal_tangent
        + abs(center[0] - pose.location[0])
        + width
    )
    catcher_half_depth = STATIC_CAMERA_CLIP_END + abs(center[1] - pose.location[1]) + depth
    card_color = (0.03, 0.03, 0.035, 1.0) if profile == "dark" else (0.92, 0.92, 0.92, 1.0)
    supports = (
        SceneSupportSpec(
            "PIMM_SCENE_SHADOW_CATCHER",
            "shadow-catcher",
            (center[0], center[1], float(bounds_min[2])),
            catcher_half_width * 2.0,
            catcher_half_depth * 2.0,
            0.0,
            (0.86, 0.86, 0.86, 1.0),
            0.72,
        ),
        SceneSupportSpec(
            MANAGED_REFLECTION_CARD_NAMES[0],
            "reflection-card",
            (center[0] - width * 1.8, center[1], center[2]),
            max(depth, 600.0),
            20.0,
            max(height * 1.3, 1_000.0),
            card_color,
            0.35,
        ),
        SceneSupportSpec(
            MANAGED_REFLECTION_CARD_NAMES[1],
            "reflection-card",
            (center[0] + width * 1.8, center[1], center[2]),
            max(depth, 600.0),
            20.0,
            max(height * 1.3, 1_000.0),
            card_color,
            0.35,
        ),
        SceneSupportSpec(
            MANAGED_REFLECTION_CARD_NAMES[2],
            "reflection-card",
            (center[0], center[1], float(bounds_max[2]) + height * 0.9),
            max(width * 1.8, 1_200.0),
            max(depth * 1.5, 900.0),
            20.0,
            card_color,
            0.35,
        ),
    )
    if tuple(spec.name for spec in lights) != MANAGED_LIGHT_NAMES:
        raise ValueError("profile light rig names do not match managed authority")
    return lights, supports


def catcher_edges_outside_camera_frustum(
    catcher: SceneSupportSpec, pose: CameraPose, config: ShotConfig
) -> bool:
    """Prove all finite catcher edges lie beyond the managed camera frustum."""

    if catcher.role != "shadow-catcher" or catcher.name != "PIMM_SCENE_SHADOW_CATCHER":
        return False
    horizontal_tangent = DEFAULT_SENSOR_WIDTH_MM / (2.0 * config.focal_length_mm)
    center_x, center_y, _center_z = catcher.center
    required_half_width = (
        STATIC_CAMERA_CLIP_END * horizontal_tangent
        + abs(center_x - pose.location[0])
    )
    required_half_depth = STATIC_CAMERA_CLIP_END + abs(center_y - pose.location[1])
    return catcher.width / 2.0 > required_half_width and catcher.depth / 2.0 > required_half_depth


def _contract_path(config: ShotConfig) -> Path:
    return ASSET_ROOT / "scenes" / "contracts" / f"{config.scene_id}.json"


def _scene_path(config: ShotConfig) -> Path:
    return ASSET_ROOT / "scenes" / "stills" / f"{config.scene_id}.blend"


def _master_path(config: ShotConfig) -> Path:
    machine = _single_machine(config)
    return ASSET_ROOT / "masters" / f"PIMM-{machine}-MASTER.blend"


def _master_paths(config: ShotConfig) -> tuple[Path, ...]:
    """Return every exact master authority in campaign machine order."""

    _validate_shot_config(config)
    return tuple(
        ASSET_ROOT / "masters" / f"PIMM-{machine}-MASTER.blend"
        for machine in config.machines
    )


def _template_path(config: ShotConfig) -> Path:
    if len(config.machines) > 1:
        return ASSET_ROOT / "scenes" / "shared-templates" / "pimm-30g-50g--comparison.blend"
    machine = _single_machine(config)
    return (
        ASSET_ROOT
        / "scenes"
        / "shared-templates"
        / f"pimm-{machine.lower()}--hero--three-quarter.blend"
    )


def _material_library_path() -> Path:
    return ASSET_ROOT / "masters" / "PIMM-MATERIAL-LIBRARY.blend"


def _foot_patch_path(config: ShotConfig) -> Path:
    machine = _single_machine(config)
    return (
        ASSET_ROOT
        / "manifests"
        / "patches"
        / f"PIMM-{machine}-foot-refresh.json"
    )


def _load_machine_foot_contact_plane(
    machine: str, *, asset_root: Path | None = None
) -> FootContactPlane:
    if machine not in {"30G", "50G"}:
        raise ValueError(f"unsupported PIMM machine: {machine}")
    root = ASSET_ROOT if asset_root is None else asset_root
    path = require_within(
        root / "manifests" / "patches" / f"PIMM-{machine}-foot-refresh.json",
        root / "manifests" / "patches",
    )
    if not path.is_file():
        raise FileNotFoundError(f"canonical foot patch is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"canonical foot patch is invalid JSON: {path}") from error
    if not isinstance(payload, Mapping):
        raise ValueError("canonical foot patch root must be an object")
    return resolve_foot_contact_plane(payload, machine)


def load_foot_contact_planes(
    config: ShotConfig, *, asset_root: Path | None = None
) -> dict[str, FootContactPlane]:
    """Load exact physical contact evidence for every machine in one shot."""

    _validate_shot_config(config)
    return {
        machine: _load_machine_foot_contact_plane(machine, asset_root=asset_root)
        for machine in config.machines
    }


def load_foot_contact_plane(config: ShotConfig) -> FootContactPlane:
    """Compatibility API for an exact single-machine physical contact plane."""

    return load_foot_contact_planes(config)[_single_machine(config)]


def load_workshop_support_records(
    config: ShotConfig,
) -> tuple[WorkshopSupportRecord, ...]:
    """Read and hash-verify every approved support for one workshop shot."""

    _validate_shot_config(config)
    if config.purpose != "workshop":
        raise ValueError("external workshop supports are valid only for workshop shots")
    manifest_path = require_within(
        ASSET_ROOT / "manifests" / "external-assets-v1.json",
        ASSET_ROOT / "manifests",
    )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"external asset manifest cannot be read: {manifest_path}: {error}"
        ) from error
    errors = validate_external_assets(payload, set(_CAMPAIGN.by_shot_id))
    if errors:
        raise ValueError("external asset manifest is invalid: " + "; ".join(errors))
    records: list[WorkshopSupportRecord] = []
    for record in payload["assets"]:
        if config.scene_id not in record["intended_shot_ids"]:
            continue
        relative = str(record["local_relative_path"])
        path = require_within(ASSET_ROOT / Path(relative), ASSET_ROOT / "assets")
        if not path.is_file():
            raise FileNotFoundError(f"approved workshop support is missing: {path}")
        expected = str(record["sha256"]).upper()
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(
                f"approved workshop support SHA-256 mismatch: expected {expected}, "
                f"found {actual}: {path}"
            )
        records.append(
            WorkshopSupportRecord(
                asset_version_id=str(record["asset_version_id"]),
                path=path,
                local_relative_path=relative,
                sha256=expected,
            )
        )
    return tuple(records)


def _workshop_product_like_error(obj: Any) -> str | None:
    if getattr(obj, "type", None) != "MESH":
        return None
    if any(
        obj.get(name) is not None
        for name in (
            "pimm_stable_id",
            "pimm_artwork_id",
            "pimm_machine",
            "pimm_asset_role",
            "pimm_product_material_override",
        )
    ):
        return f"product-like workshop support object is forbidden: {obj.name}"
    mesh = getattr(obj, "data", None)
    for material in getattr(mesh, "materials", ()) if mesh is not None else ():
        if (
            material.get("pimm_material_id") is not None
            or material.get("pimm_material_scope") in {"shared", "machine-local"}
        ):
            return (
                "product-like workshop support material is forbidden: "
                f"{material.name}"
            )
    return None


def load_workshop_support_assets(
    bpy: Any, config: ShotConfig
) -> tuple[WorkshopSupportRecord, ...]:
    """Append and tag only hash-verified non-product workshop support assets."""

    records = load_workshop_support_records(config)
    for record in records:
        before_collections = set(bpy.data.collections)
        before_objects = set(bpy.data.objects)
        before_meshes = set(bpy.data.meshes)
        before_materials = set(bpy.data.materials)
        try:
            with bpy.data.libraries.load(
                str(record.path), link=False, relative=False
            ) as (available, requested):
                if not available.collections:
                    raise ValueError(
                        f"approved workshop support contains no collections: {record.path}"
                    )
                requested.collections = list(available.collections)
            loaded_collections = [
                collection
                for collection in requested.collections
                if collection is not None
            ]
            loaded_objects = {
                obj
                for collection in loaded_collections
                for obj in getattr(collection, "all_objects", ())
            }
            mesh_objects = [
                obj for obj in loaded_objects if getattr(obj, "type", None) == "MESH"
            ]
            if not mesh_objects:
                raise ValueError(
                    f"approved workshop support contains no mesh props: {record.path}"
                )
            for obj in loaded_objects:
                product_error = _workshop_product_like_error(obj)
                if product_error:
                    raise ValueError(product_error)
            member_names = sorted(str(obj.name) for obj in mesh_objects)
            member_names_json = json.dumps(
                member_names,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            for collection in loaded_collections:
                collection["pimm_scene_support_ownership"] = "scene-support"
                collection["pimm_external_asset_version_id"] = record.asset_version_id
                collection["pimm_external_asset_member_count"] = len(member_names)
                collection["pimm_external_asset_member_names"] = member_names_json
                bpy.context.scene.collection.children.link(collection)
            for obj in loaded_objects:
                obj["pimm_scene_support_ownership"] = "scene-support"
                obj["pimm_scene_support_role"] = "workshop-prop"
                obj["pimm_external_asset_version_id"] = record.asset_version_id
                obj["pimm_external_asset_local_relative_path"] = (
                    record.local_relative_path
                )
                obj["pimm_external_asset_sha256"] = record.sha256
                mesh = getattr(obj, "data", None)
                if mesh is None:
                    continue
                obj["pimm_external_asset_member_count"] = len(member_names)
                obj["pimm_external_asset_member_names"] = member_names_json
                mesh["pimm_scene_support_ownership"] = "scene-support"
                mesh["pimm_scene_support_role"] = "workshop-prop"
                for material in getattr(mesh, "materials", ()):
                    material["pimm_scene_support_ownership"] = "scene-support"
                    material["pimm_scene_support_role"] = "workshop-prop"
        except Exception:
            for collection in list(set(bpy.data.collections) - before_collections):
                bpy.data.collections.remove(collection)
            for obj in list(set(bpy.data.objects) - before_objects):
                if getattr(obj, "users", 0) == 0:
                    bpy.data.objects.remove(obj)
            for mesh in list(set(bpy.data.meshes) - before_meshes):
                if getattr(mesh, "users", 0) == 0:
                    bpy.data.meshes.remove(mesh)
            for material in list(set(bpy.data.materials) - before_materials):
                if getattr(material, "users", 0) == 0:
                    bpy.data.materials.remove(material)
            raise
    return records


def foot_contact_evidence(
    machine: str, contact: FootContactPlane
) -> dict[str, object]:
    """Return the canonical four-foot payload shared by scenes and proof reports."""

    return {
        "schema_version": 1,
        "machine": machine,
        "selection_basis": "median_nylon_foot_pad_bottom",
        "patch_path": f"manifests/patches/PIMM-{machine}-foot-refresh.json",
        "contact_z": contact.z,
        "pad_bottoms": list(contact.pad_bottoms),
        "stable_ids": list(contact.stable_ids),
        "outlier_stable_ids": list(contact.outlier_stable_ids),
    }


def build_foot_contact_report(
    *,
    machine: str,
    contact: FootContactPlane,
    scene_id: str,
    scene_contract_sha256: str,
    master_sha256: str,
    patch_sha256: str,
) -> dict[str, object]:
    """Build the exact Task 4 report consumed by the proof-publication gate."""

    return {
        "schema": FOOT_CONTACT_REPORT_SCHEMA,
        "scene_id": scene_id,
        "scene_contract_sha256": scene_contract_sha256.upper(),
        "master_sha256": master_sha256.upper(),
        "patch_sha256": patch_sha256.upper(),
        "contact_evidence": foot_contact_evidence(machine, contact),
        "tolerance": FOOT_CONTACT_TOLERANCE,
        "passed": True,
    }


def _foot_contact_evidence(
    config: ShotConfig, contact: FootContactPlane
) -> dict[str, object]:
    """Compatibility wrapper for existing static-scene authoring callers."""

    return foot_contact_evidence(_single_machine(config), contact)


def _static_render_setup(config: ShotConfig) -> dict[str, object]:
    """Return the governed camera, color, world, and lighting contract."""

    light_specs = studio_light_specs((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    light_names = tuple(spec.name for spec in light_specs)
    if light_names != MANAGED_LIGHT_NAMES:
        raise ValueError("static product studio rig must retain the approved light arrangement")
    if any(spec.temperature_kelvin != DEFAULT_LIGHT_TEMPERATURE_KELVIN for spec in light_specs):
        raise ValueError("static product studio rig must retain 5500K lights")
    world = studio_world_environment_spec()
    hdri_path = world.path.relative_to(world.path.parents[2])
    if hdri_path != Path("assets") / "hdri" / "studio_kontrast_04_4k.exr":
        raise ValueError("static product world must retain the approved studio HDRI")
    return {
        "camera": {
            "aperture_fstop": config.aperture_fstop,
            "clip_end": STATIC_CAMERA_CLIP_END,
            "clip_start": STATIC_CAMERA_CLIP_START,
            "focal_length_mm": config.focal_length_mm,
            "sensor_width_mm": DEFAULT_SENSOR_WIDTH_MM,
            "view": config.view,
        },
        "color_management": {
            "exposure": DEFAULT_EXPOSURE,
            "gamma": 1.0,
            "look": DEFAULT_LOOK,
            "view_transform": "AgX",
        },
        "lighting": {
            "lower_bounce_name": "BASE_BOUNCE",
            "required_light_names": list(light_names),
            "temperature_kelvin": DEFAULT_LIGHT_TEMPERATURE_KELVIN,
        },
        "physical_shadow": {
            "catcher_name": "PIMM_SCENE_SHADOW_CATCHER",
            "gate": "required",
        },
        "world": {
            "hdri_path": hdri_path.as_posix(),
            "hdri_sha256": world.sha256,
            "rotation_degrees": world.rotation_degrees,
            "strength": world.strength,
        },
    }


def _validate_shot_config(config: ShotConfig) -> None:
    if config.animation_contract is not None:
        raise ValueError("static product scenes must not contain animation")
    if SHOT_CONFIGS.get(config.scene_id) != config:
        raise ValueError(f"unknown or altered static product shot: {config.scene_id}")


def _comparison_master_sha256(config: ShotConfig) -> str:
    """Bind both comparison masters through one deterministic contract digest."""

    rows = []
    for machine in config.machines:
        path = ASSET_ROOT / "masters" / f"PIMM-{machine}-MASTER.blend"
        rows.append(f"{machine}:{sha256_file(path)}")
    return hashlib.sha256(("\n".join(rows) + "\n").encode("ascii")).hexdigest().upper()


def contract_payload(config: ShotConfig) -> dict[str, object]:
    """Return the exact, hash-pinned SceneContract payload for *config*."""

    _validate_shot_config(config)
    master_path = (
        _master_path(config)
        if len(config.machines) == 1
        else ASSET_ROOT / "masters" / "PIMM-30G-MASTER.blend"
    )
    material_path = ASSET_ROOT / "masters" / "PIMM-MATERIAL-LIBRARY.blend"
    payload = {
        "animation_contract": None,
        "camera_name": "CAM_PRODUCT",
        "complete_product": True,
        "master_collection": MASTER_COLLECTION,
        "master_path": master_path.relative_to(ASSET_ROOT).as_posix(),
        "master_sha256": (
            sha256_file(master_path)
            if len(config.machines) == 1
            else _comparison_master_sha256(config)
        ),
        "material_library_path": material_path.relative_to(ASSET_ROOT).as_posix(),
        "material_library_sha256": sha256_file(material_path),
        "output_contract": {
            "alpha": config.alpha,
            "height": config.output_height,
            "width": config.output_width,
        },
        "purpose": config.purpose,
        "scene_id": config.scene_id,
        "scene_path": _scene_path(config).relative_to(ASSET_ROOT).as_posix(),
        "schema_version": 1,
        "static_render_setup": _static_render_setup(config),
    }
    if len(config.machines) == 1:
        payload["machine"] = config.machines[0]
    else:
        payload["machines"] = list(config.machines)
    return payload


def prepare_contract(config: ShotConfig) -> dict[str, object]:
    """Validate and create one new governed scene contract without overwriting it."""

    payload = contract_payload(config)
    contract = SceneContract.from_mapping(payload)
    errors = validate_scene_contract(contract)
    if errors:
        raise ValueError("invalid static product scene contract: " + "; ".join(errors))
    destination = require_within(_contract_path(config), ASSET_ROOT / "scenes" / "contracts")
    if destination.exists():
        raise FileExistsError(f"static product contract already exists: {destination}")
    atomic_write_json(destination, payload)
    return {"status": "contract_created", "path": str(destination), "payload": payload}


def _resolved_library_path(bpy: Any, datablock: Any) -> Path | None:
    library = getattr(datablock, "library", None)
    raw_path = getattr(library, "filepath", None) if library is not None else getattr(
        datablock, "filepath", None
    )
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path_api = getattr(bpy, "path", None)
    absolute = path_api.abspath(raw_path) if path_api is not None else raw_path
    return Path(absolute).resolve()


def _numeric_values_match(
    actual: Sequence[float], expected: Sequence[float], *, tolerance: float = 1e-6
) -> bool:
    return len(actual) == len(expected) and all(
        math.isclose(float(value), float(wanted), rel_tol=0.0, abs_tol=tolerance)
        for value, wanted in zip(actual, expected, strict=True)
    )


def _install_comparison_master_instances(
    bpy: Any, config: ShotConfig
) -> dict[str, FootContactPlane]:
    """Link both immutable masters once beneath exact scene-owned transforms."""

    if config.purpose != "comparison" or config.machines != ("30G", "50G"):
        raise ValueError("comparison instance authoring requires exact 30G/50G scope")
    existing = [
        obj
        for obj in bpy.context.scene.objects
        if getattr(obj, "instance_type", None) == "COLLECTION"
        or str(getattr(obj, "name", "")).startswith("PIMM_")
        and str(getattr(obj, "name", "")).endswith("_INSTANCE")
    ]
    if existing:
        raise ValueError("comparison source template must not contain product instances")
    contacts = load_foot_contact_planes(config)
    plan = comparison_link_plan(
        composition_for(config.scene_id),
        {machine: contact.z for machine, contact in contacts.items()},
    )
    for item, master_path in zip(plan, _master_paths(config), strict=True):
        if not master_path.is_file():
            raise FileNotFoundError(f"comparison master is missing: {master_path}")
        with bpy.data.libraries.load(
            str(master_path), link=True, relative=True
        ) as (available, requested):
            if MASTER_COLLECTION not in available.collections:
                raise ValueError(
                    f"comparison {item.machine} master lacks {MASTER_COLLECTION}"
                )
            requested.collections = [MASTER_COLLECTION]
        linked = requested.collections[0]
        if linked is None or not list(getattr(linked, "all_objects", ())):
            raise ValueError(
                f"comparison {item.machine} {MASTER_COLLECTION} is empty"
            )
        instance = bpy.data.objects.new(item.instance_name, None)
        instance.instance_type = "COLLECTION"
        instance.instance_collection = linked
        instance.location = (item.offset_x, item.offset_y, item.offset_z)
        instance.rotation_euler = (0.0, 0.0, 0.0)
        instance.scale = (item.scale, item.scale, item.scale)
        instance["pimm_comparison_machine"] = item.machine
        instance["pimm_scene_transform_ownership"] = "scene-owned"
        instance["pimm_source_contact_z"] = item.source_contact_z
        instance["pimm_resolved_ground_z"] = item.resolved_ground_z
        bpy.context.scene.collection.objects.link(instance)
    # Blender does not immediately evaluate linked objects' world matrices after
    # collection instances are added. Bounds queried before this update observe
    # identity-scale matrices instead of the masters' authored transforms.
    bpy.context.view_layer.update()
    return contacts


def _validate_open_template_authority(bpy: Any, config: ShotConfig) -> None:
    """Reject any template state outside the exact linked master/material authority."""

    expected_masters = {
        machine: path.resolve()
        for machine, path in zip(config.machines, _master_paths(config), strict=True)
    }
    expected_material = _material_library_path().resolve()
    library_paths = {
        path
        for path in (_resolved_library_path(bpy, library) for library in bpy.data.libraries)
        if path
    }
    expected_libraries = {*expected_masters.values(), expected_material}
    if library_paths != expected_libraries:
        raise ValueError(
            "shared template must link only the exact master(s) and material library: "
            f"found={sorted(str(path) for path in library_paths)}"
        )
    published_by_machine: dict[str, Any] = {}
    for machine, expected_master in expected_masters.items():
        published_candidates = [
            collection
            for collection in bpy.data.collections
            if str(getattr(collection, "name", "")).startswith(MASTER_COLLECTION)
            and _resolved_library_path(bpy, collection) == expected_master
        ]
        if len(published_candidates) != 1 or not list(
            published_candidates[0].all_objects
        ):
            raise ValueError(
                f"shared template must link exactly one nonempty {machine} PIMM_PUBLISHED"
            )
        published_by_machine[machine] = published_candidates[0]
    published_object_identities = {
        id(obj)
        for published in published_by_machine.values()
        for obj in published.all_objects
    }
    if config.purpose == "comparison":
        contacts = load_foot_contact_planes(config)
        plan = comparison_link_plan(
            composition_for(config.scene_id),
            {machine: contact.z for machine, contact in contacts.items()},
        )
        instances = {
            str(getattr(obj, "name", "")): obj
            for obj in bpy.context.scene.objects
            if getattr(obj, "instance_type", None) == "COLLECTION"
        }
        if set(instances) != {item.instance_name for item in plan}:
            raise ValueError("comparison scene must contain both unique managed instances")
        for item in plan:
            instance = instances[item.instance_name]
            expected_collection = published_by_machine[item.machine]
            if (
                getattr(instance, "instance_collection", None) is not expected_collection
                or not _numeric_values_match(
                    instance.location, (item.offset_x, item.offset_y, item.offset_z)
                )
                or not _numeric_values_match(instance.rotation_euler, (0.0, 0.0, 0.0))
                or not _numeric_values_match(instance.scale, (1.0, 1.0, 1.0))
                or instance.get("pimm_comparison_machine") != item.machine
                or instance.get("pimm_scene_transform_ownership") != "scene-owned"
                or not math.isclose(
                    float(instance.get("pimm_source_contact_z")),
                    item.source_contact_z,
                    rel_tol=0.0,
                    abs_tol=1e-6,
                )
                or not math.isclose(
                    float(instance.get("pimm_resolved_ground_z")),
                    item.resolved_ground_z,
                    rel_tol=0.0,
                    abs_tol=1e-6,
                )
            ):
                raise ValueError(
                    f"comparison {item.machine} instance transform or contact evidence drifted"
                )
    for obj in bpy.context.scene.objects:
        if getattr(obj, "type", None) != "MESH":
            continue
        if obj.get("pimm_scene_environment_role") is not None:
            continue
        origin = _resolved_library_path(bpy, obj)
        data_origin = _resolved_library_path(bpy, getattr(obj, "data", None))
        if origin not in expected_masters.values() or data_origin not in expected_masters.values():
            raise ValueError(f"scene-local product mesh is forbidden: {getattr(obj, 'name', '')}")
        if id(obj) not in published_object_identities:
            raise ValueError(f"product mesh is outside linked PIMM_PUBLISHED: {getattr(obj, 'name', '')}")
    for material in bpy.data.materials:
        if int(getattr(material, "users", 0)) <= 0:
            continue
        if material.get("pimm_scene_environment_role") is not None:
            continue
        origin = _resolved_library_path(bpy, material)
        if origin not in expected_libraries:
            raise ValueError(
                f"localized linked material is forbidden: {getattr(material, 'name', '')}"
            )


def inspect_target_candidates(bpy: Any, machine: str) -> dict[str, object]:
    """Return read-only stable-ID candidates from the exact linked machine master."""

    if machine not in {"30G", "50G"}:
        raise ValueError("target inspection machine must be 30G or 50G")
    representative = next(
        config for config in SHOT_CONFIGS.values() if config.machine == machine
    )
    source = Path(str(bpy.data.filepath)).resolve()
    if source != _template_path(representative).resolve():
        raise ValueError(f"open source scene does not match exact {machine} shared template: {source}")
    _validate_open_template_authority(bpy, representative)
    expected_master = _master_path(representative).resolve()
    candidates = []
    for obj in sorted(bpy.context.scene.objects, key=lambda item: str(getattr(item, "name", ""))):
        if (
            getattr(obj, "type", None) != "MESH"
            or _resolved_library_path(bpy, obj) != expected_master
        ):
            continue
        stable_id = obj.get("pimm_stable_id")
        if not isinstance(stable_id, str) or not stable_id.strip():
            continue
        candidates.append(
            {
                "stable_id": stable_id,
                "display_name": str(getattr(obj, "name", "")),
                "artwork_id": obj.get("pimm_artwork_id"),
            }
        )
    if not candidates:
        raise ValueError("shared template contains no stable target candidates")
    return {"status": "targets_inspected", "machine": machine, "candidates": candidates}


def _load_authoring_contract(config: ShotConfig) -> tuple[SceneContract, bytes]:
    path = _contract_path(config)
    try:
        contract_bytes = path.read_bytes()
        payload = json.loads(contract_bytes.decode("utf-8"))
        contract = SceneContract.from_mapping(payload)
    except (
        OSError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise ValueError(f"static product contract cannot be loaded: {path}: {error}") from error
    errors = validate_scene_contract(contract)
    if errors:
        raise ValueError("invalid static product scene contract: " + "; ".join(errors))
    expected = SceneContract.from_mapping(contract_payload(config))
    if contract.to_mapping() != expected.to_mapping():
        raise ValueError("static product scene contract does not match exact current asset hashes")
    return contract, contract_bytes


def _pinned_world_environment() -> Any:
    base = studio_world_environment_spec()
    return type(base)(
        path=ASSET_ROOT / "assets" / "hdri" / "studio_kontrast_04_4k.exr",
        sha256=base.sha256,
        strength=base.strength,
        rotation_degrees=base.rotation_degrees,
    )


def _require_pinned_hdri() -> Any:
    spec = _pinned_world_environment()
    path = require_within(spec.path, ASSET_ROOT / "assets" / "hdri")
    if not path.is_file():
        raise FileNotFoundError(f"studio HDRI is missing: {path}")
    actual_sha256 = sha256_file(path)
    if actual_sha256 != spec.sha256:
        raise ValueError(
            f"studio HDRI SHA-256 mismatch: expected {spec.sha256}, found {actual_sha256}"
        )
    return spec


def _ensure_product_camera(bpy: Any, contract: SceneContract) -> Any:
    camera = bpy.data.objects.get(contract.camera_name)
    if camera is not None and (
        getattr(camera, "type", None) != "CAMERA"
        or _resolved_library_path(bpy, camera) is not None
        or _resolved_library_path(bpy, getattr(camera, "data", None)) is not None
    ):
        raise ValueError("contracted product camera must be scene-local")
    if camera is None:
        camera_data = bpy.data.cameras.new(contract.camera_name)
        camera = bpy.data.objects.new(contract.camera_name, camera_data)
        bpy.context.scene.collection.objects.link(camera)
    for other in list(bpy.data.objects):
        if other is camera or getattr(other, "type", None) != "CAMERA":
            continue
        if _resolved_library_path(bpy, other) is not None or _resolved_library_path(
            bpy, getattr(other, "data", None)
        ) is not None:
            raise ValueError("shared template contains an unmanaged linked camera")
        other_data = getattr(other, "data", None)
        bpy.data.objects.remove(other, do_unlink=True)
        if other_data is not None and getattr(other_data, "users", 0) == 0:
            bpy.data.cameras.remove(other_data)
    bpy.context.scene.camera = camera
    return camera


def _target_evidence(config: ShotConfig, target: TargetResolution) -> dict[str, object]:
    return {
        "schema_version": 1,
        "scene_id": config.scene_id,
        "selection_basis": "pimm_stable_id",
        "groups": {name: list(values) for name, values in target.groups.items()},
        "stable_ids": list(target.stable_ids),
        "bounds_min": list(target.bounds_min),
        "bounds_max": list(target.bounds_max),
    }


def composition_evidence(
    config: ShotConfig, target: TargetResolution, pose: CameraPose
) -> dict[str, object]:
    """Serialize exact spatial authority for fresh-reopen camera validation."""

    composition = composition_for(config.scene_id)
    placement = composition.subject_placement
    protected = composition.protected_copy_rect
    return {
        "schema_version": 1,
        "shot_id": config.scene_id,
        "camera_view": composition.camera_view,
        "studio_profile": composition.studio_profile,
        "camera_azimuth_degrees": composition.camera_azimuth_degrees,
        "camera_elevation_degrees": composition.camera_elevation_degrees,
        "camera_location": list(pose.location),
        "camera_target": list(pose.target),
        "working_distance": math.dist(pose.location, pose.target),
        "minimum_working_distance_heights": (
            composition.minimum_working_distance_heights
        ),
        "target_bounds_min": list(target.bounds_min),
        "target_bounds_max": list(target.bounds_max),
        "subject_placement": {
            "center_x": placement.center_x,
            "center_y": placement.center_y,
            "clearance_left": placement.clearance_left,
            "clearance_right": placement.clearance_right,
            "clearance_top": placement.clearance_top,
            "clearance_bottom": placement.clearance_bottom,
        },
        "protected_copy_rect": (
            None
            if protected is None
            else {
                "left": protected.left,
                "top": protected.top,
                "right": protected.right,
                "bottom": protected.bottom,
            }
        ),
    }


def managed_output_path(config: ShotConfig) -> Path:
    """Return the only mutable proof-output prefix permitted during authoring."""

    _validate_shot_config(config)
    return (
        ASSET_ROOT
        / "renders"
        / "proofs"
        / "unapproved"
        / _CAMPAIGN.campaign_id
        / config.scene_id
        / config.scene_id
    ).resolve()


def _install_profile_supports(bpy: Any, specs: Sequence[SceneSupportSpec]) -> None:
    """Replace only scene-owned reflection/support geometry with exact finite meshes."""

    for obj in list(bpy.context.scene.objects):
        if getattr(obj, "library", None) is not None:
            continue
        if (
            obj.get("pimm_scene_environment_role") is None
            and obj.get("pimm_scene_support_role") != "reflection-card"
        ):
            continue
        mesh = getattr(obj, "data", None)
        materials = list(getattr(mesh, "materials", ())) if mesh is not None else []
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh is not None and getattr(mesh, "users", 0) == 0:
            bpy.data.meshes.remove(mesh)
        for material in materials:
            if material.users == 0:
                bpy.data.materials.remove(material)
    for spec in specs:
        mesh = bpy.data.meshes.new(spec.name)
        center_x, center_y, center_z = spec.center
        half_width = spec.width / 2.0
        half_depth = spec.depth / 2.0
        half_height = spec.height / 2.0
        if spec.role == "shadow-catcher":
            vertices = [
                (center_x - half_width, center_y - half_depth, center_z),
                (center_x + half_width, center_y - half_depth, center_z),
                (center_x + half_width, center_y + half_depth, center_z),
                (center_x - half_width, center_y + half_depth, center_z),
            ]
            faces = [(0, 1, 2, 3)]
            mesh["pimm_scene_environment_role"] = spec.role
        else:
            vertices = [
                (center_x + x, center_y + y, center_z + z)
                for x in (-half_width, half_width)
                for y in (-half_depth, half_depth)
                for z in (-half_height, half_height)
            ]
            faces = [
                (0, 1, 3, 2),
                (4, 6, 7, 5),
                (0, 4, 5, 1),
                (2, 3, 7, 6),
                (0, 2, 6, 4),
                (1, 5, 7, 3),
            ]
            mesh["pimm_scene_support_ownership"] = "scene-support"
            mesh["pimm_scene_support_role"] = spec.role
        mesh.from_pydata(vertices, [], faces)
        material = bpy.data.materials.new(f"{spec.name}_MATERIAL")
        material.use_nodes = True
        if spec.role == "shadow-catcher":
            material["pimm_material_id"] = "SCENE_SHADOW_CATCHER"
            material["pimm_scene_environment_role"] = spec.role
        else:
            material["pimm_scene_support_ownership"] = "scene-support"
            material["pimm_scene_support_role"] = spec.role
        material.diffuse_color = spec.base_color
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is None:
            raise ValueError(f"scene support material lacks Principled BSDF: {spec.name}")
        principled.inputs["Base Color"].default_value = spec.base_color
        principled.inputs["Roughness"].default_value = spec.roughness
        mesh.materials.append(material)
        obj = bpy.data.objects.new(spec.name, mesh)
        if spec.role == "shadow-catcher":
            obj["pimm_scene_environment_role"] = spec.role
            obj.is_shadow_catcher = True
        else:
            obj["pimm_scene_support_ownership"] = "scene-support"
            obj["pimm_scene_support_role"] = spec.role
        bpy.context.scene.collection.objects.link(obj)


def _configure_authored_scene(
    bpy: Any,
    config: ShotConfig,
    contract: SceneContract,
    contract_bytes: bytes,
    target: TargetResolution,
    world_environment: Any,
) -> tuple[Any, CameraPose]:
    scene = bpy.context.scene
    all_products = list(_stable_product_objects(bpy).values())
    product_bounds_min, product_bounds_max = bounds_for_objects(all_products)
    pose = camera_pose(target.bounds_min, target.bounds_max, config)
    camera = _ensure_product_camera(bpy, contract)
    camera.location = pose.location
    _point_at(camera, pose.target)
    camera.data.lens = config.focal_length_mm
    camera.data.sensor_fit = "HORIZONTAL"
    camera.data.sensor_width = DEFAULT_SENSOR_WIDTH_MM
    camera.data.clip_start = STATIC_CAMERA_CLIP_START
    camera.data.clip_end = STATIC_CAMERA_CLIP_END
    placement = composition_for(config.scene_id).subject_placement
    camera.data.shift_x = 0.5 - placement.center_x
    camera.data.shift_y = placement.center_y - 0.5
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = math.dist(pose.location, pose.target)
    camera.data.dof.aperture_fstop = config.aperture_fstop

    contacts = load_foot_contact_planes(config)
    if config.purpose == "comparison":
        link_plan = comparison_link_plan(
            composition_for(config.scene_id),
            {machine: contact.z for machine, contact in contacts.items()},
        )
        ground_z = link_plan[0].resolved_ground_z
    else:
        ground_z = contacts[_single_machine(config)].z
    lights, supports = profile_rig_specs(
        product_bounds_min, product_bounds_max, pose, config
    )
    supports = tuple(
        replace(spec, center=(spec.center[0], spec.center[1], ground_z))
        if spec.role == "shadow-catcher"
        else spec
        for spec in supports
    )
    _install_lights(bpy, lights)
    _install_profile_supports(bpy, supports)
    _install_world_environment(bpy, scene, world_environment)
    workshop_records = (
        load_workshop_support_assets(bpy, config)
        if config.purpose == "workshop"
        else ()
    )
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001
    scene.render.engine = "CYCLES"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = DEFAULT_LOOK
    scene.view_settings.exposure = DEFAULT_EXPOSURE
    scene.view_settings.gamma = 1.0
    scene.render.resolution_x = config.output_width
    scene.render.resolution_y = config.output_height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = config.alpha
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.filepath = str(managed_output_path(config))
    scene["pimm_scene_contract_payload"] = canonical_scene_contract_json(contract)
    scene["pimm_scene_contract_snapshot_sha256"] = hashlib.sha256(
        contract_bytes
    ).hexdigest().upper()
    scene["pimm_static_target_evidence"] = json.dumps(
        _target_evidence(config, target),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if config.purpose == "comparison":
        scene["pimm_comparison_contact_evidence"] = json.dumps(
            {
                machine: foot_contact_evidence(machine, contact)
                for machine, contact in contacts.items()
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    else:
        scene["pimm_foot_contact_evidence"] = json.dumps(
            _foot_contact_evidence(config, contacts[_single_machine(config)]),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    scene["pimm_shot_composition"] = json.dumps(
        composition_evidence(config, target, pose),
        separators=(",", ":"),
        sort_keys=True,
    )
    if config.purpose == "workshop":
        scene["pimm_workshop_support_evidence"] = json.dumps(
            [
                {
                    "asset_version_id": record.asset_version_id,
                    "local_relative_path": record.local_relative_path,
                    "sha256": record.sha256,
                }
                for record in workshop_records
            ],
            separators=(",", ":"),
            sort_keys=True,
        )
    return camera, pose


def _live_shadow_catcher_plane(bpy: Any) -> tuple[Any, float]:
    """Read the one local, untransformed plane from an already-open governed scene."""

    candidates = [
        obj
        for obj in bpy.context.scene.objects
        if getattr(obj, "type", None) == "MESH"
        and obj.get("pimm_scene_environment_role") == "shadow-catcher"
    ]
    if len(candidates) != 1:
        raise ValueError("scene must contain exactly one shadow-catcher mesh")
    catcher = candidates[0]
    if getattr(catcher, "library", None) is not None or getattr(
        catcher.data, "library", None
    ) is not None:
        raise ValueError("shadow-catcher must be scene-local")
    location = tuple(float(value) for value in catcher.location)
    rotation = tuple(float(value) for value in catcher.rotation_euler)
    scale = tuple(float(value) for value in catcher.scale)
    if any(abs(value) > 1e-9 for value in location + rotation) or any(
        abs(value - 1.0) > 1e-9 for value in scale
    ):
        raise ValueError("shadow-catcher must retain identity object transforms")
    vertices = list(catcher.data.vertices)
    if len(vertices) != 4:
        raise ValueError("shadow-catcher must retain its four-vertex studio plane")
    z_values = tuple(float(vertex.co.z) for vertex in vertices)
    current_z = float(median(z_values))
    if any(abs(value - current_z) > 1e-6 for value in z_values):
        raise ValueError("shadow-catcher vertices must remain coplanar")
    return catcher, current_z


def _contact_plane_state(bpy: Any, config: ShotConfig) -> tuple[Any, FootContactPlane, float]:
    """Return the one local planar catcher and its governed physical contact evidence."""

    source = Path(str(bpy.data.filepath)).resolve()
    expected = _scene_path(config).resolve()
    if source != expected:
        raise ValueError(f"open scene must equal governed static scene: {expected}")
    _validate_open_template_authority(bpy, config)
    catcher, current_z = _live_shadow_catcher_plane(bpy)
    return catcher, load_foot_contact_plane(config), current_z


def validate_live_foot_contact_report(
    bpy: Any,
    report: Mapping[str, object],
    *,
    scene_id: str,
    scene_contract_sha256: str,
    master_sha256: str,
) -> dict[str, object]:
    """Require an open Blender scene to carry the exact authenticated contact report."""

    if not isinstance(report, Mapping) or set(report) != _FOOT_CONTACT_REPORT_FIELDS:
        raise ValueError("live contact report has an invalid exact schema")
    if report.get("schema") != FOOT_CONTACT_REPORT_SCHEMA:
        raise ValueError("live contact report schema is unsupported")
    if report.get("scene_id") != scene_id:
        raise ValueError("live contact report scene ID does not match the open contract")
    if report.get("scene_contract_sha256") != scene_contract_sha256.upper():
        raise ValueError("live contact report scene-contract SHA-256 drifted")
    if report.get("master_sha256") != master_sha256.upper():
        raise ValueError("live contact report master SHA-256 drifted")
    if report.get("passed") is not True or report.get("tolerance") != FOOT_CONTACT_TOLERANCE:
        raise ValueError("live contact report tolerance or pass status is invalid")
    evidence = report.get("contact_evidence")
    if not isinstance(evidence, Mapping) or set(evidence) != _FOOT_CONTACT_EVIDENCE_FIELDS:
        raise ValueError("live contact report evidence has an invalid exact schema")
    machine = evidence.get("machine")
    stable_ids = evidence.get("stable_ids")
    pad_bottoms = evidence.get("pad_bottoms")
    outliers = evidence.get("outlier_stable_ids")
    contact_z = evidence.get("contact_z")
    if (
        machine not in {"30G", "50G"}
        or evidence.get("schema_version") != 1
        or evidence.get("selection_basis") != "median_nylon_foot_pad_bottom"
        or evidence.get("patch_path") != f"manifests/patches/PIMM-{machine}-foot-refresh.json"
        or not isinstance(stable_ids, list)
        or len(stable_ids) != 4
        or len(set(stable_ids)) != 4
        or not all(isinstance(value, str) and value for value in stable_ids)
        or not isinstance(pad_bottoms, list)
        or len(pad_bottoms) != 4
        or not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in pad_bottoms)
        or not isinstance(outliers, list)
        or not all(isinstance(value, str) and value in stable_ids for value in outliers)
        or not isinstance(contact_z, (int, float))
        or isinstance(contact_z, bool)
    ):
        raise ValueError("live contact report foot evidence is invalid")
    _catcher, current_z = _live_shadow_catcher_plane(bpy)
    if abs(current_z - float(contact_z)) > FOOT_CONTACT_TOLERANCE:
        raise ValueError("live shadow-catcher plane does not match the authenticated contact report")
    expected_embedded = json.dumps(
        dict(evidence), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    if bpy.context.scene.get("pimm_foot_contact_evidence") != expected_embedded:
        raise ValueError("live scene embedded foot-contact evidence is missing or altered")
    return {"contact_evidence": dict(evidence), "contact_plane_z": current_z}


def validate_contact_plane(bpy: Any, config: ShotConfig) -> dict[str, object]:
    """Fresh-process validation for one corrected static scene."""

    _catcher, contact, current_z = _contact_plane_state(bpy, config)
    if abs(current_z - contact.z) > 1e-6:
        raise ValueError(
            f"shadow-catcher contact height mismatch: expected {contact.z}, got {current_z}"
        )
    expected_evidence = json.dumps(
        _foot_contact_evidence(config, contact),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if bpy.context.scene.get("pimm_foot_contact_evidence") != expected_evidence:
        raise ValueError("scene foot-contact evidence is missing or altered")
    return {
        "status": "contact_plane_valid",
        "scene_id": config.scene_id,
        "path": str(_scene_path(config).resolve()),
        "contact_evidence": _foot_contact_evidence(config, contact),
    }


def correct_contact_plane(bpy: Any, config: ShotConfig) -> dict[str, object]:
    """Correct only the scene-owned catcher, preserving all governed product meshes."""

    catcher, contact, prior_z = _contact_plane_state(bpy, config)
    master_before = sha256_file(_master_path(config))
    material_before = sha256_file(_material_library_path())
    for vertex in catcher.data.vertices:
        vertex.co.z = contact.z
    bpy.context.scene["pimm_foot_contact_evidence"] = json.dumps(
        _foot_contact_evidence(config, contact),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    source = _scene_path(config).resolve()
    bpy.ops.wm.save_as_mainfile(filepath=str(source), check_existing=False)
    if sha256_file(_master_path(config)) != master_before:
        raise RuntimeError("authoritative master changed during contact-plane correction")
    if sha256_file(_material_library_path()) != material_before:
        raise RuntimeError("material library changed during contact-plane correction")
    return {
        "status": "contact_plane_corrected",
        "scene_id": config.scene_id,
        "path": str(source),
        "prior_z": prior_z,
        "contact_evidence": _foot_contact_evidence(config, contact),
    }


def _camera_optics_match(camera_data: Any, config: ShotConfig) -> bool:
    """Compare Blender float-backed camera values at storage precision."""

    placement = composition_for(config.scene_id).subject_placement
    expected = (
        config.focal_length_mm,
        DEFAULT_SENSOR_WIDTH_MM,
        config.aperture_fstop,
        0.5 - placement.center_x,
        placement.center_y - 0.5,
    )
    actual = (
        camera_data.lens,
        camera_data.sensor_width,
        camera_data.dof.aperture_fstop,
        camera_data.shift_x,
        camera_data.shift_y,
    )
    return all(
        math.isclose(float(value), float(wanted), rel_tol=0.0, abs_tol=1e-6)
        for value, wanted in zip(actual, expected, strict=True)
    )


def _validate_authored_scene_state(
    bpy: Any,
    config: ShotConfig,
    contract: SceneContract,
    target: TargetResolution,
    camera: Any,
    pose: CameraPose,
) -> None:
    scene = bpy.context.scene
    errors: list[str] = []
    if scene.camera is not camera or getattr(camera, "name", None) != contract.camera_name:
        errors.append("contracted CAM_PRODUCT must be active")
    camera_data = getattr(camera, "data", None)
    placement = composition_for(config.scene_id).subject_placement
    if camera_data is None or not _camera_optics_match(camera_data, config):
        errors.append("camera optics do not match the governed static shot")
    if camera_data is not None and camera_data.clip_start != STATIC_CAMERA_CLIP_START:
        errors.append("static product camera near clip must equal 1 scene unit")
    if camera_data is not None and camera_data.clip_end != STATIC_CAMERA_CLIP_END:
        errors.append("static product camera far clip must equal 10000 scene units")
    try:
        depth_min, depth_max = stable_geometry_camera_depth_range(bpy, pose)
        if camera_data is not None and (
            depth_min <= camera_data.clip_start or depth_max >= camera_data.clip_end
        ):
            errors.append(
                "stable product geometry lies outside the governed camera clip range "
                f"(depth_min={depth_min}, depth_max={depth_max}, "
                f"clip_start={camera_data.clip_start}, clip_end={camera_data.clip_end}, "
                f"target_bounds_min={target.bounds_min}, target_bounds_max={target.bounds_max}, "
                f"camera_location={pose.location})"
            )
    except ValueError as error:
        errors.append(str(error))
    view = scene.view_settings
    if (
        view.view_transform != "AgX"
        or view.look != DEFAULT_LOOK
        or view.exposure != DEFAULT_EXPOSURE
        or view.gamma != 1.0
    ):
        errors.append("scene exposure and AgX settings do not match the governed setup")
    render = scene.render
    if (
        render.engine != "CYCLES"
        or render.resolution_x != config.output_width
        or render.resolution_y != config.output_height
        or render.resolution_percentage != 100
        or render.film_transparent is not config.alpha
        or Path(str(render.filepath)).resolve() != managed_output_path(config)
    ):
        errors.append("Cycles output settings do not match the governed static shot")
    if render.use_border is not False or render.use_crop_to_border is not False:
        errors.append("render crop must be disabled for the contracted frame")
    try:
        coordinates = frame_coordinates(target.bounds_min, target.bounds_max, pose, config)
        if any(
            x < placement.clearance_left
            or x > 1.0 - placement.clearance_right
            or y < placement.clearance_top
            or y > 1.0 - placement.clearance_bottom
            for x, y in coordinates
        ):
            errors.append("stable target crop lies outside the contracted frame")
    except ValueError:
        errors.append("stable target crop lies outside the contracted frame")
    expected_evidence = json.dumps(
        _target_evidence(config, target),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if scene.get("pimm_static_target_evidence") != expected_evidence:
        errors.append("stable target contract evidence is missing or altered")
    if errors:
        raise ValueError("invalid authored static product scene: " + "; ".join(errors))


def author_scene(
    bpy: Any, config: ShotConfig, target_manifest: ValidatedTargetManifest
) -> dict[str, object]:
    """Author and fresh-process validate one new governed static product scene."""

    _validate_shot_config(config)
    _validated_target_manifest_payload(target_manifest)
    source = Path(str(bpy.data.filepath)).resolve()
    expected_source = _template_path(config).resolve()
    if source != expected_source:
        raise ValueError(f"open source scene must equal exact shared template: {expected_source}")
    destination = require_within(_scene_path(config), ASSET_ROOT / "scenes" / "stills")
    if destination.exists():
        raise FileExistsError(f"static product scene already exists: {destination}")
    contract, contract_bytes = _load_authoring_contract(config)
    if config.purpose == "comparison":
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"
        bpy.context.scene.unit_settings.scale_length = 0.001
        _install_comparison_master_instances(bpy, config)
    _validate_open_template_authority(bpy, config)
    world_environment = _require_pinned_hdri()
    target = resolve_target_bounds(bpy, config, target_manifest)
    camera, pose = _configure_authored_scene(
        bpy, config, contract, contract_bytes, target, world_environment
    )
    _validate_authored_scene_state(bpy, config, contract, target, camera, pose)

    master_before = {
        path.resolve(): sha256_file(path)
        for path in _master_paths(config)
    }
    material_before = sha256_file(_material_library_path())
    destination.parent.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    temporary = destination.with_name(f".{destination.stem}.{nonce}.tmp.blend")
    contract_snapshot = destination.with_name(
        f".{destination.stem}.{nonce}.contract.json"
    )
    contract_sha256 = hashlib.sha256(contract_bytes).hexdigest().upper()
    try:
        with contract_snapshot.open("xb") as snapshot:
            snapshot.write(contract_bytes)
            snapshot.flush()
            os.fsync(snapshot.fileno())
        contract_snapshot.chmod(stat.S_IREAD)
        bpy.ops.wm.save_as_mainfile(filepath=str(temporary), check_existing=False)
        if not temporary.is_file():
            raise RuntimeError("Blender did not create the temporary static product scene")
        validation_errors = _run_fresh_validation(temporary, contract_snapshot)
        master_after = {
            path.resolve(): sha256_file(path)
            for path in _master_paths(config)
        }
        material_after = sha256_file(_material_library_path())
        if master_after != master_before or material_after != material_before:
            validation_errors.append("scene authoring changed a protected library fingerprint")
        if sha256_file(contract_snapshot) != contract_sha256:
            validation_errors.append("immutable scene contract snapshot changed during validation")
        try:
            original_contract_unchanged = (
                sha256_file(_contract_path(config)) == contract_sha256
            )
        except OSError:
            original_contract_unchanged = False
        if not original_contract_unchanged:
            validation_errors.append("original scene contract changed during authoring")
        if validation_errors:
            raise ValueError(
                "fresh Blender scene validation failed: " + "; ".join(validation_errors)
            )
        if destination.exists():
            raise FileExistsError(f"static product scene already exists: {destination}")
        temporary.rename(destination)
    finally:
        if temporary.is_file():
            temporary.unlink()
        if contract_snapshot.is_file():
            contract_snapshot.chmod(stat.S_IWRITE)
            contract_snapshot.unlink()
    return {
        "status": "scene_created",
        "machines": list(config.machines),
        "scene_id": config.scene_id,
        "path": str(destination),
        "camera": {
            "location": list(pose.location),
            "target": list(pose.target),
            "focal_length_mm": config.focal_length_mm,
            "aperture_fstop": config.aperture_fstop,
        },
        "target_evidence": _target_evidence(config, target),
    }


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shot-id", choices=sorted(SHOT_CONFIGS), required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare-contract", action="store_true")
    modes.add_argument("--inspect-targets", action="store_true")
    modes.add_argument("--author-scene", action="store_true")
    modes.add_argument("--correct-contact-plane", action="store_true")
    modes.add_argument("--validate-contact-plane", action="store_true")
    parser.add_argument("--target-manifest", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.author_scene and arguments.target_manifest is None:
        parser.error("--author-scene requires --target-manifest")
    if not arguments.author_scene and arguments.target_manifest is not None:
        parser.error("--target-manifest is valid only with --author-scene")
    if arguments.author_scene:
        canonical = _target_manifest_path().resolve()
        try:
            supplied = require_within(arguments.target_manifest, ASSET_ROOT / "manifests")
        except ValueError:
            parser.error(f"--target-manifest must equal canonical target manifest: {canonical}")
        if supplied != canonical:
            parser.error(f"--target-manifest must equal canonical target manifest: {canonical}")
        arguments.target_manifest = canonical
    return arguments


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else sys.argv[1:]
    )
    config = SHOT_CONFIGS[arguments.shot_id]
    if arguments.prepare_contract:
        result = prepare_contract(config)
    else:
        import bpy

        if arguments.inspect_targets:
            result = inspect_target_candidates(bpy, config.machine)
        elif arguments.correct_contact_plane:
            result = correct_contact_plane(bpy, config)
        elif arguments.validate_contact_plane:
            result = validate_contact_plane(bpy, config)
        else:
            target_manifest = load_target_manifest(arguments.target_manifest)
            result = author_scene(bpy, config, target_manifest)
    print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
    if not arguments.prepare_contract:
        os._exit(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
