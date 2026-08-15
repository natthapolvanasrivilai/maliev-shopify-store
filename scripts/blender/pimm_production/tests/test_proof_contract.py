import dataclasses
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

import scripts.blender.pimm_production.proof_contract as proof_module
from scripts.blender.pimm_production.contact_sheet import build_contact_sheet
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.proof_contract import (
    ProofContract,
    validate_proof_contract,
    write_proof_manifest,
)
from scripts.blender.pimm_production.scene_contract import SceneContract
from scripts.blender.pimm_production.tests.test_scene_contract import build_scene_fixture


BLENDER = Path(r"D:\Blender 5.2\blender.exe")
REPO_ROOT = Path(__file__).resolve().parents[4]
PROOF_RUNNER = REPO_ROOT / "scripts" / "blender" / "pimm_production" / "blender_proof_render.py"
TOOL_LOCK = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\free-tools-lock.json"
)
RESULT_MARKER = "PIMM_PROOF_RENDER_JSON="


def scene_contract_fixture() -> SceneContract:
    """Return the exact Task 4 valid scene payload used by proof unit tests."""

    return SceneContract.from_mapping(
        {
            "schema_version": 1,
            "scene_id": "pimm-30g--hero--three-quarter",
            "machine": "30G",
            "purpose": "hero",
            "master_path": "masters/PIMM-30G-MASTER.blend",
            "master_sha256": "a" * 64,
            "master_collection": "PIMM_PUBLISHED",
            "material_library_path": "masters/PIMM-MATERIAL-LIBRARY.blend",
            "material_library_sha256": "b" * 64,
            "camera_name": "CAM_HERO",
            "complete_product": True,
            "animation_contract": None,
            "output_contract": {"width": 1200, "height": 1200, "alpha": True},
        }
    )


def composition_contract() -> ProofContract:
    return ProofContract.from_mapping(
        {
            "schema_version": 1,
            "generation_id": "proof-20260815T153000Z-a1b2c3d",
            "stage": "composition",
            "scene_contract_path": "scenes/contracts/pimm-30g--hero--three-quarter.json",
            "scene_sha256": "c" * 64,
            "master_sha256": "a" * 64,
            "material_library_sha256": "b" * 64,
            "resolution_percentage": 25,
            "samples": 32,
            "denoise": True,
            "backgrounds": ["white", "checker", "dark"],
            "object_masks": False,
            "output_root": "renders/proofs/proof-20260815T153000Z-a1b2c3d",
        }
    )


def material_contract(backgrounds: list[str], object_masks: bool) -> ProofContract:
    return ProofContract.from_mapping(
        {
            "schema_version": 1,
            "generation_id": "proof-20260815T153001Z-b2c3d4e",
            "stage": "material-lighting",
            "scene_contract_path": "scenes/contracts/pimm-30g--hero--three-quarter.json",
            "scene_sha256": "c" * 64,
            "master_sha256": "a" * 64,
            "material_library_sha256": "b" * 64,
            "resolution_percentage": 25,
            "samples": 64,
            "denoise": True,
            "backgrounds": list(backgrounds),
            "object_masks": object_masks,
            "output_root": "renders/proofs/proof-20260815T153001Z-b2c3d4e",
        }
    )


