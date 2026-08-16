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
                "STAINLESS_BRUSHED_HAIRLINE",
                "ALUMINUM_SATIN_EXTRUSION",
                "PINK_POWDERCOAT_STEEL",
                "NYLON_PA6",
                "PEEK",
                "ASA_3D_PRINT_0_2MM",
                "WHITE_TEXTILE_CABLE",
                "STEEL_BRAIDED_CABLE",
                "STAINLESS_STEEL_FASTENERS",
                "STEEL_SATIN",
                "STEEL_HEAT_OXIDIZED_BLUEBLACK",
                "GREEN_ILLUMINATED_NUMERIC",
                "RED_ILLUMINATED_NUMERIC",
                "RED_ILLUMINATED_TRANSPARENT",
                "WHITE_POWDERCOAT_STEEL",
                "BLACK_GLOSS_GLASS",
                "INACTIVE_NUMERIC_SEGMENT",
                "CHARCOAL_TEXTURED_POLYMER",
                "CONTROL_PANEL_SATIN_GRAY",
                "BLUE_ACCENT_POLYMER",
                "GREEN_ILLUMINATED_TRANSPARENT",
                "RED_SIGNAL_POLYMER",
                "GREEN_SIGNAL_POLYMER",
                "WARM_WHITE_MARKING",
                "SINTERED_BRONZE_POROUS",
            },
        )

    def test_requested_display_and_cable_profiles_are_explicit(self):
        green = MATERIAL_SPECS["GREEN_ILLUMINATED_NUMERIC"]
        red = MATERIAL_SPECS["RED_ILLUMINATED_NUMERIC"]
        transparent = MATERIAL_SPECS["RED_ILLUMINATED_TRANSPARENT"]
        self.assertGreater(green.emission_strength, 0.0)
        self.assertGreater(red.emission_strength, 0.0)
        self.assertGreater(transparent.transmission, 0.0)
        self.assertLess(transparent.alpha, 1.0)
        self.assertGreater(MATERIAL_SPECS["GREEN_ILLUMINATED_TRANSPARENT"].emission_strength, 0.0)
        self.assertGreater(MATERIAL_SPECS["BLACK_GLOSS_GLASS"].coat_weight, 0.0)
        self.assertGreater(MATERIAL_SPECS["INACTIVE_NUMERIC_SEGMENT"].roughness, 0.25)
        self.assertEqual(MATERIAL_SPECS["CHARCOAL_TEXTURED_POLYMER"].microstructure, "powder_grain")
        self.assertEqual(MATERIAL_SPECS["WARM_WHITE_MARKING"].microstructure, "none")
        sintered = MATERIAL_SPECS["SINTERED_BRONZE_POROUS"]
        self.assertEqual(sintered.microstructure, "sintered_porous")
        self.assertGreater(sintered.metallic, 0.5)
        self.assertGreater(sintered.roughness, 0.35)
        asa = MATERIAL_SPECS["ASA_3D_PRINT_0_2MM"]
        self.assertEqual(asa.microstructure, "layer_lines")
        self.assertLess(max(asa.base_color[:3]), 0.02)
        self.assertGreaterEqual(asa.roughness, 0.45)
        self.assertEqual(MATERIAL_SPECS["WHITE_TEXTILE_CABLE"].microstructure, "textile")
        self.assertEqual(MATERIAL_SPECS["ASA_3D_PRINT_0_2MM"].microstructure, "layer_lines")

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
