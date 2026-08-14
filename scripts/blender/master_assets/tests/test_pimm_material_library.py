import unittest

from scripts.blender.master_assets.pimm_material_library import (
    MATERIAL_SPECS,
    validate_material_specs,
)


class MaterialLibraryContractTests(unittest.TestCase):
    def test_catalog_has_exact_stable_ids(self):
        self.assertEqual(
            set(MATERIAL_SPECS),
            {
                "UNASSIGNED",
                "CNC_MILLED_ALUMINUM",
                "DIE_CAST_ALUMINUM",
                "SATIN_SHEET_ALUMINUM",
                "POLISHED_STAINLESS",
                "NICKEL_PLATED_SHAFT",
                "BLACK_OXIDE_STEEL",
                "BRASS",
                "BLACK_POWDERCOAT",
                "RUBBER_BLACK",
                "PNEUMATIC_TUBE_BLUE",
                "ENGINEERING_PLASTIC",
            },
        )

    def test_aluminum_and_shaft_profiles_are_physically_distinct(self):
        cnc = MATERIAL_SPECS["CNC_MILLED_ALUMINUM"]
        cast = MATERIAL_SPECS["DIE_CAST_ALUMINUM"]
        satin = MATERIAL_SPECS["SATIN_SHEET_ALUMINUM"]
        shaft = MATERIAL_SPECS["NICKEL_PLATED_SHAFT"]

        self.assertEqual({cnc.metallic, cast.metallic, satin.metallic, shaft.metallic}, {1.0})
        self.assertEqual(len({cnc.roughness, cast.roughness, satin.roughness, shaft.roughness}), 4)
        self.assertGreater(cnc.anisotropy, cast.anisotropy)
        self.assertLess(shaft.roughness, cnc.roughness)
        self.assertNotEqual(cnc.microstructure, cast.microstructure)

    def test_unassigned_is_obvious_and_nonmetallic(self):
        unassigned = MATERIAL_SPECS["UNASSIGNED"]
        self.assertEqual(unassigned.base_color, (1.0, 0.0, 0.65, 1.0))
        self.assertEqual(unassigned.metallic, 0.0)
        self.assertGreaterEqual(unassigned.roughness, 0.45)

    def test_catalog_validation_rejects_machine_local_semantics(self):
        validate_material_specs(MATERIAL_SPECS)
        invalid = dict(MATERIAL_SPECS)
        invalid["MALIEV_DECAL"] = MATERIAL_SPECS["ENGINEERING_PLASTIC"]
        with self.assertRaisesRegex(ValueError, "machine-local material"):
            validate_material_specs(invalid)


if __name__ == "__main__":
    unittest.main()
