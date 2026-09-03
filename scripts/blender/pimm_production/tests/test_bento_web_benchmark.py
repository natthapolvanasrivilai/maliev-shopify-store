from types import SimpleNamespace
import unittest

from scripts.blender.pimm_production import blender_bento_web_benchmark as benchmark


class WebBenchmarkTests(unittest.TestCase):
    def test_web_settings_preserve_black_face_fix_and_sampling_threshold(self):
        scene = SimpleNamespace(render=SimpleNamespace(), cycles=SimpleNamespace(adaptive_threshold=.008))
        benchmark.configure(scene)
        self.assertEqual((scene.render.resolution_x, scene.render.resolution_y), (800, 1100))
        self.assertEqual(scene.render.resolution_percentage, 100)
        self.assertEqual(scene.cycles.samples, 48)
        self.assertFalse(scene.render.use_persistent_data)
        self.assertEqual(scene.cycles.adaptive_threshold, .008)

    def test_representative_frames_cover_solid_transition_and_revealed_states(self):
        self.assertEqual(benchmark.FRAMES, (1, 50, 100))
        self.assertIn('benchmark', benchmark.GENERATION)


if __name__ == '__main__':
    unittest.main()
