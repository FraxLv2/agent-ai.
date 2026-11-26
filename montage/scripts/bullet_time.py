# Balle 3D au ralenti sortant de l'arme du joueur (reconstruction 2.5D de la killcam + balle modélisée)
# usage: python3 bullet_time.py WORKDIR OUTDIR [--test]
import bpy, bmesh, sys, os, math
import numpy as np
from mathutils import Vector, Matrix, Euler
sys.path.insert(0, os.path.dirname(__file__))
import scene25d as S

WD, OUT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
N = 142  # 6 temps ≈ 2.37 s
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 10)), pct=int(os.environ.get('PCT', 75)))
sc.cycles.max_bounces = 8
sc.cycles.transmission_bounces = 6

F = os.path.join(WD, 'f_26.50')
inv = np.load(F + '_inv.npy')
S.depth_mesh('bg', F + '.png', inv, step=3, pad=0.6)

MX, MY = 900, 165
ZM = S.inv_to_z(float(inv[MY, MX])) * 0.95
M = S.ray(MX / S.W_SRC, MY / S.H_SRC) * ZM          # bouche du canon
C_END = Vector((-0.30, 0.30, -0.10))  # frôle l'objectif à gauche, de trois quarts  # la balle finit contre l'objectif
AX = (C_END - M).normalized()                        # direction du vol
print('muzzle', M, 'z', ZM)

# ---------- balle : profil réel (ogive + corps + culot) révolutionné ----------
SCALE = 9.0  # exagération cinéma
prof = [(0.0, 0.0)]
for i in range(1, 13):  # ogive (x = position le long de l'axe, r = rayon), longueur 1.6 cm
    t = i / 12
    prof.append((t * 0.016, 0.0039 * math.sqrt(1 - (1 - t) ** 2.2)))
prof += [(0.020, 0.0040), (0.0205, 0.00385), (0.0215, 0.0040), (0.024, 0.0039), (0.026, 0.0034), (0.0265, 0.0)]
bm = bmesh.new()
segs = 48
rings = []
for x, r in prof:
    ring = []
    for k in range(segs):
        a = 2 * math.pi * k / segs
        # rainures de rayures (6) sur le corps
        rr = r * (0.985 if (0.0165 < x < 0.024 and (k % 8) < 2) else 1.0)
        ring.append(bm.verts.new((x, rr * math.cos(a), rr * math.sin(a))))
    rings.append(ring)
for j in range(len(rings) - 1):
    for k in range(segs):
        a, b = rings[j][k], rings[j][(k + 1) % segs]
        c, d = rings[j + 1][(k + 1) % segs], rings[j + 1][k]
        try:
            bm.faces.new((a, b, c, d))
        except ValueError:
            pass
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
me = bpy.data.meshes.new('bullet'); bm.to_mesh(me); bm.free()
for p in me.polygons:
    p.use_smooth = True
bullet = bpy.data.objects.new('bullet', me); sc.collection.objects.link(bullet)
bullet.scale = (SCALE,) * 3
mb = bpy.data.materials.new('copper'); mb.use_nodes = True
pb = mb.node_tree.nodes['Principled BSDF']
pb.inputs['Base Color'].default_value = (0.95, 0.52, 0.32, 1)
pb.inputs['Metallic'].default_value = 1.0
pb.inputs['Roughness'].default_value = 0.16
pb.inputs['Coat Weight'].default_value = 0.3
me.materials.append(mb)
# le nez (+x local) pointe vers la caméra
base_rot = Vector((-1, 0, 0)).rotation_difference(AX).to_matrix().to_4x4()

# ---------- matériaux d'effets ----------
def refr_mat(ior, alpha):
    m = bpy.data.materials.new('shock'); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    rf = nt.nodes.new('ShaderNodeBsdfRefraction'); rf.inputs['IOR'].default_value = ior
    rf.inputs['Roughness'].default_value = 0.05
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.inputs['Fac'].default_value = alpha
    nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(rf.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], o.inputs['Surface'])
    return m

shock_m = refr_mat(1.07, 0.55)
trail_m = S.emis_mat('trail', (0.85, 0.92, 1.0), 1.4, alpha=0.3)
flash_m = S.emis_mat('flash', (1.0, 0.6, 0.2), 40)

# ---------- trajectoire (ralenti "bullet time") ----------
def prog(f):
    t = (f - 1) / (N - 1)
    if t < 0.22:
        return 0.62 * S.ease(t / 0.22) if False else 0.62 * (1 - (1 - t / 0.22) ** 2)
    if t < 0.86:
        return 0.62 + 0.28 * (t - 0.22) / 0.64
    u = (t - 0.86) / 0.14
    return 0.90 + 0.10 * u ** 1.5

def bpos(f):
    return M.lerp(C_END, prog(f))

# spirale de vortex derrière la balle + ondes de choc périodiques
helix = []
for f in range(1, N + 1):
    s = prog(f)
    bullet.matrix_world = Matrix.Translation(bpos(f)) @ base_rot @ Matrix.Rotation(f * 0.09, 4, 'X') @ Matrix.Scale(SCALE, 4)
    bullet.keyframe_insert('location', frame=f)
    bullet.keyframe_insert('rotation_euler', frame=f)
    bullet.keyframe_insert('scale', frame=f)

# perpendiculaires à l'axe
up = Vector((0, 0, 1))
P1 = AX.cross(up).normalized(); P2 = AX.cross(P1).normalized()

