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
import stat
import sys
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo


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
    verify_published_outputs,
)
from scripts.blender.pimm_production.consumer_graph import (  # noqa: E402
    CONSUMER_GRAPH_SCHEMA,
    ConsumerGraph,
    build_consumer_graph,
    consumer_graph_payload,
)
from scripts.blender.pimm_production.approval_manifest import (  # noqa: E402
    _create_owned_file,
    _delete_owned_handle,
)


ARCHIVE_PLAN_SCHEMA = "pimm-archive-plan/v1"
ARCHIVE_APPROVAL_SCHEMA = "pimm-archive-plan-approval/v1"
ARCHIVE_MANIFEST_SCHEMA = "pimm-archive-manifest/v1"
ARCHIVE_GOVERNANCE_ROOT = ASSET_ROOT.parent / f"{ASSET_ROOT.name}-governance"
ARCHIVE_PLAN_ROOT = ARCHIVE_GOVERNANCE_ROOT / "manifests" / "archive-plans"
_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_BATCH_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_UTC = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_REPARSE_ATTRIBUTE = 0x400
_BANGKOK = ZoneInfo("Asia/Bangkok")
_PROTECTED_TOKENS = frozenset(
    {"source", "sources", "master", "masters", "material", "materials", "artwork", "scripts", "calibrated", "approved", "release", "releases"}
)
_PROTECTED_KINDS = frozenset({"authoritative-master", "artwork", "script", "texture"})


class _RecoveredGovernanceRenameError(OSError):
    def __init__(
        self, message: str, recovered_identity: tuple[int, int, int, int]
    ) -> None:
        super().__init__(message)
        self.recovered_identity = recovered_identity


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


