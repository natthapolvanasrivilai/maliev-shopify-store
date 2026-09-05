"""Contract tests for the pneumatic-input bento proof authoring script."""

from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[1] / "blender_pneumatic_input_proof.py"


class PneumaticInputProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_uses_native_bento_aspect_and_true_24_fps(self):
        self.assertIn("FPS = 24", self.source)
        self.assertIn('aspect_ratio": "8:11"', self.source)
        self.assertIn("width * 11 != height * 8", self.source)

    def test_uses_authoritative_regulator_parts(self):
        self.assertIn('KNOB_ID = "30G-17d7471e4d56f8a8"', self.source)
        self.assertIn('GAUGE_NEEDLE_ID = "30G-623a1bfb6905b6f3"', self.source)
        self.assertIn('MALE_COUPLER_ID = "30G-96016700baf3c097"', self.source)

    def test_sequence_holds_pressure_until_knob_turns(self):
        zero_hold = self.source.index('insert_key(needle, "rotation_euler", 126)')
        knob_turn = self.source.index('insert_key(knob, "rotation_euler", 126)')
        pressure_move = self.source.index('insert_key(needle, "rotation_euler", 162)')
        self.assertLess(knob_turn, zero_hold)
        self.assertLess(zero_hold, pressure_move)

    def test_knob_unlock_travel_is_one_point_five_millimeters(self):
        self.assertIn("knob_base.z + 1.5", self.source)
        self.assertIn('"knob_lift_mm": 1.5', self.source)

    def test_female_coupler_inherits_male_material_and_hose_uses_rubber(self):
        self.assertIn("coupler_material = male_coupler.material_slots[0].material", self.source)
        self.assertIn('bpy.data.materials.get("PIMM_RUBBER_BLACK")', self.source)
        self.assertIn('rubber if "hose" in obj.name.lower() else coupler_material', self.source)

    def test_import_relies_on_master_scene_unit_conversion(self):
        self.assertIn("root.scale = (1.0, 1.0, 1.0)", self.source)
        self.assertNotIn("root.scale = (1000.0, 1000.0, 1000.0)", self.source)

    def test_delivery_records_target_pressure_and_preview_only_boundary(self):
        self.assertIn('"regulated_pressure_mpa": 0.6', self.source)
        self.assertIn("math.radians(-63.0)", self.source)
        self.assertIn('"production_publish_authorized": False', self.source)


if __name__ == "__main__":
    unittest.main()
