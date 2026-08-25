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

    def test_front_camera_pose_defaults_to_a_level_optical_axis(self):
        module = self._module()

        pose = module.front_camera_pose(
            bounds_min=(-191.0, -190.0, -5.0),
            bounds_max=(223.0, 155.0, 885.0),
            distance=1540.0,
        )

        self.assertAlmostEqual(pose.target[0], 16.0)
        self.assertAlmostEqual(pose.location[0], pose.target[0])
        self.assertLess(pose.location[1], pose.target[1])
        self.assertAlmostEqual(pose.location[2], pose.target[2])
        self.assertEqual(pose.pitch_degrees, 0.0)
        self.assertAlmostEqual(
            math.dist(pose.location, pose.target),
            1540.0,
            places=6,
        )

    def test_85mm_camera_moves_back_to_preserve_56mm_framing(self):
        module = self._module()

        self.assertEqual(getattr(module, "DEFAULT_FOCAL_LENGTH_MM", None), 85.0)
        self.assertEqual(getattr(module, "DEFAULT_SENSOR_WIDTH_MM", None), 36.0)
        self.assertEqual(getattr(module, "DEFAULT_APERTURE_FSTOP", None), 11.0)
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

    def test_product_lighting_uses_rectangular_softboxes_with_controlled_ratios(self):
        module = self._module()

        lights = module.studio_light_specs(
            bounds_min=(-191.0, -190.0, -5.0),
            bounds_max=(223.0, 155.0, 885.0),
        )
        by_name = {light.name: light for light in lights}

        self.assertEqual(
            set(by_name),
            {
                "KEY_SOFTBOX",
                "FILL_SOFTBOX",
                "BASE_BOUNCE",
                "STRIP_LEFT",
                "STRIP_RIGHT",
            },
        )
        key = by_name["KEY_SOFTBOX"]
        fill = by_name["FILL_SOFTBOX"]
        base_bounce = by_name["BASE_BOUNCE"]
        self.assertGreaterEqual(math.log2(key.energy / fill.energy), 1.5)
        self.assertLessEqual(math.log2(key.energy / fill.energy), 2.5)
        compensation = module.PHOTOMETRIC_COORDINATE_COMPENSATION
        self.assertGreater(compensation, 1.0)
        self.assertLess(
            sum(light.energy for light in lights) / compensation,
            2_000_000.0,
        )
        for light in lights:
            self.assertEqual(light.shape, "RECTANGLE")
            self.assertGreater(light.size_x, 0.0)
            self.assertGreater(light.size_y, 0.0)
            self.assertEqual(light.temperature_kelvin, 5500.0)
        self.assertGreater(key.size_y, key.size_x)
        self.assertGreater(by_name["STRIP_LEFT"].size_y, by_name["STRIP_LEFT"].size_x)
        self.assertEqual(by_name["STRIP_LEFT"].energy, by_name["STRIP_RIGHT"].energy)
        self.assertEqual(
            by_name["STRIP_LEFT"].location[0],
            -by_name["STRIP_RIGHT"].location[0] + 32.0,
        )
        self.assertGreaterEqual(math.log2(key.energy / base_bounce.energy), 2.0)
        self.assertLessEqual(math.log2(key.energy / base_bounce.energy), 2.5)
        self.assertLess(base_bounce.location[2], fill.location[2])
        self.assertLess(base_bounce.target[2], fill.target[2])
        self.assertGreater(base_bounce.size_x, key.size_x)

    def test_white_studio_environment_is_one_exact_grounded_shadow_catcher(self):
        module = self._module()

        environments = module.studio_environment_specs(
            bounds_min=(-191.0, -190.0, -5.0),
            bounds_max=(223.0, 155.0, 885.0),
        )

        self.assertEqual(len(environments), 1)
        catcher = environments[0]
        self.assertEqual(catcher.name, "PIMM_SCENE_SHADOW_CATCHER")
        self.assertEqual(catcher.role, "shadow-catcher")
        self.assertEqual(catcher.material_id, "SCENE_SHADOW_CATCHER")
        self.assertAlmostEqual(catcher.z, -5.0)
        self.assertGreaterEqual(catcher.width, 414.0 * 6.0)
        self.assertGreaterEqual(catcher.depth, 345.0 * 10.0)
        self.assertLess(
            catcher.center_y - catcher.depth / 2.0,
            -5_000.0,
            "the floor must extend behind the front camera so no plane edge is visible",
        )
        self.assertGreaterEqual(catcher.base_color[0], 0.8)
        self.assertEqual(catcher.roughness, 0.72)

    def test_static_authoring_exports_no_animation_configuration(self):
        module = self._module()

        self.assertFalse(hasattr(module, "animation_action"))
        self.assertFalse(hasattr(module, "temperature_driver"))
        self.assertEqual(
            getattr(module, "DEFAULT_LOOK", None),
            "AgX - Medium High Contrast",
        )
        self.assertEqual(module.DEFAULT_EXPOSURE, 0.0)
        self.assertGreater(module.DEFAULT_WORLD_STRENGTH, 0.0)
        self.assertLessEqual(module.DEFAULT_WORLD_STRENGTH, 0.2)

    def test_world_setup_uses_the_existing_node_tree_without_deprecated_toggle(self):
        module = self._module()

        class Socket:
            default_value = None

        class Background:
            inputs = {"Color": Socket(), "Strength": Socket()}

        class World:
            node_tree = type("NodeTree", (), {"nodes": {"Background": Background()}})()

            @property
            def use_nodes(self):
                return True

            @use_nodes.setter
            def use_nodes(self, _value):
                raise AssertionError("deprecated World.use_nodes toggle must not be written")

        scene = type("Scene", (), {"world": World()})()
        module._set_world_strength(scene, 0.08)

        background = scene.world.node_tree.nodes["Background"]
        self.assertEqual(background.inputs["Color"].default_value, (0.18, 0.18, 0.18, 1.0))
        self.assertEqual(background.inputs["Strength"].default_value, 0.08)


if __name__ == "__main__":
    unittest.main()