for i, f0 in enumerate(range(6, N - 10, 7)):
    bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.07, major_segments=48, minor_segments=10)
    t = bpy.context.object; t.data.materials.append(shock_m)
    pos = bpos(f0) - AX * 0.02
    t.location = pos
    t.rotation_euler = AX.to_track_quat('Z', 'Y').to_euler()
    for f, sc_, hid in [(f0 - 1, 0.001, True), (f0, 0.025, False), (f0 + 26, 0.16, False), (f0 + 27, 0.16, True)]:
        t.scale = (sc_, sc_, sc_ * 0.6); t.keyframe_insert('scale', frame=max(1, f))
        t.hide_render = hid; t.keyframe_insert('hide_render', frame=max(1, f))

# traînée : fine spirale émissive (courbe) le long de la trajectoire
cu = bpy.data.curves.new('helix', 'CURVE'); cu.dimensions = '3D'
cu.bevel_depth = 0.0012; cu.bevel_resolution = 2
sp = cu.splines.new('POLY')
NP = 400
sp.points.add(NP - 1)
for k in range(NP):
    s = k / (NP - 1)
    p = M.lerp(C_END, s)
    a = s * 140
    r = 0.010 + 0.004 * math.sin(s * 9)
    q = p + (P1 * math.cos(a) + P2 * math.sin(a)) * r
    sp.points[k].co = (*q, 1)
hel = bpy.data.objects.new('helix', cu)  # spirale désactivée (rendu brouillon)

cu.bevel_factor_mapping_start = 'SPLINE'; cu.bevel_factor_mapping_end = 'SPLINE'
for f in range(1, N + 1, 2):
    cu.bevel_factor_end = max(0.001, prog(f) - 0.004)
    cu.bevel_factor_start = max(0.0, prog(f) - 0.30)
    cu.keyframe_insert('bevel_factor_end', frame=f)
    cu.keyframe_insert('bevel_factor_start', frame=f)

# lumières : flash de bouche chaud + contre-jour froid
bpy.ops.object.light_add(type='POINT', location=M)
fl = bpy.context.object; fl.data.color = (1, 0.55, 0.2); fl.data.shadow_soft_size = 0.2
for f, e in [(1, 500), (12, 150), (40, 25), (N, 15)]:
    fl.data.energy = e; fl.data.keyframe_insert('energy', frame=f)
bpy.ops.object.light_add(type='AREA', location=M + Vector((-1.5, -1.0, 2.0)))
ar = bpy.context.object; ar.data.energy = 35; ar.data.size = 2; ar.data.color = (0.7, 0.8, 1.0)
c = ar.constraints.new('TRACK_TO'); c.target = bullet
bpy.ops.object.light_add(type='AREA', location=Vector((1.2, 0.5, -0.4)))
ar2 = bpy.context.object; ar2.data.energy = 18; ar2.data.size = 1.5; ar2.data.color = (1.0, 0.75, 0.55)
c = ar2.constraints.new('TRACK_TO'); c.target = bullet

# environnement visible seulement dans les reflets (pas par la caméra)
wn = sc.world.node_tree
lp = wn.nodes.new('ShaderNodeLightPath'); bgc = wn.nodes.new('ShaderNodeBackground')
bgc.inputs['Strength'].default_value = 1.0
tc = wn.nodes.new('ShaderNodeTexCoord'); sx = wn.nodes.new('ShaderNodeSeparateXYZ')
cr = wn.nodes.new('ShaderNodeValToRGB')
cr.color_ramp.elements[0].position = 0.42; cr.color_ramp.elements[0].color = (0.015, 0.01, 0.008, 1)
cr.color_ramp.elements[1].position = 0.75; cr.color_ramp.elements[1].color = (0.55, 0.62, 0.75, 1)
el = cr.color_ramp.elements.new(0.52); el.color = (1.4, 0.8, 0.45, 1)
mr = wn.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -1.0
wn.links.new(tc.outputs['Generated'], sx.inputs[0]); wn.links.new(sx.outputs['Z'], mr.inputs['Value'])
wn.links.new(mr.outputs[0], cr.inputs['Fac']); wn.links.new(cr.outputs['Color'], bgc.inputs['Color'])
dark = wn.nodes['Background']
mx = wn.nodes.new('ShaderNodeMixShader')
wn.links.new(lp.outputs['Is Camera Ray'], mx.inputs['Fac'])
wn.links.new(bgc.outputs[0], mx.inputs[1]); wn.links.new(dark.outputs[0], mx.inputs[2])
wn.links.new(mx.outputs[0], wn.nodes['World Output'].inputs['Surface'])

# ---------- caméra ----------
cam = S.make_camera()
cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 2.0
CENTER = S.ray(0.5, 0.5) * 8

for f in range(1, N + 1):
    t = (f - 1) / (N - 1)
    B = bpos(f)
    e = S.ease(t)
    # léger travelling avant + latéral (parallaxe réelle sur le décor reconstruit)
    cam.location = Vector((0.30 * e, 0.55 * e, 0.04 * math.sin(math.pi * t)))
    # panoramique qui suit la balle en la gardant dans le tiers gauche/centre
    k = 0.15 + 0.5 * S.ease((f - 8) / 60)
    tgt = CENTER.lerp(B, min(k, 0.55 if f > 120 else 0.8))
    S.look_at(cam, tgt, roll=math.radians(-6) * math.sin(math.pi * t))
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.dof.focus_distance = max(0.1, (B - cam.location).length)
    cam.data.dof.keyframe_insert('focus_distance', frame=f)
    cam.data.dof.aperture_fstop = 2.8
    cam.data.dof.keyframe_insert('aperture_fstop', frame=f)

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else ([1, 20, 50, 80, 110, 130, 140] if TEST else range(1, N + 1))
for f in frames:
    p = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(p):
        continue
    sc.frame_set(f)
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
print('DONE')
