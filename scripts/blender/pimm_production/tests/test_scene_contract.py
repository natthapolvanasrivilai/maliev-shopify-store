import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import textwrap
import unittest

from scripts.blender.pimm_production.scene_contract import (
    SceneContract,
    validate_scene_contract,
)


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
            import json
            from pathlib import Path
            import sys

            import bpy

            kind = sys.argv[sys.argv.index("--") + 1]
            root = Path(sys.argv[sys.argv.index("--") + 2])
            masters = root / "masters"
            scenes = root / "scenes" / "fixtures"
            renders = root / "renders" / "proofs" / "fixture"
            masters.mkdir(parents=True, exist_ok=True)
            scenes.mkdir(parents=True, exist_ok=True)
            renders.mkdir(parents=True, exist_ok=True)
            material_path = masters / "PIMM-MATERIAL-LIBRARY.blend"
            master_path = masters / "PIMM-30G-MASTER.blend"
            scene_path = scenes / f"{kind}.blend"

            bpy.ops.wm.read_factory_settings(use_empty=True)
            shared = bpy.data.materials.new("PIMM_TEST_SHARED")
            shared.use_fake_user = True
            shared["pimm_material_id"] = "TEST_SHARED"
            shared["pimm_material_scope"] = "shared"
            bpy.ops.wm.save_as_mainfile(filepath=str(material_path), check_existing=False)

            bpy.ops.wm.read_factory_settings(use_empty=True)
            with bpy.data.libraries.load(str(material_path), link=True, relative=True) as (available, requested):
                requested.materials = ["PIMM_TEST_SHARED"]
            linked_material = bpy.data.materials["PIMM_TEST_SHARED"]
            published_name = "PIMM_WORKING" if kind == "unpublished-master" else "PIMM_PUBLISHED"
            published = bpy.data.collections.new(published_name)
            bpy.context.scene.collection.children.link(published)
            mesh = bpy.data.meshes.new("PIMM_TEST_PRODUCT_MESH")
            mesh.from_pydata(
                [(-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (0.0, 1.0, 0.0)],
                [],
                [(0, 1, 2)],
            )
            mesh.materials.append(linked_material)
            product = bpy.data.objects.new("PIMM_TEST_PRODUCT", mesh)
            product["pimm_stable_id"] = "30G-fixture-product"
            product["pimm_material_state"] = "approved"
            published.objects.link(product)
            bpy.context.scene["pimm_master_machine"] = "30G"
            bpy.ops.wm.save_as_mainfile(filepath=str(master_path), check_existing=False)

            bpy.ops.wm.read_factory_settings(use_empty=True)
            if kind not in {"missing-link", "unpublished-master"}:
                with bpy.data.libraries.load(str(master_path), link=True, relative=True) as (available, requested):
                    requested.collections = ["PIMM_PUBLISHED"]
                bpy.context.scene.collection.children.link(bpy.data.collections["PIMM_PUBLISHED"])

            camera_data = bpy.data.cameras.new("CAM_HERO")
            camera = bpy.data.objects.new("CAM_HERO", camera_data)
            bpy.context.scene.collection.objects.link(camera)
            bpy.context.scene.camera = camera
            if kind == "missing-camera":
                bpy.data.objects.remove(camera, do_unlink=True)

            if kind in {"private-product-copy", "localized-shared-material", "overridden-product-material"}:
                private_mesh = bpy.data.meshes.new("PIMM_PRIVATE_PRODUCT_MESH")
                private_mesh.from_pydata(
                    [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                    [],
                    [(0, 1, 2)],
                )
                private = bpy.data.objects.new("PIMM_PRIVATE_PRODUCT", private_mesh)
                private["pimm_stable_id"] = "30G-fixture-private"
                private["pimm_product_material_override"] = kind == "overridden-product-material"
                bpy.context.scene.collection.objects.link(private)
                if kind != "private-product-copy":
                    local_material = bpy.data.materials.new("PIMM_TEST_SHARED_LOCAL")
                    local_material["pimm_material_id"] = "TEST_SHARED"
                    local_material["pimm_material_scope"] = "shared"
                    private_mesh.materials.append(local_material)

            output = renders / "fixture.png"
            if kind == "output-escape":
                output = root.parent / "escaped-output.png"
            bpy.context.scene.render.filepath = str(output)
            bpy.context.scene.render.resolution_x = 1200
            bpy.context.scene.render.resolution_y = 1200
            bpy.context.scene.render.film_transparent = True
            bpy.context.scene.unit_settings.system = "METRIC"
            bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"
            bpy.context.scene.unit_settings.scale_length = 0.001
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
        "private-product-copy",
        "localized-shared-material",
        "overridden-product-material",
        "missing-link",
        "missing-camera",
        "output-escape",
        "wrong-master-sha",
        "wrong-material-library-sha",
        "unpublished-master",
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
            import json
            from pathlib import Path
            import sys
            import bpy
            sys.path.insert(0, {str(REPO_ROOT)!r})
            import scripts.blender.pimm_production.blender_scene_validator as validator
            from scripts.blender.pimm_production.scene_contract import SceneContract

            validator.ASSET_ROOT = Path({str(root)!r})
            contract = SceneContract.from_json(Path({str(contract_path)!r}))
            errors = validator.validate_open_render_scene(bpy, contract)
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
    master_path: Path, contract: SceneContract, output_path: Path
) -> dict[str, object]:
    root = master_path.parents[1]
    contract_path = root / "scene-contract-build.json"
    runner_path = root / "build_linked_scene.py"
    _write_contract(contract_path, contract)
    runner_path.write_text(
        textwrap.dedent(
            f"""
            import json
            from pathlib import Path
            import sys
            sys.path.insert(0, {str(REPO_ROOT)!r})
            import scripts.blender.pimm_production.blender_scene_template as template

            template.ASSET_ROOT = Path({str(root)!r})
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

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_valid_linked_fixture_passes(self):
        with TemporaryDirectory() as root:
            path, contract = build_scene_fixture("valid", Path(root))
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
            self.assertTrue(output.is_file())
            self.assertEqual(run_scene_fixture_validation(output, contract), [])


if __name__ == "__main__":
    unittest.main()
