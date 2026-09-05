"""Focused tests for native-final contract authoring."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.blender.pimm_production import blender_final_render as final_module
from scripts.blender.pimm_production.final_contract_cli import (
    _prepare_destination_parent,
    final_contract_payload,
)


class FinalContractCliTests(unittest.TestCase):
    def test_prepares_a_missing_release_contract_directory(self):
        with TemporaryDirectory() as root:
            destination = Path(root) / "renders" / "final-contracts" / "release-r01" / "shot.json"

            _prepare_destination_parent(destination)

            self.assertTrue(destination.parent.is_dir())
            self.assertFalse(destination.exists())

    def test_payload_is_exactly_bound_to_the_approval(self):
        approval = {
            "shot_id": "pimm-50g--hero--front",
            "proof_generation_id": "proof-20260828T114610Z-13d7d14",
            "authority_roots": {
                "asset": r"M:\30_Products\PIMM\blender-product-renders",
                "repository": r"B:\maliev\maliev-shopify-store",
                "tool": r"D:\Blender 5.2",
            },
            "evidence": {
                "scene": {
                    "path": r"M:\30_Products\PIMM\blender-product-renders\scenes\stills\pimm-50g--hero--front.blend"
                }
            },
            "inputs": {"scene_sha256": "B" * 64},
            "render_settings": {
                **{field: "A" * 64 for field in final_module._STATE_HASH_FIELDS},
                "base_dimensions": [1800, 2200],
                "effective_proof_dimensions": [450, 550],
                "output_dimensions": [1800, 2200],
                "alpha_mode": "RGBA",
                "proof_samples": 32,
            },
        }

        payload = final_contract_payload(
            approval, "release-2026-08-28-r21", samples=256
        )

        self.assertEqual(set(payload), final_module._FINAL_FIELDS)
        self.assertEqual(payload["generation_id"], approval["proof_generation_id"])
        self.assertEqual(payload["render_settings"], approval["render_settings"])
        self.assertEqual(payload["output_root"], "renders/final/release-2026-08-28-r21")
        self.assertEqual(payload["deliverables"], ["exr", "png", "webp"])
        self.assertEqual(payload["samples"], 256)


if __name__ == "__main__":
    unittest.main()
