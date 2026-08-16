import unittest

from scripts.blender.master_assets.pimm_master_audit import (
    AuditObjectRecord,
    evaluate_records,
)


def record(**overrides):
    values = {
        "stable_id": "30G-0123456789abcdef",
        "material_state": "unassigned",
        "material_ids": ("UNASSIGNED",),
        "material_scopes": ("shared",),
        "material_linked": (True,),
        "multi_material_exception": "",
        "disconnected_components": 1,
    }
    values.update(overrides)
    values.setdefault(
        "material_names",
        tuple(
            f"PIMM_{material_id}" if material_id else "DISPLAY_MATERIAL"
            for material_id in values["material_ids"]
        ),
    )
    return AuditObjectRecord(**values)


class MasterAuditContractTests(unittest.TestCase):
    def test_working_mode_reports_unassigned_without_failing_integrity(self):
        result = evaluate_records([record()], "working")
        self.assertEqual(result.unassigned_ids, ["30G-0123456789abcdef"])
        self.assertFalse(result.publishable)
        self.assertEqual(result.errors, [])

    def test_publish_mode_rejects_unassigned(self):
        result = evaluate_records([record()], "publish")
        self.assertIn("1 objects remain unassigned", result.errors)

    def test_unassigned_identity_rejects_publish_regardless_of_declared_state(self):
        """Catches approved/scope/link flags hiding an UNASSIGNED material identity."""

        mutations = (
            {
                "material_ids": ("UNASSIGNED",),
                "material_names": ("PIMM_UNASSIGNED",),
            },
            {
                "material_ids": ("PIMM_UNASSIGNED",),
                "material_names": ("DISPLAY_READY",),
            },
            {
                "material_ids": ("MALIEV_DECAL",),
                "material_names": ("UNASSIGNED",),
            },
            {
                "material_ids": ("MALIEV_DECAL",),
                "material_names": ("PIMM_UNASSIGNED",),
            },
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                candidate = record(
                    material_state="approved",
                    material_scopes=("machine-local",),
                    material_linked=(False,),
                    **mutation,
                )

                published = evaluate_records([candidate], "publish")
                working = evaluate_records([candidate], "working")

                self.assertFalse(published.publishable)
                self.assertEqual(
                    published.unassigned_ids, ["30G-0123456789abcdef"]
                )
                self.assertIn("1 objects remain unassigned", published.errors)
                self.assertFalse(working.publishable)
                self.assertEqual(
                    working.unassigned_ids, ["30G-0123456789abcdef"]
                )
                self.assertRegex(
                    "\n".join(working.errors), "UNASSIGNED|unassigned"
                )

    def test_shared_material_copy_made_local_fails(self):
        result = evaluate_records(
            [
                record(
                    material_state="approved",
                    material_ids=("CNC_MILLED_ALUMINUM",),
                    material_scopes=("shared",),
                    material_linked=(False,),
                )
            ],
            "working",
        )
        self.assertTrue(any("local copy of shared material" in error for error in result.errors))

    def test_machine_local_branding_is_allowed_but_never_shared(self):
        local = evaluate_records(
            [
                record(
                    material_state="approved",
                    material_ids=("MALIEV_DECAL",),
                    material_scopes=("machine-local",),
                    material_linked=(False,),
                )
            ],
            "working",
        )
        self.assertEqual(local.errors, [])
        shared = evaluate_records(
            [
                record(
                    material_state="approved",
                    material_ids=("MALIEV_DECAL",),
                    material_scopes=("shared",),
                    material_linked=(True,),
                )
            ],
            "working",
        )
        self.assertTrue(any("machine-local semantic" in error for error in shared.errors))

    def test_multiple_material_slots_require_documented_exception(self):
        result = evaluate_records(
            [
                record(
                    material_state="approved",
                    material_ids=("CNC_MILLED_ALUMINUM", "BLACK_OXIDE_STEEL"),
                    material_scopes=("shared", "shared"),
                    material_linked=(True, True),
                )
            ],
            "working",
        )
        self.assertTrue(any("multiple material slots" in error for error in result.errors))

    def test_duplicate_ids_and_disconnected_geometry_are_reported(self):
        result = evaluate_records(
            [record(), record(disconnected_components=2)], "working"
        )
        self.assertTrue(any("duplicate stable solid ID" in error for error in result.errors))
        self.assertEqual(result.disconnected_geometry, ["30G-0123456789abcdef"])

    def test_missing_material_id_never_falls_back_to_a_display_name(self):
        result = evaluate_records(
            [record(material_state="approved", material_ids=("",))], "working"
        )

        self.assertTrue(any("pimm_material_id" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
