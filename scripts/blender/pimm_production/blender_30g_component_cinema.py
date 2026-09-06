"""Component-anchored camera studies; never changes the approved CAD geometry."""
import argparse
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production import blender_master_storefront_render as studio
from scripts.blender.pimm_production.blender_collection_card_render import MASTER_HASHES

FPS = 24
FRAMES = 192
# Each shot has an explicit CAD anchor, lens, radius, azimuth and elevation move.
SHOTS = {
    'cylinder': ('30G__MDB125-200Z-0-_BODY__d7889d7dc749a14f', 1100, 65, (-16, -6), (5, 9)),
    'temperature': ('30G__Electronic-Box-Body__d49b1cfe3bdb231d', 700, 85, (12, 4), (3, 5)),
    'pressure': ('PIMM30_MASTER_Pressure_Gauge_Face', 520, 85, (-16, -8), (5, 5)),
    'mounting': ('30G__Base-Plate__bfa12d3b2a10cf6f', 1000, 65, (-28, -16), (48, 55)),
    'actuator': ('30G__MB125-200Z_ROD__01710571532bdd66', 1000, 80, (6, -4), (3, 7)),
    'complete': (None, 2300, 70, (-8, 8), (3, 3)),
}

def render(args):
    import bpy
    meshes, provenance = studio._validate_master(bpy, '30G', MASTER_HASHES['30G'])
    low, high = studio._world_bounds(meshes)
    runtime = studio._runtime_collection(bpy)
    studio._install_studio(bpy, runtime, low, high)
    studio._configure_render(bpy, 960, 1080, 32, args.output)
    scene = bpy.context.scene
    scene.render.film_transparent = True
    scene.render.use_persistent_data = True
    for obj in runtime.objects:
        if obj.type == 'MESH': obj.visible_camera = False
    camera = bpy.data.objects.new('CAM_COMPONENT_CINEMA', bpy.data.cameras.new('CAM_COMPONENT_CINEMA'))
    runtime.objects.link(camera)
    scene.camera = camera
    camera.data.type = 'PERSP'
    camera.data.clip_end = 20000
    camera.data.dof.use_dof = False
    scene.render.fps = FPS
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for name, (anchor, radius, lens, azimuth, elevation) in SHOTS.items():
        if args.shot and name != args.shot: continue
        bounds = studio._world_bounds([bpy.data.objects[anchor]]) if anchor else (low, high)
        target = [(bounds[0][i]+bounds[1][i])/2 for i in range(3)]
        # The piston CAD body includes the hidden head inside the cylinder.
        # Frame its exposed lower stroke, not that hidden mass's bounding center.
        if name == 'actuator': target[2] = 390
        if name == 'temperature': target[1] = -95
        camera.data.lens = lens
        indices = [0, 95, 191] if args.proof else range(FRAMES)
        for frame in indices:
            t = frame/(FRAMES-1)
            # Near-linear drift with gentle starts/ends, no mid-shot whip.
            ease = t*t*(3-2*t)
            u = .65*t + .35*ease
            az = math.radians(azimuth[0]+(azimuth[1]-azimuth[0])*u)
            el = math.radians(elevation[0]+(elevation[1]-elevation[0])*u)
            camera.location = (target[0]+radius*math.sin(az)*math.cos(el), target[1]-radius*math.cos(az)*math.cos(el), target[2]+radius*math.sin(el))
            studio._look_at(camera, target)
            path = args.output/f'{name}-{frame:03d}.png'
            if not path.exists():
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
            print(f'COMPONENT_FRAME {name} {frame+1}/{FRAMES}', flush=True)
        records.append({'shot':name,'anchor':anchor,'target':target,'radius':radius,'lens_mm':lens,'azimuth':azimuth,'elevation':elevation})
    (args.output/'render.json').write_text(json.dumps({'provenance':provenance,'shots':records,'fps':FPS,'frames_per_shot':FRAMES,'alpha':True,'samples':32},indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--proof',action='store_true')
    parser.add_argument('--shot',choices=SHOTS)
    render(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
    os._exit(0)
