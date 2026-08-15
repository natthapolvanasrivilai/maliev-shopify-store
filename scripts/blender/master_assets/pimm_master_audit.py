"""Read-only integrity and material audit for an open PIMM machine master."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

ASSET_ROOT = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders")
MANIFEST_ROOT = ASSET_ROOT / "manifests"
SHARED_LIBRARY_NAME = "PIMM-MATERIAL-LIBRARY.blend"
MACHINE_LOCAL_TOKENS = (
    "MALIEV",
    "DECAL",
    "DISPLAY",
    "CONTROLLER",
    "SERIAL",
    "AIRTAC",
    "LOGO",
)

from scripts.blender.master_assets.pimm_master_builder import (
    BLENDER_LENGTH_UNIT,
    BLENDER_SCENE_SCALE_LENGTH,
    BLENDER_UNIT_SYSTEM,
    SOURCE_TO_BLENDER_SCALE,
)


@dataclass(frozen=True)
class AuditObjectRecord:
    stable_id: str
    material_state: str
    material_ids: tuple[str, ...]
    material_scopes: tuple[str, ...]
    material_linked: tuple[bool, ...]
    multi_material_exception: str
    disconnected_components: int
    geometry_exception: str = ""


@dataclass
class AuditResult:
    unassigned_ids: list[str]
    multi_material_exceptions: list[str]
    disconnected_geometry: list[str]
    linked_shared_materials: list[str]
    local_machine_materials: list[str]
    publishable: bool
    errors: list[str]


def evaluate_records(
    records: list[AuditObjectRecord], mode: Literal["working", "publish"]
) -> AuditResult:
    if mode not in {"working", "publish"}:
        raise ValueError(f"unsupported audit mode: {mode}")
    errors: list[str] = []
    unassigned: list[str] = []
    documented_multi: list[str] = []
    disconnected: list[str] = []
    linked_shared: set[str] = set()
    machine_local: set[str] = set()
    seen: set[str] = set()

    for record in records:
        if record.stable_id in seen:
            errors.append(f"duplicate stable solid ID: {record.stable_id}")
        seen.add(record.stable_id)
        if not record.material_ids:
            errors.append(f"object has no material: {record.stable_id}")
        if len(record.material_ids) > 1:
            if record.multi_material_exception.strip():
                documented_multi.append(record.stable_id)
            else:
                errors.append(
                    f"object has multiple material slots without exception: {record.stable_id}"
                )
        if not (
            len(record.material_ids)
            == len(record.material_scopes)
            == len(record.material_linked)
        ):
            errors.append(f"material audit tuple mismatch: {record.stable_id}")
            continue

        if record.material_state == "unassigned":
            unassigned.append(record.stable_id)
        elif record.material_state != "approved":
            errors.append(
                f"unknown material assignment state {record.material_state}: {record.stable_id}"
            )

        for material_id, scope, linked in zip(
            record.material_ids, record.material_scopes, record.material_linked
        ):
            if any(token in material_id.upper() for token in MACHINE_LOCAL_TOKENS):
                if scope == "shared":
                    errors.append(
                        f"machine-local semantic marked shared: {record.stable_id}/{material_id}"
                    )
                machine_local.add(material_id)
            if scope == "shared":
                linked_shared.add(material_id)
                if not linked:
                    errors.append(
                        f"local copy of shared material: {record.stable_id}/{material_id}"
                    )
            elif scope == "machine-local":
                machine_local.add(material_id)
                if linked:
                    errors.append(
                        f"machine-local material unexpectedly linked: {record.stable_id}/{material_id}"
                    )
            else:
                errors.append(
                    f"unknown material scope {scope}: {record.stable_id}/{material_id}"
                )

        if record.disconnected_components > 1 and not record.geometry_exception.strip():
            disconnected.append(record.stable_id)

    if mode == "publish" and unassigned:
        errors.append(f"{len(unassigned)} objects remain unassigned")
    if mode == "publish" and disconnected:
        errors.append(
            f"{len(disconnected)} objects contain unexplained disconnected geometry"
        )
    publishable = not errors and not unassigned and not disconnected
    return AuditResult(
        unassigned_ids=sorted(unassigned),
        multi_material_exceptions=sorted(documented_multi),
        disconnected_geometry=sorted(disconnected),
        linked_shared_materials=sorted(linked_shared),
        local_machine_materials=sorted(machine_local),
        publishable=publishable,
        errors=errors,
    )


def _mesh_component_count(mesh) -> int:
    import bmesh

    if not mesh.vertices:
        return 0
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
        unseen = set(bm.verts)
        components = 0
        while unseen:
            components += 1
            stack = [unseen.pop()]
            while stack:
                vertex = stack.pop()
                for edge in vertex.link_edges:
                    neighbor = edge.other_vert(vertex)
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        stack.append(neighbor)
        return components
    finally:
        bm.free()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def audit_open_master(
    mode: Literal["working", "publish"], *, deep_geometry: bool = True
) -> dict:
    import bpy

    master_scene = next(
        (scene for scene in bpy.data.scenes if scene.get("pimm_master_machine")), None
    )
    if master_scene is None:
        raise RuntimeError("open file is not a PIMM machine master")
    machine = master_scene["pimm_master_machine"]
    manifest_path = MANIFEST_ROOT / f"PIMM-{machine}-import-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {solid["stable_id"]: solid for solid in manifest["solids"]}

    master_path = Path(bpy.data.filepath)
    master_before = {
        "path": str(master_path.resolve()),
        "size": master_path.stat().st_size,
        "mtime_ns": master_path.stat().st_mtime_ns,
        "sha256": _sha256(master_path),
    }
    source_path = Path(manifest["source"]["path"])
    source_before = {
        "path": str(source_path.resolve()),
        "size": source_path.stat().st_size,
        "mtime_ns": source_path.stat().st_mtime_ns,
        "sha256": _sha256(source_path),
    }
    integrity_errors: list[str] = []
    records: list[AuditObjectRecord] = []
    products = [obj for obj in bpy.data.objects if obj.get("pimm_stable_id")]
    for index, obj in enumerate(products, start=1):
        stable_id = obj["pimm_stable_id"]
        expected_solid = expected.get(stable_id)
        if expected_solid is None:
            integrity_errors.append(f"object is absent from import manifest: {stable_id}")
        elif obj.get("pimm_geometry_signature") != expected_solid["geometry_signature"]:
            integrity_errors.append(f"geometry signature drifted: {stable_id}")
        missing = sorted(
            key
            for key in (
                "pimm_machine",
                "pimm_step_sha256",
                "pimm_product_id",
                "pimm_occurrence_id",
                "pimm_assembly_path",
                "pimm_solid_index",
                "pimm_original_cad_name",
                "pimm_geometry_signature",
                "pimm_part_name",
                "pimm_material_state",
                "pimm_source_to_blender_scale",
            )
            if key not in obj
        )
        if missing:
            integrity_errors.append(f"object lacks provenance {missing}: {stable_id}")
        if not all(
            abs(value - SOURCE_TO_BLENDER_SCALE) <= 1e-7
            for value in obj.scale
        ):
            integrity_errors.append(f"object import scale drifted: {stable_id}")
        if abs(
            obj.get("pimm_source_to_blender_scale", 0.0) - SOURCE_TO_BLENDER_SCALE
        ) > 1e-7:
            integrity_errors.append(f"object scale provenance drifted: {stable_id}")

        materials = tuple(material for material in obj.data.materials if material)
        material_ids = tuple(
            material.get("pimm_material_id", material.name.removeprefix("PIMM_"))
            for material in materials
        )
        material_scopes = tuple(
            material.get("pimm_material_scope", "unknown") for material in materials
        )
        material_linked = tuple(material.library is not None for material in materials)
        disconnected_components = (
            _mesh_component_count(obj.data) if deep_geometry else 1
        )
        records.append(
            AuditObjectRecord(
                stable_id=stable_id,
                material_state=obj.get("pimm_material_state", "missing"),
                material_ids=material_ids,
                material_scopes=material_scopes,
                material_linked=material_linked,
                multi_material_exception=obj.get(
                    "pimm_multi_material_exception", ""
                ),
                disconnected_components=disconnected_components,
                geometry_exception=obj.get("pimm_geometry_exception", ""),
            )
        )
        if index % 100 == 0:
            print(f"PIMM_MASTER_AUDIT_PROGRESS machine={machine} objects={index}/{len(products)}")

    actual_ids = {record.stable_id for record in records}
    missing_ids = sorted(set(expected) - actual_ids)
    if missing_ids:
        integrity_errors.append(f"master is missing {len(missing_ids)} manifest solids")
    forbidden = [obj.name for obj in bpy.data.objects if obj.type in {"CAMERA", "LIGHT"}]
    if forbidden:
        integrity_errors.append(f"master contains forbidden cameras/lights: {forbidden}")
    if master_scene.unit_settings.system != BLENDER_UNIT_SYSTEM:
        integrity_errors.append("master scene unit system drifted")
    if master_scene.unit_settings.length_unit != BLENDER_LENGTH_UNIT:
        integrity_errors.append("master scene length unit drifted")
    if abs(master_scene.unit_settings.scale_length - BLENDER_SCENE_SCALE_LENGTH) > 1e-7:
        integrity_errors.append("master scene scale length drifted")

    result = evaluate_records(records, mode)
    result.errors[:0] = integrity_errors
    result.publishable = (
        not result.errors
        and not result.unassigned_ids
        and not result.disconnected_geometry
    )
    source_after = {
        "path": str(source_path.resolve()),
        "size": source_path.stat().st_size,
        "mtime_ns": source_path.stat().st_mtime_ns,
        "sha256": _sha256(source_path),
    }
    master_after = {
        "path": str(master_path.resolve()),
        "size": master_path.stat().st_size,
        "mtime_ns": master_path.stat().st_mtime_ns,
        "sha256": _sha256(master_path),
    }
    if source_after != source_before:
        result.errors.append("authoritative STEP source changed during audit")
    if master_after != master_before:
        result.errors.append("machine master changed during read-only audit")

    return {
        "schema_version": 1,
        "mode": mode,
        "machine": machine,
        "source_ok": source_after == source_before,
        "master_unchanged": master_after == master_before,
        "object_count": len(records),
        "unique_id_count": len(actual_ids),
        "manifest_solid_count": len(expected),
        **asdict(result),
        "source": source_after,
        "master": master_after,
    }


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("working", "publish"), default="working")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-deep-geometry", action="store_true")
    return parser.parse_args(blender_args())


def main() -> None:
    args = parse_args()
    report = audit_open_master(
        args.mode, deep_geometry=not args.skip_deep_geometry
    )
    output = args.output or MANIFEST_ROOT / f"PIMM-{report['machine']}-material-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, output)
    print(
        "PIMM_MASTER_AUDIT "
        f"machine={report['machine']} mode={report['mode']} "
        f"objects={report['object_count']} unassigned={len(report['unassigned_ids'])} "
        f"disconnected={len(report['disconnected_geometry'])} "
        f"errors={len(report['errors'])} publishable={report['publishable']} path={output}"
    )
    if report["errors"]:
        raise RuntimeError("; ".join(report["errors"][:10]))


if __name__ == "__main__":
    main()
