"""Immutable contracts, manifests, and quantitative QA for PIMM proofs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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


def write_proof_manifest(contract: ProofContract, outputs: Sequence[Path]) -> Path:
    """Validate exact proof images and atomically write one immutable manifest."""

    output_root = (ASSET_ROOT / Path(*PurePosixPath(contract.output_root).parts)).resolve()
    if not output_root.is_dir():
        raise ValueError(f"proof output root does not exist: {output_root}")
    manifest_path = output_root / "manifest.json"
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

    metadata_path = output_root / "render-metadata.json"
    metadata: dict[str, object] = {
        "engine": "unrecorded",
        "resolution_percentage": contract.resolution_percentage,
        "samples": contract.samples,
        "denoise": contract.denoise,
        "named_shaft_regions": {},
    }
    if metadata_path.is_file():
        loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("render metadata root must be an object")
        metadata = loaded
    regions = metadata.get("named_shaft_regions")
    region_mapping = regions if isinstance(regions, Mapping) else {}
    entries = sorted(
        (_entry(path, shot_id, background, region_mapping) for path, shot_id, background in parsed),
        key=lambda item: (item["shot_id"], item["background"]),
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
    fingerprints = metadata.get("fingerprints")
    unchanged = (
        isinstance(fingerprints, Mapping)
        and fingerprints.get("before") == fingerprints.get("after")
    )
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
        "fingerprints_unchanged": unchanged if fingerprints is not None else None,
        "qa": qa,
        "outputs": entries,
    }
    atomic_write_json(manifest_path, payload)
    return manifest_path
