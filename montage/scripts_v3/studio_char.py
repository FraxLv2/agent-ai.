# Cinématique extérieure du personnage du joueur : studio blanc/turquoise, contre-plongée, rotation, ombres, DoF
# usage: python3 studio_char.py WORKDIR OUTDIR [--test]
import bpy, sys, os, math, random
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import scene25d as S

WD, OUT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
N = 190
STEP = int(os.environ.get('STEP', 1))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 16)), pct=int(os.environ.get('PCT', 100)))
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.cycles.max_bounces = 6
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Punchy'
sc.view_settings.exposure = -0.6
P = lambda n: os.path.join(WD, n)

# ---------- personnage : carte découpée debout, qui reçoit la lumière et projette une ombre ----------
X0, Y0, X1, Y1 = 670, 20, 905, 510
HGT = 1.85
WID = HGT * (X1 - X0) / (Y1 - Y0)
bpy.ops.mesh.primitive_plane_add(size=1)
ch = bpy.context.object
ch.scale = (WID, HGT, 1); bpy.ops.object.transform_apply(scale=True)
ch.rotation_euler = (math.radians(90), 0, 0)
ch.location = (0, 0, HGT / 2 - 0.02)
uv = ch.data.uv_layers.active
for poly in ch.data.polygons:
    for li in poly.loop_indices:
        x, y, _ = ch.data.vertices[ch.data.loops[li].vertex_index].co
        u = (X0 + (x / WID + 0.5) * (X1 - X0)) / S.W_SRC
        v = 1 - (Y0 + (0.5 - y / HGT) * (Y1 - Y0)) / S.H_SRC
        uv.data[li].uv = (u, v)
m = bpy.data.materials.new('char'); m.use_nodes = True; nt = m.node_tree
pr = nt.nodes['Principled BSDF']; out = nt.nodes['Material Output']
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(P('char_fg.png')); tex.interpolation = 'Cubic'
nt.links.new(tex.outputs['Color'], pr.inputs['Base Color'])
nt.links.new(tex.outputs['Color'], pr.inputs['Emission Color'])
pr.inputs['Emission Strength'].default_value = 0.55
pr.inputs['Roughness'].default_value = 0.45
pr.inputs['Coat Weight'].default_value = 0.3
trn = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
nt.links.new(tex.outputs['Alpha'], mx.inputs['Fac']); nt.links.new(trn.outputs[0], mx.inputs[1]); nt.links.new(pr.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], out.inputs['Surface'])
ch.data.materials.append(m)

# ---------- studio : sol réfléchissant + fond cyclo blanc/turquoise + bandes lumineuses ----------
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
floor = bpy.context.object
fm = bpy.data.materials.new('floor'); fm.use_nodes = True
fp = fm.node_tree.nodes['Principled BSDF']
fp.inputs['Base Color'].default_value = (0.62, 0.86, 0.86, 1)
fp.inputs['Roughness'].default_value = 0.18
fp.inputs['Coat Weight'].default_value = 0.6
floor.data.materials.append(fm)
# mur courbe (cyclo)
bpy.ops.mesh.primitive_cylinder_add(radius=14, depth=30, location=(0, 0, 7), vertices=96)
cyc = bpy.context.object
cm = bpy.data.materials.new('cyc'); cm.use_nodes = True; cnt = cm.node_tree
cnt.nodes.clear(); co = cnt.nodes.new('ShaderNodeOutputMaterial'); ce = cnt.nodes.new('ShaderNodeEmission')
tc = cnt.nodes.new('ShaderNodeTexCoord'); sx = cnt.nodes.new('ShaderNodeSeparateXYZ'); cr = cnt.nodes.new('ShaderNodeValToRGB')
cr.color_ramp.elements[0].position = 0.45; cr.color_ramp.elements[0].color = (0.25, 0.85, 0.82, 1)
cr.color_ramp.elements[1].position = 0.62; cr.color_ramp.elements[1].color = (0.95, 1.0, 1.0, 1)
cnt.links.new(tc.outputs['Generated'], sx.inputs[0]); cnt.links.new(sx.outputs['Z'], cr.inputs['Fac'])
cnt.links.new(cr.outputs['Color'], ce.inputs['Color']); ce.inputs['Strength'].default_value = 0.9
cnt.links.new(ce.outputs[0], co.inputs['Surface'])
cyc.data.materials.append(cm)
for p in cyc.data.polygons:
    p.use_smooth = True
