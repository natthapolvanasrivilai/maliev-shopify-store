"""Regression coverage for governed PIMM static-product scene contracts."""

from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import importlib
import importlib.util
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


MODULE = "scripts.blender.pimm_production.blender_static_product_scene"

EXPECTED = {
    "pimm-30g--overview--three-quarter": ("30G", "overview", "three-quarter", 85.0),
    "pimm-30g--engineering--controls": ("30G", "engineering", "controls", 135.0),
    "pimm-30g--tooling--front-detail": ("30G", "tooling", "front-detail", 135.0),
    "pimm-50g--overview--three-quarter": ("50G", "overview", "three-quarter", 85.0),
    "pimm-50g--engineering--controls": ("50G", "engineering", "controls", 135.0),
    "pimm-50g--tooling--front-detail": ("50G", "tooling", "front-detail", 135.0),
}


class StaticProductSceneTests(unittest.TestCase):
    def _module(self):
        self.assertIsNotNone(
            importlib.util.find_spec(MODULE),
            "static product scene authoring module must exist",
        )
        return importlib.import_module(MODULE)

    def test_registry_has_exact_static_shots(self):
        """Catches a missing, renamed, or miscalibrated governed still shot."""

        module = self._module()
        self.assertEqual(set(module.SHOT_CONFIGS), set(EXPECTED))
        for shot_id, (machine, purpose, view, lens) in EXPECTED.items():
            config = module.SHOT_CONFIGS[shot_id]
            self.assertEqual((config.machine, config.purpose, config.view), (machine, purpose, view))
            self.assertEqual(config.focal_length_mm, lens)
            self.assertEqual((config.output_width, config.output_height), (2400, 1800))
            self.assertIsNone(config.animation_contract)

    def setUp(self):
        self.module = self._module()
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.asset_root = Path(self.temporary_directory.name) / "blender-product-renders"
        self.original_asset_root = self.module.ASSET_ROOT
        self.module.ASSET_ROOT = self.asset_root
        self.addCleanup(setattr, self.module, "ASSET_ROOT", self.original_asset_root)
        masters = self.asset_root / "masters"
        masters.mkdir(parents=True)
        (masters / "PIMM-30G-MASTER.blend").write_bytes(b"master-30g")
        (masters / "PIMM-50G-MASTER.blend").write_bytes(b"master-50g")
        (masters / "PIMM-MATERIAL-LIBRARY.blend").write_bytes(b"material-library")
        self.config = self.module.SHOT_CONFIGS["pimm-30g--overview--three-quarter"]

    def test_contract_payload_is_hash_pinned_and_static(self):
        """Catches a payload that loses its master, material, alpha, or still-image guard."""

        payload = self.module.contract_payload(self.config)

        self.assertEqual(payload["scene_id"], "pimm-30g--overview--three-quarter")
        self.assertEqual(payload["purpose"], "overview")
        self.assertEqual(payload["master_path"], "masters/PIMM-30G-MASTER.blend")
        self.assertEqual(
            payload["master_sha256"],
            "D660AAD870DB73EA104BC23B89F76DA188EAF286987DB4C6DFCDFB2565E65FFE",
        )
        self.assertEqual(payload["material_library_path"], "masters/PIMM-MATERIAL-LIBRARY.blend")
        self.assertEqual(
            payload["material_library_sha256"],
            "484DADB0DD2CD7DA59F26EF256C042E9ECF6D4466FB99B90E336F993E48246D1",
        )
        self.assertEqual(payload["master_collection"], "PIMM_PUBLISHED")
        self.assertTrue(payload["complete_product"])
        self.assertIsNone(payload["animation_contract"])
        self.assertEqual(payload["output_contract"], {"width": 2400, "height": 1800, "alpha": True})

    def test_unknown_shot_id_is_rejected_before_contract_write(self):
        """Catches a CLI path that could create a contract for an ungoverned shot."""

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                self.module.main(["--shot-id", "pimm-30g--unknown--view", "--prepare-contract"])

        self.assertEqual(raised.exception.code, 2)
        self.assertFalse((self.asset_root / "scenes" / "contracts").exists())

    def test_existing_contract_is_never_overwritten(self):
        """Catches preparation replacing a previously approved contract file."""

        destination = self.asset_root / "scenes" / "contracts" / f"{self.config.scene_id}.json"
        destination.parent.mkdir(parents=True)
        destination.write_text('{"approved": true}\n', encoding="utf-8")

        with self.assertRaises(FileExistsError):
            self.module.prepare_contract(self.config)

        self.assertEqual(destination.read_text(encoding="utf-8"), '{"approved": true}\n')

    def test_invalid_static_configurations_are_rejected_before_contract_write(self):
        """Catches unauthorised optics, animation, or resolution reaching contract I/O."""

        invalid_configs = (
            replace(self.config, focal_length_mm=100.0),
            replace(self.config, animation_contract="turntable"),
            replace(self.config, output_width=1920),
        )

        for config in invalid_configs:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    self.module.prepare_contract(config)
                self.assertFalse((self.asset_root / "scenes" / "contracts").exists())

    def test_contract_destination_outside_contracts_is_rejected_before_write(self):
        """Catches path construction escaping the governed contracts directory."""

        outside_destination = self.asset_root / "scenes" / "outside.json"

        with patch.object(self.module, "_contract_path", return_value=outside_destination):
            with self.assertRaises(ValueError):
                self.module.prepare_contract(self.config)

        self.assertFalse(outside_destination.exists())
        self.assertFalse((self.asset_root / "scenes" / "contracts").exists())


if __name__ == "__main__":
    unittest.main()
