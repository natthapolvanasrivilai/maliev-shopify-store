"""Lossless display-pixel derivatives of approved proofs, for local review only."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import sys
import PIL
from PIL import Image, features

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_r22_native import approved_review, APPROVAL
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT

GENERATION = 'bento-20260903-r25-web-interaction-review'


def encode_frame(source, output):
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        pixels = original.convert('RGB')
        pixels.save(output, 'WEBP', lossless=True, method=6)
        with Image.open(output) as decoded:
            if decoded.size != original.size or decoded.convert('RGB').tobytes() != pixels.tobytes():
                raise ValueError('Display pixels changed during WebP encoding')
    return {'filename': output.as_posix(), 'sha256': sha256_file(output),
            'bytes': output.stat().st_size, 'source_bytes': source.stat().st_size,
            'source_sha256': sha256_file(source)}


def package():
    root = ASSET_ROOT / 'renders/proofs' / GENERATION
    if root.exists():
        raise FileExistsError('Immutable review generation already exists')
    review = approved_review()
    original_root = Path(json.loads(APPROVAL.read_text())['review_path']).parent
    root.mkdir(parents=True)
    frames = review['sequences']['configuration']['proofs']
    def encode(record):
        source = Path(record['path'])
        checked_file(source, record['sha256'])
        output = root / 'configuration' / source.parent.name / source.with_suffix('.webp').name
        result = encode_frame(source, output)
        checked_file(source, record['sha256'])
        result['filename'] = output.relative_to(root).as_posix()
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(encode, frames))
    html = (original_root / 'index.html').read_text(encoding='utf-8')
    html = html.replace('../bento-20260903-r15-camera-previews/configuration/', 'configuration/')
    html = html.replace('frame-{frame}.png', 'frame-{frame}.webp').replace('row-03/frame-0001.png', 'row-03/frame-0001.webp')
    (root / 'index.html').write_text(html, encoding='utf-8')
    files = ['index.html']
    for name in ('pimm-bento-spin.js', 'pimm-bento-spin.css', 'pimm-bento-orbit.js', 'Outfit-Latin.woff2'):
        shutil.copyfile(REPO_ROOT / 'assets' / name, root / name)
        files.append(name)
    for name in ('capacity.mp4', 'tooling.mp4'):
        shutil.copyfile(original_root / name, root / name)
        files.append(name)
    result = {'generation': GENERATION, 'not_final': True, 'storefront_changed': False,
              'source_review_sha256': sha256_file(original_root / 'review.json'),
              'encoding': 'Lossless WebP, same size and exact decoded 8-bit RGB display pixels; no retouching',
              'pillow_version': PIL.__version__, 'webp_version': features.version('webp'),
              'frames': outputs,
              'source_bytes': sum(r['source_bytes'] for r in outputs),
              'web_bytes': sum(r['bytes'] for r in outputs),
              'files': [{'filename': name, 'sha256': sha256_file(root / name)} for name in files]}
    (root / 'web-review.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('generation', 'source_bytes', 'web_bytes')}), flush=True)


if __name__ == '__main__':
    package()
