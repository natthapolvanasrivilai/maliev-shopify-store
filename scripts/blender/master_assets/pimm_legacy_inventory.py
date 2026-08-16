"""Read-only schema-v2 inventory for the active PIMM Blender workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
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
_GENERATED_MANIFESTS = frozenset(
    {"blender-project-inventory.json", "render-generation-inventory.json", "consumer-graph.json"}
)
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

    def __post_init__(self) -> None:
        normalized_path = self.path.replace("\\", "/")
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


@dataclass(frozen=True)
class InventoryManifest:
    """Complete discovered path set and its one-to-one immutable records."""

    records: tuple[AssetRecord, ...]
    discovered_paths: tuple[str, ...]
    root: str = ""

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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


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
    if "manifests" in parts or ("manifest" in relative.stem.casefold() and suffix in _MANIFEST_SUFFIXES):
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
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_ignored(relative, root):
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
    """Small trie matcher for exact filename/path references in large inventories."""

    def __init__(self, candidates: Mapping[str, Path]):
        self._trie: dict[str, object] = {}
        for relative, absolute in candidates.items():
            variants = {
                relative,
                relative.replace("/", "\\"),
                str(absolute),
                str(absolute).replace("\\", "/"),
                PurePosixPath(relative).name,
            }
            for variant in variants:
                node = self._trie
                for character in variant.replace("\\", "/").casefold():
                    node = node.setdefault(character, {})  # type: ignore[assignment]
                node.setdefault("", set()).add(relative)  # type: ignore[union-attr]

    def matches(self, text: str) -> set[str]:
        normalized = text.replace("\\", "/").casefold()
        found: set[str] = set()
        boundary = set("abcdefghijklmnopqrstuvwxyz0123456789_.-")
        for start in range(len(normalized)):
            if start and normalized[start - 1] in boundary:
                continue
            node: Mapping[str, object] = self._trie
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


def _text_dependencies(
    path: Path,
    matcher: _ExactReferenceMatcher,
) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    if path.suffix.casefold() not in _TEXT_SUFFIXES or path.name.casefold() in _GENERATED_MANIFESTS:
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

    root = root.resolve()
    cached = _load_cached_inspections(root)
    discovered = _discover(root)
    candidates = {_relative(path, root): path for path, _kind in discovered}
    matcher = _ExactReferenceMatcher(candidates)
    records: list[AssetRecord] = []
    for path, kind in discovered:
        relative = _relative(path, root)
        stat_before = path.stat()
        digest = sha256_file(path)
        stat_after = path.stat()
        if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
            raise RuntimeError(f"asset changed while hashing: {relative}")
        inspection: Mapping[str, object] = {}
        unique_content = False
        dependency_evidence: Mapping[str, tuple[str, ...]] = {}
        cached_record = cached.get(relative)
        if cached_record is not None and cached_record[0] == digest:
            inspection, unique_content, dependency_evidence = cached_record[1:]
        dependencies, text_evidence = _text_dependencies(path, matcher)
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
            )
        )
    paths = tuple(record.path for record in records)
    return InventoryManifest(records=tuple(records), discovered_paths=paths, root=str(root))


def _record_payload(record: AssetRecord) -> dict[str, object]:
    payload = asdict(record)
    payload["blender_inspection"] = dict(record.blender_inspection)
    payload["dependency_evidence"] = {
        key: list(values) for key, values in record.dependency_evidence.items()
    }
    for key in ("consumers", "dependencies", "generation_membership", "release_membership"):
        payload[key] = list(payload[key])
    return payload


def inventory_payload(inventory: InventoryManifest) -> dict[str, object]:
    dispositions = {name: 0 for name in sorted(ALLOWED_DISPOSITIONS)}
    kinds: dict[str, int] = {}
    for record in inventory.records:
        dispositions[record.proposed_disposition] += 1
        kinds[record.kind] = kinds.get(record.kind, 0) + 1
    return {
        "schema": INVENTORY_SCHEMA,
        "root": inventory.root,
        "discovered_paths": list(inventory.discovered_paths),
        "records": [_record_payload(record) for record in inventory.records],
        "summary": {
            "record_count": len(inventory.records),
            "bytes": sum(record.size for record in inventory.records),
            "kinds": dict(sorted(kinds.items())),
            "dispositions": dispositions,
        },
    }


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
    )


def render_generation_payload(inventory: InventoryManifest) -> dict[str, object]:
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
    return {
        "schema": RENDER_INVENTORY_SCHEMA,
        "root": inventory.root,
        "records": [_record_payload(record) for record in records],
        "generations": {key: sorted(values, key=str.casefold) for key, values in sorted(generations.items())},
        "releases": {key: sorted(values, key=str.casefold) for key, values in sorted(releases.items())},
    }


def atomic_write_json(destination: Path, payload: Mapping[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, destination)


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
    summary: dict[str, object] = {
        "blender_version": ".".join(str(value) for value in bpy.app.version),
        "scenes": sorted(scene.name for scene in bpy.data.scenes),
        "mesh_object_count": sum(obj.type == "MESH" for obj in bpy.data.objects),
        "object_count": len(bpy.data.objects),
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
    root = (root or Path(inventory.root)).resolve()
    records: list[AssetRecord] = []
    blend_records = [record for record in inventory.records if record.kind in {"blend-project", "blend-recovery", "authoritative-master"}]
    total = len(blend_records)
    inspected = 0
    for record in inventory.records:
        if record not in blend_records:
            records.append(record)
            continue
        path = root / PurePosixPath(record.path)
        before = sha256_file(path)
        if before != record.sha256:
            raise RuntimeError(f"Blender file drift before inspection: {record.path}")
        try:
            import bpy

            bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
            summary, evidence = _inspection_summary(root)
            unique_content = bool(
                summary["cameras"]
                or summary["rigs"]
                or summary["animations"]
                or summary["lights"]
                or summary["compositor_nodes"]
            )
        except Exception as error:
            summary = {"inspection_error": f"{type(error).__name__}: {error}"}
            evidence = {}
            unique_content = True
        after = sha256_file(path)
        if after != before:
            raise RuntimeError(f"Blender file changed during read-only inspection: {record.path}")
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
    enriched = InventoryManifest(tuple(records), inventory.discovered_paths, inventory.root)
    atomic_write_json(inventory_path, inventory_payload(enriched))
    return enriched


def migration_report(inventory: InventoryManifest) -> str:
    migration_records = [
        record
        for record in inventory.records
        if record.proposed_disposition in {"migrate", "active-linked-scene", "unresolved"}
        and (record.kind in {"blend-project", "blend-recovery", "authoritative-master"} or record.consumers)
    ]
    lines = [
        "# PIMM Blender Migration Report",
        "",
        "This report is read-only. No file was moved, renamed, or deleted; no Blender file was saved and nothing was rendered.",
        "Scene migration remains blocked until after material publication and owner approval.",
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
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, destination)


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

    inventory = inventory_from_payload(json.loads(inventory_path.read_text(encoding="utf-8")))
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
        for dependency in record.dependencies:
            evidence = record.dependency_evidence.get(dependency, ())
            if evidence and all(item.startswith("output:") for item in evidence):
                continue
            dependency_path = Path(dependency)
            if not dependency_path.is_absolute():
                dependency_path = asset_root / PurePosixPath(dependency)
            if not dependency_path.exists():
                missing.append(dependency)
        inspection = dict(record.blender_inspection)
        inspection["missing_dependencies"] = sorted(set(missing), key=str.casefold)
        reconciled_records.append(replace(record, blender_inspection=inspection))
    inventory = InventoryManifest(tuple(reconciled_records), inventory.discovered_paths, inventory.root)
    graph = build_consumer_graph(repo_root, asset_root, inventory.records)
    records = tuple(
        replace(
            record,
            consumers=graph.consumers.get(record.path, ()),
            proposed_disposition=classify_record(record, graph),
        )
        for record in inventory.records
    )
    finalized = InventoryManifest(records, inventory.discovered_paths, inventory.root)
    atomic_write_json(inventory_path, inventory_payload(finalized))
    atomic_write_json(render_inventory_path, render_generation_payload(finalized))
    atomic_write_json(graph_path, consumer_graph_payload(graph))
    atomic_write_text(report_path, migration_report(finalized))
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
    if args.scan:
        inventory = inventory_workspace(args.root)
        atomic_write_json(args.inventory, inventory_payload(inventory))
    elif args.enrich:
        inventory = enrich_with_blender(args.inventory, args.root)
    else:
        inventory = finalize_inventory(
            args.inventory,
            args.report,
            args.graph,
            args.render_inventory,
            args.repo_root,
            args.root,
        )
    print(f"PIMM_LEGACY_INVENTORY records={len(inventory.records)}")


if __name__ == "__main__":
    main()
