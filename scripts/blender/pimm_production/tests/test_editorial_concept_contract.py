"""Regression coverage for the preview-only PIMM editorial concept campaign."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.blender.pimm_production.editorial_concept_contract import (
    EDITORIAL_CAMPAIGN_PATH,
    EditorialConceptCampaign,
    EditorialConceptShot,
    load_editorial_campaign,
    validate_editorial_campaign,
)


EXPECTED = {
    "pimm-30g--concept-architectural-daylight": ("30G", 1280, 720, 85.0),
    "pimm-50g--concept-dark-engineering": ("50G", 1280, 720, 135.0),
    "pimm-50g--concept-modern-workshop": ("50G", 1280, 720, 85.0),
    "pimm-30g--concept-process-still-life": ("30G", 900, 1125, 180.0),
}


def _payload() -> dict[str, object]:
    return json.loads(EDITORIAL_CAMPAIGN_PATH.read_text(encoding="utf-8"))


class EditorialConceptContractTests(unittest.TestCase):
    def test_campaign_freezes_exact_four_preview_shot_policies(self) -> None:
        campaign = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH)

        self.assertEqual(set(campaign.by_shot_id), set(EXPECTED))
        self.assertEqual(len(campaign.shots), 4)
        self.assertEqual(validate_editorial_campaign(campaign), [])
        self.assertEqual(campaign.master_30g_path, "masters/PIMM-30G-MASTER.blend")
        self.assertEqual(campaign.master_50g_path, "masters/PIMM-50G-MASTER.blend")
        self.assertEqual(campaign.material_library_path, "masters/PIMM-MATERIAL-LIBRARY.blend")
        self.assertEqual(campaign.input_policy, "link-only-immutable")
        actual = {
            shot.shot_id: (shot.machine, shot.width, shot.height, shot.focal_length_mm)
            for shot in campaign.shots
        }
        self.assertEqual(actual, EXPECTED)
        self.assertTrue(all(isinstance(shot, EditorialConceptShot) for shot in campaign.shots))
        self.assertIsInstance(campaign, EditorialConceptCampaign)

    def test_shots_are_immutable(self) -> None:
        shot = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH).shots[0]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            shot.machine = "50G"  # type: ignore[misc]

    def test_validation_rejects_changed_machine_dimensions_focal_length_and_authorization(self) -> None:
        payload = _payload()
        shot = payload["shots"][0]
        shot.update(machine="50G", width=900, height=1125, focal_length_mm=135.0, final_authorized=True)
        with TemporaryDirectory() as root:
            path = Path(root) / "campaign.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_editorial_campaign(load_editorial_campaign(path))
        joined = "\n".join(errors)
        self.assertIn("machine", joined)
        self.assertIn("dimensions", joined)
        self.assertIn("focal_length_mm", joined)
        self.assertIn("final_authorized", joined)

    def test_validation_rejects_missing_contact_gate_and_non_cycles_engine(self) -> None:
        payload = _payload()
        shot = payload["shots"][0]
        shot.pop("contact_gate")
        shot["render_engine"] = "BLENDER_EEVEE_NEXT"
        with TemporaryDirectory() as root:
            path = Path(root) / "campaign.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing=.*contact_gate"):
                load_editorial_campaign(path)
            shot["contact_gate"] = "four-feet-common-plane"
            path.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_editorial_campaign(load_editorial_campaign(path))
        joined = "\n".join(errors)
        self.assertIn("render_engine", joined)

    def test_validation_rejects_substituted_authoritative_inputs_and_policy(self) -> None:
        payload = _payload()
        payload["master_30g_path"] = "masters/PIMM-50G-MASTER.blend"
        payload["material_library_path"] = "masters/substitute.blend"
        payload["input_policy"] = "editable-local-copies"
        campaign = EditorialConceptCampaign(
            payload["schema"], payload["campaign_id"], payload["master_30g_path"],
            payload["master_50g_path"], payload["material_library_path"],
            payload["input_policy"], tuple(load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH).shots),
        )
        errors = validate_editorial_campaign(campaign)
        joined = "\n".join(errors)
        self.assertIn("master_30g_path", joined)
        self.assertIn("material_library_path", joined)
        self.assertIn("input_policy", joined)

    def test_loader_rejects_missing_authoritative_input_field(self) -> None:
        payload = _payload()
        payload.pop("master_50g_path")
        with TemporaryDirectory() as root:
            path = Path(root) / "campaign.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing=.*master_50g_path"):
                load_editorial_campaign(path)

    def test_loader_rejects_duplicate_shot_ids_and_duplicate_json_keys(self) -> None:
        payload = _payload()
        payload["shots"].append(dict(payload["shots"][0]))
        with TemporaryDirectory() as root:
            path = Path(root) / "campaign.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicated"):
                load_editorial_campaign(path)

            path.write_text('{"schema":"x","schema":"y","campaign_id":"x","shots":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_editorial_campaign(path)


if __name__ == "__main__":
    unittest.main()
