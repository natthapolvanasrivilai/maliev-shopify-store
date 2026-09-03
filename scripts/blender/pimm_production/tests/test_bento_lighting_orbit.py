"""Camera-only orbit and proof-boundary regressions."""
import math
from pathlib import Path
import unittest

from scripts.blender.pimm_production.blender_bento_lighting_orbit_proof import (
    AMPLITUDE_DEGREES, FPS, FRAMES, orbit_angle,
)


class BentoLightingOrbitTests(unittest.TestCase):
    def test_slow_eight_second_camera_cycle_at_24fps(self):
        self.assertEqual(FPS, 24)
        self.assertEqual(FRAMES / FPS, 8)
        self.assertEqual(AMPLITUDE_DEGREES, 3)

    def test_orbit_starts_center_reverses_gently_and_closes_seamlessly(self):
        self.assertAlmostEqual(orbit_angle(1), 0)
        self.assertAlmostEqual(orbit_angle(49), math.radians(3))
        self.assertAlmostEqual(orbit_angle(97), 0)
        self.assertAlmostEqual(orbit_angle(145), math.radians(-3))
        self.assertAlmostEqual(orbit_angle(FRAMES+1), orbit_angle(1))
        for frame in range(1, FRAMES+1):
            self.assertLessEqual(abs(orbit_angle(frame)), math.radians(3))
            self.assertLess(abs(orbit_angle(frame+1)-orbit_angle(frame)), math.radians(.1))

    def test_proof_worker_never_modifies_published_machine_or_releases_finals(self):
        source = (Path(__file__).parents[1] / 'blender_bento_lighting_orbit_proof.py').read_text()
        self.assertIn('source = approved_contract(shot)', source)
        self.assertIn("approval='pending'", source)
        self.assertIn('scene.render.resolution_percentage = 25', source)
        self.assertIn('scene.cycles.samples = 32', source)
        self.assertIn("assert all(not obj.animation_data", source)
        self.assertIn("camera.keyframe_insert(data_path='location'", source)
        self.assertIn("if animate and shot != 'controls'", source)
        self.assertNotIn('renders/final', source)
        self.assertNotIn('material_slots', source)
        self.assertNotIn('make_local', source)

    def test_review_encoding_retains_24fps_duration_and_static_reduced_motion(self):
        from scripts.blender.pimm_production.package_bento_orbit_review import frame_durations
        self.assertEqual(sum(frame_durations()), 8000)
        self.assertEqual(set(frame_durations()), {41, 42})
        source = (Path(__file__).parents[1] / 'package_bento_orbit_review.py').read_text()
        self.assertIn("prefers-reduced-motion: reduce", source)
        self.assertIn("preference.addEventListener('change',sync)", source)
        self.assertIn('lossless=True', source)
        self.assertNotIn('.resize(', source)


if __name__ == '__main__':
    unittest.main()
