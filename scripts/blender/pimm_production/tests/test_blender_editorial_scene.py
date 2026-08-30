"""Governance coverage for preview-only one-shot editorial Blender scenes."""

from __future__ import annotations

import copy
import dataclasses
from contextlib import redirect_stdout
import hashlib
import json
from io import StringIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from scripts.blender.pimm_production.editorial_concept_contract import (
    EDITORIAL_CAMPAIGN_PATH,
    load_editorial_campaign,
)
from scripts.blender.pimm_production import blender_editorial_scene
from scripts.blender.pimm_production import editorial_sets
from scripts.blender.pimm_production.tests.test_editorial_sets import _FakeBpy


BLENDER_52 = Path(r"D:\Blender 5.2\blender.exe")
_REAL_SIGNATURE_MARKER = "PIMM_REAL_SIGNATURE_SMOKE_JSON="


def _run_real_blender_signature_smoke(directory: Path) -> subprocess.CompletedProcess[str]:
    """Exercise signature mutations against saved/reopened Blender datablocks."""

    script_path = directory / "real_signature_smoke.py"
    fixture_path = directory / "real_signature_fixture.blend"
    script_path.write_text(
        textwrap.dedent(
            r'''
            from __future__ import annotations

            import json
            from pathlib import Path
            import sys

            import bpy


            arguments = sys.argv[sys.argv.index("--") + 1 :]
            repository_root = Path(arguments[0]).resolve()
            fixture_path = Path(arguments[1]).resolve()
            sys.path.insert(0, str(repository_root))

            from scripts.blender.pimm_production import blender_editorial_scene as production


            SUPPORT_NAME = "SIG_SUPPORT"
            ALLOWED_NAMES = {SUPPORT_NAME}


            def add_nested_group(root_tree, prefix: str) -> None:
                inner = bpy.data.node_groups.new(f"{prefix}_INNER", "ShaderNodeTree")
                value = inner.nodes.new("ShaderNodeValue")
                value.name = f"{prefix}_VALUE"
                value.outputs[0].default_value = 0.25
                outer = bpy.data.node_groups.new(f"{prefix}_OUTER", "ShaderNodeTree")
                nested = outer.nodes.new("ShaderNodeGroup")
                nested.name = f"{prefix}_NESTED"
                nested.node_tree = inner
                root = root_tree.nodes.new("ShaderNodeGroup")
                root.name = f"{prefix}_ROOT"
                root.node_tree = outer


            def signatures() -> tuple[str, str]:
                bpy.context.view_layer.update()
                return (
                    production._scene_geometry_signature(bpy, ALLOWED_NAMES),
                    production._scene_light_signature(bpy),
                )


            def evaluated_mesh_record() -> dict[str, object]:
                depsgraph = bpy.context.evaluated_depsgraph_get()
                evaluated = bpy.data.objects[SUPPORT_NAME].evaluated_get(depsgraph)
                mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
                try:
                    return production._mesh_signature_record(mesh)
                finally:
                    evaluated.to_mesh_clear()


            def assert_rejected(before: tuple[str, str], after: tuple[str, str]) -> None:
                contract = {
                    "set": {
                        "scene_geometry_signature": before[0],
                        "scene_light_signature": before[1],
                    }
                }
                snapshot = {
                    "set": {
                        "scene_geometry_signature": after[0],
                        "scene_light_signature": after[1],
                    },
                    "publication": {
                        "complete": True,
                        "transaction_id_matches": True,
                        "scene_sha256_matches": True,
                        "contract_sha256_matches": True,
                    },
                }
                errors = production._validate_editorial_runtime_snapshot(snapshot, contract)
                assert "editorial set signatures do not match the contract" in errors, errors


            def reopen() -> None:
                bpy.ops.wm.open_mainfile(filepath=str(fixture_path), load_ui=False)


            def run_geometry_case(name: str, mutate) -> None:
                reopen()
                before = signatures()
                evaluated_before = evaluated_mesh_record()
                mutate()
                after = signatures()
                evaluated_after = evaluated_mesh_record()
                assert before[0] != after[0], f"geometry signature unchanged for {name}"
                assert evaluated_before != evaluated_after, f"evaluated mesh unchanged for {name}"
                assert_rejected(before, after)
                results[name] = True


            def run_node_case(name: str, node_group_name: str, channel: str) -> None:
                reopen()
                before = signatures()
                inner = bpy.data.node_groups[node_group_name]
                inner.nodes[0].outputs[0].default_value = 0.75
                after = signatures()
                index = 0 if channel == "geometry" else 1
                assert before[index] != after[index], f"{channel} signature unchanged for {name}"
                assert_rejected(before, after)
                results[name] = True


            bpy.ops.wm.read_factory_settings(use_empty=True)
            scene = bpy.context.scene
            mesh = bpy.data.meshes.new("SIG_MESH")
            mesh.from_pydata(
                [(-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (-1.0, 1.0, 0.0)],
                [],
                [(0, 1, 2, 3)],
            )
            mesh.update()
            support = bpy.data.objects.new(SUPPORT_NAME, mesh)
            support["pimm_scene_support_ownership"] = "scene-support"
            support["pimm_scene_support_role"] = "signature-fixture"
            scene.collection.objects.link(support)
            solidify = support.modifiers.new("SIG_SOLIDIFY", "SOLIDIFY")
            solidify.thickness = 0.25

            material = bpy.data.materials.new("SIG_MATERIAL")
            material.use_nodes = True
            add_nested_group(material.node_tree, "SIG_MATERIAL")
            packed_image = bpy.data.images.new("SIG_PACKED_IMAGE", width=1, height=1)
            packed_image.pack(data=b"AAAA", data_len=4)
            image_node = material.node_tree.nodes.new("ShaderNodeTexImage")
            image_node.name = "SIG_PACKED_TEXTURE"
            image_node.image = packed_image
            mesh.materials.append(material)

            light_data = bpy.data.lights.new("SIG_LIGHT_DATA", "POINT")
            light_data.use_nodes = True
            add_nested_group(light_data.node_tree, "SIG_LIGHT")
            light = bpy.data.objects.new("SIG_LIGHT", light_data)
            light["pimm_editorial_light_role"] = "signature-fixture"
            scene.collection.objects.link(light)

            world = bpy.data.worlds.new("SIG_WORLD")
            world.use_nodes = True
            world["pimm_editorial_light_role"] = "signature-fixture"
            add_nested_group(world.node_tree, "SIG_WORLD")
            scene.world = world

            bpy.ops.wm.save_as_mainfile(
                filepath=str(fixture_path), check_existing=False, relative_remap=False
            )

            results: dict[str, bool] = {}

            def mutate_vertex() -> None:
                bpy.data.meshes["SIG_MESH"].vertices[0].co.x -= 0.5


            run_geometry_case("evaluated_vertex", mutate_vertex)

            def mutate_topology() -> None:
                mesh = bpy.data.meshes["SIG_MESH"]
                mesh.clear_geometry()
                mesh.from_pydata(
                    [
                        (-1.0, -1.0, 0.0),
                        (1.0, -1.0, 0.0),
                        (1.0, 1.0, 0.0),
                        (-1.0, 1.0, 0.0),
                        (0.0, 0.0, 0.5),
                    ],
                    [],
                    [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)],
                )
                mesh.update()


            run_geometry_case("evaluated_topology", mutate_topology)

            def mutate_modifier_result() -> None:
                bpy.data.objects[SUPPORT_NAME].modifiers["SIG_SOLIDIFY"].thickness = 0.75


            run_geometry_case("modifier_result", mutate_modifier_result)
            run_node_case("material_nested_group", "SIG_MATERIAL_INNER", "geometry")
            run_node_case("light_nested_group", "SIG_LIGHT_INNER", "light")
            run_node_case("world_nested_group", "SIG_WORLD_INNER", "light")

            reopen()
            packed_before = signatures()
            image = bpy.data.images["SIG_PACKED_IMAGE"]
            assert bytes(image.packed_file.data) == b"AAAA"
            image.pack(data=b"BBBB", data_len=4)
            assert image.packed_file.size == 4
            assert bytes(image.packed_file.data) == b"BBBB"
            packed_after = signatures()
            assert packed_before[0] != packed_after[0], "same-size packed bytes were ignored"
            assert_rejected(packed_before, packed_after)
            results["packed_image_same_size_bytes"] = True

            print("PIMM_REAL_SIGNATURE_SMOKE_JSON=" + json.dumps(results, sort_keys=True), flush=True)
            '''
        ),
        encoding="utf-8",
    )
    repository_root = Path(__file__).resolve().parents[4]
    return subprocess.run(
        [
            str(BLENDER_52),
            "--factory-startup",
            "-b",
            "--python-exit-code",
            "1",
            "-P",
            str(script_path),
            "--",
            str(repository_root),
            str(fixture_path),
        ],
        cwd=repository_root,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _snapshot(contract: dict[str, object]) -> dict[str, object]:
    machine_bounds = {"minimum": [-100.0, -80.0, 0.0], "maximum": [120.0, 90.0, 300.0]}
    contact = {
        "schema_version": 1,
        "machine": contract["machine"],
        "selection_basis": "live-linked-master-four-nylon-feet",
        "contact_z": 0.0,
        "tolerance": 0.0002,
        "spread": 0.0,
        "stable_ids": [f"{contract['machine']}-foot-{index}" for index in range(4)],
        "pad_bottoms": [0.0, 0.0, 0.0, 0.0],
        "feet": [
            {
                "stable_id": f"{contract['machine']}-foot-{index}",
                "bottom_z": 0.0,
                "center_x": float(index * 10),
                "center_y": float(index * 5),
                "delta_to_plane": 0.0,
            }
            for index in range(4)
        ],
        "outlier_stable_ids": [],
    }
    return {
        "scene_id": contract["scene_id"],
        "scene_path_matches": True,
        "embedded_contract_matches": True,
        "embedded_contract_sha256_matches": True,
        "final_authorized": False,
        "master_library_count": 1,
        "material_library_present": True,
        "unexpected_library_paths": [],
        "library_overrides": [],
        "local_product_copies": [],
        "linked_product_count": 10,
        "stable_id_count": 10,
        "stable_id_sha256": "A" * 64,
        "machine_bounds": machine_bounds,
        "camera": {
            "active": True,
            "scene_local": True,
            "focal_length_mm": contract["camera"]["focal_length_mm"],
            "aperture_fstop": contract["camera"]["aperture_fstop"],
            "sensor_width_mm": contract["camera"]["sensor_width_mm"],
            "verticals_upright": True,
            "eye_level_midline": True,
            "complete_machine_framed": True,
            "support_rectangle_framed": True,
            "machine_frame_width_ratio": 0.48,
            "machine_frame_height_ratio": 0.72,
            "machine_frame_area_ratio": 0.34,
            "safe_margin_minimum": 0.04,
        },
        "render": {
            "engine": "CYCLES",
            "width": contract["render"]["width"],
            "height": contract["render"]["height"],
            "resolution_percentage": 100,
            "preview_samples": 32,
            "denoise": True,
            "view_transform": "AgX",
            "look": "AgX - Medium High Contrast",
        },
        "contact": contact,
        "contact_plane": {
            "count": 1,
            "z": 0.0,
            "covers_all_feet": True,
        },
        "support_bounds": [
            {
                "name": "PIMM_SCENE_SUPPORT_FIXTURE",
                "role": "fixture",
                "minimum": [200.0, -20.0, 0.0],
                "maximum": [250.0, 20.0, 40.0],
                "intersects_machine": False,
                "hides_foot_stable_ids": [],
            }
        ],
        "set": copy.deepcopy(contract["set"]),
        "external_provenance": copy.deepcopy(contract["external_assets"]),
        "publication": {
            "complete": True,
            "transaction_id_matches": True,
            "scene_sha256_matches": True,
            "contract_sha256_matches": True,
        },
    }


class BlenderEditorialSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        campaign = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH)
        cls.campaign = campaign
        cls.shot = campaign.by_shot_id["pimm-30g--concept-architectural-daylight"]
        cls.prepared_contract = blender_editorial_scene.prepare_editorial_contract(cls.shot)
        cls.contract = copy.deepcopy(cls.prepared_contract)
        cls.contract["set"]["scene_geometry_signature"] = "A" * 64
        cls.contract["set"]["scene_light_signature"] = "B" * 64

    def errors(self, snapshot: dict[str, object], contract: dict[str, object] | None = None) -> list[str]:
        return blender_editorial_scene._validate_editorial_runtime_snapshot(
            snapshot, self.contract if contract is None else contract
        )

    def test_prepares_exact_preview_only_contract_from_current_protected_inputs(self) -> None:
        """Catches a contract that omits immutable master, material, contact, or preview authority."""

        contract = self.prepared_contract
        self.assertEqual(contract["schema"], "maliev.pimm-editorial-scene/v1")
        self.assertEqual(contract["scene_id"], self.shot.shot_id)
        self.assertEqual(contract["master"]["path"], "masters/PIMM-30G-MASTER.blend")
        self.assertEqual(contract["material_library"]["path"], "masters/PIMM-MATERIAL-LIBRARY.blend")
        self.assertEqual(contract["contact"]["gate"], "four-feet-common-plane")
        self.assertEqual(len(contract["master"]["sha256"]), 64)
        self.assertEqual(len(contract["material_library"]["sha256"]), 64)
        self.assertFalse(contract["final_authorized"])

    def test_corrective_composition_contract_keeps_context_from_shrinking_or_engulfing_the_machine(self) -> None:
        """Catches centered full-scale externals or wide props controlling hero framing."""

        architectural = blender_editorial_scene.prepare_editorial_contract(
            self.campaign.by_shot_id["pimm-30g--concept-architectural-daylight"]
        )
        workshop = blender_editorial_scene.prepare_editorial_contract(
            self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
        )
        process = blender_editorial_scene.prepare_editorial_contract(
            self.campaign.by_shot_id["pimm-30g--concept-process-still-life"]
        )

        self.assertEqual(architectural["set"].get("composition_policy"), {
            "procedural_scale": 1.0,
            "procedural_minimum_y_gap_mm": 0.0,
            "gobo_maximum_x_offset_mm": -300.0,
            "camera_safety_multiplier": 1.08,
            "external_instances": [],
        })
        self.assertEqual(workshop["set"].get("composition_policy"), {
            "procedural_scale": 0.35,
            "procedural_minimum_y_gap_mm": 220.0,
            "gobo_maximum_x_offset_mm": None,
            "camera_safety_multiplier": 1.05,
            "external_instances": [{
                "asset_id": "tool_cart",
                "framing_eligible": False,
                "center_x_offset_mm": 1700.0,
                "y_anchor": "minimum-behind",
                "y_gap_mm": 1800.0,
                "grounded": True,
            }],
        })
        self.assertEqual(process["set"].get("composition_policy"), {
            "procedural_scale": 0.36,
            "procedural_minimum_y_gap_mm": 220.0,
            "gobo_maximum_x_offset_mm": None,
            "camera_safety_multiplier": 1.08,
            "external_instances": [{
                "asset_id": "metal_toolbox",
                "framing_eligible": False,
                "center_x_offset_mm": -700.0,
                "y_anchor": "minimum-behind",
                "y_gap_mm": 800.0,
                "grounded": True,
            }],
        })
        for contract, role in (
            (workshop, "external-tool-cart"),
            (process, "external-metal-toolbox"),
        ):
            record = next(
                item for item in contract["set"]["support_allowlist"]
                if item["role"] == role
            )
            self.assertFalse(record["framing_eligible"])
        process_procedural = [
            record for record in process["set"]["support_allowlist"]
            if record["source"] == "task-3-procedural"
        ]
        self.assertTrue(process_procedural)
        self.assertFalse(any(record["framing_eligible"] for record in process_procedural))

    def test_contact_receiver_is_one_upward_facing_quad_instead_of_a_collapsed_box(self) -> None:
        """Catches coincident cube faces rendering the nominal floor as a black field."""

        class Mesh:
            def __init__(self) -> None:
                self.vertices = [SimpleNamespace(co=SimpleNamespace(z=-1.0))]
                self.cleared = False
                self.payload = None
                self.updated = False

            def clear_geometry(self) -> None:
                self.cleared = True

            def from_pydata(self, vertices, edges, faces) -> None:
                self.payload = (vertices, edges, faces)

            def update(self) -> None:
                self.updated = True

        class Support(dict):
            def __init__(self) -> None:
                super().__init__()
                self.data = Mesh()
                self.scale = SimpleNamespace(x=2.0, y=3.0, z=4.0)
                self.location = SimpleNamespace(x=0.0, y=0.0, z=0.0)

        support = Support()
        with patch.object(
            blender_editorial_scene,
            "_object_bounds",
            return_value=((-10.0, -20.0, -5.0), (10.0, 20.0, 5.0)),
        ):
            blender_editorial_scene._flatten_contact_plane(
                support,
                7.5,
                ((-100.0, -200.0, 7.5), (300.0, 400.0, 900.0)),
            )
        self.assertTrue(support.data.cleared)
        self.assertEqual(support.data.payload, (
            [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0)],
            [],
            [(0, 1, 2, 3)],
        ))
        self.assertTrue(support.data.updated)
        self.assertEqual((support.scale.x, support.scale.y, support.scale.z), (20_400.0, 20_600.0, 1.0))
        self.assertEqual((support.location.x, support.location.y, support.location.z), (100.0, 100.0, 7.5))

    def test_corrective_coverage_policy_enforces_workshop_and_portrait_product_dominance(self) -> None:
        """Catches a technically framed workshop or still life whose machine is too small."""

        workshop = blender_editorial_scene.prepare_editorial_contract(
            self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
        )["set"]["coverage_policy"]
        process = blender_editorial_scene.prepare_editorial_contract(
            self.campaign.by_shot_id["pimm-30g--concept-process-still-life"]
        )["set"]["coverage_policy"]

        self.assertEqual(workshop, {
            "minimum_machine_width_ratio": 0.20,
            "minimum_machine_height_ratio": 0.75,
            "minimum_machine_area_ratio": 0.20,
            "minimum_safe_margin": 0.02,
        })
        self.assertEqual(process, {
            "minimum_machine_width_ratio": 0.20,
            "minimum_machine_height_ratio": 0.62,
            "minimum_machine_area_ratio": 0.16,
            "minimum_safe_margin": 0.02,
        })

    def test_rejects_a_local_product_copy(self) -> None:
        """Catches scene-local meshes carrying product identity outside the linked master."""

        snapshot = _snapshot(self.contract)
        snapshot["local_product_copies"] = ["30G-private-copy"]
        self.assertIn("local product", "\n".join(self.errors(snapshot)))

    def test_rejects_changed_linked_master_and_material_library(self) -> None:
        """Catches protected input bytes drifting after the contract was prepared."""

        for key, phrase in (("master", "master SHA-256"), ("material_library", "material-library SHA-256")):
            contract = copy.deepcopy(self.contract)
            contract[key]["sha256"] = "0" * 64
            with self.subTest(key=key):
                self.assertIn(phrase, "\n".join(self.errors(_snapshot(contract), contract)))

    def test_rejects_wrong_focal_length(self) -> None:
        """Catches a camera that no longer uses the Task 1 focal length."""

        snapshot = _snapshot(self.contract)
        snapshot["camera"]["focal_length_mm"] = 50.0
        self.assertIn("focal length", "\n".join(self.errors(snapshot)))

    def test_rejects_non_level_architectural_verticals(self) -> None:
        """Catches camera roll or pitch that makes architectural verticals converge."""

        snapshot = _snapshot(self.contract)
        snapshot["camera"]["verticals_upright"] = False
        self.assertIn("architectural verticals", "\n".join(self.errors(snapshot)))

    def test_rejects_missing_per_foot_common_plane_evidence(self) -> None:
        """Catches a declared contact pass without four independently measured feet."""

        snapshot = _snapshot(self.contract)
        snapshot["contact"]["feet"] = snapshot["contact"]["feet"][:3]
        snapshot["contact"]["stable_ids"] = snapshot["contact"]["stable_ids"][:3]
        snapshot["contact"]["pad_bottoms"] = snapshot["contact"]["pad_bottoms"][:3]
        self.assertIn("exactly four measured feet", "\n".join(self.errors(snapshot)))

    def test_rejects_prop_bounds_intersecting_machine_or_hiding_feet(self) -> None:
        """Catches collision or foreground occlusion hidden behind a set-level pass flag."""

        for field, value, phrase in (
            ("intersects_machine", True, "intersects linked machine bounds"),
            ("hides_foot_stable_ids", ["30G-foot-0"], "hides linked machine feet"),
        ):
            snapshot = _snapshot(self.contract)
            snapshot["support_bounds"][0][field] = value
            with self.subTest(field=field):
                self.assertIn(phrase, "\n".join(self.errors(snapshot)))

    def test_rejects_missing_set_signatures(self) -> None:
        """Catches a generic set replacing the contracted distinct geometry/light design."""

        snapshot = _snapshot(self.contract)
        snapshot["set"]["geometry_signature"] = ""
        self.assertIn("set signature", "\n".join(self.errors(snapshot)))

    def test_rejects_missing_external_provenance(self) -> None:
        """Catches a linked contextual asset without the exact governed CC0 record."""

        shot = self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
        contract = blender_editorial_scene.prepare_editorial_contract(shot)
        snapshot = _snapshot(contract)
        snapshot["external_provenance"] = []
        self.assertIn("external provenance", "\n".join(self.errors(snapshot, contract)))

    def test_rejects_any_final_authorization(self) -> None:
        """Catches preview authoring silently widening into final-render authority."""

        contract = copy.deepcopy(self.contract)
        contract["final_authorized"] = True
        snapshot = _snapshot(contract)
        snapshot["final_authorized"] = True
        self.assertIn("final_authorized must remain false", "\n".join(self.errors(snapshot, contract)))

    def test_rejects_mutated_shot_policy_under_an_approved_id(self) -> None:
        """Catches authoring that trusts an approved ID while ignoring changed camera policy."""

        mutated = dataclasses.replace(self.shot, focal_length_mm=50.0)
        with self.assertRaisesRegex(ValueError, "exact approved editorial shot"):
            blender_editorial_scene.prepare_editorial_contract(mutated)

    def test_ordinary_python_cli_keeps_arguments_without_blenders_separator(self) -> None:
        """Catches the prepare command silently discarding normal module arguments."""

        argv = [
            "blender_editorial_scene.py",
            "--prepare-contract",
            "--shot-id",
            self.shot.shot_id,
        ]
        output = StringIO()
        with patch.object(blender_editorial_scene.sys, "argv", argv), redirect_stdout(output):
            self.assertEqual(blender_editorial_scene.main(), 0)
        self.assertIn("contract_prepared_not_published", output.getvalue())

    def test_scene_support_bounds_do_not_require_a_product_stable_id(self) -> None:
        """Catches reuse of the product-only bounds gate for governed scene supports."""

        class Identity:
            def __matmul__(self, point):
                return point

        support = SimpleNamespace(
            type="MESH",
            bound_box=tuple(
                (x, y, z)
                for x in (-2.0, 3.0)
                for y in (-4.0, 5.0)
                for z in (-6.0, 7.0)
            ),
            matrix_world=Identity(),
        )
        self.assertEqual(
            blender_editorial_scene._object_bounds(support),
            ((-2.0, -4.0, -6.0), (3.0, 5.0, 7.0)),
        )

    def test_rejects_tiny_product_coverage_even_when_every_bound_is_inside_frame(self) -> None:
        """Catches a huge contact plane making the machine technically framed but unusably tiny."""

        snapshot = _snapshot(self.contract)
        snapshot["camera"].update({
            "machine_frame_width_ratio": 0.019,
            "machine_frame_height_ratio": 0.031,
            "machine_frame_area_ratio": 0.0006,
            "safe_margin_minimum": 0.04,
        })
        self.assertIn("visually dominant", "\n".join(self.errors(snapshot)))

    def test_real_projection_and_camera_solver_exclude_a_twenty_metre_contact_plane(self) -> None:
        """Catches the contact receiver re-entering the real framing/camera solve path."""

        machine = ((-207.0, -172.5, 0.0), (207.0, 172.5, 892.5))
        prop = ((-310.0, 300.0, 0.0), (310.0, 700.0, 700.0))
        plane = ((-10_207.0, -10_172.5, 0.0), (10_207.0, 10_172.5, 0.0))

        class Support(dict):
            def __init__(self, name: str, eligible: bool) -> None:
                super().__init__(pimm_editorial_framing_eligible=eligible)
                self.name = name

        eligible = Support("PROP", True)
        contact = Support("CONTACT", False)
        fake_bpy = SimpleNamespace()
        with patch.object(
            blender_editorial_scene,
            "_support_bounds",
            return_value=[(eligible, prop), (contact, plane)],
        ):
            support_bounds = blender_editorial_scene._framing_support_bounds(fake_bpy)
        self.assertEqual(support_bounds, [prop])

        layout = blender_editorial_scene._solve_camera_layout(self.shot, machine, support_bounds)
        polluted = blender_editorial_scene._solve_camera_layout(self.shot, machine, [prop, plane])
        self.assertEqual(layout["support_rectangle"], prop)
        self.assertLess(layout["near_distance"], polluted["near_distance"] / 10.0)

        class Projected:
            def __init__(self, x: float, y: float, z: float) -> None:
                self.x, self.y, self.z = x, y, z

            def __getitem__(self, axis: int) -> float:
                return (self.x, self.y, self.z)[axis]

        camera = SimpleNamespace(
            distance=layout["near_distance"],
            target_z=layout["target"][2],
        )
        tan_h = blender_editorial_scene.SENSOR_WIDTH_MM / (2.0 * self.shot.focal_length_mm)
        tan_v = tan_h / (self.shot.width / self.shot.height)

        def project(_scene, current_camera, point):
            return Projected(
                0.5 + float(point[0]) / (2.0 * current_camera.distance * tan_h),
                0.5 + (float(point[2]) - current_camera.target_z) / (2.0 * current_camera.distance * tan_v),
                current_camera.distance + float(point[1]),
            )

        modules = {
            "bpy_extras": SimpleNamespace(),
            "bpy_extras.object_utils": SimpleNamespace(world_to_camera_view=project),
            "mathutils": SimpleNamespace(Vector=lambda value: value),
        }
        projection_bpy = SimpleNamespace(context=SimpleNamespace(scene=object()))
        with patch.dict(sys.modules, modules):
            measured = blender_editorial_scene._project_bounds(projection_bpy, camera, machine)
            polluted_camera = SimpleNamespace(
                distance=polluted["near_distance"], target_z=polluted["target"][2]
            )
            polluted_measured = blender_editorial_scene._project_bounds(
                projection_bpy, polluted_camera, machine
            )
            foot_projection = blender_editorial_scene._project_bounds(
                projection_bpy, camera, ((0.0, 0.0, 0.0), (10.0, 20.0, 10.0))
            )
            partial_projection = blender_editorial_scene._project_bounds(
                projection_bpy, camera, ((2.0, 15.0, 2.0), (8.0, 25.0, 8.0))
            )
            separate_projection = blender_editorial_scene._project_bounds(
                projection_bpy, camera, ((30.0, 15.0, 2.0), (40.0, 25.0, 8.0))
            )
            behind_projection = blender_editorial_scene._project_bounds(
                projection_bpy, camera, ((2.0, 30.0, 2.0), (8.0, 40.0, 8.0))
            )
        policy = self.contract["set"]["coverage_policy"]
        self.assertGreaterEqual(measured["width_ratio"], policy["minimum_machine_width_ratio"])
        self.assertGreaterEqual(measured["height_ratio"], policy["minimum_machine_height_ratio"])
        self.assertLess(polluted_measured["width_ratio"], policy["minimum_machine_width_ratio"])
        self.assertTrue(blender_editorial_scene._projected_occlusion(partial_projection, foot_projection))
        self.assertFalse(blender_editorial_scene._projected_occlusion(separate_projection, foot_projection))
        self.assertFalse(blender_editorial_scene._projected_occlusion(behind_projection, foot_projection))

    def test_scene_signatures_change_when_a_real_support_or_light_datablock_changes(self) -> None:
        """Catches validation trusting embedded signature text instead of reopened datablocks."""

        fake_bpy = _FakeBpy()
        evidence = editorial_sets.build_editorial_set(fake_bpy, self.shot)
        allowed = {item.name for item in evidence.geometry}
        geometry_before = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        support = next(obj for obj in fake_bpy.context.scene.objects if obj.name in allowed)
        support.location = (float(support.location[0]) + 25.0, *support.location[1:])
        geometry_after = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        self.assertNotEqual(geometry_before, geometry_after)

        light_before = blender_editorial_scene._scene_light_signature(fake_bpy)
        governed = copy.deepcopy(self.contract)
        governed["set"]["scene_geometry_signature"] = geometry_before
        governed["set"]["scene_light_signature"] = light_before
        geometry_snapshot = _snapshot(governed)
        geometry_snapshot["set"]["scene_geometry_signature"] = geometry_after
        self.assertIn("signatures do not match", "\n".join(self.errors(geometry_snapshot, governed)))

        light = next(obj for obj in fake_bpy.context.scene.objects if obj.type == "LIGHT")
        light.data.energy += 1.0
        light_after = blender_editorial_scene._scene_light_signature(fake_bpy)
        self.assertNotEqual(light_before, light_after)
        light_snapshot = _snapshot(governed)
        light_snapshot["set"]["scene_light_signature"] = light_after
        self.assertIn("signatures do not match", "\n".join(self.errors(light_snapshot, governed)))

    def test_blender_5_2_reopens_real_datablocks_and_rejects_signature_mutations(self) -> None:
        """Catches fake-only coverage masking drift in Blender's actual RNA and depsgraph."""

        self.assertTrue(BLENDER_52.is_file(), f"required Blender 5.2 executable is missing: {BLENDER_52}")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            completed = _run_real_blender_signature_smoke(root)
            self.assertEqual(
                completed.returncode,
                0,
                f"Blender mutation smoke failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
            )
            emitted = [
                line.removeprefix(_REAL_SIGNATURE_MARKER)
                for line in completed.stdout.splitlines()
                if line.startswith(_REAL_SIGNATURE_MARKER)
            ]
            self.assertEqual(len(emitted), 1, completed.stdout)
            self.assertEqual(
                json.loads(emitted[0]),
                {
                    "evaluated_topology": True,
                    "evaluated_vertex": True,
                    "light_nested_group": True,
                    "material_nested_group": True,
                    "modifier_result": True,
                    "packed_image_same_size_bytes": True,
                    "world_nested_group": True,
                },
            )
            self.assertTrue((root / "real_signature_fixture.blend").is_file())

    def test_scene_signatures_cover_geometry_modifiers_material_images_and_world_nodes(self) -> None:
        """Catches datablock edits hidden behind unchanged transforms and light energy."""

        fake_bpy = _FakeBpy()
        evidence = editorial_sets.build_editorial_set(fake_bpy, self.shot)
        allowed = {item.name for item in evidence.geometry}
        support = next(obj for obj in fake_bpy.context.scene.objects if obj.name in allowed)

        def assert_geometry_rejected(before_signature: str, after_signature: str) -> None:
            governed = copy.deepcopy(self.contract)
            governed["set"]["scene_geometry_signature"] = before_signature
            snapshot = _snapshot(governed)
            snapshot["set"]["scene_geometry_signature"] = after_signature
            self.assertIn("signatures do not match", "\n".join(self.errors(snapshot, governed)))

        def assert_light_rejected(before_signature: str, after_signature: str) -> None:
            governed = copy.deepcopy(self.contract)
            governed["set"]["scene_light_signature"] = before_signature
            snapshot = _snapshot(governed)
            snapshot["set"]["scene_light_signature"] = after_signature
            self.assertIn("signatures do not match", "\n".join(self.errors(snapshot, governed)))

        before = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        support.data.vertices[0] = tuple(value + 1.0 for value in support.data.vertices[0])
        after_vertex = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        self.assertNotEqual(before, after_vertex)
        assert_geometry_rejected(before, after_vertex)

        before_modifier = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        support.modifiers = [SimpleNamespace(name="BEND", type="SIMPLE_DEFORM", strength=0.25)]
        after_modifier_add = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        self.assertNotEqual(before_modifier, after_modifier_add)
        assert_geometry_rejected(before_modifier, after_modifier_add)
        support.modifiers[0].strength = 0.5
        after_modifier = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        self.assertNotEqual(after_modifier_add, after_modifier)
        assert_geometry_rejected(after_modifier_add, after_modifier)

        material = support.data.materials[0]
        before_topology = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        material_node = material.node_tree.nodes.new("ShaderNodeTexImage")
        after_topology = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        self.assertNotEqual(before_topology, after_topology)
        assert_geometry_rejected(before_topology, after_topology)
        material_node.inputs["Strength"].default_value = 0.25
        before_node = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        material_node.inputs["Strength"].default_value = 0.75
        after_node = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        self.assertNotEqual(before_node, after_node)
        assert_geometry_rejected(before_node, after_node)

        with TemporaryDirectory() as directory:
            image_path = Path(directory) / "identity.hdr"
            image_path.write_bytes(b"image-a")
            material_node.image = SimpleNamespace(name="IDENTITY", filepath=str(image_path))
            before_image = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
            image_path.write_bytes(b"image-b")
            after_image = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
            self.assertNotEqual(before_image, after_image)
            assert_geometry_rejected(before_image, after_image)

        fake_bpy.context.scene.world = fake_bpy.data.worlds.new("TEST_WORLD")
        before_world_topology = blender_editorial_scene._scene_light_signature(fake_bpy)
        world_node = fake_bpy.context.scene.world.node_tree.nodes.new("ShaderNodeValue")
        after_world_topology = blender_editorial_scene._scene_light_signature(fake_bpy)
        self.assertNotEqual(before_world_topology, after_world_topology)
        assert_light_rejected(before_world_topology, after_world_topology)
        world_node.inputs["Strength"].default_value = 0.25
        before_world = blender_editorial_scene._scene_light_signature(fake_bpy)
        world_node.inputs["Strength"].default_value = 0.75
        after_world = blender_editorial_scene._scene_light_signature(fake_bpy)
        self.assertNotEqual(before_world, after_world)
        assert_light_rejected(before_world, after_world)

    def test_scene_geometry_signature_uses_evaluated_mesh_coordinates_and_topology(self) -> None:
        """Catches signature collection falling back to the unmodified source mesh."""

        fake_bpy = _FakeBpy()
        evidence = editorial_sets.build_editorial_set(fake_bpy, self.shot)
        allowed = {item.name for item in evidence.geometry}
        support = next(obj for obj in fake_bpy.context.scene.objects if obj.name in allowed)
        evaluated_mesh = SimpleNamespace(
            vertices=[SimpleNamespace(co=(0.0, 0.0, 0.0)), SimpleNamespace(co=(1.0, 0.0, 0.0))],
            edges=[SimpleNamespace(vertices=(0, 1))],
            polygons=[SimpleNamespace(vertices=(0, 1), material_index=0, use_smooth=False)],
        )
        calls: list[object] = []

        class EvaluatedObject:
            def to_mesh(self, *, preserve_all_data_layers: bool, depsgraph: object) -> object:
                calls.append((preserve_all_data_layers, depsgraph))
                return evaluated_mesh

            def to_mesh_clear(self) -> None:
                calls.append("clear")

        depsgraph = object()
        support.evaluated_get = lambda actual: EvaluatedObject() if actual is depsgraph else None
        fake_bpy.context.evaluated_depsgraph_get = lambda: depsgraph
        before = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        evaluated_mesh.vertices[1].co = (2.0, 0.0, 0.0)
        evaluated_mesh.edges.append(SimpleNamespace(vertices=(1, 0)))
        evaluated_mesh.polygons.append(
            SimpleNamespace(vertices=(1, 0), material_index=0, use_smooth=True)
        )
        after = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)

        self.assertNotEqual(before, after)
        self.assertEqual(sum(item == "clear" for item in calls), 2)
        self.assertEqual(sum(isinstance(item, tuple) and item[1] is depsgraph for item in calls), 2)

    def test_scene_signatures_recurse_material_and_light_node_groups_with_cycle_protection(self) -> None:
        """Catches nested shader/light node groups being omitted from reopened signatures."""

        def socket(value: float) -> SimpleNamespace:
            return SimpleNamespace(
                default_value=value, enabled=True, hide_value=False, identifier="Value"
            )

        def nested_tree(value: float) -> tuple[SimpleNamespace, SimpleNamespace]:
            nested_socket = socket(value)
            inner = SimpleNamespace(
                name="INNER_VALUE", bl_idname="ShaderNodeValue", label="", mute=False,
                inputs={"Value": nested_socket}, outputs={}, image=None, node_tree=None,
            )
            tree = SimpleNamespace(name="NESTED_GROUP", nodes=[inner], links=[])
            cycle = SimpleNamespace(
                name="CYCLE", bl_idname="ShaderNodeGroup", label="", mute=False,
                inputs={}, outputs={}, image=None, node_tree=tree,
            )
            tree.nodes.append(cycle)
            return tree, nested_socket

        fake_bpy = _FakeBpy()
        evidence = editorial_sets.build_editorial_set(fake_bpy, self.shot)
        allowed = {item.name for item in evidence.geometry}
        support = next(obj for obj in fake_bpy.context.scene.objects if obj.name in allowed)
        material_group = support.data.materials[0].node_tree.nodes.new("ShaderNodeGroup")
        material_group.node_tree, material_socket = nested_tree(0.25)
        material_before = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        material_socket.default_value = 0.75
        material_after = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        self.assertNotEqual(material_before, material_after)

        light = next(obj for obj in fake_bpy.context.scene.objects if obj.type == "LIGHT")
        light_group_tree, light_socket = nested_tree(1.0)
        light.data.node_tree = SimpleNamespace(
            name="LIGHT_ROOT",
            nodes=[SimpleNamespace(
                name="LIGHT_GROUP", bl_idname="ShaderNodeGroup", label="", mute=False,
                inputs={}, outputs={}, image=None, node_tree=light_group_tree,
            )],
            links=[],
        )
        light_before = blender_editorial_scene._scene_light_signature(fake_bpy)
        light_socket.default_value = 2.0
        light_after = blender_editorial_scene._scene_light_signature(fake_bpy)
        self.assertNotEqual(light_before, light_after)

    def test_scene_signatures_hash_same_size_packed_image_bytes(self) -> None:
        """Catches packed textures being identified only by their byte length."""

        fake_bpy = _FakeBpy()
        evidence = editorial_sets.build_editorial_set(fake_bpy, self.shot)
        allowed = {item.name for item in evidence.geometry}
        support = next(obj for obj in fake_bpy.context.scene.objects if obj.name in allowed)
        image_node = support.data.materials[0].node_tree.nodes.new("ShaderNodeTexImage")
        packed = SimpleNamespace(size=4, data=b"AAAA")
        image_node.image = SimpleNamespace(
            name="PACKED_IDENTITY", source="FILE", filepath="", packed_file=packed
        )
        before = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        packed.data = b"BBBB"
        after = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        self.assertNotEqual(before, after)

    def test_scene_signatures_ignore_blender_runtime_and_addon_registration_state(self) -> None:
        """Catches fresh-process-only metadata making identical authored content drift."""

        fake_bpy = _FakeBpy()
        evidence = editorial_sets.build_editorial_set(fake_bpy, self.shot)
        allowed = {item.name for item in evidence.geometry}
        support = next(obj for obj in fake_bpy.context.scene.objects if obj.name in allowed)
        material = support.data.materials[0]
        light = next(obj for obj in fake_bpy.context.scene.objects if obj.type == "LIGHT")
        light.data.node_tree = SimpleNamespace(name="LIGHT_ROOT", nodes=[], links=[])
        before_geometry = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        before_light = blender_editorial_scene._scene_light_signature(fake_bpy)

        material.poliigon = ""
        light.data.node_tree.is_runtime_data = False
        after_geometry = blender_editorial_scene._scene_geometry_signature(fake_bpy, allowed)
        after_light = blender_editorial_scene._scene_light_signature(fake_bpy)

        self.assertEqual(before_geometry, after_geometry)
        self.assertEqual(before_light, after_light)

    def test_support_tag_cannot_hide_an_extra_local_product_copy(self) -> None:
        """Catches a duplicated local product mesh bypassing rejection via scene-support tags."""

        fake_bpy = _FakeBpy()
        editorial_sets.build_editorial_set(fake_bpy, self.shot)
        duplicate = fake_bpy.data.objects.new(
            "DUPLICATED_LOCAL_PRODUCT",
            fake_bpy.data.meshes.new("DUPLICATED_LOCAL_PRODUCT_MESH"),
        )
        duplicate["pimm_scene_support_ownership"] = "scene-support"
        duplicate["pimm_scene_support_role"] = "fixture"
        duplicate["pimm_stable_id"] = "30G-illegal-local-copy"
        fake_bpy.context.scene.collection.objects.link(duplicate)

        errors = blender_editorial_scene._scene_object_allowlist_errors(
            fake_bpy, self.contract["set"]["support_allowlist"]
        )
        joined = "\n".join(errors)
        self.assertIn("unexpected local renderable", joined)
        self.assertIn("product ownership", joined)

    def test_local_collection_instances_cannot_bypass_the_support_allowlist(self) -> None:
        """Catches untagged or falsely tagged EMPTY instances rendering product collections."""

        for tagged in (False, True):
            with self.subTest(tagged=tagged):
                fake_bpy = _FakeBpy()
                editorial_sets.build_editorial_set(fake_bpy, self.shot)
                product = fake_bpy.data.objects.new(
                    "PRODUCT_IN_COLLECTION", fake_bpy.data.meshes.new("PRODUCT_MESH")
                )
                product["pimm_stable_id"] = "30G-hidden-product"
                collection = SimpleNamespace(
                    name="DUPLICATED_PRODUCT_COLLECTION",
                    library=None,
                    all_objects=[product],
                )
                instance = fake_bpy.data.objects.new("LOCAL_PRODUCT_INSTANCE", None)
                instance.instance_type = "COLLECTION"
                instance.instance_collection = collection
                if tagged:
                    instance["pimm_scene_support_ownership"] = "scene-support"
                    instance["pimm_scene_support_role"] = "fixture"
                fake_bpy.context.scene.collection.objects.link(instance)
                errors = blender_editorial_scene._scene_object_allowlist_errors(
                    fake_bpy, self.contract["set"]["support_allowlist"]
                )
                joined = "\n".join(errors)
                self.assertIn("unexpected local collection instance", joined)
                self.assertIn("product ownership", joined)

    def test_expected_external_instance_is_bound_to_collection_library_hash_and_provenance(self) -> None:
        """Catches an allowed EMPTY being redirected to a different collection or library."""

        shot = self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
        contract = blender_editorial_scene.prepare_editorial_contract(shot)
        fake_bpy = _FakeBpy()
        editorial_sets.build_editorial_set(fake_bpy, shot)
        records = contract["set"]["support_allowlist"]
        by_name = {record["name"]: record for record in records}
        for obj in fake_bpy.context.scene.objects:
            record = by_name.get(obj.name)
            if record:
                obj["pimm_editorial_framing_eligible"] = record["framing_eligible"]
                obj["pimm_editorial_contact_plane"] = record["contact_plane"]
        instance = next(
            obj for obj in fake_bpy.context.scene.objects
            if obj.name == "PIMM_SCENE_SUPPORT_EXTERNAL_TOOL_CART"
        )
        external = next(item for item in contract["external_assets"] if item["asset_id"] == "tool_cart")
        instance.instance_collection.library = SimpleNamespace(
            filepath=str(blender_editorial_scene.ASSET_ROOT / external["local_relative_path"])
        )
        blender_editorial_scene._bind_external_instance_contract(fake_bpy, records)
        record = by_name[instance.name]
        self.assertEqual(record["instance_collection_name"], instance.instance_collection.name)
        self.assertEqual(record["instance_library_relative_path"], external["local_relative_path"])
        self.assertEqual(record["instance_library_sha256"], external["sha256"])
        self.assertEqual(record["instance_provenance"]["asset_version_id"], external["asset_version_id"])
        baseline = blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)
        self.assertFalse(any("external instance" in error for error in baseline), baseline)

        record["instance_object_name"] += "_REDIRECTED"
        self.assertIn(
            "instance object binding changed",
            "\n".join(blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)),
        )
        record["instance_object_name"] = instance.name

        instance.instance_collection.name += "_REDIRECTED"
        self.assertIn(
            "instance collection binding changed",
            "\n".join(blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)),
        )

    def test_expected_external_instance_recurses_membership_and_rejects_nested_product_identity(self) -> None:
        """Catches product-owned data hidden in a child collection or collection cycle."""

        shot = self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
        contract = blender_editorial_scene.prepare_editorial_contract(shot)
        fake_bpy = _FakeBpy()
        editorial_sets.build_editorial_set(fake_bpy, shot)
        records = contract["set"]["support_allowlist"]
        by_name = {record["name"]: record for record in records}
        for obj in fake_bpy.context.scene.objects:
            record = by_name.get(obj.name)
            if record:
                obj["pimm_editorial_framing_eligible"] = record["framing_eligible"]
                obj["pimm_editorial_contact_plane"] = record["contact_plane"]
        instance = next(
            obj for obj in fake_bpy.context.scene.objects
            if obj.name == "PIMM_SCENE_SUPPORT_EXTERNAL_TOOL_CART"
        )
        external = next(item for item in contract["external_assets"] if item["asset_id"] == "tool_cart")
        root = instance.instance_collection
        root.library = SimpleNamespace(
            filepath=str(blender_editorial_scene.ASSET_ROOT / external["local_relative_path"])
        )
        root.objects = list(root.all_objects)
        root.children = []
        blender_editorial_scene._bind_external_instance_contract(fake_bpy, records)
        record = by_name[instance.name]
        self.assertEqual(record["instance_object_name"], instance.name)
        self.assertEqual(len(record["instance_membership_signature"]), 64)

        product = fake_bpy.data.objects.new(
            "NESTED_PRODUCT", fake_bpy.data.meshes.new("NESTED_PRODUCT_MESH")
        )
        product.data["pimm_stable_id"] = "50G-nested-product"
        child = SimpleNamespace(
            name="NESTED_CHILD", library=root.library, objects=[product], children=[]
        )
        child.children.append(root)
        root.children.append(child)
        errors = "\n".join(
            blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)
        )
        self.assertIn("product ownership", errors)
        self.assertIn("membership signature changed", errors)

    def test_expected_external_instance_recurses_member_collection_instances(self) -> None:
        """Catches nested EMPTY targets redirecting or hiding product identity outside child trees."""

        class NestedCollection(dict):
            def __init__(self, name: str, library: object, objects: list[object]) -> None:
                super().__init__()
                self.name = name
                self.library = library
                self.objects = objects
                self.children: list[object] = []

        shot = self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
        contract = blender_editorial_scene.prepare_editorial_contract(shot)
        fake_bpy = _FakeBpy()
        editorial_sets.build_editorial_set(fake_bpy, shot)
        records = contract["set"]["support_allowlist"]
        by_name = {record["name"]: record for record in records}
        for obj in fake_bpy.context.scene.objects:
            record = by_name.get(obj.name)
            if record:
                obj["pimm_editorial_framing_eligible"] = record["framing_eligible"]
                obj["pimm_editorial_contact_plane"] = record["contact_plane"]
        instance = next(
            obj for obj in fake_bpy.context.scene.objects
            if obj.name == "PIMM_SCENE_SUPPORT_EXTERNAL_TOOL_CART"
        )
        external = next(item for item in contract["external_assets"] if item["asset_id"] == "tool_cart")
        root = instance.instance_collection
        root.library = SimpleNamespace(
            filepath=str(blender_editorial_scene.ASSET_ROOT / external["local_relative_path"])
        )
        root.objects = list(root.all_objects)
        root.children = []
        safe_mesh = fake_bpy.data.objects.new(
            "NESTED_SAFE_MESH", fake_bpy.data.meshes.new("NESTED_SAFE_MESH_DATA")
        )
        nested = NestedCollection("NESTED_INSTANCE_TARGET", root.library, [safe_mesh])
        nested["pimm_external_asset_version_id"] = "nested-safe-v1"
        nested_instance = fake_bpy.data.objects.new("NESTED_COLLECTION_INSTANCE", None)
        nested_instance.instance_type = "COLLECTION"
        nested_instance.instance_collection = nested
        nested_instance.library = root.library
        root.objects.append(nested_instance)
        cycle_instance = fake_bpy.data.objects.new("NESTED_CYCLE_INSTANCE", None)
        cycle_instance.instance_type = "COLLECTION"
        cycle_instance.instance_collection = root
        cycle_instance.library = root.library
        nested.objects.append(cycle_instance)

        blender_editorial_scene._bind_external_instance_contract(fake_bpy, records)
        record = by_name[instance.name]
        baseline_signature = record["instance_membership_signature"]
        baseline_errors = blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)
        self.assertFalse(any("external instance" in error for error in baseline_errors), baseline_errors)

        redirected = NestedCollection("REDIRECTED_TARGET", root.library, [safe_mesh])
        nested_instance.instance_collection = redirected
        redirected_errors = "\n".join(
            blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)
        )
        self.assertIn("membership signature changed", redirected_errors)
        nested_instance.instance_collection = nested

        nested.library = SimpleNamespace(filepath=str(Path(root.library.filepath).with_name("redirected.blend")))
        library_errors = "\n".join(
            blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)
        )
        self.assertIn("membership signature changed", library_errors)
        nested.library = root.library

        nested["pimm_external_asset_version_id"] = "nested-safe-v2"
        provenance_errors = "\n".join(
            blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)
        )
        self.assertIn("membership signature changed", provenance_errors)
        nested["pimm_external_asset_version_id"] = "nested-safe-v1"

        product = fake_bpy.data.objects.new(
            "NESTED_INSTANCE_PRODUCT", fake_bpy.data.meshes.new("NESTED_INSTANCE_PRODUCT_MESH")
        )
        product["pimm_stable_id"] = "50G-hidden-in-instance-target"
        nested.objects.append(product)
        product_errors = "\n".join(
            blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)
        )
        self.assertIn("product ownership", product_errors)
        self.assertIn("membership signature changed", product_errors)
        self.assertEqual(len(baseline_signature), 64)

    def test_expected_external_instance_rejects_library_path_hash_and_each_provenance_field(self) -> None:
        """Catches external instance authority drifting after its author-time binding."""

        shot = self.campaign.by_shot_id["pimm-50g--concept-modern-workshop"]
        with TemporaryDirectory() as directory:
            root_path = Path(directory)
            library_path = root_path / "tool-cart.blend"
            library_path.write_bytes(b"governed-library")
            fake_bpy = _FakeBpy()
            editorial_sets.build_editorial_set(fake_bpy, shot)
            contract = blender_editorial_scene.prepare_editorial_contract(shot)
            records = contract["set"]["support_allowlist"]
            record = next(item for item in records if "instance_collection_name" in item)
            instance = next(obj for obj in fake_bpy.context.scene.objects if obj.name == record["name"])
            record["instance_library_relative_path"] = library_path.name
            record["instance_library_sha256"] = hashlib.sha256(b"governed-library").hexdigest().upper()
            record["instance_provenance"] = copy.deepcopy(record["instance_provenance"])
            record["instance_provenance"]["local_relative_path"] = library_path.name
            record["instance_provenance"]["sha256"] = record["instance_library_sha256"]
            provenance_tags = {
                "source_url": "pimm_external_source_url",
                "asset_version_id": "pimm_external_asset_version_id",
                "license": "pimm_external_license",
                "local_relative_path": "pimm_external_local_relative_path",
                "sha256": "pimm_external_sha256",
                "machine_master_modified": "pimm_external_machine_master_modified",
            }
            for key, tag in provenance_tags.items():
                instance[tag] = record["instance_provenance"][key]
            instance["pimm_external_intended_shot_ids"] = json.dumps(
                record["instance_provenance"]["intended_shot_ids"]
            )
            instance.instance_collection.library = SimpleNamespace(filepath=str(library_path))
            instance.instance_collection.objects = list(instance.instance_collection.all_objects)
            instance.instance_collection.children = []
            with patch.object(blender_editorial_scene, "ASSET_ROOT", root_path):
                blender_editorial_scene._bind_external_instance_contract(fake_bpy, records)
                baseline = blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)
                self.assertFalse(any("external instance" in error for error in baseline), baseline)

                other_path = root_path / "other.blend"
                other_path.write_bytes(b"governed-library")
                instance.instance_collection.library.filepath = str(other_path)
                self.assertIn(
                    "library binding changed",
                    "\n".join(blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)),
                )
                instance.instance_collection.library.filepath = str(library_path)

                library_path.write_bytes(b"mutated-library")
                self.assertIn(
                    "library hash changed",
                    "\n".join(blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)),
                )
                library_path.write_bytes(b"governed-library")

                for key, tag in provenance_tags.items():
                    original = instance[tag]
                    instance[tag] = not original if isinstance(original, bool) else f"{original}-mutated"
                    with self.subTest(provenance=key):
                        self.assertIn(
                            "instance provenance changed",
                            "\n".join(blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)),
                        )
                    instance[tag] = original
                intended = instance["pimm_external_intended_shot_ids"]
                instance["pimm_external_intended_shot_ids"] = json.dumps(["wrong-shot"])
                self.assertIn(
                    "instance provenance changed",
                    "\n".join(blender_editorial_scene._scene_object_allowlist_errors(fake_bpy, records)),
                )
                instance["pimm_external_intended_shot_ids"] = intended

    def test_camera_projection_occlusion_uses_screen_overlap_and_depth(self) -> None:
        """Catches world-axis ordering that misses a real rendered foot overlap."""

        foot = {"minimum": [0.40, 0.08], "maximum": [0.50, 0.18], "depth_min": 10.0, "depth_max": 12.0}
        foreground = {"minimum": [0.45, 0.10], "maximum": [0.55, 0.20], "depth_min": 8.0, "depth_max": 9.0}
        partial_depth = {"minimum": [0.45, 0.10], "maximum": [0.55, 0.20], "depth_min": 11.0, "depth_max": 13.0}
        separate = {"minimum": [0.60, 0.10], "maximum": [0.70, 0.20], "depth_min": 8.0, "depth_max": 9.0}
        behind = {"minimum": [0.45, 0.10], "maximum": [0.55, 0.20], "depth_min": 13.0, "depth_max": 14.0}
        self.assertTrue(blender_editorial_scene._projected_occlusion(foreground, foot))
        self.assertTrue(blender_editorial_scene._projected_occlusion(partial_depth, foot))
        self.assertFalse(blender_editorial_scene._projected_occlusion(separate, foot))
        self.assertFalse(blender_editorial_scene._projected_occlusion(behind, foot))

    def test_incomplete_pair_publication_is_recovered_without_deletion_at_every_boundary(self) -> None:
        """Catches a crash between sequential renames permanently blocking a shot."""

        for boundary in ("contract-published", "scene-published", "marker-published"):
            with self.subTest(boundary=boundary), TemporaryDirectory() as directory:
                root = Path(directory)
                scenes = root / "scenes"
                contracts = root / "contracts"
                rejected = root / "rejected"
                scenes.mkdir()
                contracts.mkdir()
                nonce = "c" * 32
                scene_candidate = scenes / f".shot.{nonce}.candidate.blend"
                contract_candidate = contracts / f".shot.{nonce}.candidate.json"
                transaction_candidate = contracts / ".shot.transaction.json"
                scene_candidate.write_bytes(b"scene")
                scene_path = scenes / "shot.blend"
                contract_path = contracts / "shot.json"
                marker_path = contracts / "shot.complete.json"
                contract_bytes = json.dumps({
                    "scene_id": "shot",
                    "publication": {"transaction_id": "a" * 32},
                }).encode("utf-8")
                contract_candidate.write_bytes(contract_bytes)
                marker_payload = {
                    "schema": "maliev.pimm-editorial-publication/v1",
                    "scene_id": "shot",
                    "transaction_id": "a" * 32,
                    "scene_sha256": hashlib.sha256(b"scene").hexdigest().upper(),
                    "contract_sha256": hashlib.sha256(contract_bytes).hexdigest().upper(),
                }
                transaction = blender_editorial_scene._publication_transaction_payload(
                    scene_id="shot",
                    transaction_id="a" * 32,
                    scene_candidate=scene_candidate,
                    contract_candidate=contract_candidate,
                    transaction_path=transaction_candidate,
                    scene_destination=scene_path,
                    contract_destination=contract_path,
                    marker_destination=marker_path,
                    scene_sha256=marker_payload["scene_sha256"],
                    contract_sha256=marker_payload["contract_sha256"],
                )
                blender_editorial_scene._atomic_json_write(transaction_candidate, transaction)

                def interrupt(stage: str) -> None:
                    if stage == boundary:
                        raise KeyboardInterrupt(stage)

                with self.assertRaises(KeyboardInterrupt):
                    blender_editorial_scene._commit_publication_pair(
                        scene_candidate=scene_candidate,
                        contract_candidate=contract_candidate,
                        transaction_candidate=transaction_candidate,
                        scene_destination=scene_path,
                        contract_destination=contract_path,
                        marker_destination=marker_path,
                        marker_payload=marker_payload,
                        interrupt=interrupt,
                    )
                result = blender_editorial_scene._recover_incomplete_publication(
                    scene_path, contract_path, marker_path, transaction_candidate, rejected
                )
                if boundary == "marker-published":
                    self.assertEqual(result["status"], "complete")
                    self.assertTrue(scene_path.is_file() and contract_path.is_file() and marker_path.is_file())
                else:
                    self.assertEqual(result["status"], "recovered_to_rejected")
                    self.assertTrue(result["archived_hashes_verified"])
                    expected_names = {
                        "contract-published": {
                            scene_candidate.name, contract_path.name, transaction_candidate.name,
                        },
                        "scene-published": {
                            scene_path.name, contract_path.name, transaction_candidate.name,
                        },
                    }[boundary]
                    archived_names = {
                        path.name for path in rejected.rglob("*") if path.is_file()
                    }
                    self.assertEqual(archived_names, expected_names)
                    self.assertFalse(any(path.exists() for path in (
                        scene_candidate, contract_candidate, scene_path, contract_path,
                        marker_path, transaction_candidate,
                    )))

    def test_recovery_archives_hash_drift_or_orphan_marker_and_all_nonce_candidates(self) -> None:
        """Catches incomplete artifacts being left behind or a drifted pair being trusted."""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            scenes, contracts, rejected = root / "scenes", root / "contracts", root / "rejected"
            scenes.mkdir()
            contracts.mkdir()
            scene = scenes / "shot.blend"
            contract = contracts / "shot.json"
            marker = contracts / "shot.complete.json"
            transaction = contracts / ".shot.transaction.json"
            scene.write_bytes(b"scene")
            contract_bytes = json.dumps({
                "scene_id": "shot", "publication": {"transaction_id": "a" * 32},
            }).encode("utf-8")
            contract.write_bytes(contract_bytes)
            marker.write_text(json.dumps({
                "schema": "maliev.pimm-editorial-publication/v1",
                "scene_id": "shot",
                "transaction_id": "a" * 32,
                "scene_sha256": hashlib.sha256(b"scene").hexdigest().upper(),
                "contract_sha256": hashlib.sha256(contract_bytes).hexdigest().upper(),
            }), encoding="utf-8")
            transaction.write_text(json.dumps({"paths": {}}), encoding="utf-8")
            scene.write_bytes(b"drifted-scene")
            result = blender_editorial_scene._recover_incomplete_publication(
                scene, contract, marker, transaction, rejected
            )
            self.assertEqual(result["status"], "recovered_to_rejected")
            self.assertTrue(result["archived_hashes_verified"])
            self.assertEqual(
                {path.name for path in rejected.rglob("*") if path.is_file()},
                {scene.name, contract.name, marker.name, transaction.name},
            )

        with TemporaryDirectory() as directory:
            root = Path(directory)
            scenes, contracts, rejected = root / "scenes", root / "contracts", root / "rejected"
            scenes.mkdir()
            contracts.mkdir()
            scene = scenes / "shot.blend"
            contract = contracts / "shot.json"
            marker = contracts / "shot.complete.json"
            transaction = contracts / ".shot.transaction.json"
            scene_candidate = scenes / f".shot.{'a' * 32}.candidate.blend"
            contract_candidate = contracts / f".shot.{'b' * 32}.candidate.json"
            scene_candidate.write_bytes(b"candidate-scene")
            contract_candidate.write_bytes(b"candidate-contract")
            marker.write_text("{}", encoding="utf-8")
            result = blender_editorial_scene._recover_incomplete_publication(
                scene, contract, marker, transaction, rejected
            )
            self.assertEqual(result["status"], "recovered_to_rejected")
            self.assertTrue(result["archived_hashes_verified"])
            self.assertEqual(
                {path.name for path in rejected.rglob("*") if path.is_file()},
                {scene_candidate.name, contract_candidate.name, marker.name},
            )

    def test_corrupt_journal_cannot_archive_another_shots_valid_publication(self) -> None:
        """Catches journal path injection crossing the current shot artifact namespace."""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            scenes, contracts, rejected = root / "scenes", root / "contracts", root / "rejected"
            scenes.mkdir()
            contracts.mkdir()
            current_scene = scenes / "current-shot.blend"
            current_contract = contracts / "current-shot.json"
            current_marker = contracts / "current-shot.complete.json"
            current_journal = contracts / ".current-shot.transaction.json"
            other_scene = scenes / "other-shot.blend"
            other_contract = contracts / "other-shot.json"
            other_marker = contracts / "other-shot.complete.json"
            other_journal = contracts / ".other-shot.transaction.json"
            other_scene.write_bytes(b"other-scene")
            other_contract_bytes = json.dumps({
                "scene_id": "other-shot",
                "publication": {"transaction_id": "b" * 32},
            }).encode("utf-8")
            other_contract.write_bytes(other_contract_bytes)
            other_marker.write_text(json.dumps({
                "schema": blender_editorial_scene.PUBLICATION_SCHEMA,
                "status": "complete",
                "scene_id": "other-shot",
                "transaction_id": "b" * 32,
                "scene_sha256": hashlib.sha256(b"other-scene").hexdigest().upper(),
                "contract_sha256": hashlib.sha256(other_contract_bytes).hexdigest().upper(),
            }), encoding="utf-8")
            other_nonce = "d" * 32
            other_journal.write_text(json.dumps(
                blender_editorial_scene._publication_transaction_payload(
                    scene_id="other-shot",
                    transaction_id="b" * 32,
                    scene_candidate=scenes / f".other-shot.{other_nonce}.candidate.blend",
                    contract_candidate=contracts / f".other-shot.{other_nonce}.candidate.json",
                    transaction_path=other_journal,
                    scene_destination=other_scene,
                    contract_destination=other_contract,
                    marker_destination=other_marker,
                    scene_sha256=hashlib.sha256(b"other-scene").hexdigest().upper(),
                    contract_sha256=hashlib.sha256(other_contract_bytes).hexdigest().upper(),
                )
            ), encoding="utf-8")
            protected = {
                path: path.read_bytes()
                for path in (other_scene, other_contract, other_marker, other_journal)
            }
            current_journal.write_text(json.dumps({
                "schema": blender_editorial_scene.PUBLICATION_SCHEMA,
                "status": "staged",
                "scene_id": "current-shot",
                "transaction_id": "a" * 32,
                "scene_sha256": "A" * 64,
                "contract_sha256": "B" * 64,
                "paths": {
                    "scene_candidate": str(other_scene),
                    "contract_candidate": str(other_contract),
                    "transaction": str(other_journal),
                    "scene_published": str(other_scene),
                    "contract_published": str(other_contract),
                    "completion_marker": str(other_marker),
                },
            }), encoding="utf-8")
            before = {path: hashlib.sha256(payload).hexdigest() for path, payload in protected.items()}

            result = blender_editorial_scene._recover_incomplete_publication(
                current_scene, current_contract, current_marker, current_journal, rejected
            )

            self.assertEqual(result["status"], "recovered_to_rejected")
            self.assertEqual(
                {path.name for path in rejected.rglob("*") if path.is_file()},
                {current_journal.name},
            )
            self.assertFalse(current_journal.exists())
            self.assertEqual(
                {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected},
                before,
            )

    def test_recovery_leaves_non_nonce_marker_and_journal_prefix_files_untouched(self) -> None:
        """Catches unrestricted prefix globs sweeping unrelated same-prefix files into rejection."""

        with TemporaryDirectory() as directory:
            root = Path(directory)
            scenes, contracts, rejected = root / "scenes", root / "contracts", root / "rejected"
            scenes.mkdir()
            contracts.mkdir()
            scene = scenes / "shot.blend"
            contract = contracts / "shot.json"
            marker = contracts / "shot.complete.json"
            journal = contracts / ".shot.transaction.json"
            exact_marker_candidate = contracts / f".{marker.name}.{'a' * 32}.candidate"
            exact_journal_candidate = contracts / f".{journal.name}.{'b' * 32}.candidate"
            exact_marker_candidate.write_bytes(b"exact-marker-candidate")
            exact_journal_candidate.write_bytes(b"exact-journal-candidate")
            decoys = [
                contracts / f".{marker.name}.not-a-nonce.candidate",
                contracts / f".{marker.name}.{'c' * 31}.candidate",
                contracts / f".{marker.name}.{'D' * 32}.candidate",
                contracts / f".{marker.name}.{'e' * 32}.candidate.extra",
                contracts / f".{journal.name}.not-a-nonce.candidate",
                contracts / f".{journal.name}.{'f' * 33}.candidate",
                contracts / f".{journal.name}.{'A' * 32}.candidate",
                contracts / f".{journal.name}.{'0' * 32}.candidate.backup",
            ]
            for index, path in enumerate(decoys):
                path.write_bytes(f"decoy-{index}".encode("ascii"))
            decoy_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in decoys}

            result = blender_editorial_scene._recover_incomplete_publication(
                scene, contract, marker, journal, rejected
            )

            self.assertEqual(result["status"], "recovered_to_rejected")
            self.assertTrue(result["archived_hashes_verified"])
            self.assertEqual(
                {path.name for path in rejected.rglob("*") if path.is_file()},
                {exact_marker_candidate.name, exact_journal_candidate.name},
            )
            self.assertEqual(
                {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in decoys},
                decoy_hashes,
            )

    def test_nonzero_fresh_blender_exit_fails_even_with_an_empty_error_marker(self) -> None:
        """Catches a validator crash being accepted because stdout contained one earlier [] marker."""

        completed = SimpleNamespace(
            returncode=1,
            stdout=blender_editorial_scene.VALIDATION_MARKER + "[]\n",
            stderr="forced failure",
        )
        errors = blender_editorial_scene._interpret_fresh_validation_process(completed)
        self.assertIn("exit=1", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
