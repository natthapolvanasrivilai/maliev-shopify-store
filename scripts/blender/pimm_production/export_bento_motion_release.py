"""Add the complete approved orbit without replacing approved r11 stills."""
import json
from pathlib import Path
import shutil

from scripts.blender.pimm_production.blender_bento_r10_final import OUTPUT
from scripts.blender.pimm_production.export_bento_r10_assets import final_for
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import REPO_ROOT


def export():
    destination = REPO_ROOT / 'assets'
    still_path = destination / 'pimm-bento-r11-stills.v1.json'
    still_hash = sha256_file(still_path)
    stills = json.loads(still_path.read_text())
    assert stills['generation'] == 'bento-20260903-r11-stills'
    assert len(stills['assets']) == 4
    for asset in stills['assets']:
        checked_file(destination / asset['filename'], asset['sha256'])
        checked_file(REPO_ROOT / asset['approval'], asset['approval_sha256'])
    orbit = final_for('controls-orbit')
    controls = next(asset for asset in stills['assets'] if asset['shot'] == 'controls')
    assert controls['native_sha256'] == orbit['frames'][0]['native_sha256']
    assert controls['scene_sha256'] == orbit['scene_sha256']
    name = 'pimm-bento-20260903-r10-30g-controls-orbit.mp4'
    source = OUTPUT / 'controls-orbit' / name
    video = json.loads(source.with_suffix('.json').read_text())
    required = {'approval_sha256': orbit['approval_sha256'], 'scene_sha256': orbit['scene_sha256'],
                'filename': name, 'size': orbit['size'], 'frames': 192, 'fps': 24, 'duration_ms': 8000}
    if any(video.get(key) != value for key, value in required.items()):
        raise ValueError('Incomplete or mismatched animation')
    manifest = OUTPUT / 'controls-orbit/final.json'
    if Path(video['path']).resolve() != source.resolve() or Path(video['native_manifest']).resolve() != manifest.resolve():
        raise ValueError('Wrong native source path')
    checked_file(manifest, video['native_manifest_sha256'])
    checked_file(source, video['sha256'])
    target = destination / name
    release = destination / 'pimm-bento-r11-motion.v1.json'
    if target.exists() or release.exists():
        raise FileExistsError('Motion release is immutable')
    shutil.copyfile(source, target)
    checked_file(target, video['sha256'])
    checked_file(still_path, still_hash)
    if final_for('controls-orbit') != orbit:
        raise ValueError('Native orbit changed during export')
    for asset in stills['assets']:
        checked_file(REPO_ROOT / asset['approval'], asset['approval_sha256'])
    result = {**stills, 'generation': 'bento-20260903-r11-motion',
              'stills_manifest': still_path.name, 'stills_manifest_sha256': still_hash,
              'scope': 'Approved r10 complete orbit with unchanged r11 white-studio still release',
              'animation': video}
    release.write_text(json.dumps(result, indent=2) + '\n')
    print('BENTO_MOTION_READY=' + str(release), flush=True)


if __name__ == '__main__':
    export()
