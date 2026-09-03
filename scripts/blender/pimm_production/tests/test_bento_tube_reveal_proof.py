"""The technical reveal isolates exactly the owner's four selected components."""
from pathlib import Path
import unittest

from scripts.blender.pimm_production.blender_bento_tube_reveal_proof import TARGETS, FRAMES, reveal


class TubeRevealProofTests(unittest.TestCase):
    def test_exact_four_component_selection(self):
        self.assertEqual(set(TARGETS), {
            '30G__30g---Injection-Tube__0cd746d4874417b8',
            '30G__Nozzle---R15---3mm-hole__d15912a35de6e11f',
            '30G__25mm-plug__73f62368111f1385',
            '30G__WMH13-20__1d9dd9392dffa764',
        })

    def test_timing_is_bounded_and_returns_to_physical_view(self):
        self.assertEqual(FRAMES, 192)
        values = [reveal(frame) for frame in range(1, 194)]
        self.assertTrue(all(0 <= value <= 1 for value in values))
        self.assertEqual(values[0], values[-1])
        self.assertEqual(reveal(97), 1)
        self.assertLess(max(abs(a-b) for a,b in zip(values,values[1:])), .034)

    def test_invalid_frame_is_rejected(self):
        for frame in (0, -1, 194):
            with self.assertRaises(ValueError):
                reveal(frame)

    def test_no_master_material_or_geometry_mutation(self):
        source = (Path(__file__).parents[1] / 'blender_bento_tube_reveal_proof.py').read_text()
        for guard in ('focus.objects.link(obj)', 'obj.library and obj.data.library',
                      "before['materials'] ==", "before['matrix'] ==", "approval='pending'",
                      "opaque_tube.inputs['Type'].default_value = 'Apply Mask'",
                      "checked_file(Path(__file__), contract['script_sha256'])"):
            self.assertIn(guard, source)
        for forbidden in ('make_local', '.materials.clear(', '.materials.append(', 'objects.remove(', 'renders/final'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
