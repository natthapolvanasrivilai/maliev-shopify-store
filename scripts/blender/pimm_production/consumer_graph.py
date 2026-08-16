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
    AUTHORITATIVE_PATHS,
    DEFAULT_INVENTORY,
    GENERATED_ARTIFACT_PATHS,
    REPOSITORY_ROOT,
    AssetRecord,
    _ExactReferenceMatcher,
    inventory_from_payload,
)


CONSUMER_GRAPH_SCHEMA = "pimm-consumer-graph/v1"
_TEXT_SUFFIXES = frozenset(
    {".liquid", ".json", ".jsonl", ".css", ".js", ".mjs", ".py", ".ps1", ".bat", ".cmd", ".yaml", ".yml"}
)
_IGNORED_PARTS = frozenset(
    {
        ".git",
        ".worktrees",
        ".material-library-candidate",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
    }
)
_GENERATED_GRAPH_INPUTS = frozenset(path.casefold() for path in GENERATED_ARTIFACT_PATHS)
_PRODUCER_HINT = re.compile(r"(?:output|destination|render|write|publish|release|target)", re.IGNORECASE)


def _normalize_values(values: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(sorted({str(value).replace("\\", "/") for value in values or ()}, key=str.casefold))


@dataclass(frozen=True)
class ConsumerGraph:
    consumers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    producers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    unresolved_references: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    ambiguous_references: Mapping[str, Mapping[str, tuple[str, ...]]] = field(
        default_factory=dict
    )
    authoritative_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "consumers", {key: _normalize_values(values) for key, values in self.consumers.items()})
        object.__setattr__(self, "producers", {key: _normalize_values(values) for key, values in self.producers.items()})
        object.__setattr__(
            self,
            "unresolved_references",
            {key: _normalize_values(values) for key, values in self.unresolved_references.items()},
        )
        object.__setattr__(
            self,
            "ambiguous_references",
            {
                key: {
                    "candidate_paths": _normalize_values(value.get("candidate_paths")),
                    "evidence": _normalize_values(value.get("evidence")),
                }
                for key, value in self.ambiguous_references.items()
            },
        )
        object.__setattr__(self, "authoritative_paths", _normalize_values(self.authoritative_paths))


def _text_files(root: Path, *, exclude_generated: bool = False):
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
        if exclude_generated and relative.as_posix().casefold() in _GENERATED_GRAPH_INPUTS:
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
    unresolved_references: dict[str, set[str]],
    ambiguous_references: dict[str, dict[str, set[str]]],
) -> None:
    for text_path in _text_files(root, exclude_generated=root_name == "asset"):
        try:
            lines = text_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            matched_paths, ambiguous = matcher.match_details(line)
            evidence = _display(root_name, root, text_path, line_number)
            for basename, candidate_paths in ambiguous.items():
                unresolved_references.setdefault(basename, set()).add(evidence)
                entry = ambiguous_references.setdefault(
                    basename,
                    {"candidate_paths": set(), "evidence": set()},
                )
                entry["candidate_paths"].update(candidate_paths)
                entry["evidence"].add(evidence)
            for record_path in matched_paths:
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
    unresolved_references: dict[str, set[str]] = {}
    ambiguous_references: dict[str, dict[str, set[str]]] = {}
    by_path = {record.path.casefold(): record.path for record in records}
    candidates = {
        record.path: asset_root / PurePosixPath(record.path) for record in records
    }
    matcher = _ExactReferenceMatcher(candidates)
    _scan_text_root(
        "repo",
        repo_root,
        records,
        matcher,
        consumers,
        producers,
        unresolved_references,
        ambiguous_references,
    )
    _scan_text_root(
        "asset",
        asset_root,
        records,
        matcher,
        consumers,
        producers,
        unresolved_references,
        ambiguous_references,
    )

    for record in records:
        for dependency in record.dependencies:
            evidence_values = record.dependency_evidence.get(dependency, ("datablock:untyped",))
            normalized_dependency = dependency.replace("\\", "/")
            dependency_path = Path(dependency)
            if dependency_path.is_absolute():
                try:
                    normalized_dependency = dependency_path.relative_to(asset_root).as_posix()
                except ValueError:
                    normalized_dependency = dependency.replace("\\", "/")
            canonical_dependency = by_path.get(normalized_dependency.casefold())
            if canonical_dependency is None:
                basename = PurePosixPath(normalized_dependency).name.casefold()
                matches = [path for path in by_path.values() if PurePosixPath(path).name.casefold() == basename]
                if "/" not in normalized_dependency and len(matches) == 1:
                    canonical_dependency = matches[0]
                else:
                    for evidence in evidence_values:
                        rendered_evidence = f"asset:{record.path}#{evidence}"
                        unresolved_references.setdefault(normalized_dependency, set()).add(
                            rendered_evidence
                        )
                        if "/" not in normalized_dependency and len(matches) > 1:
                            entry = ambiguous_references.setdefault(
                                normalized_dependency.casefold(),
                                {"candidate_paths": set(), "evidence": set()},
                            )
                            entry["candidate_paths"].update(matches)
                            entry["evidence"].add(rendered_evidence)
                    continue
            for evidence in evidence_values:
                consumers.setdefault(canonical_dependency, set()).add(f"asset:{record.path}#{evidence}")
                producers[record.path].add(f"dependency:{canonical_dependency}#{evidence}")

    return ConsumerGraph(
        consumers={key: tuple(sorted(values, key=str.casefold)) for key, values in sorted(consumers.items())},
        producers={key: tuple(sorted(values, key=str.casefold)) for key, values in sorted(producers.items())},
        unresolved_references={
            key: tuple(sorted(values, key=str.casefold))
            for key, values in sorted(unresolved_references.items())
        },
        ambiguous_references={
            key: {
                "candidate_paths": tuple(
                    sorted(value["candidate_paths"], key=str.casefold)
                ),
                "evidence": tuple(sorted(value["evidence"], key=str.casefold)),
            }
            for key, value in sorted(ambiguous_references.items())
        },
        authoritative_paths=tuple(
            path
            for path in sorted(AUTHORITATIVE_PATHS, key=str.casefold)
            if path.casefold() in by_path
        ),
    )


