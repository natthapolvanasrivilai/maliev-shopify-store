"""Immutable contracts, manifests, and quantitative QA for PIMM proofs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path, PurePosixPath
import re
from statistics import fmean, pstdev
from typing import Literal, Mapping, Sequence

from .io_contract import atomic_write_json, sha256_file
from .paths import ASSET_ROOT, require_within
from .scene_contract import SceneContract


_FIELDS = {
    "schema_version",
    "generation_id",
    "stage",
    "scene_contract_path",
    "scene_sha256",
    "master_sha256",
    "material_library_sha256",
    "resolution_percentage",
    "samples",
    "denoise",
    "backgrounds",
    "object_masks",
    "output_root",
}
_GENERATION_ID = re.compile(r"^proof-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{7}$")
_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_BACKGROUNDS = frozenset({"white", "checker", "dark"})
_STAGES = frozenset({"composition", "material-lighting"})
_IMAGE_KINDS = frozenset(
    {"rgba", "white", "checker", "dark", "object-mask", "material-mask", "shadow-mask"}
)
_RENDER_METADATA_FIELDS = {
    "schema",
    "engine",
    "device",
    "blender",
    "resolution_percentage",
    "base_dimensions",
    "actual_dimensions",
    "image_settings",
    "samples",
    "denoise",
    "cycles",
    "agx",
    "render_seconds",
    "named_shaft_regions",
    "shadow_pass_available",
    "fixture_mode",
    "proof_contract_sha256",
    "scene_contract_sha256",
    "tool_lock_sha256",
    "fingerprints",
    "authored_settings",
    "intended_subject_metrics",
    "physical_shadow_metrics",
}
_BLENDER_FIELDS = {"binary_path", "binary_sha256", "version"}
_CYCLES_FIELDS = {
    "device",
    "samples",
    "use_denoising",
    "max_bounces",
    "transparent_max_bounces",
}
_AGX_FIELDS = {"view_transform", "look", "exposure", "gamma"}
_IMAGE_SETTINGS_FIELDS = {
    "film_transparent",
    "file_format",
    "color_mode",
    "color_depth",
    "use_file_extension",
}
_FINGERPRINT_NAMES = {"source", "master", "material_library", "scene"}
_FINGERPRINT_FIELDS = {"path", "bytes", "mtime_ns", "sha256"}
_AUTHORED_SETTINGS_FIELDS = {
    "camera",
    "lights",
    "world",
    "compositor",
    "render",
    "view_layers",
    "color_management",
    "cycles",
}
_CAMERA_SETTINGS_FIELDS = {
    "identity",
    "transform",
    "type",
    "lens",
    "sensor_fit",
    "sensor_width",
    "sensor_height",
    "shift_x",
    "shift_y",
    "clip_start",
    "clip_end",
    "dof",
}
_COMPOSITOR_SETTINGS_FIELDS = {"enabled", "node_tree"}
_MASK_METRIC_FIELDS = {"bounds", "nonzero_fraction", "unique_values", "unique_value_count"}


@dataclass(frozen=True)
class ProofContract:
    """Exact immutable settings and fingerprints for one proof generation."""

    schema_version: int
    generation_id: str
    stage: Literal["composition", "material-lighting"]
    scene_contract_path: str
    scene_sha256: str
    master_sha256: str
    material_library_sha256: str
    resolution_percentage: float
    samples: int
    denoise: bool
    backgrounds: tuple[str, ...]
    object_masks: bool
    output_root: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "ProofContract":
        """Construct from an exact mapping without dropping unknown fields."""

        if set(payload) != _FIELDS:
            missing = sorted(_FIELDS - set(payload))
            extra = sorted(set(payload) - _FIELDS)
            raise ValueError(
                "proof contract must contain exactly the required fields "
                f"(missing={missing}, extra={extra})"
            )
        backgrounds = payload["backgrounds"]
        if not isinstance(backgrounds, (list, tuple)):
            raise ValueError("proof contract backgrounds must be an array")
        return cls(
            schema_version=payload["schema_version"],
            generation_id=payload["generation_id"],
            stage=payload["stage"],
            scene_contract_path=payload["scene_contract_path"],
            scene_sha256=payload["scene_sha256"],
            master_sha256=payload["master_sha256"],
            material_library_sha256=payload["material_library_sha256"],
            resolution_percentage=payload["resolution_percentage"],
            samples=payload["samples"],
            denoise=payload["denoise"],
            backgrounds=tuple(backgrounds),
            object_masks=payload["object_masks"],
            output_root=payload["output_root"],
        )

    @classmethod
    def from_json(cls, path: Path) -> "ProofContract":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("proof contract JSON root must be an object")
        return cls.from_mapping(payload)

    def to_mapping(self) -> dict[str, object]:
        payload = asdict(self)
        payload["backgrounds"] = list(self.backgrounds)
        return payload


def _canonical_relative(value: object, prefix: str, suffix: str | None = None) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != prefix:
        return False
    return suffix is None or path.suffix.lower() == suffix


def effective_dimensions(
    scene: SceneContract, resolution_percentage: object
) -> tuple[int, int]:
    """Return exact effective pixels or reject fractional-pixel proof settings."""

    if (
        not isinstance(resolution_percentage, (int, float))
        or isinstance(resolution_percentage, bool)
    ):
        raise ValueError("proof resolution percentage must be numeric")
    try:
        percentage = Decimal(str(resolution_percentage))
    except InvalidOperation as error:
        raise ValueError("proof resolution percentage is invalid") from error
    dimensions: list[int] = []
    for field in ("width", "height"):
        base = scene.output_contract.get(field)
        if not isinstance(base, int) or isinstance(base, bool) or base <= 0:
            raise ValueError(f"scene output {field} must be a positive integer")
        effective = Decimal(base) * percentage / Decimal(100)
        if effective != effective.to_integral_value():
            raise ValueError(
                "proof resolution produces non-integral effective dimensions "
                f"({base} * {percentage}% = {effective})"
            )
        dimensions.append(int(effective))
    return dimensions[0], dimensions[1]


def validate_proof_contract(contract: ProofContract, scene: SceneContract) -> list[str]:
    """Return all fail-closed proof schema, cost, path, and scene errors."""

    errors: list[str] = []
    if contract.schema_version != 1:
        errors.append("proof contract schema_version must be 1")
    generation_valid = (
        isinstance(contract.generation_id, str)
        and _GENERATION_ID.fullmatch(contract.generation_id) is not None
    )
    if not generation_valid:
        errors.append("proof contract generation_id must match proof-YYYYMMDDTHHMMSSZ-xxxxxxx")
    if contract.stage not in _STAGES:
        errors.append("proof contract stage must be composition or material-lighting")
    if not _canonical_relative(contract.scene_contract_path, "scenes", ".json"):
        errors.append("proof contract scene_contract_path must be a managed scenes/*.json path")
    for field_name in ("scene_sha256", "master_sha256", "material_library_sha256"):
        value = getattr(contract, field_name)
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            errors.append(f"proof contract {field_name} must be 64 hexadecimal characters")
    if (
        isinstance(contract.master_sha256, str)
        and isinstance(scene.master_sha256, str)
        and contract.master_sha256.upper() != scene.master_sha256.upper()
    ):
        errors.append("proof contract master SHA-256 drifted from scene contract")
    if (
        isinstance(contract.material_library_sha256, str)
        and isinstance(scene.material_library_sha256, str)
        and contract.material_library_sha256.upper() != scene.material_library_sha256.upper()
    ):
        errors.append("proof contract material-library SHA-256 drifted from scene contract")

    percentage = contract.resolution_percentage
    if (
        not isinstance(percentage, (int, float))
        or isinstance(percentage, bool)
        or not 12.5 <= float(percentage) <= 25.0
    ):
        errors.append("proof resolution_percentage must be between 12.5 and 25; native resolution is forbidden")
    else:
        try:
            effective_dimensions(scene, percentage)
        except ValueError as error:
            errors.append(str(error))
    sample_ceiling = 32 if contract.stage == "composition" else 64
    if (
        not isinstance(contract.samples, int)
        or isinstance(contract.samples, bool)
        or contract.samples <= 0
        or contract.samples > sample_ceiling
    ):
        errors.append(f"proof samples must be between 1 and {sample_ceiling} for {contract.stage}")
    if contract.denoise is not True:
        errors.append("proof denoising must be enabled")
    if (
        set(contract.backgrounds) != _BACKGROUNDS
        or len(contract.backgrounds) != len(_BACKGROUNDS)
        or not all(isinstance(value, str) for value in contract.backgrounds)
    ):
        errors.append("proof backgrounds must contain exactly white/checker/dark")
    if contract.stage == "material-lighting" and contract.object_masks is not True:
        errors.append("material-lighting proof requires object/material masks")
    elif not isinstance(contract.object_masks, bool):
        errors.append("proof object_masks must be boolean")

    expected_output = (
        f"renders/proofs/{contract.generation_id}" if generation_valid else None
    )
    if (
        expected_output is None
        or contract.output_root != expected_output
        or not _canonical_relative(contract.output_root, "renders")
    ):
        errors.append("proof output_root must equal renders/proofs/<generation-id>")
    else:
        output_path = (ASSET_ROOT / Path(*PurePosixPath(contract.output_root).parts)).resolve()
        if output_path.exists():
            errors.append("proof generation ID is already in use; output directory must not preexist")

    if _canonical_relative(contract.scene_contract_path, "scenes", ".json"):
        contract_path = (
            ASSET_ROOT / Path(*PurePosixPath(contract.scene_contract_path).parts)
        ).resolve()
        if contract_path.is_file():
            try:
                pinned_scene = SceneContract.from_json(contract_path)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                errors.append(f"proof scene contract cannot be read: {error}")
            else:
                if pinned_scene != scene:
                    errors.append("proof scene contract path does not contain the supplied scene contract")
        else:
            errors.append(f"proof scene contract is missing: {contract_path}")
    return errors


def _bounds(values: list[int], width: int) -> dict[str, int] | None:
    if not values:
        return None
    xs = [index % width for index in values]
    ys = [index // width for index in values]
    return {"left": min(xs), "top": min(ys), "right": max(xs), "bottom": max(ys)}


def _percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction, 4)


def _rgba_metrics(image: object) -> dict[str, object]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = list(rgba.get_flattened_data())
    alphas = [pixel[3] for pixel in pixels]
    subject = [index for index, alpha in enumerate(alphas) if alpha > 0]
    partial = [index for index, alpha in enumerate(alphas) if 0 < alpha < 255]
    edge_indices = (
        list(range(width))
        + list(range((height - 1) * width, height * width))
        + [row * width for row in range(height)]
        + [row * width + width - 1 for row in range(height)]
    )
    attached = 0
    for index in partial:
        x, y = index % width, index // width
        neighbors = []
        if x:
            neighbors.append(index - 1)
        if x + 1 < width:
            neighbors.append(index + 1)
        if y:
            neighbors.append(index - width)
        if y + 1 < height:
            neighbors.append(index + width)
        if any(alphas[neighbor] > 0 for neighbor in neighbors):
            attached += 1
    return {
        "subject_bounds": _bounds(subject, width),
        "subject_pixel_fraction": round(len(subject) / max(1, len(pixels)), 8),
        "edge_alpha_max": max((alphas[index] for index in edge_indices), default=0),
        "edge_alpha_fraction": round(
            sum(alphas[index] > 0 for index in edge_indices) / max(1, len(edge_indices)), 8
        ),
        "partial_alpha_pixels": len(partial),
        "partial_alpha_attached_fraction": round(attached / max(1, len(partial)), 8),
    }


def _composite_metrics(image: object) -> dict[str, object]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = list(rgb.get_flattened_data())
    luma = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in pixels]
    edge = (
        pixels[:width]
        + pixels[(height - 1) * width :]
        + [pixels[row * width] for row in range(height)]
        + [pixels[row * width + width - 1] for row in range(height)]
    )
    edge_luma = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in edge]
    return {
        "background_continuity_edge_luma_stddev": round(pstdev(edge_luma), 4) if len(edge_luma) > 1 else 0.0,
        "near_white_fraction": round(sum(min(pixel) >= 245 for pixel in pixels) / max(1, len(pixels)), 8),
        "clipped_fraction": round(sum(max(pixel) == 255 for pixel in pixels) / max(1, len(pixels)), 8),
        "dark_fraction": round(sum(value <= 32 for value in luma) / max(1, len(luma)), 8),
        "luma_percentiles": {
            key: _percentile(luma, value)
            for key, value in {"p01": 1, "p05": 5, "p50": 50, "p95": 95, "p99": 99}.items()
        },
    }


def _mask_metrics(image: object) -> dict[str, object]:
    mask = image.convert("L")
    width, _ = mask.size
    values = list(mask.get_flattened_data())
    nonzero = [index for index, value in enumerate(values) if value > 0]
    unique_values = sorted(set(values))
    return {
        "bounds": _bounds(nonzero, width),
        "nonzero_fraction": round(len(nonzero) / max(1, len(values)), 8),
        "unique_values": unique_values[:256],
        "unique_value_count": len(unique_values),
    }


def analyze_mask_metrics(image: object) -> dict[str, object]:
    """Return bounds, coverage, and value-distribution metrics for one mask."""

    return _mask_metrics(image)


def _shaft_metrics(image: object, regions: Mapping[str, object] | None) -> dict[str, object]:
    if not regions:
        return {"present": False, "regions": {}}
    rgb = image.convert("RGB")
    width, height = rgb.size
    result: dict[str, object] = {}
    for name, raw_bounds in sorted(regions.items()):
        if not isinstance(raw_bounds, list) or len(raw_bounds) != 4:
            continue
        left, top, right, bottom = [float(value) for value in raw_bounds]
        box = (
            max(0, min(width, round(left * width))),
            max(0, min(height, round(top * height))),
            max(0, min(width, round(right * width))),
            max(0, min(height, round(bottom * height))),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        values = [
            0.2126 * r + 0.7152 * g + 0.0722 * b
            for r, g, b in rgb.crop(box).get_flattened_data()
        ]
        result[str(name)] = {
            "mean_luma": round(fmean(values), 4),
            "p95_luma": _percentile(values, 95),
            "highlight_fraction": round(sum(value >= 220 for value in values) / len(values), 8),
        }
    return {"present": bool(result), "regions": result}


def _entry(path: Path, shot_id: str, background: str, regions: Mapping[str, object] | None) -> dict[str, object]:
    from PIL import Image

    with Image.open(path) as image:
        image.load()
        if background == "rgba":
            metrics = _rgba_metrics(image)
        elif background.endswith("mask"):
            metrics = _mask_metrics(image)
        else:
            metrics = _composite_metrics(image)
            metrics["named_shaft_reflection"] = _shaft_metrics(image, regions)
        width, height = image.size
    return {
        "shot_id": shot_id,
        "background": background,
        "kind": "mask" if background.endswith("mask") else "proof",
        "path": path.name,
        "width": width,
        "height": height,
        "sha256": sha256_file(path),
        "metrics": metrics,
    }


def _require_exact_mapping(
    value: object, fields: set[str], label: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(f"{label} must contain exactly {sorted(fields)}")
    return value


def _validate_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a 64-character SHA-256")
    return value.upper()


def _validate_render_metadata(
    metadata: object,
    contract: ProofContract,
    scene: SceneContract,
    *,
    output_root: Path,
    scene_contract_path: Path,
) -> Mapping[str, object]:
    metadata = _require_exact_mapping(
        metadata, _RENDER_METADATA_FIELDS, "render metadata"
    )
    if metadata["schema"] != "pimm-proof-render-metadata/v1":
        raise ValueError("render metadata schema is not pimm-proof-render-metadata/v1")
    if metadata["engine"] != "CYCLES":
        raise ValueError("render metadata engine must equal CYCLES")
    device = metadata["device"]
    if device != "CPU":
        raise ValueError("render metadata device must equal CPU")
    blender = _require_exact_mapping(
        metadata["blender"], _BLENDER_FIELDS, "render metadata blender identity"
    )
    binary_path = blender["binary_path"]
    if not isinstance(binary_path, str) or not binary_path or not Path(binary_path).is_absolute():
        raise ValueError("render metadata Blender binary_path must be absolute")
    _validate_sha256(blender["binary_sha256"], "render metadata Blender binary")
    if not isinstance(blender["version"], str) or not blender["version"]:
        raise ValueError("render metadata Blender version must be nonempty")

    expected_dimensions = list(
        effective_dimensions(scene, contract.resolution_percentage)
    )
    expected_base = [
        scene.output_contract["width"],
        scene.output_contract["height"],
    ]
    if metadata["base_dimensions"] != expected_base:
        raise ValueError("render metadata base_dimensions do not match scene contract")
    if metadata["actual_dimensions"] != expected_dimensions:
        raise ValueError("render metadata actual_dimensions do not match exact proof pixels")
    image_settings = _require_exact_mapping(
        metadata["image_settings"],
        _IMAGE_SETTINGS_FIELDS,
        "render metadata image settings",
    )
    if image_settings != {
        "film_transparent": True,
        "file_format": "PNG",
        "color_mode": "RGBA",
        "color_depth": "8",
        "use_file_extension": True,
    }:
        raise ValueError("render metadata image settings do not match lossless RGBA proof settings")
    if metadata["resolution_percentage"] != contract.resolution_percentage:
        raise ValueError("render metadata resolution_percentage does not match proof contract")
    if metadata["samples"] != contract.samples:
        raise ValueError("render metadata samples do not match proof contract")
    if metadata["denoise"] is not contract.denoise:
        raise ValueError("render metadata denoise does not match proof contract")

    cycles = _require_exact_mapping(
        metadata["cycles"], _CYCLES_FIELDS, "render metadata Cycles settings"
    )
    if (
        cycles["device"] != device
        or cycles["samples"] != contract.samples
        or cycles["use_denoising"] is not contract.denoise
    ):
        raise ValueError("render metadata Cycles settings do not match contracted settings")
    for field in ("max_bounces", "transparent_max_bounces"):
        if (
            not isinstance(cycles[field], int)
            or isinstance(cycles[field], bool)
            or cycles[field] < 0
        ):
            raise ValueError(f"render metadata Cycles {field} must be a nonnegative integer")
    agx = _require_exact_mapping(metadata["agx"], _AGX_FIELDS, "render metadata AgX settings")
    if agx["view_transform"] != "AgX":
        raise ValueError("render metadata view_transform must equal AgX")
    if agx["look"] not in {
        "AgX - Medium High Contrast",
        "Medium High Contrast",
        "None",
    }:
        raise ValueError("render metadata AgX look is not an exact supported value")
    if agx["exposure"] != 0.0 or agx["gamma"] != 1.0:
        raise ValueError("render metadata AgX exposure/gamma must equal 0.0/1.0")
    if (
        not isinstance(metadata["render_seconds"], (int, float))
        or isinstance(metadata["render_seconds"], bool)
        or metadata["render_seconds"] < 0
    ):
        raise ValueError("render metadata render_seconds must be nonnegative")
    if not isinstance(metadata["named_shaft_regions"], Mapping):
        raise ValueError("render metadata named_shaft_regions must be an object")
    for name, bounds in metadata["named_shaft_regions"].items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(bounds, list)
            or len(bounds) != 4
            or any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not 0 <= value <= 1
                for value in bounds
            )
        ):
            raise ValueError("render metadata named shaft regions are invalid")
    if not isinstance(metadata["shadow_pass_available"], bool):
        raise ValueError("render metadata shadow_pass_available must be boolean")
    if not isinstance(metadata["fixture_mode"], bool):
        raise ValueError("render metadata fixture_mode must be boolean")
    if metadata["shadow_pass_available"] is not metadata["fixture_mode"]:
        raise ValueError("render metadata shadow pass must exactly match fixture render support")

    proof_snapshot = output_root / "proof-contract.json"
    scene_snapshot = output_root / "scene-contract.json"
    if not proof_snapshot.is_file() or not scene_snapshot.is_file():
        raise ValueError("immutable proof and scene contract snapshots are required")
    if ProofContract.from_json(proof_snapshot) != contract:
        raise ValueError("proof contract snapshot does not match manifest contract")
    if SceneContract.from_json(scene_snapshot) != scene:
        raise ValueError("scene contract snapshot does not match pinned scene contract")
    if sha256_file(scene_snapshot) != sha256_file(scene_contract_path):
        raise ValueError("scene contract snapshot hash does not match pinned scene contract")
    if _validate_sha256(
        metadata["proof_contract_sha256"], "render metadata proof contract"
    ) != sha256_file(proof_snapshot):
        raise ValueError("render metadata proof contract SHA-256 mismatch")
    if _validate_sha256(
        metadata["scene_contract_sha256"], "render metadata scene contract"
    ) != sha256_file(scene_snapshot):
        raise ValueError("render metadata scene contract SHA-256 mismatch")
    _validate_sha256(metadata["tool_lock_sha256"], "render metadata tool lock")
    tool_snapshot = output_root / "tool-lock.json"
    if not tool_snapshot.is_file():
        raise ValueError("immutable tool lock snapshot is required")
    if metadata["tool_lock_sha256"] != sha256_file(tool_snapshot):
        raise ValueError("render metadata tool lock SHA-256 mismatch")
    tool_payload = json.loads(tool_snapshot.read_text(encoding="utf-8"))
    tools = tool_payload.get("tools") if isinstance(tool_payload, Mapping) else None
    blender_records = [
        item
        for item in (tools if isinstance(tools, list) else [])
        if isinstance(item, Mapping) and item.get("id") == "blender"
    ]
    if len(blender_records) != 1:
        raise ValueError("tool lock snapshot must contain exactly one Blender record")
    locked_blender = blender_records[0]
    if (
        Path(str(locked_blender.get("path", ""))).resolve()
        != Path(str(blender["binary_path"])).resolve()
        or str(locked_blender.get("sha256", "")).upper()
        != blender["binary_sha256"]
        or locked_blender.get("version") != blender["version"]
    ):
        raise ValueError("render metadata Blender identity does not match tool lock snapshot")

    fingerprints = _require_exact_mapping(
        metadata["fingerprints"], {"before", "after"}, "render metadata fingerprints"
    )
    before = _require_exact_mapping(
        fingerprints["before"], _FINGERPRINT_NAMES, "render metadata before fingerprints"
    )
    after = _require_exact_mapping(
        fingerprints["after"], _FINGERPRINT_NAMES, "render metadata after fingerprints"
    )
    if before != after:
        raise ValueError("render metadata protected fingerprints drifted")
    expected_pins = {
        "master": contract.master_sha256.upper(),
        "material_library": contract.material_library_sha256.upper(),
        "scene": contract.scene_sha256.upper(),
    }
    for phase, records in (("before", before), ("after", after)):
        for name, raw_record in records.items():
            record = _require_exact_mapping(
                raw_record,
                _FINGERPRINT_FIELDS,
                f"render metadata {phase} fingerprint {name}",
            )
            if not isinstance(record["path"], str) or not Path(record["path"]).is_absolute():
                raise ValueError(f"render metadata fingerprint path must be absolute: {name}")
            if (
                not isinstance(record["bytes"], int)
                or isinstance(record["bytes"], bool)
                or record["bytes"] < 0
                or not isinstance(record["mtime_ns"], int)
                or isinstance(record["mtime_ns"], bool)
                or record["mtime_ns"] < 0
            ):
                raise ValueError(f"render metadata fingerprint size/time is invalid: {name}")
            _validate_sha256(record["sha256"], f"render metadata fingerprint {name}")
            if name in expected_pins and str(record["sha256"]).upper() != expected_pins[name]:
                raise ValueError(
                    f"render metadata {name} fingerprint does not match proof contract pin"
                )

    authored = _require_exact_mapping(
        metadata["authored_settings"],
        {"before", "after"},
        "render metadata authored settings",
    )
    if (
        not isinstance(authored["before"], Mapping)
        or not authored["before"]
        or authored["before"] != authored["after"]
    ):
        raise ValueError("render metadata authored settings are incomplete or drifted")
    authored_before = _require_exact_mapping(
        authored["before"],
        _AUTHORED_SETTINGS_FIELDS,
        "render metadata authored settings before",
    )
    camera = _require_exact_mapping(
        authored_before["camera"],
        _CAMERA_SETTINGS_FIELDS,
        "render metadata authored camera",
    )
    if (
        not isinstance(camera["identity"], Mapping)
        or not camera["identity"]
        or not isinstance(camera["transform"], Mapping)
        or not camera["transform"]
        or not isinstance(camera["type"], str)
        or not camera["type"]
        or not isinstance(camera["lens"], (int, float))
        or isinstance(camera["lens"], bool)
        or not isinstance(camera["dof"], Mapping)
        or not camera["dof"]
    ):
        raise ValueError("render metadata authored camera state is invalid")
    if not isinstance(authored_before["lights"], list):
        raise ValueError("render metadata authored lights must be a list")
    world = authored_before["world"]
    if world is not None and not isinstance(world, Mapping):
        raise ValueError("render metadata authored world must be null or an object")
    compositor = _require_exact_mapping(
        authored_before["compositor"],
        _COMPOSITOR_SETTINGS_FIELDS,
        "render metadata authored compositor",
    )
    if (
        not isinstance(compositor["enabled"], bool)
        or (
            compositor["node_tree"] is not None
            and not isinstance(compositor["node_tree"], Mapping)
        )
    ):
        raise ValueError("render metadata authored compositor settings are invalid")
    if (
        not isinstance(authored_before["render"], Mapping)
        or not authored_before["render"]
        or not isinstance(authored_before["view_layers"], list)
        or not authored_before["view_layers"]
        or not isinstance(authored_before["color_management"], Mapping)
        or not authored_before["color_management"]
        or not isinstance(authored_before["cycles"], Mapping)
        or not authored_before["cycles"]
    ):
        raise ValueError("render metadata authored render/view-layer settings are incomplete")
    for field in ("intended_subject_metrics", "physical_shadow_metrics"):
        metrics = _require_exact_mapping(
            metadata[field], _MASK_METRIC_FIELDS, f"render metadata {field}"
        )
        if (
            not isinstance(metrics["unique_values"], list)
            or not isinstance(metrics["unique_value_count"], int)
            or isinstance(metrics["unique_value_count"], bool)
            or not isinstance(metrics["nonzero_fraction"], (int, float))
            or isinstance(metrics["nonzero_fraction"], bool)
            or not 0 <= metrics["nonzero_fraction"] <= 1
        ):
            raise ValueError(f"render metadata {field} is invalid")
    return metadata


def write_proof_manifest(
    contract: ProofContract,
    outputs: Sequence[Path],
    *,
    destination: Path | None = None,
) -> Path:
    """Validate exact proof images and atomically write one immutable manifest."""

    output_root = (ASSET_ROOT / Path(*PurePosixPath(contract.output_root).parts)).resolve()
    if not output_root.is_dir():
        raise ValueError(f"proof output root does not exist: {output_root}")
    manifest_path = (
        output_root / "manifest.json" if destination is None else Path(destination).resolve()
    )
    if manifest_path not in {
        output_root / "manifest.json",
        output_root / ".manifest.pending.json",
    }:
        raise ValueError("proof manifest destination is not an approved exact path")
    if manifest_path.exists():
        raise ValueError(f"proof manifest already exists: {manifest_path}")

    expected = {"rgba", *contract.backgrounds}
    if contract.object_masks:
        expected.update({"object-mask", "material-mask", "shadow-mask"})
    parsed: list[tuple[Path, str, str]] = []
    observed: set[str] = set()
    for raw_path in outputs:
        path = require_within(Path(raw_path), output_root)
        if not path.is_file() or path.suffix.lower() != ".png":
            raise ValueError(f"proof output must be an existing PNG: {path}")
        stem = path.stem
        if "--" not in stem:
            raise ValueError(f"proof output filename lacks shot/background identity: {path.name}")
        shot_id, background = stem.rsplit("--", 1)
        if not shot_id or background not in _IMAGE_KINDS:
            raise ValueError(f"proof output filename is not canonical: {path.name}")
        if background in observed:
            raise ValueError(f"duplicate proof output background: {background}")
        observed.add(background)
        parsed.append((path, shot_id, background))
    if observed != expected:
        raise ValueError(
            "proof outputs do not match contract "
            f"(missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)})"
        )

    scene_contract_path = (
        ASSET_ROOT / Path(*PurePosixPath(contract.scene_contract_path).parts)
    ).resolve()
    if not scene_contract_path.is_file():
        raise ValueError(f"pinned scene contract is missing: {scene_contract_path}")
    scene = SceneContract.from_json(scene_contract_path)
    metadata_path = output_root / "render-metadata.json"
    if not metadata_path.is_file():
        raise ValueError("complete render metadata is required")
    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata = _validate_render_metadata(
        loaded,
        contract,
        scene,
        output_root=output_root,
        scene_contract_path=scene_contract_path,
    )
    regions = metadata.get("named_shaft_regions")
    region_mapping = regions if isinstance(regions, Mapping) else {}
    entries = sorted(
        (_entry(path, shot_id, background, region_mapping) for path, shot_id, background in parsed),
        key=lambda item: (item["shot_id"], item["background"]),
    )
    shot_ids = {entry["shot_id"] for entry in entries}
    if shot_ids != {scene.scene_id}:
        raise ValueError(
            f"proof outputs must contain exactly scene shot_id {scene.scene_id}; found={sorted(shot_ids)}"
        )
    expected_pixels = list(effective_dimensions(scene, contract.resolution_percentage))
    for entry in entries:
        if [entry["width"], entry["height"]] != expected_pixels:
            raise ValueError(
                f"proof output dimensions do not match exact effective pixels: {entry['path']}"
            )
    by_background = {entry["background"]: entry for entry in entries}
    shadow = by_background.get("shadow-mask")
    fallback_subject = {
        "bounds": by_background["rgba"]["metrics"]["subject_bounds"],
        "nonzero_fraction": by_background["rgba"]["metrics"]["subject_pixel_fraction"],
    }
    intended_subject = (
        by_background["object-mask"]["metrics"]
        if "object-mask" in by_background
        else metadata.get("intended_subject_metrics") or fallback_subject
    )
    physical_shadow = (
        shadow["metrics"]
        if shadow
        else metadata.get("physical_shadow_metrics")
        or {"bounds": None, "nonzero_fraction": 0.0}
    )
    qa = {
        "subject": by_background["rgba"]["metrics"],
        "intended_subject": intended_subject,
        "physical_shadow_extent": physical_shadow,
        "backgrounds": {
            name: by_background[name]["metrics"] for name in contract.backgrounds
        },
        "material_masks": {
            name: by_background[name]["metrics"]
            for name in ("object-mask", "material-mask")
            if name in by_background
        },
        "named_shaft_reflection": {
            name: by_background[name]["metrics"]["named_shaft_reflection"]
            for name in contract.backgrounds
        },
    }
    payload: dict[str, object] = {
        "schema": "pimm-proof-manifest/v1",
        "generation_id": contract.generation_id,
        "status": "pass",
        "stage": contract.stage,
        "scene_sha256": contract.scene_sha256.upper(),
        "master_sha256": contract.master_sha256.upper(),
        "material_library_sha256": contract.material_library_sha256.upper(),
        "resolution_percentage": contract.resolution_percentage,
        "samples": contract.samples,
        "denoise": contract.denoise,
        "contract": contract.to_mapping(),
        "render": metadata,
        "fingerprints_unchanged": True,
        "qa": qa,
        "outputs": entries,
    }
    atomic_write_json(manifest_path, payload)
    return manifest_path
