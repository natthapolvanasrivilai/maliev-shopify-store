"""Render immutable, owner-approved r10 scenes at their saved native settings."""
from __future__ import annotations

import argparse
import json
import os
import struct
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_final import checked_file, approved_contract, APPROVAL as SOURCE_APPROVAL
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT, require_within

APPROVAL = REPO_ROOT / 'docs/pimm-blender-governance/bento-r10-approval.json'
OUTPUT = ASSET_ROOT / 'renders/final/bento-20260903-r10-native'
SHOTS = ('capacity', 'controls', 'tooling', 'configuration', 'controls-orbit')


def validate_native_frame(frame, contract, approval_hash, expected_path, index):
    if (frame['frame'] != index or Path(frame['native_path']).resolve() != expected_path.resolve() or
            frame['approval_sha256'] != approval_hash or frame['scene_sha256'] != contract['scene_sha256']):
        raise ValueError('Invalid native frame identity')
    checked_file(expected_path, frame['native_sha256'])
    with expected_path.open('rb') as stream:
        header = stream.read(24)
    if (header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR' or
            list(struct.unpack('>II', header[16:24])) != contract['native_size']):
        raise ValueError('Native PNG dimensions do not match approved scene')
    return frame


def validate_final(receipt, contract, shot, approval_path=None, output_root=None):
    approval_path = approval_path or APPROVAL
    output_root = output_root or OUTPUT
    expected = {'generation': contract['generation'], 'shot': shot,
                'approval_sha256': sha256_file(approval_path), 'scene_sha256': contract['scene_sha256'],
                'master_sha256': contract['master_sha256'], 'size': contract['native_size']}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('Final authority or dimensions changed')
    if len(receipt['frames']) != (192 if shot == 'controls-orbit' else 1):
        raise ValueError('Incomplete native render')
    for index, frame in enumerate(receipt['frames'], 1):
        expected_path = require_within(output_root / shot / f'frame-{index:04d}.png', output_root)
        validate_native_frame(frame, contract, expected['approval_sha256'], expected_path, index)
    return receipt


def contract_for(shot):
    approval = json.loads(APPROVAL.read_text())
    if approval['decision'] != 'approved' or shot not in SHOTS:
        raise ValueError('Exact r10 shot approval required')
    review = json.loads((REPO_ROOT / approval['review_manifest']).read_text())
    digest = approval['contracts'][shot]
    entry = next(item for item in review['contracts'] if item['sha256'] == digest)
    path = checked_file(require_within(Path(entry['path']), ASSET_ROOT / 'scenes/contracts'), digest)
    contract = json.loads(path.read_text())
    animated = shot == 'controls-orbit'
    expected_generation = 'bento-20260903-r10-' + ('orbit' if animated else 'lighting')
    if contract['generation'] != expected_generation or contract['shot'] != shot.removesuffix('-orbit'):
        raise ValueError('Wrong generation or shot')
    source = approved_contract(contract['shot'])
    checked_file(SOURCE_APPROVAL, contract['source_approval_sha256'])
    source_approval = json.loads(SOURCE_APPROVAL.read_text())
    source_entry = next(item for item in source_approval['shots'] if item['shot'] == contract['shot'])
    if source_entry['contract_sha256'] != contract['source_contract_sha256']:
        raise ValueError('Changed source approval chain')
    for key in ('master_sha256', 'material_library_sha256', 'tool_lock_sha256'):
        if contract[key] != source[key]:
            raise ValueError(f'Changed authority: {key}')
    checked_file(contract['scene_path'], contract['scene_sha256'])
    checked_file(Path(__file__).with_name('blender_bento_lighting_orbit_proof.py'), contract['script_sha256'])
    if len(contract['proofs']) != (192 if animated else 1):
        raise ValueError('Incomplete reviewed proof')
    for proof in contract['proofs']:
        checked_file(require_within(Path(proof['path']), ASSET_ROOT / 'renders/proofs'), proof['sha256'])
    return contract


def render(shot, contract_loader=None, approval_path=None, output_root=None):
    import bpy
    contract_loader = contract_loader or contract_for
    approval_path = approval_path or APPROVAL
    output_root = output_root or OUTPUT
    contract = contract_loader(shot)
    approval_hash = sha256_file(approval_path)
    output_dir = require_within(output_root / shot, ASSET_ROOT / 'renders/final')
    output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=contract['scene_path'])
    scene = bpy.context.scene
    assert [scene.render.resolution_x, scene.render.resolution_y] == contract['native_size']
    assert scene.render.resolution_percentage == 100 and scene.cycles.samples == contract['samples']
    product = bpy.data.collections['PIMM_PUBLISHED']
    meshes = [obj for obj in product.all_objects if obj.type == 'MESH']
    assert len(meshes) == 556 and all(obj.library and obj.data.library and not obj.override_library for obj in meshes)
    assert all(not obj.animation_data for obj in product.all_objects)
    animated = shot == 'controls-orbit'
    if animated:
        assert scene.frame_end == 192 and scene.render.fps == 24 and scene.render.fps_base == 1
        assert [obj for obj in scene.objects if obj.animation_data] == [scene.camera]
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.refresh_devices()
    backend = next((name for name in ('OPTIX', 'CUDA') if any(d.type == name for d in preferences.devices)), None)
    if backend is None:
        raise RuntimeError('Approved GPU renderer unavailable')
    preferences.compute_device_type = backend
    for device in preferences.devices:
        device.use = device.type == backend
    records = []
    for frame in range(1, 193 if animated else 2):
        output = output_dir / f'frame-{frame:04d}.png'
        receipt = output.with_suffix('.json')
        if receipt.exists():
            record = json.loads(receipt.read_text())
            if (record['approval_sha256'] != approval_hash or record['scene_sha256'] != contract['scene_sha256'] or
                    record['frame'] != frame or Path(record['native_path']).resolve() != output.resolve()):
                raise ValueError('Existing frame belongs to different authority')
            checked_file(output, record['native_sha256'])
        else:
            if output.exists():
                raise FileExistsError(f'Unreceipted output: {output}')
            scene.frame_set(frame)
            scene.render.filepath = str(output)
            bpy.ops.render.render(write_still=True)
            record = {'frame': frame, 'native_path': str(output), 'native_sha256': sha256_file(output),
                      'approval_sha256': approval_hash, 'scene_sha256': contract['scene_sha256']}
            receipt.write_text(json.dumps(record, indent=2) + '\n')
        records.append(record)
        print(f'R10_NATIVE_FRAME={shot}:{frame}', flush=True)
    contract_loader(shot)
    if sha256_file(approval_path) != approval_hash:
        raise ValueError('Approval changed during render')
    manifest = output_dir / 'final.json'
    result = {'schema': 'maliev.pimm-bento-final/v2', 'generation': contract['generation'], 'shot': shot,
              'approval_sha256': approval_hash, 'scene_sha256': contract['scene_sha256'],
              'master_sha256': contract['master_sha256'], 'size': contract['native_size'], 'frames': records}
    if manifest.exists():
        assert json.loads(manifest.read_text()) == result
    else:
        manifest.write_text(json.dumps(result, indent=2) + '\n')
    print(f'R10_NATIVE_READY={manifest}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shot', choices=SHOTS, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    render(args.shot)
    os._exit(0)
