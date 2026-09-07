import unittest

from scripts.blender.pimm_production.published_artwork import (
    ARTWORK_SPECS_BY_MACHINE,
    PUBLISHED_ARTWORK_COUNT_PROPERTY,
    PUBLISHED_ARTWORK_SHA256_PROPERTY,
    canonical_artwork_evidence,
    protected_artwork_evidence,
    validate_artwork_records,
)


def _valid_records(machine: str) -> list[dict[str, object]]:
    records = []
    for spec in ARTWORK_SPECS_BY_MACHINE[machine]:
        records.append(
            {
                "machine": machine,
                "object_name": spec.object_name,
                "role": spec.role,
                "asset_key": spec.asset_key,
                "attached_parent": spec.attached_parent,
                "material_id": spec.material_id,
                "image_relative_path": spec.image_relative_path,
                "image_sha256": spec.image_sha256,
                "mesh_sha256": "A" * 64,
                "uv_sha256": "B" * 64,
                "transform_sha256": "C" * 64,
                "packed_sha256": spec.image_sha256,
                "render_visible": True,
            }
        )
    return records


class PublishedArtworkTests(unittest.TestCase):
    def test_contract_property_names_are_stable(self) -> None:
        self.assertEqual(PUBLISHED_ARTWORK_COUNT_PROPERTY, "pimm_published_artwork_count")
        self.assertEqual(PUBLISHED_ARTWORK_SHA256_PROPERTY, "pimm_published_artwork_sha256")

    def test_exact_machine_specs(self) -> None:
        self.assertEqual(
            [(spec.role, spec.object_name) for spec in ARTWORK_SPECS_BY_MACHINE["30G"]],
            [
                ("pneumatic_switch_decal", "PIMM30_MASTER_AirTAC_Decal"),
                ("pressure_gauge_face", "PIMM30_MASTER_Pressure_Gauge_Face"),
            ],
        )
        self.assertEqual(
            [(spec.role, spec.object_name) for spec in ARTWORK_SPECS_BY_MACHINE["50G"]],
            [
                ("pneumatic_switch_decal", "PIMM50_MASTER_AirTAC_Decal"),
                ("pressure_gauge_face", "PIMM50_MASTER_Pressure_Gauge_Face"),
            ],
        )
        for machine, specs in ARTWORK_SPECS_BY_MACHINE.items():
            self.assertEqual(len(specs), 2, machine)
            for spec in specs:
                self.assertRegex(spec.image_sha256, r"^[A-F0-9]{64}$")
                self.assertTrue(spec.attached_parent.startswith(machine))

    def test_canonical_evidence_is_order_independent(self) -> None:
        records = _valid_records("30G")
        count, digest = canonical_artwork_evidence(records)
        reversed_count, reversed_digest = canonical_artwork_evidence(reversed(records))
        self.assertEqual((count, digest), (2, reversed_digest))
        self.assertRegex(digest, r"^[A-F0-9]{64}$")

    def test_valid_records_pass(self) -> None:
        self.assertEqual(validate_artwork_records("50G", _valid_records("50G")), [])

    def test_missing_duplicate_unexpected_and_dual_classification_fail(self) -> None:
        records = _valid_records("30G")
        self.assertIn("missing", "\n".join(validate_artwork_records("30G", records[:1])).lower())

        duplicate = records + [dict(records[0])]
        self.assertIn("duplicate", "\n".join(validate_artwork_records("30G", duplicate)).lower())

        unexpected = records + [{**records[0], "role": "unknown_artwork"}]
        self.assertIn("unexpected", "\n".join(validate_artwork_records("30G", unexpected)).lower())

        dual = [dict(item) for item in records]
        dual[0]["stable_id"] = "30G__should-not-exist"
        self.assertIn("stable", "\n".join(validate_artwork_records("30G", dual)).lower())

    def test_wrong_contract_fields_fail(self) -> None:
        records = _valid_records("50G")
        records[0]["attached_parent"] = "50G__wrong"
        records[1]["image_sha256"] = "C" * 64
        errors = "\n".join(validate_artwork_records("50G", records))
        self.assertIn("attached_parent", errors)
        self.assertIn("image_sha256", errors)

    def test_protected_evidence_ignores_governance_only_material_id(self) -> None:
        records = _valid_records("30G")
        before = protected_artwork_evidence(records)
        records[0]["material_id"] = "MACHINE_ARTWORK_AIRTAC_DECAL"
        self.assertEqual(before, protected_artwork_evidence(records))
        records[0]["transform_sha256"] = "D" * 64
        self.assertNotEqual(before, protected_artwork_evidence(records))


if __name__ == "__main__":
    unittest.main()
