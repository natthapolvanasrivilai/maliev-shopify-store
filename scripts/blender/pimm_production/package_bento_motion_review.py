"""Verify and package combined native-motion proofs; never release storefront assets."""
import json
import os
from pathlib import Path
import shutil
import struct
import uuid

from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.blender_bento_tube_reveal_proof import TARGETS
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT, require_within

GENERATION = 'bento-20260903-r22-stable-motion-review'
CAMERA_GENERATION = 'bento-20260903-r15-camera-previews'
CAPACITY_GENERATION = 'bento-20260903-r21-stable-tube-reveal'
WORKER_ROOT = Path(__file__).parent


def same_file(actual, expected):
    """Allow a verified file's mapped-drive and UNC spellings to identify the same file."""
    if not os.path.samefile(actual, expected):
        raise ValueError(f'Incorrect proof file identity: {actual}')


def validate_sequence(contract_path, root, worker, generation, shot, count):
    contract = json.loads(contract_path.read_text(encoding='utf-8'))
    contract_hash = sha256_file(contract_path)
    if (contract.get('approval') != 'pending' or contract.get('generation') != generation or
            contract.get('shot') != shot or len(contract.get('proofs', [])) != count or
            contract.get('motion', {}).get('frames') != count or contract['motion'].get('fps') != 24):
        raise ValueError('A complete, pending exact proof sequence is required')
    checked_file(worker, contract['script_sha256'])
    checked_file(contract['scene_path'], contract['scene_sha256'])
    native = contract['native_size']
    if (len(native) != 2 or any(type(value) is not int or value <= 0 or value % 4 for value in native) or
            contract['proof_percentage'] != 25):
        raise ValueError('Invalid native-derived proof dimensions')
    size = [value // 4 for value in native]
    if shot == 'configuration' and (contract['motion'].get('yaw_views') != 120 or
            contract['motion'].get('elevation_degrees') != [-6, -4, -2, 0, 2, 4, 6]):
        raise ValueError('Configuration must contain all 120 yaw views across seven pitch rows')
    if shot == 'capacity' and (contract.get('technical_visualization') is not True or
            len(contract.get('focus_objects', [])) != 4 or set(contract['focus_objects']) != set(TARGETS) or
            contract.get('ghost_opacity') != .2):
        raise ValueError('Technical reveal must preserve exactly the four approved 30G components')
    if shot == 'capacity' and contract.get('render_stability', {}).get('persistent_data') is not False:
        raise ValueError('Technical reveal must disable persistent render data')
    records = []
    for index, record in enumerate(contract['proofs'], 1):
        if shot == 'configuration':
            row, frame = divmod(index - 1, 120)
            path = root / f'row-{row:02d}' / f'frame-{frame + 1:04d}.png'
            if record.get('index') != index or record.get('row') != row or record.get('frame') != frame + 1:
                raise ValueError('Incorrect two-axis proof order')
        else:
            path = root / f'frame-{index:04d}.png'
            if record.get('frame') != index or (shot == 'tooling' and record.get('index') != index):
                raise ValueError('Incorrect motion proof order')
        same_file(record['path'], path)
        checked_file(path, record['sha256'])
        with path.open('rb') as stream:
            header = stream.read(24)
        if (len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or
                list(struct.unpack('>II', header[16:24])) != size):
            raise ValueError('Wrong native-proof dimensions')
        records.append({'path': str(path), 'sha256': record['sha256']})
    checked_file(contract_path, contract_hash)
    return {'generation': generation, 'shot': shot, 'contract_path': str(contract_path),
            'contract_sha256': contract_hash, 'scene_path': contract['scene_path'],
            'scene_sha256': contract['scene_sha256'], 'worker_path': str(worker),
            'source_scene_sha256': contract['source_scene_sha256'],
            'worker_sha256': contract['script_sha256'], 'proof_size': size, 'native_intent': native,
            'frames': count, 'proofs': records}


def validate_video(root, shot, sequence):
    receipt_path = root / f'{shot}.json'
    receipt_hash = sha256_file(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    output = root / f'{shot}.mp4'
    if (receipt.get('generation') != sequence['generation'] or receipt.get('shot') != shot or
            receipt.get('status') != 'pending_owner_approval' or receipt.get('frames') != 192 or
            receipt.get('fps') != 24 or receipt.get('duration_ms') != 8000 or
            receipt.get('size') != sequence['proof_size'] or
            receipt.get('contract_sha256') != sequence['contract_sha256'] or
            receipt.get('encoder') != 'Locked Blender 5.2 bundled FFmpeg; H264 perceptually lossless, sRGB, no resizing or retouching'):
        raise ValueError('Video must match the complete verified native proof sequence')
    same_file(receipt['contract_path'], sequence['contract_path'])
    same_file(receipt['path'], output)
    checked_file(output, receipt['sha256'])
    if output.stat().st_size != receipt['bytes']:
        raise ValueError('Video byte count mismatch')
    with output.open('rb') as stream:
        header = stream.read(12)
    if len(header) != 12 or header[4:8] != b'ftyp':
        raise ValueError('Expected encoded MP4')
    checked_file(receipt_path, receipt_hash)
    return {'path': str(output), 'sha256': receipt['sha256'], 'receipt_path': str(receipt_path),
            'receipt_sha256': receipt_hash, 'size': receipt['size'], 'frames': 192, 'fps': 24}


def current_source_authority():
    """Revalidate the current approved master/material chain, not inherited proof metadata."""
    from scripts.blender.pimm_production.blender_bento_white_detail_final import detail_contract, APPROVAL as WHITE_APPROVAL
    from scripts.blender.pimm_production.blender_bento_r10_final import contract_for, APPROVAL as R10_APPROVAL
    authority = {}
    for shot, loader, approval in (('configuration', detail_contract, WHITE_APPROVAL),
                                   ('tooling', contract_for, R10_APPROVAL), ('capacity', contract_for, R10_APPROVAL)):
        approval_hash = sha256_file(approval)
        source = loader(shot)
        checked_file(approval, approval_hash)
        authority[shot] = {'source_scene_sha256': source['scene_sha256'],
                           'approval_path': str(approval), 'approval_sha256': approval_hash}
    return authority


def validate_source_authority(sequences, authority):
    for shot, sequence in sequences.items():
        current = authority[shot]
        if sequence['source_scene_sha256'] != current['source_scene_sha256']:
            raise ValueError(f'Proof source does not match current approved source: {shot}')
        checked_file(current['approval_path'], current['approval_sha256'])


def package():
    proofs_root = ASSET_ROOT / 'renders/proofs'
    destination = require_within(proofs_root / GENERATION, proofs_root)
    if destination.exists():
        raise FileExistsError('Combined review packages are immutable')
    authority = current_source_authority()
    sequences = {}
    roots = {}
    for shot, generation, count, worker_name in (
            ('configuration', CAMERA_GENERATION, 840, 'blender_bento_axes_proof.py'),
            ('tooling', CAMERA_GENERATION, 192, 'blender_bento_axes_proof.py'),
            ('capacity', CAPACITY_GENERATION, 192, 'blender_bento_stable_reveal_proof.py')):
        root = proofs_root / generation / shot if shot != 'capacity' else proofs_root / generation
        roots[shot] = require_within(root, proofs_root)
        contract = ASSET_ROOT / 'scenes/contracts' / f'pimm-30g--{generation}--{shot}.json'
        sequences[shot] = validate_sequence(contract, root, WORKER_ROOT / worker_name, generation, shot, count)
    validate_source_authority(sequences, authority)
    videos = {shot: validate_video(roots[shot], shot, sequences[shot]) for shot in ('tooling', 'capacity')}
    template = WORKER_ROOT / 'review/bento-motion.html'
    template_hash = sha256_file(template)
    html = template.read_text(encoding='utf-8')
    html = html.replace('__CAPACITY_GENERATION__', CAPACITY_GENERATION)
    for shot, sequence in sequences.items():
        width, height = sequence['proof_size']
        html = html.replace(f'__{shot.upper()}_WIDTH__', str(width)).replace(f'__{shot.upper()}_HEIGHT__', str(height))
    if '__' in html:
        raise ValueError('Unresolved review template values')
    checked_file(template, template_hash)
    sources = [(REPO_ROOT / 'assets' / name, name) for name in
               ('pimm-bento-spin.js', 'pimm-bento-spin.css', 'pimm-bento-orbit.js', 'Outfit-Latin.woff2')]
    sources += [(Path(value['path']), f'{shot}.mp4') for shot, value in videos.items()]
    # Missing static assets fail before staging. A failed copy never claims the final name.
    sources = [(source, filename, sha256_file(source)) for source, filename in sources]
    staging = require_within(proofs_root / f'.{GENERATION}-staging-{uuid.uuid4().hex}', proofs_root)
    staging.mkdir()
    try:
        (staging / 'index.html').write_text(html, encoding='utf-8')
        files = [{'filename': 'index.html', 'sha256': sha256_file(staging / 'index.html')}]
        for source, filename, snapshot in sources:
            shutil.copyfile(source, staging / filename)
            checked_file(source, snapshot)
            checked_file(staging / filename, snapshot)
            files.append({'filename': filename, 'sha256': snapshot})
        for sequence in sequences.values():
            checked_file(sequence['contract_path'], sequence['contract_sha256'])
            checked_file(sequence['scene_path'], sequence['scene_sha256'])
            checked_file(sequence['worker_path'], sequence['worker_sha256'])
        for video in videos.values():
            checked_file(video['path'], video['sha256'])
            checked_file(video['receipt_path'], video['receipt_sha256'])
        checked_file(template, template_hash)
        # Re-read each live approval and its full source chain after the package copy.
        current = current_source_authority()
        validate_source_authority(sequences, current)
        if current != authority:
            raise ValueError('Approved source authority changed during packaging')
        receipt = {'generation': GENERATION, 'status': 'pending_owner_approval',
                   'not_final': True, 'storefront_changed': False, 'verified_png_count': 1224,
                   'technical_visualization': 'Protective cover and surrounding components shown transparent',
                   'opaque_30g_components': list(TARGETS), 'sequences': sequences, 'videos': videos, 'files': files,
                   'current_source_authority': authority,
                   'template_path': str(template), 'template_sha256': template_hash}
        (staging / 'review.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        if destination.exists():
            raise FileExistsError('Combined review packages are immutable')
        staging.rename(destination)
    except Exception as error:
        # Keep evidence; never remove a failed staging generation automatically.
        raise RuntimeError(f'Review package failed; staging retained at {staging}: {error}') from error
    print('BENTO_MOTION_REVIEW_READY=' + str(destination), flush=True)
    return destination


if __name__ == '__main__':
    package()
