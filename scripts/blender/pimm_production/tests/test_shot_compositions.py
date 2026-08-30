"""Behavioral coverage for the governed 22-shot composition programme."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from scripts.blender.pimm_production.campaign_contract import (
    load_campaign,
    validate_campaign,
)
from scripts.blender.pimm_production.shot_compositions import (
    SHOT_COMPOSITIONS,
    composition_for,
    validate_compositions,
    validate_workshop_support_assets,
)


CAMPAIGN_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "campaigns"
    / "pimm-responsive-product-photography-v1.json"
)


class ShotCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.campaign = load_campaign(CAMPAIGN_PATH)
        campaign_errors = validate_campaign(cls.campaign)
        if campaign_errors:
            raise AssertionError(campaign_errors)

    def test_compositions_cover_the_exact_campaign_without_redefining_camera_policy(self) -> None:
        """Catches missing/rogue shots or optics copied away from campaign authority."""

        self.assertEqual(set(SHOT_COMPOSITIONS), set(self.campaign.by_shot_id))
        self.assertEqual(validate_compositions(self.campaign), [])
        for shot_id, policy in self.campaign.by_shot_id.items():
            with self.subTest(shot_id=shot_id):
                composition = composition_for(shot_id)
                self.assertEqual(composition.shot_id, policy.shot_id)
                self.assertNotIn("focal_length_mm", composition.__dataclass_fields__)
                self.assertNotIn("output_width", composition.__dataclass_fields__)

    def test_desktop_heroes_protect_left_copy_and_place_machine_right(self) -> None:
        """Catches desktop product placement colliding with the HTML decision copy."""

        for machine in ("30g", "50g"):
            shot = composition_for(f"pimm-{machine}--hero--desktop")
            with self.subTest(machine=machine):
                self.assertIsNotNone(shot.protected_copy_rect)
                self.assertLessEqual(shot.protected_copy_rect.right, 0.42)
                self.assertGreaterEqual(shot.subject_placement.center_x, 0.68)
                self.assertFalse(
                    shot.protected_copy_rect.contains(
                        shot.subject_placement.center_x,
                        shot.subject_placement.center_y,
                    )
                )

    def test_tablet_heroes_are_centered_with_balanced_clearance(self) -> None:
        """Catches tablet framing inheriting the desktop right-biased composition."""

        for machine in ("30g", "50g"):
            shot = composition_for(f"pimm-{machine}--hero--tablet")
            with self.subTest(machine=machine):
                self.assertAlmostEqual(shot.subject_placement.center_x, 0.5)
                self.assertAlmostEqual(
                    shot.subject_placement.clearance_left,
                    shot.subject_placement.clearance_right,
                )
                self.assertIsNone(shot.protected_copy_rect)

    def test_mobile_heroes_leave_the_lower_control_region_clear(self) -> None:
        """Catches mobile machines dropping into the selector and CTA field."""

        for machine in ("30g", "50g"):
            shot = composition_for(f"pimm-{machine}--hero--mobile")
            with self.subTest(machine=machine):
                self.assertLessEqual(shot.subject_placement.center_y, 0.40)
                self.assertIsNotNone(shot.protected_copy_rect)
                self.assertGreaterEqual(shot.protected_copy_rect.top, 0.66)
                self.assertEqual(shot.protected_copy_rect.bottom, 1.0)

    def test_editorial_bright_and_dark_use_distinct_eye_level_three_quarter_orbits(self) -> None:
        """Catches editorial variants collapsing to one view or a tilted full-machine camera."""

        for machine in ("30g", "50g"):
            bright = composition_for(
                f"pimm-{machine}--editorial-bright--three-quarter"
            )
            dark = composition_for(
                f"pimm-{machine}--editorial-dark--three-quarter"
            )
            with self.subTest(machine=machine):
                self.assertLess(bright.camera_azimuth_degrees, 0.0)
                self.assertGreater(dark.camera_azimuth_degrees, 0.0)
                self.assertEqual(bright.camera_elevation_degrees, 0.0)
                self.assertEqual(dark.camera_elevation_degrees, 0.0)
                self.assertGreaterEqual(bright.minimum_working_distance_heights, 3.0)
                self.assertGreaterEqual(dark.minimum_working_distance_heights, 3.0)

    def test_detail_compositions_name_every_required_stable_id_group(self) -> None:
        """Catches macro crops silently omitting a decision-relevant component group."""

        expected_groups = {
            "controls": {"controller_segments", "enclosure"},
            "pneumatics": {
                "air_cylinder",
                "regulator",
                "gauge",
                "valve_fittings_tubing",
                "gauge_decal",
                "airtac_artwork",
            },
            "tooling": {"nozzle", "platen", "fixture_grid"},
            "base-feet": {"base_plate", "springs", "posts", "foot_contacts"},
        }
        for machine in ("30g", "50g"):
            for detail, groups in expected_groups.items():
                shot_id = f"pimm-{machine}--{detail}--macro"
                composition = composition_for(shot_id)
                with self.subTest(shot_id=shot_id):
                    self.assertEqual(set(composition.target_groups), groups)
                    for identifiers in composition.target_groups.values():
                        self.assertTrue(identifiers)
                        self.assertTrue(
                            all(value.startswith(machine.upper()) for value in identifiers)
                        )
                    self.assertGreaterEqual(composition.minimum_working_distance_heights, 1.0)

    def test_pneumatics_compositions_include_the_complete_air_cylinder(self) -> None:
        """Catches pneumatic product frames regressing to an upper-control crop."""

        expected = {
            "30g": {
                "30G-a346c4960c82485b",
                "30G-01710571532bdd66",
                "30G-2b602e332d5d2816",
                "30G-ea4d84f9234f9e35",
                "30G-678f1ef64a9db8f8",
                "30G-dae70eb8d16aeb03",
                "30G-c2cad5607757c67c",
                "30G-fd3713c0793497ac",
                "30G-d7889d7dc749a14f",
            },
            "50g": {
                "50G-f5863566de699875",
                "50G-7240cdc95d9a6eb4",
                "50G-28eaf98ff78a0eac",
                "50G-6f2227a948150a84",
                "50G-817b30094d3fa693",
                "50G-5ffc7830bfe95dcf",
                "50G-c1e7ec628b39b2b7",
                "50G-aa7c5a1b44ceeb87",
                "50G-7a78ce314a111d73",
            },
        }
        for machine, stable_ids in expected.items():
            shot_id = f"pimm-{machine}--pneumatics--macro"
            composition = composition_for(shot_id)
            with self.subTest(shot_id=shot_id):
                self.assertEqual(set(composition.target_groups["air_cylinder"]), stable_ids)
                self.assertTrue(
                    set(stable_ids).isdisjoint(
                        composition.target_groups["valve_fittings_tubing"]
                    )
                )

    def test_comparison_places_each_linked_machine_once_on_one_ground_plane(self) -> None:
        """Catches duplicated collections, scale cheats, or independently tilted floors."""

        for shot_id in (
            "pimm-30g-50g--comparison--desktop",
            "pimm-30g-50g--comparison--mobile",
        ):
            composition = composition_for(shot_id)
            with self.subTest(shot_id=shot_id):
                placements = composition.machine_placements
                self.assertEqual(tuple(item.machine for item in placements), ("30G", "50G"))
                self.assertEqual(len({item.machine for item in placements}), 2)
                self.assertEqual({item.ground_z for item in placements}, {0.0})
                self.assertEqual({item.scale for item in placements}, {1.0})
                self.assertNotEqual(placements[0].offset_x, placements[1].offset_x)

    def test_workshop_support_assets_require_scene_support_ownership_and_provenance(self) -> None:
        """Catches unrecorded/local product-like meshes being accepted as workshop props."""

        shot = composition_for("pimm-50g--workshop--wide")
        approved = {
            "bench-v1": {
                "asset_version_id": "bench-v1",
                "local_relative_path": "assets/props/bench-v1.blend",
                "sha256": "A" * 64,
                "intended_shot_ids": [shot.shot_id],
            }
        }
        support = {
            "name": "PIMM_SUPPORT_BENCH",
            "ownership": "scene-support",
            "asset_version_id": "bench-v1",
            "local_relative_path": "assets/props/bench-v1.blend",
            "sha256": "A" * 64,
            "member_count": 1,
            "member_names": ["PIMM_SUPPORT_BENCH"],
        }
        self.assertEqual(validate_workshop_support_assets(shot, [support], approved), [])
        wrong_owner = {**support, "ownership": "product"}
        unknown = {**support, "asset_version_id": "unknown"}
        wrong_path = {**support, "local_relative_path": "assets/props/other.blend"}
        self.assertTrue(validate_workshop_support_assets(shot, [wrong_owner], approved))
        self.assertTrue(validate_workshop_support_assets(shot, [unknown], approved))
        self.assertTrue(validate_workshop_support_assets(shot, [wrong_path], approved))

    def test_invalid_normalized_or_non_campaign_composition_fails_closed(self) -> None:
        """Catches malformed placement values bypassing the composition gate."""

        shot = composition_for("pimm-30g--hero--desktop")
        invalid = replace(
            shot,
            subject_placement=replace(shot.subject_placement, center_x=1.2),
        )
        registry = dict(SHOT_COMPOSITIONS)
        registry[shot.shot_id] = invalid
        errors = validate_compositions(self.campaign, registry)
        self.assertIn("normalized subject placement", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
