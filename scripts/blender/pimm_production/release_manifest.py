"""Atomic, immutable PIMM final-release manifest construction."""

from __future__ import annotations

import hashlib
import io
import json
import ntpath
import os
import re
import stat
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
from typing import Mapping, Sequence

from PIL import Image

from .approval_manifest import (
    _canonical_component,
    _create_new_json,
    _decode_component_mask,
    _mapping,
    _owned_identity,
    _published_identity_matches,
    _rgba_pixel_evidence,
    _stable_file,
    _unlink_owned,
    approval_head_lock,
    build_authorized_component_contract,
    canonical_absolute_path,
    canonical_json_sha256,
    compute_final_qa,
    held_evidence_authority,
    stable_file_record,
    stable_json,
)
from .blender_final_render import (
    _authorize_final_render,
    _blender_component_mask_script,
    _component_mask_specs,
    _dependency_state_sha256,
    authorize_final_render,
)
from .proof_contract import validate_authored_settings


_RELEASE_ID = re.compile(r"^release-[0-9]{4}-[0-9]{2}-[0-9]{2}-r[0-9]{2}$")
_GENERATION_ID = re.compile(r"^proof-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{7}$")
_SHOT_ID = re.compile(r"^pimm-(?:30g|50g)(?:--[a-z0-9]+(?:-[a-z0-9]+)*)+$")
_OUTPUT_FIELDS = {
    "schema", "release_id", "generation_id", "shot_id", "approval_path",
    "approval_sha256", "authorized_final_contract_path",
    "authorized_final_contract_sha256", "final_authorization_sha256",
    "output_root", "required_deliverables", "qa", "qa_evidence",
    "component_evidence", "outputs",
}
_OUTPUT_ENTRY_FIELDS = {
    "logical_asset_id", "path", "sha256", "dimensions", "alpha", "mime_type",
}
_QA_FIELDS = {"schema", "dimensions", "product", "material", "alpha", "controller", "animation"}
_QA_EVIDENCE_FIELDS = {"role", "path", "sha256", "dimensions", "mime_type"}
_COMPONENT_EVIDENCE_FIELDS = {"schema", "contract", "masks"}
_COMPONENT_MASK_FIELDS = {"mask_id", "path", "sha256", "dimensions", "mime_type"}
_TREE_AUTHORITY_FIELDS = {"schema", "entries", "sha256"}
_TREE_FILE_IDENTITY_FIELDS = {
    "sha256", "bytes", "mtime_ns", "ctime_ns", "change_time_ns", "device", "inode", "links",
}
_MIME_BY_EXTENSION = {
    "exr": "image/x-exr", "png": "image/png", "webp": "image/webp",
}
_FORBIDDEN_OUTPUT_COMPONENTS = {"proof", "proofs", "archive", "archives", "mutable"}


