"""Build editable PIMM Blender masters from per-solid STEP manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


ASSET_ROOT = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders")
MANIFEST_ROOT = ASSET_ROOT / "manifests"
MASTER_ROOT = ASSET_ROOT / "masters"
MATERIAL_LIBRARY = MASTER_ROOT / "PIMM-MATERIAL-LIBRARY.blend"
SOURCE_TO_BLENDER_ROTATION_X = -math.pi / 2.0

REQUIRED_OBJECT_PROPERTIES = {
    "pimm_stable_id",
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
}


def safe_token(value: str, limit: int = 48) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return (token or "Unnamed")[:limit]


def master_object_name(machine: str, original_name: str, stable_id: str) -> str:
    suffix = stable_id.split("-", 1)[-1]
    return f"{machine}__{safe_token(original_name)}__{suffix}"


def collection_key(path: list[str]) -> str:
    encoded = "/".join(path).encode("utf-8")
    suffix = hashlib.sha256(encoded).hexdigest()[:10]
    return f"PIMM_ASM__{safe_token(path[-1])}__{suffix}"


def validate_import_manifest(manifest: dict[str, Any], machine: str) -> None:
    from scripts.blender.master_assets.pimm_step_manifest import (
        EXPECTED_SOURCES,
        validate_manifest_structure,
    )

    if manifest.get("source", {}).get("machine") != machine:
        raise ValueError(
            f"manifest machine mismatch: expected {machine}, "
            f"got {manifest.get('source', {}).get('machine')}"
        )
    validate_manifest_structure(manifest)
    expected = EXPECTED_SOURCES[machine]
    if manifest["source"].get("sha256", "").upper() != expected["sha256"]:
        raise ValueError("manifest source hash does not match authoritative STEP")


def _source_readback(manifest: dict[str, Any]) -> dict[str, Any]:
    from scripts.blender.master_assets.pimm_step_manifest import sha256_file

    source = Path(manifest["source"]["path"])
    stat = source.stat()
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(source),
    }


def _clear_blender(bpy) -> None:
    for scene in list(bpy.data.scenes)[1:]:
        bpy.data.scenes.remove(scene)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for material in list(bpy.data.materials):
        if material.library is None:
            bpy.data.materials.remove(material)


def _link_unassigned_material(bpy, material_library: Path):
    if not material_library.is_file():
        raise RuntimeError(f"shared material library is missing: {material_library}")
    with bpy.data.libraries.load(str(material_library), link=True) as (source, target):
        if "PIMM_UNASSIGNED" not in source.materials:
            raise RuntimeError("shared material library has no PIMM_UNASSIGNED")
        target.materials = ["PIMM_UNASSIGNED"]
    material = bpy.data.materials.get("PIMM_UNASSIGNED")
    if material is None or material.library is None:
        raise RuntimeError("PIMM_UNASSIGNED was not linked from the shared library")
    return material


def _new_collection(bpy, name: str, parent, **properties):
    collection = bpy.data.collections.new(name)
    for key, value in properties.items():
        collection[key] = value
    parent.children.link(collection)
    return collection


def _ensure_assembly_collection(bpy, cache, working, assembly_path: list[str]):
    parent = working
    current: list[str] = []
    for component in assembly_path:
        current.append(component)
        key = tuple(current)
        if key not in cache:
            cache[key] = _new_collection(
                bpy,
                collection_key(current),
                parent,
                pimm_collection_type="CAD_ASSEMBLY",
                pimm_original_cad_name=component,
                pimm_assembly_path=json.dumps(current, ensure_ascii=False),
            )
        parent = cache[key]
    return parent


def _import_one_solid(bpy, solid: dict[str, Any], machine: str, source_hash: str, target, unassigned):
    from mathutils import Matrix

    interchange = Path(solid["interchange_path"])
    if not interchange.is_file():
        raise RuntimeError(f"solid interchange is missing: {interchange}")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(interchange), import_shading="NORMALS")
    imported = [obj for obj in bpy.data.objects if obj not in before]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(
            f"solid {solid['stable_id']} imported {len(meshes)} mesh objects; expected 1"
        )
    product = meshes[0]
    for obj in imported:
        if obj is not product:
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(product.users_collection):
        collection.objects.unlink(product)
    target.objects.link(product)
    product.matrix_world = (
        Matrix.Rotation(SOURCE_TO_BLENDER_ROTATION_X, 4, "X") @ product.matrix_world
    )
    product.name = master_object_name(
        machine, solid["original_name"], solid["stable_id"]
    )
    product.data.name = f"MESH__{solid['stable_id']}"
    product.data.materials.clear()
    product.data.materials.append(unassigned)
    product["pimm_stable_id"] = solid["stable_id"]
    product["pimm_machine"] = machine
    product["pimm_step_sha256"] = source_hash
    product["pimm_product_id"] = solid["product_id"]
    product["pimm_occurrence_id"] = solid["occurrence_id"]
    product["pimm_assembly_path"] = json.dumps(
        solid["assembly_path"], ensure_ascii=False
    )
    product["pimm_solid_index"] = int(solid["solid_index"])
    product["pimm_original_cad_name"] = solid["original_name"]
    product["pimm_geometry_signature"] = solid["geometry_signature"]
    # Start the human-editable label with the exact CAD name. Owners can
    # replace this later without touching the immutable provenance fields.
    product["pimm_part_name"] = solid["original_name"]
    product["pimm_material_state"] = "unassigned"
    product["pimm_manual_material_authority"] = True
    product.show_name = False
    return product


def validate_master_scene(bpy, manifest: dict[str, Any], expected_count: int | None = None) -> None:
    from mathutils import Vector

    products = [obj for obj in bpy.data.objects if obj.get("pimm_stable_id")]
    target_count = len(manifest["solids"]) if expected_count is None else expected_count
    if len(products) != target_count:
        raise RuntimeError(
            f"master product object count drifted: expected {target_count}, got {len(products)}"
        )
    stable_ids = [obj["pimm_stable_id"] for obj in products]
    if len(set(stable_ids)) != len(stable_ids):
        raise RuntimeError("master contains duplicate stable solid IDs")
    for obj in products:
        missing = sorted(key for key in REQUIRED_OBJECT_PROPERTIES if key not in obj)
        if missing:
            raise RuntimeError(f"master object {obj.name} lacks provenance: {missing}")
        if obj.type != "MESH" or obj.data is None:
            raise RuntimeError(f"master product is not a selectable mesh: {obj.name}")
        if len(obj.data.materials) != 1:
            raise RuntimeError(f"master object has unexpected material slots: {obj.name}")
        material = obj.data.materials[0]
        if obj.get("pimm_material_state") != "unassigned":
            raise RuntimeError(f"master object falsely claims approved material: {obj.name}")
        if material is None or material.name != "PIMM_UNASSIGNED" or material.library is None:
            raise RuntimeError(f"master object lacks linked PIMM_UNASSIGNED: {obj.name}")
    forbidden = [obj.name for obj in bpy.data.objects if obj.type in {"CAMERA", "LIGHT"}]
    if forbidden:
        raise RuntimeError(f"master contains forbidden cameras or lights: {forbidden}")
    master_scene = bpy.data.scenes.get(
        f"PIMM_{manifest['source']['machine']}_MASTER"
    )
    if master_scene is None or not math.isclose(
        master_scene.get("pimm_source_to_blender_rotation_x", 0.0),
        SOURCE_TO_BLENDER_ROTATION_X,
        abs_tol=1e-12,
    ):
        raise RuntimeError("master source-to-Blender coordinate contract drifted")
    if target_count == len(manifest["solids"]):
        points = [
            obj.matrix_world @ Vector(corner)
            for obj in products
            for corner in obj.bound_box
        ]
        extents = [
            max(point[index] for point in points)
            - min(point[index] for point in points)
            for index in range(3)
        ]
        if extents[2] <= max(extents[0], extents[1]):
            raise RuntimeError(
                f"master is not Blender Z-up: extents={tuple(round(x, 6) for x in extents)}"
            )
    published = bpy.data.collections.get("PIMM_PUBLISHED")
    if published is None or any(True for _ in published.all_objects):
        raise RuntimeError("PIMM_PUBLISHED must remain empty until material approval")


def _run_mutation_self_test(bpy, manifest: dict[str, Any], expected_count: int) -> None:
    validate_master_scene(bpy, manifest, expected_count)
    products = [obj for obj in bpy.data.objects if obj.get("pimm_stable_id")]
    if len(products) < 2:
        raise RuntimeError("self-test requires at least two fixture objects")

    original_id = products[1]["pimm_stable_id"]
    products[1]["pimm_stable_id"] = products[0]["pimm_stable_id"]
    try:
        validate_master_scene(bpy, manifest, expected_count)
    except RuntimeError as error:
        if "duplicate stable solid IDs" not in str(error):
            raise
    else:
        raise RuntimeError("duplicate-ID mutation was not rejected")
    products[1]["pimm_stable_id"] = original_id

    products[0]["pimm_material_state"] = "approved"
    try:
        validate_master_scene(bpy, manifest, expected_count)
    except RuntimeError as error:
        if "falsely claims approved material" not in str(error):
            raise
    else:
        raise RuntimeError("false-material mutation was not rejected")
    products[0]["pimm_material_state"] = "unassigned"

    camera_data = bpy.data.cameras.new("MUTATION_CAMERA_DATA")
    camera = bpy.data.objects.new("MUTATION_CAMERA", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    try:
        validate_master_scene(bpy, manifest, expected_count)
    except RuntimeError as error:
        if "forbidden cameras or lights" not in str(error):
            raise
    else:
        raise RuntimeError("camera mutation was not rejected")
    bpy.data.objects.remove(camera, do_unlink=True)
    bpy.data.cameras.remove(camera_data)
    validate_master_scene(bpy, manifest, expected_count)


def build_master(
    machine: str,
    manifest_path: Path,
    material_library: Path,
    output_blend: Path | None,
    *,
    limit: int | None = None,
    run_mutations: bool = False,
) -> dict[str, Any]:
    import bpy

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_import_manifest(manifest, machine)
    source_before = _source_readback(manifest)
    _clear_blender(bpy)
    scene = bpy.context.scene
    scene.name = f"PIMM_{machine}_MASTER"
    scene["pimm_master_machine"] = machine
    scene["pimm_master_schema_version"] = 1
    scene["pimm_source_to_blender_rotation_x"] = SOURCE_TO_BLENDER_ROTATION_X
    scene["pimm_source_step_sha256"] = manifest["source"]["sha256"]
    scene["pimm_publishable"] = False
    scene["pimm_publish_blocker"] = "manual material assignments incomplete"

    working = _new_collection(
        bpy,
        "PIMM_WORKING",
        scene.collection,
        pimm_collection_type="WORKING",
        pimm_manual_authority=True,
    )
    _new_collection(
        bpy,
        "PIMM_PUBLISHED",
        scene.collection,
        pimm_collection_type="PUBLISHED",
        pimm_publishable=False,
    )
    unassigned = _link_unassigned_material(bpy, material_library)
    cache = {}
    selected_solids = manifest["solids"][:limit] if limit else manifest["solids"]
    for index, solid in enumerate(selected_solids, start=1):
        target = _ensure_assembly_collection(
            bpy, cache, working, solid["assembly_path"]
        )
        _import_one_solid(
            bpy,
            solid,
            machine,
            manifest["source"]["sha256"],
            target,
            unassigned,
        )
        if index % 25 == 0 or index == len(selected_solids):
            print(f"PIMM_MASTER_IMPORT machine={machine} objects={index}/{len(selected_solids)}")

    audit_scene = bpy.data.scenes.new(f"PIMM_{machine}_MATERIAL_AUDIT")
    audit_scene.collection.children.link(working)
    audit_scene["pimm_audit_scene"] = True
    audit_scene["pimm_unassigned_count"] = len(selected_solids)
    instructions = bpy.data.texts.new("PIMM_MASTER_README")
    instructions.write(
        "PIMM MACHINE MASTER\n"
        "1. Work only in PIMM_WORKING.\n"
        "2. Use pimm_part_name for your human-readable part name.\n"
        "3. Assign linked shared materials or machine-local branding materials manually.\n"
        "4. Never remove pimm_stable_id or source provenance properties.\n"
        "5. PIMM_PUBLISHED remains empty until the publish audit passes.\n"
    )
    provenance = bpy.data.texts.new("PIMM_IMPORT_MANIFEST_POINTER")
    provenance.write(str(manifest_path.resolve()))

    validate_master_scene(bpy, manifest, len(selected_solids))
    if run_mutations:
        _run_mutation_self_test(bpy, manifest, len(selected_solids))

    if output_blend is not None:
        output_blend.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_blend.with_name(output_blend.stem + ".tmp.blend")
        temporary.unlink(missing_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(temporary), check_existing=False)
        os.replace(temporary, output_blend)

    source_after = _source_readback(manifest)
    if source_after != source_before:
        raise RuntimeError("authoritative STEP source changed during master build")
    return {
        "machine": machine,
        "source": source_after,
        "object_count": len(selected_solids),
        "manifest_solid_count": len(manifest["solids"]),
        "unassigned_count": len(selected_solids),
        "publishable": False,
        "output": str(output_blend.resolve()) if output_blend else None,
    }


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", choices=("30G", "50G"), required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--audit-existing", action="store_true")
    parser.add_argument("--fixture-count", type=int, default=3)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(blender_args())


def main() -> None:
    args = parse_args()
    manifest = MANIFEST_ROOT / f"PIMM-{args.machine}-import-manifest.json"
    if args.audit_existing:
        import bpy

        data = json.loads(manifest.read_text(encoding="utf-8"))
        validate_import_manifest(data, args.machine)
        validate_master_scene(bpy, data)
        print(
            "PIMM_MASTER_REOPEN "
            + json.dumps(
                {
                    "machine": args.machine,
                    "objects": len(data["solids"]),
                    "source": _source_readback(data),
                    "filepath": bpy.data.filepath,
                },
                sort_keys=True,
            )
        )
        return
    output = args.output or MASTER_ROOT / f"PIMM-{args.machine}-MASTER.blend"
    result = build_master(
        args.machine,
        manifest,
        MATERIAL_LIBRARY,
        None if args.validate_only else output,
        limit=args.fixture_count if args.validate_only else None,
        run_mutations=args.validate_only,
    )
    print("PIMM_MASTER_RESULT " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
