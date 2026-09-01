"""Contract coverage for PIMM collection-card rendering and publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import struct
import sys
from tempfile import TemporaryDirectory
import unittest
import zlib

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

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest().upper()

    @staticmethod
    def _write_rgb16_png(
        path: Path,
        color: tuple[int, int, int] = (240, 241, 243),
        size: tuple[int, int] = (1200, 1600),
    ) -> None:
        """Write a standards-compliant 16-bit RGB PNG without a Pillow depth conversion."""
        width, height = size

        def chunk(kind: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
            )

        pixel = struct.pack(">HHH", *(channel * 257 for channel in color))
        scanline = b"\0" + pixel * width
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scanline * height, level=9))
            + chunk(b"IEND", b"")
        )

    def _write_model_sidecar(self, model: str) -> None:
        master_sha256 = {
            "30g": "98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA",
            "50g": "CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90",
        }[model]
        outputs = []
        for angle, degrees in (("front", 0.0), ("left", -12.0), ("right", 12.0)):
            source = self.render_dir / f"maliev-pimm-collection-20260901-r01-{model}-{angle}.png"
            outputs.append({
                "angle": angle,
                "angle_degrees": degrees,
                "path": str(source),
                "width": 1200,
                "height": 1600,
                "sha256": self._sha256(source),
            })
        sidecar = {
            "schema": "maliev.pimm-collection-card-render/v1",
            "release_id": "maliev-pimm-collection-20260901-r01",
            "machine": model.upper(),
            "provenance": {
                "master_path": f"X:/authoritative/PIMM-{model.upper()}-MASTER.blend",
                "master_sha256": master_sha256,
                "published_meshes": 556,
                "foot_contact_levels": [0.0, 0.0, 0.0, 0.0],
                "foot_contact_spread": 0.0,
            },
            "outputs": outputs,
        }
        (self.render_dir / f"maliev-pimm-collection-20260901-r01-{model}-render.v1.json").write_text(
            json.dumps(sidecar), encoding="utf-8"
        )

    def _write_complete_fixture(self) -> None:
        for model in ("30g", "50g"):
            for angle in ("front", "left", "right"):
                self._write_rgb16_png(
                    self.render_dir / f"{finalizer.RELEASE_ID}-{model}-{angle}.png"
                )
            self._write_model_sidecar(model)

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
        self._write_rgb16_png(
            self.render_dir / f"{finalizer.RELEASE_ID}-30g-front.png",
            size=(1199, 1600),
        )
        self._write_model_sidecar("30g")

        with self.assertRaisesRegex(ValueError, "unexpected collection render dimensions"):
            finalizer.publish(self.render_dir, self.asset_dir, samples=256)

    def test_finalizer_rejects_eight_bit_png_even_when_pillow_reports_rgb(self) -> None:
        """Catches release publication accepting a native PNG below the 16-bit contract."""
        self._write_complete_fixture()
        Image.new("RGB", (1200, 1600), (240, 241, 243)).save(
            self.render_dir / f"{finalizer.RELEASE_ID}-30g-front.png"
        )
        self._write_model_sidecar("30g")

        with self.assertRaisesRegex(ValueError, "16-bit RGB"):
            finalizer.publish(self.render_dir, self.asset_dir, samples=256)

    def test_finalizer_requires_hash_bound_sidecars_before_copying_assets(self) -> None:
        """Catches correctly named pixels being released without renderer provenance."""
        self._write_complete_fixture()
        (self.render_dir / f"{finalizer.RELEASE_ID}-50g-render.v1.json").unlink()

        with self.assertRaisesRegex(FileNotFoundError, "render sidecar"):
            finalizer.publish(self.render_dir, self.asset_dir, samples=256)
        self.assertFalse(self.asset_dir.exists())

    def test_finalizer_rejects_sidecar_master_identity_drift(self) -> None:
        """Catches a render manifest that asserts pixels from an unlocked master."""
        self._write_complete_fixture()
        sidecar_path = self.render_dir / f"{finalizer.RELEASE_ID}-30g-render.v1.json"
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["provenance"]["master_sha256"] = "0" * 64
        sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "master SHA"):
            finalizer.publish(self.render_dir, self.asset_dir, samples=256)

    def test_finalizer_rejects_source_png_hash_drift_from_sidecar(self) -> None:
        """Catches a source PNG replacement after the renderer recorded its output hash."""
        self._write_complete_fixture()
        self._write_rgb16_png(
            self.render_dir / f"{finalizer.RELEASE_ID}-50g-right.png",
            color=(10, 20, 30),
        )

        with self.assertRaisesRegex(ValueError, "source PNG SHA"):
            finalizer.publish(self.render_dir, self.asset_dir, samples=256)

    def test_renderer_writes_machine_sidecar_with_exact_output_hashes(self) -> None:
        """Catches renderer success returning provenance without a publishable sidecar."""
        outputs = [{
            "angle": "front",
            "angle_degrees": 0.0,
            "path": "C:/renders/maliev-pimm-collection-20260901-r01-30g-front.png",
            "width": 1200,
            "height": 1600,
            "sha256": "A" * 64,
        }]
        provenance = {
            "master_path": "C:/masters/PIMM-30G-MASTER.blend",
            "master_sha256": "98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA",
        }

        sidecar_path = renderer._write_render_sidecar(
            self.render_dir, "30G", provenance, outputs
        )

        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        self.assertEqual(sidecar_path.name, "maliev-pimm-collection-20260901-r01-30g-render.v1.json")
        self.assertEqual(sidecar["machine"], "30G")
        self.assertEqual(sidecar["provenance"], provenance)
        self.assertEqual(sidecar["outputs"], outputs)

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