@dataclass(frozen=True)
class ArchiveAuthority:
    """One freshly verified canonical Task 7 publication.

    Tests may replace ``_load_current_authority`` with this shape in-process.
    No CLI or serialized plan can select a different authority.
    """

    publication_id: str
    inventory: InventoryManifest
    graph: ConsumerGraph
    render_payload: Mapping[str, object]
    inventory_sha256: str
    consumer_graph_sha256: str
    render_inventory_sha256: str
    root_identity: tuple[int, ...]
    active_root: Path
    production: bool = True


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
    created_at = datetime.now(UTC).replace(microsecond=0)
    date = created_at.astimezone(_BANGKOK).strftime("%Y-%m-%d")
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
        created_at_utc=created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        active_root=str(active_root),
        archive_root=str(archive_root),
        publication_id="",
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
    if not plan.publication_id.strip():
        errors.append("archive plan requires a published Task 7 authority")
    for label, digest in (
        ("inventory", plan.inventory_sha256),
        ("consumer graph", plan.consumer_graph_sha256),
        ("render inventory", plan.render_inventory_sha256),
    ):
        if _SHA256.fullmatch(digest) is None:
            errors.append(f"archive plan {label} authority hash is invalid")
    if len(plan.inventory_root_identity) < 2:
        errors.append("archive plan inventory root identity is invalid")
    try:
        _canonical_utc(plan.created_at_utc, "archive plan created_at_utc")
    except ValueError as error:
        errors.append(str(error))
    active_root = _absolute(plan.active_root)
    archive_root = _absolute(plan.archive_root)
    if _within(archive_root, active_root):
        errors.append("archive destination must be outside active root")
    expected_parent = active_root.parent / f"{active_root.name}-archive" / "pending-delete"
    try:
        created_at = datetime.strptime(plan.created_at_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        expected_leaf = f"{created_at.astimezone(_BANGKOK):%Y-%m-%d}-{plan.batch_id}"
    except ValueError:
        expected_leaf = ""
    if archive_root.parent != expected_parent:
        errors.append("archive destination is outside the canonical pending-delete root")
    elif archive_root.name != expected_leaf:
        errors.append("archive destination leaf does not match the created_at Bangkok date")
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
            errors.append(f"{item.relative_path}: disposition is not exact pending-archive")
        consumers = tuple(sorted(set(record.consumers) | set(graph.consumers.get(record.path, ())), key=str.casefold))
        if consumers:
            errors.append(f"{item.relative_path}: active consumer: {', '.join(consumers)}")
        if _has_unique_content(record):
            errors.append(f"{item.relative_path}: unique content not migrated")
        if _ambiguous_for(record.path, graph):
            errors.append(f"{item.relative_path}: ambiguity protects the record")
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
    descriptor = _create_owned_file(path, share_delete=True)
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
    if os.name != "nt":
        return False
    descriptor = _open_existing_for_exact_delete(path, "owned temporary cleanup")
    try:
        if _identity(os.fstat(descriptor))[:2] != identity[:2]:
            return False
        _delete_owned_handle(descriptor, "owned temporary cleanup")
        return True
    finally:
        os.close(descriptor)


def _open_existing_for_exact_delete(path: Path, label: str) -> int:
    """Hold one existing Windows file against writes/replacement for exact deletion."""

    if os.name != "nt":
        raise OSError(f"{label}: exact handle deletion is unavailable off Windows")
    import ctypes
    import msvcrt

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
    generic_read = 0x80000000
    delete_right = 0x00010000
    file_read_attributes = 0x00000080
    file_share_read = 0x00000001
    open_existing = 3
    file_attribute_normal = 0x00000080
    native_handle = create_file(
        str(path),
        generic_read | delete_right | file_read_attributes,
        file_share_read,
        None,
        open_existing,
        file_attribute_normal,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if native_handle in (None, invalid_handle):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(int(native_handle), os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except BaseException:
        kernel32.CloseHandle(ctypes.c_void_p(native_handle))
        raise


def _sha256_descriptor(descriptor: int) -> str:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while chunk := os.read(descriptor, 8 * 1024 * 1024):
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest().upper()


def _verify_descriptor(
    descriptor: int,
    item: ArchiveItem,
    label: str,
    *,
    require_identity: bool,
) -> None:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"{label} must be one regular single-link file")
    if before.st_size != item.size:
        raise ValueError(f"{label} size drift")
    if before.st_mtime_ns != item.mtime_ns:
        raise ValueError(f"{label} mtime drift")
    if require_identity:
        planned_identity = tuple(item.filesystem_identity)
        current_identity = _identity(before)
        if (
            len(planned_identity) != 4
            or planned_identity[:2] != current_identity[:2]
            or planned_identity[3] != current_identity[3]
        ):
            raise ValueError(f"{label} identity drift")
    if _sha256_descriptor(descriptor) != item.sha256.upper():
        raise ValueError(f"{label} hash drift")
    after = os.fstat(descriptor)
    if _identity(before) != _identity(after) or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError(f"{label} changed while hashing")


def _copy_descriptor(source_descriptor: int, destination_descriptor: int) -> None:
    os.lseek(source_descriptor, 0, os.SEEK_SET)
    os.lseek(destination_descriptor, 0, os.SEEK_SET)
    while chunk := os.read(source_descriptor, 8 * 1024 * 1024):
        offset = 0
        while offset < len(chunk):
            written = os.write(destination_descriptor, chunk[offset:])
            if written <= 0:
                raise OSError("archive copy made no progress")
            offset += written
    os.fsync(destination_descriptor)


def _write_descriptor_all(descriptor: int, content: bytes) -> None:
    offset = 0
    while offset < len(content):
        written = os.write(descriptor, content[offset:])
        if written <= 0:
            raise OSError("atomic manifest write made no progress")
        offset += written


def _rename_exact_no_replace(
    source: Path,
    destination: Path,
    item: ArchiveItem,
    label: str,
    require_plan_identity: bool,
) -> None:
    """Atomically rename on Windows while refusing every destination collision."""

    if os.name != "nt":
        raise OSError(f"{label}: atomic no-replace rename is unavailable off Windows")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"{label} destination already exists: {destination}")
    _verify_file(source, item, label, require_identity=require_plan_identity)
    source_identity = _identity(source.stat(follow_symlinks=False))
    os.rename(source, destination)
    try:
        if source.exists() or source.is_symlink():
            raise ValueError(f"{label} source still exists after rename")
        destination_identity = _identity(destination.stat(follow_symlinks=False))
        if destination_identity[:2] != source_identity[:2] or destination_identity[3] != source_identity[3]:
            raise ValueError(f"{label} destination identity drift after rename")
        _verify_file(destination, item, label, require_identity=require_plan_identity)
    except BaseException:
        if not source.exists() and destination.exists():
            destination_descriptor = _open_existing_for_exact_delete(
                destination, f"{label} failed destination"
            )
            source_descriptor: int | None = None
            try:
                current_identity = _identity(os.fstat(destination_descriptor))
                if current_identity[:2] != source_identity[:2] or current_identity[3] != source_identity[3]:
                    raise OSError(
                        f"{label} verification failed after destination ownership was lost; "
                        "competitor preserved; manual intervention required"
                    )
                source_descriptor = _create_owned_file(source, share_delete=False)
                _copy_descriptor(destination_descriptor, source_descriptor)
                os.utime(source, ns=(item.mtime_ns, item.mtime_ns))
                _verify_descriptor(
                    source_descriptor,
                    item,
                    f"{label} recovered source",
                    require_identity=False,
                )
                _delete_owned_handle(
                    destination_descriptor, f"{label} failed destination"
                )
            except BaseException as rollback_error:
                if source_descriptor is not None:
                    try:
                        _delete_owned_handle(
                            source_descriptor, f"{label} incomplete recovered source"
                        )
                    except OSError as cleanup_error:
                        rollback_error.add_note(
                            f"exact recovered-source cleanup failed: {cleanup_error}"
                        )
                raise OSError(
                    f"{label} verification failed and exact-identity recovery was incomplete: "
                    f"{rollback_error}; manual intervention required"
                ) from rollback_error
            finally:
                if source_descriptor is not None:
                    os.close(source_descriptor)
                os.close(destination_descriptor)
        raise


def _rename_governance_no_replace(
    source: Path,
    destination: Path,
    expected_sha256: str,
    label: str,
) -> None:
    """Publish or relocate an exact governance file without replacing a competitor."""

    source = _absolute(source)
    destination = _absolute(destination)
    if os.name != "nt":
        raise OSError(f"{label}: atomic no-replace rename is unavailable off Windows")
    _reject_reparse_ancestors(source, label, allow_missing=False)
    _reject_reparse_ancestors(destination.parent, label, allow_missing=False)
    content, source_identity = _stable_read(source, label)
    if _sha256_bytes(content) != expected_sha256.upper():
        raise ValueError(f"{label} source hash drift")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"{label} already exists: {destination}")
    os.rename(source, destination)
    try:
        if source.exists() or source.is_symlink():
            raise ValueError(f"{label} source still exists after publication")
        persisted, destination_identity = _stable_read(destination, label)
        if destination_identity[:2] != source_identity[:2] or destination_identity[3] != source_identity[3]:
            raise ValueError(f"{label} identity drift after publication")
        if persisted != content or _sha256_bytes(persisted) != expected_sha256.upper():
            raise ValueError(f"{label} bytes drift after publication")
    except BaseException as publication_error:
        recovered_identity: tuple[int, int, int, int] | None = None
        if not source.exists() and destination.exists():
            destination_descriptor = _open_existing_for_exact_delete(
                destination, f"{label} failed publication"
            )
            source_descriptor: int | None = None
            try:
                current_identity = _identity(os.fstat(destination_descriptor))
                if current_identity[:2] != source_identity[:2] or current_identity[3] != source_identity[3]:
                    raise OSError(
                        f"{label} verification failed after destination ownership was lost; "
                        "competitor preserved; manual intervention required"
                    )
                if _sha256_descriptor(destination_descriptor) != expected_sha256.upper():
                    raise ValueError(f"{label} owned destination bytes drifted")
                source_descriptor = _create_owned_file(source, share_delete=False)
                _copy_descriptor(destination_descriptor, source_descriptor)
                if _sha256_descriptor(source_descriptor) != expected_sha256.upper():
                    raise ValueError(f"{label} recovered source bytes drifted")
                _delete_owned_handle(
                    destination_descriptor, f"{label} failed publication"
                )
                recovered_identity = _identity(os.fstat(source_descriptor))
            except BaseException as rollback_error:
                if source_descriptor is not None:
                    try:
                        _delete_owned_handle(
                            source_descriptor, f"{label} incomplete recovered source"
                        )
                    except OSError as cleanup_error:
                        rollback_error.add_note(
                            f"exact recovered-source cleanup failed: {cleanup_error}"
                        )
                raise OSError(
                    f"{label} verification failed and exact-identity recovery was incomplete: "
                    f"{rollback_error}; manual intervention required"
                ) from rollback_error
            finally:
                if source_descriptor is not None:
                    os.close(source_descriptor)
                os.close(destination_descriptor)
        if recovered_identity is not None:
            raise _RecoveredGovernanceRenameError(
                str(publication_error), recovered_identity
            ) from publication_error
        raise


