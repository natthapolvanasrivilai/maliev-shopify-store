"""Immutable camera-only two-axis and tooling-tilt proof scenes; no native release."""
import argparse
import itertools
import json
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.blender_bento_white_detail_final import detail_contract, APPROVAL as WHITE_APPROVAL
from scripts.blender.pimm_production.blender_bento_r10_final import contract_for, APPROVAL as R10_APPROVAL
from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
from scripts.blender.pimm_production import blender_master_storefront_render as studio
from scripts.blender.pimm_production.tool_policy import LOCK_PATH, validate_tool_lock

GENERATION = 'bento-20260903-r15-camera-previews'
YAW_FRAMES = 120
ELEVATIONS = (-6, -4, -2, 0, 2, 4, 6)
TILT_FRAMES = 192
FPS = 24
PLATE_ID = '30G-bfa12d3b2a10cf6f'
PLATE_GEOMETRY = '83de48e41943fc3414e708d23fafee0b104ead498174a712ba8c6c3be2526ebe'


def angles(index):
    if not isinstance(index, int) or not 1 <= index <= YAW_FRAMES * len(ELEVATIONS):
        raise ValueError('Invalid two-axis pose index')
    row, yaw = divmod(index - 1, YAW_FRAMES)
    return math.radians(yaw * 3), math.radians(ELEVATIONS[row])


def tilt(index):
    if not isinstance(index, int) or not 1 <= index <= TILT_FRAMES + 1:
        raise ValueError('Invalid tooling frame')
    return math.radians(3) * math.sin(math.tau * (index - 1) / TILT_FRAMES)


def selected_frames(shot, frames):
    count = YAW_FRAMES * len(ELEVATIONS) if shot == 'configuration' else TILT_FRAMES
    selected = list(range(1, count + 1)) if frames is None else frames
    if not selected or len(set(selected)) != len(selected) or any(type(i) is not int or not 1 <= i <= count for i in selected):
        raise ValueError('Invalid proof frame selection')
    return selected


def plate_pivot(product):
    """Verify imported plate identity and an open central hole, not a guessed target."""
    from mathutils import Vector
    candidates = [o for o in product.all_objects if o.get('pimm_stable_id') == PLATE_ID]
    if len(candidates) != 1:
        raise ValueError('Expected authoritative base plate identity')
    plate = candidates[0]
    if plate.get('pimm_geometry_signature') != PLATE_GEOMETRY:
        raise ValueError('Base plate geometry authority changed')
    low, high = studio._world_bounds([plate])
    pivot = Vector(((low[0] + high[0])/2, (low[1] + high[1])/2, high[2]))
    inverse = plate.matrix_world.inverted()
    direction = (inverse.to_3x3() @ Vector((0, 0, -1))).normalized()
    def intersects(x, y):
        origin = inverse @ (pivot + Vector((x, y, 50)))
        return plate.ray_cast(origin, direction)[0]
    # The native mesh has a central through-hole: center/6 mm radius open,
    # neighboring 10 mm cardinal positions solid. No geometry is altered.
    rays = {f'{x},{y}': intersects(x, y) for x, y in ((0,0),(6,0),(-6,0),(0,6),(0,-6),(10,0),(-10,0),(0,10),(0,-10))}
    if any(list(rays.values())[:5]) or not all(list(rays.values())[5:]):
        raise ValueError(f'Central hole verification failed: {rays}')
    return pivot, {'stable_id': PLATE_ID, 'geometry_signature': PLATE_GEOMETRY, 'hole_rays': rays, 'surface_center': list(pivot)}


def camera_pose(original, pivot, shot, index):
    from mathutils import Matrix, Vector
    if shot == 'configuration':
        yaw, pitch = angles(index)
        # Rigid camera orbit preserves the pivot's exact projected position,
        # including the approved right-hand placement beside fixed text.
        rotation = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(pitch, 4, original.to_3x3() @ Vector((1,0,0)))
    else:
        rotation = Matrix.Rotation(tilt(index), 4, original.to_3x3() @ Vector((1,0,0)))
    return Matrix.Translation(pivot) @ rotation @ Matrix.Translation(-pivot) @ original


