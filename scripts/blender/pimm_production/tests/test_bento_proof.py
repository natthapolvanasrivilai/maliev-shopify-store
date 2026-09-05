"""Guard full-tile composition intent without requiring a Blender process."""

import unittest
import tempfile
from pathlib import Path

from scripts.blender.pimm_production.blender_bento_proof import SHOTS
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file


class BentoProofTests(unittest.TestCase):
    def test_changed_or_missing_dependency_blocks_final_render(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scene.blend'
            path.write_bytes(b'approved scene')
            digest = sha256_file(path)
            self.assertEqual(checked_file(path, digest), path)
            path.write_bytes(b'changed camera')
            with self.assertRaises(ValueError):
                checked_file(path, digest)
            with self.assertRaises(ValueError):
                checked_file(Path(folder) / 'missing.blend', digest)

    def test_native_worker_reopens_approved_scene_without_rebuilding_it(self):
        source = (Path(__file__).parents[1] / 'blender_bento_final.py').read_text()
        self.assertIn("bpy.ops.wm.open_mainfile(filepath=contract['scene_path'])", source)
        self.assertIn('resolution_percentage == 100', source)
        self.assertNotIn('read_factory_settings', source)
        self.assertNotIn('save_as_mainfile', source)
        self.assertNotIn('camera.location', source)

    def test_four_shots_have_bounded_subject_and_reserved_copy_space(self):
        self.assertEqual(set(SHOTS), {'capacity', 'controls', 'tooling', 'configuration'})
        for name, shot in SHOTS.items():
            with self.subTest(shot=name):
                self.assertTrue(all(size >= 1200 for size in shot['size']))
                x0, y0, x1, y1 = shot['rect']
                self.assertTrue(0 <= x0 < x1 <= 1)
                self.assertTrue(0 <= y0 < y1 <= 1)
                if name in {'controls', 'configuration'}:
                    self.assertGreaterEqual(x0, .48)
                elif name == 'capacity':
                    self.assertGreaterEqual(y0, .32)
                else:
                    self.assertGreaterEqual(y0, .43)

    def test_worker_only_renders_low_resolution_proofs_from_linked_sources(self):
        source = (Path(__file__).parents[1] / 'blender_bento_proof.py').read_text(encoding='utf-8')
        self.assertIn('link=True', source)
        self.assertIn('resolution_percentage = 30', source)
        self.assertIn("'approval': 'pending'", source)
        self.assertIn('bpy.ops.wm.open_mainfile', source)
        self.assertNotIn('renders/final', source)
        self.assertNotIn('material_slots', source)


if __name__ == '__main__':
    unittest.main()
