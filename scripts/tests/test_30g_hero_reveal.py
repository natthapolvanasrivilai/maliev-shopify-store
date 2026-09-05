"""Pure checks for the native reveal trajectory; Blender is not imported."""
import unittest
from scripts.blender.pimm_production.blender_30g_hero_reveal import frame_state, FRAME_COUNT


class HeroRevealTrajectoryTests(unittest.TestCase):
    def test_48_native_frames_cover_two_seconds_at_24fps(self):
        self.assertEqual(FRAME_COUNT / 24, 2)

    def test_settles_at_exact_front_and_full_studio_power(self):
        self.assertEqual(frame_state(0), {'angle': -12, 'light': .3, 'background': .75})
        self.assertEqual(frame_state(47), {'angle': 0, 'light': 1, 'background': 1})

    def test_no_reversal_or_brightness_overshoot(self):
        frames = [frame_state(i) for i in range(FRAME_COUNT)]
        for first, second in zip(frames, frames[1:]):
            self.assertLessEqual(first['angle'], second['angle'])
            self.assertLessEqual(first['light'], second['light'])
            self.assertLessEqual(second['light'], 1)
        self.assertEqual(frames[34]['light'], 1)


if __name__ == '__main__':
    unittest.main()
