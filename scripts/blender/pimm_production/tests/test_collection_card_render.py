"""Contract coverage for PIMM collection-card rendering and publication."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from scripts.blender.pimm_production import blender_collection_card_render as renderer
from scripts.blender.pimm_production import finalize_collection_card_assets as finalizer


class CollectionCardContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.render_dir = root / "renders"
        self.asset_dir = root / "assets"
        self.render_dir.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write_complete_fixture(self) -> None:
        for model in ("30g", "50g"):
            for angle in ("front", "left", "right"):
                Image.new("RGB", (1200, 1600), (240, 241, 243)).save(
                    self.render_dir / f"{finalizer.RELEASE_ID}-{model}-{angle}.png"
                )

    def test_angle_contract_is_small_symmetric_and_front_resting(self) -> None:
        """Catches collection images drifting from the required restrained turntable set."""
        self.assertEqual(renderer.ANGLE_DEGREES, {"front": 0.0, "left": -12.0, "right": 12.0})
        self.assertEqual(renderer.OUTPUT_DIMENSIONS, (1200, 1600))

    def test_finalizer_publishes_lossless_native_and_storefront_records(self) -> None:
        """Catches a complete render set failing to yield uniquely addressable store assets."""
        self._write_complete_fixture()

        manifest = finalizer.publish(self.render_dir, self.asset_dir, samples=256)

        self.assertEqual(len(manifest["assets"]), 6)
        self.assertEqual({record["angle_degrees"] for record in manifest["assets"]}, {0.0, -12.0, 12.0})
        self.assertEqual(len({record["storefront"]["filename"] for record in manifest["assets"]}), 6)

    def test_finalizer_rejects_wrong_dimensions(self) -> None:
        """Catches an undersized native render before it can enter the collection release."""
        self._write_complete_fixture()
        Image.new("RGB", (1199, 1600)).save(
            self.render_dir / f"{finalizer.RELEASE_ID}-30g-front.png"
        )

        with self.assertRaisesRegex(ValueError, "unexpected collection render dimensions"):
            finalizer.publish(self.render_dir, self.asset_dir, samples=256)

    def test_renderer_script_bootstraps_outside_package_mode(self) -> None:
        """Catches Blender failing to import the shared studio helpers by file path."""
        script = Path(__file__).parents[1] / "blender_collection_card_render.py"

        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--expected-master-sha256", completed.stdout)


if __name__ == "__main__":
    unittest.main()
