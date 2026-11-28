# Bullet-cam 3D à 1:54 : après l'animation de caméra (plan du porche), une balle de sniper
# arrive du côté du joueur, la caméra la suit en tournant autour d'elle (la balle tourne sur
# elle-même), puis elle touche l'ennemi dans l'encadrement de la porte.
# Décor = reconstruction 2.5D (profondeur MiDaS) du dernier plan de l'animation ; ennemi = découpe sur plan.
# usage: python3 bullet6.py WORKDIR OUTDIR [--test]
import bpy, bmesh, sys, os, math, random
import numpy as np
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene25d as S

WD, OUT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
N = int(os.environ.get('N', 132))
F_IN, F_ORB, F_HIT = 20, 98, 114          # entrée, fin de l'orbite, impact
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 10)))
sc.render.resolution_y = 886
sc.render.motion_blur_shutter = 0.5
sc.render.film_transparent = False

inv = np.load(os.path.join(WD, 'plate_inv.npy'))
S.depth_mesh('bg', os.path.join(WD, 'plate_bg.png'), inv, step=3, pad=0.6)
wn = sc.world.node_tree.nodes['Background']
wn.inputs['Color'].default_value = (0.75, 0.78, 0.8, 1); wn.inputs['Strength'].default_value = 0.9

ZE = 12.0
S.card('enemy', os.path.join(WD, 'soldier_fg.png'), (600, 150, 700, 340), ZE)
T = S.ray(660 / S.W_SRC, 212 / S.H_SRC) * ZE                    # point d'impact (torse)
B0 = Vector((0.32, -0.55, -0.20))                                # derrière la caméra, à droite (côté du tireur)
D = (T - B0).normalized()
UPW = Vector((0, 0, 1))
SIDE = D.cross(UPW).normalized(); UP = SIDE.cross(D).normalized()
L = (T - B0).length
print('path length', L)

