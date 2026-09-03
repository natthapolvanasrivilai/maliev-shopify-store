"""Encode complete proof-only sequences without resizing their Blender pixels."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.encode_bento_r10_video import encode
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT


def main(shot):
    if shot not in ('capacity', 'tooling'):
        raise ValueError('Unknown proof sequence')
    generation = 'bento-20260903-r21-stable-tube-reveal' if shot == 'capacity' else 'bento-20260903-r15-camera-previews'
    worker = 'blender_bento_stable_reveal_proof.py' if shot == 'capacity' else 'blender_bento_axes_proof.py'
    contract_path = ASSET_ROOT / 'scenes/contracts' / f'pimm-30g--{generation}--{shot}.json'
    contract = json.loads(contract_path.read_text())
    if contract['approval'] != 'pending' or len(contract['proofs']) != 192:
        raise ValueError('Complete pending proof required')
    checked_file(contract['scene_path'], contract['scene_sha256'])
    checked_file(Path(__file__).with_name(worker), contract['script_sha256'])
    contract_hash = sha256_file(contract_path)
    root = ASSET_ROOT / 'renders/proofs' / generation
    if shot == 'tooling':
        root /= shot
    size = [int(n * contract['proof_percentage'] / 100) for n in contract['native_size']]
    paths = []
    for index, record in enumerate(contract['proofs'], 1):
        path = root / f'frame-{index:04d}.png'
        if record['frame'] != index or not os.path.samefile(record['path'], path):
            raise ValueError('Incorrect proof sequence identity')
        checked_file(path, record['sha256'])
        with path.open('rb') as stream:
            header = stream.read(24)
        if header[:8] != b'\x89PNG\r\n\x1a\n' or list(struct.unpack('>II', header[16:24])) != size:
            raise ValueError('Incorrect proof dimensions')
        paths.append(path)
    output = root / f'{shot}.mp4'
    encode(paths, output, size)
    checked_file(contract_path, contract_hash)
    receipt = dict(generation=generation, shot=shot, contract_path=str(contract_path),
                   contract_sha256=contract_hash, path=str(output), sha256=sha256_file(output),
                   bytes=output.stat().st_size, size=size, frames=192, fps=24, duration_ms=8000,
                   encoder='Locked Blender 5.2 bundled FFmpeg; H264 perceptually lossless, sRGB, no resizing or retouching',
                   status='pending_owner_approval')
    output.with_suffix('.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('MOTION_PROOF_VIDEO=' + str(output), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shot', choices=('capacity', 'tooling'), required=True)
    main(parser.parse_args(sys.argv[sys.argv.index('--')+1:]).shot)
    os._exit(0)
