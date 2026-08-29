import dataclasses
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image

import scripts.blender.pimm_production.blender_proof_render as render_module
import scripts.blender.pimm_production.proof_contract as proof_module
from scripts.blender.pimm_production.contact_sheet import build_contact_sheet
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.proof_contract import (
    ProofContract,
    validate_proof_contract,
    write_proof_manifest,
)
from scripts.blender.pimm_production.scene_contract import SceneContract
from scripts.blender.pimm_production.tests.test_scene_contract import build_scene_fixture


BLENDER = Path(r"D:\Blender 5.2\blender.exe")
REPO_ROOT = Path(__file__).resolve().parents[4]
PROOF_RUNNER = REPO_ROOT / "scripts" / "blender" / "pimm_production" / "blender_proof_render.py"
TOOL_LOCK = Path(
    r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\free-tools-lock.json"
)
RESULT_MARKER = "PIMM_PROOF_RENDER_JSON="


def scene_contract_fixture() -> SceneContract:
    """Return the exact Task 4 valid scene payload used by proof unit tests."""

    return SceneContract.from_mapping(
        {
            "schema_version": 1,
            "scene_id": "pimm-30g--hero--three-quarter",
            "machine": "30G",
            "purpose": "hero",
            "master_path": "masters/PIMM-30G-MASTER.blend",
            "master_sha256": "a" * 64,
            "master_collection": "PIMM_PUBLISHED",
            "material_library_path": "masters/PIMM-MATERIAL-LIBRARY.blend",
            "material_library_sha256": "b" * 64,
            "camera_name": "CAM_HERO",
            "complete_product": True,
            "animation_contract": None,
            "output_contract": {"width": 1200, "height": 1200, "alpha": True},
        }
    )


