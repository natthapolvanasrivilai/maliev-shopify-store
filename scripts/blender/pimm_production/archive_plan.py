"""Plan, apply, and restore reversible PIMM pending-delete archive batches.

The CLI defaults to ``plan``. Planning may publish one immutable JSON proposal,
but it never moves, renames, deletes, saves, or renders an active asset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.blender.master_assets.pimm_legacy_inventory import (  # noqa: E402
    ASSET_ROOT,
    DEFAULT_GRAPH,
    DEFAULT_INVENTORY,
    DEFAULT_RENDER_INVENTORY,
    AssetRecord,
    InventoryManifest,
    inventory_from_payload,
    inventory_payload,
)
from scripts.blender.pimm_production.consumer_graph import (  # noqa: E402
    CONSUMER_GRAPH_SCHEMA,
    ConsumerGraph,
    consumer_graph_payload,
)


ARCHIVE_PLAN_SCHEMA = "pimm-archive-plan/v1"
ARCHIVE_APPROVAL_SCHEMA = "pimm-archive-plan-approval/v1"
ARCHIVE_MANIFEST_SCHEMA = "pimm-archive-manifest/v1"
_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_BATCH_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_REPARSE_ATTRIBUTE = 0x400
_PROTECTED_TOKENS = frozenset(
    {"source", "sources", "master", "masters", "material", "materials", "artwork", "scripts", "calibrated", "approved", "release", "releases"}
)
_PROTECTED_KINDS = frozenset({"authoritative-master", "artwork", "script", "texture"})


def _canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _identity(status: os.stat_result) -> tuple[int, int, int, int]:
    return (int(status.st_dev), int(status.st_ino), int(status.st_ctime_ns), int(status.st_size))


def _is_reparse(path: Path) -> bool:
    status = os.lstat(path)
    return stat.S_ISLNK(status.st_mode) or bool(
        int(getattr(status, "st_file_attributes", 0)) & _REPARSE_ATTRIBUTE
    )


def _reject_reparse_ancestors(path: Path, label: str, *, allow_missing: bool = True) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if not current.exists() and not current.is_symlink():
            if allow_missing:
                continue
            raise ValueError(f"{label} does not exist: {current}")
        if _is_reparse(current):
            raise ValueError(f"{label} traverses a symlink, junction, or reparse point: {current}")


def _absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(Path(path)))


def _within(path: Path, root: Path) -> bool:
    try:
        return os.path.normcase(os.path.commonpath((str(_absolute(path)), str(_absolute(root))))) == os.path.normcase(
            str(_absolute(root))
        )
    except ValueError:
        return False


def _canonical_relative(value: str, label: str) -> str:
    normalized = str(value).replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} must be a contained relative path")
    return normalized


def _canonical_utc(value: str, label: str) -> None:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise ValueError(f"{label} must be canonical UTC ending in Z")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError(f"{label} must be a real canonical UTC instant") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError(f"{label} must be canonical UTC ending in Z")


@dataclass(frozen=True)
class ArchiveItem:
    action: str
    relative_path: str
    source: str
    destination: str
    sha256: str
    size: int
    mtime_ns: int
    filesystem_identity: tuple[int, ...]
    kind: str
    disposition: str
    reason: str
    replacement: str
    consumer_evidence: tuple[str, ...] = ()
    unique_content_evidence: Mapping[str, object] = field(default_factory=dict)
    directory_root: str = ""
    directory_inventory: tuple[str, ...] = ()
    generation_membership: tuple[str, ...] = ()
    release_membership: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        for key in (
            "filesystem_identity",
            "consumer_evidence",
            "directory_inventory",
            "generation_membership",
            "release_membership",
        ):
            payload[key] = list(payload[key])
        payload["unique_content_evidence"] = dict(self.unique_content_evidence)
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ArchiveItem":
        required = {field.name for field in cls.__dataclass_fields__.values()}
        if set(payload) != required:
            raise ValueError("archive item fields are incomplete or unknown")
        values = dict(payload)
        for key in (
            "filesystem_identity",
            "consumer_evidence",
            "directory_inventory",
            "generation_membership",
            "release_membership",
        ):
            value = values[key]
            if not isinstance(value, list):
                raise ValueError(f"archive item {key} must be a list")
            values[key] = tuple(value)
        if not isinstance(values["unique_content_evidence"], Mapping):
            raise ValueError("archive item unique-content evidence must be an object")
        return cls(**values)


@dataclass(frozen=True)
class ArchivePlan:
    batch_id: str
    created_at_utc: str
    active_root: str
    archive_root: str
    publication_id: str
    inventory_sha256: str
    consumer_graph_sha256: str
    render_inventory_sha256: str
    inventory_root_identity: tuple[int, ...]
    discovered_path_count: int
    items: tuple[ArchiveItem, ...]
    blockers: tuple[str, ...] = ()
    schema: str = ARCHIVE_PLAN_SCHEMA
    schema_version: int = 1

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "created_at_utc": self.created_at_utc,
            "active_root": self.active_root,
            "archive_root": self.archive_root,
            "publication_id": self.publication_id,
            "inventory_sha256": self.inventory_sha256,
            "consumer_graph_sha256": self.consumer_graph_sha256,
            "render_inventory_sha256": self.render_inventory_sha256,
            "inventory_root_identity": list(self.inventory_root_identity),
            "discovered_path_count": self.discovered_path_count,
            "items": [item.to_payload() for item in self.items],
            "blockers": list(self.blockers),
            "summary": {
                "item_count": len(self.items),
                "total_bytes": sum(item.size for item in self.items),
                "highest_risk_items": [
                    {"path": item.relative_path, "risk": "recovery-copy archive"}
                    for item in sorted(self.items, key=lambda entry: entry.size, reverse=True)[:5]
                ],
                "destination": self.archive_root,
                "operation": "reversible-archive-only",
            },
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ArchivePlan":
        expected = {
            "schema", "schema_version", "batch_id", "created_at_utc", "active_root",
            "archive_root", "publication_id", "inventory_sha256", "consumer_graph_sha256",
            "render_inventory_sha256", "inventory_root_identity", "discovered_path_count",
            "items", "blockers", "summary",
        }
        if set(payload) != expected:
            raise ValueError("archive plan fields are incomplete or unknown")
        if payload.get("schema") != ARCHIVE_PLAN_SCHEMA or payload.get("schema_version") != 1:
            raise ValueError("archive plan schema must be pimm-archive-plan/v1 version 1")
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise ValueError("archive plan items must be a list")
        raw_identity = payload.get("inventory_root_identity")
        raw_blockers = payload.get("blockers")
        if not isinstance(raw_identity, list) or not isinstance(raw_blockers, list):
            raise ValueError("archive plan authority metadata is invalid")
        plan = cls(
            batch_id=str(payload["batch_id"]),
            created_at_utc=str(payload["created_at_utc"]),
            active_root=str(payload["active_root"]),
            archive_root=str(payload["archive_root"]),
            publication_id=str(payload["publication_id"]),
            inventory_sha256=str(payload["inventory_sha256"]),
            consumer_graph_sha256=str(payload["consumer_graph_sha256"]),
            render_inventory_sha256=str(payload["render_inventory_sha256"]),
            inventory_root_identity=tuple(int(value) for value in raw_identity),
            discovered_path_count=int(payload["discovered_path_count"]),
            items=tuple(ArchiveItem.from_payload(item) for item in raw_items),
            blockers=tuple(str(value) for value in raw_blockers),
        )
        expected_summary = plan.to_payload()["summary"]
        if payload.get("summary") != expected_summary:
            raise ValueError("archive plan summary does not match its exact items")
        return plan


@dataclass(frozen=True)
class ArchiveFileResult:
    source: str
    destination: str
    sha256: str
    size: int
    mtime_ns: int
    move_mode: str


@dataclass(frozen=True)
class ArchiveResult:
    manifest_path: Path
    moved: tuple[ArchiveFileResult, ...] = ()
    restored: tuple[ArchiveFileResult, ...] = ()
    rolled_back: tuple[ArchiveFileResult, ...] = ()


def _unique_evidence(record: AssetRecord) -> dict[str, object]:
    inspection = record.blender_inspection
    return {
        "record_unique_content": bool(record.unique_content),
        "object_count": int(inspection.get("object_count", 0) or 0),
        "mesh_datablock_count": int(inspection.get("mesh_datablock_count", 0) or 0),
        "material_count": int(inspection.get("material_count", 0) or 0),
        "migration_complete": not bool(record.unique_content),
    }


def _has_unique_content(record: AssetRecord) -> bool:
    evidence = _unique_evidence(record)
    return bool(
        evidence["record_unique_content"]
        or evidence["object_count"]
        or evidence["mesh_datablock_count"]
        or evidence["material_count"]
    )


def _is_protected(record: AssetRecord) -> bool:
    parts = {part.casefold() for part in PurePosixPath(record.path).parts}
    return bool(
        record.kind.casefold() in _PROTECTED_KINDS
        or parts & _PROTECTED_TOKENS
        or record.generation_membership
        or record.release_membership
        or record.proposed_disposition in {"authoritative", "active-linked-scene", "migrate", "unresolved"}
    )


def _ambiguous_for(path: str, graph: ConsumerGraph) -> bool:
    folded = path.casefold()
    return any(
        folded in {str(candidate).casefold() for candidate in value.get("candidate_paths", ())}
        for value in graph.ambiguous_references.values()
    )


def _replacement_path(record: AssetRecord, records: Mapping[str, AssetRecord]) -> str | None:
    if not record.path.casefold().endswith(".blend1"):
        return None
    replacement = record.path[:-1]
    return replacement if replacement.casefold() in records else None


def _directory_records(path: str, inventory: InventoryManifest) -> tuple[str, ...]:
    parent = PurePosixPath(path).parent
    prefix = "" if str(parent) == "." else parent.as_posix().rstrip("/") + "/"
    return tuple(
        sorted(
            (record.path for record in inventory.records if record.path.startswith(prefix)),
            key=str.casefold,
        )
    )


def build_archive_plan(
    inventory: InventoryManifest,
    graph: ConsumerGraph,
    batch_id: str,
) -> ArchivePlan:
    """Build a conservative proposal from exact Task 7 pending-archive records."""

    if _BATCH_ID.fullmatch(batch_id) is None:
        raise ValueError("archive batch ID must be lowercase kebab-case")
    active_root = _absolute(inventory.root)
    date = datetime.now().astimezone().strftime("%Y-%m-%d")
    archive_root = active_root.parent / f"{active_root.name}-archive" / "pending-delete" / f"{date}-{batch_id}"
    records = {record.path.casefold(): record for record in inventory.records}
    items: list[ArchiveItem] = []
    for record in sorted(inventory.records, key=lambda value: value.path.casefold()):
        consumers = tuple(sorted(set(record.consumers) | set(graph.consumers.get(record.path, ())), key=str.casefold))
        replacement_path = _replacement_path(record, records)
        eligible = (
            record.proposed_disposition == "pending-archive"
            and record.kind == "blend-recovery"
            and record.path.casefold().endswith(".blend1")
            and not consumers
            and not _has_unique_content(record)
            and not _ambiguous_for(record.path, graph)
            and not _is_protected(record)
            and replacement_path is not None
        )
        if not eligible:
            continue
        relative = _canonical_relative(record.path, "archive record path")
        source = active_root / PurePosixPath(relative)
        destination = archive_root / PurePosixPath(relative)
        directory_relative = PurePosixPath(relative).parent.as_posix()
        items.append(
            ArchiveItem(
                action="archive",
                relative_path=relative,
                source=str(source),
                destination=str(destination),
                sha256=record.sha256.upper(),
                size=record.size,
                mtime_ns=record.mtime_ns,
                filesystem_identity=record.filesystem_identity,
                kind=record.kind,
                disposition=record.proposed_disposition,
                reason="Task 7 exact pending-archive Blender recovery copy with no consumers or unique content",
                replacement=replacement_path or "",
                consumer_evidence=consumers,
                unique_content_evidence=_unique_evidence(record),
                directory_root=directory_relative,
                directory_inventory=_directory_records(record.path, inventory),
                generation_membership=record.generation_membership,
                release_membership=record.release_membership,
            )
        )
    blockers: tuple[str, ...] = ()
    if not items:
        pending_count = sum(record.proposed_disposition == "pending-archive" for record in inventory.records)
        blockers = (
            f"zero safe candidates: inventory contains {pending_count} exact pending-archive records after protected-role, consumer, ambiguity, unique-content, replacement, and completeness gates",
        )
    model_inventory_sha = _sha256_bytes(_canonical_json_bytes(inventory_payload(inventory)))
    model_graph_sha = _sha256_bytes(_canonical_json_bytes(consumer_graph_payload(graph)))
    return ArchivePlan(
        batch_id=batch_id,
        created_at_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        active_root=str(active_root),
        archive_root=str(archive_root),
        publication_id="unpublished-fixture",
        inventory_sha256=model_inventory_sha,
        consumer_graph_sha256=model_graph_sha,
        render_inventory_sha256="",
        inventory_root_identity=inventory.root_identity,
        discovered_path_count=len(inventory.discovered_paths),
        items=tuple(items),
        blockers=blockers,
    )


def _validate_plan_structure(plan: ArchivePlan) -> list[str]:
    errors: list[str] = []
    if plan.schema != ARCHIVE_PLAN_SCHEMA or plan.schema_version != 1:
        errors.append("archive plan schema is invalid")
    if _BATCH_ID.fullmatch(plan.batch_id) is None:
        errors.append("archive batch ID is invalid")
    try:
        _canonical_utc(plan.created_at_utc, "archive plan created_at_utc")
    except ValueError as error:
        errors.append(str(error))
    active_root = _absolute(plan.active_root)
    archive_root = _absolute(plan.archive_root)
    if _within(archive_root, active_root):
        errors.append("archive destination must be outside active root")
    expected_parent = active_root.parent / f"{active_root.name}-archive" / "pending-delete"
    expected_leaf = re.fullmatch(
        rf"[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}-{re.escape(plan.batch_id)}",
        archive_root.name,
    )
    if archive_root.parent != expected_parent or expected_leaf is None:
        errors.append("archive destination is outside the canonical pending-delete root")
    seen_sources: set[str] = set()
    seen_destinations: set[str] = set()
    for item in plan.items:
        if item.action == "delete":
            errors.append(f"{item.relative_path}: delete action is forbidden")
        elif item.action != "archive":
            errors.append(f"{item.relative_path}: only archive action is allowed")
        try:
            relative = _canonical_relative(item.relative_path, "archive item path")
        except ValueError as error:
            errors.append(str(error))
            continue
        expected_source = active_root / PurePosixPath(relative)
        expected_destination = archive_root / PurePosixPath(relative)
        if _absolute(item.source) != _absolute(expected_source) or not _within(_absolute(item.source), active_root):
            errors.append(f"{relative}: source path containment is invalid")
        if _absolute(item.destination) != _absolute(expected_destination) or not _within(
            _absolute(item.destination), archive_root
        ):
            errors.append(f"{relative}: destination path containment is invalid")
        source_key = os.path.normcase(str(_absolute(item.source)))
        destination_key = os.path.normcase(str(_absolute(item.destination)))
        if source_key in seen_sources or destination_key in seen_destinations:
            errors.append(f"{relative}: duplicate source or destination")
        seen_sources.add(source_key)
        seen_destinations.add(destination_key)
        if item.mtime_ns <= 0:
            errors.append(f"{relative}: missing timestamp")
        if item.size < 0 or _SHA256.fullmatch(item.sha256) is None:
            errors.append(f"{relative}: size or SHA-256 is invalid")
        if item.disposition != "pending-archive":
            errors.append(f"{relative}: disposition is not pending-archive")
        if item.kind != "blend-recovery" or not relative.casefold().endswith(".blend1"):
            errors.append(f"{relative}: only exact Blender recovery records are supported")
        if item.consumer_evidence:
            errors.append(f"{relative}: active consumer evidence is present")
        if any(bool(item.unique_content_evidence.get(key)) for key in ("record_unique_content", "object_count", "mesh_datablock_count", "material_count")):
            errors.append(f"{relative}: unique content not migrated")
        if item.unique_content_evidence.get("migration_complete") is not True:
            errors.append(f"{relative}: unique-content migration evidence is incomplete")
        if item.generation_membership or item.release_membership:
            errors.append(f"{relative}: approved/release or generation role is protected")
        parts = {part.casefold() for part in PurePosixPath(relative).parts}
        if parts & _PROTECTED_TOKENS or item.kind.casefold() in _PROTECTED_KINDS:
            errors.append(f"{relative}: protected source/master/material/artwork/script role")
        expected_directory = PurePosixPath(relative).parent.as_posix()
        if item.directory_root != expected_directory:
            errors.append(f"{relative}: directory inventory root is invalid")
        if relative not in item.directory_inventory:
            errors.append(f"{relative}: directory inventory is incomplete")
    return errors


def validate_archive_plan(
    plan: ArchivePlan,
    inventory: InventoryManifest,
    graph: ConsumerGraph,
) -> list[str]:
    """Return all fail-closed plan/inventory/graph contract errors."""

    errors = _validate_plan_structure(plan)
    active_root = _absolute(inventory.root)
    if _absolute(plan.active_root) != active_root:
        errors.append("archive plan active root does not match inventory")
    if plan.discovered_path_count != len(inventory.discovered_paths):
        errors.append("archive plan discovered path count does not match inventory")
    records = {record.path.casefold(): record for record in inventory.records}
    for item in plan.items:
        record = records.get(item.relative_path.casefold())
        if record is None:
            errors.append(f"{item.relative_path}: record is absent from inventory")
            continue
        if record.proposed_disposition != "pending-archive":
            errors.append(f"{item.relative_path}: record is not exact pending-archive")
        consumers = tuple(sorted(set(record.consumers) | set(graph.consumers.get(record.path, ())), key=str.casefold))
        if consumers:
            errors.append(f"{item.relative_path}: active consumer: {', '.join(consumers)}")
        if _has_unique_content(record):
            errors.append(f"{item.relative_path}: unique content not migrated")
        if _ambiguous_for(record.path, graph):
            errors.append(f"{item.relative_path}: ambiguous reference protects the record")
        if _is_protected(record):
            errors.append(f"{item.relative_path}: record has a protected role")
        if (
            record.size != item.size
            or record.mtime_ns != item.mtime_ns
            or record.sha256.upper() != item.sha256.upper()
            or record.filesystem_identity != item.filesystem_identity
        ):
            errors.append(f"{item.relative_path}: inventory identity evidence drift")
        expected_directory = _directory_records(record.path, inventory)
        if tuple(item.directory_inventory) != expected_directory:
            errors.append(f"{item.relative_path}: directory inventory is incomplete")
        replacement = _replacement_path(record, records)
        if replacement is None or replacement != item.replacement:
            errors.append(f"{item.relative_path}: replacement evidence is invalid")
    return errors


def _stable_read(path: Path, label: str) -> tuple[bytes, tuple[int, int, int, int]]:
    _reject_reparse_ancestors(path, label, allow_missing=False)
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"{label} must be one regular single-link file")
    content = path.read_bytes()
    after = path.stat(follow_symlinks=False)
    if _identity(before) != _identity(after) or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError(f"{label} changed while reading")
    return content, _identity(after)


def _load_plan(path: Path) -> tuple[ArchivePlan, str]:
    content, _ = _stable_read(path, "archive plan")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"archive plan is not canonical UTF-8 JSON: {error}") from error
    if not isinstance(payload, Mapping):
        raise ValueError("archive plan must be a JSON object")
    plan = ArchivePlan.from_payload(payload)
    errors = _validate_plan_structure(plan)
    if errors:
        raise ValueError("; ".join(errors))
    return plan, _sha256_bytes(content)


def _validate_approval(path: Path, plan_path: Path, plan: ArchivePlan, plan_sha256: str) -> str:
    content, _ = _stable_read(path, "archive approval")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"archive approval is not canonical UTF-8 JSON: {error}") from error
    expected = {
        "schema", "schema_version", "batch_id", "plan_path",
        "approved_archive_plan_sha256", "decision", "authority", "owner", "created_at_utc",
    }
    if not isinstance(payload, Mapping) or set(payload) != expected:
        raise ValueError("archive approval fields are incomplete or unknown")
    try:
        _canonical_utc(str(payload.get("created_at_utc")), "archive approval created_at_utc")
    except ValueError as error:
        raise ValueError(str(error)) from error
    if (
        payload.get("schema") != ARCHIVE_APPROVAL_SCHEMA
        or payload.get("schema_version") != 1
        or payload.get("decision") != "approved"
        or payload.get("authority") != "owner"
        or not str(payload.get("owner", "")).strip()
        or payload.get("batch_id") != plan.batch_id
        or _absolute(str(payload.get("plan_path"))) != _absolute(plan_path)
        or str(payload.get("approved_archive_plan_sha256", "")).upper() != plan_sha256
    ):
        raise ValueError("approval must contain the exact approved archive-plan SHA-256 and owner authority")
    return _sha256_bytes(content)


def _live_directory_inventory(item: ArchiveItem, active_root: Path) -> tuple[str, ...]:
    directory = active_root if item.directory_root == "." else active_root / PurePosixPath(item.directory_root)
    _reject_reparse_ancestors(directory, "archive source directory", allow_missing=False)
    values: list[str] = []
    for path in directory.rglob("*"):
        if _is_reparse(path):
            raise ValueError(f"archive source directory traverses a reparse entry: {path}")
        if path.is_file():
            values.append(path.relative_to(active_root).as_posix())
    return tuple(sorted(values, key=str.casefold))


def _verify_file(path: Path, item: ArchiveItem, label: str, *, require_identity: bool) -> None:
    _reject_reparse_ancestors(path, label, allow_missing=False)
    status = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1:
        raise ValueError(f"{label} must be one regular single-link file")
    if status.st_size != item.size:
        raise ValueError(f"{label} size drift")
    if status.st_mtime_ns != item.mtime_ns:
        raise ValueError(f"{label} mtime drift")
    if require_identity and tuple(item.filesystem_identity) != _identity(status):
        raise ValueError(f"{label} identity drift")
    if _sha256_file(path) != item.sha256.upper():
        raise ValueError(f"{label} hash drift")
    after = path.stat(follow_symlinks=False)
    if _identity(status) != _identity(after) or status.st_mtime_ns != after.st_mtime_ns:
        raise ValueError(f"{label} changed while hashing")


def _preflight_apply(plan: ArchivePlan) -> None:
    active_root = _absolute(plan.active_root)
    _reject_reparse_ancestors(active_root, "active root", allow_missing=False)
    for item in plan.items:
        source = _absolute(item.source)
        destination = _absolute(item.destination)
        _verify_file(source, item, "source", require_identity=True)
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"destination already exists: {destination}")
        _reject_reparse_ancestors(destination.parent, "archive destination", allow_missing=True)
        if _live_directory_inventory(item, active_root) != tuple(item.directory_inventory):
            raise ValueError(f"{item.relative_path}: directory inventory is incomplete")


def _same_volume(source: Path, destination: Path) -> bool:
    current = destination.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    return source.stat().st_dev == current.stat().st_dev


def _create_owned_temporary(path: Path) -> tuple[int, tuple[int, int, int, int]]:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_BINARY", 0))
    return descriptor, _identity(os.fstat(descriptor))


def _remove_if_exact(path: Path, identity: tuple[int, int, int, int]) -> bool:
    try:
        current = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return True
    # Size/ctime legitimately change while this owned staging inode is filled.
    # Device+inode still distinguish a pathname replacement on local filesystems.
    if _identity(current)[:2] != identity[:2]:
        return False
    path.unlink()
    return True


def _copy_source_to_temporary(source: Path, temporary: Path, item: ArchiveItem) -> None:
    with source.open("rb") as input_stream, temporary.open("wb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream, 8 * 1024 * 1024)
        output_stream.flush()
        os.fsync(output_stream.fileno())
    os.utime(temporary, ns=(item.mtime_ns, item.mtime_ns))


def _unlink_verified_source(source: Path, item: ArchiveItem) -> None:
    _verify_file(source, item, "source", require_identity=True)
    source.unlink()


def _move_item(item: ArchiveItem, manifest_tmp: Path) -> str:
    source = _absolute(item.source)
    destination = _absolute(item.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _reject_reparse_ancestors(destination.parent, "archive destination", allow_missing=False)
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"destination already exists: {destination}")
    _verify_file(source, item, "source", require_identity=True)
    if _same_volume(source, destination):
        os.replace(source, destination)
        try:
            _verify_file(destination, item, "archive destination", require_identity=False)
        except BaseException:
            if not source.exists():
                os.replace(destination, source)
            raise
        return "atomic-rename"

    temporary = destination.parent / f".{destination.name}.archive-copy-{uuid.uuid4().hex}"
    descriptor, temporary_identity = _create_owned_temporary(temporary)
    os.close(descriptor)
    moved_identity: tuple[int, int, int, int] | None = None
    try:
        _copy_source_to_temporary(source, temporary, item)
        _verify_file(temporary, item, "archive copy", require_identity=False)
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"destination already exists: {destination}")
        os.rename(temporary, destination)
        moved_identity = _identity(destination.stat(follow_symlinks=False))
        _verify_file(destination, item, "archive destination", require_identity=False)
        _unlink_verified_source(source, item)
        return "copy-verify-unlink"
    except BaseException:
        if temporary.exists() and not _remove_if_exact(temporary, temporary_identity):
            pass
        if moved_identity is not None and destination.exists() and source.exists():
            _remove_if_exact(destination, moved_identity)
        raise


def _result_payload(result: ArchiveFileResult) -> dict[str, object]:
    return asdict(result)


def _write_manifest_tmp(path: Path, payload: Mapping[str, object], *, create: bool) -> None:
    content = _canonical_json_bytes(payload)
    mode = "xb" if create else "wb"
    with path.open(mode) as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _restore_one(result: ArchiveFileResult) -> ArchiveFileResult:
    source = _absolute(result.source)
    destination = _absolute(result.destination)
    if source.exists() or source.is_symlink():
        raise ValueError(f"restore destination collision: {source}")
    item = ArchiveItem(
        action="archive", relative_path=source.name, source=str(source), destination=str(destination),
        sha256=result.sha256, size=result.size, mtime_ns=result.mtime_ns, filesystem_identity=(),
        kind="blend-recovery", disposition="pending-archive", reason="restore", replacement="restored",
        unique_content_evidence={"migration_complete": True}, directory_root=".", directory_inventory=(source.name,),
    )
    _verify_file(destination, item, "archived source", require_identity=False)
    source.parent.mkdir(parents=True, exist_ok=True)
    if _same_volume(destination, source):
        os.replace(destination, source)
        mode = "atomic-rename"
    else:
        temporary = source.parent / f".{source.name}.restore-copy-{uuid.uuid4().hex}"
        descriptor, temporary_identity = _create_owned_temporary(temporary)
        os.close(descriptor)
        try:
            _copy_source_to_temporary(destination, temporary, item)
            _verify_file(temporary, item, "restore copy", require_identity=False)
            os.rename(temporary, source)
            _verify_file(source, item, "restored source", require_identity=False)
            destination_identity = _identity(destination.stat(follow_symlinks=False))
            if not _remove_if_exact(destination, destination_identity):
                raise ValueError("archived source pathname was replaced before exact cleanup")
            mode = "copy-verify-unlink"
        except BaseException:
            if temporary.exists():
                _remove_if_exact(temporary, temporary_identity)
            raise
    _verify_file(source, item, "restored source", require_identity=False)
    return ArchiveFileResult(str(source), str(destination), result.sha256, result.size, result.mtime_ns, mode)


def _rollback_moved(results: Sequence[ArchiveFileResult]) -> tuple[ArchiveFileResult, ...]:
    restored: list[ArchiveFileResult] = []
    for result in reversed(results):
        try:
            restored.append(_restore_one(result))
        except (OSError, ValueError):
            # Fail closed: never remove or overwrite a competing pathname.
            continue
    return tuple(restored)


def apply_archive_plan(plan_path: Path, approval_path: Path) -> ArchiveResult:
    """Apply one exact owner-approved plan, rolling completed moves back on failure."""

    plan_path = _absolute(plan_path)
    approval_path = _absolute(approval_path)
    plan, plan_sha256 = _load_plan(plan_path)
    approval_sha256 = _validate_approval(approval_path, plan_path, plan, plan_sha256)
    if not plan.items:
        raise ValueError("archive plan contains no movable items; no-op plans cannot be applied")
    _preflight_apply(plan)
    archive_root = _absolute(plan.archive_root)
    archive_root.mkdir(parents=True, exist_ok=False)
    _reject_reparse_ancestors(archive_root, "archive root", allow_missing=False)
    manifest_tmp = archive_root / "archive-manifest.json.tmp"
    manifest_path = archive_root / "archive-manifest.json"
    base_payload: dict[str, object] = {
        "schema": ARCHIVE_MANIFEST_SCHEMA,
        "schema_version": 1,
        "batch_id": plan.batch_id,
        "status": "pending",
        "active_root": plan.active_root,
        "archive_root": plan.archive_root,
        "plan_path": str(plan_path),
        "plan_sha256": plan_sha256,
        "approval_path": str(approval_path),
        "approval_sha256": approval_sha256,
        "items": [],
    }
    _write_manifest_tmp(manifest_tmp, base_payload, create=True)
    moved: list[ArchiveFileResult] = []
    try:
        for item in plan.items:
            mode = _move_item(item, manifest_tmp)
            moved.append(
                ArchiveFileResult(item.source, item.destination, item.sha256, item.size, item.mtime_ns, mode)
            )
            base_payload["items"] = [_result_payload(result) for result in moved]
            _write_manifest_tmp(manifest_tmp, base_payload, create=False)
        base_payload["status"] = "archived"
        _write_manifest_tmp(manifest_tmp, base_payload, create=False)
        if manifest_path.exists() or manifest_path.is_symlink():
            raise ValueError("immutable archive manifest already exists")
        os.rename(manifest_tmp, manifest_path)
        persisted, _ = _stable_read(manifest_path, "archive manifest")
        if persisted != _canonical_json_bytes(base_payload):
            raise ValueError("archive manifest publication drift")
        return ArchiveResult(manifest_path=manifest_path, moved=tuple(moved))
    except BaseException as error:
        rolled_back = _rollback_moved(moved)
        failure_payload = dict(base_payload)
        failure_payload["status"] = "failed-rolled-back"
        failure_payload["error"] = f"{type(error).__name__}: {error}"
        failure_payload["rolled_back"] = [_result_payload(result) for result in rolled_back]
        if manifest_tmp.exists():
            _write_manifest_tmp(manifest_tmp, failure_payload, create=False)
        raise


def restore_archive_batch(manifest_path: Path) -> ArchiveResult:
    """Restore an archived batch without overwriting any current active path."""

    manifest_path = _absolute(manifest_path)
    content, _ = _stable_read(manifest_path, "archive manifest")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"archive manifest is not canonical UTF-8 JSON: {error}") from error
    required = {
        "schema", "schema_version", "batch_id", "status", "active_root", "archive_root",
        "plan_path", "plan_sha256", "approval_path", "approval_sha256", "items",
    }
    if not isinstance(payload, Mapping) or set(payload) != required:
        raise ValueError("archive manifest fields are incomplete or unknown")
    if payload.get("schema") != ARCHIVE_MANIFEST_SCHEMA or payload.get("schema_version") != 1 or payload.get("status") != "archived":
        raise ValueError("only a complete immutable archive manifest can be restored")
    active_root = _absolute(str(payload["active_root"]))
    archive_root = _absolute(str(payload["archive_root"]))
    if not _within(manifest_path, archive_root):
        raise ValueError("archive manifest is outside its archive root")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("archive manifest items must be a list")
    results: list[ArchiveFileResult] = []
    for raw in raw_items:
        if not isinstance(raw, Mapping) or set(raw) != {"source", "destination", "sha256", "size", "mtime_ns", "move_mode"}:
            raise ValueError("archive manifest item fields are invalid")
        result = ArchiveFileResult(
            source=str(raw["source"]), destination=str(raw["destination"]), sha256=str(raw["sha256"]).upper(),
            size=int(raw["size"]), mtime_ns=int(raw["mtime_ns"]), move_mode=str(raw["move_mode"]),
        )
        if not _within(_absolute(result.source), active_root) or not _within(_absolute(result.destination), archive_root):
            raise ValueError("archive restore mapping escapes its authority roots")
        results.append(result)
    for result in results:
        if _absolute(result.source).exists() or _absolute(result.source).is_symlink():
            raise ValueError(f"restore destination collision: {result.source}")
        item = ArchiveItem(
            action="archive", relative_path=Path(result.source).name, source=result.source, destination=result.destination,
            sha256=result.sha256, size=result.size, mtime_ns=result.mtime_ns, filesystem_identity=(), kind="blend-recovery",
            disposition="pending-archive", reason="restore", replacement="restored",
            unique_content_evidence={"migration_complete": True}, directory_root=".", directory_inventory=(Path(result.source).name,),
        )
        _verify_file(_absolute(result.destination), item, "archived source", require_identity=False)
    restored: list[ArchiveFileResult] = []
    try:
        for result in results:
            restored.append(_restore_one(result))
    except BaseException:
        # Restore is itself reversible: move already restored records back to archive.
        for result in reversed(restored):
            source = _absolute(result.source)
            destination = _absolute(result.destination)
            if source.exists() and not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, destination)
        raise
    return ArchiveResult(manifest_path=manifest_path, restored=tuple(restored))


def _graph_from_payload(payload: Mapping[str, object]) -> ConsumerGraph:
    if payload.get("schema") != CONSUMER_GRAPH_SCHEMA:
        raise ValueError("consumer graph schema must be pimm-consumer-graph/v1")
    return ConsumerGraph(
        consumers=payload.get("consumers", {}),
        producers=payload.get("producers", {}),
        unresolved_references=payload.get("unresolved_references", {}),
        ambiguous_references=payload.get("ambiguous_references", {}),
        authoritative_paths=tuple(payload.get("authoritative_paths", ())),
    )


def _read_json(path: Path, label: str) -> tuple[Mapping[str, object], bytes]:
    content, _ = _stable_read(path, label)
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not canonical UTF-8 JSON: {error}") from error
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return payload, content


def _publish_immutable_plan(path: Path, plan: ArchivePlan) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_reparse_ancestors(path.parent, "archive plan directory", allow_missing=False)
    if path.exists() or path.is_symlink():
        raise ValueError(f"immutable archive plan already exists: {path}")
    content = _canonical_json_bytes(plan.to_payload())
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.pending"
    descriptor, identity = _create_owned_temporary(temporary)
    try:
        os.write(descriptor, content)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        if path.exists() or path.is_symlink():
            raise ValueError(f"immutable archive plan already exists: {path}")
        os.rename(temporary, path)
    except BaseException:
        if temporary.exists():
            _remove_if_exact(temporary, identity)
        raise
    persisted, _ = _stable_read(path, "published archive plan")
    if persisted != content:
        raise ValueError("published archive plan bytes drift")
    return _sha256_bytes(content)


def _build_cli_plan(args: argparse.Namespace) -> tuple[Path, ArchivePlan, str]:
    inventory_path = _absolute(args.inventory)
    graph_path = _absolute(args.graph)
    inventory_raw, inventory_bytes = _read_json(inventory_path, "published inventory")
    graph_raw, graph_bytes = _read_json(graph_path, "published consumer graph")
    inventory = inventory_from_payload(inventory_raw)
    graph = _graph_from_payload(graph_raw)
    publication_ids = {str(value) for value in (inventory_raw.get("publication_id"), graph_raw.get("publication_id")) if value}
    if len(publication_ids) > 1:
        raise ValueError("inventory and consumer graph publication IDs differ")
    publication_id = next(iter(publication_ids), "unpublished-fixture")
    generated = inventory_raw.get("generated_artifacts", {})
    if isinstance(generated, Mapping) and "manifests/consumer-graph.json" in generated:
        expected = generated["manifests/consumer-graph.json"]
        if not isinstance(expected, Mapping) or str(expected.get("sha256", "")).upper() != _sha256_bytes(graph_bytes):
            raise ValueError("consumer graph does not match inventory publication authority")
    render_sha = ""
    render_path = _absolute(args.render_inventory) if args.render_inventory else None
    if render_path is not None:
        render_raw, render_bytes = _read_json(render_path, "published render inventory")
        if render_raw.get("publication_id") and str(render_raw.get("publication_id")) != publication_id:
            raise ValueError("render inventory publication ID differs")
        render_sha = _sha256_bytes(render_bytes)
        if isinstance(generated, Mapping) and "manifests/render-generation-inventory.json" in generated:
            expected = generated["manifests/render-generation-inventory.json"]
            if not isinstance(expected, Mapping) or str(expected.get("sha256", "")).upper() != render_sha:
                raise ValueError("render inventory does not match inventory publication authority")
    plan = build_archive_plan(inventory, graph, args.batch_id)
    plan = replace(
        plan,
        publication_id=publication_id,
        inventory_sha256=_sha256_bytes(inventory_bytes),
        consumer_graph_sha256=_sha256_bytes(graph_bytes),
        render_inventory_sha256=render_sha,
    )
    errors = validate_archive_plan(plan, inventory, graph)
    if errors:
        raise ValueError("archive plan validation failed: " + "; ".join(errors))
    output = _absolute(args.output) if args.output else _absolute(inventory.root) / "manifests" / "archive-plans" / f"{args.batch_id}.json"
    digest = _publish_immutable_plan(output, plan)
    return output, plan, digest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("plan", "apply", "restore"), default="plan")
    parser.add_argument("--batch-id", default="legacy-recovery-files-01")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--render-inventory", type=Path, default=None)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan-path", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    if args.command == "plan" and args.render_inventory is None and _absolute(args.inventory) == _absolute(DEFAULT_INVENTORY):
        args.render_inventory = DEFAULT_RENDER_INVENTORY
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "plan":
        output, plan, digest = _build_cli_plan(args)
        print(
            json.dumps(
                {
                    "status": "plan-only",
                    "path": str(output),
                    "sha256": digest,
                    "item_count": len(plan.items),
                    "total_bytes": sum(item.size for item in plan.items),
                    "destination": plan.archive_root,
                    "blockers": list(plan.blockers),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "apply":
        if args.plan_path is None or args.approval is None:
            raise ValueError("apply requires --plan-path and --approval")
        result = apply_archive_plan(args.plan_path, args.approval)
        print(result.manifest_path)
        return 0
    if args.manifest is None:
        raise ValueError("restore requires --manifest")
    result = restore_archive_batch(args.manifest)
    print(result.manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
