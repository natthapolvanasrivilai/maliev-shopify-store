import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.blender.master_assets.pimm_legacy_inventory import AssetRecord, AUTHORITATIVE_PATHS
from scripts.blender.pimm_production.consumer_graph import (
    ConsumerGraph,
    build_consumer_graph,
    classify_record,
)


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / Path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class ConsumerGraphTests(unittest.TestCase):
    def test_exact_filename_consumer_has_source_line_evidence(self):
        with TemporaryDirectory() as repository_text, TemporaryDirectory() as asset_text:
            repository = Path(repository_text)
            asset_root = Path(asset_text)
            _write(repository, "scripts/render.py", "open('PIMM-product-render-master.blend')\n")
            _write(repository, "scripts/backup.py", "open('PIMM-product-render-master.blend1')\n")
            record = AssetRecord(path="PIMM-product-render-master.blend", kind="blend-project")

            graph = build_consumer_graph(repository, asset_root, [record])

            self.assertEqual(graph.consumers[record.path], ("repo:scripts/render.py:1",))

    def test_record_dependencies_create_blender_datablock_consumer_edges(self):
        dependency = AssetRecord(path="textures/steel.png", kind="texture")
        scene = AssetRecord(
            path="scenes/hero.blend",
            kind="blend-project",
            dependencies=("textures/steel.png",),
            dependency_evidence={"textures/steel.png": ("image:Steel",)},
        )

        graph = build_consumer_graph(Path("missing-repo"), Path("missing-assets"), [dependency, scene])

        self.assertEqual(graph.consumers[dependency.path], ("asset:scenes/hero.blend#image:Steel",))
        self.assertEqual(graph.producers[scene.path], ("dependency:textures/steel.png#image:Steel",))

    def test_duplicate_basename_reference_is_unresolved_without_fanout(self):
        with TemporaryDirectory() as repository_text, TemporaryDirectory() as asset_text:
            repository = Path(repository_text)
            asset_root = Path(asset_text)
            _write(repository, "scripts/render.py", "open('logo.png')\n")
            records = (
                AssetRecord(path="textures/vendor-a/logo.png", kind="texture"),
                AssetRecord(path="artwork/vendor-b/logo.png", kind="artwork"),
            )

            graph = build_consumer_graph(repository, asset_root, records)

            self.assertEqual(graph.consumers[records[0].path], ())
            self.assertEqual(graph.consumers[records[1].path], ())
            self.assertEqual(graph.unresolved_references["logo.png"], ("repo:scripts/render.py:1",))

    def test_only_exact_generated_graph_path_is_excluded_from_asset_evidence(self):
        with TemporaryDirectory() as repository_text, TemporaryDirectory() as asset_text:
            repository = Path(repository_text)
            asset_root = Path(asset_text)
            _write(asset_root, "manifests/consumer-graph.json", '"renders/hero.png"\n')
            _write(
                asset_root,
                "archive/manifests/consumer-graph.json",
                '"renders/hero.png"\n',
            )
            hero = AssetRecord(path="renders/hero.png", kind="render-image")

            graph = build_consumer_graph(repository, asset_root, [hero])

            self.assertEqual(
                graph.consumers[hero.path],
                ("asset:archive/manifests/consumer-graph.json:1",),
            )

    def test_tool_virtual_environment_is_not_a_consumer(self):
        with TemporaryDirectory() as repository_text, TemporaryDirectory() as asset_text:
            repository = Path(repository_text)
            asset_root = Path(asset_text)
            _write(asset_root, "tools/pimm-render-py311/pyvenv.cfg", "home = python")
            _write(asset_root, "tools/pimm-render-py311/Lib/site-packages/tool.py", "open('hero.png')")
            record = AssetRecord(path="renders/hero.png", kind="render-image")

            graph = build_consumer_graph(repository, asset_root, [record])

            self.assertEqual(graph.consumers[record.path], ())

    def test_active_consumer_prevents_archive(self):
        record = AssetRecord(path="PIMM-product-render-master.blend", unique_content=True)
        graph = ConsumerGraph(consumers={record.path: ("repo:scripts/render.py:1",)}, producers={})
        self.assertEqual(classify_record(record, graph), "migrate")

    def test_authoritative_and_linked_scene_classification(self):
        authoritative = AssetRecord(path="masters/PIMM-30G-MASTER.blend", kind="authoritative-master")
        linked = AssetRecord(
            path="scenes/30g-hero.blend",
            kind="blend-project",
            dependencies=("masters/PIMM-30G-MASTER.blend",),
        )
        graph = ConsumerGraph(
            consumers={},
            producers={},
            authoritative_paths=tuple(AUTHORITATIVE_PATHS),
        )

        self.assertEqual(classify_record(authoritative, graph), "authoritative")
        self.assertEqual(classify_record(linked, graph), "active-linked-scene")

    def test_all_exact_authoritative_paths_remain_authoritative_with_dependency_evidence(self):
        graph = ConsumerGraph(
            consumers={},
            producers={},
            authoritative_paths=tuple(AUTHORITATIVE_PATHS),
        )

        for path in AUTHORITATIVE_PATHS:
            with self.subTest(path=path):
                record = AssetRecord(
                    path=path,
                    kind="authoritative-master",
                    blender_inspection={
                        "missing_dependencies": ["Z:/historical-output"],
                        "unsafe_dependencies": ["Z:/historical-output"],
                    },
                )
                self.assertEqual(classify_record(record, graph), "authoritative")

    def test_archived_same_name_master_and_dependency_never_gain_authority(self):
        archived_master = AssetRecord(
            path="archives/prior/masters/PIMM-30G-MASTER.blend",
            kind="authoritative-master",
        )
        linked_to_archive = AssetRecord(
            path="scenes/legacy.blend",
            kind="blend-project",
            dependencies=("archives/prior/masters/PIMM-30G-MASTER.blend",),
        )
        graph = ConsumerGraph(consumers={}, producers={})

        self.assertEqual(classify_record(archived_master, graph), "unresolved")
        self.assertEqual(classify_record(linked_to_archive, graph), "unresolved")

    def test_geometry_only_blend_recovery_is_never_pending_archive(self):
        record = AssetRecord(
            path="backups/geometry-only.blend1",
            kind="blend-recovery",
            unique_content=False,
            blender_inspection={
                "object_count": 1,
                "mesh_object_count": 1,
                "mesh_datablock_count": 1,
                "material_count": 1,
                "object_identity_sha256": "1" * 64,
                "geometry_identity_sha256": "2" * 64,
                "material_identity_sha256": "3" * 64,
                "missing_dependencies": [],
                "inspection_error": None,
            },
        )

        self.assertEqual(classify_record(record, ConsumerGraph(consumers={}, producers={})), "migrate")

    def test_backup_without_unique_content_or_consumers_is_pending_archive(self):
        record = AssetRecord(path="PIMM-old.blend1", kind="blend-recovery")
        self.assertEqual(classify_record(record, ConsumerGraph(consumers={}, producers={})), "pending-archive")

    def test_unclassified_asset_is_unresolved(self):
        record = AssetRecord(path="textures/orphan.png", kind="texture")
        self.assertEqual(classify_record(record, ConsumerGraph(consumers={}, producers={})), "unresolved")

    def test_missing_blender_dependency_stays_unresolved(self):
        record = AssetRecord(
            path="legacy/hero.blend",
            kind="blend-project",
            unique_content=True,
            blender_inspection={"missing_dependencies": ["Z:/missing-decal.png"]},
        )
        self.assertEqual(classify_record(record, ConsumerGraph(consumers={}, producers={})), "unresolved")


if __name__ == "__main__":
    unittest.main()
