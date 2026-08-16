from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.blender.master_assets.pimm_legacy_inventory import AssetRecord, InventoryManifest
from scripts.blender.pimm_production.consumer_graph import ConsumerGraph
from scripts.blender.pimm_production.archive_plan import (
    ArchivePlan,
    apply_archive_plan,
    build_archive_plan,
    restore_archive_batch,
    validate_archive_plan,
)
import scripts.blender.pimm_production.archive_plan as archive_module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _record(path: Path, root: Path, **overrides: object) -> AssetRecord:
    status = path.stat(follow_symlinks=False)
    values: dict[str, object] = {
        "path": path.relative_to(root).as_posix(),
        "size": status.st_size,
        "mtime_ns": status.st_mtime_ns,
        "sha256": _sha256(path),
        "kind": "blend-recovery" if path.suffix.casefold() == ".blend1" else "blend-project",
        "unique_content": False,
        "proposed_disposition": "pending-archive" if path.suffix.casefold() == ".blend1" else "unresolved",
        "filesystem_identity": (status.st_dev, status.st_ino, status.st_ctime_ns, status.st_size),
    }
    values.update(overrides)
    return AssetRecord(**values)


@dataclass(frozen=True)
class ArchiveTestFixture:
    plan: ArchivePlan
    inventory: InventoryManifest
    graph: ConsumerGraph
    plan_path: Path
    stale_approval_path: Path
    manifest_path: Path
    original_sha256: str


