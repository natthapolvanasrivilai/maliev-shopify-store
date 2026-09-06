"""Package the supplied coaster mold CAD tessellations without changing geometry."""
import hashlib
import json
from pathlib import Path
import bpy
import math
from mathutils import Matrix

root=Path('M:/30_Products/00_Pneumatic Injection Molding Machine/blender-product-renders')
source=root/'assets/molds/80mm Coaster.step'
manifest=json.loads((root/'renders/proofs/fixture-mounting-20260903-draft-01/plain.json').read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest().upper()==manifest['source']['sha256']
bpy.ops.wm.read_factory_settings(use_empty=True)
for solid in manifest['solids']:
    if solid['original_name']=='80mm Coaster':continue  # Finished plastic part, not tooling.
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=solid['interchange_path'])
    for o in set(bpy.data.objects)-before:
        if o.type=='MESH':o.name=solid['original_name']
# Legacy per-solid exports store millimetres in a Y-up Blender basis.
# Normalize to metre-sized, Z-up Blender geometry before standard glTF export.
meshes=[o for o in bpy.data.objects if o.type=='MESH']
transforms={o:o.matrix_world.copy() for o in meshes}
for o in meshes:
    o.parent=None
    o.matrix_world=Matrix.Scale(.001,4)@Matrix.Rotation(-math.pi/2,4,'X')@transforms[o]
out=Path(__file__).parent/'fixtures/80mm-coaster.glb'
bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB')
out.with_suffix('.json').write_text(json.dumps(dict(source=str(source),source_sha256=manifest['source']['sha256'],glb_sha256=hashlib.sha256(out.read_bytes()).hexdigest().upper(),mesh_count=6,source_step_sprue_axis_xy_mm=[0,0],components='Injection side, cavity side, four screws; excludes finished plastic coaster.'),indent=2))