def _canonical_plan_path(batch_id: str) -> Path:
    if _BATCH_ID.fullmatch(batch_id) is None:
        raise ValueError("archive batch ID is invalid")
    return _absolute(ARCHIVE_PLAN_ROOT / f"{batch_id}.json")


def _move_item(item: ArchiveItem, manifest_tmp: Path) -> str:
    source = _absolute(item.source)
    destination = _absolute(item.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _reject_reparse_ancestors(destination.parent, "archive destination", allow_missing=False)
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"destination already exists: {destination}")
    _verify_file(source, item, "source", require_identity=True)
    if _same_volume(source, destination):
        _rename_exact_no_replace(
            source,
            destination,
            item,
            "archive destination",
            True,
        )
        return "atomic-rename"

    if os.name != "nt":
        raise OSError("cross-volume archive mutation is unavailable off Windows")
    source_descriptor = _open_existing_for_exact_delete(source, "archive source")
    destination_descriptor: int | None = None
    try:
        _verify_descriptor(source_descriptor, item, "source", require_identity=True)
        if _identity(source.stat(follow_symlinks=False))[:2] != _identity(os.fstat(source_descriptor))[:2]:
            raise ValueError("source pathname identity drift after handle acquisition")
        destination_descriptor = _create_owned_file(destination, share_delete=False)
        _copy_descriptor(source_descriptor, destination_descriptor)
        os.utime(destination, ns=(item.mtime_ns, item.mtime_ns))
        _verify_descriptor(destination_descriptor, item, "archive destination", require_identity=False)
        if _identity(destination.stat(follow_symlinks=False))[:2] != _identity(os.fstat(destination_descriptor))[:2]:
            raise ValueError("archive destination pathname identity drift")
        _verify_descriptor(source_descriptor, item, "source", require_identity=True)
        _delete_owned_handle(source_descriptor, "archive source")
        return "copy-verify-unlink"
    except BaseException:
        if destination_descriptor is not None:
            try:
                _delete_owned_handle(destination_descriptor, "failed archive destination")
            except OSError as cleanup_error:
                raise OSError(f"archive move failed and exact destination cleanup failed: {cleanup_error}")
        raise
    finally:
        if destination_descriptor is not None:
            os.close(destination_descriptor)
        os.close(source_descriptor)


