"""Render the exact owner-approved bento scenes; never rebuild or modify them."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT, require_within
from scripts.blender.pimm_production.tool_policy import LOCK_PATH, validate_tool_lock

APPROVAL = REPO_ROOT / 'docs/pimm-blender-governance/bento-20260903-r06-approval.json'


def checked_file(path, digest):
    path = Path(path)
    if not path.is_file() or sha256_file(path).upper() != digest.upper():
        raise ValueError(f'Approved dependency changed: {path}')
    return path


def approved_contract(shot):
    approval = json.loads(APPROVAL.read_text(encoding='utf-8'))
    if approval['decision'] != 'approved' or approval['generation'] != 'bento-20260903-r06':
        raise ValueError('Exact generation must be approved')
    entry = next(item for item in approval['shots'] if item['shot'] == shot)
    path = require_within(Path(entry['contract_path']), ASSET_ROOT / 'scenes/contracts')
    checked_file(path, entry['contract_sha256'])
    contract = json.loads(path.read_text(encoding='utf-8'))
    if contract['generation'] != approval['generation'] or contract['shot'] != shot:
        raise ValueError('Wrong proof contract')
    for key in ('scene', 'proof'):
        checked_file(require_within(Path(contract[f'{key}_path']), ASSET_ROOT), contract[f'{key}_sha256'])
    checked_file(ASSET_ROOT / 'masters/PIMM-30G-MASTER.blend', contract['master_sha256'])
    checked_file(ASSET_ROOT / 'masters/PIMM-MATERIAL-LIBRARY.blend', contract['material_library_sha256'])
    checked_file(LOCK_PATH, contract['tool_lock_sha256'])
    lock = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
    if validate_tool_lock(lock):
        raise ValueError('Invalid free-tools lock')
    for tool in lock['tools']:
        if tool['id'] != 'blender-mcp':
            checked_file(tool['path'], tool['sha256'])
    hdri = lock['asset_provenance']['pinned_hdri']
    checked_file(ASSET_ROOT / hdri['path'], hdri['sha256'])
    return contract


def render(shot):
    import bpy
    contract = approved_contract(shot)
    output_dir = require_within(ASSET_ROOT / 'renders/final/bento-20260903-r06-native2', ASSET_ROOT)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f'pimm-bento-20260903-r06-30g-{shot}.png'
    receipt = output.with_suffix('.json')
    if output.exists() or receipt.exists():
        raise FileExistsError(output)
    bpy.ops.wm.open_mainfile(filepath=contract['scene_path'])
    scene = bpy.context.scene
    assert [scene.render.resolution_x, scene.render.resolution_y] == contract['native_size']
    assert scene.render.resolution_percentage == 100
    assert scene.cycles.samples == contract['samples']
    # Device preferences belong to the Blender process, not the saved scene.
    # Restore the proof worker's local GPU backend; do not change scene settings.
    if scene.cycles.device == 'GPU':
        preferences = bpy.context.preferences.addons['cycles'].preferences
        preferences.refresh_devices()
        available = {device.type for device in preferences.devices}
        backend = 'OPTIX' if 'OPTIX' in available else 'CUDA' if 'CUDA' in available else None
        if backend is None:
            raise RuntimeError('Approved GPU renderer is unavailable')
        preferences.compute_device_type = backend
        for device in preferences.devices:
            device.use = device.type == backend
    meshes = [o for o in bpy.data.collections['PIMM_PUBLISHED'].all_objects if o.type == 'MESH']
    assert len(meshes) == 556 and all(o.library and o.data.library for o in meshes)
    # Destination only: camera, materials, lighting and all render settings stay saved-state exact.
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    approved_contract(shot)  # Also fail closed if authority changed during rendering.
    receipt.write_text(json.dumps({
        'schema': 'maliev.pimm-bento-final/v1', 'generation': contract['generation'],
        'shot': shot, 'approval_sha256': sha256_file(APPROVAL),
        'scene_sha256': contract['scene_sha256'], 'proof_sha256': contract['proof_sha256'],
        'native_path': str(output), 'native_sha256': sha256_file(output),
        'size': contract['native_size'], 'master_sha256': contract['master_sha256'],
    }, indent=2) + '\n', encoding='utf-8')
    print(f'BENTO_FINAL_READY={receipt}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shot', choices=['capacity', 'controls', 'tooling', 'configuration'], required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    render(args.shot)
    os._exit(0)
