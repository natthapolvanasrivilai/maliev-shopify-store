"""Refresh a machine master from a newer STEP manifest without losing manual materials.

The refresh is intentionally conservative: it snapshots the existing CAD objects,
replaces only objects carrying ``pimm_stable_id``, transfers approved material
slots by CAD identity/geometry, and leaves every unmatched new solid linked to
``PIMM_UNASSIGNED``.  The source master is never saved in place; callers must
provide a separate candidate output path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.blender.master_assets import pimm_master_builder as builder
from scripts.blender.master_assets.pimm_step_manifest import validate_manifest_structure


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def file_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def _path_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(part) for part in value)
    return ()


def _center(solid: dict[str, Any]) -> tuple[float, float, float] | None:
    metrics = solid.get("geometry", {})
    values = metrics.get("center_of_mass")
    if not isinstance(values, list) or len(values) != 3:
        return None
    try:
        return tuple(float(value) for value in values)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def _distance(a: tuple[float, float, float] | None, b: tuple[float, float, float] | None) -> float:
    if a is None or b is None:
        return math.inf
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b)))


def _material_names(obj) -> list[str]:
    return [material.name for material in obj.data.materials if material is not None]


def _is_unassigned(material_names: list[str]) -> bool:
    return not material_names or all(name == "PIMM_UNASSIGNED" for name in material_names)


def _snapshot_old_objects(bpy, old_manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_solids = {solid["stable_id"]: solid for solid in old_manifest.get("solids", [])}
    records: list[dict[str, Any]] = []
    nonstable = [obj.name for obj in bpy.data.objects if not obj.get("pimm_stable_id")]
    for obj in (obj for obj in bpy.data.objects if obj.get("pimm_stable_id")):
        stable_id = str(obj["pimm_stable_id"])
        solid = manifest_solids.get(stable_id, {})
        materials = _material_names(obj)
        assigned = not _is_unassigned(materials)
        if assigned and len(set(materials)) > 1:
            raise RuntimeError(
                f"manual multi-material object requires review before refresh: {obj.name}"
            )
        records.append(
            {
                "stable_id": stable_id,
                "original_name": str(obj.get("pimm_original_cad_name", solid.get("original_name", ""))),
                "solid_index": int(obj.get("pimm_solid_index", solid.get("solid_index", 0))),
                "assembly_path": _path_tuple(obj.get("pimm_assembly_path", solid.get("assembly_path", []))),
                "center": _center(solid),
                "materials": materials,
                "material_state": str(obj.get("pimm_material_state", "unassigned")),
                "part_name": str(obj.get("pimm_part_name", obj.name)),
                "multi_material_exception": str(obj.get("pimm_multi_material_exception", "")),
                "geometry_exception": str(obj.get("pimm_geometry_exception", "")),
                "assigned": assigned,
            }
        )
    return records, {"old_object_count": len(records), "nonstable_names": nonstable}


def _match_new_solid(solid: dict[str, Any], old_records: list[dict[str, Any]], used: set[str]) -> tuple[dict[str, Any] | None, str]:
    name = str(solid.get("original_name", ""))
    solid_index = int(solid.get("solid_index", 0))
    path = _path_tuple(solid.get("assembly_path", []))
    center = _center(solid)
    candidates = [
        record
        for record in old_records
        if record["stable_id"] not in used
        and record["original_name"] == name
        and record["solid_index"] == solid_index
    ]
    if not candidates:
        candidates = [
            record
            for record in old_records
            if record["stable_id"] not in used and record["original_name"] == name
        ]
    if not candidates:
        return None, "no-name-match"

    def rank(record: dict[str, Any]) -> tuple[int, int, float]:
        record_path = record["assembly_path"]
        exact_path = int(record_path != path)
        leaf_match = int(bool(path and record_path and path[-1] != record_path[-1]))
        return exact_path, leaf_match, _distance(record["center"], center)

    candidates.sort(key=rank)
    chosen = candidates[0]
    return chosen, "exact" if chosen["assembly_path"] == path else "nearest-name"


def _find_unassigned(bpy):
    material = bpy.data.materials.get("PIMM_UNASSIGNED")
    if material is not None:
        return material
    return builder._link_unassigned_material(bpy, builder.MATERIAL_LIBRARY)


def _ensure_working(bpy):
    working = bpy.data.collections.get("PIMM_WORKING")
    if working is None:
        raise RuntimeError("master has no PIMM_WORKING collection")
    return working


def _remove_old_cad(bpy, working) -> None:
    products = [obj for obj in bpy.data.objects if obj.get("pimm_stable_id")]
    for obj in products:
        bpy.data.objects.remove(obj, do_unlink=True)
    cad_collections = [
        collection
        for collection in bpy.data.collections
        if collection.get("pimm_collection_type") == "CAD_ASSEMBLY"
    ]
    unexpected = [
        collection.name
        for collection in cad_collections
        if any(obj for obj in collection.all_objects if not obj.get("pimm_stable_id"))
    ]
    if unexpected:
        raise RuntimeError(f"CAD collections contain non-CAD objects: {unexpected}")
    for collection in cad_collections:
        bpy.data.collections.remove(collection, do_unlink=True)


def _assign_materials(bpy, obj, record: dict[str, Any] | None, unassigned) -> str:
    if record is None or not record["assigned"]:
        obj.data.materials.clear()
        obj.data.materials.append(unassigned)
        obj["pimm_material_state"] = "unassigned"
        return "unassigned"
    resolved = []
    missing = []
    for name in record["materials"]:
        material = bpy.data.materials.get(name)
        if material is None:
            missing.append(name)
        else:
            resolved.append(material)
    if missing or not resolved:
        raise RuntimeError(
            f"cannot preserve material assignment for {record['stable_id']}: missing={missing}"
        )
    obj.data.materials.clear()
    for material in resolved:
        obj.data.materials.append(material)
    obj["pimm_material_state"] = record["material_state"] if record["material_state"] != "unassigned" else "approved"
    obj["pimm_part_name"] = record["part_name"]
    if record["multi_material_exception"]:
        obj["pimm_multi_material_exception"] = record["multi_material_exception"]
    if record["geometry_exception"]:
        obj["pimm_geometry_exception"] = record["geometry_exception"]
    return "approved"


def validate_candidate(bpy, machine: str, manifest: dict[str, Any], old_summary: dict[str, Any], report: dict[str, Any]) -> None:
    products = [obj for obj in bpy.data.objects if obj.get("pimm_stable_id")]
    if len(products) != len(manifest["solids"]):
        raise RuntimeError(f"candidate CAD count mismatch: {len(products)} != {len(manifest['solids'])}")
    if len({obj["pimm_stable_id"] for obj in products}) != len(products):
        raise RuntimeError("candidate contains duplicate stable IDs")
    unassigned = [obj for obj in products if obj.get("pimm_material_state") == "unassigned"]
    assigned = [obj for obj in products if obj.get("pimm_material_state") == "approved"]
    if len(assigned) != report["transferred_assignment_count"]:
        raise RuntimeError("candidate assignment count does not match transfer report")
    for obj in products:
        if obj.type != "MESH" or len(obj.data.materials) != 1:
            raise RuntimeError(f"candidate object has unexpected mesh/material slots: {obj.name}")
        if not math.isclose(float(obj.get("pimm_source_to_blender_scale", 0.0)), builder.SOURCE_TO_BLENDER_SCALE, abs_tol=1e-12):
            raise RuntimeError(f"candidate scale provenance drifted: {obj.name}")
        if not all(math.isclose(abs(float(value)), builder.SOURCE_TO_BLENDER_SCALE, abs_tol=1e-7) for value in obj.scale):
            raise RuntimeError(f"candidate object scale drifted: {obj.name}")
        if obj.get("pimm_material_state") == "unassigned" and obj.data.materials[0].name != "PIMM_UNASSIGNED":
            raise RuntimeError(f"unassigned candidate object has a different material: {obj.name}")
    scene = bpy.data.scenes.get(f"PIMM_{machine}_MASTER")
    if scene is None:
        raise RuntimeError("candidate master scene missing")
    builder._configure_scene_units(scene)
    scene["pimm_source_step_sha256"] = manifest["source"]["sha256"]
    published = bpy.data.collections.get("PIMM_PUBLISHED")
    if published is None or any(True for _ in published.all_objects):
        raise RuntimeError("PIMM_PUBLISHED changed during refresh")
    if report["new_regulator_unassigned_count"] != 5:
        raise RuntimeError("expected exactly five new unassigned regulator bodies")
    if old_summary["nonstable_names"]:
        current = {obj.name for obj in bpy.data.objects}
        missing = sorted(set(old_summary["nonstable_names"]) - current)
        if missing:
            raise RuntimeError(f"non-CAD objects were lost during refresh: {missing}")


def refresh_master(machine: str, manifest_path: Path, old_manifest_path: Path, output: Path) -> dict[str, Any]:
    import bpy

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
    validate_manifest_structure(manifest)
    source = Path(manifest["source"]["path"])
    source_before = file_identity(source)
    if source_before["sha256"] != str(manifest["source"]["sha256"]).upper():
        raise RuntimeError("candidate manifest source hash does not match STEP on disk")
    if bpy.data.filepath.lower() == str(output.resolve()).lower():
        raise RuntimeError("candidate output must not overwrite the opened master")
    old_records, old_summary = _snapshot_old_objects(bpy, old_manifest)
    old_assigned = {record["stable_id"] for record in old_records if record["assigned"]}
    working = _ensure_working(bpy)
    preserved_names = set(old_summary["nonstable_names"])
    _remove_old_cad(bpy, working)
    unassigned = _find_unassigned(bpy)
    cache: dict[tuple[str, ...], Any] = {}
    used: set[str] = set()
    transferred = 0
    unmatched_assigned: list[str] = []
    mapping: list[dict[str, Any]] = []
    regulator_new: list[str] = []
    builder._configure_import_units(bpy.context.scene)
    for index, solid in enumerate(manifest["solids"], start=1):
        target = builder._ensure_assembly_collection(bpy, cache, working, solid["assembly_path"])
        obj = builder._import_one_solid(
            bpy, solid, machine, manifest["source"]["sha256"], target, unassigned
        )
        old_record, match_kind = _match_new_solid(solid, old_records, used)
        if old_record is not None:
            used.add(old_record["stable_id"])
        state = _assign_materials(bpy, obj, old_record, unassigned)
        if state == "approved":
            transferred += 1
        if old_record is not None and old_record["assigned"] and state != "approved":
            unmatched_assigned.append(old_record["stable_id"])
        if old_record is None and any("MSR8A-S" in str(part) for part in solid.get("assembly_path", [])):
            regulator_new.append(obj.name)
        mapping.append({
            "new_stable_id": solid["stable_id"],
            "new_name": obj.name,
            "old_stable_id": old_record["stable_id"] if old_record else None,
            "match": match_kind,
            "material_state": obj.get("pimm_material_state"),
            "materials": _material_names(obj),
        })
        if index % 25 == 0 or index == len(manifest["solids"]):
            print(f"PIMM_MASTER_REFRESH machine={machine} objects={index}/{len(manifest['solids'])}")
    if unmatched_assigned:
        raise RuntimeError(f"manual assignments were not transferred: {unmatched_assigned[:10]}")
    if old_assigned - used:
        raise RuntimeError(f"manual assignments had no new CAD match: {sorted(old_assigned - used)[:10]}")
    if len(regulator_new) != 5:
        raise RuntimeError(f"expected five new regulator solids, got {len(regulator_new)}")
    bpy.context.view_layer.update()
    scene = bpy.data.scenes.get(f"PIMM_{machine}_MASTER")
    if scene is not None:
        builder._configure_scene_units(scene)
        scene["pimm_source_step_sha256"] = manifest["source"]["sha256"]
    report = {
        "machine": machine,
        "source_before": source_before,
        "old_master": file_identity(Path(bpy.data.filepath)),
        "old_object_count": old_summary["old_object_count"],
        "new_object_count": len(manifest["solids"]),
        "old_assigned_count": len(old_assigned),
        "transferred_assignment_count": transferred,
        "new_unassigned_count": len(manifest["solids"]) - transferred,
        "new_regulator_unassigned_count": len(regulator_new),
        "new_regulator_objects": regulator_new,
        "preserved_nonstable_objects": sorted(preserved_names),
        "mapping": mapping,
    }
    validate_candidate(bpy, machine, manifest, old_summary, report)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + ".tmp.blend")
    temporary.unlink(missing_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(temporary), check_existing=False)
    os.replace(temporary, output)
    source_after = file_identity(source)
    if source_after != source_before:
        raise RuntimeError("authoritative STEP source changed during refresh")
    report["source_after"] = source_after
    report["candidate"] = file_identity(output)
    return report


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", choices=("30G", "50G"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--old-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(blender_args())


def main() -> None:
    args = parse_args()
    if args.validate_only:
        import bpy

        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report_path = args.output.with_suffix(".refresh-report.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        validate_candidate(
            bpy,
            args.machine,
            manifest,
            {"nonstable_names": report.get("preserved_nonstable_objects", [])},
            report,
        )
        print("PIMM_MASTER_REFRESH_VALIDATE " + json.dumps({"machine": args.machine, "path": bpy.data.filepath, "objects": report.get("new_object_count")}, sort_keys=True))
        return
    report = refresh_master(args.machine, args.manifest, args.old_manifest, args.output)
    report_path = args.output.with_suffix(".refresh-report.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PIMM_MASTER_REFRESH " + json.dumps({key: value for key, value in report.items() if key != "mapping"}, sort_keys=True))


if __name__ == "__main__":
    main()
