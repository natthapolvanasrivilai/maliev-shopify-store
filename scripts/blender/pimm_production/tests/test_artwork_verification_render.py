import unittest

from scripts.blender.pimm_production.blender_render_artwork_verification import (
    crop_border,
)


class ArtworkVerificationRenderTests(unittest.TestCase):
    def test_crop_border_pads_and_clamps_projected_points(self) -> None:
        border = crop_border([(0.40, 0.45), (0.60, 0.55)], padding=0.5)
        self.assertEqual(border, (0.30, 0.70, 0.40, 0.60))

    def test_crop_border_enforces_minimum_span(self) -> None:
        x_min, x_max, y_min, y_max = crop_border(
            [(0.50, 0.50), (0.51, 0.51)], padding=0.0, minimum_span=0.10
        )
        self.assertAlmostEqual(x_max - x_min, 0.10)
        self.assertAlmostEqual(y_max - y_min, 0.10)

    def test_crop_border_rejects_empty_points(self) -> None:
        with self.assertRaisesRegex(ValueError, "projected point"):
            crop_border([])


if __name__ == "__main__":
    unittest.main()
