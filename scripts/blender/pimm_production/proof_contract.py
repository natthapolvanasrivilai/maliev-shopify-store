"""Immutable contracts, manifests, and quantitative QA for PIMM proofs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
from statistics import fmean, pstdev
from typing import Literal, Mapping, Sequence

from scripts.blender.master_assets.pimm_material_library import MATERIAL_SPECS

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
_PIMM_MATERIAL_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
_CANONICAL_SHARED_MATERIAL_IDS = frozenset(MATERIAL_SPECS) - {"UNASSIGNED"}
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
    "scene_identity",
    "camera",
    "lights",
    "world",
    "compositor",
    "render",
    "view_layers",
    "color_management",
    "cycles",
    "objects",
    "materials",
    "images",
    "collection_tree",
    "dependency_sha256",
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
_IDENTITY_FIELDS = {"name", "type", "library"}
_OPTIONAL_IDENTITY_FIELDS = {"pimm_stable_id", "pimm_material_id"}
_TRANSFORM_FIELDS = {
    "location",
    "rotation_mode",
    "rotation_euler",
    "scale",
    "matrix_world",
    "parent",
}
_NODE_TREE_FIELDS = {"identity", "nodes", "links"}
_NODE_TREE_REFERENCE_FIELDS = {"identity", "recursive_reference"}
_NODE_FIELDS = {"name", "type", "mute", "properties", "inputs", "outputs", "data"}
_SOCKET_FIELDS = {"name", "identifier", "type", "enabled", "is_linked", "default"}
_LINK_FIELDS = {
    "from_node",
    "from_socket",
    "from_socket_identifier",
    "to_node",
    "to_socket",
    "to_socket_identifier",
}
_GEOMETRY_FIELDS = {"sha256", "vertices", "edges", "loops", "polygons"}
_OBJECT_FIELDS = {
    "identity",
    "object_type",
    "data",
    "transform",
    "hide_render",
    "hide_viewport",
    "properties",
    "collections",
    "material_slots",
    "modifiers",
}
_OBJECT_DATA_FIELDS = {"identity", "properties"}
_COLLECTION_MEMBERSHIP_FIELDS = {"identity", "path"}
_MATERIAL_SLOT_FIELDS = {"index", "name", "link", "material"}
_MODIFIER_FIELDS = {
    "name",
    "type",
    "properties",
    "references",
    "id_properties",
    "interface_inputs",
    "node_group",
}
_ID_PROPERTY_FIELDS = {"name", "dependency"}
_DEPENDENCY_VALUE_FIELDS = {"kind", "value"}
_INTERFACE_INPUT_FIELDS = {
    "index",
    "identifier",
    "name",
    "socket_type",
    "properties",
    "references",
}
_MATERIAL_FIELDS = {"identity", "properties", "node_tree"}
_IMAGE_FIELDS = {
    "filepath",
    "source",
    "size",
    "channels",
    "depth",
    "is_float",
    "file_format",
    "alpha_mode",
    "colorspace",
    "external_files",
    "packed_files",
    "pixels",
}
_EXTERNAL_IMAGE_FIELDS = {
    "path",
    "resolved_path",
    "bytes",
    "mtime_ns",
    "ctime_ns",
    "device",
    "inode",
    "links",
    "sha256",
}
_PACKED_IMAGE_FIELDS = {"index", "filepath", "view", "tile_number", "bytes", "sha256"}
_PIXEL_FIELDS = {"encoding", "values", "sha256"}
_COLLECTION_FIELDS = {
    "identity",
    "path",
    "hide_render",
    "hide_viewport",
    "properties",
    "objects",
    "children",
}
_COLLECTION_REFERENCE_FIELDS = {"identity", "path", "recursive_reference"}
_VIEW_LAYER_FIELDS = {"name", "properties", "material_override", "layer_collection"}
_LAYER_COLLECTION_FIELDS = {
    "path",
    "collection",
    "exclude",
    "holdout",
    "indirect_only",
    "hide_viewport",
    "children",
}
_OBJECT_TYPES = frozenset(
    {
        "MESH",
        "CURVE",
        "SURFACE",
        "META",
        "FONT",
        "CURVES",
        "POINTCLOUD",
        "VOLUME",
        "GREASEPENCIL",
        "ARMATURE",
        "LATTICE",
        "EMPTY",
        "LIGHT",
        "LIGHT_PROBE",
        "CAMERA",
        "SPEAKER",
    }
)
_IMAGE_SOURCES = frozenset(
    {"FILE", "SEQUENCE", "MOVIE", "GENERATED", "VIEWER", "TILED", "RENDER_RESULT"}
)
_FILE_BACKED_IMAGE_SOURCES = frozenset({"FILE", "SEQUENCE", "MOVIE", "TILED"})
_DEPENDENCY_KINDS = frozenset({"value", "identity", "image", "node_tree"})
_NODE_TREE_TYPES = frozenset(
    {"ShaderNodeTree", "GeometryNodeTree", "CompositorNodeTree"}
)
_NODE_TYPES_BY_TREE = {
    "ShaderNodeTree": frozenset(
        {
            "ShaderNodeBackground",
            "ShaderNodeBsdfPrincipled",
            "ShaderNodeEmission",
            "ShaderNodeGroup",
            "ShaderNodeMath",
            "ShaderNodeOutputLight",
            "ShaderNodeOutputMaterial",
            "ShaderNodeOutputWorld",
            "ShaderNodeTexImage",
            "ShaderNodeValue",
        }
    ),
    "GeometryNodeTree": frozenset(
        {
            "GeometryNodeGroup",
            "GeometryNodeInputPosition",
            "GeometryNodeJoinGeometry",
            "GeometryNodeSetMaterial",
            "GeometryNodeTransform",
            "NodeGroupInput",
            "NodeGroupOutput",
            "ShaderNodeMath",
            "ShaderNodeValue",
        }
    ),
    "CompositorNodeTree": frozenset(
        {
            "CompositorNodeBrightContrast",
            "CompositorNodeComposite",
            "CompositorNodeRLayers",
            "NodeGroupInput",
            "NodeGroupOutput",
        }
    ),
}
_UNSAFE_NODE_TYPES_BY_TREE = {
    "CompositorNodeTree": frozenset({"CompositorNodeOutputFile"}),
}
_NODE_SOCKET_TYPES = frozenset(
    {
        "NodeSocketBool",
        "NodeSocketCollection",
        "NodeSocketColor",
        "NodeSocketFloat",
        "NodeSocketFloatDistance",
        "NodeSocketFloatFactor",
        "NodeSocketFloatWavelength",
        "NodeSocketGeometry",
        "NodeSocketImage",
        "NodeSocketInt",
        "NodeSocketMaterial",
        "NodeSocketMatrix",
        "NodeSocketMenu",
        "NodeSocketObject",
        "NodeSocketRotation",
        "NodeSocketShader",
        "NodeSocketString",
        "NodeSocketVector",
        "NodeSocketVectorTranslation",
        "NodeSocketVectorXYZ",
        "NodeSocketVirtual",
    }
)
_NODE_SOCKET_POINTER_TYPES = {
    "NodeSocketCollection": "Collection",
    "NodeSocketImage": "Image",
    "NodeSocketMaterial": "Material",
    "NodeSocketObject": "Object",
}
# Blender 5.2 still exposes NodeSocketTexture RNA, but it is absent from the
# node-group interface enum and no renderer-supported node emits it.
_MODIFIER_TYPES = frozenset({"NODES"})
_GEOMETRY_INTERFACE_SOCKET_TYPES = frozenset(
    {
        "NodeSocketCollection",
        "NodeSocketFloat",
        "NodeSocketGeometry",
        "NodeSocketImage",
        "NodeSocketMaterial",
        "NodeSocketObject",
    }
)
_OBJECT_DATA_TYPES = {
    "ARMATURE": frozenset({"Armature"}),
    "CAMERA": frozenset({"Camera"}),
    "CURVE": frozenset({"Curve"}),
    "EMPTY": frozenset(),
    "FONT": frozenset({"TextCurve"}),
    "LATTICE": frozenset({"Lattice"}),
    "LIGHT": frozenset({"AreaLight", "PointLight", "SpotLight", "SunLight"}),
    "MESH": frozenset({"Mesh"}),
    "POINTCLOUD": frozenset({"PointCloud"}),
    "SPEAKER": frozenset({"Speaker"}),
    "VOLUME": frozenset({"Volume"}),
}
_ROTATION_MODES = frozenset(
    {"QUATERNION", "XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX", "AXIS_ANGLE"}
)
_RENDER_ENGINES = frozenset({"BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"})
_NODE_COMMON_PROPERTY_FIELDS = frozenset(
    {
        "bl_description",
        "bl_height_default",
        "bl_height_max",
        "bl_height_min",
        "bl_icon",
        "bl_idname",
        "bl_label",
        "bl_static_type",
        "bl_width_default",
        "bl_width_max",
        "bl_width_min",
        "color_tag",
        "hide",
        "mute",
        "type",
        "use_custom_color",
        "warning_propagation",
    }
)
_NODE_EXTRA_PROPERTY_FIELDS = {
    "CompositorNodeRLayers": frozenset({"layer"}),
    "NodeGroupOutput": frozenset({"is_active_output"}),
    "ShaderNodeBsdfPrincipled": frozenset({"distribution", "subsurface_method"}),
    "ShaderNodeGroup": frozenset(),
    "ShaderNodeMath": frozenset({"operation", "use_clamp"}),
    "ShaderNodeOutputLight": frozenset({"is_active_output", "target"}),
    "ShaderNodeOutputMaterial": frozenset({"is_active_output", "target"}),
    "ShaderNodeOutputWorld": frozenset({"is_active_output", "target"}),
    "ShaderNodeTexImage": frozenset(
        {"extension", "interpolation", "projection", "projection_blend"}
    ),
}
_NODE_STATIC_TYPES = {
    "CompositorNodeRLayers": "R_LAYERS",
    "GeometryNodeSetMaterial": "SET_MATERIAL",
    "NodeGroupInput": "GROUP_INPUT",
    "NodeGroupOutput": "GROUP_OUTPUT",
    "ShaderNodeBackground": "BACKGROUND",
    "ShaderNodeBsdfPrincipled": "BSDF_PRINCIPLED",
    "ShaderNodeEmission": "EMISSION",
    "ShaderNodeGroup": "GROUP",
    "ShaderNodeMath": "MATH",
    "ShaderNodeOutputLight": "OUTPUT_LIGHT",
    "ShaderNodeOutputMaterial": "OUTPUT_MATERIAL",
    "ShaderNodeOutputWorld": "OUTPUT_WORLD",
    "ShaderNodeTexImage": "TEX_IMAGE",
    "ShaderNodeValue": "VALUE",
}
_MATH_OPERATIONS = frozenset(
    {
        "ABSOLUTE", "ADD", "ARCCOSINE", "ARCSINE", "ARCTAN2", "ARCTANGENT",
        "CEIL", "COMPARE", "COSINE", "COSH", "DEGREES", "DIVIDE", "EXPONENT",
        "FLOOR", "FLOORED_MODULO", "FRACT", "GREATER_THAN", "INVERSE_SQRT",
        "LESS_THAN", "LOGARITHM", "MAXIMUM", "MINIMUM", "MODULO", "MULTIPLY",
        "MULTIPLY_ADD", "PINGPONG", "POWER", "RADIANS", "ROUND", "SIGN", "SINE",
        "SINH", "SMOOTH_MAX", "SMOOTH_MIN", "SNAP", "SQRT", "SUBTRACT",
        "TANGENT", "TANH", "TRUNCATE", "WRAP",
    }
)
_NODES_MODIFIER_PROPERTY_FIELDS = frozenset(
    {
        "bake_directory",
        "bake_target",
        "execution_time",
        "is_active",
        "is_override_data",
        "open_bake_data_blocks_panel",
        "open_bake_panel",
        "open_manage_panel",
        "open_named_attributes_panel",
        "open_output_attributes_panel",
        "open_warnings_panel",
        "persistent_uid",
        "show_expanded",
        "show_group_selector",
        "show_in_editmode",
        "show_manage_panel",
        "show_on_cage",
        "show_render",
        "show_viewport",
        "use_apply_on_spline",
        "use_pin_to_last",
    }
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


def _require_string(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError(f"{label} must be a {'string' if allow_empty else 'nonempty string'}")
    return value


def _require_integer(value: object, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _require_number(value: object, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _validate_json_value(value: object, label: str) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{label}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _require_string(key, f"{label} key")
            _validate_json_value(item, f"{label}.{key}")
        return
    raise ValueError(f"{label} contains an unsupported value type")


def _validate_properties(
    value: object,
    label: str,
    *,
    exact_fields: frozenset[str] | None = None,
    enum_domains: Mapping[str, frozenset[str]] | None = None,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    if exact_fields is not None and set(value) != exact_fields:
        raise ValueError(f"{label} must contain the exact pinned Blender RNA fields")
    for key, item in value.items():
        _require_string(key, f"{label} key")
        _validate_json_value(item, f"{label}.{key}")
    for identifier, domain in (enum_domains or {}).items():
        if identifier in value and value[identifier] not in domain:
            raise ValueError(
                f"{label}.{identifier} is outside the pinned Blender enum domain"
            )
    return value


def _canonical_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _validate_sorted_unique(
    values: object,
    label: str,
    key,
) -> list[object]:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list")
    keys = [key(item) for item in values]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError(f"{label} must be deterministically sorted with unique identities")
    return values


def _validate_absolute_safe_path(value: object, label: str) -> str:
    path_text = _require_string(value, label)
    path = Path(path_text)
    if not path.is_absolute() or path != Path(os.path.abspath(path_text)):
        raise ValueError(f"{label} must be one absolute lexical canonical path")
    return path_text


def _identity_fields(value: Mapping[str, object]) -> set[str]:
    return _IDENTITY_FIELDS | (_OPTIONAL_IDENTITY_FIELDS & set(value))


def _validate_identity(
    value: object,
    label: str,
    *,
    allow_none: bool = False,
    allow_empty_name: bool = False,
) -> Mapping[str, object] | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, Mapping) or set(value) != _identity_fields(value):
        raise ValueError(f"{label} must be an exact data-block identity")
    _require_string(value["name"], f"{label} name", allow_empty=allow_empty_name)
    _require_string(value["type"], f"{label} type")
    library = value["library"]
    if library is not None:
        _validate_absolute_safe_path(library, f"{label} library")
    if "pimm_stable_id" in value:
        _require_string(value["pimm_stable_id"], f"{label} pimm_stable_id")
    if value["type"] == "Material":
        if "pimm_material_id" not in value:
            raise ValueError(f"{label} requires an exact pimm_material_id")
        material_id = _require_string(
            value["pimm_material_id"], f"{label} pimm_material_id"
        )
        if material_id != material_id.strip() or _PIMM_MATERIAL_ID.fullmatch(material_id) is None:
            raise ValueError(f"{label} pimm_material_id must be canonical uppercase authority")
        if material_id == "UNASSIGNED":
            raise ValueError(f"{label} pimm_material_id cannot equal UNASSIGNED")
        if (
            material_id in _CANONICAL_SHARED_MATERIAL_IDS
            and value["name"] != f"PIMM_{material_id}"
        ):
            raise ValueError(
                f"{label} shared material name/pimm_material_id mapping is invalid"
            )
    elif "pimm_material_id" in value:
        raise ValueError(f"{label} pimm_material_id is valid only for Material identities")
    return value


def _require_identity_type(
    identity: Mapping[str, object] | None,
    expected: str,
    label: str,
) -> None:
    if identity is None or identity["type"] != expected:
        raise ValueError(f"{label} identity type must equal {expected}")


def _validate_vector(value: object, length: int, label: str) -> None:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label} must contain exactly {length} numbers")
    for index, item in enumerate(value):
        _require_number(item, f"{label}[{index}]")


def _validate_transform(value: object, label: str) -> None:
    transform = _require_exact_mapping(value, _TRANSFORM_FIELDS, label)
    _validate_vector(transform["location"], 3, f"{label} location")
    rotation_mode = _require_string(
        transform["rotation_mode"], f"{label} rotation_mode"
    )
    if rotation_mode not in _ROTATION_MODES:
        raise ValueError(f"{label} rotation_mode is outside the Blender enum domain")
    _validate_vector(transform["rotation_euler"], 3, f"{label} rotation_euler")
    _validate_vector(transform["scale"], 3, f"{label} scale")
    _validate_vector(transform["matrix_world"], 16, f"{label} matrix_world")
    parent = _validate_identity(
        transform["parent"], f"{label} parent", allow_none=True
    )
    if parent is not None:
        _require_identity_type(parent, "Object", f"{label} parent")


def _validate_socket(value: object, label: str) -> None:
    socket = _require_exact_mapping(value, _SOCKET_FIELDS, label)
    _require_string(socket["name"], f"{label} name", allow_empty=True)
    _require_string(socket["identifier"], f"{label} identifier", allow_empty=True)
    socket_type = _require_string(socket["type"], f"{label} type")
    if socket_type not in _NODE_SOCKET_TYPES:
        raise ValueError(f"{label} type is not a supported Blender socket identifier")
    if not isinstance(socket["enabled"], bool) or not isinstance(socket["is_linked"], bool):
        raise ValueError(f"{label} enabled/is_linked must be boolean")
    if socket_type in _NODE_SOCKET_POINTER_TYPES:
        default = _require_exact_mapping(
            socket["default"], _DEPENDENCY_VALUE_FIELDS, f"{label} default"
        )
        if default["kind"] == "value":
            if default["value"] is not None:
                raise ValueError(f"{label} null pointer default must use value null")
        elif default["kind"] == "identity":
            _validate_dependency_value(
                default,
                f"{label} default",
                expected_identity_types=frozenset(
                    {_NODE_SOCKET_POINTER_TYPES[socket_type]}
                ),
            )
        else:
            raise ValueError(
                f"{label} pointer default must be an identity or explicit value null"
            )
    elif socket_type in {"NodeSocketVectorTranslation", "NodeSocketVectorXYZ"}:
        _validate_vector(socket["default"], 3, f"{label} default")
    else:
        _validate_json_value(socket["default"], f"{label} default")


def _validate_image(value: object, label: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an image dependency object")
    identity_fields = _identity_fields(value)
    if set(value) != identity_fields | _IMAGE_FIELDS:
        raise ValueError(f"{label} has missing or unknown image fields")
    identity = {field: value[field] for field in identity_fields}
    validated_identity = _validate_identity(identity, f"{label} identity")
    _require_identity_type(validated_identity, "Image", label)
    _require_string(value["filepath"], f"{label} filepath", allow_empty=True)
    source = _require_string(value["source"], f"{label} source")
    if source not in _IMAGE_SOURCES:
        raise ValueError(f"{label} source is not a supported Blender image source")
    size = value["size"]
    if not isinstance(size, list) or len(size) != 2:
        raise ValueError(f"{label} size must contain two integers")
    for index, item in enumerate(size):
        _require_integer(item, f"{label} size[{index}]", minimum=1)
    channels = _require_integer(value["channels"], f"{label} channels", minimum=1)
    if channels > 4:
        raise ValueError(f"{label} channels must be between 1 and 4")
    _require_integer(value["depth"], f"{label} depth", minimum=1)
    if not isinstance(value["is_float"], bool):
        raise ValueError(f"{label} is_float must be boolean")
    _require_string(value["file_format"], f"{label} file_format")
    if value["alpha_mode"] not in {"CHANNEL_PACKED", "NONE", "PREMUL", "STRAIGHT"}:
        raise ValueError(f"{label} alpha_mode is outside the Blender enum domain")
    _require_string(value["colorspace"], f"{label} colorspace")
    external_files = value["external_files"]
    if not isinstance(external_files, list):
        raise ValueError(f"{label} external_files must be a list")
    external_keys: list[str] = []
    for index, raw in enumerate(external_files):
        record = _require_exact_mapping(
            raw, _EXTERNAL_IMAGE_FIELDS, f"{label} external_files[{index}]"
        )
        path = _validate_absolute_safe_path(
            record["path"], f"{label} external_files[{index}] path"
        )
        resolved = _validate_absolute_safe_path(
            record["resolved_path"], f"{label} external_files[{index}] resolved_path"
        )
        _require_integer(
            record["bytes"], f"{label} external_files[{index}] bytes", minimum=1
        )
        for field in ("mtime_ns", "ctime_ns", "device", "inode"):
            _require_integer(record[field], f"{label} external_files[{index}] {field}")
        _require_integer(record["links"], f"{label} external_files[{index}] links", minimum=1)
        _validate_sha256(record["sha256"], f"{label} external_files[{index}]")
        external_path = Path(path)
        if not external_path.is_file() or str(external_path.resolve(strict=True)) != resolved:
            raise ValueError(f"{label} external image authority is missing or aliased")
        before = external_path.stat()
        if (
            before.st_size != record["bytes"]
            or before.st_mtime_ns != record["mtime_ns"]
            or before.st_ctime_ns != record["ctime_ns"]
            or before.st_dev & 0xFFFFFFFF != record["device"]
            or before.st_ino != record["inode"]
            or before.st_nlink != record["links"]
            or sha256_file(external_path) != str(record["sha256"]).upper()
        ):
            raise ValueError(f"{label} external image evidence does not match its file")
        after = external_path.stat()
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
            before.st_nlink,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            after.st_nlink,
        ):
            raise ValueError(f"{label} external image changed during validation")
        external_keys.append(_canonical_key([path, resolved]))
    if external_keys != sorted(external_keys) or len(external_keys) != len(set(external_keys)):
        raise ValueError(f"{label} external_files must be sorted and unique")
    packed_files = value["packed_files"]
    if not isinstance(packed_files, list):
        raise ValueError(f"{label} packed_files must be a list")
    for index, raw in enumerate(packed_files):
        record = _require_exact_mapping(
            raw, _PACKED_IMAGE_FIELDS, f"{label} packed_files[{index}]"
        )
        if record["index"] != index:
            raise ValueError(f"{label} packed file indices must be contiguous")
        _require_string(record["filepath"], f"{label} packed filepath", allow_empty=True)
        for field in ("view", "tile_number"):
            _require_integer(record[field], f"{label} packed {field}")
        _require_integer(record["bytes"], f"{label} packed bytes", minimum=1)
        _validate_sha256(record["sha256"], f"{label} packed file")
    pixels = _require_exact_mapping(value["pixels"], _PIXEL_FIELDS, f"{label} pixels")
    if pixels["encoding"] != "float32-little-endian":
        raise ValueError(f"{label} pixel encoding must be float32-little-endian")
    pixel_values = _require_integer(
        pixels["values"], f"{label} pixel values", minimum=1
    )
    if pixel_values != size[0] * size[1] * channels:
        raise ValueError(f"{label} pixel values do not match dimensions and channels")
    _validate_sha256(pixels["sha256"], f"{label} pixels")
    has_external = bool(external_files)
    has_packed = bool(packed_files)
    filepath = value["filepath"]
    if source in _FILE_BACKED_IMAGE_SOURCES:
        if has_external == has_packed:
            raise ValueError(
                f"{label} file-backed image requires exactly one external or packed authority"
            )
        if has_external:
            if len(external_files) != 1 or filepath != external_files[0]["path"]:
                raise ValueError(
                    f"{label} external image filepath must equal its single content authority"
                )
            if external_files[0]["path"] != external_files[0]["resolved_path"]:
                raise ValueError(f"{label} external image path must resolve without aliases")
        elif filepath != "":
            raise ValueError(f"{label} packed image filepath must be empty")
    elif has_external or has_packed or filepath != "":
        raise ValueError(
            f"{label} generated/viewer/render-result image cannot claim file authority"
        )


def _validate_dependency_value(
    value: object,
    label: str,
    *,
    expected_identity_types: frozenset[str] | None = None,
    expected_node_tree_type: str | None = None,
) -> None:
    record = _require_exact_mapping(value, _DEPENDENCY_VALUE_FIELDS, label)
    kind = record["kind"]
    if kind not in _DEPENDENCY_KINDS:
        raise ValueError(f"{label} kind is invalid")
    dependency = record["value"]
    if kind == "value":
        _validate_json_value(dependency, f"{label} value")
    elif kind == "identity":
        identity = _validate_identity(
            dependency, f"{label} identity", allow_empty_name=True
        )
        if expected_identity_types is not None and identity["type"] not in expected_identity_types:
            raise ValueError(f"{label} identity type is incompatible with its parent context")
    elif kind == "image":
        _validate_image(dependency, f"{label} image")
    else:
        _validate_node_tree(
            dependency,
            f"{label} node_tree",
            expected_type=expected_node_tree_type,
            allow_none=False,
        )


def _validate_pointer_mapping(
    value: object,
    label: str,
    *,
    tree_type: str,
    node_type: str,
    current_scene_identity: Mapping[str, object] | None = None,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    allowed: dict[str, tuple[str, frozenset[str] | str]] = {
        "parent": ("identity", _NODE_TYPES_BY_TREE[tree_type]),
    }
    if node_type == "ShaderNodeGroup":
        allowed["node_tree"] = ("node_tree", "ShaderNodeTree")
    elif node_type == "GeometryNodeGroup":
        allowed["node_tree"] = ("node_tree", "GeometryNodeTree")
    elif node_type == "CompositorNodeGroup":
        allowed["node_tree"] = ("node_tree", "CompositorNodeTree")
    elif node_type == "ShaderNodeTexImage":
        allowed.update(
            {
                "color_mapping": ("identity", frozenset({"ColorMapping"})),
                "image": ("image", frozenset()),
                "image_user": ("identity", frozenset({"ImageUser"})),
                "texture_mapping": ("identity", frozenset({"TexMapping"})),
            }
        )
    elif node_type == "CompositorNodeRLayers":
        allowed["scene"] = ("identity", frozenset({"Scene"}))
    if set(value) != set(allowed):
        raise ValueError(f"{label} has missing or unknown pointer properties")
    for name, dependency in value.items():
        _require_string(name, f"{label} property")
        if dependency is None:
            if name != "parent":
                raise ValueError(f"{label}.{name} cannot be null")
            continue
        kind, domain = allowed[name]
        if kind == "image":
            _validate_image(dependency, f"{label}.{name}")
        elif kind == "node_tree":
            _validate_node_tree(
                dependency,
                f"{label}.{name}",
                expected_type=str(domain),
                allow_none=False,
                current_scene_identity=current_scene_identity,
            )
        else:
            identity = _validate_identity(
                dependency, f"{label}.{name}", allow_empty_name=True
            )
            if identity["type"] not in domain:
                raise ValueError(f"{label}.{name} identity type is incompatible")
    if (
        node_type == "CompositorNodeRLayers"
        and current_scene_identity is not None
        and value["scene"] != current_scene_identity
    ):
        raise ValueError(
            f"{label}.scene must resolve exactly to the current proof scene"
        )


def _validate_node_tree(
    value: object,
    label: str,
    *,
    expected_type: str | None = None,
    allow_none: bool = True,
    current_scene_identity: Mapping[str, object] | None = None,
) -> None:
    if value is None:
        if allow_none:
            return
        raise ValueError(f"{label} cannot be null")
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be null or an exact node tree")
    if set(value) == _NODE_TREE_REFERENCE_FIELDS:
        identity = _validate_identity(value["identity"], f"{label} identity")
        if identity["type"] not in _NODE_TREE_TYPES:
            raise ValueError(f"{label} identity type must be a supported Blender NodeTree")
        if expected_type is not None and identity["type"] != expected_type:
            raise ValueError(f"{label} node-tree type is incompatible with its parent context")
        if value["recursive_reference"] is not True:
            raise ValueError(f"{label} recursive_reference must equal true")
        return
    tree = _require_exact_mapping(value, _NODE_TREE_FIELDS, label)
    identity = _validate_identity(tree["identity"], f"{label} identity")
    tree_type = str(identity["type"])
    if tree_type not in _NODE_TREE_TYPES:
        raise ValueError(f"{label} identity type must be a supported Blender NodeTree")
    if expected_type is not None and tree_type != expected_type:
        raise ValueError(f"{label} node-tree type is incompatible with its parent context")
    nodes = _validate_sorted_unique(
        tree["nodes"], label + " nodes", lambda item: _canonical_key(
            [item.get("name"), item.get("type")]
        ) if isinstance(item, Mapping) else ""
    )
    node_names: set[str] = set()
    for index, raw in enumerate(nodes):
        node = _require_exact_mapping(raw, _NODE_FIELDS, f"{label} nodes[{index}]")
        name = _require_string(node["name"], f"{label} node name")
        if name in node_names:
            raise ValueError(f"{label} node names must be unique")
        node_names.add(name)
        node_type = _require_string(node["type"], f"{label} node type")
        if node_type in _UNSAFE_NODE_TYPES_BY_TREE.get(tree_type, frozenset()):
            raise ValueError(
                f"{label} contains unsafe external writer node type {node_type}"
            )
        if node_type not in _NODE_TYPES_BY_TREE[tree_type]:
            raise ValueError(f"{label} node type is not supported for {tree_type}")
        if not isinstance(node["mute"], bool):
            raise ValueError(f"{label} node mute must be boolean")
        expected_property_fields = _NODE_COMMON_PROPERTY_FIELDS | _NODE_EXTRA_PROPERTY_FIELDS.get(
            node_type, frozenset()
        )
        enum_domains: dict[str, frozenset[str]] = {
            "bl_icon": frozenset({"NONE"}),
            "color_tag": frozenset(
                {
                    "ATTRIBUTE", "COLOR", "CONVERTER", "DISTORT", "FILTER", "GEOMETRY",
                    "GROUP", "INPUT", "INTERFACE", "MATTE", "NONE", "OUTPUT", "PATTERN",
                    "SCRIPT", "SHADER", "TEXTURE", "VECTOR",
                }
            ),
            "warning_propagation": frozenset({"ALL", "NONE"}),
        }
        static_type = _NODE_STATIC_TYPES.get(node_type)
        if static_type is not None:
            enum_domains["bl_static_type"] = frozenset({static_type})
            enum_domains["type"] = frozenset({static_type})
        if node_type == "ShaderNodeMath":
            enum_domains["operation"] = _MATH_OPERATIONS
        elif node_type == "ShaderNodeTexImage":
            enum_domains.update(
                {
                    "extension": frozenset({"CLIP", "EXTEND", "MIRROR", "REPEAT"}),
                    "interpolation": frozenset({"Closest", "Cubic", "Linear", "Smart"}),
                    "projection": frozenset({"BOX", "FLAT", "SPHERE", "TUBE"}),
                }
            )
        elif node_type == "ShaderNodeBsdfPrincipled":
            enum_domains.update(
                {
                    "distribution": frozenset({"MULTI_GGX"}),
                    "subsurface_method": frozenset(
                        {"BURLEY", "RANDOM_WALK", "RANDOM_WALK_SKIN"}
                    ),
                }
            )
        elif node_type in {
            "ShaderNodeOutputLight",
            "ShaderNodeOutputMaterial",
            "ShaderNodeOutputWorld",
        }:
            enum_domains["target"] = frozenset({"ALL", "CYCLES", "EEVEE"})
        properties = _validate_properties(
            node["properties"],
            f"{label} node properties",
            exact_fields=expected_property_fields,
            enum_domains=enum_domains,
        )
        if properties.get("bl_idname") != node_type:
            raise ValueError(f"{label} node properties bl_idname does not match node type")
        for socket_field in ("inputs", "outputs"):
            sockets = node[socket_field]
            if not isinstance(sockets, list):
                raise ValueError(f"{label} node {socket_field} must be a list")
            for socket_index, socket in enumerate(sockets):
                _validate_socket(
                    socket, f"{label} node {name} {socket_field}[{socket_index}]"
                )
        _validate_pointer_mapping(
            node["data"],
            f"{label} node {name} data",
            tree_type=tree_type,
            node_type=node_type,
            current_scene_identity=current_scene_identity,
        )
    node_types_by_name = {
        str(node["name"]): str(node["type"]) for node in nodes
    }
    for node in nodes:
        parent = node["data"].get("parent")
        if parent is not None and node_types_by_name.get(parent["name"]) != parent["type"]:
            raise ValueError(f"{label} node parent identity does not resolve in its tree")
    links = _validate_sorted_unique(
        tree["links"], label + " links", lambda item: _canonical_key(
            [
                item.get("from_node"),
                item.get("from_socket"),
                item.get("from_socket_identifier"),
                item.get("to_node"),
                item.get("to_socket"),
                item.get("to_socket_identifier"),
            ]
        ) if isinstance(item, Mapping) else ""
    )
    for index, raw in enumerate(links):
        link = _require_exact_mapping(raw, _LINK_FIELDS, f"{label} links[{index}]")
        for field in _LINK_FIELDS:
            _require_string(link[field], f"{label} link {field}", allow_empty=True)
        for field in ("from_socket_identifier", "to_socket_identifier"):
            _require_string(link[field], f"{label} link {field}")
        if link["from_node"] not in node_names or link["to_node"] not in node_names:
            raise ValueError(f"{label} link references an unknown node")
    node_by_name = {str(node["name"]): node for node in nodes}
    for link in links:
        source_sockets = {
            str(socket["identifier"]): str(socket["name"])
            for socket in node_by_name[str(link["from_node"])]["outputs"]
        }
        target_sockets = {
            str(socket["identifier"]): str(socket["name"])
            for socket in node_by_name[str(link["to_node"])]["inputs"]
        }
        if (
            source_sockets.get(str(link["from_socket_identifier"]))
            != link["from_socket"]
            or target_sockets.get(str(link["to_socket_identifier"]))
            != link["to_socket"]
        ):
            raise ValueError(f"{label} link socket name/identifier pair is inconsistent")
    linked_outputs = {
        (str(link["from_node"]), str(link["from_socket_identifier"]))
        for link in links
    }
    linked_inputs = {
        (str(link["to_node"]), str(link["to_socket_identifier"]))
        for link in links
    }
    for node_name, node in node_by_name.items():
        output_identifiers = {str(socket["identifier"]) for socket in node["outputs"]}
        input_identifiers = {str(socket["identifier"]) for socket in node["inputs"]}
        if (
            "" in output_identifiers
            or "" in input_identifiers
            or len(output_identifiers) != len(node["outputs"])
            or len(input_identifiers) != len(node["inputs"])
        ):
            raise ValueError(f"{label} node socket identifiers must be nonempty and unique")
        if any(
            from_name == node_name and identifier not in output_identifiers
            for from_name, identifier in linked_outputs
        ) or any(
            to_name == node_name and identifier not in input_identifiers
            for to_name, identifier in linked_inputs
        ):
            raise ValueError(f"{label} link references an unknown node socket")
        for socket in node["outputs"]:
            if socket["is_linked"] is (
                (node_name, str(socket["identifier"])) not in linked_outputs
            ):
                raise ValueError(f"{label} output socket link state is inconsistent")
        for socket in node["inputs"]:
            if socket["is_linked"] is (
                (node_name, str(socket["identifier"])) not in linked_inputs
            ):
                raise ValueError(f"{label} input socket link state is inconsistent")


def _validate_modifier(value: object, label: str) -> None:
    modifier = _require_exact_mapping(value, _MODIFIER_FIELDS, label)
    _require_string(modifier["name"], f"{label} name")
    modifier_type = _require_string(modifier["type"], f"{label} type")
    if modifier_type not in _MODIFIER_TYPES:
        raise ValueError(f"{label} type is outside the pinned Blender modifier domain")
    _validate_properties(
        modifier["properties"],
        f"{label} properties",
        exact_fields=_NODES_MODIFIER_PROPERTY_FIELDS,
        enum_domains={"bake_target": frozenset({"DISK", "PACKED"})},
    )
    references = modifier["references"]
    if not isinstance(references, Mapping) or set(references) != {"node_group", "properties"}:
        raise ValueError(f"{label} references must match the Geometry Nodes pointer schema")
    node_group_identity = _validate_identity(
        references["node_group"], f"{label} node_group reference"
    )
    _require_identity_type(
        node_group_identity, "GeometryNodeTree", f"{label} node_group reference"
    )
    interface_identity = _validate_identity(
        references["properties"],
        f"{label} properties reference",
        allow_empty_name=True,
    )
    _require_identity_type(
        interface_identity,
        "GeometryNodesModifierInterface",
        f"{label} properties reference",
    )
    id_properties = _validate_sorted_unique(
        modifier["id_properties"], label + " ID-properties", lambda item: str(
            item.get("name", "")
        ) if isinstance(item, Mapping) else ""
    )
    for index, raw in enumerate(id_properties):
        record = _require_exact_mapping(raw, _ID_PROPERTY_FIELDS, f"{label} ID-property[{index}]")
        _require_string(record["name"], f"{label} ID-property name")
        _validate_dependency_value(record["dependency"], f"{label} ID-property dependency")
    if id_properties:
        raise ValueError(f"{label} legacy ID-properties are not emitted by pinned Blender 5.2")
    interface_inputs = modifier["interface_inputs"]
    if not isinstance(interface_inputs, list):
        raise ValueError(f"{label} interface_inputs must be a list")
    prior_index = -1
    identifiers: set[str] = set()
    for offset, raw in enumerate(interface_inputs):
        record = _require_exact_mapping(
            raw, _INTERFACE_INPUT_FIELDS, f"{label} interface_inputs[{offset}]"
        )
        index = _require_integer(record["index"], f"{label} interface input index")
        if index <= prior_index:
            raise ValueError(f"{label} interface inputs must retain deterministic interface order")
        prior_index = index
        identifier = _require_string(record["identifier"], f"{label} interface identifier")
        if identifier in identifiers:
            raise ValueError(f"{label} interface identifiers must be unique")
        identifiers.add(identifier)
        _require_string(record["name"], f"{label} interface name")
        socket_type = _require_string(
            record["socket_type"], f"{label} interface socket_type"
        )
        if socket_type not in _GEOMETRY_INTERFACE_SOCKET_TYPES:
            raise ValueError(f"{label} interface socket_type is unsupported")
        if socket_type == "NodeSocketFloat":
            property_fields = frozenset({"attribute_name", "name", "type", "value"})
            binding_types = frozenset({"VALUE"})
        elif socket_type == "NodeSocketGeometry":
            property_fields = frozenset({"name", "type"})
            binding_types = frozenset({"FALLBACK"})
        else:
            property_fields = frozenset({"name", "type"})
            binding_types = frozenset({"VALUE"})
        _validate_properties(
            record["properties"],
            f"{label} interface properties",
            exact_fields=property_fields,
            enum_domains={"type": binding_types},
        )
        deps = record["references"]
        if not isinstance(deps, Mapping):
            raise ValueError(f"{label} interface references must be an object")
        expected_reference_types = {
            "NodeSocketCollection": frozenset({"Collection"}),
            "NodeSocketImage": frozenset({"Image"}),
            "NodeSocketMaterial": frozenset({"Material"}),
            "NodeSocketObject": frozenset({"Object"}),
        }
        if socket_type in {"NodeSocketFloat", "NodeSocketGeometry"}:
            if deps:
                raise ValueError(f"{label} scalar interface input cannot carry pointers")
        else:
            if set(deps) != {"value"}:
                raise ValueError(f"{label} pointer interface input requires exactly value")
            dependency = deps["value"]
            if socket_type == "NodeSocketImage":
                parsed = _require_exact_mapping(
                    dependency,
                    _DEPENDENCY_VALUE_FIELDS,
                    f"{label} interface image reference",
                )
                if parsed["kind"] != "image":
                    raise ValueError(f"{label} image socket requires an image dependency")
                _validate_dependency_value(
                    dependency, f"{label} interface image reference"
                )
            else:
                parsed = _require_exact_mapping(
                    dependency,
                    _DEPENDENCY_VALUE_FIELDS,
                    f"{label} interface identity reference",
                )
                if parsed["kind"] != "identity":
                    raise ValueError(f"{label} pointer socket requires an identity dependency")
                _validate_dependency_value(
                    dependency,
                    f"{label} interface identity reference",
                    expected_identity_types=expected_reference_types[socket_type],
                )
    node_group = modifier["node_group"]
    _validate_node_tree(
        node_group,
        f"{label} node_group",
        expected_type="GeometryNodeTree",
        allow_none=False,
    )
    if node_group_identity != node_group["identity"]:
        raise ValueError(f"{label} node_group reference does not match its full record")


def _validate_object(value: object, label: str) -> None:
    obj = _require_exact_mapping(value, _OBJECT_FIELDS, label)
    identity = _validate_identity(obj["identity"], f"{label} identity")
    _require_identity_type(identity, "Object", label)
    object_type = _require_string(obj["object_type"], f"{label} object_type")
    if object_type not in _OBJECT_TYPES:
        raise ValueError(f"{label} object_type is not a supported Blender enum")
    data = obj["data"]
    expected_data_types = _OBJECT_DATA_TYPES.get(object_type)
    if expected_data_types is None:
        raise ValueError(f"{label} object_type is outside the closed capture schema")
    if bool(expected_data_types) is (data is None):
        raise ValueError(f"{label} data presence is incompatible with object_type")
    if data is not None:
        if not isinstance(data, Mapping):
            raise ValueError(f"{label} data must be null or an object")
        expected = _OBJECT_DATA_FIELDS | ({"geometry"} if "geometry" in data else set())
        data = _require_exact_mapping(data, expected, f"{label} data")
        data_identity = _validate_identity(data["identity"], f"{label} data identity")
        if data_identity["type"] not in expected_data_types:
            raise ValueError(f"{label} data identity type is incompatible with object_type")
        _validate_properties(data["properties"], f"{label} data properties")
        if object_type == "MESH" and "geometry" not in data:
            raise ValueError(f"{label} mesh data requires a geometry fingerprint")
        if "geometry" in data:
            geometry = _require_exact_mapping(data["geometry"], _GEOMETRY_FIELDS, f"{label} geometry")
            _validate_sha256(geometry["sha256"], f"{label} geometry")
            for field in _GEOMETRY_FIELDS - {"sha256"}:
                _require_integer(geometry[field], f"{label} geometry {field}")
    _validate_transform(obj["transform"], f"{label} transform")
    if not isinstance(obj["hide_render"], bool) or not isinstance(obj["hide_viewport"], bool):
        raise ValueError(f"{label} visibility fields must be boolean")
    _validate_properties(obj["properties"], f"{label} properties")
    collections = _validate_sorted_unique(
        obj["collections"], label + " collections", lambda item: _canonical_key(item)
    )
    for index, raw_membership in enumerate(collections):
        membership = _require_exact_mapping(
            raw_membership,
            _COLLECTION_MEMBERSHIP_FIELDS,
            f"{label} collections[{index}]",
        )
        collection_identity = _validate_identity(
            membership["identity"], f"{label} collections[{index}] identity"
        )
        _require_identity_type(
            collection_identity, "Collection", f"{label} collections[{index}]"
        )
        membership_path = _validate_path(
            membership["path"], f"{label} collections[{index}] path"
        )
        if membership_path[-1] != collection_identity["name"]:
            raise ValueError(f"{label} collection membership path leaf is inconsistent")
    slots = obj["material_slots"]
    if not isinstance(slots, list):
        raise ValueError(f"{label} material_slots must be a list")
    for index, raw in enumerate(slots):
        slot = _require_exact_mapping(raw, _MATERIAL_SLOT_FIELDS, f"{label} material_slots[{index}]")
        if slot["index"] != index:
            raise ValueError(f"{label} material slot indices must be contiguous")
        _require_string(slot["name"], f"{label} material slot name", allow_empty=True)
        if slot["link"] not in {"DATA", "OBJECT"}:
            raise ValueError(f"{label} material slot link must be DATA or OBJECT")
        material_identity = _validate_identity(
            slot["material"], f"{label} material slot", allow_none=True
        )
        if material_identity is not None:
            _require_identity_type(
                material_identity, "Material", f"{label} material slot"
            )
    modifiers = obj["modifiers"]
    if not isinstance(modifiers, list):
        raise ValueError(f"{label} modifiers must be a list")
    modifier_names: set[str] = set()
    for index, modifier in enumerate(modifiers):
        _validate_modifier(modifier, f"{label} modifiers[{index}]")
        name = str(modifier["name"])
        if name in modifier_names:
            raise ValueError(f"{label} modifier names must be unique")
        modifier_names.add(name)


def _validate_material(value: object, label: str) -> None:
    material = _require_exact_mapping(value, _MATERIAL_FIELDS, label)
    identity = _validate_identity(material["identity"], f"{label} identity")
    _require_identity_type(identity, "Material", label)
    _validate_properties(material["properties"], f"{label} properties")
    _validate_node_tree(
        material["node_tree"],
        f"{label} node_tree",
        expected_type="ShaderNodeTree",
    )


def _validate_path(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a nonempty hierarchy path")
    return [_require_string(item, f"{label} segment") for item in value]


def _validate_collection_tree(
    value: object,
    label: str,
    *,
    parent_path: list[str] | None = None,
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an exact collection record")
    if set(value) == _COLLECTION_REFERENCE_FIELDS:
        identity = _validate_identity(value["identity"], f"{label} identity")
        _require_identity_type(identity, "Collection", label)
        path = _validate_path(value["path"], f"{label} path")
        if path[-1] != identity["name"]:
            raise ValueError(f"{label} path leaf does not match collection identity")
        if parent_path is None and path != [identity["name"]]:
            raise ValueError(f"{label} root path must equal its collection identity")
        if parent_path is not None and path != parent_path + [identity["name"]]:
            raise ValueError(f"{label} path does not match its collection hierarchy")
        if value["recursive_reference"] is not True:
            raise ValueError(f"{label} recursive collection reference is invalid")
        return
    record = _require_exact_mapping(value, _COLLECTION_FIELDS, label)
    identity = _validate_identity(record["identity"], f"{label} identity")
    _require_identity_type(identity, "Collection", label)
    path = _validate_path(record["path"], f"{label} path")
    if path[-1] != identity["name"]:
        raise ValueError(f"{label} path leaf does not match collection identity")
    if parent_path is None and path != [identity["name"]]:
        raise ValueError(f"{label} root path must equal its collection identity")
    if parent_path is not None and path != parent_path + [identity["name"]]:
        raise ValueError(f"{label} path does not match its collection hierarchy")
    if not isinstance(record["hide_render"], bool) or not isinstance(record["hide_viewport"], bool):
        raise ValueError(f"{label} visibility fields must be boolean")
    _validate_properties(record["properties"], f"{label} properties")
    objects = _validate_sorted_unique(
        record["objects"], label + " objects", lambda item: _canonical_key(item)
    )
    for index, obj in enumerate(objects):
        object_identity = _validate_identity(obj, f"{label} objects[{index}]")
        _require_identity_type(
            object_identity, "Object", f"{label} objects[{index}]"
        )
    children = _validate_sorted_unique(
        record["children"], label + " children", lambda item: _canonical_key(
            item.get("identity")
        ) if isinstance(item, Mapping) else ""
    )
    for index, child in enumerate(children):
        _validate_collection_tree(
            child, f"{label} children[{index}]", parent_path=path
        )


def _validate_layer_collection(
    value: object,
    label: str,
    *,
    parent_path: list[str] | None = None,
) -> None:
    record = _require_exact_mapping(value, _LAYER_COLLECTION_FIELDS, label)
    identity = _validate_identity(record["collection"], f"{label} collection")
    _require_identity_type(identity, "Collection", f"{label} collection")
    path = _validate_path(record["path"], f"{label} path")
    if path[-1] != identity["name"]:
        raise ValueError(f"{label} path leaf does not match layer collection identity")
    if parent_path is None and path != [identity["name"]]:
        raise ValueError(f"{label} root path must equal its collection identity")
    if parent_path is not None and path != parent_path + [identity["name"]]:
        raise ValueError(f"{label} path does not match its layer hierarchy")
    for field in ("exclude", "holdout", "indirect_only", "hide_viewport"):
        if not isinstance(record[field], bool):
            raise ValueError(f"{label} {field} must be boolean")
    children = _validate_sorted_unique(
        record["children"], label + " children", lambda item: _canonical_key(
            item.get("collection")
        ) if isinstance(item, Mapping) else ""
    )
    for index, child in enumerate(children):
        _validate_layer_collection(
            child, f"{label} children[{index}]", parent_path=path
        )


def _dependency_digest(settings: Mapping[str, object]) -> str:
    payload = {
        field: settings[field]
        for field in (
            "scene_identity",
            "objects",
            "materials",
            "images",
            "collection_tree",
            "view_layers",
        )
    }
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest().upper()


def _identity_key(value: Mapping[str, object]) -> str:
    return _canonical_key(value)


def _validate_dependency_graph(
    authored: Mapping[str, object], label: str
) -> None:
    objects = {
        _identity_key(item["identity"]): item for item in authored["objects"]
    }
    materials = {
        _identity_key(item["identity"]): item for item in authored["materials"]
    }
    images = {
        _identity_key({field: item[field] for field in _identity_fields(item)}): item
        for item in authored["images"]
    }

    collection_paths: dict[tuple[str, ...], str] = {}
    collection_identities: set[str] = set()
    tree_memberships: dict[str, set[tuple[str, ...]]] = {}

    def visit_collection(record: Mapping[str, object]) -> None:
        path = tuple(str(segment) for segment in record["path"])
        identity_key = _identity_key(record["identity"])
        if path in collection_paths:
            raise ValueError(f"{label} collection paths must be globally unique")
        collection_paths[path] = identity_key
        collection_identities.add(identity_key)
        if set(record) == _COLLECTION_REFERENCE_FIELDS:
            return
        for object_identity in record["objects"]:
            object_key = _identity_key(object_identity)
            if object_key not in objects:
                raise ValueError(f"{label} collection contains an unknown object identity")
            tree_memberships.setdefault(object_key, set()).add(path)
        for child in record["children"]:
            visit_collection(child)

    visit_collection(authored["collection_tree"])

    object_memberships: dict[str, set[tuple[str, ...]]] = {}
    for object_key, obj in objects.items():
        memberships: set[tuple[str, ...]] = set()
        for membership in obj["collections"]:
            path = tuple(str(segment) for segment in membership["path"])
            identity_key = _identity_key(membership["identity"])
            if collection_paths.get(path) != identity_key:
                raise ValueError(
                    f"{label} object collection membership path does not resolve"
                )
            memberships.add(path)
        if not memberships:
            raise ValueError(f"{label} scene object must belong to a captured collection")
        object_memberships[object_key] = memberships
    if object_memberships != {
        key: tree_memberships.get(key, set()) for key in objects
    }:
        raise ValueError(f"{label} object and collection memberships are inconsistent")

    expected_layer_paths = set(collection_paths)

    def visit_layer(record: Mapping[str, object], seen: set[tuple[str, ...]]) -> None:
        path = tuple(str(segment) for segment in record["path"])
        identity_key = _identity_key(record["collection"])
        if path in seen or collection_paths.get(path) != identity_key:
            raise ValueError(f"{label} layer collection path does not resolve uniquely")
        seen.add(path)
        for child in record["children"]:
            visit_layer(child, seen)

    for layer in authored["view_layers"]:
        seen: set[tuple[str, ...]] = set()
        visit_layer(layer["layer_collection"], seen)
        if seen != expected_layer_paths:
            raise ValueError(
                f"{label} view-layer hierarchy does not match the scene collection hierarchy"
            )

    def require_registry_identity(
        identity: Mapping[str, object] | None,
        registry: Mapping[str, object] | set[str],
        reference_label: str,
    ) -> None:
        if identity is None:
            return
        key = _identity_key(identity)
        if key not in registry:
            raise ValueError(f"{reference_label} does not resolve to a captured registry")

    camera_key = _identity_key(authored["camera"]["identity"])
    if camera_key not in objects or objects[camera_key]["object_type"] != "CAMERA":
        raise ValueError(f"{label} camera identity does not resolve to a camera object")
    require_registry_identity(
        authored["camera"]["dof"]["focus_object"], objects, f"{label} focus object"
    )
    captured_light_keys: set[str] = set()
    light_data_types = {
        "AREA": "AreaLight",
        "POINT": "PointLight",
        "SPOT": "SpotLight",
        "SUN": "SunLight",
    }
    for light in authored["lights"]:
        key = _identity_key(light["identity"])
        if key not in objects or objects[key]["object_type"] != "LIGHT":
            raise ValueError(f"{label} light identity does not resolve to a light object")
        captured_light_keys.add(key)
        if objects[key]["data"]["identity"]["type"] != light_data_types[light["type"]]:
            raise ValueError(f"{label} light data type is incompatible with light type")
    scene_light_keys = {
        key for key, obj in objects.items() if obj["object_type"] == "LIGHT"
    }
    if captured_light_keys != scene_light_keys:
        raise ValueError(f"{label} light registry does not match scene light objects")
    for layer in authored["view_layers"]:
        require_registry_identity(
            layer["material_override"], materials, f"{label} material override"
        )
    for obj in authored["objects"]:
        require_registry_identity(
            obj["transform"]["parent"], objects, f"{label} object parent"
        )
        for slot in obj["material_slots"]:
            require_registry_identity(
                slot["material"], materials, f"{label} material slot"
            )
        for modifier in obj["modifiers"]:
            for interface_input in modifier["interface_inputs"]:
                dependency = interface_input["references"].get("value")
                if dependency is None:
                    continue
                if dependency["kind"] == "identity":
                    identity = dependency["value"]
                    registries = {
                        "Collection": collection_identities,
                        "Material": materials,
                        "Object": objects,
                    }
                    require_registry_identity(
                        identity,
                        registries[identity["type"]],
                        f"{label} Geometry Nodes interface identity",
                    )

    full_node_trees: dict[str, str] = {}
    recursive_node_tree_references: set[str] = set()
    referenced_images: dict[str, str] = {}
    socket_identity_references: list[tuple[Mapping[str, object], str]] = []

    def visit_nested(value: object) -> None:
        if isinstance(value, Mapping):
            if "source" in value and set(value) == _identity_fields(value) | _IMAGE_FIELDS:
                identity = {field: value[field] for field in _identity_fields(value)}
                key = _identity_key(identity)
                encoded = _canonical_key(value)
                prior = referenced_images.setdefault(key, encoded)
                if prior != encoded:
                    raise ValueError(f"{label} image identity has conflicting records")
                return
            if set(value) == _NODE_TREE_REFERENCE_FIELDS:
                recursive_node_tree_references.add(_identity_key(value["identity"]))
                return
            if set(value) == _NODE_TREE_FIELDS:
                key = _identity_key(value["identity"])
                encoded = _canonical_key(value)
                prior = full_node_trees.setdefault(key, encoded)
                if prior != encoded:
                    raise ValueError(f"{label} node-tree identity has conflicting records")
                for node in value["nodes"]:
                    for socket in (*node["inputs"], *node["outputs"]):
                        socket_type = str(socket["type"])
                        if socket_type not in _NODE_SOCKET_POINTER_TYPES:
                            continue
                        dependency = socket["default"]
                        if dependency["kind"] == "identity":
                            socket_identity_references.append(
                                (dependency["value"], socket_type)
                            )
                    visit_nested(node["data"])
                return
            for item in value.values():
                visit_nested(item)
        elif isinstance(value, list):
            for item in value:
                visit_nested(item)

    for field in ("lights", "world", "compositor", "materials", "objects"):
        visit_nested(authored[field])
    if not recursive_node_tree_references <= set(full_node_trees):
        raise ValueError(f"{label} recursive node-tree reference does not resolve")
    socket_image_keys = {
        _identity_key(identity)
        for identity, socket_type in socket_identity_references
        if _NODE_SOCKET_POINTER_TYPES[socket_type] == "Image"
    }
    if set(referenced_images) | socket_image_keys != set(images):
        raise ValueError(f"{label} image registry does not match referenced images")
    for key, encoded in referenced_images.items():
        if _canonical_key(images[key]) != encoded:
            raise ValueError(f"{label} image reference differs from its registry record")
    socket_registries: dict[str, Mapping[str, object] | set[str]] = {
        "Collection": collection_identities,
        "Image": images,
        "Material": materials,
        "Object": objects,
    }
    for identity, socket_type in socket_identity_references:
        identity_type = _NODE_SOCKET_POINTER_TYPES[socket_type]
        require_registry_identity(
            identity,
            socket_registries[identity_type],
            f"{label} node socket {identity_type} identity",
        )


def _validate_authored_settings(value: object, label: str) -> Mapping[str, object]:
    authored = _require_exact_mapping(value, _AUTHORED_SETTINGS_FIELDS, label)
    scene_identity = _validate_identity(
        authored["scene_identity"], f"{label} scene identity"
    )
    _require_identity_type(scene_identity, "Scene", f"{label} scene")
    camera = _require_exact_mapping(authored["camera"], _CAMERA_SETTINGS_FIELDS, f"{label} camera")
    camera_identity = _validate_identity(camera["identity"], f"{label} camera identity")
    _require_identity_type(camera_identity, "Object", f"{label} camera")
    _validate_transform(camera["transform"], f"{label} camera transform")
    if camera["type"] not in {"PERSP", "ORTHO", "PANO"}:
        raise ValueError(f"{label} camera type is invalid")
    for field in (
        "lens", "sensor_width", "sensor_height", "shift_x", "shift_y", "clip_start", "clip_end"
    ):
        _require_number(camera[field], f"{label} camera {field}")
    if camera["sensor_fit"] not in {"AUTO", "HORIZONTAL", "VERTICAL"}:
        raise ValueError(f"{label} camera sensor_fit is outside the Blender enum domain")
    dof = _require_exact_mapping(
        camera["dof"],
        {
            "use_dof", "focus_object", "focus_distance", "aperture_fstop",
            "aperture_blades", "aperture_rotation", "aperture_ratio",
        },
        f"{label} camera DOF",
    )
    if not isinstance(dof["use_dof"], bool):
        raise ValueError(f"{label} camera use_dof must be boolean")
    focus_object = _validate_identity(
        dof["focus_object"], f"{label} focus object", allow_none=True
    )
    if focus_object is not None:
        _require_identity_type(focus_object, "Object", f"{label} focus object")
    for field in ("focus_distance", "aperture_fstop", "aperture_rotation", "aperture_ratio"):
        _require_number(dof[field], f"{label} DOF {field}")
    _require_integer(dof["aperture_blades"], f"{label} aperture_blades")

    lights = _validate_sorted_unique(
        authored["lights"], label + " lights", lambda item: _canonical_key(
            item.get("identity")
        ) if isinstance(item, Mapping) else ""
    )
    light_fields = {
        "identity", "transform", "type", "color", "energy", "shape", "size",
        "size_y", "spot_size", "spot_blend", "shadow_soft_size", "properties", "node_tree",
    }
    for index, raw in enumerate(lights):
        light = _require_exact_mapping(raw, light_fields, f"{label} lights[{index}]")
        light_identity = _validate_identity(light["identity"], f"{label} light identity")
        _require_identity_type(light_identity, "Object", f"{label} light")
        _validate_transform(light["transform"], f"{label} light transform")
        if light["type"] not in {"AREA", "POINT", "SPOT", "SUN"}:
            raise ValueError(f"{label} light type is outside the Blender enum domain")
        _validate_vector(light["color"], 3, f"{label} light color")
        for field in ("energy", "size", "size_y", "spot_size", "spot_blend", "shadow_soft_size"):
            _require_number(light[field], f"{label} light {field}")
        if light["type"] == "AREA":
            if light["shape"] not in {"DISK", "ELLIPSE", "RECTANGLE", "SQUARE"}:
                raise ValueError(f"{label} area-light shape is outside the Blender enum domain")
        elif light["shape"] != "":
            raise ValueError(f"{label} non-area light cannot carry an area shape")
        _validate_properties(light["properties"], f"{label} light properties")
        _validate_node_tree(
            light["node_tree"],
            f"{label} light node_tree",
            expected_type="ShaderNodeTree",
        )

    world = authored["world"]
    if world is not None:
        world = _require_exact_mapping(
            world, {"identity", "color", "properties", "node_tree"}, f"{label} world"
        )
        world_identity = _validate_identity(world["identity"], f"{label} world identity")
        _require_identity_type(world_identity, "World", f"{label} world")
        _validate_vector(world["color"], 3, f"{label} world color")
        _validate_properties(world["properties"], f"{label} world properties")
        _validate_node_tree(
            world["node_tree"],
            f"{label} world node_tree",
            expected_type="ShaderNodeTree",
        )
    compositor = _require_exact_mapping(
        authored["compositor"], _COMPOSITOR_SETTINGS_FIELDS, f"{label} compositor"
    )
    if not isinstance(compositor["enabled"], bool):
        raise ValueError(f"{label} compositor enabled must be boolean")
    _validate_node_tree(
        compositor["node_tree"],
        f"{label} compositor node_tree",
        expected_type="CompositorNodeTree",
        current_scene_identity=scene_identity,
    )
    if compositor["enabled"] is not (compositor["node_tree"] is not None):
        raise ValueError(f"{label} compositor enabled state does not match node_tree")
    render = _require_exact_mapping(
        authored["render"], {"properties", "image_settings", "ffmpeg"}, f"{label} render"
    )
    _validate_properties(
        render["properties"],
        f"{label} render properties",
        enum_domains={"engine": _RENDER_ENGINES},
    )
    for field in ("image_settings", "ffmpeg"):
        _validate_properties(render[field], f"{label} render {field}")
    color = _require_exact_mapping(
        authored["color_management"], {"view", "display", "sequencer"}, f"{label} color management"
    )
    for field in ("view", "display", "sequencer"):
        _validate_properties(color[field], f"{label} color management {field}")
    _validate_properties(authored["cycles"], f"{label} cycles")

    view_layers = _validate_sorted_unique(
        authored["view_layers"], label + " view_layers", lambda item: str(
            item.get("name", "")
        ) if isinstance(item, Mapping) else ""
    )
    if not view_layers:
        raise ValueError(f"{label} requires at least one view layer")
    for index, raw in enumerate(view_layers):
        layer = _require_exact_mapping(raw, _VIEW_LAYER_FIELDS, f"{label} view_layers[{index}]")
        _require_string(layer["name"], f"{label} view layer name")
        _validate_properties(layer["properties"], f"{label} view layer properties")
        material_override = _validate_identity(
            layer["material_override"], f"{label} material override", allow_none=True
        )
        if material_override is not None:
            _require_identity_type(
                material_override, "Material", f"{label} material override"
            )
        _validate_layer_collection(layer["layer_collection"], f"{label} layer collection")

    objects = _validate_sorted_unique(
        authored["objects"],
        label + " objects",
        lambda item: _canonical_key(
            [
                item.get("identity", {}).get("name"),
                item.get("object_type"),
                item.get("identity", {}).get("library"),
            ]
        )
        if isinstance(item, Mapping)
        and isinstance(item.get("identity"), Mapping)
        else "",
    )
    for index, obj in enumerate(objects):
        _validate_object(obj, f"{label} objects[{index}]")
    materials = _validate_sorted_unique(
        authored["materials"], label + " materials", lambda item: _canonical_key(
            item.get("identity")
        ) if isinstance(item, Mapping) else ""
    )
    for index, material in enumerate(materials):
        _validate_material(material, f"{label} materials[{index}]")
    material_ids: dict[str, str] = {}
    for material in materials:
        identity = material["identity"]
        material_id = str(identity["pimm_material_id"])
        identity_key = _identity_key(identity)
        prior = material_ids.setdefault(material_id, identity_key)
        if prior != identity_key:
            raise ValueError(f"{label} pimm_material_id values must be unique per datablock")
    images = _validate_sorted_unique(
        authored["images"], label + " images", lambda item: _canonical_key(
            {field: item.get(field) for field in _identity_fields(item)}
        ) if isinstance(item, Mapping) else ""
    )
    for index, image in enumerate(images):
        _validate_image(image, f"{label} images[{index}]")
    _validate_collection_tree(authored["collection_tree"], f"{label} collection_tree")
    _validate_dependency_graph(authored, label)
    digest = _validate_sha256(authored["dependency_sha256"], f"{label} dependency digest")
    if digest != _dependency_digest(authored):
        raise ValueError(f"{label} dependency digest is inconsistent with dependency records")
    return authored


def validate_authored_settings(
    value: object, label: str = "authored settings"
) -> Mapping[str, object]:
    """Validate one complete Task 5 authored dependency graph and its digest."""

    return _validate_authored_settings(value, label)


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
    for phase in ("before", "after"):
        _validate_authored_settings(
            authored[phase], f"render metadata authored settings {phase}"
        )
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
