import unittest
from pathlib import Path

from scripts.blender.master_assets.pimm_legacy_inventory import (
    ALLOWED_DISPOSITIONS,
    classify_project,
)


class LegacyInventoryContractTests(unittest.TestCase):
    def test_dispositions_never_include_delete(self):
        self.assertEqual(
            ALLOWED_DISPOSITIONS,
            {
                "keep-authoritative",
                "migrate-scene",
                "archive-after-validation",
                "review",
            },
        )
        self.assertNotIn("delete", ALLOWED_DISPOSITIONS)

    def test_new_masters_and_material_library_are_authoritative(self):
        for name in (
            "PIMM-30G-MASTER.blend",
            "PIMM-50G-MASTER.blend",
            "PIMM-MATERIAL-LIBRARY.blend",
        ):
            self.assertEqual(
                classify_project(Path("masters") / name, [], None, False),
                "keep-authoritative",
            )

    def test_backups_and_duplicate_non_consumers_archive_only_after_validation(self):
        self.assertEqual(
            classify_project(Path("PIMM-old.blend1"), [], None, False),
            "archive-after-validation",
        )
        self.assertEqual(
            classify_project(Path("PIMM-copy.blend"), [], "duplicate-group", False),
            "archive-after-validation",
        )

    def test_consumed_scene_requires_migration_even_if_backup_named(self):
        self.assertEqual(
            classify_project(
                Path("PIMM-product-story.blend1"),
                ["scripts/render-story.py"],
                "duplicate-group",
                False,
            ),
            "migrate-scene",
        )

    def test_unique_unconsumed_project_remains_review(self):
        self.assertEqual(
            classify_project(Path("PIMM-experiment.blend"), [], None, True),
            "review",
        )


if __name__ == "__main__":
    unittest.main()
