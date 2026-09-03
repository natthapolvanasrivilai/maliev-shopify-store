"""Proof-only 360 view coverage and published-product guardrails."""
import math
from pathlib import Path
import unittest

from scripts.blender.pimm_production.blender_bento_spin_proof import FRAMES, FPS, angle


class SpinProofTests(unittest.TestCase):
    def test_every_angle_is_unique_at_three_degree_intervals(self):
        self.assertEqual(FRAMES, 120)
        self.assertEqual(FPS, 24)
        values = [angle(frame) for frame in range(1, FRAMES + 1)]
        self.assertEqual(len(set(values)), FRAMES)
        self.assertEqual(values[0], 0)
        self.assertAlmostEqual(math.degrees(values[-1]), 357)
        for first, second in zip(values, values[1:]):
            self.assertAlmostEqual(math.degrees(second-first), 3)

    def test_matching_endpoint_is_not_an_extra_delivered_frame(self):
        self.assertAlmostEqual(angle(FRAMES + 1), math.tau)
        self.assertAlmostEqual(math.sin(angle(FRAMES + 1)), math.sin(angle(1)))
        self.assertAlmostEqual(math.cos(angle(FRAMES + 1)), math.cos(angle(1)))

    def test_invalid_frame_is_rejected(self):
        for value in (0, -1, 122):
            with self.assertRaises(ValueError):
                angle(value)

    def test_worker_preserves_approved_source_and_only_animates_camera(self):
        source = (Path(__file__).parents[1] / 'blender_bento_spin_proof.py').read_text()
        self.assertIn("source = detail_contract('configuration')", source)
        self.assertIn("approval='pending'", source)
        self.assertIn("== [scene.camera]", source)
        self.assertIn('scene.render.resolution_percentage = 25', source)
        self.assertIn('camera.data.ortho_scale == original_scale', source)
        self.assertNotIn('renders/final', source)
        self.assertNotIn('material_slots', source)
        self.assertNotIn('make_local', source)

    def test_proof_resume_requires_immutable_scene_script_and_source(self):
        source = (Path(__file__).parents[1] / 'blender_bento_spin_proof.py').read_text()
        for check in ("checked_file(scene_path, contract['scene_sha256'])",
                      "checked_file(Path(__file__), contract['script_sha256'])",
                      "checked_file(APPROVAL, contract['source_approval_sha256'])",
                      "checked_file(path, records[frame]['sha256'])"):
            self.assertIn(check, source)


if __name__ == '__main__':
    unittest.main()
