"""Read-only schema-v2 inventory for the active PIMM Blender workspace."""

from __future__ import annotations

import argparse
import ctypes
import functools
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from ctypes import wintypes
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
ASSET_ROOT = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders")
MANIFEST_ROOT = ASSET_ROOT / "manifests"
DEFAULT_INVENTORY = MANIFEST_ROOT / "blender-project-inventory.json"
DEFAULT_RENDER_INVENTORY = MANIFEST_ROOT / "render-generation-inventory.json"
DEFAULT_GRAPH = MANIFEST_ROOT / "consumer-graph.json"
DEFAULT_REPORT = MANIFEST_ROOT / "blender-project-migration-report.md"

INVENTORY_SCHEMA = "pimm-asset-inventory/v2"
RENDER_INVENTORY_SCHEMA = "pimm-render-generation-inventory/v1"
AUTHORITATIVE_NAMES = frozenset(
    {"PIMM-30G-MASTER.blend", "PIMM-50G-MASTER.blend", "PIMM-MATERIAL-LIBRARY.blend"}
)
AUTHORITATIVE_PATHS = frozenset(f"masters/{name}" for name in AUTHORITATIVE_NAMES)
ALLOWED_DISPOSITIONS = frozenset(
    {"authoritative", "active-linked-scene", "migrate", "pending-archive", "unresolved"}
)
# Schema-v1 labels retained as an explicit reader migration map. Schema v2 emits only
# the normalized values above: keep-authoritative, migrate-scene, and
# archive-after-validation are never written to refreshed manifests.
LEGACY_DISPOSITION_ALIASES = {
    "keep-authoritative": "authoritative",
    "migrate-scene": "migrate",
    "archive-after-validation": "pending-archive",
}

_SCRIPT_SUFFIXES = frozenset({".py", ".ps1", ".bat", ".cmd", ".mjs", ".js"})
_IMAGE_SUFFIXES = frozenset(
    {".png", ".webp", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".hdr", ".svg"}
)
_VIDEO_SUFFIXES = frozenset({".mp4", ".webm", ".mov", ".mkv", ".avi"})
_FONT_SUFFIXES = frozenset({".ttf", ".otf", ".woff", ".woff2"})
_MANIFEST_SUFFIXES = frozenset({".json", ".jsonl", ".yaml", ".yml", ".csv", ".md"})
_TEXT_SUFFIXES = frozenset(
    {".py", ".ps1", ".bat", ".cmd", ".mjs", ".js", ".liquid", ".css", ".json", ".jsonl", ".yaml", ".yml", ".md", ".txt"}
)
_IGNORED_DIRECTORY_NAMES = frozenset(
    {"pending-delete", ".venv", "venv", "__pycache__", "node_modules", ".git"}
)
GENERATED_ARTIFACT_PATHS = frozenset(
    {
        "manifests/blender-project-inventory.json",
        "manifests/render-generation-inventory.json",
        "manifests/consumer-graph.json",
        "manifests/blender-project-migration-report.md",
    }
)
_GENERATED_ARTIFACT_PATHS_FOLDED = frozenset(
    path.casefold() for path in GENERATED_ARTIFACT_PATHS
)
_PUBLICATION_LOCK = "manifests/.pimm-inventory-publish.lock"
_PROOF_ID = re.compile(r"^proof-[0-9]{8}T[0-9]{6}Z-[a-z0-9]+$", re.IGNORECASE)
_RELEASE_ID = re.compile(r"^release-[0-9]{4}-[0-9]{2}-[0-9]{2}-r[0-9]{2}$", re.IGNORECASE)