def _write_scene_contract(root: Path, contract: SceneContract, relative: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8")
    return path


def _run_fixture_proofs(
    scene_path: Path,
    proof_paths: list[Path],
    root: Path,
) -> tuple[subprocess.CompletedProcess[str], list[dict[str, object]]]:
    command = [
        str(BLENDER),
        "--factory-startup",
        "-b",
        str(scene_path),
        "--python-exit-code",
        "1",
        "-P",
        str(PROOF_RUNNER),
        "--",
        "--fixture-asset-root",
        str(root),
        "--tool-lock",
        str(TOOL_LOCK),
    ]
    for proof_path in proof_paths:
        command.extend(["--proof-contract", str(proof_path)])
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    rows = [
        json.loads(line.removeprefix(RESULT_MARKER))
        for line in result.stdout.splitlines()
        if line.startswith(RESULT_MARKER)
    ]
    return result, rows


class ProofContractTests(unittest.TestCase):
    def test_composition_proof_is_low_cost(self):
        contract = composition_contract()
        self.assertLessEqual(contract.resolution_percentage, 25)
        self.assertGreaterEqual(contract.resolution_percentage, 12.5)
        self.assertLessEqual(contract.samples, 32)

    def test_material_proof_requires_all_backgrounds_and_masks(self):
        contract = material_contract(backgrounds=["white"], object_masks=False)
        errors = validate_proof_contract(contract, scene_contract_fixture())
        self.assertIn("white/checker/dark", "\n".join(errors))
        self.assertIn("object/material masks", "\n".join(errors))

    def test_contract_is_exact_immutable_and_round_trips_json(self):
        contract = composition_contract()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            contract.samples = 1
        payload = contract.to_mapping()
        payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "exactly"):
            ProofContract.from_mapping(payload)

        with TemporaryDirectory() as root_text:
            path = Path(root_text) / "proof.json"
            payload.pop("unexpected")
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(ProofContract.from_json(path), contract)
        self.assertIsInstance(contract.backgrounds, tuple)

    def test_contract_rejects_cost_path_generation_and_hash_mutations(self):
        scene = scene_contract_fixture()
        mutations = {
            "generation": ("generation_id", "proof-reused"),
            "native": ("resolution_percentage", 100),
            "samples": ("samples", 33),
            "denoise": ("denoise", False),
            "escape": ("output_root", "renders/finals/proof-20260815T153000Z-a1b2c3d"),
            "master": ("master_sha256", "d" * 64),
        }
        for name, (field, value) in mutations.items():
            with self.subTest(name=name):
                contract = dataclasses.replace(composition_contract(), **{field: value})
                errors = "\n".join(validate_proof_contract(contract, scene))
                self.assertTrue(errors)
        self.assertIn(
            "samples",
            "\n".join(
                validate_proof_contract(
                    dataclasses.replace(material_contract(["white", "checker", "dark"], True), samples=65),
                    scene,
                )
            ),
        )

    def test_contract_rejects_preexisting_generation_directory(self):
        contract = composition_contract()
        scene = scene_contract_fixture()
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            _write_scene_contract(root, scene, contract.scene_contract_path)
            (root / contract.output_root).mkdir(parents=True)
            with patch.object(proof_module, "ASSET_ROOT", root):
                errors = validate_proof_contract(contract, scene)
        self.assertIn("generation ID is already in use", "\n".join(errors))

    def test_manifest_and_contact_sheet_are_hash_verified_and_do_not_mutate_sources(self):
        contract = composition_contract()
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            output_root = root / contract.output_root
            output_root.mkdir(parents=True)
            outputs: list[Path] = []
            for background, color in {
                "rgba": (80, 120, 160, 255),
                "white": (255, 255, 255, 255),
                "checker": (192, 192, 192, 255),
                "dark": (24, 24, 24, 255),
            }.items():
                path = output_root / f"{scene_contract_fixture().scene_id}--{background}.png"
                Image.new("RGBA", (24, 16), color).save(path)
                outputs.append(path)
            (output_root / "render-metadata.json").write_text(
                json.dumps(
                    {
                        "engine": "CYCLES",
                        "resolution_percentage": contract.resolution_percentage,
                        "samples": contract.samples,
                        "denoise": contract.denoise,
                        "named_shaft_regions": {"SHAFT_FIXTURE": [0.25, 0.25, 0.75, 0.75]},
                    }
                ),
                encoding="utf-8",
            )
            before = {path: sha256_file(path) for path in outputs}
            with patch.object(proof_module, "ASSET_ROOT", root):
                manifest_path = write_proof_manifest(contract, outputs)
            sheet_path = build_contact_sheet(manifest_path, output_root / "contact-sheet.png")
            after = {path: sha256_file(path) for path in outputs}

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            evidence = json.loads((output_root / "contact-sheet.json").read_text(encoding="utf-8"))
            self.assertEqual(before, after)
            self.assertEqual([item["background"] for item in manifest["outputs"]], ["checker", "dark", "rgba", "white"])
            self.assertEqual(evidence["generation_id"], contract.generation_id)
            self.assertEqual(evidence["manifest_sha256"], sha256_file(manifest_path))
            self.assertEqual(evidence["contact_sheet_sha256"], sha256_file(sheet_path))
            self.assertEqual(len(evidence["cells"]), 4)
            self.assertTrue(
                manifest["qa"]["named_shaft_reflection"]["white"]["present"]
            )
            with Image.open(sheet_path) as sheet:
                self.assertGreater(sheet.width, 24)
                self.assertGreater(sheet.height, 16)

            manifest["outputs"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (output_root / "contact-sheet.json").unlink()
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                build_contact_sheet(manifest_path, output_root / "mutated-sheet.png")

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_fixture_composition_and_material_proofs_render_real_outputs_and_cleanup(self):
        root_path: Path | None = None
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            root_path = root
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(
                root, scene, "scenes/fixtures/pimm-30g--hero--three-quarter.json"
            )
            protected = [
                source_path,
                root / scene.master_path,
                root / scene.material_library_path,
                scene_path,
                scene_contract_path,
            ]
            before = {path: (path.stat().st_size, path.stat().st_mtime_ns, sha256_file(path)) for path in protected}

            contracts: list[ProofContract] = []
            for base, generation, samples in [
                (composition_contract(), "proof-20260815T153000Z-a1b2c3d", 16),
                (material_contract(["white", "checker", "dark"], True), "proof-20260815T153001Z-b2c3d4e", 32),
            ]:
                contract = dataclasses.replace(
                    base,
                    generation_id=generation,
                    scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                    scene_sha256=sha256_file(scene_path),
                    master_sha256=scene.master_sha256,
                    material_library_sha256=scene.material_library_sha256,
                    resolution_percentage=12.5 if base.stage == "composition" else 25,
                    samples=samples,
                    output_root=f"renders/proofs/{generation}",
                )
                proof_path = root / "scenes" / "fixtures" / f"{generation}.json"
                proof_path.write_text(json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8")
                contracts.append(contract)

                result, rows = _run_fixture_proofs(scene_path, [proof_path], root)
                self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["status"], "pass")

            after = {path: (path.stat().st_size, path.stat().st_mtime_ns, sha256_file(path)) for path in protected}
            self.assertEqual(before, after)

            for contract in contracts:
                output_root = root / contract.output_root
                expected = {"rgba", "white", "checker", "dark"}
                if contract.object_masks:
                    expected |= {"object-mask", "material-mask", "shadow-mask"}
                image_paths = sorted(output_root.glob("*.png"))
                backgrounds = {
                    path.stem.rsplit("--", 1)[-1]
                    for path in image_paths
                    if path.name != "contact-sheet.png"
                }
                self.assertEqual(backgrounds, expected)
                manifest_path = output_root / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "pass")
                self.assertEqual(manifest["render"]["engine"], "CYCLES")
                self.assertEqual(manifest["render"]["samples"], contract.samples)
                self.assertEqual(manifest["render"]["resolution_percentage"], contract.resolution_percentage)
                expected_dimension = 150 if contract.resolution_percentage == 12.5 else 300
                self.assertEqual(manifest["render"]["actual_dimensions"], [expected_dimension, expected_dimension])
                self.assertTrue(manifest["fingerprints_unchanged"])
                self.assertGreater(manifest["qa"]["subject"]["subject_pixel_fraction"], 0)
                self.assertIsNotNone(manifest["qa"]["subject"]["subject_bounds"])
                intended = manifest["qa"]["intended_subject"]["bounds"]
                self.assertGreater(intended["left"], 0)
                self.assertGreater(intended["top"], 0)
                self.assertLess(intended["right"], expected_dimension - 1)
                self.assertLess(intended["bottom"], expected_dimension - 1)
                self.assertTrue(manifest["render"]["shadow_pass_available"])
                self.assertGreater(
                    manifest["qa"]["physical_shadow_extent"]["nonzero_fraction"],
                    0,
                )
                if contract.object_masks:
                    self.assertIsNotNone(manifest["qa"]["intended_subject"]["bounds"])
                self.assertTrue((output_root / "contact-sheet.png").is_file())
                self.assertTrue((output_root / "contact-sheet.json").is_file())
                for entry in manifest["outputs"]:
                    path = output_root / entry["path"]
                    self.assertEqual(entry["sha256"], sha256_file(path))
                    self.assertIn("metrics", entry)

                rgba = output_root / f"{scene.scene_id}--rgba.png"
                with Image.open(rgba).convert("RGBA") as source:
                    for background in ("white", "checker", "dark"):
                        composite_path = (
                            output_root / f"{scene.scene_id}--{background}.png"
                        )
                        with Image.open(composite_path).convert("RGBA") as composite:
                            for source_pixel, composite_pixel in zip(
                                source.get_flattened_data(), composite.get_flattened_data()
                            ):
                                if source_pixel[3] == 255:
                                    self.assertEqual(source_pixel[:3], composite_pixel[:3])

        self.assertIsNotNone(root_path)
        self.assertFalse(root_path.exists())

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_scene_hash_failure_stops_batch_before_any_generation_output(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(root, scene, "scenes/fixtures/scene.json")
            first = dataclasses.replace(
                composition_contract(),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256="0" * 64,
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
            )
            second = dataclasses.replace(
                material_contract(["white", "checker", "dark"], True),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256=sha256_file(scene_path),
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
            )
            proof_paths = []
            for contract in (first, second):
                path = root / "scenes" / "fixtures" / f"{contract.generation_id}.json"
                path.write_text(json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8")
                proof_paths.append(path)

            result, rows = _run_fixture_proofs(scene_path, proof_paths, root)

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "blocked_scene_drift")
            self.assertFalse((root / first.output_root).exists())
            self.assertFalse((root / second.output_root).exists())


if __name__ == "__main__":
    unittest.main()
