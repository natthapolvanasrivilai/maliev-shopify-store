"""Assemble the individually approved r10/r11 native stills into one release."""
import json
from pathlib import Path

from PIL import Image, ImageChops

from scripts.blender.pimm_production import blender_bento_r10_final as native
from scripts.blender.pimm_production import blender_bento_white_final as white
from scripts.blender.pimm_production.export_bento_r10_assets import final_for
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import REPO_ROOT


def sources():
    selected = []
    for shot in ('capacity', 'controls', 'tooling', 'configuration'):
        approval = white.APPROVAL if shot == 'configuration' else native.APPROVAL
        if shot == 'configuration':
            contract = white.white_contract(shot)
            receipt = json.loads((white.OUTPUT / shot / 'final.json').read_text())
            native.validate_final(receipt, contract, shot, white.APPROVAL, white.OUTPUT)
            frame = receipt['frames'][0]
        elif shot == 'controls':
            contract = native.contract_for('controls-orbit')
            path = native.OUTPUT / 'controls-orbit/frame-0001.png'
            frame = json.loads(path.with_suffix('.json').read_text())
            native.validate_native_frame(frame, contract, sha256_file(approval), path, 1)
        else:
            contract = native.contract_for(shot)
            frame = final_for(shot)['frames'][0]
        selected.append({'shot': shot, 'size': contract['native_size'], 'generation': contract['generation'],
                         'approval': approval.relative_to(REPO_ROOT).as_posix(),
                         'approval_sha256': sha256_file(approval), 'scene_sha256': contract['scene_sha256'],
                         'master_sha256': contract['master_sha256'], 'native_path': frame['native_path'],
                         'native_sha256': frame['native_sha256']})
    return selected


def export():
    selected = sources()
    destination = REPO_ROOT / 'assets'
    release = destination / 'pimm-bento-r11-stills.v1.json'
    if release.exists():
        raise FileExistsError(release)
    for item in selected:
        item['filename'] = f"pimm-bento-20260903-r11-30g-{item['shot']}.webp"
    if any((destination / item['filename']).exists() for item in selected):
        raise FileExistsError('Approved still release is immutable')
    for item in selected:
        target = destination / item['filename']
        with Image.open(item['native_path']) as original:
            image = original.convert('RGB')
            assert list(image.size) == item['size']
            image.save(target, 'WEBP', lossless=True, method=6)
            with Image.open(target) as encoded:
                assert ImageChops.difference(image, encoded.convert('RGB')).getbbox() is None
        item.update(sha256=sha256_file(target), bytes=target.stat().st_size)
    if sources() != [{k: v for k, v in item.items() if k not in ('filename', 'sha256', 'bytes')} for item in selected]:
        raise ValueError('Source approval changed during encoding')
    manifest = {'schema_version': 2, 'generation': 'bento-20260903-r11-stills',
                'encoding': 'native-size lossless RGB WebP from individually approved Blender PNG',
                'scope': 'Approved r10 lighting and r11 white configuration, static preview until orbit is complete',
                'assets': selected}
    if release.exists():
        raise FileExistsError(release)
    release.write_text(json.dumps(manifest, indent=2) + '\n')
    print('APPROVED_STILLS_READY=' + str(release), flush=True)


if __name__ == '__main__':
    export()
