"""Native rigid-body pellet pour in the master scene's millimetre coordinates."""
import math

def prop_visibility(t):
    from scripts.blender.pimm_production.pimm_operating_motion import ramp
    return ramp(t, 0, .14)*(1-ramp(t, .84, 1))

def tube_pose(t):
    from scripts.blender.pimm_production.pimm_operating_motion import ramp
    tip = ramp(t, .30, .72)
    # Fixed pouring lip: appear in place, tilt, then disappear in place.
    # A shallow initial tilt retains pellets without extending below the plate.
    return (-40, -15, 325), math.radians(-105+40*tip)

def pellet_sites():
    return [(x*4.3, y*4.3) for y in range(-2,3) for x in range(-2,3) if (x*4.3)**2+(y*4.3)**2 < 9.5**2]

class PelletSimulation:
    def __init__(self, ops):
        from mathutils import Vector
        self.ops = ops
        b = ops.bpy
        scene = b.context.scene
        scene.frame_start = 1
        scene.frame_end = 288
        scene.render.fps = 24
        scene.gravity = (0, 0, -9810)
        self.frame = 1
        scene.frame_set(1)
        # Fade the props, including their shadows, without disabling physics.
        self.fade_inputs = []
        materials = {slot.material for obj in [ops.tube,*ops.pellets] for slot in obj.material_slots if slot.material}
        for material in materials:
            nodes=material.node_tree.nodes;links=material.node_tree.links
            output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output)
            surface=output.inputs['Surface'].links[0].from_socket
            clear=nodes.new('ShaderNodeBsdfTransparent')
            fade=nodes.new('ShaderNodeMixShader');fade.name='OP_PROP_VISIBILITY'
            links.new(clear.outputs[0],fade.inputs[1]);links.new(surface,fade.inputs[2])
            links.new(fade.outputs[0],output.inputs['Surface'])
            self.fade_inputs.append(fade.inputs[0])
        # Evaluate the complete glass shell as a concave, animated collider.
        self.body(ops.tube, 'PASSIVE', 'MESH')
        ops.tube.rigid_body.kinematic = True
        ops.tube.rigid_body.mesh_source = 'FINAL'
        for frame in range(1, 289):
            t = (frame-1)/287
            location,tilt=tube_pose(t)
            ops.tube.location = location
            ops.tube.rotation_euler = (0, tilt, 0)
            ops.tube.keyframe_insert('location', frame=frame)
            ops.tube.keyframe_insert('rotation_euler', frame=frame)
        scene.frame_set(1)
        b.context.view_layer.update()
        # Non-overlapping layers inside the bore; let gravity settle the load.
        sites = pellet_sites()
        for i, pellet in enumerate(ops.pellets):
            x,y = sites[i % len(sites)]
            z = 20+(i//len(sites))*4.3
            pellet.location = ops.tube.matrix_world @ Vector((x,y,z))
            pellet.scale = (1,1,1)
            self.body(pellet, 'ACTIVE', 'SPHERE')
            pellet.rigid_body.mass = .00003
            pellet.rigid_body.friction = .35
            pellet.rigid_body.restitution = .08
            pellet.rigid_body.linear_damping = .04
            pellet.rigid_body.angular_damping = .1
        # Actual open CAD melt bore, not a convex hull sealing the opening.
        self.body(ops.part('0cd746d4874417b8'), 'PASSIVE', 'MESH')
        world = scene.rigidbody_world
        world.substeps_per_frame = 16
        world.solver_iterations = 30
        world.point_cache.frame_start = 1
        world.point_cache.frame_end = 288
        b.context.view_layer.update()

    def body(self, obj, kind, shape):
        b = self.ops.bpy
        b.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        b.context.view_layer.objects.active = obj
        b.ops.rigidbody.object_add()
        obj.rigid_body.type = kind
        obj.rigid_body.collision_shape = shape
        obj.rigid_body.use_margin = True
        obj.rigid_body.collision_margin = .05

    def apply(self, t):
        scene = self.ops.bpy.context.scene
        target = round(t*287)+1
        for frame in range(self.frame+1,target+1):
            scene.frame_set(frame)
        self.frame = target
        for socket in self.fade_inputs:
            socket.default_value = prop_visibility(t)
        self.ops.tube.hide_render = False
        for pellet in self.ops.pellets:
            pellet.hide_render = False
