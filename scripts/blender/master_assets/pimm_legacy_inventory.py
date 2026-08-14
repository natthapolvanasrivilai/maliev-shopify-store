"""Read-only inventory and migration classification for PIMM Blender projects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ASSET_ROOT = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders")
MANIFEST_ROOT = ASSET_ROOT / "manifests"
DEFAULT_INVENTORY = MANIFEST_ROOT / "blender-project-inventory.json"
DEFAULT_REPORT = MANIFEST_ROOT / "blender-project-migration-report.md"
AUTHORITATIVE_NAMES = {
    "PIMM-30G-MASTER.blend",
    "PIMM-50G-MASTER.blend",
    "PIMM-MATERIAL-LIBRARY.blend",
}
ALLOWED_DISPOSITIONS = {
    "keep-authoritative",
    "migrate-scene",
    "archive-after-validation",
    "review",
}
TEXT_SUFFIXES = {
    ".py",
    ".ps1",
    ".bat",
    ".cmd",
    ".md",
    ".txt",
    ".json",
    ".mjs",
    ".js",
    ".liquid",
    ".css",
    ".yml",
    ".yaml",
}
IGNORED_PARTS = {".git", ".worktrees", "node_modules", "archive", "__pycache__"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def classify_project(
    relative_path: Path,
    consumers: list[str],
    duplicate_group: str | None,
    unique_content: bool,
) -> str:
    if relative_path.name in AUTHORITATIVE_NAMES and "masters" in {
        part.lower() for part in relative_path.parts
    }:
        return "keep-authoritative"
    if consumers:
        return "migrate-scene"
    if relative_path.suffix.lower() == ".blend1" or duplicate_group:
        return "archive-after-validation"
    if unique_content:
        return "review"
    return "review"


def _text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        yield path


def _consumer_map(projects: list[Path]) -> dict[str, list[str]]:
    names = {path.name for path in projects}
    consumers = {name: [] for name in names}
    search_roots = (REPOSITORY_ROOT, ASSET_ROOT / "scripts")
    for root in search_roots:
        if not root.exists():
            continue
        for text_path in _text_files(root):
            try:
                content = text_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            matched = [name for name in names if name in content]
            for name in matched:
                try:
                    display = str(text_path.relative_to(REPOSITORY_ROOT))
                except ValueError:
                    display = str(text_path)
                consumers[name].append(display)
    return {name: sorted(set(paths)) for name, paths in consumers.items()}


def scan_projects(root: Path = ASSET_ROOT) -> dict[str, Any]:
    projects = sorted(
        [
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".blend", ".blend1"}
            and "archive" not in {part.lower() for part in path.parts}
        ],
        key=lambda path: str(path).lower(),
    )
    consumers = _consumer_map(projects)
    records: list[dict[str, Any]] = []
    hashes: dict[str, list[str]] = {}
    for index, path in enumerate(projects, start=1):
        stat = path.stat()
        digest = sha256_file(path)
        relative = path.relative_to(root)
        hashes.setdefault(digest, []).append(str(relative))
        records.append(
            {
                "path": str(path.resolve()),
                "relative_path": str(relative),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": digest,
                "consumers": consumers.get(path.name, []),
                "blender": None,
            }
        )
        print(f"PIMM_LEGACY_HASH files={index}/{len(projects)} path={relative}")

    duplicate_hashes = {digest for digest, paths in hashes.items() if len(paths) > 1}
    for record in records:
        record["duplicate_group"] = (
            record["sha256"][:16] if record["sha256"] in duplicate_hashes else None
        )
    return {
        "schema_version": 1,
        "root": str(root.resolve()),
        "projects": records,
        "summary": {
            "project_count": len(records),
            "bytes": sum(record["size"] for record in records),
            "duplicate_group_count": len(duplicate_hashes),
        },
    }


def write_json(data: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, destination)


def enrich_with_blender(inventory_path: Path) -> dict[str, Any]:
    import bpy

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    for index, record in enumerate(inventory["projects"], start=1):
        path = Path(record["path"])
        try:
            bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
            meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
            product_objects = [
                obj
                for obj in meshes
                if obj.get("pimm_stable_id")
                or any(token in obj.name.lower() for token in ("pimm", "30g", "50g"))
            ]
            record["blender"] = {
                "version": ".".join(str(value) for value in bpy.data.version),
                "scenes": sorted(scene.name for scene in bpy.data.scenes),
                "mesh_object_count": len(meshes),
                "product_object_count": len(product_objects),
                "camera_count": sum(obj.type == "CAMERA" for obj in bpy.data.objects),
                "light_count": sum(obj.type == "LIGHT" for obj in bpy.data.objects),
                "action_count": len(bpy.data.actions),
                "animated_object_count": sum(
                    obj.animation_data is not None for obj in bpy.data.objects
                ),
                "linked_libraries": sorted(
                    library.filepath for library in bpy.data.libraries
                ),
                "referenced_images": sorted(
                    image.filepath for image in bpy.data.images if image.filepath
                ),
                "inspection_error": None,
            }
        except Exception as error:
            record["blender"] = {
                "inspection_error": f"{type(error).__name__}: {error}"
            }
        print(
            f"PIMM_LEGACY_INSPECT files={index}/{len(inventory['projects'])} "
            f"path={record['relative_path']}"
        )
    write_json(inventory, inventory_path)
    return inventory


def finalize_inventory(inventory_path: Path, report_path: Path) -> dict[str, Any]:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    dispositions = {value: 0 for value in sorted(ALLOWED_DISPOSITIONS)}
    for record in inventory["projects"]:
        blender = record.get("blender") or {}
        unique_content = bool(
            blender.get("camera_count", 0)
            or blender.get("light_count", 0)
            or blender.get("action_count", 0)
            or blender.get("animated_object_count", 0)
        )
        disposition = classify_project(
            Path(record["relative_path"]),
            record["consumers"],
            record["duplicate_group"],
            unique_content,
        )
        if disposition not in ALLOWED_DISPOSITIONS:
            raise RuntimeError(f"forbidden inventory disposition: {disposition}")
        record["unique_scene_content"] = unique_content
        record["proposed_disposition"] = disposition
        dispositions[disposition] += 1
    inventory["summary"]["dispositions"] = dispositions
    write_json(inventory, inventory_path)

    lines = [
        "# PIMM Blender Project Migration Report",
        "",
        f"- Root: `{inventory['root']}`",
        f"- Projects inventoried: {inventory['summary']['project_count']}",
        f"- Total bytes: {inventory['summary']['bytes']}",
        f"- Duplicate groups: {inventory['summary']['duplicate_group_count']}",
        "- No file was moved, renamed, or deleted by this inventory.",
        "",
        "## Disposition summary",
        "",
    ]
    lines.extend(
        f"- `{name}`: {count}" for name, count in sorted(dispositions.items())
    )
    lines.extend(
        [
            "",
            "## Projects",
            "",
            "| Project | Size MiB | Consumers | Scenes | Animation | Disposition |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for record in inventory["projects"]:
        blender = record.get("blender") or {}
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{record['relative_path']}`",
                    f"{record['size'] / 1024 / 1024:.1f}",
                    str(len(record["consumers"])),
                    str(len(blender.get("scenes", []))),
                    str(blender.get("action_count", 0)),
                    f"`{record['proposed_disposition']}`",
                )
            )
            + " |"
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(".md.tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary, report_path)
    return inventory


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true")
    group.add_argument("--enrich", action="store_true")
    group.add_argument("--finalize", action="store_true")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(blender_args())


def main() -> None:
    args = parse_args()
    if args.scan:
        inventory = scan_projects()
        write_json(inventory, args.inventory)
    elif args.enrich:
        inventory = enrich_with_blender(args.inventory)
    else:
        inventory = finalize_inventory(args.inventory, args.report)
    print(
        "PIMM_LEGACY_INVENTORY "
        f"projects={inventory['summary']['project_count']} mode="
        f"{'scan' if args.scan else 'enrich' if args.enrich else 'finalize'}"
    )


if __name__ == "__main__":
    main()