def _write_manifest_tmp(
    path: Path,
    payload: Mapping[str, object],
    *,
    create: bool,
    expected_identity: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int]:
    content = _canonical_json_bytes(payload)
    if create:
        descriptor, identity = _create_owned_temporary(path)
        try:
            _write_descriptor_all(descriptor, content)
            os.fsync(descriptor)
            identity = _identity(os.fstat(descriptor))
        finally:
            os.close(descriptor)
        return identity
    if expected_identity is None:
        raise ValueError("manifest journal update requires its exact owned identity")
    update = path.parent / f".{path.name}.{uuid.uuid4().hex}.update"
    descriptor, identity = _create_owned_temporary(update)
    try:
        _write_descriptor_all(descriptor, content)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    current_descriptor = _open_existing_for_exact_delete(path, "manifest journal")
    try:
        current_identity = _identity(os.fstat(current_descriptor))
        if current_identity[:2] != expected_identity[:2]:
            raise ValueError(
                "manifest journal destination ownership was lost; competitor preserved"
            )
        pathname_identity = _identity(path.stat(follow_symlinks=False))
        if pathname_identity[:2] != current_identity[:2]:
            raise ValueError(
                "manifest journal pathname ownership was lost; competitor preserved"
            )
        _delete_owned_handle(current_descriptor, "manifest journal")
    except BaseException:
        if update.exists():
            _remove_if_exact(update, identity)
        raise
    finally:
        os.close(current_descriptor)
    try:
        _rename_governance_no_replace(
            update,
            path,
            _sha256_bytes(content),
            "manifest journal update",
        )
    except BaseException as error:
        if update.exists():
            error.add_note(f"complete failure journal retained at {update}")
        raise
    return _identity(path.stat(follow_symlinks=False))


def _publish_failure_journal(
    archive_root: Path, payload: Mapping[str, object]
) -> Path:
    """Publish a complete immutable residual report at a collision-free name."""

    path = archive_root / f"archive-manifest.failure-{uuid.uuid4().hex}.json"
    content = _canonical_json_bytes(payload)
    temporary = archive_root / f".{path.name}.{uuid.uuid4().hex}.pending"
    descriptor, identity = _create_owned_temporary(temporary)
    try:
        _write_descriptor_all(descriptor, content)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        _rename_governance_no_replace(
            temporary,
            path,
            _sha256_bytes(content),
            "immutable archive failure journal",
        )
    except BaseException:
        if temporary.exists():
            _remove_if_exact(temporary, identity)
        raise
    return path


def _result_for_item(item: ArchiveItem, move_mode: str) -> ArchiveFileResult:
    return ArchiveFileResult(
        item.source,
        item.destination,
        item.sha256,
        item.size,
        item.mtime_ns,
        move_mode,
    )


def _manifest_item(item: ArchiveItem) -> dict[str, object]:
    return {
        "plan_item": item.to_payload(),
        "state": "pending",
        "move_mode": None,
        "error": None,
    }


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
    _reject_reparse_ancestors(source.parent, "restore destination", allow_missing=False)
    if _same_volume(destination, source):
        _rename_exact_no_replace(
            destination,
            source,
            item,
            "restore destination",
            False,
        )
        mode = "atomic-rename"
    else:
        if os.name != "nt":
            raise OSError("cross-volume restore mutation is unavailable off Windows")
        archived_descriptor = _open_existing_for_exact_delete(destination, "archived source")
        source_descriptor: int | None = None
        try:
            _verify_descriptor(archived_descriptor, item, "archived source", require_identity=False)
            source_descriptor = _create_owned_file(source, share_delete=False)
            _copy_descriptor(archived_descriptor, source_descriptor)
            os.utime(source, ns=(item.mtime_ns, item.mtime_ns))
            _verify_descriptor(source_descriptor, item, "restored source", require_identity=False)
            if _identity(source.stat(follow_symlinks=False))[:2] != _identity(os.fstat(source_descriptor))[:2]:
                raise ValueError("restored source pathname identity drift")
            _verify_descriptor(archived_descriptor, item, "archived source", require_identity=False)
            _delete_owned_handle(archived_descriptor, "archived source")
            mode = "copy-verify-unlink"
        except BaseException:
            if source_descriptor is not None:
                try:
                    _delete_owned_handle(source_descriptor, "failed restored source")
                except OSError as cleanup_error:
                    raise OSError(f"restore failed and exact destination cleanup failed: {cleanup_error}")
            raise
        finally:
            if source_descriptor is not None:
                os.close(source_descriptor)
            os.close(archived_descriptor)
    _verify_file(source, item, "restored source", require_identity=False)
    return ArchiveFileResult(str(source), str(destination), result.sha256, result.size, result.mtime_ns, mode)


def _rollback_moved(
    results: Sequence[ArchiveFileResult],
) -> tuple[tuple[ArchiveFileResult, ...], tuple[tuple[str, str], ...]]:
    restored: list[ArchiveFileResult] = []
    failures: list[tuple[str, str]] = []
    for result in reversed(results):
        try:
            restored.append(_restore_one(result))
        except (OSError, ValueError) as error:
            failures.append((result.source, f"{type(error).__name__}: {error}"))
    return tuple(restored), tuple(failures)


