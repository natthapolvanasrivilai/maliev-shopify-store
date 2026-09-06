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
PROFILES = {'legacy': (960, 1080), 'desktop': (1920, 1080), 'mobile': (1080, 1920), 'material-proof': (960, 540), 'motion-proof': (640, 360)}
# Each shot has an explicit CAD anchor, lens, radius, azimuth and elevation move.
SHOTS = {
    'cylinder': ('30G__MDB125-200Z-0-_BODY__d7889d7dc749a14f', 1100, 65, (-16, -6), (5, 9)),
    'temperature': ('30G__Electronic-Box-Body__d49b1cfe3bdb231d', 700, 85, (12, 4), (3, 5)),
    'pressure': ('PIMM30_MASTER_Pressure_Gauge_Face', 520, 85, (-16, -8), (5, 5)),
    'mounting': ('30G__Base-Plate__bfa12d3b2a10cf6f', 1000, 65, (-28, -16), (48, 55)),
    'actuator': ('30G__MB125-200Z_ROD__01710571532bdd66', 1000, 80, (6, -4), (3, 7)),
    'complete': (None, 2300, 70, (-8, 8), (3, 3)),
}

def stabilize_decal(bpy):
    """Runtime-only stand-off; preserve master geometry, UVs and artwork."""
    decal=bpy.data.objects['PIMM30_MASTER_AirTAC_Decal']
    if not decal.get('pimm_cinema_decal_stabilized'):
        normal=(decal.matrix_world.to_3x3().inverted().transposed()@decal.data.polygons[0].normal).normalized()
        transform=decal.matrix_world.copy();transform.translation+=normal*.25
        decal.matrix_world=transform
        decal['pimm_cinema_decal_stabilized']=True

def render(args):
    import bpy
    meshes, provenance = studio._validate_master(bpy, '30G', MASTER_HASHES['30G'])
    stabilize_decal(bpy)
    low, high = studio._world_bounds(meshes)
    runtime = studio._runtime_collection(bpy)
    studio._install_studio(bpy, runtime, low, high)
    width, height = PROFILES[args.profile]
    studio._configure_render(bpy, width, height, args.samples, args.output)
    scene = bpy.context.scene
    if args.profile == 'motion-proof':
        scene.render.engine = 'BLENDER_EEVEE'
        scene.eevee.taa_render_samples = 8
    scene.render.film_transparent = True
    scene.render.use_persistent_data = True
    for obj in runtime.objects:
        if obj.type == 'MESH': obj.visible_camera = False
    camera = bpy.data.objects.new('CAM_COMPONENT_CINEMA', bpy.data.cameras.new('CAM_COMPONENT_CINEMA'))
    runtime.objects.link(camera)
    scene.camera = camera
    camera.data.type = 'PERSP'
    camera.data.clip_start = 10
    camera.data.clip_end = 20000
    camera.data.dof.use_dof = False
    # Preserve vertical composition while revealing the wider desktop frame.
    # Native profile renders avoid enlarging the old portrait raster with cover.
    if args.profile != 'legacy':
        camera.data.sensor_fit = 'VERTICAL'
        camera.data.sensor_height = 36
    scene.render.fps = FPS
    args.output.mkdir(parents=True, exist_ok=True)
    operations = None
    shots = SHOTS
    if args.operations:
        from scripts.blender.pimm_production.pimm_operating_motion import Operations
        operations = Operations(bpy)
        shots = {name: SHOTS[name] for name in ('cylinder','pressure','temperature','mounting')}
        shots['pressure'] = (SHOTS['pressure'][0], 360, 85, (-16,-8), (5,5))
        shots['mounting'] = (SHOTS['mounting'][0], 700, 70, (-25,-15), (15,20))
        shots['pellets'] = ('30G__30g---Injection-Tube__0cd746d4874417b8', 600, 65, (-16,-8), (20,25))
        shots.update({name:SHOTS[name] for name in ('actuator','complete')})
    records = []
    frame_count = 288 if args.operations else FRAMES
    for name, (anchor, radius, lens, azimuth, elevation) in shots.items():
        if args.shot and name != args.shot: continue
        bounds = studio._world_bounds([bpy.data.objects[anchor]]) if anchor else (low, high)
        target = [(bounds[0][i]+bounds[1][i])/2 for i in range(3)]
        # The piston CAD body includes the hidden head inside the cylinder.
        # Frame its exposed lower stroke, not that hidden mass's bounding center.
        if name == 'actuator': target[2] = 390
        if name == 'temperature': target[1] = -95
        if name == 'pellets': target[2] = 325
        if name == 'mounting' and args.operations: target[2] = 90
        camera.data.lens = lens
        indices = [round(t*(frame_count-1)) for t in (0,.2,.4,.6,.8,1)] if args.proof else range(0,frame_count,args.frame_step)
        if args.proof and name == 'pellets':
            indices = [round(t*(frame_count-1)) for t in (0,.07,.2,.6,.92,1)]
        for frame in indices:
            t = frame/(frame_count-1)
            if name == 'pellets':
                # A hollow glass tube crosses four interfaces; allow refraction
                # paths to exit instead of terminating inside the glass wall.
                scene.cycles.max_bounces = 20
                scene.cycles.transmission_bounces = 16
                scene.cycles.transparent_max_bounces = 16
                scene.cycles.film_transparent_glass = True
                scene.cycles.film_transparent_roughness = .2
            if operations: operations.apply(name,t)
            bpy.context.view_layer.update()
            # Near-linear drift with gentle starts/ends, no mid-shot whip.
            ease = t*t*(3-2*t)
            u = .65*t + .35*ease
            az = math.radians(azimuth[0]+(azimuth[1]-azimuth[0])*u)
            el = math.radians(elevation[0]+(elevation[1]-elevation[0])*u)
            camera.location = (target[0]+radius*math.sin(az)*math.cos(el), target[1]-radius*math.cos(az)*math.cos(el), target[2]+radius*math.sin(el))
            studio._look_at(camera, target)
            image_index = frame if args.proof else frame//args.frame_step
            path = args.output/f'{name}-{image_index:03d}.png'
            if not path.exists():
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
            print(f'COMPONENT_FRAME {name} {frame+1}/{frame_count}', flush=True)
        records.append({'shot':name,'anchor':anchor,'target':target,'radius':radius,'lens_mm':lens,'azimuth':azimuth,'elevation':elevation})
    (args.output/'render.json').write_text(json.dumps({'provenance':provenance,'shots':records,'fps':FPS,'frames_per_shot':frame_count,'frame_step':args.frame_step,'operations':args.operations,'alpha':True,'samples':args.samples,'profile':args.profile,'width':width,'height':height},indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--proof',action='store_true')
    parser.add_argument('--shot',choices=(*SHOTS,'pellets'))
    parser.add_argument('--profile',choices=PROFILES,default='legacy')
    parser.add_argument('--samples',type=int,default=48)
    parser.add_argument('--operations',action='store_true')
    parser.add_argument('--frame-step',type=int,default=1)
    render(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
    os._exit(0)
