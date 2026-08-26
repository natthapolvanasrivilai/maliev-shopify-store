"""Fail-closed Cycles proof renderer and pinned-Pillow finalizer."""

from __future__ import annotations

import argparse
from array import array
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

from scripts.blender.pimm_production import blender_scene_validator
from scripts.blender.pimm_production import proof_contract as proof_module
from scripts.blender.pimm_production.contact_sheet import build_contact_sheet
from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT as CANONICAL_ASSET_ROOT
from scripts.blender.pimm_production.paths import require_within
from scripts.blender.pimm_production.proof_contract import (
    ProofContract,
    analyze_mask_metrics,
    effective_dimensions,
    validate_proof_contract,
    write_proof_manifest,
)
from scripts.blender.pimm_production.scene_contract import SceneContract
from scripts.blender.pimm_production.tool_policy import validate_tool_lock


RESULT_MARKER = "PIMM_PROOF_RENDER_JSON="
_PENDING_TO_PUBLISHED = {
    ".contact-sheet.pending.png": "contact-sheet.png",
    ".contact-sheet.pending.json": "contact-sheet.json",
    ".manifest.pending.json": "manifest.json",
}


@dataclass(frozen=True)
class _ScratchIdentity:
    path: Path
    resolved_path: Path
    stat_identity: tuple[int, ...]


