import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.blender.master_assets.pimm_legacy_inventory import (
    AssetRecord,
    InventoryManifest,
    LEGACY_DISPOSITION_ALIASES,
    inventory_payload,
    inventory_workspace,
    migration_report,
    render_generation_payload,
    _compositor_node_tree,
)
import scripts.blender.master_assets.pimm_legacy_inventory as inventory_module


def _write(root: Path, relative: str, content: bytes = b"fixture") -> Path:
    path = root / Path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class LegacyInventoryContractTests(unittest.TestCase):
    def test_legacy_dispositions_have_explicit_schema_v2_migrations(self):
        self.assertEqual(
            LEGACY_DISPOSITION_ALIASES,
            {
                "keep-authoritative": "authoritative",
                "migrate-scene": "migrate",
                "archive-after-validation": "pending-archive",
            },
        )

    def test_every_supported_asset_is_accounted_once(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            expected = {
                "legacy/PIMM-old.blend",
                "legacy/PIMM-old.blend1",
                "renders/proofs/gen-a/hero.png",
                "renders/final/release-a/hero.webm",
                "renders/passes/gen-a/normal.exr",
                "scripts/render.py",
                "textures/steel.exr",
                "artwork/controller.svg",
                "manifests/release-manifest.json",
                "archive/legacy/ignored-no-longer.blend",
            }
            for relative in expected:
                _write(root, relative)
            _write(root, "tools/.venv/ignored.py")
            _write(root, "tools/pimm-render-py311/pyvenv.cfg")
            _write(root, "tools/pimm-render-py311/Lib/site-packages/ignored.py")
            _write(root, "notes/not-an-asset.txt")

            inventory = inventory_workspace(root)

            paths = [record.path for record in inventory.records]
            self.assertEqual(len(paths), len(set(paths)))
            self.assertEqual(set(paths), set(inventory.discovered_paths))
            self.assertEqual(set(paths), expected)

    def test_inventory_refreshes_stale_authoritative_hash_and_records_metadata(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            master = _write(root, "masters/PIMM-30G-MASTER.blend", b"current-master")
            _write(
                root,
                "manifests/blender-project-inventory.json",
                json.dumps(
                    {
                        "schema": "pimm-asset-inventory/v2",
                        "records": [
                            {
                                "path": "masters/PIMM-30G-MASTER.blend",
                                "sha256": "0" * 64,
                                "blender_inspection": {"object_count": 1},
                            }
                        ],
                    }
                ).encode(),
            )

            inventory = inventory_workspace(root)

            record = next(item for item in inventory.records if item.path == "masters/PIMM-30G-MASTER.blend")
            self.assertEqual(record.sha256, hashlib.sha256(master.read_bytes()).hexdigest().upper())
            self.assertEqual(record.size, len(b"current-master"))
            self.assertEqual(record.kind, "authoritative-master")
            self.assertEqual(record.blender_inspection, {})

    def test_archived_master_named_copy_is_not_authoritative(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            _write(root, "archives/prior/masters/PIMM-30G-MASTER.blend")

            inventory = inventory_workspace(root)

            self.assertEqual(inventory.records[0].kind, "blend-project")

    def test_inventory_records_generation_release_and_dependencies(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            _write(root, "renders/proofs/proof-20260816T100000Z-a1b2c3d/hero.png")
            _write(root, "renders/final/release-2026-08-16-r01/hero.webp")
            _write(root, "renders/product-story/legacy-hero.jpg")
            dependency = _write(root, "textures/brushed.png")
            _write(
                root,
                "manifests/release-manifest.json",
                json.dumps({"texture": str(dependency)}).encode(),
            )

            inventory = inventory_workspace(root)

            proof = next(record for record in inventory.records if record.path.endswith("hero.png"))
            final = next(record for record in inventory.records if record.path.endswith("hero.webp"))
            legacy = next(record for record in inventory.records if record.path.endswith("legacy-hero.jpg"))
            manifest = next(record for record in inventory.records if record.path.endswith("release-manifest.json"))
            self.assertEqual(proof.generation_membership, ("proof-20260816T100000Z-a1b2c3d",))
            self.assertEqual(final.release_membership, ("release-2026-08-16-r01",))
            self.assertEqual(legacy.generation_membership, ("legacy:product-story",))
            self.assertEqual(manifest.dependencies, ("textures/brushed.png",))

    def test_render_generation_payload_contains_only_render_assets(self):
        records = (
            AssetRecord(path="renders/proofs/gen/hero.png", kind="render-image", generation_membership=("gen",)),
            AssetRecord(path="scripts/render.py", kind="script"),
        )

        payload = render_generation_payload(InventoryManifest(records=records, discovered_paths=tuple(r.path for r in records)))

        self.assertEqual(payload["schema"], "pimm-render-generation-inventory/v1")
        self.assertEqual([item["path"] for item in payload["records"]], ["renders/proofs/gen/hero.png"])

    def test_migration_report_lists_scene_content_and_consumers(self):
        record = AssetRecord(
            path="PIMM-product-render-master.blend",
            kind="blend-project",
            unique_content=True,
            consumers=("repo:scripts/render.py:12",),
            proposed_disposition="migrate",
            blender_inspection={
                "cameras": ["Camera"],
                "rigs": ["TurntableRig"],
                "animations": ["HeroTurn"],
                "lights": ["Key"],
                "compositor_nodes": ["AlphaOver"],
            },
        )

        report = migration_report(InventoryManifest(records=(record,), discovered_paths=(record.path,)))

        for expected in ("Camera", "TurntableRig", "HeroTurn", "Key", "AlphaOver", "repo:scripts/render.py:12"):
            self.assertIn(expected, report)
        self.assertIn("after material publication", report)

    def test_delete_disposition_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "delete disposition"):
            AssetRecord(path="legacy.blend1", proposed_disposition="delete")

    def test_blender_52_compositor_group_is_supported(self):
        group = object()
        scene = type("SceneFixture", (), {"compositing_node_group": group})()
        self.assertIs(_compositor_node_tree(scene), group)

    def test_finalize_cli_resolves_repository_package_when_run_by_path(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            manifest_root.mkdir()
            inventory_path = manifest_root / "blender-project-inventory.json"
            inventory_path.write_text(
                json.dumps(inventory_payload(InventoryManifest(records=(), discovered_paths=(), root=str(root)))),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(inventory_module.__file__)),
                    "--finalize",
                    "--root",
                    str(root),
                    "--repo-root",
                    str(root),
                    "--inventory",
                    str(inventory_path),
                    "--render-inventory",
                    str(manifest_root / "render-generation-inventory.json"),
                    "--graph",
                    str(manifest_root / "consumer-graph.json"),
                    "--report",
                    str(manifest_root / "migration.md"),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
