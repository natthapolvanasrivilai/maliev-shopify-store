from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.blender.pimm_production import blender_fixture_bento_final as worker


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class FixtureBentoFinalApprovalTests(unittest.TestCase):
    def create_authority(self, root: Path) -> Path:
        proof_dir = root / "renders" / "proofs" / "approved-fixture"
        proof_dir.mkdir(parents=True)
        scene = proof_dir / "scene.blend"
        video = proof_dir / "review.mp4"
        scene.write_bytes(b"approved scene")
        video.write_bytes(b"approved video")
        contract = {
            "resolution": [400, 550],
            "aspect_ratio": "8:11",
            "fps": 24,
            "frames": 912,
            "duration_seconds": 38.0,
            "samples": 16,
            "camera": "CAM_STOREFRONT",
            "camera_lens_mm": 105.0,
            "camera_sensor_fit": "VERTICAL",
            "camera_shift_y": -0.18000000715255737,
        }
        proof = {
            "schema": worker.EXPECTED_PROOF_SCHEMA,
            "scene": {"path": str(scene), "sha256": digest(scene)},
            "contract": contract,
        }
        proof_path = proof_dir / "proof.json"
        proof_path.write_text(json.dumps(proof), encoding="utf-8")
        approval = {
            "schema": worker.EXPECTED_APPROVAL_SCHEMA,
            "decision": "approved",
            "owner": "store owner",
            "proof_manifest_path": str(proof_path),
            "proof_manifest_sha256": digest(proof_path),
            "proof_video_path": str(video),
            "proof_video_sha256": digest(video),
            "scene_path": str(scene),
            "scene_sha256": digest(scene),
            "final_contract": {
                **{field: contract[field] for field in (
                    "aspect_ratio", "fps", "frames", "duration_seconds", "camera",
                    "camera_lens_mm", "camera_sensor_fit", "camera_shift_y"
                )},
                "resolution": [800, 1100],
                "samples": 48,
            },
        }
        approval_path = root / "approval.json"
        approval_path.write_text(json.dumps(approval), encoding="utf-8")
        return approval_path

    def test_accepts_exact_approved_camera_timing_and_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approval_path = self.create_authority(root)
            with patch.object(worker, "ASSET_ROOT", root), patch.object(worker, "APPROVAL", approval_path):
                approval, proof = worker.approved_contract()
            self.assertEqual(approval["final_contract"]["resolution"], [800, 1100])
            self.assertEqual(proof["contract"]["frames"], 912)

    def test_rejects_camera_drift_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            approval_path = self.create_authority(root)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["final_contract"]["camera_shift_y"] = 0.0
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            with patch.object(worker, "ASSET_ROOT", root), patch.object(worker, "APPROVAL", approval_path):
                with self.assertRaisesRegex(ValueError, "camera or timing"):
                    worker.approved_contract()


if __name__ == "__main__":
    unittest.main()
