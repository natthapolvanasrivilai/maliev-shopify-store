"""Four native perspective camera studies, with transparent studio output.

The approved master is validated and never saved or modified on disk.
"""
import argparse
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production import blender_master_storefront_render as studio
from scripts.blender.pimm_production.blender_collection_card_render import MASTER_HASHES

SHOTS = {
    'drive': (.76, .66, -26, 22, .07),
    'control': (.57, .66, 30, -18, .10),
    'tooling': (.32, .60, -24, 28, .18),
    'complete': (.49, 1.18, -18, 18, .045),
}

def render(args):
    import bpy
    meshes, provenance = studio._validate_master(bpy, '30G', MASTER_HASHES['30G'])
    low, high = studio._world_bounds(meshes)
    runtime = studio._runtime_collection(bpy)
    studio._install_studio(bpy, runtime, low, high)
    studio._configure_render(bpy, 960, 1080, 48, args.output)
    scene = bpy.context.scene
    scene.render.film_transparent = True
    # Lighting stays physical, while the machine alpha exposes the live type layer.
    for obj in runtime.objects:
        if obj.type == 'MESH':
            obj.visible_camera = False
    camera = bpy.data.objects.new('CAM_CINEMATIC_HERO', bpy.data.cameras.new('CAM_CINEMATIC_HERO'))
    runtime.objects.link(camera)
    scene.camera = camera
    camera.data.type = 'PERSP'
    camera.data.lens = 70
    camera.data.clip_end = 20000
    camera.data.dof.use_dof = False
    scene.render.fps = 24
    height = high[2] - low[2]
    cx, cy = (low[0] + high[0]) / 2, (low[1] + high[1]) / 2
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for name, (level, span, start, end, elevation) in SHOTS.items():
        target = (cx, cy, low[2] + height * level)
        distance = height * span * 2.12
        indices = [0, 47, 95] if args.proof else range(96)
        for frame in indices:
            t = frame / 95
            angle = math.radians(start + (end - start) * (t*t*(3-2*t)))
            camera.location = (cx + math.sin(angle)*distance, cy - math.cos(angle)*distance, target[2] + height*elevation)
            studio._look_at(camera, target)
            path = args.output / f'{name}-{frame:03d}.png'
            if not path.exists():
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
            print(f'CINEMATIC_FRAME {name} {frame+1}/96', flush=True)
        records.append({'shot': name, 'target_height': level, 'span': span, 'orbit': [start,end]})
    (args.output / 'render.json').write_text(json.dumps({'provenance': provenance, 'shots': records, 'fps':24, 'frames_per_shot':96, 'alpha':True}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--proof', action='store_true')
    render(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
    os._exit(0)
