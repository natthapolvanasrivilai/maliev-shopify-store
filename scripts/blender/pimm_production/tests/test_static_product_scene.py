"""Regression coverage for governed PIMM static-product scene contracts."""

from __future__ import annotations

from contextlib import redirect_stderr
from copy import deepcopy
from io import StringIO
import importlib
import importlib.util
from dataclasses import replace
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


MODULE = "scripts.blender.pimm_production.blender_static_product_scene"

EXPECTED = {
    "pimm-30g--overview--three-quarter": ("30G", "overview", "three-quarter", 85.0, 11.0),
    "pimm-30g--engineering--controls": ("30G", "engineering", "controls", 135.0, 8.0),
    "pimm-30g--tooling--front-detail": ("30G", "tooling", "front-detail", 135.0, 11.0),
    "pimm-50g--overview--three-quarter": ("50G", "overview", "three-quarter", 85.0, 11.0),
    "pimm-50g--engineering--controls": ("50G", "engineering", "controls", 135.0, 8.0),
    "pimm-50g--tooling--front-detail": ("50G", "tooling", "front-detail", 135.0, 11.0),
}


class IdentityMatrix:
    def __matmul__(self, value):
        return value


class StableMesh(dict):
    def __init__(self, stable_id, bounds_min, bounds_max, *, name=None):
        super().__init__(pimm_stable_id=stable_id)
        self.name = name or stable_id
        self.type = "MESH"
        self.matrix_world = IdentityMatrix()
        x0, y0, z0 = bounds_min
        x1, y1, z1 = bounds_max
        self.bound_box = (
            (x0, y0, z0),
            (x0, y0, z1),
            (x0, y1, z0),
            (x0, y1, z1),
            (x1, y0, z0),
            (x1, y0, z1),
            (x1, y1, z0),
            (x1, y1, z1),
        )


class PropertyNamespace(dict):
    def __init__(self, **values):
        dict.__init__(self)
        self.__dict__.update(values)


class NamedStore(list):
    def get(self, name):
        return next((item for item in self if getattr(item, "name", None) == name), None)


