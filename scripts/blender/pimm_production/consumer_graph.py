"""Exact, evidence-bearing PIMM asset consumer and producer graph."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal, Mapping, Sequence

from scripts.blender.master_assets.pimm_legacy_inventory import (
    ASSET_ROOT,
    DEFAULT_GRAPH,
    DEFAULT_INVENTORY,
    REPOSITORY_ROOT,
    AssetRecord,
    _ExactReferenceMatcher,
    atomic_write_json,
    inventory_from_payload,
)


CONSUMER_GRAPH_SCHEMA = "pimm-consumer-graph/v1"
_TEXT_SUFFIXES = frozenset(
    {".liquid", ".json", ".jsonl", ".css", ".js", ".mjs", ".py", ".ps1", ".bat", ".cmd", ".yaml", ".yml"}
)
_IGNORED_PARTS = frozenset({".git", ".worktrees", "node_modules", ".venv", "venv", "__pycache__"})
_GENERATED_GRAPH_INPUTS = frozenset(
    {"blender-project-inventory.json", "render-generation-inventory.json", "consumer-graph.json"}
)
_PRODUCER_HINT = re.compile(r"(?:output|destination|render|write|publish|release|target)", re.IGNORECASE)


def _normalize_values(values: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(sorted({str(value).replace("\\", "/") for value in values or ()}, key=str.casefold))


@dataclass(frozen=True)
class ConsumerGraph:
    consumers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    producers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "consumers", {key: _normalize_values(values) for key, values in self.consumers.items()})
        object.__setattr__(self, "producers", {key: _normalize_values(values) for key, values in self.producers.items()})


def _text_files(root: Path):
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in _TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if any(part.casefold() in _IGNORED_PARTS for part in relative.parts[:-1]):
            continue
        current = root
        in_virtual_environment = False
        for part in relative.parts[:-1]:
            current /= part
            if (current / "pyvenv.cfg").is_file():
                in_virtual_environment = True
                break
        if in_virtual_environment:
            continue
        if path.name.casefold() in _GENERATED_GRAPH_INPUTS:
            continue
        yield path


def _display(root_name: str, root: Path, path: Path, line: int) -> str:
    return f"{root_name}:{path.relative_to(root).as_posix()}:{line}"


def _scan_text_root(
    root_name: str,
    root: Path,
    records: Sequence[AssetRecord],
    matcher: _ExactReferenceMatcher,
    consumers: dict[str, set[str]],
    producers: dict[str, set[str]],
) -> None:
    for text_path in _text_files(root):
        try:
            lines = text_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            matched_paths = matcher.matches(line)
            for record_path in matched_paths:
                evidence = _display(root_name, root, text_path, line_number)
                consumers[record_path].add(evidence)
                if _PRODUCER_HINT.search(line):
                    producers[record_path].add(evidence)


def build_consumer_graph(
    repo_root: Path,
    asset_root: Path,
    records: Sequence[AssetRecord],
) -> ConsumerGraph:
    """Build exact text and Blender-datablock edges for every inventory record."""

    consumers = {record.path: set() for record in records}
    producers = {record.path: set() for record in records}
    by_path = {record.path.casefold(): record.path for record in records}
    candidates = {
        record.path: asset_root / PurePosixPath(record.path) for record in records
    }
    matcher = _ExactReferenceMatcher(candidates)
    _scan_text_root("repo", repo_root, records, matcher, consumers, producers)
    _scan_text_root("asset", asset_root, records, matcher, consumers, producers)

    for record in records:
        for dependency in record.dependencies:
            canonical_dependency = by_path.get(dependency.casefold(), dependency)
            evidence_values = record.dependency_evidence.get(dependency, ("datablock:untyped",))
            for evidence in evidence_values:
                consumers.setdefault(canonical_dependency, set()).add(f"asset:{record.path}#{evidence}")
                producers[record.path].add(f"dependency:{canonical_dependency}#{evidence}")

    return ConsumerGraph(
        consumers={key: tuple(sorted(values, key=str.casefold)) for key, values in sorted(consumers.items())},
        producers={key: tuple(sorted(values, key=str.casefold)) for key, values in sorted(producers.items())},
    )


def classify_record(
    record: AssetRecord,
    graph: ConsumerGraph,
) -> Literal["authoritative", "active-linked-scene", "migrate", "pending-archive", "unresolved"]:
    """Apply fail-closed archive classification to one current record."""

    missing_dependencies = record.blender_inspection.get("missing_dependencies", ())
    if record.blender_inspection.get("inspection_error") or missing_dependencies:
        return "unresolved"
    if record.kind == "authoritative-master" or (
        PurePosixPath(record.path).name
        in {"PIMM-30G-MASTER.blend", "PIMM-50G-MASTER.blend", "PIMM-MATERIAL-LIBRARY.blend"}
        and PurePosixPath(record.path).parent.as_posix().casefold() == "masters"
    ):
        return "authoritative"
    authoritative_dependencies = {
        "PIMM-30G-MASTER.blend",
        "PIMM-50G-MASTER.blend",
        "PIMM-MATERIAL-LIBRARY.blend",
    }
    if record.kind == "blend-project" and any(
        PurePosixPath(dependency).name in authoritative_dependencies for dependency in record.dependencies
    ):
        return "active-linked-scene"
    if graph.consumers.get(record.path) or record.consumers or record.unique_content:
        return "migrate"
    if record.kind == "blend-recovery" or record.path.casefold().endswith(".blend1"):
        return "pending-archive"
    return "unresolved"


def consumer_graph_payload(graph: ConsumerGraph) -> dict[str, object]:
    return {
        "schema": CONSUMER_GRAPH_SCHEMA,
        "consumers": {key: list(values) for key, values in graph.consumers.items()},
        "producers": {key: list(values) for key, values in graph.producers.items()},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--asset-root", type=Path, default=ASSET_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inventory = inventory_from_payload(json.loads(args.inventory.read_text(encoding="utf-8")))
    graph = build_consumer_graph(args.repo_root, args.asset_root, inventory.records)
    atomic_write_json(args.output, consumer_graph_payload(graph))
    print(f"PIMM_CONSUMER_GRAPH assets={len(graph.consumers)}")


if __name__ == "__main__":
    main()