def _tuple_values(values: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(sorted({str(value).replace("\\", "/") for value in values or ()}, key=str.casefold))


def _evidence_values(
    values: Mapping[str, Sequence[str]] | None,
) -> dict[str, tuple[str, ...]]:
    return {
        str(key).replace("\\", "/"): _tuple_values(items)
        for key, items in sorted((values or {}).items(), key=lambda pair: str(pair[0]).casefold())
    }


@dataclass(frozen=True)
class AssetRecord:
    """One immutable observed file record in the active asset root."""

    path: str
    size: int = 0
    mtime_ns: int = 0
    sha256: str = ""
    kind: str = "unclassified"
    unique_content: bool = False
    consumers: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    proposed_disposition: str = "unresolved"
    blender_inspection: Mapping[str, object] = field(default_factory=dict)
    dependency_evidence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    generation_membership: tuple[str, ...] = ()
    release_membership: tuple[str, ...] = ()
    filesystem_identity: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        normalized_path = self.path.replace("\\", "/")
        pure_path = PurePosixPath(normalized_path)
        if (
            not normalized_path
            or pure_path.is_absolute()
            or re.match(r"^[A-Za-z]:/", normalized_path)
            or any(part in {"", ".", ".."} for part in pure_path.parts)
        ):
            raise ValueError(f"asset path must be a relative contained path: {self.path}")
        if self.proposed_disposition == "delete":
            raise ValueError("delete disposition is forbidden")
        if self.proposed_disposition not in ALLOWED_DISPOSITIONS:
            raise ValueError(f"unsupported disposition: {self.proposed_disposition}")
        object.__setattr__(self, "path", normalized_path)
        object.__setattr__(self, "consumers", _tuple_values(self.consumers))
        object.__setattr__(self, "dependencies", _tuple_values(self.dependencies))
        object.__setattr__(self, "dependency_evidence", _evidence_values(self.dependency_evidence))
        object.__setattr__(self, "generation_membership", _tuple_values(self.generation_membership))
        object.__setattr__(self, "release_membership", _tuple_values(self.release_membership))
        object.__setattr__(self, "filesystem_identity", tuple(int(value) for value in self.filesystem_identity))


@dataclass(frozen=True)
class InventoryManifest:
    """Complete discovered path set and its one-to-one immutable records."""

    records: tuple[AssetRecord, ...]
    discovered_paths: tuple[str, ...]
    root: str = ""
    root_identity: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        paths = tuple(record.path for record in self.records)
        discovered = tuple(path.replace("\\", "/") for path in self.discovered_paths)
        if len(paths) != len(set(paths)):
            raise ValueError("inventory contains duplicate record paths")
        if len(discovered) != len(set(discovered)):
            raise ValueError("inventory contains duplicate discovered paths")
        if set(paths) != set(discovered):
            raise ValueError("inventory records do not exactly match discovered paths")
        object.__setattr__(self, "discovered_paths", discovered)
        object.__setattr__(self, "root_identity", tuple(int(value) for value in self.root_identity))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (int(value.st_dev), int(value.st_ino), int(value.st_ctime_ns), int(value.st_size))


@functools.lru_cache(maxsize=1)
def _windows_file_api():
    class FILE_BASIC_INFO(ctypes.Structure):
        _fields_ = (
            ("CreationTime", ctypes.c_longlong),
            ("LastAccessTime", ctypes.c_longlong),
            ("LastWriteTime", ctypes.c_longlong),
            ("ChangeTime", ctypes.c_longlong),
            ("FileAttributes", wintypes.DWORD),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    get_information = kernel32.GetFileInformationByHandleEx
    get_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    get_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    return FILE_BASIC_INFO, create_file, get_information, close_handle


def _windows_extended_path(path: Path) -> str:
    value = str(_absolute_lexical(path))
    if value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def _windows_change_time(path: Path) -> int | None:
    """Return native Windows ChangeTime when the backing filesystem exposes it."""

    if os.name != "nt":
        return None
    FILE_BASIC_INFO, create_file, get_information, close_handle = _windows_file_api()
    handle = create_file(
        _windows_extended_path(path),
        0x0080,  # FILE_READ_ATTRIBUTES
        0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
        None,
        3,  # OPEN_EXISTING
        0x02000000,  # FILE_FLAG_BACKUP_SEMANTICS
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        information = FILE_BASIC_INFO()
        if not get_information(
            handle,
            0,  # FileBasicInfo
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            error = ctypes.get_last_error()
            if error in {1, 50, 87}:  # unsupported by this filesystem/provider
                return None
            raise ctypes.WinError(error)
        return int(information.ChangeTime)
    finally:
        close_handle(handle)


@functools.lru_cache(maxsize=1)
def _windows_directory_change_api():
    pointer_integer = (
        ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
    )

    class OVERLAPPED(ctypes.Structure):
        _fields_ = (
            ("Internal", pointer_integer),
            ("InternalHigh", pointer_integer),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    create_event = kernel32.CreateEventW
    create_event.argtypes = (
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    create_event.restype = wintypes.HANDLE
    reset_event = kernel32.ResetEvent
    reset_event.argtypes = (wintypes.HANDLE,)
    reset_event.restype = wintypes.BOOL
    read_changes = kernel32.ReadDirectoryChangesW
    read_changes.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(OVERLAPPED),
        wintypes.LPVOID,
    )
    read_changes.restype = wintypes.BOOL
    wait = kernel32.WaitForSingleObject
    wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait.restype = wintypes.DWORD
    get_result = kernel32.GetOverlappedResult
    get_result.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(OVERLAPPED),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.BOOL,
    )
    get_result.restype = wintypes.BOOL
    cancel = kernel32.CancelIoEx
    cancel.argtypes = (wintypes.HANDLE, ctypes.POINTER(OVERLAPPED))
    cancel.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    return (
        OVERLAPPED,
        create_file,
        create_event,
        reset_event,
        read_changes,
        wait,
        get_result,
        cancel,
        close_handle,
    )


class _WindowsDirectoryChangeAuthority:
    """Kernel-observed mutation boundary for one governed directory tree."""

    _BUFFER_SIZE = 32 * 1024  # Network providers reject buffers larger than 64 KiB.
    _WAIT_OBJECT_0 = 0
    _WAIT_TIMEOUT = 258
    _ERROR_IO_PENDING = 997
    _ERROR_OPERATION_ABORTED = 995
    _ERROR_NOT_FOUND = 1168
    _NOTIFY_FILTER = (
        0x00000001  # FILE_NOTIFY_CHANGE_FILE_NAME
        | 0x00000002  # FILE_NOTIFY_CHANGE_DIR_NAME
        | 0x00000004  # FILE_NOTIFY_CHANGE_ATTRIBUTES
        | 0x00000008  # FILE_NOTIFY_CHANGE_SIZE
        | 0x00000010  # FILE_NOTIFY_CHANGE_LAST_WRITE
        | 0x00000040  # FILE_NOTIFY_CHANGE_CREATION
    )

    def __init__(self, root: Path) -> None:
        self._root = root
        (
            self._overlapped_type,
            create_file,
            create_event,
            self._reset_event,
            self._read_changes,
            self._wait,
            self._get_result,
            self._cancel,
            self._close_handle,
        ) = _windows_directory_change_api()
        self._directory = create_file(
            _windows_extended_path(root),
            0x0001,  # FILE_LIST_DIRECTORY
            0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
            None,
            3,  # OPEN_EXISTING
            0x02000000 | 0x40000000,  # BACKUP_SEMANTICS | OVERLAPPED
            None,
        )
        if self._directory == ctypes.c_void_p(-1).value:
            detail = ctypes.WinError(ctypes.get_last_error())
            raise RuntimeError(
                f"cannot establish governed directory change authority: {detail}"
            )
        self._event = create_event(None, True, False, None)
        if not self._event:
            error = ctypes.WinError(ctypes.get_last_error())
            self._close_handle(self._directory)
            raise RuntimeError(f"cannot create governed directory change event: {error}")
        self._buffer = (ctypes.c_ubyte * self._BUFFER_SIZE)()
        self._overlapped = self._overlapped_type()
        self._overlapped.hEvent = self._event
        self._pending = False
        self._closed = False
        try:
            self._arm()
            self._directory_states = self._capture_directory_states()
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass  # Preserve the primary authority-creation failure.
            raise

    def _capture_directory_states(self) -> dict[str, _FreshnessState]:
        """Record directory identities after arming; enumeration noise is validated later."""

        states: dict[str, _FreshnessState] = {}
        candidates = (
            self._root,
            *(path for path in self._root.rglob("*") if path.is_dir()),
        )
        for path in candidates:
            if _is_reparse_or_symlink(path):
                raise RuntimeError(f"governed directory is a reparse point: {path}")
            value = path.stat(follow_symlinks=False)
            relative = "." if path == self._root else path.relative_to(self._root).as_posix()
            states[relative.casefold()] = (
                _stat_identity(value),
                int(value.st_size),
                int(value.st_mtime_ns),
                _windows_change_time(path),
            )
        return states

    def _arm(self) -> None:
        if not self._reset_event(self._event):
            detail = ctypes.WinError(ctypes.get_last_error())
            raise RuntimeError(
                f"cannot reset governed directory change event: {detail}"
            )
        returned = wintypes.DWORD()
        if not self._read_changes(
            self._directory,
            ctypes.byref(self._buffer),
            self._BUFFER_SIZE,
            True,
            self._NOTIFY_FILTER,
            ctypes.byref(returned),
            ctypes.byref(self._overlapped),
            None,
        ):
            error = ctypes.get_last_error()
            if error != self._ERROR_IO_PENDING:
                raise RuntimeError(
                    f"cannot arm governed directory change authority: {ctypes.WinError(error)}"
                )
        self._pending = True

    def _completed_bytes(self) -> bytes:
        transferred = wintypes.DWORD()
        if not self._get_result(
            self._directory,
            ctypes.byref(self._overlapped),
            ctypes.byref(transferred),
            False,
        ):
            detail = ctypes.WinError(ctypes.get_last_error())
            raise RuntimeError(
                f"ambiguous governed directory watcher completion: {detail}"
            )
        self._pending = False
        if transferred.value == 0:
            raise RuntimeError("governed directory watcher overflow")
        return bytes(self._buffer[: transferred.value])

    @staticmethod
    def _events(payload: bytes) -> tuple[tuple[int, str], ...]:
        events: list[tuple[int, str]] = []
        offset = 0
        while True:
            if len(payload) - offset < 12:
                raise RuntimeError("malformed governed directory watcher result")
            next_offset = int.from_bytes(payload[offset : offset + 4], "little")
            action = int.from_bytes(payload[offset + 4 : offset + 8], "little")
            name_size = int.from_bytes(payload[offset + 8 : offset + 12], "little")
            end = offset + 12 + name_size
            if name_size % 2 or end > len(payload):
                raise RuntimeError("malformed governed directory watcher path")
            try:
                relative = payload[offset + 12 : end].decode("utf-16-le")
            except UnicodeDecodeError as error:
                raise RuntimeError("malformed governed directory watcher encoding") from error
            events.append((action, relative))
            if next_offset == 0:
                break
            if next_offset < 12 + name_size or offset + next_offset >= len(payload):
                raise RuntimeError("malformed governed directory watcher offset")
            offset += next_offset
        return tuple(events)

    def assert_quiet(self) -> None:
        """Drain exact-owned noise; the final timeout is the snapshot boundary."""

        observed: list[tuple[int, str]] = []
        while True:
            status = int(self._wait(self._event, 0))
            if status == self._WAIT_TIMEOUT:
                break
            if status != self._WAIT_OBJECT_0:
                raise RuntimeError(f"ambiguous governed directory watcher status: {status}")
            payload = self._completed_bytes()
            observed.extend(self._events(payload))
            self._arm()

        for action, relative in observed:
            normalized = relative.replace("\\", "/")
            folded = normalized.casefold()
            initial = self._directory_states.get(folded)
            # Windows reports FILE_ACTION_MODIFIED for a non-empty directory
            # merely because FindFirstFile enumerates it. Accept that observer
            # noise only when the same exact directory identity/state survived,
            # with no filename-based exception for child events.
            if action == 3 and initial is not None:
                path = self._root / PurePosixPath(normalized)
                try:
                    value = path.stat(follow_symlinks=False)
                    current = (
                        _stat_identity(value),
                        int(value.st_size),
                        int(value.st_mtime_ns),
                        _windows_change_time(path),
                    )
                except (FileNotFoundError, OSError):
                    current = None
                if current == initial:
                    continue
            raise RuntimeError(
                "governed directory changed during verification: "
                f"action={action} path={normalized}"
            )

    def close(self) -> None:
        if self._closed:
            return
        cleanup_error: BaseException | None = None
        if self._pending:
            if not self._cancel(self._directory, ctypes.byref(self._overlapped)):
                error = ctypes.get_last_error()
                if error != self._ERROR_NOT_FOUND:
                    detail = ctypes.WinError(error)
                    cleanup_error = RuntimeError(
                        f"ambiguous governed directory watcher cancellation: {detail}"
                    )
            else:
                status = int(self._wait(self._event, 5000))
                if status != self._WAIT_OBJECT_0:
                    cleanup_error = RuntimeError(
                        f"ambiguous governed directory watcher cancellation status: {status}"
                    )
                else:
                    transferred = wintypes.DWORD()
                    if self._get_result(
                        self._directory,
                        ctypes.byref(self._overlapped),
                        ctypes.byref(transferred),
                        False,
                    ):
                        # The read completed after the successful final poll.
                        # That is known later drift, not an ambiguous snapshot.
                        pass
                    elif ctypes.get_last_error() != self._ERROR_OPERATION_ABORTED:
                        cleanup_error = RuntimeError(
                            "ambiguous governed directory watcher cancellation completion: "
                            f"{ctypes.WinError(ctypes.get_last_error())}"
                        )
        self._pending = False
        if not self._close_handle(self._event) and cleanup_error is None:
            detail = ctypes.WinError(ctypes.get_last_error())
            cleanup_error = RuntimeError(
                f"cannot close governed directory watcher event: {detail}"
            )
        if not self._close_handle(self._directory) and cleanup_error is None:
            detail = ctypes.WinError(ctypes.get_last_error())
            cleanup_error = RuntimeError(
                f"cannot close governed directory watcher handle: {detail}"
            )
        self._closed = True
        if cleanup_error is not None:
            raise cleanup_error


def _directory_change_authority(root: Path) -> _WindowsDirectoryChangeAuthority:
    if os.name != "nt":
        raise RuntimeError(
            "kernel directory change authority is required for governed inventory verification"
        )
    return _WindowsDirectoryChangeAuthority(root)


def _is_reparse_or_symlink(path: Path) -> bool:
    value = path.lstat()
    attributes = int(getattr(value, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(value.st_mode) or bool(attributes & reparse_flag)


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _guard_path(root: Path, path: Path, *, allow_missing_leaf: bool = False) -> Path:
    """Validate lexical containment and reject every existing alias component."""

    root = _absolute_lexical(root)
    candidate = _absolute_lexical(path)
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"path is outside the governed root: {candidate}") from error
    if _is_reparse_or_symlink(root):
        raise ValueError(f"governed root is a reparse point or symbolic link: {root}")
    current = root
    for index, part in enumerate(relative.parts):
        current /= part
        if not current.exists() and not current.is_symlink():
            if allow_missing_leaf and index == len(relative.parts) - 1:
                break
            if allow_missing_leaf:
                continue
            raise FileNotFoundError(current)
        if _is_reparse_or_symlink(current):
            raise ValueError(f"path contains a reparse point or symbolic link: {current}")
    return candidate


def _canonical_root(root: Path) -> Path:
    lexical = _absolute_lexical(root)
    if not lexical.is_dir():
        raise ValueError(f"asset root must be an existing directory: {lexical}")
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current /= part
        if _is_reparse_or_symlink(current):
            raise ValueError(
                f"asset root contains a reparse point or symbolic link: {current}"
            )
    _guard_path(lexical, lexical)
    return lexical


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_ignored(relative: Path, root: Path) -> bool:
    if any(part.casefold() in _IGNORED_DIRECTORY_NAMES for part in relative.parts[:-1]):
        return True
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if (current / "pyvenv.cfg").is_file():
            return True
    return False


def _asset_kind(relative: Path) -> str | None:
    suffix = relative.suffix.casefold()
    parts = {part.casefold() for part in relative.parts[:-1]}
    if suffix in {".blend", ".blend1"}:
        if suffix == ".blend" and relative.name in AUTHORITATIVE_NAMES and relative.parent.as_posix().casefold() == "masters":
            return "authoritative-master"
        return "blend-recovery" if suffix == ".blend1" else "blend-project"
    if suffix in _SCRIPT_SUFFIXES:
        return "script"
    if ("manifests" in parts and suffix in _MANIFEST_SUFFIXES) or (
        "manifest" in relative.stem.casefold() and suffix in _MANIFEST_SUFFIXES
    ):
        return "manifest"
    if suffix in _VIDEO_SUFFIXES:
        return "render-video" if "renders" in parts else "artwork-video"
    if suffix in _IMAGE_SUFFIXES:
        if "renders" in parts:
            if "masks" in parts or "mask" in relative.stem.casefold():
                return "render-mask"
            if "passes" in parts or suffix in {".exr", ".hdr"}:
                return "render-pass"
            return "render-image"
        if "textures" in parts:
            return "texture"
        return "artwork"
    if suffix in _FONT_SUFFIXES:
        return "font"
    return None


def _discover(root: Path) -> list[tuple[Path, str]]:
    discovered: list[tuple[Path, str]] = []
    for path in root.rglob("*"):
        if _is_reparse_or_symlink(path):
            raise ValueError(f"asset tree contains a reparse point or symbolic link: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_ignored(relative, root):
            continue
        relative_text = relative.as_posix()
        if relative_text.casefold() in _GENERATED_ARTIFACT_PATHS_FOLDED:
            continue
        kind = _asset_kind(relative)
        if kind is not None:
            discovered.append((path, kind))
    return sorted(discovered, key=lambda item: _relative(item[0], root).casefold())


def _load_cached_inspections(root: Path) -> dict[str, tuple[str, Mapping[str, object], bool, Mapping[str, tuple[str, ...]]]]:
    inventory_path = root / "manifests" / "blender-project-inventory.json"
    if not inventory_path.is_file():
        return {}
    try:
        payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        records = payload.get("projects", []) if isinstance(payload, dict) else []
    cached: dict[str, tuple[str, Mapping[str, object], bool, Mapping[str, tuple[str, ...]]]] = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        try:
            absolute = Path(path)
            relative = str(item.get("relative_path") or absolute.relative_to(root)).replace("\\", "/")
        except (ValueError, OSError):
            relative = str(item.get("relative_path", path)).replace("\\", "/")
        inspection = item.get("blender_inspection", item.get("blender", {}))
        evidence = item.get("dependency_evidence", {})
        if isinstance(inspection, dict) and isinstance(evidence, dict):
            cached[relative] = (
                str(item.get("sha256", "")).upper(),
                inspection,
                bool(item.get("unique_content", item.get("unique_scene_content", False))),
                _evidence_values(evidence),
            )
    return cached


def _membership(relative: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    parts = PurePosixPath(relative).parts
    generations = tuple(part for part in parts if _PROOF_ID.fullmatch(part))
    releases = tuple(part for part in parts if _RELEASE_ID.fullmatch(part))
    if not generations and len(parts) > 2 and parts[0].casefold() == "renders":
        generations = (f"legacy:{parts[1]}",)
    return generations, releases


class _ExactReferenceMatcher:
    """Resolve exact paths and only unambiguous bare basenames."""

    def __init__(self, candidates: Mapping[str, Path]):
        self._exact_trie: dict[str, object] = {}
        self._basename_trie: dict[str, object] = {}
        basename_paths: dict[str, set[str]] = {}
        for relative, absolute in candidates.items():
            basename_paths.setdefault(PurePosixPath(relative).name.casefold(), set()).add(relative)
            variants = {relative, str(absolute).replace("\\", "/")}
            for variant in variants:
                if "/" not in variant:
                    continue
                self._insert(self._exact_trie, variant, relative)
        self._basename_paths = basename_paths
        for basename in basename_paths:
            self._insert(self._basename_trie, basename, basename)

    @staticmethod
    def _insert(trie: dict[str, object], variant: str, value: str) -> None:
        node = trie
        for character in variant.replace("\\", "/").casefold():
            node = node.setdefault(character, {})  # type: ignore[assignment]
        node.setdefault("", set()).add(value)  # type: ignore[union-attr]

    @staticmethod
    def _trie_matches(trie: Mapping[str, object], normalized: str) -> set[str]:
        found: set[str] = set()
        boundary = set("abcdefghijklmnopqrstuvwxyz0123456789_.-")
        for start in range(len(normalized)):
            if start and normalized[start - 1] in boundary:
                continue
            node = trie
            index = start
            while index < len(normalized) and normalized[index] in node:
                child = node[normalized[index]]
                if not isinstance(child, dict):
                    break
                node = child
                index += 1
                terminals = node.get("")
                if terminals and (index == len(normalized) or normalized[index] not in boundary):
                    found.update(terminals)  # type: ignore[arg-type]
        return found

    def match_details(self, text: str) -> tuple[set[str], dict[str, set[str]]]:
        normalized = text.replace("\\", "/").casefold()
        resolved = self._trie_matches(self._exact_trie, normalized)
        exact_basenames = {PurePosixPath(path).name.casefold() for path in resolved}
        ambiguous: dict[str, set[str]] = {}
        for basename in self._trie_matches(self._basename_trie, normalized):
            if basename in exact_basenames:
                continue
            paths = self._basename_paths[basename]
            if len(paths) == 1:
                resolved.update(paths)
            else:
                ambiguous[basename] = set(paths)
        return resolved, ambiguous

    def matches(self, text: str) -> set[str]:
        return self.match_details(text)[0]


def _text_dependencies(
    path: Path,
    matcher: _ExactReferenceMatcher,
    relative: str,
) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    if (
        path.suffix.casefold() not in _TEXT_SUFFIXES
        or relative.casefold() in _GENERATED_ARTIFACT_PATHS_FOLDED
    ):
        return (), {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return (), {}
    found: dict[str, list[str]] = {}
    for line_number, line in enumerate(lines, start=1):
        for relative in matcher.matches(line):
            found.setdefault(relative, []).append(f"text:{line_number}")
    evidence = {key: tuple(sorted(set(values))) for key, values in found.items()}
    return tuple(sorted(evidence, key=str.casefold)), evidence


def inventory_workspace(root: Path) -> InventoryManifest:
    """Hash every governed active file without opening or mutating Blender files."""

    root = _canonical_root(root)
    cached = _load_cached_inspections(root)
    discovered = _discover(root)
    candidates = {_relative(path, root): path for path, _kind in discovered}
    matcher = _ExactReferenceMatcher(candidates)
    records: list[AssetRecord] = []
    for path, kind in discovered:
        relative = _relative(path, root)
        guarded_path = _guard_path(root, path)
        stat_before = guarded_path.stat(follow_symlinks=False)
        digest = sha256_file(path)
        stat_after = guarded_path.stat(follow_symlinks=False)
        if _stat_identity(stat_before) != _stat_identity(stat_after) or stat_before.st_mtime_ns != stat_after.st_mtime_ns:
            raise RuntimeError(f"asset changed while hashing: {relative}")
        inspection: Mapping[str, object] = {}
        unique_content = False
        dependency_evidence: Mapping[str, tuple[str, ...]] = {}
        cached_record = cached.get(relative)
        if cached_record is not None and cached_record[0] == digest:
            inspection, unique_content, dependency_evidence = cached_record[1:]
        dependencies, text_evidence = _text_dependencies(path, matcher, relative)
        combined_evidence = dict(dependency_evidence)
        combined_evidence.update(text_evidence)
        combined_dependencies = tuple(sorted(set(dependencies) | set(combined_evidence), key=str.casefold))
        generation_membership, release_membership = _membership(relative)
        records.append(
            AssetRecord(
                path=relative,
                size=stat_after.st_size,
                mtime_ns=stat_after.st_mtime_ns,
                sha256=digest,
                kind=kind,
                unique_content=unique_content,
                dependencies=combined_dependencies,
                blender_inspection=inspection,
                dependency_evidence=combined_evidence,
                generation_membership=generation_membership,
                release_membership=release_membership,
                filesystem_identity=_stat_identity(stat_after),
            )
        )
    paths = tuple(record.path for record in records)
    return InventoryManifest(
        records=tuple(records),
        discovered_paths=paths,
        root=str(root),
        root_identity=_stat_identity(root.stat(follow_symlinks=False))[:2],
    )


def _record_payload(record: AssetRecord) -> dict[str, object]:
    payload = asdict(record)
    payload["blender_inspection"] = dict(record.blender_inspection)
    payload["dependency_evidence"] = {
        key: list(values) for key, values in record.dependency_evidence.items()
    }
    for key in (
        "consumers",
        "dependencies",
        "generation_membership",
        "release_membership",
        "filesystem_identity",
    ):
        payload[key] = list(payload[key])
    return payload


def inventory_payload(
    inventory: InventoryManifest,
    *,
    publication_id: str | None = None,
    generated_artifacts: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    dispositions = {name: 0 for name in sorted(ALLOWED_DISPOSITIONS)}
    kinds: dict[str, int] = {}
    for record in inventory.records:
        dispositions[record.proposed_disposition] += 1
        kinds[record.kind] = kinds.get(record.kind, 0) + 1
    payload: dict[str, object] = {
        "schema": INVENTORY_SCHEMA,
        "root": inventory.root,
        "root_identity": list(inventory.root_identity),
        "generated_path_policy": {
            "rule": "exact-path exclusion; generated children are hash-bound by the inventory authority",
            "excluded_paths": sorted(GENERATED_ARTIFACT_PATHS, key=str.casefold),
        },
        "discovered_paths": list(inventory.discovered_paths),
        "records": [_record_payload(record) for record in inventory.records],
        "summary": {
            "record_count": len(inventory.records),
            "bytes": sum(record.size for record in inventory.records),
            "kinds": dict(sorted(kinds.items())),
            "dispositions": dispositions,
        },
    }
    if publication_id is not None:
        payload["publication_id"] = publication_id
    if generated_artifacts is not None:
        payload["generated_artifacts"] = {
            path: dict(value)
            for path, value in sorted(generated_artifacts.items(), key=lambda item: item[0].casefold())
        }
    return payload


def inventory_from_payload(payload: Mapping[str, object]) -> InventoryManifest:
    if payload.get("schema") != INVENTORY_SCHEMA:
        raise ValueError("schema-v2 inventory required")
    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        raise ValueError("inventory records must be a list")
    records: list[AssetRecord] = []
    for item in raw_records:
        if not isinstance(item, dict):
            raise ValueError("inventory record must be an object")
        records.append(AssetRecord(**item))
    discovered = payload.get("discovered_paths")
    if not isinstance(discovered, list):
        raise ValueError("inventory discovered_paths must be a list")
    return InventoryManifest(
        records=tuple(records),
        discovered_paths=tuple(str(path) for path in discovered),
        root=str(payload.get("root", "")),
        root_identity=tuple(int(value) for value in payload.get("root_identity", ())),
    )


def render_generation_payload(
    inventory: InventoryManifest, *, publication_id: str | None = None
) -> dict[str, object]:
    records = [
        record
        for record in inventory.records
        if record.kind.startswith("render-")
        or record.generation_membership
        or record.release_membership
    ]
    generations: dict[str, list[str]] = {}
    releases: dict[str, list[str]] = {}
    for record in records:
        for generation in record.generation_membership:
            generations.setdefault(generation, []).append(record.path)
        for release in record.release_membership:
            releases.setdefault(release, []).append(record.path)
    payload: dict[str, object] = {
        "schema": RENDER_INVENTORY_SCHEMA,
        "root": inventory.root,
        "records": [_record_payload(record) for record in records],
        "generations": {key: sorted(values, key=str.casefold) for key, values in sorted(generations.items())},
        "releases": {key: sorted(values, key=str.casefold) for key, values in sorted(releases.items())},
    }
    if publication_id is not None:
        payload["publication_id"] = publication_id
    return payload


def _canonical_generated_paths(root: Path) -> dict[str, Path]:
    return {
        relative: root / PurePosixPath(relative)
        for relative in GENERATED_ARTIFACT_PATHS
    }


def _validate_generated_destinations(
    root: Path,
    inventory_path: Path,
    report_path: Path,
    graph_path: Path,
    render_inventory_path: Path,
) -> dict[str, Path]:
    root = _canonical_root(root)
    expected = _canonical_generated_paths(root)
    provided = {
        "manifests/blender-project-inventory.json": inventory_path,
        "manifests/render-generation-inventory.json": render_inventory_path,
        "manifests/consumer-graph.json": graph_path,
        "manifests/blender-project-migration-report.md": report_path,
    }
    for relative, path in provided.items():
        canonical = _absolute_lexical(expected[relative])
        if _absolute_lexical(path) != canonical:
            raise ValueError(
                f"canonical generated output required for {relative}: {canonical}"
            )
        _guard_path(root, canonical, allow_missing_leaf=True)
    return expected


_FreshnessState = tuple[tuple[int, int, int, int], int, int, int | None]


def _freshness_state(root: Path, path: Path, relative: str, phase: str) -> _FreshnessState:
    try:
        guarded = _guard_path(root, path)
        current_stat = guarded.stat(follow_symlinks=False)
        change_time = _windows_change_time(guarded)
    except FileNotFoundError as error:
        raise RuntimeError(f"asset disappeared {phase}: {relative}") from error
    return (
        _stat_identity(current_stat),
        int(current_stat.st_size),
        int(current_stat.st_mtime_ns),
        change_time,
    )


def _assert_freshness_state(
    before: _FreshnessState,
    after: _FreshnessState,
    relative: str,
    phase: str,
) -> None:
    if before[0][:2] != after[0][:2]:
        raise RuntimeError(f"asset filesystem identity changed {phase}: {relative}")
    if before[1:3] != after[1:3]:
        raise RuntimeError(f"asset metadata changed {phase}: {relative}")
    if before[3] is not None and after[3] is not None and before[3] != after[3]:
        raise RuntimeError(f"asset Windows ChangeTime changed {phase}: {relative}")
    if before[0] != after[0]:
        raise RuntimeError(f"asset metadata identity changed {phase}: {relative}")


def _discovered_path_set(discovered: Sequence[tuple[Path, str]], root: Path) -> set[str]:
    return {_relative(path, root) for path, _kind in discovered}


def _verify_inventory_fresh(
    inventory: InventoryManifest,
    root: Path,
    *,
    verify_hashes: bool = True,
    permitted_missing_paths: Sequence[str] = (),
) -> None:
    root = _canonical_root(root)
    authority = _directory_change_authority(root)
    verification_error: BaseException | None = None
    try:
        if not inventory.root or _absolute_lexical(Path(inventory.root)) != root:
            raise RuntimeError("stale inventory root")
        root_identity = _stat_identity(root.stat(follow_symlinks=False))[:2]
        if not inventory.root_identity or tuple(inventory.root_identity) != root_identity:
            raise RuntimeError("stale inventory root filesystem identity")
        expected_paths = set(inventory.discovered_paths)
        permitted = tuple(permitted_missing_paths)
        if len({value.casefold() for value in permitted}) != len(permitted):
            raise RuntimeError("permitted missing inventory paths are duplicated")
        if any(value not in expected_paths for value in permitted):
            raise RuntimeError("permitted missing path is not an exact published inventory path")
        current = _discover(root)
        current_paths = _discovered_path_set(current, root)
        missing_paths = expected_paths - current_paths
        if current_paths - expected_paths or missing_paths - set(permitted):
            raise RuntimeError("stale inventory path set")
        records = {record.path: record for record in inventory.records}
        post_hash_states: dict[str, _FreshnessState] = {}
        for path, _kind in current:
            relative = _relative(path, root)
            record = records[relative]
            before = _freshness_state(root, path, relative, "before hash")
            if not record.filesystem_identity or tuple(record.filesystem_identity) != before[0]:
                raise RuntimeError(f"asset filesystem identity changed: {relative}")
            if record.size != before[1] or record.mtime_ns != before[2]:
                raise RuntimeError(f"asset metadata changed: {relative}")
            digest = sha256_file(path) if verify_hashes else None
            after = _freshness_state(root, path, relative, "after hash")
            _assert_freshness_state(before, after, relative, "after hash")
            if digest is not None and digest != record.sha256:
                raise RuntimeError(f"asset content hash changed: {relative}")
            post_hash_states[relative] = after

        closing = _discover(root)
        if _discovered_path_set(closing, root) != current_paths:
            raise RuntimeError("stale inventory path set at closing verification")
        closing_states: dict[str, _FreshnessState] = {}
        for path, _kind in closing:
            relative = _relative(path, root)
            state = _freshness_state(root, path, relative, "during closing verification")
            _assert_freshness_state(
                post_hash_states[relative],
                state,
                relative,
                "during closing verification",
            )
            closing_states[relative] = state

        # These two complete state passes overlap between the last post-hash state
        # and the first closing state. Equal identity/metadata/ChangeTime values give
        # verification one stable source snapshot instead of unrelated per-file reads.
        final = _discover(root)
        if _discovered_path_set(final, root) != current_paths:
            raise RuntimeError("stale inventory path set at final consistency check")
        for path, _kind in final:
            relative = _relative(path, root)
            state = _freshness_state(root, path, relative, "during final consistency check")
            _assert_freshness_state(
                closing_states[relative],
                state,
                relative,
                "during final consistency check",
            )
        final_root_identity = _stat_identity(root.stat(follow_symlinks=False))[:2]
        if final_root_identity != root_identity:
            raise RuntimeError("stale inventory root filesystem identity at closing verification")
        # A successful zero-time kernel poll linearizes this verified snapshot.
        # Anything reported before/during this poll invalidates the current call;
        # a mutation after it is later drift and is rejected by the next call.
        authority.assert_quiet()
    except BaseException as error:
        verification_error = error
        raise
    finally:
        try:
            authority.close()
        except BaseException:
            if verification_error is None:
                raise


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _prepare_atomic_bytes(destination: Path, content: bytes) -> tuple[Path, tuple[int, ...]]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp.{uuid.uuid4().hex}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        identity = _stat_identity(os.fstat(descriptor))
    finally:
        os.close(descriptor)
    return temporary, identity


def _remove_owned_file(path: Path, identity: tuple[int, ...]) -> None:
    try:
        current = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return
    if _stat_identity(current) != identity:
        raise RuntimeError(f"owned temporary path identity changed: {path}")
    path.unlink()


def _replace_prepared(destination: Path, temporary: Path, content: bytes) -> None:
    os.replace(temporary, destination)
    if destination.read_bytes() != content:
        raise RuntimeError(f"atomic publication readback mismatch: {destination}")


def atomic_write_json(destination: Path, payload: Mapping[str, object]) -> None:
    content = _json_bytes(payload)
    temporary, identity = _prepare_atomic_bytes(destination, content)
    try:
        _replace_prepared(destination, temporary, content)
    finally:
        if temporary.exists():
            _remove_owned_file(temporary, identity)


def _blender_path(value: str, owner: object | None = None) -> str:
    import bpy

    if not value:
        return ""
    try:
        absolute = bpy.path.abspath(value, library=owner)
    except (OSError, ValueError, TypeError):
        absolute = value
    return str(Path(absolute).resolve()).replace("\\", "/")


def _compositor_node_tree(scene: object) -> object | None:
    """Return the compositor tree across Blender 4.x and 5.2 APIs."""

    return getattr(scene, "node_tree", None) or getattr(scene, "compositing_node_group", None)


def _identity_digest(rows: Sequence[object]) -> str:
    encoded = json.dumps(list(rows), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _unique_blender_content(summary: Mapping[str, object]) -> bool:
    return bool(
        int(summary.get("object_count", 0) or 0)
        or int(summary.get("mesh_datablock_count", 0) or 0)
        or int(summary.get("material_count", 0) or 0)
        or summary.get("cameras")
        or summary.get("rigs")
        or summary.get("animations")
        or summary.get("lights")
        or summary.get("compositor_nodes")
    )


def _inspection_summary(root: Path) -> tuple[dict[str, object], dict[str, tuple[str, ...]]]:
    import bpy

    dependencies: dict[str, list[str]] = {}
    missing_dependencies: set[str] = set()

    def add_dependency(value: str, evidence: str, owner: object | None = None) -> None:
        absolute_text = _blender_path(value, owner)
        if not absolute_text or value == "<builtin>":
            return
        absolute = Path(absolute_text)
        try:
            display = absolute.relative_to(root).as_posix()
        except ValueError:
            display = absolute_text
        dependencies.setdefault(display, []).append(evidence)
        if not evidence.startswith("output:") and not absolute.exists():
            missing_dependencies.add(display)

    for library in bpy.data.libraries:
        add_dependency(library.filepath, f"library:{library.name}")
    for image in bpy.data.images:
        if image.filepath and image.packed_file is None:
            add_dependency(image.filepath, f"image:{image.name}", image.library)
    for font in bpy.data.fonts:
        if font.filepath:
            add_dependency(font.filepath, f"font:{font.name}", font.library)
    for sound in bpy.data.sounds:
        if sound.filepath:
            add_dependency(sound.filepath, f"sound:{sound.name}", sound.library)
    for cache in bpy.data.cache_files:
        if cache.filepath:
            add_dependency(cache.filepath, f"cache:{cache.name}", cache.library)
    for scene in bpy.data.scenes:
        if scene.render.filepath:
            add_dependency(scene.render.filepath, f"output:{scene.name}")

    cameras = sorted(obj.name for obj in bpy.data.objects if obj.type == "CAMERA")
    lights = sorted(obj.name for obj in bpy.data.objects if obj.type == "LIGHT")
    rigs = sorted(
        obj.name
        for obj in bpy.data.objects
        if obj.type == "ARMATURE" or (obj.type == "EMPTY" and (obj.constraints or obj.animation_data))
    )
    animations = sorted(
        set(action.name for action in bpy.data.actions)
        | {obj.name for obj in bpy.data.objects if obj.animation_data is not None}
    )
    compositor_nodes = sorted(
        f"{scene.name}/{node.name}:{node.bl_idname}"
        for scene in bpy.data.scenes
        if scene.use_nodes and _compositor_node_tree(scene) is not None
        for node in _compositor_node_tree(scene).nodes
    )
    object_identities = sorted(
        (
            obj.name,
            obj.type,
            getattr(getattr(obj, "data", None), "name", ""),
            getattr(getattr(obj, "parent", None), "name", ""),
        )
        for obj in bpy.data.objects
    )
    geometry_identities = sorted(
        (
            mesh.name,
            len(mesh.vertices),
            len(mesh.edges),
            len(mesh.polygons),
            tuple(slot.name if slot is not None else "" for slot in mesh.materials),
        )
        for mesh in bpy.data.meshes
    )
    material_identities = sorted(
        (
            material.name,
            str(material.get("pimm_material_id", "")),
            getattr(getattr(material, "library", None), "filepath", ""),
            bool(material.use_nodes),
        )
        for material in bpy.data.materials
    )
    summary: dict[str, object] = {
        "blender_version": ".".join(str(value) for value in bpy.app.version),
        "scenes": sorted(scene.name for scene in bpy.data.scenes),
        "mesh_object_count": sum(obj.type == "MESH" for obj in bpy.data.objects),
        "mesh_datablock_count": len(bpy.data.meshes),
        "object_count": len(bpy.data.objects),
        "material_count": len(bpy.data.materials),
        "object_identity_sha256": _identity_digest(object_identities),
        "geometry_identity_sha256": _identity_digest(geometry_identities),
        "material_identity_sha256": _identity_digest(material_identities),
        "cameras": cameras,
        "rigs": rigs,
        "animations": animations,
        "lights": lights,
        "compositor_nodes": compositor_nodes,
        "missing_dependencies": sorted(missing_dependencies, key=str.casefold),
        "inspection_error": None,
    }
    evidence = {key: tuple(sorted(set(values))) for key, values in sorted(dependencies.items())}
    return summary, evidence


def enrich_with_blender(inventory_path: Path, root: Path | None = None) -> InventoryManifest:
    """Inspect Blender datablocks read-only, hash-checking each file before and after open."""

    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory = inventory_from_payload(payload)
    root = _canonical_root(root or Path(inventory.root))
    expected_inventory = _canonical_generated_paths(root)["manifests/blender-project-inventory.json"]
    if _absolute_lexical(inventory_path) != _absolute_lexical(expected_inventory):
        raise ValueError(f"canonical generated output required for inventory: {expected_inventory}")
    _guard_path(root, expected_inventory)
    _verify_inventory_fresh(inventory, root)
    records: list[AssetRecord] = []
    blend_records = [record for record in inventory.records if record.kind in {"blend-project", "blend-recovery", "authoritative-master"}]
    total = len(blend_records)
    inspected = 0
    for record in inventory.records:
        if record not in blend_records:
            records.append(record)
            continue
        path = _guard_path(root, root / PurePosixPath(record.path))
        stat_before = path.stat(follow_symlinks=False)
        if tuple(record.filesystem_identity) != _stat_identity(stat_before):
            raise RuntimeError(f"Blender file filesystem identity drift before inspection: {record.path}")
        before = sha256_file(path)
        if before != record.sha256:
            raise RuntimeError(f"Blender file drift before inspection: {record.path}")
        try:
            import bpy

            bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
            summary, evidence = _inspection_summary(root)
            unique_content = _unique_blender_content(summary)
        except Exception as error:
            summary = {"inspection_error": f"{type(error).__name__}: {error}"}
            evidence = {}
            unique_content = True
        after = sha256_file(path)
        if after != before:
            raise RuntimeError(f"Blender file changed during read-only inspection: {record.path}")
        stat_after = path.stat(follow_symlinks=False)
        if _stat_identity(stat_after) != _stat_identity(stat_before):
            raise RuntimeError(f"Blender file filesystem identity changed during inspection: {record.path}")
        dependencies = tuple(sorted(set(record.dependencies) | set(evidence), key=str.casefold))
        combined_evidence = dict(record.dependency_evidence)
        combined_evidence.update(evidence)
        records.append(
            replace(
                record,
                unique_content=unique_content,
                dependencies=dependencies,
                dependency_evidence=combined_evidence,
                blender_inspection=summary,
            )
        )
        inspected += 1
        print(f"PIMM_INVENTORY_INSPECT files={inspected}/{total} path={record.path}", flush=True)
    enriched = InventoryManifest(
        tuple(records),
        inventory.discovered_paths,
        inventory.root,
        inventory.root_identity,
    )
    atomic_write_json(inventory_path, inventory_payload(enriched))
    return enriched


def migration_report(
    inventory: InventoryManifest, *, publication_id: str | None = None
) -> str:
    migration_records = [
        record
        for record in inventory.records
        if record.proposed_disposition in {"migrate", "unresolved"}
    ]
    migrate_count = sum(record.proposed_disposition == "migrate" for record in migration_records)
    unresolved_count = sum(record.proposed_disposition == "unresolved" for record in migration_records)
    lines = [
        "# PIMM Blender Migration Report",
        "",
        "This report is read-only. No file was moved, renamed, or deleted; no Blender file was saved and nothing was rendered.",
        "Scene migration remains blocked until after material publication and owner approval.",
        "",
        f"- Publication ID: `{publication_id or 'unpublished'}`",
        f"- Migrate records: {migrate_count}",
        f"- Unresolved records: {unresolved_count}",
        f"- Enumerated records: {len(migration_records)}",
        "",
        "## Migration and unresolved records",
        "",
    ]
    if not migration_records:
        lines.append("- None.")
    for record in migration_records:
        inspection = record.blender_inspection
        lines.extend([f"### `{record.path}`", "", f"- Disposition: `{record.proposed_disposition}`"])
        for label, key in (
            ("Cameras", "cameras"),
            ("Rigs", "rigs"),
            ("Animations", "animations"),
            ("Lights", "lights"),
            ("Compositor nodes", "compositor_nodes"),
        ):
            values = inspection.get(key, []) if isinstance(inspection, Mapping) else []
            display = ", ".join(f"`{value}`" for value in values) if isinstance(values, list) and values else "none recorded"
            lines.append(f"- {label}: {display}")
        consumers = ", ".join(f"`{value}`" for value in record.consumers) or "none recorded"
        missing = inspection.get("missing_dependencies", []) if isinstance(inspection, Mapping) else []
        missing_display = ", ".join(f"`{value}`" for value in missing) if isinstance(missing, list) and missing else "none recorded"
        lines.extend([f"- Consumers: {consumers}", f"- Missing dependencies: {missing_display}", ""])
    return "\n".join(lines).rstrip() + "\n"


def atomic_write_text(destination: Path, text: str) -> None:
    content = text.encode("utf-8")
    temporary, identity = _prepare_atomic_bytes(destination, content)
    try:
        _replace_prepared(destination, temporary, content)
    finally:
        if temporary.exists():
            _remove_owned_file(temporary, identity)


def _path_snapshot(path: Path) -> tuple[tuple[int, ...], str] | None:
    if not path.exists():
        return None
    return _stat_identity(path.stat(follow_symlinks=False)), sha256_file(path)


def _acquire_publication_lock(root: Path, publication_id: str) -> tuple[Path, int, tuple[int, ...]]:
    lock_path = root / PurePosixPath(_PUBLICATION_LOCK)
    _guard_path(root, lock_path, allow_missing_leaf=True)
    try:
        descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise RuntimeError(f"publication lock already exists: {lock_path}") from error
    try:
        os.write(descriptor, (publication_id + "\n").encode("ascii"))
        os.fsync(descriptor)
        identity = _stat_identity(os.fstat(descriptor))
    except BaseException:
        os.close(descriptor)
        raise
    return lock_path, descriptor, identity


def _release_publication_lock(path: Path, descriptor: int, identity: tuple[int, ...]) -> None:
    current = path.stat(follow_symlinks=False)
    if _stat_identity(current)[:2] != identity[:2] or _stat_identity(os.fstat(descriptor))[:2] != identity[:2]:
        os.close(descriptor)
        raise RuntimeError("publication lock filesystem identity changed")
    os.close(descriptor)
    current = path.stat(follow_symlinks=False)
    if _stat_identity(current)[:2] != identity[:2]:
        raise RuntimeError("publication lock changed before cleanup")
    path.unlink()


def _artifact_authority(
    content: bytes, publication_id: str, schema: str
) -> dict[str, object]:
    return {
        "publication_id": publication_id,
        "schema": schema,
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest().upper(),
    }


def verify_published_outputs(
    asset_root: Path,
    inventory_path: Path | None = None,
    report_path: Path | None = None,
    graph_path: Path | None = None,
    render_inventory_path: Path | None = None,
    *,
    permitted_missing_paths: Sequence[str] = (),
) -> Mapping[str, object]:
    """Read back one committed publication and verify every bound child byte."""

    root = _canonical_root(asset_root)
    expected = _canonical_generated_paths(root)
    inventory_path = inventory_path or expected["manifests/blender-project-inventory.json"]
    report_path = report_path or expected["manifests/blender-project-migration-report.md"]
    graph_path = graph_path or expected["manifests/consumer-graph.json"]
    render_inventory_path = render_inventory_path or expected["manifests/render-generation-inventory.json"]
    paths = _validate_generated_destinations(
        root, inventory_path, report_path, graph_path, render_inventory_path
    )
    authority = json.loads(paths["manifests/blender-project-inventory.json"].read_text(encoding="utf-8"))
    if authority.get("schema") != INVENTORY_SCHEMA:
        raise RuntimeError("published inventory schema mismatch")
    publication_id = authority.get("publication_id")
    if not isinstance(publication_id, str) or not publication_id:
        raise RuntimeError("published inventory lacks a publication ID")
    generated = authority.get("generated_artifacts")
    expected_children = set(GENERATED_ARTIFACT_PATHS) - {"manifests/blender-project-inventory.json"}
    if not isinstance(generated, dict) or set(generated) != expected_children:
        raise RuntimeError("published inventory generated-artifact authority is incomplete")
    policy = authority.get("generated_path_policy")
    if not isinstance(policy, dict) or set(policy.get("excluded_paths", ())) != set(GENERATED_ARTIFACT_PATHS):
        raise RuntimeError("published inventory generated-path exclusion policy is invalid")
    for relative in expected_children:
        descriptor = generated[relative]
        if not isinstance(descriptor, dict):
            raise RuntimeError(f"invalid generated-artifact descriptor: {relative}")
        artifact = _guard_path(root, paths[relative])
        content = artifact.read_bytes()
        if int(descriptor.get("size", -1)) != len(content):
            raise RuntimeError(f"published generated artifact size mismatch: {relative}")
        if str(descriptor.get("sha256", "")).upper() != hashlib.sha256(content).hexdigest().upper():
            raise RuntimeError(f"published generated artifact hash mismatch: {relative}")
        if descriptor.get("publication_id") != publication_id:
            raise RuntimeError(f"published generated artifact authority ID mismatch: {relative}")
        if artifact.suffix.casefold() == ".json":
            child = json.loads(content)
            if child.get("publication_id") != publication_id:
                raise RuntimeError(f"published generated artifact payload ID mismatch: {relative}")
        elif f"Publication ID: `{publication_id}`" not in content.decode("utf-8"):
            raise RuntimeError(f"published migration report ID mismatch: {relative}")
    published_inventory = inventory_from_payload(authority)
    _verify_inventory_fresh(
        published_inventory,
        root,
        permitted_missing_paths=permitted_missing_paths,
    )
    return authority


def _publish_output_set(
    root: Path,
    inventory: InventoryManifest,
    graph_payload: Mapping[str, object],
    render_payload: Mapping[str, object],
    report_text: str,
    publication_id: str,
) -> None:
    paths = _canonical_generated_paths(root)
    child_contents = {
        "manifests/render-generation-inventory.json": _json_bytes(render_payload),
        "manifests/consumer-graph.json": _json_bytes(graph_payload),
        "manifests/blender-project-migration-report.md": report_text.encode("utf-8"),
    }
    child_schemas = {
        "manifests/render-generation-inventory.json": RENDER_INVENTORY_SCHEMA,
        "manifests/consumer-graph.json": "pimm-consumer-graph/v1",
        "manifests/blender-project-migration-report.md": "pimm-migration-report/v1",
    }
    generated_artifacts = {
        relative: _artifact_authority(content, publication_id, child_schemas[relative])
        for relative, content in child_contents.items()
    }
    inventory_content = _json_bytes(
        inventory_payload(
            inventory,
            publication_id=publication_id,
            generated_artifacts=generated_artifacts,
        )
    )
    contents = {**child_contents, "manifests/blender-project-inventory.json": inventory_content}
    lock_path, lock_descriptor, lock_identity = _acquire_publication_lock(root, publication_id)
    prepared: dict[str, tuple[Path, tuple[int, ...]]] = {}
    snapshots = {relative: _path_snapshot(paths[relative]) for relative in contents}
    publication_error: BaseException | None = None
    try:
        _verify_inventory_fresh(inventory, root)
        for relative, content in contents.items():
            prepared[relative] = _prepare_atomic_bytes(paths[relative], content)
        for relative in (
            "manifests/render-generation-inventory.json",
            "manifests/consumer-graph.json",
            "manifests/blender-project-migration-report.md",
        ):
            if _path_snapshot(paths[relative]) != snapshots[relative]:
                raise RuntimeError(f"competing publication changed output: {relative}")
            temporary, _identity = prepared.pop(relative)
            _replace_prepared(paths[relative], temporary, contents[relative])
        for relative in child_contents:
            descriptor = generated_artifacts[relative]
            if sha256_file(paths[relative]) != descriptor["sha256"]:
                raise RuntimeError(f"generated child drift before authority commit: {relative}")
        inventory_relative = "manifests/blender-project-inventory.json"
        if _path_snapshot(paths[inventory_relative]) != snapshots[inventory_relative]:
            raise RuntimeError("competing publication changed inventory authority")
        temporary, _identity = prepared.pop(inventory_relative)
        _replace_prepared(paths[inventory_relative], temporary, contents[inventory_relative])
        verify_published_outputs(root)
    except BaseException as error:
        publication_error = error
        raise
    finally:
        cleanup_error: BaseException | None = None
        for temporary, identity in prepared.values():
            if temporary.exists():
                try:
                    _remove_owned_file(temporary, identity)
                except BaseException as error:
                    if cleanup_error is None:
                        cleanup_error = error
        try:
            _release_publication_lock(lock_path, lock_descriptor, lock_identity)
        except BaseException as error:
            if cleanup_error is None:
                cleanup_error = error
        if publication_error is None and cleanup_error is not None:
            raise cleanup_error


def finalize_inventory(
    inventory_path: Path,
    report_path: Path = DEFAULT_REPORT,
    graph_path: Path = DEFAULT_GRAPH,
    render_inventory_path: Path = DEFAULT_RENDER_INVENTORY,
    repo_root: Path = REPOSITORY_ROOT,
    asset_root: Path = ASSET_ROOT,
) -> InventoryManifest:
    from scripts.blender.pimm_production.consumer_graph import (
        build_consumer_graph,
        classify_record,
        consumer_graph_payload,
    )

    asset_root = _canonical_root(asset_root)
    paths = _validate_generated_destinations(
        asset_root,
        inventory_path,
        report_path,
        graph_path,
        render_inventory_path,
    )
    inventory_path = paths["manifests/blender-project-inventory.json"]
    report_path = paths["manifests/blender-project-migration-report.md"]
    graph_path = paths["manifests/consumer-graph.json"]
    render_inventory_path = paths["manifests/render-generation-inventory.json"]
    inventory = inventory_from_payload(json.loads(inventory_path.read_text(encoding="utf-8")))
    _verify_inventory_fresh(inventory, asset_root, verify_hashes=False)
    reconciled_records: list[AssetRecord] = []
    for record in inventory.records:
        generations, releases = _membership(record.path)
        record = replace(
            record,
            generation_membership=generations,
            release_membership=releases,
        )
        if record.kind not in {"blend-project", "blend-recovery", "authoritative-master"}:
            reconciled_records.append(record)
            continue
        missing: list[str] = []
        unsafe: list[str] = []
        for dependency in record.dependencies:
            evidence = record.dependency_evidence.get(dependency, ())
            if evidence and all(item.startswith("output:") for item in evidence):
                continue
            dependency_path = Path(dependency)
            if dependency_path.is_absolute():
                unsafe.append(dependency)
                missing.append(dependency)
                continue
            pure_dependency = PurePosixPath(dependency.replace("\\", "/"))
            if any(part in {"", ".", ".."} for part in pure_dependency.parts):
                unsafe.append(dependency)
                missing.append(dependency)
                continue
            dependency_path = asset_root / pure_dependency
            try:
                guarded_dependency = _guard_path(
                    asset_root, dependency_path, allow_missing_leaf=True
                )
            except (OSError, ValueError):
                unsafe.append(dependency)
                missing.append(dependency)
                continue
            if not guarded_dependency.exists():
                missing.append(dependency)
        inspection = dict(record.blender_inspection)
        inspection["missing_dependencies"] = sorted(set(missing), key=str.casefold)
        inspection["unsafe_dependencies"] = sorted(set(unsafe), key=str.casefold)
        reconciled_records.append(replace(record, blender_inspection=inspection))
    inventory = InventoryManifest(
        tuple(reconciled_records),
        inventory.discovered_paths,
        inventory.root,
        inventory.root_identity,
    )
    graph = build_consumer_graph(repo_root, asset_root, inventory.records)
    records = tuple(
        replace(
            record,
            consumers=graph.consumers.get(record.path, ()),
            proposed_disposition=classify_record(record, graph),
        )
        for record in inventory.records
    )
    finalized = InventoryManifest(
        records,
        inventory.discovered_paths,
        inventory.root,
        inventory.root_identity,
    )
    publication_id = uuid.uuid4().hex
    render_payload = render_generation_payload(finalized, publication_id=publication_id)
    graph_payload = consumer_graph_payload(graph, publication_id=publication_id)
    report_text = migration_report(finalized, publication_id=publication_id)
    _publish_output_set(
        asset_root,
        finalized,
        graph_payload,
        render_payload,
        report_text,
        publication_id,
    )
    return finalized


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true")
    group.add_argument("--enrich", action="store_true")
    group.add_argument("--finalize", action="store_true")
    parser.add_argument("--root", type=Path, default=ASSET_ROOT)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--render-inventory", type=Path, default=DEFAULT_RENDER_INVENTORY)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(blender_args())


def main() -> None:
    args = parse_args()
    root = _canonical_root(args.root)
    expected_inventory = _canonical_generated_paths(root)["manifests/blender-project-inventory.json"]
    if _absolute_lexical(args.inventory) != _absolute_lexical(expected_inventory):
        raise ValueError(f"canonical generated output required for inventory: {expected_inventory}")
    if args.scan:
        inventory = inventory_workspace(root)
        atomic_write_json(args.inventory, inventory_payload(inventory))
    elif args.enrich:
        inventory = enrich_with_blender(args.inventory, root)
    else:
        inventory = finalize_inventory(
            args.inventory,
            args.report,
            args.graph,
            args.render_inventory,
            args.repo_root,
            root,
        )
    print(f"PIMM_LEGACY_INVENTORY records={len(inventory.records)}")


if __name__ == "__main__":
    main()
