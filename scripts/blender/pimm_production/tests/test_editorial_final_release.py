"""Governed owner approval and native editorial final-release coverage."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from scripts.blender.pimm_production import blender_editorial_preview as preview_module
from scripts.blender.pimm_production.editorial_final_contract import (
    APPROVED_GENERATION_ID,
    RELEASE_ID,
    authorize_editorial_final_release,
    record_editorial_owner_approval,
    validate_editorial_final_contract,
    validate_editorial_owner_approval,
)
from scripts.blender.pimm_production.blender_editorial_final import (
    _validate_ephemeral_render_delta,
    publish_editorial_native_release,
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

    def tearDown(self) -> None:
        self.preview.tearDown()

    def _approval(self) -> Path:
        return record_editorial_owner_approval(
            self.asset_root,
            self.accepted.generation_id,
            owner="natth",
            notes="Approved all four exact editorial previews for native final rendering",
        )

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
        staging = self.asset_root / "renders" / "final" / "editorial-concepts-v1" / f".{RELEASE_ID}.pending-fixture"
        staging.mkdir(parents=True)
        contract = validate_editorial_final_contract(contract_path, self.asset_root)
        shots = []
        for index, approved in enumerate(contract["shots"]):
            width, height = (3840, 2160) if index < 3 else (2400, 3000)
            png = staging / f"{approved['shot_id']}.png"
            exr = staging / f"{approved['shot_id']}.exr"
            Image.new("RGB", (width, height), (80 + index, 90, 100)).save(png)
            exr.write_bytes(f"EXR-{index}".encode())
            shots.append({
                "shot_id": approved["shot_id"], "png": png.name, "png_sha256": sha256_file(png),
                "exr": exr.name, "exr_sha256": sha256_file(exr), "dimensions": [width, height],
            })
        Image.new("RGB", (2560, 1800), (30, 40, 50)).save(staging / "sheet-editorial-finals.png")
        (staging / "native-report.json").write_text(json.dumps({
            "release_id": RELEASE_ID,
            "contract_path": str(contract_path),
            "contract_sha256": sha256_file(contract_path),
            "shots": shots,
            "contact_sheet": {
                "path": "sheet-editorial-finals.png",
                "sha256": sha256_file(staging / "sheet-editorial-finals.png"),
                "dimensions": [2560, 1800],
            },
        }), encoding="utf-8")
        disposition = {
            "decision": "accept", "reviewer": "Codex actual-pixel reviewer",
            "reviewed_at": "2026-08-30T13:00:00Z",
            "contact_sheet": {"sha256": sha256_file(staging / "sheet-editorial-finals.png"), "pixel_review": "pass"},
            "shots": [
                {"shot_id": shot["shot_id"], "png_sha256": shot["png_sha256"],
                 "exr_sha256": shot["exr_sha256"], "pixel_review": "pass",
                 "grounding": "pass", "clipping": "pass", "props": "pass",
                 "exposure": "pass", "detail": "pass", "decals": "pass", "notes": "reviewed"}
                for shot in shots
            ],
        }
        disposition["shots"][0]["pixel_review"] = "fail"
        with self.assertRaisesRegex(ValueError, "pixel|pass"):
            publish_editorial_native_release(staging, contract_path, disposition)
        self.assertFalse((staging.parent / RELEASE_ID).exists())

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


if __name__ == "__main__":
    unittest.main()
