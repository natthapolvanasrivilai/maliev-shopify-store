import bpy,sys,math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.blender.pimm_production.pimm_operating_motion import Operations
o=Operations(bpy)
o.apply('pellets',0)
prev={}
cross={}
for f in range(288):
    o.pellet_simulation.apply(f/287)
    bpy.context.view_layer.update()
    for p in o.pellets:
        v=p.matrix_world.translation.copy()
        if p.name in prev and prev[p.name].z>285 and v.z<=285:
            cross.setdefault(p.name,(round(v.x,2),round(v.y,2),f))
        prev[p.name]=v
print('CROSSINGS',len(cross), 'INSIDE_40',sum(x*x+y*y<1600 for x,y,f in cross.values()))
print('SAMPLE',list(cross.values())[:20])
assert len(cross)>=200, 'Pour did not empty enough pellets'
assert all(x*x+y*y<1600 for x,y,f in cross.values()), 'Pellets fell outside the bore envelope'
