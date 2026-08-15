import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.blender.master_assets.pimm_step_manifest import (
    EXPECTED_SOURCES,
    stable_solid_id,
    validate_manifest_structure,
    validate_source_identity,
)


class StepManifestContractTests(unittest.TestCase):
    def test_stable_id_is_deterministic(self):
        first = stable_solid_id("30G", "0:1/0:4", "PRODUCT_18", 3)
        second = stable_solid_id("30G", "0:1/0:4", "PRODUCT_18", 3)

        self.assertEqual(first, second)
        self.assertRegex(first, r"^30G-[0-9a-f]{16}$")

    def test_stable_id_changes_with_solid_identity(self):
        first = stable_solid_id("50G", "0:1/0:4", "PRODUCT_18", 3)
        second = stable_solid_id("50G", "0:1/0:4", "PRODUCT_18", 4)

        self.assertNotEqual(first, second)

    def test_source_identity_rejects_hash_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "machine.step")
            source.write_bytes(b"STEP")
            with self.assertRaisesRegex(ValueError, "source SHA-256 mismatch"):
                validate_source_identity(
                    source,
                    expected_size=4,
                    expected_sha256="0" * 64,
                )

    def test_source_identity_accepts_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "machine.step")
            source.write_bytes(b"STEP")
            result = validate_source_identity(
                source,
                expected_size=4,
                expected_sha256=hashlib.sha256(b"STEP").hexdigest(),
            )

        self.assertEqual(result["size"], 4)

    def test_expected_authoritative_sources_are_exact(self):
        self.assertEqual(EXPECTED_SOURCES["30G"]["size"], 116_623_783)
        self.assertEqual(
            EXPECTED_SOURCES["30G"]["sha256"],
            "2EA1C86BD15386717BB53F02B61490ABB2F8DB45E7D70ED668AF29203A4E2205",
        )
        self.assertEqual(EXPECTED_SOURCES["50G"]["size"], 116_854_560)
        self.assertEqual(
            EXPECTED_SOURCES["50G"]["sha256"],
            "A6CB2CAA65CA2002A3A18D9C341833506764D55F7ED840BC9095ED8AF7386FEF",
        )

    def test_manifest_rejects_duplicate_or_missing_solid_interchange(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mesh = root / "solid.glb"
            mesh.write_bytes(b"glTF")
            solid = {
                "stable_id": "30G-0123456789abcdef",
                "assembly_path": ["Root"],
                "product_id": "PRODUCT_1",
                "occurrence_id": "OCC_1",
                "solid_index": 1,
                "original_name": "Body",
                "geometry_signature": "abc",
                "interchange_path": str(mesh),
            }
            manifest = {
                "source": {"machine": "30G"},
                "assemblies": [{"path": ["Root"]}],
                "occurrences": [{"id": "OCC_1"}],
                "non_solid_products": [],
                "solids": [solid, dict(solid)],
                "summary": {"solid_count": 2, "non_solid_product_count": 0},
            }

            with self.assertRaisesRegex(ValueError, "duplicate stable solid ID"):
                validate_manifest_structure(manifest)

            manifest["solids"] = [dict(solid, interchange_path=str(root / "missing.glb"))]
            manifest["summary"]["solid_count"] = 1
            with self.assertRaisesRegex(ValueError, "interchange file is missing"):
                validate_manifest_structure(manifest)

    def test_manifest_requires_explicit_non_solid_product_accounting(self):
        manifest = {
            "source": {"machine": "30G"},
            "assemblies": [],
            "occurrences": [],
            "solids": [],
            "summary": {"solid_count": 0, "non_solid_product_count": 0},
        }
        with self.assertRaisesRegex(ValueError, "non_solid_products"):
            validate_manifest_structure(manifest)

        manifest["non_solid_products"] = [
            {
                "product_id": "0:1:1:56",
                "occurrence_id": "0:1:1:54:2",
                "original_name": "_FJRPDdummy",
                "topology": {
                    "solids": 0,
                    "shells": 0,
                    "faces": 0,
                    "wires": 0,
                    "edges": 0,
                    "vertices": 0,
                },
            }
        ]
        manifest["summary"]["non_solid_product_count"] = 1
        validate_manifest_structure(manifest)


if __name__ == "__main__":
    unittest.main()