def _write_plan(path: Path, plan: ArchivePlan) -> None:
    path.write_text(
        json.dumps(plan.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_approval(path: Path, plan_path: Path, plan: ArchivePlan, digest: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "pimm-archive-plan-approval/v1",
                "schema_version": 1,
                "batch_id": plan.batch_id,
                "plan_path": str(plan_path.resolve()),
                "approved_archive_plan_sha256": digest,
                "decision": "approved",
                "authority": "owner",
                "owner": "fixture-owner",
                "created_at_utc": "2026-08-17T00:00:00Z",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def archive_test_fixture(
    root: Path,
    consumers: tuple[str, ...],
    unique_content: bool,
) -> ArchiveTestFixture:
    active_root = root / "blender-product-renders"
    source = active_root / "legacy" / "PIMM-old.blend1"
    replacement_path = active_root / "legacy" / "PIMM-old.blend"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"recovery-copy")
    replacement_path.write_bytes(b"current-source")
    source_record = _record(
        source,
        active_root,
        consumers=consumers,
        unique_content=unique_content,
    )
    replacement_record = _record(replacement_path, active_root)
    inventory = InventoryManifest(
        records=(source_record, replacement_record),
        discovered_paths=(source_record.path, replacement_record.path),
        root=str(active_root.resolve()),
        root_identity=(active_root.stat().st_dev, active_root.stat().st_ino),
    )
    graph = ConsumerGraph(
        consumers={source_record.path: consumers, replacement_record.path: ()},
        producers={source_record.path: (), replacement_record.path: ()},
    )
    safe_source_record = replace(source_record, consumers=(), unique_content=False)
    safe_inventory = InventoryManifest(
        records=(safe_source_record, replacement_record),
        discovered_paths=(safe_source_record.path, replacement_record.path),
        root=inventory.root,
        root_identity=inventory.root_identity,
    )
    safe_graph = ConsumerGraph(
        consumers={safe_source_record.path: (), replacement_record.path: ()},
        producers={safe_source_record.path: (), replacement_record.path: ()},
    )
    plan = build_archive_plan(safe_inventory, safe_graph, "legacy-recovery-files-01")
    plan_path = root / "plan.json"
    _write_plan(plan_path, plan)
    stale_approval_path = root / "stale-approval.json"
    _write_approval(stale_approval_path, plan_path, plan, "0" * 64)

    restore_root = root / "restore-archive"
    archived = restore_root / "legacy" / source.name
    archived.parent.mkdir(parents=True)
    archived.write_bytes(source.read_bytes())
    os.utime(archived, ns=(source_record.mtime_ns, source_record.mtime_ns))
    manifest_path = restore_root / "archive-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "pimm-archive-manifest/v1",
                "schema_version": 1,
                "batch_id": plan.batch_id,
                "status": "archived",
                "active_root": str(active_root.resolve()),
                "archive_root": str(restore_root.resolve()),
                "plan_path": str(plan_path.resolve()),
                "plan_sha256": _sha256(plan_path),
                "approval_path": str(stale_approval_path.resolve()),
                "approval_sha256": _sha256(stale_approval_path),
                "items": [
                    {
                        "source": str(source.resolve()),
                        "destination": str(archived.resolve()),
                        "sha256": source_record.sha256,
                        "size": source_record.size,
                        "mtime_ns": source_record.mtime_ns,
                        "move_mode": "fixture",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return ArchiveTestFixture(
        plan=plan,
        inventory=inventory,
        graph=graph,
        plan_path=plan_path,
        stale_approval_path=stale_approval_path,
        manifest_path=manifest_path,
        original_sha256=source_record.sha256,
    )


class ArchivePlanTests(unittest.TestCase):
    def test_consumer_or_unique_content_blocks_move(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), ("theme.liquid",), True)
            errors = validate_archive_plan(fixture.plan, fixture.inventory, fixture.graph)
            self.assertIn("active consumer", "\n".join(errors))
            self.assertIn("unique content not migrated", "\n".join(errors))

    def test_apply_requires_exact_owner_approved_plan_hash(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            with self.assertRaisesRegex(ValueError, "approved archive-plan SHA-256"):
                apply_archive_plan(fixture.plan_path, fixture.stale_approval_path)

    def test_restore_recreates_original_path_and_hash(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            source.unlink()
            result = restore_archive_batch(fixture.manifest_path)
            self.assertEqual(result.restored[0].sha256, fixture.original_sha256)
            self.assertEqual(_sha256(source), fixture.original_sha256)

    def test_destination_must_be_outside_active_root(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            item = fixture.plan.items[0]
            unsafe_root = Path(fixture.plan.active_root) / "pending-delete"
            unsafe = replace(
                fixture.plan,
                archive_root=str(unsafe_root),
                items=(replace(item, destination=str(unsafe_root / "legacy" / "PIMM-old.blend1")),),
            )
            self.assertIn("outside active root", "\n".join(validate_archive_plan(unsafe, fixture.inventory, fixture.graph)))

    def test_destination_collision_blocks_apply_without_mutation(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            destination = Path(fixture.plan.items[0].destination)
            destination.parent.mkdir(parents=True)
            destination.write_bytes(b"competitor")
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            with self.assertRaisesRegex(ValueError, "destination already exists"):
                apply_archive_plan(fixture.plan_path, approval)
            self.assertEqual(destination.read_bytes(), b"competitor")
            self.assertTrue(Path(fixture.plan.items[0].source).exists())

    def test_source_hash_drift_blocks_apply(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            source.write_bytes(b"changed bytes")
            os.utime(source, ns=(fixture.plan.items[0].mtime_ns,) * 2)
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            with self.assertRaisesRegex(ValueError, "source hash drift"):
                apply_archive_plan(fixture.plan_path, approval)

    def test_same_byte_identity_drift_blocks_apply(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            temporary = source.with_suffix(".replacement")
            temporary.write_bytes(source.read_bytes())
            os.utime(temporary, ns=(fixture.plan.items[0].mtime_ns,) * 2)
            os.replace(temporary, source)
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            with self.assertRaisesRegex(ValueError, "source identity drift"):
                apply_archive_plan(fixture.plan_path, approval)

    def test_partial_directory_inventory_blocks_apply(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            (source.parent / "late-file.txt").write_text("late", encoding="utf-8")
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            with self.assertRaisesRegex(ValueError, "directory inventory is incomplete"):
                apply_archive_plan(fixture.plan_path, approval)

    def test_cross_volume_partial_copy_rolls_back_without_removing_source(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            destination = Path(fixture.plan.items[0].destination)
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))

            def partial_copy(_source: Path, temporary: Path, _item: object) -> None:
                temporary.write_bytes(b"partial")
                raise OSError("injected cross-volume copy failure")

            with patch.object(archive_module, "_same_volume", return_value=False), patch.object(
                archive_module, "_copy_source_to_temporary", side_effect=partial_copy
            ):
                with self.assertRaisesRegex(OSError, "injected cross-volume copy failure"):
                    apply_archive_plan(fixture.plan_path, approval)
            self.assertEqual(_sha256(source), fixture.original_sha256)
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob(".*.archive-copy-*")), [])

    def test_missing_timestamp_is_rejected(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            item = replace(fixture.plan.items[0], mtime_ns=0)
            invalid = replace(fixture.plan, items=(item,))
            self.assertIn("missing timestamp", "\n".join(validate_archive_plan(invalid, fixture.inventory, fixture.graph)))

    def test_plan_containing_delete_is_rejected_before_mutation(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            payload = fixture.plan.to_payload()
            payload["items"][0]["action"] = "delete"
            fixture.plan_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            with self.assertRaisesRegex(ValueError, "delete action is forbidden"):
                apply_archive_plan(fixture.plan_path, approval)
            self.assertTrue(Path(fixture.plan.items[0].source).exists())

    def test_manifest_tmp_exists_before_first_move_and_final_manifest_is_atomic(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            observed = []
            original = archive_module._move_item

            def observing_move(item: object, manifest_tmp: Path) -> str:
                observed.append(manifest_tmp.exists())
                return original(item, manifest_tmp)

            with patch.object(archive_module, "_move_item", side_effect=observing_move):
                result = apply_archive_plan(fixture.plan_path, approval)
            self.assertEqual(observed, [True])
            self.assertTrue(result.manifest_path.is_file())
            self.assertFalse(result.manifest_path.with_suffix(".json.tmp").exists())
            self.assertFalse(Path(fixture.plan.items[0].source).exists())

    def test_rollback_preserves_competitor_destination(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            destination = Path(fixture.plan.items[0].destination)

            def competing_move(_item: object, _manifest_tmp: Path) -> str:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"competitor")
                raise OSError("injected move failure")

            with patch.object(archive_module, "_move_item", side_effect=competing_move):
                with self.assertRaisesRegex(OSError, "injected move failure"):
                    apply_archive_plan(fixture.plan_path, approval)
            self.assertEqual(destination.read_bytes(), b"competitor")
            self.assertTrue(Path(fixture.plan.items[0].source).exists())

    def test_reparse_source_is_rejected_when_supported(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            target = Path(root) / "outside.blend1"
            target.write_bytes(source.read_bytes())
            source.unlink()
            try:
                source.symlink_to(target)
            except OSError as error:
                self.skipTest(f"symlinks unavailable: {error}")
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            with self.assertRaisesRegex(ValueError, "reparse"):
                apply_archive_plan(fixture.plan_path, approval)

    def test_protected_and_non_pending_records_never_enter_plan(self):
        with TemporaryDirectory() as root:
            root_path = Path(root)
            active = root_path / "active"
            active.mkdir()
            paths = []
            records = []
            for name, kind, disposition in (
                ("script.py", "script", "pending-archive"),
                ("master.blend1", "blend-recovery", "migrate"),
                ("approved.blend1", "blend-recovery", "pending-archive"),
            ):
                path = active / name
                path.write_bytes(name.encode())
                paths.append(path)
                records.append(
                    _record(
                        path,
                        active,
                        kind=kind,
                        proposed_disposition=disposition,
                        release_membership=("release-2026-08-17-r01",) if name.startswith("approved") else (),
                    )
                )
            inventory = InventoryManifest(tuple(records), tuple(record.path for record in records), str(active.resolve()))
            graph = ConsumerGraph(consumers={record.path: () for record in records})
            plan = build_archive_plan(inventory, graph, "protected-records")
            self.assertEqual(plan.items, ())


if __name__ == "__main__":
    unittest.main()
