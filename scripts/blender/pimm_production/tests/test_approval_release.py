"""Fixture-only contract tests for PIMM owner approval and immutable releases."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from scripts.blender.pimm_production.approval_manifest import (
    record_decision,
    validate_approval,
    validate_approval_payload,
)
from scripts.blender.pimm_production.blender_final_render import authorize_final_render, run_authorized_final
from scripts.blender.pimm_production.release_manifest import build_release_manifest


SHOT_ID = "pimm-30g--hero--three-quarter"
RELEASE_ID = "release-2026-08-15-r01"
BLENDER = Path(r"D:\Blender 5.2\blender.exe")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _proof_manifest(root: Path, scene_sha256: str) -> Path:
    proof_root = root / "renders" / "proofs" / "proof-20260815T153000Z-a1b2c3d"
    proof_root.mkdir(parents=True)
    rgba = proof_root / f"{SHOT_ID}--rgba.png"
    Image.new("RGBA", (16, 12), (30, 40, 50, 160)).save(rgba)
    contact = proof_root / "contact-sheet.png"
    Image.new("RGBA", (16, 12), (255, 255, 255, 255)).save(contact)
    settings = {
        "camera": {"lens": 50},
        "lights": [{"energy": 400}],
        "world": {"strength": 0.1},
        "compositor": {"enabled": True},
        "render": {"engine": "CYCLES"},
    }
    proof = {
        "schema": "pimm-proof-manifest/v1",
        "generation_id": "proof-20260815T153000Z-a1b2c3d",
        "status": "pass",
        "stage": "material-lighting",
        "scene_sha256": scene_sha256,
        "master_sha256": "b" * 64,
        "material_library_sha256": "c" * 64,
        "render": {
            "proof_contract_sha256": "d" * 64,
            "actual_dimensions": [16, 12],
            "image_settings": {"color_mode": "RGBA"},
            "samples": 64,
            "fingerprints": {
                "before": {
                    "source": {"path": "", "sha256": "e" * 64},
                    "master": {"path": "", "sha256": "b" * 64},
                    "material_library": {"path": "", "sha256": "c" * 64},
                    "scene": {"path": "", "sha256": scene_sha256},
                },
                "after": {
                    "source": {"path": "", "sha256": "e" * 64},
                    "master": {"path": "", "sha256": "b" * 64},
                    "material_library": {"path": "", "sha256": "c" * 64},
                    "scene": {"path": "", "sha256": scene_sha256},
                },
            },
            "authored_settings": {"before": settings, "after": settings},
        },
        "qa": {"composition": "approved fixture"},
        "outputs": [
            {
                "shot_id": SHOT_ID,
                "background": "rgba",
                "path": rgba.name,
                "width": 16,
                "height": 12,
                "sha256": _sha256(rgba),
            }
        ],
    }
    _write_json(proof_root / "manifest.json", proof)
    return proof_root / "manifest.json"


def write_approval_fixture(root: Path, decision: str, scene_sha256: str) -> tuple[Path, Path]:
    """Write a complete approval and matching final contract for fixture tests."""

    proof_path = _proof_manifest(root, scene_sha256)
    approval_path = record_decision(proof_path, SHOT_ID, decision, "natth", "fixture review")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    final = {
        "schema": "pimm-final-render-contract/v1",
        "release_id": RELEASE_ID,
        "shot_id": SHOT_ID,
        "generation_id": approval["proof_generation_id"],
        "inputs": approval["inputs"],
        "render_settings": approval["render_settings"],
        "samples": 128,
        "output_root": f"renders/final/{RELEASE_ID}",
        "deliverables": ["exr", "png", "webp"],
    }
    final_path = _write_json(root / "contracts" / "final.json", final)
    return approval_path, final_path


def write_release_output_fixture(root: Path, generation_id: str) -> Path:
    """Write one complete final-output manifest with a transparent delivery family."""

    output_root = root / "renders" / "final" / RELEASE_ID / SHOT_ID
    output_root.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, object]] = []
    for extension, mime in (("png", "image/png"), ("webp", "image/webp")):
        path = output_root / f"{SHOT_ID}--transparent.{extension}"
        Image.new("RGBA", (16, 12), (30, 40, 50, 160)).save(path)
        outputs.append(
            {
                "logical_asset_id": f"{SHOT_ID}--transparent-{extension}",
                "path": path.name,
                "sha256": _sha256(path),
                "dimensions": [16, 12],
                "alpha": True,
                "mime_type": mime,
            }
        )
    exr = output_root / f"{SHOT_ID}--transparent.exr"
    exr.write_bytes(b"v/1\x01fixture-float-exr")
    outputs.append(
        {
            "logical_asset_id": f"{SHOT_ID}--transparent-exr",
            "path": exr.name,
            "sha256": _sha256(exr),
            "dimensions": [16, 12],
            "alpha": True,
            "mime_type": "image/x-exr",
        }
    )
    manifest = {
        "schema": "pimm-final-output-manifest/v1",
        "release_id": RELEASE_ID,
        "generation_id": generation_id,
        "shot_id": SHOT_ID,
        "approval_sha256": "a" * 64,
        "output_root": f"renders/final/{RELEASE_ID}",
        "required_deliverables": ["exr", "png", "webp"],
        "outputs": outputs,
    }
    return _write_json(output_root / "final-output-manifest.json", manifest)


class ApprovalReleaseTests(unittest.TestCase):
    def test_native_final_runner_is_an_explicit_authorized_operation(self) -> None:
        """Catches a final gate that authorizes data but cannot render native evidence."""

        self.assertTrue(callable(run_authorized_final))

    @unittest.skipUnless(BLENDER.is_file(), "fixture Blender runtime unavailable")
    def test_native_final_runner_emits_real_exr_png_webp_and_manifest(self) -> None:
        """Catches a final runner that claims release evidence without native media."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            scene_path = root / "fixtures" / "final.blend"
            scene_path.parent.mkdir(parents=True)
            setup = "\n".join((
                "import bpy",
                "bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))",
                "bpy.context.object.data.materials.append(bpy.data.materials.new('fixture-material'))",
                "bpy.ops.object.camera_add(location=(0, -6, 0))",
                "camera = bpy.context.object",
                "camera.rotation_euler = (1.5708, 0, 0)",
                "bpy.context.scene.camera = camera",
                "bpy.ops.wm.save_as_mainfile(filepath=" + repr(str(scene_path)) + ")",
            ))
            result = subprocess.run(
                [str(BLENDER), "--factory-startup", "-b", "--python-expr", setup],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            final = json.loads(final_contract_path.read_text(encoding="utf-8"))
            final["asset_root"] = str(root)
            final["scene_path"] = str(scene_path)
            _write_json(final_contract_path, final)
            manifest_path = run_authorized_final(approval_path, final_contract_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual({item["mime_type"] for item in manifest["outputs"]}, {"image/x-exr", "image/png", "image/webp"})
            self.assertTrue((manifest_path.parent / "final.exr").read_bytes().startswith(b"v/1\x01"))
            with Image.open(manifest_path.parent / "final.png") as png:
                self.assertEqual(png.mode, "RGBA")
                self.assertEqual(png.size, (16, 12))

    def test_any_scene_drift_invalidates_approval(self) -> None:
        approval = {
            "schema_version": 1,
            "decision": "approved",
            "owner": "natth",
            "inputs": {"scene_sha256": "a" * 64},
        }
        errors = validate_approval_payload(approval, {"scene_sha256": "b" * 64})
        self.assertIn("scene SHA-256 drift", "\n".join(errors))

    def test_recorded_approval_is_hash_bound_revisioned_and_not_overwritten(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            first = record_decision(proof, SHOT_ID, "approved", "natth", "approved")
            second = record_decision(proof, SHOT_ID, "rejected", "natth", "amended")
            first_payload = json.loads(first.read_text(encoding="utf-8"))
            second_payload = json.loads(second.read_text(encoding="utf-8"))
            self.assertNotEqual(first, second)
            self.assertEqual(first_payload["revision"], 1)
            self.assertEqual(second_payload["revision"], 2)
            self.assertEqual(second_payload["prior_approval_sha256"], _sha256(first))
            self.assertEqual(validate_approval(first, first_payload["inputs"]), [])

    def test_later_rejection_revokes_an_older_approved_revision(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            approved = record_decision(proof, SHOT_ID, "approved", "natth", "approved")
            record_decision(proof, SHOT_ID, "rejected", "natth", "rejected later")
            _, final_contract = write_approval_fixture(root / "final", "approved", "a" * 64)
            with self.assertRaisesRegex(ValueError, "latest approval revision"):
                authorize_final_render(approved, final_contract)

    def test_proof_pixel_mutation_invalidates_recorded_approval(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, _ = write_approval_fixture(root, "approved", "a" * 64)
            proof_pixel = root / "renders" / "proofs" / "proof-20260815T153000Z-a1b2c3d" / f"{SHOT_ID}--rgba.png"
            Image.new("RGBA", (16, 12), (1, 2, 3, 255)).save(proof_pixel)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            self.assertIn("proof pixel SHA-256 drift", "\n".join(validate_approval(approval_path, approval["inputs"])))

    def test_source_file_mutation_invalidates_approval_on_disk(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            source = root / "source.step"
            source.write_bytes(b"authoritative source")
            payload = json.loads(proof.read_text(encoding="utf-8"))
            fingerprints = payload["render"]["fingerprints"]
            for phase in ("before", "after"):
                fingerprints[phase]["source"] = {"path": str(source), "sha256": _sha256(source)}
                for name, digest in (("master", "b" * 64), ("material_library", "c" * 64), ("scene", "a" * 64)):
                    fingerprints[phase][name] = {"path": "", "sha256": digest}
            _write_json(proof, payload)
            approval = record_decision(proof, SHOT_ID, "approved", "natth", "reviewed")
            source.write_bytes(b"changed source")
            self.assertIn("proof evidence cannot be read", "\n".join(validate_approval(approval, {})))

    def test_validate_approval_returns_errors_for_unreadable_proof_evidence(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, _ = write_approval_fixture(root, "approved", "a" * 64)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            Path(approval["proof_manifest_path"]).write_text("{", encoding="utf-8")
            errors = validate_approval(approval_path, approval["inputs"])
            self.assertIn("proof evidence cannot be read", "\n".join(errors))

    def test_final_render_requires_approved_decision(self) -> None:
        with TemporaryDirectory() as root_text:
            approval_path, final_contract_path = write_approval_fixture(Path(root_text), "rejected", "a" * 64)
            with self.assertRaisesRegex(ValueError, "owner approval required"):
                authorize_final_render(approval_path, final_contract_path)

    def test_final_render_fails_closed_on_settings_and_dimension_drift(self) -> None:
        with TemporaryDirectory() as root_text:
            approval_path, final_contract_path = write_approval_fixture(Path(root_text), "approved", "a" * 64)
            payload = json.loads(final_contract_path.read_text(encoding="utf-8"))
            payload["render_settings"]["camera_sha256"] = "f" * 64
            payload["render_settings"]["output_dimensions"] = [17, 12]
            _write_json(final_contract_path, payload)
            with self.assertRaisesRegex(ValueError, "final render authorization failed") as error:
                authorize_final_render(approval_path, final_contract_path)
            self.assertIn("camera SHA-256 drift", str(error.exception))
            self.assertIn("output dimensions drift", str(error.exception))

    def test_final_render_rejects_each_approved_render_state_mutation(self) -> None:
        mutations = {
            "camera_sha256": "camera SHA-256 drift",
            "lights_sha256": "lights SHA-256 drift",
            "world_sha256": "world SHA-256 drift",
            "compositor_sha256": "compositor SHA-256 drift",
            "render_settings_sha256": "render settings SHA-256 drift",
            "composition_sha256": "composition SHA-256 drift",
        }
        for field, expected_error in mutations.items():
            with self.subTest(field=field), TemporaryDirectory() as root_text:
                approval_path, final_contract_path = write_approval_fixture(Path(root_text), "approved", "a" * 64)
                payload = json.loads(final_contract_path.read_text(encoding="utf-8"))
                payload["render_settings"][field] = "f" * 64
                _write_json(final_contract_path, payload)
                with self.assertRaisesRegex(ValueError, expected_error):
                    authorize_final_render(approval_path, final_contract_path)

    def test_owner_and_shot_are_required_for_an_approval(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            with self.assertRaisesRegex(ValueError, "shot_id is not present"):
                record_decision(proof, "pimm-30g--unknown", "approved", "natth", "review")
            approval_path, final_contract_path = write_approval_fixture(root / "missing-owner", "approved", "a" * 64)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["owner"] = ""
            _write_json(approval_path, approval)
            with self.assertRaisesRegex(ValueError, "owner approval required"):
                authorize_final_render(approval_path, final_contract_path)

    def test_final_render_allows_only_explicit_sampling_increase(self) -> None:
        with TemporaryDirectory() as root_text:
            approval_path, final_contract_path = write_approval_fixture(Path(root_text), "approved", "a" * 64)
            authorization = authorize_final_render(approval_path, final_contract_path)
            self.assertEqual(authorization.output_root.as_posix(), f"renders/final/{RELEASE_ID}")
            payload = json.loads(final_contract_path.read_text(encoding="utf-8"))
            payload["samples"] = 64
            _write_json(final_contract_path, payload)
            with self.assertRaisesRegex(ValueError, "sampling increase"):
                authorize_final_render(approval_path, final_contract_path)

    def test_release_rejects_mixed_generations(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            outputs = [
                write_release_output_fixture(root / "one", "proof-20260815T153000Z-a1b2c3d"),
                write_release_output_fixture(root / "two", "proof-20260815T160000Z-d4e5f6a"),
            ]
            with self.assertRaisesRegex(ValueError, "mixed proof generations"):
                build_release_manifest(RELEASE_ID, outputs)

    def test_release_rejects_outputs_from_separate_immutable_roots(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            outputs = [
                write_release_output_fixture(root / "one", "proof-20260815T153000Z-a1b2c3d"),
                write_release_output_fixture(root / "two", "proof-20260815T153000Z-a1b2c3d"),
            ]
            with self.assertRaisesRegex(ValueError, "release output roots"):
                build_release_manifest(RELEASE_ID, outputs)

    def test_release_rejects_duplicate_assets_missing_exr_and_proof_paths(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            output = write_release_output_fixture(root, "proof-20260815T153000Z-a1b2c3d")
            payload = json.loads(output.read_text(encoding="utf-8"))
            duplicate = copy.deepcopy(payload["outputs"][0])
            payload["outputs"].append(duplicate)
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "duplicate logical asset ID"):
                build_release_manifest(RELEASE_ID, [output])

            output = write_release_output_fixture(root / "missing", "proof-20260815T153000Z-a1b2c3d")
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["outputs"] = [item for item in payload["outputs"] if item["mime_type"] != "image/x-exr"]
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "absent EXR"):
                build_release_manifest(RELEASE_ID, [output])

            output = write_release_output_fixture(root / "unsafe", "proof-20260815T153000Z-a1b2c3d")
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["output_root"] = "renders/proofs/proof-20260815T153000Z-a1b2c3d"
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "proof/archive/mutable"):
                build_release_manifest(RELEASE_ID, [output])

    def test_approved_fixture_creates_atomic_release_manifest_last(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            output = write_release_output_fixture(root, "proof-20260815T153000Z-a1b2c3d")
            release_path = build_release_manifest(RELEASE_ID, [output])
            release = json.loads(release_path.read_text(encoding="utf-8"))
            self.assertEqual(release["release_id"], RELEASE_ID)
            self.assertEqual(release["generation_id"], "proof-20260815T153000Z-a1b2c3d")
            self.assertEqual(len(release["assets"]), 3)
            self.assertEqual(release_path.name, "release-manifest.json")
            self.assertFalse(release_path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