def validate_product(scene):
    import bpy
    product = bpy.data.collections['PIMM_PUBLISHED']
    meshes = [o for o in product.all_objects if o.type == 'MESH']
    assert len(meshes) == 556
    assert all(o.library and o.data.library and not o.override_library for o in meshes)
    assert all(not o.animation_data and not o.override_library for o in product.all_objects)
    assert [o for o in scene.objects if o.animation_data] == [scene.camera]
    return product, meshes


def render(shot, generation=GENERATION, frames=None, validate_only=False):
    import bpy
    from mathutils import Matrix, Vector
    from bpy_extras.object_utils import world_to_camera_view
    if shot not in ('configuration', 'tooling'):
        raise ValueError('Unknown camera proof shot')
    if not generation.startswith('bento-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in generation):
        raise ValueError('Invalid immutable generation')
    selected = selected_frames(shot, frames)
    loader = detail_contract if shot == 'configuration' else contract_for
    approval = WHITE_APPROVAL if shot == 'configuration' else R10_APPROVAL
    source = loader(shot)
    errors = validate_tool_lock(json.loads(LOCK_PATH.read_text()))
    if errors:
        raise ValueError(errors)
    root = require_within(ASSET_ROOT / 'renders/proofs' / generation / shot, ASSET_ROOT / 'renders/proofs')
    scene_path = ASSET_ROOT / 'scenes/animations' / f'pimm-30g--{generation}--{shot}.blend'
    contract_path = ASSET_ROOT / 'scenes/contracts' / f'pimm-30g--{generation}--{shot}.json'
    count = 840 if shot == 'configuration' else TILT_FRAMES
    if contract_path.exists():
        contract = json.loads(contract_path.read_text())
        checked_file(scene_path, contract['scene_sha256'])
        checked_file(Path(__file__), contract['script_sha256'])
        checked_file(approval, contract['source_approval_sha256'])
        if source['scene_sha256'] != contract['source_scene_sha256']:
            raise ValueError('Source scene changed')
        bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    else:
        if root.exists() or scene_path.exists():
            raise FileExistsError('Unreceipted generation cannot be overwritten')
        bpy.ops.wm.open_mainfile(filepath=source['scene_path'])
        scene = bpy.context.scene
        product = bpy.data.collections['PIMM_PUBLISHED']
        meshes = [o for o in product.all_objects if o.type == 'MESH']
        assert len(meshes) == 556 and all(o.library and o.data.library and not o.override_library for o in meshes)
        assert all(not o.animation_data for o in product.all_objects)
        low, high = studio._world_bounds(meshes)
        if shot == 'configuration':
            pivot = Vector([(a+b)/2 for a,b in zip(low,high)])
            pivot_evidence = {'type': 'published-product-bounds-center', 'low':low, 'high':high}
        else:
            pivot, pivot_evidence = plate_pivot(product)
        camera = scene.camera
        assert camera and camera.data.type == 'ORTHO' and not camera.library and not camera.animation_data
        original = camera.matrix_world.copy()
        original_scale = camera.data.ortho_scale
        origin_projection = world_to_camera_view(scene, camera, pivot)
        projection = []
        corners = [Vector(c) for c in itertools.product(*zip(low, high))]
        for index in range(1, count + (2 if shot == 'tooling' else 1)):
            scene.frame_set(index)
            camera.matrix_world = camera_pose(original, pivot, shot, index)
            camera.keyframe_insert(data_path='location', frame=index)
            camera.keyframe_insert(data_path='rotation_euler', frame=index)
            bpy.context.view_layer.update()
            target = world_to_camera_view(scene, camera, pivot)
            assert abs(target.x-origin_projection.x) < 0.00001 and abs(target.y-origin_projection.y) < 0.00001
            points = [world_to_camera_view(scene,camera,c) for c in corners]
            projection.append([min(p.x for p in points),min(p.y for p in points),max(p.x for p in points),max(p.y for p in points)])
        bounds = [min(p[0] for p in projection),min(p[1] for p in projection),max(p[2] for p in projection),max(p[3] for p in projection)]
        if shot == 'configuration' and (bounds[0] < .45 or bounds[1] < .015 or bounds[2] > .995 or bounds[3] > .995):
            raise ValueError(f'Two-axis orbit exceeds safe image rectangle: {bounds}')
        scene.frame_start, scene.frame_end = 1, count
        scene.render.fps, scene.render.fps_base = FPS, 1
        scene.frame_set(361 if shot == 'configuration' else 1)
        assert camera.data.ortho_scale == original_scale
        assert [scene.render.resolution_x,scene.render.resolution_y] == source['native_size']
        assert scene.render.resolution_percentage == 100
        root.mkdir(parents=True)
        scene.render.filepath = str(root / 'frame-')
        bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
        contract = dict(source, shot=shot,generation=generation,approval='pending',scene_path=str(scene_path),
            scene_sha256=sha256_file(scene_path),source_scene_sha256=source['scene_sha256'],
            source_approval_sha256=sha256_file(approval),script_sha256=sha256_file(Path(__file__)),
            motion={'type':'camera-only-two-axis' if shot=='configuration' else 'camera-only-tooling-tilt',
                    'frames':count,'fps':FPS,'yaw_views':120 if shot=='configuration' else 1,
                    'elevation_degrees':list(ELEVATIONS) if shot=='configuration' else [-3,3],
                    'pivot':list(pivot),'pivot_evidence':pivot_evidence,'machine_motion':False,
                    'original_camera_matrix':[list(row) for row in original],
                    'controller_values':'unchanged 300/300'},projected_union=bounds,
            pivot_projection=list(origin_projection),proof_percentage=25,proof_samples=32,proof_path=str(root),proofs=[])
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    scene = bpy.context.scene
    product, meshes = validate_product(scene)
    pivot = Vector(contract['motion']['pivot'])
    original = Matrix(contract['motion']['original_camera_matrix'])
    if shot == 'tooling':
        actual, _ = plate_pivot(product)
        assert (actual-pivot).length < .00001
    # Verify every saved pose after reopening, not merely successful save.
    for index in range(1, count + (2 if shot == 'tooling' else 1)):
        scene.frame_set(index)
        expected = camera_pose(original,pivot,shot,index)
        assert max(abs(expected[r][c]-scene.camera.matrix_world[r][c]) for r in range(4) for c in range(4)) < .002
        projection = world_to_camera_view(scene,scene.camera,pivot)
        assert max(abs(projection[i]-contract['pivot_projection'][i]) for i in (0,1)) < .00001
    if validate_only:
        print('CAMERA_SCENE_VALIDATED='+str(contract_path),flush=True)
        return
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.refresh_devices()
    backend = next((name for name in ('OPTIX','CUDA') if any(d.type==name for d in preferences.devices)),None)
    if not backend:
        raise RuntimeError('Approved GPU unavailable')
    preferences.compute_device_type = backend
    for device in preferences.devices:
        device.use = device.type == backend
    scene.render.resolution_percentage = 25
    scene.cycles.samples = 32
    scene.cycles.adaptive_threshold = .03
    records = {r['index']:r for r in contract['proofs']}
    for index in selected:
        row, frame = divmod(index-1,YAW_FRAMES) if shot=='configuration' else (0,index-1)
        directory = root / f'row-{row:02d}' if shot=='configuration' else root
        path = directory / f'frame-{frame+1:04d}.png'
        if index in records:
            checked_file(path,records[index]['sha256'])
            continue
        if path.exists():
            raise FileExistsError(f'Unreceipted proof: {path}')
        directory.mkdir(parents=True,exist_ok=True)
        scene.frame_set(index)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        records[index] = {'index':index,'row':row,'frame':frame+1,'path':str(path),'sha256':sha256_file(path)}
        contract['proofs'] = [records[key] for key in sorted(records)]
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        print(f'CAMERA_PROOF_FRAME={shot}:{index}/{count}',flush=True)
    loader(shot)
    checked_file(scene_path,contract['scene_sha256'])
    print('CAMERA_PROOF_READY='+str(contract_path),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shot',choices=('configuration','tooling'),required=True)
    parser.add_argument('--generation',default=GENERATION)
    parser.add_argument('--frames',nargs='+',type=int)
    parser.add_argument('--validate-only',action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    render(args.shot,args.generation,args.frames,args.validate_only)
    os._exit(0)
