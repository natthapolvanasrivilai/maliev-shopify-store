"""Behavior coverage for the four preview-only PIMM editorial sets."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
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
    "architectural-daylight": {
        "AMBIENT_WARM", "SUN_Gobo", "FILL_WALL", "FRONT_LOWER_FILL", "EDGE_STRIP",
    },
    "dark-engineering": {
        "AMBIENT_COOL", "KEY_SLASH", "RIM_LEFT", "RIM_RIGHT", "FRONT_FILL",
        "BASE_LIFT", "BLUE_ACCENT", "BACKDROP_WASH",
    },
    "modern-workshop": {
        "WORKSHOP_HDRI", "WINDOW_KEY", "MACHINE_FILL", "BASE_FILL", "PRACTICAL_WARM",
    },
    "process-still-life": {
        "AMBIENT_SOFT", "KEY_TOP_SIDE", "EDGE_CARD", "FOREGROUND_KICK",
        "FRONT_FILL", "BASE_LIFT",
    },
}

EXPECTED_SHADOWS = {
    "architectural-daylight": "crisp-window-grid-clear-of-product-evidence",
    "dark-engineering": "elongated-diagonal-readable-underside",
    "modern-workshop": "soft-window-cast-with-contact-depth",
    "process-still-life": "layered-foreground-edge-defined",
}

EXPECTED_LIGHT_PARAMETERS = {
    "architectural-daylight": {
        "AMBIENT_WARM": ("WORLD", 0.40, (0.35, 0.31, 0.27), (0, 0, 0), (0, 0, 0), 0.0, 0.0, 0.0),
        "SUN_Gobo": ("SUN", 4.0, (1.0, 0.82, 0.64), (-3600, -3000, 4800), (math.radians(28), 0, math.radians(-38)), 0.0, 0.0, math.radians(1.3)),
        "FILL_WALL": ("AREA", 600_000.0, (1.0, 0.91, 0.80), (2800, -1400, 2200), (1.150261998177, 0.0, 1.107148766518), 2800, 1800, 0.0),
        "FRONT_LOWER_FILL": ("AREA", 700_000.0, (1.0, 0.94, 0.86), (0, -2200, 650), (1.395346283913, 0.0, 0.0), 2600, 900, 0.0),
        "EDGE_STRIP": ("AREA", 350_000.0, (1.0, 0.94, 0.85), (-1800, 1200, 2200), (1.029696822166, 0.0, -2.158798933029), 1800, 220, 0.0),
    },
    "dark-engineering": {
        "AMBIENT_COOL": ("WORLD", 1.50, (0.22, 0.25, 0.30), (0, 0, 0), (0, 0, 0), 0.0, 0.0, 0.0),
        "KEY_SLASH": ("AREA", 5_000_000.0, (1.0, 0.86, 0.70), (-2900, -2500, 4100), (0.859445214272, 0.0, -0.859337091446), 1100, 260, 0.0),
        "RIM_LEFT": ("AREA", 3_000_000.0, (0.84, 0.91, 1.0), (-2300, 1500, 2300), (1.099300026894, 0.0, -2.148698329926), 2100, 180, 0.0),
        "RIM_RIGHT": ("AREA", 2_800_000.0, (0.91, 0.95, 1.0), (2400, 1700, 2100), (1.183402061462, 0.0, 2.187093496323), 1900, 180, 0.0),
        "FRONT_FILL": ("AREA", 4_000_000.0, (0.64, 0.72, 0.84), (0, -2300, 1650), (1.201584696770, 0.0, 0.0), 2800, 2000, 0.0),
        "BASE_LIFT": ("AREA", 5_000_000.0, (0.76, 0.82, 0.90), (0, -1600, 500), (1.421906232834, 0.0, 0.0), 2200, 800, 0.0),
        "BLUE_ACCENT": ("AREA", 700_000.0, (0.035, 0.20, 0.82), (1350, 900, 1650), (1.088225126266, 0.0, 2.158799171448), 900, 120, 0.0),
        "BACKDROP_WASH": ("AREA", 8_000_000.0, (0.34, 0.40, 0.52), (0, 1500, 1900), (1.516794800758, 0.0, 0.0), 3200, 2200, 0.0),
    },
    "modern-workshop": {
        "WORKSHOP_HDRI": ("WORLD", 0.42, (1.0, 1.0, 1.0), (0, 0, 0), (0, 0, 0), 0.0, 0.0, 0.0),
        "WINDOW_KEY": ("AREA", 300_000.0, (0.82, 0.91, 1.0), (-3200, -1700, 3600), (0.912908554077, 0.0, -1.082462549210), 2400, 1400, 0.0),
        "MACHINE_FILL": ("AREA", 550_000.0, (0.93, 0.96, 1.0), (2200, -800, 1500), (1.264624118805, 0.0, 1.222025394440), 1800, 1000, 0.0),
        "BASE_FILL": ("AREA", 500_000.0, (0.82, 0.88, 0.96), (0, -1800, 500), (1.438244938850, 0.0, 0.0), 2200, 800, 0.0),
        "PRACTICAL_WARM": ("POINT", 250_000.0, (1.0, 0.54, 0.24), (-1700, 1650, 2600), (0, 0, 0), 180, 0.0, 0.0),
    },
    "process-still-life": {
        "AMBIENT_SOFT": ("WORLD", 0.45, (0.28, 0.30, 0.34), (0, 0, 0), (0, 0, 0), 0.0, 0.0, 0.0),
        "KEY_TOP_SIDE": ("AREA", 1_200_000.0, (1.0, 0.86, 0.69), (-2200, -1700, 3900), (0.731081366539, 0.0, -0.912907600403), 1500, 900, 0.0),
        "EDGE_CARD": ("AREA", 600_000.0, (0.82, 0.90, 1.0), (2100, 400, 2200), (1.007534265518, 0.0, 1.759017944336), 1700, 200, 0.0),
        "FOREGROUND_KICK": ("AREA", 450_000.0, (1.0, 0.66, 0.39), (-900, -2500, 700), (1.403028488159, 0.0, -0.345555514097), 1100, 320, 0.0),
        "FRONT_FILL": ("AREA", 650_000.0, (0.82, 0.87, 0.94), (0, -2200, 1500), (1.222025156021, 0.0, 0.0), 2600, 1800, 0.0),
        "BASE_LIFT": ("AREA", 750_000.0, (0.78, 0.84, 0.92), (600, -1200, 500), (1.393783211708, 0.0, 0.463647603989), 1800, 750, 0.0),
    },
}

EXPECTED_GEOMETRY_ROLES = {
    "architectural-daylight": {"warm-grey-floor", "warm-grey-wall", "window-gobo", "accent-slab"},
    "dark-engineering": {"graphite-floor", "graphite-wall", "black-flag-left", "black-flag-right"},
    "modern-workshop": {"steel-workbench", "pellet-jar", "mold-block", "technical-drawing"},
    "process-still-life": {
        "mold-half", "peek-pellets", "black-pellets", "neutral-pellets",
        "molded-sample", "inspection-caliper", "technical-drawing",
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
        self.matrix_world = (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )
        self.bound_box = tuple(
            (x, y, z)
            for x in (-0.5, 0.5)
            for y in (-0.5, 0.5)
            for z in (-0.5, 0.5)
        )


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
        dimensions = (
            (1.2734, 0.7536, 0.9646)
            if "tool_cart" in self.path
            else (0.4001, 0.3198, 0.1724)
        )
        half = tuple(value / 2.0 for value in dimensions)
        source = _Object("external-mesh", _Mesh("external-mesh"))
        source.bound_box = tuple(
            (x, y, z)
            for x in (-half[0], half[0])
            for y in (-half[1], half[1])
            for z in (-half[2], half[2])
        )
        self.requested.collections = [
            _Collection(f"LINKED::{Path(self.path).stem}", (source,))
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

    def test_freezes_every_light_type_color_energy_size_and_direction(self) -> None:
        """Catches materially changed rigs hidden behind unchanged role labels."""

        for shot in self.campaign.shots:
            if shot.concept in {"modern-workshop", "process-still-life"}:
                directory = TemporaryDirectory()
                self.addCleanup(directory.cleanup)
                root = Path(directory.name)
                _asset_manifest(root)
            else:
                root = Path("unused")
            with patch.object(editorial_sets, "ASSET_ROOT", root):
                evidence = editorial_sets.build_editorial_set(_FakeBpy(), shot)
            actual = {
                light.role: (
                    light.light_type, light.energy, light.color, light.location_mm,
                    light.rotation_euler, light.size_mm, light.size_y_mm, light.angle_radians,
                )
                for light in evidence.lights
            }
            with self.subTest(concept=shot.concept):
                self.assertEqual(actual, EXPECTED_LIGHT_PARAMETERS[shot.concept])

    def test_corrective_rigs_install_world_lift_and_aim_broad_base_fills_at_the_product(self) -> None:
        """Catches a nominal fill role that leaves the lower machine black or faces away."""

        expected_world = {
            "architectural-daylight": ("AMBIENT_WARM", 0.40, (0.35, 0.31, 0.27, 1.0)),
            "dark-engineering": ("AMBIENT_COOL", 1.50, (0.22, 0.25, 0.30, 1.0)),
            "process-still-life": ("AMBIENT_SOFT", 0.45, (0.28, 0.30, 0.34, 1.0)),
        }
        fill_targets = {
            "architectural-daylight": ("FRONT_LOWER_FILL", (0.0, 0.0, 260.0)),
            "dark-engineering": ("BASE_LIFT", (0.0, 0.0, 260.0)),
            "modern-workshop": ("BASE_FILL", (0.0, 0.0, 260.0)),
            "process-still-life": ("BASE_LIFT", (0.0, 0.0, 260.0)),
        }

        with TemporaryDirectory() as directory:
            root = Path(directory)
            _asset_manifest(root)
            with patch.object(editorial_sets, "ASSET_ROOT", root):
                for shot in self.campaign.shots:
                    fake_bpy = _FakeBpy()
                    evidence = editorial_sets.build_editorial_set(fake_bpy, shot)
                    role, target = fill_targets[shot.concept]
                    lights_by_role = {item.role: item for item in evidence.lights}
                    self.assertIn(role, lights_by_role)
                    fill = lights_by_role[role]
                    direction = self._light_forward(fill.rotation_euler)
                    to_target = tuple(target[index] - fill.location_mm[index] for index in range(3))
                    dot = sum(left * right for left, right in zip(direction, self._normalize(to_target)))
                    with self.subTest(concept=shot.concept, behavior="base-fill-aim"):
                        self.assertGreater(dot, 0.95)
                        self.assertGreaterEqual(fill.size_mm, 1800.0)
                        self.assertGreaterEqual(fill.size_y_mm, 750.0)
                    if shot.concept in expected_world:
                        world_role, strength, color = expected_world[shot.concept]
                        background = fake_bpy.context.scene.world.node_tree.nodes.get("Background")
                        with self.subTest(concept=shot.concept, behavior="world-lift"):
                            self.assertEqual(fake_bpy.context.scene.world["pimm_editorial_light_role"], world_role)
                            self.assertEqual(background.inputs["Strength"].default_value, strength)
                            self.assertEqual(background.inputs["Color"].default_value, color)

    def test_architectural_gobo_is_a_grid_and_process_has_no_camera_dominating_blocks(self) -> None:
        """Catches the rejected single-cross shadow and wide portrait framing blocks."""

        architectural = editorial_sets._SETS["architectural-daylight"].geometry
        gobos = [item for item in architectural if item.role == "window-gobo"]
        self.assertGreaterEqual(len(gobos), 6)
        self.assertGreaterEqual(sum(item.dimensions_mm[0] < item.dimensions_mm[1] for item in gobos), 3)
        self.assertGreaterEqual(sum(item.dimensions_mm[0] > item.dimensions_mm[1] for item in gobos), 3)
        self.assertTrue(all(item.dimensions_mm[2] <= 40.0 for item in gobos))
        self.assertEqual({item.center_mm[2] for item in gobos}, {1800})

        process = editorial_sets._SETS["process-still-life"].geometry
        self.assertNotIn("foreground-block", {item.role for item in process})

    @staticmethod
    def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
        length = math.sqrt(sum(value * value for value in vector))
        return tuple(value / length for value in vector)

    @staticmethod
    def _light_forward(rotation: tuple[float, float, float]) -> tuple[float, float, float]:
        x_angle, y_angle, z_angle = rotation
        if abs(y_angle) > 1e-12:
            raise AssertionError("test helper expects the authored zero-Y light rotations")
        sin_x = math.sin(x_angle)
        return (
            -math.sin(z_angle) * sin_x,
            math.cos(z_angle) * sin_x,
            -math.cos(x_angle),
        )

    def test_external_model_instances_convert_real_meter_bounds_to_credible_millimetres(self) -> None:
        """Catches linked metre-authored props left 1,000 times too small in the mm scene."""

        expected_ranges = {
            "tool_cart": ((1200.0, 1350.0), (700.0, 820.0), (900.0, 1030.0)),
            "metal_toolbox": ((360.0, 450.0), (280.0, 360.0), (140.0, 220.0)),
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _asset_manifest(root)
            with patch.object(editorial_sets, "ASSET_ROOT", root):
                for shot_id in (
                    "pimm-50g--concept-modern-workshop",
                    "pimm-30g--concept-process-still-life",
                ):
                    fake_bpy = _FakeBpy()
                    evidence = editorial_sets.build_editorial_set(fake_bpy, self.campaign.by_shot_id[shot_id])
                    for item in evidence.external_instances:
                        ranges = expected_ranges[item.asset_id]
                        with self.subTest(asset=item.asset_id):
                            self.assertEqual(item.instance_scale, (1000.0, 1000.0, 1000.0))
                            self.assertTrue(all(low <= actual <= high for actual, (low, high) in zip(item.resolved_dimensions_mm, ranges)))
                            instance = next(obj for obj in fake_bpy.context.scene.objects if obj.name == item.object_name)
                            self.assertEqual(instance.scale, item.instance_scale)

    def test_editorial_props_have_recognizable_feature_geometry(self) -> None:
        """Catches semantic props regressing to one renamed primitive per requested object."""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            _asset_manifest(root)
            with patch.object(editorial_sets, "ASSET_ROOT", root):
                workshop = editorial_sets.build_editorial_set(
                    _FakeBpy(), self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
                )
                process = editorial_sets.build_editorial_set(
                    _FakeBpy(), self.campaign.by_shot_id["pimm-30g--concept-process-still-life"]
                )

        workshop_counts = dict(workshop.feature_counts)
        self.assertGreaterEqual(workshop_counts["container-pellet"], 24)
        self.assertGreaterEqual(workshop_counts["mold-cavity"], 2)
        self.assertGreaterEqual(workshop_counts["mold-parting-line"], 2)
        self.assertGreaterEqual(workshop_counts["mold-fastener"], 8)
        self.assertGreaterEqual(workshop_counts["drawing-linework"], 8)

        process_counts = dict(process.feature_counts)
        for pellet_role in ("peek-pellets", "black-pellets", "neutral-pellets"):
            self.assertGreaterEqual(process_counts[pellet_role], 12)
            granules = [item for item in process.geometry if item.role == pellet_role]
            self.assertTrue(all(8.0 <= item.maximum_dimension_mm <= 30.0 for item in granules))
        self.assertGreaterEqual(process_counts["mold-cavity"], 2)
        self.assertGreaterEqual(process_counts["mold-parting-line"], 2)
        self.assertGreaterEqual(process_counts["mold-fastener"], 8)
        self.assertGreaterEqual(process_counts["molded-sample"], 4)
        self.assertGreaterEqual(process_counts["inspection-caliper"], 5)
        self.assertGreaterEqual(process_counts["drawing-linework"], 10)

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
