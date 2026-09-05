"""Encode native Blender r10 finals, with no resize, retouch or compositing."""
import json
from pathlib import Path
import shutil

from PIL import Image, ImageChops

from scripts.blender.pimm_production.blender_bento_r10_final import APPROVAL, OUTPUT, contract_for, validate_final
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import REPO_ROOT


def final_for(shot):
    contract = contract_for(shot)
    receipt = json.loads((OUTPUT / shot / 'final.json').read_text())
    return validate_final(receipt, contract, shot)


def export():
    stills = {shot: final_for(shot) for shot in ('capacity', 'controls', 'tooling', 'configuration')}
    orbit = final_for('controls-orbit')
    assets = []
    destination = REPO_ROOT / 'assets'
    video_path = destination / 'pimm-bento-20260903-r10-30g-controls-orbit.mp4'
    video = json.loads((OUTPUT / 'controls-orbit' / video_path.with_suffix('.json').name).read_text())
    required = {'approval_sha256': orbit['approval_sha256'], 'scene_sha256': orbit['scene_sha256'],
                'filename': video_path.name, 'size': orbit['size'], 'frames': 192, 'fps': 24, 'duration_ms': 8000}
    if any(video.get(key) != value for key, value in required.items()):
        raise ValueError('Video metadata does not match approved orbit')
    if (Path(video['path']).resolve() != (OUTPUT / 'controls-orbit' / video_path.name).resolve() or
            Path(video['native_manifest']).resolve() != (OUTPUT / 'controls-orbit/final.json').resolve()):
        raise ValueError('Video must come from the canonical native release')
    checked_file(video['native_manifest'], video['native_manifest_sha256'])
    checked_file(video['path'], video['sha256'])
    targets = [destination / f'pimm-bento-20260903-r10-30g-{shot}.webp' for shot in stills] + [video_path]
    if any(path.exists() for path in targets):
        raise FileExistsError('Refusing to overwrite r10 assets')
    for shot, receipt in stills.items():
        # The orbit's actual first frame is the static fallback: exact endpoint parity.
        source = orbit['frames'][0] if shot == 'controls' else receipt['frames'][0]
        path = destination / f'pimm-bento-20260903-r10-30g-{shot}.webp'
        if path.exists():
            raise FileExistsError(path)
        with Image.open(source['native_path']) as image:
            image = image.convert('RGB')
            assert list(image.size) == receipt['size']
            image.save(path, 'WEBP', lossless=True, method=6)
            with Image.open(path) as encoded:
                assert ImageChops.difference(image, encoded.convert('RGB')).getbbox() is None
        assets.append({k: receipt[k] for k in ('generation', 'shot', 'approval_sha256', 'scene_sha256', 'master_sha256', 'size')})
        assets[-1].update(native_path=source['native_path'], native_sha256=source['native_sha256'],
                          generation=orbit['generation'] if shot == 'controls' else receipt['generation'],
                          scene_sha256=source['scene_sha256'],
                          filename=path.name, sha256=sha256_file(path), bytes=path.stat().st_size)
    path = destination / 'pimm-bento-20260903-r10-30g-controls-orbit.mp4'
    if path.exists():
        raise FileExistsError(path)
    shutil.copyfile(checked_file(video['path'], video['sha256']), path)
    manifest = {'schema_version': 2, 'generation': 'bento-20260903-r10',
                'approval': str(APPROVAL.relative_to(REPO_ROOT)).replace('\\', '/'),
                'encoding': 'native-size lossless RGB WebP from approved Blender PNG', 'assets': assets,
                'animation': video}
    (destination / 'pimm-bento-assets.v1.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'stills': len(assets), 'animation_bytes': path.stat().st_size, 'frames': 192}), flush=True)


if __name__ == '__main__':
    export()
