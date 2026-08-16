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

from scripts.blender.master_assets.pimm_material_library import MATERIAL_SPECS

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
_MATERIAL_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
_APPROVED_SHARED_MATERIAL_IDS = frozenset(MATERIAL_SPECS) - {"UNASSIGNED"}
_SEGMENT_LABELS = ("a", "b", "c", "d", "e", "f", "g")
_DIGIT_SEGMENTS = {
    "0": "1110111",
    "1": "0010010",
    "2": "1011101",
    "3": "1011011",
    "4": "0111010",
    "5": "1101011",
    "6": "1101111",
    "7": "1010010",
    "8": "1111111",
    "9": "1111011",
}


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


@contextlib.contextmanager
def held_evidence_authority(
    authority_roots: object,
    evidence_value: object,
    *,
    names: tuple[str, ...] = ("source", "master", "material_library", "scene"),
) -> Iterator[tuple[dict[str, Path], dict[str, dict[str, object]]]]:
    """Hold approval-bound inputs against write/delete races for one operation.

    Blender opens linked libraries after its process starts.  A closed-handle
    preflight hash therefore cannot prove which bytes Blender actually loaded.
    On Windows, read handles whose share mode is FILE_SHARE_READ deny both
    writes and path replacement until every protected consumer has exited.
    """

    roots, current = validate_evidence_records(authority_roots, evidence_value)
    missing = set(names) - set(current)
    if missing:
        raise ValueError(
            "held evidence authority is missing: " + ", ".join(sorted(missing))
        )
    if os.name != "nt":
        raise ValueError(
            "held evidence authority requires Windows deny-write/delete handles"
        )

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    )
    create_file.restype = ctypes.c_void_p
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (ctypes.c_void_p,)
    close_handle.restype = ctypes.c_int
    generic_read = 0x80000000
    file_share_read = 0x00000001
    open_existing = 3
    file_attribute_normal = 0x00000080
    invalid_handle = ctypes.c_void_p(-1).value
    handles: list[int] = []
    try:
        for name in names:
            record = current[name]
            handle = create_file(
                str(record["path"]),
                generic_read,
                file_share_read,
                None,
                open_existing,
                file_attribute_normal,
                None,
            )
            if handle in (None, invalid_handle):
                error = ctypes.get_last_error()
                raise OSError(
                    error,
                    f"cannot hold {name} evidence authority",
                    str(record["path"]),
                )
            handles.append(int(handle))

        # Close the acquisition race only after every path is protected.  The
        # evidence record includes NTFS ChangeTime, so mutate-and-restore also
        # fails even when bytes and mtime are restored.
        for name in names:
            record = current[name]
            stable_file_record(
                Path(str(record["path"])),
                roots[str(record["authority"])],
                str(record["authority"]),
                f"held {name} evidence",
                record,
            )
        yield roots, current
        for name in names:
            record = current[name]
            stable_file_record(
                Path(str(record["path"])),
                roots[str(record["authority"])],
                str(record["authority"]),
                f"held {name} evidence",
                record,
            )
    except PermissionError as error:
        raise ValueError(
            "evidence drift or held-authority write/delete race"
        ) from error
    finally:
        for handle in reversed(handles):
            close_handle(ctypes.c_void_p(handle))


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


