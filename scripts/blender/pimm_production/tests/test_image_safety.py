"""Pixel-level regression tests for PIMM alpha safety evidence."""

from __future__ import annotations

import unittest

from PIL import Image

from scripts.blender.pimm_production.image_safety import analyze_alpha_safety


def _rgba_canvas(size: tuple[int, int] = (100, 100)) -> Image.Image:
    return Image.new("RGBA", size, (0, 0, 0, 0))


def _rectangle(
    image: Image.Image,
    bounds: tuple[int, int, int, int],
    color: tuple[int, int, int, int],
) -> Image.Image:
    for y in range(bounds[1], bounds[3] + 1):
        for x in range(bounds[0], bounds[2] + 1):
            image.putpixel((x, y), color)
    return image


class AlphaSafetyTests(unittest.TestCase):
    def test_accepts_interior_product_and_shadow_with_required_clearance(self) -> None:
        """Catches a gate that rejects valid, separately measured transparent evidence."""

        product = _rectangle(_rgba_canvas(), (10, 10, 89, 89), (40, 50, 60, 255))
        shadow = _rectangle(_rgba_canvas(), (15, 16, 84, 83), (0, 0, 0, 120))

        evidence = analyze_alpha_safety(product, shadow, 0.08, 0.12)

        self.assertTrue(evidence.passed)
        self.assertEqual(evidence.canvas_size, (100, 100))
        self.assertEqual(evidence.product_bounds, (10, 10, 89, 89))
        self.assertEqual(evidence.shadow_bounds, (15, 16, 84, 83))
        self.assertEqual(evidence.product_edge_fractions["left"], 0.0)
        self.assertEqual(evidence.shadow_edge_fractions["bottom"], 0.0)
        self.assertFalse(evidence.catcher_visible)
        self.assertEqual(evidence.reasons, ())

    def test_rejects_product_alpha_touching_a_frame_edge(self) -> None:
        """Catches product crop loss hidden by a valid-looking shadow pass."""

        product = _rectangle(_rgba_canvas(), (0, 15, 70, 85), (1, 2, 3, 255))
        shadow = _rectangle(_rgba_canvas(), (15, 15, 84, 84), (0, 0, 0, 128))

        evidence = analyze_alpha_safety(product, shadow, 0.08, 0.12)

        self.assertFalse(evidence.passed)
        self.assertIn("product alpha touches left frame edge", evidence.reasons)

    def test_rejects_shadow_alpha_touching_a_frame_edge(self) -> None:
        """Catches a physically rendered shadow that clips outside the product bounds."""

        product = _rectangle(_rgba_canvas(), (10, 10, 89, 89), (1, 2, 3, 255))
        shadow = _rectangle(_rgba_canvas(), (16, 16, 84, 99), (0, 0, 0, 128))

        evidence = analyze_alpha_safety(product, shadow, 0.08, 0.12)

        self.assertFalse(evidence.passed)
        self.assertIn("shadow alpha touches bottom frame edge", evidence.reasons)

    def test_rejects_product_with_less_than_eight_percent_clearance(self) -> None:
        """Catches a hero product that is inset but still violates the approved 8% margin."""

        product = _rectangle(_rgba_canvas(), (7, 10, 89, 89), (1, 2, 3, 255))
        shadow = _rectangle(_rgba_canvas(), (15, 15, 84, 84), (0, 0, 0, 128))

        evidence = analyze_alpha_safety(product, shadow, 0.08, 0.12)

        self.assertFalse(evidence.passed)
        self.assertIn("product clearance at left is below 8.00%", evidence.reasons)

    def test_rejects_shadow_with_less_than_twelve_percent_hero_clearance(self) -> None:
        """Catches an inset hero shadow that nevertheless breaches the 12% safety margin."""

        product = _rectangle(_rgba_canvas(), (10, 10, 89, 89), (1, 2, 3, 255))
        shadow = _rectangle(_rgba_canvas(), (11, 15, 84, 84), (0, 0, 0, 128))

        evidence = analyze_alpha_safety(product, shadow, 0.08, 0.12)

        self.assertFalse(evidence.passed)
        self.assertIn("shadow clearance at left is below 12.00%", evidence.reasons)

    def test_rejects_visible_catcher_rgb_outside_product_alpha(self) -> None:
        """Catches a catcher or composited backdrop surviving where product alpha is zero."""

        product = _rectangle(_rgba_canvas(), (10, 10, 89, 89), (1, 2, 3, 255))
        product.putpixel((5, 5), (80, 70, 60, 0))
        shadow = _rectangle(_rgba_canvas(), (15, 15, 84, 84), (0, 0, 0, 128))

        evidence = analyze_alpha_safety(product, shadow, 0.08, 0.12)

        self.assertFalse(evidence.passed)
        self.assertTrue(evidence.catcher_visible)
        self.assertIn("visible catcher RGB exists outside product alpha", evidence.reasons)

    def test_rejects_missing_product_pixels(self) -> None:
        """Catches a transparent but empty product pass before it can pass presentation QA."""

        shadow = _rectangle(_rgba_canvas(), (15, 15, 84, 84), (0, 0, 0, 128))

        evidence = analyze_alpha_safety(_rgba_canvas(), shadow, 0.08, 0.12)

        self.assertFalse(evidence.passed)
        self.assertIsNone(evidence.product_bounds)
        self.assertIn("product pixels are missing", evidence.reasons)

    def test_rejects_a_fully_opaque_canvas(self) -> None:
        """Catches a render that claims transparency while filling every alpha pixel."""

        product = Image.new("RGBA", (100, 100), (1, 2, 3, 255))
        shadow = _rectangle(_rgba_canvas(), (15, 15, 84, 84), (0, 0, 0, 128))

        evidence = analyze_alpha_safety(product, shadow, 0.08, 0.12)

        self.assertFalse(evidence.passed)
        self.assertEqual(evidence.product_alpha_extrema, (255, 255))
        self.assertIn("product alpha is fully opaque", evidence.reasons)


if __name__ == "__main__":
    unittest.main()