def apply_archive_plan(plan_path: Path, approval_path: Path) -> ArchiveResult:
    """Apply one exact owner-approved plan, rolling completed moves back on failure."""

    plan_path = _absolute(plan_path)
    approval_path = _absolute(approval_path)
    plan, plan_sha256 = _load_plan(plan_path)
    approval_sha256 = _validate_approval(approval_path, plan_path, plan, plan_sha256)
    if not plan.items:
        raise ValueError("archive plan contains no movable items; no-op plans cannot be applied")
    authority = _load_current_authority()
    if authority.production:
        canonical_plan_path = _canonical_plan_path(plan.batch_id)
        if plan_path != canonical_plan_path:
            raise ValueError("production apply requires the exact canonical archive plan path")
    _validate_plan_against_current_authority(plan, authority)
    _preflight_apply(plan)
    live_graph = _rebuild_current_consumer_graph(authority)
    live_errors = validate_archive_plan(plan, authority.inventory, live_graph)
    if live_errors:
        raise ValueError(
            "current consumer evidence rejected archive operation: "
            + "; ".join(live_errors)
        )
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
        "publication_id": plan.publication_id,
        "inventory_sha256": plan.inventory_sha256,
        "consumer_graph_sha256": plan.consumer_graph_sha256,
        "render_inventory_sha256": plan.render_inventory_sha256,
        "inventory_root_identity": list(plan.inventory_root_identity),
        "plan_path": str(plan_path),
        "plan_sha256": plan_sha256,
        "approval_path": str(approval_path),
        "approval_sha256": approval_sha256,
        "error": None,
        "residuals": [],
        "items": [_manifest_item(item) for item in plan.items],
    }
    manifest_identity = _write_manifest_tmp(manifest_tmp, base_payload, create=True)
    moved: list[ArchiveFileResult] = []
    current_index: int | None = None
    try:
        for index, item in enumerate(plan.items):
            current_index = index
            mode = _move_item(item, manifest_tmp)
            result = _result_for_item(item, mode)
            moved.append(result)
            entry = base_payload["items"][index]
            entry["state"] = "moved"
            entry["move_mode"] = mode
            manifest_identity = _write_manifest_tmp(
                manifest_tmp,
                base_payload,
                create=False,
                expected_identity=manifest_identity,
            )
        base_payload["status"] = "archived"
        manifest_identity = _write_manifest_tmp(
            manifest_tmp,
            base_payload,
            create=False,
            expected_identity=manifest_identity,
        )
        if manifest_path.exists() or manifest_path.is_symlink():
            raise ValueError("immutable archive manifest already exists")
        manifest_bytes = _canonical_json_bytes(base_payload)
        _rename_governance_no_replace(
            manifest_tmp,
            manifest_path,
            _sha256_bytes(manifest_bytes),
            "immutable archive manifest",
        )
        return ArchiveResult(manifest_path=manifest_path, moved=tuple(moved))
    except Exception as error:
        if isinstance(error, _RecoveredGovernanceRenameError):
            manifest_identity = error.recovered_identity
        rolled_back, rollback_failures = _rollback_moved(moved)
        failure_payload = base_payload
        failure_payload["status"] = (
            "failed-partial-rollback" if rollback_failures else "failed-rolled-back"
        )
        failure_payload["error"] = f"{type(error).__name__}: {error}"
        failure_payload["residuals"] = [source for source, _ in rollback_failures]
        if current_index is not None:
            failed_entry = failure_payload["items"][current_index]
            if failed_entry["state"] == "pending":
                failed_entry["state"] = "move-failed"
                failed_entry["error"] = f"{type(error).__name__}: {error}"
        restored_sources = {result.source for result in rolled_back}
        failure_by_source = dict(rollback_failures)
        for entry in failure_payload["items"]:
            source = str(entry["plan_item"]["source"])
            if source in restored_sources:
                entry["state"] = "rolled-back"
                entry["error"] = None
            elif source in failure_by_source:
                entry["state"] = "rollback-failed"
                entry["error"] = failure_by_source[source]
        failure_recorded = False
        if manifest_tmp.exists():
            try:
                _write_manifest_tmp(
                    manifest_tmp,
                    failure_payload,
                    create=False,
                    expected_identity=manifest_identity,
                )
                failure_recorded = True
            except (OSError, ValueError) as journal_error:
                error.add_note(f"canonical failure-journal update failed safely: {journal_error}")
        if not failure_recorded:
            failure_path = _publish_failure_journal(archive_root, failure_payload)
            error.add_note(f"immutable failure journal: {failure_path}")
        if rollback_failures:
            residuals = ", ".join(source for source, _ in rollback_failures)
            raise OSError(
                f"{error}; rollback incomplete; manual intervention required for: {residuals}"
            ) from error
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
        "publication_id", "inventory_sha256", "consumer_graph_sha256",
        "render_inventory_sha256", "inventory_root_identity",
        "plan_path", "plan_sha256", "approval_path", "approval_sha256",
        "error", "residuals", "items",
    }
    if not isinstance(payload, Mapping) or set(payload) != required:
        raise ValueError("archive manifest fields are incomplete or unknown")
    allowed_statuses = {"archived", "pending", "failed-rolled-back", "failed-partial-rollback"}
    if payload.get("schema") != ARCHIVE_MANIFEST_SCHEMA or payload.get("schema_version") != 1 or payload.get("status") not in allowed_statuses:
        raise ValueError("archive manifest schema or recoverable status is invalid")
    if not isinstance(payload.get("residuals"), list) or not (
        payload.get("error") is None or isinstance(payload.get("error"), str)
    ):
        raise ValueError("archive manifest failure state is invalid")
    active_root = _absolute(str(payload["active_root"]))
    archive_root = _absolute(str(payload["archive_root"]))
    expected_manifest_paths = {
        archive_root / "archive-manifest.json",
        archive_root / "archive-manifest.json.tmp",
    }
    retained_update = (
        manifest_path.parent == archive_root
        and re.fullmatch(
            r"\.archive-manifest\.json\.tmp\.[0-9a-f]{32}\.update",
            manifest_path.name,
        )
        is not None
    )
    failure_journal = (
        manifest_path.parent == archive_root
        and re.fullmatch(
            r"archive-manifest\.failure-[0-9a-f]{32}\.json",
            manifest_path.name,
        )
        is not None
    )
    if (
        manifest_path not in expected_manifest_paths
        and not retained_update
        and not failure_journal
    ):
        raise ValueError("archive manifest path is outside the exact canonical archive root")
    _reject_reparse_ancestors(active_root, "restore active root", allow_missing=False)
    _reject_reparse_ancestors(archive_root, "restore archive root", allow_missing=False)
    plan_path = _absolute(str(payload["plan_path"]))
    plan, plan_sha256 = _load_plan(plan_path)
    if str(payload["plan_sha256"]).upper() != plan_sha256:
        raise ValueError("archive manifest plan hash mismatch; plan SHA-256 does not match immutable plan bytes")
    approval_path = _absolute(str(payload["approval_path"]))
    approval_content, _ = _stable_read(approval_path, "archive approval")
    approval_sha256 = _sha256_bytes(approval_content)
    if str(payload["approval_sha256"]).upper() != approval_sha256:
        raise ValueError("archive manifest approval hash mismatch; approval SHA-256 does not match immutable approval bytes")
    _validate_approval(approval_path, plan_path, plan, plan_sha256)
    bindings = {
        "batch_id": plan.batch_id,
        "active_root": plan.active_root,
        "archive_root": plan.archive_root,
        "publication_id": plan.publication_id,
        "inventory_sha256": plan.inventory_sha256,
        "consumer_graph_sha256": plan.consumer_graph_sha256,
        "render_inventory_sha256": plan.render_inventory_sha256,
        "inventory_root_identity": list(plan.inventory_root_identity),
    }
    for key, expected in bindings.items():
        if payload.get(key) != expected:
            label = "active root" if key == "active_root" else key.replace("_", " ")
            raise ValueError(f"archive manifest {label} binding mismatch")
    if _absolute(plan.archive_root) != archive_root or _absolute(plan.active_root) != active_root:
        raise ValueError("archive manifest root binding mismatch")
    authority = _load_current_authority(
        permitted_missing_paths=tuple(item.relative_path for item in plan.items)
    )
    if authority.production:
        canonical_plan_path = _canonical_plan_path(plan.batch_id)
        if plan_path != canonical_plan_path:
            raise ValueError("production restore requires the exact canonical archive plan path")
    _validate_plan_against_current_authority(
        plan,
        authority,
        restore=True,
        current_graph=_rebuild_current_consumer_graph(authority),
    )
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("archive manifest items must be a list")
    if len(raw_items) < len(plan.items):
        raise ValueError("archive manifest has a missing item")
    if len(raw_items) > len(plan.items):
        raise ValueError("archive manifest has an extra item")
    results: list[ArchiveFileResult] = []
    for index, (raw, plan_item) in enumerate(zip(raw_items, plan.items, strict=True)):
        if not isinstance(raw, Mapping) or set(raw) != {"plan_item", "state", "move_mode", "error"}:
            raise ValueError("archive manifest item fields are invalid")
        if raw.get("plan_item") != plan_item.to_payload():
            raise ValueError(f"archive manifest item mapping mismatch at index {index}")
        if raw.get("state") not in {"pending", "moved", "rolled-back", "rollback-failed", "move-failed"}:
            raise ValueError("archive manifest item state is invalid")
        if not (raw.get("error") is None or isinstance(raw.get("error"), str)):
            raise ValueError("archive manifest item error is invalid")
        result = _result_for_item(plan_item, str(raw.get("move_mode") or "reconciled"))
        if not _within(_absolute(result.source), active_root) or not _within(_absolute(result.destination), archive_root):
            raise ValueError("archive restore mapping escapes its authority roots")
        results.append(result)
    states = [str(raw["state"]) for raw in raw_items]
    residuals = [str(value) for value in payload["residuals"]]
    status = str(payload["status"])
    if status == "archived" and (
        any(state != "moved" for state in states) or payload["error"] is not None or residuals
    ):
        raise ValueError("archive manifest status and item state mismatch")
    if status == "pending" and (
        any(state not in {"pending", "moved"} for state in states)
        or payload["error"] is not None
        or residuals
    ):
        raise ValueError("archive manifest status and item state mismatch")
    rollback_failed_sources = [
        str(raw["plan_item"]["source"])
        for raw in raw_items
        if raw["state"] == "rollback-failed"
    ]
    if status == "failed-rolled-back" and (rollback_failed_sources or residuals):
        raise ValueError("archive manifest status and item state mismatch")
    if status == "failed-partial-rollback" and (
        not rollback_failed_sources
        or sorted(residuals, key=str.casefold)
        != sorted(rollback_failed_sources, key=str.casefold)
    ):
        raise ValueError("archive manifest status and item state mismatch")
    restore_results: list[ArchiveFileResult] = []
    duplicate_archive_results: list[ArchiveFileResult] = []
    for result, plan_item in zip(results, plan.items, strict=True):
        source = _absolute(result.source)
        destination = _absolute(result.destination)
        _reject_reparse_ancestors(source, "restore active mapping", allow_missing=True)
        _reject_reparse_ancestors(destination, "restore archive mapping", allow_missing=True)
        source_exists = source.exists() or source.is_symlink()
        destination_exists = destination.exists() or destination.is_symlink()
        if source_exists:
            _verify_file(source, plan_item, "restore active source", require_identity=False)
        if destination_exists:
            _verify_file(destination, plan_item, "archived source", require_identity=False)
        if not source_exists and destination_exists:
            restore_results.append(result)
        elif source_exists and destination_exists:
            duplicate_archive_results.append(result)
        elif not source_exists and not destination_exists:
            raise ValueError(f"archive item is missing from both roots: {result.source}")
    restored: list[ArchiveFileResult] = []
    try:
        for result in restore_results:
            restored.append(_restore_one(result))
        for result in duplicate_archive_results:
            destination = _absolute(result.destination)
            item = next(item for item in plan.items if item.source == result.source)
            descriptor = _open_existing_for_exact_delete(destination, "duplicate archived source")
            try:
                _verify_descriptor(descriptor, item, "duplicate archived source", require_identity=False)
                _delete_owned_handle(descriptor, "duplicate archived source")
            finally:
                os.close(descriptor)
    except Exception as error:
        # Restore is itself reversible: move already restored records back to archive.
        rollback_failures: list[str] = []
        for result in reversed(restored):
            source = _absolute(result.source)
            destination = _absolute(result.destination)
            if source.exists() and not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                item = next(item for item in plan.items if item.source == result.source)
                try:
                    _rename_exact_no_replace(
                        source,
                        destination,
                        item,
                        "restore rollback destination",
                        False,
                    )
                except (OSError, ValueError) as rollback_error:
                    rollback_failures.append(f"{source}: {rollback_error}")
        if rollback_failures:
            raise OSError(
                f"{error}; restore rollback incomplete; manual intervention required: "
                + "; ".join(rollback_failures)
            ) from error
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


