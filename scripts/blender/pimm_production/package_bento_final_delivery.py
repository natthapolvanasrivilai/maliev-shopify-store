"""Verify completed renders and package web derivatives; never publish to Shopify."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production import blender_bento_r22_native as native
from scripts.blender.pimm_production import blender_bento_capacity_web_final as capacity
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT

GENERATION = 'bento-20260903-r28-final-motion-review'
OUTPUT = ASSET_ROOT / 'renders/proofs' / GENERATION
SIZES = {'capacity': [800, 1100], 'tooling': [1600, 2000], 'configuration': [2400, 1200]}
DELIVERY_SIZES = {'capacity': [800, 1100], 'tooling': [800, 1000], 'configuration': [1200, 600]}
BLENDER = Path(r'D:\Blender 5.2\blender.exe')


def validate_manifest(record, shot, authority):
    count = 840 if shot == 'configuration' else 192
    if (record.get('shot') != shot or record.get('size') != SIZES[shot] or
            record.get('resolution_percentage') != 100 or record.get('authority') != authority or
            record.get('samples') != (48 if shot == 'capacity' else 128) or
            len(record.get('frames', [])) != count or
            [item.get('index') for item in record['frames']] != list(range(1, count + 1))):
        raise ValueError(f'Incomplete or changed native render sequence: {shot}')
    if shot == 'capacity' and record.get('persistent_data') is not False:
        raise ValueError('Capacity stability fix is missing')


def load_sources(review):
    records = {}
    for shot in native.SHOTS:
        root = capacity.OUTPUT if shot == 'capacity' else native.OUTPUT
        approval_path = capacity.APPROVAL if shot == 'capacity' else native.APPROVAL
        approval = json.loads(approval_path.read_text())
        if approval.get('decision') != 'approved':
            raise ValueError('Owner approval missing')
        worker = capacity if shot == 'capacity' else native
        entry = review['sequences'][shot]
        authority = {
            'approval_sha256': sha256_file(approval_path), 'review_sha256': approval['review_sha256'],
            'contract_sha256': entry['contract_sha256'], 'scene_sha256': entry['scene_sha256'],
            'worker_sha256': sha256_file(Path(worker.__file__)),
        }
        path = root / shot / 'final.json'
        manifest_hash = sha256_file(path)
        manifest = json.loads(path.read_text())
        validate_manifest(manifest, shot, authority)
        for record in manifest['frames']:
            native.validate_frame(record, native.frame_path(root, shot, record['index']), SIZES[shot], authority, record['index'])
        checked_file(path, manifest_hash)
        records[shot] = {'path': str(path), 'sha256': manifest_hash, 'manifest': manifest}
    return records


def derivative(source, output, size):
    from PIL import Image
    source_hash = sha256_file(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError('Existing derivative preserved: ' + str(output))
    with Image.open(source) as original:
        pixels = original.convert('RGB')
        if list(pixels.size) != size:
            pixels = pixels.resize(size, Image.Resampling.LANCZOS)
        if output.suffix == '.webp':
            pixels.save(output, 'WEBP', lossless=True, method=6)
        else:
            pixels.save(output, 'PNG')
        with Image.open(output) as decoded:
            if list(decoded.size) != size or decoded.convert('RGB').tobytes() != pixels.tobytes():
                raise ValueError('Derivative decode mismatch')
    checked_file(source, source_hash)
    return {'filename': output.relative_to(OUTPUT).as_posix(), 'size': size,
            'sha256': sha256_file(output), 'bytes': output.stat().st_size,
            'native_path': str(source), 'native_sha256': source_hash}


def encode_video(shot):
    from scripts.blender.pimm_production.encode_bento_r10_video import encode
    receipt_path = OUTPUT / 'derivatives.json'
    receipt_hash = sha256_file(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    entries = receipt['derivatives'][shot]
    if len(entries) != 192 or any(item['size'] != DELIVERY_SIZES[shot] for item in entries):
        raise ValueError('Complete motion derivatives required')
    paths = [checked_file(OUTPUT / item['filename'], item['sha256']) for item in entries]
    encode(paths, OUTPUT / f'{shot}.mp4', DELIVERY_SIZES[shot])
    checked_file(receipt_path, receipt_hash)
    output = OUTPUT / f'{shot}.mp4'
    result = {'filename': output.name, 'sha256': sha256_file(output), 'bytes': output.stat().st_size,
              'frames': 192, 'fps': 24, 'size': DELIVERY_SIZES[shot],
              'derivatives_sha256': receipt_hash}
    (OUTPUT / f'{shot}-video.json').write_text(json.dumps(result, indent=2) + '\n')


def package():
    review = native.approved_review()
    sources = load_sources(review)
    if OUTPUT.exists():
        raise FileExistsError('Immutable delivery staging already exists; preserve for investigation')
    OUTPUT.mkdir(parents=True)
    derivatives = {}
    for shot, source in sources.items():
        def convert(record):
            path = Path(record['path'])
            if shot == 'configuration':
                target = OUTPUT / shot / path.parent.name / path.with_suffix('.webp').name
            else:
                target = OUTPUT / shot / path.name
            return derivative(path, target, DELIVERY_SIZES[shot])
        with ThreadPoolExecutor(max_workers=4) as pool:
            derivatives[shot] = list(pool.map(convert, source['manifest']['frames']))
    receipt = {'generation': GENERATION, 'sources': sources, 'derivatives': derivatives,
               'method': 'Approved final PNG display pixels; Lanczos downsample only; lossless WebP or PNG'}
    (OUTPUT / 'derivatives.json').write_text(json.dumps(receipt, indent=2) + '\n')
    for shot in ('capacity', 'tooling'):
        with (OUTPUT / f'{shot}-encode.log').open('w') as log:
            subprocess.run([str(BLENDER), '--background', '--python-exit-code', '1', '--python',
                            str(Path(__file__).resolve()), '--', '--encode', shot],
                           check=True, stdout=log, stderr=subprocess.STDOUT)
    for name in ('pimm-bento-spin.js', 'pimm-bento-spin.css', 'pimm-bento-orbit.js', 'Outfit-Latin.woff2'):
        shutil.copyfile(REPO_ROOT / 'assets' / name, OUTPUT / name)
        checked_file(OUTPUT / name, sha256_file(REPO_ROOT / 'assets' / name))
    template = Path(__file__).parent / 'review/bento-motion.html'
    html = template.read_text(encoding='utf-8')
    html = html.replace('../__CAPACITY_GENERATION__/frame-0001.png', 'capacity/frame-0001.png')
    html = html.replace('../bento-20260903-r15-camera-previews/tooling/frame-0001.png', 'tooling/frame-0001.png')
    html = html.replace('../bento-20260903-r15-camera-previews/configuration/', 'configuration/')
    html = html.replace('frame-{frame}.png', 'frame-{frame}.webp').replace('row-03/frame-0001.png', 'row-03/frame-0001.webp')
    for shot, size in DELIVERY_SIZES.items():
        html = html.replace(f'__{shot.upper()}_WIDTH__', str(size[0])).replace(f'__{shot.upper()}_HEIGHT__', str(size[1]))
    html = html.replace('combined motion proof', 'final motion renders')
    html = html.replace('30G · motion and interaction proof', '30G · final motion renders')
    html = html.replace('Low-resolution Blender preview, not final renders and not the storefront. Review the motion, camera framing and component visibility here before full-resolution rendering.',
                        'Completed approved Blender renders, optimized for web delivery. Local review only; production is unchanged.')
    html = html.replace('Proof only: 1,224 verified native frames.', 'Final-render review: 1,224 verified frames with archived float masters.')
    html = html.replace('CONFIRM YOUR<br>MOLD PATH', 'FLEXIBLE<br>FIXTURE PLATFORM')
    if '__' in html or '../bento-' in html:
        raise ValueError('Review still refers to proof pixels or unresolved tokens')
    # Only expose the review after every render, derivative and video is verified.
    for shot, source in sources.items():
        checked_file(source['path'], source['sha256'])
    for entries in derivatives.values():
        for item in entries:
            checked_file(OUTPUT / item['filename'], item['sha256'])
    for shot in ('capacity', 'tooling'):
        video = json.loads((OUTPUT / f'{shot}-video.json').read_text())
        checked_file(OUTPUT / video['filename'], video['sha256'])
    (OUTPUT / 'index.html').write_text(html, encoding='utf-8')
    result = {'generation': GENERATION, 'final_native_frames': 1224, 'production_changed': False,
              'sources': {shot: {'path': value['path'], 'sha256': value['sha256']} for shot, value in sources.items()},
              'index_sha256': sha256_file(OUTPUT / 'index.html')}
    (OUTPUT / 'review.json').write_text(json.dumps(result, indent=2) + '\n')
    print('FINAL_REVIEW_READY=http://127.0.0.1:61284/' + GENERATION + '/', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--encode', choices=('capacity', 'tooling'))
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    args = parser.parse_args(arguments)
    if args.encode:
        encode_video(args.encode)
        import os
        os._exit(0)
    else:
        package()
