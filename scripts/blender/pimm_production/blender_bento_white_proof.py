"""Proof a white physical studio for the configuration tile only."""
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_r10_final import contract_for
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within


def main():
    import bpy
    source = contract_for('configuration')
    generation = 'bento-20260903-r11-white'
    scene_path = require_within(ASSET_ROOT / f'scenes/stills/pimm-30g--{generation}--configuration.blend', ASSET_ROOT)
    proof_dir = require_within(ASSET_ROOT / f'renders/proofs/{generation}', ASSET_ROOT)
    receipt_path = require_within(ASSET_ROOT / f'scenes/contracts/pimm-30g--{generation}--configuration.json', ASSET_ROOT)
    if scene_path.exists() or proof_dir.exists() or receipt_path.exists():
        raise FileExistsError('White proof generation is immutable')
    bpy.ops.wm.open_mainfile(filepath=source['scene_path'])
    scene = bpy.context.scene
    floor = bpy.data.objects['BENTO_INFINITE_GROUND']
    assert not floor.library and not floor.data.library
    material = floor.data.materials[0]
    assert not material.library
    shader = next(node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = (.98, .98, .98, 1)
    receivers = bpy.data.collections.new('WHITE_STUDIO_GROUND_RECEIVER')
    scene.collection.children.link(receivers)
    receivers.objects.link(floor)
    light = bpy.data.lights.new('WHITE_STUDIO_GROUND_WASH', 'SUN')
    light.energy = 5
    light.angle = math.radians(25)
    lamp = bpy.data.objects.new('WHITE_STUDIO_GROUND_WASH', light)
    scene.collection.objects.link(lamp)
    lamp.rotation_euler = (math.radians(18), math.radians(-25), math.radians(-20))
    lamp.light_linking.receiver_collection = receivers
    product = bpy.data.collections['PIMM_PUBLISHED']
    assert all(obj.library and not obj.animation_data for obj in product.all_objects)
    proof_dir.mkdir(parents=True)
    scene.render.filepath = str(proof_dir / 'configuration.png')
    assert scene.render.resolution_percentage == 100 and scene.cycles.samples == 128
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
    scene_hash = sha256_file(scene_path)
    bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    assert all(obj.library for obj in bpy.data.collections['PIMM_PUBLISHED'].all_objects)
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.refresh_devices()
    preferences.compute_device_type = 'OPTIX'
    for device in preferences.devices:
        device.use = device.type == 'OPTIX'
    scene = bpy.context.scene
    scene.render.resolution_percentage = 25
    scene.cycles.samples = 32
    bpy.ops.render.render(write_still=True)
    checked_file(source['scene_path'], source['scene_sha256'])
    receipt = {**source, 'generation': generation, 'approval': 'pending', 'scene_path': str(scene_path),
               'scene_sha256': scene_hash, 'source_scene_sha256': source['scene_sha256'],
               'script_sha256': sha256_file(Path(__file__)),
               'scope': 'Configuration-only white ground with physical ground-linked studio wash; unchanged product and camera',
               'proofs': [{'path': scene.render.filepath, 'sha256': sha256_file(Path(scene.render.filepath))}]}
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    print('WHITE_STUDIO_PROOF_READY=' + str(receipt_path), flush=True)


if __name__ == '__main__':
    main()
    os._exit(0)
