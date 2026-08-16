import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.blender.master_assets.pimm_legacy_inventory import (
    AssetRecord,
    InventoryManifest,
    LEGACY_DISPOSITION_ALIASES,
    atomic_write_json,
    finalize_inventory,
    inventory_payload,
    inventory_workspace,
    migration_report,
    render_generation_payload,
    verify_published_outputs,
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

    def test_generated_outputs_are_excluded_by_exact_schema_path(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            _write(root, "scripts/render.py")
            _write(
                root,
                "archive/manifests/consumer-graph.json",
                b'{"source": "scripts/render.py"}',
            )
            for relative in (
                "manifests/blender-project-inventory.json",
                "manifests/render-generation-inventory.json",
                "manifests/consumer-graph.json",
                "manifests/blender-project-migration-report.md",
            ):
                _write(root, relative, b"generated")

            inventory = inventory_workspace(root)

            self.assertEqual(
                inventory.discovered_paths,
                ("archive/manifests/consumer-graph.json", "scripts/render.py"),
            )
            nested = next(
                record
                for record in inventory.records
                if record.path == "archive/manifests/consumer-graph.json"
            )
            self.assertEqual(nested.dependencies, ("scripts/render.py",))

    def test_finalize_publishes_hash_bound_children_before_inventory_authority(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            _write(root, "scripts/render.py")
            inventory_path = manifest_root / "blender-project-inventory.json"
            render_path = manifest_root / "render-generation-inventory.json"
            graph_path = manifest_root / "consumer-graph.json"
            report_path = manifest_root / "blender-project-migration-report.md"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))

            finalize_inventory(
                inventory_path,
                report_path,
                graph_path,
                render_path,
                Path(repo_text),
                root,
            )

            authority = json.loads(inventory_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(authority["generated_artifacts"]),
                {
                    "manifests/render-generation-inventory.json",
                    "manifests/consumer-graph.json",
                    "manifests/blender-project-migration-report.md",
                },
            )
            for relative, expected in authority["generated_artifacts"].items():
                artifact = root / Path(relative)
                self.assertEqual(expected["size"], artifact.stat().st_size)
                self.assertEqual(expected["sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest().upper())

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

    def test_migration_report_enumerates_every_migrate_and_unresolved_path(self):
        records = (
            AssetRecord(path="textures/orphan.png", kind="texture", proposed_disposition="unresolved"),
            AssetRecord(path="artwork/controller.svg", kind="artwork", proposed_disposition="migrate"),
            AssetRecord(path="renders/approved.webp", kind="render-image", proposed_disposition="active-linked-scene"),
        )

        report = migration_report(
            InventoryManifest(records=records, discovered_paths=tuple(record.path for record in records))
        )

        self.assertIn("- Migrate records: 1", report)
        self.assertIn("- Unresolved records: 1", report)
        self.assertIn("### `textures/orphan.png`", report)
        self.assertIn("### `artwork/controller.svg`", report)
        self.assertNotIn("### `renders/approved.webp`", report)

    def test_asset_record_rejects_absolute_and_parent_escape_paths(self):
        for path in ("../escape.blend", "C:/escape.blend", "/escape.blend"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "relative contained path"):
                AssetRecord(path=path)

    def test_finalize_rejects_empty_manifest_for_nonempty_root(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            _write(root, "scripts/render.py")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(
                inventory_path,
                inventory_payload(InventoryManifest(records=(), discovered_paths=(), root=str(root.resolve()))),
            )

            with self.assertRaisesRegex(RuntimeError, "stale inventory"):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )

    def test_finalize_rejects_replaced_file_with_same_bytes_and_mtime(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            source = _write(root, "scripts/render.py", b"same bytes")
            inventory = inventory_workspace(root)
            original = source.stat()
            source.unlink()
            source.write_bytes(b"same bytes")
            os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory))

            with self.assertRaisesRegex(RuntimeError, "filesystem identity"):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )

    def test_finalize_rejects_file_added_after_scan(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            _write(root, "scripts/render.py")
            inventory = inventory_workspace(root)
            _write(root, "textures/late.png")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory))

            with self.assertRaisesRegex(RuntimeError, "stale inventory path set"):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )

    def test_published_authority_rejects_governed_source_drift(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            source = _write(root, "scripts/render.py", b"original")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            finalize_inventory(
                inventory_path,
                manifest_root / "blender-project-migration-report.md",
                manifest_root / "consumer-graph.json",
                manifest_root / "render-generation-inventory.json",
                Path(repo_text),
                root,
            )
            source.write_bytes(b"mutated!")

            with self.assertRaisesRegex(RuntimeError, "asset .*changed"):
                verify_published_outputs(root)

    def test_finalize_fails_when_governed_bytes_change_at_publish_boundary(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            source = _write(root, "scripts/render.py", b"original")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            real_prepare = inventory_module._prepare_atomic_bytes
            mutated = False

            def mutate_after_final_check(*args, **kwargs):
                nonlocal mutated
                if not mutated:
                    mutated = True
                    source.write_bytes(b"mutated!")
                return real_prepare(*args, **kwargs)

            with patch.object(
                inventory_module,
                "_prepare_atomic_bytes",
                side_effect=mutate_after_final_check,
            ), self.assertRaisesRegex(RuntimeError, "asset .*changed"):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )

    def test_finalize_fails_when_path_set_changes_at_publish_boundary(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            source = _write(root, "scripts/render.py")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            real_prepare = inventory_module._prepare_atomic_bytes
            mutated = False

            def replace_path_set_after_final_check(*args, **kwargs):
                nonlocal mutated
                if not mutated:
                    mutated = True
                    source.unlink()
                    _write(root, "scripts/replacement.py")
                return real_prepare(*args, **kwargs)

            with patch.object(
                inventory_module,
                "_prepare_atomic_bytes",
                side_effect=replace_path_set_after_final_check,
            ), self.assertRaisesRegex(RuntimeError, "stale inventory path set"):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )

    def test_finalize_fails_when_path_identity_changes_at_publish_boundary(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            source = _write(root, "scripts/render.py", b"same bytes")
            original_stat = source.stat()
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            real_prepare = inventory_module._prepare_atomic_bytes
            mutated = False

            def replace_identity_after_final_check(*args, **kwargs):
                nonlocal mutated
                if not mutated:
                    mutated = True
                    source.unlink()
                    source.write_bytes(b"same bytes")
                    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
                return real_prepare(*args, **kwargs)

            with patch.object(
                inventory_module,
                "_prepare_atomic_bytes",
                side_effect=replace_identity_after_final_check,
            ), self.assertRaisesRegex(RuntimeError, "filesystem identity"):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )

    def test_finalize_fails_when_symlink_replaces_path_at_publish_boundary(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text, TemporaryDirectory() as outside_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            source = _write(root, "scripts/render.py")
            external = _write(Path(outside_text), "external.py")
            probe = root / "symlink-probe"
            try:
                probe.symlink_to(external)
                probe.unlink()
            except OSError as error:
                self.skipTest(f"symlink creation unavailable: {error}")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            real_prepare = inventory_module._prepare_atomic_bytes
            mutated = False

            def replace_with_symlink_after_final_check(*args, **kwargs):
                nonlocal mutated
                if not mutated:
                    mutated = True
                    source.unlink()
                    source.symlink_to(external)
                return real_prepare(*args, **kwargs)

            with patch.object(
                inventory_module,
                "_prepare_atomic_bytes",
                side_effect=replace_with_symlink_after_final_check,
            ), self.assertRaisesRegex(ValueError, "reparse|symbolic link"):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )

    def test_publication_cleanup_preserves_competing_generated_output(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            _write(root, "scripts/render.py")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            render_path = manifest_root / "render-generation-inventory.json"
            real_replace = inventory_module._replace_prepared

            def replace_then_compete(destination, temporary, content):
                real_replace(destination, temporary, content)
                if destination == render_path:
                    destination.write_bytes(b"competitor")
                    raise RuntimeError("injected competitor")

            with patch.object(
                inventory_module,
                "_replace_prepared",
                side_effect=replace_then_compete,
            ), self.assertRaisesRegex(RuntimeError, "injected competitor"):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    render_path,
                    Path(repo_text),
                    root,
                )

            self.assertEqual(render_path.read_bytes(), b"competitor")

    def test_finalize_rejects_competing_publication_lock_without_writes(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            _write(root, "scripts/render.py")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            original = inventory_path.read_bytes()
            _write(root, "manifests/.pimm-inventory-publish.lock", b"competitor")

            with self.assertRaisesRegex(RuntimeError, "publication lock"):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )
            self.assertEqual(inventory_path.read_bytes(), original)

    def test_finalize_rejects_arbitrary_output_destination(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text, TemporaryDirectory() as outside_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            _write(root, "scripts/render.py")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            outside_report = Path(outside_text) / "report.md"

            with self.assertRaisesRegex(ValueError, "canonical generated output"):
                finalize_inventory(
                    inventory_path,
                    outside_report,
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )
            self.assertFalse(outside_report.exists())

    def test_inventory_rejects_symlinked_asset_without_following_it(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            target = _write(root, "targets/real.blend")
            alias = root / "alias.blend"
            try:
                alias.symlink_to(target)
            except OSError as error:
                self.skipTest(f"symlink creation unavailable: {error}")

            with self.assertRaisesRegex(ValueError, "reparse|symbolic link"):
                inventory_workspace(root)

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
                json.dumps(inventory_payload(inventory_workspace(root))),
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
                    str(manifest_root / "blender-project-migration-report.md"),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
