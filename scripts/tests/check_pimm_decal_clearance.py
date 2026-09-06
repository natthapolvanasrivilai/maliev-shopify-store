"""Native Blender check; run with the approved 30G master, never save it."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import bpy
from mathutils import Vector
from scripts.blender.pimm_production.blender_30g_component_cinema import stabilize_decal
decal=bpy.data.objects['PIMM30_MASTER_AirTAC_Decal']
support=bpy.data.objects['30G__white-powdercoat-aluminum__663ad7c8ef8b894f']
mesh=decal.data
stabilize_decal(bpy);bpy.context.view_layer.update()
matrix=decal.matrix_world.copy()
stabilize_decal(bpy)
assert decal.matrix_world==matrix and decal.data==mesh
gap=min((support.matrix_world@Vector(v)).y for v in support.bound_box)-max((decal.matrix_world@Vector(v)).y for v in decal.bound_box)
assert .25<gap<.28, gap
print('PASS decal stand-off',gap,'mm; idempotent; artwork geometry unchanged')
