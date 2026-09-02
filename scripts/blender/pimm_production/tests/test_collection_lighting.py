import unittest
from pathlib import Path

from scripts.blender.pimm_production import blender_collection_card_render as collection
from scripts.blender.pimm_production.finalize_collection_lighting import validate


class CollectionLightingTests(unittest.TestCase):
    def test_native_lighting_ramp_changes_emitters_not_image_exposure(self):
        self.assertTrue(hasattr(collection, 'lighting_levels'), 'native lighting transition is missing')
        frames = collection.lighting_levels()
        self.assertEqual(len(frames), 12)
        self.assertTrue(all(value == 1 for value in frames[0].values()))
        self.assertLess(frames[-1]['KEY_SOFTBOX'], .1)
        self.assertGreater(frames[-1]['REFLECTION_CARD_LEFT'], frames[-1]['KEY_SOFTBOX'])
        for name in frames[0]:
            values = [frame[name] for frame in frames]
            self.assertEqual(values, sorted(values, reverse=True))
            self.assertEqual(len(set(values)), 12)
            self.assertGreater(values[-1], 0)

    def test_proof_and_wrong_native_contracts_are_rejected_before_encoding(self):
        source = {'release_id': collection.LIGHTING_RELEASE, 'machine': '30G',
                  'proof': False, 'resolution_percentage': 100, 'fps': 24,
                  'frame_count': 12, 'frames': [{}] * 12, 'width': 1440,
                  'height': 1920, 'samples': 128,
                  'provenance': {'master_sha256': collection.MASTER_HASHES['30G']},
                  'exposure': -.15, 'camera_scale': 1.24}
        for field, invalid in [('proof', True), ('resolution_percentage', 50),
                               ('fps', 12), ('frame_count', 3), ('width', 720),
                               ('samples', 64), ('exposure', -2), ('camera_scale', 1.5),
                               ('provenance', {'master_sha256': 'untrusted'})]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate({**source, field: invalid}, '30g', Path('.'))


if __name__ == '__main__':
    unittest.main()
