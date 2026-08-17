from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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
    authority: object


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
    item_count: int = 1,
) -> ArchiveTestFixture:
    active_root = root / "blender-product-renders"
    legacy_root = active_root / "legacy"
    legacy_root.mkdir(parents=True)
    source_records: list[AssetRecord] = []
    replacement_records: list[AssetRecord] = []
    sources: list[Path] = []
    for index in range(item_count):
        suffix = "" if index == 0 else f"-{index + 1}"
        source = legacy_root / f"PIMM-old{suffix}.blend1"
        replacement_path = legacy_root / f"PIMM-old{suffix}.blend"
        source.write_bytes(f"recovery-copy-{index}".encode())
        replacement_path.write_bytes(f"current-source-{index}".encode())
        sources.append(source)
        source_records.append(
            _record(
                source,
                active_root,
                consumers=consumers,
                unique_content=unique_content,
            )
        )
        replacement_records.append(_record(replacement_path, active_root))
    records = tuple(source_records + replacement_records)
    inventory = InventoryManifest(
        records=records,
        discovered_paths=tuple(record.path for record in records),
        root=str(active_root.resolve()),
        root_identity=(active_root.stat().st_dev, active_root.stat().st_ino),
    )
    graph = ConsumerGraph(
        consumers={record.path: consumers if record in source_records else () for record in records},
        producers={record.path: () for record in records},
    )
    safe_source_records = tuple(
        replace(record, consumers=(), unique_content=False) for record in source_records
    )
    safe_records = safe_source_records + tuple(replacement_records)
    safe_inventory = InventoryManifest(
        records=safe_records,
        discovered_paths=tuple(record.path for record in safe_records),
        root=inventory.root,
        root_identity=inventory.root_identity,
    )
    safe_graph = ConsumerGraph(
        consumers={record.path: () for record in safe_records},
        producers={record.path: () for record in safe_records},
    )
    plan = build_archive_plan(safe_inventory, safe_graph, "legacy-recovery-files-01")
    render_payload = {
        "schema": "pimm-render-generation-inventory/v1",
        "publication_id": "fixture-publication",
        "root": safe_inventory.root,
        "records": [],
        "generations": {},
        "releases": {},
    }
    render_sha256 = hashlib.sha256(
        (json.dumps(render_payload, indent=2, sort_keys=True) + "\n").encode()
    ).hexdigest().upper()
    plan = replace(
        plan,
        publication_id="fixture-publication",
        render_inventory_sha256=render_sha256,
    )
    authority = SimpleNamespace(
        publication_id=plan.publication_id,
        inventory=safe_inventory,
        graph=safe_graph,
        render_payload=render_payload,
        inventory_sha256=plan.inventory_sha256,
        consumer_graph_sha256=plan.consumer_graph_sha256,
        render_inventory_sha256=plan.render_inventory_sha256,
        root_identity=plan.inventory_root_identity,
        active_root=Path(plan.active_root),
        production=False,
    )
    plan_path = root / "plan.json"
    _write_plan(plan_path, plan)
    stale_approval_path = root / "stale-approval.json"
    _write_approval(stale_approval_path, plan_path, plan, "0" * 64)
    restore_approval_path = root / "restore-approval.json"
    _write_approval(restore_approval_path, plan_path, plan, _sha256(plan_path))

    manifest_path = Path(plan.archive_root) / "archive-manifest.json"
    return ArchiveTestFixture(
        plan=plan,
        inventory=inventory,
        graph=graph,
        plan_path=plan_path,
        stale_approval_path=stale_approval_path,
        manifest_path=manifest_path,
        original_sha256=source_records[0].sha256,
        authority=authority,
    )


