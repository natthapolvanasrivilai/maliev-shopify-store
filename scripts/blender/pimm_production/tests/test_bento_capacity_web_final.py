import unittest
from scripts.blender.pimm_production.blender_bento_capacity_web_final import validate_approval


class CapacityWebApprovalTests(unittest.TestCase):
    def setUp(self):
        self.approval = {'decision': 'approved', 'review_generation': 'bento-20260903-r24-web-benchmark'}
        self.entry = {'scene_sha256': 'scene', 'contract_sha256': 'contract'}
        self.benchmark = {'size': [800, 1100], 'samples': 48, 'persistent_data': False,
                          'source_scene_sha256': 'scene', 'source_contract_sha256': 'contract'}

    def test_exact_approved_quality_passes(self):
        validate_approval(self.approval, self.benchmark, self.entry)

    def test_changed_settings_and_sources_fail_closed(self):
        for key, value in [('size', [400, 550]), ('samples', 24), ('persistent_data', True),
                           ('source_scene_sha256', 'changed'), ('source_contract_sha256', 'changed')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_approval(self.approval, {**self.benchmark, key: value}, self.entry)

    def test_pending_or_wrong_review_is_rejected(self):
        for key, value in [('decision', 'pending'), ('review_generation', 'other')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_approval({**self.approval, key: value}, self.benchmark, self.entry)


if __name__ == '__main__':
    unittest.main()
