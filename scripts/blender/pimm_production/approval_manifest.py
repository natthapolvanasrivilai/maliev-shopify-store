"""Immutable, hash-bound owner decisions for reviewed PIMM proof renders."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import ntpath
import os
import re
import secrets
import stat
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator, Mapping

from PIL import Image

from .proof_contract import (
    ProofContract,
    _entry as proof_output_entry,
    _validate_render_metadata,
    validate_proof_contract,
)
from .scene_contract import SceneContract
from .machine_contract import validate_machine_contract


_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_SHOT_ID = re.compile(r"^pimm-(?:30g|50g)(?:--[a-z0-9]+(?:-[a-z0-9]+)*)+$")
_GENERATION_ID = re.compile(r"^proof-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{7}$")
_REVISION_NAME = re.compile(r"^approval-r([0-9]{2,})\.json$")
_DECISIONS = frozenset({"approved", "rejected"})
_APPROVAL_SCHEMA = "pimm-owner-approval/v1"
_APPROVAL_FIELDS = {
    "schema", "schema_version", "revision", "prior_approval_sha256",
    "prior_approval_path", "decision", "owner", "notes", "created_at_utc",
    "shot_id", "proof_manifest_path", "proof_generation_id", "authority_roots",
    "evidence", "inputs", "render_settings", "proof_output_sha256",
}
_PROOF_FIELDS = {
    "schema", "generation_id", "status", "stage", "scene_sha256",
    "master_sha256", "material_library_sha256", "resolution_percentage",
    "samples", "denoise", "contract", "render", "fingerprints_unchanged",
    "qa", "outputs",
}
_AUTHORITY_NAMES = frozenset({"asset", "repository", "tool"})
_BASE_EVIDENCE_AUTHORITIES = {
    "source": "asset",
    "master": "asset",
    "material_library": "asset",
    "scene": "asset",
    "proof_contract": "asset",
    "scene_contract": "asset",
    "scene_contract_snapshot": "asset",
    "tool_lock": "asset",
    "render_metadata": "asset",
    "proof_manifest": "asset",
    "contact_sheet": "asset",
    "blender_binary": "tool",
    "proof_runner": "repository",
    "final_runner": "repository",
    "machine_contract": "repository",
}
_FILE_RECORD_FIELDS = {
    "authority", "path", "sha256", "bytes", "mtime_ns", "ctime_ns", "change_time_ns",
    "device", "inode", "links",
}
_RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
_REPARSE_ATTRIBUTE = 0x400
_CANONICAL_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def canonical_json_sha256(value: object) -> str:
    """Return the deterministic SHA-256 used for immutable state records."""

    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest().upper()


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a 64-character SHA-256")
    return value.upper()


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _canonical_component(value: object, label: str) -> str:
    """Validate one Windows-safe path/identity component without aliases."""

    if not isinstance(value, str) or not value or value in {".", ".."}:
        raise ValueError(f"{label} must be a canonical component")
    if "/" in value or "\\" in value or ":" in value or value[-1] in {".", " "}:
        raise ValueError(f"{label} must be a canonical component")
    if value.upper().split(".", 1)[0] in _RESERVED_WINDOWS_NAMES:
        raise ValueError(f"{label} uses a reserved Windows name")
    return value


def _validate_created_at_utc(value: object) -> None:
    if not isinstance(value, str) or _CANONICAL_UTC.fullmatch(value) is None:
        raise ValueError("approval created_at_utc must be canonical UTC ISO-8601 ending in Z")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("approval created_at_utc must be a real canonical UTC instant") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("approval created_at_utc must be canonical UTC ISO-8601 ending in Z")


def canonical_absolute_path(value: object, label: str) -> Path:
    """Accept only an exact drive-absolute, non-device Windows spelling."""

    if not isinstance(value, str) or not value or "/" in value:
        raise ValueError(f"{label} must be an exact absolute Windows path")
    if (
        value.startswith("\\\\")
        or value.startswith("\\??\\")
        or value.startswith("\\\\?\\")
        or value.startswith("\\\\.\\")
    ):
        raise ValueError(f"{label} cannot be UNC or a Windows device path")
    drive, tail = ntpath.splitdrive(value)
    if re.fullmatch(r"[A-Z]:", drive) is None or not tail.startswith("\\"):
        raise ValueError(f"{label} must be an exact drive-absolute Windows path")
    if ":" in tail:
        raise ValueError(f"{label} cannot contain an alternate data stream")
    components = tail[1:].split("\\") if len(tail) > 1 else []
    if any(not component for component in components):
        raise ValueError(f"{label} contains an empty path alias")
    for component in components:
        _canonical_component(component, label)
    path = Path(value)
    if str(path) != value:
        raise ValueError(f"{label} is not canonically spelled")
    return path


def _lexically_within(path: Path, root: Path, label: str) -> None:
    """Check containment on validated lexical paths before any resolution."""

    path_text = ntpath.normcase(ntpath.normpath(str(path)))
    root_text = ntpath.normcase(ntpath.normpath(str(root)))
    try:
        common = ntpath.commonpath((path_text, root_text))
    except ValueError as error:
        raise ValueError(f"{label} is outside its authority root") from error
    if common != root_text:
        raise ValueError(f"{label} is outside its authority root")


def _reject_reparse_ancestors(path: Path, label: str) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            status = os.lstat(current)
        except FileNotFoundError:
            continue
        attributes = int(getattr(status, "st_file_attributes", 0))
        if stat.S_ISLNK(status.st_mode) or attributes & _REPARSE_ATTRIBUTE:
            raise ValueError(f"{label} traverses a symlink, junction, or reparse point")


def _identity(status: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        int(status.st_dev), int(status.st_ino), int(status.st_nlink),
        int(status.st_size), int(status.st_mtime_ns),
    )


def _change_time_ns(descriptor: int, status: os.stat_result) -> int:
    """Return NTFS ChangeTime (not creation time) for transient mutation detection."""

    if os.name != "nt":
        return int(status.st_ctime_ns)
    import ctypes
    import msvcrt

    class FileBasicInfo(ctypes.Structure):
        _fields_ = (
            ("CreationTime", ctypes.c_longlong),
            ("LastAccessTime", ctypes.c_longlong),
            ("LastWriteTime", ctypes.c_longlong),
            ("ChangeTime", ctypes.c_longlong),
            ("FileAttributes", ctypes.c_ulong),
        )

    information = FileBasicInfo()
    handle = msvcrt.get_osfhandle(descriptor)
    succeeded = ctypes.windll.kernel32.GetFileInformationByHandleEx(
        ctypes.c_void_p(handle),
        0,
        ctypes.byref(information),
        ctypes.sizeof(information),
    )
    if not succeeded:
        raise OSError(ctypes.get_last_error(), "GetFileInformationByHandleEx(FileBasicInfo) failed")
    return int(information.ChangeTime) * 100


def _stable_file(
    path_value: object,
    root_value: object,
    authority: str,
    label: str,
    *,
    expected: Mapping[str, object] | None = None,
    capture: bool = False,
) -> tuple[dict[str, object], bytes | None]:
    """Hash/read one file while pinning identity before, during, and after I/O."""

    path = canonical_absolute_path(path_value, f"{label} path")
    root = canonical_absolute_path(root_value, f"{label} authority root")
    _lexically_within(path, root, label)
    _reject_reparse_ancestors(path, label)
    before = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"{label} must be one regular single-link file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    captured = bytearray() if capture else None
    try:
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(before):
            raise ValueError(f"{label} file identity raced before read")
        change_time_ns = _change_time_ns(descriptor, opened)
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            digest.update(chunk)
            if captured is not None:
                captured.extend(chunk)
        after_open = os.fstat(descriptor)
        if _identity(after_open) != _identity(before):
            raise ValueError(f"{label} file identity raced during read")
        if _change_time_ns(descriptor, after_open) != change_time_ns:
            raise ValueError(f"{label} file change time raced during read")
    finally:
        os.close(descriptor)
    after_path = os.stat(path, follow_symlinks=False)
    if (
        _identity(after_path) != _identity(before)
        or int(after_path.st_ctime_ns) != int(before.st_ctime_ns)
    ):
        raise ValueError(f"{label} file identity raced after read")
    record: dict[str, object] = {
        "authority": authority,
        "path": str(path),
        "sha256": digest.hexdigest().upper(),
        "bytes": int(before.st_size),
        "mtime_ns": int(before.st_mtime_ns),
        "ctime_ns": int(before.st_ctime_ns),
        "change_time_ns": change_time_ns,
        "device": int(before.st_dev),
        "inode": int(before.st_ino),
        "links": int(before.st_nlink),
    }
    if expected is not None:
        if set(expected) != _FILE_RECORD_FIELDS:
            raise ValueError(f"{label} evidence fields are invalid")
        if dict(expected) != record:
            raise ValueError(f"{label} evidence drift")
    return record, bytes(captured) if captured is not None else None


def stable_file_record(
    path: Path,
    root: Path,
    authority: str,
    label: str,
    expected: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return _stable_file(str(path), str(root), authority, label, expected=expected)[0]


def stable_json(
    path: Path,
    root: Path,
    authority: str,
    label: str,
    expected: Mapping[str, object] | None = None,
) -> tuple[Mapping[str, object], dict[str, object]]:
    record, raw = _stable_file(
        str(path), str(root), authority, label, expected=expected, capture=True
    )
    try:
        payload = json.loads((raw or b"").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not canonical UTF-8 JSON: {error}") from error
    return _mapping(payload, label), record


def _create_new_json(
    path: Path,
    payload: Mapping[str, object],
    *,
    before_commit: Callable[[Path], None] | None = None,
    after_commit: Callable[[Path], None] | None = None,
) -> dict[str, object]:
    """Stage complete JSON privately, then atomically claim its absent final name."""

    _canonical_component(path.name, "immutable JSON filename")
    _reject_reparse_ancestors(path.parent, "immutable JSON parent")
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    pending = path.parent / f".{path.name}.{secrets.token_hex(16)}.pending"
    descriptor = os.open(
        pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    )
    created = os.fstat(descriptor)
    created_identity = (int(created.st_dev), int(created.st_ino), int(created.st_nlink))
    pending_published = False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        status = os.stat(pending, follow_symlinks=False)
        if (
            not stat.S_ISREG(status.st_mode)
            or int(status.st_nlink) != 1
            or (int(status.st_dev), int(status.st_ino), int(status.st_nlink))
            != created_identity
            or int(status.st_size) != len(encoded)
        ):
            raise ValueError("exclusive JSON pending identity changed")
        if os.path.lexists(path):
            raise FileExistsError(f"immutable JSON already exists: {path}")
        if before_commit is not None:
            before_commit(pending)
        revalidated = os.stat(pending, follow_symlinks=False)
        if _identity(revalidated) != _identity(status):
            raise ValueError("exclusive JSON pending identity changed before commit")
        if os.path.lexists(path):
            raise FileExistsError(f"immutable JSON already exists: {path}")
        os.rename(pending, path)
        pending_published = True
        final = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(final.st_mode)
            or int(final.st_nlink) != 1
            or (int(final.st_dev), int(final.st_ino))
            != (int(status.st_dev), int(status.st_ino))
            or int(final.st_size) != len(encoded)
        ):
            raise ValueError("exclusive JSON final identity changed")
        if after_commit is not None:
            after_commit(path)
        return {
            "device": int(final.st_dev),
            "inode": int(final.st_ino),
            "links": int(final.st_nlink),
            "bytes": int(final.st_size),
            "mtime_ns": int(final.st_mtime_ns),
            "ctime_ns": int(final.st_ctime_ns),
        }
    except BaseException:
        # A final-name competitor is never removed. Clean only the exact pending
        # or final inode created by this call.
        cleanup_path = path if pending_published else pending
        try:
            current = os.stat(cleanup_path, follow_symlinks=False)
            if (
                int(current.st_dev), int(current.st_ino), int(current.st_nlink)
            ) == created_identity:
                cleanup_path.unlink()
        except OSError:
            pass
        raise


def _unlink_owned(path: Path, identity: Mapping[str, object], label: str) -> None:
    _reject_reparse_ancestors(path, label)
    status = os.stat(path, follow_symlinks=False)
    actual = {
        "device": int(status.st_dev),
        "inode": int(status.st_ino),
        "links": int(status.st_nlink),
        "bytes": int(status.st_size),
        "mtime_ns": int(status.st_mtime_ns),
        "ctime_ns": int(status.st_ctime_ns),
    }
    expected = {key: identity.get(key) for key in actual}
    if actual != expected:
        raise ValueError(f"{label} identity changed before delete")
    path.unlink()


@contextlib.contextmanager
def approval_head_lock(approval_dir: Path) -> Iterator[None]:
    """Hold the exclusive revision-head claim for selection through publication."""

    approval_dir.mkdir(parents=True, exist_ok=True)
    _reject_reparse_ancestors(approval_dir, "approval head directory")
    lock_path = approval_dir / ".approval-head.lock"
    descriptor = os.open(
        lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    )
    try:
        os.write(descriptor, b"pimm approval head lock\n")
        os.fsync(descriptor)
        status = os.stat(lock_path, follow_symlinks=False)
        identity = {
            "device": int(status.st_dev),
            "inode": int(status.st_ino),
            "links": int(status.st_nlink),
            "bytes": int(status.st_size),
            "mtime_ns": int(status.st_mtime_ns),
            "ctime_ns": int(status.st_ctime_ns),
        }
        yield
    finally:
        os.close(descriptor)
        _unlink_owned(lock_path, identity, "approval head lock")


def _authority_roots(asset_root: Path, blender_binary: Path) -> dict[str, str]:
    repository = Path(__file__).resolve().parents[3]
    return {
        "asset": str(asset_root),
        "repository": str(repository),
        "tool": str(blender_binary.parent),
    }


def _validate_roots(value: object) -> dict[str, Path]:
    roots = _mapping(value, "authority roots")
    if set(roots) != _AUTHORITY_NAMES:
        raise ValueError("authority roots must contain exactly asset, repository, and tool")
    return {
        name: canonical_absolute_path(roots[name], f"{name} authority root")
        for name in sorted(_AUTHORITY_NAMES)
    }


def _state_from_proof(
    proof: Mapping[str, object], scene: SceneContract, metadata: Mapping[str, object]
) -> dict[str, object]:
    authored = _mapping(metadata.get("authored_settings"), "proof authored settings")
    current = _mapping(authored.get("before"), "proof authored settings before")
    image = _mapping(metadata.get("image_settings"), "proof image settings")
    effective_dimensions = metadata.get("actual_dimensions")
    base_dimensions = metadata.get("base_dimensions")
    samples = metadata.get("samples")
    state: dict[str, object] = {
        "camera_sha256": canonical_json_sha256(current.get("camera")),
        "lights_sha256": canonical_json_sha256(current.get("lights")),
        "world_sha256": canonical_json_sha256(current.get("world")),
        "compositor_sha256": canonical_json_sha256(current.get("compositor")),
        "render_settings_sha256": canonical_json_sha256(
            {
                "render": current.get("render"),
                "cycles": current.get("cycles"),
                "color_management": current.get("color_management"),
                "view_layers": current.get("view_layers"),
            }
        ),
        "animation_sha256": canonical_json_sha256(
            {"animation_contract": scene.animation_contract, "objects": current.get("objects")}
        ),
        "composition_sha256": canonical_json_sha256(proof.get("qa")),
        "base_dimensions": base_dimensions,
        "effective_proof_dimensions": effective_dimensions,
        "output_dimensions": base_dimensions,
        "alpha_mode": image.get("color_mode"),
        "proof_samples": samples,
    }
    if (
        not isinstance(base_dimensions, list)
        or len(base_dimensions) != 2
        or not all(isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in base_dimensions)
        or not isinstance(effective_dimensions, list)
        or len(effective_dimensions) != 2
        or not all(
            isinstance(item, int) and not isinstance(item, bool) and item > 0
            for item in effective_dimensions
        )
        or base_dimensions != [scene.output_contract["width"], scene.output_contract["height"]]
        or state["alpha_mode"] != "RGBA"
        or not isinstance(samples, int)
        or isinstance(samples, bool)
        or samples <= 0
    ):
        raise ValueError("proof current render settings are invalid")
    return state


def _decode_rgba_pixels(
    data: bytes, dimensions: list[object], label: str
) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.format != "PNG" or image.mode != "RGBA" or list(image.size) != dimensions:
                raise ValueError(f"{label} must be an original-resolution RGBA PNG")
            width, height = image.size
            pixels = list(image.get_flattened_data())
    except OSError as error:
        raise ValueError(f"{label} is not genuine PNG pixel evidence: {error}") from error
    return width, height, pixels


def _rgba_pixel_evidence(
    data: bytes, dimensions: list[object], label: str
) -> dict[str, object]:
    width, _, pixels = _decode_rgba_pixels(data, dimensions, label)
    visible = [pixel for pixel in pixels if pixel[3] > 0]
    if not visible:
        raise ValueError(f"{label} contains no visible product pixels")
    indices = [index for index, pixel in enumerate(pixels) if pixel[3] > 0]
    xs = [index % width for index in indices]
    ys = [index // width for index in indices]
    rgba_bytes = bytes(channel for pixel in pixels for channel in pixel)
    mask_bytes = bytes(255 if pixel[3] > 0 else 0 for pixel in pixels)
    visible_rgb = bytes(channel for pixel in visible for channel in pixel[:3])
    alpha = bytes(pixel[3] for pixel in pixels)
    return {
        "rgba_sha256": hashlib.sha256(rgba_bytes).hexdigest().upper(),
        "product_mask_sha256": hashlib.sha256(mask_bytes).hexdigest().upper(),
        "subject_bounds": [min(xs), min(ys), max(xs), max(ys)],
        "visible_pixels": len(visible),
        "visible_fraction": round(len(visible) / len(pixels), 8),
        "visible_rgb_sha256": hashlib.sha256(visible_rgb).hexdigest().upper(),
        "unique_rgb_values": len({pixel[:3] for pixel in visible}),
        "alpha_sha256": hashlib.sha256(alpha).hexdigest().upper(),
        "alpha_minimum": min(alpha),
        "alpha_maximum": max(alpha),
        "alpha_nonzero_pixels": sum(value > 0 for value in alpha),
        "alpha_partial_pixels": sum(0 < value < 255 for value in alpha),
    }


def _region_pixel_evidence(
    pixels: list[tuple[int, int, int, int]],
    width: int,
    box: list[int],
    label: str,
) -> dict[str, object]:
    left, top, right, bottom = box
    region = [
        pixels[y * width + x]
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
    ]
    visible = [pixel for pixel in region if pixel[3] > 0]
    if not visible:
        raise ValueError(f"final {label} region contains no visible product pixels")
    rgba_bytes = bytes(channel for pixel in region for channel in pixel)
    mask_bytes = bytes(255 if pixel[3] > 0 else 0 for pixel in region)
    visible_rgb = bytes(channel for pixel in visible for channel in pixel[:3])
    return {
        "region": box,
        "rgba_sha256": hashlib.sha256(rgba_bytes).hexdigest().upper(),
        "product_mask_sha256": hashlib.sha256(mask_bytes).hexdigest().upper(),
        "visible_rgb_sha256": hashlib.sha256(visible_rgb).hexdigest().upper(),
        "visible_pixels": len(visible),
        "unique_rgb_values": len({pixel[:3] for pixel in visible}),
    }


def _controller_digit_patterns(
    pixels: list[tuple[int, int, int, int]],
    width: int,
    box: list[int],
    digit_count: int,
) -> list[str]:
    left, top, right, bottom = box
    visible_luma = [
        sum(pixels[y * width + x][:3])
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
        if pixels[y * width + x][3] > 0
    ]
    threshold = (min(visible_luma) + max(visible_luma)) / 2
    samples = ((0.5, 0.1), (0.2, 0.3), (0.8, 0.3), (0.5, 0.5),
               (0.2, 0.7), (0.8, 0.7), (0.5, 0.9))
    region_width = right - left + 1
    region_height = bottom - top + 1
    patterns: list[str] = []
    for digit in range(digit_count):
        digit_left = left + digit * region_width / digit_count
        digit_right = left + (digit + 1) * region_width / digit_count - 1
        bits = []
        for x_fraction, y_fraction in samples:
            x = round(digit_left + max(0, digit_right - digit_left) * x_fraction)
            y = round(top + max(0, region_height - 1) * y_fraction)
            pixel = pixels[y * width + min(right, max(left, x))]
            bits.append("1" if pixel[3] > 0 and sum(pixel[:3]) > threshold else "0")
        patterns.append("".join(bits))
    return patterns


def compute_final_qa(
    png_bytes: bytes,
    endpoint_png_bytes: Mapping[str, bytes],
    dimensions: list[object],
    machine_contract: Mapping[str, object],
    scene_contract: Mapping[str, object],
    *,
    material_library_sha256: str,
    scene_contract_sha256: str,
    machine_contract_sha256: str,
) -> dict[str, object]:
    """Derive final QA only from original pixels and current validated contracts."""

    machine_errors = validate_machine_contract(machine_contract)
    if machine_errors:
        raise ValueError("final machine contract is invalid: " + "; ".join(machine_errors))
    animation = _mapping(machine_contract.get("animation"), "machine animation contract")
    controller = _mapping(machine_contract.get("controller"), "machine controller contract")
    if (
        animation.get("status") != "blocked_pending_owner_motion_map"
        or scene_contract.get("animation_contract") is not None
    ):
        raise ValueError("final animation QA requires a supported owner-approved endpoint contract")
    if set(endpoint_png_bytes) != {"start", "end"}:
        raise ValueError("final animation QA requires exact start and end endpoint renders")
    width, _, pixels = _decode_rgba_pixels(png_bytes, dimensions, "final product")
    main = _rgba_pixel_evidence(png_bytes, dimensions, "final product")
    left, top, right, bottom = main["subject_bounds"]
    if right - left + 1 < 4:
        raise ValueError("final product is too narrow for dedicated material/controller regions")
    split = left + max(1, ((right - left + 1) * 2) // 3)
    material = _region_pixel_evidence(
        pixels, width, [left, top, split - 1, bottom], "material"
    )
    controller_pixels = _region_pixel_evidence(
        pixels, width, [split, top, right, bottom], "controller"
    )
    if material["unique_rgb_values"] < 2 or controller_pixels["unique_rgb_values"] < 2:
        raise ValueError("final material/controller evidence cannot be a uniform whole frame")
    display_values = controller.get("display_values")
    assert isinstance(display_values, list)
    digit_count = sum(len(str(value)) for value in display_values)
    patterns = _controller_digit_patterns(
        pixels, width, list(controller_pixels["region"]), digit_count
    )
    endpoints: list[dict[str, object]] = []
    for label in ("start", "end"):
        evidence = _rgba_pixel_evidence(
            endpoint_png_bytes[label], dimensions, f"final animation {label} endpoint"
        )
        endpoints.append({
            "label": label,
            "file_sha256": hashlib.sha256(endpoint_png_bytes[label]).hexdigest().upper(),
            "rgba_sha256": evidence["rgba_sha256"],
            "product_mask_sha256": evidence["product_mask_sha256"],
            "subject_bounds": evidence["subject_bounds"],
            "visible_pixels": evidence["visible_pixels"],
            "visible_fraction": evidence["visible_fraction"],
        })
    if any(
        endpoint["rgba_sha256"] != main["rgba_sha256"]
        or endpoint["product_mask_sha256"] != main["product_mask_sha256"]
        or endpoint["subject_bounds"] != main["subject_bounds"]
        for endpoint in endpoints
    ):
        raise ValueError("static animation endpoint parity drift from final product pixels")
    return {
        "schema": "pimm-final-qa/v1",
        "dimensions": list(dimensions),
        "product": {
            "rgba_sha256": main["rgba_sha256"],
            "product_mask_sha256": main["product_mask_sha256"],
            "subject_bounds": main["subject_bounds"],
            "visible_pixels": main["visible_pixels"],
            "visible_fraction": main["visible_fraction"],
        },
        "material": {
            "material_library_sha256": _sha(material_library_sha256, "material library SHA-256"),
            "scene_contract_sha256": _sha(scene_contract_sha256, "scene contract SHA-256"),
            **material,
        },
        "alpha": {
            "channel_sha256": main["alpha_sha256"],
            "minimum": main["alpha_minimum"],
            "maximum": main["alpha_maximum"],
            "nonzero_pixels": main["alpha_nonzero_pixels"],
            "partial_pixels": main["alpha_partial_pixels"],
        },
        "controller": {
            "machine_contract_sha256": _sha(machine_contract_sha256, "machine contract SHA-256"),
            "controller_contract_sha256": canonical_json_sha256(controller),
            **controller_pixels,
            "digit_patterns": patterns,
            "active_segment_count": sum(pattern.count("1") for pattern in patterns),
            "segment_mask_sha256": hashlib.sha256(
                "".join(patterns).encode("ascii")
            ).hexdigest().upper(),
        },
        "animation": {
            "contract_sha256": canonical_json_sha256({
                "machine": animation,
                "scene": scene_contract.get("animation_contract"),
            }),
            "status": animation["status"],
            "endpoints": endpoints,
            "identical": True,
        },
    }


def _proof_output_records(
    proof_path: Path,
    proof: Mapping[str, object],
    metadata: Mapping[str, object],
    scene: SceneContract,
) -> tuple[dict[str, str], list[tuple[str, Path]]]:
    outputs = proof.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("proof manifest must contain output evidence")
    regions = metadata.get("named_shaft_regions")
    region_mapping = regions if isinstance(regions, Mapping) else {}
    hashes: dict[str, str] = {}
    paths: list[tuple[str, Path]] = []
    backgrounds: set[str] = set()
    for raw in outputs:
        entry = _mapping(raw, "proof output")
        relative = _canonical_component(entry.get("path"), "proof output path")
        shot_id = entry.get("shot_id")
        background = entry.get("background")
        if shot_id != scene.scene_id or not isinstance(background, str):
            raise ValueError("proof output shot/background identity is invalid")
        expected_name = f"{scene.scene_id}--{background}.png"
        if relative != expected_name or background in backgrounds:
            raise ValueError("proof output path must be a unique canonical shot/background filename")
        backgrounds.add(background)
        path = proof_path.parent / relative
        recomputed = proof_output_entry(path, scene.scene_id, background, region_mapping)
        if dict(entry) != recomputed:
            raise ValueError(f"proof output declaration drift: {relative}")
        hashes[relative] = _sha(entry.get("sha256"), f"proof output {relative} SHA-256")
        paths.append((background, path))
    return dict(sorted(hashes.items())), paths


def _validate_proof_qa(
    proof: Mapping[str, object], contract: ProofContract, metadata: Mapping[str, object]
) -> None:
    """Recompute the Task 5 manifest QA object from current pixel declarations."""

    raw_outputs = proof.get("outputs")
    assert isinstance(raw_outputs, list)
    entries = [_mapping(item, "proof output") for item in raw_outputs]
    by_background = {str(entry["background"]): entry for entry in entries}
    expected_backgrounds = {"rgba", *contract.backgrounds}
    if contract.object_masks:
        expected_backgrounds.update({"object-mask", "material-mask", "shadow-mask"})
    if set(by_background) != expected_backgrounds:
        raise ValueError("proof output shot family is incomplete or contains extras")
    shadow = by_background.get("shadow-mask")
    rgba_metrics = _mapping(by_background["rgba"].get("metrics"), "proof RGBA metrics")
    fallback_subject = {
        "bounds": rgba_metrics.get("subject_bounds"),
        "nonzero_fraction": rgba_metrics.get("subject_pixel_fraction"),
    }
    intended_subject = (
        _mapping(by_background["object-mask"].get("metrics"), "proof object-mask metrics")
        if "object-mask" in by_background
        else metadata.get("intended_subject_metrics") or fallback_subject
    )
    physical_shadow = (
        _mapping(shadow.get("metrics"), "proof shadow metrics")
        if shadow is not None
        else metadata.get("physical_shadow_metrics")
        or {"bounds": None, "nonzero_fraction": 0.0}
    )
    recomputed = {
        "subject": rgba_metrics,
        "intended_subject": intended_subject,
        "physical_shadow_extent": physical_shadow,
        "backgrounds": {
            name: _mapping(by_background[name].get("metrics"), f"proof {name} metrics")
            for name in contract.backgrounds
        },
        "material_masks": {
            name: _mapping(by_background[name].get("metrics"), f"proof {name} metrics")
            for name in ("object-mask", "material-mask")
            if name in by_background
        },
        "named_shaft_reflection": {
            name: _mapping(by_background[name].get("metrics"), f"proof {name} metrics").get(
                "named_shaft_reflection"
            )
            for name in contract.backgrounds
        },
    }
    if proof.get("qa") != recomputed:
        raise ValueError("proof manifest QA does not match current Task 5 pixel evidence")


def extract_current_approval_evidence(proof_manifest_path: Path) -> dict[str, object]:
    """Validate a genuine Task 5 proof and recompute every current authority."""

    raw_path = canonical_absolute_path(str(Path(proof_manifest_path)), "proof manifest path")
    if len(raw_path.parents) < 4:
        raise ValueError("proof manifest path is outside the canonical proof tree")
    asset_root = raw_path.parents[3]
    proof, _ = stable_json(raw_path, asset_root, "asset", "proof manifest")
    if set(proof) != _PROOF_FIELDS:
        raise ValueError("proof manifest fields do not match genuine Task 5 evidence")
    generation = proof.get("generation_id")
    if not isinstance(generation, str) or _GENERATION_ID.fullmatch(generation) is None:
        raise ValueError("proof manifest generation ID is invalid")
    expected_manifest = asset_root / "renders" / "proofs" / generation / "manifest.json"
    if raw_path != expected_manifest:
        raise ValueError("proof manifest path is outside the canonical proof tree")
    if proof.get("schema") != "pimm-proof-manifest/v1" or proof.get("status") != "pass":
        raise ValueError("proof manifest must be a passing pimm-proof-manifest/v1")
    contract = ProofContract.from_mapping(_mapping(proof.get("contract"), "proof contract"))
    if contract.generation_id != generation:
        raise ValueError("proof manifest generation drifted from proof contract")
    proof_snapshot = raw_path.parent / "proof-contract.json"
    scene_snapshot = raw_path.parent / "scene-contract.json"
    tool_snapshot = raw_path.parent / "tool-lock.json"
    metadata_path = raw_path.parent / "render-metadata.json"
    scene_payload, _ = stable_json(scene_snapshot, asset_root, "asset", "scene contract snapshot")
    scene = SceneContract.from_mapping(scene_payload)
    contract_errors = [
        error
        for error in validate_proof_contract(contract, scene)
        if "proof generation ID is already in use" not in error
        and "proof scene contract is missing" not in error
    ]
    if contract_errors:
        raise ValueError("proof contract validation failed: " + "; ".join(contract_errors))
    if (
        proof.get("stage") != contract.stage
        or proof.get("samples") != contract.samples
        or proof.get("resolution_percentage") != contract.resolution_percentage
        or proof.get("denoise") is not contract.denoise
        or proof.get("fingerprints_unchanged") is not True
    ):
        raise ValueError("proof manifest contract settings drift")
    if proof.get("scene_sha256") != contract.scene_sha256.upper():
        raise ValueError("proof manifest scene SHA-256 drift")
    if proof.get("master_sha256") != contract.master_sha256.upper():
        raise ValueError("proof manifest master SHA-256 drift")
    if proof.get("material_library_sha256") != contract.material_library_sha256.upper():
        raise ValueError("proof manifest material-library SHA-256 drift")
    metadata = _validate_render_metadata(
        proof.get("render"), contract, scene,
        output_root=raw_path.parent,
        scene_contract_path=scene_snapshot,
    )
    output_hashes, output_paths = _proof_output_records(raw_path, proof, metadata, scene)
    _validate_proof_qa(proof, contract, metadata)
    contact = raw_path.parent / "contact-sheet.png"
    contact_record, contact_bytes = _stable_file(
        str(contact), str(asset_root), "asset", "contact sheet", capture=True
    )
    try:
        with Image.open(io.BytesIO(contact_bytes or b"")) as image:
            image.load()
            if image.width <= 0 or image.height <= 0:
                raise ValueError("contact sheet has invalid dimensions")
    except OSError as error:
        raise ValueError(f"contact sheet is not genuine image evidence: {error}") from error

    render = _mapping(proof.get("render"), "proof render metadata")
    fingerprints = _mapping(render.get("fingerprints"), "proof fingerprints")
    before = _mapping(fingerprints.get("before"), "proof before fingerprints")
    blender = _mapping(render.get("blender"), "proof Blender identity")
    blender_binary = canonical_absolute_path(blender.get("binary_path"), "Blender binary path")
    roots = _authority_roots(asset_root, blender_binary)
    root_paths = _validate_roots(roots)
    repository = root_paths["repository"]
    evidence: dict[str, dict[str, object]] = {}
    for name in ("source", "master", "material_library", "scene"):
        fingerprint = _mapping(before.get(name), f"proof {name} fingerprint")
        path = canonical_absolute_path(fingerprint.get("path"), f"proof {name} path")
        record = stable_file_record(path, asset_root, "asset", name)
        if (
            record["sha256"] != _sha(fingerprint.get("sha256"), f"proof {name} SHA-256")
            or record["bytes"] != fingerprint.get("bytes")
            or record["mtime_ns"] != fingerprint.get("mtime_ns")
        ):
            raise ValueError(f"proof {name} current evidence drift")
        evidence[name] = record
    static_paths = {
        "proof_contract": proof_snapshot,
        "scene_contract": asset_root / Path(*PurePosixPath(contract.scene_contract_path).parts),
        "scene_contract_snapshot": scene_snapshot,
        "tool_lock": tool_snapshot,
        "render_metadata": metadata_path,
        "proof_manifest": raw_path,
        "proof_runner": repository / "scripts" / "blender" / "pimm_production" / "blender_proof_render.py",
        "final_runner": repository / "scripts" / "blender" / "pimm_production" / "blender_final_render.py",
        "blender_binary": blender_binary,
        "machine_contract": repository / "scripts" / "blender" / "pimm_production"
        / "contracts" / "machines" / ("30g.json" if scene.scene_id.startswith("pimm-30g") else "50g.json"),
    }
    for name, path in static_paths.items():
        authority = _BASE_EVIDENCE_AUTHORITIES[name]
        evidence[name] = stable_file_record(path, root_paths[authority], authority, name)
    if evidence["scene_contract"]["sha256"] != evidence["scene_contract_snapshot"]["sha256"]:
        raise ValueError("current scene contract drifted from immutable proof snapshot")
    machine_payload, _ = stable_json(
        Path(str(evidence["machine_contract"]["path"])),
        repository,
        "repository",
        "machine contract",
        evidence["machine_contract"],
    )
    machine_errors = validate_machine_contract(machine_payload)
    expected_machine = "30G" if scene.scene_id.startswith("pimm-30g") else "50G"
    if machine_errors or machine_payload.get("machine") != expected_machine:
        raise ValueError(
            "current machine contract is invalid: "
            + "; ".join(machine_errors or ["machine identity drift"])
        )
    evidence["contact_sheet"] = contact_record
    for background, path in output_paths:
        key = f"proof_pixel_{background.replace('-', '_')}"
        if key in evidence:
            raise ValueError("proof pixels contain duplicate evidence identities")
        evidence[key] = stable_file_record(path, asset_root, "asset", key)
    for name, record in evidence.items():
        authority = str(record["authority"])
        stable_file_record(Path(str(record["path"])), root_paths[authority], authority, name, record)

    inputs = {
        "source_sha256": str(evidence["source"]["sha256"]),
        "master_sha256": str(evidence["master"]["sha256"]),
        "material_library_sha256": str(evidence["material_library"]["sha256"]),
        "scene_sha256": str(evidence["scene"]["sha256"]),
        "proof_manifest_sha256": str(evidence["proof_manifest"]["sha256"]),
        "proof_contract_sha256": str(evidence["proof_contract"]["sha256"]),
        "contact_sheet_sha256": str(evidence["contact_sheet"]["sha256"]),
        "tool_lock_sha256": str(evidence["tool_lock"]["sha256"]),
        "proof_runner_sha256": str(evidence["proof_runner"]["sha256"]),
        "final_runner_sha256": str(evidence["final_runner"]["sha256"]),
        "machine_contract_sha256": str(evidence["machine_contract"]["sha256"]),
    }
    return {
        "authority_roots": roots,
        "evidence": dict(sorted(evidence.items())),
        "inputs": inputs,
        "render_settings": _state_from_proof(proof, scene, metadata),
        "generation_id": generation,
        "shot_id": scene.scene_id,
        "proof_output_sha256": output_hashes,
    }


def validate_evidence_records(
    authority_roots: object, evidence_value: object
) -> tuple[dict[str, Path], dict[str, dict[str, object]]]:
    """Rehash final-contract evidence independently from approval values."""

    roots = _validate_roots(authority_roots)
    evidence = _mapping(evidence_value, "final evidence")
    required = set(_BASE_EVIDENCE_AUTHORITIES)
    pixel_keys = {str(key) for key in evidence if str(key).startswith("proof_pixel_")}
    if set(evidence) != required | pixel_keys or not pixel_keys:
        raise ValueError("final evidence must contain every protected artifact and proof pixel")
    current: dict[str, dict[str, object]] = {}
    physical: set[str] = set()
    for raw_name, raw_record in evidence.items():
        name = str(raw_name)
        _canonical_component(name, "evidence ID")
        record = _mapping(raw_record, f"{name} evidence")
        if set(record) != _FILE_RECORD_FIELDS:
            raise ValueError(f"{name} evidence fields are invalid")
        authority = record.get("authority")
        if authority not in roots:
            raise ValueError(f"{name} evidence authority is invalid")
        expected_authority = (
            "asset" if name.startswith("proof_pixel_") else _BASE_EVIDENCE_AUTHORITIES.get(name)
        )
        if authority != expected_authority:
            raise ValueError(f"{name} evidence authority drift")
        refreshed = stable_file_record(
            Path(str(record.get("path"))), roots[str(authority)], str(authority), name, record
        )
        identity = ntpath.normcase(str(refreshed["path"]))
        if identity in physical:
            raise ValueError("evidence contains duplicate physical paths")
        physical.add(identity)
        current[name] = refreshed
    return roots, current


def validate_approval_payload(
    payload: Mapping[str, object], current_inputs: Mapping[str, str]
) -> list[str]:
    """Return fail-closed approval schema and independently supplied drift errors."""

    errors: list[str] = []
    if set(payload) != _APPROVAL_FIELDS:
        errors.append("approval schema fields are incomplete or contain unknown values")
    if payload.get("schema") != _APPROVAL_SCHEMA or payload.get("schema_version") != 1:
        errors.append("approval schema must be pimm-owner-approval/v1 version 1")
    if payload.get("decision") not in _DECISIONS:
        errors.append("approval decision must be approved or rejected")
    if not isinstance(payload.get("owner"), str) or not str(payload.get("owner")).strip():
        errors.append("approval owner is required")
    if not isinstance(payload.get("notes"), str) or not str(payload.get("notes")).strip():
        errors.append("approval notes are required")
    try:
        _validate_created_at_utc(payload.get("created_at_utc"))
    except ValueError as error:
        errors.append(str(error))
    if (
        not isinstance(payload.get("revision"), int)
        or isinstance(payload.get("revision"), bool)
        or int(payload.get("revision", 0)) <= 0
    ):
        errors.append("approval revision must be positive")
    inputs = payload.get("inputs")
    if not isinstance(inputs, Mapping):
        return errors + ["approval inputs are required"]
    labels = {
        "source_sha256": "source SHA-256",
        "master_sha256": "master SHA-256",
        "material_library_sha256": "material library SHA-256",
        "scene_sha256": "scene SHA-256",
        "proof_manifest_sha256": "proof manifest SHA-256",
        "proof_contract_sha256": "proof contract SHA-256",
        "contact_sheet_sha256": "contact sheet SHA-256",
        "tool_lock_sha256": "tool lock SHA-256",
        "proof_runner_sha256": "proof runner SHA-256",
        "final_runner_sha256": "final runner SHA-256",
        "machine_contract_sha256": "machine contract SHA-256",
    }
    for key, label in labels.items():
        expected = inputs.get(key)
        if not isinstance(expected, str) or _SHA256.fullmatch(expected) is None:
            errors.append(f"approval {label} is invalid")
        actual = current_inputs.get(key)
        if actual is not None and isinstance(expected, str) and actual.upper() != expected.upper():
            errors.append(f"{label} drift")
    return errors


def _load_approval(path: Path) -> tuple[Mapping[str, object], dict[str, Path]]:
    absolute = canonical_absolute_path(str(path), "approval path")
    drive_root = Path(absolute.anchor)
    payload, _ = stable_json(absolute, drive_root, "asset", "approval")
    roots = _validate_roots(payload.get("authority_roots"))
    _lexically_within(absolute, roots["asset"], "approval")
    stable_json(absolute, roots["asset"], "asset", "approval")
    return payload, roots


def validate_approval(
    approval_path: Path, current_inputs: Mapping[str, str]
) -> list[str]:
    """Validate an approval by recomputing genuine proof evidence from disk."""

    try:
        payload, _ = _load_approval(Path(approval_path))
    except (OSError, ValueError) as error:
        return [f"approval cannot be read: {error}"]
    errors = validate_approval_payload(payload, {})
    try:
        current = extract_current_approval_evidence(Path(str(payload.get("proof_manifest_path"))))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        if "proof output" in str(error):
            return errors + [f"proof pixel SHA-256 drift: {error}"]
        return errors + [f"proof evidence cannot be read: {error}"]
    for field in (
        "authority_roots", "evidence", "inputs", "render_settings",
        "generation_id", "shot_id", "proof_output_sha256",
    ):
        approval_field = {"generation_id": "proof_generation_id"}.get(field, field)
        if payload.get(approval_field) != current.get(field):
            errors.append(f"approval {field.replace('_', ' ')} drift")
    actual_inputs = _mapping(current.get("inputs"), "current inputs")
    for key, supplied in current_inputs.items():
        actual = actual_inputs.get(key)
        if actual is None or not isinstance(supplied, str) or supplied.upper() != actual:
            errors.append(f"{key.replace('_', ' ')} drift")
    return errors


def _revision_entries(approval_dir: Path) -> list[Path]:
    entries: list[tuple[int, Path]] = []
    for path in approval_dir.iterdir():
        match = _REVISION_NAME.fullmatch(path.name)
        if match:
            entries.append((int(match.group(1)), path))
    entries.sort(key=lambda pair: pair[0])
    if [revision for revision, _ in entries] != list(range(1, len(entries) + 1)):
        raise ValueError("approval revision chain is broken")
    return [path for _, path in entries]


def record_decision(
    proof_manifest: Path,
    shot_id: str,
    decision: str,
    owner: str,
    notes: str,
) -> Path:
    """Append one immutable, current-evidence-bound owner decision revision."""

    if decision not in _DECISIONS:
        raise ValueError("decision must be approved or rejected")
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("owner is required")
    if not isinstance(notes, str) or not notes.strip():
        raise ValueError("notes are required")
    if not isinstance(shot_id, str) or _SHOT_ID.fullmatch(shot_id) is None:
        raise ValueError("shot_id is not canonical")
    current = extract_current_approval_evidence(Path(proof_manifest))
    if current["shot_id"] != shot_id:
        raise ValueError("shot_id is not present in proof manifest outputs")
    roots = _validate_roots(current["authority_roots"])
    proof_path = canonical_absolute_path(str(Path(proof_manifest)), "proof manifest path")
    approval_dir = proof_path.parent / "approvals" / _canonical_component(shot_id, "shot_id")
    _lexically_within(approval_dir, roots["asset"], "approval directory")
    _reject_reparse_ancestors(approval_dir.parent, "approval directory")
    with approval_head_lock(approval_dir):
        # The first pass locates the canonical approval directory. Recompute all
        # current proof authority while holding its chain-head lock so a stale
        # pre-lock snapshot can never become a decision revision.
        current = extract_current_approval_evidence(proof_path)
        if current["shot_id"] != shot_id or _validate_roots(current["authority_roots"]) != roots:
            raise ValueError("proof authority drifted before approval publication")
        existing = _revision_entries(approval_dir)
        revision = len(existing) + 1
        destination = approval_dir / f"approval-r{revision:02d}.json"
        prior = None
        prior_path = None
        if existing:
            prior_record = stable_file_record(
                existing[-1], roots["asset"], "asset", "prior approval"
            )
            prior = prior_record["sha256"]
            prior_path = str(existing[-1])
        payload: dict[str, object] = {
            "schema": _APPROVAL_SCHEMA,
            "schema_version": 1,
            "revision": revision,
            "prior_approval_sha256": prior,
            "prior_approval_path": prior_path,
            "decision": decision,
            "owner": owner.strip(),
            "notes": notes.strip(),
            "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "shot_id": shot_id,
            "proof_manifest_path": str(proof_path),
            "proof_generation_id": current["generation_id"],
            "authority_roots": current["authority_roots"],
            "evidence": current["evidence"],
            "inputs": current["inputs"],
            "render_settings": current["render_settings"],
            "proof_output_sha256": current["proof_output_sha256"],
        }
        created = _create_new_json(destination, payload)
        published, record = stable_json(destination, roots["asset"], "asset", "new approval")
        if published != payload or any(record[key] != value for key, value in created.items()):
            raise ValueError("new approval publication identity or payload drift")
    return destination


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    record = subparsers.add_parser("record")
    record.add_argument("--proof-manifest", type=Path, required=True)
    record.add_argument("--shot-id", required=True)
    record.add_argument("--decision", choices=sorted(_DECISIONS), required=True)
    record.add_argument("--owner", required=True)
    record.add_argument("--notes", required=True)
    arguments = parser.parse_args()
    if arguments.command == "record":
        print(record_decision(
            arguments.proof_manifest, arguments.shot_id, arguments.decision,
            arguments.owner, arguments.notes,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
