"""Catch stepped, incomplete, or incorrectly timed physical turntable motion."""
import json
from pathlib import Path
import tempfile
import unittest


class CollectionMotionTests(unittest.TestCase):
    def test_finalizer_rejects_low_resolution_or_depth_blur_before_encoding(self):
        from scripts.blender.pimm_production.finalize_collection_motion import publish, RELEASE, MASTER_HASHES
        for width, height, depth_of_field in [(720, 960, False), (1440, 1920, True)]:
            with self.subTest(width=width, depth_of_field=depth_of_field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / f'{RELEASE}-30g.json').write_text(json.dumps({
                    'release_id': RELEASE, 'machine': '30G', 'fps': 24, 'frame_count': 72,
                    'provenance': {'master_sha256': MASTER_HASHES['30G']}, 'frames': [{}] * 72,
                    'width': width, 'height': height, 'depth_of_field': depth_of_field,
                }))
                with self.assertRaisesRegex(ValueError, 'native high resolution'):
                    publish(root, root)
                self.assertEqual(list(root.glob('*.mp4')), [])

    def test_motion_is_native_double_resolution_and_all_in_focus(self):
        from scripts.blender.pimm_production import blender_collection_card_render as renderer
        self.assertEqual(getattr(renderer, 'MOTION_DIMENSIONS', None), (1440, 1920))
        self.assertEqual(renderer.MOTION_RELEASE, 'maliev-pimm-collection-motion-20260902-r02')
        source = Path(renderer.__file__).read_text()
        self.assertIn('scene.camera.data.dof.use_dof = False', source)

    def test_finalizer_rejects_untrusted_master_before_encoding(self):
        from scripts.blender.pimm_production.finalize_collection_motion import publish, RELEASE
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / f'{RELEASE}-30g.json').write_text(json.dumps({
                'release_id': RELEASE, 'machine': '30G', 'fps': 24, 'frame_count': 72,
                'provenance': {'master_sha256': 'wrong'}, 'frames': [{}] * 72,
            }))
            with self.assertRaisesRegex(ValueError, 'master'):
                publish(root, root)
            self.assertEqual(list(root.glob('*.mp4')), [])

    def test_motion_has_intermediate_angles_and_returns_to_front(self):
        from scripts.blender.pimm_production import blender_collection_card_render as still
        self.assertTrue(hasattr(still, "motion_angles"), "continuous motion is missing")
        angles = still.motion_angles()
        self.assertEqual(len(angles), 72)
        self.assertEqual(angles[0], 0.0)
        self.assertEqual(angles[-1], 0.0)
        self.assertAlmostEqual(min(angles), -12.0)
        self.assertAlmostEqual(max(angles), 12.0)
        self.assertGreater(len(set(round(a, 5) for a in angles)), 45)
        self.assertLess(max(abs(b-a) for a, b in zip(angles, angles[1:])), 1.7)


if __name__ == "__main__":
    unittest.main()
