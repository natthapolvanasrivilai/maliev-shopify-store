"""Author an immutable camera-only 360 configuration proof from approved r12."""
import argparse
import itertools
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_white_detail_final import detail_contract, APPROVAL
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
from scripts.blender.pimm_production import blender_master_storefront_render as studio
from scripts.blender.pimm_production.tool_policy import LOCK_PATH, validate_tool_lock

FRAMES = 120
FPS = 24
GENERATION = 'bento-20260903-r14-configuration-spin'


def angle(frame):
    if not 1 <= frame <= FRAMES + 1:
        raise ValueError('Frame outside authored 360 cycle')
    return 2 * math.pi * (frame - 1) / FRAMES


def render(generation=GENERATION, frames=None):
    import bpy
    from mathutils import Matrix, Vector
    from bpy_extras.object_utils import world_to_camera_view

    if not generation.startswith('bento-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in generation):
        raise ValueError('Invalid immutable proof generation')
    source = detail_contract('configuration')
    lock_errors = validate_tool_lock(json.loads(LOCK_PATH.read_text()))
    if lock_errors:
        raise ValueError(lock_errors)
    root = require_within(ASSET_ROOT / 'renders/proofs' / generation, ASSET_ROOT / 'renders/proofs')
    scene_path = ASSET_ROOT / 'scenes/animations' / f'pimm-30g--{generation}--configuration.blend'
    contract_path = ASSET_ROOT / 'scenes/contracts' / f'pimm-30g--{generation}--configuration.json'
    selected = frames or list(range(1, FRAMES + 1))
    if len(selected) != len(set(selected)) or any(not 1 <= frame <= FRAMES for frame in selected):
        raise ValueError('Invalid selected proof frames')
    if contract_path.exists():
        contract = json.loads(contract_path.read_text())
        checked_file(scene_path, contract['scene_sha256'])
        checked_file(Path(__file__), contract['script_sha256'])
        checked_file(APPROVAL, contract['source_approval_sha256'])
        if contract['source_scene_sha256'] != source['scene_sha256']:
            raise ValueError('Source changed')
        bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    else:
        if root.exists() or scene_path.exists():
            raise FileExistsError('Unreceipted generation; do not overwrite')
        bpy.ops.wm.open_mainfile(filepath=source['scene_path'])
        scene = bpy.context.scene
        product = bpy.data.collections['PIMM_PUBLISHED']
        meshes = [obj for obj in product.all_objects if obj.type == 'MESH']
        assert len(meshes) == 556 and all(obj.library and obj.data.library and not obj.override_library for obj in meshes)
        assert all(not obj.animation_data for obj in product.all_objects)
        low, high = studio._world_bounds(meshes)
        pivot = Vector(((low[0]+high[0])/2, (low[1]+high[1])/2, (low[2]+high[2])/2))
        camera = scene.camera
        assert camera and not camera.library and not camera.animation_data
        original = camera.matrix_world.copy()
        original_scale = camera.data.ortho_scale
        assert camera.data.type == 'ORTHO'
        projection = []
        corners = [Vector(c) for c in itertools.product(*zip(low, high))]
        for frame in range(1, FRAMES + 2):
            scene.frame_set(frame)
            transform = Matrix.Translation(pivot) @ Matrix.Rotation(angle(frame), 4, 'Z') @ Matrix.Translation(-pivot)
            # Avoid float32 sin(2*pi) drift in this millimetre-scale scene.
            camera.matrix_world = original if frame == FRAMES + 1 else transform @ original
            camera.keyframe_insert(data_path='location', frame=frame)
            camera.keyframe_insert(data_path='rotation_euler', frame=frame)
            bpy.context.view_layer.update()
            points = [world_to_camera_view(scene, camera, c) for c in corners]
            projection.append([min(p.x for p in points), min(p.y for p in points), max(p.x for p in points), max(p.y for p in points)])
        # Product stays to the right of fixed text at every angle. No per-frame crop or scale.
        bounds = [min(p[0] for p in projection), min(p[1] for p in projection), max(p[2] for p in projection), max(p[3] for p in projection)]
        if bounds[0] < .45 or bounds[1] < .025 or bounds[2] > .995 or bounds[3] > .985:
            raise ValueError(f'Full orbit exceeds safe image rectangle: {bounds}')
        scene.frame_start, scene.frame_end = 1, FRAMES
        scene.render.fps, scene.render.fps_base = FPS, 1
        scene.frame_set(1)
        assert camera.data.ortho_scale == original_scale
        scene.render.resolution_percentage = 100
        assert [scene.render.resolution_x, scene.render.resolution_y] == [2400, 1200]
        root.mkdir(parents=True)
        scene.render.filepath = str(root / 'frame-')
        bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
        contract = dict(source, generation=generation, approval='pending', scene_path=str(scene_path),
                        scene_sha256=sha256_file(scene_path), source_scene_sha256=source['scene_sha256'],
                        source_approval_sha256=sha256_file(APPROVAL), script_sha256=sha256_file(Path(__file__)),
                        motion={'type':'camera-only-360','frames':FRAMES,'fps':FPS,'step_degrees':3,
                                'machine_motion':False,'pivot':list(pivot),'controller_values':'unchanged 300/300'},
                        projected_union=bounds, proof_percentage=25, proof_samples=32,
                        proof_path=str(root), proofs=[])
        contract_path.write_text(json.dumps(contract, indent=2)+'\n')
        bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    scene = bpy.context.scene
    product = bpy.data.collections['PIMM_PUBLISHED']
    assert all(not obj.animation_data and not obj.override_library for obj in product.all_objects)
    assert [obj for obj in scene.objects if obj.animation_data] == [scene.camera]
    scene.frame_set(1)
    start = scene.camera.matrix_world.copy()
    scene.frame_set(FRAMES + 1)
    assert max(abs(start[r][c] - scene.camera.matrix_world[r][c]) for r in range(4) for c in range(4)) < .00001
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.refresh_devices()
    backend = next((name for name in ('OPTIX','CUDA') if any(d.type == name for d in preferences.devices)), None)
    if not backend:
        raise RuntimeError('Approved GPU unavailable')
    preferences.compute_device_type = backend
    for device in preferences.devices:
        device.use = device.type == backend
    scene.render.resolution_percentage = 25
    scene.cycles.samples = 32
    scene.cycles.adaptive_threshold = .03
    records = {record['frame']: record for record in contract['proofs']}
    for frame in selected:
        path = root / f'frame-{frame:04d}.png'
        if frame in records:
            checked_file(path, records[frame]['sha256'])
            continue
        if path.exists():
            raise FileExistsError(f'Unreceipted proof {path}')
        scene.frame_set(frame)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        records[frame] = {'frame':frame,'path':str(path),'sha256':sha256_file(path)}
        contract['proofs'] = [records[key] for key in sorted(records)]
        contract_path.write_text(json.dumps(contract, indent=2)+'\n')
        print(f'SPIN_PROOF_FRAME={frame}/{FRAMES}',flush=True)
    detail_contract('configuration')
    checked_file(scene_path, contract['scene_sha256'])
    print('SPIN_PROOF_READY=' + str(contract_path), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--generation', default=GENERATION)
    parser.add_argument('--frames', nargs='+', type=int)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    render(args.generation, args.frames)
    os._exit(0)
