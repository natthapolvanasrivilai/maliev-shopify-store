"""Governance coverage for preview-only one-shot editorial Blender scenes."""

from __future__ import annotations

import copy
import dataclasses
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from scripts.blender.pimm_production.editorial_concept_contract import (
    EDITORIAL_CAMPAIGN_PATH,
    load_editorial_campaign,
)
from scripts.blender.pimm_production import blender_editorial_scene


def _snapshot(contract: dict[str, object]) -> dict[str, object]:
    machine_bounds = {"minimum": [-100.0, -80.0, 0.0], "maximum": [120.0, 90.0, 300.0]}
    contact = {
        "schema_version": 1,
        "machine": contract["machine"],
        "selection_basis": "live-linked-master-four-nylon-feet",
        "contact_z": 0.0,
        "tolerance": 0.0002,
        "spread": 0.0,
        "stable_ids": [f"{contract['machine']}-foot-{index}" for index in range(4)],
        "pad_bottoms": [0.0, 0.0, 0.0, 0.0],
        "feet": [
            {
                "stable_id": f"{contract['machine']}-foot-{index}",
                "bottom_z": 0.0,
                "center_x": float(index * 10),
                "center_y": float(index * 5),
                "delta_to_plane": 0.0,
            }
            for index in range(4)
        ],
        "outlier_stable_ids": [],
    }
    return {
        "scene_id": contract["scene_id"],
        "scene_path_matches": True,
        "embedded_contract_matches": True,
        "embedded_contract_sha256_matches": True,
        "final_authorized": False,
        "master_library_count": 1,
        "material_library_present": True,
        "unexpected_library_paths": [],
        "library_overrides": [],
        "local_product_copies": [],
        "linked_product_count": 10,
        "stable_id_count": 10,
        "stable_id_sha256": "A" * 64,
        "machine_bounds": machine_bounds,
        "camera": {
            "active": True,
            "scene_local": True,
            "focal_length_mm": contract["camera"]["focal_length_mm"],
            "aperture_fstop": contract["camera"]["aperture_fstop"],
            "sensor_width_mm": contract["camera"]["sensor_width_mm"],
            "verticals_upright": True,
            "eye_level_midline": True,
            "complete_machine_framed": True,
            "support_rectangle_framed": True,
        },
        "render": {
            "engine": "CYCLES",
            "width": contract["render"]["width"],
            "height": contract["render"]["height"],
            "resolution_percentage": 100,
            "preview_samples": 32,
            "denoise": True,
            "view_transform": "AgX",
            "look": "AgX - Medium High Contrast",
        },
        "contact": contact,
        "contact_plane": {
            "count": 1,
            "z": 0.0,
            "covers_all_feet": True,
        },
        "support_bounds": [
            {
                "name": "PIMM_SCENE_SUPPORT_FIXTURE",
                "role": "fixture",
                "minimum": [200.0, -20.0, 0.0],
                "maximum": [250.0, 20.0, 40.0],
                "intersects_machine": False,
                "hides_foot_stable_ids": [],
            }
        ],
        "set": copy.deepcopy(contract["set"]),
        "external_provenance": copy.deepcopy(contract["external_assets"]),
    }


class BlenderEditorialSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        campaign = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH)
        cls.campaign = campaign
        cls.shot = campaign.by_shot_id["pimm-30g--concept-architectural-daylight"]
        cls.contract = blender_editorial_scene.prepare_editorial_contract(cls.shot)

    def errors(self, snapshot: dict[str, object], contract: dict[str, object] | None = None) -> list[str]:
        return blender_editorial_scene._validate_editorial_runtime_snapshot(
            snapshot, self.contract if contract is None else contract
        )

    def test_prepares_exact_preview_only_contract_from_current_protected_inputs(self) -> None:
        """Catches a contract that omits immutable master, material, contact, or preview authority."""

        contract = self.contract
        self.assertEqual(contract["schema"], "maliev.pimm-editorial-scene/v1")
        self.assertEqual(contract["scene_id"], self.shot.shot_id)
        self.assertEqual(contract["master"]["path"], "masters/PIMM-30G-MASTER.blend")
        self.assertEqual(contract["material_library"]["path"], "masters/PIMM-MATERIAL-LIBRARY.blend")
        self.assertEqual(contract["contact"]["gate"], "four-feet-common-plane")
        self.assertEqual(len(contract["master"]["sha256"]), 64)
        self.assertEqual(len(contract["material_library"]["sha256"]), 64)
        self.assertFalse(contract["final_authorized"])

    def test_rejects_a_local_product_copy(self) -> None:
        """Catches scene-local meshes carrying product identity outside the linked master."""

        snapshot = _snapshot(self.contract)
        snapshot["local_product_copies"] = ["30G-private-copy"]
        self.assertIn("local product", "\n".join(self.errors(snapshot)))

    def test_rejects_changed_linked_master_and_material_library(self) -> None:
        """Catches protected input bytes drifting after the contract was prepared."""

        for key, phrase in (("master", "master SHA-256"), ("material_library", "material-library SHA-256")):
            contract = copy.deepcopy(self.contract)
            contract[key]["sha256"] = "0" * 64
            with self.subTest(key=key):
                self.assertIn(phrase, "\n".join(self.errors(_snapshot(contract), contract)))

    def test_rejects_wrong_focal_length(self) -> None:
        """Catches a camera that no longer uses the Task 1 focal length."""

        snapshot = _snapshot(self.contract)
        snapshot["camera"]["focal_length_mm"] = 50.0
        self.assertIn("focal length", "\n".join(self.errors(snapshot)))

    def test_rejects_non_level_architectural_verticals(self) -> None:
        """Catches camera roll or pitch that makes architectural verticals converge."""

        snapshot = _snapshot(self.contract)
        snapshot["camera"]["verticals_upright"] = False
        self.assertIn("architectural verticals", "\n".join(self.errors(snapshot)))

    def test_rejects_missing_per_foot_common_plane_evidence(self) -> None:
        """Catches a declared contact pass without four independently measured feet."""

        snapshot = _snapshot(self.contract)
        snapshot["contact"]["feet"] = snapshot["contact"]["feet"][:3]
        snapshot["contact"]["stable_ids"] = snapshot["contact"]["stable_ids"][:3]
        snapshot["contact"]["pad_bottoms"] = snapshot["contact"]["pad_bottoms"][:3]
        self.assertIn("exactly four measured feet", "\n".join(self.errors(snapshot)))

    def test_rejects_prop_bounds_intersecting_machine_or_hiding_feet(self) -> None:
        """Catches collision or foreground occlusion hidden behind a set-level pass flag."""

        for field, value, phrase in (
            ("intersects_machine", True, "intersects linked machine bounds"),
            ("hides_foot_stable_ids", ["30G-foot-0"], "hides linked machine feet"),
        ):
            snapshot = _snapshot(self.contract)
            snapshot["support_bounds"][0][field] = value
            with self.subTest(field=field):
                self.assertIn(phrase, "\n".join(self.errors(snapshot)))

    def test_rejects_missing_set_signatures(self) -> None:
        """Catches a generic set replacing the contracted distinct geometry/light design."""

        snapshot = _snapshot(self.contract)
        snapshot["set"]["geometry_signature"] = ""
        self.assertIn("set signature", "\n".join(self.errors(snapshot)))

    def test_rejects_missing_external_provenance(self) -> None:
        """Catches a linked contextual asset without the exact governed CC0 record."""

        shot = self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
        contract = blender_editorial_scene.prepare_editorial_contract(shot)
        snapshot = _snapshot(contract)
        snapshot["external_provenance"] = []
        self.assertIn("external provenance", "\n".join(self.errors(snapshot, contract)))

    def test_rejects_any_final_authorization(self) -> None:
        """Catches preview authoring silently widening into final-render authority."""

        contract = copy.deepcopy(self.contract)
        contract["final_authorized"] = True
        snapshot = _snapshot(contract)
        snapshot["final_authorized"] = True
        self.assertIn("final_authorized must remain false", "\n".join(self.errors(snapshot, contract)))

    def test_rejects_mutated_shot_policy_under_an_approved_id(self) -> None:
        """Catches authoring that trusts an approved ID while ignoring changed camera policy."""

        mutated = dataclasses.replace(self.shot, focal_length_mm=50.0)
        with self.assertRaisesRegex(ValueError, "exact approved editorial shot"):
            blender_editorial_scene.prepare_editorial_contract(mutated)

    def test_ordinary_python_cli_keeps_arguments_without_blenders_separator(self) -> None:
        """Catches the prepare command silently discarding normal module arguments."""

        argv = [
            "blender_editorial_scene.py",
            "--prepare-contract",
            "--shot-id",
            self.shot.shot_id,
        ]
        output = StringIO()
        with patch.object(blender_editorial_scene.sys, "argv", argv), redirect_stdout(output):
            self.assertEqual(blender_editorial_scene.main(), 0)
        self.assertIn("contract_prepared_not_published", output.getvalue())

    def test_scene_support_bounds_do_not_require_a_product_stable_id(self) -> None:
        """Catches reuse of the product-only bounds gate for governed scene supports."""

        class Identity:
            def __matmul__(self, point):
                return point

        support = SimpleNamespace(
            type="MESH",
            bound_box=tuple(
                (x, y, z)
                for x in (-2.0, 3.0)
                for y in (-4.0, 5.0)
                for z in (-6.0, 7.0)
            ),
            matrix_world=Identity(),
        )
        self.assertEqual(
            blender_editorial_scene._object_bounds(support),
            ((-2.0, -4.0, -6.0), (3.0, 5.0, 7.0)),
        )


if __name__ == "__main__":
    unittest.main()
