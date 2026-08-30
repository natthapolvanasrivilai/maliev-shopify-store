"""Render and atomically publish one approval-bound editorial native release."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import time
from typing import Any, Mapping, Sequence
import uuid

try:
    from . import blender_editorial_scene
    from .blender_editorial_preview import (
        _CAMPAIGN, _authority_worker_record, _load_completion_authority,
        _validate_blender_authority, _validate_rendered_png_dimensions,
    )
    from .editorial_final_contract import (
        ALLOWED_SCENE_MUTATIONS, FINAL_CONTRACT_NAME, RELEASE_ID,
        validate_editorial_final_contract,
    )
    from .io_contract import sha256_file
    from .paths import require_within
except ImportError:  # Blender executes this checked-in file outside package mode.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production import blender_editorial_scene
    from scripts.blender.pimm_production.blender_editorial_preview import (
        _CAMPAIGN, _authority_worker_record, _load_completion_authority,
        _validate_blender_authority, _validate_rendered_png_dimensions,
    )
    from scripts.blender.pimm_production.editorial_final_contract import (
        ALLOWED_SCENE_MUTATIONS, FINAL_CONTRACT_NAME, RELEASE_ID,
        validate_editorial_final_contract,
    )
    from scripts.blender.pimm_production.io_contract import sha256_file
    from scripts.blender.pimm_production.paths import require_within


WORKER_MARKER = "PIMM_EDITORIAL_FINAL_JSON="
REPORT_NAME = "native-report.json"
CONTACT_SHEET_NAME = "sheet-editorial-finals.png"
DISPOSITION_NAME = "actual-pixel-disposition.json"
REJECTED_DISPOSITION_NAME = "rejected-disposition.json"
RELEASE_MANIFEST_NAME = "release-manifest.json"
FINAL_LIBRARY = "editorial-concepts-v1"
WORKER_TIMEOUT_SECONDS = 3600
FFPROBE_TIMEOUT_SECONDS = 60
FFPROBE_SHA256 = "55BB6C6289367AE2383EFA86B26BF2596F8ADB72AC747360EB13DF162354161C"
_PASS_FIELDS = ("pixel_review", "grounding", "clipping", "props", "exposure", "detail", "decals")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _exclusive_json(path: Path, payload: Mapping[str, object]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(_json_bytes(payload))
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _validate_ephemeral_render_delta(
    baseline: Mapping[str, object],
    final: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    """Reject every in-memory scene mutation not explicitly authorized by contract."""

    if set(baseline) != set(final):
        raise ValueError("final render state fields drift")
    allowed = contract.get("allowed_scene_mutations")
    if allowed != ALLOWED_SCENE_MUTATIONS:
        raise ValueError("final render allowed mutation policy drift")
    for field in baseline:
        if field not in ALLOWED_SCENE_MUTATIONS and baseline[field] != final[field]:
            raise ValueError(f"unauthorized final render {field} drift")


def _state_record(bpy: Any) -> dict[str, object]:
    scene = bpy.context.scene
    camera = scene.camera
    camera_data = getattr(camera, "data", None)
    return {
        "camera": {
            "name": str(camera.name if camera else ""),
            "matrix_world": [list(row) for row in camera.matrix_world] if camera else None,
            "lens": float(camera_data.lens) if camera_data else None,
            "sensor_width": float(camera_data.sensor_width) if camera_data else None,
            "aperture_fstop": float(camera_data.dof.aperture_fstop) if camera_data else None,
        },
        "lights": blender_editorial_scene._scene_light_signature(bpy),
        "world": str(getattr(scene.world, "name", "")),
        "compositor": blender_editorial_scene._node_tree_signature_record(
            bpy, getattr(scene, "node_tree", None)
        ),
        "resolution_x": int(scene.render.resolution_x),
        "resolution_y": int(scene.render.resolution_y),
        "resolution_percentage": int(scene.render.resolution_percentage),
        "cycles.samples": int(scene.cycles.samples),
        "cycles.use_denoising": bool(scene.cycles.use_denoising),
        "render.filepath": str(scene.render.filepath),
        "image_settings.file_format": str(scene.render.image_settings.file_format),
        "image_settings.color_mode": str(scene.render.image_settings.color_mode),
        "image_settings.color_depth": str(scene.render.image_settings.color_depth),
        "color_management": {
            "view_transform": str(scene.view_settings.view_transform),
            "look": str(scene.view_settings.look),
            "exposure": float(scene.view_settings.exposure),
            "gamma": float(scene.view_settings.gamma),
        },
    }


def _shot_dimensions(contract: Mapping[str, object], approved_shot: Mapping[str, object]) -> tuple[int, int]:
    source = approved_shot.get("dimensions")
    if not isinstance(source, list) or len(source) != 2:
        raise ValueError("approved shot dimensions are invalid")
    target = contract["landscape_dimensions"] if int(source[0]) > int(source[1]) else contract["portrait_dimensions"]
    width, height = int(target[0]), int(target[1])
    if int(source[0]) * height != int(source[1]) * width:
        raise ValueError("native final aspect ratio drift")
    return width, height


def _parse_openexr(path: Path) -> dict[str, object]:
    """Parse and structurally decode one single-part scanline OpenEXR file."""

    data = Path(path).read_bytes()
    if len(data) < 16 or data[:4] != b"\x76\x2f\x31\x01":
        raise ValueError("native final EXR magic is invalid")
    version = struct.unpack_from("<I", data, 4)[0]
    # Blender 5.2 writes v2 scanline files with LONG_NAMES (0x400). Reject
    # tiled, deep/non-image, and multipart flags, but accept that valid flag.
    if (version & 0xFF) not in {1, 2} or version & 0x00001A00:
        raise ValueError("native final EXR must be a single-part scanline image")
    cursor = 8
    attributes: dict[str, tuple[str, bytes]] = {}

    def cstring(position: int) -> tuple[str, int]:
        end = data.find(b"\0", position)
        if end < 0:
            raise ValueError("native final EXR header is truncated")
        try:
            return data[position:end].decode("ascii"), end + 1
        except UnicodeDecodeError as error:
            raise ValueError("native final EXR header name is invalid") from error

    while True:
        name, cursor = cstring(cursor)
        if not name:
            break
        kind, cursor = cstring(cursor)
        if cursor + 4 > len(data):
            raise ValueError("native final EXR attribute length is truncated")
        size = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4
        if size > len(data) - cursor:
            raise ValueError("native final EXR attribute payload is truncated")
        if name in attributes:
            raise ValueError("native final EXR contains duplicate attributes")
        attributes[name] = (kind, data[cursor:cursor + size])
        cursor += size
    required = {"channels", "compression", "dataWindow"}
    if not required.issubset(attributes):
        raise ValueError("native final EXR required header attributes are missing")
    if attributes["dataWindow"][0] != "box2i" or len(attributes["dataWindow"][1]) != 16:
        raise ValueError("native final EXR data window is invalid")
    xmin, ymin, xmax, ymax = struct.unpack("<iiii", attributes["dataWindow"][1])
    width, height = xmax - xmin + 1, ymax - ymin + 1
    if width <= 0 or height <= 0:
        raise ValueError("native final EXR data window dimensions are invalid")
    compression_payload = attributes["compression"][1]
    if attributes["compression"][0] != "compression" or len(compression_payload) != 1:
        raise ValueError("native final EXR compression attribute is invalid")
    compression = compression_payload[0]
    lines_per_chunk = {0: 1, 1: 1, 2: 1, 3: 16, 4: 32, 5: 16, 6: 32, 7: 32, 8: 32, 9: 256}.get(compression)
    if lines_per_chunk is None:
        raise ValueError("native final EXR compression is unsupported")
    kind, channel_payload = attributes["channels"]
    if kind != "chlist":
        raise ValueError("native final EXR channel list type is invalid")
    channels: list[str] = []
    position = 0
    while position < len(channel_payload):
        end = channel_payload.find(b"\0", position)
        if end < 0:
            raise ValueError("native final EXR channel list is truncated")
        if end == position:
            position += 1
            break
        try:
            channel = channel_payload[position:end].decode("ascii")
        except UnicodeDecodeError as error:
            raise ValueError("native final EXR channel name is invalid") from error
        position = end + 1
        if position + 16 > len(channel_payload):
            raise ValueError("native final EXR channel record is truncated")
        pixel_type, _linear, x_sampling, y_sampling = struct.unpack_from("<iB3xii", channel_payload, position)
        position += 16
        if pixel_type not in {0, 1, 2} or x_sampling <= 0 or y_sampling <= 0:
            raise ValueError("native final EXR channel record is invalid")
        channels.append(channel)
    if position != len(channel_payload) or not channels or len(channels) != len(set(channels)):
        raise ValueError("native final EXR channel list is invalid")
    chunk_count = (height + lines_per_chunk - 1) // lines_per_chunk
    table_end = cursor + chunk_count * 8
    if table_end > len(data):
        raise ValueError("native final EXR chunk table is truncated")
    offsets = struct.unpack_from(f"<{chunk_count}Q", data, cursor)
    for offset in offsets:
        if offset < table_end or offset + 8 > len(data):
            raise ValueError("native final EXR chunk offset is invalid")
        packed_size = struct.unpack_from("<I", data, offset + 4)[0]
        if packed_size == 0 or offset + 8 + packed_size > len(data):
            raise ValueError("native final EXR chunk payload is truncated")
    return {
        "dimensions": [width, height],
        "channels": channels,
        "compression": compression,
        "chunk_count": chunk_count,
    }


def _ffprobe_decode_exr(
    path: Path, width: int, height: int, ffprobe: Path | None = None
) -> dict[str, object]:
    """Decode exactly one EXR frame through the pinned, bounded FFprobe authority."""

    resolved = Path(ffprobe or shutil.which("ffprobe") or "").resolve()
    if not resolved.is_file() or sha256_file(resolved) != FFPROBE_SHA256:
        raise ValueError("pinned FFprobe authority is missing or hash-drifted")
    command = [
        str(resolved), "-v", "error", "-select_streams", "v:0",
        "-show_entries",
        "stream=codec_name,width,height,pix_fmt:frame=media_type,width,height,pix_fmt,pkt_size",
        "-show_frames", "-read_intervals", "%+#1", "-of", "json", str(path),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("FFprobe EXR decode timed out") from error
    if completed.returncode != 0:
        raise ValueError(f"FFprobe EXR decode failed: {completed.stderr[-2000:]}")
    if len(completed.stdout) > 65536 or len(completed.stderr) > 8192:
        raise ValueError("FFprobe EXR decode output exceeded the bounded evidence limit")
    try:
        payload = json.loads(completed.stdout)
        streams, frames = payload["streams"], payload["frames"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("FFprobe EXR decode evidence is malformed") from error
    if len(streams) != 1 or len(frames) != 1:
        raise ValueError("FFprobe EXR decode did not produce exactly one image frame")
    stream, frame = streams[0], frames[0]
    if (
        stream.get("codec_name") != "exr"
        or [stream.get("width"), stream.get("height")] != [width, height]
        or [frame.get("width"), frame.get("height")] != [width, height]
        or stream.get("pix_fmt") != "gbrpf32le"
        or frame.get("pix_fmt") != "gbrpf32le"
        or frame.get("media_type") != "video"
    ):
        raise ValueError("FFprobe EXR codec, dimensions, or float RGB format drift")
    return {
        "status": "pass", "tool_sha256": FFPROBE_SHA256,
        "codec": "exr", "dimensions": [width, height],
        "pixel_format": "gbrpf32le", "decoded_frames": 1,
    }


def _validate_worker_png(
    bpy: Any, path: Path, width: int, height: int
) -> dict[str, object]:
    """Validate written dimensions while tolerating Blender's headless 0x0 image API."""

    render_result = bpy.data.images.get("Render Result")
    observed = tuple(render_result.size) if render_result is not None else None
    return _validate_rendered_png_dimensions(
        path, width, height, render_result_size=observed
    )


