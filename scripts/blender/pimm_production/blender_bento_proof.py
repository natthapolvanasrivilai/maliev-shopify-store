"""Author linked, full-bleed 30G tile scenes and render review-only proofs."""

from __future__ import annotations

import argparse
import itertools
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production import blender_master_storefront_render as studio
from scripts.blender.pimm_production.blender_collection_card_render import MASTER_HASHES
from scripts.blender.pimm_production.paths import ASSET_ROOT, require_within
from scripts.blender.pimm_production.tool_policy import LOCK_PATH, validate_tool_lock


# Image-space rectangles use a bottom-left origin. Text lives outside these
# subject rectangles, but the physical studio fills the entire camera frame.
SHOTS = {
    'capacity': {'size': (1600, 2200), 'source': 'overview', 'z': (0, 1), 'rect': (.04, .32, .96, .98)},
    'controls': {'size': (2400, 1200), 'source': 'controls', 'z': (.52, .81), 'rect': (.48, .04, .98, .95)},
    'tooling': {'size': (1600, 2000), 'source': 'tooling', 'z': (0, .24), 'rect': (.04, .43, .96, .94)},
    'configuration': {'size': (2400, 1200), 'source': 'configuration', 'z': (0, 1), 'rect': (.53, .05, .97, .95)},
}


def fit_camera(bpy, camera, low, high, shot):
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    height = high[2] - low[2]
    points = [Vector(p) for p in itertools.product(
        (low[0], high[0]), (low[1], high[1]),
        (low[2] + height * shot['z'][0], low[2] + height * shot['z'][1]))]
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = height
    camera.data.dof.use_dof = False
    scene = bpy.context.scene

    def projection():
        bpy.context.view_layer.update()
        return [world_to_camera_view(scene, camera, point) for point in points]

    def bounds(projected):
        return (min(p.x for p in projected), min(p.y for p in projected),
                max(p.x for p in projected), max(p.y for p in projected))

    x0, y0, x1, y1 = shot['rect']
    a, b, c, d = bounds(projection())
    camera.data.ortho_scale *= max((c-a)/(x1-x0), (d-b)/(y1-y0))
    a, b, c, d = bounds(projection())
    origin = Vector((0, 0, 0))
    projected_origin = world_to_camera_view(scene, camera, origin)
    rotation = camera.rotation_euler.to_matrix()
    right, up = rotation @ Vector((1, 0, 0)), rotation @ Vector((0, 1, 0))
    unit_x = world_to_camera_view(scene, camera, origin + right).x - projected_origin.x
    unit_y = world_to_camera_view(scene, camera, origin + up).y - projected_origin.y
    camera.location += right * (((a+c)-(x0+x1))/2/unit_x)
    camera.location += up * (((b+d)-(y0+y1))/2/unit_y)
    return bounds(projection())


