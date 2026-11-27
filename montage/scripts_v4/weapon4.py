# Cinématique 3D du sniper du joueur : la caméra quitte la vue FPS et filme l'arme isolée (relief 2.5D)
# reflets cyan/turquoise balayants, bokeh bleu nuit, profondeur de champ
# usage: python3 weapon_cine.py WORKDIR OUTDIR [--test]
import bpy, sys, os, math, random
import numpy as np, cv2
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import scene25d as S

WD, OUT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
N = int(os.environ.get('N', 217))
STEP = int(os.environ.get('STEP', 1))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 14)), pct=int(os.environ.get('PCT', 100)))
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.cycles.max_bounces = 6
P = lambda n: os.path.join(WD, n)

# ---------- arme en relief : maillage dont l'épaisseur suit la carte de distance du masque ----------
rgba = cv2.imread(P('f_34.8_fg.png'), cv2.IMREAD_UNCHANGED)
alpha = rgba[..., 3]
x0, y0, x1, y1 = 598, 226, 862, 500
dt = cv2.distanceTransform((alpha > 100).astype(np.uint8), cv2.DIST_L2, 5)
dt = cv2.GaussianBlur(dt, (0, 0), 3)
H = np.sqrt(dt / (dt.max() + 1e-6))
Z0 = 1.0
step = 2
us = np.arange(x0, x1 + 1, step); vs = np.arange(y0, y1 + 1, step)
verts, uvs = [], []
for v in vs:
    for u in us:
        h = float(H[min(int(v), 509), min(int(u), 1107)]) * 0.05
        p = S.ray(u / S.W_SRC, v / S.H_SRC) * (Z0 - h)
        verts.append(tuple(p)); uvs.append((u / S.W_SRC, 1 - v / S.H_SRC))
nu = len(us)
faces = [(j * nu + i, (j + 1) * nu + i, (j + 1) * nu + i + 1, j * nu + i + 1) for j in range(len(vs) - 1) for i in range(nu - 1)]
me = bpy.data.meshes.new('gun'); me.from_pydata(verts, [], faces)
uvl = me.uv_layers.new()
for poly in me.polygons:
    poly.use_smooth = True
    for li in poly.loop_indices:
        uvl.data[li].uv = uvs[me.loops[li].vertex_index]
gun = bpy.data.objects.new('gun', me); sc.collection.objects.link(gun)
m = bpy.data.materials.new('gun'); m.use_nodes = True; nt = m.node_tree
pr = nt.nodes['Principled BSDF']; out = nt.nodes['Material Output']
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(P('f_34.8_fg.png')); tex.interpolation = 'Cubic'
nt.links.new(tex.outputs['Color'], pr.inputs['Base Color'])
nt.links.new(tex.outputs['Color'], pr.inputs['Emission Color'])
pr.inputs['Emission Strength'].default_value = 0.55
pr.inputs['Metallic'].default_value = 0.55
pr.inputs['Roughness'].default_value = 0.25
pr.inputs['Coat Weight'].default_value = 0.8
pr.inputs['Coat Roughness'].default_value = 0.05
trn = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
nt.links.new(tex.outputs['Alpha'], mx.inputs['Fac']); nt.links.new(trn.outputs[0], mx.inputs[1]); nt.links.new(pr.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], out.inputs['Surface'])
me.materials.append(m)

# ---------- arrière-plan : l'image FPS d'origine s'efface vers un espace bleu nuit ----------
bg = S.card('bgframe', P('f_34.8.png'), (-60, -40, 1168, 550), 6.0)
bgm = bg.data.materials[0]; bnt = bgm.node_tree
em = [n for n in bnt.nodes if n.type == 'EMISSION'][0]
bo = [n for n in bnt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
btr = bnt.nodes.new('ShaderNodeBsdfTransparent'); bmx = bnt.nodes.new('ShaderNodeMixShader')
bnt.links.new(btr.outputs[0], bmx.inputs[1]); bnt.links.new(em.outputs[0], bmx.inputs[2]); bnt.links.new(bmx.outputs[0], bo.inputs['Surface'])
for f, s_ in [(1, 1.0), (10, 1.0), (40, 0.0), (N - 22, 0.0), (N, 1.0)]:   # s'efface puis revient pour le raccord
    bmx.inputs['Fac'].default_value = s_; bmx.inputs['Fac'].keyframe_insert('default_value', frame=f)
w = sc.world.node_tree.nodes['Background']
w.inputs['Color'].default_value = (0.004, 0.012, 0.028, 1); w.inputs['Strength'].default_value = 1.0

# bokeh cyan/blanc lointain (devient visible quand le décor s'efface)
random.seed(3)
bok = S.emis_mat('bokeh', (0.3, 0.95, 1.0), 6)
bok2 = S.emis_mat('bokeh2', (0.85, 1.0, 1.0), 4)
for i in range(70):
    z = random.uniform(2.5, 5.5)
    p = S.ray(random.uniform(-0.2, 1.2), random.uniform(-0.1, 1.1)) * z
    bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(0.005, 0.014), location=p, segments=12, ring_count=6)
    o = bpy.context.object; o.data.materials.append(bok if i % 3 else bok2)
    for f, hd in [(1, True), (16, False), (N - 4, True)]:
        o.hide_render = hd; o.keyframe_insert('hide_render', frame=f)
