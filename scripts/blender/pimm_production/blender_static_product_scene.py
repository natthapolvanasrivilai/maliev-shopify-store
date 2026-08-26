"""Define fail-closed contract payloads for governed PIMM static product scenes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Sequence

try:
    from .blender_static_hero_scene import (
        DEFAULT_EXPOSURE,
        DEFAULT_LIGHT_TEMPERATURE_KELVIN,
        DEFAULT_LOOK,
        DEFAULT_SENSOR_WIDTH_MM,
        studio_light_specs,
        studio_world_environment_spec,
    )
    from .io_contract import atomic_write_json, sha256_file
    from .paths import ASSET_ROOT, require_within
    from .scene_contract import SceneContract, validate_scene_contract
except ImportError:  # Blender executes checked-in scripts outside package mode.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production.blender_static_hero_scene import (
        DEFAULT_EXPOSURE,
        DEFAULT_LIGHT_TEMPERATURE_KELVIN,
        DEFAULT_LOOK,
        DEFAULT_SENSOR_WIDTH_MM,
        studio_light_specs,
        studio_world_environment_spec,
    )
    from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
    from scripts.blender.pimm_production.scene_contract import SceneContract, validate_scene_contract


RESULT_MARKER = "PIMM_STATIC_PRODUCT_SCENE_JSON="
MASTER_COLLECTION = "PIMM_PUBLISHED"
OUTPUT_WIDTH = 2400
OUTPUT_HEIGHT = 1800
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


def _contract_path(config: ShotConfig) -> Path:
    return ASSET_ROOT / "scenes" / "contracts" / f"{config.scene_id}.json"


def _scene_path(config: ShotConfig) -> Path:
    return ASSET_ROOT / "scenes" / "stills" / f"{config.scene_id}.blend"


def _master_path(config: ShotConfig) -> Path:
    return ASSET_ROOT / "masters" / f"PIMM-{config.machine}-MASTER.blend"


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


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shot-id", choices=sorted(SHOT_CONFIGS), required=True)
    parser.add_argument("--prepare-contract", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else sys.argv[1:]
    )
    config = SHOT_CONFIGS[arguments.shot_id]
    if not arguments.prepare_contract:
        raise ValueError("static product scene authoring is not available in this contract slice")
    result = prepare_contract(config)
    print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