def _machine_contract_path(repository: Path, scene: SceneContract) -> Path:
    """Return the one checked-in machine contract selected by approved scene identity."""

    filename = "30g.json" if scene.scene_id.startswith("pimm-30g") else "50g.json"
    return repository / "scripts" / "blender" / "pimm_production" / "contracts" / "machines" / filename


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
        "dependency_sha256": _sha(
            current.get("dependency_sha256"), "proof authored dependency SHA-256"
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


def _identity_sha256(value: object, label: str) -> str:
    identity = _mapping(value, label)
    if not isinstance(identity.get("name"), str) or not str(identity["name"]):
        raise ValueError(f"{label} name is required")
    return canonical_json_sha256(identity)


def _exact_material_id(identity: Mapping[str, object], label: str) -> str:
    """Return one explicit canonical material ID without name/stable-ID fallback."""

    material_id = identity.get("pimm_material_id")
    if (
        not isinstance(material_id, str)
        or not material_id
        or material_id != material_id.strip()
        or _MATERIAL_ID.fullmatch(material_id) is None
    ):
        raise ValueError(f"{label} requires one exact nonempty pimm_material_id")
    return material_id


def _material_registry(
    authored_settings: Mapping[str, object],
) -> tuple[dict[str, Mapping[str, object]], dict[str, str]]:
    raw_materials = authored_settings.get("materials")
    if not isinstance(raw_materials, list):
        raise ValueError("approved authored settings materials must be a list")
    identities: dict[str, Mapping[str, object]] = {}
    identifiers: dict[str, str] = {}
    for index, raw_material in enumerate(raw_materials):
        material = _mapping(raw_material, f"approved authored material {index}")
        identity = _mapping(
            material.get("identity"), f"approved authored material {index} identity"
        )
        if identity.get("type") != "Material":
            raise ValueError("approved authored material identity type must equal Material")
        material_id = _exact_material_id(
            identity, f"approved authored material {index} identity"
        )
        if material_id == "UNASSIGNED":
            raise ValueError("approved pimm_material_id cannot equal UNASSIGNED")
        identity_key = canonical_json_sha256(identity)
        if identity_key in identities:
            raise ValueError("approved material datablock identities must be unique")
        prior = identifiers.setdefault(material_id, identity_key)
        if prior != identity_key:
            raise ValueError("approved pimm_material_id values must be unique per datablock")
        identities[identity_key] = identity
    return identities, identifiers


def _material_ids_from_object(
    obj: Mapping[str, object],
    material_registry: Mapping[str, Mapping[str, object]],
) -> tuple[list[str], list[str]]:
    slots = obj.get("material_slots")
    if not isinstance(slots, list):
        raise ValueError("approved component object material_slots must be a list")
    identifiers: list[str] = []
    identities: list[str] = []
    for raw_slot in slots:
        slot = _mapping(raw_slot, "approved component material slot")
        raw_material = slot.get("material")
        if raw_material is None:
            continue
        material = _mapping(raw_material, "approved component material identity")
        if material.get("type") != "Material":
            raise ValueError("approved component material identity type must equal Material")
        material_id = _exact_material_id(
            material, "approved component material identity"
        )
        identity_hash = canonical_json_sha256(material)
        if identity_hash not in material_registry:
            raise ValueError(
                "approved component material identity does not match Task 5 captured material evidence"
            )
        identifiers.append(material_id)
        identities.append(identity_hash)
    return sorted(set(identifiers)), sorted(set(identities))


def build_component_contract(
    machine_contract: Mapping[str, object], authored_settings: Mapping[str, object]
) -> dict[str, object]:
    """Bind approved scene identities to exact material and physical segment roles."""

    errors = validate_machine_contract(machine_contract)
    if errors:
        raise ValueError("component machine contract is invalid: " + "; ".join(errors))
    machine = machine_contract.get("machine")
    controller = _mapping(machine_contract.get("controller"), "component controller contract")
    values = controller.get("display_values")
    if not isinstance(values, list) or not values or any(
        not isinstance(value, str) or not value or any(digit not in _DIGIT_SEGMENTS for digit in value)
        for value in values
    ):
        raise ValueError("component controller display values must contain decimal digit strings")
    expected_patterns = [_DIGIT_SEGMENTS[digit] for value in values for digit in value]
    raw_segments = controller.get("approved_segments")
    expected_count = len(expected_patterns) * len(_SEGMENT_LABELS)
    if not isinstance(raw_segments, list) or len(raw_segments) != expected_count:
        raise ValueError(
            f"approved physical controller segment map requires exactly {expected_count} identities"
        )
    machine_local = set(controller.get("approved_machine_local_material_ids", []))

    raw_objects = authored_settings.get("objects")
    if not isinstance(raw_objects, list):
        raise ValueError("approved authored settings objects must be a list")
    material_registry, _ = _material_registry(authored_settings)
    for identity in material_registry.values():
        material_id = _exact_material_id(identity, "approved material identity")
        if material_id in machine_local:
            continue
        if material_id not in _APPROVED_SHARED_MATERIAL_IDS:
            raise ValueError(
                "approved shared pimm_material_id is outside the canonical material catalog"
            )
        if identity.get("name") != f"PIMM_{material_id}":
            raise ValueError(
                "approved shared pimm_material_id does not match its canonical material "
                f"datablock name: {identity.get('name')!r} != 'PIMM_{material_id}'"
            )
    objects: dict[str, Mapping[str, object]] = {}
    for raw_object in raw_objects:
        obj = _mapping(raw_object, "approved authored object")
        identity = _mapping(obj.get("identity"), "approved authored object identity")
        stable_id = identity.get("pimm_stable_id")
        if stable_id is None:
            continue
        if not isinstance(stable_id, str) or not stable_id.strip() or stable_id in objects:
            raise ValueError("approved authored component stable object identities must be unique")
        objects[stable_id] = obj

    segment_ids: set[str] = set()
    segments: list[dict[str, object]] = []
    for ordinal, raw_segment in enumerate(raw_segments):
        segment = _mapping(raw_segment, f"approved controller segment {ordinal}")
        digit_index, label_index = divmod(ordinal, len(_SEGMENT_LABELS))
        expected_active = expected_patterns[digit_index][label_index] == "1"
        stable_id = segment.get("stable_object_id")
        if not isinstance(stable_id, str) or stable_id in segment_ids:
            raise ValueError("approved physical controller segment identities must be unique")
        if segment.get("active") is not expected_active:
            raise ValueError("approved controller segment state does not encode exact display values")
        obj = objects.get(stable_id)
        if obj is None:
            raise ValueError(f"approved controller segment object is absent from scene: {stable_id}")
        if obj.get("object_type") != "MESH" or obj.get("hide_render") is not False:
            raise ValueError(f"approved controller segment is not a visible physical MESH: {stable_id}")
        material_ids, material_identity_hashes = _material_ids_from_object(
            obj, material_registry
        )
        if segment.get("material_id") not in material_ids:
            raise ValueError(f"approved controller segment material mismatch: {stable_id}")
        object_identity = _mapping(obj.get("identity"), "approved segment object identity")
        segments.append(
            {
                "ordinal": ordinal,
                "digit_index": digit_index,
                "segment": _SEGMENT_LABELS[label_index],
                "stable_object_id": stable_id,
                "material_id": segment["material_id"],
                "expected_active": expected_active,
                "object_identity_sha256": _identity_sha256(
                    object_identity, "approved segment object identity"
                ),
                "material_identity_sha256": canonical_json_sha256(material_identity_hashes),
            }
        )
        segment_ids.add(stable_id)

    material_objects: list[dict[str, object]] = []
    for stable_id, obj in sorted(objects.items()):
        if stable_id in segment_ids or obj.get("object_type") != "MESH" or obj.get("hide_render") is not False:
            continue
        material_ids, material_identity_hashes = _material_ids_from_object(
            obj, material_registry
        )
        if not material_ids:
            raise ValueError(
                f"approved visible MESH requires an exact material identity: {stable_id}"
            )
        approved_material_ids = [
            material_id
            for material_id in material_ids
            if material_id not in machine_local
            and material_id.casefold().removeprefix("pimm_") != "unassigned"
        ]
        if not approved_material_ids:
            continue
        identity = _mapping(obj.get("identity"), "approved material object identity")
        material_objects.append(
            {
                "stable_object_id": stable_id,
                "object_identity_sha256": _identity_sha256(
                    identity, "approved material object identity"
                ),
                "material_ids": approved_material_ids,
                "material_identity_sha256": canonical_json_sha256(material_identity_hashes),
            }
        )
    if not material_objects:
        raise ValueError("approved scene has no exact assigned material-bearing object identities")

    payload: dict[str, object] = {
        "schema": "pimm-final-component-contract/v1",
        "machine": machine,
        "display_values": list(values),
        "expected_digit_patterns": expected_patterns,
        "material_objects": material_objects,
        "segments": segments,
    }
    payload["sha256"] = canonical_json_sha256(payload)
    return payload


def _identity_mapping(value: Mapping[str, object]) -> Mapping[str, object] | None:
    if not {"name", "type", "library"}.issubset(value):
        return None
    if not isinstance(value.get("name"), str) or not isinstance(value.get("type"), str):
        return None
    return value


def _validate_component_library_paths(
    authored_settings: Mapping[str, object],
    roots: Mapping[str, Path],
    evidence: Mapping[str, Mapping[str, object]],
    machine_local_material_ids: frozenset[str],
) -> None:
    """Resolve every captured Blender library to an existing approval authority."""

    allowed: dict[str, tuple[str, Path, Mapping[str, object]]] = {}
    authorities_by_name: dict[str, tuple[Path, Mapping[str, object]]] = {}
    for name in ("master", "material_library"):
        record = _mapping(evidence.get(name), f"{name} evidence")
        if set(record) != _FILE_RECORD_FIELDS or record.get("authority") != "asset":
            raise ValueError(f"{name} evidence is not an exact approval-bound file record")
        path = canonical_absolute_path(record.get("path"), f"{name} evidence path")
        refreshed = stable_file_record(
            path, roots["asset"], "asset", name.replace("_", " "), record
        )
        allowed[ntpath.normcase(str(path))] = (name, path, refreshed)
        authorities_by_name[name] = (path, refreshed)

    observed_authorities: set[str] = set()

    def visit(value: object, label: str) -> None:
        if isinstance(value, Mapping):
            identity = _identity_mapping(value)
            if identity is not None:
                material_id: str | None = None
                if identity.get("type") == "Material":
                    material_id = _exact_material_id(identity, label)
                library_value = identity.get("library")
                if material_id is not None and library_value is None:
                    expected_name = (
                        "master"
                        if material_id in machine_local_material_ids
                        else "material_library"
                    )
                    raise ValueError(
                        f"{label} material is local instead of resolving to its exact "
                        f"pinned {expected_name.replace('_', '-')} authority"
                    )
                if library_value is not None:
                    library_path = canonical_absolute_path(
                        library_value, f"{label} linked Blender library"
                    )
                    authority = allowed.get(ntpath.normcase(str(library_path)))
                    if authority is None or library_path != authority[1]:
                        raise ValueError(
                            f"{label} linked Blender library is not the exact pinned master "
                            "or material-library authority"
                        )
                    name, _, record = authority
                    if material_id is not None:
                        expected_name = (
                            "master"
                            if material_id in machine_local_material_ids
                            else "material_library"
                        )
                        if name != expected_name:
                            raise ValueError(
                                f"{label} material library role is outside its exact "
                                f"{expected_name.replace('_', '-')} authority"
                            )
                    stable_file_record(
                        library_path,
                        roots["asset"],
                        "asset",
                        f"approved component {name.replace('_', ' ')} library",
                        record,
                    )
                    observed_authorities.add(name)
                if identity.get("type") == "Image" and value.get("external_files"):
                    raise ValueError(
                        f"{label} external image bytes are not pinned master/material-library authority"
                    )
            for key, nested in value.items():
                visit(nested, f"{label}.{key}")
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                visit(nested, f"{label}[{index}]")

    visit(authored_settings, "approved component dependency")
    for name in observed_authorities:
        path, record = authorities_by_name[name]
        stable_file_record(
            path,
            roots["asset"],
            "asset",
            f"observed approved component {name.replace('_', ' ')} library",
            record,
        )


def build_authorized_component_contract(
    machine_contract: Mapping[str, object],
    authored_settings: Mapping[str, object],
    authority_roots: Mapping[str, object],
    evidence: Mapping[str, object],
) -> dict[str, object]:
    """Build the component contract only under pinned master/material authority."""

    roots = _validate_roots(
        {name: str(value) for name, value in authority_roots.items()}
    )
    contract = build_component_contract(machine_contract, authored_settings)
    controller = _mapping(
        machine_contract.get("controller"), "component controller contract"
    )
    _validate_component_library_paths(
        authored_settings,
        roots,
        {
            name: _mapping(evidence.get(name), f"{name} evidence")
            for name in ("master", "material_library")
        },
        frozenset(controller.get("approved_machine_local_material_ids", [])),
    )
    return contract


def _validated_component_contract(value: Mapping[str, object]) -> Mapping[str, object]:
    required = {
        "schema", "machine", "display_values", "expected_digit_patterns",
        "material_objects", "segments", "sha256",
    }
    if set(value) != required or value.get("schema") != "pimm-final-component-contract/v1":
        raise ValueError("final component contract fields are invalid")
    unsigned = {key: value[key] for key in required - {"sha256"}}
    if value.get("sha256") != canonical_json_sha256(unsigned):
        raise ValueError("final component contract identity hash drift")
    return value


def _decode_component_mask(
    data: bytes, dimensions: list[object], label: str
) -> tuple[list[int], dict[str, object]]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.format != "PNG" or list(image.size) != dimensions or image.mode not in {"L", "RGBA"}:
                raise ValueError(f"{label} must be an exact original-resolution PNG mask")
            channel = image if image.mode == "L" else image.getchannel("A")
            values = list(channel.get_flattened_data())
    except OSError as error:
        raise ValueError(f"{label} is not genuine PNG mask evidence: {error}") from error
    selected = [index for index, value in enumerate(values) if value > 0]
    if not selected:
        raise ValueError(f"{label} contains no component pixels")
    width = int(dimensions[0])
    xs = [index % width for index in selected]
    ys = [index // width for index in selected]
    return values, {
        "file_sha256": hashlib.sha256(data).hexdigest().upper(),
        "channel_sha256": hashlib.sha256(bytes(values)).hexdigest().upper(),
        "dimensions": list(dimensions),
        "nonzero_pixels": len(selected),
        "bounds": [min(xs), min(ys), max(xs), max(ys)],
        "centroid": [
            round(sum(xs) / len(xs), 8),
            round(sum(ys) / len(ys), 8),
        ],
    }


def _masked_pixel_evidence(
    pixels: list[tuple[int, int, int, int]], mask: list[int], label: str
) -> dict[str, object]:
    selected = [pixel for pixel, value in zip(pixels, mask) if value > 0]
    visible = [pixel for pixel in selected if pixel[3] > 0]
    if not visible:
        raise ValueError(f"{label} has no visible overlap with final product pixels")
    rgba = bytes(channel for pixel in selected for channel in pixel)
    visible_rgb = bytes(channel for pixel in visible for channel in pixel[:3])
    return {
        "masked_rgba_sha256": hashlib.sha256(rgba).hexdigest().upper(),
        "visible_rgb_sha256": hashlib.sha256(visible_rgb).hexdigest().upper(),
        "visible_overlap_pixels": len(visible),
        "unique_rgb_values": len({pixel[:3] for pixel in visible}),
        "mean_luma": round(sum(sum(pixel[:3]) / 3 for pixel in visible) / len(visible), 8),
    }


def _validate_segment_layout(records: list[dict[str, object]]) -> None:
    digit_centroids: list[float] = []
    for digit_index in range(len(records) // len(_SEGMENT_LABELS)):
        digit = records[
            digit_index * len(_SEGMENT_LABELS):(digit_index + 1) * len(_SEGMENT_LABELS)
        ]
        points = {
            str(record["segment"]): record["mask"]["centroid"] for record in digit
        }
        if set(points) != set(_SEGMENT_LABELS):
            raise ValueError("controller physical segment identity set is incomplete")
        a, b, c, d, e, f, g = (points[label] for label in _SEGMENT_LABELS)
        if not (
            a[1] < min(b[1], c[1])
            and max(b[1], c[1]) < d[1] < min(e[1], f[1])
            and max(e[1], f[1]) < g[1]
            and b[0] < c[0]
            and e[0] < f[0]
        ):
            raise ValueError("controller physical segment mask identity/layout is swapped")
        digit_centroids.append(sum(float(point[0]) for point in points.values()) / 7)
    if any(left >= right for left, right in zip(digit_centroids, digit_centroids[1:])):
        raise ValueError("controller physical digit mask order is swapped")


def compute_final_qa(
    png_bytes: bytes,
    endpoint_png_bytes: Mapping[str, bytes],
    dimensions: list[object],
    machine_contract: Mapping[str, object],
    scene_contract: Mapping[str, object],
    *,
    component_contract: Mapping[str, object],
    component_mask_bytes: Mapping[str, bytes],
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
    _, _, pixels = _decode_rgba_pixels(png_bytes, dimensions, "final product")
    main = _rgba_pixel_evidence(png_bytes, dimensions, "final product")
    components = _validated_component_contract(component_contract)
    if (
        components.get("machine") != machine_contract.get("machine")
        or components.get("display_values") != controller.get("display_values")
    ):
        raise ValueError("final component contract machine/controller identity drift")
    expected_patterns = components.get("expected_digit_patterns")
    if not isinstance(expected_patterns, list) or expected_patterns != [
        _DIGIT_SEGMENTS[digit]
        for value in controller.get("display_values", [])
        for digit in str(value)
    ]:
        raise ValueError("final component contract display pattern drift")
    raw_segments = components.get("segments")
    material_objects = components.get("material_objects")
    if not isinstance(raw_segments, list) or not isinstance(material_objects, list):
        raise ValueError("final component contract object identities are invalid")
    segment_ids = [
        str(_mapping(item, "final component segment").get("stable_object_id"))
        for item in raw_segments
    ]
    expected_mask_ids = {"material", *segment_ids}
    if set(component_mask_bytes) != expected_mask_ids:
        raise ValueError("final component masks are missing, extra, or bound to wrong identities")

    material_mask, material_mask_evidence = _decode_component_mask(
        component_mask_bytes["material"], dimensions, "final material object mask"
    )
    material_pixels = _masked_pixel_evidence(
        pixels, material_mask, "final material object mask"
    )
    if material_pixels["unique_rgb_values"] < 2:
        raise ValueError("final material object pixels cannot be uniform")

    occupied = [False] * len(pixels)
    segment_records: list[dict[str, object]] = []
    for ordinal, raw_segment in enumerate(raw_segments):
        segment = _mapping(raw_segment, f"final component segment {ordinal}")
        if segment.get("ordinal") != ordinal:
            raise ValueError("final controller segment order/identity drift")
        stable_id = str(segment.get("stable_object_id"))
        mask, mask_evidence = _decode_component_mask(
            component_mask_bytes[stable_id], dimensions,
            f"final controller segment mask {stable_id}",
        )
        if any(existing and value > 0 for existing, value in zip(occupied, mask)):
            raise ValueError("final controller physical segment masks overlap or are duplicated")
        for index, value in enumerate(mask):
            if value > 0:
                occupied[index] = True
        pixel_evidence = _masked_pixel_evidence(
            pixels, mask, f"final controller segment mask {stable_id}"
        )
        segment_records.append(
            {
                "ordinal": ordinal,
                "digit_index": segment.get("digit_index"),
                "segment": segment.get("segment"),
                "stable_object_id": stable_id,
                "material_id": segment.get("material_id"),
                "expected_active": segment.get("expected_active"),
                "object_identity_sha256": segment.get("object_identity_sha256"),
                "material_identity_sha256": segment.get("material_identity_sha256"),
                "mask": mask_evidence,
                "pixels": pixel_evidence,
            }
        )
    if any(value > 0 and occupied[index] for index, value in enumerate(material_mask)):
        raise ValueError("final material and controller component masks overlap")
    _validate_segment_layout(segment_records)

    active_luma = [
        float(record["pixels"]["mean_luma"])
        for record in segment_records if record["expected_active"] is True
    ]
    inactive_luma = [
        float(record["pixels"]["mean_luma"])
        for record in segment_records if record["expected_active"] is False
    ]
    if not active_luma or not inactive_luma or min(active_luma) <= max(inactive_luma):
        raise ValueError("controller active/inactive physical segment states are not distinguishable")
    threshold = (min(active_luma) + max(inactive_luma)) / 2
    observed_patterns: list[str] = []
    for digit_index in range(len(expected_patterns)):
        digit = segment_records[
            digit_index * len(_SEGMENT_LABELS):(digit_index + 1) * len(_SEGMENT_LABELS)
        ]
        observed_patterns.append(
            "".join(
                "1" if float(record["pixels"]["mean_luma"]) > threshold else "0"
                for record in digit
            )
        )
    if observed_patterns != expected_patterns:
        raise ValueError("controller physical segment state pattern does not match exact display values")
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
            "component_contract_sha256": components["sha256"],
            "stable_object_ids": [
                _mapping(item, "final material object")["stable_object_id"]
                for item in material_objects
            ],
            "object_identity_sha256": canonical_json_sha256(material_objects),
            "mask": material_mask_evidence,
            **material_pixels,
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
            "component_contract_sha256": components["sha256"],
            "display_values": list(controller["display_values"]),
            "expected_digit_patterns": expected_patterns,
            "observed_digit_patterns": observed_patterns,
            "active_segment_count": sum(record["expected_active"] is True for record in segment_records),
            "inactive_segment_count": sum(record["expected_active"] is False for record in segment_records),
            "illumination_threshold": round(threshold, 8),
            "segment_identity_sha256": canonical_json_sha256(raw_segments),
            "segments": segment_records,
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
        "machine_contract": _machine_contract_path(repository, scene),
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
    approved_authored = _mapping(
        _mapping(metadata.get("authored_settings"), "proof authored settings").get("before"),
        "proof authored settings before",
    )
    build_authorized_component_contract(
        machine_payload,
        approved_authored,
        roots,
        evidence,
    )

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
    render_metadata, _ = stable_json(
        Path(str(current["render_metadata"]["path"])),
        roots["asset"],
        "asset",
        "final approved render metadata",
        current["render_metadata"],
    )
    machine_contract, _ = stable_json(
        Path(str(current["machine_contract"]["path"])),
        roots["repository"],
        "repository",
        "final approved machine contract",
        current["machine_contract"],
    )
    authored_settings = _mapping(
        _mapping(
            render_metadata.get("authored_settings"), "final approved authored settings"
        ).get("before"),
        "final approved authored settings before",
    )
    build_authorized_component_contract(
        machine_contract,
        authored_settings,
        {name: str(path) for name, path in roots.items()},
        current,
    )
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
