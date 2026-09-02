"""Encode verified Blender frames at 24fps; no synthesized frames or compositing."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_collection_card_render import MASTER_HASHES, motion_angles

RELEASE = 'maliev-pimm-collection-motion-20260902-r01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def publish(render_dir, asset_dir):
    sources = []
    manifest_path = asset_dir / f'{RELEASE}-assets.v1.json'
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    for model in ['30g', '50g']:
        prefix = f'{RELEASE}-{model}'
        source = json.loads((render_dir / f'{prefix}.json').read_text())
        if source['fps'] != 24 or source['frame_count'] != 72 or len(source['frames']) != 72:
            raise ValueError('Motion must contain 72 native frames at 24fps')
        if source['machine'].lower() != model or source['release_id'] != RELEASE:
            raise ValueError('Wrong model or release')
        if source.get('provenance', {}).get('master_sha256') != MASTER_HASHES[model.upper()]:
            raise ValueError('Untrusted master provenance')
        for index, frame in enumerate(source['frames']):
            expected = f'{prefix}-{index:03d}.png'
            if frame['filename'] != expected or frame['index'] != index:
                raise ValueError('Frame sequence mismatch')
            if abs(frame['angle_degrees'] - motion_angles()[index]) > 0.000001:
                raise ValueError('Physical rotation sequence mismatch')
            path = render_dir / expected
            if sha(path) != frame['sha256']:
                raise ValueError(f'Frame hash mismatch: {path}')
            with Image.open(path) as image:
                if image.size != (720, 960):
                    raise ValueError('Frame dimensions mismatch')
        for suffix in ['.mp4', '-poster.webp']:
            if (asset_dir / f'{prefix}{suffix}').exists():
                raise FileExistsError(f'{prefix}{suffix}')
        sources.append(source)
    for source in sources:
        prefix = f"{RELEASE}-{source['machine'].lower()}"
        video = asset_dir / f'{prefix}.mp4'
        poster = asset_dir / f'{prefix}-poster.webp'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
            '-framerate', '24', '-i', str(render_dir / f'{prefix}-%03d.png'),
            '-frames:v', '72', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '17',
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)], check=True)
        probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error',
            '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate,nb_frames,duration',
            '-of', 'json', str(video)]))['streams'][0]
        if probe != {'width': 720, 'height': 960, 'r_frame_rate': '24/1', 'duration': '3.000000', 'nb_frames': '72'}:
            raise ValueError(f'Encoded video violates playback contract: {probe}')
        with Image.open(render_dir / source['frames'][0]['filename']) as image:
            image.convert('RGB').save(poster, 'WEBP', lossless=True, method=6)
        source['video'] = {'filename': video.name, 'sha256': sha(video), **probe}
        source['poster'] = {'filename': poster.name, 'sha256': sha(poster)}
    manifest = {'schema_version': 1, 'release_id': RELEASE,
                'shadow_source': 'Native Blender Cycles physical studio floor',
                'assets': sources}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(manifest_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--render-dir', type=Path, required=True)
    parser.add_argument('--asset-dir', type=Path, default=Path('assets'))
    args = parser.parse_args()
    publish(args.render_dir, args.asset_dir)
