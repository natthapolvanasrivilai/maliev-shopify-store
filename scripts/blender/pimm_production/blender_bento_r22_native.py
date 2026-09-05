"""Resumable native PNG/float EXR rendering of the owner-approved r22 motion set."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.blender_bento_stable_reveal_proof import verify_product
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.package_bento_motion_review import (
    current_source_authority, validate_sequence, validate_source_authority)
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT, require_within

APPROVAL = REPO_ROOT / 'docs/pimm-blender-governance/bento-r22-approval.json'
GENERATION = 'bento-20260903-r23-native-motion'
OUTPUT = ASSET_ROOT / 'renders/final' / GENERATION
SHOTS = ('capacity', 'tooling', 'configuration')


def approved_review():
    approval = json.loads(APPROVAL.read_text())
    if approval.get('decision') != 'approved' or approval.get('shots') != list(SHOTS):
        raise ValueError('Exact complete r22 owner approval required')
    path = require_within(Path(approval['review_path']), ASSET_ROOT / 'renders/proofs')
    checked_file(path, approval['review_sha256'])
    review = json.loads(path.read_text())
    if review['generation'] != 'bento-20260903-r22-stable-motion-review' or review['verified_png_count'] != 1224:
        raise ValueError('Wrong approved review generation')
    for file in review['files']:
        checked_file(require_within(path.parent / file['filename'], path.parent), file['sha256'])
    sequences = review['sequences']
    for shot in SHOTS:
        entry = sequences[shot]
        contract = Path(entry['contract_path'])
        checked_file(contract, entry['contract_sha256'])
        root = ASSET_ROOT / 'renders/proofs' / entry['generation']
        if shot != 'capacity':
            root /= shot
        actual = validate_sequence(contract, root, Path(entry['worker_path']), entry['generation'], shot, entry['frames'])
        if actual != entry:
            raise ValueError('Reviewed sequence changed')
    validate_source_authority(sequences, current_source_authority())
    return review


def frame_path(root, shot, index):
    count = 840 if shot == 'configuration' else 192
    if shot not in SHOTS or type(index) is not int or not 1 <= index <= count:
        raise ValueError('Invalid native frame')
    if shot == 'configuration':
        row, frame = divmod(index - 1, 120)
        return root / shot / f'row-{row:02d}' / f'frame-{frame + 1:04d}.png'
    return root / shot / f'frame-{index:04d}.png'


def validate_frame(record, output, size, authority, index):
    if record.get('index') != index or record.get('authority') != authority:
        raise ValueError('Native frame authority changed')
    if not os.path.samefile(record['path'], output):
        raise ValueError('Wrong native frame path')
    checked_file(output, record['sha256'])
    with output.open('rb') as stream:
        header = stream.read(24)
    if header[:8] != b'\x89PNG\r\n\x1a\n' or list(struct.unpack('>II', header[16:24])) != size:
        raise ValueError('Wrong native PNG size')
    exr = output.with_suffix('.exr')
    if not os.path.samefile(record['exr_path'], exr):
        raise ValueError('Wrong native EXR path')
    checked_file(exr, record['exr_sha256'])
    with exr.open('rb') as stream:
        if stream.read(4) != b'\x76\x2f\x31\x01':
            raise ValueError('Expected native float EXR')


def save_float_master(scene, path):
    import bpy
    settings = scene.render.image_settings
    original = settings.file_format, settings.color_mode, settings.color_depth, settings.exr_codec
    try:
        settings.file_format, settings.color_mode = 'OPEN_EXR', 'RGBA'
        settings.color_depth, settings.exr_codec = '32', 'ZIP'
        bpy.data.images['Render Result'].save_render(str(path), scene=scene)
    finally:
        settings.file_format, settings.color_mode, settings.color_depth, settings.exr_codec = original


def render(shot, review, selected=None):
    import bpy
    entry = review['sequences'][shot]
    if selected is not None:
        if not selected or len(set(selected)) != len(selected):
            raise ValueError('Expected unique native frame indices')
        for index in selected:
            frame_path(OUTPUT, shot, index)
    contract = json.loads(Path(entry['contract_path']).read_text())
    authority = {'approval_sha256': sha256_file(APPROVAL), 'review_sha256': json.loads(APPROVAL.read_text())['review_sha256'],
                 'contract_sha256': entry['contract_sha256'], 'scene_sha256': entry['scene_sha256'],
                 'worker_sha256': sha256_file(Path(__file__))}
    bpy.ops.wm.open_mainfile(filepath=entry['scene_path'])
    scene = bpy.context.scene
    size = entry['native_intent']
    assert [scene.render.resolution_x, scene.render.resolution_y] == size
    assert scene.render.resolution_percentage == 100 and scene.cycles.samples == contract['samples']
    assert scene.frame_end == entry['frames'] and scene.render.fps == 24 and scene.render.fps_base == 1
    product = bpy.data.collections['PIMM_PUBLISHED']
    original = {obj.name: {'mesh': obj.data.name, 'materials': [m.name for m in obj.data.materials],
                          'matrix': [list(row) for row in obj.matrix_world]}
                for obj in product.all_objects if obj.type == 'MESH'}
    verify_product(product, contract['original_product'] if shot == 'capacity' else original)
    if shot == 'capacity':
        assert scene.render.use_persistent_data is False
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.refresh_devices()
    prefs.compute_device_type = 'OPTIX'
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    if not any(device.use for device in prefs.devices):
        raise RuntimeError('Approved OptiX GPU unavailable')
    print(f'NATIVE_START={shot}:{size}:{scene.cycles.samples} samples', flush=True)
    for index in selected or range(1, entry['frames'] + 1):
        output = require_within(frame_path(OUTPUT, shot, index), ASSET_ROOT / 'renders/final')
        receipt = output.with_suffix('.json')
        if receipt.exists():
            validate_frame(json.loads(receipt.read_text()), output, size, authority, index)
            continue
        if output.exists() or output.with_suffix('.exr').exists():
            raise FileExistsError('Unreceipted native output; preserve for investigation')
        output.parent.mkdir(parents=True, exist_ok=True)
        scene.frame_set(index)
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)
        exr = output.with_suffix('.exr')
        save_float_master(scene, exr)
        record = {'index': index, 'path': str(output), 'sha256': sha256_file(output),
                  'exr_path': str(exr), 'exr_sha256': sha256_file(exr), 'authority': authority}
        validate_frame(record, output, size, authority, index)
        receipt.write_text(json.dumps(record, indent=2) + '\n')
        print(f'NATIVE_FRAME={shot}:{index}/{entry["frames"]}', flush=True)
    verify_product(product, original)
    checked_file(entry['scene_path'], entry['scene_sha256'])
    checked_file(APPROVAL, authority['approval_sha256'])
    checked_file(entry['contract_path'], entry['contract_sha256'])
    if selected is None:
        records = []
        for index in range(1, entry['frames'] + 1):
            output = frame_path(OUTPUT, shot, index)
            record = json.loads(output.with_suffix('.json').read_text())
            validate_frame(record, output, size, authority, index)
            records.append(record)
        manifest = OUTPUT / shot / 'final.json'
        result = {'generation': GENERATION, 'shot': shot, 'size': size, 'samples': scene.cycles.samples,
                  'resolution_percentage': 100, 'authority': authority, 'frames': records}
        if manifest.exists() and json.loads(manifest.read_text()) != result:
            raise ValueError('Immutable native manifest differs')
        if not manifest.exists():
            manifest.write_text(json.dumps(result, indent=2) + '\n')
        print('NATIVE_READY=' + str(manifest), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shot', choices=(*SHOTS, 'all'), required=True)
    parser.add_argument('--frames', nargs='+', type=int)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    reviewed = approved_review()
    for chosen in SHOTS if args.shot == 'all' else (args.shot,):
        render(chosen, reviewed, args.frames)
    validate_source_authority(reviewed['sequences'], current_source_authority())
    os._exit(0)
