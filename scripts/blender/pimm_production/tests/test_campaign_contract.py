"""Regression coverage for the governed PIMM responsive photography campaign."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.blender.pimm_production.campaign_contract import (
    CAMPAIGN_SCHEMA,
    CampaignShot,
    load_campaign,
    shot_policy,
    validate_campaign,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
CAMPAIGN_PATH = (
    REPO_ROOT
    / "scripts"
    / "blender"
    / "pimm_production"
    / "contracts"
    / "campaigns"
    / "pimm-responsive-product-photography-v1.json"
)


def _campaign_payload() -> dict[str, object]:
    return json.loads(CAMPAIGN_PATH.read_text(encoding="utf-8"))


class CampaignContractTests(unittest.TestCase):
    def test_campaign_freezes_each_approved_shot_policy(self) -> None:
        """Catches a campaign change that drops, swaps, or weakens a specified shot."""

        campaign = load_campaign(CAMPAIGN_PATH)

        self.assertEqual(campaign.schema, "maliev.pimm-render-campaign/v1")
        self.assertEqual(campaign.campaign_id, "pimm-responsive-product-photography-v1")
        self.assertEqual(len(campaign.shots), 22)
        self.assertEqual(len({shot.shot_id for shot in campaign.shots}), 22)

        expected = {
            "pimm-30g--hero--desktop": (("30G",), "hero", 2560, 1440, True, 85.0, 11.0, 0.08, 0.12, ("hero-desktop",)),
            "pimm-30g--hero--tablet": (("30G",), "hero", 2048, 1536, True, 135.0, 11.0, 0.08, 0.12, ("hero-tablet",)),
            "pimm-30g--hero--mobile": (("30G",), "hero", 1440, 2560, True, 135.0, 11.0, 0.08, 0.12, ("hero-mobile",)),
            "pimm-50g--hero--desktop": (("50G",), "hero", 2560, 1440, True, 85.0, 11.0, 0.08, 0.12, ("hero-desktop",)),
            "pimm-50g--hero--tablet": (("50G",), "hero", 2048, 1536, True, 135.0, 11.0, 0.08, 0.12, ("hero-tablet",)),
            "pimm-50g--hero--mobile": (("50G",), "hero", 1440, 2560, True, 135.0, 11.0, 0.08, 0.12, ("hero-mobile",)),
            "pimm-30g--editorial-bright--three-quarter": (("30G",), "editorial", 1800, 2250, False, 135.0, 11.0, 0.0, 0.0, ("editorial-bright", "bento-primary")),
            "pimm-30g--editorial-dark--three-quarter": (("30G",), "editorial", 1800, 2250, False, 135.0, 11.0, 0.0, 0.0, ("editorial-dark",)),
            "pimm-50g--editorial-bright--three-quarter": (("50G",), "editorial", 1800, 2250, False, 135.0, 11.0, 0.0, 0.0, ("editorial-bright", "bento-primary")),
            "pimm-50g--editorial-dark--three-quarter": (("50G",), "editorial", 1800, 2250, False, 135.0, 11.0, 0.0, 0.0, ("editorial-dark",)),
            "pimm-30g--controls--macro": (("30G",), "detail", 1800, 2250, False, 135.0, 8.0, 0.0, 0.0, ("detail-controls", "bento-controls")),
            "pimm-30g--pneumatics--macro": (("30G",), "detail", 1800, 2250, False, 135.0, 8.0, 0.0, 0.0, ("detail-pneumatics", "bento-pneumatics")),
            "pimm-30g--tooling--macro": (("30G",), "detail", 1800, 2250, False, 135.0, 8.0, 0.0, 0.0, ("detail-tooling", "bento-tooling")),
            "pimm-30g--base-feet--macro": (("30G",), "detail", 1800, 2250, False, 135.0, 8.0, 0.0, 0.0, ("detail-base-feet", "bento-base-feet")),
            "pimm-50g--controls--macro": (("50G",), "detail", 1800, 2250, False, 135.0, 8.0, 0.0, 0.0, ("detail-controls", "bento-controls")),
            "pimm-50g--pneumatics--macro": (("50G",), "detail", 1800, 2250, False, 135.0, 8.0, 0.0, 0.0, ("detail-pneumatics", "bento-pneumatics")),
            "pimm-50g--tooling--macro": (("50G",), "detail", 1800, 2250, False, 135.0, 8.0, 0.0, 0.0, ("detail-tooling", "bento-tooling")),
            "pimm-50g--base-feet--macro": (("50G",), "detail", 1800, 2250, False, 135.0, 8.0, 0.0, 0.0, ("detail-base-feet", "bento-base-feet")),
            "pimm-30g-50g--comparison--desktop": (("30G", "50G"), "comparison", 2560, 1440, False, 85.0, 11.0, 0.0, 0.0, ("comparison-desktop",)),
            "pimm-30g-50g--comparison--mobile": (("30G", "50G"), "comparison", 1440, 1800, False, 135.0, 11.0, 0.0, 0.0, ("comparison-mobile",)),
            "pimm-50g--workshop--wide": (("50G",), "workshop", 2560, 1440, False, 85.0, 11.0, 0.0, 0.0, ("workshop-wide",)),
            "pimm-50g--workshop--portrait": (("50G",), "workshop", 1800, 2250, False, 135.0, 11.0, 0.0, 0.0, ("workshop-portrait",)),
        }
        actual = {
            shot.shot_id: (
                shot.machines,
                shot.purpose,
                shot.width,
                shot.height,
                shot.alpha,
                shot.focal_length_mm,
                shot.aperture_fstop,
                shot.product_safe_margin,
                shot.shadow_safe_margin,
                shot.storefront_roles,
            )
            for shot in campaign.shots
        }
        self.assertEqual(actual, expected)

    def test_manifest_maps_every_shot_to_its_canonical_scene_files(self) -> None:
        """Catches a scene contract or blend path drifting away from its shot identity."""

        payload = _campaign_payload()
        for shot in payload["shots"]:
            shot_id = shot["shot_id"]
            with self.subTest(shot_id=shot_id):
                self.assertEqual(shot["scene_contract_path"], f"scenes/contracts/{shot_id}.json")
                self.assertEqual(shot["scene_path"], f"scenes/stills/{shot_id}.blend")
                self.assertIsNone(shot["animation_contract"])

    def test_manifest_freezes_background_and_render_rig_constraints(self) -> None:
        """Catches a portable hero or controlled scene being changed to the wrong render class."""

        payload = _campaign_payload()
        expected_backgrounds = {
            "hero": "transparent",
            "editorial": "studio",
            "detail": "studio",
            "comparison": "studio",
            "workshop": "workshop",
        }
        for shot in payload["shots"]:
            with self.subTest(shot_id=shot["shot_id"]):
                self.assertEqual(shot["background_class"], expected_backgrounds[shot["purpose"]])
                self.assertEqual(shot["sensor_width_mm"], 36.0)
                self.assertEqual(shot["color_management"], "AgX - Medium High Contrast")
                self.assertEqual(shot["hdri_path"], "assets/hdri/studio_kontrast_04_4k.exr")
                self.assertEqual(shot["hdri_sha256"], "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06")
                self.assertEqual(shot["hdri_strength"], 0.5)
                self.assertEqual(shot["hdri_rotation_degrees"], 0.0)
                self.assertEqual(
                    shot["required_light_names"],
                    ["KEY_SOFTBOX", "FILL_SOFTBOX", "BASE_BOUNCE", "STRIP_LEFT", "STRIP_RIGHT"],
                )

    def test_campaign_validation_returns_every_semantic_error(self) -> None:
        """Catches a validator that stops after the first invalid campaign field."""

        payload = _campaign_payload()
        payload["schema"] = "wrong"
        payload["campaign_id"] = "wrong"
        payload["shots"][0]["focal_length_mm"] = 50.0
        payload["shots"][0]["aperture_fstop"] = 5.6
        payload["shots"][0]["animation_contract"] = "spin"
        with TemporaryDirectory() as root:
            path = Path(root) / "campaign.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_campaign(load_campaign(path))

        self.assertGreaterEqual(len(errors), 5)
        self.assertIn("campaign schema must equal maliev.pimm-render-campaign/v1", errors)
        self.assertIn("campaign_id must equal pimm-responsive-product-photography-v1", errors)
        self.assertIn("pimm-30g--hero--desktop focal_length_mm must be one of 85, 135, 200", errors)
        self.assertIn("pimm-30g--hero--desktop aperture_fstop must be one of 8, 11, 16", errors)
        self.assertIn("pimm-30g--hero--desktop animation_contract must be null", errors)

    def test_campaign_validation_rejects_a_permitted_but_wrong_shot_policy(self) -> None:
        """Catches a desktop hero being silently changed to another permitted camera policy."""

        payload = _campaign_payload()
        desktop = payload["shots"][0]
        desktop["width"] = 2048
        desktop["height"] = 1536
        desktop["focal_length_mm"] = 135.0
        desktop["storefront_roles"] = ["hero-tablet"]
        with TemporaryDirectory() as root:
            path = Path(root) / "campaign.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_campaign(load_campaign(path))

        self.assertIn(
            "pimm-30g--hero--desktop must match its exact approved campaign policy",
            errors,
        )

    def test_campaign_validation_collects_malformed_semantic_field_types(self) -> None:
        """Catches malformed campaign fields raising a TypeError instead of failing closed."""

        payload = _campaign_payload()
        payload["shots"][0]["purpose"] = []
        payload["shots"][0]["focal_length_mm"] = []
        payload["shots"][0]["machines"] = [["30G"]]
        with TemporaryDirectory() as root:
            path = Path(root) / "campaign.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_campaign(load_campaign(path))

        self.assertIn("pimm-30g--hero--desktop purpose must be a string", errors)
        self.assertIn("pimm-30g--hero--desktop focal_length_mm must be one of 85, 135, 200", errors)
        self.assertIn("pimm-30g--hero--desktop machines must be 30G, 50G, or the exact shared pair", errors)

    def test_loader_rejects_ambiguous_json_and_uncontracted_shot_policy(self) -> None:
        """Catches a permissive loader silently accepting an ambiguous campaign shape."""

        with TemporaryDirectory() as root:
            path = Path(root) / "campaign.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "root must be an object"):
                load_campaign(path)

            payload = _campaign_payload()
            payload["unexpected"] = True
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected fields"):
                load_campaign(path)

        campaign = load_campaign(CAMPAIGN_PATH)
        self.assertIsInstance(
            shot_policy(campaign, "pimm-30g--hero--desktop"), CampaignShot
        )
        with self.assertRaisesRegex(ValueError, "uncontracted shot"):
            shot_policy(campaign, "pimm-30g--hero--front")


if __name__ == "__main__":
    unittest.main()
