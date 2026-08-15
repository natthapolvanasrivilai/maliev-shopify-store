import dataclasses
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image

import scripts.blender.pimm_production.blender_proof_render as render_module
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
    *,
    inject_drift_after_prepare: bool = False,
    inject_authored_mutation: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[dict[str, object]]]:
    runner = PROOF_RUNNER
    if inject_drift_after_prepare or inject_authored_mutation is not None:
        runner = root / "inject_proof_drift.py"
        runner.write_text(
            "\n".join(
                [
                    "from pathlib import Path",
                    "import sys",
                    f"sys.path.insert(0, {str(REPO_ROOT)!r})",
                    "import bpy",
                    "import scripts.blender.pimm_production.blender_proof_render as proof_render",
                    *(
                        [
                            "scene = bpy.context.scene",
                            "authored_light_data = bpy.data.lights.new('AUTHORED_KEY', type='AREA')",
                            "authored_light_data.energy = 125.0",
                            "authored_light_data.color = (0.2, 0.4, 0.6)",
                            "authored_light = bpy.data.objects.new('AUTHORED_KEY', authored_light_data)",
                            "scene.collection.objects.link(authored_light)",
                            "authored_world = bpy.data.worlds.new('AUTHORED_WORLD')",
                            "authored_world.use_nodes = True",
                            "scene.world = authored_world",
                            "compositor = bpy.data.node_groups.new('AUTHORED_COMPOSITOR', 'CompositorNodeTree')",
                            "compositor_node = compositor.nodes.new('CompositorNodeBrightContrast')",
                        ]
                        if inject_authored_mutation is not None
                        else []
                    ),
                    "original = proof_render._run_pillow_finalizer",
                    "def injected(*args, **kwargs):",
                    "    result = original(*args, **kwargs)",
                    *(
                        [
                            f"    source = Path({str(root / 'sources' / 'PIMM-30G-authoritative-source.step')!r})",
                            "    source.write_bytes(source.read_bytes() + b'INJECTED-DRIFT')",
                        ]
                        if inject_drift_after_prepare
                        else []
                    ),
                    *(
                        {
                            "camera": ["    scene.camera.data.sensor_width += 1.0"],
                            "light": ["    authored_light_data.color = (0.9, 0.1, 0.2)"],
                            "world": [
                                "    authored_world.node_tree.nodes['Background'].inputs['Strength'].default_value += 1.0"
                            ],
                            "compositor": [
                                "    compositor_node.mute = True",
                                "    scene.compositing_node_group = compositor",
                            ],
                        }.get(inject_authored_mutation, [])
                    ),
                    "    return result",
                    "proof_render._run_pillow_finalizer = injected",
                    "raise SystemExit(proof_render.main())",
                ]
            ),
            encoding="utf-8",
        )
    command = [
        str(BLENDER),
        "--factory-startup",
        "-b",
        str(scene_path),
        "--python-exit-code",
        "1",
        "-P",
        str(runner),
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


def _fingerprint_record(path: str, sha256: str) -> dict[str, object]:
    return {"path": path, "bytes": 1, "mtime_ns": 1, "sha256": sha256}


def _valid_render_metadata(
    contract: ProofContract,
    *,
    actual_dimensions: list[int] | None = None,
    named_shaft_regions: dict[str, object] | None = None,
) -> dict[str, object]:
    fingerprints = {
        "source": _fingerprint_record("C:/fixture/source.step", "1" * 64),
        "master": _fingerprint_record(
            "C:/fixture/master.blend", contract.master_sha256.upper()
        ),
        "material_library": _fingerprint_record(
            "C:/fixture/material.blend", contract.material_library_sha256.upper()
        ),
        "scene": _fingerprint_record("C:/fixture/scene.blend", contract.scene_sha256.upper()),
    }
    authored_settings = {
        "camera": {
            "identity": {"name": "CAM_HERO", "type": "Object", "library": None},
            "transform": {
                "location": [4.0, -6.0, 3.0],
                "rotation_mode": "XYZ",
                "rotation_euler": [1.0, 0.0, 0.5],
                "scale": [1.0, 1.0, 1.0],
                "matrix_world": [1.0] * 16,
                "parent": None,
            },
            "type": "PERSP",
            "lens": 50.0,
            "sensor_fit": "AUTO",
            "sensor_width": 36.0,
            "sensor_height": 32.0,
            "shift_x": 0.0,
            "shift_y": 0.0,
            "clip_start": 0.1,
            "clip_end": 1000.0,
            "dof": {
                "use_dof": False,
                "focus_object": None,
                "focus_distance": 10.0,
                "aperture_fstop": 2.8,
                "aperture_blades": 0,
                "aperture_rotation": 0.0,
                "aperture_ratio": 1.0,
            },
        },
        "lights": [],
        "world": None,
        "compositor": {"enabled": False, "node_tree": None},
        "render": {"properties": {"engine": "CYCLES"}},
        "view_layers": [{"name": "ViewLayer", "properties": {}, "material_override": None}],
        "color_management": {"view": {"view_transform": "AgX"}},
        "cycles": {"samples": contract.samples},
    }
    return {
        "schema": "pimm-proof-render-metadata/v1",
        "engine": "CYCLES",
        "device": "CPU",
        "blender": {
            "binary_path": "D:/Blender 5.2/blender.exe",
            "binary_sha256": "4" * 64,
            "version": "5.2.0",
        },
        "resolution_percentage": contract.resolution_percentage,
        "base_dimensions": [1200, 1200],
        "actual_dimensions": actual_dimensions or [300, 300],
        "image_settings": {
            "film_transparent": True,
            "file_format": "PNG",
            "color_mode": "RGBA",
            "color_depth": "8",
            "use_file_extension": True,
        },
        "samples": contract.samples,
        "denoise": contract.denoise,
        "cycles": {
            "device": "CPU",
            "samples": contract.samples,
            "use_denoising": contract.denoise,
            "max_bounces": 12,
            "transparent_max_bounces": 8,
        },
        "agx": {
            "view_transform": "AgX",
            "look": "Medium High Contrast",
            "exposure": 0.0,
            "gamma": 1.0,
        },
        "render_seconds": 0.25,
        "named_shaft_regions": named_shaft_regions or {},
        "shadow_pass_available": True,
        "fixture_mode": True,
        "proof_contract_sha256": "5" * 64,
        "scene_contract_sha256": "6" * 64,
        "tool_lock_sha256": "7" * 64,
        "fingerprints": {"before": fingerprints, "after": fingerprints},
        "authored_settings": {
            "before": authored_settings,
            "after": authored_settings,
        },
        "intended_subject_metrics": {
            "bounds": {"left": 1, "top": 1, "right": 20, "bottom": 14},
            "nonzero_fraction": 0.5,
            "unique_values": [0, 255],
            "unique_value_count": 2,
        },
        "physical_shadow_metrics": {
            "bounds": {"left": 2, "top": 2, "right": 21, "bottom": 15},
            "nonzero_fraction": 0.25,
            "unique_values": [0, 255],
            "unique_value_count": 2,
        },
    }


def _write_manifest_evidence(
    root: Path,
    output_root: Path,
    contract: ProofContract,
    scene: SceneContract,
    metadata: dict[str, object],
) -> None:
    del root
    proof_snapshot = output_root / "proof-contract.json"
    scene_snapshot = output_root / "scene-contract.json"
    tool_snapshot = output_root / "tool-lock.json"
    proof_snapshot.write_text(
        json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
    )
    scene_snapshot.write_text(
        json.dumps(scene.to_mapping(), sort_keys=True), encoding="utf-8"
    )
    tool_snapshot.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "id": "blender",
                        "path": metadata["blender"]["binary_path"],
                        "sha256": metadata["blender"]["binary_sha256"],
                        "version": metadata["blender"]["version"],
                    }
                ]
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    metadata["proof_contract_sha256"] = sha256_file(proof_snapshot)
    metadata["scene_contract_sha256"] = sha256_file(scene_snapshot)
    metadata["tool_lock_sha256"] = sha256_file(tool_snapshot)
    (output_root / "render-metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )


def _prepare_finalizer_fixture(
    root: Path, output_root: Path
) -> tuple[ProofContract, SceneContract, Path, Path, Path]:
    contract = material_contract(["white", "checker", "dark"], True)
    scene = scene_contract_fixture()
    proof_path = root / "fixture-proof.json"
    proof_path.write_text(
        json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
    )
    _write_scene_contract(root, scene, contract.scene_contract_path)
    output_root.mkdir(parents=True, exist_ok=True)
    _write_manifest_evidence(
        root, output_root, contract, scene, _valid_render_metadata(contract)
    )
    rgba = output_root / f"{scene.scene_id}--rgba.png"
    Image.new("RGBA", (300, 300), (90, 110, 130, 255)).save(rgba)
    product = output_root / f".{scene.scene_id}--product-only.tmp.png"
    Image.new("RGBA", (300, 300), (90, 110, 130, 255)).save(product)
    return contract, scene, proof_path, rgba, product


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

    def test_effective_dimensions_are_exact_and_fractional_rounding_is_rejected(self):
        scene = scene_contract_fixture()
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            for percentage, expected in ((12.5, (150, 150)), (25, (300, 300))):
                with self.subTest(percentage=percentage):
                    contract = dataclasses.replace(
                        composition_contract(),
                        resolution_percentage=percentage,
                    )
                    _write_scene_contract(root, scene, contract.scene_contract_path)
                    with patch.object(proof_module, "ASSET_ROOT", root):
                        errors = validate_proof_contract(contract, scene)
                    self.assertEqual(errors, [])
                    self.assertEqual(
                        proof_module.effective_dimensions(scene, percentage), expected
                    )

            rounded = dataclasses.replace(
                composition_contract(), resolution_percentage=12.6
            )
            with patch.object(proof_module, "ASSET_ROOT", root):
                errors = validate_proof_contract(rounded, scene)
            self.assertIn("non-integral effective dimensions", "\n".join(errors))

    def test_manifest_rejects_incomplete_mixed_or_drifted_evidence(self):
        mutations = {
            "missing-engine": "metadata",
            "fingerprint-drift": "metadata",
            "master-pin-mismatch": "metadata",
            "material-pin-mismatch": "metadata",
            "scene-pin-mismatch": "metadata",
            "settings-mismatch": "metadata",
            "blender-lock-mismatch": "metadata",
            "wrong-dimensions": "image",
            "mixed-shot": "filename",
            "missing-output": "output",
        }
        for mutation in mutations:
            with self.subTest(mutation=mutation), TemporaryDirectory() as root_text:
                root = Path(root_text)
                contract = composition_contract()
                scene = scene_contract_fixture()
                _write_scene_contract(root, scene, contract.scene_contract_path)
                output_root = root / contract.output_root
                output_root.mkdir(parents=True)
                outputs: list[Path] = []
                for background in ("rgba", "white", "checker", "dark"):
                    if mutation == "missing-output" and background == "dark":
                        continue
                    shot_id = (
                        "pimm-30g--detail--mixed"
                        if mutation == "mixed-shot" and background == "dark"
                        else scene.scene_id
                    )
                    dimensions = (
                        (299, 300)
                        if mutation == "wrong-dimensions" and background == "white"
                        else (300, 300)
                    )
                    path = output_root / f"{shot_id}--{background}.png"
                    Image.new("RGBA", dimensions, (100, 120, 140, 255)).save(path)
                    outputs.append(path)
                metadata = _valid_render_metadata(contract)
                if mutation == "missing-engine":
                    metadata.pop("engine")
                elif mutation == "fingerprint-drift":
                    metadata["fingerprints"] = json.loads(
                        json.dumps(metadata["fingerprints"])
                    )
                    metadata["fingerprints"]["after"]["source"]["sha256"] = "9" * 64
                elif mutation == "settings-mismatch":
                    metadata["samples"] = contract.samples - 1
                elif mutation.endswith("-pin-mismatch"):
                    name = mutation.removesuffix("-pin-mismatch")
                    if name == "material":
                        name = "material_library"
                    metadata["fingerprints"] = json.loads(
                        json.dumps(metadata["fingerprints"])
                    )
                    metadata["fingerprints"]["before"][name]["sha256"] = "9" * 64
                    metadata["fingerprints"]["after"][name]["sha256"] = "9" * 64
                _write_manifest_evidence(root, output_root, contract, scene, metadata)
                if mutation == "blender-lock-mismatch":
                    metadata["blender"]["binary_sha256"] = "8" * 64
                    (output_root / "render-metadata.json").write_text(
                        json.dumps(metadata), encoding="utf-8"
                    )

                with patch.object(proof_module, "ASSET_ROOT", root):
                    with self.assertRaises(ValueError):
                        write_proof_manifest(contract, outputs)

    def test_standalone_finalizer_rejects_external_product_temp_and_preserves_it(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene = scene_contract_fixture()
            contract = material_contract(["white", "checker", "dark"], True)
            output_root = root / contract.output_root
            output_root.mkdir(parents=True)
            proof_path = output_root / "proof-contract.json"
            proof_path.write_text(
                json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
            )
            _write_scene_contract(root, scene, contract.scene_contract_path)
            (output_root / "scene-contract.json").write_text(
                json.dumps(scene.to_mapping(), sort_keys=True), encoding="utf-8"
            )
            rgba = output_root / f"{scene.scene_id}--rgba.png"
            Image.new("RGBA", (300, 300), (90, 110, 130, 255)).save(rgba)
            (output_root / "render-metadata.json").write_text(
                json.dumps(_valid_render_metadata(contract)), encoding="utf-8"
            )
            external = root / f".{scene.scene_id}--product-only.tmp.png"
            Image.new("RGBA", (300, 300), (90, 110, 130, 255)).save(external)
            before = sha256_file(external)

            with self.assertRaisesRegex(ValueError, "product-only temporary path"):
                render_module.finalize_proof(
                    proof_path, output_root, rgba, root, external
                )

            self.assertTrue(external.is_file())
            self.assertEqual(sha256_file(external), before)
            rgba_before = sha256_file(rgba)
            with self.assertRaisesRegex(ValueError, "product-only temporary path"):
                render_module.finalize_proof(proof_path, output_root, rgba, root, rgba)
            self.assertEqual(sha256_file(rgba), rgba_before)

            exact_hidden = output_root / f".{scene.scene_id}--product-only.tmp.png"
            os.link(external, exact_hidden)
            with self.assertRaisesRegex(ValueError, "product-only temporary path"):
                render_module.finalize_proof(
                    proof_path, output_root, rgba, root, exact_hidden
                )
            self.assertTrue(exact_hidden.is_file())
            self.assertEqual(sha256_file(external), before)
            self.assertFalse((output_root / "manifest.json").exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction mutation")
    def test_finalizer_rejects_generation_junction_without_deleting_external_target(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as external_text:
            root = Path(root_text)
            external = Path(external_text)
            contract = material_contract(["white", "checker", "dark"], True)
            generation = root / contract.output_root
            generation.parent.mkdir(parents=True)
            subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", str(generation), str(external)],
                check=True,
                capture_output=True,
                text=True,
            )
            try:
                _, _, proof_path, rgba, product = _prepare_finalizer_fixture(
                    root, generation
                )
                external_product = external / product.name
                before = sha256_file(external_product)
                captured: ValueError | None = None
                try:
                    render_module.finalize_proof(
                        proof_path, generation, rgba, root, product
                    )
                except ValueError as error:
                    captured = error

                self.assertIsNotNone(captured)
                self.assertRegex(str(captured), "junction|reparse")
                self.assertTrue(external_product.is_file())
                self.assertEqual(sha256_file(external_product), before)
                for name in (
                    "manifest.json",
                    "contact-sheet.png",
                    "contact-sheet.json",
                    ".manifest.pending.json",
                    ".contact-sheet.pending.png",
                    ".contact-sheet.pending.json",
                ):
                    self.assertFalse((external / name).exists(), msg=name)
            finally:
                if generation.exists():
                    os.rmdir(generation)

    def test_product_scratch_replacement_race_is_preserved_and_fails_closed(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            contract = material_contract(["white", "checker", "dark"], True)
            output_root = root / contract.output_root
            _, _, proof_path, rgba, product = _prepare_finalizer_fixture(
                root, output_root
            )
            external = root / "external-readable.png"
            Image.new("RGBA", (300, 300), (12, 34, 56, 255)).save(external)
            external_before = sha256_file(external)
            original_product = root / "original-product-preserved.png"
            original_analyze = render_module.analyze_mask_metrics
            injected = False

            def replace_after_validation(image: object) -> dict[str, object]:
                nonlocal injected
                result = original_analyze(image)
                if not injected:
                    injected = True
                    os.replace(product, original_product)
                    shutil.copyfile(external, product)
                return result

            captured: ValueError | None = None
            with patch.object(
                render_module, "analyze_mask_metrics", replace_after_validation
            ):
                try:
                    render_module.finalize_proof(
                        proof_path, output_root, rgba, root, product
                    )
                except ValueError as error:
                    captured = error

            self.assertTrue(injected)
            self.assertIsNotNone(captured)
            self.assertRegex(str(captured), "replaced|identity|race")
            self.assertTrue(product.is_file())
            self.assertTrue(original_product.is_file())
            self.assertEqual(sha256_file(external), external_before)
            self.assertEqual(sha256_file(product), external_before)
            for name in (
                "manifest.json",
                "contact-sheet.png",
                "contact-sheet.json",
                ".manifest.pending.json",
                ".contact-sheet.pending.png",
                ".contact-sheet.pending.json",
            ):
                self.assertFalse((output_root / name).exists(), msg=name)

    def test_product_scratch_lexical_alias_is_rejected_and_preserved(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            contract = material_contract(["white", "checker", "dark"], True)
            output_root = root / contract.output_root
            _, _, proof_path, rgba, product = _prepare_finalizer_fixture(
                root, output_root
            )
            (output_root / "alias-component").mkdir()
            alias = output_root / "alias-component" / ".." / product.name
            before = sha256_file(product)

            with self.assertRaisesRegex(ValueError, "lexical|alias|canonical"):
                render_module.finalize_proof(
                    proof_path, output_root, rgba, root, alias
                )

            self.assertTrue(product.is_file())
            self.assertEqual(sha256_file(product), before)

    def test_canonical_mode_never_calls_fixture_setup_and_rejects_fixture_roles(self):
        clean_bpy = SimpleNamespace(data=SimpleNamespace(objects=[]))
        with patch.object(
            render_module,
            "_frame_fixture_scene",
            side_effect=AssertionError("fixture setup called"),
        ) as fixture_setup:
            self.assertEqual(
                render_module._prepare_render_environment(
                    clean_bpy, object(), fixture_mode=False
                ),
                ([], []),
            )
            fixture_setup.assert_not_called()

        fixture_object = SimpleNamespace(
            type="MESH",
            library=None,
            name="PIMM_ENV_SHADOW_CATCHER",
            get=lambda name, default=None: (
                "shadow-catcher"
                if name == "pimm_proof_environment_role"
                else default
            ),
        )
        dirty_bpy = SimpleNamespace(data=SimpleNamespace(objects=[fixture_object]))
        with self.assertRaisesRegex(ValueError, "fixture-only"):
            render_module._prepare_render_environment(
                dirty_bpy, object(), fixture_mode=False
            )

    def test_executing_blender_must_match_exact_locked_path_hash_and_version(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            locked_binary = root / "blender.exe"
            locked_binary.write_bytes(b"PINNED-BLENDER")
            lock = {
                "tools": [
                    {
                        "id": "blender",
                        "path": str(locked_binary),
                        "sha256": sha256_file(locked_binary),
                        "version": "5.2.0",
                    }
                ]
            }
            exact = SimpleNamespace(
                app=SimpleNamespace(
                    binary_path=str(locked_binary), version_string="5.2.0 LTS"
                )
            )
            self.assertEqual(
                render_module._validate_executing_blender(exact, lock),
                {
                    "binary_path": str(locked_binary.resolve()),
                    "binary_sha256": sha256_file(locked_binary),
                    "version": "5.2.0",
                },
            )

            other_binary = root / "other-blender.exe"
            other_binary.write_bytes(b"PINNED-BLENDER")
            mutations = {
                "path": SimpleNamespace(
                    app=SimpleNamespace(
                        binary_path=str(other_binary), version_string="5.2.0 LTS"
                    )
                ),
                "version": SimpleNamespace(
                    app=SimpleNamespace(
                        binary_path=str(locked_binary), version_string="5.1.0"
                    )
                ),
            }
            for name, fake_bpy in mutations.items():
                with self.subTest(name=name), self.assertRaises(ValueError):
                    render_module._validate_executing_blender(fake_bpy, lock)
            drifted_lock = json.loads(json.dumps(lock))
            drifted_lock["tools"][0]["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                render_module._validate_executing_blender(exact, drifted_lock)

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
                Image.new("RGBA", (300, 300), color).save(path)
                outputs.append(path)
            _write_scene_contract(root, scene_contract_fixture(), contract.scene_contract_path)
            _write_manifest_evidence(
                root,
                output_root,
                contract,
                scene_contract_fixture(),
                _valid_render_metadata(
                    contract,
                    named_shaft_regions={
                        "SHAFT_FIXTURE": [0.25, 0.25, 0.75, 0.75]
                    },
                ),
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
            self.assertEqual(evidence["header"]["stage"], contract.stage)
            self.assertIs(evidence["header"]["denoise"], True)
            self.assertEqual(len(evidence["cells"]), 4)
            self.assertTrue(
                manifest["qa"]["named_shaft_reflection"]["white"]["present"]
            )
            with Image.open(sheet_path) as sheet:
                self.assertGreater(sheet.width, 300)
                self.assertGreater(sheet.height, 300)

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
                evidence = json.loads(
                    (output_root / "contact-sheet.json").read_text(encoding="utf-8")
                )
                self.assertEqual(evidence["header"]["stage"], contract.stage)
                self.assertEqual(evidence["header"]["denoise"], contract.denoise)
                for pending_name in render_module._PENDING_TO_PUBLISHED:
                    self.assertFalse((output_root / pending_name).exists())
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

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_injected_drift_after_prepare_publishes_no_pass_artifacts(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(
                root, scene, "scenes/fixtures/scene.json"
            )
            contract = dataclasses.replace(
                composition_contract(),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256=sha256_file(scene_path),
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
                resolution_percentage=12.5,
                samples=16,
            )
            proof_path = root / "scenes" / "fixtures" / "drift-proof.json"
            proof_path.write_text(
                json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
            )

            result, rows = _run_fixture_proofs(
                scene_path,
                [proof_path],
                root,
                inject_drift_after_prepare=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(rows), 1, msg=result.stdout + result.stderr)
            self.assertEqual(rows[0]["status"], "blocked_fingerprint_drift")
            output_root = root / contract.output_root
            for name in (
                "manifest.json",
                "contact-sheet.png",
                "contact-sheet.json",
                ".manifest.pending.json",
                ".contact-sheet.pending.png",
                ".contact-sheet.pending.json",
            ):
                self.assertFalse((output_root / name).exists(), msg=name)

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_authored_render_state_mutations_at_final_gate_publish_no_pass_artifacts(self):
        for mutation in ("camera", "light", "world", "compositor"):
            with self.subTest(mutation=mutation), TemporaryDirectory() as root_text:
                root = Path(root_text)
                scene_path, scene = build_scene_fixture("valid", root)
                source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
                source_path.parent.mkdir(parents=True)
                source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
                scene_contract_path = _write_scene_contract(
                    root, scene, "scenes/fixtures/scene.json"
                )
                contract = dataclasses.replace(
                    composition_contract(),
                    scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                    scene_sha256=sha256_file(scene_path),
                    master_sha256=scene.master_sha256,
                    material_library_sha256=scene.material_library_sha256,
                    resolution_percentage=12.5,
                    samples=16,
                )
                proof_path = root / "scenes" / "fixtures" / f"{mutation}-proof.json"
                proof_path.write_text(
                    json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
                )

                result, rows = _run_fixture_proofs(
                    scene_path,
                    [proof_path],
                    root,
                    inject_authored_mutation=mutation,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(rows), 1, msg=result.stdout + result.stderr)
                self.assertEqual(
                    rows[0]["status"],
                    "blocked_settings_drift",
                    msg=result.stdout + result.stderr,
                )
                output_root = root / contract.output_root
                for name in (
                    "manifest.json",
                    "contact-sheet.png",
                    "contact-sheet.json",
                    ".manifest.pending.json",
                    ".contact-sheet.pending.png",
                    ".contact-sheet.pending.json",
                ):
                    self.assertFalse((output_root / name).exists(), msg=name)


if __name__ == "__main__":
    unittest.main()
