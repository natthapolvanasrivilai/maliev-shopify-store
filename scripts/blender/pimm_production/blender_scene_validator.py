"""Read-only Blender validation for linked PIMM render-scene ownership."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Sequence

try:
    from .io_contract import sha256_file
    from .machine_contract import load_machine_contract, validate_controller_scene
    from .paths import ASSET_ROOT, require_within
    from .published_artwork import ARTWORK_SPECS_BY_MACHINE, validate_published_artwork
    from .scene_contract import (
        PUBLISHED_STABLE_ID_COUNT_PROPERTY,
        PUBLISHED_STABLE_ID_SHA256_PROPERTY,
        SceneContract,
        canonical_scene_contract_json,
        stable_id_evidence,
        validate_scene_contract,
    )
except ImportError:  # Blender may execute this checked-in script directly.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production.io_contract import sha256_file
    from scripts.blender.pimm_production.machine_contract import (
        load_machine_contract,
        validate_controller_scene,
    )
    from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
    from scripts.blender.pimm_production.published_artwork import (
        ARTWORK_SPECS_BY_MACHINE,
        validate_published_artwork,
    )
    from scripts.blender.pimm_production.scene_contract import (
        PUBLISHED_STABLE_ID_COUNT_PROPERTY,
        PUBLISHED_STABLE_ID_SHA256_PROPERTY,
        SceneContract,
        canonical_scene_contract_json,
        stable_id_evidence,
        validate_scene_contract,
    )

from scripts.blender.master_assets.pimm_material_library import MATERIAL_SPECS


VALIDATION_MARKER = "PIMM_SCENE_VALIDATION_JSON="
_MATERIAL_ID = re.compile(r"^[A-Z][A-Z0-9_]*$")
_APPROVED_SHARED_MATERIAL_IDS = frozenset(MATERIAL_SPECS) - {"UNASSIGNED"}


def _library_path(bpy: Any, library: object | None) -> Path | None:
    lexical = _library_lexical_path(bpy, library)
    return lexical.resolve() if lexical is not None else None


def _library_lexical_path(
    bpy: Any,
    library: object | None,
) -> Path | None:
    if library is None:
        return None
    filepath = str(getattr(library, "filepath", ""))
    if not filepath:
        return None
    if filepath.startswith("//"):
        abspath = getattr(getattr(bpy, "path", None), "abspath", None)
        if callable(abspath):
            return Path(os.path.abspath(str(abspath(filepath))))
        scene_path = Path(os.path.abspath(str(getattr(bpy.data, "filepath", ""))))
        return Path(os.path.abspath(scene_path.parent / filepath[2:]))
    return Path(os.path.abspath(filepath))


def _library_authority_record(bpy: Any, library: object) -> dict[str, object]:
    """Capture Blender's raw/lexical library spelling and its canonical target."""

    raw = str(getattr(library, "filepath", ""))
    lexical = _library_lexical_path(bpy, library)
    if not raw or lexical is None:
        raise ValueError("linked Blender library filepath is empty")
    try:
        canonical = lexical.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"linked Blender library target is unreadable: {lexical}") from error
    parent = getattr(library, "parent", None)
    parent_canonical = _library_path(bpy, parent)
    return {
        "raw_filepath": raw,
        "lexical_path": str(lexical),
        "canonical_path": str(canonical),
        "parent_canonical_path": (
            str(parent_canonical) if parent_canonical is not None else None
        ),
    }


def _datablock_library_path(bpy: Any, datablock: object | None) -> Path | None:
    return _library_path(bpy, getattr(datablock, "library", None))


def _property(datablock: object, name: str, default: object = None) -> object:
    getter = getattr(datablock, "get", None)
    return getter(name, default) if callable(getter) else default


def _reachable_collections(scene: object) -> set[object]:
    reachable: set[object] = set()
    stack = list(getattr(getattr(scene, "collection", None), "children", ()))
    while stack:
        collection = stack.pop()
        if collection in reachable:
            continue
        reachable.add(collection)
        stack.extend(getattr(collection, "children", ()))
    return reachable


