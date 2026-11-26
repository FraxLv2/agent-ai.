# Réplique 3D du sniper doré du joueur (modélisée) : orbite complète, reflets cyan/turquoise, DoF, bokeh
# usage: python3 replica_sniper.py WORKDIR OUTDIR [--test]
import bpy, bmesh, sys, os, math, random
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import scene25d as S

WD, OUT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
N = 142
STEP = int(os.environ.get('STEP', 1))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 16)), pct=int(os.environ.get('PCT', 100)))
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.cycles.max_bounces = 8
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Punchy'
sc.view_settings.exposure = 0.4

# ---------- matériaux ----------
def gold_mat():
    m = bpy.data.materials.new('gold'); m.use_nodes = True; nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (1.0, 0.70, 0.28, 1); p.inputs['Metallic'].default_value = 1.0
    # gravures : motif voronoï/bruit en relief + rugosité variable
    tc = nt.nodes.new('ShaderNodeTexCoord'); vo = nt.nodes.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 120
    vo.feature = 'DISTANCE_TO_EDGE'
    no = nt.nodes.new('ShaderNodeTexNoise'); no.inputs['Scale'].default_value = 60
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.12; bp.inputs['Distance'].default_value = 0.0006
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value = 0.10; mr.inputs['To Max'].default_value = 0.22
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector']); nt.links.new(tc.outputs['Object'], no.inputs['Vector'])
    nt.links.new(vo.outputs['Distance'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], p.inputs['Normal'])
    nt.links.new(no.outputs['Fac'], mr.inputs['Value']); nt.links.new(mr.outputs[0], p.inputs['Roughness'])
    return m
GOLD = gold_mat()
BLACK = bpy.data.materials.new('black'); BLACK.use_nodes = True
bp_ = BLACK.node_tree.nodes['Principled BSDF']
bp_.inputs['Base Color'].default_value = (0.012, 0.012, 0.014, 1); bp_.inputs['Metallic'].default_value = 0.6; bp_.inputs['Roughness'].default_value = 0.28
bp_.inputs['Coat Weight'].default_value = 0.5
GLASS = bpy.data.materials.new('lens'); GLASS.use_nodes = True
gp = GLASS.node_tree.nodes['Principled BSDF']
gp.inputs['Base Color'].default_value = (0.0, 0.02, 0.03, 1); gp.inputs['Roughness'].default_value = 0.02
gp.inputs['Coat Weight'].default_value = 1.0; gp.inputs['Emission Color'].default_value = (0.1, 0.9, 1.0, 1); gp.inputs['Emission Strength'].default_value = 0.6

parts = []
def add(o, mat):
    o.data.materials.append(mat); parts.append(o)
    for p in o.data.polygons:
        p.use_smooth = True
    b = o.modifiers.new('bev', 'BEVEL'); b.width = 0.002; b.segments = 2
    return o

def box(x0, x1, z0, z1, w, mat, y=0.0):
    bpy.ops.mesh.primitive_cube_add(location=((x0 + x1) / 2, y, (z0 + z1) / 2))
    o = bpy.context.object; o.scale = ((x1 - x0) / 2, w / 2, (z1 - z0) / 2); bpy.ops.object.transform_apply(scale=True)
    return add(o, mat)

def cyl(x0, x1, r0, r1, z, mat, y=0.0, verts=48):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r0, radius2=r1, depth=x1 - x0, location=((x0 + x1) / 2, y, z), rotation=(0, math.radians(90), 0))
    return add(bpy.context.object, mat)

def profile(pts, w, mat, y=0.0):
    bm = bmesh.new()
    vs = [bm.verts.new((x, -w / 2 + y, z)) for x, z in pts]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]:
        v.co.y += w
    me = bpy.data.meshes.new('p'); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new('p', me); sc.collection.objects.link(o)
    return add(o, mat)

# crosse + poignée (profil extrudé)
profile([(-0.64, -0.03), (-0.64, 0.10), (-0.42, 0.085), (-0.24, 0.045), (-0.18, 0.04), (-0.18, -0.03), (-0.21, -0.03),
         (-0.25, -0.14), (-0.30, -0.14), (-0.29, -0.06), (-0.40, -0.07), (-0.62, -0.13)], 0.05, GOLD)
box(-0.66, -0.63, -0.13, 0.10, 0.055, BLACK)                    # plaque de couche
box(-0.18, 0.16, -0.035, 0.05, 0.046, GOLD)                     # boîtier
box(-0.02, 0.055, -0.14, -0.03, 0.034, BLACK)                   # chargeur
box(0.16, 0.46, -0.03, 0.035, 0.05, GOLD)                       # garde-main
for i in range(6):                                              # évents du garde-main
    box(0.19 + i * 0.045, 0.215 + i * 0.045, -0.012, 0.018, 0.052, BLACK)
cyl(0.16, 0.80, 0.012, 0.011, 0.01, BLACK)                      # canon
cyl(0.80, 0.88, 0.021, 0.021, 0.01, BLACK)                      # frein de bouche
for i in range(3):
    cyl(0.815 + i * 0.022, 0.825 + i * 0.022, 0.0225, 0.0225, 0.01, GOLD)