def classify_record(
    record: AssetRecord,
    graph: ConsumerGraph,
) -> Literal["authoritative", "active-linked-scene", "migrate", "pending-archive", "unresolved"]:
    """Apply fail-closed archive classification to one current record."""

    authoritative_paths = {path.casefold() for path in graph.authoritative_paths}
    if record.path.casefold() in authoritative_paths and record.path in AUTHORITATIVE_PATHS:
        return "authoritative"
    missing_dependencies = record.blender_inspection.get("missing_dependencies", ())
    if record.blender_inspection.get("inspection_error") or missing_dependencies:
        return "unresolved"
    if any(
        value.get("evidence")
        and record.path.casefold()
        in {path.casefold() for path in value.get("candidate_paths", ())}
        for value in graph.ambiguous_references.values()
    ):
        return "unresolved"
    if record.kind == "blend-project" and any(
        dependency.replace("\\", "/").casefold() in authoritative_paths
        for dependency in record.dependencies
    ):
        return "active-linked-scene"
    summary_has_unique_content = bool(
        int(record.blender_inspection.get("object_count", 0) or 0)
        or int(record.blender_inspection.get("mesh_datablock_count", 0) or 0)
        or int(record.blender_inspection.get("material_count", 0) or 0)
    )
    if graph.consumers.get(record.path) or record.consumers or record.unique_content or summary_has_unique_content:
        return "migrate"
    if record.kind == "blend-recovery" or record.path.casefold().endswith(".blend1"):
        return "pending-archive"
    return "unresolved"


def consumer_graph_payload(
    graph: ConsumerGraph, *, publication_id: str | None = None
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": CONSUMER_GRAPH_SCHEMA,
        "consumers": {key: list(values) for key, values in graph.consumers.items()},
        "producers": {key: list(values) for key, values in graph.producers.items()},
        "unresolved_references": {
            key: list(values) for key, values in graph.unresolved_references.items()
        },
        "ambiguous_references": {
            key: {
                "candidate_paths": list(value.get("candidate_paths", ())),
                "evidence": list(value.get("evidence", ())),
            }
            for key, value in graph.ambiguous_references.items()
        },
        "authoritative_paths": list(graph.authoritative_paths),
    }
    if publication_id is not None:
        payload["publication_id"] = publication_id
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--asset-root", type=Path, default=ASSET_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inventory = inventory_from_payload(json.loads(args.inventory.read_text(encoding="utf-8")))
    graph = build_consumer_graph(args.repo_root, args.asset_root, inventory.records)
    print(json.dumps(consumer_graph_payload(graph), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
