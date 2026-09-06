"""Run with Blender and the approved 30G master loaded; never saves the master."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import bpy
from scripts.blender.pimm_production.pimm_operating_motion import Operations

ops = Operations(bpy)
bpy.context.view_layer.update()
allowed = {ops.knob.name, ops.needle.name}
baseline = {o.name: o.matrix_world.copy() for o in bpy.data.objects if o.type == 'MESH'}
for t in (0, .15, .21, .4, .68, .8, 1):
    ops.apply('pressure', t)
    bpy.context.view_layer.update()
    for name, matrix in baseline.items():
        if name not in allowed:
            assert max(abs(bpy.data.objects[name].matrix_world[i][j]-matrix[i][j]) for i in range(4) for j in range(4)) < 1e-5, name
    if t == .21:
        assert abs(ops.knob.matrix_world.translation.z-baseline[ops.knob.name].translation.z-3) < 1e-5
print('PASS: upper knob lifts 3 mm; all other CAD bodies except the gauge needle stay fixed across seven poses')
