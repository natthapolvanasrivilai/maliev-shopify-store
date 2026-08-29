import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import textwrap
from types import SimpleNamespace
import unittest

from scripts.blender.pimm_production import blender_scene_validator, scene_contract
from scripts.blender.pimm_production.scene_contract import (
    SceneContract,
    canonical_scene_contract_json,
    validate_scene_contract,
)
from scripts.blender.pimm_production.campaign_contract import load_campaign


BLENDER = Path(r"D:\Blender 5.2\blender.exe")
REPO_ROOT = Path(__file__).resolve().parents[4]
VALIDATION_MARKER = "PIMM_SCENE_VALIDATION_JSON="
BUILD_MARKER = "PIMM_SCENE_BUILD_JSON="


def _run_blender(arguments: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(BLENDER), *arguments],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError(
            f"Blender fixture command failed ({result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _write_fixture_builder(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """
            import hashlib
            import json
            from pathlib import Path
            import sys

            import bpy

            repository_root = Path(sys.argv[sys.argv.index("--") + 3])
            sys.path.insert(0, str(repository_root))
            from scripts.blender.pimm_production.published_artwork import (
                ARTWORK_SPECS_BY_MACHINE,
                PUBLISHED_ARTWORK_COUNT_PROPERTY,
                PUBLISHED_ARTWORK_SHA256_PROPERTY,
                canonical_artwork_evidence,
                capture_published_artwork,
            )

            kind = sys.argv[sys.argv.index("--") + 1]
            root = Path(sys.argv[sys.argv.index("--") + 2])
            masters = root / "masters"
            manifests = root / "manifests"
            scenes = root / "scenes" / "fixtures"
            renders = root / "renders" / "proofs" / "fixture"
            masters.mkdir(parents=True, exist_ok=True)
            manifests.mkdir(parents=True, exist_ok=True)
            scenes.mkdir(parents=True, exist_ok=True)
            renders.mkdir(parents=True, exist_ok=True)
            material_path = masters / "PIMM-MATERIAL-LIBRARY.blend"
            master_path = masters / "PIMM-30G-MASTER.blend"
            scene_path = scenes / f"{kind}.blend"

            bpy.ops.wm.read_factory_settings(use_empty=True)
            shared = bpy.data.materials.new("PIMM_BLACK_POWDERCOAT")
            shared.use_fake_user = True
            if kind != "missing-material-id":
                shared["pimm_material_id"] = "BLACK_POWDERCOAT"
            shared["pimm_material_scope"] = "shared"
            if kind == "node-only-wrong-shared-id":
                wrong_node_material = bpy.data.materials.new(
                    "PIMM_BLACK_POWDERCOAT_NODE_POINTER"
                )
                wrong_node_material.use_fake_user = True
                wrong_node_material["pimm_material_id"] = "NOT_IN_SHARED_CATALOG"
                wrong_node_material["pimm_material_scope"] = "shared"
            bpy.ops.wm.save_as_mainfile(filepath=str(material_path), check_existing=False)

            bpy.ops.wm.read_factory_settings(use_empty=True)
            with bpy.data.libraries.load(str(material_path), link=True, relative=True) as (available, requested):
                requested.materials = ["PIMM_BLACK_POWDERCOAT"]
                if kind == "node-only-wrong-shared-id":
                    requested.materials.append("PIMM_BLACK_POWDERCOAT_NODE_POINTER")
            linked_material = bpy.data.materials["PIMM_BLACK_POWDERCOAT"]
            published_name = "PIMM_WORKING" if kind == "unpublished-master" else "PIMM_PUBLISHED"
            published = bpy.data.collections.new(published_name)
            bpy.context.scene.collection.children.link(published)
            withheld = None
            if kind in {"partial-published", "manifest-truncated-partial"}:
                withheld = bpy.data.collections.new("PIMM_WITHHELD")
                bpy.context.scene.collection.children.link(withheld)
            stable_ids = ["30G-fixture-product-1", "30G-fixture-product-2"]
            products = []
            for index, stable_id in enumerate(stable_ids, start=1):
                mesh = bpy.data.meshes.new(f"PIMM_TEST_PRODUCT_MESH_{index}")
                mesh.from_pydata(
                    [(-1.0, -1.0, float(index)), (1.0, -1.0, float(index)), (0.0, 1.0, float(index))],
                    [],
                    [(0, 1, 2)],
                )
                mesh.materials.append(linked_material)
                product = bpy.data.objects.new(f"PIMM_TEST_PRODUCT_{index}", mesh)
                product["pimm_stable_id"] = stable_id
                product["pimm_material_state"] = "approved"
                target = withheld if index == 2 and withheld is not None else published
                target.objects.link(product)
                products.append(product)
            if kind == "node-only-wrong-shared-id":
                node_group = bpy.data.node_groups.new(
                    "PIMM_NODE_ONLY_MATERIAL_POINTER", "GeometryNodeTree"
                )
                set_material = node_group.nodes.new("GeometryNodeSetMaterial")
                set_material.inputs["Material"].default_value = bpy.data.materials[
                    "PIMM_BLACK_POWDERCOAT_NODE_POINTER"
                ]
                modifier = products[0].modifiers.new(
                    "PIMM_NODE_ONLY_MATERIAL_POINTER", "NODES"
                )
                modifier.node_group = node_group
            evidence_payload = "\\n".join(sorted(stable_ids)) + "\\n"
            if kind != "collection-evidence-absent":
                published["pimm_published_stable_id_count"] = (
                    1 if kind == "collection-evidence-count-mismatch" else len(stable_ids)
                )
                published["pimm_published_stable_id_sha256"] = (
                    "0" * 64
                    if kind == "collection-evidence-digest-mismatch"
                    else hashlib.sha256(evidence_payload.encode("utf-8")).hexdigest().upper()
                )
            if published_name == "PIMM_PUBLISHED":
                artwork_collection = bpy.data.collections.new("PIMM_SURFACE_DECALS")
                published.children.link(artwork_collection)
                asset_root = Path(r"M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders")
                artwork_specs = list(ARTWORK_SPECS_BY_MACHINE["30G"])
                if kind == "artwork-missing":
                    artwork_specs = artwork_specs[:1]
                if kind == "artwork-duplicate":
                    artwork_specs.append(artwork_specs[0])
                for index, spec in enumerate(artwork_specs, start=1):
                    image = bpy.data.images.load(
                        str(asset_root / Path(spec.image_relative_path)), check_existing=True
                    )
                    image.pack()
                    material = bpy.data.materials.new(spec.material_name)
                    material.use_nodes = True
                    material["pimm_material_id"] = spec.material_id
                    material["pimm_material_scope"] = "machine-local"
                    texture = material.node_tree.nodes.new("ShaderNodeTexImage")
                    texture.image = image
                    mesh = bpy.data.meshes.new(f"{spec.object_name}_MESH")
                    mesh.from_pydata(
                        [(-0.1, 0.0, float(index)), (0.1, 0.0, float(index)), (0.0, 0.2, float(index))],
                        [],
                        [(0, 1, 2)],
                    )
                    mesh.materials.append(material)
                    artwork_name = spec.object_name
                    if kind == "artwork-duplicate" and index == len(artwork_specs):
                        artwork_name += "_DUPLICATE"
                    artwork = bpy.data.objects.new(artwork_name, mesh)
                    artwork["pimm_machine"] = "30G"
                    artwork["pimm_asset_role"] = spec.role
                    artwork["pimm_identical_asset_key"] = spec.asset_key
                    artwork["pimm_attached_parent"] = spec.attached_parent
                    if kind == "artwork-wrong-parent" and index == 1:
                        artwork["pimm_attached_parent"] = "30G__wrong-parent"
                    if kind == "artwork-dual-classified" and index == 1:
                        artwork["pimm_stable_id"] = "30G__invalid-artwork-stable-id"
                    artwork["pimm_asset_image"] = Path(spec.image_relative_path).name
                    artwork_collection.objects.link(artwork)
                artwork_records, artwork_errors = capture_published_artwork(published, "30G")
                if artwork_errors:
                    raise RuntimeError(artwork_errors)
                artwork_count, artwork_sha256 = canonical_artwork_evidence(artwork_records)
                published[PUBLISHED_ARTWORK_COUNT_PROPERTY] = artwork_count
                published[PUBLISHED_ARTWORK_SHA256_PROPERTY] = artwork_sha256
                if kind == "artwork-stale-evidence":
                    published[PUBLISHED_ARTWORK_SHA256_PROPERTY] = "0" * 64
                if kind == "artwork-unclassified":
                    mesh = bpy.data.meshes.new("PIMM_UNCLASSIFIED_MESH")
                    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
                    mesh.materials.append(linked_material)
                    published.objects.link(bpy.data.objects.new("PIMM_UNCLASSIFIED", mesh))
            bpy.context.scene["pimm_master_machine"] = "30G"
            bpy.ops.wm.save_as_mainfile(filepath=str(master_path), check_existing=False)
            manifest_ids = stable_ids[:1] if kind == "manifest-truncated-partial" else stable_ids
            (manifests / "PIMM-30G-import-manifest.json").write_text(
                json.dumps({"schema_version": 1, "solids": [{"stable_id": value} for value in manifest_ids]}, sort_keys=True),
                encoding="utf-8",
            )

            def sha256_file(file_path):
                digest = hashlib.sha256()
                with file_path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                return digest.hexdigest().upper()

            contract_payload = {
                "schema_version": 1,
                "scene_id": "pimm-30g--hero--three-quarter",
                "machine": "30G",
                "purpose": "hero",
                "master_path": "masters/PIMM-30G-MASTER.blend",
                "master_sha256": sha256_file(master_path),
                "master_collection": "PIMM_PUBLISHED",
                "material_library_path": "masters/PIMM-MATERIAL-LIBRARY.blend",
                "material_library_sha256": sha256_file(material_path),
                "camera_name": "CAM_HERO",
                "complete_product": True,
                "animation_contract": None,
                "output_contract": {"width": 1200, "height": 1200, "alpha": True},
            }
            contract_snapshot = json.dumps(contract_payload, sort_keys=True).encode("utf-8")
            contract_canonical = json.dumps(
                contract_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )

            bpy.ops.wm.read_factory_settings(use_empty=True)
            if kind not in {"missing-link", "unpublished-master"}:
                with bpy.data.libraries.load(str(master_path), link=True, relative=True) as (available, requested):
                    requested.collections = ["PIMM_PUBLISHED"]
                if kind == "orphaned-linked-collection":
                    orphan_scene = bpy.data.scenes.new("ORPHAN_SCENE")
                    orphan_scene.collection.children.link(bpy.data.collections["PIMM_PUBLISHED"])
                else:
                    bpy.context.scene.collection.children.link(bpy.data.collections["PIMM_PUBLISHED"])

            if kind in {
                "node-only-local-shared-material",
                "node-only-local-machine-material",
            }:
                local_node_material = bpy.data.materials.new(
                    "PIMM_NODE_ONLY_LOCAL_MATERIAL"
                )
                local_node_material["pimm_material_id"] = (
                    "BLACK_POWDERCOAT"
                    if kind == "node-only-local-shared-material"
                    else "CONTROLLER_ACTIVE"
                )
                local_node_material["pimm_material_scope"] = (
                    "shared"
                    if kind == "node-only-local-shared-material"
                    else "machine-local"
                )
                local_node_group = bpy.data.node_groups.new(
                    "PIMM_NODE_ONLY_LOCAL_POINTER", "GeometryNodeTree"
                )
                local_node_group.use_fake_user = True
                local_set_material = local_node_group.nodes.new(
                    "GeometryNodeSetMaterial"
                )
                local_set_material.inputs[
                    "Material"
                ].default_value = local_node_material

            camera_data = bpy.data.cameras.new("CAM_HERO")
            camera = bpy.data.objects.new("CAM_HERO", camera_data)
            bpy.context.scene.collection.objects.link(camera)
            bpy.context.scene.camera = camera
            if kind == "missing-camera":
                bpy.data.objects.remove(camera, do_unlink=True)

            if kind in {
                "private-product-copy",
                "localized-shared-material",
                "overridden-product-material",
                "untagged-local-mesh",
            }:
                private_mesh = bpy.data.meshes.new("PIMM_PRIVATE_PRODUCT_MESH")
                private_mesh.from_pydata(
                    [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                    [],
                    [(0, 1, 2)],
                )
                private = bpy.data.objects.new("PIMM_PRIVATE_PRODUCT", private_mesh)
                if kind != "untagged-local-mesh":
                    private["pimm_stable_id"] = "30G-fixture-private"
                    private["pimm_product_material_override"] = kind == "overridden-product-material"
                bpy.context.scene.collection.objects.link(private)
                if kind != "private-product-copy":
                    local_material = bpy.data.materials.new("PIMM_BLACK_POWDERCOAT_LOCAL")
                    local_material["pimm_material_id"] = "BLACK_POWDERCOAT"
                    local_material["pimm_material_scope"] = "shared"
                    private_mesh.materials.append(local_material)

            if kind == "stripped-provenance-copy":
                source = bpy.data.objects["PIMM_TEST_PRODUCT_1"]
                stripped = bpy.data.objects.new("PIMM_STRIPPED_COPY", source.data.copy())
                bpy.context.scene.collection.objects.link(stripped)

            if kind == "valid-shadow-catcher":
                catcher_mesh = bpy.data.meshes.new("PIMM_SCENE_SHADOW_CATCHER")
                catcher_mesh["pimm_scene_environment_role"] = "shadow-catcher"
                catcher_mesh.from_pydata(
                    [(-5.0, -5.0, 0.0), (5.0, -5.0, 0.0), (5.0, 5.0, 0.0), (-5.0, 5.0, 0.0)],
                    [],
                    [(0, 1, 2, 3)],
                )
                catcher_material = bpy.data.materials.new(
                    "PIMM_SCENE_SHADOW_CATCHER_MATERIAL"
                )
                catcher_material["pimm_scene_environment_role"] = "shadow-catcher"
                catcher_material["pimm_material_id"] = "SCENE_SHADOW_CATCHER"
                catcher_mesh.materials.append(catcher_material)
                catcher = bpy.data.objects.new(
                    "PIMM_SCENE_SHADOW_CATCHER", catcher_mesh
                )
                catcher["pimm_scene_environment_role"] = "shadow-catcher"
                catcher.is_shadow_catcher = True
                bpy.context.scene.collection.objects.link(catcher)

            if kind == "real-library-override":
                linked_collection = bpy.data.collections["PIMM_PUBLISHED"]
                linked_collection.override_hierarchy_create(
                    bpy.context.scene,
                    bpy.context.view_layer,
                    do_fully_editable=True,
                )
                overrides = [obj for obj in bpy.data.objects if obj.override_library is not None]
                if not overrides:
                    raise RuntimeError("Blender override_hierarchy_create produced no object override")
                override = overrides[0]
                override.name = "PIMM_TEST_PRODUCT_OVERRIDE"
                override_material = bpy.data.materials.new("PIMM_BLACK_POWDERCOAT_OVERRIDE")
                override_material["pimm_material_id"] = "BLACK_POWDERCOAT"
                override_material["pimm_material_scope"] = "shared"
                override.data.materials.clear()
                override.data.materials.append(override_material)

            output = renders / "fixture.png"
            if kind == "output-escape":
                output = root.parent / "escaped-output.png"
            bpy.context.scene.render.filepath = str(output)
            bpy.context.scene.render.resolution_x = 1200
            bpy.context.scene.render.resolution_y = 1200
            bpy.context.scene.render.resolution_percentage = 50 if kind == "resolution-50-percent" else 100
            bpy.context.scene.render.film_transparent = True
            bpy.context.scene.unit_settings.system = "METRIC"
            bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"
            bpy.context.scene.unit_settings.scale_length = 0.001
            bpy.context.scene["pimm_scene_contract_payload"] = contract_canonical
            bpy.context.scene["pimm_scene_contract_snapshot_sha256"] = hashlib.sha256(
                contract_snapshot
            ).hexdigest().upper()
            bpy.ops.wm.save_as_mainfile(filepath=str(scene_path), check_existing=False)
            print("PIMM_FIXTURE_JSON=" + json.dumps({
                "scene": str(scene_path),
                "master": str(master_path),
                "material": str(material_path),
            }, sort_keys=True))
            """
        ),
        encoding="utf-8",
    )


def _base_payload(master_sha256: str, material_sha256: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "scene_id": "pimm-30g--hero--three-quarter",
        "machine": "30G",
        "purpose": "hero",
        "master_path": "masters/PIMM-30G-MASTER.blend",
        "master_sha256": master_sha256,
        "master_collection": "PIMM_PUBLISHED",
        "material_library_path": "masters/PIMM-MATERIAL-LIBRARY.blend",
        "material_library_sha256": material_sha256,
        "camera_name": "CAM_HERO",
        "complete_product": True,
        "animation_contract": None,
        "output_contract": {"width": 1200, "height": 1200, "alpha": True},
    }


def build_scene_fixture(kind: str, root: Path) -> tuple[Path, SceneContract]:
    """Create one real tiny linked Blender fixture beneath the supplied temp root."""

    allowed = {
        "valid",
        "valid-shadow-catcher",
        "private-product-copy",
        "localized-shared-material",
        "overridden-product-material",
        "real-library-override",
        "untagged-local-mesh",
        "stripped-provenance-copy",
        "partial-published",
        "manifest-truncated-partial",
        "collection-evidence-absent",
        "collection-evidence-count-mismatch",
        "collection-evidence-digest-mismatch",
        "orphaned-linked-collection",
        "resolution-50-percent",
        "missing-link",
        "missing-camera",
        "output-escape",
        "wrong-master-sha",
        "wrong-material-library-sha",
        "missing-material-id",
        "node-only-wrong-shared-id",
        "node-only-local-shared-material",
        "node-only-local-machine-material",
        "unpublished-master",
        "artwork-missing",
        "artwork-duplicate",
        "artwork-wrong-parent",
        "artwork-dual-classified",
        "artwork-stale-evidence",
        "artwork-unclassified",
    }
    if kind not in allowed:
        raise ValueError(f"unsupported fixture kind: {kind}")
    builder_path = root / "build_scene_fixture.py"
    _write_fixture_builder(builder_path)
    result = _run_blender(
        [
            "--factory-startup",
            "-b",
            "--python-exit-code",
            "1",
            "-P",
            str(builder_path),
            "--",
            kind,
            str(root),
            str(REPO_ROOT),
        ],
        cwd=REPO_ROOT,
    )
    marker = next(
        line.removeprefix("PIMM_FIXTURE_JSON=")
        for line in result.stdout.splitlines()
        if line.startswith("PIMM_FIXTURE_JSON=")
    )
    built = json.loads(marker)
    from scripts.blender.pimm_production.io_contract import sha256_file

    master_sha256 = sha256_file(Path(built["master"]))
    material_sha256 = sha256_file(Path(built["material"]))
    if kind == "wrong-master-sha":
        master_sha256 = "0" * 64
    if kind == "wrong-material-library-sha":
        material_sha256 = "0" * 64
    return Path(built["scene"]), SceneContract.from_mapping(
        _base_payload(master_sha256, material_sha256)
    )


def _write_contract(path: Path, contract: SceneContract) -> None:
    path.write_text(json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8")


def run_scene_fixture_validation(path: Path, contract: SceneContract) -> list[str]:
    """Open one fixture in fresh background Blender and return validator errors."""

    root = path.parents[2]
    contract_path = root / "scene-contract.json"
    runner_path = root / "validate_scene_fixture.py"
    _write_contract(contract_path, contract)
    runner_path.write_text(
        textwrap.dedent(
            f"""
            import hashlib
            import json
            from pathlib import Path
            import sys
            import bpy
            sys.path.insert(0, {str(REPO_ROOT)!r})
            import scripts.blender.pimm_production.blender_scene_validator as validator
            from scripts.blender.pimm_production.scene_contract import SceneContract

            validator.ASSET_ROOT = Path({str(root)!r})
            contract = SceneContract.from_json(Path({str(contract_path)!r}))
            contract_snapshot_sha256 = hashlib.sha256(
                Path({str(contract_path)!r}).read_bytes()
            ).hexdigest().upper()
            errors = validator.validate_open_render_scene(
                bpy, contract, contract_snapshot_sha256=contract_snapshot_sha256
            )
            print({VALIDATION_MARKER!r} + json.dumps(errors, sort_keys=True))
            """
        ),
        encoding="utf-8",
    )
    result = _run_blender(
        [
            "--factory-startup",
            "-b",
            str(path),
            "--python-exit-code",
            "1",
            "-P",
            str(runner_path),
        ],
        cwd=REPO_ROOT,
    )
    serialized = next(
        line.removeprefix(VALIDATION_MARKER)
        for line in result.stdout.splitlines()
        if line.startswith(VALIDATION_MARKER)
    )
    return json.loads(serialized)


def run_scene_fixture_build(
    master_path: Path,
    contract: SceneContract,
    output_path: Path,
    *,
    mutate_temporary_before_reopen: bool = False,
    mutate_original_contract_before_reopen: bool = False,
    mutate_embedded_contract_before_reopen: bool = False,
) -> dict[str, object]:
    root = master_path.parents[1]
    contract_path = root / "scene-contract-build.json"
    runner_path = root / "build_linked_scene.py"
    has_mutation = (
        mutate_temporary_before_reopen
        or mutate_original_contract_before_reopen
        or mutate_embedded_contract_before_reopen
    )
    _write_contract(contract_path, contract)
    runner_path.write_text(
        textwrap.dedent(
            f"""
            import json
            from pathlib import Path
            import sys
            import bpy
            sys.path.insert(0, {str(REPO_ROOT)!r})
            import scripts.blender.pimm_production.blender_scene_template as template

            template.ASSET_ROOT = Path({str(root)!r})
            if {has_mutation!r}:
                original_validation = template._run_fresh_validation
                def mutate_then_validate(scene_path, snapshot_path):
                    if {mutate_temporary_before_reopen!r}:
                        camera = bpy.data.objects.get("CAM_HERO")
                        bpy.data.objects.remove(camera, do_unlink=True)
                        bpy.ops.wm.save_as_mainfile(filepath=str(scene_path), check_existing=False)
                    if {mutate_original_contract_before_reopen!r}:
                        changed = json.loads(Path({str(contract_path)!r}).read_text(encoding="utf-8"))
                        changed["scene_id"] = "pimm-30g--detail--three-quarter"
                        changed["purpose"] = "detail"
                        Path({str(contract_path)!r}).write_text(
                            json.dumps(changed, sort_keys=True), encoding="utf-8"
                        )
                    if {mutate_embedded_contract_before_reopen!r}:
                        changed = json.loads(bpy.context.scene["pimm_scene_contract_payload"])
                        changed["scene_id"] = "pimm-30g--detail--three-quarter"
                        changed["purpose"] = "detail"
                        bpy.context.scene["pimm_scene_contract_payload"] = json.dumps(
                            changed, sort_keys=True, separators=(",", ":")
                        )
                        bpy.ops.wm.save_as_mainfile(filepath=str(scene_path), check_existing=False)
                    return original_validation(scene_path, snapshot_path)
                template._run_fresh_validation = mutate_then_validate
            result = template.build_linked_scene(Path({str(contract_path)!r}), Path({str(output_path)!r}))
            print({BUILD_MARKER!r} + json.dumps(result, sort_keys=True))
            """
        ),
        encoding="utf-8",
    )
    result = _run_blender(
        [
            "--factory-startup",
            "-b",
            str(master_path),
            "--python-exit-code",
            "1",
            "-P",
            str(runner_path),
        ],
        cwd=REPO_ROOT,
    )
    serialized = next(
        line.removeprefix(BUILD_MARKER)
        for line in result.stdout.splitlines()
        if line.startswith(BUILD_MARKER)
    )
    return json.loads(serialized)


class SceneContractTests(unittest.TestCase):
    def test_campaign_scene_contract_requires_the_exact_shared_machine_scope(self) -> None:
        """Catches a comparison contract being represented as a single-machine scene."""

        campaign_path = (
            REPO_ROOT
            / "scripts"
            / "blender"
            / "pimm_production"
            / "contracts"
            / "campaigns"
            / "pimm-responsive-product-photography-v1.json"
        )
        comparison = load_campaign(campaign_path).by_shot_id[
            "pimm-30g-50g--comparison--desktop"
        ]
        self.assertEqual(comparison.machines, ("30G", "50G"))

        payload = _base_payload("a" * 64, "b" * 64)
        payload.pop("machine")
        payload["machines"] = ["30G", "50G"]
        payload["scene_id"] = "pimm-30g-50g--comparison--desktop"
        payload["purpose"] = "comparison"
        contract = SceneContract.from_mapping(payload)

        self.assertIsNone(contract.machine)
        self.assertEqual(contract.machines, ("30G", "50G"))
        self.assertEqual(contract.to_mapping()["machines"], ("30G", "50G"))

    def test_campaign_scene_contract_derives_output_and_camera_policy(self) -> None:
        """Catches a scene contract that drifts from its immutable campaign camera policy."""

        payload = _base_payload("a" * 64, "b" * 64)
        payload.update(
            {
                "scene_id": "pimm-30g--hero--desktop",
                "purpose": "hero",
                "output_contract": {"width": 2560, "height": 1440, "alpha": True},
                "scene_path": "scenes/stills/pimm-30g--hero--desktop.blend",
                "static_render_setup": {
                    "camera": {
                        "aperture_fstop": 11.0,
                        "clip_end": 10000.0,
                        "clip_start": 1.0,
                        "focal_length_mm": 85.0,
                        "sensor_width_mm": 36.0,
                        "view": "hero-desktop",
                    },
                    "color_management": {
                        "exposure": 0.0,
                        "gamma": 1.0,
                        "look": "AgX - Medium High Contrast",
                        "view_transform": "AgX",
                    },
                    "lighting": {
                        "lower_bounce_name": "BASE_BOUNCE",
                        "required_light_names": ["KEY_SOFTBOX", "FILL_SOFTBOX", "BASE_BOUNCE", "STRIP_LEFT", "STRIP_RIGHT"],
                        "temperature_kelvin": 5500.0,
                    },
                    "physical_shadow": {"catcher_name": "PIMM_SCENE_SHADOW_CATCHER", "gate": "required"},
                    "world": {
                        "hdri_path": "assets/hdri/studio_kontrast_04_4k.exr",
                        "hdri_sha256": "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06",
                        "rotation_degrees": 0.0,
                        "strength": 0.5,
                    },
                },
            }
        )
        self.assertEqual(validate_scene_contract(SceneContract.from_mapping(payload)), [])

        payload["output_contract"]["width"] = 1800
        payload["static_render_setup"]["camera"]["focal_length_mm"] = 135.0
        errors = validate_scene_contract(SceneContract.from_mapping(payload))
        self.assertIn("campaign scene output_contract must match the governed shot policy", errors)
        self.assertIn("static product camera must match the governed shot configuration", errors)

        payload["output_contract"]["width"] = 2560
        payload["static_render_setup"]["camera"]["focal_length_mm"] = 85.0
        payload["animation_contract"] = "still"
        errors = validate_scene_contract(SceneContract.from_mapping(payload))
        self.assertIn("campaign scene animation_contract must be null", errors)

        payload["animation_contract"] = None
        payload["static_render_setup"]["camera"]["view"] = "hero-tablet"
        errors = validate_scene_contract(SceneContract.from_mapping(payload))
        self.assertIn("static product camera must match the governed shot configuration", errors)

    def test_campaign_policy_rejects_invalid_manifest_and_rogue_shared_scene(self) -> None:
        """Catches a mutable campaign manifest or uncontracted shared scene entering validation."""

        payload = json.loads(
            (
                REPO_ROOT
                / "scripts"
                / "blender"
                / "pimm_production"
                / "contracts"
                / "campaigns"
                / "pimm-responsive-product-photography-v1.json"
            ).read_text(encoding="utf-8")
        )
        payload["shots"][0]["width"] = 2048
        with TemporaryDirectory() as root:
            path = Path(root) / "campaign.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            original = scene_contract._CAMPAIGN_PATH
            try:
                scene_contract._CAMPAIGN_PATH = path
                with self.assertRaisesRegex(ValueError, "campaign validation failed"):
                    scene_contract._campaign_policy("pimm-30g--hero--desktop")
            finally:
                scene_contract._CAMPAIGN_PATH = original

        payload = _base_payload("a" * 64, "b" * 64)
        payload.pop("machine")
        payload["machines"] = ["30G", "50G"]
        payload["scene_id"] = "pimm-30g-50g--hero--rogue"
        payload["purpose"] = "hero"
        errors = validate_scene_contract(SceneContract.from_mapping(payload))
        self.assertIn("shared scene contract must refer to an approved campaign comparison shot", errors)

    def test_scene_publication_material_gate_requires_explicit_material_ids(self) -> None:
        """Catches approved material state falling back to a datablock display name."""

        from scripts.blender.pimm_production import blender_scene_template

        for material_id in (None, ""):
            with self.subTest(material_id=material_id):
                properties = (
                    {}
                    if material_id is None
                    else {"pimm_material_id": material_id}
                )
                material = SimpleNamespace(
                    name="PIMM_CONTROLLER_ACTIVE",
                    get=lambda key, default=None, values=properties: values.get(
                        key, default
                    ),
                )
                product_properties = {
                    "pimm_stable_id": "30G-controller-a",
                    "pimm_material_state": "approved",
                }
                product = SimpleNamespace(
                    name="controller-a",
                    data=SimpleNamespace(materials=[material]),
                    get=lambda key, default=None: product_properties.get(key, default),
                )

                errors, _ = blender_scene_template._material_gate_errors([product])
                self.assertIn("pimm_material_id", "\n".join(errors))

    def test_relative_library_resolution_uses_blender_scene_semantics_not_file_existence(
        self,
    ) -> None:
        """Catches authority capture guessing a different relative-library base."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene = root / "scenes" / "scene.blend"
            master = root / "masters" / "PIMM-30G-MASTER.blend"
            material = root / "masters" / "PIMM-MATERIAL-LIBRARY.blend"
            for path in (scene, master, material):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(path.name.encode("utf-8"))
            bpy = SimpleNamespace(data=SimpleNamespace(filepath=str(scene)))
            parent = SimpleNamespace(filepath=str(master), parent=None)
            indirect = SimpleNamespace(filepath=f"//../masters/{material.name}", parent=parent)

            self.assertEqual(
                blender_scene_validator._library_path(bpy, indirect),
                material.resolve(),
            )

    def test_library_authority_preserves_relative_nested_parent_lexical_path(
        self,
    ) -> None:
        """Catches indirect Blender libraries being rebased to the scene or resolved early."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene = root / "scenes" / "fixtures" / "scene.blend"
            master = root / "masters" / "PIMM-30G-MASTER.blend"
            material = root / "masters" / "nested" / "PIMM-MATERIAL-LIBRARY.blend"
            for path in (scene, master, material):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(path.name.encode("utf-8"))
            parent = SimpleNamespace(
                filepath=f"//../../masters/{master.name}", parent=None
            )
            indirect = SimpleNamespace(
                filepath=f"//../../masters/nested/{material.name}", parent=parent
            )
            bpy = SimpleNamespace(
                data=SimpleNamespace(filepath=str(scene)),
            )

            record = blender_scene_validator._library_authority_record(
                bpy, indirect
            )

            self.assertEqual(record["raw_filepath"], indirect.filepath)
            self.assertEqual(record["lexical_path"], str(material))
            self.assertEqual(record["canonical_path"], str(material.resolve()))
            self.assertEqual(record["parent_canonical_path"], str(master.resolve()))

    def test_scene_contract_requires_published_master_collection(self):
        payload = _base_payload("a" * 64, "b" * 64)
        payload["master_collection"] = "PIMM_WORKING"

        errors = validate_scene_contract(SceneContract.from_mapping(payload))

        self.assertRegex("\n".join(errors), "PIMM_PUBLISHED")

    def test_scene_contract_rejects_invalid_identity_and_output_shape(self):
        payload = _base_payload("a" * 64, "b" * 64)
        payload["scene_id"] = "PIMM-30G hero"
        payload["master_path"] = "../PIMM-30G-MASTER.blend"
        payload["material_library_path"] = "materials.blend"
        payload["camera_name"] = "Camera"
        payload["complete_product"] = False
        payload["output_contract"] = {"width": 0, "height": 1200, "alpha": "yes"}

        errors = "\n".join(validate_scene_contract(SceneContract.from_mapping(payload)))

        self.assertIn("scene_id", errors)
        self.assertIn("canonical master_path", errors)
        self.assertIn("canonical material_library_path", errors)
        self.assertIn("camera_name", errors)
        self.assertIn("complete_product", errors)
        self.assertIn("output_contract width", errors)
        self.assertIn("output_contract alpha", errors)

    def test_scene_contract_mapping_is_exact_and_json_round_trips(self):
        payload = _base_payload("a" * 64, "b" * 64)
        payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "exactly"):
            SceneContract.from_mapping(payload)

        payload.pop("unexpected")
        with TemporaryDirectory() as root:
            path = Path(root) / "contract.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            contract = SceneContract.from_json(path)
        self.assertEqual(contract.to_mapping(), payload)
        self.assertEqual(
            canonical_scene_contract_json(contract),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_valid_linked_fixture_passes(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture("valid", Path(root))
            self.assertEqual(run_scene_fixture_validation(path, contract), [])

    def test_published_artwork_contract_fails_closed(self):
        expectations = {
            "artwork-missing": "missing artwork roles",
            "artwork-duplicate": "duplicate artwork roles",
            "artwork-wrong-parent": "attached_parent mismatch",
            "artwork-dual-classified": "stable_id",
            "artwork-stale-evidence": "embedded artwork SHA-256",
            "artwork-unclassified": "published mesh is unclassified",
        }
        for kind, expected in expectations.items():
            with self.subTest(kind=kind), TemporaryDirectory() as root:
                path, contract = build_scene_fixture(kind, Path(root))
                errors = run_scene_fixture_validation(path, contract)
                self.assertIn(expected, "\n".join(errors))

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_exact_authored_shadow_catcher_is_the_only_allowed_local_scene_mesh(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture("valid-shadow-catcher", Path(root))
            self.assertEqual(run_scene_fixture_validation(path, contract), [])

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_private_mesh_and_localized_product_material_fail(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture("private-product-copy", Path(root))
            self.assertIn(
                "private machine mesh",
                "\n".join(run_scene_fixture_validation(path, contract)),
            )
            path, contract = build_scene_fixture("localized-shared-material", Path(root))
            self.assertIn(
                "linked product material made local",
                "\n".join(run_scene_fixture_validation(path, contract)),
            )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_untagged_and_stripped_scene_local_meshes_fail(self):
        expected = {
            "untagged-local-mesh": "scene-local MESH object is forbidden",
            "stripped-provenance-copy": "scene-local MESH datablock is forbidden",
        }
        for kind, message in expected.items():
            with self.subTest(kind=kind), TemporaryDirectory() as root:
                path, contract = build_scene_fixture(kind, Path(root))
                self.assertIn(
                    message,
                    "\n".join(run_scene_fixture_validation(path, contract)),
                )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_complete_product_requires_reachable_full_published_collection(self):
        expected = {
            "partial-published": "embedded stable-ID evidence",
            "orphaned-linked-collection": "not reachable from the active scene",
        }
        for kind, message in expected.items():
            with self.subTest(kind=kind), TemporaryDirectory() as root:
                path, contract = build_scene_fixture(kind, Path(root))
                self.assertIn(
                    message,
                    "\n".join(run_scene_fixture_validation(path, contract)),
                )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_manifest_truncation_cannot_authorize_partial_published_collection(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture("manifest-truncated-partial", Path(root))
            manifest = json.loads(
                (Path(root) / "manifests" / "PIMM-30G-import-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(manifest["solids"]), 1)
            self.assertIn(
                "embedded stable-ID evidence",
                "\n".join(run_scene_fixture_validation(path, contract)),
            )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_published_collection_requires_exact_embedded_evidence(self):
        for kind in {
            "collection-evidence-absent",
            "collection-evidence-count-mismatch",
            "collection-evidence-digest-mismatch",
        }:
            with self.subTest(kind=kind), TemporaryDirectory() as root:
                path, contract = build_scene_fixture(kind, Path(root))
                self.assertIn(
                    "embedded stable-ID evidence",
                    "\n".join(run_scene_fixture_validation(path, contract)),
                )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_resolution_percentage_must_be_native(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture("resolution-50-percent", Path(root))
            self.assertIn(
                "resolution_percentage must equal 100",
                "\n".join(run_scene_fixture_validation(path, contract)),
            )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_real_library_override_is_rejected_when_blender_can_create_it(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture("real-library-override", Path(root))
            self.assertIn(
                "approved product material override",
                "\n".join(run_scene_fixture_validation(path, contract)),
            )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_override_missing_link_camera_and_output_escape_fail(self):
        expected = {
            "overridden-product-material": "approved product material override",
            "missing-link": "PIMM_PUBLISHED",
            "missing-camera": "required camera",
            "output-escape": "managed render root",
        }
        for kind, message in expected.items():
            with self.subTest(kind=kind), TemporaryDirectory() as root:
                path, contract = build_scene_fixture(kind, Path(root))
                self.assertIn(
                    message,
                    "\n".join(run_scene_fixture_validation(path, contract)),
                )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_exact_master_and_material_hashes_are_required(self):
        expected = {
            "wrong-master-sha": "master SHA-256 mismatch",
            "wrong-material-library-sha": "material-library SHA-256 mismatch",
        }
        for kind, message in expected.items():
            with self.subTest(kind=kind), TemporaryDirectory() as root:
                path, contract = build_scene_fixture(kind, Path(root))
                self.assertIn(
                    message,
                    "\n".join(run_scene_fixture_validation(path, contract)),
                )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_render_preflight_requires_explicit_material_id(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture("missing-material-id", Path(root))

            self.assertIn(
                "pimm_material_id",
                "\n".join(run_scene_fixture_validation(path, contract)),
            )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_render_preflight_rejects_wrong_node_only_shared_material_id(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture(
                "node-only-wrong-shared-id", Path(root)
            )

            self.assertIn(
                "canonical shared catalog",
                "\n".join(run_scene_fixture_validation(path, contract)),
            )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_render_preflight_rejects_local_node_only_component_materials(self):
        for kind in (
            "node-only-local-shared-material",
            "node-only-local-machine-material",
        ):
            with self.subTest(kind=kind), TemporaryDirectory() as root:
                path, contract = build_scene_fixture(kind, Path(root))

                self.assertIn(
                    "scene-local or outside the exact master/material-library authority",
                    "\n".join(run_scene_fixture_validation(path, contract)),
                )

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_unpublished_master_blocks_builder_without_creating_output(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture("unpublished-master", Path(root))
            output = Path(root) / "scenes" / "shared-templates" / "template.blend"
            result = run_scene_fixture_build(
                Path(root) / "masters" / "PIMM-30G-MASTER.blend",
                contract,
                output,
            )
            self.assertEqual(result["status"], "blocked_manual_material_approval")
            self.assertFalse(output.exists())
            self.assertIn("PIMM_PUBLISHED", "\n".join(result["errors"]))

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_publishable_fixture_builds_a_linked_template_that_reopens_clean(self):
        with TemporaryDirectory() as root:
            _, contract = build_scene_fixture("valid", Path(root))
            master = Path(root) / "masters" / "PIMM-30G-MASTER.blend"
            output = (
                Path(root)
                / "scenes"
                / "shared-templates"
                / "pimm-linked-studio-template.blend"
            )

            result = run_scene_fixture_build(master, contract, output)

            self.assertEqual(result["status"], "created")
            self.assertIs(result["fresh_validation"], True)
            self.assertTrue(output.is_file())
            self.assertEqual(run_scene_fixture_validation(output, contract), [])

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_reopen_validation_failure_never_publishes_and_cleans_temporary_scene(self):
        with TemporaryDirectory() as root:
            _, contract = build_scene_fixture("valid", Path(root))
            master = Path(root) / "masters" / "PIMM-30G-MASTER.blend"
            output = (
                Path(root)
                / "scenes"
                / "shared-templates"
                / "pimm-linked-studio-template.blend"
            )

            result = run_scene_fixture_build(
                master,
                contract,
                output,
                mutate_temporary_before_reopen=True,
            )

            self.assertEqual(result["status"], "blocked_reopen_validation")
            self.assertIn("required camera", "\n".join(result["errors"]))
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob("*.tmp.blend")), [])

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_original_contract_drift_never_publishes_and_cleans_snapshot(self):
        with TemporaryDirectory() as root:
            _, contract = build_scene_fixture("valid", Path(root))
            master = Path(root) / "masters" / "PIMM-30G-MASTER.blend"
            output = Path(root) / "scenes" / "shared-templates" / "template.blend"

            result = run_scene_fixture_build(
                master,
                contract,
                output,
                mutate_original_contract_before_reopen=True,
            )

            self.assertEqual(result["status"], "blocked_contract_drift")
            self.assertIn("contract changed during build", "\n".join(result["errors"]))
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob("*.tmp.blend")), [])
            self.assertEqual(list(output.parent.glob("*.contract.json")), [])

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_embedded_contract_mismatch_fails_fresh_reopen_and_cleans_snapshot(self):
        with TemporaryDirectory() as root:
            _, contract = build_scene_fixture("valid", Path(root))
            master = Path(root) / "masters" / "PIMM-30G-MASTER.blend"
            output = Path(root) / "scenes" / "shared-templates" / "template.blend"

            result = run_scene_fixture_build(
                master,
                contract,
                output,
                mutate_embedded_contract_before_reopen=True,
            )

            self.assertEqual(result["status"], "blocked_reopen_validation")
            self.assertIn("embedded scene contract payload", "\n".join(result["errors"]))
            self.assertFalse(output.exists())
            self.assertEqual(list(output.parent.glob("*.tmp.blend")), [])
            self.assertEqual(list(output.parent.glob("*.contract.json")), [])


if __name__ == "__main__":
    unittest.main()