def _load_worker_contract(
    contract_path: Path,
    asset_root: Path,
    expected_sha256: str,
    expected_bindings: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Perform Pillow-free contract validation inside a fresh Blender process.

    The controller performs the full accepted-image validation immediately
    before and after every worker.  Blender independently binds the exact
    contract and approval bytes, policy, shot count, and current scene
    authority without importing raster tooling that is absent from Blender's
    bundled Python.
    """

    contract_path = require_within(Path(contract_path).resolve(), Path(asset_root).resolve())
    if sha256_file(contract_path) != expected_sha256:
        raise ValueError("fresh Blender final contract hash drift")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    required = {
        "schema", "revision", "release_id", "generation_id", "approval", "samples", "denoise",
        "landscape_dimensions", "portrait_dimensions", "archive_format", "delivery_format",
        "web_derivative_format", "allowed_scene_mutations", "shots", "authorized_at",
    }
    if set(contract) != required or contract.get("schema") != "maliev.pimm-editorial-final-contract/v1":
        raise ValueError("fresh Blender final contract fields or schema drift")
    if (
        contract.get("release_id") != RELEASE_ID
        or contract.get("samples") != 256
        or contract.get("denoise") is not True
        or contract.get("landscape_dimensions") != [3840, 2160]
        or contract.get("portrait_dimensions") != [2400, 3000]
        or contract.get("archive_format") != "OPEN_EXR"
        or contract.get("delivery_format") != "PNG"
        or contract.get("web_derivative_format") != "WEBP"
        or contract.get("allowed_scene_mutations") != ALLOWED_SCENE_MUTATIONS
    ):
        raise ValueError("fresh Blender final render policy drift")
    shots = contract.get("shots")
    if not isinstance(shots, list) or [item.get("shot_id") for item in shots if isinstance(item, Mapping)] != [shot.shot_id for shot in _CAMPAIGN.shots]:
        raise ValueError("fresh Blender final exact four-shot contract drift")
    approval = contract.get("approval")
    if not isinstance(approval, Mapping) or set(approval) != {"path", "sha256"}:
        raise ValueError("fresh Blender approval binding is invalid")
    approval_path = require_within(Path(str(approval["path"])).resolve(), Path(asset_root).resolve())
    if sha256_file(approval_path) != approval.get("sha256"):
        raise ValueError("fresh Blender approval hash drift")
    approval_payload = json.loads(approval_path.read_text(encoding="utf-8"))
    bindings = {
        "generation_id": approval_payload.get("generation_id"),
        "approval_sha256": sha256_file(approval_path),
        "manifest_sha256": approval_payload.get("manifest", {}).get("sha256"),
        "report_sha256": approval_payload.get("report", {}).get("sha256"),
        "visual_disposition_sha256": approval_payload.get("visual_disposition", {}).get("sha256"),
        "contact_sheet_sha256": approval_payload.get("contact_sheet", {}).get("sha256"),
    }
    if expected_bindings is not None and bindings != dict(expected_bindings):
        raise ValueError("fresh Blender held approval/accepted-generation binding drift")
    return contract


def _controller_authority_snapshot(contract_path: Path, asset_root: Path) -> dict[str, object]:
    contract_path = Path(contract_path).resolve()
    contract_bytes = contract_path.read_bytes()
    captured_contract = json.loads(contract_bytes)
    approval_path = Path(str(captured_contract["approval"]["path"])).resolve()
    approval_bytes = approval_path.read_bytes()
    captured_approval = json.loads(approval_bytes)
    validated_contract = validate_editorial_final_contract(contract_path, asset_root)
    if (
        contract_path.read_bytes() != contract_bytes
        or approval_path.read_bytes() != approval_bytes
        or validated_contract != captured_contract
    ):
        raise ValueError("controller contract/approval capture tuple drift during validation")
    return {
        "_captured_contract": captured_contract,
        "contract_sha256": hashlib.sha256(contract_bytes).hexdigest().upper(),
        "generation_id": captured_approval["generation_id"],
        "approval_sha256": hashlib.sha256(approval_bytes).hexdigest().upper(),
        "manifest_sha256": captured_approval["manifest"]["sha256"],
        "report_sha256": captured_approval["report"]["sha256"],
        "visual_disposition_sha256": captured_approval["visual_disposition"]["sha256"],
        "contact_sheet_sha256": captured_approval["contact_sheet"]["sha256"],
    }


def _assert_controller_authority_snapshot(
    contract_path: Path, asset_root: Path, expected: Mapping[str, object]
) -> dict[str, object]:
    current = _controller_authority_snapshot(contract_path, asset_root)
    if current != dict(expected):
        raise ValueError("held controller approval/final-contract authority drift")
    return current


def _render_worker(
    bpy: Any,
    *,
    asset_root: Path,
    contract_path: Path,
    staging_root: Path,
    shot_id: str,
    expected_contract_sha256: str,
    expected_bindings: Mapping[str, object],
) -> dict[str, object]:
    contract = _load_worker_contract(
        contract_path, asset_root, expected_contract_sha256, expected_bindings
    )
    approved = next((item for item in contract["shots"] if item["shot_id"] == shot_id), None)
    if approved is None:
        raise ValueError("final shot is not approval-authorized")
    campaign_shot = _CAMPAIGN.by_shot_id[shot_id]
    authority = _load_completion_authority(asset_root, campaign_shot)
    expected_authority = dict(approved["authority"])
    expected_authority.pop("checked_at", None)
    expected_authority.pop("blender_scene_validation", None)
    if expected_authority != _authority_worker_record(authority):
        raise ValueError("final shot current completion authority drift")
    if Path(str(bpy.data.filepath)).resolve() != authority.scene_path:
        raise ValueError("fresh Blender process opened the wrong editorial scene")
    snapshot, collection_errors = blender_editorial_scene._collect_runtime_snapshot(bpy, authority.contract)
    errors = [
        *collection_errors,
        *blender_editorial_scene._validate_editorial_runtime_snapshot(snapshot, authority.contract),
    ]
    if errors:
        raise ValueError("fresh native final scene authority failed: " + "; ".join(errors))

    width, height = _shot_dimensions(contract, approved)
    png = require_within(staging_root / f"{shot_id}.png", staging_root)
    exr = require_within(staging_root / f"{shot_id}.exr", staging_root)
    if png.exists() or exr.exists():
        raise ValueError("native final worker output already exists")
    baseline = _state_record(bpy)
    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.cycles.samples = int(contract["samples"])
    scene.cycles.use_denoising = bool(contract["denoise"])
    scene.render.filepath = str(png)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    mutated = _state_record(bpy)
    _validate_ephemeral_render_delta(baseline, mutated, contract)
    started_at = _utc_now()
    started = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    seconds = time.perf_counter() - started
    _validate_worker_png(bpy, png, width, height)
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "32"
    bpy.data.images["Render Result"].save_render(filepath=str(exr), scene=scene)
    if not exr.is_file() or exr.stat().st_size <= 0:
        raise ValueError("native archive EXR was not produced")
    if exr.read_bytes()[:4] != b"\x76\x2f\x31\x01":
        raise ValueError("native archive EXR magic is invalid")
    final_state = _state_record(bpy)
    _validate_ephemeral_render_delta(baseline, final_state, contract)
    after_snapshot, after_collection_errors = blender_editorial_scene._collect_runtime_snapshot(
        bpy, authority.contract
    )
    normalized_after = dict(after_snapshot)
    normalized_after["render"] = snapshot["render"]
    after_errors = [
        *after_collection_errors,
        *blender_editorial_scene._validate_editorial_runtime_snapshot(
            normalized_after, authority.contract
        ),
    ]
    if after_errors:
        raise ValueError("post-render editorial scene authority failed: " + "; ".join(after_errors))
    if {key: value for key, value in after_snapshot.items() if key != "render"} != {
        key: value for key, value in snapshot.items() if key != "render"
    }:
        raise ValueError("post-render camera/light/world/product/material/decal/contact drift")
    _load_worker_contract(
        contract_path, asset_root, expected_contract_sha256, expected_bindings
    )
    return {
        "shot_id": shot_id,
        "process_id": os.getpid(),
        "scene_sha256": authority.scene_sha256,
        "contract_sha256": authority.contract_sha256,
        "completion_marker_sha256": authority.completion_marker_sha256,
        "png": png.name,
        "png_sha256": sha256_file(png),
        "exr": exr.name,
        "exr_sha256": sha256_file(exr),
        "exr_validation": _parse_openexr(exr),
        "dimensions": [width, height],
        "samples": int(contract["samples"]),
        "denoise": bool(contract["denoise"]),
        "film_transparent": bool(scene.render.film_transparent),
        "started_at": started_at,
        "finished_at": _utc_now(),
        "seconds": round(seconds, 6),
        "authority_status": "pass",
        "actual_pixel_review": "pending",
    }


def _worker_command(
    blender: Path, scene: Path, asset_root: Path, contract: Path, staging: Path, shot_id: str,
    expected_contract_sha256: str,
    expected_bindings: Mapping[str, object],
) -> list[str]:
    return [
        str(blender), "--background", str(scene), "--python", str(Path(__file__).resolve()), "--",
        "--render-shot", "--asset-root", str(asset_root), "--contract", str(contract),
        "--staging-root", str(staging), "--shot-id", shot_id,
        "--expected-contract-sha256", expected_contract_sha256,
        "--expected-bindings-json", json.dumps(dict(expected_bindings), sort_keys=True),
    ]


def _parse_worker(completed: subprocess.CompletedProcess[str], shot_id: str) -> dict[str, object]:
    if completed.returncode != 0:
        raise ValueError(f"native final Blender worker failed for {shot_id}: {completed.stderr[-2000:]}")
    lines = [line for line in completed.stdout.splitlines() if line.startswith(WORKER_MARKER)]
    if len(lines) != 1:
        diagnostic = "\n".join(
            part[-2000:] for part in (completed.stdout, completed.stderr) if part
        )
        raise ValueError(
            f"native final Blender worker result is missing for {shot_id}; "
            f"worker_tail={diagnostic}"
        )
    payload = json.loads(lines[0][len(WORKER_MARKER):])
    if payload.get("shot_id") != shot_id:
        raise ValueError("native final Blender worker shot identity drift")
    return payload


def _build_contact_sheet(staging: Path, shots: Sequence[Mapping[str, object]]) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    output = staging / CONTACT_SHEET_NAME
    canvas = Image.new("RGB", (2560, 1800), (238, 238, 236))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=24)
    for index, shot in enumerate(shots):
        x = (index % 2) * 1280
        y = (index // 2) * 900
        with Image.open(staging / str(shot["png"])) as source:
            image = source.convert("RGB")
            image.thumbnail((1240, 820), Image.Resampling.LANCZOS)
            px = x + (1280 - image.width) // 2
            py = y + 38 + (820 - image.height) // 2
            canvas.paste(image, (px, py))
        draw.text((x + 20, y + 10), str(shot["shot_id"]), fill=(18, 18, 18), font=font)
    canvas.save(output, format="PNG", compress_level=6)
    return output


def _preserve_failure(staging: Path, asset_root: Path, release_id: str, error: Exception) -> Path | None:
    if not staging.exists():
        return None
    failure_parent = asset_root / "renders" / "final-failures" / FINAL_LIBRARY
    failure_parent.mkdir(parents=True, exist_ok=True)
    rejected = failure_parent / f"{release_id}-{uuid.uuid4().hex[:8]}"
    try:
        (staging / "failure.json").write_bytes(_json_bytes({
            "release_id": release_id, "failed_at": _utc_now(),
            "error_type": type(error).__name__, "error": str(error),
        }))
        os.rename(staging, rejected)
        return rejected
    except OSError:
        return None


def render_editorial_native_finals(asset_root: Path, blender: Path, contract_path: Path) -> Path:
    """Render four fresh native pairs into one exclusively claimed hidden staging root."""

    asset_root = Path(asset_root).resolve()
    blender = Path(blender).resolve()
    contract_path = Path(contract_path).resolve()
    held = _controller_authority_snapshot(contract_path, asset_root)
    contract = dict(held["_captured_contract"])
    _validate_blender_authority(asset_root, blender)
    parent = asset_root / "renders" / "final" / FINAL_LIBRARY
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / str(contract["release_id"])
    if target.exists():
        raise ValueError("editorial native final release already exists")
    staging = parent / f".{contract['release_id']}.pending-{uuid.uuid4().hex}"
    staging.mkdir(exist_ok=False)
    try:
        records = []
        for shot in contract["shots"]:
            _assert_controller_authority_snapshot(contract_path, asset_root, held)
            scene = Path(str(shot["authority"]["scene_path"]))
            completed = subprocess.run(
                _worker_command(
                    blender, scene, asset_root, contract_path, staging, str(shot["shot_id"]),
                    str(held["contract_sha256"]),
                    {key: value for key, value in held.items() if not key.startswith("_") and key != "contract_sha256"},
                ),
                capture_output=True, text=True, timeout=WORKER_TIMEOUT_SECONDS, check=False,
            )
            record = _parse_worker(completed, str(shot["shot_id"]))
            width, height = _shot_dimensions(contract, shot)
            record["ffprobe_exr_decode"] = _ffprobe_decode_exr(
                staging / str(record["exr"]), width, height
            )
            records.append(record)
            _assert_controller_authority_snapshot(contract_path, asset_root, held)
        if len({record["process_id"] for record in records}) != 4:
            raise ValueError("native final campaign did not use four fresh Blender processes")
        contact = _build_contact_sheet(staging, records)
        report = {
            "schema": "maliev.pimm-editorial-native-report/v1",
            "release_id": contract["release_id"],
            "generation_id": contract["generation_id"],
            "contract_path": str(contract_path),
            "contract_sha256": held["contract_sha256"],
            "rendered_at": _utc_now(),
            "fresh_blender_processes": 4,
            "samples": 256,
            "denoise": True,
            "shots": records,
            "contact_sheet": {"path": contact.name, "sha256": sha256_file(contact), "dimensions": [2560, 1800]},
            "status": "pending-actual-pixel-review",
        }
        _exclusive_json(staging / REPORT_NAME, report)
        _assert_controller_authority_snapshot(contract_path, asset_root, held)
        return staging
    except Exception as error:
        rejected = _preserve_failure(staging, asset_root, str(contract["release_id"]), error)
        suffix = f"; evidence={rejected}" if rejected else ""
        raise RuntimeError(f"editorial native final render failed: {error}{suffix}") from error


def _validate_staging(staging: Path, contract: Mapping[str, object]) -> tuple[dict[str, object], set[str]]:
    from PIL import Image

    report_path = staging / REPORT_NAME
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        report.get("schema") != "maliev.pimm-editorial-native-report/v1"
        or report.get("status") != "pending-actual-pixel-review"
        or report.get("release_id") != contract["release_id"]
        or report.get("generation_id") != contract["generation_id"]
        or report.get("contract_sha256") != sha256_file(Path(str(report["contract_path"])))
        or report.get("fresh_blender_processes") != 4
        or report.get("samples") != 256
        or report.get("denoise") is not True
    ):
        raise ValueError("native report contract binding drift")
    records = report.get("shots")
    if not isinstance(records, list) or [item.get("shot_id") for item in records] != [item["shot_id"] for item in contract["shots"]]:
        raise ValueError("native report exact four-shot set drift")
    process_ids = [item.get("process_id") for item in records]
    if (
        any(not isinstance(value, int) or isinstance(value, bool) for value in process_ids)
        or len(set(process_ids)) != 4
    ):
        raise ValueError("native report does not prove four fresh Blender processes")
    expected = {REPORT_NAME, CONTACT_SHEET_NAME}
    for approved, record in zip(contract["shots"], records, strict=True):
        width, height = _shot_dimensions(contract, approved)
        authority = approved["authority"]
        if (
            record.get("dimensions") != [width, height]
            or record.get("samples") != 256
            or record.get("denoise") is not True
            or record.get("film_transparent") is not False
            or record.get("authority_status") != "pass"
            or record.get("scene_sha256") != authority.get("scene_sha256")
            or record.get("contract_sha256") != authority.get("contract_sha256")
            or record.get("completion_marker_sha256") != authority.get("completion_marker_sha256")
        ):
            raise ValueError("native final dimensions, render, opacity, or authority evidence drift")
        for field in ("png", "exr"):
            relative = record.get(field)
            if not isinstance(relative, str) or Path(relative).name != relative:
                raise ValueError("native final output path is invalid")
            path = require_within(staging / relative, staging)
            if not path.is_file() or sha256_file(path) != record.get(f"{field}_sha256"):
                raise ValueError(f"native final {field} hash drift")
            expected.add(relative)
        exr_path = staging / str(record["exr"])
        exr_validation = _parse_openexr(exr_path)
        ffprobe_decode = _ffprobe_decode_exr(exr_path, width, height)
        if (
            record.get("exr_validation") != exr_validation
            or exr_validation.get("dimensions") != [width, height]
            or not {"R", "G", "B"}.issubset(set(exr_validation.get("channels", [])))
            or record.get("ffprobe_exr_decode") != ffprobe_decode
        ):
            raise ValueError("native final EXR dimensions/channels/decode evidence drift")
        with Image.open(staging / str(record["png"])) as image:
            if image.format != "PNG" or image.size != (width, height):
                raise ValueError("native final PNG dimensions or format drift")
    sheet = staging / CONTACT_SHEET_NAME
    if report.get("contact_sheet", {}).get("sha256") != sha256_file(sheet):
        raise ValueError("native final contact-sheet hash drift")
    observed = {path.name for path in staging.iterdir()}
    if observed != expected or any(path.is_dir() for path in staging.iterdir()):
        raise ValueError("native final staging contains extra or missing files")
    return report, expected


def _tree_fingerprint(root: Path) -> tuple[tuple[str, str], ...]:
    return tuple(
        (path.relative_to(root).as_posix(), sha256_file(path))
        for path in sorted(root.rglob("*")) if path.is_file()
    )


def _copy_transaction_candidate(
    staging: Path, asset_root: Path, release_id: str
) -> Path:
    """Copy immutable pending bytes into one owned transaction candidate."""

    before = _tree_fingerprint(staging)
    transaction_root = asset_root / "renders" / "final-transactions" / FINAL_LIBRARY
    transaction_root.mkdir(parents=True, exist_ok=True)
    candidate = transaction_root / f".{release_id}.{uuid.uuid4().hex}.candidate"
    candidate.mkdir(exist_ok=False)
    try:
        for source in staging.iterdir():
            if not source.is_file():
                raise ValueError("native final pending tree contains a directory")
            shutil.copyfile(source, candidate / source.name)
        if _tree_fingerprint(staging) != before or _tree_fingerprint(candidate) != before:
            raise ValueError("native final pending bytes drifted during copy-on-write capture")
        return candidate
    except Exception:
        shutil.rmtree(candidate, ignore_errors=True)
        raise


def _discard_candidate(candidate: Path) -> None:
    """Remove an owned candidate; it never removes or edits pending source bytes."""

    if candidate.exists():
        for path in candidate.rglob("*"):
            if path.is_file():
                path.chmod(0o644)
        shutil.rmtree(candidate)


def _disposition_claim_paths(
    staging: Path, asset_root: Path
) -> tuple[Path, Path, Path]:
    claim_root = asset_root / "renders" / "final-transactions" / FINAL_LIBRARY / ".claims"
    key = hashlib.sha256(str(staging.resolve()).encode()).hexdigest()
    return (
        claim_root / f"{key}.claim",
        claim_root / f"{key}.accept",
        claim_root / f"{key}.reject",
    )


def _acquire_disposition_claim(
    staging: Path,
    asset_root: Path,
    release_id: str,
    decision: str,
    source_fingerprint: tuple[tuple[str, str], ...],
) -> Path:
    """Exclusively claim one pending tree for exactly one accept/reject decision."""

    if decision not in {"accept", "reject"}:
        raise ValueError("native final disposition decision is invalid")
    active, accepted, rejected = _disposition_claim_paths(staging, asset_root)
    active.parent.mkdir(parents=True, exist_ok=True)
    if accepted.exists() or rejected.exists():
        raise ValueError("native final pending tree already has a terminal disposition claim")
    try:
        active.mkdir(exist_ok=False)
    except FileExistsError as error:
        raise ValueError("native final pending tree already has an active disposition") from error
    try:
        if accepted.exists() or rejected.exists():
            raise ValueError("native final pending tree already has a terminal disposition claim")
        _exclusive_json(active / "decision.json", {
            "schema": "maliev.pimm-editorial-disposition-claim/v1",
            "release_id": release_id,
            "decision": decision,
            "pending_path": str(staging),
            "pending_fingerprint": list(source_fingerprint),
        })
        return active
    except Exception:
        _discard_candidate(active)
        raise


def _terminalize_disposition_claim(
    active: Path, decision: str, result: Mapping[str, object]
) -> Path:
    """Bind the terminal output then atomically rename the exclusive claim."""

    accepted = active.with_suffix(".accept")
    rejected = active.with_suffix(".reject")
    terminal = accepted if decision == "accept" else rejected
    if accepted.exists() or rejected.exists():
        raise ValueError("native final terminal disposition already exists")
    _exclusive_json(active / "result.json", {
        "schema": "maliev.pimm-editorial-disposition-result/v1",
        "decision": decision,
        **dict(result),
    })
    os.rename(active, terminal)
    return terminal


def reject_editorial_native_release(
    staging: Path, contract_path: Path, disposition: Mapping[str, object]
) -> Path:
    """Atomically preserve one hash-bound actual-pixel rejection outside finals."""

    staging = Path(staging).resolve()
    contract_path = Path(contract_path).resolve()
    asset_root = contract_path.parents[3]
    contract = validate_editorial_final_contract(contract_path, asset_root)
    parent = asset_root / "renders" / "final" / FINAL_LIBRARY
    require_within(staging, parent)
    if not staging.is_dir() or not staging.name.startswith(f".{contract['release_id']}.pending"):
        raise ValueError("native final staging claim is missing or invalid")
    report, _expected = _validate_staging(staging, contract)
    if disposition.get("decision") != "reject" or not str(disposition.get("reviewer", "")).strip():
        raise ValueError("actual-pixel rejection is not identified")
    sheet = disposition.get("contact_sheet")
    if not isinstance(sheet, Mapping) or sheet.get("sha256") != report["contact_sheet"]["sha256"]:
        raise ValueError("actual-pixel rejection contact-sheet hash drift")
    reviews = disposition.get("shots")
    if not isinstance(reviews, list) or len(reviews) != 4:
        raise ValueError("actual-pixel rejection requires exact four-shot evidence")
    any_failure = False
    for record, review in zip(report["shots"], reviews, strict=True):
        if (
            not isinstance(review, Mapping)
            or review.get("shot_id") != record["shot_id"]
            or review.get("png_sha256") != record["png_sha256"]
            or review.get("exr_sha256") != record["exr_sha256"]
            or not str(review.get("notes", "")).strip()
        ):
            raise ValueError("actual-pixel rejection shot/hash evidence drift")
        states = [review.get(field) for field in _PASS_FIELDS]
        if any(state not in {"pass", "fail"} for state in states):
            raise ValueError("actual-pixel rejection fields must be explicit pass/fail")
        any_failure = any_failure or "fail" in states
    if not any_failure:
        raise ValueError("actual-pixel rejection must identify at least one failed field")
    target = parent / str(contract["release_id"])
    if target.exists():
        raise ValueError("native final release already has an accepted terminal output")
    source_fingerprint = _tree_fingerprint(staging)
    claim = _acquire_disposition_claim(
        staging, asset_root, str(contract["release_id"]), "reject", source_fingerprint
    )
    candidate: Path | None = None
    failure_parent = asset_root / "renders" / "final-failures" / FINAL_LIBRARY
    failure_parent.mkdir(parents=True, exist_ok=True)
    rejected = failure_parent / f"{contract['release_id']}-rejected-{uuid.uuid4().hex[:8]}"
    try:
        candidate = _copy_transaction_candidate(
            staging, asset_root, str(contract["release_id"])
        )
        _exclusive_json(candidate / REJECTED_DISPOSITION_NAME, dict(disposition))
        os.rename(candidate, rejected)
        candidate = None
        _terminalize_disposition_claim(claim, "reject", {
            "output_path": str(rejected),
            "output_fingerprint": list(_tree_fingerprint(rejected)),
        })
    except Exception as error:
        if candidate is not None and candidate.exists():
            _discard_candidate(candidate)
        if not rejected.exists() and claim.exists():
            _discard_candidate(claim)
        if _tree_fingerprint(staging) != source_fingerprint:
            raise ValueError("reject rollback failed: pending source bytes changed") from error
        raise ValueError(f"native final rejection transaction failed: {error}") from error
    return rejected


def publish_editorial_native_release(
    staging: Path, contract_path: Path, disposition: Mapping[str, object]
) -> Path:
    """Publish only a complete, hash-bound actual-pixel acceptance; marker last."""

    staging = Path(staging).resolve()
    contract_path = Path(contract_path).resolve()
    asset_root = contract_path.parents[3]
    contract = validate_editorial_final_contract(contract_path, asset_root)
    parent = asset_root / "renders" / "final" / FINAL_LIBRARY
    require_within(staging, parent)
    if not staging.name.startswith(f".{contract['release_id']}") or ".pending" not in staging.name:
        raise ValueError("native final staging claim is invalid")
    report, expected = _validate_staging(staging, contract)
    from PIL import Image

    target = parent / str(contract["release_id"])
    if target.exists():
        raise ValueError("native final release replay or competing publication collision")

    if disposition.get("decision") != "accept" or not str(disposition.get("reviewer", "")).strip():
        raise ValueError("actual-pixel disposition is not an identified acceptance")
    reviewed_at = disposition.get("reviewed_at")
    if not isinstance(reviewed_at, str) or not reviewed_at.endswith("Z"):
        raise ValueError("actual-pixel disposition UTC timestamp is invalid")
    sheet_review = disposition.get("contact_sheet")
    if not isinstance(sheet_review, Mapping) or sheet_review.get("pixel_review") != "pass" or sheet_review.get("sha256") != report["contact_sheet"]["sha256"]:
        raise ValueError("contact-sheet actual-pixel disposition is incomplete or hash drifted")
    reviews = disposition.get("shots")
    if not isinstance(reviews, list) or len(reviews) != 4:
        raise ValueError("exactly four actual-pixel shot dispositions are required")
    for record, review in zip(report["shots"], reviews, strict=True):
        if not isinstance(review, Mapping) or review.get("shot_id") != record["shot_id"]:
            raise ValueError("actual-pixel shot disposition identity drift")
        if review.get("png_sha256") != record["png_sha256"] or review.get("exr_sha256") != record["exr_sha256"]:
            raise ValueError("actual-pixel shot disposition hash drift")
        if any(review.get(field) != "pass" for field in _PASS_FIELDS) or not str(review.get("notes", "")).strip():
            raise ValueError("actual-pixel shot disposition requires every field to pass")
    source_staging = staging
    source_fingerprint = _tree_fingerprint(source_staging)
    claim = _acquire_disposition_claim(
        source_staging, asset_root, str(contract["release_id"]), "accept",
        source_fingerprint,
    )
    staging: Path | None = None
    try:
        staging = _copy_transaction_candidate(
            source_staging, asset_root, str(contract["release_id"])
        )
        report, expected = _validate_staging(staging, contract)
        # Web derivatives are intentionally created only after acceptance is complete.
        for record in report["shots"]:
            webp = staging / f"{record['shot_id']}.webp"
            with Image.open(staging / str(record["png"])) as image:
                image.save(webp, format="WEBP", quality=92, method=6)
            record["webp"] = webp.name
            record["webp_sha256"] = sha256_file(webp)
            expected.add(webp.name)
        disposition_path = staging / DISPOSITION_NAME
        _exclusive_json(disposition_path, dict(disposition))
        expected.add(DISPOSITION_NAME)
        report["status"] = "accepted"
        report["accepted_at"] = _utc_now()
        report["actual_pixel_disposition"] = {
            "path": DISPOSITION_NAME,
            "sha256": sha256_file(disposition_path),
        }
        report_path = staging / REPORT_NAME
        report_path.chmod(0o644)
        report_path.write_bytes(_json_bytes(report))
        report_path.chmod(0o444)
        validate_editorial_final_contract(contract_path, asset_root)
        expected.add(REPORT_NAME)
        manifest = {
            "schema": "maliev.pimm-editorial-native-release/v1",
            "release_id": contract["release_id"],
            "generation_id": contract["generation_id"],
            "approval": contract["approval"],
            "contract": {
                "path": str(contract_path),
                "sha256": sha256_file(contract_path),
            },
            "report": {"path": REPORT_NAME, "sha256": sha256_file(report_path)},
            "contact_sheet": report["contact_sheet"],
            "actual_pixel_disposition": report["actual_pixel_disposition"],
            "shots": report["shots"],
            "published_at": _utc_now(),
            "status": "accepted",
        }
        # Every fallible authority and tree check completes before marker creation.
        observed = {path.name for path in staging.iterdir()}
        if observed != expected or any(path.is_dir() for path in staging.iterdir()):
            raise ValueError("native final release tree contains extra or missing files")
        validate_editorial_final_contract(contract_path, asset_root)
        marker = staging / RELEASE_MANIFEST_NAME
        _exclusive_json(marker, manifest)
        os.rename(staging, target)  # marker is immediately followed by atomic rename
        staging = None
        _terminalize_disposition_claim(claim, "accept", {
            "output_path": str(target),
            "release_manifest_sha256": sha256_file(target / RELEASE_MANIFEST_NAME),
        })
    except Exception as error:
        if staging is not None and staging.exists():
            _discard_candidate(staging)
        if not target.exists() and claim.exists():
            _discard_candidate(claim)
        if _tree_fingerprint(source_staging) != source_fingerprint:
            raise ValueError("publication rollback failed: pending source bytes changed") from error
        raise ValueError(f"native final publication transaction failed: {error}") from error
    return target


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-shot", action="store_true")
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--staging-root", type=Path)
    parser.add_argument("--shot-id")
    parser.add_argument("--expected-contract-sha256")
    parser.add_argument("--expected-bindings-json")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(
        list(argv) if argv is not None else sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    )
    if not arguments.render_shot or None in (
        arguments.asset_root, arguments.contract, arguments.staging_root,
        arguments.shot_id, arguments.expected_contract_sha256,
        arguments.expected_bindings_json,
    ):
        raise ValueError("native final worker requires render-shot, asset-root, contract, staging-root, and shot-id")
    import bpy
    result = _render_worker(
        bpy,
        asset_root=arguments.asset_root.resolve(),
        contract_path=arguments.contract.resolve(),
        staging_root=arguments.staging_root.resolve(),
        shot_id=str(arguments.shot_id),
        expected_contract_sha256=str(arguments.expected_contract_sha256),
        expected_bindings=json.loads(str(arguments.expected_bindings_json)),
    )
    print(WORKER_MARKER + json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