def _validate_complete_product(
    published: object | None, contract: SceneContract
) -> list[str]:
    if published is None:
        return []
    errors: list[str] = []
    published_meshes = [
        obj
        for obj in getattr(published, "all_objects", ())
        if getattr(obj, "type", None) == "MESH"
    ]
    identifier_rows: list[str] = []
    artwork_names = {
        spec.object_name for spec in ARTWORK_SPECS_BY_MACHINE[contract.machine]
    }
    missing_provenance: list[str] = []
    for product in published_meshes:
        stable_id = _property(product, "pimm_stable_id")
        if (not isinstance(stable_id, str) or not stable_id) and str(
            getattr(product, "name", "")
        ) not in artwork_names:
            missing_provenance.append(str(getattr(product, "name", "")))
        elif isinstance(stable_id, str) and stable_id:
            identifier_rows.append(stable_id)
    actual_ids = set(identifier_rows)
    if missing_provenance:
        errors.append(
            "PIMM_PUBLISHED contains MESH objects without stable provenance: "
            + ", ".join(sorted(missing_provenance))
        )
    if len(identifier_rows) != len(actual_ids):
        errors.append("PIMM_PUBLISHED contains duplicate stable IDs")
    expected_count = _property(published, PUBLISHED_STABLE_ID_COUNT_PROPERTY)
    expected_sha256 = _property(published, PUBLISHED_STABLE_ID_SHA256_PROPERTY)
    if (
        not isinstance(expected_count, int)
        or isinstance(expected_count, bool)
        or expected_count <= 0
        or not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(character not in "0123456789ABCDEF" for character in expected_sha256)
    ):
        errors.append(
            "PIMM_PUBLISHED embedded stable-ID evidence is absent or invalid"
        )
        return errors
    actual_count, actual_sha256 = stable_id_evidence(actual_ids)
    if actual_count != expected_count or actual_sha256 != expected_sha256:
        errors.append(
            "PIMM_PUBLISHED does not match embedded stable-ID evidence "
            f"(expected_count={expected_count}, actual_count={actual_count}, "
            f"expected_sha256={expected_sha256}, actual_sha256={actual_sha256})"
        )
    _, artwork_errors = validate_published_artwork(published, contract.machine)
    errors.extend(artwork_errors)
    return errors


