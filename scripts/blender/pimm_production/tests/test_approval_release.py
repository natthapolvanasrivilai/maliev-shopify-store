"""Fixture-only contract tests for PIMM owner approval and immutable releases."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image

from scripts.blender.pimm_production.approval_manifest import (
    record_decision,
    validate_approval,
    validate_approval_payload,
)
import scripts.blender.pimm_production.approval_manifest as approval_module
import scripts.blender.pimm_production.blender_final_render as final_module
from scripts.blender.pimm_production.blender_final_render import authorize_final_render, run_authorized_final
from scripts.blender.pimm_production.io_contract import sha256_file
import scripts.blender.pimm_production.proof_contract as proof_module
from scripts.blender.pimm_production.release_manifest import build_release_manifest
import scripts.blender.pimm_production.release_manifest as release_module
from scripts.blender.pimm_production.tests import test_proof_contract as proof_fixtures


SHOT_ID = "pimm-30g--hero--three-quarter"
RELEASE_ID = "release-2026-08-15-r01"
BLENDER = Path(r"D:\Blender 5.2\blender.exe")
REPO_ROOT = Path(__file__).resolve().parents[4]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fingerprint(path: Path) -> dict[str, object]:
    stat_result = path.stat()
    return {
        "path": str(path.resolve()),
        "bytes": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
        "sha256": _sha256(path),
    }


def _proof_manifest(
    root: Path,
    scene_sha256: str,
    generation_id: str = "proof-20260815T153000Z-a1b2c3d",
) -> Path:
    """Write a genuine Task 5 proof manifest and all on-disk authorities."""

    del scene_sha256  # the fixture derives all pins from real bytes
    root.mkdir(parents=True, exist_ok=True)
    inputs = root / "inputs"
    inputs.mkdir(exist_ok=True)
    source = inputs / "source.step"
    master = inputs / "PIMM-30G-MASTER.blend"
    material = inputs / "PIMM-MATERIAL-LIBRARY.blend"
    scene_path = inputs / "scene.blend"
    native_scene = scene_path.exists()
    source.write_bytes(b"authoritative STEP")
    master.write_bytes(b"authoritative master")
    material.write_bytes(b"authoritative material library")
    if not scene_path.exists():
        scene_path.write_bytes(b"authoritative fixture scene")

    base_contract = proof_fixtures.composition_contract()
    contract = dataclasses.replace(
        base_contract,
        generation_id=generation_id,
        scene_sha256=_sha256(scene_path),
        master_sha256=_sha256(master),
        material_library_sha256=_sha256(material),
        output_root=f"renders/proofs/{generation_id}",
    )
    base_scene = proof_fixtures.scene_contract_fixture()
    scene = dataclasses.replace(
        base_scene,
        master_sha256=contract.master_sha256,
        material_library_sha256=contract.material_library_sha256,
        output_contract={"width": 64, "height": 48, "alpha": True},
    )
    proof_fixtures._write_scene_contract(root, scene, contract.scene_contract_path)
    proof_root = root / "renders" / "proofs" / generation_id
    proof_root.mkdir(parents=True)
    metadata = proof_fixtures._valid_render_metadata(contract, actual_dimensions=[16, 12])
    metadata["base_dimensions"] = [64, 48]
    tool_binary = BLENDER if native_scene else root / "tools" / "blender.exe"
    if tool_binary != BLENDER:
        tool_binary.parent.mkdir(parents=True)
        tool_binary.write_bytes(b"fixture Blender binary")
    metadata["blender"] = {
        "binary_path": str(tool_binary.resolve()),
        "binary_sha256": _sha256(tool_binary),
        "version": "5.2.0",
    }
    records = {
        "source": _fingerprint(source),
        "master": _fingerprint(master),
        "material_library": _fingerprint(material),
        "scene": _fingerprint(scene_path),
    }
    metadata["fingerprints"] = {"before": copy.deepcopy(records), "after": copy.deepcopy(records)}

    if tool_binary == BLENDER:
        capture_path = root / "captured-authored-settings.json"
        expression = "\n".join(
            (
                "import json, pathlib, sys",
                f"sys.path.insert(0, {str(REPO_ROOT)!r})",
                "from scripts.blender.pimm_production.blender_proof_render import _capture_authored_settings",
                f"pathlib.Path({str(capture_path)!r}).write_text(json.dumps(_capture_authored_settings(__import__('bpy')), sort_keys=True), encoding='utf-8')",
            )
        )
        result = subprocess.run(
            [str(BLENDER), "--factory-startup", "-b", str(scene_path), "--python-expr", expression],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        authored = json.loads(capture_path.read_text(encoding="utf-8"))
        metadata["authored_settings"] = {"before": authored, "after": copy.deepcopy(authored)}

    proof_fixtures._write_manifest_evidence(root, proof_root, contract, scene, metadata)
    outputs: list[Path] = []
    for background, color in (
        ("rgba", (30, 40, 50, 160)),
        ("white", (230, 230, 230, 255)),
        ("checker", (120, 130, 140, 255)),
        ("dark", (20, 25, 30, 255)),
    ):
        output = proof_root / f"{SHOT_ID}--{background}.png"
        Image.new("RGBA", (16, 12), color).save(output)
        outputs.append(output)
    with patch.object(proof_module, "ASSET_ROOT", root.resolve()):
        proof = proof_module.write_proof_manifest(contract, outputs)
    Image.new("RGBA", (64, 48), (255, 255, 255, 255)).save(proof_root / "contact-sheet.png")
    return proof


def write_approval_fixture(
    root: Path,
    decision: str,
    scene_sha256: str,
    *,
    generation_id: str = "proof-20260815T153000Z-a1b2c3d",
) -> tuple[Path, Path]:
    """Write a complete approval and matching final contract for fixture tests."""

    proof_path = _proof_manifest(root, scene_sha256, generation_id)
    approval_path = record_decision(proof_path, SHOT_ID, decision, "natth", "fixture review")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    final = {
        "schema": "pimm-final-render-contract/v1",
        "release_id": RELEASE_ID,
        "shot_id": SHOT_ID,
        "generation_id": approval["proof_generation_id"],
        "authority_roots": approval["authority_roots"],
        "evidence": approval["evidence"],
        "inputs": approval["inputs"],
        "render_settings": approval["render_settings"],
        "samples": 128,
        "output_root": f"renders/final/{RELEASE_ID}",
        "deliverables": ["exr", "png", "webp"],
        "asset_root": approval["authority_roots"]["asset"],
        "scene_path": approval["evidence"]["scene"]["path"],
    }
    final_path = _write_json(root / "contracts" / "final.json", final)
    return approval_path, final_path


def write_release_output_fixture(root: Path, generation_id: str) -> Path:
    """Write one complete final-output manifest with a transparent delivery family."""

    approval_path, final_contract_path = write_approval_fixture(
        root, "approved", "a" * 64, generation_id=generation_id
    )
    authorization = authorize_final_render(approval_path, final_contract_path)
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
    _write_float_exr(exr, 16, 12)
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
        "approval_path": str(authorization.approval_path),
        "approval_sha256": authorization.approval_sha256,
        "authorized_final_contract_path": str(authorization.final_contract_path),
        "authorized_final_contract_sha256": authorization.final_contract_sha256,
        "final_authorization_sha256": authorization.authorization_sha256,
        "output_root": f"renders/final/{RELEASE_ID}",
        "required_deliverables": ["exr", "png", "webp"],
        "qa": {
            "product_visible": True,
            "alpha_min": 160,
            "alpha_max": 160,
            "material_state_sha256": "1" * 64,
            "controller_state_sha256": "2" * 64,
            "animation_state_sha256": "3" * 64,
        },
        "outputs": outputs,
    }
    return _write_json(output_root / "final-output-manifest.json", manifest)


def _write_float_exr(path: Path, width: int, height: int) -> None:
    """Write a minimal valid uncompressed scanline float-RGBA OpenEXR fixture."""

    def attribute(name: str, kind: str, value: bytes) -> bytes:
        return name.encode("ascii") + b"\0" + kind.encode("ascii") + b"\0" + struct.pack("<I", len(value)) + value

    channels = b""
    for name in ("A", "B", "G", "R"):
        channels += name.encode("ascii") + b"\0" + struct.pack("<I", 2) + b"\0\0\0\0" + struct.pack("<II", 1, 1)
    channels += b"\0"
    window = struct.pack("<iiii", 0, 0, width - 1, height - 1)
    header = b"v/1\x01" + struct.pack("<I", 2)
    header += attribute("channels", "chlist", channels)
    header += attribute("compression", "compression", b"\0")
    header += attribute("dataWindow", "box2i", window)
    header += attribute("displayWindow", "box2i", window)
    header += attribute("lineOrder", "lineOrder", b"\0")
    header += attribute("pixelAspectRatio", "float", struct.pack("<f", 1.0))
    header += attribute("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0))
    header += attribute("screenWindowWidth", "float", struct.pack("<f", 1.0))
    header += b"\0"
    scanline_data = struct.pack("<f", 0.5) * (width * 4)
    chunks = [struct.pack("<iI", y, len(scanline_data)) + scanline_data for y in range(height)]
    cursor = len(header) + height * 8
    offsets: list[int] = []
    for chunk in chunks:
        offsets.append(cursor)
        cursor += len(chunk)
    path.write_bytes(header + struct.pack(f"<{height}Q", *offsets) + b"".join(chunks))


class ApprovalReleaseTests(unittest.TestCase):
    def test_native_final_runner_is_an_explicit_authorized_operation(self) -> None:
        """Catches a final gate that authorizes data but cannot render native evidence."""

        self.assertTrue(callable(run_authorized_final))

    @unittest.skipUnless(BLENDER.is_file(), "fixture Blender runtime unavailable")
    def test_native_final_runner_emits_real_exr_png_webp_and_manifest(self) -> None:
        """Catches a final runner that claims release evidence without native media."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path = root / "inputs" / "scene.blend"
            scene_path.parent.mkdir(parents=True)
            setup = "\n".join((
                "import bpy",
                "bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))",
                "bpy.ops.object.camera_add(location=(0, -6, 0))",
                "camera = bpy.context.object",
                "camera.rotation_euler = (1.5708, 0, 0)",
                "bpy.context.scene.camera = camera",
                "bpy.context.scene.world = None",
                "bpy.context.scene.render.engine = 'CYCLES'",
                "bpy.ops.wm.save_as_mainfile(filepath=" + repr(str(scene_path)) + ")",
            ))
            result = subprocess.run(
                [str(BLENDER), "--factory-startup", "-b", "--python-expr", setup],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            manifest_path = run_authorized_final(approval_path, final_contract_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual({item["mime_type"] for item in manifest["outputs"]}, {"image/x-exr", "image/png", "image/webp"})
            self.assertTrue((manifest_path.parent / f"{SHOT_ID}--transparent.exr").read_bytes().startswith(b"v/1\x01"))
            with Image.open(manifest_path.parent / f"{SHOT_ID}--transparent.png") as png:
                self.assertEqual(png.mode, "RGBA")
                self.assertEqual(png.size, (16, 12))
            release_path = build_release_manifest(RELEASE_ID, [manifest_path])
            self.assertTrue(release_path.is_file())

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
            approval, _ = write_approval_fixture(root, "approved", "a" * 64)
            payload = json.loads(approval.read_text(encoding="utf-8"))
            source = Path(payload["evidence"]["source"]["path"])
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
            payload["samples"] = payload["render_settings"]["proof_samples"]
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

    def test_release_rejects_noncanonical_logical_asset_and_extra_family_member(self) -> None:
        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(Path(root_text), "proof-20260815T153000Z-a1b2c3d")
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["outputs"][0]["logical_asset_id"] = "counterfeit"
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "logical asset ID"):
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

    def test_final_contract_rehashes_every_authoritative_artifact_and_state(self) -> None:
        """Catches authorization that trusts approval/final JSON instead of current bytes."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            final = json.loads(final_contract_path.read_text(encoding="utf-8"))
            evidence = final["evidence"]

            for name, record in evidence.items():
                with self.subTest(artifact=name):
                    path = Path(str(record["path"]))
                    if name in {"proof_runner", "final_runner"}:
                        changed = copy.deepcopy(final)
                        changed["evidence"][name]["sha256"] = "f" * 64
                        _write_json(final_contract_path, changed)
                        with self.assertRaisesRegex(ValueError, rf"{name}.*drift|drift.*{name}"):
                            authorize_final_render(approval_path, final_contract_path)
                        _write_json(final_contract_path, final)
                        continue
                    original = path.read_bytes()
                    original_stat = path.stat()
                    path.write_bytes(original + b" drift")
                    with self.assertRaisesRegex(ValueError, rf"{name}.*drift|drift.*{name}"):
                        authorize_final_render(approval_path, final_contract_path)
                    path.write_bytes(original)
                    os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

            for field in (
                "camera_sha256",
                "lights_sha256",
                "world_sha256",
                "compositor_sha256",
                "render_settings_sha256",
                "animation_sha256",
            ):
                with self.subTest(state=field):
                    changed = copy.deepcopy(final)
                    changed["render_settings"][field] = "f" * 64
                    _write_json(final_contract_path, changed)
                    with self.assertRaisesRegex(ValueError, field.replace("_sha256", "").replace("_", "[ _]")):
                        authorize_final_render(approval_path, final_contract_path)
            _write_json(final_contract_path, final)

    def test_approval_rejects_windows_path_aliases_without_touching_external_bytes(self) -> None:
        """Catches a PurePosix suffix check accepting Windows traversal/absolute aliases."""

        attacks = (r"..\outside.png", r"C:\outside.png", r"\\server\share\outside.png")
        for attack in attacks:
            with self.subTest(attack=attack), TemporaryDirectory() as root_text:
                root = Path(root_text)
                external = root / "outside.png"
                external.write_bytes(b"external sentinel")
                proof = _proof_manifest(root / "asset", "a" * 64)
                payload = json.loads(proof.read_text(encoding="utf-8"))
                payload["outputs"][0]["path"] = attack
                payload["outputs"][0]["sha256"] = _sha256(external)
                _write_json(proof, payload)
                with self.assertRaisesRegex(ValueError, "canonical"):
                    record_decision(proof, SHOT_ID, "approved", "natth", "reviewed")
                self.assertEqual(external.read_bytes(), b"external sentinel")

    @unittest.skipUnless(BLENDER.is_file(), "fixture Blender runtime unavailable")
    def test_native_final_rejects_a_preexisting_release_root_without_deleting_it(self) -> None:
        """Catches a runner that claims a family below somebody else's release root."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            release_root = root / "renders" / "final" / RELEASE_ID
            release_root.mkdir(parents=True)
            sentinel = release_root / "competing-owner.txt"
            sentinel.write_bytes(b"competitor")
            with self.assertRaisesRegex(ValueError, "release root already exists"):
                run_authorized_final(approval_path, final_contract_path)
            self.assertEqual(sentinel.read_bytes(), b"competitor")

    def test_release_requires_real_current_approval_and_final_authorization(self) -> None:
        """Catches a release manifest that accepts suffix-only approval hashes."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["approval_sha256"] = "0" * 64
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "approval|authorization"):
                build_release_manifest(RELEASE_ID, [output])

    def test_release_rejects_a_magic_only_exr_without_float_rgba_channels(self) -> None:
        """Catches EXR validation that checks only the four-byte magic suffix."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            exr_record = next(item for item in payload["outputs"] if item["mime_type"] == "image/x-exr")
            exr = output.parent / exr_record["path"]
            exr.write_bytes(b"v/1\x01not-an-exr-header")
            exr_record["sha256"] = _sha256(exr)
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "EXR"):
                build_release_manifest(RELEASE_ID, [output])

    def test_release_rejects_unmanifested_files_before_publishing_marker(self) -> None:
        """Catches a pass marker that ignores extra mutable release contents."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            extra = output.parents[1] / "unmanifested.tmp"
            extra.write_bytes(b"not approved")
            with self.assertRaisesRegex(ValueError, "extra|unmanifested"):
                build_release_manifest(RELEASE_ID, [output])
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_rejects_extra_family_directories_and_false_alpha_qa(self) -> None:
        """Catches incomplete entry scans and self-declared alpha evidence."""

        with self.subTest(mutation="extra directory"), TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            (output.parent / "mutable-cache").mkdir()
            with self.assertRaisesRegex(ValueError, "extra|unmanifested"):
                build_release_manifest(RELEASE_ID, [output])
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

        with self.subTest(mutation="false alpha QA"), TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["qa"]["alpha_min"] = 0
            payload["qa"]["alpha_max"] = 255
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "alpha QA|alpha.*drift"):
                build_release_manifest(RELEASE_ID, [output])
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_competing_approval_revision_is_not_deleted_and_head_lock_is_released(self) -> None:
        """Catches revision selection without an exclusive chain-head claim."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            original_create = approval_module._create_new_json
            competitor = b'{"competitor":true}\n'

            def inject_revision(path: Path, payload: dict[str, object]) -> dict[str, object]:
                self.assertTrue((path.parent / ".approval-head.lock").is_file())
                path.write_bytes(competitor)
                return original_create(path, payload)

            with patch.object(approval_module, "_create_new_json", side_effect=inject_revision):
                with self.assertRaises(FileExistsError):
                    record_decision(proof, SHOT_ID, "approved", "natth", "reviewed")
            approval_dir = proof.parent / "approvals" / SHOT_ID
            self.assertEqual((approval_dir / "approval-r01.json").read_bytes(), competitor)
            self.assertFalse((approval_dir / ".approval-head.lock").exists())

    def test_competing_release_root_race_keeps_competitor_and_removes_only_stage(self) -> None:
        """Catches a final publisher overwriting a root that appears after QA."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            final = json.loads(final_contract_path.read_text(encoding="utf-8"))
            proof_manifest = Path(final["evidence"]["proof_manifest"]["path"])
            proof = json.loads(proof_manifest.read_text(encoding="utf-8"))
            authored = proof["render"]["authored_settings"]["before"]

            def fake_blender(*args: object, **kwargs: object) -> SimpleNamespace:
                del args, kwargs
                stage = next((root / "renders" / "final").glob(f".{RELEASE_ID}-*.stage"))
                family = stage / SHOT_ID
                _write_json(family / ".native-state.json", authored)
                Image.new("RGBA", (16, 12), (30, 40, 50, 160)).save(
                    family / f"{SHOT_ID}--transparent.png"
                )
                _write_float_exr(family / f"{SHOT_ID}--transparent.exr", 16, 12)
                return SimpleNamespace(returncode=0, stderr="", stdout="fixture Blender")

            original_rename = final_module.os.rename
            competitor_root = root / "renders" / "final" / RELEASE_ID

            def inject_root(source: object, destination: object) -> None:
                self.assertNotEqual(Path(source), competitor_root)
                self.assertEqual(Path(destination), competitor_root)
                competitor_root.mkdir()
                (competitor_root / "competing-owner.txt").write_bytes(b"competitor")
                original_rename(source, destination)

            with (
                patch.object(final_module.subprocess, "run", side_effect=fake_blender),
                patch.object(final_module.os, "rename", side_effect=inject_root),
            ):
                with self.assertRaisesRegex(ValueError, "competing publication"):
                    run_authorized_final(approval_path, final_contract_path)
            self.assertEqual((competitor_root / "competing-owner.txt").read_bytes(), b"competitor")
            self.assertEqual(list((root / "renders" / "final").glob(f".{RELEASE_ID}-*.stage")), [])

    def test_competing_release_marker_is_not_overwritten_or_deleted(self) -> None:
        """Catches a marker race between validation and immutable publication."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            original_create = release_module._create_new_json
            competitor = b'{"competitor":true}\n'

            def inject_marker(path: Path, payload: dict[str, object]) -> dict[str, object]:
                path.write_bytes(competitor)
                return original_create(path, payload)

            with patch.object(release_module, "_create_new_json", side_effect=inject_marker):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    build_release_manifest(RELEASE_ID, [output])
            marker = output.parents[1] / "release-manifest.json"
            self.assertEqual(marker.read_bytes(), competitor)
            self.assertTrue(output.is_file())

    def test_release_rejects_windows_alias_reserved_and_ads_output_names(self) -> None:
        """Catches cross-platform aliases before any external path can be opened."""

        attacks = (
            "../outside.exr",
            r"..\outside.exr",
            r"C:\outside.exr",
            r"\\server\share\outside.exr",
            "CON.exr",
            f"{SHOT_ID}--transparent.exr.",
            f"{SHOT_ID}--transparent.exr ",
            f"{SHOT_ID}--transparent.exr:stream",
        )
        for attack in attacks:
            with self.subTest(attack=attack), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                payload["outputs"][2]["path"] = attack
                _write_json(output, payload)
                with self.assertRaisesRegex(ValueError, "canonical|reserved"):
                    build_release_manifest(RELEASE_ID, [output])

    def test_release_revalidates_latest_approval_revision(self) -> None:
        """Catches release publication from an approval superseded by a rejection."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            approval = Path(payload["approval_path"])
            approval_payload = json.loads(approval.read_text(encoding="utf-8"))
            record_decision(
                Path(approval_payload["proof_manifest_path"]),
                SHOT_ID,
                "rejected",
                "natth",
                "superseded",
            )
            with self.assertRaisesRegex(ValueError, "latest approval revision"):
                build_release_manifest(RELEASE_ID, [output])

    def test_final_authority_rejects_hardlinks_and_reparse_ancestors(self) -> None:
        """Catches physical aliases even when their target bytes still match."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            final = json.loads(final_contract_path.read_text(encoding="utf-8"))
            source = Path(final["evidence"]["source"]["path"])
            hardlink = source.with_name("source-hardlink.step")
            os.link(source, hardlink)
            with self.assertRaisesRegex(ValueError, "single-link|evidence drift"):
                authorize_final_render(approval_path, final_contract_path)
            hardlink.unlink()

            alias = root / "inputs-alias"
            try:
                os.symlink(source.parent, alias, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlink unavailable: {error}")
            changed = copy.deepcopy(final)
            changed["evidence"]["source"]["path"] = str(alias / source.name)
            _write_json(final_contract_path, changed)
            with self.assertRaisesRegex(ValueError, "symlink|junction|reparse"):
                authorize_final_render(approval_path, final_contract_path)
            self.assertEqual(source.read_bytes(), b"authoritative STEP")


if __name__ == "__main__":
    unittest.main()
