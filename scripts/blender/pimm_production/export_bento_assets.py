"""Create native-size, lossless WebP derivatives of approved Blender finals."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_final import APPROVAL, approved_contract, checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT


def export():
    from PIL import Image
    assets = []
    generation = 'bento-20260903-r06'
    for shot in ('capacity', 'controls', 'tooling', 'configuration'):
        contract = approved_contract(shot)
        stem = f'pimm-{generation}-30g-{shot}'
        receipt = json.loads((ASSET_ROOT / f'renders/final/{generation}-native2/{stem}.json').read_text())
        if receipt['approval_sha256'] != sha256_file(APPROVAL):
            raise ValueError('Approval changed after native rendering')
        native = checked_file(receipt['native_path'], receipt['native_sha256'])
        destination = REPO_ROOT / 'assets' / f'{stem}.webp'
        if destination.exists():
            raise FileExistsError(destination)
        with Image.open(native) as image:
            if list(image.size) != contract['native_size']:
                raise ValueError('Native dimensions do not match approval')
            image.convert('RGB').save(destination, 'WEBP', lossless=True, method=6)
        assets.append({**receipt, 'filename': destination.name,
                       'sha256': sha256_file(destination), 'bytes': destination.stat().st_size})
    manifest = REPO_ROOT / 'assets/pimm-bento-assets.v1.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'generation': generation,
        'approval': 'docs/pimm-blender-governance/bento-20260903-r06-approval.json',
        'encoding': 'native-size lossless RGB WebP from approved Blender PNG',
        'assets': assets}, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {len(assets)} native-size bento images')


if __name__ == '__main__':
    export()
