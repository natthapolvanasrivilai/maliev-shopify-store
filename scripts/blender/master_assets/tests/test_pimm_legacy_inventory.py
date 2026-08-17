import hashlib
import json
import os
import subprocess
import sys
import unittest
from collections.abc import Callable
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


def _finalize_with_postcommit_hash_action(
    root: Path,
    repo_root: Path,
    source: Path,
    action: Callable[[], None],
) -> None:
    """Inject one source race immediately after its postcommit hash read."""

    manifest_root = root / "manifests"
    inventory_path = manifest_root / "blender-project-inventory.json"
    real_sha256_file = inventory_module.sha256_file
    source_hash_reads = 0

    def hash_then_act(path: Path) -> str:
        nonlocal source_hash_reads
        digest = real_sha256_file(path)
        if Path(path) == source:
            source_hash_reads += 1
            if source_hash_reads == 2:
                action()
        return digest

    with patch.object(inventory_module, "sha256_file", side_effect=hash_then_act):
        finalize_inventory(
            inventory_path,
            manifest_root / "blender-project-migration-report.md",
            manifest_root / "consumer-graph.json",
            manifest_root / "render-generation-inventory.json",
            repo_root,
            root,
        )


class LegacyInventoryContractTests(unittest.TestCase):
    def test_published_authority_allows_only_the_exact_archived_source_paths_to_be_missing(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            archived = _write(root, "legacy/PIMM-old.blend1", b"recovery")
            remaining = _write(root, "legacy/PIMM-old.blend", b"current")
            manifest_root = root / "manifests"
            atomic_write_json(
                manifest_root / "blender-project-inventory.json",
                inventory_payload(inventory_workspace(root)),
            )
            finalize_inventory(
                manifest_root / "blender-project-inventory.json",
                manifest_root / "blender-project-migration-report.md",
                manifest_root / "consumer-graph.json",
                manifest_root / "render-generation-inventory.json",
                Path(repo_text),
                root,
            )
            archived.unlink()

            authority = verify_published_outputs(
                root, permitted_missing_paths=("legacy/PIMM-old.blend1",)
            )
            self.assertTrue(authority["publication_id"])
            with self.assertRaisesRegex(RuntimeError, "stale inventory path set"):
                verify_published_outputs(root)

            remaining.write_bytes(b"drifted")
            with self.assertRaisesRegex(RuntimeError, "metadata changed|content hash changed"):
                verify_published_outputs(
                    root, permitted_missing_paths=("legacy/PIMM-old.blend1",)
                )

    def test_published_authority_rejects_any_unplanned_missing_or_extra_path(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            planned = _write(root, "legacy/PIMM-old.blend1", b"recovery")
            unplanned = _write(root, "legacy/keep.blend", b"keep")
            manifest_root = root / "manifests"
            atomic_write_json(
                manifest_root / "blender-project-inventory.json",
                inventory_payload(inventory_workspace(root)),
            )
            finalize_inventory(
                manifest_root / "blender-project-inventory.json",
                manifest_root / "blender-project-migration-report.md",
                manifest_root / "consumer-graph.json",
                manifest_root / "render-generation-inventory.json",
                Path(repo_text),
                root,
            )
            planned.unlink()
            unplanned.unlink()
            with self.assertRaisesRegex(RuntimeError, "stale inventory path set"):
                verify_published_outputs(
                    root, permitted_missing_paths=("legacy/PIMM-old.blend1",)
                )

            unplanned.write_bytes(b"keep")
            _write(root, "legacy/unpublished.blend", b"extra")
            with self.assertRaisesRegex(RuntimeError, "stale inventory path set"):
                verify_published_outputs(
                    root, permitted_missing_paths=("legacy/PIMM-old.blend1",)
                )

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

    def test_finalize_rejects_byte_replacement_after_postcommit_hash_without_deleting_competitor(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            source = _write(root, "scripts/render.py", b"original")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            render_path = manifest_root / "render-generation-inventory.json"

            def replace_source_and_output() -> None:
                source.write_bytes(b"mutated source bytes")
                render_path.write_bytes(b"competitor-owned-output")

            with self.assertRaisesRegex(
                RuntimeError, "asset metadata changed after hash"
            ):
                _finalize_with_postcommit_hash_action(
                    root,
                    Path(repo_text),
                    source,
                    replace_source_and_output,
                )

            self.assertEqual(render_path.read_bytes(), b"competitor-owned-output")

    def test_finalize_rejects_delete_after_postcommit_hash(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            source = _write(root, "scripts/render.py", b"original")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))

            with self.assertRaisesRegex(
                RuntimeError, "asset disappeared after hash"
            ):
                _finalize_with_postcommit_hash_action(
                    root,
                    Path(repo_text),
                    source,
                    source.unlink,
                )

    def test_finalize_rejects_identity_swap_after_postcommit_hash(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            source = _write(root, "scripts/render.py", b"same bytes")
            original_stat = source.stat()
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))

            def swap_identity() -> None:
                source.unlink()
                source.write_bytes(b"same bytes")
                os.utime(
                    source,
                    ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
                )

            with self.assertRaisesRegex(
                RuntimeError, "asset filesystem identity changed after hash"
            ):
                _finalize_with_postcommit_hash_action(
                    root,
                    Path(repo_text),
                    source,
                    swap_identity,
                )

    def test_closing_path_set_rejects_new_delete_and_rename_races(self):
        for race in ("new", "delete", "rename"):
            with self.subTest(race=race), TemporaryDirectory() as root_text:
                root = Path(root_text)
                source = _write(root, "scripts/render.py", b"original")
                inventory = inventory_workspace(root)
                real_discover = inventory_module._discover
                discovery_calls = 0

                def discover_with_closing_race(value: Path):
                    nonlocal discovery_calls
                    discovery_calls += 1
                    if discovery_calls == 2:
                        if race == "new":
                            _write(root, "textures/late.png")
                        elif race == "delete":
                            source.unlink()
                        else:
                            source.rename(root / "scripts/renamed.py")
                    return real_discover(value)

                with patch.object(
                    inventory_module,
                    "_discover",
                    side_effect=discover_with_closing_race,
                ), self.assertRaisesRegex(RuntimeError, "stale inventory path set"):
                    inventory_module._verify_inventory_fresh(inventory, root)

    def test_tail_create_after_last_discovery_fails_current_verification(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            _write(root, "scripts/render.py", b"original")
            inventory = inventory_workspace(root)
            real_discover = inventory_module._discover
            discovery_calls = 0

            def discover_then_create(value: Path):
                nonlocal discovery_calls
                discovered = real_discover(value)
                discovery_calls += 1
                if discovery_calls == 3:
                    _write(root, "textures/tail.png")
                return discovered

            with patch.object(
                inventory_module,
                "_discover",
                side_effect=discover_then_create,
            ), self.assertRaisesRegex(
                RuntimeError, "governed directory changed during verification"
            ):
                inventory_module._verify_inventory_fresh(inventory, root)

    def test_kernel_boundary_rejects_every_tail_filesystem_event(self):
        for race in (
            "create",
            "delete",
            "rename",
            "byte-write",
            "identity-replacement",
            "nested-generated-basename",
            "unknown-path",
        ):
            with self.subTest(race=race), TemporaryDirectory() as root_text:
                root = Path(root_text)
                source = _write(root, "scripts/render.py", b"same bytes")
                original_stat = source.stat()
                inventory = inventory_workspace(root)
                real_state = inventory_module._freshness_state
                state_calls = 0

                def state_then_race(*args, **kwargs):
                    nonlocal state_calls
                    state = real_state(*args, **kwargs)
                    state_calls += 1
                    if state_calls == 4:
                        if race == "create":
                            _write(root, "textures/tail.png")
                        elif race == "delete":
                            source.unlink()
                        elif race == "rename":
                            source.rename(root / "scripts/renamed.py")
                        elif race == "byte-write":
                            source.write_bytes(b"new bytes!")
                        elif race == "identity-replacement":
                            source.unlink()
                            source.write_bytes(b"same bytes")
                            os.utime(
                                source,
                                ns=(
                                    original_stat.st_atime_ns,
                                    original_stat.st_mtime_ns,
                                ),
                            )
                        elif race == "nested-generated-basename":
                            _write(root, "archive/manifests/consumer-graph.json")
                        else:
                            _write(root, "notes.tmp")
                    return state

                with patch.object(
                    inventory_module,
                    "_freshness_state",
                    side_effect=state_then_race,
                ), self.assertRaisesRegex(
                    RuntimeError, "governed directory changed during verification"
                ):
                    inventory_module._verify_inventory_fresh(inventory, root)

    def test_kernel_boundary_rejects_competitors_using_publication_names(self):
        competitor_paths = (
            "manifests/blender-project-inventory.json",
            "manifests/render-generation-inventory.json",
            "manifests/consumer-graph.json",
            "manifests/blender-project-migration-report.md",
            "manifests/.pimm-inventory-publish.lock",
            "manifests/.blender-project-inventory.json.tmp.0123456789abcdef0123456789abcdef",
            "manifests/.render-generation-inventory.json.tmp.0123456789abcdef0123456789abcdef",
            "manifests/.consumer-graph.json.tmp.0123456789abcdef0123456789abcdef",
            "manifests/.blender-project-migration-report.md.tmp.0123456789abcdef0123456789abcdef",
        )
        for relative in competitor_paths:
            with (
                self.subTest(relative=relative),
                TemporaryDirectory() as root_text,
                TemporaryDirectory() as repo_text,
            ):
                root = Path(root_text)
                manifest_root = root / "manifests"
                _write(root, "scripts/render.py", b"original")
                inventory_path = manifest_root / "blender-project-inventory.json"
                atomic_write_json(
                    inventory_path,
                    inventory_payload(inventory_workspace(root)),
                )
                real_state = inventory_module._freshness_state
                state_calls = 0
                competitor = root / Path(relative)
                competitor_bytes = b"competitor-owned bytes"

                def state_then_write(*args, **kwargs):
                    nonlocal state_calls
                    state = real_state(*args, **kwargs)
                    state_calls += 1
                    if state_calls == 4:
                        _write(root, relative, competitor_bytes)
                    return state

                with patch.object(
                    inventory_module,
                    "_freshness_state",
                    side_effect=state_then_write,
                ), self.assertRaisesRegex(
                    RuntimeError, "governed directory changed during verification"
                ):
                    finalize_inventory(
                        inventory_path,
                        manifest_root / "blender-project-migration-report.md",
                        manifest_root / "consumer-graph.json",
                        manifest_root / "render-generation-inventory.json",
                        Path(repo_text),
                        root,
                    )
                self.assertEqual(competitor.read_bytes(), competitor_bytes)

    def test_legitimate_finalizer_writes_only_between_watcher_windows(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            _write(root, "scripts/render.py", b"original")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(
                inventory_path,
                inventory_payload(inventory_workspace(root)),
            )

            finalize_inventory(
                inventory_path,
                manifest_root / "blender-project-migration-report.md",
                manifest_root / "consumer-graph.json",
                manifest_root / "render-generation-inventory.json",
                Path(repo_text),
                root,
            )

            authority = verify_published_outputs(root)
            self.assertTrue(authority["publication_id"])
            self.assertFalse((manifest_root / ".pimm-inventory-publish.lock").exists())
            self.assertEqual(tuple(manifest_root.glob(".*.tmp.*")), ())

    def test_kernel_boundary_fails_closed_on_overflow_status_and_non_windows(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            watcher = inventory_module._WindowsDirectoryChangeAuthority(root)
            with patch.object(watcher, "_wait", return_value=0), patch.object(
                watcher, "_get_result", return_value=True
            ), self.assertRaisesRegex(RuntimeError, "watcher overflow"):
                watcher.assert_quiet()
            watcher.close()

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            watcher = inventory_module._WindowsDirectoryChangeAuthority(root)
            with patch.object(
                watcher, "_wait", return_value=0xFFFFFFFF
            ), self.assertRaisesRegex(RuntimeError, "ambiguous .* watcher status"):
                watcher.assert_quiet()
            watcher.close()

        with patch.object(inventory_module.os, "name", "posix"), self.assertRaisesRegex(
            RuntimeError, "kernel directory change authority is required"
        ):
            inventory_module._directory_change_authority(Path("governed-root"))

    def test_finalizer_postcommit_watcher_rejects_tail_create(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as repo_text:
            root = Path(root_text)
            manifest_root = root / "manifests"
            _write(root, "scripts/render.py", b"original")
            inventory_path = manifest_root / "blender-project-inventory.json"
            atomic_write_json(inventory_path, inventory_payload(inventory_workspace(root)))
            real_state = inventory_module._freshness_state
            state_calls = 0

            def state_then_create(*args, **kwargs):
                nonlocal state_calls
                state = real_state(*args, **kwargs)
                state_calls += 1
                if state_calls == 12:
                    _write(root, "textures/postcommit-tail.png")
                return state

            with patch.object(
                inventory_module,
                "_freshness_state",
                side_effect=state_then_create,
            ), self.assertRaisesRegex(
                RuntimeError, "governed directory changed during verification"
            ):
                finalize_inventory(
                    inventory_path,
                    manifest_root / "blender-project-migration-report.md",
                    manifest_root / "consumer-graph.json",
                    manifest_root / "render-generation-inventory.json",
                    Path(repo_text),
                    root,
                )

    def test_drift_after_successful_verification_is_rejected_by_next_verification(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            source = _write(root, "scripts/render.py", b"original")
            inventory = inventory_workspace(root)

            inventory_module._verify_inventory_fresh(inventory, root)
            source.write_bytes(b"later external drift")

            with self.assertRaisesRegex(RuntimeError, "asset .*changed"):
                inventory_module._verify_inventory_fresh(inventory, root)

    def test_drift_after_kernel_poll_is_later_drift_rejected_by_next_verification(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            source = _write(root, "scripts/render.py", b"original")
            inventory = inventory_workspace(root)
            real_poll = inventory_module._WindowsDirectoryChangeAuthority.assert_quiet
            mutated = False

            def mutate_after_poll(authority):
                nonlocal mutated
                real_poll(authority)
                if not mutated:
                    mutated = True
                    source.write_bytes(b"later external drift")

            with patch.object(
                inventory_module._WindowsDirectoryChangeAuthority,
                "assert_quiet",
                mutate_after_poll,
            ):
                inventory_module._verify_inventory_fresh(inventory, root)

            with self.assertRaisesRegex(RuntimeError, "asset .*changed"):
                inventory_module._verify_inventory_fresh(inventory, root)

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
