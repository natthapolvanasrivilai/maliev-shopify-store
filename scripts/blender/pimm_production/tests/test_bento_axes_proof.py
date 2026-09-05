"""Two-axis coverage, camera tilt timing and native-source safety contracts."""
import math
from pathlib import Path
import unittest
from scripts.blender.pimm_production.blender_bento_axes_proof import angles, tilt, selected_frames, ELEVATIONS


class CameraAxesProofTests(unittest.TestCase):
    def test_two_axes_cover_all_unique_views(self):
        poses = [angles(i) for i in range(1,841)]
        self.assertEqual(len(set(poses)),840)
        self.assertEqual(ELEVATIONS,(-6,-4,-2,0,2,4,6))
        self.assertEqual(angles(361),(0,0))
        self.assertAlmostEqual(math.degrees(angles(840)[0]),357)
        self.assertAlmostEqual(math.degrees(angles(840)[1]),6)

    def test_tilt_is_smooth_bounded_and_seamless(self):
        self.assertAlmostEqual(tilt(1),tilt(193))
        self.assertAlmostEqual(math.degrees(tilt(49)),3)
        self.assertAlmostEqual(math.degrees(tilt(145)),-3)
        self.assertTrue(all(abs(math.degrees(tilt(i))) <= 3 + 1e-12 for i in range(1,194)))

    def test_invalid_indices_fail_closed(self):
        for value in (0,-1,841,1.5):
            with self.assertRaises(ValueError): angles(value)
        for value in (0,194,2.5):
            with self.assertRaises(ValueError): tilt(value)
        for selection in ([],[1,1],[0],[841]):
            with self.assertRaises(ValueError): selected_frames('configuration',selection)
        self.assertEqual(len(selected_frames('configuration',None)),840)
        self.assertEqual(len(selected_frames('tooling',None)),192)

    def test_authority_and_native_intent_are_retained(self):
        source = (Path(__file__).parents[1]/'blender_bento_axes_proof.py').read_text()
        for guard in ("approval='pending'","== [scene.camera]","scene.render.resolution_percentage = 25",
                      "source['native_size']","checked_file(scene_path, contract['scene_sha256'])",
                      "checked_file(Path(__file__), contract['script_sha256'])","plate.ray_cast"):
            self.assertIn(guard,source)
        for forbidden in ('make_local','material_slots','renders/final','objects.remove'):
            self.assertNotIn(forbidden,source)


if __name__ == '__main__':
    unittest.main()
