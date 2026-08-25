"""Author deterministic linked straight-on PIMM static hero scenes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Sequence

try:
    from .io_contract import atomic_write_json, sha256_file
    from .paths import ASSET_ROOT, require_within
    from .scene_contract import SceneContract, canonical_scene_contract_json, validate_scene_contract
except ImportError:  # Blender executes checked-in scripts outside package mode.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
    from scripts.blender.pimm_production.scene_contract import (
        SceneContract,
        canonical_scene_contract_json,
        validate_scene_contract,
    )


RESULT_MARKER = "PIMM_STATIC_HERO_JSON="
DEFAULT_EXPOSURE = 3.5
DEFAULT_WORLD_STRENGTH = 3.0
DEFAULT_PITCH_DEGREES = 2.5
DEFAULT_LOOK = "AgX - Medium High Contrast"
DEFAULT_FOCAL_LENGTH_MM = 85.0


@dataclass(frozen=True)
class MachineConfig:
    machine: str
    scene_id: str
    source_path: Path
    output_path: Path
    contract_path: Path
    master_path: Path
    output_width: int = 1800
    output_height: int = 2200


@dataclass(frozen=True)
class CameraPose:
    location: tuple[float, float, float]
    target: tuple[float, float, float]
    pitch_degrees: float


@dataclass(frozen=True)
class LightSpec:
    name: str
    location: tuple[float, float, float]
    energy: float
    size: float


MACHINE_CONFIGS = {
    machine: MachineConfig(
        machine=machine,
        scene_id=f"pimm-{machine.lower()}--hero--front",
        source_path=ASSET_ROOT
        / "scenes"
        / "shared-templates"
        / f"pimm-{machine.lower()}--hero--three-quarter.blend",
        output_path=ASSET_ROOT
        / "scenes"
        / "stills"
        / f"pimm-{machine.lower()}--hero--front.blend",
        contract_path=ASSET_ROOT
        / "scenes"
        / "contracts"
        / f"pimm-{machine.lower()}--hero--front.json",
        master_path=ASSET_ROOT / "masters" / f"PIMM-{machine}-MASTER.blend",
    )
    for machine in ("30G", "50G")
}


def _center_and_size(
    bounds_min: Sequence[float], bounds_max: Sequence[float]
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if len(bounds_min) != 3 or len(bounds_max) != 3:
        raise ValueError("product bounds must contain three coordinates")
    center = tuple((float(bounds_min[index]) + float(bounds_max[index])) / 2 for index in range(3))
    size = tuple(float(bounds_max[index]) - float(bounds_min[index]) for index in range(3))
    if any(component <= 0 for component in size):
        raise ValueError("product bounds must have positive extent")
    return center, size


def front_camera_pose(
    bounds_min: Sequence[float],
    bounds_max: Sequence[float],
    distance: float,
    pitch_degrees: float = DEFAULT_PITCH_DEGREES,
) -> CameraPose:
    """Return a centered front-axis camera pose with a bounded downward pitch."""

    center, _size = _center_and_size(bounds_min, bounds_max)
    if float(distance) <= 0:
        raise ValueError("camera distance must be positive")
    if not 0 <= float(pitch_degrees) <= 3:
        raise ValueError("front hero pitch must be between zero and three degrees")
    pitch = math.radians(float(pitch_degrees))
    horizontal = float(distance) * math.cos(pitch)
    vertical = float(distance) * math.sin(pitch)
    return CameraPose(
        location=(center[0], center[1] - horizontal, center[2] + vertical),
        target=center,
        pitch_degrees=float(pitch_degrees),
    )


def scaled_camera_distance(
    source_distance: float, source_focal_length: float, target_focal_length: float
) -> float:
    """Scale working distance with focal length to preserve subject framing."""

    values = (source_distance, source_focal_length, target_focal_length)
    if any(float(value) <= 0 for value in values):
        raise ValueError("camera distances and focal lengths must be positive")
    return float(source_distance) * float(target_focal_length) / float(source_focal_length)


def studio_light_specs(
    bounds_min: Sequence[float], bounds_max: Sequence[float]
) -> tuple[LightSpec, ...]:
    """Return a broad, balanced four-light product-photography arrangement."""

    center, size = _center_and_size(bounds_min, bounds_max)
    width, depth, height = size
    key_size = max(height * 0.9, 700.0)
    return (
        LightSpec(
            "KEY_FRONT",
            (center[0], center[1] - depth * 2.8, center[2] + height * 1.05),
            1_200_000.0,
            key_size,
        ),
        LightSpec(
            "FILL_FRONT",
            (center[0] + width * 1.25, center[1] - depth * 2.4, center[2] + height * 0.2),
            520_000.0,
            max(height * 0.75, 600.0),
        ),
        LightSpec(
            "RIM_LEFT",
            (center[0] - width * 2.0, center[1] + depth * 1.5, center[2] + height * 0.55),
            700_000.0,
            max(height * 0.65, 500.0),
        ),
        LightSpec(
            "RIM_RIGHT",
            (center[0] + width * 2.0, center[1] + depth * 1.5, center[2] + height * 0.55),
            700_000.0,
            max(height * 0.65, 500.0),
        ),
    )


def _product_bounds(bpy: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    from mathutils import Vector

    points = []
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.get("pimm_stable_id"):
            points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        raise ValueError("linked scene contains no stable-ID product meshes")
    return (
        tuple(min(point[index] for point in points) for index in range(3)),
        tuple(max(point[index] for point in points) for index in range(3)),
    )


def _point_at(obj: Any, target: Sequence[float]) -> None:
    from mathutils import Vector

    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def _set_world_strength(scene: Any, strength: float) -> None:
    if scene.world is None:
        import bpy

        scene.world = bpy.data.worlds.new("PIMM_STUDIO_WORLD")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background is None:
        raise ValueError("studio world is missing its Background node")
    background.inputs["Strength"].default_value = float(strength)


def _install_lights(bpy: Any, specs: Sequence[LightSpec], target: Sequence[float]) -> None:
    for obj in list(bpy.context.scene.objects):
        if obj.type == "LIGHT" and obj.library is None:
            bpy.data.objects.remove(obj, do_unlink=True)
    for spec in specs:
        data = bpy.data.lights.new(f"{spec.name}_DATA", type="AREA")
        data.energy = spec.energy
        data.shape = "DISK"
        data.size = spec.size
        obj = bpy.data.objects.new(spec.name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = spec.location
        _point_at(obj, target)


def contract_payload(config: MachineConfig) -> dict[str, object]:
    material_path = ASSET_ROOT / "masters" / "PIMM-MATERIAL-LIBRARY.blend"
    return {
        "animation_contract": None,
        "camera_name": "CAM_HERO",
        "complete_product": True,
        "machine": config.machine,
        "master_collection": "PIMM_PUBLISHED",
        "master_path": config.master_path.relative_to(ASSET_ROOT).as_posix(),
        "master_sha256": sha256_file(config.master_path),
        "material_library_path": material_path.relative_to(ASSET_ROOT).as_posix(),
        "material_library_sha256": sha256_file(material_path),
        "output_contract": {
            "alpha": True,
            "height": config.output_height,
            "width": config.output_width,
        },
        "purpose": "hero",
        "scene_id": config.scene_id,
        "schema_version": 1,
    }


def prepare_contract(config: MachineConfig) -> dict[str, object]:
    payload = contract_payload(config)
    contract = SceneContract.from_mapping(payload)
    errors = validate_scene_contract(contract)
    if errors:
        raise ValueError("invalid front scene contract: " + "; ".join(errors))
    destination = require_within(config.contract_path, ASSET_ROOT / "scenes" / "contracts")
    if destination.exists():
        raise FileExistsError(f"front scene contract already exists: {destination}")
    atomic_write_json(destination, payload)
    return {"status": "contract_created", "path": str(destination), "payload": payload}


def author_front_scene(bpy: Any, config: MachineConfig) -> dict[str, object]:
    source = Path(str(bpy.data.filepath)).resolve()
    if source != config.source_path.resolve():
        raise ValueError(f"open source scene does not match {config.machine}: {source}")
    destination = require_within(config.output_path, ASSET_ROOT / "scenes" / "stills")
    if destination.exists():
        raise FileExistsError(f"front still scene already exists: {destination}")
    contract_bytes = config.contract_path.read_bytes()
    contract = SceneContract.from_mapping(json.loads(contract_bytes.decode("utf-8")))
    if contract.scene_id != config.scene_id or contract.machine != config.machine:
        raise ValueError("front scene contract does not match machine configuration")

    bounds_min, bounds_max = _product_bounds(bpy)
    camera = bpy.context.scene.camera
    if camera is None or camera.name != contract.camera_name:
        raise ValueError("source scene is missing contracted CAM_HERO")
    center, _size = _center_and_size(bounds_min, bounds_max)
    distance = scaled_camera_distance(
        math.dist(tuple(camera.location), center),
        float(camera.data.lens),
        DEFAULT_FOCAL_LENGTH_MM,
    )
    pose = front_camera_pose(bounds_min, bounds_max, distance)
    camera.location = pose.location
    _point_at(camera, pose.target)
    camera.data.lens = DEFAULT_FOCAL_LENGTH_MM
    camera.data.shift_x = 0.0
    camera.data.shift_y = 0.0

    scene = bpy.context.scene
    _install_lights(bpy, studio_light_specs(bounds_min, bounds_max), pose.target)
    _set_world_strength(scene, DEFAULT_WORLD_STRENGTH)
    scene.view_settings.look = DEFAULT_LOOK
    scene.view_settings.exposure = DEFAULT_EXPOSURE
    scene.render.resolution_x = config.output_width
    scene.render.resolution_y = config.output_height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.filepath = str(
        (ASSET_ROOT / "renders" / "proofs" / "unapproved" / config.scene_id).resolve()
    )
    scene["pimm_scene_contract_payload"] = canonical_scene_contract_json(contract)
    scene["pimm_scene_contract_snapshot_sha256"] = hashlib.sha256(contract_bytes).hexdigest().upper()
    destination.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination), check_existing=False)
    return {
        "status": "scene_created",
        "machine": config.machine,
        "scene_id": config.scene_id,
        "path": str(destination),
        "camera": {
            "location": list(pose.location),
            "target": list(pose.target),
            "pitch_degrees": pose.pitch_degrees,
            "lens": camera.data.lens,
        },
        "lights": [spec.name for spec in studio_light_specs(bounds_min, bounds_max)],
        "exposure": scene.view_settings.exposure,
        "world_strength": DEFAULT_WORLD_STRENGTH,
    }


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--machine", choices=sorted(MACHINE_CONFIGS), required=True)
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
    config = MACHINE_CONFIGS[arguments.machine]
    if arguments.prepare_contract:
        result = prepare_contract(config)
    else:
        import bpy

        result = author_front_scene(bpy, config)
    print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