def _load_current_authority(
    *, permitted_missing_paths: Sequence[str] = ()
) -> ArchiveAuthority:
    """Load only the canonical, current, freshly verified Task 7 publication."""

    first = verify_published_outputs(
        ASSET_ROOT, permitted_missing_paths=permitted_missing_paths
    )
    inventory_raw, inventory_bytes = _read_json(DEFAULT_INVENTORY, "canonical Task 7 inventory")
    graph_raw, graph_bytes = _read_json(DEFAULT_GRAPH, "canonical Task 7 consumer graph")
    render_raw, render_bytes = _read_json(
        DEFAULT_RENDER_INVENTORY, "canonical Task 7 render inventory"
    )
    second = verify_published_outputs(
        ASSET_ROOT, permitted_missing_paths=permitted_missing_paths
    )
    publication_id = str(first.get("publication_id", ""))
    if not publication_id or second.get("publication_id") != publication_id:
        raise ValueError("canonical Task 7 publication changed while loading authority")
    for label, payload in (
        ("inventory", inventory_raw),
        ("graph", graph_raw),
        ("render", render_raw),
    ):
        if payload.get("publication_id") != publication_id:
            raise ValueError(f"canonical Task 7 {label} publication drift")
    inventory = inventory_from_payload(inventory_raw)
    graph = _graph_from_payload(graph_raw)
    active_root = _absolute(ASSET_ROOT)
    if _absolute(inventory.root) != active_root:
        raise ValueError("canonical Task 7 inventory root is not the canonical active root")
    _reject_reparse_ancestors(active_root, "canonical active root", allow_missing=False)
    current_root_identity = _identity(active_root.stat(follow_symlinks=False))[:2]
    if tuple(inventory.root_identity) != current_root_identity:
        raise ValueError("canonical Task 7 inventory root identity drift")
    generated = inventory_raw.get("generated_artifacts")
    if not isinstance(generated, Mapping):
        raise ValueError("canonical Task 7 generated-artifact authority is missing")
    graph_sha = _sha256_bytes(graph_bytes)
    render_sha = _sha256_bytes(render_bytes)
    for relative, actual in (
        ("manifests/consumer-graph.json", graph_sha),
        ("manifests/render-generation-inventory.json", render_sha),
    ):
        descriptor = generated.get(relative)
        if not isinstance(descriptor, Mapping) or str(descriptor.get("sha256", "")).upper() != actual:
            raise ValueError(f"canonical Task 7 bound {relative} hash drift")
    return ArchiveAuthority(
        publication_id=publication_id,
        inventory=inventory,
        graph=graph,
        render_payload=render_raw,
        inventory_sha256=_sha256_bytes(inventory_bytes),
        consumer_graph_sha256=graph_sha,
        render_inventory_sha256=render_sha,
        root_identity=current_root_identity,
        active_root=active_root,
    )