def overview_scene_contract_fixture() -> SceneContract:
    """Return a governed static overview contract with a required shadow gate."""

    return SceneContract.from_mapping(
        {
            "schema_version": 1,
            "scene_id": "pimm-30g--overview--three-quarter",
            "machine": "30G",
            "purpose": "overview",
            "master_path": "masters/PIMM-30G-MASTER.blend",
            "master_sha256": "a" * 64,
            "master_collection": "PIMM_PUBLISHED",
            "material_library_path": "masters/PIMM-MATERIAL-LIBRARY.blend",
            "material_library_sha256": "b" * 64,
            "camera_name": "CAM_PRODUCT",
            "complete_product": True,
            "animation_contract": None,
            "output_contract": {"width": 1200, "height": 1200, "alpha": True},
            "scene_path": "scenes/stills/pimm-30g--overview--three-quarter.blend",
            "static_render_setup": {
                "camera": {
                    "aperture_fstop": 11.0,
                    "clip_end": 10000.0,
                    "clip_start": 1.0,
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
        }
    )


def engineering_scene_contract_fixture() -> SceneContract:
    payload = overview_scene_contract_fixture().to_mapping()
    payload["scene_id"] = "pimm-30g--engineering--controls"
    payload["purpose"] = "engineering"
    payload["scene_path"] = "scenes/stills/pimm-30g--engineering--controls.blend"
    payload["static_render_setup"]["camera"].update(
        {"aperture_fstop": 8.0, "focal_length_mm": 135.0, "view": "controls"}
    )
    payload["static_render_setup"]["physical_shadow"]["gate"] = "not-applicable"
    return SceneContract.from_mapping(payload)


def composition_contract() -> ProofContract:
    return ProofContract.from_mapping(
        {
            "schema_version": 1,
            "generation_id": "proof-20260815T153000Z-a1b2c3d",
            "stage": "composition",
            "scene_contract_path": "scenes/contracts/pimm-30g--hero--three-quarter.json",
            "scene_sha256": "c" * 64,
            "master_sha256": "a" * 64,
            "material_library_sha256": "b" * 64,
            "resolution_percentage": 25,
            "samples": 32,
            "denoise": True,
            "backgrounds": ["white", "checker", "dark"],
            "object_masks": False,
            "alpha_safety": {
                "product_margin": 0.08,
                "shadow_margin": 0.12,
                "evidence_path": "manifests/proof-evidence/proof-20260815T153000Z-a1b2c3d/alpha-safety.json",
                "evidence_sha256": "e" * 64,
                "result": {
                    "canvas_size": [100, 100], "product_bounds": [10, 10, 89, 89], "shadow_bounds": [15, 15, 84, 84],
                    "product_edge_fractions": {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0}, "shadow_edge_fractions": {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0},
                    "product_alpha_extrema": [0, 255], "shadow_alpha_extrema": [0, 128], "catcher_visible": False, "reasons": [], "passed": True,
                },
            },
            "contact_evidence": {"status": "not-applicable"},
            "output_root": "renders/proofs/proof-20260815T153000Z-a1b2c3d",
        }
    )


def material_contract(backgrounds: list[str], object_masks: bool) -> ProofContract:
    return ProofContract.from_mapping(
        {
            "schema_version": 1,
            "generation_id": "proof-20260815T153001Z-b2c3d4e",
            "stage": "material-lighting",
            "scene_contract_path": "scenes/contracts/pimm-30g--hero--three-quarter.json",
            "scene_sha256": "c" * 64,
            "master_sha256": "a" * 64,
            "material_library_sha256": "b" * 64,
            "resolution_percentage": 25,
            "samples": 64,
            "denoise": True,
            "backgrounds": list(backgrounds),
            "object_masks": object_masks,
            "alpha_safety": {
                "product_margin": 0.08,
                "shadow_margin": 0.12,
                "evidence_path": "manifests/proof-evidence/proof-20260815T153001Z-b2c3d4e/alpha-safety.json",
                "evidence_sha256": "e" * 64,
                "result": {
                    "canvas_size": [100, 100], "product_bounds": [10, 10, 89, 89], "shadow_bounds": [15, 15, 84, 84],
                    "product_edge_fractions": {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0}, "shadow_edge_fractions": {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0},
                    "product_alpha_extrema": [0, 255], "shadow_alpha_extrema": [0, 128], "catcher_visible": False, "reasons": [], "passed": True,
                },
            },
            "contact_evidence": {"status": "not-applicable"},
            "output_root": "renders/proofs/proof-20260815T153001Z-b2c3d4e",
        }
    )


def _write_scene_contract(root: Path, contract: SceneContract, relative: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8")
    return path


def _run_fixture_proofs(
    scene_path: Path,
    proof_paths: list[Path],
    root: Path,
    *,
    inject_drift_after_prepare: bool = False,
    inject_authored_mutation: str | None = None,
    inject_dependency_mutation: str | None = None,
    inject_minimal_geometry_nodes: bool = False,
    inject_pointer_socket_materials: bool = False,
    inject_pointer_socket_swap: bool = False,
    inject_geometry_transform: bool = False,
    inject_compositor_file_output: bool = False,
    inject_compositor_render_layers: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[dict[str, object]]]:
    runner = PROOF_RUNNER
    if (
        inject_drift_after_prepare
        or inject_authored_mutation is not None
        or inject_dependency_mutation is not None
        or inject_minimal_geometry_nodes
        or inject_pointer_socket_materials
        or inject_pointer_socket_swap
        or inject_geometry_transform
        or inject_compositor_file_output
        or inject_compositor_render_layers is not None
    ):
        runner = root / "inject_proof_drift.py"
        runner.write_text(
            "\n".join(
                [
                    "from pathlib import Path",
                    "import json",
                    "import os",
                    "import sys",
                    f"sys.path.insert(0, {str(REPO_ROOT)!r})",
                    "import bpy",
                    "import scripts.blender.pimm_production.blender_proof_render as proof_render",
                    *(
                        [
                            "fixture_compositor = bpy.data.node_groups.new('AUTHORED_COMPOSITOR', 'CompositorNodeTree')",
                            "bpy.context.scene.compositing_node_group = fixture_compositor",
                            *(
                                [
                                    "unsafe_directory = Path("
                                    + repr(str(root / "unsafe-compositor-output"))
                                    + ")",
                                    "unsafe_directory.mkdir(parents=True, exist_ok=True)",
                                    "fixture_render_layers = fixture_compositor.nodes.new('CompositorNodeRLayers')",
                                    "fixture_file_output = fixture_compositor.nodes.new('CompositorNodeOutputFile')",
                                    "fixture_file_output.directory = str(unsafe_directory) + os.sep",
                                    "fixture_file_output.file_name = 'UNSAFE_{frame}'",
                                    "fixture_compositor.links.new(fixture_render_layers.outputs['Image'], fixture_file_output.inputs[0])",
                                ]
                                if inject_compositor_file_output
                                else [
                                    "fixture_render_layers = fixture_compositor.nodes.new('CompositorNodeRLayers')",
                                    *(
                                        [
                                            "fixture_second_scene = bpy.data.scenes.new('SECOND_PROOF_SCENE')",
                                            "fixture_render_layers.scene = fixture_second_scene",
                                        ]
                                        if inject_compositor_render_layers == "second"
                                        else []
                                    ),
                                ]
                            ),
                            "original_compositor_capture = proof_render._capture_authored_settings",
                            "compositor_capture_written = False",
                            "def capture_with_fixture_compositor(bpy_arg):",
                            "    global compositor_capture_written",
                            "    capture = original_compositor_capture(bpy_arg)",
                            "    if not compositor_capture_written:",
                            "        compositor_capture_written = True",
                            "        Path("
                            + repr(str(root / "compositor-capture.json"))
                            + ").write_text(json.dumps(capture, sort_keys=True), encoding='utf-8')",
                            "    return capture",
                            "proof_render._capture_authored_settings = capture_with_fixture_compositor",
                        ]
                        if inject_compositor_file_output
                        or inject_compositor_render_layers is not None
                        else []
                    ),
                    *(
                        [
                            "original_minimal_capture = proof_render._capture_authored_settings",
                            "minimal_setup_done = False",
                            "minimal_capture_written = False",
                            "def capture_with_minimal_geometry_nodes(bpy_arg):",
                            "    global minimal_setup_done, minimal_capture_written, fixture_group, fixture_set_material, fixture_set_material_b",
                            "    if not minimal_setup_done:",
                            "        minimal_setup_done = True",
                            "        fixture_mesh = bpy.data.meshes.new('MINIMAL_GEOMETRY_MESH')",
                            "        fixture_mesh.from_pydata([(-0.1,-0.1,0.1),(0.1,-0.1,0.1),(0.0,0.1,0.1)], [], [(0,1,2)])",
                            "        fixture_object = bpy.data.objects.new('MINIMAL_GEOMETRY_OBJECT', fixture_mesh)",
                            "        bpy.context.scene.collection.objects.link(fixture_object)",
                            "        fixture_group = bpy.data.node_groups.new('MINIMAL_GEOMETRY_GROUP', 'GeometryNodeTree')",
                            "        fixture_group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')",
                            "        fixture_group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')",
                            "        fixture_input = fixture_group.nodes.new('NodeGroupInput')",
                            "        fixture_set_material = fixture_group.nodes.new('GeometryNodeSetMaterial')",
                            "        fixture_output = fixture_group.nodes.new('NodeGroupOutput')",
                            *(
                                [
                            "        fixture_material_a = bpy.data.materials.new('SOCKET_MATERIAL_A')",
                            "        fixture_material_a['pimm_material_id'] = 'SOCKET_MATERIAL_A'",
                            "        fixture_material_b = bpy.data.materials.new('SOCKET_MATERIAL_B')",
                            "        fixture_material_b['pimm_material_id'] = 'SOCKET_MATERIAL_B'",
                                    "        fixture_set_material.name = 'SET_MATERIAL_A'",
                                    "        fixture_set_material.inputs['Material'].default_value = fixture_material_a",
                                    "        fixture_set_material_b = fixture_group.nodes.new('GeometryNodeSetMaterial')",
                                    "        fixture_set_material_b.name = 'SET_MATERIAL_B'",
                                    "        fixture_set_material_b.inputs['Material'].default_value = fixture_material_b",
                                    "        fixture_group.links.new(fixture_input.outputs['Geometry'], fixture_set_material.inputs['Geometry'])",
                                    "        fixture_group.links.new(fixture_set_material.outputs['Geometry'], fixture_set_material_b.inputs['Geometry'])",
                                    "        fixture_group.links.new(fixture_set_material_b.outputs['Geometry'], fixture_output.inputs['Geometry'])",
                                ]
                                if inject_pointer_socket_materials or inject_pointer_socket_swap
                                else ([
                                    "        fixture_set_material_b = None",
                                    "        fixture_transform = fixture_group.nodes.new('GeometryNodeTransform')",
                                    "        fixture_group.links.new(fixture_input.outputs['Geometry'], fixture_transform.inputs['Geometry'])",
                                    "        fixture_group.links.new(fixture_transform.outputs['Geometry'], fixture_set_material.inputs['Geometry'])",
                                    "        fixture_group.links.new(fixture_set_material.outputs['Geometry'], fixture_output.inputs['Geometry'])",
                                ] if inject_geometry_transform else [
                                    "        fixture_set_material_b = None",
                                    "        fixture_group.links.new(fixture_input.outputs['Geometry'], fixture_set_material.inputs['Geometry'])",
                                    "        fixture_group.links.new(fixture_set_material.outputs['Geometry'], fixture_output.inputs['Geometry'])",
                                ])
                            ),
                            "        fixture_modifier = fixture_object.modifiers.new('MINIMAL_GEOMETRY_NODES', 'NODES')",
                            "        fixture_modifier.node_group = fixture_group",
                            "    fixture_capture = original_minimal_capture(bpy_arg)",
                            "    if not minimal_capture_written:",
                            "        minimal_capture_written = True",
                            "        Path(" + repr(str(root / "minimal-geometry-capture.json")) + ").write_text(json.dumps(fixture_capture, sort_keys=True), encoding='utf-8')",
                            "    return fixture_capture",
                            "proof_render._capture_authored_settings = capture_with_minimal_geometry_nodes",
                            "original_environment_errors = proof_render._proof_environment_errors",
                            "def fixture_environment_errors(bpy_arg):",
                            "    return [error for error in original_environment_errors(bpy_arg) if error != 'unauthorized local proof environment mesh object: MINIMAL_GEOMETRY_OBJECT']",
                            "proof_render._proof_environment_errors = fixture_environment_errors",
                        ]
                        if (
                            inject_minimal_geometry_nodes
                            or inject_pointer_socket_materials
                            or inject_pointer_socket_swap
                            or inject_geometry_transform
                        )
                        else []
                    ),
                    *(
                        [
                            "scene = bpy.context.scene",
                            "authored_light_data = bpy.data.lights.new('AUTHORED_KEY', type='AREA')",
                            "authored_light_data.energy = 125.0",
                            "authored_light_data.color = (0.2, 0.4, 0.6)",
                            "authored_light = bpy.data.objects.new('AUTHORED_KEY', authored_light_data)",
                            "scene.collection.objects.link(authored_light)",
                            "authored_world = bpy.data.worlds.new('AUTHORED_WORLD')",
                            "authored_world.use_nodes = True",
                            "scene.world = authored_world",
                            "compositor = bpy.data.node_groups.new('AUTHORED_COMPOSITOR', 'CompositorNodeTree')",
                            "compositor_node = compositor.nodes.new('CompositorNodeBrightContrast')",
                        ]
                        if inject_authored_mutation is not None
                        else []
                    ),
                    *(
                        [
                            "external_path = Path(" + repr(str(root / "fixture-external.png")) + ")",
                            "replacement_path = Path(" + repr(str(root / "fixture-external-replacement.png")) + ")",
                            "original_capture = proof_render._capture_authored_settings",
                            "dependency_setup_done = False",
                            "def capture_with_fixture_dependencies(bpy_arg):",
                            "    global dependency_setup_done, authored_object, authored_mesh, authored_material, alternate_material, principled, authored_packed, authored_collection, authored_layer_collection, authored_modifier, authored_geometry_group, authored_geometry_socket, authored_geometry_input, authored_geometry_material_input, authored_geometry_value, authored_geometry_math, authored_geometry_link",
                            "    if not dependency_setup_done:",
                            "        dependency_setup_done = True",
                            "        authored_mesh = bpy.data.meshes.new('AUTHORED_RENDER_MESH')",
                            "        authored_mesh.from_pydata([(-0.4,-0.4,0.2),(0.4,-0.4,0.2),(0.0,0.4,0.2)], [], [(0,1,2)])",
                            "        authored_object = bpy.data.objects.new('AUTHORED_RENDER_OBJECT', authored_mesh)",
                            "        bpy.context.scene.collection.objects.link(authored_object)",
                            "        authored_collection = bpy.data.collections.new('AUTHORED_RENDER_COLLECTION')",
                            "        bpy.context.scene.collection.children.link(authored_collection)",
                            "        authored_layer_collection = bpy.context.view_layer.layer_collection.children[authored_collection.name]",
                            "        authored_material = bpy.data.materials.new('AUTHORED_RENDER_MATERIAL')",
                            "        authored_material['pimm_material_id'] = 'AUTHORED_RENDER_MATERIAL'",
                            "        authored_material.use_nodes = True",
                            "        authored_material.diffuse_color = (0.2,0.3,0.4,1.0)",
                            "        authored_material.roughness = 0.35",
                            "        principled = authored_material.node_tree.nodes.get('Principled BSDF')",
                            "        external_image = bpy.data.images.load(str(external_path), check_existing=False)",
                            "        external_node = authored_material.node_tree.nodes.new('ShaderNodeTexImage')",
                            "        external_node.image = external_image",
                            "        authored_material.node_tree.links.new(external_node.outputs['Color'], principled.inputs['Base Color'])",
                            "        authored_packed = bpy.data.images.new('AUTHORED_PACKED_IMAGE', width=2, height=2)",
                            "        authored_packed.pixels[:] = [0.1,0.2,0.3,1.0] * 4",
                            "        authored_packed.pack()",
                            "        packed_node = authored_material.node_tree.nodes.new('ShaderNodeTexImage')",
                            "        packed_node.image = authored_packed",
                            "        authored_material.node_tree.links.new(packed_node.outputs['Alpha'], principled.inputs['Roughness'])",
                            "        nested = bpy.data.node_groups.new('AUTHORED_NESTED_GROUP', 'ShaderNodeTree')",
                            "        nested.nodes.new('ShaderNodeValue').outputs[0].default_value = 0.25",
                            "        group_node = authored_material.node_tree.nodes.new('ShaderNodeGroup')",
                            "        group_node.node_tree = nested",
                            "        authored_modifier = authored_object.modifiers.new('AUTHORED_GEOMETRY_NODES', 'NODES')",
                            "        authored_geometry_group = bpy.data.node_groups.new('AUTHORED_GEOMETRY_GROUP', 'GeometryNodeTree')",
                            "        authored_geometry_socket = authored_geometry_group.interface.new_socket(name='Authored Scale', in_out='INPUT', socket_type='NodeSocketFloat')",
                            "        authored_geometry_object_socket = authored_geometry_group.interface.new_socket(name='Authored Object', in_out='INPUT', socket_type='NodeSocketObject')",
                            "        authored_geometry_collection_socket = authored_geometry_group.interface.new_socket(name='Authored Collection', in_out='INPUT', socket_type='NodeSocketCollection')",
                            "        authored_geometry_material_socket = authored_geometry_group.interface.new_socket(name='Authored Material', in_out='INPUT', socket_type='NodeSocketMaterial')",
                            "        authored_geometry_image_socket = authored_geometry_group.interface.new_socket(name='Authored Image', in_out='INPUT', socket_type='NodeSocketImage')",
                            "        authored_modifier.node_group = authored_geometry_group",
                            "        authored_geometry_input = getattr(authored_modifier.properties.inputs, authored_geometry_socket.identifier)",
                            "        authored_geometry_input.value = 0.25",
                            "        getattr(authored_modifier.properties.inputs, authored_geometry_object_socket.identifier).value = authored_object",
                            "        getattr(authored_modifier.properties.inputs, authored_geometry_collection_socket.identifier).value = authored_collection",
                            "        authored_geometry_material_input = getattr(authored_modifier.properties.inputs, authored_geometry_material_socket.identifier)",
                            "        authored_geometry_material_input.value = authored_material",
                            "        getattr(authored_modifier.properties.inputs, authored_geometry_image_socket.identifier).value = authored_packed",
                            "        authored_geometry_value = authored_geometry_group.nodes.new('ShaderNodeValue')",
                            "        authored_geometry_value.outputs[0].default_value = 0.125",
                            "        authored_geometry_math = authored_geometry_group.nodes.new('ShaderNodeMath')",
                            "        authored_geometry_link = authored_geometry_group.links.new(authored_geometry_value.outputs[0], authored_geometry_math.inputs[0])",
                            "        authored_mesh.materials.append(authored_material)",
                            "        alternate_material = bpy.data.materials.new('AUTHORED_ALTERNATE_MATERIAL')",
                            "        alternate_material['pimm_material_id'] = 'AUTHORED_ALTERNATE_MATERIAL'",
                            "    return original_capture(bpy_arg)",
                            "proof_render._capture_authored_settings = capture_with_fixture_dependencies",
                            "original_environment_errors = proof_render._proof_environment_errors",
                            "def fixture_environment_errors(bpy_arg):",
                            "    return [error for error in original_environment_errors(bpy_arg) if error != 'unauthorized local proof environment mesh object: AUTHORED_RENDER_OBJECT']",
                            "proof_render._proof_environment_errors = fixture_environment_errors",
                        ]
                        if inject_dependency_mutation is not None
                        else []
                    ),
                    "original = proof_render._run_pillow_finalizer",
                    "def injected(*args, **kwargs):",
                    "    result = original(*args, **kwargs)",
                    *(
                        [
                            "    pointer_a = fixture_set_material.inputs['Material'].default_value",
                            "    pointer_b = fixture_set_material_b.inputs['Material'].default_value",
                            "    fixture_set_material.inputs['Material'].default_value = pointer_b",
                            "    fixture_set_material_b.inputs['Material'].default_value = pointer_a",
                            "    swapped_capture = original_minimal_capture(bpy)",
                            "    Path(" + repr(str(root / "swapped-material-capture.json")) + ").write_text(json.dumps(swapped_capture, sort_keys=True), encoding='utf-8')",
                        ]
                        if inject_pointer_socket_swap
                        else []
                    ),
                    *(
                        [
                            f"    source = Path({str(root / 'sources' / 'PIMM-30G-authoritative-source.step')!r})",
                            "    source.write_bytes(source.read_bytes() + b'INJECTED-DRIFT')",
                        ]
                        if inject_drift_after_prepare
                        else []
                    ),
                    *(
                        {
                            "camera": ["    scene.camera.data.sensor_width += 1.0"],
                            "light": ["    authored_light_data.color = (0.9, 0.1, 0.2)"],
                            "world": [
                                "    authored_world.node_tree.nodes['Background'].inputs['Strength'].default_value += 1.0"
                            ],
                            "compositor": [
                                "    compositor_node.mute = True",
                                "    scene.compositing_node_group = compositor",
                            ],
                        }.get(inject_authored_mutation, [])
                    ),
                    *(
                        {
                            "object_visibility": ["    authored_object.hide_render = True"],
                            "geometry": [
                                "    authored_mesh.vertices[0].co.x += 0.25",
                                "    authored_mesh.update()",
                            ],
                            "material_scalar": ["    authored_material.roughness = 0.9"],
                            "material_node": [
                                "    principled.inputs['Metallic'].default_value = 0.75"
                            ],
                            "material_assignment": [
                                "    authored_mesh.materials[0] = alternate_material"
                            ],
                            "external_image": [
                                "    external_path.write_bytes(replacement_path.read_bytes())"
                            ],
                            "packed_image": [
                                "    authored_packed.pixels[0:4] = (0.9,0.8,0.7,1.0)",
                                "    authored_packed.update()",
                            ],
                            "dof": [
                                "    bpy.context.scene.camera.data.dof.focus_distance += 3.0"
                            ],
                            "collection_hide_render": [
                                "    authored_collection.hide_render = True"
                            ],
                            "layer_collection_exclude": [
                                "    authored_layer_collection.exclude = True"
                            ],
                            "layer_collection_holdout": [
                                "    authored_layer_collection.holdout = True"
                            ],
                            "layer_collection_indirect_only": [
                                "    authored_layer_collection.indirect_only = True"
                            ],
                            "collection_membership": [
                                "    authored_collection.objects.link(authored_object)"
                            ],
                            "gn_modifier_id_property": [
                                "    authored_geometry_input.value = 0.875"
                            ],
                            "gn_modifier_pointer": [
                                "    authored_geometry_material_input.value = alternate_material"
                            ],
                            "gn_node": [
                                "    authored_geometry_group.nodes.new('ShaderNodeValue')"
                            ],
                            "gn_node_default": [
                                "    authored_geometry_value.outputs[0].default_value = 0.875"
                            ],
                            "gn_node_link": [
                                "    authored_geometry_group.links.remove(authored_geometry_link)"
                            ],
                        }.get(inject_dependency_mutation, [])
                    ),
                    "    return result",
                    "proof_render._run_pillow_finalizer = injected",
                    "raise SystemExit(proof_render.main())",
                ]
            ),
            encoding="utf-8",
        )
    command = [
        str(BLENDER),
        "--factory-startup",
        "-b",
        str(scene_path),
        "--python-exit-code",
        "1",
        "-P",
        str(runner),
        "--",
        "--fixture-asset-root",
        str(root),
        "--tool-lock",
        str(TOOL_LOCK),
    ]
    for proof_path in proof_paths:
        command.extend(["--proof-contract", str(proof_path)])
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    rows = [
        json.loads(line.removeprefix(RESULT_MARKER))
        for line in result.stdout.splitlines()
        if line.startswith(RESULT_MARKER)
    ]
    return result, rows


_BLENDER_52_ALLOWLIST_INSTANTIATION_EXCLUSIONS = {
    "CompositorNodeTree:CompositorNodeComposite": {
        "reason": (
            "Blender 5.2 factory-startup reports the legacy node identifier as undefined"
        ),
        "instantiable": False,
    },
    "CompositorNodeTree:CompositorNodeOutputFile": {
        "reason": "unsafe external writer prohibited in proof scenes",
        "instantiable": True,
    },
}
_BLENDER_52_UNSAFE_AUDIT_NODE_TYPES = {
    "CompositorNodeTree": frozenset({"CompositorNodeOutputFile"})
}


def _run_allowlist_compatibility_audit(
    root: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    result_path = root / "allowlist-compatibility.json"
    script_path = root / "audit_allowlisted_nodes.py"
    script_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import json",
                "import sys",
                f"sys.path.insert(0, {str(REPO_ROOT)!r})",
                "import bpy",
                "import scripts.blender.pimm_production.blender_proof_render as proof_render",
                "import scripts.blender.pimm_production.proof_contract as proof_contract",
                f"result_path = Path({str(result_path)!r})",
                "exclusions = "
                + repr(_BLENDER_52_ALLOWLIST_INSTANTIATION_EXCLUSIONS),
                "unsafe_node_types = " + repr(_BLENDER_52_UNSAFE_AUDIT_NODE_TYPES),
                "passed = []",
                "excluded = []",
                "failures = []",
                "for tree_type, node_types in sorted(proof_contract._NODE_TYPES_BY_TREE.items()):",
                "    audit_node_types = set(node_types) | set(unsafe_node_types.get(tree_type, ()))",
                "    for node_type in sorted(audit_node_types):",
                "        key = f'{tree_type}:{node_type}'",
                "        tree = bpy.data.node_groups.new(f'AUDIT_{tree_type}_{node_type}', tree_type)",
                "        try:",
                "            node = tree.nodes.new(node_type)",
                "        except Exception as error:",
                "            if key in exclusions and not exclusions[key]['instantiable']:",
                "                excluded.append({'key': key, 'reason': exclusions[key]['reason'], 'error': f'{type(error).__name__}: {error}'})",
                "            else:",
                "                failures.append({'key': key, 'stage': 'instantiate', 'error': f'{type(error).__name__}: {error}'})",
                "            continue",
                "        if key in exclusions:",
                "            if exclusions[key]['instantiable']:",
                "                excluded.append({'key': key, 'reason': exclusions[key]['reason']})",
                "            else:",
                "                failures.append({'key': key, 'stage': 'exclusion', 'error': 'documented exclusion unexpectedly instantiated'})",
                "            continue",
                "        if node_type in {'ShaderNodeGroup', 'GeometryNodeGroup'}:",
                "            nested = bpy.data.node_groups.new(f'{key}_NESTED', tree_type)",
                "            node.node_tree = nested",
                "        elif node_type in {'ShaderNodeTexImage', 'ShaderNodeTexEnvironment'}:",
                "            node.image = bpy.data.images.new(f'{key}_IMAGE', width=1, height=1)",
                "        if node_type in {'NodeGroupInput', 'NodeGroupOutput'} and tree_type == 'GeometryNodeTree':",
                "            tree.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')",
                "            tree.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')",
                "        try:",
                "            proof_render._node_tree_record(tree, image_cache={})",
                "        except Exception as error:",
                "            failures.append({'key': key, 'stage': 'capture', 'error': f'{type(error).__name__}: {error}'})",
                "        else:",
                "            passed.append(key)",
                "payload = {'passed': passed, 'excluded': excluded, 'failures': failures}",
                "result_path.write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            str(BLENDER),
            "--factory-startup",
            "-b",
            "--python-exit-code",
            "1",
            "-P",
            str(script_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    payload = (
        json.loads(result_path.read_text(encoding="utf-8"))
        if result_path.is_file()
        else {}
    )
    return result, payload


def _write_real_fixture_proof(
    root: Path, slug: str
) -> tuple[Path, ProofContract, Path]:
    scene_path, scene = build_scene_fixture("valid", root)
    source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
    scene_contract_path = _write_scene_contract(
        root, scene, f"scenes/fixtures/{slug}-scene.json"
    )
    contract = dataclasses.replace(
        composition_contract(),
        scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
        scene_sha256=sha256_file(scene_path),
        master_sha256=scene.master_sha256,
        material_library_sha256=scene.material_library_sha256,
        resolution_percentage=12.5,
        samples=16,
    )
    proof_path = root / "scenes" / "fixtures" / f"{slug}-proof.json"
    proof_path.write_text(
        json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
    )
    return scene_path, contract, proof_path


def _fingerprint_record(path: str, sha256: str) -> dict[str, object]:
    return {"path": path, "bytes": 1, "mtime_ns": 1, "sha256": sha256}


def _recompute_dependency_digest(authored: dict[str, object]) -> None:
    dependency_payload = {
        field: authored[field]
        for field in (
            "scene_identity",
            "library_authorities",
            "objects",
            "materials",
            "images",
            "collection_tree",
            "view_layers",
        )
    }
    authored["dependency_sha256"] = hashlib.sha256(
        json.dumps(
            dependency_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest().upper()


def _valid_dependency_object(name: str = "AUTHORED_OBJECT") -> dict[str, object]:
    return {
        "identity": {"name": name, "type": "Object", "library": None},
        "object_type": "MESH",
        "data": {
            "identity": {"name": f"{name}_MESH", "type": "Mesh", "library": None},
            "properties": {},
            "geometry": {
                "sha256": "8" * 64,
                "vertices": 3,
                "edges": 3,
                "loops": 3,
                "polygons": 1,
            },
        },
        "transform": {
            "location": [0.0, 0.0, 0.0],
            "rotation_mode": "XYZ",
            "rotation_euler": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
            "matrix_world": [1.0] * 16,
            "parent": None,
        },
        "hide_render": False,
        "hide_viewport": False,
        "properties": {},
        "collections": [
            {
                "identity": {
                    "name": "Scene Collection",
                    "type": "Collection",
                    "library": None,
                },
                "path": ["Scene Collection"],
            }
        ],
        "material_slots": [],
        "modifiers": [],
    }


def _valid_camera_dependency_object() -> dict[str, object]:
    record = _valid_dependency_object("CAM_HERO")
    record["object_type"] = "CAMERA"
    record["data"] = {
        "identity": {"name": "CAM_HERO", "type": "Camera", "library": None},
        "properties": {},
    }
    record["transform"] = {
        "location": [4.0, -6.0, 3.0],
        "rotation_mode": "XYZ",
        "rotation_euler": [1.0, 0.0, 0.5],
        "scale": [1.0, 1.0, 1.0],
        "matrix_world": [1.0] * 16,
        "parent": None,
    }
    return record


def _valid_dependency_node_tree() -> dict[str, object]:
    return {
        "identity": {"name": "AUTHORED_TREE", "type": "ShaderNodeTree", "library": None},
        "nodes": [
            {
                "name": "Value",
                "type": "ShaderNodeValue",
                "mute": False,
                "properties": {},
                "inputs": [],
                "outputs": [
                    {
                        "name": "Value",
                        "identifier": "Value",
                        "type": "NodeSocketFloat",
                        "enabled": True,
                        "is_linked": False,
                        "default": 0.5,
                    }
                ],
                "data": {},
            }
        ],
        "links": [],
    }


def _valid_compositor_node_tree(
    node_type: str, *, scene_name: str = "Scene"
) -> dict[str, object]:
    common_properties: dict[str, object] = {
        "bl_height_default": 100.0,
        "bl_height_max": 3.4028234663852886e38,
        "bl_height_min": 30.0,
        "bl_icon": "NONE",
        "bl_width_max": 700.0,
        "bl_width_min": 100.0,
        "hide": False,
        "mute": False,
        "use_custom_color": False,
        "warning_propagation": "ALL",
    }
    if node_type == "CompositorNodeOutputFile":
        node = {
            "name": "File Output",
            "type": node_type,
            "mute": False,
            "properties": {
                **common_properties,
                "active_item_index": 0,
                "bl_description": "Write image file to disk",
                "bl_idname": node_type,
                "bl_label": "File Output",
                "bl_static_type": "OUTPUT_FILE",
                "bl_width_default": 140.0,
                "color_tag": "OUTPUT",
                "directory": "C:\\unsafe-external-output\\",
                "file_name": "UNSAFE_{frame}",
                "save_as_render": True,
                "type": "OUTPUT_FILE",
                "use_file_extension": True,
            },
            "inputs": [
                {
                    "name": "",
                    "identifier": "__extend__",
                    "type": "NodeSocketVirtual",
                    "enabled": True,
                    "is_linked": False,
                    "default": None,
                }
            ],
            "outputs": [],
            "data": {
                "parent": None,
                "format": {
                    "name": "",
                    "type": "ImageFormatSettings",
                    "library": None,
                },
            },
        }
    elif node_type == "CompositorNodeRLayers":
        node = {
            "name": "Render Layers",
            "type": node_type,
            "mute": False,
            "properties": {
                **common_properties,
                "bl_description": "Input render passes from a scene render",
                "bl_idname": node_type,
                "bl_label": "Render Layers",
                "bl_static_type": "R_LAYERS",
                "bl_width_default": 240.0,
                "color_tag": "INPUT",
                "layer": "ViewLayer",
                "type": "R_LAYERS",
            },
            "inputs": [],
            "outputs": [
                {
                    "name": "Image",
                    "identifier": "Image",
                    "type": "NodeSocketColor",
                    "enabled": True,
                    "is_linked": False,
                    "default": [
                        0.800000011921,
                        0.800000011921,
                        0.800000011921,
                        1.0,
                    ],
                },
                {
                    "name": "Alpha",
                    "identifier": "Alpha",
                    "type": "NodeSocketFloat",
                    "enabled": True,
                    "is_linked": False,
                    "default": 0.0,
                },
            ],
            "data": {
                "parent": None,
                "scene": {"name": scene_name, "type": "Scene", "library": None},
            },
        }
    else:
        raise ValueError(f"unsupported compositor fixture node: {node_type}")
    return {
        "identity": {
            "name": "AUTHORED_COMPOSITOR",
            "type": "CompositorNodeTree",
            "library": None,
        },
        "nodes": [node],
        "links": [],
    }


def _valid_dependency_material() -> dict[str, object]:
    return {
        "identity": {
            "name": "AUTHORED_MATERIAL",
            "type": "Material",
            "library": None,
            "pimm_material_id": "AUTHORED_MATERIAL",
        },
        "properties": {},
        "node_tree": _valid_dependency_node_tree(),
    }


def _valid_dependency_modifier() -> dict[str, object]:
    group_identity = {
        "name": "AUTHORED_GEOMETRY_GROUP",
        "type": "GeometryNodeTree",
        "library": None,
    }
    return {
        "name": "AUTHORED_MODIFIER",
        "type": "NODES",
        "properties": {
            "bake_directory": "",
            "bake_target": "PACKED",
            "execution_time": 0.0,
            "is_active": True,
            "is_override_data": False,
            "open_bake_data_blocks_panel": False,
            "open_bake_panel": False,
            "open_manage_panel": False,
            "open_named_attributes_panel": False,
            "open_output_attributes_panel": False,
            "open_warnings_panel": True,
            "persistent_uid": 1,
            "show_expanded": True,
            "show_group_selector": True,
            "show_in_editmode": True,
            "show_manage_panel": True,
            "show_on_cage": False,
            "show_render": True,
            "show_viewport": True,
            "use_apply_on_spline": False,
            "use_pin_to_last": False,
        },
        "references": {
            "node_group": group_identity,
            "properties": {
                "name": "",
                "type": "GeometryNodesModifierInterface",
                "library": None,
            },
        },
        "id_properties": [],
        "interface_inputs": [],
        "node_group": {"identity": group_identity, "nodes": [], "links": []},
    }


def _valid_material_socket_modifier(
    material_identity: dict[str, object],
) -> dict[str, object]:
    modifier = _valid_dependency_modifier()
    modifier["node_group"]["nodes"] = [
        {
            "name": "SET_MATERIAL",
            "type": "GeometryNodeSetMaterial",
            "mute": False,
            "properties": {
                "bl_description": "Assign a material to geometry elements",
                "bl_height_default": 100.0,
                "bl_height_max": 3.4028234663852886e38,
                "bl_height_min": 30.0,
                "bl_icon": "NONE",
                "bl_idname": "GeometryNodeSetMaterial",
                "bl_label": "Set Material",
                "bl_static_type": "SET_MATERIAL",
                "bl_width_default": 140.0,
                "bl_width_max": 700.0,
                "bl_width_min": 100.0,
                "color_tag": "GEOMETRY",
                "hide": False,
                "mute": False,
                "type": "SET_MATERIAL",
                "use_custom_color": False,
                "warning_propagation": "ALL",
            },
            "inputs": [
                {
                    "name": "Material",
                    "identifier": "Material",
                    "type": "NodeSocketMaterial",
                    "enabled": True,
                    "is_linked": False,
                    "default": {"kind": "identity", "value": dict(material_identity)},
                }
            ],
            "outputs": [],
            "data": {"parent": None},
        }
    ]
    return modifier


def _valid_dependency_image() -> dict[str, object]:
    return {
        "name": "AUTHORED_IMAGE",
        "type": "Image",
        "library": None,
        "filepath": "",
        "source": "GENERATED",
        "size": [4, 4],
        "channels": 4,
        "depth": 32,
        "is_float": False,
        "file_format": "PNG",
        "alpha_mode": "STRAIGHT",
        "colorspace": "sRGB",
        "external_files": [],
        "packed_files": [],
        "pixels": {
            "encoding": "float32-little-endian",
            "values": 64,
            "sha256": "9" * 64,
        },
    }


def _valid_render_metadata(
    contract: ProofContract,
    *,
    actual_dimensions: list[int] | None = None,
    named_shaft_regions: dict[str, object] | None = None,
) -> dict[str, object]:
    fingerprints = {
        "source": _fingerprint_record("C:/fixture/source.step", "1" * 64),
        "master": _fingerprint_record(
            "C:/fixture/master.blend", contract.master_sha256.upper()
        ),
        "material_library": _fingerprint_record(
            "C:/fixture/material.blend", contract.material_library_sha256.upper()
        ),
        "scene": _fingerprint_record("C:/fixture/scene.blend", contract.scene_sha256.upper()),
    }
    collection_identity = {"name": "Scene Collection", "type": "Collection", "library": None}
    layer_collection = {
        "path": ["Scene Collection"],
        "collection": collection_identity,
        "exclude": False,
        "holdout": False,
        "indirect_only": False,
        "hide_viewport": False,
        "children": [],
    }
    authored_settings: dict[str, object] = {
        "scene_identity": {"name": "Scene", "type": "Scene", "library": None},
        "library_authorities": [],
        "camera": {
            "identity": {"name": "CAM_HERO", "type": "Object", "library": None},
            "transform": {
                "location": [4.0, -6.0, 3.0],
                "rotation_mode": "XYZ",
                "rotation_euler": [1.0, 0.0, 0.5],
                "scale": [1.0, 1.0, 1.0],
                "matrix_world": [1.0] * 16,
                "parent": None,
            },
            "type": "PERSP",
            "lens": 50.0,
            "sensor_fit": "AUTO",
            "sensor_width": 36.0,
            "sensor_height": 32.0,
            "shift_x": 0.0,
            "shift_y": 0.0,
            "clip_start": 0.1,
            "clip_end": 1000.0,
            "dof": {
                "use_dof": False,
                "focus_object": None,
                "focus_distance": 10.0,
                "aperture_fstop": 2.8,
                "aperture_blades": 0,
                "aperture_rotation": 0.0,
                "aperture_ratio": 1.0,
            },
        },
        "lights": [],
        "world": None,
        "compositor": {"enabled": False, "node_tree": None},
        "render": {
            "properties": {"engine": "CYCLES"},
            "image_settings": {},
            "ffmpeg": {},
        },
        "view_layers": [
            {
                "name": "ViewLayer",
                "properties": {},
                "material_override": None,
                "layer_collection": layer_collection,
            }
        ],
        "color_management": {
            "view": {"view_transform": "AgX"},
            "display": {},
            "sequencer": {},
        },
        "cycles": {"samples": contract.samples},
        "objects": [_valid_camera_dependency_object()],
        "materials": [],
        "images": [],
        "collection_tree": {
            "identity": collection_identity,
            "path": ["Scene Collection"],
            "hide_render": False,
            "hide_viewport": False,
            "properties": {},
            "objects": [
                {"name": "CAM_HERO", "type": "Object", "library": None}
            ],
            "children": [],
        },
    }
    _recompute_dependency_digest(authored_settings)
    return {
        "schema": "pimm-proof-render-metadata/v1",
        "engine": "CYCLES",
        "device": "CPU",
        "blender": {
            "binary_path": "D:/Blender 5.2/blender.exe",
            "binary_sha256": "4" * 64,
            "version": "5.2.0",
        },
        "resolution_percentage": contract.resolution_percentage,
        "base_dimensions": [1200, 1200],
        "actual_dimensions": actual_dimensions or [300, 300],
        "image_settings": {
            "film_transparent": True,
            "file_format": "PNG",
            "color_mode": "RGBA",
            "color_depth": "8",
            "use_file_extension": True,
        },
        "samples": contract.samples,
        "denoise": contract.denoise,
        "cycles": {
            "device": "CPU",
            "samples": contract.samples,
            "use_denoising": contract.denoise,
            "max_bounces": 12,
            "transparent_max_bounces": 8,
        },
        "agx": {
            "view_transform": "AgX",
            "look": "Medium High Contrast",
            "exposure": 0.0,
            "gamma": 1.0,
        },
        "render_seconds": 0.25,
        "named_shaft_regions": named_shaft_regions or {},
        "shadow_pass_available": True,
        "shadow_evidence_sha256": None,
        "meaningful_physical_shadow_threshold": 32,
        "fixture_mode": True,
        "proof_contract_sha256": "5" * 64,
        "scene_contract_sha256": "6" * 64,
        "tool_lock_sha256": "7" * 64,
        "fingerprints": {"before": fingerprints, "after": fingerprints},
        "authored_settings": {
            "before": authored_settings,
            "after": authored_settings,
        },
        "intended_subject_metrics": {
            "bounds": {"left": 1, "top": 1, "right": 20, "bottom": 14},
            "nonzero_fraction": 0.5,
            "unique_values": [0, 255],
            "unique_value_count": 2,
        },
        "physical_shadow_metrics": {
            "bounds": {"left": 2, "top": 2, "right": 21, "bottom": 15},
            "nonzero_fraction": 0.25,
            "unique_values": [0, 255],
            "unique_value_count": 2,
        },
    }


def _write_manifest_evidence(
    root: Path,
    output_root: Path,
    contract: ProofContract,
    scene: SceneContract,
    metadata: dict[str, object],
) -> None:
    del root
    proof_snapshot = output_root / "proof-contract.json"
    scene_snapshot = output_root / "scene-contract.json"
    tool_snapshot = output_root / "tool-lock.json"
    proof_snapshot.write_text(
        json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
    )
    scene_snapshot.write_text(
        json.dumps(scene.to_mapping(), sort_keys=True), encoding="utf-8"
    )
    tool_snapshot.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "id": "blender",
                        "path": metadata["blender"]["binary_path"],
                        "sha256": metadata["blender"]["binary_sha256"],
                        "version": metadata["blender"]["version"],
                    }
                ]
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    metadata["proof_contract_sha256"] = sha256_file(proof_snapshot)
    metadata["scene_contract_sha256"] = sha256_file(scene_snapshot)
    metadata["tool_lock_sha256"] = sha256_file(tool_snapshot)
    (output_root / "render-metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )


def _prepare_finalizer_fixture(
    root: Path, output_root: Path
) -> tuple[ProofContract, SceneContract, Path, Path, Path]:
    contract = material_contract(["white", "checker", "dark"], True)
    scene = scene_contract_fixture()
    proof_path = root / "fixture-proof.json"
    proof_path.write_text(
        json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
    )
    _write_scene_contract(root, scene, contract.scene_contract_path)
    output_root.mkdir(parents=True, exist_ok=True)
    _write_manifest_evidence(
        root, output_root, contract, scene, _valid_render_metadata(contract)
    )
    rgba = output_root / f"{scene.scene_id}--rgba.png"
    Image.new("RGBA", (300, 300), (90, 110, 130, 255)).save(rgba)
    product = output_root / f".{scene.scene_id}--product-only.tmp.png"
    Image.new("RGBA", (300, 300), (90, 110, 130, 255)).save(product)
    return contract, scene, proof_path, rgba, product


def _prepare_canonical_shadow_fixture(
    root: Path,
) -> tuple[ProofContract, SceneContract, Path, Path, Path, Path]:
    scene = overview_scene_contract_fixture()
    contract = ProofContract.from_mapping(
        {
            **composition_contract().to_mapping(),
            "scene_contract_path": "scenes/contracts/pimm-30g--overview--three-quarter.json",
        }
    )
    output_root = root / contract.output_root
    output_root.mkdir(parents=True)
    proof_path = root / "canonical-proof.json"
    proof_path.write_text(json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8")
    _write_scene_contract(root, scene, contract.scene_contract_path)
    metadata = _valid_render_metadata(contract)
    metadata["fixture_mode"] = False
    metadata["shadow_pass_available"] = True
    shadow = output_root / f".{scene.scene_id}--shadow-catcher.tmp.png"
    shadow_image = Image.new("L", (300, 300), 0)
    for y in range(205, 231):
        for x in range(65, 236):
            shadow_image.putpixel((x, y), 96)
    shadow_image.save(shadow)
    metadata["shadow_evidence_sha256"] = sha256_file(shadow)
    _write_manifest_evidence(root, output_root, contract, scene, metadata)
    rgba = output_root / f"{scene.scene_id}--rgba.png"
    source = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    for y in range(40, 221):
        for x in range(50, 251):
            source.putpixel((x, y), (90, 110, 130, 255))
    source.save(rgba)
    return contract, scene, proof_path, output_root, rgba, shadow


class ProofContractTests(unittest.TestCase):
    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 fixture runtime unavailable")
    def test_blender_captures_lossless_canonical_shadow_pass_and_restores_state(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            script = root / "capture_shadow.py"
            destination = root / ".pimm-30g--overview--three-quarter--shadow-catcher.tmp.png"
            script.write_text(
                textwrap.dedent(
                    f"""
                    import json
                    from pathlib import Path
                    import sys
                    import bpy
                    from mathutils import Vector
                    sys.path.insert(0, {str(REPO_ROOT)!r})
                    from scripts.blender.pimm_production import blender_proof_render as module

                    destination = Path({str(destination)!r})
                    scene = bpy.context.scene
                    scene.render.engine = "CYCLES"
                    scene.cycles.samples = 4
                    scene.render.resolution_x = 32
                    scene.render.resolution_y = 32
                    scene.render.resolution_percentage = 100
                    scene.render.film_transparent = True
                    scene.render.filepath = str(destination.parent / "combined.png")
                    scene.render.image_settings.file_format = "PNG"
                    scene.render.image_settings.color_mode = "RGBA"
                    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
                    catcher = bpy.context.object
                    catcher.name = "PIMM_SCENE_SHADOW_CATCHER"
                    catcher.is_shadow_catcher = True
                    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
                    bpy.ops.object.light_add(type="AREA", location=(4, -4, 6))
                    bpy.context.object.data.energy = 1000
                    bpy.ops.object.camera_add(location=(6, -6, 5))
                    camera = bpy.context.object
                    camera.rotation_euler = (
                        Vector((0, 0, 1)) - camera.location
                    ).to_track_quat("-Z", "Y").to_euler()
                    scene.camera = camera
                    view_layer = bpy.context.view_layer
                    prior_pass = view_layer.cycles.use_pass_shadow_catcher
                    prior_tree = scene.compositing_node_group
                    view_layer.cycles.use_pass_shadow_catcher = True
                    state = module._install_shadow_catcher_output(
                        bpy, scene, view_layer, destination
                    )
                    try:
                        bpy.ops.render.render(write_still=True)
                        module._publish_shadow_catcher_output(destination, state[3])
                    finally:
                        module._remove_shadow_catcher_output(bpy, scene, *state[:3])
                        view_layer.cycles.use_pass_shadow_catcher = prior_pass
                    import OpenImageIO as oiio
                    image = oiio.ImageInput.open(str(destination))
                    pixels = image.read_image()
                    image.close()
                    print("PIMM_SHADOW_CAPTURE_JSON=" + json.dumps({{
                        "max": float(pixels.max()),
                        "pass_restored": view_layer.cycles.use_pass_shadow_catcher == prior_pass,
                        "tree_restored": scene.compositing_node_group == prior_tree,
                    }}, sort_keys=True))
                    """
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(BLENDER), "--background", "--factory-startup", "--python", str(script)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            markers = [
                line.removeprefix("PIMM_SHADOW_CAPTURE_JSON=")
                for line in result.stdout.splitlines()
                if line.startswith("PIMM_SHADOW_CAPTURE_JSON=")
            ]
            self.assertEqual(len(markers), 1, msg=result.stdout + result.stderr)
            marker = markers[0]
            payload = json.loads(marker)
            self.assertGreater(payload["max"], 0)
            self.assertTrue(payload["pass_restored"])
            self.assertTrue(payload["tree_restored"])

    def test_canonical_shadow_evidence_populates_real_physical_shadow_metrics(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            _contract, _scene, proof_path, output_root, rgba, shadow = (
                _prepare_canonical_shadow_fixture(root)
            )

            result = render_module.finalize_proof(
                proof_path,
                output_root,
                rgba,
                root,
                shadow_catcher_path=shadow,
            )

            metadata = json.loads(
                (output_root / "render-metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["meaningful_physical_shadow_threshold"], 32)
            self.assertGreater(metadata["physical_shadow_metrics"]["nonzero_fraction"], 0)
            self.assertEqual(metadata["physical_shadow_metrics"]["bounds"]["bottom"], 230)
            self.assertFalse(shadow.exists())
            self.assertTrue(Path(result["manifest_pending_path"]).is_file())

    def test_render_metadata_rejects_physical_shadow_threshold_drift(self):
        for drifted in (31, 32.0, True):
            with self.subTest(drifted=drifted), TemporaryDirectory() as root_text:
                root = Path(root_text)
                _contract, _scene, proof_path, output_root, rgba, shadow = (
                    _prepare_canonical_shadow_fixture(root)
                )
                metadata_path = output_root / "render-metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["meaningful_physical_shadow_threshold"] = drifted
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "physical shadow threshold"):
                    render_module.finalize_proof(
                        proof_path,
                        output_root,
                        rgba,
                        root,
                        shadow_catcher_path=shadow,
                    )

    def test_required_canonical_shadow_evidence_rejects_missing_empty_and_corrupt_inputs(self):
        cases = ("missing", "empty", "hash-mismatch", "corrupt")
        for case in cases:
            with self.subTest(case=case), TemporaryDirectory() as root_text:
                root = Path(root_text)
                _contract, _scene, proof_path, output_root, rgba, shadow = (
                    _prepare_canonical_shadow_fixture(root)
                )
                supplied = shadow
                expected = "physical shadow evidence"
                if case == "missing":
                    supplied = None
                elif case == "empty":
                    Image.new("L", (300, 300), 0).save(shadow)
                    metadata_path = output_root / "render-metadata.json"
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    metadata["shadow_evidence_sha256"] = sha256_file(shadow)
                    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
                    expected = "empty"
                elif case == "hash-mismatch":
                    Image.new("L", (300, 300), 64).save(shadow)
                    expected = "hash"
                else:
                    shadow.write_bytes(b"not-a-png")
                    metadata_path = output_root / "render-metadata.json"
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    metadata["shadow_evidence_sha256"] = sha256_file(shadow)
                    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
                    expected = "corrupt|image"

                with self.assertRaisesRegex(ValueError, expected):
                    render_module.finalize_proof(
                        proof_path,
                        output_root,
                        rgba,
                        root,
                        shadow_catcher_path=supplied,
                    )

                self.assertFalse((output_root / "manifest.json").exists())

    def test_overview_rejects_meaningful_combined_alpha_on_disallowed_frame_edge(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            _contract, _scene, proof_path, output_root, rgba, shadow = (
                _prepare_canonical_shadow_fixture(root)
            )
            with Image.open(rgba) as loaded:
                source = loaded.convert("RGBA")
            for y in range(100, 151):
                source.putpixel((0, y), (90, 110, 130, 255))
            source.save(rgba)

            with self.assertRaisesRegex(ValueError, "overview.*frame edge"):
                render_module.finalize_proof(
                    proof_path,
                    output_root,
                    rgba,
                    root,
                    shadow_catcher_path=shadow,
                )

    def test_overview_rejects_shadow_only_left_right_and_bottom_frame_edges(self):
        edge_pixels = {
            "left": ((0, y) for y in range(205, 231)),
            "right": ((299, y) for y in range(205, 231)),
            "bottom": ((x, 299) for x in range(65, 236)),
        }
        for edge, pixels in edge_pixels.items():
            with self.subTest(edge=edge), TemporaryDirectory() as root_text:
                root = Path(root_text)
                _contract, _scene, proof_path, output_root, rgba, shadow = (
                    _prepare_canonical_shadow_fixture(root)
                )
                with Image.open(shadow) as loaded:
                    shadow_image = loaded.convert("L")
                for pixel in pixels:
                    shadow_image.putpixel(pixel, 32)
                shadow_image.save(shadow)
                metadata_path = output_root / "render-metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["shadow_evidence_sha256"] = sha256_file(shadow)
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

                with self.assertRaisesRegex(
                    ValueError, f"overview meaningful shadow alpha touches.*{edge}.*frame edge"
                ):
                    render_module.finalize_proof(
                        proof_path,
                        output_root,
                        rgba,
                        root,
                        shadow_catcher_path=shadow,
                    )

    def test_overview_ignores_subthreshold_shadow_edges_and_keeps_strong_inset_metrics(self):
        edge_pixels = {
            "left": ((0, y) for y in range(205, 231)),
            "right": ((299, y) for y in range(205, 231)),
            "bottom": ((x, 299) for x in range(65, 236)),
        }
        for edge, pixels in edge_pixels.items():
            with self.subTest(edge=edge), TemporaryDirectory() as root_text:
                root = Path(root_text)
                _contract, _scene, proof_path, output_root, rgba, shadow = (
                    _prepare_canonical_shadow_fixture(root)
                )
                with Image.open(shadow) as loaded:
                    shadow_image = loaded.convert("L")
                for pixel in pixels:
                    shadow_image.putpixel(pixel, 31)
                shadow_image.save(shadow)
                metadata_path = output_root / "render-metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["shadow_evidence_sha256"] = sha256_file(shadow)
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

                render_module.finalize_proof(
                    proof_path,
                    output_root,
                    rgba,
                    root,
                    shadow_catcher_path=shadow,
                )

                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                self.assertEqual(
                    metadata["physical_shadow_metrics"]["bounds"],
                    {"left": 65, "top": 205, "right": 235, "bottom": 230},
                )

    def test_engineering_close_crop_may_finalize_without_shadow_only_when_contract_bound(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene = engineering_scene_contract_fixture()
            contract = ProofContract.from_mapping(
                {
                    **composition_contract().to_mapping(),
                    "scene_contract_path": "scenes/contracts/pimm-30g--engineering--controls.json",
                }
            )
            output_root = root / contract.output_root
            output_root.mkdir(parents=True)
            proof_path = root / "engineering-proof.json"
            proof_path.write_text(
                json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
            )
            _write_scene_contract(root, scene, contract.scene_contract_path)
            metadata = _valid_render_metadata(contract)
            metadata["fixture_mode"] = False
            metadata["shadow_pass_available"] = False
            _write_manifest_evidence(root, output_root, contract, scene, metadata)
            rgba = output_root / f"{scene.scene_id}--rgba.png"
            Image.new("RGBA", (300, 300), (90, 110, 130, 255)).save(rgba)

            result = render_module.finalize_proof(
                proof_path, output_root, rgba, root
            )

            metadata = json.loads(
                (output_root / "render-metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["physical_shadow_metrics"]["nonzero_fraction"], 0)
            self.assertTrue(Path(result["manifest_pending_path"]).is_file())

    def test_blender_52_node_capture_does_not_read_deprecated_use_nodes(self):
        class Property:
            identifier = "use_nodes"
            type = "BOOLEAN"

        class Owner:
            bl_rna = type("RNA", (), {"properties": [Property()]})()
            node_tree = "NODE_TREE"

            @property
            def use_nodes(self):
                raise AssertionError("deprecated use_nodes must not be read")

        owner = Owner()

        self.assertEqual(render_module._rna_scalar_properties(owner), {})
        self.assertEqual(render_module._node_tree_for_owner(owner), "NODE_TREE")

    def test_authored_settings_require_a_schema_bound_library_authority_manifest(
        self,
    ) -> None:
        """Catches Task 5 evidence that erases Blender's lexical library authority."""

        authored = _valid_render_metadata(composition_contract())["authored_settings"][
            "before"
        ]

        try:
            validated = proof_module.validate_authored_settings(
                authored, "fixture authored settings"
            )
        except ValueError as error:
            self.fail(f"library authority manifest is not schema-bound: {error}")

        self.assertEqual(validated["library_authorities"], [])

    def test_composition_proof_is_low_cost(self):
        contract = composition_contract()
        self.assertLessEqual(contract.resolution_percentage, 25)
        self.assertGreaterEqual(contract.resolution_percentage, 12.5)
        self.assertLessEqual(contract.samples, 32)

    def test_material_proof_requires_all_backgrounds_and_masks(self):
        contract = material_contract(backgrounds=["white"], object_masks=False)
        errors = validate_proof_contract(contract, scene_contract_fixture())
        self.assertIn("white/checker/dark", "\n".join(errors))
        self.assertIn("object/material masks", "\n".join(errors))

    def test_contract_is_exact_immutable_and_round_trips_json(self):
        contract = composition_contract()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            contract.samples = 1
        payload = contract.to_mapping()
        payload["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "exactly"):
            ProofContract.from_mapping(payload)

        with TemporaryDirectory() as root_text:
            path = Path(root_text) / "proof.json"
            payload.pop("unexpected")
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(ProofContract.from_json(path), contract)
        self.assertIsInstance(contract.backgrounds, tuple)

    def test_contract_requires_alpha_policy_and_current_contact_evidence(self):
        """Catches a proof contract that can omit alpha QA or bind an unauditable floor report."""

        payload = composition_contract().to_mapping()
        payload["alpha_safety"] = {"product_margin": 0.08, "shadow_margin": 0.12}
        payload["contact_evidence"] = {"status": "bound", "reports": [{"machine": "30G", "report_path": "../masters/contact.json", "report_sha256": "not-a-hash"}]}
        malformed = ProofContract.from_mapping(payload)

        errors = "\n".join(validate_proof_contract(malformed, scene_contract_fixture()))

        self.assertIn("alpha_safety must contain exactly", errors)
        self.assertIn("contact_evidence reports[0] report_path", errors)
        self.assertIn("contact_evidence reports[0] report_sha256", errors)

    def test_campaign_base_feet_detail_cannot_skip_current_contact_plane_evidence(self):
        """Catches a base/feet proof declaring its full-machine contact plane irrelevant."""

        scene = dataclasses.replace(
            scene_contract_fixture(), scene_id="pimm-30g--base-feet--macro"
        )
        contract = dataclasses.replace(
            composition_contract(),
            scene_contract_path="scenes/contracts/pimm-30g--base-feet--macro.json",
            contact_evidence={"status": "not-applicable"},
        )

        errors = "\n".join(validate_proof_contract(contract, scene))

        self.assertIn("base/feet detail requires bound contact evidence", errors)

    def test_campaign_proof_requires_hashed_measured_alpha_and_current_contact_reports(self):
        """Catches campaign proof policy being accepted without authenticated measured evidence."""

        scene = dataclasses.replace(
            scene_contract_fixture(),
            scene_id="pimm-30g--hero--desktop",
            output_contract={"width": 2560, "height": 1440, "alpha": True},
        )
        result = {
            "canvas_size": [100, 100],
            "product_bounds": [10, 10, 89, 89],
            "shadow_bounds": [15, 15, 84, 84],
            "product_edge_fractions": {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0},
            "shadow_edge_fractions": {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0},
            "product_alpha_extrema": [0, 255],
            "shadow_alpha_extrema": [0, 128],
            "catcher_visible": False,
            "reasons": [],
            "passed": True,
        }
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            alpha_path = root / "manifests/proof-evidence/proof-20260815T153000Z-a1b2c3d/alpha-safety.json"
            alpha_path.parent.mkdir(parents=True)
            alpha_path.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
            contact_payload = {
                "schema": "maliev.pimm-four-foot-contact/v1",
                "machine": "30G",
                "master_sha256": scene.master_sha256,
                "foot_count": 4,
                "stable_ids": ["pad-a", "pad-b", "pad-c", "pad-d"],
                "contact_plane_z": -0.162624216,
            }
            contact_path = root / "manifests/contact/pimm-30g-foot-contact.json"
            contact_path.parent.mkdir(parents=True)
            contact_path.write_text(json.dumps(contact_payload, sort_keys=True), encoding="utf-8")
            contract = dataclasses.replace(
                composition_contract(),
                scene_contract_path="scenes/contracts/pimm-30g--hero--desktop.json",
                alpha_safety={
                    "product_margin": 0.08,
                    "shadow_margin": 0.12,
                    "evidence_path": "manifests/proof-evidence/proof-20260815T153000Z-a1b2c3d/alpha-safety.json",
                    "evidence_sha256": sha256_file(alpha_path),
                    "result": result,
                },
                contact_evidence={
                    "status": "bound",
                    "reports": [{
                        "machine": "30G",
                        "report_path": "manifests/contact/pimm-30g-foot-contact.json",
                        "report_sha256": sha256_file(contact_path),
                    }],
                },
            )
            _write_scene_contract(root, scene, contract.scene_contract_path)
            with patch.object(proof_module, "ASSET_ROOT", root):
                self.assertEqual(validate_proof_contract(contract, scene), [])
                alpha_path.write_text("{}", encoding="utf-8")
                errors = "\n".join(validate_proof_contract(contract, scene))

            with patch.object(proof_module, "_CAMPAIGN_PATH", root / "missing-campaign.json"):
                campaign_errors = "\n".join(validate_proof_contract(contract, scene))

        self.assertIn("alpha_safety evidence", errors)
        self.assertIn("campaign-owned proof validation failed closed", campaign_errors)

    def test_contract_rejects_cost_path_generation_and_hash_mutations(self):
        scene = scene_contract_fixture()
        mutations = {
            "generation": ("generation_id", "proof-reused"),
            "native": ("resolution_percentage", 100),
            "samples": ("samples", 33),
            "denoise": ("denoise", False),
            "escape": ("output_root", "renders/finals/proof-20260815T153000Z-a1b2c3d"),
            "master": ("master_sha256", "d" * 64),
        }
        for name, (field, value) in mutations.items():
            with self.subTest(name=name):
                contract = dataclasses.replace(composition_contract(), **{field: value})
                errors = "\n".join(validate_proof_contract(contract, scene))
                self.assertTrue(errors)
        self.assertIn(
            "samples",
            "\n".join(
                validate_proof_contract(
                    dataclasses.replace(material_contract(["white", "checker", "dark"], True), samples=65),
                    scene,
                )
            ),
        )

    def test_contract_rejects_preexisting_generation_directory(self):
        contract = composition_contract()
        scene = scene_contract_fixture()
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            _write_scene_contract(root, scene, contract.scene_contract_path)
            (root / contract.output_root).mkdir(parents=True)
            with patch.object(proof_module, "ASSET_ROOT", root):
                errors = validate_proof_contract(contract, scene)
        self.assertIn("generation ID is already in use", "\n".join(errors))

    def test_effective_dimensions_are_exact_and_fractional_rounding_is_rejected(self):
        scene = scene_contract_fixture()
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            for percentage, expected in ((12.5, (150, 150)), (25, (300, 300))):
                with self.subTest(percentage=percentage):
                    contract = dataclasses.replace(
                        composition_contract(),
                        resolution_percentage=percentage,
                    )
                    _write_scene_contract(root, scene, contract.scene_contract_path)
                    with patch.object(proof_module, "ASSET_ROOT", root):
                        errors = validate_proof_contract(contract, scene)
                    self.assertEqual(errors, [])
                    self.assertEqual(
                        proof_module.effective_dimensions(scene, percentage), expected
                    )

            rounded = dataclasses.replace(
                composition_contract(), resolution_percentage=12.6
            )
            with patch.object(proof_module, "ASSET_ROOT", root):
                errors = validate_proof_contract(rounded, scene)
            self.assertIn("non-integral effective dimensions", "\n".join(errors))

    def test_manifest_rejects_incomplete_mixed_or_drifted_evidence(self):
        mutations = {
            "missing-engine": "metadata",
            "fingerprint-drift": "metadata",
            "master-pin-mismatch": "metadata",
            "material-pin-mismatch": "metadata",
            "scene-pin-mismatch": "metadata",
            "settings-mismatch": "metadata",
            "blender-lock-mismatch": "metadata",
            "wrong-dimensions": "image",
            "mixed-shot": "filename",
            "missing-output": "output",
        }
        for mutation in mutations:
            with self.subTest(mutation=mutation), TemporaryDirectory() as root_text:
                root = Path(root_text)
                contract = composition_contract()
                scene = scene_contract_fixture()
                _write_scene_contract(root, scene, contract.scene_contract_path)
                output_root = root / contract.output_root
                output_root.mkdir(parents=True)
                outputs: list[Path] = []
                for background in ("rgba", "white", "checker", "dark"):
                    if mutation == "missing-output" and background == "dark":
                        continue
                    shot_id = (
                        "pimm-30g--detail--mixed"
                        if mutation == "mixed-shot" and background == "dark"
                        else scene.scene_id
                    )
                    dimensions = (
                        (299, 300)
                        if mutation == "wrong-dimensions" and background == "white"
                        else (300, 300)
                    )
                    path = output_root / f"{shot_id}--{background}.png"
                    Image.new("RGBA", dimensions, (100, 120, 140, 255)).save(path)
                    outputs.append(path)
                metadata = _valid_render_metadata(contract)
                if mutation == "missing-engine":
                    metadata.pop("engine")
                elif mutation == "fingerprint-drift":
                    metadata["fingerprints"] = json.loads(
                        json.dumps(metadata["fingerprints"])
                    )
                    metadata["fingerprints"]["after"]["source"]["sha256"] = "9" * 64
                elif mutation == "settings-mismatch":
                    metadata["samples"] = contract.samples - 1
                elif mutation.endswith("-pin-mismatch"):
                    name = mutation.removesuffix("-pin-mismatch")
                    if name == "material":
                        name = "material_library"
                    metadata["fingerprints"] = json.loads(
                        json.dumps(metadata["fingerprints"])
                    )
                    metadata["fingerprints"]["before"][name]["sha256"] = "9" * 64
                    metadata["fingerprints"]["after"][name]["sha256"] = "9" * 64
                _write_manifest_evidence(root, output_root, contract, scene, metadata)
                if mutation == "blender-lock-mismatch":
                    metadata["blender"]["binary_sha256"] = "8" * 64
                    (output_root / "render-metadata.json").write_text(
                        json.dumps(metadata), encoding="utf-8"
                    )

                with patch.object(proof_module, "ASSET_ROOT", root):
                    with self.assertRaises(ValueError):
                        write_proof_manifest(contract, outputs)

    def test_manifest_rejects_malformed_authored_dependency_entries(self):
        mutations = (
            "not-a-dependency",
            "geometry-hash",
            "object-type",
            "material-node",
            "modifier-record",
            "image-path-and-hash",
            "image-identity-type",
            "duplicate-object-identity",
            "reordered-objects",
            "inconsistent-digest",
            "identity-null-dependency",
            "node-tree-null-dependency",
            "fake-node-tree-type",
            "wrong-context-node-tree-type",
            "fake-modifier-enum",
            "fake-rna-enum",
            "file-image-without-content-evidence",
            "file-image-with-both-content-authorities",
            "generated-image-without-pixel-evidence",
            "collection-path-leaf-mismatch",
            "collection-child-path-mismatch",
            "layer-path-leaf-mismatch",
            "layer-child-path-mismatch",
            "object-membership-path-spoof",
            "unknown-material-reference",
            "material-socket-wrong-pointer-type",
            "material-socket-unknown-identity",
            "material-socket-identity-null-kind",
            "unsafe-compositor-file-output",
            "render-layers-unknown-scene",
            "shared-material-id-name-swap",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), TemporaryDirectory() as root_text:
                root = Path(root_text)
                contract = composition_contract()
                scene = scene_contract_fixture()
                _write_scene_contract(root, scene, contract.scene_contract_path)
                output_root = root / contract.output_root
                output_root.mkdir(parents=True)
                outputs: list[Path] = []
                for background in ("rgba", "white", "checker", "dark"):
                    path = output_root / f"{scene.scene_id}--{background}.png"
                    Image.new("RGBA", (300, 300), (100, 120, 140, 255)).save(path)
                    outputs.append(path)
                metadata = _valid_render_metadata(contract)
                authored = json.loads(json.dumps(metadata["authored_settings"]["before"]))
                if mutation == "not-a-dependency":
                    authored["objects"] = [{"not": "a dependency fingerprint"}]
                elif mutation == "geometry-hash":
                    record = _valid_dependency_object()
                    record["data"]["geometry"]["sha256"] = "not-a-hash"
                    authored["objects"] = [record]
                elif mutation == "object-type":
                    record = _valid_dependency_object()
                    record["object_type"] = "NOT_A_BLENDER_OBJECT_TYPE"
                    authored["objects"] = [record]
                elif mutation == "material-node":
                    record = _valid_dependency_material()
                    record["node_tree"]["nodes"][0].pop("mute")
                    authored["materials"] = [record]
                elif mutation == "modifier-record":
                    record = _valid_dependency_object()
                    record["modifiers"] = [{"name": "broken"}]
                    authored["objects"] = [record]
                elif mutation == "image-path-and-hash":
                    record = _valid_dependency_image()
                    record["source"] = "FILE"
                    record["filepath"] = "relative.png"
                    record["external_files"] = [
                        {
                            "path": "relative.png",
                            "resolved_path": "relative.png",
                            "bytes": 1,
                            "mtime_ns": 1,
                            "ctime_ns": 1,
                            "device": 1,
                            "inode": 1,
                            "links": 1,
                            "sha256": "bad",
                        }
                    ]
                    authored["images"] = [record]
                elif mutation == "image-identity-type":
                    record = _valid_dependency_image()
                    record["type"] = "Material"
                    authored["images"] = [record]
                elif mutation == "duplicate-object-identity":
                    authored["objects"] = [
                        _valid_dependency_object(),
                        _valid_dependency_object(),
                    ]
                elif mutation == "reordered-objects":
                    authored["objects"] = [
                        _valid_dependency_object("B_OBJECT"),
                        _valid_dependency_object("A_OBJECT"),
                    ]
                elif mutation == "identity-null-dependency":
                    record = _valid_dependency_object()
                    modifier = _valid_dependency_modifier()
                    modifier["interface_inputs"] = [
                        {
                            "index": 0,
                            "identifier": "Socket_0",
                            "name": "Authored Object",
                            "socket_type": "NodeSocketObject",
                            "properties": {"name": "", "type": "VALUE"},
                            "references": {
                                "value": {"kind": "identity", "value": None}
                            },
                        }
                    ]
                    record["modifiers"] = [modifier]
                    authored["objects"] = [record]
                elif mutation == "node-tree-null-dependency":
                    record = _valid_dependency_object()
                    modifier = _valid_dependency_modifier()
                    modifier["id_properties"] = [
                        {
                            "name": "AuthoredTree",
                            "dependency": {"kind": "node_tree", "value": None},
                        }
                    ]
                    record["modifiers"] = [modifier]
                    authored["objects"] = [record]
                elif mutation == "fake-node-tree-type":
                    record = _valid_dependency_material()
                    record["node_tree"]["identity"]["type"] = "DefinitelyFakeNodeTree"
                    authored["materials"] = [record]
                elif mutation == "wrong-context-node-tree-type":
                    record = _valid_dependency_material()
                    record["node_tree"]["identity"]["type"] = "GeometryNodeTree"
                    authored["materials"] = [record]
                elif mutation == "fake-modifier-enum":
                    record = _valid_dependency_object()
                    modifier = _valid_dependency_modifier()
                    modifier["type"] = "DEFINITELY_FAKE"
                    record["modifiers"] = [modifier]
                    authored["objects"] = [record]
                elif mutation == "fake-rna-enum":
                    authored["render"]["properties"]["engine"] = "DEFINITELY_FAKE"
                elif mutation == "file-image-without-content-evidence":
                    record = _valid_dependency_image()
                    record["source"] = "FILE"
                    record["filepath"] = "C:/fixture/no-evidence.png"
                    authored["images"] = [record]
                elif mutation == "file-image-with-both-content-authorities":
                    record = _valid_dependency_image()
                    ambiguous_path = root / "ambiguous.png"
                    Image.new("RGBA", (4, 4), (1, 2, 3, 255)).save(ambiguous_path)
                    ambiguous_stat = ambiguous_path.stat()
                    record["source"] = "FILE"
                    record["filepath"] = str(ambiguous_path)
                    record["external_files"] = [
                        {
                            "path": str(ambiguous_path),
                            "resolved_path": str(ambiguous_path.resolve()),
                            "bytes": ambiguous_stat.st_size,
                            "mtime_ns": ambiguous_stat.st_mtime_ns,
                            "ctime_ns": ambiguous_stat.st_ctime_ns,
                            "device": ambiguous_stat.st_dev & 0xFFFFFFFF,
                            "inode": ambiguous_stat.st_ino,
                            "links": ambiguous_stat.st_nlink,
                            "sha256": sha256_file(ambiguous_path),
                        }
                    ]
                    record["packed_files"] = [
                        {
                            "index": 0,
                            "filepath": "",
                            "view": 0,
                            "tile_number": 1001,
                            "bytes": 1,
                            "sha256": "B" * 64,
                        }
                    ]
                    authored["images"] = [record]
                elif mutation == "generated-image-without-pixel-evidence":
                    record = _valid_dependency_image()
                    record["pixels"]["values"] = 0
                    authored["images"] = [record]
                elif mutation == "collection-path-leaf-mismatch":
                    authored["collection_tree"]["path"] = ["WRONG_COLLECTION"]
                elif mutation == "collection-child-path-mismatch":
                    authored["collection_tree"]["children"] = [
                        {
                            "identity": {
                                "name": "AUTHORED_CHILD",
                                "type": "Collection",
                                "library": None,
                            },
                            "path": ["Scene Collection", "WRONG_CHILD"],
                            "hide_render": False,
                            "hide_viewport": False,
                            "properties": {},
                            "objects": [],
                            "children": [],
                        }
                    ]
                elif mutation == "layer-path-leaf-mismatch":
                    authored["view_layers"][0]["layer_collection"]["path"] = [
                        "WRONG_COLLECTION"
                    ]
                elif mutation == "layer-child-path-mismatch":
                    authored["view_layers"][0]["layer_collection"]["children"] = [
                        {
                            "path": ["Scene Collection", "WRONG_CHILD"],
                            "collection": {
                                "name": "AUTHORED_CHILD",
                                "type": "Collection",
                                "library": None,
                            },
                            "exclude": False,
                            "holdout": False,
                            "indirect_only": False,
                            "hide_viewport": False,
                            "children": [],
                        }
                    ]
                elif mutation == "object-membership-path-spoof":
                    authored["objects"][0]["collections"][0]["path"] = [
                        "SPOOFED_ROOT",
                        "Scene Collection",
                    ]
                elif mutation == "unknown-material-reference":
                    record = _valid_dependency_object()
                    record["material_slots"] = [
                        {
                            "index": 0,
                            "name": "AUTHORED_UNKNOWN_MATERIAL",
                            "link": "DATA",
                            "material": {
                                "name": "AUTHORED_UNKNOWN_MATERIAL",
                                "type": "Material",
                                "library": None,
                                "pimm_material_id": "AUTHORED_UNKNOWN_MATERIAL",
                            },
                        }
                    ]
                    authored["objects"] = [
                        record,
                        _valid_camera_dependency_object(),
                    ]
                    authored["collection_tree"]["objects"] = [
                        record["identity"],
                        authored["camera"]["identity"],
                    ]
                elif mutation in {
                    "material-socket-wrong-pointer-type",
                    "material-socket-unknown-identity",
                    "material-socket-identity-null-kind",
                }:
                    material_identity: dict[str, object] = {
                        "name": "AUTHORED_SOCKET_MATERIAL",
                        "type": "Material",
                        "library": None,
                        "pimm_material_id": "AUTHORED_SOCKET_MATERIAL",
                    }
                    record = _valid_dependency_object()
                    record["modifiers"] = [
                        _valid_material_socket_modifier(material_identity)
                    ]
                    authored["objects"] = [
                        record,
                        _valid_camera_dependency_object(),
                    ]
                    authored["collection_tree"]["objects"] = [
                        record["identity"],
                        authored["camera"]["identity"],
                    ]
                    authored["materials"] = [
                        {
                            "identity": material_identity,
                            "properties": {},
                            "node_tree": None,
                        }
                    ]
                    socket_default = record["modifiers"][0]["node_group"]["nodes"][
                        0
                    ]["inputs"][0]["default"]
                    if mutation == "material-socket-wrong-pointer-type":
                        socket_default["value"] = {
                            "name": "AUTHORED_OBJECT",
                            "type": "Object",
                            "library": None,
                        }
                    elif mutation == "material-socket-unknown-identity":
                        socket_default["value"]["name"] = "UNKNOWN_SOCKET_MATERIAL"
                    else:
                        socket_default["value"] = None
                elif mutation == "unsafe-compositor-file-output":
                    unsafe_tree = _valid_compositor_node_tree(
                        "CompositorNodeOutputFile"
                    )
                    unsafe_tree["nodes"][0]["mute"] = True
                    unsafe_tree["nodes"][0]["properties"]["mute"] = True
                    authored["compositor"] = {
                        "enabled": True,
                        "node_tree": unsafe_tree,
                    }
                elif mutation == "render-layers-unknown-scene":
                    authored["compositor"] = {
                        "enabled": True,
                        "node_tree": _valid_compositor_node_tree(
                            "CompositorNodeRLayers", scene_name="UNKNOWN_SCENE"
                        ),
                    }
                elif mutation == "shared-material-id-name-swap":
                    record = _valid_dependency_material()
                    record["identity"] = {
                        "name": "PIMM_BLACK_POWDERCOAT",
                        "type": "Material",
                        "library": None,
                        "pimm_material_id": "DIE_CAST_ALUMINUM",
                    }
                    authored["materials"] = [record]
                if mutation != "inconsistent-digest":
                    _recompute_dependency_digest(authored)
                else:
                    authored["dependency_sha256"] = "F" * 64
                metadata["authored_settings"] = {
                    "before": authored,
                    "after": json.loads(json.dumps(authored)),
                }
                _write_manifest_evidence(root, output_root, contract, scene, metadata)

                expected_errors = {
                    "identity-null-dependency": "exact data-block identity",
                    "node-tree-null-dependency": "cannot be null",
                    "fake-node-tree-type": "supported Blender NodeTree",
                    "wrong-context-node-tree-type": "parent context",
                    "fake-modifier-enum": "pinned Blender modifier domain",
                    "fake-rna-enum": "pinned Blender enum domain",
                    "file-image-without-content-evidence": "exactly one",
                    "file-image-with-both-content-authorities": "exactly one",
                    "generated-image-without-pixel-evidence": "pixel values",
                    "collection-path-leaf-mismatch": "path leaf",
                    "collection-child-path-mismatch": "path leaf",
                    "layer-path-leaf-mismatch": "path leaf",
                    "layer-child-path-mismatch": "path leaf",
                    "object-membership-path-spoof": "does not resolve",
                    "unknown-material-reference": "captured registry",
                    "material-socket-wrong-pointer-type": "parent context",
                    "material-socket-unknown-identity": "captured registry",
                    "material-socket-identity-null-kind": "exact data-block identity",
                    "unsafe-compositor-file-output": "unsafe external writer",
                    "render-layers-unknown-scene": "current proof scene",
                    "shared-material-id-name-swap": "name/pimm_material_id mapping",
                }
                with patch.object(proof_module, "ASSET_ROOT", root):
                    with self.assertRaisesRegex(
                        ValueError, expected_errors.get(mutation, ".+")
                    ):
                        write_proof_manifest(contract, outputs)

    def test_standalone_finalizer_rejects_external_product_temp_and_preserves_it(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene = scene_contract_fixture()
            contract = material_contract(["white", "checker", "dark"], True)
            output_root = root / contract.output_root
            output_root.mkdir(parents=True)
            proof_path = output_root / "proof-contract.json"
            proof_path.write_text(
                json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
            )
            _write_scene_contract(root, scene, contract.scene_contract_path)
            (output_root / "scene-contract.json").write_text(
                json.dumps(scene.to_mapping(), sort_keys=True), encoding="utf-8"
            )
            rgba = output_root / f"{scene.scene_id}--rgba.png"
            Image.new("RGBA", (300, 300), (90, 110, 130, 255)).save(rgba)
            (output_root / "render-metadata.json").write_text(
                json.dumps(_valid_render_metadata(contract)), encoding="utf-8"
            )
            external = root / f".{scene.scene_id}--product-only.tmp.png"
            Image.new("RGBA", (300, 300), (90, 110, 130, 255)).save(external)
            before = sha256_file(external)

            with self.assertRaisesRegex(ValueError, "product-only temporary path"):
                render_module.finalize_proof(
                    proof_path, output_root, rgba, root, external
                )

            self.assertTrue(external.is_file())
            self.assertEqual(sha256_file(external), before)
            rgba_before = sha256_file(rgba)
            with self.assertRaisesRegex(ValueError, "product-only temporary path"):
                render_module.finalize_proof(proof_path, output_root, rgba, root, rgba)
            self.assertEqual(sha256_file(rgba), rgba_before)

            exact_hidden = output_root / f".{scene.scene_id}--product-only.tmp.png"
            os.link(external, exact_hidden)
            with self.assertRaisesRegex(ValueError, "product-only temporary path"):
                render_module.finalize_proof(
                    proof_path, output_root, rgba, root, exact_hidden
                )
            self.assertTrue(exact_hidden.is_file())
            self.assertEqual(sha256_file(external), before)
            self.assertFalse((output_root / "manifest.json").exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction mutation")
    def test_finalizer_rejects_generation_junction_without_deleting_external_target(self):
        with TemporaryDirectory() as root_text, TemporaryDirectory() as external_text:
            root = Path(root_text)
            external = Path(external_text)
            contract = material_contract(["white", "checker", "dark"], True)
            generation = root / contract.output_root
            generation.parent.mkdir(parents=True)
            subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", str(generation), str(external)],
                check=True,
                capture_output=True,
                text=True,
            )
            try:
                _, _, proof_path, rgba, product = _prepare_finalizer_fixture(
                    root, generation
                )
                external_product = external / product.name
                before = sha256_file(external_product)
                captured: ValueError | None = None
                try:
                    render_module.finalize_proof(
                        proof_path, generation, rgba, root, product
                    )
                except ValueError as error:
                    captured = error

                self.assertIsNotNone(captured)
                self.assertRegex(str(captured), "junction|reparse")
                self.assertTrue(external_product.is_file())
                self.assertEqual(sha256_file(external_product), before)
                for name in (
                    "manifest.json",
                    "contact-sheet.png",
                    "contact-sheet.json",
                    ".manifest.pending.json",
                    ".contact-sheet.pending.png",
                    ".contact-sheet.pending.json",
                ):
                    self.assertFalse((external / name).exists(), msg=name)
            finally:
                if generation.exists():
                    os.rmdir(generation)

    def test_product_scratch_replacement_race_is_preserved_and_fails_closed(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            contract = material_contract(["white", "checker", "dark"], True)
            output_root = root / contract.output_root
            _, _, proof_path, rgba, product = _prepare_finalizer_fixture(
                root, output_root
            )
            external = root / "external-readable.png"
            Image.new("RGBA", (300, 300), (12, 34, 56, 255)).save(external)
            external_before = sha256_file(external)
            original_product = root / "original-product-preserved.png"
            original_analyze = render_module.analyze_mask_metrics
            injected = False

            def replace_after_validation(image: object) -> dict[str, object]:
                nonlocal injected
                result = original_analyze(image)
                if not injected:
                    injected = True
                    os.replace(product, original_product)
                    shutil.copyfile(external, product)
                return result

            captured: ValueError | None = None
            with patch.object(
                render_module, "analyze_mask_metrics", replace_after_validation
            ):
                try:
                    render_module.finalize_proof(
                        proof_path, output_root, rgba, root, product
                    )
                except ValueError as error:
                    captured = error

            self.assertTrue(injected)
            self.assertIsNotNone(captured)
            self.assertRegex(str(captured), "replaced|identity|race")
            self.assertTrue(product.is_file())
            self.assertTrue(original_product.is_file())
            self.assertEqual(sha256_file(external), external_before)
            self.assertEqual(sha256_file(product), external_before)
            for name in (
                "manifest.json",
                "contact-sheet.png",
                "contact-sheet.json",
                ".manifest.pending.json",
                ".contact-sheet.pending.png",
                ".contact-sheet.pending.json",
            ):
                self.assertFalse((output_root / name).exists(), msg=name)

    def test_product_scratch_lexical_alias_is_rejected_and_preserved(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            contract = material_contract(["white", "checker", "dark"], True)
            output_root = root / contract.output_root
            _, _, proof_path, rgba, product = _prepare_finalizer_fixture(
                root, output_root
            )
            (output_root / "alias-component").mkdir()
            alias = output_root / "alias-component" / ".." / product.name
            before = sha256_file(product)

            with self.assertRaisesRegex(ValueError, "lexical|alias|canonical"):
                render_module.finalize_proof(
                    proof_path, output_root, rgba, root, alias
                )

            self.assertTrue(product.is_file())
            self.assertEqual(sha256_file(product), before)

    def test_canonical_mode_never_calls_fixture_setup_and_rejects_fixture_roles(self):
        clean_bpy = SimpleNamespace(data=SimpleNamespace(objects=[]))
        with patch.object(
            render_module,
            "_frame_fixture_scene",
            side_effect=AssertionError("fixture setup called"),
        ) as fixture_setup:
            self.assertEqual(
                render_module._prepare_render_environment(
                    clean_bpy, object(), fixture_mode=False
                ),
                ([], []),
            )
            fixture_setup.assert_not_called()

        fixture_object = SimpleNamespace(
            type="MESH",
            library=None,
            name="PIMM_ENV_SHADOW_CATCHER",
            get=lambda name, default=None: (
                "shadow-catcher"
                if name == "pimm_proof_environment_role"
                else default
            ),
        )
        dirty_bpy = SimpleNamespace(data=SimpleNamespace(objects=[fixture_object]))
        with self.assertRaisesRegex(ValueError, "fixture-only"):
            render_module._prepare_render_environment(
                dirty_bpy, object(), fixture_mode=False
            )

    def test_executing_blender_must_match_exact_locked_path_hash_and_version(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            locked_binary = root / "blender.exe"
            locked_binary.write_bytes(b"PINNED-BLENDER")
            lock = {
                "tools": [
                    {
                        "id": "blender",
                        "path": str(locked_binary),
                        "sha256": sha256_file(locked_binary),
                        "version": "5.2.0",
                    }
                ]
            }
            exact = SimpleNamespace(
                app=SimpleNamespace(
                    binary_path=str(locked_binary), version_string="5.2.0 LTS"
                )
            )
            self.assertEqual(
                render_module._validate_executing_blender(exact, lock),
                {
                    "binary_path": str(locked_binary.resolve()),
                    "binary_sha256": sha256_file(locked_binary),
                    "version": "5.2.0",
                },
            )

            other_binary = root / "other-blender.exe"
            other_binary.write_bytes(b"PINNED-BLENDER")
            mutations = {
                "path": SimpleNamespace(
                    app=SimpleNamespace(
                        binary_path=str(other_binary), version_string="5.2.0 LTS"
                    )
                ),
                "version": SimpleNamespace(
                    app=SimpleNamespace(
                        binary_path=str(locked_binary), version_string="5.1.0"
                    )
                ),
            }
            for name, fake_bpy in mutations.items():
                with self.subTest(name=name), self.assertRaises(ValueError):
                    render_module._validate_executing_blender(fake_bpy, lock)
            drifted_lock = json.loads(json.dumps(lock))
            drifted_lock["tools"][0]["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                render_module._validate_executing_blender(exact, drifted_lock)

    def test_manifest_and_contact_sheet_are_hash_verified_and_do_not_mutate_sources(self):
        contract = composition_contract()
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            output_root = root / contract.output_root
            output_root.mkdir(parents=True)
            outputs: list[Path] = []
            for background, color in {
                "rgba": (80, 120, 160, 255),
                "white": (255, 255, 255, 255),
                "checker": (192, 192, 192, 255),
                "dark": (24, 24, 24, 255),
            }.items():
                path = output_root / f"{scene_contract_fixture().scene_id}--{background}.png"
                Image.new("RGBA", (300, 300), color).save(path)
                outputs.append(path)
            _write_scene_contract(root, scene_contract_fixture(), contract.scene_contract_path)
            _write_manifest_evidence(
                root,
                output_root,
                contract,
                scene_contract_fixture(),
                _valid_render_metadata(
                    contract,
                    named_shaft_regions={
                        "SHAFT_FIXTURE": [0.25, 0.25, 0.75, 0.75]
                    },
                ),
            )
            before = {path: sha256_file(path) for path in outputs}
            with patch.object(proof_module, "ASSET_ROOT", root):
                manifest_path = write_proof_manifest(contract, outputs)
            sheet_path = build_contact_sheet(manifest_path, output_root / "contact-sheet.png")
            after = {path: sha256_file(path) for path in outputs}

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            evidence = json.loads((output_root / "contact-sheet.json").read_text(encoding="utf-8"))
            self.assertEqual(before, after)
            self.assertEqual([item["background"] for item in manifest["outputs"]], ["checker", "dark", "rgba", "white"])
            self.assertEqual(evidence["generation_id"], contract.generation_id)
            self.assertEqual(evidence["manifest_sha256"], sha256_file(manifest_path))
            self.assertEqual(evidence["contact_sheet_sha256"], sha256_file(sheet_path))
            self.assertEqual(evidence["header"]["stage"], contract.stage)
            self.assertIs(evidence["header"]["denoise"], True)
            self.assertEqual(len(evidence["cells"]), 4)
            self.assertTrue(
                manifest["qa"]["named_shaft_reflection"]["white"]["present"]
            )
            with Image.open(sheet_path) as sheet:
                self.assertGreater(sheet.width, 300)
                self.assertGreater(sheet.height, 300)

            manifest["outputs"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (output_root / "contact-sheet.json").unlink()
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                build_contact_sheet(manifest_path, output_root / "mutated-sheet.png")

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 runtime unavailable")
    def test_blender_52_allowlisted_nodes_all_capture_with_explicit_exclusions(self):
        with TemporaryDirectory() as root_text:
            result, payload = _run_allowlist_compatibility_audit(Path(root_text))

        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertTrue(payload, msg=result.stdout + result.stderr)
        expected = {
            f"{tree_type}:{node_type}"
            for tree_type, node_types in proof_module._NODE_TYPES_BY_TREE.items()
            for node_type in (
                set(node_types)
                | set(_BLENDER_52_UNSAFE_AUDIT_NODE_TYPES.get(tree_type, ()))
            )
        }
        self.assertEqual(
            payload["failures"],
            [],
            msg=json.dumps(payload["failures"], indent=2, sort_keys=True),
        )
        observed = set(payload["passed"]) | {
            entry["key"] for entry in payload["excluded"]
        }
        self.assertEqual(observed, expected)
        self.assertEqual(
            {entry["key"] for entry in payload["excluded"]},
            set(_BLENDER_52_ALLOWLIST_INSTANTIATION_EXCLUSIONS),
        )
        self.assertNotIn(
            "CompositorNodeOutputFile",
            proof_module._NODE_TYPES_BY_TREE["CompositorNodeTree"],
        )
        self.assertIn(
            "ShaderNodeMixRGB",
            proof_module._NODE_TYPES_BY_TREE["ShaderNodeTree"],
        )
        self.assertIn(
            "ShaderNodeUVMap",
            proof_module._NODE_TYPES_BY_TREE["ShaderNodeTree"],
        )
        self.assertEqual(
            proof_module._UNSAFE_NODE_TYPES_BY_TREE,
            _BLENDER_52_UNSAFE_AUDIT_NODE_TYPES,
        )

    def test_approved_procedural_material_dependencies_are_allowlisted(self):
        self.assertTrue(
            {
                "ShaderNodeBump",
                "ShaderNodeMapping",
                "ShaderNodeTexEnvironment",
                "ShaderNodeTexCoord",
                "ShaderNodeTexNoise",
                "ShaderNodeTexWave",
                "ShaderNodeValToRGB",
            }.issubset(proof_module._NODE_TYPES_BY_TREE["ShaderNodeTree"])
        )
        self.assertEqual(
            proof_module._NODE_EXTRA_PROPERTY_FIELDS["ShaderNodeTexNoise"],
            frozenset({"noise_dimensions", "noise_type", "normalize"}),
        )
        self.assertEqual(
            proof_module._NODE_EXTRA_PROPERTY_FIELDS["ShaderNodeMapping"],
            frozenset({"vector_type"}),
        )
        self.assertIn("NodeSocketVectorEuler", proof_module._NODE_SOCKET_TYPES)

    def test_mapping_euler_socket_default_is_captured_as_three_numbers(self):
        class EulerDefault:
            def __getitem__(self, index):
                values = (0.0, 0.0, 0.0)
                if index >= len(values):
                    raise IndexError
                return values[index]

        socket = SimpleNamespace(
            bl_idname="NodeSocketVectorEuler",
            name="Rotation",
            identifier="Rotation",
            default_value=EulerDefault(),
            enabled=True,
            is_linked=False,
        )

        self.assertEqual(render_module._socket_record(socket)["default"], [0.0, 0.0, 0.0])
        self.assertEqual(
            proof_module._NODE_STATIC_TYPES["ShaderNodeTexNoise"],
            "TEX_NOISE",
        )
        self.assertEqual(
            proof_module._NODE_STATIC_TYPES["ShaderNodeValToRGB"],
            "VALTORGB",
        )
        self.assertTrue(hasattr(render_module, "_embedded_rna_fingerprint"))

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 runtime unavailable")
    def test_color_ramp_mutation_changes_captured_dependency(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            result_path = root / "ramp-fingerprints.json"
            script_path = root / "capture_ramp.py"
            script_path.write_text(
                "\n".join(
                    [
                        "import bpy, json, sys",
                        f"sys.path.insert(0, {str(REPO_ROOT)!r})",
                        "import scripts.blender.pimm_production.blender_proof_render as render",
                        "material = bpy.data.materials.new('RAMP_TEST')",
                        "material.use_nodes = True",
                        "node = material.node_tree.nodes.new('ShaderNodeValToRGB')",
                        "before = render._node_tree_record(material.node_tree, image_cache={})",
                        "node.color_ramp.elements[0].position = 0.125",
                        "after = render._node_tree_record(material.node_tree, image_cache={})",
                        f"open({str(result_path)!r}, 'w', encoding='utf-8').write(json.dumps({{'before': before, 'after': after}}, sort_keys=True))",
                    ]
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(BLENDER), "--factory-startup", "-b", "-P", str(script_path)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertNotEqual(payload["before"], payload["after"])

    @unittest.skipUnless(BLENDER.is_file(), "Blender 5.2 runtime unavailable")
    def test_material_node_tree_identity_is_scoped_to_its_owner(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            result_path = root / "tree-identities.json"
            script_path = root / "capture_tree_identities.py"
            script_path.write_text(
                "\n".join(
                    [
                        "import bpy, json, sys",
                        f"sys.path.insert(0, {str(REPO_ROOT)!r})",
                        "import scripts.blender.pimm_production.blender_proof_render as render",
                        "materials = [bpy.data.materials.new(name) for name in ('ONE', 'TWO')]",
                        "for index, material in enumerate(materials):",
                        "    material.use_nodes = True",
                        "    material['pimm_material_id'] = f'TEST_{index}'",
                        "records = [render._material_record(material, {}) for material in materials]",
                        f"open({str(result_path)!r}, 'w', encoding='utf-8').write(json.dumps([record['node_tree']['identity'] for record in records], sort_keys=True))",
                    ]
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [str(BLENDER), "--factory-startup", "-b", "-P", str(script_path)],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            identities = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertNotEqual(identities[0], identities[1])

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_blender_52_file_output_is_blocked_before_render_and_writes_nothing(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, contract, proof_path = _write_real_fixture_proof(
                root, "unsafe-file-output"
            )

            result, rows = _run_fixture_proofs(
                scene_path,
                [proof_path],
                root,
                inject_compositor_file_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(rows), 1, msg=result.stdout + result.stderr)
            self.assertEqual(rows[0]["status"], "failed")
            self.assertRegex(" ".join(rows[0]["errors"]), "unsafe external writer")
            external_files = [
                path
                for path in (root / "unsafe-compositor-output").rglob("*")
                if path.is_file()
            ]
            self.assertEqual(external_files, [])
            output_root = root / contract.output_root
            for name in (
                f"{scene_contract_fixture().scene_id}--rgba.png",
                "render-metadata.json",
                "manifest.json",
                "contact-sheet.png",
                "contact-sheet.json",
                ".manifest.pending.json",
                ".contact-sheet.pending.png",
                ".contact-sheet.pending.json",
            ):
                self.assertFalse((output_root / name).exists(), msg=name)

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_blender_52_render_layers_current_scene_capture_and_finalizer_succeed(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, _contract, proof_path = _write_real_fixture_proof(
                root, "current-scene-render-layers"
            )

            result, rows = _run_fixture_proofs(
                scene_path,
                [proof_path],
                root,
                inject_compositor_render_layers="current",
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout={result.stdout}\nstderr={result.stderr}",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "pass")
            capture = json.loads(
                (root / "compositor-capture.json").read_text(encoding="utf-8")
            )
            expected_scene = {"name": "Scene", "type": "Scene", "library": None}
            self.assertEqual(capture["scene_identity"], expected_scene)
            render_layers = next(
                node
                for node in capture["compositor"]["node_tree"]["nodes"]
                if node["type"] == "CompositorNodeRLayers"
            )
            self.assertEqual(render_layers["data"]["scene"], expected_scene)
            changed_scene = json.loads(json.dumps(capture))
            changed_scene["scene_identity"]["name"] = "SECOND_PROOF_SCENE"
            self.assertNotEqual(
                capture["dependency_sha256"],
                render_module._dependency_sha256(changed_scene),
            )

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_blender_52_render_layers_other_scene_is_blocked_before_publication(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, contract, proof_path = _write_real_fixture_proof(
                root, "other-scene-render-layers"
            )

            result, rows = _run_fixture_proofs(
                scene_path,
                [proof_path],
                root,
                inject_compositor_render_layers="second",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(rows), 1, msg=result.stdout + result.stderr)
            self.assertEqual(rows[0]["status"], "failed")
            self.assertRegex(" ".join(rows[0]["errors"]), "current proof scene")
            output_root = root / contract.output_root
            for name in (
                f"{scene_contract_fixture().scene_id}--rgba.png",
                "render-metadata.json",
                "manifest.json",
                "contact-sheet.png",
                "contact-sheet.json",
                ".manifest.pending.json",
                ".contact-sheet.pending.png",
                ".contact-sheet.pending.json",
            ):
                self.assertFalse((output_root / name).exists(), msg=name)

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_blender_52_minimal_geometry_nodes_capture_and_finalizer_succeed(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(
                root, scene, "scenes/fixtures/minimal-geometry-scene.json"
            )
            contract = dataclasses.replace(
                composition_contract(),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256=sha256_file(scene_path),
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
                resolution_percentage=12.5,
                samples=16,
            )
            proof_path = root / "scenes" / "fixtures" / "minimal-geometry-proof.json"
            proof_path.write_text(
                json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
            )

            result, rows = _run_fixture_proofs(
                scene_path,
                [proof_path],
                root,
                inject_minimal_geometry_nodes=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout={result.stdout}\nstderr={result.stderr}",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "pass")
            self.assertEqual(rows[0]["generation_id"], contract.generation_id)
            self.assertTrue(rows[0]["fingerprints_unchanged"])
            capture = json.loads(
                (root / "minimal-geometry-capture.json").read_text(encoding="utf-8")
            )
            modifier = next(
                modifier
                for obj in capture["objects"]
                for modifier in obj["modifiers"]
                if modifier["name"] == "MINIMAL_GEOMETRY_NODES"
            )
            self.assertEqual(
                [node["type"] for node in modifier["node_group"]["nodes"]],
                ["NodeGroupInput", "NodeGroupOutput", "GeometryNodeSetMaterial"],
            )
            set_material = next(
                node
                for node in modifier["node_group"]["nodes"]
                if node["type"] == "GeometryNodeSetMaterial"
            )
            material_socket = next(
                socket
                for socket in set_material["inputs"]
                if socket["type"] == "NodeSocketMaterial"
            )
            self.assertEqual(
                material_socket["default"], {"kind": "value", "value": None}
            )
            manifest = json.loads(
                (root / contract.output_root / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["status"], "pass")

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_blender_52_geometry_transform_capture_and_finalizer_succeed(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(
                root, scene, "scenes/fixtures/geometry-transform-scene.json"
            )
            contract = dataclasses.replace(
                composition_contract(),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256=sha256_file(scene_path),
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
                resolution_percentage=12.5,
                samples=16,
            )
            proof_path = root / "scenes" / "fixtures" / "geometry-transform-proof.json"
            proof_path.write_text(
                json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
            )

            result, rows = _run_fixture_proofs(
                scene_path,
                [proof_path],
                root,
                inject_geometry_transform=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout={result.stdout}\nstderr={result.stderr}",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "pass")
            capture = json.loads(
                (root / "minimal-geometry-capture.json").read_text(encoding="utf-8")
            )
            modifier = next(
                modifier
                for obj in capture["objects"]
                for modifier in obj["modifiers"]
                if modifier["name"] == "MINIMAL_GEOMETRY_NODES"
            )
            transform = next(
                node
                for node in modifier["node_group"]["nodes"]
                if node["type"] == "GeometryNodeTransform"
            )
            defaults = {
                socket["type"]: socket["default"] for socket in transform["inputs"]
            }
            self.assertEqual(defaults["NodeSocketVectorTranslation"], [0.0, 0.0, 0.0])
            self.assertEqual(defaults["NodeSocketVectorXYZ"], [1.0, 1.0, 1.0])

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_blender_52_material_socket_defaults_capture_stable_identities(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(
                root, scene, "scenes/fixtures/pointer-socket-scene.json"
            )
            contract = dataclasses.replace(
                composition_contract(),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256=sha256_file(scene_path),
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
                resolution_percentage=12.5,
                samples=16,
            )
            proof_path = root / "scenes" / "fixtures" / "pointer-socket-proof.json"
            proof_path.write_text(
                json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
            )

            result, rows = _run_fixture_proofs(
                scene_path,
                [proof_path],
                root,
                inject_pointer_socket_materials=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout={result.stdout}\nstderr={result.stderr}",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "pass")
            capture = json.loads(
                (root / "minimal-geometry-capture.json").read_text(encoding="utf-8")
            )
            modifier = next(
                modifier
                for obj in capture["objects"]
                for modifier in obj["modifiers"]
                if modifier["name"] == "MINIMAL_GEOMETRY_NODES"
            )
            nodes = {
                node["name"]: node for node in modifier["node_group"]["nodes"]
            }
            for suffix in ("A", "B"):
                material_socket = next(
                    socket
                    for socket in nodes[f"SET_MATERIAL_{suffix}"]["inputs"]
                    if socket["name"] == "Material"
                )
                self.assertIsNotNone(material_socket["default"])
                self.assertEqual(
                    material_socket["default"],
                    {
                        "kind": "identity",
                        "value": {
                            "name": f"SOCKET_MATERIAL_{suffix}",
                            "type": "Material",
                            "library": None,
                            "pimm_material_id": f"SOCKET_MATERIAL_{suffix}",
                        },
                    },
                )

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_material_socket_swap_changes_digest_and_blocks_final_publication(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(
                root, scene, "scenes/fixtures/pointer-swap-scene.json"
            )
            contract = dataclasses.replace(
                composition_contract(),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256=sha256_file(scene_path),
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
                resolution_percentage=12.5,
                samples=16,
            )
            proof_path = root / "scenes" / "fixtures" / "pointer-swap-proof.json"
            proof_path.write_text(
                json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
            )

            result, rows = _run_fixture_proofs(
                scene_path,
                [proof_path],
                root,
                inject_pointer_socket_swap=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(rows), 1, msg=result.stdout + result.stderr)
            self.assertEqual(
                rows[0]["status"],
                "blocked_settings_drift",
                msg=result.stdout + result.stderr,
            )
            before = json.loads(
                (root / "minimal-geometry-capture.json").read_text(encoding="utf-8")
            )
            after = json.loads(
                (root / "swapped-material-capture.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                [material["identity"] for material in before["materials"]],
                [material["identity"] for material in after["materials"]],
            )
            self.assertNotEqual(
                before["dependency_sha256"], after["dependency_sha256"]
            )
            output_root = root / contract.output_root
            for name in (
                "manifest.json",
                "contact-sheet.png",
                "contact-sheet.json",
                ".manifest.pending.json",
                ".contact-sheet.pending.png",
                ".contact-sheet.pending.json",
            ):
                self.assertFalse((output_root / name).exists(), msg=name)

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_fixture_composition_and_material_proofs_render_real_outputs_and_cleanup(self):
        root_path: Path | None = None
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            root_path = root
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(
                root, scene, "scenes/fixtures/pimm-30g--hero--three-quarter.json"
            )
            protected = [
                source_path,
                root / scene.master_path,
                root / scene.material_library_path,
                scene_path,
                scene_contract_path,
            ]
            before = {path: (path.stat().st_size, path.stat().st_mtime_ns, sha256_file(path)) for path in protected}

            contracts: list[ProofContract] = []
            for base, generation, samples in [
                (composition_contract(), "proof-20260815T153000Z-a1b2c3d", 16),
                (material_contract(["white", "checker", "dark"], True), "proof-20260815T153001Z-b2c3d4e", 32),
            ]:
                contract = dataclasses.replace(
                    base,
                    generation_id=generation,
                    scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                    scene_sha256=sha256_file(scene_path),
                    master_sha256=scene.master_sha256,
                    material_library_sha256=scene.material_library_sha256,
                    resolution_percentage=12.5 if base.stage == "composition" else 25,
                    samples=samples,
                    output_root=f"renders/proofs/{generation}",
                )
                proof_path = root / "scenes" / "fixtures" / f"{generation}.json"
                proof_path.write_text(json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8")
                contracts.append(contract)

                result, rows = _run_fixture_proofs(scene_path, [proof_path], root)
                self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["status"], "pass")

            after = {path: (path.stat().st_size, path.stat().st_mtime_ns, sha256_file(path)) for path in protected}
            self.assertEqual(before, after)

            for contract in contracts:
                output_root = root / contract.output_root
                expected = {"rgba", "white", "checker", "dark"}
                if contract.object_masks:
                    expected |= {"object-mask", "material-mask", "shadow-mask"}
                image_paths = sorted(output_root.glob("*.png"))
                backgrounds = {
                    path.stem.rsplit("--", 1)[-1]
                    for path in image_paths
                    if path.name != "contact-sheet.png"
                }
                self.assertEqual(backgrounds, expected)
                manifest_path = output_root / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "pass")
                self.assertEqual(manifest["render"]["engine"], "CYCLES")
                self.assertEqual(manifest["render"]["samples"], contract.samples)
                self.assertEqual(manifest["render"]["resolution_percentage"], contract.resolution_percentage)
                expected_dimension = 150 if contract.resolution_percentage == 12.5 else 300
                self.assertEqual(manifest["render"]["actual_dimensions"], [expected_dimension, expected_dimension])
                self.assertTrue(manifest["fingerprints_unchanged"])
                self.assertGreater(manifest["qa"]["subject"]["subject_pixel_fraction"], 0)
                self.assertIsNotNone(manifest["qa"]["subject"]["subject_bounds"])
                intended = manifest["qa"]["intended_subject"]["bounds"]
                self.assertGreater(intended["left"], 0)
                self.assertGreater(intended["top"], 0)
                self.assertLess(intended["right"], expected_dimension - 1)
                self.assertLess(intended["bottom"], expected_dimension - 1)
                self.assertTrue(manifest["render"]["shadow_pass_available"])
                self.assertGreater(
                    manifest["qa"]["physical_shadow_extent"]["nonzero_fraction"],
                    0,
                )
                if contract.object_masks:
                    self.assertIsNotNone(manifest["qa"]["intended_subject"]["bounds"])
                self.assertTrue((output_root / "contact-sheet.png").is_file())
                self.assertTrue((output_root / "contact-sheet.json").is_file())
                evidence = json.loads(
                    (output_root / "contact-sheet.json").read_text(encoding="utf-8")
                )
                self.assertEqual(evidence["header"]["stage"], contract.stage)
                self.assertEqual(evidence["header"]["denoise"], contract.denoise)
                for pending_name in render_module._PENDING_TO_PUBLISHED:
                    self.assertFalse((output_root / pending_name).exists())
                for entry in manifest["outputs"]:
                    path = output_root / entry["path"]
                    self.assertEqual(entry["sha256"], sha256_file(path))
                    self.assertIn("metrics", entry)

                rgba = output_root / f"{scene.scene_id}--rgba.png"
                with Image.open(rgba).convert("RGBA") as source:
                    for background in ("white", "checker", "dark"):
                        composite_path = (
                            output_root / f"{scene.scene_id}--{background}.png"
                        )
                        with Image.open(composite_path).convert("RGBA") as composite:
                            for source_pixel, composite_pixel in zip(
                                source.get_flattened_data(), composite.get_flattened_data()
                            ):
                                if source_pixel[3] == 255:
                                    self.assertEqual(source_pixel[:3], composite_pixel[:3])

        self.assertIsNotNone(root_path)
        self.assertFalse(root_path.exists())

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_scene_hash_failure_stops_batch_before_any_generation_output(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(root, scene, "scenes/fixtures/scene.json")
            first = dataclasses.replace(
                composition_contract(),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256="0" * 64,
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
            )
            second = dataclasses.replace(
                material_contract(["white", "checker", "dark"], True),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256=sha256_file(scene_path),
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
            )
            proof_paths = []
            for contract in (first, second):
                path = root / "scenes" / "fixtures" / f"{contract.generation_id}.json"
                path.write_text(json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8")
                proof_paths.append(path)

            result, rows = _run_fixture_proofs(scene_path, proof_paths, root)

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "blocked_scene_drift")
            self.assertFalse((root / first.output_root).exists())
            self.assertFalse((root / second.output_root).exists())

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_injected_drift_after_prepare_publishes_no_pass_artifacts(self):
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path, scene = build_scene_fixture("valid", root)
            source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
            scene_contract_path = _write_scene_contract(
                root, scene, "scenes/fixtures/scene.json"
            )
            contract = dataclasses.replace(
                composition_contract(),
                scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                scene_sha256=sha256_file(scene_path),
                master_sha256=scene.master_sha256,
                material_library_sha256=scene.material_library_sha256,
                resolution_percentage=12.5,
                samples=16,
            )
            proof_path = root / "scenes" / "fixtures" / "drift-proof.json"
            proof_path.write_text(
                json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
            )

            result, rows = _run_fixture_proofs(
                scene_path,
                [proof_path],
                root,
                inject_drift_after_prepare=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(rows), 1, msg=result.stdout + result.stderr)
            self.assertEqual(rows[0]["status"], "blocked_fingerprint_drift")
            output_root = root / contract.output_root
            for name in (
                "manifest.json",
                "contact-sheet.png",
                "contact-sheet.json",
                ".manifest.pending.json",
                ".contact-sheet.pending.png",
                ".contact-sheet.pending.json",
            ):
                self.assertFalse((output_root / name).exists(), msg=name)

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_authored_render_state_mutations_at_final_gate_publish_no_pass_artifacts(self):
        for mutation in ("camera", "light", "world", "compositor"):
            with self.subTest(mutation=mutation), TemporaryDirectory() as root_text:
                root = Path(root_text)
                scene_path, scene = build_scene_fixture("valid", root)
                source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
                source_path.parent.mkdir(parents=True)
                source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
                scene_contract_path = _write_scene_contract(
                    root, scene, "scenes/fixtures/scene.json"
                )
                contract = dataclasses.replace(
                    composition_contract(),
                    scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                    scene_sha256=sha256_file(scene_path),
                    master_sha256=scene.master_sha256,
                    material_library_sha256=scene.material_library_sha256,
                    resolution_percentage=12.5,
                    samples=16,
                )
                proof_path = root / "scenes" / "fixtures" / f"{mutation}-proof.json"
                proof_path.write_text(
                    json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
                )

                result, rows = _run_fixture_proofs(
                    scene_path,
                    [proof_path],
                    root,
                    inject_authored_mutation=mutation,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(rows), 1, msg=result.stdout + result.stderr)
                self.assertEqual(
                    rows[0]["status"],
                    "blocked_settings_drift",
                    msg=result.stdout + result.stderr,
                )
                output_root = root / contract.output_root
                for name in (
                    "manifest.json",
                    "contact-sheet.png",
                    "contact-sheet.json",
                    ".manifest.pending.json",
                    ".contact-sheet.pending.png",
                    ".contact-sheet.pending.json",
                ):
                    self.assertFalse((output_root / name).exists(), msg=name)

    @unittest.skipUnless(BLENDER.is_file() and TOOL_LOCK.is_file(), "fixture proof runtime unavailable")
    def test_render_dependency_mutations_at_final_gate_publish_no_pass_artifacts(self):
        mutations = (
            "object_visibility",
            "geometry",
            "material_scalar",
            "material_node",
            "material_assignment",
            "external_image",
            "packed_image",
            "dof",
            "collection_hide_render",
            "layer_collection_exclude",
            "layer_collection_holdout",
            "layer_collection_indirect_only",
            "collection_membership",
            "gn_modifier_id_property",
            "gn_modifier_pointer",
            "gn_node",
            "gn_node_default",
            "gn_node_link",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), TemporaryDirectory() as root_text:
                root = Path(root_text)
                external_path = root / "fixture-external.png"
                replacement_path = root / "fixture-external-replacement.png"
                Image.new("RGBA", (4, 4), (10, 20, 30, 255)).save(external_path)
                Image.new("RGBA", (4, 4), (210, 120, 30, 255)).save(replacement_path)
                external_before = external_path.read_bytes()
                scene_path, scene = build_scene_fixture("valid", root)
                source_path = root / "sources" / "PIMM-30G-authoritative-source.step"
                source_path.parent.mkdir(parents=True)
                source_path.write_bytes(b"TASK-5-FIXTURE-SOURCE\n")
                scene_contract_path = _write_scene_contract(
                    root, scene, "scenes/fixtures/dependency-scene.json"
                )
                contract = dataclasses.replace(
                    composition_contract(),
                    scene_contract_path=scene_contract_path.relative_to(root).as_posix(),
                    scene_sha256=sha256_file(scene_path),
                    master_sha256=scene.master_sha256,
                    material_library_sha256=scene.material_library_sha256,
                    resolution_percentage=12.5,
                    samples=16,
                )
                proof_path = root / "scenes" / "fixtures" / f"{mutation}-proof.json"
                proof_path.write_text(
                    json.dumps(contract.to_mapping(), sort_keys=True), encoding="utf-8"
                )

                result, rows = _run_fixture_proofs(
                    scene_path,
                    [proof_path],
                    root,
                    inject_dependency_mutation=mutation,
                )
                if mutation == "external_image":
                    self.assertNotEqual(external_path.read_bytes(), external_before)
                    external_path.write_bytes(external_before)
                    self.assertEqual(external_path.read_bytes(), external_before)

                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(len(rows), 1, msg=result.stdout + result.stderr)
                self.assertEqual(
                    rows[0]["status"],
                    "blocked_settings_drift",
                    msg=result.stdout + result.stderr,
                )
                output_root = root / contract.output_root
                for name in (
                    "manifest.json",
                    "contact-sheet.png",
                    "contact-sheet.json",
                    ".manifest.pending.json",
                    ".contact-sheet.pending.png",
                    ".contact-sheet.pending.json",
                ):
                    self.assertFalse((output_root / name).exists(), msg=name)


if __name__ == "__main__":
    unittest.main()
