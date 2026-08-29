"""Regression coverage for governed PIMM static-product scene contracts."""

from __future__ import annotations

from contextlib import redirect_stderr
from copy import deepcopy
from io import StringIO
import hashlib
import importlib
import importlib.util
from dataclasses import replace
import json
import math
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch


MODULE = "scripts.blender.pimm_production.blender_static_product_scene"
BLENDER = Path(r"D:\Blender 5.2\blender.exe")
REPO_ROOT = Path(__file__).resolve().parents[4]

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
        """Catches the authoring registry drifting from campaign-owned shot policy."""

        module = self._module()
        campaign = module.load_campaign(module.CAMPAIGN_PATH)
        self.assertEqual(module.validate_campaign(campaign), [])
        self.assertEqual(set(module.SHOT_CONFIGS), set(campaign.by_shot_id))
        self.assertEqual(len(module.SHOT_CONFIGS), 22)
        for shot_id, policy in campaign.by_shot_id.items():
            config = module.SHOT_CONFIGS[shot_id]
            self.assertEqual(config.machines, policy.machines)
            self.assertEqual(config.purpose, policy.purpose)
            self.assertEqual(config.view, module.composition_for(shot_id).camera_view)
            self.assertEqual(config.focal_length_mm, policy.focal_length_mm)
            self.assertEqual(config.aperture_fstop, policy.aperture_fstop)
            self.assertEqual((config.output_width, config.output_height), (policy.width, policy.height))
            self.assertIs(config.alpha, policy.alpha)
            self.assertIsNone(config.animation_contract)

    def test_camera_optics_accept_blender_float_storage_precision_only(self):
        """Catches exact-float comparisons rejecting authored camera shift values."""

        module = self._module()
        config = module.SHOT_CONFIGS["pimm-30g--hero--desktop"]
        camera_data = SimpleNamespace(
            lens=85.0,
            sensor_width=36.0,
            shift_x=-0.2199999988079071,
            shift_y=0.0,
            dof=SimpleNamespace(aperture_fstop=11.0),
        )
        self.assertTrue(module._camera_optics_match(camera_data, config))
        camera_data.shift_x = -0.21
        self.assertFalse(module._camera_optics_match(camera_data, config))
        self.assertTrue(
            module._numeric_values_match(
                (250.0, 0.0, 0.0000034550001),
                (250.0, 0.0, 0.000003455),
            )
        )

    def test_live_foot_contact_uses_current_master_geometry_not_stale_patch(self):
        """Catches a historical patch lowering the catcher below the current feet."""

        module = self._module()
        resolver = getattr(module, "resolve_live_foot_contact_planes", None)
        self.assertIsNotNone(resolver, "live master foot-contact resolver must exist")
        if resolver is None:
            return
        config = module.SHOT_CONFIGS["pimm-30g--hero--desktop"]
        bottoms = (0.000001223, -0.000008132, 0.000001223, -0.000003455)
        feet = {
            f"30G-{suffix}": StableMesh(
                f"30G-{suffix}",
                (index * 50.0, 0.0, bottom),
                (index * 50.0 + 20.0, 20.0, bottom + 2.74),
                name=f"30G__nylon-feet__{suffix}",
            )
            for index, (suffix, bottom) in enumerate(
                zip(("64039c77f719dbec", "1a7f1009f15a7ee4", "7419ee7fe262373b", "d81608e985bd200f"), bottoms)
            )
        }
        stale = module.FootContactPlane(
            z=-0.162624216,
            pad_bottoms=(-0.162624216,) * 4,
            stable_ids=tuple(f"30G-stale-{index}" for index in range(4)),
            outlier_stable_ids=(),
        )
        with patch.object(module, "_stable_product_objects", return_value=feet), patch.object(
            module, "load_foot_contact_planes", return_value={"30G": stale}
        ):
            contact = resolver(SimpleNamespace(), config)["30G"]
        self.assertAlmostEqual(contact.z, -0.000001116, places=9)
        self.assertEqual(contact.pad_bottoms, bottoms)
        self.assertEqual(set(contact.stable_ids), set(feet))
        self.assertEqual(contact.outlier_stable_ids, ())

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

    def test_foot_contact_plane_uses_majority_pad_height_not_low_outlier(self):
        """Catches one malformed foot lowering the studio ground below three valid feet."""

        module = self._module()
        payload = {
            "kind": "PIMM_FOOT_GEOMETRY_PATCH",
            "machine": "50G",
            "schema_version": 1,
            "solids": [
                {
                    "original_name": "nylon feet",
                    "stable_id": stable_id,
                    "geometry": {"bounds": [-1, -1, bottom, 1, 1, bottom + 3]},
                }
                for stable_id, bottom in (
                    ("pad-a", -0.162624216),
                    ("pad-b", -0.162624216),
                    ("pad-c", -0.162624216),
                    ("pad-d", -4.825847972),
                )
            ],
        }

        contact = module.resolve_foot_contact_plane(payload, "50G")

        self.assertAlmostEqual(contact.z, -0.162624216)
        self.assertEqual(contact.stable_ids, ("pad-a", "pad-b", "pad-c", "pad-d"))
        self.assertEqual(contact.outlier_stable_ids, ("pad-d",))

    def test_foot_contact_plane_rejects_incomplete_or_wrong_machine_patch(self):
        """Catches grounding from an incomplete or cross-machine foot manifest."""

        module = self._module()
        payload = {
            "kind": "PIMM_FOOT_GEOMETRY_PATCH",
            "machine": "30G",
            "schema_version": 1,
            "solids": [
                {
                    "original_name": "nylon feet",
                    "stable_id": f"pad-{index}",
                    "geometry": {"bounds": [-1, -1, 0, 1, 1, 3]},
                }
                for index in range(3)
            ],
        }

        with self.assertRaisesRegex(ValueError, "machine mismatch"):
            module.resolve_foot_contact_plane(payload, "50G")
        with self.assertRaisesRegex(ValueError, "exactly four nylon foot pads"):
            module.resolve_foot_contact_plane(payload, "30G")

    def test_contact_environment_replaces_only_shadow_catcher_height(self):
        """Catches a grounding fix drifting the approved studio floor dimensions."""

        module = self._module()
        original = module.studio_environment_specs(
            (-200.0, -130.0, -4.825847972),
            (200.0, 130.0, 900.0),
        )
        corrected = module.contact_environment_specs(original, -0.162624216)

        self.assertEqual(len(corrected), 1)
        self.assertAlmostEqual(corrected[0].z, -0.162624216)
        self.assertEqual(corrected[0].width, original[0].width)
        self.assertEqual(corrected[0].depth, original[0].depth)
        self.assertEqual(corrected[0].base_color, original[0].base_color)

    def _target_manifest(self):
        shots = {
            config.scene_id: {
                "groups": {
                    name: list(identifiers)
                    for name, identifiers in self.module.composition_for(
                        config.scene_id
                    ).target_groups.items()
                }
            }
            for config in self.module.SHOT_CONFIGS.values()
            if config.purpose == "detail"
        }
        return {"schema_version": 1, "shots": shots}

    def test_target_manifest_requires_every_semantic_stable_id_group(self):
        """Catches mutable-name targeting or a missing engineering/tooling component group."""

        path = (
            self.asset_root
            / "manifests"
            / "PIMM-static-shot-targets-v1.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._target_manifest()
        payload["shots"]["pimm-30g--pneumatics--macro"]["groups"][
            "airtac_artwork"
        ] = []
        path.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "airtac_artwork.*composition stable-ID list"):
            self.module.load_target_manifest(path)

    def test_detail_bounds_resolve_by_stable_id_and_preserve_group_evidence(self):
        """Catches detail targeting by display name or loss of semantic target evidence."""

        config = self.module.SHOT_CONFIGS["pimm-30g--controls--macro"]
        _manifest_path, manifest = self._write_canonical_target_manifest()
        identifiers = self.module.composition_for(config.scene_id).target_stable_ids
        objects = [
            StableMesh(
                stable_id,
                (-25 + index * 5, -7, 60 + index * 10),
                (10 + index * 5, 7, 100 + index * 15),
                name="mutable display name" if index == 0 else f"renamed-{index}",
            )
            for index, stable_id in enumerate(identifiers)
        ]
        bpy = type(
            "Bpy",
            (),
            {"context": type("Context", (), {"scene": type("Scene", (), {"objects": objects})()})()},
        )()

        target = self.module.resolve_target_bounds(bpy, config, manifest)

        self.assertEqual(target.bounds_min, (-25.0, -7.0, 60.0))
        self.assertEqual(target.bounds_max, (25.0, 7.0, 145.0))
        self.assertEqual(
            target.groups["controller_segments"],
            self.module.composition_for(config.scene_id).target_groups[
                "controller_segments"
            ],
        )
        self.assertNotIn("mutable display name", target.stable_ids)

    def test_detail_bounds_reject_a_missing_artwork_stable_target(self):
        """Catches an engineering crop that silently omits the actuator artwork."""

        config = self.module.SHOT_CONFIGS["pimm-30g--pneumatics--macro"]
        _manifest_path, manifest = self._write_canonical_target_manifest()
        composition = self.module.composition_for(config.scene_id)
        omitted = composition.target_groups["airtac_artwork"][0]
        objects = [
            StableMesh(stable_id, (-10, -5, 100), (10, 5, 120))
            for stable_id in composition.target_stable_ids
            if stable_id != omitted
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
            "pimm-30g--hero--desktop",
            "pimm-30g--hero--tablet",
            "pimm-30g--controls--macro",
        ):
            with self.subTest(shot_id=shot_id):
                config = self.module.SHOT_CONFIGS[shot_id]
                bounds_min = (-200.0, -180.0, 0.0)
                bounds_max = (220.0, 160.0, 900.0)
                pose = self.module.camera_pose(bounds_min, bounds_max, config)
                frame = self.module.frame_coordinates(bounds_min, bounds_max, pose, config)
                placement = self.module.composition_for(shot_id).subject_placement
                self.assertGreaterEqual(min(x for x, _y in frame), placement.clearance_left)
                self.assertLessEqual(max(x for x, _y in frame), 1.0 - placement.clearance_right)
                self.assertGreaterEqual(min(y for _x, y in frame), placement.clearance_top)
                self.assertLessEqual(max(y for _x, y in frame), 1.0 - placement.clearance_bottom)

    def test_camera_distances_keep_exact_reviewed_margin_policy(self):
        """Catches a full-machine camera moving inside the three-height minimum."""

        bounds_min = (-200.0, -180.0, 0.0)
        bounds_max = (220.0, 160.0, 900.0)
        desktop = self.module.camera_pose(
            bounds_min,
            bounds_max,
            self.module.SHOT_CONFIGS["pimm-30g--hero--desktop"],
        )
        tablet = self.module.camera_pose(
            bounds_min,
            bounds_max,
            self.module.SHOT_CONFIGS["pimm-30g--hero--tablet"],
        )
        detail = self.module.camera_pose(
            bounds_min,
            bounds_max,
            self.module.SHOT_CONFIGS["pimm-30g--controls--macro"],
        )

        self.assertGreaterEqual(math.dist(desktop.location, desktop.target), 2700.0)
        self.assertGreaterEqual(math.dist(tablet.location, tablet.target), 2700.0)
        self.assertGreaterEqual(math.dist(detail.location, detail.target), 900.0)
        self.assertEqual(desktop.target, (10.0, -10.0, 450.0))
        self.assertEqual(tablet.target, (10.0, -10.0, 450.0))
        self.assertEqual(detail.target, (10.0, -10.0, 450.0))

    def test_profile_rig_has_exact_broad_lights_cards_and_frustum_safe_catcher(self):
        """Catches a profile losing reflection control or exposing a finite floor edge."""

        config = self.module.SHOT_CONFIGS["pimm-30g--hero--desktop"]
        bounds_min = (-200.0, -180.0, 0.0)
        bounds_max = (220.0, 160.0, 900.0)
        pose = self.module.camera_pose(bounds_min, bounds_max, config)

        lights, supports = self.module.profile_rig_specs(
            bounds_min, bounds_max, pose, config
        )

        self.assertEqual(tuple(item.name for item in lights), self.module.MANAGED_LIGHT_NAMES)
        cards = tuple(item.name for item in supports if item.role == "reflection-card")
        self.assertEqual(cards, self.module.MANAGED_REFLECTION_CARD_NAMES)
        catcher = next(item for item in supports if item.role == "shadow-catcher")
        self.assertEqual(catcher.name, "PIMM_SCENE_SHADOW_CATCHER")
        self.assertTrue(self.module.catcher_edges_outside_camera_frustum(catcher, pose, config))

    def test_comparison_authority_covers_both_masters_and_contact_planes(self):
        """Catches comparison authoring falling back to a one-machine helper."""

        module = self._module()
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            original = module.ASSET_ROOT
            module.ASSET_ROOT = root
            self.addCleanup(setattr, module, "ASSET_ROOT", original)
            masters = root / "masters"
            patches = root / "manifests" / "patches"
            masters.mkdir(parents=True)
            patches.mkdir(parents=True)
            for machine, contact_z in (("30G", -0.25), ("50G", -0.5)):
                (masters / f"PIMM-{machine}-MASTER.blend").write_bytes(
                    f"master-{machine}".encode("ascii")
                )
                payload = {
                    "kind": "PIMM_FOOT_GEOMETRY_PATCH",
                    "machine": machine,
                    "schema_version": 1,
                    "solids": [
                        {
                            "original_name": "nylon feet",
                            "stable_id": f"{machine}-pad-{index}",
                            "geometry": {
                                "bounds": [-1, -1, contact_z, 1, 1, contact_z + 1]
                            },
                        }
                        for index in range(4)
                    ],
                }
                (patches / f"PIMM-{machine}-foot-refresh.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )

            config = module.SHOT_CONFIGS["pimm-30g-50g--comparison--desktop"]
            self.assertEqual(
                tuple(path.name for path in module._master_paths(config)),
                ("PIMM-30G-MASTER.blend", "PIMM-50G-MASTER.blend"),
            )
            contacts = module.load_foot_contact_planes(config)
            self.assertEqual(set(contacts), {"30G", "50G"})
            plan = module.comparison_link_plan(
                module.composition_for(config.scene_id),
                {machine: contact.z for machine, contact in contacts.items()},
            )
            self.assertEqual({item.resolved_ground_z for item in plan}, {0.0})

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime is unavailable")
    def test_comparison_author_scene_executes_desktop_and_mobile_in_blender(self):
        """Catches a comparison plan that has no executable two-master authoring caller."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            fixture = root / "comparison_authoring_fixture.py"
            fixture.write_text(
                textwrap.dedent(
                    """
                    import json
                    from pathlib import Path
                    from types import SimpleNamespace
                    import sys

                    import bpy

                    root = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
                    repository = Path(sys.argv[sys.argv.index("--") + 2]).resolve()
                    sys.path.insert(0, str(repository))
                    import scripts.blender.pimm_production.blender_static_product_scene as authoring
                    import scripts.blender.pimm_production.blender_scene_validator as validator

                    masters = root / "masters"
                    templates = root / "scenes" / "shared-templates"
                    contracts = root / "scenes" / "contracts"
                    patches = root / "manifests" / "patches"
                    for path in (masters, templates, contracts, patches):
                        path.mkdir(parents=True, exist_ok=True)

                    material_path = masters / "PIMM-MATERIAL-LIBRARY.blend"
                    bpy.ops.wm.read_factory_settings(use_empty=True)
                    material = bpy.data.materials.new("PIMM_FIXTURE_SHARED")
                    material["pimm_material_id"] = "FIXTURE_SHARED"
                    material["pimm_material_scope"] = "shared"
                    material.use_fake_user = True
                    bpy.ops.wm.save_as_mainfile(filepath=str(material_path), check_existing=False)

                    for machine, contact_z, width in (("30G", -0.25, 200.0), ("50G", -0.5, 260.0)):
                        bpy.ops.wm.read_factory_settings(use_empty=True)
                        with bpy.data.libraries.load(str(material_path), link=True) as (available, requested):
                            requested.materials = ["PIMM_FIXTURE_SHARED"]
                        published = bpy.data.collections.new("PIMM_PUBLISHED")
                        bpy.context.scene.collection.children.link(published)
                        mesh = bpy.data.meshes.new(f"{machine}_FIXTURE_MESH")
                        mesh.from_pydata(
                            [
                                (-width, -100.0, contact_z),
                                (width, -100.0, contact_z),
                                (width, 100.0, 800.0),
                                (-width, 100.0, 800.0),
                            ],
                            [],
                            [(0, 1, 2, 3)],
                        )
                        mesh.materials.append(bpy.data.materials["PIMM_FIXTURE_SHARED"])
                        product = bpy.data.objects.new(f"{machine}_FIXTURE_PRODUCT", mesh)
                        product["pimm_stable_id"] = f"{machine}-fixture-product"
                        published.objects.link(product)
                        for index, (x, y) in enumerate(
                            ((-150.0, -70.0), (-150.0, 70.0), (150.0, -70.0), (150.0, 70.0))
                        ):
                            foot_mesh = bpy.data.meshes.new(f"{machine}_FIXTURE_FOOT_{index}")
                            foot_mesh.from_pydata(
                                [
                                    (x - 5.0, y - 5.0, contact_z),
                                    (x + 5.0, y - 5.0, contact_z),
                                    (x + 5.0, y + 5.0, contact_z + 10.0),
                                    (x - 5.0, y + 5.0, contact_z + 10.0),
                                ],
                                [],
                                [(0, 1, 2, 3)],
                            )
                            foot_mesh.materials.append(bpy.data.materials["PIMM_FIXTURE_SHARED"])
                            foot = bpy.data.objects.new(
                                f"{machine}__nylon-feet__fixture-{index}", foot_mesh
                            )
                            foot["pimm_stable_id"] = f"{machine}-fixture-foot-{index}"
                            published.objects.link(foot)
                        bpy.ops.wm.save_as_mainfile(
                            filepath=str(masters / f"PIMM-{machine}-MASTER.blend"),
                            check_existing=False,
                        )
                        patch = {
                            "kind": "PIMM_FOOT_GEOMETRY_PATCH",
                            "machine": machine,
                            "schema_version": 1,
                            "solids": [
                                {
                                    "original_name": "nylon feet",
                                    "stable_id": f"{machine}-pad-{index}",
                                    "geometry": {"bounds": [-1, -1, contact_z, 1, 1, contact_z + 1]},
                                }
                                for index in range(4)
                            ],
                        }
                        (patches / f"PIMM-{machine}-foot-refresh.json").write_text(
                            json.dumps(patch), encoding="utf-8"
                        )

                    template = templates / "pimm-30g-50g--comparison.blend"
                    bpy.ops.wm.read_factory_settings(use_empty=True)
                    bpy.ops.wm.save_as_mainfile(filepath=str(template), check_existing=False)

                    authoring.ASSET_ROOT = root
                    validator.ASSET_ROOT = root
                    shots = {}
                    for config in authoring.SHOT_CONFIGS.values():
                        if config.purpose != "detail":
                            continue
                        groups = authoring.composition_for(config.scene_id).target_groups
                        shots[config.scene_id] = {
                            "groups": {name: list(values) for name, values in groups.items()}
                        }
                    target_path = root / "manifests" / "PIMM-static-shot-targets-v1.json"
                    target_path.write_text(
                        json.dumps({"schema_version": 1, "shots": shots}), encoding="utf-8"
                    )
                    manifest = authoring.load_target_manifest(target_path)
                    authoring._run_fresh_validation = lambda *_args: []
                    authoring._require_pinned_hdri = lambda: SimpleNamespace(
                        path=root / "unused.exr", sha256="0" * 64,
                        strength=0.5, rotation_degrees=0.0,
                    )
                    authoring._install_world_environment = lambda *_args: None

                    results = []
                    for shot_id in (
                        "pimm-30g-50g--comparison--desktop",
                        "pimm-30g-50g--comparison--mobile",
                    ):
                        config = authoring.SHOT_CONFIGS[shot_id]
                        contract_path = contracts / f"{shot_id}.json"
                        contract_path.write_text(
                            json.dumps(authoring.contract_payload(config)), encoding="utf-8"
                        )
                        bpy.ops.wm.open_mainfile(filepath=str(template))
                        result = authoring.author_scene(bpy, config, manifest)
                        contacts = authoring.resolve_live_foot_contact_planes(bpy, config)
                        comparison_errors = validator._validate_comparison_runtime_state(
                            bpy, config, contacts, root
                        )
                        instances = sorted(
                            (
                                obj for obj in bpy.context.scene.objects
                                if getattr(obj, "instance_type", None) == "COLLECTION"
                            ),
                            key=lambda obj: obj.name,
                        )
                        results.append(
                            {
                                "shot_id": shot_id,
                                "status": result["status"],
                                "instances": [obj.name for obj in instances],
                                "scales": [list(obj.scale) for obj in instances],
                                "grounds": [
                                    obj.get("pimm_resolved_ground_z") for obj in instances
                                ],
                                "comparison_errors": comparison_errors,
                                "output_exists": Path(result["path"]).is_file(),
                            }
                        )
                    print("PIMM_COMPARISON_FIXTURE_JSON=" + json.dumps(results, sort_keys=True))
                    """
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(BLENDER),
                    "--factory-startup",
                    "--background",
                    "--python",
                    str(fixture),
                    "--",
                    str(root),
                    str(REPO_ROOT),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            marker = "PIMM_COMPARISON_FIXTURE_JSON="
            lines = [line for line in result.stdout.splitlines() if line.startswith(marker)]
            self.assertEqual(len(lines), 1, result.stdout + result.stderr)
            line = lines[0]
            payload = json.loads(line.removeprefix(marker))
            self.assertEqual([item["status"] for item in payload], ["scene_created"] * 2)
            self.assertTrue(all(item["output_exists"] for item in payload))
            self.assertTrue(
                all(
                    item["instances"] == ["PIMM_30G_INSTANCE", "PIMM_50G_INSTANCE"]
                    and item["scales"] == [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]
                    and item["grounds"] == [0.0, 0.0]
                    and item["comparison_errors"] == []
                    for item in payload
                ),
                payload,
            )

    def test_workshop_provenance_records_are_read_and_hash_verified(self):
        """Catches workshop authoring ignoring empty, valid, drifted, or unrecorded assets."""

        module = self._module()
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            original = module.ASSET_ROOT
            module.ASSET_ROOT = root
            self.addCleanup(setattr, module, "ASSET_ROOT", original)
            manifests = root / "manifests"
            assets = root / "assets" / "props"
            manifests.mkdir(parents=True)
            assets.mkdir(parents=True)
            config = module.SHOT_CONFIGS["pimm-50g--workshop--wide"]
            manifest_path = manifests / "external-assets-v1.json"
            manifest_path.write_text(
                json.dumps({"schema": "maliev.pimm-external-assets/v1", "assets": []}),
                encoding="utf-8",
            )
            self.assertEqual(module.load_workshop_support_records(config), ())

            unrecorded = assets / "unrecorded.blend"
            unrecorded.write_bytes(b"unrecorded")
            self.assertEqual(module.load_workshop_support_records(config), ())

            support = assets / "fixture.blend"
            support.write_bytes(b"approved-support")
            digest = hashlib.sha256(support.read_bytes()).hexdigest().upper()
            record = {
                "source_url": "https://polyhaven.com/a/fixture",
                "asset_version_id": "fixture-1.0",
                "license": "CC0-1.0",
                "local_relative_path": "assets/props/fixture.blend",
                "sha256": digest,
                "intended_shot_ids": [config.scene_id],
                "machine_master_modified": False,
            }
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": "maliev.pimm-external-assets/v1",
                        "assets": [record],
                    }
                ),
                encoding="utf-8",
            )
            approved = module.load_workshop_support_records(config)
            self.assertEqual(len(approved), 1)
            self.assertEqual(approved[0].asset_version_id, "fixture-1.0")
            self.assertEqual(approved[0].path, support.resolve())

            support.write_bytes(b"drifted-support")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                module.load_workshop_support_records(config)

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime is unavailable")
    def test_workshop_loader_appends_only_hash_verified_non_product_supports(self):
        """Catches approved workshop records that are validated but never safely loaded."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            fixture = root / "workshop_support_fixture.py"
            fixture.write_text(
                textwrap.dedent(
                    """
                    import hashlib
                    import json
                    from pathlib import Path
                    import sys

                    import bpy

                    root = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
                    repository = Path(sys.argv[sys.argv.index("--") + 2]).resolve()
                    sys.path.insert(0, str(repository))
                    import scripts.blender.pimm_production.blender_static_product_scene as authoring
                    import scripts.blender.pimm_production.blender_scene_validator as validator

                    props = root / "assets" / "props"
                    manifests = root / "manifests"
                    masters = root / "masters"
                    for path in (props, manifests, masters):
                        path.mkdir(parents=True, exist_ok=True)
                    master = masters / "PIMM-50G-MASTER.blend"
                    master.write_bytes(b"immutable-50g-master")

                    def build_support(path, product_like=False, material_like=False, mesh_count=1):
                        bpy.ops.wm.read_factory_settings(use_empty=True)
                        collection = bpy.data.collections.new("FIXTURE_SUPPORT")
                        bpy.context.scene.collection.children.link(collection)
                        for index in range(mesh_count):
                            mesh = bpy.data.meshes.new(f"FIXTURE_SUPPORT_MESH_{index}")
                            mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
                            material = bpy.data.materials.new(f"FIXTURE_SUPPORT_MATERIAL_{index}")
                            if material_like:
                                material["pimm_material_id"] = "BLACK_POWDERCOAT"
                            mesh.materials.append(material)
                            obj = bpy.data.objects.new(f"FIXTURE_SUPPORT_OBJECT_{index}", mesh)
                            if product_like:
                                obj["pimm_stable_id"] = "50G-forbidden-support-product"
                            collection.objects.link(obj)
                        bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)

                    valid_path = props / "valid-support.blend"
                    product_path = props / "product-like.blend"
                    material_path = props / "material-like.blend"
                    unrecorded_path = props / "unrecorded.blend"
                    build_support(valid_path, mesh_count=2)
                    build_support(product_path, product_like=True)
                    build_support(material_path, material_like=True)
                    unrecorded_path.write_bytes(b"unrecorded")
                    authoring.ASSET_ROOT = root
                    validator.ASSET_ROOT = root
                    config = authoring.SHOT_CONFIGS["pimm-50g--workshop--wide"]
                    manifest_path = manifests / "external-assets-v1.json"

                    def digest(path):
                        return hashlib.sha256(path.read_bytes()).hexdigest().upper()

                    def record(path, version):
                        return {
                            "source_url": f"https://polyhaven.com/a/{version}",
                            "asset_version_id": version,
                            "license": "CC0-1.0",
                            "local_relative_path": f"assets/props/{path.name}",
                            "sha256": digest(path),
                            "intended_shot_ids": [config.scene_id],
                            "machine_master_modified": False,
                        }

                    def write_manifest(records):
                        manifest_path.write_text(
                            json.dumps({"schema": "maliev.pimm-external-assets/v1", "assets": records}),
                            encoding="utf-8",
                        )

                    bpy.ops.wm.read_factory_settings(use_empty=True)
                    write_manifest([])
                    empty = authoring.load_workshop_support_assets(bpy, config)
                    unrecorded = authoring.load_workshop_support_assets(bpy, config)

                    bpy.ops.wm.read_factory_settings(use_empty=True)
                    write_manifest([record(valid_path, "valid-1.0")])
                    before = digest(master)
                    loaded = authoring.load_workshop_support_assets(bpy, config)
                    after = digest(master)
                    tagged = [
                        obj for obj in bpy.context.scene.objects
                        if obj.get("pimm_scene_support_ownership") == "scene-support"
                    ]
                    tagged_asset_id = tagged[0].get("pimm_external_asset_version_id")
                    authoring._install_profile_supports(bpy, ())
                    retained = [
                        obj for obj in bpy.context.scene.objects
                        if obj.get("pimm_external_asset_version_id") == "valid-1.0"
                    ]
                    scene_evidence = json.dumps(
                        [
                            {
                                "asset_version_id": "valid-1.0",
                                "local_relative_path": "assets/props/valid-support.blend",
                                "sha256": digest(valid_path),
                            }
                        ],
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    bpy.context.scene["pimm_workshop_support_evidence"] = scene_evidence
                    reopened_path = root / "workshop-reopened.blend"
                    bpy.ops.wm.save_as_mainfile(filepath=str(reopened_path), check_existing=False)
                    bpy.ops.wm.open_mainfile(filepath=str(reopened_path))

                    def support_records():
                        return [
                            {
                                "name": obj.name,
                                "ownership": obj.get("pimm_scene_support_ownership"),
                                "asset_version_id": obj.get("pimm_external_asset_version_id"),
                                "local_relative_path": obj.get("pimm_external_asset_local_relative_path"),
                                "sha256": obj.get("pimm_external_asset_sha256"),
                                "member_count": obj.get("pimm_external_asset_member_count"),
                                "member_names": json.loads(
                                    obj.get("pimm_external_asset_member_names")
                                ),
                            }
                            for obj in bpy.context.scene.objects
                            if obj.type == "MESH"
                            and obj.get("pimm_external_asset_version_id") is not None
                        ]

                    records = support_records()
                    reopened_valid = validator._validate_workshop_runtime_state(
                        bpy.context.scene, config.scene_id, records, root
                    )
                    member_hash = [dict(item) for item in records]
                    member_hash[0]["sha256"] = "0" * 64
                    member_hash_rejected = bool(
                        validator._validate_workshop_runtime_state(
                            bpy.context.scene, config.scene_id, member_hash, root
                        )
                    )
                    member_id = [dict(item) for item in records]
                    member_id[0]["asset_version_id"] = "rogue-member"
                    member_id_rejected = bool(
                        validator._validate_workshop_runtime_state(
                            bpy.context.scene, config.scene_id, member_id, root
                        )
                    )
                    missing_member_rejected = bool(
                        validator._validate_workshop_runtime_state(
                            bpy.context.scene, config.scene_id, records[1:], root
                        )
                    )
                    valid = {
                        "count": len(loaded),
                        "tagged": len(tagged),
                        "retained_after_rig": len(retained),
                        "asset_id": tagged_asset_id,
                        "master_unchanged": before == after,
                        "reopened_valid": reopened_valid,
                        "member_hash_rejected": member_hash_rejected,
                        "member_id_rejected": member_id_rejected,
                        "missing_member_rejected": missing_member_rejected,
                    }

                    bpy.ops.wm.read_factory_settings(use_empty=True)
                    drift_record = record(valid_path, "drift-1.0")
                    write_manifest([drift_record])
                    valid_path.write_bytes(valid_path.read_bytes() + b"drift")
                    try:
                        authoring.load_workshop_support_assets(bpy, config)
                    except ValueError as error:
                        hash_drift = "SHA-256" in str(error)
                    else:
                        hash_drift = False

                    bpy.ops.wm.read_factory_settings(use_empty=True)
                    write_manifest([record(product_path, "product-1.0")])
                    try:
                        authoring.load_workshop_support_assets(bpy, config)
                    except ValueError as error:
                        product_rejected = "product-like" in str(error)
                    else:
                        product_rejected = False

                    bpy.ops.wm.read_factory_settings(use_empty=True)
                    write_manifest([record(material_path, "material-1.0")])
                    try:
                        authoring.load_workshop_support_assets(bpy, config)
                    except ValueError as error:
                        material_rejected = "product-like" in str(error)
                    else:
                        material_rejected = False

                    print(
                        "PIMM_WORKSHOP_FIXTURE_JSON="
                        + json.dumps(
                            {
                                "empty": len(empty),
                                "unrecorded": len(unrecorded),
                                "valid": valid,
                                "hash_drift": hash_drift,
                                "product_rejected": product_rejected,
                                "material_rejected": material_rejected,
                            },
                            sort_keys=True,
                        )
                    )
                    """
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    str(BLENDER),
                    "--factory-startup",
                    "--background",
                    "--python",
                    str(fixture),
                    "--",
                    str(root),
                    str(REPO_ROOT),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            marker = "PIMM_WORKSHOP_FIXTURE_JSON="
            lines = [line for line in result.stdout.splitlines() if line.startswith(marker)]
            self.assertEqual(len(lines), 1, result.stdout + result.stderr)
            payload = json.loads(lines[0].removeprefix(marker))
            self.assertEqual(payload["empty"], 0)
            self.assertEqual(payload["unrecorded"], 0)
            self.assertEqual(
                payload["valid"],
                {
                    "count": 1,
                    "tagged": 2,
                    "retained_after_rig": 2,
                    "asset_id": "valid-1.0",
                    "master_unchanged": True,
                    "reopened_valid": [],
                    "member_hash_rejected": True,
                    "member_id_rejected": True,
                    "missing_member_rejected": True,
                },
            )
            self.assertTrue(payload["hash_drift"])
            self.assertTrue(payload["product_rejected"])
            self.assertTrue(payload["material_rejected"])

    def test_governed_clip_range_contains_current_farthest_stable_geometry(self):
        """Catches the camera far plane clipping the observed 3622-unit product depth."""

        pose = self.module.CameraPose(
            location=(0.0, 0.0, 0.0),
            target=(0.0, 1.0, 0.0),
            pitch_degrees=0.0,
        )
        objects = [
            StableMesh("near", (-10.0, 1318.0, -10.0), (10.0, 1400.0, 10.0)),
            StableMesh("far", (-10.0, 3500.0, -10.0), (10.0, 3622.0, 10.0)),
        ]
        bpy = SimpleNamespace(
            context=SimpleNamespace(scene=SimpleNamespace(objects=objects))
        )

        depth_min, depth_max = self.module.stable_geometry_camera_depth_range(bpy, pose)

        self.assertEqual((depth_min, depth_max), (1318.0, 3622.0))
        self.assertLess(depth_max, self.module.STATIC_CAMERA_CLIP_END)

    def test_authoring_rejects_default_blender_far_clip(self):
        """Catches authored static cameras retaining Blender's 1000-unit far plane."""

        config = self.config
        target = self.module.TargetResolution(
            (-200.0, -180.0, 0.0),
            (220.0, 160.0, 900.0),
            {"complete_product": ("part",)},
            ("part",),
        )
        pose = self.module.camera_pose(target.bounds_min, target.bounds_max, config)
        bpy = self._minimal_authoring_bpy(config)
        bpy.context.scene.camera.data.clip_end = 1000.0

        with self.assertRaisesRegex(ValueError, "far clip"):
            self._call_author_with_configured_state(config, bpy, target, pose)

    def _contract_and_bytes(self, config):
        payload = self.module.contract_payload(config)
        contract = self.module.SceneContract.from_mapping(payload)
        return contract, json.dumps(payload, sort_keys=True).encode("utf-8")

    def _minimal_authoring_bpy(self, config, *, exposure=0.0):
        camera_data = SimpleNamespace(
            lens=config.focal_length_mm,
            sensor_width=36.0,
            clip_start=1.0,
            clip_end=10000.0,
            sensor_fit="HORIZONTAL",
            shift_x=0.5 - self.module.composition_for(config.scene_id).subject_placement.center_x,
            shift_y=self.module.composition_for(config.scene_id).subject_placement.center_y - 0.5,
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
            resolution_x=config.output_width,
            resolution_y=config.output_height,
            resolution_percentage=100,
            film_transparent=config.alpha,
            use_border=False,
            use_crop_to_border=False,
            filepath=str(self.module.managed_output_path(config)),
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
        _manifest_path, target_manifest = self._write_canonical_target_manifest()
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
            return self.module.author_scene(bpy, config, target_manifest)

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
        _manifest_path, manifest = self._write_canonical_target_manifest()

        with self.assertRaises(FileExistsError):
            self.module.author_scene(bpy, self.config, manifest)

        self.assertEqual(destination.read_bytes(), b"approved-scene")

    def test_authoring_rejects_wrong_hdri_hash_before_scene_mutation(self):
        """Catches a substituted environment image entering a governed scene."""

        config = self.config
        hdri = self.asset_root / "assets" / "hdri" / "studio_kontrast_04_4k.exr"
        hdri.parent.mkdir(parents=True)
        hdri.write_bytes(b"wrong-hdri")
        contract, contract_bytes = self._contract_and_bytes(config)
        bpy = self._minimal_authoring_bpy(config)
        _manifest_path, manifest = self._write_canonical_target_manifest()

        with (
            patch.object(
                self.module,
                "_load_authoring_contract",
                return_value=(contract, contract_bytes),
            ),
            patch.object(self.module, "_validate_open_template_authority"),
        ):
            with self.assertRaisesRegex(ValueError, "HDRI SHA-256 mismatch"):
                self.module.author_scene(bpy, config, manifest)

    def test_authoring_rejects_local_product_mesh_and_localized_material(self):
        """Catches private geometry or localized governed materials entering the shot."""

        config = self.config
        contract, contract_bytes = self._contract_and_bytes(config)
        expected_master = self.module._master_path(config).resolve()
        material_path = (self.asset_root / "masters" / "PIMM-MATERIAL-LIBRARY.blend").resolve()
        _manifest_path, manifest = self._write_canonical_target_manifest()

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
                        self.module.author_scene(bpy, config, manifest)

    def test_cli_exposes_inspection_and_manifest_gated_authoring_modes(self):
        """Catches Task 3 losing either the read-only inspection or manifest-gated author path."""

        shot_id = "pimm-30g--hero--desktop"
        inspected = self.module._arguments(["--shot-id", shot_id, "--inspect-targets"])
        self.assertTrue(inspected.inspect_targets)
        self.assertFalse(inspected.author_scene)

        manifest = (
            self.asset_root
            / "manifests"
            / "PIMM-static-shot-targets-v1.json"
        )
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

    def _write_canonical_target_manifest(self):
        path = (
            self.asset_root
            / "manifests"
            / "PIMM-static-shot-targets-v1.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._target_manifest()), encoding="utf-8")
        return path, self.module.load_target_manifest(path)

    def test_target_manifest_loader_and_cli_reject_noncanonical_paths(self):
        """Catches an otherwise valid manifest bypassing canonical asset authority."""

        outside = Path(self.temporary_directory.name) / "alternate-targets.json"
        outside.write_text(json.dumps(self._target_manifest()), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "canonical target manifest"):
            self.module.load_target_manifest(outside)

        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                self.module._arguments(
                    [
                        "--shot-id",
                        self.config.scene_id,
                        "--author-scene",
                        "--target-manifest",
                        str(outside),
                    ]
                )

    def test_author_scene_rejects_an_unvalidated_manifest_dictionary(self):
        """Catches direct Python callers bypassing all-shot schema and file authority checks."""

        bpy = self._minimal_authoring_bpy(self.config)

        with self.assertRaisesRegex(ValueError, "validated canonical target manifest"):
            self.module.author_scene(bpy, self.config, self._target_manifest())

    def _run_authoring_publication_scenario(self, save, fresh_validate):
        config = self.config
        target = self.module.TargetResolution(
            (-200.0, -180.0, 0.0),
            (220.0, 160.0, 900.0),
            {"complete_product": ("part",)},
            ("part",),
        )
        pose = self.module.camera_pose(target.bounds_min, target.bounds_max, config)
        bpy = self._minimal_authoring_bpy(config)
        bpy.ops.wm.save_as_mainfile = save
        contract, contract_bytes = self._contract_and_bytes(config)
        contract_path = self.module._contract_path(config)
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_bytes(contract_bytes)
        _manifest_path, manifest = self._write_canonical_target_manifest()
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
            patch.object(self.module, "_validate_authored_scene_state"),
            patch.object(self.module, "_run_fresh_validation", side_effect=fresh_validate),
        ):
            return self.module.author_scene(bpy, config, manifest)

    def test_authoring_destination_race_preserves_competitor_and_cleans_temporary_files(self):
        """Catches validation-success publication overwriting a destination created mid-run."""

        destination = self.module._scene_path(self.config)

        def save(*, filepath, **_kwargs):
            Path(filepath).write_bytes(b"candidate")

        def race(_temporary, _snapshot):
            destination.write_bytes(b"competitor")
            return []

        with self.assertRaises(FileExistsError):
            self._run_authoring_publication_scenario(save, race)

        self.assertEqual(destination.read_bytes(), b"competitor")
        self.assertEqual(list(destination.parent.glob(".*.tmp.blend")), [])
        self.assertEqual(list(destination.parent.glob(".*.contract.json")), [])

    def test_authoring_exceptions_leave_no_unvalidated_candidate_or_final_scene(self):
        """Catches save or fresh-Blender exceptions leaking unvalidated scene files."""

        destination = self.module._scene_path(self.config)

        def save_then_raise(*, filepath, **_kwargs):
            Path(filepath).write_bytes(b"candidate")
            raise RuntimeError("save failed after write")

        with self.subTest(stage="save"):
            with self.assertRaisesRegex(RuntimeError, "save failed"):
                self._run_authoring_publication_scenario(save_then_raise, lambda *_args: [])
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob(".*.tmp.blend")), [])
            self.assertEqual(list(destination.parent.glob(".*.contract.json")), [])

        def save(*, filepath, **_kwargs):
            Path(filepath).write_bytes(b"candidate")

        with self.subTest(stage="fresh_validation"):
            with self.assertRaisesRegex(TimeoutError, "fresh Blender timeout"):
                self._run_authoring_publication_scenario(
                    save,
                    lambda *_args: (_ for _ in ()).throw(
                        TimeoutError("fresh Blender timeout")
                    ),
                )
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob(".*.tmp.blend")), [])
            self.assertEqual(list(destination.parent.glob(".*.contract.json")), [])

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
        self.config = self.module.SHOT_CONFIGS["pimm-30g--hero--desktop"]

    def test_contract_payload_is_hash_pinned_and_static(self):
        """Catches a payload that loses its master, material, alpha, or still-image guard."""

        payload = self.module.contract_payload(self.config)

        self.assertEqual(payload["scene_id"], "pimm-30g--hero--desktop")
        self.assertEqual(payload["purpose"], "hero")
        self.assertEqual(
            payload["scene_path"],
            "scenes/stills/pimm-30g--hero--desktop.blend",
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
        self.assertEqual(payload["output_contract"], {"width": 2560, "height": 1440, "alpha": True})
        self.assertEqual(
            payload["static_render_setup"],
            {
                "camera": {
                    "aperture_fstop": 11.0,
                    "clip_end": 10000.0,
                    "clip_start": 1.0,
                    "focal_length_mm": 85.0,
                    "sensor_width_mm": 36.0,
                    "view": "hero-desktop",
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
                "physical_shadow": {
                    "catcher_name": "PIMM_SCENE_SHADOW_CATCHER",
                    "gate": "required",
                },
                "world": {
                    "hdri_path": "assets/hdri/studio_kontrast_04_4k.exr",
                    "hdri_sha256": "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06",
                    "rotation_degrees": 0.0,
                    "strength": 0.5,
                },
            },
        )

    def test_physical_shadow_gate_is_contract_bound_by_shot_class(self):
        for config in self.module.SHOT_CONFIGS.values():
            with self.subTest(shot_id=config.scene_id):
                payload = self.module.contract_payload(config)
                self.assertEqual(
                    payload["static_render_setup"]["physical_shadow"],
                    {
                        "catcher_name": "PIMM_SCENE_SHADOW_CATCHER",
                        "gate": "required",
                    },
                )

    def test_scene_contract_rejects_shadow_policy_drift(self):
        for config in self.module.SHOT_CONFIGS.values():
            if config.machine != "30G":
                continue
            payload = self.module.contract_payload(config)
            payload["static_render_setup"]["physical_shadow"]["gate"] = "not-applicable"

            errors = self.module.validate_scene_contract(
                self.module.SceneContract.from_mapping(payload)
            )

            self.assertIn(
                "static product physical shadow policy must match the governed shot class",
                errors,
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

        mutated = deepcopy(payload)
        mutated["static_render_setup"]["camera"]["clip_end"] = 1000.0
        contract = self.module.SceneContract.from_mapping(mutated)
        self.assertIn(
            "static product camera far clip must equal 10000 scene units",
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

    def test_scene_contract_rejects_static_camera_near_clip_drift(self):
        """Catches a known static contract weakening near-plane depth precision."""

        payload = self.module.contract_payload(self.config)
        payload["static_render_setup"]["camera"]["clip_start"] = 0.1
        contract = self.module.SceneContract.from_mapping(payload)

        self.assertIn(
            "static product camera near clip must equal 1 scene unit",
            self.module.validate_scene_contract(contract),
        )

    def test_scene_contract_rejects_missing_static_camera_clip_start(self):
        """Catches a known static contract omitting its governed near plane."""

        payload = self.module.contract_payload(self.config)
        payload["static_render_setup"]["camera"].pop("clip_start")
        contract = self.module.SceneContract.from_mapping(payload)

        self.assertIn(
            "static product camera setup has unexpected fields",
            self.module.validate_scene_contract(contract),
        )

    def test_scene_contract_rejects_missing_static_camera_clip_end(self):
        """Catches a known static contract falling back to Blender's default far plane."""

        payload = self.module.contract_payload(self.config)
        payload["static_render_setup"]["camera"].pop("clip_end")
        contract = self.module.SceneContract.from_mapping(payload)

        self.assertIn(
            "static product camera setup has unexpected fields",
            self.module.validate_scene_contract(contract),
        )

    def test_open_scene_validation_rejects_camera_far_clip_drift(self):
        """Catches a structurally valid scene whose actual camera clips the product away."""

        from scripts.blender.pimm_production import blender_scene_validator

        contract = self.module.SceneContract.from_mapping(
            self.module.contract_payload(self.config)
        )
        camera = SimpleNamespace(
            data=SimpleNamespace(clip_start=1.0, clip_end=1000.0)
        )
        errors = []

        blender_scene_validator._validate_static_camera_clip_range(
            camera, contract, errors
        )

        self.assertIn(
            "static product camera far clip does not match contract",
            errors,
        )

    def test_open_scene_validation_rejects_camera_near_clip_drift(self):
        """Catches a reopened static scene whose actual near plane drifted from contract."""

        from scripts.blender.pimm_production import blender_scene_validator

        contract = self.module.SceneContract.from_mapping(
            self.module.contract_payload(self.config)
        )
        camera = SimpleNamespace(
            data=SimpleNamespace(clip_start=0.1, clip_end=10000.0)
        )
        errors = []

        blender_scene_validator._validate_static_camera_clip_range(
            camera, contract, errors
        )

        self.assertIn(
            "static product camera near clip does not match contract",
            errors,
        )

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