for mm in (bok, bok2):
    e = [n for n in mm.node_tree.nodes if n.type == 'EMISSION'][0]
    base = e.inputs['Strength'].default_value
    for f, s_ in [(1, 0), (18, 0), (45, base), (N - 25, base), (N - 5, 0)]:
        e.inputs['Strength'].default_value = s_; e.inputs['Strength'].keyframe_insert('default_value', frame=f)

# ---------- lumières cyan qui balaient l'arme (reflets métalliques) ----------
G = S.ray(720 / S.W_SRC, 365 / S.H_SRC) * Z0          # centre de l'arme
LENS = S.ray(762 / S.W_SRC, 315 / S.H_SRC) * (Z0 - 0.05)
REC = S.ray(665 / S.W_SRC, 290 / S.H_SRC) * (Z0 - 0.04)   # boîtier / anneaux de lunette
STOCK = S.ray(640 / S.W_SRC, 425 / S.H_SRC) * (Z0 - 0.03)
def area(name, col, energy, size):
    bpy.ops.object.light_add(type='AREA'); l = bpy.context.object; l.name = name
    l.data.color = col; l.data.energy = energy; l.data.size = size
    c = l.constraints.new('TRACK_TO'); c.target = gun; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return l
L1 = area('cyan', (0.2, 0.95, 1.0), 60, 0.5)
L2 = area('teal', (0.1, 1.0, 0.75), 35, 0.4)
L3 = area('white', (0.9, 0.97, 1.0), 25, 0.8)
for f in range(1, N + 1, 4):
    t = f / N
    L1.location = G + Vector((-0.6 + 1.2 * t, -0.35, 0.35 * math.cos(t * 6)))
    L2.location = G + Vector((0.5 - 0.9 * t, -0.3, -0.3 + 0.4 * math.sin(t * 5)))
    L3.location = G + Vector((0.0, -0.8, 0.6))
    for l in (L1, L2, L3):
        l.keyframe_insert('location', frame=f)

for l, e0 in ((L1, 60), (L2, 35), (L3, 25)):
    for f, k in [(1, 0), (14, 0), (34, 1), (N - 28, 1), (N - 8, 0)]:
        l.data.energy = e0 * k; l.data.keyframe_insert('energy', frame=f)

# ---------- caméra : vue FPS -> gros plans -> retour ----------
cam = S.make_camera()
cd = cam.data; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 24
cd.lens = 12 / math.tan(math.atan(S.SY / 2))          # même champ vertical que la source
cd.dof.use_dof = True

def shot(f):
    """(position caméra, cible, ouverture, distance de mise au point)"""
    O = Vector((0, 0, 0))
    k = [
        (1,   O,                                         S.ray(0.5, 0.5) * 3, 16),
        (39,  REC + Vector((-0.22, -0.28, 0.06)),        REC + Vector((0.03, 0, 0)), 2.2),
        (91,  STOCK + Vector((0.02, -0.30, 0.14)),       STOCK + Vector((0.06, 0, 0.03)), 2.0),   # travelling latéral le long de l'arme
        (114, LENS + Vector((-0.10, -0.24, 0.08)),       LENS, 1.8),
        (160, LENS + Vector((0.12, -0.17, -0.03)),       LENS + Vector((-0.01, 0, 0)), 1.6),     # rotation autour de la lunette
        (192, G + Vector((0.10, -0.50, 0.02)),           G, 2.8),
        (N,   O,                                         S.ray(0.5, 0.5) * 3, 16),
    ]
    for a, b in zip(k, k[1:]):
        if a[0] <= f <= b[0]:
            u = S.ease((f - a[0]) / (b[0] - a[0]))
            return a[1].lerp(b[1], u), a[2].lerp(b[2], u), a[3] + (b[3] - a[3]) * u
    return k[-1][1], k[-1][2], k[-1][3]

for f in range(1, N + 1):
    loc, tgt, fs = shot(f)
    cam.location = loc
    S.look_at(cam, tgt, roll=math.radians(6) * math.sin(math.pi * f / N))
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    cd.dof.focus_distance = max(0.05, (tgt - loc).length)
    cd.dof.aperture_fstop = fs
    cd.dof.keyframe_insert('focus_distance', frame=f); cd.dof.keyframe_insert('aperture_fstop', frame=f)

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else (
    [1, 25, 45, 80, 114, 150, 190, 210] if TEST else sorted(set(list(range(1, N + 1, STEP)) + [N])))
for f in frames:
    p = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(p):
        continue
    sc.frame_set(f); sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
print('DONE')