# bandes lumineuses verticales turquoise derrière le personnage
strip = S.emis_mat('strip', (0.2, 1.0, 0.9), 14)
for i, x in enumerate([-3.5, -1.6, 1.6, 3.5]):
    bpy.ops.mesh.primitive_cube_add(location=(x, 7.5, 2.2))
    st = bpy.context.object; st.scale = (0.07, 0.07, 2.2); st.data.materials.append(strip)
w = sc.world.node_tree.nodes['Background']
w.inputs['Color'].default_value = (0.8, 0.95, 0.95, 1); w.inputs['Strength'].default_value = 0.35

# ---------- lumières : clé blanche, contre-jour cyan, appoint turquoise (ombres réelles) ----------
def light(t, loc, col, e, size):
    bpy.ops.object.light_add(type=t, location=loc); l = bpy.context.object
    l.data.color = col; l.data.energy = e
    if t == 'AREA':
        l.data.size = size
    c = l.constraints.new('TRACK_TO'); c.target = ch; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return l
light('AREA', (2.8, -3.0, 3.6), (1.0, 0.98, 0.95), 900, 1.2)        # clé
light('AREA', (-2.5, 2.5, 2.8), (0.25, 0.95, 1.0), 1200, 1.5)       # contre-jour cyan
light('AREA', (-3.0, -2.0, 0.8), (0.2, 1.0, 0.8), 250, 2.0)         # appoint turquoise bas
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(35), math.radians(-25), 0))
sun = bpy.context.object; sun.data.energy = 2.5; sun.data.angle = math.radians(2)

# particules lumineuses au ralenti
random.seed(9)
dm = S.emis_mat('dust', (0.7, 1.0, 1.0), 5)
for i in range(90):
    p = Vector((random.uniform(-3, 3), random.uniform(-2.5, 4), random.uniform(0.1, 3.2)))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.006, 0.016), location=p)
    o = bpy.context.object; o.data.materials.append(dm)
    o.keyframe_insert('location', frame=1)
    o.location = p + Vector((random.uniform(-0.1, 0.1), random.uniform(-0.1, 0.1), random.uniform(0.05, 0.2)))
    o.keyframe_insert('location', frame=N)

# ---------- caméra en contre-plongée, rotation lente autour du personnage ----------
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 32; cam.data.sensor_width = 36
cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 2.2
CH = Vector((0, 0, 0.98))
for f in range(1, N + 1):
    t = (f - 1) / (N - 1); e = S.ease(t)
    yaw = math.radians(-32 + 64 * e)
    dist = 4.4 - 1.0 * e
    z = 0.32 + 0.12 * math.sin(math.pi * t)
    cam.location = Vector((dist * math.sin(yaw), -dist * math.cos(yaw), z))
    tgt = CH + Vector((0, 0, 0.1 * e))
    S.look_at(cam, tgt, roll=math.radians(-3 + 6 * e))
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.dof.focus_distance = (cam.location - Vector((0, 0, 1.1))).length
    cam.data.dof.keyframe_insert('focus_distance', frame=f)
    # la carte suit à moitié la caméra : parallaxe et ombre visibles sans révéler qu'elle est plate
    ch.rotation_euler = (math.radians(90), 0, yaw * 0.55)
    ch.keyframe_insert('rotation_euler', frame=f)

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else (
    [1, 95, 190] if TEST else sorted(set(list(range(1, N + 1, STEP)) + [N])))
for f in frames:
    p = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(p):
        continue
    sc.frame_set(f); sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
print('DONE')