def _validate_materials(
    bpy: Any,
    product: object,
    expected_master: Path,
    expected_material_library: Path,
    material_registry: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    name = str(getattr(product, "name", ""))
    if getattr(product, "override_library", None) is not None or _property(
        product, "pimm_product_material_override"
    ) is True:
        errors.append(f"approved product material override is forbidden: {name}")
    materials = [
        material
        for material in (
            getattr(slot, "material", None)
            for slot in getattr(product, "material_slots", ())
        )
        if material is not None
    ]
    if not materials:
        errors.append(f"approved product has no exact material datablock: {name}")
    for material in materials:
        scope = _property(material, "pimm_material_scope", "unknown")
        origin = _datablock_library_path(bpy, material)
        material_name = str(getattr(material, "name", ""))
        material_id = _property(material, "pimm_material_id")
        if (
            not isinstance(material_id, str)
            or material_id != material_id.strip()
            or _MATERIAL_ID.fullmatch(material_id) is None
            or material_id == "UNASSIGNED"
        ):
            errors.append(
                f"product material requires exact pimm_material_id: {name}/{material_name}"
            )
        else:
            prior = material_registry.setdefault(material_id, material)
            if prior is not material:
                errors.append(
                    f"pimm_material_id must identify one exact material datablock: {material_id}"
                )
            if scope == "shared" and material_name != f"PIMM_{material_id}":
                errors.append(
                    f"shared material name/pimm_material_id mismatch: {name}/{material_name}"
                )
            if (
                scope == "shared"
                and material_id not in _APPROVED_SHARED_MATERIAL_IDS
            ):
                errors.append(
                    f"shared pimm_material_id is outside the canonical material catalog: "
                    f"{name}/{material_id}"
                )
        if scope == "shared" and origin != expected_material_library:
            errors.append(
                f"linked product material made local or resolved outside material library: {name}/{material_name} origin={origin}"
            )
        elif scope == "machine-local" and origin != expected_master:
            errors.append(
                f"machine-local product material did not resolve through master: {name}/{material_name}"
            )
        elif scope not in {"shared", "machine-local"}:
            errors.append(f"product material scope is not approved: {name}/{material_name}")
    return errors


def validate_open_render_scene(
    bpy: Any,
    contract: SceneContract,
    *,
    contract_snapshot_sha256: str | None = None,
) -> list[str]:
    """Inspect the open file without mutation and return all ownership errors."""

    errors = list(validate_scene_contract(contract))
    if errors:
        return errors

    embedded_payload = _property(
        bpy.context.scene, "pimm_scene_contract_payload"
    )
    embedded_snapshot_sha256 = _property(
        bpy.context.scene, "pimm_scene_contract_snapshot_sha256"
    )
    if embedded_payload != canonical_scene_contract_json(contract):
        errors.append("embedded scene contract payload does not match validation snapshot")
    if (
        not isinstance(embedded_snapshot_sha256, str)
        or len(embedded_snapshot_sha256) != 64
        or any(
            character not in "0123456789ABCDEF"
            for character in embedded_snapshot_sha256
        )
    ):
        errors.append("embedded scene contract snapshot SHA-256 is absent or invalid")
    elif (
        contract_snapshot_sha256 is not None
        and embedded_snapshot_sha256 != contract_snapshot_sha256.upper()
    ):
        errors.append("embedded scene contract snapshot SHA-256 does not match snapshot")

    machine_contract = load_machine_contract(contract.machine)
    errors.extend(validate_controller_scene(bpy, machine_contract))
    animation = machine_contract["animation"]
    if (
        contract.animation_contract is not None
        and animation["status"] != "enabled_owner_approved"
    ):
        errors.append(
            "scene animation_contract is present while the machine motion map remains blocked"
        )

    expected_master = (ASSET_ROOT / Path(contract.master_path)).resolve()
    expected_material_library = (
        ASSET_ROOT / Path(contract.material_library_path)
    ).resolve()
    if not expected_master.is_file():
        errors.append(f"expected master is missing: {expected_master}")
    elif sha256_file(expected_master) != contract.master_sha256.upper():
        errors.append(f"master SHA-256 mismatch: {expected_master}")
    if not expected_material_library.is_file():
        errors.append(f"expected material library is missing: {expected_material_library}")
    elif sha256_file(expected_material_library) != contract.material_library_sha256.upper():
        errors.append(
            f"material-library SHA-256 mismatch: {expected_material_library}"
        )

    opened_path = Path(str(getattr(bpy.data, "filepath", "")))
    try:
        require_within(opened_path, ASSET_ROOT / "scenes")
    except ValueError as error:
        errors.append(f"open render scene is outside managed scene root: {error}")

    library_paths = {
        path
        for path in (_library_path(bpy, library) for library in bpy.data.libraries)
        if path is not None
    }
    if expected_master not in library_paths:
        errors.append(f"missing expected master library link: {expected_master}")
    if expected_material_library not in library_paths:
        errors.append(
            f"missing expected material-library dependency: {expected_material_library}; found={sorted(str(path) for path in library_paths)}"
        )
    unexpected_library_paths = library_paths - {
        expected_master,
        expected_material_library,
    }
    if unexpected_library_paths:
        errors.append(
            "render scene contains linked libraries outside the exact master/material-library "
            f"authority: {sorted(str(path) for path in unexpected_library_paths)}"
        )

    candidates = [
        collection
        for collection in bpy.data.collections
        if getattr(collection, "name", "") == contract.master_collection
        and _datablock_library_path(bpy, collection) == expected_master
    ]
    published = candidates[0] if len(candidates) == 1 else None
    if published is None:
        errors.append(
            "render scene must link exactly one PIMM_PUBLISHED collection from the expected master"
        )
    elif not list(getattr(published, "all_objects", ())):
        errors.append("linked PIMM_PUBLISHED collection is empty")
    if published is not None and published not in _reachable_collections(
        bpy.context.scene
    ):
        errors.append(
            "linked PIMM_PUBLISHED is not reachable from the active scene hierarchy"
        )
    errors.extend(_validate_complete_product(published, contract))

    environment_objects = [
        obj
        for obj in bpy.data.objects
        if getattr(obj, "type", None) == "MESH"
        and _property(obj, "pimm_scene_environment_role") is not None
    ]
    environment_meshes: set[object] = set()
    environment_materials: set[object] = set()
    if len(environment_objects) > 1:
        errors.append("render scene may contain only one authored environment mesh")
    for environment in environment_objects:
        mesh = getattr(environment, "data", None)
        materials = list(getattr(mesh, "materials", ())) if mesh is not None else []
        role = _property(environment, "pimm_scene_environment_role")
        valid = (
            role == "shadow-catcher"
            and str(getattr(environment, "name", "")) == "PIMM_SCENE_SHADOW_CATCHER"
            and _datablock_library_path(bpy, environment) is None
            and mesh is not None
            and str(getattr(mesh, "name", "")) == "PIMM_SCENE_SHADOW_CATCHER"
            and _datablock_library_path(bpy, mesh) is None
            and _property(mesh, "pimm_scene_environment_role") == role
            and getattr(environment, "is_shadow_catcher", False) is True
            and len(materials) == 1
            and str(getattr(materials[0], "name", ""))
            == "PIMM_SCENE_SHADOW_CATCHER_MATERIAL"
            and _datablock_library_path(bpy, materials[0]) is None
            and _property(materials[0], "pimm_scene_environment_role") == role
            and _property(materials[0], "pimm_material_id")
            == "SCENE_SHADOW_CATCHER"
            and _property(materials[0], "pimm_material_scope") is None
            and _property(environment, "pimm_stable_id") is None
        )
        if not valid:
            errors.append(
                f"authored scene environment is not the exact shadow catcher: {getattr(environment, 'name', '')}"
            )
            continue
        environment_meshes.add(mesh)
        environment_materials.add(materials[0])

    products = sorted(
        (
            obj
            for obj in bpy.data.objects
            if getattr(obj, "type", None) == "MESH" and obj not in environment_objects
        ),
        key=lambda obj: str(getattr(obj, "name", "")),
    )
    expected_products = set(getattr(published, "all_objects", ())) if published else set()
    material_registry: dict[str, object] = {}
    # Validate every used material datablock, not only object slots. Geometry
    # Nodes and node-socket pointers can contribute a material to rendering
    # without placing it in ``Object.material_slots``.
    for material in getattr(bpy.data, "materials", ()):
        if int(getattr(material, "users", 0)) <= 0:
            continue
        if material in environment_materials:
            continue
        material_name = str(getattr(material, "name", ""))
        material_id = _property(material, "pimm_material_id")
        if (
            not isinstance(material_id, str)
            or material_id != material_id.strip()
            or _MATERIAL_ID.fullmatch(material_id) is None
            or material_id == "UNASSIGNED"
        ):
            errors.append(
                f"used material requires exact pimm_material_id: {material_name}"
            )
            continue
        prior = material_registry.setdefault(material_id, material)
        if prior is not material:
            errors.append(
                f"pimm_material_id must identify one exact material datablock: {material_id}"
            )
        origin = _datablock_library_path(bpy, material)
        if origin == expected_material_library:
            if material_id not in _APPROVED_SHARED_MATERIAL_IDS:
                errors.append(
                    "material-library pimm_material_id is outside the canonical shared "
                    f"catalog: {material_name}/{material_id}"
                )
            elif material_name != f"PIMM_{material_id}":
                errors.append(
                    "shared material name/pimm_material_id mismatch: "
                    f"{material_name}/{material_id}"
                )
        elif origin == expected_master and material_id in _APPROVED_SHARED_MATERIAL_IDS:
            errors.append(
                "shared material resolved from master instead of material library: "
                f"{material_name}/{material_id}"
            )
        elif origin not in {expected_master, expected_material_library}:
            errors.append(
                "used material is scene-local or outside the exact master/material-library "
                f"authority: {material_name}/{material_id} origin={origin}"
            )
    for product in products:
        name = str(getattr(product, "name", ""))
        object_library = _datablock_library_path(bpy, product)
        mesh = getattr(product, "data", None)
        mesh_library = _datablock_library_path(bpy, mesh)
        if object_library != expected_master:
            errors.append(
                f"scene-local MESH object is forbidden; private machine mesh: {name}"
            )
        elif product not in expected_products:
            errors.append(f"master MESH is outside PIMM_PUBLISHED: {name}")
        if mesh_library != expected_master:
            errors.append(
                f"scene-local MESH datablock is forbidden; private machine mesh: {name}"
            )
        errors.extend(
            _validate_materials(
                bpy,
                product,
                expected_master,
                expected_material_library,
                material_registry,
            )
        )

    for mesh in bpy.data.meshes:
        if mesh in environment_meshes:
            continue
        if _datablock_library_path(bpy, mesh) != expected_master:
            name = str(getattr(mesh, "name", ""))
            message = f"scene-local MESH datablock is forbidden: {name}"
            if message not in errors:
                errors.append(message)

    camera = bpy.data.objects.get(contract.camera_name)
    if camera is None or getattr(camera, "type", None) != "CAMERA":
        errors.append(f"required camera is missing: {contract.camera_name}")
    else:
        if getattr(bpy.context.scene, "camera", None) != camera:
            errors.append(f"required camera is not active: {contract.camera_name}")
        if _datablock_library_path(bpy, camera) is not None or _datablock_library_path(
            bpy, getattr(camera, "data", None)
        ) is not None:
            errors.append(f"required camera must be scene-local: {contract.camera_name}")

    render = bpy.context.scene.render
    output_path = Path(bpy.path.abspath(render.filepath)).resolve()
    try:
        require_within(output_path, ASSET_ROOT / "renders")
    except ValueError as error:
        errors.append(f"output is outside managed render root: {error}")
    if render.resolution_x != contract.output_contract["width"]:
        errors.append("render width does not match output_contract")
    if render.resolution_y != contract.output_contract["height"]:
        errors.append("render height does not match output_contract")
    if render.resolution_percentage != 100:
        errors.append("render resolution_percentage must equal 100")
    if render.film_transparent is not contract.output_contract["alpha"]:
        errors.append("render alpha does not match output_contract")

    units = bpy.context.scene.unit_settings
    if units.system != "METRIC" or units.length_unit != "MILLIMETERS":
        errors.append("render scene units must be Metric/Millimeters")
    if abs(float(units.scale_length) - 0.001) > 1e-7:
        errors.append("render scene scale_length must equal 0.001")
    return errors


def _fixture_asset_root(path: Path) -> Path:
    resolved = path.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if resolved == temporary_root:
        raise ValueError("fixture asset root cannot equal the system temporary root")
    try:
        resolved.relative_to(temporary_root)
    except ValueError as error:
        raise ValueError(
            "fixture asset root must be beneath the system temporary root"
        ) from error
    return resolved


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--fixture-asset-root", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    global ASSET_ROOT

    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else []
    )
    if arguments.fixture_asset_root is not None:
        ASSET_ROOT = _fixture_asset_root(arguments.fixture_asset_root)
    contract = SceneContract.from_json(arguments.contract)
    contract_snapshot_sha256 = sha256_file(arguments.contract)
    import bpy

    errors = validate_open_render_scene(
        bpy,
        contract,
        contract_snapshot_sha256=contract_snapshot_sha256,
    )
    print(VALIDATION_MARKER + json.dumps(errors, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
