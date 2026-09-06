"""Deterministic operating poses; CAD geometry stays in the approved master."""
import math
import hashlib
import json
from pathlib import Path

def ramp(t, start, end):
    u = max(0., min(1., (t-start)/(end-start)))
    return u*u*(3-2*u)

def pose(shot, t):
    """Twelve-second editorial demonstration, not real heating duration."""
    turn = ramp(t, .22, .68)
    lift = ramp(t, .10, .20)*(1-ramp(t, .76, .86))
    stroke = ramp(t, .20, .48)*(1-ramp(t, .72, .94))
    reached = t >= .76
    blink = (.79 <= t < .82) or (.87 <= t < .90)
    return dict(clockwise_degrees=-135*turn, lock_lift_mm=3*lift,
                gauge_degrees=189*turn, stroke_mm=-145*stroke,
                powered=t>=.08, set_ready=t>=.22,
                upper_pv=round(25+190*ramp(t,.28,.72)),
                lower_pv=round(25+195*ramp(t,.32,.76)),
                confirmed=reached and not blink, blink=blink,
                mold_y=-260*(1-ramp(t,.12,.58)),
                pour=ramp(t,.15,.28)*(1-ramp(t,.76,.90)))

def tube_transform(pour):
    """Pouring lip and tilt approach from the open left side of the machine."""
    return (-25-150*(1-pour), -15, 322+50*(1-pour)), math.radians(-15-50*pour)

