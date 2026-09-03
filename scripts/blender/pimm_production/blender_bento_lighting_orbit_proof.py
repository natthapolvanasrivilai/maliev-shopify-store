"""Proof-only lighting revision and camera-only orbit of approved bento scenes."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production import blender_master_storefront_render as studio
from scripts.blender.pimm_production.blender_bento_final import checked_file, approved_contract
from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
from scripts.blender.pimm_production.tool_policy import LOCK_PATH, validate_tool_lock

FPS = 24
FRAMES = 192
AMPLITUDE_DEGREES = 3.0


def orbit_angle(frame):
    return math.radians(AMPLITUDE_DEGREES) * math.sin(2 * math.pi * (frame - 1) / FRAMES)


def render(shot, generation, animate=False):
    import bpy
    from mathutils import Matrix, Vector

    if animate and shot != 'controls':
        raise ValueError('Only the controls camera is authorized to orbit')
    errors = validate_tool_lock(json.loads(LOCK_PATH.read_text(encoding='utf-8')))
    if errors:
        raise ValueError(errors)
    approval_path = Path(__file__).resolve().parents[3] / 'docs/pimm-blender-governance/bento-20260903-r06-approval.json'
    approval = json.loads(approval_path.read_text(encoding='utf-8'))
    entry = next(item for item in approval['shots'] if item['shot'] == shot)
    source_path = checked_file(Path(entry['contract_path']), entry['contract_sha256'])
    source = approved_contract(shot)
    master = checked_file(ASSET_ROOT / 'masters/PIMM-30G-MASTER.blend', source['master_sha256'])
    library = checked_file(ASSET_ROOT / 'masters/PIMM-MATERIAL-LIBRARY.blend', source['material_library_sha256'])
    checked_file(LOCK_PATH, source['tool_lock_sha256'])
    checked_file(Path(source['scene_path']), source['scene_sha256'])
    stem = f'pimm-30g--bento-{generation}--{shot}'
    scene_path = require_within(ASSET_ROOT / ('scenes/animations' if animate else 'scenes/stills') / f'{stem}.blend', ASSET_ROOT)
    proof_dir = require_within(ASSET_ROOT / 'renders/proofs' / generation / shot, ASSET_ROOT)
    contract_path = require_within(ASSET_ROOT / 'scenes/contracts' / f'{stem}.json', ASSET_ROOT)
    if scene_path.exists() or proof_dir.exists() or contract_path.exists():
        raise FileExistsError('Proof generations are immutable; choose a new generation')
    proof_dir.mkdir(parents=True)
    scene_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=source['scene_path'])
    scene = bpy.context.scene
    published = bpy.data.collections['PIMM_PUBLISHED']
    meshes = [obj for obj in published.all_objects if obj.type == 'MESH']
    assert len(meshes) == studio.EXPECTED_OBJECT_COUNT
    assert all(obj.library and obj.data.library and not obj.override_library for obj in meshes)
    low, high = studio._world_bounds(meshes)
    feet = [obj for obj in meshes if '__nylon-feet__' in obj.name.lower()]
    levels = [min((obj.matrix_world @ Vector(c)).z for c in obj.bound_box) for obj in feet]
    assert len(levels) == 4 and max(abs(z) for z in levels) <= studio.FOOT_TOLERANCE

    # Only scene-local studio light sources change. Published finishes stay linked.
    scene.view_settings.look = 'AgX - High Contrast'
    scene.view_settings.exposure = 1.1
    scene.world.node_tree.nodes['PIMM_HDRI_LIGHTING'].inputs['Strength'].default_value = .65
    for name, energy in [('KEY_SOFTBOX', 180), ('FILL_SOFTBOX', 6), ('BACKGROUND_WASH', 1600)]:
        light = bpy.data.objects[name]
        assert not light.library and not light.data.library
        light.data.energy = energy
    card = bpy.data.objects['REFLECTION_WALL_CAMERA']
    material = card.data.materials[0]
    assert not material.library
    emission = next(node for node in material.node_tree.nodes if node.type == 'EMISSION')
    emission.inputs['Strength'].default_value = .65

    camera = scene.camera
    assert camera.type == 'CAMERA' and not camera.library and not camera.animation_data
    if animate:
        pivot = Vector(((low[0]+high[0])/2, (low[1]+high[1])/2, low[2]+(high[2]-low[2])*.665))
        original = camera.matrix_world.copy()
        for frame in range(1, FRAMES+2):
            rotation = Matrix.Rotation(orbit_angle(frame), 4, 'Z')
            camera.matrix_world = Matrix.Translation(pivot) @ rotation @ Matrix.Translation(-pivot) @ original
            camera.keyframe_insert(data_path='location', frame=frame)
            camera.keyframe_insert(data_path='rotation_euler', frame=frame)
        scene.frame_start, scene.frame_end = 1, FRAMES
        scene.render.fps = FPS
        scene.render.fps_base = 1
    scene.frame_set(1)
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(proof_dir / 'frame-')
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
    scene_hash = studio.sha256_file(scene_path)
    bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    scene = bpy.context.scene
    assert all(obj.library and obj.data.library for obj in bpy.data.collections['PIMM_PUBLISHED'].all_objects if obj.type == 'MESH')
    assert all(not obj.animation_data for obj in bpy.data.collections['PIMM_PUBLISHED'].all_objects)
    # Device preferences are process-local, not scene state.
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.refresh_devices()
    backend = 'OPTIX' if any(d.type == 'OPTIX' for d in preferences.devices) else 'CUDA'
    preferences.compute_device_type = backend
    for device in preferences.devices:
        device.use = device.type == backend
    contract = dict(source, generation=generation, scene_path=str(scene_path), scene_sha256=scene_hash,
                    source_contract_sha256=entry['contract_sha256'], source_approval_sha256=studio.sha256_file(approval_path),
                    script_sha256=studio.sha256_file(Path(__file__)), approval='pending',
                    proof_percentage=25, proof_samples=32, proof_path=str(proof_dir),
                    lighting={'look':'AgX - High Contrast','exposure':1.1,'hdri_strength':.65,'key_watts':180,'fill_watts':6,'background_watts':1600,'camera_reflector_strength':.65},
                    motion={'type':'camera-only' if animate else 'static','fps':FPS,'frames':FRAMES if animate else 1,
                            'orbit_degrees':AMPLITUDE_DEGREES if animate else 0,'machine_motion':False,'controller_values':'unchanged 300/300'},
                    foot_levels=levels)
    contract.pop('proof_sha256', None)
    contract_path.write_text(json.dumps(contract, indent=2)+'\n', encoding='utf-8')
    scene.render.resolution_percentage = 25
    scene.cycles.samples = 32
    scene.cycles.adaptive_threshold = .03
    if animate:
        bpy.ops.render.render(animation=True)
    else:
        scene.render.filepath = str(proof_dir / 'still.png')
        bpy.ops.render.render(write_still=True)
    contract['proofs'] = [{'path':str(path),'sha256':studio.sha256_file(path)} for path in sorted(proof_dir.glob('*.png'))]
    assert len(contract['proofs']) == (FRAMES if animate else 1)
    checked_file(master, source['master_sha256'])
    checked_file(library, source['material_library_sha256'])
    contract_path.write_text(json.dumps(contract, indent=2)+'\n', encoding='utf-8')
    print('BENTO_LIGHTING_PROOF_READY='+str(contract_path), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shot', choices=['capacity','controls','tooling','configuration'], required=True)
    parser.add_argument('--generation', required=True)
    parser.add_argument('--animate', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    render(args.shot, args.generation, args.animate)
    os._exit(0)