def _rebuild_current_consumer_graph(authority: ArchiveAuthority) -> ConsumerGraph:
    """Re-scan mutable source inputs immediately before an archive mutation."""

    if authority.production:
        repo_root = REPOSITORY_ROOT
    else:
        repo_root = getattr(authority, "test_consumer_source_root", None)
        if repo_root is None:
            return authority.graph
    return build_consumer_graph(
        _absolute(repo_root),
        _absolute(authority.active_root),
        authority.inventory.records,
    )


def _validate_plan_against_current_authority(
    plan: ArchivePlan,
    authority: ArchiveAuthority,
    *,
    restore: bool = False,
    current_graph: ConsumerGraph | None = None,
) -> None:
    errors: list[str] = []
    if _absolute(plan.active_root) != _absolute(authority.active_root):
        errors.append("archive plan does not name the canonical active root")
    if tuple(plan.inventory_root_identity) != tuple(authority.root_identity):
        errors.append("archive plan root identity drift")
    if plan.publication_id != authority.publication_id:
        errors.append("archive plan publication drift")
    if plan.inventory_sha256.upper() != authority.inventory_sha256.upper():
        errors.append("archive plan inventory hash drift")
    if plan.consumer_graph_sha256.upper() != authority.consumer_graph_sha256.upper():
        errors.append("archive plan graph hash drift")
    if plan.render_inventory_sha256.upper() != authority.render_inventory_sha256.upper():
        errors.append("archive plan render hash drift")
    graph = current_graph or authority.graph
    if not restore:
        errors.extend(validate_archive_plan(plan, authority.inventory, graph))
    else:
        # Restore authenticates the original publication while allowing only the
        # plan's source paths to be absent. Current consumers still block mutation.
        records = {record.path.casefold(): record for record in authority.inventory.records}
        for item in plan.items:
            record = records.get(item.relative_path.casefold())
            if record is not None and record.consumers:
                errors.append(f"{item.relative_path}: current consumer blocks restore")
            graph_consumers = graph.consumers.get(item.relative_path, ())
            if graph_consumers:
                errors.append(f"{item.relative_path}: current consumer blocks restore")
            if _ambiguous_for(item.relative_path, graph):
                errors.append(f"{item.relative_path}: current ambiguity blocks restore")
    if errors:
        raise ValueError("current Task 7 authority rejected archive operation: " + "; ".join(errors))


