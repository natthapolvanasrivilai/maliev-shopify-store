import unittest
from scripts.blender.pimm_production.package_bento_final_delivery import validate_manifest, SIZES, DELIVERY_SIZES


class FinalDeliveryTests(unittest.TestCase):
    def fixture(self, shot):
        return {'shot': shot, 'size': SIZES[shot], 'resolution_percentage': 100,
                'authority': {'review': 'approved'}, 'samples': 48 if shot == 'capacity' else 128,
                'persistent_data': False,
                'frames': [{'index': n} for n in range(1, 841 if shot == 'configuration' else 193)]}

    def test_all_three_complete_native_manifests_pass(self):
        for shot in SIZES:
            validate_manifest(self.fixture(shot), shot, {'review': 'approved'})

    def test_missing_duplicated_or_reordered_frames_are_rejected(self):
        for shot in SIZES:
            for action in ('missing', 'duplicate', 'reordered'):
                record = self.fixture(shot)
                if action == 'missing': record['frames'].pop()
                elif action == 'duplicate': record['frames'][-1] = record['frames'][0]
                else: record['frames'].reverse()
                with self.subTest(shot=shot, action=action), self.assertRaises(ValueError):
                    validate_manifest(record, shot, {'review': 'approved'})

    def test_quality_authority_and_flicker_regressions_fail_closed(self):
        for key, value in [('size', [400, 550]), ('samples', 24), ('resolution_percentage', 25),
                           ('authority', {}), ('persistent_data', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_manifest({**self.fixture('capacity'), key: value}, 'capacity', {'review': 'approved'})

    def test_delivery_never_upscales_or_changes_aspect_ratio(self):
        for shot, target in DELIVERY_SIZES.items():
            source = SIZES[shot]
            self.assertLessEqual(target[0], source[0])
            self.assertLessEqual(target[1], source[1])
            self.assertEqual(target[0] * source[1], target[1] * source[0])


if __name__ == '__main__':
    unittest.main()