# lunette
ZS = 0.115
cyl(-0.13, 0.20, 0.018, 0.018, ZS, BLACK)
cyl(0.20, 0.28, 0.018, 0.032, ZS, BLACK)
cyl(0.28, 0.32, 0.032, 0.032, ZS, BLACK)
cyl(-0.18, -0.13, 0.026, 0.018, ZS, BLACK)
cyl(0.305, 0.322, 0.0335, 0.0335, ZS, GOLD)
cyl(-0.175, -0.165, 0.027, 0.027, ZS, GOLD)
bpy.ops.mesh.primitive_cylinder_add(radius=0.029, depth=0.002, location=(0.3215, 0, ZS), rotation=(0, math.radians(90), 0))
add(bpy.context.object, GLASS)
bpy.ops.mesh.primitive_cylinder_add(radius=0.022, depth=0.002, location=(-0.181, 0, ZS), rotation=(0, math.radians(90), 0))
add(bpy.context.object, GLASS)
for x in (-0.05, 0.12):                                         # anneaux de montage dorés
    cyl(x - 0.012, x + 0.012, 0.022, 0.022, ZS, GOLD)
    box(x - 0.012, x + 0.012, 0.05, ZS - 0.015, 0.03, GOLD)
bpy.ops.mesh.primitive_cylinder_add(radius=0.013, depth=0.03, location=(0.04, 0, ZS + 0.03)); add(bpy.context.object, GOLD)   # tourelles
bpy.ops.mesh.primitive_cylinder_add(radius=0.013, depth=0.03, location=(0.04, 0.03, ZS), rotation=(math.radians(90), 0, 0)); add(bpy.context.object, GOLD)
# levier de culasse
bpy.ops.mesh.primitive_cylinder_add(radius=0.006, depth=0.07, location=(-0.10, 0.05, 0.02), rotation=(math.radians(70), 0, 0)); add(bpy.context.object, BLACK)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.012, location=(-0.10, 0.083, 0.0)); add(bpy.context.object, BLACK)
# pontet + détente
bpy.ops.mesh.primitive_torus_add(major_radius=0.028, minor_radius=0.004, location=(-0.07, 0, -0.05), rotation=(math.radians(90), 0, 0)); add(bpy.context.object, BLACK)

bpy.ops.object.empty_add(location=(0, 0, 0)); rifle = bpy.context.object
for o in parts:
    o.parent = rifle

# ---------- environnement bleu nuit, bokeh, lumières cyan/turquoise ----------
w = sc.world.node_tree.nodes['Background']
w.inputs['Color'].default_value = (0.003, 0.009, 0.02, 1); w.inputs['Strength'].default_value = 1.0
random.seed(8)
bm1 = S.emis_mat('bk', (0.2, 0.95, 1.0), 8); bm2 = S.emis_mat('bk2', (0.9, 1.0, 1.0), 5)
for i in range(110):
    a = random.uniform(0, 2 * math.pi); r = random.uniform(2.0, 5.0)
    p = Vector((r * math.cos(a), r * math.sin(a), random.uniform(-1.5, 1.8)))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(0.01, 0.03), location=p, segments=10, ring_count=5)
    bpy.context.object.data.materials.append(bm1 if i % 3 else bm2)
def area(loc, col, e, size):
    bpy.ops.object.light_add(type='AREA', location=loc); l = bpy.context.object
    l.data.color = col; l.data.energy = e; l.data.size = size
    c = l.constraints.new('TRACK_TO'); c.target = rifle; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return l
area((0.3, -1.2, 0.9), (0.95, 0.98, 1.0), 90, 1.2)            # clé blanche
area((0.1, 0.0, 1.6), (0.85, 0.97, 1.0), 260, 2.5)             # boîte à lumière au-dessus (reflets dorés)
area((0.2, 1.4, 0.2), (0.4, 0.95, 1.0), 120, 1.8)              # panneau cyan arrière
L1 = area((-1.0, 0.8, 0.6), (0.15, 0.95, 1.0), 140, 0.8)       # contre-jour cyan
L2 = area((1.2, 0.6, -0.4), (0.1, 1.0, 0.75), 90, 0.6)         # turquoise
for f in range(1, N + 1, 6):
    a = f / N * math.pi * 2
    L1.location = (-1.0 * math.cos(a), 1.0 * math.sin(a) + 0.5, 0.6)
    L1.keyframe_insert('location', frame=f)
    L2.location = (1.2 * math.cos(a * 0.7), -0.8 * math.sin(a * 0.7), -0.4)
    L2.keyframe_insert('location', frame=f)

# ---------- caméra : orbite autour du sniper puis poussée vers la lunette ----------
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 42; cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 2.4
C = Vector((0.1, 0, 0.04))
LENS = Vector((0.33, 0, ZS))
for f in range(1, N + 1):
    t = (f - 1) / (N - 1); e = S.ease(t)
    ang = math.radians(-70 + 250 * e)
    rad = 1.75 - 0.85 * e
    z = 0.12 + 0.18 * math.sin(math.pi * t)
    loc = C + Vector((rad * math.cos(ang), rad * math.sin(ang), z))
    tgt = C.lerp(LENS, S.ease((t - 0.55) / 0.45))
    if t > 0.75:   # poussée finale vers l'objectif de la lunette
        u = S.ease((t - 0.75) / 0.25)
        loc = loc.lerp(LENS + Vector((0.30, -0.10, 0.04)), u)
    cam.location = loc
    S.look_at(cam, tgt, roll=math.radians(8) * math.sin(math.pi * t))
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.dof.focus_distance = (tgt - loc).length; cam.data.dof.keyframe_insert('focus_distance', frame=f)
# légère rotation propre de l'arme (flottement)
for f, rz in [(1, -0.1), (N, 0.15)]:
    rifle.rotation_euler = (0, 0, rz); rifle.keyframe_insert('rotation_euler', frame=f)

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else (
    [1, 40, 80, 110, 135] if TEST else sorted(set(list(range(1, N + 1, STEP)) + [N])))
for f in frames:
    p = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(p):
        continue
    sc.frame_set(f); sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
print('DONE')
