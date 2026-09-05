"""Approved technical-visualization proof using linked render layers, not material edits."""
import argparse
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_r10_final import contract_for
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT

GENERATION = 'bento-20260903-r17-tube-reveal'
FRAMES = 192
TARGETS = (
 '30G__30g---Injection-Tube__0cd746d4874417b8',
 '30G__Nozzle---R15---3mm-hole__d15912a35de6e11f',
 '30G__25mm-plug__73f62368111f1385',
 '30G__WMH13-20__1d9dd9392dffa764',
)


def reveal(frame):
    t = (frame - 1) / FRAMES
    if not 0 <= t <= 1:
        raise ValueError('Invalid frame')
    if t < .15 or t >= .9: return 0.0
    if t < .4: return (1 - math.cos(math.pi * (t-.15)/.25)) / 2
    if t < .65: return 1.0
    return (1 + math.cos(math.pi * (t-.65)/.25)) / 2


def layer_collection(root, name):
    if root.name == name: return root
    for child in root.children:
        found = layer_collection(child, name)
        if found: return found
    return None


def render(selected=None):
    import bpy
    source = contract_for('capacity')
    root = ASSET_ROOT / 'renders/proofs' / GENERATION
    scene_path = ASSET_ROOT / 'scenes/animations' / f'pimm-30g--{GENERATION}--capacity.blend'
    contract_path = ASSET_ROOT / 'scenes/contracts' / f'pimm-30g--{GENERATION}--capacity.json'
    if contract_path.exists():
        contract = json.loads(contract_path.read_text())
        checked_file(scene_path, contract['scene_sha256'])
        checked_file(Path(__file__), contract['script_sha256'])
        assert contract['source_scene_sha256'] == source['scene_sha256']
        bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    else:
        if root.exists() or scene_path.exists(): raise FileExistsError('Immutable proof generation exists')
        bpy.ops.wm.open_mainfile(filepath=source['scene_path'])
        scene = bpy.context.scene
        published = bpy.data.collections['PIMM_PUBLISHED']
        original = {o.name: {'mesh':o.data.name,'materials':[m.name for m in o.data.materials],
                             'matrix':[list(row) for row in o.matrix_world]}
                    for o in published.all_objects if o.type == 'MESH'}
        assert len(original) == 556
        focus = bpy.data.collections.new('TECHNICAL_INJECTION_TUBE_REFERENCES')
        scene.collection.children.link(focus)
        for name in TARGETS:
            obj = bpy.data.objects[name]
            assert obj.library and obj.data.library and not obj.override_library
            focus.objects.link(obj)  # Same linked datablock: no geometry or material copy.
        full = scene.view_layers[0]
        full.name = 'Physical machine'
        tube = scene.view_layers.new('Injection tube only')
        background = scene.view_layers.new('Physical studio')
        for layer in (tube, background):
            layer_collection(layer.layer_collection, 'PIMM_PUBLISHED').exclude = True
        layer_collection(full.layer_collection, focus.name).exclude = True
        layer_collection(background.layer_collection, focus.name).exclude = True
        tube.use_pass_cryptomatte_object = True
        tree = bpy.data.node_groups.new('PIMM_TECHNICAL_REVEAL', 'CompositorNodeTree')
        tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        def node(kind): return tree.nodes.new(kind)
        def connect(a, output, b, input): tree.links.new(a.outputs[output], b.inputs[input])
        full_node, tube_node, bg_node = [node('CompositorNodeRLayers') for _ in range(3)]
        for n, layer in ((full_node,full),(tube_node,tube),(bg_node,background)):
            n.scene, n.layer = scene, layer.name
        crypto = node('CompositorNodeCryptomatteV2')
        crypto.scene, crypto.layer_name = scene, tube.name + '.CryptoObject'
        crypto.matte_id = ','.join(TARGETS)
        ghost = node('ShaderNodeMix')
        ghost.data_type = 'RGBA'
        ghost.inputs[0].default_value = .20
        connect(bg_node,'Image',ghost,6)
        connect(full_node,'Image',ghost,7)
        opaque_tube = node('CompositorNodeSetAlpha')
        opaque_tube.inputs['Type'].default_value = 'Apply Mask'
        connect(tube_node,'Image',opaque_tube,'Image')
        connect(crypto,'Matte',opaque_tube,'Alpha')
        over = node('CompositorNodeAlphaOver')
        over.inputs['Factor'].default_value = 1
        connect(ghost,2,over,'Background')
        connect(opaque_tube,'Image',over,'Foreground')
        blend = node('ShaderNodeMix')
        blend.data_type = 'RGBA'
        blend.name = 'Technical reveal amount'
        connect(full_node,'Image',blend,6)
        connect(over,'Image',blend,7)
        output = node('NodeGroupOutput')
        connect(blend,2,output,'Image')
        scene.compositing_node_group = tree
        original_scale = scene.camera.data.ortho_scale
        for frame in range(1, FRAMES + 2):
            blend.inputs[0].default_value = reveal(frame)
            blend.inputs[0].keyframe_insert(data_path='default_value', frame=frame)
            scene.camera.data.ortho_scale = original_scale * (1 - .35 * reveal(frame))
            scene.camera.data.keyframe_insert(data_path='ortho_scale', frame=frame)
        scene.frame_start, scene.frame_end = 1, FRAMES
        scene.render.fps, scene.render.fps_base = 24, 1
        scene.frame_set(1)
        root.mkdir(parents=True)
        scene.render.filepath = str(root / 'frame-')
        assert scene.render.resolution_percentage == 100 and scene.cycles.samples == 128
        bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
        contract = dict(source, generation=GENERATION, approval='pending',
                        scene_path=str(scene_path), scene_sha256=sha256_file(scene_path),
                        source_scene_sha256=source['scene_sha256'], script_sha256=sha256_file(Path(__file__)),
                        owner_direction='Show only these 4 components. The rest reduced opacity.',
                        component_mapping={'50g injection tube':'30g injection tube', '30mm plug':'25mm plug',
                                           'Nozzle R15 3mm hole':'Nozzle R15 3mm hole', 'WMH13-20':'WMH13-20'},
                        technical_visualization=True, focus_objects=list(TARGETS),
                        ghost_opacity=.2, camera_scale_min=.65, original_product=original, proof_percentage=25, proof_samples=32,
                        motion={'type':'Blender-render-layer-opacity','frames':FRAMES,'fps':24,'machine_motion':False},
                        proofs=[])
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    scene = bpy.context.scene
    for obj in bpy.data.collections['PIMM_PUBLISHED'].all_objects:
        if obj.type != 'MESH': continue
        assert obj.library and obj.data.library and not obj.override_library and not obj.animation_data
        before = contract['original_product'][obj.name]
        assert before['materials'] == [m.name for m in obj.data.materials]
        assert before['matrix'] == [list(row) for row in obj.matrix_world]
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.refresh_devices()
    preferences.compute_device_type = 'OPTIX'
    for device in preferences.devices: device.use = device.type == 'OPTIX'
    scene.render.resolution_percentage = 25
    scene.cycles.samples = 32
    records = {r['frame']:r for r in contract['proofs']}
    for frame in selected or range(1,FRAMES+1):
        path = root / f'frame-{frame:04d}.png'
        if frame in records:
            checked_file(path,records[frame]['sha256']); continue
        if path.exists(): raise FileExistsError('Unreceipted proof frame')
        scene.frame_set(frame)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        records[frame] = {'frame':frame,'path':str(path),'sha256':sha256_file(path)}
        contract['proofs'] = [records[k] for k in sorted(records)]
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        print(f'TUBE_REVEAL_FRAME={frame}',flush=True)
    contract_for('capacity')
    print('TUBE_REVEAL_READY='+str(contract_path),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--frames', nargs='+', type=int)
    render(parser.parse_args(sys.argv[sys.argv.index('--')+1:]).frames)
    os._exit(0)
