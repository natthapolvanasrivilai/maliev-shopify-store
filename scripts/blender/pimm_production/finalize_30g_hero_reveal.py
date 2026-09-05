"""Encode verified native frames; no interpolation, relighting, or shadow editing."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_30g_hero_reveal import RELEASE, FRAME_COUNT, frame_state
from scripts.blender.pimm_production.blender_collection_card_render import MASTER_HASHES
from scripts.blender.pimm_production.finalize_collection_motion import sha


def publish(source, assets):
    data = json.loads((source / f'{RELEASE}.json').read_text())
    assert data['release_id'] == RELEASE and data['proof'] is False
    assert data['resolution_percentage'] == 100 and data['samples'] >= 128
    assert data['width'] == 1440 and data['height'] == 1920 and data['fps'] == 24
    assert data['provenance']['master_sha256'] == MASTER_HASHES['30G']
    assert len(data['frames']) == FRAME_COUNT
    for i, frame in enumerate(data['frames']):
        assert frame['index'] == i and frame['filename'] == f'{RELEASE}-{i:03d}.png'
        assert all(frame[k] == v for k,v in frame_state(i).items())
        path = source / frame['filename']
        assert sha(path) == frame['sha256']
        with Image.open(path) as image:
            assert image.size == (1440,1920)
    targets = [assets / f'{RELEASE}{suffix}' for suffix in ['.mp4','-rest.webp','-start.webp','.json']]
    if any(path.exists() for path in targets):
        raise FileExistsError('Refusing to overwrite a hero release')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-framerate','24',
        '-i',str(source / f'{RELEASE}-%03d.png'),'-frames:v',str(FRAME_COUNT),'-an',
        '-c:v','libx264','-preset','slow','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(targets[0])],check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height,r_frame_rate,nb_frames,duration','-of','json',str(targets[0])]))['streams'][0]
    assert probe == {'width':1440,'height':1920,'r_frame_rate':'24/1','duration':'2.000000','nb_frames':'48'}
    for target,index in [(targets[1],47),(targets[2],0)]:
        with Image.open(source / data['frames'][index]['filename']) as image:
            image.convert('RGB').save(target,'WEBP',lossless=True,method=6)
    data['outputs']=[{'filename':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in targets[:3]]
    data['video']=probe
    targets[-1].write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print('Verified native hero release published to local assets')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--assets',type=Path,default=Path('assets'))
    args=parser.parse_args()
    publish(args.source,args.assets)