class StaticProductSceneTests(unittest.TestCase):
    def _module(self):
        self.assertIsNotNone(
            importlib.util.find_spec(MODULE),
            "static product scene authoring module must exist",
        )
        return importlib.import_module(MODULE)

    def test_registry_has_exact_static_shots(self):
        """Catches a missing, renamed, or miscalibrated governed still shot."""

        module = self._module()
        self.assertEqual(set(module.SHOT_CONFIGS), set(EXPECTED))
        for shot_id, (machine, purpose, view, lens, aperture) in EXPECTED.items():
            config = module.SHOT_CONFIGS[shot_id]
            self.assertEqual((config.machine, config.purpose, config.view), (machine, purpose, view))
            self.assertEqual(config.focal_length_mm, lens)
            self.assertEqual(config.aperture_fstop, aperture)
            self.assertEqual((config.output_width, config.output_height), (2400, 1800))
            self.assertIsNone(config.animation_contract)

    def test_three_quarter_camera_is_level_and_uses_realistic_orbit(self):
        """Catches a three-quarter camera collapsing to a straight-on or tilted view."""

        module = self._module()
        pose = module.orbit_camera_pose(
            (-200, -200, 0), (220, 160, 900), 2400, -24.0, 0.0
        )

        self.assertLess(pose.location[1], pose.target[1])
        self.assertNotEqual(pose.location[0], pose.target[0])
        self.assertAlmostEqual(pose.location[2], pose.target[2])
        self.assertAlmostEqual(
            math.dist(pose.location, pose.target),
            2400.0,
        )

    def test_detail_target_requires_one_nonempty_stable_id_group(self):
        """Catches detail authoring continuing without any stable target meshes."""

        module = self._module()
        with self.assertRaisesRegex(ValueError, "stable target"):
            module.bounds_for_objects([])

    def _target_manifest(self):
        shots = {}
        for machine in ("30g", "50g"):
            shots[f"pimm-{machine}--engineering--controls"] = {
                "groups": {
                    "gauge": [f"{machine}-gauge"],
                    "regulator": [f"{machine}-regulator"],
                    "controller": [f"{machine}-controller"],
                    "actuator_artwork": [f"{machine}-actuator-artwork"],
                }
            }
            shots[f"pimm-{machine}--tooling--front-detail"] = {
                "groups": {
                    "nozzle": [f"{machine}-nozzle"],
                    "platen": [f"{machine}-platen"],
                    "fixture": [f"{machine}-fixture"],
                }
            }
        return {"schema_version": 1, "shots": shots}

    def test_target_manifest_requires_every_semantic_stable_id_group(self):
        """Catches mutable-name targeting or a missing engineering/tooling component group."""

        path = Path(self.temporary_directory.name) / "targets.json"
        payload = self._target_manifest()
        payload["shots"]["pimm-30g--engineering--controls"]["groups"][
            "actuator_artwork"
        ] = []
        path.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "actuator_artwork.*nonempty stable-ID list"):
            self.module.load_target_manifest(path)

    def test_detail_bounds_resolve_by_stable_id_and_preserve_group_evidence(self):
        """Catches detail targeting by display name or loss of semantic target evidence."""

        config = self.module.SHOT_CONFIGS["pimm-30g--engineering--controls"]
        manifest = self._target_manifest()
        objects = [
            StableMesh("30g-gauge", (-10, -5, 100), (10, 5, 120), name="renamed-A"),
            StableMesh("30g-regulator", (20, -4, 80), (35, 4, 110), name="renamed-B"),
            StableMesh("30g-controller", (-25, -6, 130), (25, 6, 190), name="renamed-C"),
            StableMesh(
                "30g-actuator-artwork",
                (-8, -7, 60),
                (8, 7, 78),
                name="mutable display name",
            ),
        ]
        bpy = type(
            "Bpy",
            (),
            {"context": type("Context", (), {"scene": type("Scene", (), {"objects": objects})()})()},
        )()

        target = self.module.resolve_target_bounds(bpy, config, manifest)

        self.assertEqual(target.bounds_min, (-25.0, -7.0, 60.0))
        self.assertEqual(target.bounds_max, (35.0, 7.0, 190.0))
        self.assertEqual(
            target.groups["actuator_artwork"],
            ("30g-actuator-artwork",),
        )
        self.assertNotIn("mutable display name", target.stable_ids)

    def test_detail_bounds_reject_a_missing_artwork_stable_target(self):
        """Catches an engineering crop that silently omits the actuator artwork."""

        config = self.module.SHOT_CONFIGS["pimm-30g--engineering--controls"]
        manifest = self._target_manifest()
        objects = [
            StableMesh("30g-gauge", (-10, -5, 100), (10, 5, 120)),
            StableMesh("30g-regulator", (20, -4, 80), (35, 4, 110)),
            StableMesh("30g-controller", (-25, -6, 130), (25, 6, 190)),
        ]
        bpy = type(
            "Bpy",
            (),
            {"context": type("Context", (), {"scene": type("Scene", (), {"objects": objects})()})()},
        )()

        with self.assertRaisesRegex(ValueError, "missing artwork target"):
            self.module.resolve_target_bounds(bpy, config, manifest)

    def test_governed_camera_pose_keeps_target_bounds_inside_frame(self):
        """Catches focal-length or distance drift that crops the contracted target bounds."""

        for shot_id in (
            "pimm-30g--overview--three-quarter",
            "pimm-30g--engineering--controls",
            "pimm-30g--tooling--front-detail",
        ):
            with self.subTest(shot_id=shot_id):
                config = self.module.SHOT_CONFIGS[shot_id]
                bounds_min = (-200.0, -180.0, 0.0)
                bounds_max = (220.0, 160.0, 900.0)
                pose = self.module.camera_pose(bounds_min, bounds_max, config)
                frame = self.module.frame_coordinates(bounds_min, bounds_max, pose, config)
                self.assertGreaterEqual(min(x for x, _y in frame), 0.05)
                self.assertLessEqual(max(x for x, _y in frame), 0.95)
                self.assertGreaterEqual(min(y for _x, y in frame), 0.05)
                self.assertLessEqual(max(y for _x, y in frame), 0.95)

    def _contract_and_bytes(self, config):
        payload = self.module.contract_payload(config)
        contract = self.module.SceneContract.from_mapping(payload)
        return contract, json.dumps(payload, sort_keys=True).encode("utf-8")

    def _minimal_authoring_bpy(self, config, *, exposure=0.0):
        camera_data = SimpleNamespace(
            lens=config.focal_length_mm,
            sensor_width=36.0,
            sensor_fit="HORIZONTAL",
            shift_x=0.0,
            shift_y=0.0,
            dof=SimpleNamespace(use_dof=True, aperture_fstop=config.aperture_fstop),
        )
        camera = PropertyNamespace(
            name="CAM_PRODUCT",
            type="CAMERA",
            data=camera_data,
            library=None,
            location=(0.0, -3000.0, 450.0),
        )
        render = SimpleNamespace(
            engine="CYCLES",
            resolution_x=2400,
            resolution_y=1800,
            resolution_percentage=100,
            film_transparent=True,
            use_border=False,
            use_crop_to_border=False,
        )
        scene = PropertyNamespace(
            objects=[],
            camera=camera,
            render=render,
            view_settings=SimpleNamespace(
                view_transform="AgX",
                look="AgX - Medium High Contrast",
                exposure=exposure,
                gamma=1.0,
            ),
            unit_settings=SimpleNamespace(
                system="METRIC", length_unit="MILLIMETERS", scale_length=0.001
            ),
        )
        return SimpleNamespace(
            context=SimpleNamespace(scene=scene),
            data=SimpleNamespace(
                filepath=str(self.module._template_path(config)),
                collections=NamedStore(),
                libraries=[],
                materials=[],
                meshes=[],
                objects=NamedStore([camera]),
            ),
            ops=SimpleNamespace(
                wm=SimpleNamespace(
                    save_as_mainfile=lambda **_kwargs: self.fail(
                        "rejected authoring must not save a scene"
                    )
                )
            ),
        )

    def _call_author_with_configured_state(self, config, bpy, target, pose):
        contract, contract_bytes = self._contract_and_bytes(config)
        with (
            patch.object(
                self.module,
                "_load_authoring_contract",
                return_value=(contract, contract_bytes),
            ),
            patch.object(self.module, "_validate_open_template_authority"),
            patch.object(self.module, "_require_pinned_hdri"),
            patch.object(self.module, "resolve_target_bounds", return_value=target),
            patch.object(
                self.module,
                "_configure_authored_scene",
                return_value=(bpy.context.scene.camera, pose),
            ),
        ):
            return self.module.author_scene(bpy, config, self._target_manifest())

    def test_authoring_rejects_nonzero_exposure_after_configuration(self):
        """Catches scene setup leaving exposure compensation outside the governed zero value."""

        config = self.config
        target = self.module.TargetResolution(
            (-200.0, -180.0, 0.0),
            (220.0, 160.0, 900.0),
            {"complete_product": ("part",)},
            ("part",),
        )
        pose = self.module.camera_pose(target.bounds_min, target.bounds_max, config)
        bpy = self._minimal_authoring_bpy(config, exposure=0.25)

        with self.assertRaisesRegex(ValueError, "exposure"):
            self._call_author_with_configured_state(config, bpy, target, pose)

    def test_authoring_rejects_target_crop_outside_contracted_frame(self):
        """Catches a configured camera that crops the stable-ID target group."""

        config = self.config
        target = self.module.TargetResolution(
            (-200.0, -180.0, 0.0),
            (220.0, 160.0, 900.0),
            {"complete_product": ("part",)},
            ("part",),
        )
        pose = self.module.orbit_camera_pose(
            target.bounds_min, target.bounds_max, 100.0, -24.0, 0.0
        )
        bpy = self._minimal_authoring_bpy(config)

        with self.assertRaisesRegex(ValueError, "contracted frame"):
            self._call_author_with_configured_state(config, bpy, target, pose)

    def test_authoring_rejects_preexisting_destination_before_mutation(self):
        """Catches a static-shot authoring run overwriting an existing scene."""

        destination = self.module._scene_path(self.config)
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"approved-scene")
        bpy = self._minimal_authoring_bpy(self.config)

        with self.assertRaises(FileExistsError):
            self.module.author_scene(bpy, self.config, self._target_manifest())

        self.assertEqual(destination.read_bytes(), b"approved-scene")

    def test_authoring_rejects_wrong_hdri_hash_before_scene_mutation(self):
        """Catches a substituted environment image entering a governed scene."""

        config = self.config
        hdri = self.asset_root / "assets" / "hdri" / "studio_kontrast_04_4k.exr"
        hdri.parent.mkdir(parents=True)
        hdri.write_bytes(b"wrong-hdri")
        contract, contract_bytes = self._contract_and_bytes(config)
        bpy = self._minimal_authoring_bpy(config)

        with (
            patch.object(
                self.module,
                "_load_authoring_contract",
                return_value=(contract, contract_bytes),
            ),
            patch.object(self.module, "_validate_open_template_authority"),
        ):
            with self.assertRaisesRegex(ValueError, "HDRI SHA-256 mismatch"):
                self.module.author_scene(bpy, config, self._target_manifest())

    def test_authoring_rejects_local_product_mesh_and_localized_material(self):
        """Catches private geometry or localized governed materials entering the shot."""

        config = self.config
        contract, contract_bytes = self._contract_and_bytes(config)
        expected_master = self.module._master_path(config).resolve()
        material_path = (self.asset_root / "masters" / "PIMM-MATERIAL-LIBRARY.blend").resolve()

        for mutation in ("local_mesh", "localized_material"):
            with self.subTest(mutation=mutation):
                bpy = self._minimal_authoring_bpy(config)
                master_library = SimpleNamespace(filepath=str(expected_master))
                material_library = SimpleNamespace(filepath=str(material_path))
                linked_mesh_data = SimpleNamespace(library=master_library)
                linked_product = StableMesh("part", (-1, -1, 0), (1, 1, 2))
                linked_product.library = master_library
                linked_product.data = linked_mesh_data
                linked_product.material_slots = []
                published = SimpleNamespace(
                    name="PIMM_PUBLISHED",
                    library=master_library,
                    all_objects=[linked_product],
                )
                bpy.data.collections.append(published)
                bpy.data.libraries[:] = [master_library, material_library]
                bpy.data.objects.append(linked_product)
                bpy.context.scene.objects.append(linked_product)
                if mutation == "local_mesh":
                    local = StableMesh("private", (-1, -1, 0), (1, 1, 2))
                    local.library = None
                    local.data = SimpleNamespace(library=None)
                    local.material_slots = []
                    bpy.data.objects.append(local)
                    bpy.context.scene.objects.append(local)
                    expected = "scene-local product mesh"
                else:
                    localized = PropertyNamespace(
                        name="PIMM_METAL_DARK",
                        users=1,
                        library=None,
                    )
                    localized["pimm_material_id"] = "METAL_DARK"
                    bpy.data.materials.append(localized)
                    expected = "localized linked material"

                with patch.object(
                    self.module,
                    "_load_authoring_contract",
                    return_value=(contract, contract_bytes),
                ):
                    with self.assertRaisesRegex(ValueError, expected):
                        self.module.author_scene(bpy, config, self._target_manifest())

    def test_cli_exposes_inspection_and_manifest_gated_authoring_modes(self):
        """Catches Task 3 losing either the read-only inspection or manifest-gated author path."""

        shot_id = "pimm-30g--overview--three-quarter"
        inspected = self.module._arguments(["--shot-id", shot_id, "--inspect-targets"])
        self.assertTrue(inspected.inspect_targets)
        self.assertFalse(inspected.author_scene)

        manifest = Path(self.temporary_directory.name) / "targets.json"
        authored = self.module._arguments(
            [
                "--shot-id",
                shot_id,
                "--author-scene",
                "--target-manifest",
                str(manifest),
            ]
        )
        self.assertTrue(authored.author_scene)
        self.assertEqual(authored.target_manifest, manifest)

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                self.module._arguments(["--shot-id", shot_id, "--author-scene"])

    def test_linked_library_paths_use_blender_relative_path_resolution(self):
        """Catches //-relative library links being resolved against the process directory."""

        expected = self.asset_root / "masters" / "PIMM-30G-MASTER.blend"
        bpy = SimpleNamespace(path=SimpleNamespace(abspath=lambda _value: str(expected)))
        datablock = SimpleNamespace(library=SimpleNamespace(filepath="//../../masters/PIMM.blend"))

        self.assertEqual(
            self.module._resolved_library_path(bpy, datablock),
            expected.resolve(),
        )

    def setUp(self):
        self.module = self._module()
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.asset_root = Path(self.temporary_directory.name) / "blender-product-renders"
        self.original_asset_root = self.module.ASSET_ROOT
        self.module.ASSET_ROOT = self.asset_root
        self.addCleanup(setattr, self.module, "ASSET_ROOT", self.original_asset_root)
        masters = self.asset_root / "masters"
        masters.mkdir(parents=True)
        (masters / "PIMM-30G-MASTER.blend").write_bytes(b"master-30g")
        (masters / "PIMM-50G-MASTER.blend").write_bytes(b"master-50g")
        (masters / "PIMM-MATERIAL-LIBRARY.blend").write_bytes(b"material-library")
        self.config = self.module.SHOT_CONFIGS["pimm-30g--overview--three-quarter"]

    def test_contract_payload_is_hash_pinned_and_static(self):
        """Catches a payload that loses its master, material, alpha, or still-image guard."""

        payload = self.module.contract_payload(self.config)

        self.assertEqual(payload["scene_id"], "pimm-30g--overview--three-quarter")
        self.assertEqual(payload["purpose"], "overview")
        self.assertEqual(
            payload["scene_path"],
            "scenes/stills/pimm-30g--overview--three-quarter.blend",
        )
        self.assertEqual(payload["master_path"], "masters/PIMM-30G-MASTER.blend")
        self.assertEqual(
            payload["master_sha256"],
            "D660AAD870DB73EA104BC23B89F76DA188EAF286987DB4C6DFCDFB2565E65FFE",
        )
        self.assertEqual(payload["material_library_path"], "masters/PIMM-MATERIAL-LIBRARY.blend")
        self.assertEqual(
            payload["material_library_sha256"],
            "484DADB0DD2CD7DA59F26EF256C042E9ECF6D4466FB99B90E336F993E48246D1",
        )
        self.assertEqual(payload["master_collection"], "PIMM_PUBLISHED")
        self.assertTrue(payload["complete_product"])
        self.assertIsNone(payload["animation_contract"])
        self.assertEqual(payload["output_contract"], {"width": 2400, "height": 1800, "alpha": True})
        self.assertEqual(
            payload["static_render_setup"],
            {
                "camera": {
                    "aperture_fstop": 11.0,
                    "focal_length_mm": 85.0,
                    "sensor_width_mm": 36.0,
                    "view": "three-quarter",
                },
                "color_management": {
                    "exposure": 0.0,
                    "gamma": 1.0,
                    "look": "AgX - Medium High Contrast",
                    "view_transform": "AgX",
                },
                "lighting": {
                    "lower_bounce_name": "BASE_BOUNCE",
                    "required_light_names": [
                        "KEY_SOFTBOX",
                        "FILL_SOFTBOX",
                        "BASE_BOUNCE",
                        "STRIP_LEFT",
                        "STRIP_RIGHT",
                    ],
                    "temperature_kelvin": 5500.0,
                },
                "world": {
                    "hdri_path": "assets/hdri/studio_kontrast_04_4k.exr",
                    "hdri_sha256": "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06",
                    "rotation_degrees": 0.0,
                    "strength": 0.5,
                },
            },
        )

    def test_unknown_shot_id_is_rejected_before_contract_write(self):
        """Catches a CLI path that could create a contract for an ungoverned shot."""

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                self.module.main(["--shot-id", "pimm-30g--unknown--view", "--prepare-contract"])

        self.assertEqual(raised.exception.code, 2)
        self.assertFalse((self.asset_root / "scenes" / "contracts").exists())

    def test_scene_contract_rejects_static_render_setup_or_scene_path_drift(self):
        """Catches a consumer changing the governed setup after contract preparation."""

        payload = self.module.contract_payload(self.config)
        mutations = (
            ("scene_path", "scenes/stills/unrelated.blend"),
            ("static_render_setup", {"world": {}}),
        )
        for key, replacement in mutations:
            with self.subTest(key=key):
                mutated = deepcopy(payload)
                mutated[key] = replacement
                contract = self.module.SceneContract.from_mapping(mutated)
                self.assertTrue(self.module.validate_scene_contract(contract))

        mutated = deepcopy(payload)
        mutated["static_render_setup"]["camera"]["aperture_fstop"] = 8.0
        contract = self.module.SceneContract.from_mapping(mutated)
        self.assertIn(
            "static product camera must match the governed shot configuration",
            self.module.validate_scene_contract(contract),
        )

        for setup_area, field, replacement in (
            ("color_management", "gamma", 0.9),
            ("lighting", "temperature_kelvin", 5000.0),
            ("world", "hdri_sha256", "0" * 64),
        ):
            with self.subTest(setup_area=setup_area, field=field):
                mutated = deepcopy(payload)
                mutated["static_render_setup"][setup_area][field] = replacement
                contract = self.module.SceneContract.from_mapping(mutated)
                self.assertTrue(self.module.validate_scene_contract(contract))

    def test_governed_static_shot_requires_scene_path_and_render_setup(self):
        """Catches a known static scene silently falling back to the legacy contract shape."""

        payload = self.module.contract_payload(self.config)
        payload.pop("scene_path")
        payload.pop("static_render_setup")

        contract = self.module.SceneContract.from_mapping(payload)

        self.assertIn(
            "governed static product scene contracts require scene_path and static_render_setup",
            self.module.validate_scene_contract(contract),
        )

    def test_existing_contract_is_never_overwritten(self):
        """Catches preparation replacing a previously approved contract file."""

        destination = self.asset_root / "scenes" / "contracts" / f"{self.config.scene_id}.json"
        destination.parent.mkdir(parents=True)
        destination.write_text('{"approved": true}\n', encoding="utf-8")

        with self.assertRaises(FileExistsError):
            self.module.prepare_contract(self.config)

        self.assertEqual(destination.read_text(encoding="utf-8"), '{"approved": true}\n')

    def test_invalid_static_configurations_are_rejected_before_contract_write(self):
        """Catches unauthorised optics, animation, or resolution reaching contract I/O."""

        invalid_configs = (
            replace(self.config, focal_length_mm=100.0),
            replace(self.config, animation_contract="turntable"),
            replace(self.config, output_width=1920),
        )

        for config in invalid_configs:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    self.module.prepare_contract(config)
                self.assertFalse((self.asset_root / "scenes" / "contracts").exists())

    def test_contract_destination_outside_contracts_is_rejected_before_write(self):
        """Catches path construction escaping the governed contracts directory."""

        outside_destination = self.asset_root / "scenes" / "outside.json"

        with patch.object(self.module, "_contract_path", return_value=outside_destination):
            with self.assertRaises(ValueError):
                self.module.prepare_contract(self.config)

        self.assertFalse(outside_destination.exists())
        self.assertFalse((self.asset_root / "scenes" / "contracts").exists())


if __name__ == "__main__":
    unittest.main()