def render(shot_name, generation):
    import bpy
    from mathutils import Vector

    lock = json.loads(LOCK_PATH.read_text(encoding='utf-8'))
    errors = validate_tool_lock(lock)
    if errors:
        raise ValueError(errors)
    master = ASSET_ROOT / 'masters/PIMM-30G-MASTER.blend'
    material_library = ASSET_ROOT / 'masters/PIMM-MATERIAL-LIBRARY.blend'
    assert studio.sha256_file(master) == MASTER_HASHES['30G'], 'Master has changed'
    assert material_library.is_file(), 'Missing material library'
    assert not bpy.data.filepath, 'Run in a new factory-startup process'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(master), link=True) as (source, target):
        assert 'PIMM_PUBLISHED' in source.collections
        target.collections = ['PIMM_PUBLISHED']
    published = target.collections[0]
    bpy.context.scene.collection.children.link(published)
    bpy.context.view_layer.update()
    meshes = [o for o in published.all_objects if o.type == 'MESH']
    assert len(meshes) == studio.EXPECTED_OBJECT_COUNT
    assert all(o.library and o.data.library for o in meshes), 'Product must stay linked'
    feet = [o for o in meshes if '__nylon-feet__' in o.name.lower()]
    levels = [min((o.matrix_world @ Vector(c)).z for c in o.bound_box) for o in feet]
    assert len(levels) == 4 and max(abs(z) for z in levels) <= studio.FOOT_TOLERANCE, levels
    low, high = studio._world_bounds(meshes)
    shot = SHOTS[shot_name]
    stem = f'pimm-30g--bento-{generation}--{shot_name}'
    scene_file = require_within(ASSET_ROOT / 'scenes/stills' / f'{stem}.blend', ASSET_ROOT)
    proof_dir = require_within(ASSET_ROOT / 'renders/proofs' / generation, ASSET_ROOT)
    contract_file = require_within(ASSET_ROOT / 'scenes/contracts' / f'{stem}.json', ASSET_ROOT)
    proof = proof_dir / f'{stem}.png'
    for path in (scene_file, contract_file, proof):
        if path.exists():
            raise FileExistsError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
    runtime = studio._runtime_collection(bpy)
    studio._install_studio(bpy, runtime, low, high)
    # A single effectively infinite floor fills every orthographic camera ray.
    # No wall/floor junction can project behind the machine's feet.
    sweep = bpy.data.objects['PIMM_WHITE_CYCLORAMA']
    sweep.hide_render = True
    extent = max(high[i] - low[i] for i in range(3))
    bpy.ops.mesh.primitive_plane_add(size=extent * 2000, location=(0, 0, 0))
    floor = bpy.context.object
    floor.name = 'BENTO_INFINITE_GROUND'
    floor.data.materials.append(studio._material(bpy, 'BENTO_MATTE_GROUND', (.82, .82, .82, 1), .84))
    camera, _ = studio._shot_camera(bpy, runtime, shot['source'], low, high, shot['size'][0])
    camera.location.z += extent * .4
    studio._look_at(camera, camera.data.dof.focus_object.location)
    studio._configure_render(bpy, *shot['size'], 128, proof)
    scene = bpy.context.scene
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '16'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = 1.1
    scene.world.node_tree.nodes['PIMM_HDRI_LIGHTING'].inputs['Strength'].default_value = .65
    projected_bounds = fit_camera(bpy, camera, low, high, shot)
    # Orthographic framing can shift the near camera plane below the floor.
    # Retreat along the viewing axis without changing projection so every
    # camera ray starts above the physical ground instead of seeing the world.
    camera.location += camera.rotation_euler.to_matrix() @ Vector((0, 0, extent * 5))
    camera.data.clip_end = max(camera.data.clip_end, extent * 100)
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_file))
    scene_hash = studio.sha256_file(scene_file)
    bpy.ops.wm.open_mainfile(filepath=str(scene_file))
    assert studio.sha256_file(master) == MASTER_HASHES['30G']
    assert all(o.library and o.data.library for o in bpy.data.collections['PIMM_PUBLISHED'].all_objects if o.type == 'MESH')
    contract = {'schema': 'maliev.pimm-bento-proof/v1', 'generation': generation,
                'shot': shot_name, 'scene_path': str(scene_file), 'scene_sha256': scene_hash,
                'master_sha256': MASTER_HASHES['30G'], 'material_library_sha256': studio.sha256_file(material_library),
                'tool_lock_sha256': studio.sha256_file(LOCK_PATH), 'native_size': shot['size'],
                'proof_percentage': 30, 'samples': 128, 'subject_rectangle': shot['rect'],
                'projected_bounds': projected_bounds, 'foot_levels': levels,
                'approval': 'pending', 'proof_path': str(proof)}
    contract_file.write_text(json.dumps(contract, indent=2)+'\n', encoding='utf-8')
    bpy.context.scene.render.resolution_percentage = 30
    bpy.ops.render.render(write_still=True)
    contract['proof_sha256'] = studio.sha256_file(proof)
    contract_file.write_text(json.dumps(contract, indent=2)+'\n', encoding='utf-8')
    print('BENTO_PROOF_READY='+json.dumps(contract), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shot', choices=SHOTS, required=True)
    parser.add_argument('--generation', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    render(args.shot, args.generation)
    os._exit(0)
