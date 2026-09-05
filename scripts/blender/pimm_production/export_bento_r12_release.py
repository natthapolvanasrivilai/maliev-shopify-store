"""Replace only configuration in the completed, individually approved motion set."""
import json
from PIL import Image, ImageChops

from scripts.blender.pimm_production import blender_bento_white_detail_final as detail
from scripts.blender.pimm_production.blender_bento_r10_final import validate_final
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.paths import REPO_ROOT
from scripts.blender.pimm_production.io_contract import sha256_file


def export():
    assets = REPO_ROOT / 'assets'
    source_path = assets / 'pimm-bento-r11-motion.v1.json'
    source_hash = sha256_file(source_path)
    source = json.loads(source_path.read_text())
    assert source['generation'] == 'bento-20260903-r11-motion'
    assert len(source['assets']) == 4
    for item in source['assets']:
        checked_file(assets / item['filename'], item['sha256'])
        checked_file(REPO_ROOT / item['approval'], item['approval_sha256'])
    checked_file(assets / source['animation']['filename'], source['animation']['sha256'])
    contract = detail.detail_contract('configuration')
    approval_hash = sha256_file(detail.APPROVAL)
    receipt = json.loads((detail.OUTPUT / 'configuration/final.json').read_text())
    validate_final(receipt, contract, 'configuration', detail.APPROVAL, detail.OUTPUT)
    frame = receipt['frames'][0]
    path = assets / 'pimm-bento-20260903-r12-30g-configuration.webp'
    manifest = assets / 'pimm-bento-r12-assets.v1.json'
    if path.exists() or manifest.exists():
        raise FileExistsError('r12 release is immutable')
    with Image.open(frame['native_path']) as original:
        image = original.convert('RGB')
        assert list(image.size) == contract['native_size']
        image.save(path, 'WEBP', lossless=True, method=6)
        with Image.open(path) as encoded:
            assert ImageChops.difference(image, encoded.convert('RGB')).getbbox() is None
    item = {'shot': 'configuration', 'generation': contract['generation'], 'size': contract['native_size'],
            'approval': detail.APPROVAL.relative_to(REPO_ROOT).as_posix(),
            'approval_sha256': approval_hash, 'scene_sha256': contract['scene_sha256'],
            'master_sha256': contract['master_sha256'], 'native_path': frame['native_path'],
            'native_sha256': frame['native_sha256'], 'filename': path.name,
            'sha256': sha256_file(path), 'bytes': path.stat().st_size}
    checked_file(source_path, source_hash)
    checked_file(detail.APPROVAL, approval_hash)
    detail.detail_contract('configuration')
    result = {**source, 'generation': 'bento-20260903-r12',
              'scope': 'Complete approved controls orbit and approved lower-exposure white configuration',
              'previous_manifest': source_path.name, 'previous_manifest_sha256': source_hash,
              'assets': [item if record['shot'] == 'configuration' else record for record in source['assets']]}
    manifest.write_text(json.dumps(result, indent=2) + '\n')
    print('R12_RELEASE_READY=' + str(manifest), flush=True)


if __name__ == '__main__':
    export()
