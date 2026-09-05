"""Package native Cycles lighting frames, forward/reversed; never composite pixels."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_collection_card_render import (
    LIGHTING_RELEASE, MASTER_HASHES, MOTION_DIMENSIONS, lighting_levels,
)
from scripts.blender.pimm_production.finalize_collection_motion import sha


def validate(source, model, render_dir):
    prefix = f'{LIGHTING_RELEASE}-{model}'
    if source['release_id'] != LIGHTING_RELEASE or source['machine'].lower() != model:
        raise ValueError('Wrong lighting release or model')
    if source.get('proof') is not False or source.get('resolution_percentage') != 100:
        raise ValueError('Proof renders cannot be published')
    if source['fps'] != 24 or source['frame_count'] != 12 or len(source['frames']) != 12:
        raise ValueError('Lighting requires twelve native frames at 24fps')
    if (source['width'], source['height']) != MOTION_DIMENSIONS or source['samples'] < 128:
        raise ValueError('Lighting requires native 1440x1920 at 128 samples or higher')
    if source['provenance']['master_sha256'] != MASTER_HASHES[model.upper()]:
        raise ValueError('Untrusted master provenance')
    if abs(source['exposure'] + .15) > .000001 or source['camera_scale'] != 1.24:
        raise ValueError('Exposure and framing must match the bright motion')
    for index, frame in enumerate(source['frames']):
        if frame['index'] != index or frame['filename'] != f'{prefix}-{index:03d}.png':
            raise ValueError('Lighting frame sequence mismatch')
        if frame['emitters'] != lighting_levels()[index]:
            raise ValueError('Physical emitter ramp mismatch')
        path = render_dir / frame['filename']
        if sha(path) != frame['sha256']:
            raise ValueError('Lighting frame hash mismatch')
        with Image.open(path) as image:
            if image.size != MOTION_DIMENSIONS:
                raise ValueError('Lighting frame resolution mismatch')


def publish(render_dir, asset_dir):
    manifest_path = asset_dir / f'{LIGHTING_RELEASE}-assets.v1.json'
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    sources = []
    for model in ['30g', '50g']:
        prefix = f'{LIGHTING_RELEASE}-{model}'
        source = json.loads((render_dir / f'{prefix}.json').read_text())
        validate(source, model, render_dir)
        for suffix in ['-down.mp4', '-up.mp4', '-dim.webp']:
            if (asset_dir / f'{prefix}{suffix}').exists():
                raise FileExistsError(f'{prefix}{suffix}')
        sources.append(source)
    for source in sources:
        prefix = f"{LIGHTING_RELEASE}-{source['machine'].lower()}"
        for direction in ['down', 'up']:
            video = asset_dir / f'{prefix}-{direction}.mp4'
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
                '-framerate', '24', '-i', str(render_dir / f'{prefix}-%03d.png'),
                *(['-vf', 'reverse'] if direction == 'up' else []),
                '-frames:v', '12', '-an', '-c:v', 'libx264', '-preset', 'slow',
                '-crf', '15', '-g', '1', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                str(video)], check=True)
            probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error',
                '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate,nb_frames,duration',
                '-of', 'json', str(video)]))['streams'][0]
            if probe != {'width': 1440, 'height': 1920, 'r_frame_rate': '24/1', 'duration': '0.500000', 'nb_frames': '12'}:
                raise ValueError(f'Invalid native lighting video: {probe}')
            source[direction] = {'filename': video.name, 'sha256': sha(video), **probe}
        poster = asset_dir / f'{prefix}-dim.webp'
        with Image.open(render_dir / source['frames'][-1]['filename']) as image:
            image.convert('RGB').save(poster, 'WEBP', lossless=True, method=6)
        source['dim'] = {'filename': poster.name, 'sha256': sha(poster)}
    manifest_path.write_text(json.dumps({'schema_version': 1,
        'release_id': LIGHTING_RELEASE,
        'lighting_source': 'Native Blender Cycles emitter powers; fixed exposure; no image overlays or filters',
        'reverse_source': 'Exact reversed native frames; no interpolation',
        'assets': sources}, indent=2) + '\n', encoding='utf-8')
    print(manifest_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--render-dir', type=Path, required=True)
    parser.add_argument('--asset-dir', type=Path, default=Path('assets'))
    args = parser.parse_args()
    publish(args.render_dir, args.asset_dir)
