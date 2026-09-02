"""Native 24fps 30G reveal. Authoritative master is read-only; no composited shadows."""
import argparse
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production import blender_collection_card_render as card
from scripts.blender.pimm_production import blender_master_storefront_render as studio

RELEASE = 'pimm-30g-hero-reveal-20260902-r01'
FRAME_COUNT = 48


def frame_state(index):
    t = index / (FRAME_COUNT - 1)
    turn = t * t * (3 - 2 * t)
    light_t = min(1.0, t / .72)
    light = light_t * light_t * (3 - 2 * light_t)
    return {'angle': -12 * (1 - turn), 'light': .3 + .7 * light,
            'background': .75 + .25 * light}


def render(args):
    import bpy
    args.output = args.output.resolve()
    meshes, provenance = studio._validate_master(bpy, '30G', card.MASTER_HASHES['30G'])
    low, high = studio._world_bounds(meshes)
    runtime = studio._runtime_collection(bpy)
    studio._install_studio(bpy, runtime, low, high)
    card._collection_camera(bpy, runtime, low, high, 1.08)
    stage = card._collection_stage(bpy, runtime, meshes, tuple((a+b)/2 for a,b in zip(low, high)))
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise FileExistsError('Use a new empty render directory')
    card._configure_collection_render(bpy, 32 if args.proof else 128, args.output / RELEASE)
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = 1440, 1920
    scene.render.resolution_percentage = 50 if args.proof else 100
    scene.camera.data.dof.use_dof = False
    scene.render.fps = 24
    setters = {}
    for name in card.lighting_levels()[0]:
        if name in ('PIMM_HDRI_LIGHTING', 'PIMM_WHITE_CAMERA_BACKGROUND'):
            target = scene.world.node_tree.nodes[name].inputs['Strength']
            setters[name] = (target, 'default_value', target.default_value)
        elif name.startswith('REFLECTION_') or name == 'PIMM_WHITE_CYCLORAMA':
            material = bpy.data.objects[name].data.materials[0]
            node = next(n for n in material.node_tree.nodes if n.type == 'EMISSION')
            target = node.inputs['Strength']
            setters[name] = (target, 'default_value', target.default_value)
        else:
            target = bpy.data.objects[name].data
            setters[name] = (target, 'energy', target.energy)
    frames = []
    for index in ([0, 24, 47] if args.proof else range(FRAME_COUNT)):
        state = frame_state(index)
        stage.rotation_euler[2] = math.radians(state['angle'])
        for name, (target, attribute, initial) in setters.items():
            multiplier = state['background'] if name in ('PIMM_WHITE_CAMERA_BACKGROUND', 'PIMM_WHITE_CYCLORAMA') else state['light']
            setattr(target, attribute, initial * multiplier)
        bpy.context.view_layer.update()
        output = args.output / f'{RELEASE}-{index:03d}.png'
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)
        frames.append({'index': index, 'filename': output.name, 'sha256': studio.sha256_file(output), **state})
        print(f'HERO_REVEAL_FRAME {index + 1}/48', flush=True)
    result = {'release_id': RELEASE, 'proof': args.proof, 'fps': 24,
              'width': 1440, 'height': 1920, 'resolution_percentage': scene.render.resolution_percentage,
              'samples': scene.cycles.samples, 'exposure': scene.view_settings.exposure,
              'camera_scale': 1.08, 'provenance': provenance, 'frames': frames}
    (args.output / f'{RELEASE}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('HERO_REVEAL_COMPLETE', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--proof', action='store_true')
    render(parser.parse_args(sys.argv[sys.argv.index('--') + 1:]))
    os._exit(0)
