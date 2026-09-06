"""Fit the actual sprue and nozzle rim vertices; never save the CAD master."""
import sys
from pathlib import Path
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.blender.pimm_production.pimm_operating_motion import Operations
op=Operations(bpy);op.apply('mounting',1);bpy.context.view_layer.update()
for o in op.mold_meshes:
    p=[o.matrix_world@v.co for v in o.data.vertices]
    print(o.name,[(min(v[i] for v in p),max(v[i] for v in p)) for i in range(3)],flush=True)
def rim(objects,top):
    points=np.array([tuple(o.matrix_world@v.co) for o in objects for v in o.data.vertices])
    z=points[:,2].max() if top else points[:,2].min()
    points=points[(abs(points[:,2]-z)<.05)&(np.linalg.norm(points[:,:2],axis=1)<8)]
    points=np.unique(np.round(points,5),axis=0)
    assert len(points)>8, ('Missing circular rim',z,len(points))
    a=np.column_stack([2*points[:,0],2*points[:,1],np.ones(len(points))])
    center=np.linalg.lstsq(a,points[:,0]**2+points[:,1]**2,rcond=None)[0][:2]
    return center
sprue=rim(op.mold_meshes,True)
nozzle=rim([op.part('d15912a35de6e11f')],False)
assert np.linalg.norm(sprue-nozzle)<.05,(sprue,nozzle)
bottom=min((o.matrix_world@v.co).z for o in op.mold_meshes for v in o.data.vertices)
assert abs(bottom-42.5)<.01,bottom
print('PASS sprue/nozzle XY:',sprue,nozzle,'; base contact Z:',bottom,flush=True)
