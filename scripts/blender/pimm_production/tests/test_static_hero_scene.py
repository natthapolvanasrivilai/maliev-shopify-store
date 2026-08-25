"""Tests for deterministic straight-on PIMM static hero authoring."""

from __future__ import annotations

import importlib
import importlib.util
import math
import unittest


MODULE = "scripts.blender.pimm_production.blender_static_hero_scene"


class StaticHeroSceneTests(unittest.TestCase):
    def _module(self):
        self.assertIsNotNone(
            importlib.util.find_spec(MODULE),
            "static hero scene authoring module must exist",
        )
        return importlib.import_module(MODULE)

    def test_machine_configs_create_distinct_front_still_shots(self):
        module = self._module()

        self.assertEqual(set(module.MACHINE_CONFIGS), {"30G", "50G"})
        self.assertEqual(
            module.MACHINE_CONFIGS["30G"].scene_id,
            "pimm-30g--hero--front",
        )
        self.assertEqual(
            module.MACHINE_CONFIGS["50G"].scene_id,
            "pimm-50g--hero--front",
        )
        for config in module.MACHINE_CONFIGS.values():
            self.assertEqual(config.output_width, 1800)
            self.assertEqual(config.output_height, 2200)
            self.assertIn("scenes/stills/", config.output_path.as_posix())

    def test_front_camera_pose_is_centered_and_nearly_level(self):
        module = self._module()

        pose = module.front_camera_pose(
            bounds_min=(-191.0, -190.0, -5.0),
            bounds_max=(223.0, 155.0, 885.0),
            distance=1540.0,
            pitch_degrees=2.5,
        )

        self.assertAlmostEqual(pose.target[0], 16.0)
        self.assertAlmostEqual(pose.location[0], pose.target[0])
        self.assertLess(pose.location[1], pose.target[1])
        self.assertAlmostEqual(pose.pitch_degrees, 2.5)
        self.assertLessEqual(pose.pitch_degrees, 3.0)
        self.assertAlmostEqual(
            math.dist(pose.location, pose.target),
            1540.0,
            places=6,
        )

    def test_85mm_camera_moves_back_to_preserve_56mm_framing(self):
        module = self._module()

        self.assertEqual(getattr(module, "DEFAULT_FOCAL_LENGTH_MM", None), 85.0)
        self.assertAlmostEqual(
            module.scaled_camera_distance(1540.0, 56.0, 85.0),
            2337.5,
            places=6,
        )
        self.assertAlmostEqual(
            module.scaled_camera_distance(1715.0, 56.0, 85.0),
            2603.125,
            places=6,
        )

    def test_product_lighting_has_broad_front_key_fill_and_two_rims(self):
        module = self._module()

        lights = module.studio_light_specs(
            bounds_min=(-191.0, -190.0, -5.0),
            bounds_max=(223.0, 155.0, 885.0),
        )
        by_name = {light.name: light for light in lights}

        self.assertEqual(
            set(by_name),
            {"KEY_FRONT", "FILL_FRONT", "RIM_LEFT", "RIM_RIGHT"},
        )
        self.assertGreater(by_name["KEY_FRONT"].energy, by_name["FILL_FRONT"].energy)
        self.assertEqual(by_name["RIM_LEFT"].energy, by_name["RIM_RIGHT"].energy)
        self.assertGreaterEqual(by_name["KEY_FRONT"].size, 0.75 * 890.0)
        self.assertGreater(by_name["KEY_FRONT"].location[2], 885.0)
        self.assertEqual(by_name["RIM_LEFT"].location[0], -by_name["RIM_RIGHT"].location[0] + 32.0)

    def test_static_authoring_exports_no_animation_configuration(self):
        module = self._module()

        self.assertFalse(hasattr(module, "animation_action"))
        self.assertFalse(hasattr(module, "temperature_driver"))
        self.assertEqual(
            getattr(module, "DEFAULT_LOOK", None),
            "AgX - Medium High Contrast",
        )
        self.assertEqual(module.DEFAULT_EXPOSURE, 3.5)
        self.assertEqual(module.DEFAULT_WORLD_STRENGTH, 3.0)


if __name__ == "__main__":
    unittest.main()