# ---------------------------------------------------------------- balle
def revolve(profile, segs=48):
    bm = bmesh.new(); rings = []
    for (r, y) in profile:
        if r < 1e-6: rings.append(bm.verts.new((0, y, 0)))
        else: rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segs), y, r * math.sin(2 * math.pi * i / segs))) for i in range(segs)])
    for j in range(len(rings) - 1):
        A, Bv = rings[j], rings[j + 1]
        for i in range(segs):
            i2 = (i + 1) % segs
            if not isinstance(A, list): bm.faces.new((A, Bv[i2], Bv[i]))
            elif not isinstance(Bv, list): bm.faces.new((A[i], A[i2], Bv))
            else: bm.faces.new((A[i], A[i2], Bv[i2], Bv[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('bullet'); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    return me

R0, LEN = 0.012, 0.085
prof = [(0.0, 0.0), (R0 * 0.86, 0.0), (R0 * 0.93, 0.002), (R0, 0.006), (R0, 0.028), (R0 * 0.94, 0.0295), (R0 * 0.94, 0.0325), (R0, 0.034), (R0, 0.044)]
for k in range(1, 15):                         # ogive
    t = k / 14
    prof.append((R0 * math.cos(t * math.pi / 2) ** 0.85, 0.044 + (LEN - 0.044) * math.sin(t * math.pi / 2) ** 0.9))
prof[-1] = (0.0, LEN)
bul = bpy.data.objects.new('bullet', revolve(prof)); sc.collection.objects.link(bul)
m = bpy.data.materials.new('copper'); m.use_nodes = True; nt = m.node_tree
pb = nt.nodes['Principled BSDF']
pb.inputs['Base Color'].default_value = (0.95, 0.52, 0.28, 1); pb.inputs['Metallic'].default_value = 1.0
pb.inputs['Roughness'].default_value = 0.16
# rayures longitudinales (traces de rayures du canon) : rendent la rotation visible
tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
mth = nt.nodes.new('ShaderNodeMath'); mth.operation = 'ARCTAN2'
nt.links.new(tc.outputs['Object'], sep.inputs[0]); nt.links.new(sep.outputs['Z'], mth.inputs[0]); nt.links.new(sep.outputs['X'], mth.inputs[1])
mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 6 / math.pi
nt.links.new(mth.outputs[0], mul.inputs[0])
fr = nt.nodes.new('ShaderNodeMath'); fr.operation = 'FRACT'; nt.links.new(mul.outputs[0], fr.inputs[0])
ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = 0.08; ramp.color_ramp.elements[1].position = 0.14
nt.links.new(fr.outputs[0], ramp.inputs[0])
mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'
mx.inputs['A'].default_value = (0.35, 0.16, 0.08, 1); mx.inputs['B'].default_value = (0.95, 0.52, 0.28, 1)
nt.links.new(ramp.outputs['Color'], mx.inputs['Factor']); nt.links.new(mx.outputs['Result'], pb.inputs['Base Color'])
rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.42; rr.inputs['To Max'].default_value = 0.14
nt.links.new(ramp.outputs['Color'], rr.inputs['Value']); nt.links.new(rr.outputs['Result'], pb.inputs['Roughness'])
bul.data.materials.append(m)
bul.rotation_mode = 'QUATERNION'

def bpos(f):
    """paramètre le long de la trajectoire : traversée rapide, ralenti (bullet time), accélération finale"""
    if f <= F_IN: s = 0.05 * (f - 1) / (F_IN - 1)
    elif f <= F_ORB: s = 0.05 + 0.73 * (f - F_IN) / (F_ORB - F_IN)
    elif f <= F_HIT: u = (f - F_ORB) / (F_HIT - F_ORB); s = 0.78 + 0.22 * u ** 1.6
    else: s = 1.0
    return B0 + D * (L * s - (0.0 if f < F_HIT else 0.0))

base_q = D.to_track_quat('Y', 'Z')
for f in range(1, N + 1):
    p = bpos(f)
    if f >= F_HIT: p = T - D * 0.02
    bul.location = p
    spin = math.radians(26) * f                                   # rotation sur son axe
    bul.rotation_quaternion = base_q @ Matrix.Rotation(spin, 4, 'Y').to_quaternion()
    bul.keyframe_insert('location', frame=f); bul.keyframe_insert('rotation_quaternion', frame=f)
    bul.hide_render = f > F_HIT + 1; bul.keyframe_insert('hide_render', frame=f)

# ---------------------------------------------------------------- traînée + ondes de choc
def tmat(name, col, strength):
    mm = bpy.data.materials.new(name); mm.use_nodes = True; t = mm.node_tree; t.nodes.clear()
    o = t.nodes.new('ShaderNodeOutputMaterial'); em = t.nodes.new('ShaderNodeEmission'); tr = t.nodes.new('ShaderNodeBsdfTransparent')
    mxs = t.nodes.new('ShaderNodeMixShader')
    em.inputs['Color'].default_value = (*col, 1); em.inputs['Strength'].default_value = strength
    t.links.new(tr.outputs[0], mxs.inputs[1]); t.links.new(em.outputs[0], mxs.inputs[2]); t.links.new(mxs.outputs[0], o.inputs['Surface'])
    return mm, mxs.inputs['Fac']

random.seed(5)
for j, f0 in enumerate([]):   # ondes de choc retirées (formaient un tube flou)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.016, minor_radius=0.0006, major_segments=48, minor_segments=8, location=bpos(f0) - D * 0.005)
    tor = bpy.context.object; tor.rotation_mode = 'QUATERNION'; tor.rotation_quaternion = D.to_track_quat('Z', 'Y')
    if hasattr(tor, 'cycles'): tor.cycles.use_motion_blur = False
    mm, fac = tmat(f'ring{j}', (0.75, 0.92, 1.0), 1.6); tor.data.materials.append(mm)
    for f, sc_, a in [(f0 - 1, 0.8, 0.0), (f0, 1.0, 0.45), (f0 + 8, 3.2, 0.15), (f0 + 14, 4.5, 0.0)]:
        tor.scale = (sc_, sc_, sc_ * 0.6); tor.keyframe_insert('scale', frame=f)
        fac.default_value = a; fac.keyframe_insert('default_value', frame=f)
# traînée lumineuse fine derrière la balle
trail_m, trail_fac = tmat('trail', (1.0, 0.86, 0.65), 1.4)
bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.0012, depth=1.0)
tr = bpy.context.object; tr.data.materials.append(trail_m)
if hasattr(tr, 'cycles'): tr.cycles.use_motion_blur = False; tr.rotation_mode = 'QUATERNION'
tr.data.transform(Matrix.Translation((0, 0, -0.5)))              # extrémité à l'origine, s'étend vers -Z local
tr.rotation_quaternion = D.to_track_quat('Z', 'Y')
for f in range(1, N + 1):
    p = bpos(f) if f < F_HIT else T - D * 0.02
    ln = min(0.7, (p - B0).length) if f < F_HIT + 10 else 0.001
    tr.location = p; tr.scale = (1, 1, max(ln, 0.001)); tr.keyframe_insert('location', frame=f); tr.keyframe_insert('scale', frame=f)
    trail_fac.default_value = 0.3 if f < F_HIT else max(0.0, 0.3 * (1 - (f - F_HIT) / 10)); trail_fac.keyframe_insert('default_value', frame=f)

# ---------------------------------------------------------------- impact : étincelles, éclats rouges, flash
spark = S.emis_mat('spark', (1.0, 0.62, 0.25), 18)
red = S.emis_mat('red', (0.9, 0.04, 0.03), 4)
random.seed(9)
for i in range(70):
    is_red = i >= 46
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.004, 0.009) if is_red else random.uniform(0.0015, 0.0035), location=T)
    o = bpy.context.object; o.data.materials.append(red if is_red else spark)
    v = Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))).normalized()
    v = (v - D * (1.4 if not is_red else -0.6)).normalized() * random.uniform(0.6, 2.4) * (0.6 if is_red else 1)
    for f in range(F_HIT - 1, N + 1, 2):
        t = max(0, f - F_HIT) / 60
        o.location = T - D * 0.03 + v * t * (1 - t * 0.9) + Vector((0, 0, -1.2)) * t * t
        o.keyframe_insert('location', frame=f)
        sc_ = 0.0 if f < F_HIT else max(0.05, 1 - t * 1.6); o.scale = (sc_, sc_, sc_ * (1 if is_red else 3)); o.keyframe_insert('scale', frame=f)
