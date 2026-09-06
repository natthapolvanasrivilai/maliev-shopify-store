"""Run in Blender with the approved 30G master loaded; never saves it."""
import bpy,sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.blender.pimm_production.pimm_operating_motion import Operations
from scripts.blender.pimm_production.pimm_pellet_simulation import tube_pose
ops=Operations(bpy)
cad=[o for o in bpy.data.objects if o.type=='MESH' and o.name in ops.original]
cache={}
hits=set()
def bounds(o):
    p=[o.matrix_world@Vector(v) for v in o.bound_box]
    return [min(v[i] for v in p) for i in range(3)],[max(v[i] for v in p) for i in range(3)]
def tree(o):
    e=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=e.to_mesh()
    result=BVHTree.FromPolygons([o.matrix_world@v.co for v in m.vertices],[list(p.vertices) for p in m.polygons])
    e.to_mesh_clear();return result
for f in range(0,288,4):
    pos,tilt=tube_pose(f/287);ops.tube.location=pos;ops.tube.rotation_euler=(0,tilt,0)
    bpy.context.view_layer.update();lo,hi=bounds(ops.tube);tt=tree(ops.tube)
    for o in cad:
        a,z=bounds(o)
        if any(z[i]<lo[i] or a[i]>hi[i] for i in range(3)):continue
        if o.name not in cache:cache[o.name]=tree(o)
        if tt.overlap(cache[o.name]):hits.add(o.name)
print('COLLISIONS',sorted(hits),flush=True)
assert not hits