def _publish_immutable_plan(path: Path, plan: ArchivePlan) -> str:
    path = _absolute(path)
    if path != _canonical_plan_path(plan.batch_id):
        raise ValueError("archive plan path must be the exact external governance plan root")
    _reject_reparse_ancestors(path.parent, "archive plan directory", allow_missing=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_reparse_ancestors(path.parent, "archive plan directory", allow_missing=False)
    if path.exists() or path.is_symlink():
        raise ValueError(f"immutable archive plan already exists: {path}")
    content = _canonical_json_bytes(plan.to_payload())
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.pending"
    descriptor, identity = _create_owned_temporary(temporary)
    try:
        _write_descriptor_all(descriptor, content)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        _rename_governance_no_replace(
            temporary,
            path,
            _sha256_bytes(content),
            "immutable archive plan",
        )
    except BaseException:
        if temporary.exists():
            _remove_if_exact(temporary, identity)
        raise
    persisted, _ = _stable_read(path, "published archive plan")
    if persisted != content:
        raise ValueError("published archive plan bytes drift")
    return _sha256_bytes(content)


def _build_cli_plan(args: argparse.Namespace) -> tuple[Path, ArchivePlan, str]:
    authority = _load_current_authority()
    if not authority.production:
        raise ValueError("production plan CLI cannot use injected or unpublished authority")
    plan = build_archive_plan(authority.inventory, authority.graph, args.batch_id)
    plan = replace(
        plan,
        publication_id=authority.publication_id,
        inventory_sha256=authority.inventory_sha256,
        consumer_graph_sha256=authority.consumer_graph_sha256,
        render_inventory_sha256=authority.render_inventory_sha256,
    )
    _validate_plan_against_current_authority(plan, authority)
    output = _canonical_plan_path(args.batch_id)
    digest = _publish_immutable_plan(output, plan)
    return output, plan, digest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    forbidden_authority_options = {"--inventory", "--graph", "--render-inventory", "--output"}
    if any(argument.split("=", 1)[0] in forbidden_authority_options for argument in raw_arguments):
        parser.error("production plan CLI requires canonical Task 7 authority; caller-selected manifests are forbidden")
    parser.add_argument("command", nargs="?", choices=("plan", "apply", "restore"), default="plan")
    parser.add_argument("--batch-id", default="legacy-recovery-files-01")
    parser.add_argument("--plan-path", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--manifest", type=Path)
    return parser.parse_args(raw_arguments)


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
