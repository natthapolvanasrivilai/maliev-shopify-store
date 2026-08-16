"""Publication-gated builder for linked PIMM studio scenes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any, Sequence
import uuid

try:
    from .io_contract import sha256_file
    from .paths import ASSET_ROOT, require_within
    from .scene_contract import (
        PUBLISHED_STABLE_ID_COUNT_PROPERTY,
        PUBLISHED_STABLE_ID_SHA256_PROPERTY,
        SceneContract,
        canonical_scene_contract_json,
        load_authoritative_product_ids,
        stable_id_evidence,
        validate_scene_contract,
    )
except ImportError:  # Blender may execute this checked-in script directly.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production.io_contract import sha256_file
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
    from scripts.blender.pimm_production.scene_contract import (
        PUBLISHED_STABLE_ID_COUNT_PROPERTY,
        PUBLISHED_STABLE_ID_SHA256_PROPERTY,
        SceneContract,
        canonical_scene_contract_json,
        load_authoritative_product_ids,
        stable_id_evidence,
        validate_scene_contract,
    )


STATUS_BLOCKED = "blocked_manual_material_approval"
AUDIT_MARKER = "PIMM_SCENE_PUBLISH_AUDIT_JSON="
BUILD_MARKER = "PIMM_SCENE_BUILD_JSON="
VALIDATION_MARKER = "PIMM_SCENE_VALIDATION_JSON="
_CANONICAL_ASSET_ROOT = ASSET_ROOT
_MATERIAL_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _material_gate_errors(objects: list[object]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    unassigned: list[str] = []
    for product in objects:
        getter = getattr(product, "get", None)
        stable_id = getter("pimm_stable_id", getattr(product, "name", ""))
        state = getter("pimm_material_state", "missing")
        materials = [
            material
            for material in getattr(getattr(product, "data", None), "materials", ())
            if material is not None
        ]
        if state != "approved":
            unassigned.append(str(stable_id))
        if not materials:
            errors.append(f"product object has no material: {stable_id}")
        for material in materials:
            material_id = material.get("pimm_material_id")
            if (
                not isinstance(material_id, str)
                or material_id != material_id.strip()
                or _MATERIAL_ID.fullmatch(material_id) is None
            ):
                errors.append(
                    f"product material requires exact pimm_material_id: {stable_id}/"
                    f"{getattr(material, 'name', '')}"
                )
                continue
            if material_id == "UNASSIGNED":
                if str(stable_id) not in unassigned:
                    unassigned.append(str(stable_id))
    return errors, sorted(unassigned)


def audit_master_publication(
    bpy: Any, contract: SceneContract, *, deep_geometry: bool = False
) -> dict[str, object]:
    """Read one open master and return its non-mutating publication gate."""

    schema_errors = validate_scene_contract(contract)
    master_path = (ASSET_ROOT / Path(contract.master_path)).resolve()
    material_path = (ASSET_ROOT / Path(contract.material_library_path)).resolve()
    errors = list(schema_errors)
    before = {
        "master_sha256": sha256_file(master_path) if master_path.is_file() else None,
        "material_library_sha256": sha256_file(material_path)
        if material_path.is_file()
        else None,
    }
    opened_path = Path(str(getattr(bpy.data, "filepath", ""))).resolve()
    if opened_path != master_path:
        errors.append(f"open file is not the contracted master: {opened_path}")
    if before["master_sha256"] != contract.master_sha256.upper():
        errors.append(f"master SHA-256 mismatch: {master_path}")
    if before["material_library_sha256"] != contract.material_library_sha256.upper():
        errors.append(f"material-library SHA-256 mismatch: {material_path}")

    published = bpy.data.collections.get(contract.master_collection)
    published_objects = list(getattr(published, "all_objects", ())) if published else []
    if published is None:
        errors.append("master is missing PIMM_PUBLISHED")
    elif not published_objects:
        errors.append("PIMM_PUBLISHED is empty")
    expected_ids, manifest_errors = load_authoritative_product_ids(
        ASSET_ROOT, contract.machine
    )
    errors.extend(manifest_errors)
    published_id_rows = [
        str(obj.get("pimm_stable_id"))
        for obj in published_objects
        if getattr(obj, "type", None) == "MESH" and obj.get("pimm_stable_id")
    ]
    published_ids = set(published_id_rows)
    if len(published_id_rows) != len(published_ids):
        errors.append("PIMM_PUBLISHED contains duplicate stable IDs")
    if published is not None and not manifest_errors and published_ids != expected_ids:
        errors.append(
            "PIMM_PUBLISHED does not match authoritative import manifest "
            f"(missing={sorted(expected_ids - published_ids)}, extra={sorted(published_ids - expected_ids)})"
        )
    evidence_count = (
        published.get(PUBLISHED_STABLE_ID_COUNT_PROPERTY) if published else None
    )
    evidence_sha256 = (
        published.get(PUBLISHED_STABLE_ID_SHA256_PROPERTY) if published else None
    )
    actual_count, actual_sha256 = stable_id_evidence(published_ids)
    if published is not None and (
        evidence_count != actual_count or evidence_sha256 != actual_sha256
    ):
        errors.append(
            "PIMM_PUBLISHED embedded stable-ID evidence does not match its contents"
        )
    if published is not None and not manifest_errors:
        manifest_count, manifest_sha256 = stable_id_evidence(expected_ids)
        if evidence_count != manifest_count or evidence_sha256 != manifest_sha256:
            errors.append(
                "PIMM_PUBLISHED embedded stable-ID evidence does not match authoritative import manifest"
            )

    all_products = [obj for obj in bpy.data.objects if obj.get("pimm_stable_id")]
    material_errors, unassigned = _material_gate_errors(all_products)
    errors.extend(material_errors)

    canonical_root = Path(
        r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders"
    ).resolve()
    material_audit: dict[str, object] | None = None
    try:
        master_path.relative_to(canonical_root)
    except ValueError:
        pass
    else:
        from scripts.blender.master_assets.pimm_master_audit import audit_open_master

        material_audit = audit_open_master(
            "publish", deep_geometry=deep_geometry
        )
        errors.extend(str(error) for error in material_audit["errors"])
        unassigned = sorted(
            set(unassigned) | set(material_audit["unassigned_ids"])
        )
    if unassigned:
        errors.append(f"{len(unassigned)} objects remain unassigned")

    after = {
        "master_sha256": sha256_file(master_path) if master_path.is_file() else None,
        "material_library_sha256": sha256_file(material_path)
        if material_path.is_file()
        else None,
    }
    if after != before:
        errors.append("master or material-library fingerprint changed during publish audit")

    return {
        "status": STATUS_BLOCKED if errors else "publishable",
        "machine": contract.machine,
        "master_path": str(master_path),
        "material_library_path": str(material_path),
        "published_object_count": len(published_objects),
        "unassigned_count": len(unassigned),
        "errors": list(dict.fromkeys(errors)),
        "fingerprints_before": before,
        "fingerprints_after": after,
        "fingerprints_unchanged": before == after,
        "material_audit_publishable": material_audit.get("publishable")
        if material_audit
        else not material_errors and not unassigned,
    }


def _run_fresh_validation(scene_path: Path, contract_path: Path) -> list[str]:
    """Open the temporary scene in a new Blender and return checked-in validator errors."""

    import bpy

    validator = Path(__file__).resolve().with_name("blender_scene_validator.py")
    command = [
        str(Path(bpy.app.binary_path).resolve()),
        "--factory-startup",
        "-b",
        str(scene_path),
        "--python-exit-code",
        "1",
        "-P",
        str(validator),
        "--",
        "--contract",
        str(contract_path.resolve()),
    ]
    if ASSET_ROOT.resolve() != _CANONICAL_ASSET_ROOT.resolve():
        command.extend(["--fixture-asset-root", str(ASSET_ROOT.resolve())])
    completed = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode:
        return [
            "fresh Blender validation process failed "
            f"(exit={completed.returncode}, stderr={completed.stderr.strip()})"
        ]
    emitted = [
        line.removeprefix(VALIDATION_MARKER)
        for line in completed.stdout.splitlines()
        if line.startswith(VALIDATION_MARKER)
    ]
    if len(emitted) != 1:
        return ["fresh Blender validation did not emit exactly one result"]
    try:
        result = json.loads(emitted[0])
    except json.JSONDecodeError as error:
        return [f"fresh Blender validation emitted invalid JSON: {error}"]
    if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
        return ["fresh Blender validation result must be a list of errors"]
    return result


def build_linked_scene(
    contract_path: Path, output_blend: Path
) -> dict[str, object]:
    """Build only from a publish-audit-green open master, otherwise do nothing."""

    import bpy

    contract_path = Path(contract_path).resolve()
    try:
        contract_bytes = contract_path.read_bytes()
        contract = SceneContract.from_mapping(
            json.loads(contract_bytes.decode("utf-8"))
        )
    except (
        OSError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        return {"status": "blocked_contract", "errors": [str(error)]}
    contract_sha256 = hashlib.sha256(contract_bytes).hexdigest().upper()
    contract_errors = validate_scene_contract(contract)
    if contract_errors:
        return {"status": "blocked_contract", "errors": contract_errors}
    try:
        destination = require_within(
            output_blend, ASSET_ROOT / "scenes" / "shared-templates"
        )
    except ValueError as error:
        return {"status": "blocked_output_path", "errors": [str(error)]}
    if destination.suffix.lower() != ".blend":
        return {
            "status": "blocked_output_path",
            "errors": ["linked scene output must use the .blend extension"],
        }
    if destination.exists():
        return {
            "status": "blocked_output_exists",
            "errors": [f"linked scene output already exists: {destination}"],
        }

    audit = audit_master_publication(bpy, contract)
    if audit["status"] != "publishable":
        audit["output_created"] = False
        audit["output_path"] = str(destination)
        return audit

    master_path = (ASSET_ROOT / Path(contract.master_path)).resolve()
    master_before = sha256_file(master_path)
    material_path = (ASSET_ROOT / Path(contract.material_library_path)).resolve()
    material_before = sha256_file(material_path)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(
        str(master_path), link=True, relative=True
    ) as (available, requested):
        if contract.master_collection not in available.collections:
            raise RuntimeError("publish-audit-green master lost PIMM_PUBLISHED")
        requested.collections = [contract.master_collection]
    linked = bpy.data.collections[contract.master_collection]
    bpy.context.scene.collection.children.link(linked)

    camera_data = bpy.data.cameras.new(contract.camera_name)
    camera = bpy.data.objects.new(contract.camera_name, camera_data)
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    light_data = bpy.data.lights.new("KEY_AREA", type="AREA")
    light = bpy.data.objects.new("KEY_AREA", light_data)
    bpy.context.scene.collection.objects.link(light)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001
    scene.render.resolution_x = int(contract.output_contract["width"])
    scene.render.resolution_y = int(contract.output_contract["height"])
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = bool(contract.output_contract["alpha"])
    scene.render.filepath = str(
        (ASSET_ROOT / "renders" / "proofs" / "unapproved" / contract.scene_id).resolve()
    )
    scene["pimm_scene_contract_payload"] = canonical_scene_contract_json(contract)
    scene["pimm_scene_contract_snapshot_sha256"] = contract_sha256
    destination.parent.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    temporary = destination.with_name(f".{destination.stem}.{nonce}.tmp.blend")
    contract_snapshot = destination.with_name(
        f".{destination.stem}.{nonce}.contract.json"
    )
    try:
        with contract_snapshot.open("xb") as snapshot:
            snapshot.write(contract_bytes)
            snapshot.flush()
            os.fsync(snapshot.fileno())
        contract_snapshot.chmod(stat.S_IREAD)
        bpy.ops.wm.save_as_mainfile(filepath=str(temporary), check_existing=False)
        validation_errors = _run_fresh_validation(temporary, contract_snapshot)
        master_after = sha256_file(master_path)
        material_after = sha256_file(material_path)
        if master_after != master_before or material_after != material_before:
            validation_errors.append(
                "linked scene build changed a protected library fingerprint"
            )
        try:
            original_contract_unchanged = sha256_file(contract_path) == contract_sha256
        except OSError:
            original_contract_unchanged = False
        try:
            snapshot_unchanged = sha256_file(contract_snapshot) == contract_sha256
        except OSError:
            snapshot_unchanged = False
        if not original_contract_unchanged:
            return {
                "status": "blocked_contract_drift",
                "errors": ["original scene contract changed during build"],
                "output_created": False,
                "output_path": str(destination),
            }
        if not snapshot_unchanged:
            validation_errors.append(
                "immutable scene contract snapshot changed during build"
            )
        if validation_errors:
            return {
                "status": "blocked_reopen_validation",
                "errors": validation_errors,
                "output_created": False,
                "output_path": str(destination),
            }
        if destination.exists():
            return {
                "status": "blocked_output_exists",
                "errors": [f"linked scene output appeared during validation: {destination}"],
                "output_created": False,
                "output_path": str(destination),
            }
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
        if contract_snapshot.exists():
            contract_snapshot.chmod(stat.S_IWRITE)
            contract_snapshot.unlink()
    return {
        "status": "created",
        "errors": [],
        "output_created": True,
        "output_path": str(destination),
        "master_sha256": master_after,
        "material_library_sha256": material_after,
        "fresh_validation": True,
    }


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--audit-contract", type=Path)
    group.add_argument("--contract", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else []
    )
    if arguments.audit_contract:
        import bpy

        result = audit_master_publication(
            bpy, SceneContract.from_json(arguments.audit_contract)
        )
        print(AUDIT_MARKER + json.dumps(result, sort_keys=True), flush=True)
        return
    if arguments.output is None:
        raise ValueError("--output is required with --contract")
    result = build_linked_scene(arguments.contract, arguments.output)
    print(BUILD_MARKER + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
