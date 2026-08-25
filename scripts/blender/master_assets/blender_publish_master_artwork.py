"""Publish existing master-owned PIMM artwork without altering visual data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import bpy

from scripts.blender.pimm_production.published_artwork import (
    ARTWORK_SPECS_BY_MACHINE,
    PUBLISHED_ARTWORK_COUNT_PROPERTY,
    PUBLISHED_ARTWORK_SHA256_PROPERTY,
    canonical_artwork_evidence,
    capture_published_artwork,
    protected_artwork_evidence,
    validate_published_artwork,
)
from scripts.blender.pimm_production.scene_contract import (
    PUBLISHED_STABLE_ID_COUNT_PROPERTY,
    PUBLISHED_STABLE_ID_SHA256_PROPERTY,
    stable_id_evidence,
)


MARKER = "PIMM_ARTWORK_MIGRATION_JSON="


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", choices=tuple(ARTWORK_SPECS_BY_MACHINE), required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(blender_args())


def migrate(machine: str) -> dict[str, object]:
    published = bpy.data.collections.get("PIMM_PUBLISHED")
    decals = bpy.data.collections.get("PIMM_SURFACE_DECALS")
    if published is None or decals is None:
        raise RuntimeError("master requires PIMM_PUBLISHED and PIMM_SURFACE_DECALS")

    expected_specs = ARTWORK_SPECS_BY_MACHINE[machine]
    expected_names = {spec.object_name for spec in expected_specs}
    actual_meshes = {
        obj.name for obj in decals.all_objects if getattr(obj, "type", None) == "MESH"
    }
    if actual_meshes != expected_names:
        raise RuntimeError(
            f"PIMM_SURFACE_DECALS exact object mismatch: expected={sorted(expected_names)} "
            f"actual={sorted(actual_meshes)}"
        )

    before_records, before_errors = capture_published_artwork(decals, machine)
    if before_errors:
        raise RuntimeError("; ".join(before_errors))
    before_by_role = {str(record["role"]): record for record in before_records}
    if set(before_by_role) != {spec.role for spec in expected_specs}:
        raise RuntimeError("existing artwork roles do not match the governed contract")
    for spec in expected_specs:
        record = before_by_role[spec.role]
        expected = {
            "machine": machine,
            "object_name": spec.object_name,
            "asset_key": spec.asset_key,
            "attached_parent": spec.attached_parent,
            "image_relative_path": spec.image_relative_path,
            "image_sha256": spec.image_sha256,
            "packed_sha256": spec.image_sha256,
            "render_visible": True,
        }
        mismatches = {
            key: (expected_value, record.get(key))
            for key, expected_value in expected.items()
            if record.get(key) != expected_value
        }
        obj = bpy.data.objects[spec.object_name]
        materials = [material for material in obj.data.materials if material]
        if len(materials) != 1 or materials[0].name != spec.material_name:
            mismatches["material_name"] = (spec.material_name, [m.name for m in materials])
        if obj.get("pimm_surface_attached") is not True:
            mismatches["pimm_surface_attached"] = (True, obj.get("pimm_surface_attached"))
        if obj.get("pimm_image_packed") is not True:
            mismatches["pimm_image_packed"] = (True, obj.get("pimm_image_packed"))
        if mismatches:
            raise RuntimeError(f"existing artwork contract mismatch for {spec.role}: {mismatches}")

    protected_before = protected_artwork_evidence(before_records)
    stable_ids_before = {
        str(obj.get("pimm_stable_id"))
        for obj in published.all_objects
        if getattr(obj, "type", None) == "MESH" and obj.get("pimm_stable_id")
    }
    stable_evidence_before = stable_id_evidence(stable_ids_before)
    embedded_stable_before = (
        published.get(PUBLISHED_STABLE_ID_COUNT_PROPERTY),
        published.get(PUBLISHED_STABLE_ID_SHA256_PROPERTY),
    )
    if embedded_stable_before != stable_evidence_before:
        raise RuntimeError("geometry stable-ID evidence is invalid before artwork migration")

    for spec in expected_specs:
        material = bpy.data.materials.get(spec.material_name)
        if material is None:
            raise RuntimeError(f"missing existing artwork material: {spec.material_name}")
        material["pimm_material_id"] = spec.material_id
        material["pimm_material_scope"] = "machine-local"
    if decals.name not in published.children:
        published.children.link(decals)

    after_records, capture_errors = capture_published_artwork(published, machine)
    if capture_errors:
        raise RuntimeError("; ".join(capture_errors))
    if protected_artwork_evidence(after_records) != protected_before:
        raise RuntimeError("protected artwork fingerprint changed during migration")
    stable_ids_after = {
        str(obj.get("pimm_stable_id"))
        for obj in published.all_objects
        if getattr(obj, "type", None) == "MESH" and obj.get("pimm_stable_id")
    }
    if stable_id_evidence(stable_ids_after) != stable_evidence_before:
        raise RuntimeError("geometry stable-ID evidence changed during artwork migration")

    artwork_count, artwork_sha256 = canonical_artwork_evidence(after_records)
    published[PUBLISHED_ARTWORK_COUNT_PROPERTY] = artwork_count
    published[PUBLISHED_ARTWORK_SHA256_PROPERTY] = artwork_sha256
    _, validation_errors = validate_published_artwork(published, machine)
    if validation_errors:
        raise RuntimeError("; ".join(validation_errors))

    return {
        "schema_version": 1,
        "machine": machine,
        "geometry_stable_id_count": stable_evidence_before[0],
        "geometry_stable_id_sha256": stable_evidence_before[1],
        "artwork_count": artwork_count,
        "artwork_sha256": artwork_sha256,
        "protected_artwork_sha256": protected_before[1],
        "artwork": after_records,
    }


def main() -> None:
    args = parse_args()
    source = Path(bpy.data.filepath).resolve()
    if not source.is_file():
        raise RuntimeError(f"open Blender source is missing: {source}")
    source_sha256 = sha256_file(source)
    if source_sha256 != args.expected_source_sha256.upper():
        raise RuntimeError(
            f"source SHA-256 mismatch: expected={args.expected_source_sha256.upper()} "
            f"actual={source_sha256}"
        )
    if bpy.context.scene.get("pimm_master_machine") != args.machine:
        raise RuntimeError("open master machine identity does not match --machine")

    report = migrate(args.machine)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output), check_existing=False)
    report.update(
        {
            "source_path": str(source),
            "source_sha256": source_sha256,
            "output_path": str(args.output.resolve()),
            "output_sha256": sha256_file(args.output.resolve()),
        }
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(MARKER + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
