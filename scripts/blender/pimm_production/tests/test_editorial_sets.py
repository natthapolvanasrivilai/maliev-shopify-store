"""Behavior coverage for the four preview-only PIMM editorial sets."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.blender.pimm_production.editorial_concept_contract import (
    EDITORIAL_CAMPAIGN_PATH,
    load_editorial_campaign,
)
from scripts.blender.pimm_production import editorial_sets


EXPECTED_LIGHTS = {
    "architectural-daylight": {"SUN_Gobo", "FILL_WALL", "EDGE_STRIP"},
    "dark-engineering": {"KEY_SLASH", "RIM_LEFT", "RIM_RIGHT", "BASE_LIFT", "BLUE_ACCENT"},
    "modern-workshop": {"WORKSHOP_HDRI", "WINDOW_KEY", "MACHINE_FILL", "PRACTICAL_WARM"},
    "process-still-life": {"KEY_TOP_SIDE", "EDGE_CARD", "FOREGROUND_KICK", "BASE_LIFT"},
}

EXPECTED_SHADOWS = {
    "architectural-daylight": "crisp-window-grid-clear-of-product-evidence",
    "dark-engineering": "elongated-diagonal-readable-underside",
    "modern-workshop": "soft-window-cast-with-contact-depth",
    "process-still-life": "layered-foreground-edge-defined",
}

EXPECTED_GEOMETRY_ROLES = {
    "architectural-daylight": {"warm-grey-floor", "warm-grey-wall", "window-gobo", "accent-slab"},
    "dark-engineering": {"graphite-floor", "graphite-wall", "black-flag-left", "black-flag-right"},
    "modern-workshop": {"steel-workbench", "pellet-jar", "mold-block", "technical-drawing"},
    "process-still-life": {
        "mold-half", "peek-pellets", "black-pellets", "neutral-pellets",
        "molded-sample", "inspection-caliper", "technical-drawing", "foreground-block",
    },
}

PROVENANCE_TAGS = {
    "pimm_external_source_url",
    "pimm_external_asset_version_id",
    "pimm_external_license",
    "pimm_external_local_relative_path",
    "pimm_external_sha256",
    "pimm_external_intended_shot_ids",
    "pimm_external_machine_master_modified",
}

PRODUCT_TAGS = {
    "pimm_stable_id",
    "pimm_artwork_id",
    "pimm_machine",
    "pimm_asset_role",
    "pimm_product_material_override",
}


class _ID(dict):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name


class _Socket:
    def __init__(self) -> None:
        self.default_value = None


class _Nodes:
    def __init__(self, *, material: bool = False, world: bool = False) -> None:
        self._items: dict[str, object] = {}
        if material:
            self._items["Principled BSDF"] = SimpleNamespace(
                inputs={name: _Socket() for name in (
                    "Base Color", "Roughness", "Metallic", "Transmission Weight", "Alpha",
                )}
            )
        if world:
            self._items["Background"] = SimpleNamespace(
                inputs={"Color": _Socket(), "Strength": _Socket()}, outputs={"Background": _Socket()}
            )

    def get(self, name: str) -> object | None:
        return self._items.get(name)

    def new(self, node_type: str) -> object:
        node = SimpleNamespace(
            name=node_type,
            image=None,
            inputs={"Color": _Socket(), "Strength": _Socket()},
            outputs={"Color": _Socket(), "Background": _Socket()},
        )
        self._items[node_type] = node
        return node


class _Links:
    def new(self, output: object, input_: object) -> None:
        del output, input_


class _NodeTree:
    def __init__(self, *, material: bool = False, world: bool = False) -> None:
        self.nodes = _Nodes(material=material, world=world)
        self.links = _Links()


class _Mesh(_ID):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.materials: list[object] = []
        self.vertices: list[tuple[float, float, float]] = []
        self.faces: list[tuple[int, ...]] = []

    def from_pydata(self, vertices: list[tuple[float, float, float]], edges: list[object], faces: list[tuple[int, ...]]) -> None:
        del edges
        self.vertices = vertices
        self.faces = faces

    def update(self) -> None:
        pass


class _Material(_ID):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.use_nodes = False
        self.node_tree = _NodeTree(material=True)
        self.diffuse_color = None
        self.blend_method = "OPAQUE"
        self.surface_render_method = "OPAQUE"


class _Light(_ID):
    def __init__(self, name: str, light_type: str) -> None:
        super().__init__(name)
        self.type = light_type
        self.energy = 0.0
        self.color = None
        self.shape = "RECTANGLE"
        self.size = 0.0
        self.size_y = 0.0
        self.angle = 0.0


class _Object(_ID):
    def __init__(self, name: str, data: object) -> None:
        super().__init__(name)
        self.data = data
        self.type = "LIGHT" if isinstance(data, _Light) else "MESH" if isinstance(data, _Mesh) else "EMPTY"
        self.location = None
        self.rotation_euler = None
        self.scale = (1.0, 1.0, 1.0)
        self.parent = None
        self.library = None
        self.instance_type = "NONE"
        self.instance_collection = None


class _Collection(_ID):
    def __init__(self, name: str, objects: tuple[_Object, ...] = ()) -> None:
        super().__init__(name)
        self.all_objects = objects


class _Store(list):
    def __init__(self, factory) -> None:
        super().__init__()
        self._factory = factory

    def new(self, *args):
        item = self._factory(*args)
        self.append(item)
        return item


class _ObjectLinker:
    def __init__(self, scene_objects: list[_Object]) -> None:
        self._scene_objects = scene_objects

    def link(self, obj: _Object) -> None:
        self._scene_objects.append(obj)


class _ChildLinker(list):
    def link(self, collection: _Collection) -> None:
        self.append(collection)


class _LibraryLoad:
    def __init__(self, path: str, calls: list[tuple[str, bool, bool]]) -> None:
        self.path = path
        self.calls = calls
        self.available = SimpleNamespace(collections=["Scene Collection"])
        self.requested = SimpleNamespace(collections=[])

    def __enter__(self):
        return self.available, self.requested

    def __exit__(self, *args: object) -> None:
        self.requested.collections = [
            _Collection(f"LINKED::{Path(self.path).stem}", (_Object("external-mesh", _Mesh("external-mesh")),))
            for item in self.requested.collections
            if item is not None
        ]


class _Libraries:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, bool]] = []

    def load(self, path: str, *, link: bool, relative: bool) -> _LibraryLoad:
        self.calls.append((path, link, relative))
        return _LibraryLoad(path, self.calls)


class _Images(list):
    def load(self, path: str, *, check_existing: bool) -> _ID:
        del check_existing
        image = _ID(path)
        self.append(image)
        return image


class _World(_ID):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.use_nodes = False
        self.node_tree = _NodeTree(world=True)


class _FakeBpy:
    def __init__(self) -> None:
        scene_objects: list[_Object] = []
        collection = SimpleNamespace(objects=_ObjectLinker(scene_objects), children=_ChildLinker())
        self.context = SimpleNamespace(scene=SimpleNamespace(objects=scene_objects, collection=collection, world=None))
        self.data = SimpleNamespace(
            meshes=_Store(_Mesh),
            materials=_Store(_Material),
            lights=_Store(_Light),
            objects=_Store(_Object),
            worlds=_Store(_World),
            images=_Images(),
            libraries=_Libraries(),
        )


def _write_asset(root: Path, relative: str, payload: bytes) -> dict[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"path": relative, "sha256": hashlib.sha256(payload).hexdigest().upper()}


def _asset_manifest(root: Path) -> None:
    workshop = "pimm-50g--concept-modern-workshop"
    process = "pimm-30g--concept-process-still-life"
    assets = []
    for asset_id, kind, extension, payload, shots in (
        ("university_workshop", "hdris:4k:exr", "university_workshop_4k.exr", b"hdri", [workshop]),
        ("tool_cart", "models:1k:blend", "tool_cart_1k.blend", b"cart", [workshop]),
        ("metal_toolbox", "models:1k:blend", "metal_toolbox_1k.blend", b"toolbox", [workshop, process]),
    ):
        relative = f"assets/external/polyhaven/{asset_id}/{extension}"
        written = _write_asset(root, relative, payload)
        assets.append({
            "source_url": f"https://polyhaven.com/a/{asset_id}",
            "asset_version_id": f"{asset_id}:{kind}:{hashlib.md5(payload).hexdigest()}",
            "license": "CC0-1.0",
            "local_relative_path": written["path"],
            "sha256": written["sha256"],
            "intended_shot_ids": shots,
            "machine_master_modified": False,
        })
    path = root / "manifests" / "external-assets-v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema": "maliev.pimm-external-assets/v1", "assets": assets}), encoding="utf-8")


class EditorialSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.campaign = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH)

    def test_builds_four_materially_distinct_geometry_light_and_shadow_signatures(self) -> None:
        """Catches a generic renamed studio rig or reused support set across concepts."""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            _asset_manifest(root)
            results = {}
            with patch.object(editorial_sets, "ASSET_ROOT", root):
                for shot in self.campaign.shots:
                    fake_bpy = _FakeBpy()
                    results[shot.concept] = (fake_bpy, editorial_sets.build_editorial_set(fake_bpy, shot))

        signatures = set()
        for concept, (fake_bpy, evidence) in results.items():
            with self.subTest(concept=concept):
                self.assertEqual({light.role for light in evidence.lights}, EXPECTED_LIGHTS[concept])
                self.assertEqual(evidence.shadow_intent, EXPECTED_SHADOWS[concept])
                self.assertTrue(EXPECTED_GEOMETRY_ROLES[concept] <= {item.role for item in evidence.geometry})
                self.assertEqual(evidence.concept, concept)
                signatures.add(evidence.geometry_signature)
                self.assertTrue(all(obj.get("pimm_editorial_light_role") for obj in fake_bpy.context.scene.objects if obj.type == "LIGHT"))
        self.assertEqual(len(signatures), 4)

    def test_all_supports_are_scene_local_non_product_owned_and_credibly_scaled(self) -> None:
        """Catches support props that masquerade as, parent into, or dwarf linked product data."""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            _asset_manifest(root)
            with patch.object(editorial_sets, "ASSET_ROOT", root):
                for shot in self.campaign.shots:
                    fake_bpy = _FakeBpy()
                    evidence = editorial_sets.build_editorial_set(fake_bpy, shot)
                    supports = [obj for obj in fake_bpy.context.scene.objects if obj.get("pimm_scene_support_role")]
                    with self.subTest(concept=shot.concept):
                        self.assertEqual(len(supports), len(evidence.geometry) + len(evidence.external_assets))
                        self.assertTrue(all(obj.library is None and obj.parent is None for obj in supports))
                        self.assertTrue(all(obj.get("pimm_scene_support_ownership") == "scene-support" for obj in supports))
                        self.assertTrue(all(not (set(obj) & PRODUCT_TAGS) for obj in supports))
                        self.assertTrue(all(item.maximum_dimension_mm <= 8_000.0 for item in evidence.geometry))
                        self.assertFalse(any("person" in obj.name.lower() or "technician" in obj.name.lower() for obj in supports))

    def test_loads_only_concept_authorized_external_assets_with_complete_provenance(self) -> None:
        """Catches unsupported assets, untagged instances, editable appends, or master mutation claims."""

        expected = {
            "architectural-daylight": set(),
            "dark-engineering": set(),
            "modern-workshop": {"university_workshop", "tool_cart"},
            "process-still-life": {"metal_toolbox"},
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _asset_manifest(root)
            with patch.object(editorial_sets, "ASSET_ROOT", root):
                for shot in self.campaign.shots:
                    fake_bpy = _FakeBpy()
                    evidence = editorial_sets.build_editorial_set(fake_bpy, shot)
                    external = [obj for obj in fake_bpy.context.scene.objects if obj.get("pimm_external_asset_version_id")]
                    actual_ids = {record.asset_id for record in evidence.external_assets}
                    with self.subTest(concept=shot.concept):
                        self.assertEqual(actual_ids, expected[shot.concept])
                        self.assertEqual(len(external), len(evidence.external_assets))
                        for obj in external:
                            self.assertTrue(PROVENANCE_TAGS <= set(obj))
                            self.assertEqual(obj["pimm_external_license"], "CC0-1.0")
                            self.assertFalse(obj["pimm_external_machine_master_modified"])
                            intended = tuple(json.loads(obj["pimm_external_intended_shot_ids"]))
                            record = next(
                                item for item in evidence.external_assets
                                if item.asset_version_id == obj["pimm_external_asset_version_id"]
                            )
                            self.assertEqual(intended, record.intended_shot_ids)
                            self.assertIn(shot.shot_id, intended)
                    if shot.concept == "modern-workshop":
                        self.assertEqual(len(fake_bpy.data.libraries.calls), 1)
                        self.assertTrue(fake_bpy.data.libraries.calls[0][1])
                        self.assertEqual(fake_bpy.context.scene.world.get("pimm_editorial_light_role"), "WORKSHOP_HDRI")
                    elif shot.concept == "process-still-life":
                        self.assertEqual(len(fake_bpy.data.libraries.calls), 1)
                        self.assertTrue(fake_bpy.data.libraries.calls[0][1])
                    else:
                        self.assertEqual(fake_bpy.data.libraries.calls, [])

    def test_set_light_and_evidence_records_are_immutable(self) -> None:
        """Catches mutable rig evidence that can drift after scene construction."""

        shot = self.campaign.by_shot_id["pimm-30g--concept-architectural-daylight"]
        evidence = editorial_sets.build_editorial_set(_FakeBpy(), shot)

        with self.assertRaises(dataclasses.FrozenInstanceError):
            evidence.shadow_intent = "soft"  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            evidence.geometry[0].role = "product"  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            evidence.lights[0].role = "KEY"  # type: ignore[misc]

    def test_translucent_pellet_jars_use_the_current_blender_dithered_surface(self) -> None:
        """Catches use of the removed legacy blend-method API for translucent supports."""

        shot = self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _asset_manifest(root)
            fake_bpy = _FakeBpy()
            with patch.object(editorial_sets, "ASSET_ROOT", root):
                editorial_sets.build_editorial_set(fake_bpy, shot)

        jar_materials = [item for item in fake_bpy.data.materials if "PELLET_JAR_CLEAR" in item.name]
        self.assertEqual(len(jar_materials), 2)
        self.assertTrue(all(item.surface_render_method == "DITHERED" for item in jar_materials))

    def test_rejects_a_shot_outside_the_exact_campaign_identity(self) -> None:
        """Catches concept-only dispatch that could load assets into an uncontracted shot."""

        shot = dataclasses.replace(self.campaign.shots[0], shot_id="uncontracted-architectural")

        with self.assertRaisesRegex(ValueError, "approved editorial shot"):
            editorial_sets.build_editorial_set(_FakeBpy(), shot)

    def test_rejects_a_mutated_policy_under_an_approved_shot_id(self) -> None:
        """Catches dispatch that trusts an approved ID while ignoring changed render policy."""

        shot = dataclasses.replace(self.campaign.shots[0], preview_samples=8)

        with self.assertRaisesRegex(ValueError, "approved editorial shot"):
            editorial_sets.build_editorial_set(_FakeBpy(), shot)


if __name__ == "__main__":
    unittest.main()