def _prepare_restore_manifest(fixture: ArchiveTestFixture, *, status: str = "archived") -> Path:
    source = Path(fixture.plan.items[0].source)
    archived = Path(fixture.plan.items[0].destination)
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_bytes(source.read_bytes())
    os.utime(archived, ns=(fixture.plan.items[0].mtime_ns,) * 2)
    approval_path = fixture.plan_path.parent / "restore-approval.json"
    _write_approval(approval_path, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
    fixture.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fixture.manifest_path.write_text(
        json.dumps(
            {
                "schema": "pimm-archive-manifest/v1",
                "schema_version": 1,
                "batch_id": fixture.plan.batch_id,
                "status": status,
                "active_root": fixture.plan.active_root,
                "archive_root": fixture.plan.archive_root,
                "publication_id": fixture.plan.publication_id,
                "inventory_sha256": fixture.plan.inventory_sha256,
                "consumer_graph_sha256": fixture.plan.consumer_graph_sha256,
                "render_inventory_sha256": fixture.plan.render_inventory_sha256,
                "inventory_root_identity": list(fixture.plan.inventory_root_identity),
                "plan_path": str(fixture.plan_path.resolve()),
                "plan_sha256": _sha256(fixture.plan_path),
                "approval_path": str(approval_path.resolve()),
                "approval_sha256": _sha256(approval_path),
                "error": None,
                "residuals": [],
                "items": [
                    {
                        "plan_item": fixture.plan.items[0].to_payload(),
                        "state": "moved",
                        "move_mode": "fixture",
                        "error": None,
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return archived


def _authority_patch(authority: object):
    return patch.object(
        archive_module,
        "_load_current_authority",
        return_value=authority,
        create=True,
    )


def _valid_approval(fixture: ArchiveTestFixture) -> Path:
    path = fixture.plan_path.parent / "approval.json"
    _write_approval(path, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
    return path


def _manifest_payload(fixture: ArchiveTestFixture) -> dict[str, object]:
    return json.loads(fixture.manifest_path.read_text(encoding="utf-8"))


def _write_manifest_payload(fixture: ArchiveTestFixture, payload: dict[str, object]) -> None:
    fixture.manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
            with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, "approved archive-plan SHA-256"):
                apply_archive_plan(fixture.plan_path, fixture.stale_approval_path)

    def test_restore_recreates_original_path_and_hash(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            _prepare_restore_manifest(fixture)
            source.unlink()
            with _authority_patch(fixture.authority):
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
            with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, "destination already exists"):
                apply_archive_plan(fixture.plan_path, approval)
            self.assertEqual(destination.read_bytes(), b"competitor")
            self.assertTrue(Path(fixture.plan.items[0].source).exists())

    def test_source_hash_drift_blocks_apply(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            source.write_bytes(b"changed-copy--0")
            os.utime(source, ns=(fixture.plan.items[0].mtime_ns,) * 2)
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, "source hash drift"):
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
            with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, "source identity drift"):
                apply_archive_plan(fixture.plan_path, approval)

    def test_partial_directory_inventory_blocks_apply(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            (source.parent / "late-file.txt").write_text("late", encoding="utf-8")
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))
            with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, "directory inventory is incomplete"):
                apply_archive_plan(fixture.plan_path, approval)

    def test_cross_volume_partial_copy_rolls_back_without_removing_source(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            source = Path(fixture.plan.items[0].source)
            destination = Path(fixture.plan.items[0].destination)
            approval = Path(root) / "approval.json"
            _write_approval(approval, fixture.plan_path, fixture.plan, _sha256(fixture.plan_path))

            def partial_copy(_source_descriptor: int, destination_descriptor: int) -> None:
                os.write(destination_descriptor, b"partial")
                raise OSError("injected cross-volume copy failure")

            with _authority_patch(fixture.authority), patch.object(archive_module, "_same_volume", return_value=False), patch.object(
                archive_module, "_copy_descriptor", side_effect=partial_copy
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
            with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, "delete action is forbidden"):
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

            with _authority_patch(fixture.authority), patch.object(archive_module, "_move_item", side_effect=observing_move):
                result = apply_archive_plan(fixture.plan_path, approval)
            self.assertEqual(observed, [True])
            self.assertTrue(result.manifest_path.is_file())
            self.assertFalse(result.manifest_path.with_suffix(".json.tmp").exists())
            self.assertFalse(Path(fixture.plan.items[0].source).exists())

    def test_final_manifest_readback_failure_rolls_manifest_and_asset_back_together(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            original_read = archive_module._stable_read

            def fail_final_read(path: Path, label: str):
                if label == "immutable archive manifest" and path.name == "archive-manifest.json":
                    raise OSError("injected final manifest readback failure")
                return original_read(path, label)

            with _authority_patch(fixture.authority), patch.object(
                archive_module, "_stable_read", side_effect=fail_final_read
            ), self.assertRaisesRegex(OSError, "manifest readback failure"):
                apply_archive_plan(fixture.plan_path, _valid_approval(fixture))
            self.assertTrue(Path(fixture.plan.items[0].source).exists())
            self.assertFalse(fixture.manifest_path.exists())
            pending = fixture.manifest_path.with_suffix(".json.tmp")
            self.assertEqual(
                json.loads(pending.read_text(encoding="utf-8"))["status"],
                "failed-rolled-back",
            )

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

            with _authority_patch(fixture.authority), patch.object(archive_module, "_move_item", side_effect=competing_move):
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
            with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, "reparse"):
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

    def test_plan_publication_requires_exact_external_governance_root(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            plan_root = Path(root) / "blender-product-renders-governance" / "manifests" / "archive-plans"
            exact = plan_root / f"{fixture.plan.batch_id}.json"
            outside = Path(fixture.plan.active_root) / "manifests" / "archive-plans" / exact.name
            with patch.object(archive_module, "ARCHIVE_PLAN_ROOT", plan_root):
                with self.assertRaisesRegex(ValueError, "external governance plan root"):
                    archive_module._publish_immutable_plan(outside, fixture.plan)
                digest = archive_module._publish_immutable_plan(exact, fixture.plan)
            self.assertEqual(digest, _sha256(exact))
            self.assertFalse(outside.exists())

    def test_plan_publication_atomic_no_replace_preserves_competitor(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            plan_root = Path(root) / "governance" / "manifests" / "archive-plans"
            exact = plan_root / f"{fixture.plan.batch_id}.json"

            def inject_competitor(_source: Path, destination: Path, *_args: object) -> None:
                destination.write_bytes(b"governance-competitor")
                raise FileExistsError("governance competitor exists")

            with patch.object(archive_module, "ARCHIVE_PLAN_ROOT", plan_root), patch.object(
                archive_module, "_rename_governance_no_replace", side_effect=inject_competitor
            ), self.assertRaisesRegex(FileExistsError, "competitor"):
                archive_module._publish_immutable_plan(exact, fixture.plan)
            self.assertEqual(exact.read_bytes(), b"governance-competitor")
            self.assertEqual(list(plan_root.glob(".*.pending")), [])

    def test_plan_publication_rejects_reparse_governance_ancestor(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            root_path = Path(root)
            real = root_path / "real-governance"
            real.mkdir()
            linked = root_path / "linked-governance"
            try:
                linked.symlink_to(real, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlinks unavailable: {error}")
            plan_root = linked / "manifests" / "archive-plans"
            exact = plan_root / f"{fixture.plan.batch_id}.json"
            with patch.object(archive_module, "ARCHIVE_PLAN_ROOT", plan_root), self.assertRaisesRegex(
                ValueError, "symlink|junction|reparse"
            ):
                archive_module._publish_immutable_plan(exact, fixture.plan)

    def test_apply_rejects_current_consumer_ambiguity_unique_and_disposition_drift(self):
        mutations = ("consumer", "ambiguity", "unique", "disposition")
        for mutation in mutations:
            with self.subTest(mutation=mutation), TemporaryDirectory() as root:
                fixture = archive_test_fixture(Path(root), (), False)
                item = fixture.plan.items[0]
                authority = fixture.authority
                if mutation == "consumer":
                    graph = replace(authority.graph, consumers={**authority.graph.consumers, item.relative_path: ("repo:theme.liquid:1",)})
                    authority = SimpleNamespace(**{**vars(authority), "graph": graph})
                elif mutation == "ambiguity":
                    graph = replace(authority.graph, ambiguous_references={"PIMM-old.blend1": {"candidate_paths": (item.relative_path,), "evidence": ("repo:theme.liquid:1",)}})
                    authority = SimpleNamespace(**{**vars(authority), "graph": graph})
                else:
                    records = tuple(
                        replace(record, unique_content=True)
                        if mutation == "unique" and record.path == item.relative_path
                        else replace(record, proposed_disposition="migrate")
                        if mutation == "disposition" and record.path == item.relative_path
                        else record
                        for record in authority.inventory.records
                    )
                    inventory = InventoryManifest(records, authority.inventory.discovered_paths, authority.inventory.root, authority.inventory.root_identity)
                    authority = SimpleNamespace(**{**vars(authority), "inventory": inventory})
                approval = _valid_approval(fixture)
                with _authority_patch(authority), self.assertRaisesRegex(ValueError, mutation):
                    apply_archive_plan(fixture.plan_path, approval)
                self.assertTrue(Path(item.source).exists())
                self.assertFalse(Path(item.destination).exists())

    def test_apply_rejects_publication_hash_and_root_identity_drift(self):
        mutations = {
            "publication": {"publication_id": "new-publication"},
            "inventory hash": {"inventory_sha256": "A" * 64},
            "graph hash": {"consumer_graph_sha256": "B" * 64},
            "render hash": {"render_inventory_sha256": "C" * 64},
            "root identity": {"root_identity": (999, 999)},
        }
        for label, changes in mutations.items():
            with self.subTest(label=label), TemporaryDirectory() as root:
                fixture = archive_test_fixture(Path(root), (), False)
                authority = SimpleNamespace(**{**vars(fixture.authority), **changes})
                with _authority_patch(authority), self.assertRaisesRegex(ValueError, label):
                    apply_archive_plan(fixture.plan_path, _valid_approval(fixture))
                self.assertTrue(Path(fixture.plan.items[0].source).exists())

    def test_apply_rejects_plan_with_arbitrary_active_root(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            rogue_root = Path(root) / "rogue-active"
            rogue_source = rogue_root / fixture.plan.items[0].relative_path
            rogue_source.parent.mkdir(parents=True)
            rogue_source.write_bytes(Path(fixture.plan.items[0].source).read_bytes())
            os.utime(rogue_source, ns=(fixture.plan.items[0].mtime_ns,) * 2)
            status = rogue_source.stat()
            rogue_archive = rogue_root.parent / f"{rogue_root.name}-archive" / "pending-delete" / Path(fixture.plan.archive_root).name
            rogue_item = replace(
                fixture.plan.items[0],
                source=str(rogue_source.resolve()),
                destination=str((rogue_archive / fixture.plan.items[0].relative_path).resolve()),
                filesystem_identity=(status.st_dev, status.st_ino, status.st_ctime_ns, status.st_size),
            )
            fixture = replace(
                fixture,
                plan=replace(fixture.plan, active_root=str(rogue_root.resolve()), archive_root=str(rogue_archive.resolve()), items=(rogue_item,)),
            )
            _write_plan(fixture.plan_path, fixture.plan)
            with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, "canonical active root"):
                apply_archive_plan(fixture.plan_path, _valid_approval(fixture))
            self.assertTrue(rogue_source.exists())

    def test_same_volume_apply_and_restore_never_overwrite_boundary_competitor(self):
        for operation in ("apply", "restore"):
            with self.subTest(operation=operation), TemporaryDirectory() as root:
                fixture = archive_test_fixture(Path(root), (), False)
                item = fixture.plan.items[0]
                if operation == "restore":
                    _prepare_restore_manifest(fixture)
                    Path(item.source).unlink()
                    competitor = Path(item.source)
                else:
                    competitor = Path(item.destination)

                def inject_competitor(_source: Path, destination: Path, *_args: object) -> None:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(b"competitor")
                    raise FileExistsError("destination competitor")

                with _authority_patch(fixture.authority), patch.object(
                    archive_module, "_rename_exact_no_replace", side_effect=inject_competitor, create=True
                ), self.assertRaisesRegex((ValueError, FileExistsError), "competitor|exists"):
                    if operation == "apply":
                        apply_archive_plan(fixture.plan_path, _valid_approval(fixture))
                    else:
                        restore_archive_batch(fixture.manifest_path)
                self.assertEqual(competitor.read_bytes(), b"competitor")

    def test_apply_rollback_never_overwrites_boundary_competitor(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False, item_count=2)
            first_source = Path(fixture.plan.items[0].source)
            original_move = archive_module._move_item
            calls = 0

            def fail_second(item: object, manifest_tmp: Path) -> str:
                nonlocal calls
                calls += 1
                if calls == 2:
                    first_source.write_bytes(b"rollback-competitor")
                    raise OSError("second move failed after competitor arrived")
                return original_move(item, manifest_tmp)

            with _authority_patch(fixture.authority), patch.object(
                archive_module, "_move_item", side_effect=fail_second
            ), self.assertRaisesRegex(OSError, "rollback incomplete"):
                apply_archive_plan(fixture.plan_path, _valid_approval(fixture))
            self.assertEqual(first_source.read_bytes(), b"rollback-competitor")
            state = json.loads(
                (Path(fixture.plan.archive_root) / "archive-manifest.json.tmp").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(state["status"], "failed-partial-rollback")
            self.assertEqual(state["items"][0]["state"], "rollback-failed")

    def test_cross_volume_create_new_boundary_preserves_competitor(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            destination = Path(fixture.plan.items[0].destination)
            original_create = archive_module._create_owned_file

            def create_with_competitor(path: Path, *, share_delete: bool) -> int:
                if path == destination:
                    path.write_bytes(b"cross-volume-competitor")
                return original_create(path, share_delete=share_delete)

            with _authority_patch(fixture.authority), patch.object(
                archive_module, "_same_volume", return_value=False
            ), patch.object(
                archive_module, "_create_owned_file", side_effect=create_with_competitor
            ), self.assertRaisesRegex(FileExistsError, "exists"):
                apply_archive_plan(fixture.plan_path, _valid_approval(fixture))
            self.assertEqual(destination.read_bytes(), b"cross-volume-competitor")
            self.assertTrue(Path(fixture.plan.items[0].source).exists())

    def test_restore_authenticates_plan_approval_roots_and_exact_item_mapping(self):
        mutations = ("plan hash", "approval hash", "active root", "mapping", "extra item", "missing item")
        for mutation in mutations:
            with self.subTest(mutation=mutation), TemporaryDirectory() as root:
                fixture = archive_test_fixture(Path(root), (), False)
                archived = _prepare_restore_manifest(fixture)
                source = Path(fixture.plan.items[0].source)
                source.unlink()
                payload = _manifest_payload(fixture)
                if mutation == "plan hash":
                    payload["plan_sha256"] = "0" * 64
                elif mutation == "approval hash":
                    payload["approval_sha256"] = "1" * 64
                elif mutation == "active root":
                    payload["active_root"] = str(Path(fixture.plan.active_root).parent)
                elif mutation == "mapping":
                    remapped = archived.with_name("remapped.blend1")
                    archived.rename(remapped)
                    payload["items"][0]["plan_item"]["destination"] = str(remapped)
                elif mutation == "extra item":
                    payload["items"].append(dict(payload["items"][0]))
                else:
                    payload["items"] = []
                _write_manifest_payload(fixture, payload)
                with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, mutation):
                    restore_archive_batch(fixture.manifest_path)
                self.assertFalse(source.exists())

    def test_restore_rejects_plan_or_approval_bytes_changed_after_archive(self):
        for target in ("plan", "approval"):
            with self.subTest(target=target), TemporaryDirectory() as root:
                fixture = archive_test_fixture(Path(root), (), False)
                _prepare_restore_manifest(fixture)
                Path(fixture.plan.items[0].source).unlink()
                payload = _manifest_payload(fixture)
                path = Path(payload[f"{target}_path"])
                path.write_bytes(path.read_bytes() + b" ")
                with _authority_patch(fixture.authority), self.assertRaisesRegex(ValueError, f"{target} SHA-256"):
                    restore_archive_batch(fixture.manifest_path)

    def test_restore_rejects_manifest_status_item_state_mismatch(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            _prepare_restore_manifest(fixture)
            Path(fixture.plan.items[0].source).unlink()
            payload = _manifest_payload(fixture)
            payload["items"][0]["state"] = "pending"
            _write_manifest_payload(fixture, payload)
            with _authority_patch(fixture.authority), self.assertRaisesRegex(
                ValueError, "status.*state|state.*status"
            ):
                restore_archive_batch(fixture.manifest_path)

    def test_restore_rejects_manifest_path_root_identity_and_authority_path_tampering(self):
        mutations = ("manifest path", "archive root", "root identity", "plan path", "approval path")
        for mutation in mutations:
            with self.subTest(mutation=mutation), TemporaryDirectory() as root:
                fixture = archive_test_fixture(Path(root), (), False)
                _prepare_restore_manifest(fixture)
                Path(fixture.plan.items[0].source).unlink()
                payload = _manifest_payload(fixture)
                candidate = fixture.manifest_path
                if mutation == "manifest path":
                    candidate = fixture.manifest_path.with_name("tampered-manifest.json")
                elif mutation == "archive root":
                    payload["archive_root"] = str(Path(payload["archive_root"]).parent)
                elif mutation == "root identity":
                    payload["inventory_root_identity"] = [999, 999]
                elif mutation == "plan path":
                    payload["plan_path"] = str(Path(root) / "missing-plan.json")
                else:
                    payload["approval_path"] = str(Path(root) / "missing-approval.json")
                candidate.write_text(
                    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                expected = {
                    "plan path": "archive plan",
                    "approval path": "archive approval",
                }.get(mutation, mutation)
                with _authority_patch(fixture.authority), self.assertRaisesRegex(
                    (ValueError, FileNotFoundError), expected
                ):
                    restore_archive_batch(candidate)

    def test_restore_rejects_reparse_ancestors_on_active_and_archive_sides(self):
        for side in ("active", "archive"):
            with self.subTest(side=side), TemporaryDirectory() as root:
                fixture = archive_test_fixture(Path(root), (), False)
                _prepare_restore_manifest(fixture)
                Path(fixture.plan.items[0].source).unlink()
                mapped = (
                    Path(fixture.plan.items[0].source).parent
                    if side == "active"
                    else Path(fixture.plan.items[0].destination).parent
                )
                real = mapped.with_name(f"real-{mapped.name}")
                mapped.rename(real)
                try:
                    mapped.symlink_to(real, target_is_directory=True)
                except OSError as error:
                    self.skipTest(f"directory symlinks unavailable: {error}")
                with _authority_patch(fixture.authority), self.assertRaisesRegex(
                    ValueError, "symlink|junction|reparse"
                ):
                    restore_archive_batch(fixture.manifest_path)

    def test_crash_after_move_before_state_update_is_recoverable_from_pending_manifest(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            original_write = archive_module._write_manifest_tmp
            calls = 0

            def crash_after_first_write(path: Path, payload: object, *, create: bool) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise SystemExit("injected crash")
                original_write(path, payload, create=create)

            with _authority_patch(fixture.authority), patch.object(archive_module, "_write_manifest_tmp", side_effect=crash_after_first_write), self.assertRaises(SystemExit):
                apply_archive_plan(fixture.plan_path, _valid_approval(fixture))
            source = Path(fixture.plan.items[0].source)
            destination = Path(fixture.plan.items[0].destination)
            pending = Path(fixture.plan.archive_root) / "archive-manifest.json.tmp"
            self.assertFalse(source.exists())
            self.assertTrue(destination.exists())
            state = json.loads(pending.read_text(encoding="utf-8"))
            self.assertEqual(state["items"][0]["state"], "pending")
            with _authority_patch(fixture.authority):
                restore_archive_batch(pending)
            self.assertEqual(_sha256(source), fixture.original_sha256)

    def test_two_item_failure_persists_truthful_complete_rollback_state(self):
        for rollback_fails in (False, True):
            with self.subTest(rollback_fails=rollback_fails), TemporaryDirectory() as root:
                fixture = archive_test_fixture(Path(root), (), False, item_count=2)
                original_move = archive_module._move_item
                calls = 0

                def fail_second(item: object, manifest_tmp: Path) -> str:
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        raise OSError("second move failed")
                    return original_move(item, manifest_tmp)

                contexts = [
                    _authority_patch(fixture.authority),
                    patch.object(archive_module, "_move_item", side_effect=fail_second),
                ]
                if rollback_fails:
                    contexts.append(patch.object(archive_module, "_restore_one", side_effect=OSError("rollback blocked")))
                with contexts[0], contexts[1]:
                    optional = contexts[2] if rollback_fails else patch.object(archive_module, "_restore_one", wraps=archive_module._restore_one)
                    with optional, self.assertRaisesRegex(OSError, "second move failed|rollback incomplete"):
                        apply_archive_plan(fixture.plan_path, _valid_approval(fixture))
                pending = Path(fixture.plan.archive_root) / "archive-manifest.json.tmp"
                state = json.loads(pending.read_text(encoding="utf-8"))
                self.assertEqual(len(state["items"]), 2)
                expected = "failed-partial-rollback" if rollback_fails else "failed-rolled-back"
                self.assertEqual(state["status"], expected)
                if rollback_fails:
                    self.assertTrue(any(item["error"] for item in state["items"]))

    def test_archive_leaf_uses_bangkok_date_derived_from_created_at(self):
        with TemporaryDirectory() as root:
            fixture = archive_test_fixture(Path(root), (), False)
            wrong_leaf = Path(fixture.plan.archive_root).parent / f"2026-08-16-{fixture.plan.batch_id}"
            item = replace(fixture.plan.items[0], destination=str(wrong_leaf / fixture.plan.items[0].relative_path))
            wrong = replace(
                fixture.plan,
                created_at_utc="2026-08-16T18:00:00Z",
                archive_root=str(wrong_leaf),
                items=(item,),
            )
            self.assertIn("Bangkok date", "\n".join(validate_archive_plan(wrong, fixture.inventory, fixture.graph)))


if __name__ == "__main__":
    unittest.main()
