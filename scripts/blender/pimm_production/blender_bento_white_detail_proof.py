"""Immutable configuration-only lighting proof; never publish preview pixels."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_white_final import white_contract
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
from scripts.blender.pimm_production import blender_master_storefront_render as studio

GENERATION = 'bento-20260903-r12-white-detail'
EXPOSURE = .3
HDRI_STRENGTH = .45
REFLECTOR_STRENGTH = .35


def main():
    import bpy
    from mathutils import Vector
    source = white_contract('configuration')
    scene_path = require_within(ASSET_ROOT / f'scenes/stills/pimm-30g--{GENERATION}--configuration.blend', ASSET_ROOT)
    proof_dir = require_within(ASSET_ROOT / f'renders/proofs/{GENERATION}', ASSET_ROOT)
    receipt_path = require_within(ASSET_ROOT / f'scenes/contracts/pimm-30g--{GENERATION}--configuration.json', ASSET_ROOT)
    if any(path.exists() for path in (scene_path, proof_dir, receipt_path)):
        raise FileExistsError('Lighting proof generation is immutable')
    bpy.ops.wm.open_mainfile(filepath=source['scene_path'])
    scene = bpy.context.scene
    meshes = [obj for obj in bpy.data.collections['PIMM_PUBLISHED'].all_objects if obj.type == 'MESH']
    assert len(meshes) == studio.EXPECTED_OBJECT_COUNT
    assert all(obj.library and obj.data.library and not obj.override_library and not obj.animation_data for obj in meshes)
    feet = [obj for obj in meshes if '__nylon-feet__' in obj.name.lower()]
    levels = [min((obj.matrix_world @ Vector(c)).z for c in obj.bound_box) for obj in feet]
    assert len(levels) == 4 and max(abs(z) for z in levels) <= studio.FOOT_TOLERANCE
    original = {'exposure': scene.view_settings.exposure,
                'hdri_strength': scene.world.node_tree.nodes['PIMM_HDRI_LIGHTING'].inputs['Strength'].default_value}
    camera_matrix = [list(row) for row in scene.camera.matrix_world]
    assert not scene.world.library
    scene.view_settings.exposure = EXPOSURE
    scene.world.node_tree.nodes['PIMM_HDRI_LIGHTING'].inputs['Strength'].default_value = HDRI_STRENGTH
    card = bpy.data.objects['REFLECTION_WALL_CAMERA']
    material = card.data.materials[0]
    assert not card.library and not material.library
    emission = next(node for node in material.node_tree.nodes if node.type == 'EMISSION')
    original['camera_reflector_strength'] = emission.inputs['Strength'].default_value
    emission.inputs['Strength'].default_value = REFLECTOR_STRENGTH
    assert scene.render.resolution_percentage == 100 and scene.cycles.samples == 128
    assert [scene.render.resolution_x, scene.render.resolution_y] == [2400, 1200]
    proof_dir.mkdir(parents=True)
    scene.render.filepath = str(proof_dir / 'configuration.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
    scene_hash = sha256_file(scene_path)
    bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    scene = bpy.context.scene
    assert [list(row) for row in scene.camera.matrix_world] == camera_matrix
    assert all(obj.library for obj in bpy.data.collections['PIMM_PUBLISHED'].all_objects)
    assert abs(scene.view_settings.exposure - EXPOSURE) < .0001
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.refresh_devices()
    preferences.compute_device_type = 'OPTIX'
    for device in preferences.devices:
        device.use = device.type == 'OPTIX'
    scene.render.resolution_percentage = 25
    scene.cycles.samples = 64
    bpy.ops.render.render(write_still=True)
    white_contract('configuration')
    checked_file(source['scene_path'], source['scene_sha256'])
    receipt = {**source, 'generation': GENERATION, 'approval': 'pending',
               'scene_path': str(scene_path), 'scene_sha256': scene_hash,
               'source_scene_sha256': source['scene_sha256'], 'script_sha256': sha256_file(Path(__file__)),
               'scope': 'Configuration-only lower exposure and studio fill; white floor, product and camera unchanged',
               'previous_lighting': original,
               'lighting': {'exposure': EXPOSURE, 'hdri_strength': HDRI_STRENGTH, 'camera_reflector_strength': REFLECTOR_STRENGTH},
               'foot_levels': levels, 'proof_percentage': 25, 'proof_samples': 64,
               'proofs': [{'path': scene.render.filepath, 'sha256': sha256_file(Path(scene.render.filepath))}]}
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    print('WHITE_DETAIL_PROOF_READY=' + str(receipt_path), flush=True)


if __name__ == '__main__':
    main()
    os._exit(0)
