"""Create a new immutable interaction review; keep reviewed image bytes unchanged."""
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT, require_within


def refresh():
    source = ASSET_ROOT / 'renders/proofs/bento-20260903-r25-web-interaction-review'
    destination = ASSET_ROOT / 'renders/proofs/bento-20260903-r26-smooth-drag-review'
    if destination.exists():
        raise FileExistsError('Immutable review generation already exists')
    manifest = source / 'web-review.json'
    snapshot = sha256_file(manifest)
    data = json.loads(manifest.read_text())
    if data['not_final'] is not True or len(data['frames']) != 840:
        raise ValueError('Expected complete proof-only web frame set')
    for record in data['files'] + data['frames']:
        checked_file(require_within(source / record['filename'], source), record['sha256'])
    shutil.copytree(source, destination)
    shutil.copyfile(REPO_ROOT / 'assets/pimm-bento-spin.js', destination / 'pimm-bento-spin.js')
    data['generation'] = destination.name
    data['source_web_review_sha256'] = snapshot
    for record in data['files']:
        if record['filename'] == 'pimm-bento-spin.js':
            record['sha256'] = sha256_file(destination / record['filename'])
    for record in data['files'] + data['frames']:
        checked_file(require_within(destination / record['filename'], destination), record['sha256'])
    checked_file(manifest, snapshot)
    (destination / 'web-review.json').write_text(json.dumps(data, indent=2) + '\n')
    print('SMOOTH_DRAG_REVIEW=' + str(destination))


if __name__ == '__main__':
    refresh()
