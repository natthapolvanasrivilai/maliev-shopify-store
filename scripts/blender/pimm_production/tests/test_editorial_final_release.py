"""Governed owner approval and native editorial final-release coverage."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from scripts.blender.pimm_production import blender_editorial_preview as preview_module
from scripts.blender.pimm_production import editorial_final_contract as contract_module
from scripts.blender.pimm_production.editorial_final_contract import (
    APPROVED_GENERATION_ID,
    RELEASE_ID,
    authorize_editorial_final_release,
    record_editorial_owner_approval,
    validate_editorial_final_contract,
    validate_editorial_owner_approval,
)
from scripts.blender.pimm_production.blender_editorial_final import (
    _controller_authority_snapshot,
    _load_worker_contract,
    _validate_ephemeral_render_delta,
    publish_editorial_native_release,
    reject_editorial_native_release,
)
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.tests import test_editorial_preview as _preview_tests


class EditorialFinalReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = _preview_tests.EditorialPreviewTests("runTest")
        self.preview.setUp()
        self.asset_root = self.preview.asset_root
        pending = self.preview._render()
        self.accepted = preview_module.accept_editorial_preview_generation(
            self.asset_root,
            pending.generation_id,
            self.preview._visual_decision(pending),
        )
        self._original_generation = contract_module.APPROVED_GENERATION_ID
        self._original_hashes = dict(contract_module.EXPECTED_ACCEPTED_HASHES)
        accepted = preview_module.validate_accepted_editorial_generation(
            self.asset_root, self.accepted.generation_id
        )
        contract_module.APPROVED_GENERATION_ID = self.accepted.generation_id
        contract_module.EXPECTED_ACCEPTED_HASHES = {
            field: accepted[field] for field in contract_module.EXPECTED_ACCEPTED_HASHES
        }

    def tearDown(self) -> None:
        contract_module.APPROVED_GENERATION_ID = self._original_generation
        contract_module.EXPECTED_ACCEPTED_HASHES = self._original_hashes
        self.preview.tearDown()

    def _approval(self) -> Path:
        return record_editorial_owner_approval(
            self.asset_root,
            self.accepted.generation_id,
            owner="natth",
            notes="Approved all four exact editorial previews for native final rendering",
        )

    def _staging_fixture(self, contract_path: Path) -> tuple[Path, dict[str, object]]:
        contract = validate_editorial_final_contract(contract_path, self.asset_root)
        staging = (
            self.asset_root / "renders" / "final" / "editorial-concepts-v1"
            / f".{RELEASE_ID}.pending-fixture"
        )
        staging.mkdir(parents=True)
        shots = []
        for index, approved in enumerate(contract["shots"]):
            width, height = (3840, 2160) if index < 3 else (2400, 3000)
            png = staging / f"{approved['shot_id']}.png"
            exr = staging / f"{approved['shot_id']}.exr"
            Image.new("RGB", (width, height), (80 + index, 90, 100)).save(png)
            exr.write_bytes(b"\x76\x2f\x31\x01" + f"EXR-{index}".encode())
            authority = approved["authority"]
            shots.append({
                "shot_id": approved["shot_id"], "process_id": 1000 + index,
                "png": png.name, "png_sha256": sha256_file(png),
                "exr": exr.name, "exr_sha256": sha256_file(exr), "dimensions": [width, height],
                "samples": 256, "denoise": True, "film_transparent": False,
                "authority_status": "pass", "scene_sha256": authority["scene_sha256"],
                "contract_sha256": authority["contract_sha256"],
                "completion_marker_sha256": authority["completion_marker_sha256"],
                "exr_validation": {"magic": "762F3101", "dimensions": [width, height],
                    "channels": ["R", "G", "B"], "authority": "blender-render-result"},
            })
        sheet = staging / "sheet-editorial-finals.png"
        Image.new("RGB", (2560, 1800), (30, 40, 50)).save(sheet)
        report = {
            "schema": "maliev.pimm-editorial-native-report/v1", "status": "pending-actual-pixel-review",
            "release_id": RELEASE_ID, "generation_id": contract["generation_id"],
            "contract_path": str(contract_path), "contract_sha256": sha256_file(contract_path),
            "fresh_blender_processes": 4, "samples": 256, "denoise": True,
            "shots": shots,
            "contact_sheet": {"path": sheet.name, "sha256": sha256_file(sheet), "dimensions": [2560, 1800]},
        }
        (staging / "native-report.json").write_text(json.dumps(report), encoding="utf-8")
        disposition = {
            "decision": "accept", "reviewer": "Codex actual-pixel reviewer",
            "reviewed_at": "2026-08-30T13:00:00Z",
            "contact_sheet": {"sha256": report["contact_sheet"]["sha256"], "pixel_review": "pass"},
            "shots": [
                {"shot_id": shot["shot_id"], "png_sha256": shot["png_sha256"],
                 "exr_sha256": shot["exr_sha256"], "pixel_review": "pass",
                 "grounding": "pass", "clipping": "pass", "props": "pass",
                 "exposure": "pass", "detail": "pass", "decals": "pass", "notes": "reviewed"}
                for shot in shots
            ],
        }
        return staging, disposition

    def test_owner_approval_binds_every_exact_accepted_image_and_authority(self) -> None:
        """Catches approval that binds only a generation label or contact sheet."""

        approval_path = self._approval()
        approval = validate_editorial_owner_approval(approval_path, self.asset_root)

        self.assertEqual(approval["owner"], "natth")
        self.assertEqual(approval["decision"], "approved")
        self.assertEqual(len(approval["shots"]), 4)
        self.assertEqual(
            {shot["output_sha256"] for shot in approval["shots"]},
            {
                shot["output_sha256"]
                for shot in preview_module.validate_accepted_editorial_generation(
                    self.asset_root, self.accepted.generation_id
                )["shots"]
            },
        )
        self.assertTrue(all(shot["authority"] for shot in approval["shots"]))

    def test_approval_requires_owner_notes_and_exclusive_revision(self) -> None:
        """Catches anonymous, context-free, or replayed approval authority."""

        for owner, notes in (("", "approved"), ("natth", "")):
            with self.subTest(owner=owner, notes=notes):
                with self.assertRaisesRegex(ValueError, "owner|notes"):
                    record_editorial_owner_approval(
                        self.asset_root,
                        self.accepted.generation_id,
                        owner=owner,
                        notes=notes,
                    )
        approval_path = self._approval()
        with self.assertRaisesRegex(FileExistsError, "approval-r01"):
            self._approval()
        self.assertTrue(approval_path.is_file())

    def test_r01_rejects_every_other_accepted_generation(self) -> None:
        """Catches release r01 authority being reused for a later accepted generation."""

        pending = self.preview._render()
        another = preview_module.accept_editorial_preview_generation(
            self.asset_root, pending.generation_id, self.preview._visual_decision(pending)
        )
        with self.assertRaisesRegex(ValueError, "exact|generation"):
            record_editorial_owner_approval(
                self.asset_root, another.generation_id, owner="natth", notes="wrong generation"
            )

    def test_approval_rejects_any_accepted_generation_or_current_authority_drift(self) -> None:
        """Catches final authorization after preview bytes or protected scene bytes change."""

        approval_path = self._approval()
        approved = validate_editorial_owner_approval(approval_path, self.asset_root)
        shot_path = Path(approved["shots"][0]["output_path"])
        original = shot_path.read_bytes()
        shot_path.write_bytes(b"drift")
        try:
            with self.assertRaisesRegex(ValueError, "PNG|hash|drift"):
                validate_editorial_owner_approval(approval_path, self.asset_root)
        finally:
            shot_path.write_bytes(original)

        scene_path = self.preview.paths[next(iter(self.preview.paths))]["scene"]
        original_scene = scene_path.read_bytes()
        scene_path.write_bytes(b"scene drift")
        try:
            with self.assertRaisesRegex(ValueError, "authority|scene|drift"):
                validate_editorial_owner_approval(approval_path, self.asset_root)
        finally:
            scene_path.write_bytes(original_scene)

    def test_final_contract_is_preview_immutable_and_allows_only_native_ephemeral_deltas(self) -> None:
        """Catches campaign mutation or camera/light/world changes disguised as final settings."""

        approval_path = self._approval()
        contract_path = authorize_editorial_final_release(
            approval_path,
            self.asset_root,
            RELEASE_ID,
        )
        contract = validate_editorial_final_contract(contract_path, self.asset_root)

        self.assertEqual(contract["samples"], 256)
        self.assertEqual(contract["landscape_dimensions"], [3840, 2160])
        self.assertEqual(contract["portrait_dimensions"], [2400, 3000])
        self.assertEqual(contract["allowed_scene_mutations"], [
            "resolution_x", "resolution_y", "resolution_percentage", "cycles.samples",
            "cycles.use_denoising", "render.filepath", "image_settings.file_format",
            "image_settings.color_mode", "image_settings.color_depth",
        ])
        baseline = {
            "camera": "A", "lights": "B", "world": "C", "compositor": "D",
            "resolution_x": 1280, "resolution_y": 720, "resolution_percentage": 100,
            "cycles.samples": 32, "cycles.use_denoising": True,
            "render.filepath": "preview.png", "image_settings.file_format": "PNG",
            "image_settings.color_mode": "RGB", "image_settings.color_depth": "8",
        }
        final = {**baseline, "resolution_x": 3840, "resolution_y": 2160,
                 "cycles.samples": 256, "render.filepath": "final.png"}
        _validate_ephemeral_render_delta(baseline, final, contract)
        for field in ("camera", "lights", "world", "compositor"):
            with self.subTest(field=field):
                changed = {**final, field: "drift"}
                with self.assertRaisesRegex(ValueError, field):
                    _validate_ephemeral_render_delta(baseline, changed, contract)

    def test_contract_rejects_replay_extra_fields_and_superseded_approval(self) -> None:
        """Catches contract replay, loose schemas, or approval-head substitution."""

        approval_path = self._approval()
        contract_path = authorize_editorial_final_release(
            approval_path, self.asset_root, RELEASE_ID
        )
        with self.assertRaisesRegex(FileExistsError, "campaign-contract-r01"):
            authorize_editorial_final_release(approval_path, self.asset_root, RELEASE_ID)
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
        payload["unexpected"] = True
        contract_path.chmod(0o644)
        contract_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fields"):
            validate_editorial_final_contract(contract_path, self.asset_root)

    def test_atomic_publication_requires_complete_hash_bound_actual_pixel_disposition(self) -> None:
        """Catches partial visual acceptance, missing archive pairs, or marker-first release."""

        approval_path = self._approval()
        contract_path = authorize_editorial_final_release(
            approval_path, self.asset_root, RELEASE_ID
        )
        staging, disposition = self._staging_fixture(contract_path)
        disposition["shots"][0]["pixel_review"] = "fail"
        with self.assertRaisesRegex(ValueError, "pixel|pass"):
            publish_editorial_native_release(staging, contract_path, disposition)
        self.assertFalse((staging.parent / RELEASE_ID).exists())

    def test_staging_rejects_invalid_exr_magic_and_missing_native_evidence(self) -> None:
        """Catches arbitrary bytes or incomplete claims being accepted as native finals."""

        contract_path = authorize_editorial_final_release(
            self._approval(), self.asset_root, RELEASE_ID
        )
        staging, disposition = self._staging_fixture(contract_path)
        report_path = staging / "native-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        exr = staging / report["shots"][0]["exr"]
        exr.write_bytes(b"not an exr")
        report["shots"][0]["exr_sha256"] = sha256_file(exr)
        disposition["shots"][0]["exr_sha256"] = sha256_file(exr)
        report_path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "EXR|exr"):
            publish_editorial_native_release(staging, contract_path, disposition)

        exr.write_bytes(b"\x76\x2f\x31\x01fixture")
        report["shots"][0]["exr_sha256"] = sha256_file(exr)
        report["shots"][0].pop("authority_status")
        disposition["shots"][0]["exr_sha256"] = sha256_file(exr)
        report_path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "authority|evidence"):
            publish_editorial_native_release(staging, contract_path, disposition)

    def test_reject_flow_is_hash_bound_exclusive_and_never_publishes(self) -> None:
        """Catches visual rejection being deleted, overwritten, or moved into final release."""

        contract_path = authorize_editorial_final_release(
            self._approval(), self.asset_root, RELEASE_ID
        )
        staging, disposition = self._staging_fixture(contract_path)
        disposition["decision"] = "reject"
        disposition["shots"][0]["pixel_review"] = "fail"
        disposition["shots"][0]["notes"] = "Rejected at actual pixels"
        rejected = reject_editorial_native_release(staging, contract_path, disposition)
        self.assertTrue((rejected / "rejected-disposition.json").is_file())
        self.assertFalse((staging.parent / RELEASE_ID).exists())
        with self.assertRaisesRegex(ValueError, "staging|claim|missing"):
            reject_editorial_native_release(staging, contract_path, disposition)

    def test_accept_collision_preserves_reviewed_staging_without_release_marker(self) -> None:
        """Catches target races leaving a marker-certified hidden tree or deleting evidence."""

        contract_path = authorize_editorial_final_release(
            self._approval(), self.asset_root, RELEASE_ID
        )
        staging, disposition = self._staging_fixture(contract_path)
        target = staging.parent / RELEASE_ID
        target.mkdir()
        with self.assertRaisesRegex(ValueError, "competing|replay|collision"):
            publish_editorial_native_release(staging, contract_path, disposition)
        self.assertFalse(staging.exists())
        preserved = list(
            (self.asset_root / "renders" / "final-failures" / "editorial-concepts-v1").glob(
                f"{RELEASE_ID}-publication-*"
            )
        )
        self.assertEqual(len(preserved), 1)
        self.assertFalse((preserved[0] / "release-manifest.json").exists())

    def test_blender_worker_script_bootstraps_outside_package_mode(self) -> None:
        """Catches Blender executing the checked-in worker with unresolved relative imports."""

        script = Path(__file__).parents[1] / "blender_editorial_final.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--render-shot", completed.stdout)

    def test_blender_worker_import_does_not_require_pillow(self) -> None:
        """Catches fresh Blender exiting before render because its Python lacks Pillow."""

        script = Path(__file__).parents[1] / "blender_editorial_final.py"
        probe = (
            "import builtins,runpy,sys;"
            "real=builtins.__import__;"
            "builtins.__import__=lambda name,*a,**k: "
            "(_ for _ in ()).throw(ModuleNotFoundError('blocked Pillow')) "
            "if name=='PIL' or name.startswith('PIL.') else real(name,*a,**k);"
            f"sys.argv=[{str(script)!r},'--help'];"
            f"runpy.run_path({str(script)!r},run_name='__main__')"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, check=False
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_fresh_blender_worker_uses_hash_bound_headless_contract_validation(self) -> None:
        """Catches worker re-entering Pillow-dependent accepted-image validation."""

        approval_path = self._approval()
        contract_path = authorize_editorial_final_release(
            approval_path, self.asset_root, RELEASE_ID
        )
        expected_sha = sha256_file(contract_path)
        held = _controller_authority_snapshot(contract_path, self.asset_root)
        bindings = {key: value for key, value in held.items() if key != "contract_sha256"}
        with patch(
            "scripts.blender.pimm_production.blender_editorial_final.validate_editorial_final_contract",
            side_effect=ModuleNotFoundError("Pillow unavailable in Blender"),
        ):
            contract = _load_worker_contract(
                contract_path, self.asset_root, expected_sha, bindings
            )
        self.assertEqual(contract["release_id"], RELEASE_ID)
        self.assertEqual(contract["samples"], 256)
        drifted = {**bindings, "manifest_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "binding drift"):
            _load_worker_contract(contract_path, self.asset_root, expected_sha, drifted)


if __name__ == "__main__":
    unittest.main()