class Operations:
    def __init__(self, bpy):
        self.bpy=bpy
        self.original={o.name:o.matrix_world.copy() for o in bpy.data.objects if o.type=='MESH'}
        self.knob=self.part('17d7471e4d56f8a8')
        self.ring=self.part('d697fcbb01970757')
        self.needle=self.part('623a1bfb6905b6f3')
        self.plunger=[self.part(s) for s in ('01710571532bdd66','a346c4960c82485b','c15229288d0b1154','aafda372ef4bb4b8','2a58599fb2846cb6')]
        self.segments=[]
        self.props=[]
        self.make_displays()
        segment_names={o.name for o,_,_,_ in self.segments}
        self.indicators=[(o,o.hide_render) for o in bpy.data.objects if o.type=='MESH' and o.name not in segment_names and any(slot.material and 'NUMERIC' in slot.material.name for slot in o.material_slots)]
        self.make_props()

    def part(self, suffix):
        matches=[o for o in self.bpy.data.objects if o.get('pimm_stable_id')=='30G-'+suffix]
        if len(matches)!=1:raise ValueError(f'Expected one CAD body {suffix}')
        return matches[0]

    def make_displays(self):
        from mathutils import Vector
        rows=[505.62,493.18,440.62,428.18]; xs=[176.41,183.90,191.38,198.87]
        found=set()
        for o in self.bpy.data.objects:
            if o.type!='MESH' or not o.name.startswith('30G__Component'):continue
            d=o.dimensions; horizontal=d.x>3 and d.z<1.5 and d.y<.5
            if not horizontal and not (d.x<1.5 and d.z>3 and d.y<.5):continue
            p=[o.matrix_world@Vector(c) for c in o.bound_box]
            c=Vector([(min(v[i] for v in p)+max(v[i] for v in p))/2 for i in range(3)])
            row=min(range(4),key=lambda i:abs(c.z-rows[i])); digit=min(range(4),key=lambda i:abs(c.x-xs[i]))
            if abs(c.z-rows[row])>5 or abs(c.x-xs[digit])>3:continue
            dz=c.z-rows[row]
            segment=('a' if dz>2.5 else 'd' if dz< -2.5 else 'g') if horizontal else (('b' if dz>0 else 'c') if c.x>xs[digit] else ('f' if dz>0 else 'e'))
            key=(row,digit,segment)
            if key in found:raise ValueError(f'Duplicate display segment {key}')
            found.add(key)
            o.data=o.data.copy(); o.data.materials.clear()
            o.data.materials.append(self.bpy.data.materials['PIMM_RED_ILLUMINATED_NUMERIC' if row%2==0 else 'PIMM_GREEN_ILLUMINATED_NUMERIC'])
            # Separate the authored light segments from the coplanar window.
            transform=o.matrix_world.copy();transform.translation.y-=.35;o.matrix_world=transform
            self.segments.append((o,row,digit,segment))
        if len(found)!=112:raise ValueError(f'Expected 112 CAD segments, got {len(found)}')

    def mat(self,name,color,metal=0.,glass=False):
        m=self.bpy.data.materials.new(name);m.use_nodes=True
        p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1)
        p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=.12 if glass else .3
        if glass:p.inputs['Transmission Weight'].default_value=1.;p.inputs['IOR'].default_value=1.46
        return m

    def make_props(self):
        from mathutils import Matrix,Vector
        b=self.bpy
        before=set(b.data.objects)
        fixture=Path(__file__).parent/'fixtures'/'4040-single-cavity.glb'
        provenance=json.loads(fixture.with_suffix('.json').read_text())
        if hashlib.sha256(fixture.read_bytes()).hexdigest().upper()!=provenance['glb_sha256']:raise ValueError('Supplied mold asset hash changed')
        b.ops.import_scene.gltf(filepath=str(fixture))
        imported=[o for o in b.data.objects if o not in before and o.type=='MESH']
        if len(imported)!=6:raise ValueError('Expected supplied mold, insert, and four screws')
        # STEP millimetres were exported to glTF metres. Restore units, not scale-to-fit.
        transforms={o:o.matrix_world.copy() for o in imported}
        unit_factor=1000*b.context.scene.unit_settings.scale_length
        for o in imported:o.parent=None;o.matrix_world=Matrix.Scale(unit_factor,4)@transforms[o]
        b.context.view_layer.update()
        points=[o.matrix_world@Vector(c) for o in imported for c in o.bound_box]
        low=[min(p[i] for p in points) for i in range(3)];high=[max(p[i] for p in points) for i in range(3)]
        if any(abs((high[i]-low[i])-expected)>.01 for i,expected in enumerate((80,30,49))):raise ValueError(f'Supplied mold dimensions changed: {[high[i]-low[i] for i in range(3)]}')
        self.mold=b.data.objects.new('OP_SUPPLIED_4040_MOLD',None);b.context.collection.objects.link(self.mold)
        # The supplied assembly's sprue face points along -Y; turn it upward.
        orient=Matrix.Rotation(-math.pi/2,4,'X')
        points=[orient@p for p in points]
        low=[min(p[i] for p in points) for i in range(3)];high=[max(p[i] for p in points) for i in range(3)]
        # STEP sprue cone is at X=6, Y=0, not the bounding-box centre.
        offset=Matrix.Translation((-6,0,42.5-low[2]))@orient
        metal=self.mat('OP_MOLD_METAL',(.36,.39,.42),.8)
        for o in imported:
            o.matrix_world=offset@o.matrix_world;o.parent=self.mold
            if o.name.startswith('Mold'):o.data.materials.clear();o.data.materials.append(metal)
        self.mold_meshes=imported;self.props.extend(imported)
        # Open glass tube, closed far end; its local origin is the pouring lip.
        verts=[]; faces=[]; n=64
        profile=[(14,0),(14,86)]
        profile.extend((14*math.cos(j*math.pi/24),86+14*math.sin(j*math.pi/24)) for j in range(1,12))
        profile.append((0,100))
        for radius,z in profile:
            verts.extend([(radius*math.cos(i*2*math.pi/n),radius*math.sin(i*2*math.pi/n),z) for i in range(n)])
        for row in range(len(profile)-1):
            for i in range(n):faces.append((row*n+i,row*n+(i+1)%n,(row+1)*n+(i+1)%n,(row+1)*n+i))
        mesh=b.data.meshes.new('OP_TEST_TUBE');mesh.from_pydata(verts,[],faces)
        self.tube=b.data.objects.new('OP_TEST_TUBE',mesh);b.context.collection.objects.link(self.tube)
        solid=self.tube.modifiers.new('Glass wall','SOLIDIFY');solid.thickness=1.2
        for polygon in mesh.polygons:polygon.use_smooth=True
        mesh.materials.append(self.mat('OP_GLASS',(.96,.98,1),glass=True));self.props.append(self.tube)
        blue=self.mat('OP_BLUE_PELLETS',(.015,.25,.65))
        self.pellets=[]
        for i in range(240):
            b.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=2)
            o=b.context.object;o.name=f'OP_PELLET_{i:02d}';o.scale.z=.6;o.data.materials.append(blue)
            self.pellets.append(o);self.props.append(o)

    def apply(self,shot,t):
        from mathutils import Matrix,Vector
        s=pose(shot,t)
        for o in [self.knob,self.ring,self.needle,*self.plunger]:o.matrix_world=self.original[o.name].copy()
        for o in self.props:o.hide_render=True
        if shot=='pressure':
            pivot=Vector((-90,-120,0))
            # Only the upper adjustment handle unlocks. The lower mounting nut
            # remains seated against the bracket throughout the demonstration.
            for o in (self.knob,):
                o.matrix_world=Matrix.Translation((0,0,s['lock_lift_mm']))@Matrix.Translation(pivot)@Matrix.Rotation(math.radians(s['clockwise_degrees']),4,'Z')@Matrix.Translation(-pivot)@self.original[o.name]
            pivot=Vector((-90,-164.72,530.5))
            self.needle.matrix_world=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(s['gauge_degrees']),4,'Y')@Matrix.Translation(-pivot)@self.original[self.needle.name]
        if shot=='actuator':
            for o in self.plunger:o.matrix_world=Matrix.Translation((0,0,s['stroke_mm']))@self.original[o.name]
        digits={'0':'abcdef','1':'bc','2':'abged','3':'abgcd','4':'fgbc','5':'afgcd','6':'afgecd','7':'abc','8':'abcdefg','9':'abfgcd'}
        values=[300]*4
        if shot=='temperature':values=[s['upper_pv'],215 if s['set_ready'] else 25,s['lower_pv'],220 if s['set_ready'] else 25]
        for o,row,digit,segment in self.segments:
            active=digit>0 and segment in digits[str(values[row]).zfill(3)[digit-1]]
            o.hide_render=not active or (shot=='temperature' and (not s['powered'] or s['blink']))
        for o,hidden in self.indicators:o.hide_render=hidden or (shot=='temperature' and not s['powered'])
        if shot=='mounting':
            for o in self.mold_meshes:o.hide_render=False
            self.mold.location.y=s['mold_y']
        if shot=='pellets':
            u=s['pour'];self.tube.hide_render=False
            # Approach from the open left side, away from the controller box.
            location, tilt=tube_transform(u)
            self.tube.location=location;self.tube.rotation_euler=(0,tilt,0)
            for i,o in enumerate(self.pellets):
                release=.29+i*(.42/239)
                q=(t-release)/.13
                o.hide_render=q>1
                if q<0:
                    angle=i*2.39996323
                    radius=9*math.sqrt((i%13+.5)/13)
                    local=Vector((radius*math.cos(angle),radius*math.sin(angle),min(86,max(2,(release-t)*180))))
                    o.location=self.tube.location+self.tube.rotation_euler.to_matrix()@local
                elif not o.hide_render:o.location=(-25*(1-q)+(i%3-1)*2,-15*(1-q),322-65*q*q)
        return s