def _fingerprint(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def _protected_paths(asset_root: Path, scene: SceneContract, scene_path: Path) -> dict[str, Path]:
    return {
        "source": asset_root / "sources" / f"PIMM-{scene.machine}-authoritative-source.step",
        "master": asset_root / Path(*PurePosixPath(scene.master_path).parts),
        "material_library": asset_root / Path(*PurePosixPath(scene.material_library_path).parts),
        "scene": scene_path,
    }


def _snapshot(paths: Mapping[str, Path]) -> dict[str, object]:
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ValueError("protected proof inputs are missing: " + "; ".join(missing))
    return {name: _fingerprint(path) for name, path in paths.items()}


def _validate_tools(lock_path: Path) -> tuple[dict[str, object], Path]:
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("free tool lock root must be an object")
    errors = validate_tool_lock(payload)
    tools = payload.get("tools")
    records = {
        str(item.get("id")): item
        for item in tools
        if isinstance(tools, list) and isinstance(item, Mapping)
    }
    for tool_id in ("blender", "python", "pillow"):
        record = records.get(tool_id)
        if not isinstance(record, Mapping):
            continue
        path = Path(str(record.get("path", "")))
        if not path.is_file():
            errors.append(f"{tool_id}: locked file is missing")
        elif sha256_file(path) != str(record.get("sha256", "")).upper():
            errors.append(f"{tool_id}: locked file SHA-256 mismatch")
    evidence = payload.get("license_evidence")
    mcp_evidence = evidence.get("blender-mcp") if isinstance(evidence, Mapping) else None
    if isinstance(mcp_evidence, Mapping):
        evidence_path = Path(str(mcp_evidence.get("path", "")))
        if not evidence_path.is_file():
            errors.append("blender-mcp: locked license evidence is missing")
        elif sha256_file(evidence_path) != str(mcp_evidence.get("sha256", "")).upper():
            errors.append("blender-mcp: locked license evidence SHA-256 mismatch")
    if errors:
        raise ValueError("free tool lock validation failed: " + "; ".join(errors))
    python_record = records["python"]
    return dict(payload), Path(str(python_record["path"])).resolve()


def _validate_executing_blender(
    bpy: Any, lock: Mapping[str, object]
) -> dict[str, str]:
    """Prove the process itself is the exact Blender executable in the lock."""

    tools = lock.get("tools")
    records = [
        item
        for item in (tools if isinstance(tools, list) else [])
        if isinstance(item, Mapping)
        and item.get("id") == "blender"
    ]
    if len(records) != 1:
        raise ValueError("free tool lock must contain exactly one Blender record")
    record = records[0]
    locked = Path(str(record.get("path", ""))).resolve()
    executing = Path(str(bpy.app.binary_path)).resolve()
    if executing != locked:
        raise ValueError(
            f"executing Blender path does not match lock: {executing} != {locked}"
        )
    locked_hash = str(record.get("sha256", "")).upper()
    actual_hash = sha256_file(executing)
    if actual_hash != locked_hash:
        raise ValueError("executing Blender SHA-256 does not match lock")
    version = str(record.get("version", ""))
    if not version or not str(bpy.app.version_string).startswith(version):
        raise ValueError("executing Blender version does not match lock")
    return {
        "binary_path": str(executing),
        "binary_sha256": actual_hash,
        "version": version,
    }


def _fixture_asset_root(path: Path) -> Path:
    import tempfile

    resolved = path.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if resolved == temporary_root:
        raise ValueError("fixture asset root cannot equal the system temporary root")
    try:
        resolved.relative_to(temporary_root)
    except ValueError as error:
        raise ValueError("fixture asset root must be beneath the system temporary root") from error
    return resolved


def _project_named_shafts(bpy: Any, camera: object) -> dict[str, list[float]]:
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    scene = bpy.context.scene
    regions: dict[str, list[float]] = {}
    for obj in bpy.data.objects:
        if getattr(obj, "type", None) != "MESH" or "shaft" not in obj.name.lower():
            continue
        points = [
            world_to_camera_view(scene, camera, obj.matrix_world @ Vector(corner))
            for corner in obj.bound_box
        ]
        visible = [point for point in points if point.z > 0]
        if not visible:
            continue
        left = max(0.0, min(point.x for point in visible))
        right = min(1.0, max(point.x for point in visible))
        bottom = max(0.0, min(point.y for point in visible))
        top = min(1.0, max(point.y for point in visible))
        if right > left and top > bottom:
            regions[obj.name] = [left, 1.0 - top, right, 1.0 - bottom]
    return regions


def _proof_environment_errors(bpy: Any) -> list[str]:
    """Authorize only exact, named, temporary proof-environment meshes."""

    errors: list[str] = []
    allowed = {"shadow-catcher": "PIMM_ENV_SHADOW_CATCHER"}
    for obj in bpy.data.objects:
        if getattr(obj, "type", None) != "MESH" or getattr(obj, "library", None) is not None:
            continue
        role = obj.get("pimm_proof_environment_role")
        expected_name = allowed.get(role)
        mesh = getattr(obj, "data", None)
        if expected_name is None or obj.name != expected_name:
            errors.append(f"unauthorized local proof environment mesh object: {obj.name}")
            continue
        if mesh is None or mesh.name != expected_name or mesh.get("pimm_proof_environment_role") != role:
            errors.append(f"proof environment mesh role mismatch: {obj.name}")
        if obj.get("pimm_stable_id") is not None:
            errors.append(f"proof environment mesh cannot carry product identity: {obj.name}")
        if role == "shadow-catcher" and getattr(obj, "is_shadow_catcher", False) is not True:
            errors.append(f"proof shadow catcher role lacks Cycles shadow-catcher state: {obj.name}")
        for material in getattr(mesh, "materials", ()):
            if material is None:
                continue
            if (
                material.name != "PIMM_ENV_SHADOW_CATCHER_MATERIAL"
                or material.get("pimm_proof_environment_role") != role
                or material.get("pimm_material_scope") is not None
            ):
                errors.append(f"unauthorized proof environment material: {material.name}")
    return errors


def _frame_fixture_scene(bpy: Any, camera: object) -> tuple[list[object], list[object]]:
    from mathutils import Vector

    meshes = [obj for obj in bpy.data.objects if getattr(obj, "type", None) == "MESH"]
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    if not points:
        raise ValueError("proof scene has no product mesh bounds")
    minimum = Vector(
        (
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        )
    )
    maximum = Vector(
        (
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        )
    )
    target = (minimum + maximum) * 0.5
    extent = max((maximum - minimum).length, 1.0)
    camera.location = target + Vector((2.6 * extent, -3.8 * extent, 3.2 * extent))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 52

    lights: list[object] = []
    for name, offset, energy, size in (
        ("PIMM_PROOF_KEY", (2.0, -2.5, 4.0), 900.0, 4.0),
        ("PIMM_PROOF_FILL", (-3.0, -1.0, 2.0), 500.0, 3.0),
    ):
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(light)
        light.location = target + Vector(offset) * extent
        light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
        lights.append(light)
    catcher_mesh = bpy.data.meshes.new("PIMM_ENV_SHADOW_CATCHER")
    catcher_mesh["pimm_proof_environment_role"] = "shadow-catcher"
    size = extent * 5.0
    z = minimum.z - extent * 0.15
    catcher_mesh.from_pydata(
        [(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)],
        [],
        [(0, 1, 2, 3)],
    )
    catcher_material = bpy.data.materials.new("PIMM_ENV_SHADOW_CATCHER_MATERIAL")
    catcher_material["pimm_proof_environment_role"] = "shadow-catcher"
    catcher_material.diffuse_color = (0.5, 0.5, 0.5, 1.0)
    catcher_mesh.materials.append(catcher_material)
    catcher = bpy.data.objects.new("PIMM_ENV_SHADOW_CATCHER", catcher_mesh)
    catcher["pimm_proof_environment_role"] = "shadow-catcher"
    catcher.is_shadow_catcher = True
    bpy.context.scene.collection.objects.link(catcher)
    environment_errors = _proof_environment_errors(bpy)
    if environment_errors:
        raise ValueError("; ".join(environment_errors))
    return lights, [catcher]


def _prepare_render_environment(
    bpy: Any, camera: object, *, fixture_mode: bool
) -> tuple[list[object], list[object]]:
    """Add synthetic framing and environment only in explicit fixture mode."""

    if fixture_mode:
        return _frame_fixture_scene(bpy, camera)
    fixture_roles = [
        obj.name
        for obj in bpy.data.objects
        if getattr(obj, "library", None) is None
        and getattr(obj, "type", None) == "MESH"
        and obj.get("pimm_proof_environment_role") is not None
    ]
    if fixture_roles:
        raise ValueError(
            "canonical proof contains fixture-only environment roles: "
            + ", ".join(sorted(fixture_roles))
        )
    return [], []


_UNSUPPORTED = object()


def _stable_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 12)
    if isinstance(value, Mapping):
        serialized = {
            str(key): _stable_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
        return (
            serialized
            if all(item is not _UNSUPPORTED for item in serialized.values())
            else _UNSUPPORTED
        )
    if isinstance(value, (list, tuple)):
        serialized = [_stable_value(item) for item in value]
        return serialized if all(item is not _UNSUPPORTED for item in serialized) else _UNSUPPORTED
    if isinstance(value, (set, frozenset)):
        serialized = [_stable_value(item) for item in value]
        if any(item is _UNSUPPORTED for item in serialized):
            return _UNSUPPORTED
        return sorted(serialized, key=lambda item: json.dumps(item, sort_keys=True))
    if hasattr(value, "__len__") and hasattr(value, "__iter__"):
        try:
            serialized = [_stable_value(item) for item in value]
        except (TypeError, ValueError):
            return _UNSUPPORTED
        return serialized if all(item is not _UNSUPPORTED for item in serialized) else _UNSUPPORTED
    return _UNSUPPORTED


def _data_identity(value: object | None) -> dict[str, object] | None:
    if value is None:
        return None
    if getattr(value, "override_library", None) is not None:
        raise ValueError("Blender library overrides are outside pinned component authority")
    library = getattr(value, "library", None)
    library_path: str | None = None
    if library is not None:
        library_path = str(getattr(library, "filepath", ""))
        try:
            import bpy  # type: ignore[import-not-found]

            resolved_library = blender_scene_validator._library_path(bpy, library)
        except ImportError:
            resolved_library = None
        if resolved_library is not None:
            library_path = str(resolved_library)
    result: dict[str, object] = {
        # ``name_full`` decorates linked IDs with their library filename in
        # Blender 5.2.  The stable datablock authority is its exact ID name;
        # library provenance is captured independently below.
        "name": str(getattr(value, "name", getattr(value, "name_full", ""))),
        "type": type(value).__name__,
        "library": library_path,
    }
    stable_properties: dict[str, str] = {}
    if hasattr(value, "get"):
        for property_name in ("pimm_stable_id", "pimm_material_id"):
            try:
                property_value = value.get(property_name)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                property_value = None
            if property_value is not None:
                stable_properties[property_name] = str(property_value)
    result.update(stable_properties)
    return result


def _rna_scalar_properties(
    owner: object,
    *,
    exclude: frozenset[str] = frozenset(),
) -> dict[str, object]:
    result: dict[str, object] = {}
    rna = getattr(owner, "bl_rna", None)
    properties = getattr(rna, "properties", ())
    for prop in properties:
        identifier = str(prop.identifier)
        if identifier in {"rna_type", "use_nodes"} or identifier in exclude:
            continue
        if getattr(prop, "type", None) not in {
            "BOOLEAN",
            "INT",
            "FLOAT",
            "STRING",
            "ENUM",
        }:
            continue
        try:
            serialized = _stable_value(getattr(owner, identifier))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
        if serialized is not _UNSUPPORTED:
            result[identifier] = serialized
    return dict(sorted(result.items()))


def _node_tree_for_owner(owner: object) -> object | None:
    """Return Blender 5.2's always-present node tree without deprecated toggles."""

    return getattr(owner, "node_tree", None)


def _socket_record(
    socket: object,
    image_cache: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    socket_type = str(getattr(socket, "bl_idname", type(socket).__name__))
    if socket_type in proof_module._NODE_SOCKET_POINTER_TYPES:
        try:
            pointer = socket.default_value
        except (AttributeError, RuntimeError, TypeError, ValueError) as error:
            raise ValueError(
                f"Blender pointer socket default is unreadable: {socket_type}"
            ) from error
        if pointer is None:
            default: object = {"kind": "value", "value": None}
        else:
            identity = _data_identity(pointer)
            expected_type = proof_module._NODE_SOCKET_POINTER_TYPES[socket_type]
            if identity is None or identity["type"] != expected_type:
                raise ValueError(
                    f"Blender pointer socket default type is incompatible: {socket_type}"
                )
            if socket_type == "NodeSocketImage":
                _image_identity(pointer, image_cache)
            default = {"kind": "identity", "value": identity}
    else:
        stable = _UNSUPPORTED
        if hasattr(socket, "default_value"):
            try:
                raw_default = socket.default_value
                if socket_type in {
                    "NodeSocketVectorEuler",
                    "NodeSocketVectorTranslation",
                    "NodeSocketVectorXYZ",
                }:
                    stable = [round(float(component), 12) for component in raw_default]
                else:
                    stable = _stable_value(raw_default)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass
        default = None if stable is _UNSUPPORTED else stable
    return {
        "name": str(socket.name),
        "identifier": str(getattr(socket, "identifier", "")),
        "type": socket_type,
        "enabled": bool(getattr(socket, "enabled", True)),
        "is_linked": bool(getattr(socket, "is_linked", False)),
        "default": default,
    }


def _external_image_file_record(path: Path) -> dict[str, object]:
    canonical = _lexical_absolute(path)
    anchor = Path(canonical.anchor)
    if not anchor:
        raise ValueError(f"external render image path is not absolute: {path}")
    _validate_no_reparse_ancestors(anchor, canonical)
    if not canonical.is_file():
        raise ValueError(f"external render image is missing or unreadable: {canonical}")
    before = _scratch_stat_identity(canonical)
    resolved = canonical.resolve(strict=True)
    digest = sha256_file(canonical)
    after = _scratch_stat_identity(canonical)
    if before != after:
        raise ValueError(f"external render image changed while fingerprinting: {canonical}")
    return {
        "path": str(canonical),
        "resolved_path": str(resolved),
        "bytes": before[3],
        "mtime_ns": before[4],
        "ctime_ns": before[5],
        # CPython 3.11 and 3.14 expose the same Windows volume identity at
        # different widths; normalize to the stable low 32 bits for the
        # pinned Blender -> Pillow validation boundary.
        "device": before[0] & 0xFFFFFFFF,
        "inode": before[1],
        "links": before[6],
        "sha256": digest,
    }


def _packed_image_hashes(image: object) -> list[dict[str, object]]:
    packed_files = list(getattr(image, "packed_files", ()))
    if not packed_files and getattr(image, "packed_file", None) is not None:
        packed_files = [image.packed_file]
    records: list[dict[str, object]] = []
    for index, packed in enumerate(packed_files):
        packed_file = getattr(packed, "packed_file", packed)
        try:
            data = bytes(packed_file.data)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(f"packed render image bytes are unreadable: {image.name}") from error
        records.append(
            {
                "index": index,
                "filepath": str(getattr(packed, "filepath", "")),
                "view": int(getattr(packed, "view", 0)),
                "tile_number": int(getattr(packed, "tile_number", 0)),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest().upper(),
            }
        )
    return records


def _image_pixel_hash(image: object) -> dict[str, object]:
    pixels = image.pixels
    values = array("f", [0.0]) * len(pixels)
    if values:
        pixels.foreach_get(values)
    if sys.byteorder != "little":
        values.byteswap()
    return {
        "encoding": "float32-little-endian",
        "values": len(values),
        "sha256": hashlib.sha256(values.tobytes()).hexdigest().upper(),
    }


def _image_identity(
    image: object | None,
    cache: dict[str, dict[str, object]] | None = None,
) -> dict[str, object] | None:
    identity = _data_identity(image)
    if identity is None:
        return None
    cache_key = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    source = str(getattr(image, "source", ""))
    if source not in proof_module._IMAGE_SOURCES:
        raise ValueError(f"unsupported Blender render image source: {source}")
    packed = _packed_image_hashes(image)
    external_files: list[dict[str, object]] = []
    if source in proof_module._FILE_BACKED_IMAGE_SOURCES and not packed:
        try:
            raw_paths = [Path(image.filepath_from_user())]
        except (AttributeError, RuntimeError, TypeError, ValueError):
            raw_paths = [Path(str(getattr(image, "filepath_raw", "")))]
        for raw_path in raw_paths:
            if raw_path.is_file():
                external_files.append(_external_image_file_record(raw_path))
            else:
                raise ValueError(
                    f"external render image is missing or unreadable: {raw_path}"
                )
    if source in proof_module._FILE_BACKED_IMAGE_SOURCES:
        filepath = external_files[0]["path"] if external_files else ""
    else:
        if packed:
            raise ValueError(
                f"non-file Blender render image cannot carry packed bytes: {image.name}"
            )
        filepath = ""
    identity.update(
        {
            "filepath": filepath,
            "source": source,
            "size": [int(value) for value in image.size],
            "channels": int(getattr(image, "channels", 0)),
            "depth": int(getattr(image, "depth", 0)),
            "is_float": bool(getattr(image, "is_float", False)),
            "file_format": str(getattr(image, "file_format", "")),
            "alpha_mode": str(getattr(image, "alpha_mode", "")),
            "colorspace": str(getattr(getattr(image, "colorspace_settings", None), "name", "")),
            "external_files": external_files,
            "packed_files": packed,
            "pixels": _image_pixel_hash(image),
        }
    )
    proof_module._validate_image(identity, f"captured image {identity['name']}")
    if cache is not None:
        cache[cache_key] = identity
    return identity


def _node_tree_record(
    tree: object | None,
    *,
    ancestry: frozenset[str] = frozenset(),
    image_cache: dict[str, dict[str, object]] | None = None,
    current_scene_identity: Mapping[str, object] | None = None,
    owner_identity: Mapping[str, object] | None = None,
) -> dict[str, object] | None:
    if tree is None:
        return None
    identity = _data_identity(tree)
    if owner_identity is not None:
        identity = dict(identity)
        identity["name"] = (
            f"{owner_identity['type']}:{owner_identity['name']}::{identity['name']}"
        )
        identity["library"] = owner_identity.get("library") or identity["library"]
    tree_type = str(identity["type"])
    if tree_type not in proof_module._NODE_TREE_TYPES:
        raise ValueError(f"unsupported Blender node-tree type: {tree_type}")
    tree_key = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    if tree_key in ancestry:
        reference = {"identity": identity, "recursive_reference": True}
        proof_module._validate_node_tree(
            reference,
            f"captured recursive {tree_type}",
            expected_type=tree_type,
            allow_none=False,
            current_scene_identity=current_scene_identity,
        )
        return reference
    nested_ancestry = ancestry | {tree_key}
    node_records: list[dict[str, object]] = []
    for node in sorted(tree.nodes, key=lambda item: (item.name, item.bl_idname)):
        if node.bl_idname in proof_module._UNSAFE_NODE_TYPES_BY_TREE.get(
            tree_type, frozenset()
        ):
            raise ValueError(
                f"captured {tree_type} contains unsafe external writer node type "
                f"{node.bl_idname}"
            )
        if node.bl_idname not in proof_module._NODE_TYPES_BY_TREE[tree_type]:
            raise ValueError(
                f"unsupported {tree_type} node type: {node.bl_idname}"
            )
        pointers = _pointer_property_records(node)
        if hasattr(node, "image"):
            pointers["image"] = _image_identity(
                getattr(node, "image", None), image_cache
            )
        if hasattr(node, "node_tree"):
            pointers["node_tree"] = _node_tree_record(
                getattr(node, "node_tree", None),
                ancestry=nested_ancestry,
                image_cache=image_cache,
                current_scene_identity=current_scene_identity,
            )
        node_records.append(
            {
                "name": node.name,
                "type": node.bl_idname,
                "mute": bool(getattr(node, "mute", False)),
                "properties": _rna_scalar_properties(
                    node,
                    exclude=frozenset(
                        {
                            "name",
                            "label",
                            "select",
                            "show_options",
                            "show_preview",
                            "show_texture",
                            "width",
                            "width_hidden",
                            "height",
                        }
                    ),
                ),
                "inputs": [
                    _socket_record(socket, image_cache) for socket in node.inputs
                ],
                "outputs": [
                    _socket_record(socket, image_cache) for socket in node.outputs
                ],
                "data": dict(sorted(pointers.items())),
            }
        )
    links = sorted(
        [
            {
                "from_node": link.from_node.name,
                "from_socket": link.from_socket.name,
                "from_socket_identifier": str(
                    getattr(link.from_socket, "identifier", "")
                ),
                "to_node": link.to_node.name,
                "to_socket": link.to_socket.name,
                "to_socket_identifier": str(
                    getattr(link.to_socket, "identifier", "")
                ),
            }
            for link in tree.links
        ],
        key=lambda item: (
            item["from_node"],
            item["from_socket"],
            item["from_socket_identifier"],
            item["to_node"],
            item["to_socket"],
            item["to_socket_identifier"],
        ),
    )
    record = {
        "identity": identity,
        "nodes": node_records,
        "links": links,
    }
    proof_module._validate_node_tree(
        record,
        f"captured {tree_type}",
        expected_type=tree_type,
        allow_none=False,
        current_scene_identity=current_scene_identity,
    )
    return record


def _transform_record(obj: object) -> dict[str, object]:
    return {
        "location": [round(float(value), 12) for value in obj.location],
        "rotation_mode": str(obj.rotation_mode),
        "rotation_euler": [round(float(value), 12) for value in obj.rotation_euler],
        "scale": [round(float(value), 12) for value in obj.scale],
        "matrix_world": [
            round(float(value), 12) for row in obj.matrix_world for value in row
        ],
        "parent": _data_identity(obj.parent),
    }


def _hash_json_value(digest: object, value: object) -> None:
    digest.update(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    digest.update(b"\n")


def _mesh_geometry_record(mesh: object) -> dict[str, object]:
    digest = hashlib.sha256()
    _hash_json_value(
        digest,
        {
            "vertices": len(mesh.vertices),
            "edges": len(mesh.edges),
            "loops": len(mesh.loops),
            "polygons": len(mesh.polygons),
        },
    )
    for vertex in mesh.vertices:
        _hash_json_value(digest, [vertex.index, [float(value) for value in vertex.co]])
    for edge in mesh.edges:
        _hash_json_value(digest, [edge.index, [int(value) for value in edge.vertices]])
    for loop in mesh.loops:
        _hash_json_value(digest, [loop.index, int(loop.vertex_index), int(loop.edge_index)])
    for polygon in mesh.polygons:
        _hash_json_value(
            digest,
            [
                polygon.index,
                [int(value) for value in polygon.vertices],
                int(polygon.material_index),
                bool(polygon.use_smooth),
            ],
        )
    for layer in sorted(mesh.uv_layers, key=lambda item: item.name):
        _hash_json_value(digest, {"uv_layer": layer.name, "active_render": layer.active_render})
        for item in layer.uv:
            _hash_json_value(digest, [float(value) for value in item.vector])
    for attribute in sorted(mesh.attributes, key=lambda item: item.name):
        _hash_json_value(
            digest,
            {
                "attribute": attribute.name,
                "domain": attribute.domain,
                "data_type": attribute.data_type,
                "length": len(attribute.data),
            },
        )
        for item in attribute.data:
            values: dict[str, object] = {}
            for field in ("value", "vector", "color", "byte_color"):
                if hasattr(item, field):
                    serialized = _stable_value(getattr(item, field))
                    if serialized is not _UNSUPPORTED:
                        values[field] = serialized
            _hash_json_value(digest, values)
    shape_keys = getattr(mesh, "shape_keys", None)
    if shape_keys is not None:
        for block in shape_keys.key_blocks:
            _hash_json_value(
                digest,
                {
                    "name": block.name,
                    "mute": block.mute,
                    "value": block.value,
                    "slider_min": block.slider_min,
                    "slider_max": block.slider_max,
                },
            )
            for point in block.data:
                _hash_json_value(digest, [float(value) for value in point.co])
    return {
        "sha256": digest.hexdigest().upper(),
        "vertices": len(mesh.vertices),
        "edges": len(mesh.edges),
        "loops": len(mesh.loops),
        "polygons": len(mesh.polygons),
    }


_EMBEDDED_RNA_TYPES = frozenset({"ColorMapping", "ColorRamp", "TexMapping"})


def _embedded_rna_payload(
    value: object, *, ancestry: frozenset[int] = frozenset()
) -> dict[str, object]:
    pointer = id(value)
    if pointer in ancestry:
        raise ValueError("recursive embedded render dependency")
    next_ancestry = ancestry | {pointer}
    rna = getattr(value, "bl_rna", None)
    rna_type = str(getattr(rna, "identifier", type(value).__name__))
    if rna_type not in _EMBEDDED_RNA_TYPES and not rna_type.endswith("Element"):
        raise ValueError(f"unsupported embedded render dependency: {rna_type}")
    properties: dict[str, object] = {}
    for prop in getattr(rna, "properties", ()):
        name = str(prop.identifier)
        if name == "rna_type":
            continue
        try:
            item = getattr(value, name)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
        prop_type = str(getattr(prop, "type", ""))
        if prop_type in {"BOOLEAN", "ENUM", "FLOAT", "INT", "STRING"}:
            stable = (
                [round(float(component), 12) for component in item]
                if bool(getattr(prop, "is_array", False))
                else _stable_value(item)
            )
            if stable is _UNSUPPORTED:
                raise ValueError(f"unsupported embedded render value: {rna_type}.{name}")
            properties[name] = stable
        elif prop_type == "POINTER":
            if item is not None:
                properties[name] = _embedded_rna_payload(
                    item, ancestry=next_ancestry
                )
        elif prop_type == "COLLECTION":
            properties[name] = [
                _embedded_rna_payload(element, ancestry=next_ancestry)
                for element in item
            ]
    return {"type": rna_type, "properties": properties}


def _embedded_rna_fingerprint(value: object) -> str:
    payload = _embedded_rna_payload(value)
    canonical = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest().upper()


def _pointer_property_records(owner: object) -> dict[str, object]:
    result: dict[str, object] = {}
    for prop in getattr(getattr(owner, "bl_rna", None), "properties", ()):
        if getattr(prop, "type", None) != "POINTER" or prop.identifier == "rna_type":
            continue
        try:
            value = getattr(owner, prop.identifier)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
        identity = _data_identity(value)
        if identity is not None and identity["type"] in _EMBEDDED_RNA_TYPES:
            identity["content_sha256"] = _embedded_rna_fingerprint(value)
        result[str(prop.identifier)] = identity
    return dict(sorted(result.items()))


def _dependency_value_record(
    value: object,
    image_cache: dict[str, dict[str, object]],
    *,
    ancestry: frozenset[str] = frozenset(),
) -> dict[str, object]:
    rna_identifier = str(getattr(getattr(value, "bl_rna", None), "identifier", ""))
    if rna_identifier == "Image":
        return {"kind": "image", "value": _image_identity(value, image_cache)}
    if "NodeTree" in rna_identifier or hasattr(value, "nodes") and hasattr(value, "links"):
        return {
            "kind": "node_tree",
            "value": _node_tree_record(
                value, ancestry=ancestry, image_cache=image_cache
            ),
        }
    if rna_identifier and hasattr(value, "name"):
        return {"kind": "identity", "value": _data_identity(value)}
    stable = _stable_value(value)
    if stable is _UNSUPPORTED:
        raise ValueError(
            f"unsupported render-affecting modifier dependency: {type(value).__name__}"
        )
    return {"kind": "value", "value": stable}


def _modifier_id_property_records(
    modifier: object,
    image_cache: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    try:
        keys = sorted(str(key) for key in modifier.keys() if str(key) != "_RNA_UI")
    except (AttributeError, RuntimeError, TypeError, ValueError):
        keys = []
    records: list[dict[str, object]] = []
    for key in keys:
        try:
            value = modifier[key]
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            raise ValueError(f"modifier ID-property is unreadable: {modifier.name}.{key}") from error
        records.append(
            {"name": key, "dependency": _dependency_value_record(value, image_cache)}
        )
    return records


def _modifier_interface_input_records(
    modifier: object,
    image_cache: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    node_group = getattr(modifier, "node_group", None)
    interface = getattr(node_group, "interface", None)
    items = getattr(interface, "items_tree", ())
    inputs = getattr(getattr(modifier, "properties", None), "inputs", None)
    records: list[dict[str, object]] = []
    for index, item in enumerate(items):
        if str(getattr(item, "item_type", "")) != "SOCKET" or str(
            getattr(item, "in_out", "")
        ) != "INPUT":
            continue
        identifier = str(getattr(item, "identifier", ""))
        if not identifier:
            raise ValueError(f"Geometry Nodes modifier input lacks an identifier: {modifier.name}")
        binding = getattr(inputs, identifier, None) if inputs is not None else None
        if binding is None:
            raise ValueError(
                f"Geometry Nodes modifier input is unavailable: {modifier.name}.{identifier}"
            )
        references: dict[str, object] = {}
        for prop in getattr(getattr(binding, "bl_rna", None), "properties", ()):
            if getattr(prop, "type", None) != "POINTER" or prop.identifier == "rna_type":
                continue
            try:
                pointer = getattr(binding, prop.identifier)
            except (AttributeError, RuntimeError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Geometry Nodes modifier pointer is unreadable: {modifier.name}.{identifier}.{prop.identifier}"
                ) from error
            references[str(prop.identifier)] = _dependency_value_record(
                pointer, image_cache
            )
        records.append(
            {
                "index": index,
                "identifier": identifier,
                "name": str(getattr(item, "name", "")),
                "socket_type": str(getattr(item, "socket_type", "")),
                "properties": _rna_scalar_properties(binding),
                "references": dict(sorted(references.items())),
            }
        )
    return records


def _modifier_record(
    modifier: object,
    image_cache: dict[str, dict[str, object]],
) -> dict[str, object]:
    if modifier.type not in proof_module._MODIFIER_TYPES:
        raise ValueError(f"unsupported Blender modifier type: {modifier.type}")
    record = {
        "name": modifier.name,
        "type": modifier.type,
        "properties": _rna_scalar_properties(
            modifier, exclude=frozenset({"name", "type"})
        ),
        "references": _pointer_property_records(modifier),
        "id_properties": _modifier_id_property_records(modifier, image_cache),
        "interface_inputs": _modifier_interface_input_records(modifier, image_cache),
        "node_group": _node_tree_record(
            getattr(modifier, "node_group", None), image_cache=image_cache
        ),
    }
    proof_module._validate_modifier(record, f"captured modifier {modifier.name}")
    return record


def _material_record(
    material: object,
    image_cache: dict[str, dict[str, object]],
) -> dict[str, object]:
    identity = _data_identity(material)
    record = {
        "identity": identity,
        "properties": _rna_scalar_properties(material),
        "node_tree": _node_tree_record(
            _node_tree_for_owner(material),
            image_cache=image_cache,
            owner_identity=identity,
        ),
    }
    proof_module._validate_material(record, f"captured material {material.name}")
    return record


def _object_record(
    obj: object,
    image_cache: dict[str, dict[str, object]],
    collection_paths: Mapping[str, tuple[tuple[str, ...], ...]],
) -> dict[str, object]:
    data = getattr(obj, "data", None)
    data_record: dict[str, object] | None = None
    if data is not None:
        data_record = {
            "identity": _data_identity(data),
            "properties": _rna_scalar_properties(data),
        }
        if getattr(obj, "type", None) == "MESH":
            data_record["geometry"] = _mesh_geometry_record(data)
    material_slots = [
        {
            "index": index,
            "name": slot.name,
            "link": slot.link,
            "material": _data_identity(slot.material),
        }
        for index, slot in enumerate(obj.material_slots)
    ]
    for collection in obj.users_collection:
        identity = _data_identity(collection)
        key = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        if key not in collection_paths:
            raise ValueError(
                f"object collection membership has no canonical scene path: {obj.name}"
            )
    record = {
        "identity": _data_identity(obj),
        "object_type": str(obj.type),
        "data": data_record,
        "transform": _transform_record(obj),
        "hide_render": bool(obj.hide_render),
        "hide_viewport": bool(obj.hide_viewport),
        "properties": _rna_scalar_properties(obj),
        "collections": sorted(
            (
                {"identity": identity, "path": list(path)}
                for collection in obj.users_collection
                for identity in (_data_identity(collection),)
                for path in collection_paths.get(
                    json.dumps(identity, sort_keys=True, separators=(",", ":")), ()
                )
            ),
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        ),
        "material_slots": material_slots,
        "modifiers": [
            _modifier_record(modifier, image_cache) for modifier in obj.modifiers
        ],
    }
    proof_module._validate_object(record, f"captured object {obj.name}")
    return record


def _collection_tree_record(
    collection: object,
    *,
    path: tuple[str, ...],
    ancestry: frozenset[str] = frozenset(),
) -> dict[str, object]:
    identity = _data_identity(collection)
    key = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    if key in ancestry:
        return {
            "identity": identity,
            "path": list(path),
            "recursive_reference": True,
        }
    children = sorted(
        collection.children,
        key=lambda child: json.dumps(
            _data_identity(child), sort_keys=True, separators=(",", ":")
        ),
    )
    child_identities = {
        id(child): _data_identity(child) for child in children
    }
    return {
        "identity": identity,
        "path": list(path),
        "hide_render": bool(getattr(collection, "hide_render", False)),
        "hide_viewport": bool(getattr(collection, "hide_viewport", False)),
        "properties": _rna_scalar_properties(collection),
        "objects": sorted(
            (_data_identity(obj) for obj in collection.objects),
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        ),
        "children": [
            _collection_tree_record(
                child,
                path=path + (str(child_identities[id(child)]["name"]),),
                ancestry=ancestry | {key},
            )
            for child in children
        ],
    }


def _layer_collection_record(
    layer_collection: object,
    *,
    path: tuple[str, ...],
) -> dict[str, object]:
    collection = layer_collection.collection
    collection_identity = _data_identity(collection)
    children = sorted(
        layer_collection.children,
        key=lambda child: json.dumps(
            _data_identity(child.collection), sort_keys=True, separators=(",", ":")
        ),
    )
    return {
        "path": list(path),
        "collection": collection_identity,
        "exclude": bool(layer_collection.exclude),
        "holdout": bool(layer_collection.holdout),
        "indirect_only": bool(layer_collection.indirect_only),
        "hide_viewport": bool(layer_collection.hide_viewport),
        "children": [
            _layer_collection_record(
                child,
                path=path
                + (str(_data_identity(child.collection)["name"]),),
            )
            for child in children
        ],
    }


def _collection_paths_by_identity(
    root: Mapping[str, object],
) -> dict[str, tuple[tuple[str, ...], ...]]:
    paths: dict[str, list[tuple[str, ...]]] = {}

    def visit(record: Mapping[str, object]) -> None:
        identity = record["identity"]
        key = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        path = tuple(str(segment) for segment in record["path"])
        paths.setdefault(key, []).append(path)
        for child in record.get("children", []):
            visit(child)

    visit(root)
    return {
        key: tuple(sorted(set(identity_paths)))
        for key, identity_paths in paths.items()
    }


def _dependency_sha256(settings: Mapping[str, object]) -> str:
    payload = {
        field: settings[field]
        for field in (
            "scene_identity",
            "library_authorities",
            "objects",
            "materials",
            "images",
            "collection_tree",
            "view_layers",
        )
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _capture_authored_settings(bpy: Any) -> dict[str, object]:
    """Deterministically capture all available material render-affecting state."""

    bpy.context.view_layer.update()
    scene = bpy.context.scene
    scene_identity = _data_identity(scene)
    image_cache: dict[str, dict[str, object]] = {}
    camera = scene.camera
    camera_record: dict[str, object] | None = None
    if camera is not None:
        data = camera.data
        dof = data.dof
        camera_record = {
            "identity": _data_identity(camera),
            "transform": _transform_record(camera),
            "type": str(data.type),
            "lens": float(data.lens),
            "sensor_fit": str(data.sensor_fit),
            "sensor_width": float(data.sensor_width),
            "sensor_height": float(data.sensor_height),
            "shift_x": float(data.shift_x),
            "shift_y": float(data.shift_y),
            "clip_start": float(data.clip_start),
            "clip_end": float(data.clip_end),
            "dof": {
                "use_dof": bool(dof.use_dof),
                "focus_object": _data_identity(dof.focus_object),
                "focus_distance": float(dof.focus_distance),
                "aperture_fstop": float(dof.aperture_fstop),
                "aperture_blades": int(dof.aperture_blades),
                "aperture_rotation": float(dof.aperture_rotation),
                "aperture_ratio": float(dof.aperture_ratio),
            },
        }
    lights: list[dict[str, object]] = []
    for obj in bpy.data.objects:
        if getattr(obj, "type", None) != "LIGHT":
            continue
        data = obj.data
        lights.append(
            {
                "identity": _data_identity(obj),
                "transform": _transform_record(obj),
                "type": str(data.type),
                "color": [round(float(value), 12) for value in data.color],
                "energy": float(data.energy),
                "shape": str(getattr(data, "shape", "")),
                "size": float(getattr(data, "size", 0.0)),
                "size_y": float(getattr(data, "size_y", 0.0)),
                "spot_size": float(getattr(data, "spot_size", 0.0)),
                "spot_blend": float(getattr(data, "spot_blend", 0.0)),
                "shadow_soft_size": float(getattr(data, "shadow_soft_size", 0.0)),
                "properties": _rna_scalar_properties(data),
                "node_tree": _node_tree_record(
                    _node_tree_for_owner(data),
                    image_cache=image_cache,
                ),
            }
        )
    lights.sort(key=lambda item: json.dumps(item["identity"], sort_keys=True))
    world = scene.world
    world_record = None
    if world is not None:
        world_record = {
            "identity": _data_identity(world),
            "color": [round(float(value), 12) for value in world.color],
            "properties": _rna_scalar_properties(world),
            "node_tree": _node_tree_record(
                _node_tree_for_owner(world),
                image_cache=image_cache,
            ),
        }
    compositor_tree = getattr(scene, "compositing_node_group", None)
    if compositor_tree is None:
        compositor_tree = getattr(scene, "node_tree", None)
    compositor = {
        "enabled": compositor_tree is not None,
        "node_tree": _node_tree_record(
            compositor_tree,
            image_cache=image_cache,
            current_scene_identity=scene_identity,
        ),
    }
    render = scene.render
    view_layers = [
        {
            "name": layer.name,
            "properties": _rna_scalar_properties(layer, exclude=frozenset({"name"})),
            "material_override": _data_identity(layer.material_override),
            "layer_collection": _layer_collection_record(
                layer.layer_collection,
                path=(
                    str(_data_identity(layer.layer_collection.collection)["name"]),
                ),
            ),
        }
        for layer in sorted(scene.view_layers, key=lambda item: item.name)
    ]
    collection_tree = _collection_tree_record(
        scene.collection, path=(str(scene.collection.name),)
    )
    collection_paths = _collection_paths_by_identity(collection_tree)
    objects = [
        _object_record(obj, image_cache, collection_paths)
        for obj in sorted(
            scene.objects,
            key=lambda item: (
                item.name,
                item.type,
                str(getattr(getattr(item, "library", None), "filepath", "")),
            ),
        )
    ]
    used_materials = {
        json.dumps(
            _data_identity(material), sort_keys=True, separators=(",", ":")
        ): material
        for material in bpy.data.materials
        if int(getattr(material, "users", 0)) > 0
    }
    materials = [
        _material_record(used_materials[key], image_cache)
        for key in sorted(used_materials)
    ]
    settings: dict[str, object] = {
        "scene_identity": scene_identity,
        "library_authorities": sorted(
            (
                blender_scene_validator._library_authority_record(bpy, library)
                for library in bpy.data.libraries
            ),
            key=lambda item: json.dumps(
                [
                    item["canonical_path"],
                    item["lexical_path"],
                    item["raw_filepath"],
                ],
                sort_keys=True,
                separators=(",", ":"),
            ),
        ),
        "camera": camera_record,
        "lights": lights,
        "world": world_record,
        "compositor": compositor,
        "render": {
            "properties": _rna_scalar_properties(render),
            "image_settings": _rna_scalar_properties(render.image_settings),
            "ffmpeg": _rna_scalar_properties(render.ffmpeg),
        },
        "view_layers": view_layers,
        "color_management": {
            "view": _rna_scalar_properties(scene.view_settings),
            "display": _rna_scalar_properties(scene.display_settings),
            "sequencer": _rna_scalar_properties(scene.sequencer_colorspace_settings),
        },
        "cycles": _rna_scalar_properties(scene.cycles),
        "objects": objects,
        "materials": materials,
        "images": [image_cache[key] for key in sorted(image_cache)],
        "collection_tree": collection_tree,
    }
    settings["dependency_sha256"] = _dependency_sha256(settings)
    proof_module.validate_authored_settings(settings, "captured authored settings")
    return settings


def _expected_product_rgba_path(output_root: Path, shot_id: str) -> Path:
    return output_root / f".{shot_id}--product-only.tmp.png"


def _expected_shadow_catcher_path(output_root: Path, shot_id: str) -> Path:
    return output_root / f".{shot_id}--shadow-catcher.tmp.png"


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _require_lexical_canonical(path: Path, label: str) -> Path:
    raw = Path(path)
    canonical = _lexical_absolute(raw)
    if not raw.is_absolute() or raw != canonical:
        raise ValueError(f"{label} must be one absolute lexical canonical path without aliases")
    return canonical


def _is_reparse_path(path: Path) -> bool:
    try:
        details = os.lstat(path)
    except OSError:
        return False
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    is_junction = getattr(path, "is_junction", lambda: False)
    return bool(attributes & reparse_flag) or path.is_symlink() or bool(is_junction())


def _validate_no_reparse_ancestors(asset_root: Path, target: Path) -> None:
    root = _lexical_absolute(asset_root)
    candidate = _lexical_absolute(target)
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("proof path is not lexically inside the canonical asset root") from error
    current = root
    paths = [current]
    for part in relative.parts:
        current /= part
        paths.append(current)
    for existing in paths:
        if os.path.lexists(existing) and _is_reparse_path(existing):
            raise ValueError(f"proof path ancestor is a junction or reparse point: {existing}")


def _scratch_stat_identity(path: Path) -> tuple[int, ...]:
    details = os.lstat(path)
    return (
        int(details.st_dev),
        int(details.st_ino),
        int(details.st_mode),
        int(details.st_size),
        int(details.st_mtime_ns),
        int(details.st_ctime_ns),
        int(details.st_nlink),
        int(getattr(details, "st_file_attributes", 0)),
        int(getattr(details, "st_reparse_tag", 0)),
    )


def _validate_product_rgba_path(
    asset_root: Path,
    output_root: Path,
    shot_id: str,
    product_rgba_path: Path,
) -> _ScratchIdentity:
    """Allow cleanup of only the exact hidden file created for this generation."""

    output_root = _require_lexical_canonical(output_root, "proof output root")
    supplied = _require_lexical_canonical(
        product_rgba_path, "product-only temporary path"
    )
    expected = _expected_product_rgba_path(output_root, shot_id)
    contracted = {
        output_root / "manifest.json",
        output_root / "contact-sheet.png",
        output_root / "contact-sheet.json",
        output_root / "render-metadata.json",
        output_root / "proof-contract.json",
        output_root / "scene-contract.json",
    }
    if (
        supplied != expected
        or supplied.name != f".{shot_id}--product-only.tmp.png"
        or expected in contracted
    ):
        raise ValueError("product-only temporary path is not the exact contained generation file")
    _validate_no_reparse_ancestors(asset_root, supplied)
    try:
        resolved_root = output_root.resolve(strict=True)
        resolved = supplied.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise ValueError("product-only temporary path is not a readable contained file") from error
    if (
        resolved != expected.resolve()
        or not resolved.is_file()
        or os.lstat(supplied).st_nlink != 1
    ):
        raise ValueError("product-only temporary path is not the exact readable generation file")
    return _ScratchIdentity(
        path=supplied,
        resolved_path=resolved,
        stat_identity=_scratch_stat_identity(supplied),
    )


def _unlink_validated_product_scratch(
    initial: _ScratchIdentity,
    asset_root: Path,
    output_root: Path,
    shot_id: str,
) -> None:
    current = _validate_product_rgba_path(
        asset_root, output_root, shot_id, initial.path
    )
    if (
        current.path != initial.path
        or current.resolved_path != initial.resolved_path
        or current.stat_identity != initial.stat_identity
    ):
        raise ValueError("product-only temporary path was replaced in a cleanup race")
    # No operation may intervene between final identity validation and deletion.
    current.path.unlink()


def _validate_shadow_catcher_path(
    asset_root: Path,
    output_root: Path,
    shot_id: str,
    shadow_catcher_path: Path,
) -> _ScratchIdentity:
    """Validate only the exact governed lossless shadow-catcher scratch image."""

    output_root = _require_lexical_canonical(output_root, "proof output root")
    supplied = _require_lexical_canonical(
        shadow_catcher_path, "physical shadow evidence temporary path"
    )
    expected = _expected_shadow_catcher_path(output_root, shot_id)
    if supplied != expected or supplied.name != f".{shot_id}--shadow-catcher.tmp.png":
        raise ValueError(
            "physical shadow evidence temporary path is not the exact contained generation file"
        )
    _validate_no_reparse_ancestors(asset_root, supplied)
    try:
        resolved_root = output_root.resolve(strict=True)
        resolved = supplied.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise ValueError("physical shadow evidence is not a readable contained file") from error
    if (
        resolved != expected.resolve()
        or not resolved.is_file()
        or os.lstat(supplied).st_nlink != 1
    ):
        raise ValueError("physical shadow evidence is not the exact readable generation file")
    return _ScratchIdentity(supplied, resolved, _scratch_stat_identity(supplied))


def _unlink_validated_shadow_scratch(
    initial: _ScratchIdentity,
    asset_root: Path,
    output_root: Path,
    shot_id: str,
) -> None:
    current = _validate_shadow_catcher_path(
        asset_root, output_root, shot_id, initial.path
    )
    if current != initial:
        raise ValueError("physical shadow evidence was replaced in a cleanup race")
    current.path.unlink()


def _install_shadow_catcher_output(
    bpy: Any, scene: object, view_layer: object, destination: Path
) -> tuple[object, object | None, list[object], Path]:
    """Install a temporary lossless compositor output for the Cycles catcher pass."""

    prior_tree = getattr(scene, "compositing_node_group", None)
    tree = prior_tree
    created_tree = None
    created_nodes: list[object] = []
    try:
        if tree is None:
            created_tree = bpy.data.node_groups.new(
                f"PIMM_SHADOW_CAPTURE_{destination.stem}", "CompositorNodeTree"
            )
            tree = created_tree
            scene.compositing_node_group = tree
        render_layers = tree.nodes.new("CompositorNodeRLayers")
        created_nodes.append(render_layers)
        render_layers.name = f"PIMM_SHADOW_CAPTURE_RENDER_{destination.stem}"
        render_layers.layer = view_layer.name
        file_output = tree.nodes.new("CompositorNodeOutputFile")
        created_nodes.append(file_output)
        file_output.name = f"PIMM_SHADOW_CAPTURE_FILE_{destination.stem}"
        file_output.directory = str(destination.parent)
        file_output.file_name = destination.name.removesuffix(".tmp.png") + ".raw"
        file_output.file_output_items.new("RGBA", "Shadow")
        shadow_socket = render_layers.outputs.get("Shadow Catcher")
        if shadow_socket is None:
            raise ValueError("Cycles Render Layers node exposes no Shadow Catcher pass")
        tree.links.new(shadow_socket, file_output.inputs["Shadow"])
        raw_path = destination.parent / f"{file_output.file_name}.exr"
        return prior_tree, created_tree, [file_output, render_layers], raw_path
    except Exception:
        for node in reversed(created_nodes):
            tree.nodes.remove(node)
        scene.compositing_node_group = prior_tree
        if created_tree is not None:
            bpy.data.node_groups.remove(created_tree)
        raise


def _remove_shadow_catcher_output(
    bpy: Any,
    scene: object,
    prior_tree: object | None,
    created_tree: object | None,
    nodes: Sequence[object],
) -> None:
    tree = getattr(scene, "compositing_node_group", None)
    if tree is not None:
        for node in nodes:
            if node.name in tree.nodes:
                tree.nodes.remove(node)
    scene.compositing_node_group = prior_tree
    if created_tree is not None:
        bpy.data.node_groups.remove(created_tree)


def _publish_shadow_catcher_output(destination: Path, raw_path: Path) -> None:
    """Convert the isolated float catcher pass into a lossless shadow-opacity mask."""

    if not raw_path.is_file() or raw_path.is_symlink():
        raise ValueError("Cycles did not create physical shadow pass evidence")
    import numpy
    import OpenImageIO as oiio

    image_input = oiio.ImageInput.open(str(raw_path))
    if image_input is None:
        raise ValueError("Cycles physical shadow pass evidence is corrupt")
    try:
        spec = image_input.spec()
        if tuple(spec.channelnames) != (
            "Shadow.R",
            "Shadow.G",
            "Shadow.B",
            "Shadow.A",
        ):
            raise ValueError("Cycles physical shadow pass channels are invalid")
        pixels = image_input.read_image(format=oiio.FLOAT)
    finally:
        image_input.close()
    if pixels is None or pixels.shape != (spec.height, spec.width, 4):
        raise ValueError("Cycles physical shadow pass pixels are invalid")
    # The catcher pass is a multiplicative plate: neutral is RGB 1, shadows are lower.
    shadow = numpy.clip(1.0 - pixels[:, :, :3].mean(axis=2), 0.0, 1.0)
    encoded = numpy.rint(shadow * 255.0).astype(numpy.uint8)[:, :, numpy.newaxis]
    output = oiio.ImageOutput.create(str(destination))
    if output is None:
        raise ValueError("lossless physical shadow mask writer is unavailable")
    try:
        if not output.open(
            str(destination), oiio.ImageSpec(spec.width, spec.height, 1, oiio.UINT8)
        ):
            raise ValueError("lossless physical shadow mask could not be opened")
        if not output.write_image(encoded):
            raise ValueError("lossless physical shadow mask could not be written")
    finally:
        output.close()
    raw_path.unlink()


def _render_rgba(
    bpy: Any,
    contract: ProofContract,
    destination: Path,
    *,
    fixture_mode: bool,
) -> tuple[dict[str, object], list[object], list[object], Path | None, Path | None]:
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None:
        raise ValueError("proof scene has no active camera")
    lights, environment = _prepare_render_environment(
        bpy, camera, fixture_mode=fixture_mode
    )
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = contract.samples
    scene.cycles.use_denoising = contract.denoise
    scene_contract = SceneContract.from_json(destination.parent / "scene-contract.json")
    width, height = effective_dimensions(scene_contract, contract.resolution_percentage)
    scene.render.resolution_percentage = 100
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = str(destination)
    scene.render.use_file_extension = True
    scene.view_settings.view_transform = "AgX"
    available_looks = {
        item.identifier
        for item in scene.view_settings.bl_rna.properties["look"].enum_items
    }
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "None"):
        if look in available_looks:
            scene.view_settings.look = look
            break
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    shadow_policy = (scene_contract.static_render_setup or {}).get("physical_shadow", {})
    shadow_required = (
        not fixture_mode
        and isinstance(shadow_policy, Mapping)
        and shadow_policy.get("gate") == "required"
    )
    view_layer = bpy.context.view_layer
    shadow_pass_before = bool(view_layer.cycles.use_pass_shadow_catcher)
    shadow_catcher_path = None
    shadow_output_state = None
    if shadow_required:
        expected_name = shadow_policy.get("catcher_name")
        catchers = [
            obj
            for obj in bpy.data.objects
            if obj.name == expected_name
            and obj.type == "MESH"
            and obj.library is None
            and getattr(obj, "is_shadow_catcher", False) is True
        ]
        if len(catchers) != 1:
            raise ValueError("canonical proof requires the exact governed shadow catcher")
    try:
        if shadow_required:
            view_layer.cycles.use_pass_shadow_catcher = True
            shadow_catcher_path = _expected_shadow_catcher_path(
                destination.parent, scene_contract.scene_id
            )
            shadow_output_state = _install_shadow_catcher_output(
                bpy, scene, view_layer, shadow_catcher_path
            )
        started = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        elapsed = time.perf_counter() - started
        if shadow_required:
            _publish_shadow_catcher_output(
                shadow_catcher_path, shadow_output_state[3]
            )
    finally:
        if shadow_output_state is not None:
            _remove_shadow_catcher_output(
                bpy, scene, *shadow_output_state[:3]
            )
        view_layer.cycles.use_pass_shadow_catcher = shadow_pass_before
    actual = destination if destination.is_file() else destination.with_suffix(".png")
    if actual != destination and actual.is_file():
        os.replace(actual, destination)
    if not destination.is_file():
        raise ValueError(f"Cycles did not create the contracted RGBA proof: {destination}")
    actual_dimensions = [width, height]
    product_rgba = None
    if fixture_mode:
        product_rgba = _expected_product_rgba_path(destination.parent, destination.stem.removesuffix("--rgba"))
        for obj in environment:
            obj.hide_render = True
        scene.render.filepath = str(product_rgba)
        bpy.ops.render.render(write_still=True)
        if not product_rgba.is_file():
            raise ValueError("Cycles did not create the product-only mask source")
    elif contract.object_masks:
        raise ValueError("canonical object masks require authored passes; fixture-only product render is forbidden")
    metadata = {
        "schema": "pimm-proof-render-metadata/v1",
        "engine": scene.render.engine,
        "device": scene.cycles.device,
        "samples": contract.samples,
        "resolution_percentage": contract.resolution_percentage,
        "base_dimensions": [
            scene_contract.output_contract["width"],
            scene_contract.output_contract["height"],
        ],
        "actual_dimensions": actual_dimensions,
        "image_settings": {
            "film_transparent": scene.render.film_transparent,
            "file_format": scene.render.image_settings.file_format,
            "color_mode": scene.render.image_settings.color_mode,
            "color_depth": scene.render.image_settings.color_depth,
            "use_file_extension": scene.render.use_file_extension,
        },
        "denoise": scene.cycles.use_denoising,
        "cycles": {
            "device": scene.cycles.device,
            "samples": scene.cycles.samples,
            "use_denoising": scene.cycles.use_denoising,
            "max_bounces": scene.cycles.max_bounces,
            "transparent_max_bounces": scene.cycles.transparent_max_bounces,
        },
        "agx": {
            "view_transform": scene.view_settings.view_transform,
            "look": scene.view_settings.look,
            "exposure": scene.view_settings.exposure,
            "gamma": scene.view_settings.gamma,
        },
        "render_seconds": round(elapsed, 6),
        "named_shaft_regions": _project_named_shafts(bpy, camera),
        "shadow_pass_available": fixture_mode or shadow_catcher_path is not None,
        "shadow_evidence_sha256": (
            sha256_file(shadow_catcher_path) if shadow_catcher_path is not None else None
        ),
        "fixture_mode": fixture_mode,
    }
    return metadata, lights, environment, product_rgba, shadow_catcher_path


def _save_png_once(image: object, path: Path, *, mode: str | None = None) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        target = image.convert(mode) if mode else image
        target.save(temporary, format="PNG")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def finalize_proof(
    proof_contract_path: Path,
    output_root: Path,
    rgba_path: Path,
    asset_root: Path,
    product_rgba_path: Path | None = None,
    shadow_catcher_path: Path | None = None,
) -> dict[str, object]:
    """Create lossless composites/masks, quantitative manifest, and contact sheet."""

    from PIL import Image, ImageDraw

    asset_root = _require_lexical_canonical(asset_root, "asset root")
    output_root = _require_lexical_canonical(output_root, "proof output root")
    rgba_path = _require_lexical_canonical(rgba_path, "RGBA path")
    proof_module.ASSET_ROOT = asset_root.resolve()
    contract = ProofContract.from_json(proof_contract_path)
    expected_root = _lexical_absolute(
        asset_root / Path(*PurePosixPath(contract.output_root).parts)
    )
    if output_root != expected_root:
        raise ValueError("finalizer output root does not match proof contract")
    _validate_no_reparse_ancestors(asset_root, output_root)
    scene_contract = SceneContract.from_json(output_root / "scene-contract.json")
    shot_id = scene_contract.scene_id
    expected_rgba = output_root / f"{shot_id}--rgba.png"
    if rgba_path != expected_rgba:
        raise ValueError("RGBA path is not the exact contracted generation output")
    _validate_no_reparse_ancestors(asset_root, rgba_path)
    metadata_path = output_root / "render-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    fixture_mode = metadata.get("fixture_mode") is True
    shadow_policy = (scene_contract.static_render_setup or {}).get("physical_shadow", {})
    shadow_gate = shadow_policy.get("gate") if isinstance(shadow_policy, Mapping) else None
    shadow_required = shadow_gate == "required"
    validated_product = None
    validated_shadow = None
    if product_rgba_path is not None:
        if not fixture_mode:
            raise ValueError("product-only temporary path is fixture-only")
        validated_product = _validate_product_rgba_path(
            asset_root, output_root, shot_id, product_rgba_path
        )
    elif fixture_mode:
        raise ValueError("fixture proof QA requires the exact product-only temporary path")
    if shadow_catcher_path is not None:
        if fixture_mode:
            raise ValueError("canonical physical shadow evidence is forbidden in fixture mode")
        if not shadow_required:
            raise ValueError("physical shadow evidence is not applicable to this contracted shot")
        validated_shadow = _validate_shadow_catcher_path(
            asset_root, output_root, shot_id, shadow_catcher_path
        )
        expected_hash = metadata.get("shadow_evidence_sha256")
        if not isinstance(expected_hash, str) or sha256_file(validated_shadow.path) != expected_hash:
            raise ValueError("physical shadow evidence hash does not match render metadata")
    elif shadow_required:
        raise ValueError("required physical shadow evidence is missing")
    with Image.open(rgba_path) as loaded:
        source = loaded.convert("RGBA")
        source.load()
    if source.getchannel("A").getextrema()[1] == 0:
        raise ValueError("proof RGBA contains no visible subject pixels")

    outputs = [rgba_path]
    for background in contract.backgrounds:
        if background == "white":
            backdrop = Image.new("RGBA", source.size, (255, 255, 255, 255))
        elif background == "dark":
            backdrop = Image.new("RGBA", source.size, (24, 26, 30, 255))
        else:
            backdrop = Image.new("RGBA", source.size, (224, 224, 224, 255))
            draw = ImageDraw.Draw(backdrop)
            tile = max(8, min(source.size) // 12)
            for top in range(0, source.height, tile):
                for left in range(0, source.width, tile):
                    if (left // tile + top // tile) % 2:
                        draw.rectangle(
                            (left, top, min(left + tile - 1, source.width - 1), min(top + tile - 1, source.height - 1)),
                            fill=(174, 177, 182, 255),
                        )
        composite = Image.alpha_composite(backdrop, source)
        destination = output_root / f"{shot_id}--{background}.png"
        _save_png_once(composite, destination)
        outputs.append(destination)
    if validated_shadow is not None:
        try:
            with Image.open(validated_shadow.path) as loaded_shadow:
                if loaded_shadow.size != source.size:
                    raise ValueError("physical shadow evidence dimensions do not match proof RGBA")
                shadow_alpha = loaded_shadow.convert("L")
                shadow_alpha.load()
        except (OSError, ValueError) as error:
            raise ValueError(f"physical shadow evidence image is corrupt: {error}") from error
        shadow_alpha = shadow_alpha.point(lambda value: value if value >= 16 else 0)
        if shadow_alpha.getextrema()[1] == 0:
            raise ValueError("physical shadow evidence is empty")
        from PIL import ImageChops

        product_alpha = ImageChops.subtract(source.getchannel("A"), shadow_alpha)
    elif validated_product is not None:
        with Image.open(validated_product.path) as loaded_product:
            product_alpha = loaded_product.convert("RGBA").getchannel("A")
            product_alpha.load()
        from PIL import ImageChops

        shadow_alpha = ImageChops.subtract(source.getchannel("A"), product_alpha).point(
            lambda value: value if value >= 16 else 0
        )
    else:
        product_alpha = source.getchannel("A")
        shadow_alpha = Image.new("L", source.size, 0)
    if scene_contract.purpose == "overview":
        meaningful_combined = source.getchannel("A").point(
            lambda value: 255 if value >= 16 else 0
        )
        meaningful_product = product_alpha.point(lambda value: 255 if value >= 16 else 0)
        for label, mask in (
            ("combined alpha", meaningful_combined),
            ("product alpha", meaningful_product),
        ):
            bounds = mask.getbbox()
            if bounds is not None and (
                bounds[0] == 0
                or bounds[1] == 0
                or bounds[2] == source.width
                or bounds[3] == source.height
            ):
                raise ValueError(
                    f"overview meaningful {label} touches a disallowed frame edge"
                )
    metadata["intended_subject_metrics"] = analyze_mask_metrics(product_alpha)
    metadata["physical_shadow_metrics"] = analyze_mask_metrics(shadow_alpha)
    atomic_write_json(metadata_path, metadata)
    if contract.object_masks:
        masks = {
            "object-mask": product_alpha,
            "material-mask": product_alpha,
            "shadow-mask": shadow_alpha,
        }
        for name, mask in masks.items():
            destination = output_root / f"{shot_id}--{name}.png"
            _save_png_once(mask, destination, mode="L")
            outputs.append(destination)
    if validated_product is not None:
        _unlink_validated_product_scratch(
            validated_product, asset_root, output_root, shot_id
        )
    if validated_shadow is not None:
        _unlink_validated_shadow_scratch(
            validated_shadow, asset_root, output_root, shot_id
        )

    manifest_path = write_proof_manifest(
        contract, outputs, destination=output_root / ".manifest.pending.json"
    )
    contact_path = build_contact_sheet(
        manifest_path,
        output_root / ".contact-sheet.pending.png",
        evidence_path=output_root / ".contact-sheet.pending.json",
        published_manifest_name="manifest.json",
        published_output_name="contact-sheet.png",
    )
    return {
        "manifest_pending_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "contact_sheet_pending_path": str(contact_path),
        "contact_sheet_sha256": sha256_file(contact_path),
        "outputs": [str(path) for path in outputs],
    }


def _pending_artifact_paths(output_root: Path) -> dict[Path, Path]:
    return {
        output_root / pending: output_root / published
        for pending, published in _PENDING_TO_PUBLISHED.items()
    }


def _cleanup_pending_artifacts(output_root: Path) -> None:
    for pending in _pending_artifact_paths(output_root):
        if pending.exists() and pending.is_file() and not pending.is_symlink():
            pending.unlink()


def _publish_pending_artifacts(output_root: Path) -> None:
    paths = _pending_artifact_paths(output_root)
    for pending, published in paths.items():
        if (
            not pending.is_file()
            or pending.is_symlink()
            or pending.parent.resolve() != output_root.resolve()
            or published.exists()
        ):
            raise ValueError("pending proof artifact set is incomplete or unsafe")
    published_now: list[Path] = []
    try:
        # The manifest is the pass marker and is deliberately published last.
        order = (
            output_root / ".contact-sheet.pending.png",
            output_root / ".contact-sheet.pending.json",
            output_root / ".manifest.pending.json",
        )
        for pending in order:
            published = paths[pending]
            os.replace(pending, published)
            published_now.append(published)
    except Exception:
        for path in published_now:
            if path.is_file() and not path.is_symlink():
                path.unlink()
        _cleanup_pending_artifacts(output_root)
        raise


def _run_pillow_finalizer(
    pillow_python: Path,
    proof_snapshot: Path,
    asset_root: Path,
    output_root: Path,
    rgba_path: Path,
    product_rgba_path: Path | None,
    shadow_catcher_path: Path | None,
) -> dict[str, object]:
    command = [
        str(pillow_python),
        "-m",
        "scripts.blender.pimm_production.blender_proof_render",
        "--finalize",
        "--proof-contract",
        str(proof_snapshot),
        "--asset-root",
        str(asset_root),
        "--output-root",
        str(output_root),
        "--rgba",
        str(rgba_path),
    ]
    if product_rgba_path is not None:
        command.extend(["--product-rgba", str(product_rgba_path)])
    if shadow_catcher_path is not None:
        command.extend(["--shadow-catcher", str(shadow_catcher_path)])
    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[3],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip())
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise ValueError("Pillow finalizer did not return one JSON result") from error
    if not isinstance(payload, Mapping):
        raise ValueError("Pillow finalizer result must be an object")
    return dict(payload)


def _run_one(
    bpy: Any,
    proof_path: Path,
    asset_root: Path,
    tool_lock: Path,
    *,
    fixture_mode: bool,
) -> dict[str, object]:
    output_root: Path | None = None
    try:
        lock, pillow_python = _validate_tools(tool_lock)
        blender_identity = _validate_executing_blender(bpy, lock)
        contract_bytes = proof_path.read_bytes()
        contract = ProofContract.from_mapping(json.loads(contract_bytes.decode("utf-8")))
        scene_contract_path = (
            asset_root / Path(*PurePosixPath(contract.scene_contract_path).parts)
        ).resolve()
        scene = SceneContract.from_json(scene_contract_path)
        proof_module.ASSET_ROOT = asset_root
        blender_scene_validator.ASSET_ROOT = asset_root
        contract_errors = validate_proof_contract(contract, scene)
        scene_errors = blender_scene_validator.validate_open_render_scene(
            bpy,
            scene,
            contract_snapshot_sha256=sha256_file(scene_contract_path),
        )
        if contract_errors or scene_errors:
            return {
                "status": "blocked_contract",
                "generation_id": contract.generation_id,
                "errors": contract_errors + scene_errors,
            }
        scene_path = Path(str(bpy.data.filepath)).resolve()
        if sha256_file(scene_path) != contract.scene_sha256.upper():
            return {
                "status": "blocked_scene_drift",
                "generation_id": contract.generation_id,
                "errors": ["open scene SHA-256 drifted from proof contract"],
            }
        paths = _protected_paths(asset_root, scene, scene_path)
        before = _snapshot(paths)
        scene_context = bpy.context.scene
        camera = scene_context.camera
        if camera is None:
            raise ValueError("proof scene has no active camera")
        authored_before = _capture_authored_settings(bpy)
        output_root = (
            asset_root / Path(*PurePosixPath(contract.output_root).parts)
        ).resolve()
        require_within(output_root, asset_root / "renders" / "proofs")
        output_root.mkdir(parents=True, exist_ok=False)
        proof_snapshot = output_root / "proof-contract.json"
        scene_snapshot = output_root / "scene-contract.json"
        tool_snapshot = output_root / "tool-lock.json"
        proof_snapshot.write_bytes(contract_bytes)
        scene_snapshot.write_bytes(scene_contract_path.read_bytes())
        tool_snapshot.write_bytes(tool_lock.read_bytes())

        camera_location = camera.location.copy()
        camera_rotation = camera.rotation_euler.copy()
        camera_lens = camera.data.lens
        saved = {
            "engine": scene_context.render.engine,
            "resolution_x": scene_context.render.resolution_x,
            "resolution_y": scene_context.render.resolution_y,
            "resolution_percentage": scene_context.render.resolution_percentage,
            "film_transparent": scene_context.render.film_transparent,
            "filepath": scene_context.render.filepath,
            "file_format": scene_context.render.image_settings.file_format,
            "color_mode": scene_context.render.image_settings.color_mode,
            "color_depth": scene_context.render.image_settings.color_depth,
            "use_file_extension": scene_context.render.use_file_extension,
            "view_transform": scene_context.view_settings.view_transform,
            "look": scene_context.view_settings.look,
            "exposure": scene_context.view_settings.exposure,
            "gamma": scene_context.view_settings.gamma,
            "cycles_device": scene_context.cycles.device,
            "cycles_samples": scene_context.cycles.samples,
            "cycles_use_denoising": scene_context.cycles.use_denoising,
        }
        lights: list[object] = []
        environment: list[object] = []
        product_rgba_path: Path | None = None
        shadow_catcher_path: Path | None = None
        try:
            rgba_path = output_root / f"{scene.scene_id}--rgba.png"
            (
                metadata,
                lights,
                environment,
                product_rgba_path,
                shadow_catcher_path,
            ) = _render_rgba(bpy, contract, rgba_path, fixture_mode=fixture_mode)
        finally:
            for obj in environment:
                mesh = obj.data
                materials = list(mesh.materials)
                bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.meshes.remove(mesh)
                for material in materials:
                    if material.users == 0:
                        bpy.data.materials.remove(material)
            for light in lights:
                data = light.data
                bpy.data.objects.remove(light, do_unlink=True)
                bpy.data.lights.remove(data)
            camera.location = camera_location
            camera.rotation_euler = camera_rotation
            camera.data.lens = camera_lens
            scene_context.render.engine = saved["engine"]
            scene_context.render.resolution_x = saved["resolution_x"]
            scene_context.render.resolution_y = saved["resolution_y"]
            scene_context.render.resolution_percentage = saved["resolution_percentage"]
            scene_context.render.film_transparent = saved["film_transparent"]
            scene_context.render.filepath = saved["filepath"]
            scene_context.render.image_settings.file_format = saved["file_format"]
            scene_context.render.image_settings.color_mode = saved["color_mode"]
            scene_context.render.image_settings.color_depth = saved["color_depth"]
            scene_context.render.use_file_extension = saved["use_file_extension"]
            scene_context.view_settings.view_transform = saved["view_transform"]
            scene_context.view_settings.look = saved["look"]
            scene_context.view_settings.exposure = saved["exposure"]
            scene_context.view_settings.gamma = saved["gamma"]
            scene_context.cycles.device = saved["cycles_device"]
            scene_context.cycles.samples = saved["cycles_samples"]
            scene_context.cycles.use_denoising = saved["cycles_use_denoising"]
        after_render = _snapshot(paths)
        try:
            authored_after = _capture_authored_settings(bpy)
        except ValueError as error:
            return {
                "status": "blocked_settings_drift",
                "generation_id": contract.generation_id,
                "errors": [f"authored dependency state became invalid during render: {error}"],
            }
        if before != after_render:
            return {
                "status": "blocked_fingerprint_drift",
                "generation_id": contract.generation_id,
                "errors": ["source/master/material/scene fingerprints changed during render"],
            }
        if authored_before != authored_after:
            return {
                "status": "blocked_settings_drift",
                "generation_id": contract.generation_id,
                "errors": ["authored camera/light/world/compositor settings changed during render"],
            }
        metadata.update(
            {
                "blender": blender_identity,
                "proof_contract_sha256": sha256_file(proof_snapshot),
                "scene_contract_sha256": sha256_file(scene_snapshot),
                "tool_lock_sha256": sha256_file(tool_snapshot),
                "fingerprints": {"before": before, "after": after_render},
                "authored_settings": {
                    "before": authored_before,
                    "after": authored_after,
                },
                "intended_subject_metrics": {},
                "physical_shadow_metrics": {},
            }
        )
        atomic_write_json(output_root / "render-metadata.json", metadata)
        try:
            _run_pillow_finalizer(
                pillow_python,
                proof_snapshot,
                asset_root,
                output_root,
                rgba_path,
                product_rgba_path,
                shadow_catcher_path,
            )
        except Exception as error:
            _cleanup_pending_artifacts(output_root)
            return {
                "status": "failed_finalize",
                "generation_id": contract.generation_id,
                "errors": [f"{type(error).__name__}: {error}"],
            }
        # This is the final gate. No pass-labelled artifact exists before it.
        after_prepare = _snapshot(paths)
        try:
            authored_after_prepare = _capture_authored_settings(bpy)
        except ValueError as error:
            _cleanup_pending_artifacts(output_root)
            return {
                "status": "blocked_settings_drift",
                "generation_id": contract.generation_id,
                "errors": [
                    f"authored dependency state became invalid during proof finalization: {error}"
                ],
            }
        if before != after_prepare:
            _cleanup_pending_artifacts(output_root)
            return {
                "status": "blocked_fingerprint_drift",
                "generation_id": contract.generation_id,
                "errors": ["source/master/material/scene fingerprints changed during proof finalization"],
            }
        if authored_before != authored_after_prepare:
            _cleanup_pending_artifacts(output_root)
            return {
                "status": "blocked_settings_drift",
                "generation_id": contract.generation_id,
                "errors": ["authored camera/light/world/compositor settings changed during proof finalization"],
            }
        _publish_pending_artifacts(output_root)
        manifest_path = output_root / "manifest.json"
        contact_path = output_root / "contact-sheet.png"
        return {
            "status": "pass",
            "generation_id": contract.generation_id,
            "output_root": str(output_root),
            "manifest_sha256": sha256_file(manifest_path),
            "contact_sheet_sha256": sha256_file(contact_path),
            "fingerprints_unchanged": True,
        }
    except Exception as error:  # Fail closed and stop the batch after one emitted result.
        if output_root is not None:
            _cleanup_pending_artifacts(output_root)
        return {
            "status": "failed",
            "generation_id": getattr(locals().get("contract"), "generation_id", None),
            "errors": [f"{type(error).__name__}: {error}"],
        }


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--proof-contract", type=Path, action="append", required=True)
    parser.add_argument("--fixture-asset-root", type=Path)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--tool-lock", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--rgba", type=Path)
    parser.add_argument("--product-rgba", type=Path)
    parser.add_argument("--shadow-catcher", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else sys.argv[1:]
    )
    if arguments.finalize:
        if len(arguments.proof_contract) != 1 or not all(
            (arguments.asset_root, arguments.output_root, arguments.rgba)
        ):
            raise ValueError("finalizer requires one contract, asset root, output root, and RGBA")
        result = finalize_proof(
            arguments.proof_contract[0],
            arguments.output_root,
            arguments.rgba,
            arguments.asset_root,
            arguments.product_rgba,
            arguments.shadow_catcher,
        )
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0

    import bpy

    if arguments.fixture_asset_root is not None:
        asset_root = _fixture_asset_root(arguments.fixture_asset_root)
    else:
        asset_root = CANONICAL_ASSET_ROOT.resolve()
    tool_lock = arguments.tool_lock or asset_root / "manifests" / "free-tools-lock.json"
    exit_code = 0
    for proof_path in arguments.proof_contract:
        result = _run_one(
            bpy,
            proof_path.resolve(),
            asset_root,
            tool_lock.resolve(),
            fixture_mode=arguments.fixture_asset_root is not None,
        )
        print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
        if result["status"] != "pass":
            exit_code = 1
            break
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
