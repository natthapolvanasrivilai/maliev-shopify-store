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
    from .blender_scene_template import _run_fresh_validation
    from .io_contract import atomic_write_json, sha256_file
    from .paths import ASSET_ROOT, require_within
    from .scene_contract import (
        SceneContract,
        canonical_scene_contract_json,
        validate_scene_contract,
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
    from scripts.blender.pimm_production.blender_scene_template import _run_fresh_validation
    from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
    from scripts.blender.pimm_production.scene_contract import (
        SceneContract,
        canonical_scene_contract_json,
        validate_scene_contract,
    )


RESULT_MARKER = "PIMM_STATIC_PRODUCT_SCENE_JSON="
MASTER_COLLECTION = "PIMM_PUBLISHED"
OUTPUT_WIDTH = 2400
OUTPUT_HEIGHT = 1800
STATIC_CAMERA_CLIP_START = 1.0
STATIC_CAMERA_CLIP_END = 10000.0
CAMERA_DISTANCE_MULTIPLIER_BY_PURPOSE = {
    "overview": 1.25,
    "engineering": 1.0,
    "tooling": 1.25,
}
_ALLOWED_FOCAL_LENGTHS = {85.0, 135.0}
_REQUIRED_LIGHT_NAMES = (
    "KEY_SOFTBOX",
    "FILL_SOFTBOX",
    "BASE_BOUNCE",
    "STRIP_LEFT",
    "STRIP_RIGHT",
)


@dataclass(frozen=True)
class ShotConfig:
    """Immutable camera and output requirements for one static PIMM still."""

    scene_id: str
    machine: str
    purpose: str
    view: str
    focal_length_mm: float
    aperture_fstop: float
    output_width: int = OUTPUT_WIDTH
    output_height: int = OUTPUT_HEIGHT
    animation_contract: None = None


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
    tolerance = 1e-6
    outliers = tuple(
        stable_id
        for stable_id, bottom in zip(stable_ids, bottoms, strict=True)
        if abs(bottom - contact_z) > tolerance
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


SHOT_CONFIGS = {
    shot.scene_id: shot
    for shot in (
        ShotConfig("pimm-30g--overview--three-quarter", "30G", "overview", "three-quarter", 85.0, 11.0),
        ShotConfig("pimm-30g--engineering--controls", "30G", "engineering", "controls", 135.0, 8.0),
        ShotConfig("pimm-30g--tooling--front-detail", "30G", "tooling", "front-detail", 135.0, 11.0),
        ShotConfig("pimm-50g--overview--three-quarter", "50G", "overview", "three-quarter", 85.0, 11.0),
        ShotConfig("pimm-50g--engineering--controls", "50G", "engineering", "controls", 135.0, 8.0),
        ShotConfig("pimm-50g--tooling--front-detail", "50G", "tooling", "front-detail", 135.0, 11.0),
    )
}

_DETAIL_TARGET_GROUPS = {
    "engineering": ("gauge", "regulator", "controller", "actuator_artwork"),
    "tooling": ("nozzle", "platen", "fixture"),
}
_FRAME_MARGIN = 0.05


def _target_manifest_path() -> Path:
    return ASSET_ROOT / "manifests" / "PIMM-static-shot-targets-v1.json"


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
    detail_configs = [config for config in SHOT_CONFIGS.values() if config.purpose != "overview"]
    if set(shots) != {config.scene_id for config in detail_configs}:
        raise ValueError("target manifest shots must exactly match the governed detail shots")
    for config in detail_configs:
        shot = shots[config.scene_id]
        if not isinstance(shot, dict) or set(shot) != {"groups"}:
            raise ValueError(f"target manifest {config.scene_id} must contain exactly groups")
        groups = shot["groups"]
        expected_groups = _DETAIL_TARGET_GROUPS[config.purpose]
        if not isinstance(groups, dict) or set(groups) != set(expected_groups):
            raise ValueError(
                f"target manifest {config.scene_id} groups must equal {list(expected_groups)}"
            )
        for group_name in expected_groups:
            identifiers = groups[group_name]
            if (
                not isinstance(identifiers, list)
                or not identifiers
                or not all(
                    isinstance(identifier, str) and identifier == identifier.strip() and identifier
                    for identifier in identifiers
                )
                or len(set(identifiers)) != len(identifiers)
            ):
                raise ValueError(
                    f"target manifest {config.scene_id} {group_name} must be a nonempty stable-ID list"
                )
    return payload


def load_target_manifest(path: Path) -> ValidatedTargetManifest:
    """Load only the canonical v1 stable-ID target manifest and validate every shot."""

    canonical_root = ASSET_ROOT / "manifests"
    try:
        resolved = require_within(Path(path), canonical_root)
    except ValueError as error:
        raise ValueError(f"canonical target manifest path is required: {path}") from error
    canonical = _target_manifest_path().resolve()
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
) -> dict[str, object]:
    if not isinstance(manifest, ValidatedTargetManifest):
        raise ValueError("authoring requires a validated canonical target manifest")
    refreshed = load_target_manifest(manifest.path)
    if refreshed != manifest:
        raise ValueError("validated canonical target manifest changed after loading")
    payload = json.loads(manifest.canonical_json)
    return _validate_target_manifest_payload(payload)


def _stable_product_objects(bpy: Any) -> dict[str, Any]:
    by_stable_id: dict[str, Any] = {}
    for obj in bpy.context.scene.objects:
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
    bpy: Any, config: ShotConfig, target_manifest: ValidatedTargetManifest
) -> TargetResolution:
    """Resolve overview or semantic detail bounds without using display names."""

    _validate_shot_config(config)
    target_payload = _validated_target_manifest_payload(target_manifest)
    by_stable_id = _stable_product_objects(bpy)
    if config.purpose == "overview":
        stable_ids = tuple(sorted(by_stable_id))
        groups = {"complete_product": stable_ids}
    else:
        shots = target_payload["shots"]
        shot = shots.get(config.scene_id) if isinstance(shots, dict) else None
        source_groups = shot.get("groups") if isinstance(shot, dict) else None
        expected_groups = _DETAIL_TARGET_GROUPS[config.purpose]
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
            if "actuator_artwork" in missing_by_group:
                raise ValueError(
                    "missing artwork target stable IDs: "
                    + ", ".join(missing_by_group["actuator_artwork"])
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
    projected: list[tuple[float, float]] = []
    for corner in _bounds_corners(bounds_min, bounds_max):
        relative = _subtract(corner, pose.location)
        depth = _dot(relative, forward)
        if depth <= 0:
            raise ValueError("contracted target lies behind the camera")
        projected.append(
            (
                0.5 + _dot(relative, right) / (2.0 * depth * horizontal_tangent),
                0.5 + _dot(relative, up) / (2.0 * depth * vertical_tangent),
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
    azimuth = -24.0 if config.purpose == "overview" else 0.0
    unit_pose = orbit_camera_pose(bounds_min, bounds_max, 1.0, azimuth, 0.0)
    right, up, forward = _camera_basis(unit_pose)
    horizontal_tangent = DEFAULT_SENSOR_WIDTH_MM / (2.0 * config.focal_length_mm)
    sensor_height = DEFAULT_SENSOR_WIDTH_MM * config.output_height / config.output_width
    vertical_tangent = sensor_height / (2.0 * config.focal_length_mm)
    usable_half_frame = 0.5 - _FRAME_MARGIN
    distance = 1.0
    for corner in _bounds_corners(bounds_min, bounds_max):
        offset = _subtract(corner, center)
        along = _dot(offset, forward)
        distance = max(
            distance,
            abs(_dot(offset, right)) / (2.0 * usable_half_frame * horizontal_tangent)
            - along,
            abs(_dot(offset, up)) / (2.0 * usable_half_frame * vertical_tangent)
            - along,
        )
    distance *= 1.001
    distance *= CAMERA_DISTANCE_MULTIPLIER_BY_PURPOSE[config.purpose]
    return orbit_camera_pose(bounds_min, bounds_max, distance, azimuth, 0.0)


def _contract_path(config: ShotConfig) -> Path:
    return ASSET_ROOT / "scenes" / "contracts" / f"{config.scene_id}.json"


def _scene_path(config: ShotConfig) -> Path:
    return ASSET_ROOT / "scenes" / "stills" / f"{config.scene_id}.blend"


def _master_path(config: ShotConfig) -> Path:
    return ASSET_ROOT / "masters" / f"PIMM-{config.machine}-MASTER.blend"


def _template_path(config: ShotConfig) -> Path:
    return (
        ASSET_ROOT
        / "scenes"
        / "shared-templates"
        / f"pimm-{config.machine.lower()}--hero--three-quarter.blend"
    )


def _material_library_path() -> Path:
    return ASSET_ROOT / "masters" / "PIMM-MATERIAL-LIBRARY.blend"


def _foot_patch_path(config: ShotConfig) -> Path:
    return (
        ASSET_ROOT
        / "manifests"
        / "patches"
        / f"PIMM-{config.machine}-foot-refresh.json"
    )


def load_foot_contact_plane(config: ShotConfig) -> FootContactPlane:
    """Load the canonical, machine-specific foot evidence for studio grounding."""

    path = require_within(
        _foot_patch_path(config), ASSET_ROOT / "manifests" / "patches"
    )
    if not path.is_file():
        raise FileNotFoundError(f"canonical foot patch is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"canonical foot patch is invalid JSON: {path}") from error
    if not isinstance(payload, Mapping):
        raise ValueError("canonical foot patch root must be an object")
    return resolve_foot_contact_plane(payload, config.machine)


def _foot_contact_evidence(
    config: ShotConfig, contact: FootContactPlane
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "machine": config.machine,
        "selection_basis": "median_nylon_foot_pad_bottom",
        "patch_path": _foot_patch_path(config).relative_to(ASSET_ROOT).as_posix(),
        "contact_z": contact.z,
        "pad_bottoms": list(contact.pad_bottoms),
        "stable_ids": list(contact.stable_ids),
        "outlier_stable_ids": list(contact.outlier_stable_ids),
    }


def _static_render_setup(config: ShotConfig) -> dict[str, object]:
    """Return the governed camera, color, world, and lighting contract."""

    light_specs = studio_light_specs((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    light_names = tuple(spec.name for spec in light_specs)
    if light_names != _REQUIRED_LIGHT_NAMES:
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
            "gate": "not-applicable" if config.purpose == "engineering" else "required",
        },
        "world": {
            "hdri_path": hdri_path.as_posix(),
            "hdri_sha256": world.sha256,
            "rotation_degrees": world.rotation_degrees,
            "strength": world.strength,
        },
    }


def _validate_shot_config(config: ShotConfig) -> None:
    if config.machine not in {"30G", "50G"}:
        raise ValueError("static product shot machine must be 30G or 50G")
    if config.focal_length_mm not in _ALLOWED_FOCAL_LENGTHS:
        raise ValueError("static product shot focal length must be 85mm or 135mm")
    if config.animation_contract is not None:
        raise ValueError("static product scenes must not contain animation")
    if (config.output_width, config.output_height) != (OUTPUT_WIDTH, OUTPUT_HEIGHT):
        raise ValueError("static product output must be 2400 x 1800")
    if SHOT_CONFIGS.get(config.scene_id) != config:
        raise ValueError(f"unknown or altered static product shot: {config.scene_id}")


def contract_payload(config: ShotConfig) -> dict[str, object]:
    """Return the exact, hash-pinned SceneContract payload for *config*."""

    _validate_shot_config(config)
    master_path = _master_path(config)
    material_path = ASSET_ROOT / "masters" / "PIMM-MATERIAL-LIBRARY.blend"
    return {
        "animation_contract": None,
        "camera_name": "CAM_PRODUCT",
        "complete_product": True,
        "machine": config.machine,
        "master_collection": MASTER_COLLECTION,
        "master_path": master_path.relative_to(ASSET_ROOT).as_posix(),
        "master_sha256": sha256_file(master_path),
        "material_library_path": material_path.relative_to(ASSET_ROOT).as_posix(),
        "material_library_sha256": sha256_file(material_path),
        "output_contract": {
            "alpha": True,
            "height": config.output_height,
            "width": config.output_width,
        },
        "purpose": config.purpose,
        "scene_id": config.scene_id,
        "scene_path": _scene_path(config).relative_to(ASSET_ROOT).as_posix(),
        "schema_version": 1,
        "static_render_setup": _static_render_setup(config),
    }


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


def _validate_open_template_authority(bpy: Any, config: ShotConfig) -> None:
    """Reject any template state outside the exact linked master/material authority."""

    expected_master = _master_path(config).resolve()
    expected_material = _material_library_path().resolve()
    library_paths = {
        path
        for path in (_resolved_library_path(bpy, library) for library in bpy.data.libraries)
        if path
    }
    if library_paths != {expected_master, expected_material}:
        raise ValueError(
            "shared template must link only the exact master and material library: "
            f"found={sorted(str(path) for path in library_paths)}"
        )
    published_candidates = [
        collection
        for collection in bpy.data.collections
        if getattr(collection, "name", None) == MASTER_COLLECTION
        and _resolved_library_path(bpy, collection) == expected_master
    ]
    if len(published_candidates) != 1 or not list(published_candidates[0].all_objects):
        raise ValueError("shared template must link exactly one nonempty PIMM_PUBLISHED")
    published_object_identities = {id(obj) for obj in published_candidates[0].all_objects}
    for obj in bpy.context.scene.objects:
        if getattr(obj, "type", None) != "MESH":
            continue
        if obj.get("pimm_scene_environment_role") is not None:
            continue
        if _resolved_library_path(bpy, obj) != expected_master or _resolved_library_path(
            bpy, getattr(obj, "data", None)
        ) != expected_master:
            raise ValueError(f"scene-local product mesh is forbidden: {getattr(obj, 'name', '')}")
        if id(obj) not in published_object_identities:
            raise ValueError(f"product mesh is outside linked PIMM_PUBLISHED: {getattr(obj, 'name', '')}")
    for material in bpy.data.materials:
        if int(getattr(material, "users", 0)) <= 0:
            continue
        if material.get("pimm_scene_environment_role") is not None:
            continue
        origin = _resolved_library_path(bpy, material)
        if origin not in {expected_master, expected_material}:
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
    expected = contract_payload(config)
    if contract.to_mapping() != expected:
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
    camera.data.shift_x = 0.0
    camera.data.shift_y = 0.0
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = math.dist(pose.location, pose.target)
    camera.data.dof.aperture_fstop = config.aperture_fstop

    foot_contact = load_foot_contact_plane(config)
    _install_lights(bpy, studio_light_specs(product_bounds_min, product_bounds_max))
    _install_environment(
        bpy,
        contact_environment_specs(
            studio_environment_specs(product_bounds_min, product_bounds_max),
            foot_contact.z,
        ),
    )
    _install_world_environment(bpy, scene, world_environment)
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
    scene.render.film_transparent = True
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.filepath = str(
        (ASSET_ROOT / "renders" / "proofs" / "unapproved" / config.scene_id).resolve()
    )
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
    scene["pimm_foot_contact_evidence"] = json.dumps(
        _foot_contact_evidence(config, foot_contact),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return camera, pose


def _contact_plane_state(bpy: Any, config: ShotConfig) -> tuple[Any, FootContactPlane, float]:
    """Return the one local planar catcher and its governed physical contact evidence."""

    source = Path(str(bpy.data.filepath)).resolve()
    expected = _scene_path(config).resolve()
    if source != expected:
        raise ValueError(f"open scene must equal governed static scene: {expected}")
    _validate_open_template_authority(bpy, config)
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
    return catcher, load_foot_contact_plane(config), current_z


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
    if (
        camera_data is None
        or camera_data.lens != config.focal_length_mm
        or camera_data.sensor_width != DEFAULT_SENSOR_WIDTH_MM
        or camera_data.dof.aperture_fstop != config.aperture_fstop
    ):
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
                "stable product geometry lies outside the governed camera clip range"
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
        or render.film_transparent is not True
    ):
        errors.append("Cycles output settings do not match the governed static shot")
    if render.use_border is not False or render.use_crop_to_border is not False:
        errors.append("render crop must be disabled for the contracted frame")
    try:
        coordinates = frame_coordinates(target.bounds_min, target.bounds_max, pose, config)
        if any(
            x < _FRAME_MARGIN
            or x > 1.0 - _FRAME_MARGIN
            or y < _FRAME_MARGIN
            or y > 1.0 - _FRAME_MARGIN
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
    _validate_open_template_authority(bpy, config)
    world_environment = _require_pinned_hdri()
    target = resolve_target_bounds(bpy, config, target_manifest)
    camera, pose = _configure_authored_scene(
        bpy, config, contract, contract_bytes, target, world_environment
    )
    _validate_authored_scene_state(bpy, config, contract, target, camera, pose)

    master_before = sha256_file(_master_path(config))
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
        master_after = sha256_file(_master_path(config))
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
        "machine": config.machine,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
