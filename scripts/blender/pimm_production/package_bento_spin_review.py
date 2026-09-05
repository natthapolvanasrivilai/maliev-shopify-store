"""Package a button-free interactive review without releasing proof pixels."""
import argparse
import json
from pathlib import Path
import shutil
import struct

from scripts.blender.pimm_production.blender_bento_spin_proof import GENERATION, FRAMES
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT, require_within


def package(review_name='review'):
    if not review_name.startswith('review') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in review_name):
        raise ValueError('Invalid review package name')
    root = require_within(ASSET_ROOT / 'renders/proofs' / GENERATION, ASSET_ROOT / 'renders/proofs')
    contract_path = ASSET_ROOT / 'scenes/contracts' / f'pimm-30g--{GENERATION}--configuration.json'
    contract = json.loads(contract_path.read_text())
    if contract['approval'] != 'pending' or len(contract['proofs']) != FRAMES:
        raise ValueError('Complete exact proof sequence is required')
    checked_file(Path(__file__).with_name('blender_bento_spin_proof.py'), contract['script_sha256'])
    checked_file(contract['scene_path'], contract['scene_sha256'])
    for index, frame in enumerate(contract['proofs'], 1):
        path = root / f'frame-{index:04d}.png'
        if frame['frame'] != index or Path(frame['path']).resolve() != path.resolve():
            raise ValueError('Incorrect proof frame identity')
        checked_file(path, frame['sha256'])
        with path.open('rb') as stream:
            header = stream.read(24)
        if header[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', header[16:24]) != (600, 300):
            raise ValueError('Wrong native-proof dimensions')
    destination = root / review_name
    if destination.exists():
        raise FileExistsError('Review packages are immutable')
    destination.mkdir()
    sources = [(Path(__file__).parent / 'review/bento-spin.html', 'index.html')]
    sources += [(REPO_ROOT / 'assets' / name, name) for name in
                ('pimm-bento-spin.js','pimm-bento-spin.css','Outfit-Latin.woff2')]
    files = []
    for source, filename in sources:
        output = destination / filename
        shutil.copyfile(source, output)
        files.append({'filename': filename, 'sha256': sha256_file(output)})
    receipt = {'generation': GENERATION, 'status': 'pending_owner_approval',
               'contract_path': str(contract_path), 'contract_sha256': sha256_file(contract_path),
               'frames': FRAMES, 'step_degrees': 3, 'proof_size': [600,300],
               'native_intent': [2400,1200], 'files': files}
    (destination / 'review.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('SPIN_REVIEW_READY=' + str(destination), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--review-name', default='review')
    package(parser.parse_args().review_name)