def _release_publication_matches(
    destination: Path,
    expected_payload: Mapping[str, object],
    published_payload: Mapping[str, object],
    created: Mapping[str, object],
    published_record: Mapping[str, object],
) -> bool:
    """Validate marker content and durable identity while SMB timestamps settle."""

    encoded = (
        json.dumps(expected_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return (
        published_payload == expected_payload
        and published_record.get("path") == str(destination)
        and published_record.get("sha256")
        == hashlib.sha256(encoded).hexdigest().upper()
        and _published_identity_matches(created, published_record)
    )


def _validate_independent_dependency_state(
    approved_authored: Mapping[str, object], live_authored: Mapping[str, object]
) -> None:
    """Reject independent dependency drift beyond exact governed addon caches."""

    if _dependency_state_sha256(approved_authored) != _dependency_state_sha256(
        live_authored
    ):
        raise ValueError("release independent linked dependency state drift")


def _regenerate_component_evidence(
    scene_path: Path,
    blender_binary: Path,
    dimensions: list[object],
    shot_id: str,
    component_contract: Mapping[str, object],
    samples: int,
    *,
    repository_root: Path,
    approved_authored_settings: Mapping[str, object],
) -> tuple[bytes, bytes, dict[str, bytes]]:
    """Independently regenerate final media and masks from the approved Blender scene."""

    specs = _component_mask_specs(component_contract, shot_id)
    with tempfile.TemporaryDirectory(prefix="pimm-component-verify-") as root_text:
        root = Path(root_text)
        output_root = root / "masks"
        output_root.mkdir()
        combined_filename = "approved-final.png"
        combined_exr_filename = "approved-final.exr"
        audit = root / "approved-authored-state.json"
        script = root / "verify-component-masks.py"
        script.write_text(
            _blender_component_mask_script(
                output_root,
                audit,
                repository_root,
                dimensions,
                shot_id,
                component_contract,
                samples,
                combined_filename,
                combined_exr_filename,
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                str(blender_binary),
                "--factory-startup",
                "-b",
                str(scene_path),
                "-P",
                str(script),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        expected_paths = {
            output_root / str(spec["path"]): str(spec["mask_id"])
            for spec in specs
        }
        combined_path = output_root / combined_filename
        combined_exr_path = output_root / combined_exr_filename
        actual_paths = set(output_root.iterdir())
        if result.returncode or not audit.is_file() or actual_paths != set(expected_paths) | {
            combined_path,
            combined_exr_path,
        }:
            raise ValueError(
                "release could not independently regenerate approved Blender pixels/masks "
                f"(returncode={result.returncode}, files={sorted(path.name for path in actual_paths)}, "
                f"stderr={result.stderr[-2000:]})"
            )
        try:
            live_authored = validate_authored_settings(
                json.loads(audit.read_text(encoding="utf-8")),
                "independently regenerated authored state",
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(
                "release independent authored-state audit is invalid"
            ) from error
        _validate_independent_dependency_state(approved_authored_settings, live_authored)
        return (
            combined_path.read_bytes(),
            combined_exr_path.read_bytes(),
            {mask_id: path.read_bytes() for path, mask_id in expected_paths.items()},
        )


def _cstring(data: bytes, offset: int, label: str) -> tuple[str, int]:
    end = data.find(b"\x00", offset)
    if end < 0:
        raise ValueError(f"final output EXR {label} is truncated")
    try:
        value = data[offset:end].decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError(f"final output EXR {label} is not ASCII") from error
    return value, end + 1


def _validate_float_exr(
    data: bytes, dimensions: list[object]
) -> dict[str, object]:
    """Parse EXR structure and return decoded float-channel pixel evidence."""

    if len(data) < 9 or data[:4] != b"v/1\x01":
        raise ValueError("final output EXR magic header is not genuine")
    version_flags = struct.unpack_from("<I", data, 4)[0]
    # OpenEXR's long-name capability bit (0x400) is valid for scanline images;
    # tiled, deep, non-image, and multipart flags remain forbidden here.
    if version_flags & 0xFF != 2 or version_flags & ~(0xFF | 0x400):
        raise ValueError("final output EXR must be a single-part scanline version 2 image")
    offset = 8
    attributes: dict[str, tuple[str, bytes]] = {}
    while True:
        name, offset = _cstring(data, offset, "attribute name")
        if not name:
            break
        kind, offset = _cstring(data, offset, f"{name} type")
        if offset + 4 > len(data):
            raise ValueError("final output EXR attribute size is truncated")
        size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if size > len(data) - offset or name in attributes:
            raise ValueError("final output EXR attribute payload is invalid")
        attributes[name] = (kind, data[offset : offset + size])
        offset += size
    required = {"channels", "compression", "dataWindow", "displayWindow", "lineOrder"}
    if not required <= set(attributes):
        raise ValueError("final output EXR header is incomplete")
    channel_kind, channel_data = attributes["channels"]
    if channel_kind != "chlist":
        raise ValueError("final output EXR channels declaration is invalid")
    channels: dict[str, int] = {}
    channel_order: list[str] = []
    cursor = 0
    while cursor < len(channel_data):
        name, cursor = _cstring(channel_data, cursor, "channel name")
        if not name:
            break
        if cursor + 16 > len(channel_data):
            raise ValueError("final output EXR channel record is truncated")
        pixel_type = struct.unpack_from("<I", channel_data, cursor)[0]
        linear = channel_data[cursor + 4]
        reserved = channel_data[cursor + 5 : cursor + 8]
        x_sampling, y_sampling = struct.unpack_from("<II", channel_data, cursor + 8)
        cursor += 16
        if (
            name in channels
            or linear not in {0, 1}
            or reserved != b"\0\0\0"
            or x_sampling != 1
            or y_sampling != 1
        ):
            raise ValueError("final output EXR channel sampling is invalid")
        channels[name] = pixel_type
        channel_order.append(name)
    if cursor != len(channel_data):
        raise ValueError("final output EXR channel list has trailing payload")
    if channels != {"R": 2, "G": 2, "B": 2, "A": 2}:
        raise ValueError("final output EXR must contain exactly float RGBA channels")
    expected_width, expected_height = int(dimensions[0]), int(dimensions[1])
    for name in ("dataWindow", "displayWindow"):
        kind, raw = attributes[name]
        if kind != "box2i" or len(raw) != 16:
            raise ValueError(f"final output EXR {name} is invalid")
        left, top, right, bottom = struct.unpack("<iiii", raw)
        if (left, top, right, bottom) != (0, 0, expected_width - 1, expected_height - 1):
            raise ValueError(f"final output EXR {name} dimensions drift")
    compression_kind, compression_value = attributes["compression"]
    if compression_kind != "compression" or len(compression_value) != 1:
        raise ValueError("final output EXR compression declaration is invalid")
    scanlines_per_block = {0: 1, 2: 1, 3: 16}.get(
        compression_value[0]
    )
    if scanlines_per_block is None:
        raise ValueError("final output EXR requires exact uncompressed, ZIPS, or ZIP validation")
    line_order_kind, line_order_value = attributes["lineOrder"]
    if (
        line_order_kind != "lineOrder"
        or len(line_order_value) != 1
        or line_order_value[0] not in {0, 1, 2}
    ):
        raise ValueError("final output EXR line order is invalid")
    block_count = (expected_height + scanlines_per_block - 1) // scanlines_per_block
    table_end = offset + block_count * 8
    if table_end > len(data):
        raise ValueError("final output EXR scanline offset table is truncated")
    offsets = struct.unpack_from(f"<{block_count}Q", data, offset)
    if len(set(offsets)) != len(offsets):
        raise ValueError("final output EXR scanline chunk offsets must be unique")
    observed_y: set[int] = set()
    ranges: list[tuple[int, int]] = []
    table_y: list[int] = []
    physical_chunks: list[tuple[int, int]] = []
    decoded_chunks: list[tuple[int, bytes]] = []
    for chunk_offset in offsets:
        if chunk_offset < table_end or chunk_offset + 8 > len(data):
            raise ValueError("final output EXR scanline chunk offset is invalid")
        y, size = struct.unpack_from("<iI", data, chunk_offset)
        if size == 0:
            raise ValueError("final output EXR scanline chunk payload cannot be empty")
        if size > len(data) - chunk_offset - 8:
            raise ValueError("final output EXR scanline chunk is truncated")
        if y < 0 or y >= expected_height or y % scanlines_per_block != 0 or y in observed_y:
            raise ValueError("final output EXR scanline chunk coordinate or coverage is invalid")
        rows = min(scanlines_per_block, expected_height - y)
        expected_payload_bytes = rows * expected_width * 4 * 4
        payload = data[chunk_offset + 8 : chunk_offset + 8 + size]
        if compression_value[0] == 0:
            if size != expected_payload_bytes:
                raise ValueError("final output EXR uncompressed scanline payload length is invalid")
            decoded = payload
        elif size == expected_payload_bytes:
            # OpenEXR stores the original channel bytes when ZIP/ZIPS would not
            # make the block smaller. Equal-size chunks are therefore raw data,
            # even when they happen to begin with a valid zlib stream.
            decoded = payload
        else:
            if size > expected_payload_bytes:
                raise ValueError("final output EXR compressed payload length is invalid")
            try:
                inflater = zlib.decompressobj()
                transformed = inflater.decompress(payload, expected_payload_bytes + 1)
            except zlib.error as error:
                raise ValueError("final output EXR ZIP payload is invalid") from error
            if (
                len(transformed) != expected_payload_bytes
                or not inflater.eof
                or inflater.unused_data
                or inflater.unconsumed_tail
            ):
                raise ValueError("final output EXR compressed payload length is invalid")
            # OpenEXR ZIP shuffles the source bytes, applies a byte predictor,
            # then DEFLATEs. Invert the predictor on the inflated shuffled
            # stream before interleaving even/odd bytes back into channel data.
            shuffled = bytearray(transformed)
            for index in range(1, len(shuffled)):
                shuffled[index] = (
                    shuffled[index - 1] + shuffled[index] - 128
                ) & 0xFF
            split = (len(shuffled) + 1) // 2
            decoded_buffer = bytearray(len(shuffled))
            decoded_buffer[0::2] = shuffled[:split]
            decoded_buffer[1::2] = shuffled[split:]
            decoded = bytes(decoded_buffer)
        observed_y.add(y)
        table_y.append(y)
        physical_chunks.append((int(chunk_offset), y))
        decoded_chunks.append((y, decoded))
        ranges.append((int(chunk_offset), int(chunk_offset + 8 + size)))
    expected_y = list(range(0, expected_height, scanlines_per_block))
    if observed_y != set(expected_y):
        raise ValueError("final output EXR scanline coverage is incomplete")
    if table_y != expected_y:
        raise ValueError("final output EXR scanline offset table order is invalid")
    ordered_ranges = sorted(ranges)
    if any(left[1] > right[0] for left, right in zip(ordered_ranges, ordered_ranges[1:])):
        raise ValueError("final output EXR scanline chunks overlap")
    if (
        not ordered_ranges
        or ordered_ranges[0][0] != table_end
        or any(left[1] != right[0] for left, right in zip(ordered_ranges, ordered_ranges[1:]))
        or ordered_ranges[-1][1] != len(data)
    ):
        raise ValueError("final output EXR scanline chunk payload coverage is not exact")
    physical_y = [y for _, y in sorted(physical_chunks)]
    if (
        line_order_value[0] == 0 and physical_y != expected_y
        or line_order_value[0] == 1 and physical_y != list(reversed(expected_y))
    ):
        raise ValueError("final output EXR physical scanline order is invalid")
    channel_digest = hashlib.sha256()
    channel_digest.update(struct.pack("<II", expected_width, expected_height))
    channel_digest.update("\0".join(channel_order).encode("ascii") + b"\0")
    for y, decoded in sorted(decoded_chunks):
        channel_digest.update(struct.pack("<iI", y, len(decoded)))
        channel_digest.update(decoded)
    return {
        "channels": channel_order,
        "dimensions": [expected_width, expected_height],
        "decoded_channels_sha256": channel_digest.hexdigest().upper(),
    }


def _validate_media_bytes(
    data: bytes, dimensions: list[object], mime_type: str
) -> dict[str, object]:
    if mime_type == "image/x-exr":
        return _validate_float_exr(data, dimensions)
    expected_format = "PNG" if mime_type == "image/png" else "WEBP"
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.format != expected_format or list(image.size) != dimensions or image.mode != "RGBA":
                raise ValueError("final output declared dimensions, MIME type, or alpha mode drift")
            alpha_min, alpha_max = image.getchannel("A").getextrema()
            if alpha_max == 0:
                raise ValueError("final output alpha contains no visible product")
            rgba = bytearray(image.tobytes())
            # Lossless WebP is permitted to normalize RGB beneath alpha=0.
            # Canonicalize only those invisible channels while retaining every
            # visible RGBA value and the complete alpha plane.
            for offset in range(0, len(rgba), 4):
                if rgba[offset + 3] == 0:
                    rgba[offset : offset + 3] = b"\0\0\0"
            return {
                "format": expected_format,
                "dimensions": list(image.size),
                "rgba_sha256": hashlib.sha256(rgba).hexdigest().upper(),
                "alpha_extrema": [int(alpha_min), int(alpha_max)],
            }
    except OSError as error:
        raise ValueError(f"final output {expected_format} bytes are invalid: {error}") from error


def _safe_release_root(path: Path, release_id: str) -> Path:
    _canonical_component(release_id, "release ID")
    if path.name != release_id or path.parent.name != "final" or path.parent.parent.name != "renders":
        raise ValueError("proof/archive/mutable output path is forbidden")
    if any(part.casefold() in _FORBIDDEN_OUTPUT_COMPONENTS for part in path.parts):
        raise ValueError("proof/archive/mutable output path is forbidden")
    return path


def _preflight_manifest(
    raw_path: Path, release_id: str
) -> tuple[Path, Path, Mapping[str, object], dict[str, object]]:
    path = canonical_absolute_path(str(Path(raw_path)), "final output manifest path")
    if path.name != "final-output-manifest.json" or len(path.parents) < 2:
        raise ValueError("final output manifest path is not canonical")
    shot_component = _canonical_component(path.parent.name, "final output shot directory")
    if _SHOT_ID.fullmatch(shot_component) is None:
        raise ValueError("final output manifest shot directory is invalid")
    release_root = _safe_release_root(path.parents[1], release_id)
    payload, record = stable_json(path, release_root, "asset", "final output manifest")
    if payload.get("schema") != "pimm-final-output-manifest/v1":
        raise ValueError("final output manifest schema is invalid")
    if payload.get("release_id") != release_id:
        raise ValueError("final output manifest release ID drift")
    generation = payload.get("generation_id")
    if not isinstance(generation, str) or _GENERATION_ID.fullmatch(generation) is None:
        raise ValueError("final output manifest generation is invalid")
    return path, release_root, payload, record


def _validate_manifest(
    path: Path,
    release_root: Path,
    payload: Mapping[str, object],
    manifest_record: Mapping[str, object],
    release_id: str,
    *,
    head_locked: bool,
) -> tuple[str, str, tuple[str, str], str, list[dict[str, object]], set[Path], list[tuple[Path, dict[str, object]]]]:
    if set(payload) != _OUTPUT_FIELDS:
        raise ValueError("final output manifest fields are incomplete or unknown")
    shot_id = payload.get("shot_id")
    generation = str(payload.get("generation_id"))
    if not isinstance(shot_id, str) or _SHOT_ID.fullmatch(shot_id) is None:
        raise ValueError("final output manifest shot is invalid")
    if path.parent.name != shot_id:
        raise ValueError("final output manifest directory/shot relationship is not canonical")
    if payload.get("output_root") != f"renders/final/{release_id}":
        raise ValueError("proof/archive/mutable output path is forbidden")
    required = payload.get("required_deliverables")
    if not isinstance(required, list) or set(required) != {"exr", "png", "webp"} or len(required) != 3:
        raise ValueError("final output manifest has absent EXR or contracted transparent deliverable")

    approval_path = canonical_absolute_path(payload.get("approval_path"), "release approval path")
    final_path = canonical_absolute_path(
        payload.get("authorized_final_contract_path"), "authorized final contract path"
    )
    authorization = _authorize_final_render(
        approval_path, final_path, head_locked=head_locked
    )
    authorized_final, _ = stable_json(
        final_path, authorization.asset_root, "asset", "authorized final contract",
        authorization.final_contract_record,
    )
    expected_dimensions = _mapping(
        authorized_final.get("render_settings"), "authorized final render settings"
    ).get("output_dimensions")
    expected_auth = {
        "release_id": authorization.release_id,
        "generation_id": authorization.generation_id,
        "shot_id": authorization.shot_id,
        "approval_sha256": authorization.approval_sha256,
        "authorized_final_contract_sha256": authorization.final_contract_sha256,
        "final_authorization_sha256": authorization.authorization_sha256,
    }
    for field, expected in expected_auth.items():
        if payload.get(field) != expected:
            raise ValueError(f"release approval/final authorization {field} drift")
    if release_root != authorization.asset_root / "renders" / "final" / release_id:
        raise ValueError("release physical root is outside authorized asset authority")

    qa = _mapping(payload.get("qa"), "final output QA")
    if set(qa) != _QA_FIELDS or qa.get("schema") != "pimm-final-qa/v1":
        raise ValueError("final output QA evidence is incomplete")

    records: list[dict[str, object]] = []
    expected_files = {path}
    stable_records: list[tuple[Path, dict[str, object]]] = [(path, dict(manifest_record))]
    endpoint_bytes: dict[str, bytes] = {}
    qa_evidence = payload.get("qa_evidence")
    if not isinstance(qa_evidence, list) or len(qa_evidence) != 2:
        raise ValueError("final animation endpoint evidence must contain exact start and end files")
    for item in qa_evidence:
        entry = _mapping(item, "final animation endpoint evidence")
        if set(entry) != _QA_EVIDENCE_FIELDS:
            raise ValueError("final animation endpoint evidence fields are invalid")
        role = entry.get("role")
        if role not in {"animation-start", "animation-end"}:
            raise ValueError("final animation endpoint role is invalid")
        label = str(role).removeprefix("animation-")
        if label in endpoint_bytes:
            raise ValueError("final animation endpoint roles must be unique")
        relative = _canonical_component(entry.get("path"), f"animation {label} endpoint path")
        if relative != f"{shot_id}--animation-{label}.png":
            raise ValueError("final animation endpoint path/role relationship is not canonical")
        if entry.get("dimensions") != expected_dimensions or entry.get("mime_type") != "image/png":
            raise ValueError("final animation endpoint dimensions or MIME type drift")
        actual = path.parent / relative
        try:
            record, data = _stable_file(
                str(actual), str(release_root), "asset", f"animation {label} endpoint", capture=True
            )
        except OSError as error:
            raise ValueError(f"final animation {label} endpoint is missing or unreadable") from error
        if record["sha256"] != str(entry.get("sha256", "")).upper():
            raise ValueError(f"final animation {label} endpoint bytes or SHA-256 drift")
        _validate_media_bytes(data or b"", list(expected_dimensions), "image/png")
        endpoint_bytes[label] = data or b""
        expected_files.add(actual)
        stable_records.append((actual, record))
    if set(endpoint_bytes) != {"start", "end"}:
        raise ValueError("final animation endpoint evidence must contain exact start and end files")

    outputs = payload.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError("final output family must contain exactly EXR, PNG, and WebP")
    raw_logical_ids = [
        item.get("logical_asset_id") for item in outputs if isinstance(item, Mapping)
    ]
    if len(raw_logical_ids) != len(set(raw_logical_ids)):
        raise ValueError("duplicate logical asset ID")
    if len(outputs) != 3:
        raise ValueError("absent EXR or contracted transparent deliverable")
    observed_extensions: set[str] = set()
    logical_ids: set[str] = set()
    physical_paths: set[str] = set()
    media_bytes: dict[str, bytes] = {}
    media_pixel_evidence: dict[str, dict[str, object]] = {}
    for item in outputs:
        entry = _mapping(item, "final output entry")
        if set(entry) != _OUTPUT_ENTRY_FIELDS:
            raise ValueError("final output entry fields are invalid")
        relative = _canonical_component(entry.get("path"), "final output path")
        extension = Path(relative).suffix.lower().lstrip(".")
        expected_name = f"{shot_id}--transparent.{extension}"
        expected_logical = f"{shot_id}--transparent-{extension}"
        if relative != expected_name or entry.get("logical_asset_id") != expected_logical:
            raise ValueError("final output logical asset ID/directory relationship is not canonical")
        if extension not in _MIME_BY_EXTENSION or entry.get("mime_type") != _MIME_BY_EXTENSION[extension]:
            raise ValueError("final output MIME type does not match its immutable path")
        dimensions = entry.get("dimensions")
        if (
            not isinstance(dimensions, list)
            or len(dimensions) != 2
            or not all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in dimensions)
        ):
            raise ValueError("final output dimensions are invalid")
        if dimensions != expected_dimensions:
            raise ValueError("final output dimensions drift from final authorization")
        if entry.get("alpha") is not True:
            raise ValueError("final output must preserve transparent alpha")
        actual = path.parent / relative
        record, data = _stable_file(
            str(actual), str(release_root), "asset", f"final output {relative}", capture=True
        )
        if record["sha256"] != str(entry.get("sha256", "")).upper():
            raise ValueError("final output bytes or SHA-256 drift")
        media_pixel_evidence[extension] = _validate_media_bytes(
            data or b"", dimensions, str(entry["mime_type"])
        )
        media_bytes[extension] = data or b""
        logical = str(entry["logical_asset_id"])
        physical = ntpath.normcase(str(actual))
        if logical in logical_ids:
            raise ValueError("duplicate logical asset ID")
        if physical in physical_paths:
            raise ValueError("duplicate physical output path")
        if extension in observed_extensions:
            raise ValueError("final output family contains a duplicate media member")
        logical_ids.add(logical)
        physical_paths.add(physical)
        observed_extensions.add(extension)
        expected_files.add(actual)
        stable_records.append((actual, record))
        records.append({
            "logical_asset_id": logical,
            "path": str(actual),
            "sha256": record["sha256"],
            "dimensions": dimensions,
            "alpha": True,
            "mime_type": entry["mime_type"],
            "generation_id": generation,
            "approval_path": str(authorization.approval_path),
            "approval_sha256": authorization.approval_sha256,
            "authorized_final_contract_path": str(authorization.final_contract_path),
            "authorized_final_contract_sha256": authorization.final_contract_sha256,
            "final_authorization_sha256": authorization.authorization_sha256,
            "release_id": release_id,
            "shot_id": shot_id,
        })
    if observed_extensions != {"exr", "png", "webp"}:
        raise ValueError("absent EXR or contracted transparent deliverable")
    final_evidence = _mapping(authorized_final.get("evidence"), "authorized final evidence")
    scene_record = _mapping(final_evidence.get("scene_contract"), "scene contract evidence")
    machine_record = _mapping(final_evidence.get("machine_contract"), "machine contract evidence")
    scene_contract, _ = stable_json(
        Path(str(scene_record.get("path"))),
        authorization.asset_root,
        "asset",
        "release scene contract",
        scene_record,
    )
    repository_root = canonical_absolute_path(
        _mapping(authorized_final.get("authority_roots"), "authorized roots").get("repository"),
        "repository authority root",
    )
    machine_contract, _ = stable_json(
        Path(str(machine_record.get("path"))),
        repository_root,
        "repository",
        "release machine contract",
        machine_record,
    )
    metadata_record = _mapping(
        final_evidence.get("render_metadata"), "render metadata evidence"
    )
    render_metadata, _ = stable_json(
        Path(str(metadata_record.get("path"))),
        authorization.asset_root,
        "asset",
        "release approved render metadata",
        metadata_record,
    )
    authored_settings = _mapping(
        render_metadata.get("authored_settings"), "approved authored settings evidence"
    )
    approved_components = build_authorized_component_contract(
        machine_contract,
        _mapping(authored_settings.get("before"), "approved authored settings before"),
        _mapping(authorized_final.get("authority_roots"), "authorized roots"),
        final_evidence,
    )
    component_evidence = _mapping(
        payload.get("component_evidence"), "final component evidence"
    )
    if (
        set(component_evidence) != _COMPONENT_EVIDENCE_FIELDS
        or component_evidence.get("schema") != "pimm-final-component-evidence/v1"
        or component_evidence.get("contract") != approved_components
    ):
        raise ValueError("final component contract identity drift from approved scene/machine")
    expected_component_paths = {
        "material": f"{shot_id}--material-objects-mask.png"
    }
    for raw_segment in approved_components["segments"]:
        segment = _mapping(raw_segment, "approved component segment")
        expected_component_paths[str(segment["stable_object_id"])] = (
            f"{shot_id}--controller-segment-{int(segment['ordinal']):02d}-mask.png"
        )
    raw_masks = component_evidence.get("masks")
    if not isinstance(raw_masks, list) or len(raw_masks) != len(expected_component_paths):
        raise ValueError("final component masks are missing or contain extras")
    component_mask_bytes: dict[str, bytes] = {}
    component_physical_paths: set[str] = set()
    for raw_mask in raw_masks:
        entry = _mapping(raw_mask, "final component mask evidence")
        if set(entry) != _COMPONENT_MASK_FIELDS:
            raise ValueError("final component mask evidence fields are invalid")
        mask_id = entry.get("mask_id")
        if not isinstance(mask_id, str) or mask_id not in expected_component_paths:
            raise ValueError("final component mask identity is missing, extra, or unknown")
        if mask_id in component_mask_bytes:
            raise ValueError("final component mask identities must be unique")
        relative = _canonical_component(entry.get("path"), f"component mask {mask_id} path")
        if relative != expected_component_paths[mask_id]:
            raise ValueError("final component mask path/identity relationship is not canonical")
        if entry.get("dimensions") != expected_dimensions or entry.get("mime_type") != "image/png":
            raise ValueError("final component mask dimensions or MIME type drift")
        actual = path.parent / relative
        physical = ntpath.normcase(str(actual))
        if physical in component_physical_paths:
            raise ValueError("final component masks cannot share physical paths")
        try:
            record, data = _stable_file(
                str(actual), str(release_root), "asset", f"component mask {mask_id}", capture=True
            )
        except OSError as error:
            raise ValueError(f"final component mask is missing or unreadable: {mask_id}") from error
        if record["sha256"] != str(entry.get("sha256", "")).upper():
            raise ValueError(f"final component mask bytes or SHA-256 drift: {mask_id}")
        component_mask_bytes[mask_id] = data or b""
        component_physical_paths.add(physical)
        expected_files.add(actual)
        stable_records.append((actual, record))
    if set(component_mask_bytes) != set(expected_component_paths):
        raise ValueError("final component masks are missing or contain extras")
    blender_record = _mapping(
        final_evidence.get("blender_binary"), "Blender binary evidence"
    )
    # This is deliberately adjacent to native regeneration: no earlier approval
    # snapshot can authorize Blender to reopen changed linked-library bytes.
    current_components = build_authorized_component_contract(
        machine_contract,
        _mapping(authored_settings.get("before"), "approved authored settings before"),
        _mapping(authorized_final.get("authority_roots"), "authorized roots"),
        final_evidence,
    )
    if current_components != approved_components:
        raise ValueError("approved component dependency authority drift before regeneration")
    with held_evidence_authority(
        authorized_final.get("authority_roots"), final_evidence
    ):
        regenerated_png, regenerated_exr, regenerated_masks = _regenerate_component_evidence(
            authorization.scene_path,
            Path(str(blender_record.get("path"))),
            list(expected_dimensions),
            shot_id,
            approved_components,
            int(authorized_final["samples"]),
            repository_root=repository_root,
            approved_authored_settings=_mapping(
                authored_settings.get("before"), "approved authored settings before"
            ),
        )
    if build_authorized_component_contract(
        machine_contract,
        _mapping(authored_settings.get("before"), "approved authored settings before"),
        _mapping(authorized_final.get("authority_roots"), "authorized roots"),
        final_evidence,
    ) != approved_components:
        raise ValueError("approved component dependency authority drift during regeneration")
    regenerated_pixels = _rgba_pixel_evidence(
        regenerated_png,
        list(expected_dimensions),
        "independently regenerated approved Blender final",
    )
    persisted_pixels = _rgba_pixel_evidence(
        media_bytes["png"], list(expected_dimensions), "persisted final PNG"
    )
    if regenerated_pixels["rgba_sha256"] != persisted_pixels["rgba_sha256"]:
        raise ValueError(
            "final pixels do not match independently regenerated approved Blender render"
        )
    if (
        media_pixel_evidence["webp"]["rgba_sha256"]
        != media_pixel_evidence["png"]["rgba_sha256"]
    ):
        raise ValueError(
            "final WebP pixels do not match independently regenerated approved Blender render"
        )
    regenerated_exr_evidence = _validate_float_exr(
        regenerated_exr,
        list(expected_dimensions),
    )
    if (
        media_pixel_evidence["exr"]["decoded_channels_sha256"]
        != regenerated_exr_evidence["decoded_channels_sha256"]
    ):
        raise ValueError(
            "final EXR decoded channels do not match independently regenerated approved Blender render"
        )
    if set(regenerated_masks) != set(component_mask_bytes):
        raise ValueError("regenerated approved Blender object mask identities drift")
    for mask_id, persisted in component_mask_bytes.items():
        _, persisted_evidence = _decode_component_mask(
            persisted, list(expected_dimensions), f"persisted component mask {mask_id}"
        )
        _, regenerated_evidence = _decode_component_mask(
            regenerated_masks[mask_id],
            list(expected_dimensions),
            f"regenerated approved Blender object mask {mask_id}",
        )
        if (
            persisted_evidence["channel_sha256"]
            != regenerated_evidence["channel_sha256"]
        ):
            raise ValueError(
                "component mask does not match regenerated approved Blender object: "
                f"{mask_id} (persisted={persisted_evidence}, regenerated={regenerated_evidence})"
            )
    final_inputs = _mapping(authorized_final.get("inputs"), "authorized final inputs")
    recomputed_qa = compute_final_qa(
        media_bytes["png"],
        endpoint_bytes,
        list(expected_dimensions),
        machine_contract,
        scene_contract,
        component_contract=approved_components,
        component_mask_bytes=component_mask_bytes,
        material_library_sha256=str(final_inputs["material_library_sha256"]),
        scene_contract_sha256=str(scene_record["sha256"]),
        machine_contract_sha256=str(machine_record["sha256"]),
    )
    for section in ("schema", "dimensions", "product", "material", "alpha", "controller", "animation"):
        if qa.get(section) != recomputed_qa.get(section):
            raise ValueError(f"final output {section} QA drift from current pixels/contracts")
    actual_family_entries = set(path.parent.iterdir())
    if actual_family_entries != expected_files:
        raise ValueError("extra or unmanifested final family files are forbidden")
    return (
        generation,
        shot_id,
        (str(authorization.approval_path), authorization.approval_sha256),
        authorization.authorization_sha256,
        records,
        expected_files,
        stable_records,
    )


def _directory_tree_identity(status: os.stat_result) -> dict[str, int]:
    return {
        "mtime_ns": int(status.st_mtime_ns),
        "ctime_ns": int(status.st_ctime_ns),
        "device": int(status.st_dev),
        "inode": int(status.st_ino),
        "links": int(status.st_nlink),
    }


def _tree_authority_from_records(
    release_root: Path,
    expected_children: set[Path],
    stable_records: Sequence[tuple[Path, Mapping[str, object]]],
) -> dict[str, object]:
    """Bind every pre-marker directory/file entry to exact immutable evidence."""

    entries: list[dict[str, object]] = []
    for directory in expected_children:
        status = os.stat(directory, follow_symlinks=False)
        entry: dict[str, object] = {
            "kind": "directory",
            "path": directory.relative_to(release_root).as_posix(),
        }
        entry.update(_directory_tree_identity(status))
        entries.append(entry)
    for path, record in stable_records:
        entry: dict[str, object] = {
            "kind": "file",
            "path": path.relative_to(release_root).as_posix(),
        }
        for field in _TREE_FILE_IDENTITY_FIELDS:
            entry[field] = record[field]
        entries.append(entry)
    entries.sort(key=lambda entry: (str(entry["path"]), str(entry["kind"])))
    paths = [str(entry["path"]) for entry in entries]
    if len(paths) != len(set(paths)):
        raise ValueError("release tree authority contains duplicate paths")
    return {
        "schema": "pimm-release-tree-authority/v1",
        "entries": entries,
        "sha256": canonical_json_sha256(entries),
    }


def _current_tree_authority(release_root: Path, marker: Path) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    root_entries = sorted(release_root.iterdir(), key=lambda item: item.name.casefold())
    paths: list[Path] = []
    for path in root_entries:
        if path == marker:
            continue
        status = os.stat(path, follow_symlinks=False)
        if path.is_symlink() or int(getattr(status, "st_file_attributes", 0)) & 0x400:
            raise ValueError("release tree authority rejects reparse entries")
        relative = path.relative_to(release_root).as_posix()
        if stat.S_ISDIR(status.st_mode):
            entry: dict[str, object] = {"kind": "directory", "path": relative}
            entry.update(_directory_tree_identity(status))
            entries.append(entry)
            paths.extend(sorted(path.iterdir(), key=lambda item: item.name.casefold()))
            continue
        raise ValueError("release tree authority contains an unexpected root entry")
    for path in paths:
        status = os.stat(path, follow_symlinks=False)
        if (
            path.is_symlink()
            or int(getattr(status, "st_file_attributes", 0)) & 0x400
            or not stat.S_ISREG(status.st_mode)
        ):
            raise ValueError("release tree authority contains a non-file family entry")
        relative = path.relative_to(release_root).as_posix()
        record = stable_file_record(path, release_root, "asset", "release tree authority file")
        entry: dict[str, object] = {"kind": "file", "path": relative}
        for field in _TREE_FILE_IDENTITY_FIELDS:
            entry[field] = record[field]
        entries.append(entry)
    entries.sort(key=lambda entry: (str(entry["path"]), str(entry["kind"])))
    return {
        "schema": "pimm-release-tree-authority/v1",
        "entries": entries,
        "sha256": canonical_json_sha256(entries),
    }


def _validate_release_tree_authority(
    marker: Path, published_payload: Mapping[str, object] | None = None
) -> Mapping[str, object]:
    """Reject any marker whose exact immutable tree differs at observation time."""

    release_root = marker.parent
    if marker.name != "release-manifest.json" or _RELEASE_ID.fullmatch(release_root.name) is None:
        raise ValueError("release tree authority marker path is invalid")
    if published_payload is None:
        try:
            payload, _ = stable_json(marker, release_root, "asset", "release manifest")
        except OSError as error:
            raise ValueError("release tree authority marker is not readable") from error
    else:
        payload = published_payload
    authority = _mapping(payload.get("tree_authority"), "release tree authority")
    if set(authority) != _TREE_AUTHORITY_FIELDS:
        raise ValueError("release tree authority fields are invalid")
    entries = authority.get("entries")
    if not isinstance(entries, list) or authority.get("sha256") != canonical_json_sha256(entries):
        raise ValueError("release tree authority hash is invalid")
    current = _current_tree_authority(release_root, marker)
    if authority != current:
        raise ValueError("release tree authority drift at marker observation")
    return payload


def _release_commit_revalidate(
    pending: Path,
    release_root: Path,
    expected_children: set[Path],
    expected_families: Mapping[Path, set[Path]],
    stable_records: Sequence[tuple[Path, Mapping[str, object]]],
    approval_path: Path,
    final_path: Path,
    expected_approval_sha256: str,
    expected_authorization_sha256: str,
) -> None:
    """Reauthorize, rehash, and rescan at the pending-to-final commit point."""

    authorization = _authorize_final_render(
        approval_path, final_path, head_locked=True
    )
    if (
        authorization.approval_sha256 != expected_approval_sha256
        or authorization.authorization_sha256 != expected_authorization_sha256
    ):
        raise ValueError("release commit approval/final authorization drift")
    for path, record in stable_records:
        stable_file_record(path, release_root, "asset", "release commit input", record)
    for family, expected_entries in expected_families.items():
        if set(family.iterdir()) != expected_entries:
            raise ValueError("release tree rescan found extra or missing family entries")
    if set(release_root.iterdir()) != expected_children | {pending}:
        raise ValueError("release tree rescan found extra or missing root entries")


def _release_postcommit_validate(
    marker: Path,
    release_root: Path,
    expected_children: set[Path],
    expected_families: Mapping[Path, set[Path]],
    stable_records: Sequence[tuple[Path, Mapping[str, object]]],
    approval_path: Path,
    final_path: Path,
    expected_approval_sha256: str,
    expected_authorization_sha256: str,
    published_payload: Mapping[str, object],
) -> None:
    _release_commit_revalidate(
        marker,
        release_root,
        expected_children,
        expected_families,
        stable_records,
        approval_path,
        final_path,
        expected_approval_sha256,
        expected_authorization_sha256,
    )
    _validate_release_tree_authority(marker, published_payload)


def _build_release_manifest_locked(
    release_id: str,
    preflight: Sequence[tuple[Path, Path, Mapping[str, object], dict[str, object]]],
    approval_path: Path,
    final_path: Path,
) -> Path:
    generations = {str(payload.get("generation_id")) for _, _, payload, _ in preflight}
    release_roots = {root for _, root, _, _ in preflight}
    manifest_paths = [path for path, _, _, _ in preflight]
    all_records: list[dict[str, object]] = []
    shot_ids: set[str] = set()
    approvals: set[tuple[str, str]] = set()
    authorizations: set[str] = set()
    all_stable_records: list[tuple[Path, dict[str, object]]] = []
    expected_families: dict[Path, set[Path]] = {}
    for path, root, payload, manifest_record in preflight:
        generation, shot_id, approval, authorization, records, expected_files, stable_records = _validate_manifest(
            path, root, payload, manifest_record, release_id, head_locked=True
        )
        if generation not in generations:
            raise ValueError("mixed proof generations are forbidden")
        if shot_id in shot_ids:
            raise ValueError("duplicate shot manifests are forbidden")
        shot_ids.add(shot_id)
        approvals.add(approval)
        authorizations.add(authorization)
        all_records.extend(records)
        all_stable_records.extend(stable_records)
        expected_families[path.parent] = expected_files
    if len(approvals) != 1 or len(authorizations) != 1:
        raise ValueError("one current approval and final authorization is required per release")
    logical_ids = [str(record["logical_asset_id"]) for record in all_records]
    physical = [ntpath.normcase(str(record["path"])) for record in all_records]
    if len(logical_ids) != len(set(logical_ids)):
        raise ValueError("duplicate logical asset ID")
    if len(physical) != len(set(physical)):
        raise ValueError("duplicate physical output path")

    release_root = next(iter(release_roots))
    actual_children = {child for child in release_root.iterdir()}
    expected_children = {path.parent for path in manifest_paths}
    if actual_children != expected_children:
        raise ValueError("extra or unmanifested release-root entries are forbidden")
    destination = release_root / "release-manifest.json"
    payload: dict[str, object] = {
        "schema": "pimm-final-release-manifest/v1",
        "release_id": release_id,
        "generation_id": next(iter(generations)),
        "approval_path": next(iter(approvals))[0],
        "approval_sha256": next(iter(approvals))[1],
        "final_authorization_sha256": next(iter(authorizations)),
        "shot_ids": sorted(shot_ids),
        "assets": sorted(all_records, key=lambda record: str(record["logical_asset_id"])),
        "tree_authority": _tree_authority_from_records(
            release_root, expected_children, all_stable_records
        ),
    }
    # Revalidate every manifest/output identity immediately before the immutable
    # marker is the last write. O_EXCL handles an injected competing marker race.
    for path, record in all_stable_records:
        stable_file_record(path, release_root, "asset", "release input", record)
    marker_authorization = _authorize_final_render(
        approval_path, final_path, head_locked=True
    )
    marker_final, _ = stable_json(
        final_path,
        marker_authorization.asset_root,
        "asset",
        "marker authorized final contract",
        marker_authorization.final_contract_record,
    )
    marker_owned_handles: list[int] = []

    def validate_marker(
        marker: Path, owned_identity: Mapping[str, object], descriptor: int
    ) -> None:
        ownership_fields = ("device", "inode", "links", "bytes")
        handle_identity = _owned_identity(os.fstat(descriptor))
        path_identity = _owned_identity(os.stat(marker, follow_symlinks=False))
        if any(
            handle_identity[field] != owned_identity.get(field)
            or path_identity[field] != handle_identity[field]
            for field in ownership_fields
        ):
            raise ValueError("release marker pathname no longer names its creation handle")
        _release_postcommit_validate(
            marker,
            release_root,
            expected_children,
            expected_families,
            all_stable_records,
            approval_path,
            final_path,
            next(iter(approvals))[1],
            next(iter(authorizations)),
            payload,
        )
        path_identity = _owned_identity(os.stat(marker, follow_symlinks=False))
        if any(
            path_identity[field] != handle_identity[field]
            for field in ownership_fields
        ):
            raise ValueError("release marker pathname changed during postcommit validation")
    try:
        with held_evidence_authority(
            marker_final.get("authority_roots"), marker_final.get("evidence")
        ):
            created = _create_new_json(
                destination,
                payload,
                before_commit=lambda pending: _release_commit_revalidate(
                    pending,
                    release_root,
                    expected_children,
                    expected_families,
                    all_stable_records,
                    approval_path,
                    final_path,
                    next(iter(approvals))[1],
                    next(iter(authorizations)),
                ),
                after_commit=validate_marker,
                retain_owned_handle=marker_owned_handles,
            )
    except FileExistsError as error:
        raise ValueError("release manifest already exists; releases are immutable") from error
    except BaseException:
        if marker_owned_handles:
            handle = marker_owned_handles[0]
            _unlink_owned(
                handle,
                _owned_identity(os.fstat(handle)),
                "release marker failed held-authority exit",
            )
        raise
    finally:
        for handle in marker_owned_handles:
            os.close(handle)
    published, record = stable_json(destination, release_root, "asset", "release manifest")
    if not _release_publication_matches(
        destination, payload, published, created, record
    ):
        raise ValueError("release manifest publication identity or payload drift")
    _validate_release_tree_authority(destination)
    return destination


def build_release_manifest(release_id: str, approved_outputs: Sequence[Path]) -> Path:
    """Authenticate one immutable final family and publish its last pass marker."""

    if _RELEASE_ID.fullmatch(release_id) is None:
        raise ValueError("release ID must match release-YYYY-MM-DD-rNN")
    if not approved_outputs:
        raise ValueError("approved final outputs are required")
    preflight = [_preflight_manifest(Path(path), release_id) for path in approved_outputs]
    generations = {str(payload.get("generation_id")) for _, _, payload, _ in preflight}
    if len(generations) != 1:
        raise ValueError("mixed proof generations are forbidden")
    release_roots = {root for _, root, _, _ in preflight}
    if len(release_roots) != 1:
        raise ValueError("release output roots must be one immutable directory")
    manifest_paths = [path for path, _, _, _ in preflight]
    if len({ntpath.normcase(str(path)) for path in manifest_paths}) != len(manifest_paths):
        raise ValueError("duplicate shot manifests are forbidden")
    approval_paths = {
        canonical_absolute_path(payload.get("approval_path"), "release approval path")
        for _, _, payload, _ in preflight
    }
    final_paths = {
        canonical_absolute_path(
            payload.get("authorized_final_contract_path"), "authorized final contract path"
        )
        for _, _, payload, _ in preflight
    }
    if len(approval_paths) != 1 or len(final_paths) != 1:
        raise ValueError("one approval and final contract path is required per release")
    approval_path = next(iter(approval_paths))
    final_path = next(iter(final_paths))
    # Validate the lock location read-only first, then reacquire and reauthorize
    # inside the lock to close the handoff race.
    authorize_final_render(approval_path, final_path)
    with approval_head_lock(approval_path.parent):
        return _build_release_manifest_locked(
            release_id, preflight, approval_path, final_path
        )