fl = bpy.data.lights.new('flash', 'POINT'); flo = bpy.data.objects.new('flash', fl); sc.collection.objects.link(flo)
flo.location = T - D * 0.25; fl.color = (1.0, 0.7, 0.4); fl.shadow_soft_size = 0.05
for f, e in [(1, 0), (F_HIT - 1, 0), (F_HIT, 400), (F_HIT + 4, 120), (F_HIT + 14, 0)]:
    fl.energy = e; fl.keyframe_insert('energy', frame=f)
# lueur de bouche (le tir) au tout début
mz = bpy.data.lights.new('muzzle', 'POINT'); mzo = bpy.data.objects.new('muzzle', mz); sc.collection.objects.link(mzo)
mzo.location = B0 + D * 0.35; mz.color = (1.0, 0.75, 0.45)
for f, e in [(1, 25), (4, 8), (9, 0)]:
    mz.energy = e; mz.keyframe_insert('energy', frame=f)

# ---------------------------------------------------------------- caméra
cam = S.make_camera()
cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 2.2
key = bpy.data.lights.new('key', 'POINT'); key.energy = 6; key.color = (1.0, 0.9, 0.78); key.shadow_soft_size = 0.06
ko = bpy.data.objects.new('key', key); sc.collection.objects.link(ko)
rim = bpy.data.lights.new('rim', 'POINT'); rim.energy = 5; rim.color = (0.45, 0.85, 1.0); rim.shadow_soft_size = 0.04
ro = bpy.data.objects.new('rim', rim); sc.collection.objects.link(ro)
CTR = S.ray(0.5, 0.5) * 12
END = T - D * 0.85 + SIDE * 0.22 + UP * 0.07
for f in range(1, N + 1):
    bp = bpos(f)
    if f <= F_IN:
        u = S.ease((f - 1) / (F_IN - 1))
        follow = bp - D * 0.22 + UP * 0.035 + SIDE * 0.06
        loc = Vector((0, 0, 0)).lerp(follow, u ** 1.4)
        tgt = CTR.lerp(bp + D * 0.06, u); roll = 0.0; foc = (tgt - loc).length if u > 0.5 else 8
    elif f <= F_ORB:
        u = (f - F_IN) / (F_ORB - F_IN)
        th = math.radians(300) * S.ease(u)
        rad = 0.05 + 0.07 * math.sin(math.pi * min(1, u * 1.2))
        back = 0.16 - 0.07 * math.sin(math.pi * u)
        loc = bp - D * back + (SIDE * math.cos(th) + UP * math.sin(th)) * rad + UP * 0.035 * (1 - u)
        tgt = bp + D * 0.05; roll = math.radians(25) * math.sin(th); foc = (bp - loc).length
    else:
        u = S.ease((f - F_ORB) / (N - F_ORB))
        th = math.radians(300)
        start = bpos(F_ORB) - D * 0.22 + (SIDE * math.cos(th) + UP * math.sin(th)) * 0.06
        loc = start.lerp(END, u ** 0.7)
        tgt = (bp + D * 0.05).lerp(T, S.ease(u * 1.5)); roll = math.radians(25) * math.sin(th) * (1 - u)
        foc = (bp - loc).length if f < F_HIT else (T - loc).length
    cam.location = loc; S.look_at(cam, tgt, roll=roll)
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.dof.focus_distance = max(0.05, foc); cam.data.dof.keyframe_insert('focus_distance', frame=f)
    # ouverture : large pendant l'orbite (gros bokeh), plus fermée au début et à la fin
    cam.data.dof.aperture_fstop = 8.0 if f < 8 else (1.6 if F_IN < f < F_ORB else 3.5)
    cam.data.dof.keyframe_insert('aperture_fstop', frame=f)
    ko.location = bp + UP * 0.12 + SIDE * 0.08 - D * 0.05; ko.keyframe_insert('location', frame=f)
    ro.location = bp - UP * 0.08 - SIDE * 0.1 + D * 0.06; ro.keyframe_insert('location', frame=f)

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else (
    [1, 12, 22, 45, 70, 95, 110, 116, 125] if TEST else list(range(1, N + 1)))
for f in frames:
    p = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(p): continue
    sc.frame_set(f); sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
print('DONE')
