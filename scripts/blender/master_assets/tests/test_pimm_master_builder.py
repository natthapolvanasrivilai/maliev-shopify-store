import math
import unittest

from scripts.blender.master_assets.pimm_master_builder import (
    BLENDER_LENGTH_UNIT,
    BLENDER_SCENE_SCALE_LENGTH,
    BLENDER_UNIT_SYSTEM,
    REQUIRED_OBJECT_PROPERTIES,
    SOURCE_TO_BLENDER_ROTATION_X,
    SOURCE_TO_BLENDER_SCALE,
    collection_key,
    master_object_name,
    validate_import_manifest,
)


class MasterBuilderContractTests(unittest.TestCase):
    def test_source_coordinate_conversion_is_fixed_to_blender_z_up(self):
        self.assertAlmostEqual(SOURCE_TO_BLENDER_ROTATION_X, -math.pi / 2.0)
        self.assertAlmostEqual(SOURCE_TO_BLENDER_SCALE, 0.01)
        self.assertEqual(BLENDER_UNIT_SYSTEM, "METRIC")
        self.assertEqual(BLENDER_LENGTH_UNIT, "MILLIMETERS")
        self.assertAlmostEqual(BLENDER_SCENE_SCALE_LENGTH, 0.001)

    def test_master_object_name_is_deterministic_and_readable(self):
        name = master_object_name(
            "30G", "Base / Structural Plate", "30G-0123456789abcdef"
        )
        self.assertEqual(name, "30G__Base-Structural-Plate__0123456789abcdef")
        self.assertEqual(
            name,
            master_object_name(
                "30G", "Base / Structural Plate", "30G-0123456789abcdef"
            ),
        )

    def test_collection_key_keeps_repeated_assembly_paths_distinct(self):
        left = collection_key(["Assembly", "Frame:1", "Shaft:1"])
        right = collection_key(["Assembly", "Frame:1", "Shaft:2"])
        self.assertNotEqual(left, right)
        self.assertTrue(left.startswith("PIMM_ASM__Shaft-1__"))

    def test_manifest_validation_rejects_duplicate_ids_and_machine_drift(self):
        solid = {
            "stable_id": "30G-0123456789abcdef",
            "assembly_path": ["Assembly"],
            "product_id": "PRODUCT_1",
            "occurrence_id": "OCC_1",
            "solid_index": 1,
            "original_name": "Body",
            "geometry_signature": "abc",
            "interchange_path": __file__,
        }
        manifest = {
            "source": {"machine": "30G", "sha256": "A" * 64},
            "assemblies": [],
            "occurrences": [],
            "non_solid_products": [],
            "solids": [solid, dict(solid)],
            "summary": {
                "solid_count": 2,
                "non_solid_product_count": 0,
            },
        }
        with self.assertRaisesRegex(ValueError, "duplicate stable solid ID"):
            validate_import_manifest(manifest, "30G")

        manifest["solids"] = [solid]
        manifest["summary"]["solid_count"] = 1
        with self.assertRaisesRegex(ValueError, "machine mismatch"):
            validate_import_manifest(manifest, "50G")

    def test_required_provenance_contract_is_complete(self):
        self.assertEqual(
            REQUIRED_OBJECT_PROPERTIES,
            {
                "pimm_stable_id",
                "pimm_machine",
                "pimm_step_sha256",
                "pimm_product_id",
                "pimm_occurrence_id",
                "pimm_assembly_path",
                "pimm_solid_index",
                "pimm_original_cad_name",
                "pimm_geometry_signature",
                "pimm_part_name",
                "pimm_material_state",
                "pimm_source_to_blender_scale",
            },
        )


if __name__ == "__main__":
    unittest.main()
