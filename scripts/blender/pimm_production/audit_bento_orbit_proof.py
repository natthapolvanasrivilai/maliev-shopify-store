"""Read-only verification of the saved camera orbit and unchanged linked model."""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.blender.pimm_production.paths import ASSET_ROOT
from scripts.blender.pimm_production.blender_bento_final import checked_file


def main():
    import bpy
    path = ASSET_ROOT / 'scenes/contracts/pimm-30g--bento-bento-20260903-r10-orbit--controls.json'
    contract = json.loads(path.read_text())
    checked_file(contract['scene_path'], contract['scene_sha256'])
    bpy.ops.wm.open_mainfile(filepath=contract['scene_path'])
    scene = bpy.context.scene
    camera = scene.camera
    product = bpy.data.collections['PIMM_PUBLISHED']
    assert scene.render.fps == 24 and scene.frame_end == 192
    assert scene.render.resolution_percentage == 100
    assert all(obj.library and not obj.animation_data for obj in product.all_objects)
    assert [obj for obj in scene.objects if obj.animation_data] == [camera]
    def matrix(obj):
        return [value for row in obj.matrix_world for value in row]
    poses, product_pose = {}, None
    for frame in [1,49,97,145,193]:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        current = {obj.name:matrix(obj) for obj in product.all_objects}
        if product_pose is None:
            product_pose = current
        assert current == product_pose, 'Machine transform changed during camera orbit'
        poses[frame] = matrix(camera)
    assert max(abs(a-b) for a,b in zip(poses[1],poses[193])) < .00001
    assert poses[49] != poses[145] and poses[1] != poses[49]
    checked_file(contract['scene_path'], contract['scene_sha256'])
    print('ORBIT_AUDIT='+json.dumps({'camera_only':True,'stationary_product_objects':len(product_pose),
                                  'frames':192,'fps':24,'closed_loop':True,'camera_poses':poses}), flush=True)


if __name__ == '__main__':
    main()
    os._exit(0)
