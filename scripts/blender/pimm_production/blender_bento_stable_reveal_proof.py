"""Rerender the approved tube reveal without Cycles' cross-frame render cache."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.blender_bento_r10_final import contract_for
from scripts.blender.pimm_production.blender_bento_tube_reveal_proof import FRAMES, TARGETS
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT

GENERATION = 'bento-20260903-r21-stable-tube-reveal'
SOURCE_GENERATION = 'bento-20260903-r17-tube-reveal'


def stabilize(scene):
    # With three composited view layers, persistent data intermittently reuses
    # invalid face shading after frame_set(). Fresh scene data removes the flashes.
    scene.render.use_persistent_data = False


def verify_product(published, original):
    meshes = {obj.name: obj for obj in published.all_objects if obj.type == 'MESH'}
    assert set(meshes) == set(original) and len(meshes) == 556
    for name, obj in meshes.items():
        before = original[name]
        assert obj.library and obj.data.library and not obj.override_library and not obj.animation_data
        assert before['mesh'] == obj.data.name
        assert before['materials'] == [material.name for material in obj.data.materials]
        assert before['matrix'] == [list(row) for row in obj.matrix_world]


def render(selected=None):
    import bpy
    selected = list(selected or range(1, FRAMES + 1))
    if len(set(selected)) != len(selected) or any(not 1 <= frame <= FRAMES for frame in selected):
        raise ValueError('Expected unique frames within the approved loop')
    authority = contract_for('capacity')
    source_path = ASSET_ROOT / 'scenes/contracts' / f'pimm-30g--{SOURCE_GENERATION}--capacity.json'
    source_hash = sha256_file(source_path)
    source = json.loads(source_path.read_text())
    checked_file(source['scene_path'], source['scene_sha256'])
    checked_file(Path(__file__).with_name('blender_bento_tube_reveal_proof.py'), source['script_sha256'])
    assert source['source_scene_sha256'] == authority['scene_sha256']
    assert source['focus_objects'] == list(TARGETS) and source['ghost_opacity'] == .2
    root = ASSET_ROOT / 'renders/proofs' / GENERATION
    scene_path = ASSET_ROOT / 'scenes/animations' / f'pimm-30g--{GENERATION}--capacity.blend'
    contract_path = ASSET_ROOT / 'scenes/contracts' / f'pimm-30g--{GENERATION}--capacity.json'
    if contract_path.exists():
        contract = json.loads(contract_path.read_text())
        checked_file(scene_path, contract['scene_sha256'])
        checked_file(Path(__file__), contract['script_sha256'])
        assert contract['source_animation_contract_sha256'] == source_hash
    else:
        if root.exists() or scene_path.exists():
            raise FileExistsError('Immutable proof generation exists')
        bpy.ops.wm.open_mainfile(filepath=source['scene_path'])
        scene = bpy.context.scene
        verify_product(bpy.data.collections['PIMM_PUBLISHED'], source['original_product'])
        stabilize(scene)
        scene.frame_set(1)
        scene.render.filepath = str(root / 'frame-')
        assert scene.render.resolution_percentage == 100 and scene.cycles.samples == 128
        root.mkdir(parents=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
        contract = dict(source, generation=GENERATION, approval='pending',
                        scene_path=str(scene_path), scene_sha256=sha256_file(scene_path),
                        script_sha256=sha256_file(Path(__file__)), proofs=[],
                        source_animation_contract_path=str(source_path),
                        source_animation_contract_sha256=source_hash,
                        source_animation_scene_sha256=source['scene_sha256'],
                        render_stability={'persistent_data': False,
                                          'reason': 'Prevent intermittent black faces between composited frames'})
        contract_path.write_text(json.dumps(contract, indent=2) + '\n')
    bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    scene = bpy.context.scene
    assert scene.render.use_persistent_data is False
    verify_product(bpy.data.collections['PIMM_PUBLISHED'], contract['original_product'])
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.refresh_devices()
    preferences.compute_device_type = 'OPTIX'
    for device in preferences.devices:
        device.use = device.type == 'OPTIX'
    scene.render.resolution_percentage = contract['proof_percentage']
    scene.cycles.samples = contract['proof_samples']
    records = {record['frame']: record for record in contract['proofs']}
    for frame in selected:
        path = root / f'frame-{frame:04d}.png'
        if frame in records:
            checked_file(path, records[frame]['sha256'])
            continue
        if path.exists():
            raise FileExistsError('Unreceipted proof frame')
        scene.frame_set(frame)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        records[frame] = {'frame': frame, 'path': str(path), 'sha256': sha256_file(path)}
        contract['proofs'] = [records[key] for key in sorted(records)]
        contract_path.write_text(json.dumps(contract, indent=2) + '\n')
        print(f'STABLE_REVEAL_FRAME={frame}', flush=True)
    verify_product(bpy.data.collections['PIMM_PUBLISHED'], contract['original_product'])
    checked_file(source_path, source_hash)
    checked_file(scene_path, contract['scene_sha256'])
    contract_for('capacity')
    print('STABLE_REVEAL_READY=' + str(contract_path), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames', nargs='+', type=int)
    render(parser.parse_args(sys.argv[sys.argv.index('--') + 1:]).frames)
    os._exit(0)
