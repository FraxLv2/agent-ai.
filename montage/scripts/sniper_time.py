# Freeze 3D sur le 2e tir de sniper : la caméra traverse la lunette et suit la balle jusqu'au 2e soldat
# Scène en couches : HUD/lunette (trou central) -> soldat découpé -> décor ; balle modélisée ; impact en étincelles
# usage: python3 sniper_time.py WORKDIR OUTDIR [--test]
import bpy, bmesh, sys, os, math, random
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(__file__))
import scene25d as S

WD, OUT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
N = int(os.environ.get('N', 175))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 10)), pct=int(os.environ.get('PCT', 75)))
sc.cycles.transparent_max_bounces = 24
P = lambda n: os.path.join(WD, n)

Z_HUD, Z_EN, Z_BG = 0.6, 9.0, 15.0
S.card('bg', P('sn_bg.png'), (-500, -300, 1608, 810), Z_BG)
enemy = S.card('enemy', P('sn_enemy.png'), (503, 22, 751, 432), Z_EN)
S.card('hud', P('sn_hud.png'), (0, 0, 1108, 510), Z_HUD)

T = S.ray(615 / S.W_SRC, 225 / S.H_SRC) * (Z_EN - 0.05)   # impact : torse sous la croix
B0 = Vector((0.0, 0.55, -0.04))
AX = (T - B0).normalized()
up = Vector((0, 0, 1)); P1 = AX.cross(up).normalized(); P2 = AX.cross(P1).normalized()

# ---------- balle de sniper (profil long, révolution) ----------
SCALE = 4.5
prof = [(0.0, 0.0)]
for i in range(1, 16):
    t = i / 15
    prof.append((t * 0.024, 0.0043 * math.sqrt(1 - (1 - t) ** 2.4)))
prof += [(0.030, 0.0044), (0.0305, 0.0042), (0.0315, 0.0044), (0.036, 0.0043), (0.0385, 0.0036), (0.039, 0.0)]
bm = bmesh.new(); segs = 48; rings = []
for x, r in prof:
    rings.append([bm.verts.new((x, r * math.cos(2 * math.pi * k / segs), r * math.sin(2 * math.pi * k / segs))) for k in range(segs)])
for j in range(len(rings) - 1):
    for k in range(segs):
        try:
            bm.faces.new((rings[j][k], rings[j][(k + 1) % segs], rings[j + 1][(k + 1) % segs], rings[j + 1][k]))
        except ValueError:
            pass
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
me = bpy.data.meshes.new('bullet'); bm.to_mesh(me); bm.free()
for p in me.polygons:
    p.use_smooth = True
bullet = bpy.data.objects.new('bullet', me); sc.collection.objects.link(bullet)
mb = bpy.data.materials.new('copper'); mb.use_nodes = True
pb = mb.node_tree.nodes['Principled BSDF']
pb.inputs['Base Color'].default_value = (0.95, 0.55, 0.33, 1)
pb.inputs['Metallic'].default_value = 1.0
pb.inputs['Roughness'].default_value = 0.16
me.materials.append(mb)
ROT = Vector((-1, 0, 0)).rotation_difference(AX).to_matrix().to_4x4()   # nez en avant

# environnement visible seulement dans les reflets
wn = sc.world.node_tree
lp = wn.nodes.new('ShaderNodeLightPath'); bgc = wn.nodes.new('ShaderNodeBackground')
tc = wn.nodes.new('ShaderNodeTexCoord'); sx = wn.nodes.new('ShaderNodeSeparateXYZ'); cr = wn.nodes.new('ShaderNodeValToRGB')
cr.color_ramp.elements[0].position = 0.42; cr.color_ramp.elements[0].color = (0.015, 0.01, 0.008, 1)
cr.color_ramp.elements[1].position = 0.75; cr.color_ramp.elements[1].color = (0.5, 0.58, 0.72, 1)
cr.color_ramp.elements.new(0.52).color = (1.4, 0.8, 0.45, 1)
mr = wn.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -1.0
wn.links.new(tc.outputs['Generated'], sx.inputs[0]); wn.links.new(sx.outputs['Z'], mr.inputs['Value'])
wn.links.new(mr.outputs[0], cr.inputs['Fac']); wn.links.new(cr.outputs['Color'], bgc.inputs['Color'])
mx = wn.nodes.new('ShaderNodeMixShader')
wn.links.new(lp.outputs['Is Camera Ray'], mx.inputs['Fac'])
wn.links.new(bgc.outputs[0], mx.inputs[1]); wn.links.new(wn.nodes['Background'].outputs[0], mx.inputs[2])
wn.links.new(mx.outputs[0], wn.nodes['World Output'].inputs['Surface'])

IMPACT = N - 15

def prog(f):
    if f <= 28:
        return 0.06 * (f - 1) / 27
    if f <= IMPACT:
        u = (f - 28) / (IMPACT - 28)
        return 0.06 + 0.94 * (0.85 * u + 0.15 * u * u)
    return 1.0

def bpos(f):
    return B0.lerp(T, prog(f))

for f in range(1, N + 1):
    bullet.matrix_world = Matrix.Translation(bpos(f)) @ ROT @ Matrix.Rotation(f * 0.12, 4, 'X') @ Matrix.Scale(SCALE, 4)
    for prop in ('location', 'rotation_euler', 'scale'):
        bullet.keyframe_insert(prop, frame=f)
    bullet.hide_render = f > IMPACT or f < 6; bullet.keyframe_insert('hide_render', frame=f)

# ondes de choc réfractives derrière la balle
m = bpy.data.materials.new('shock'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
o = nt.nodes.new('ShaderNodeOutputMaterial'); rf = nt.nodes.new('ShaderNodeBsdfRefraction'); rf.inputs['IOR'].default_value = 1.07
trn = nt.nodes.new('ShaderNodeBsdfTransparent'); mxs = nt.nodes.new('ShaderNodeMixShader'); mxs.inputs['Fac'].default_value = 0.55
nt.links.new(trn.outputs[0], mxs.inputs[1]); nt.links.new(rf.outputs[0], mxs.inputs[2]); nt.links.new(mxs.outputs[0], o.inputs['Surface'])
for f0 in range(30, IMPACT - 4, 8):
    bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.07, major_segments=48, minor_segments=10)
    t = bpy.context.object; t.data.materials.append(m)
    t.location = bpos(f0); t.rotation_euler = AX.to_track_quat('Z', 'Y').to_euler()
    for f, s_, hid in [(f0 - 1, 0.001, True), (f0, 0.03, False), (f0 + 30, 0.22, False), (f0 + 31, 0.22, True)]:
        t.scale = (s_, s_, s_ * 0.6); t.keyframe_insert('scale', frame=max(1, f))
        t.hide_render = hid; t.keyframe_insert('hide_render', frame=max(1, f))

# traînée de vapeur : cône translucide qui s'allonge derrière la balle
trail_m = S.emis_mat('trail', (0.8, 0.88, 1.0), 0.7, alpha=0.07)
bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.0, radius2=0.009, depth=1.0)
trail = bpy.context.object; trail.data.materials.append(trail_m)
trail.data.transform(Matrix.Translation((0, 0, -0.5)))  # pointe en +Z = origine
for f in range(1, N + 1):
    L = max(0.01, min(2.5, (bpos(f) - B0).length))
    trail.matrix_world = Matrix.Translation(bpos(f) - AX * 0.02) @ AX.to_track_quat('Z', 'Y').to_matrix().to_4x4() @ Matrix.Diagonal((1, 1, L, 1))
    for prop in ('location', 'rotation_euler', 'scale'):
        trail.keyframe_insert(prop, frame=f)
    trail.hide_render = f > IMPACT + 6; trail.keyframe_insert('hide_render', frame=f)

# impact : gerbe d'étincelles + flash + recul du soldat
random.seed(4)
spark_m = S.emis_mat('spark', (1.0, 0.5, 0.12), 7)
for i in range(60):
    d = (-AX * 0.6 + Vector((random.gauss(0, 1), random.gauss(0, 1), random.gauss(0.3, 1)))).normalized()
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.0035, depth=random.uniform(0.04, 0.12))
    s = bpy.context.object; s.data.materials.append(spark_m)
    s.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    dist = random.uniform(0.4, 1.6)
    for f, loc, hid, scl in [(IMPACT - 1, T, True, 1), (IMPACT, T, False, 1), (IMPACT + 16, T + d * dist + Vector((0, 0, -0.25)), False, 0.3), (IMPACT + 17, T + d * dist, True, 0.3)]:
        s.location = loc; s.keyframe_insert('location', frame=f)
        s.scale = (scl,) * 3; s.keyframe_insert('scale', frame=f)
        s.hide_render = hid; s.keyframe_insert('hide_render', frame=f)
bpy.ops.object.light_add(type='POINT', location=T - AX * 0.3)
fl = bpy.context.object; fl.data.color = (1, 0.6, 0.25)
for f, e in [(1, 0), (IMPACT - 1, 0), (IMPACT, 500), (IMPACT + 10, 60), (N, 0)]:
    fl.data.energy = e; fl.data.keyframe_insert('energy', frame=f)
el = enemy.location.copy()
for f, off in [(IMPACT, 0), (IMPACT + 4, 0.25), (N, 0.35)]:
    enemy.location = el + AX * off; enemy.keyframe_insert('location', frame=f)

# éclairage de la balle
bpy.ops.object.light_add(type='AREA', location=(-1.2, 2.0, 1.5))
a1 = bpy.context.object; a1.data.energy = 40; a1.data.size = 2; a1.data.color = (0.75, 0.85, 1.0)
a1.constraints.new('TRACK_TO').target = bullet
bpy.ops.object.light_add(type='AREA', location=(1.0, 1.0, -0.6))
a2 = bpy.context.object; a2.data.energy = 25; a2.data.size = 1.5; a2.data.color = (1.0, 0.7, 0.45)
a2.constraints.new('TRACK_TO').target = bullet
for a in (a1, a2):  # les lumières suivent la balle
    c = a.constraints.new('CHILD_OF'); c.target = bullet; c.use_rotation_x = c.use_rotation_y = c.use_rotation_z = False; c.use_scale_x = c.use_scale_y = c.use_scale_z = False

# ---------- caméra : fixe -> traverse la lunette -> poursuite latérale -> plan sur l'impact ----------
cam = S.make_camera()
cam.data.dof.use_dof = True
L = (T - B0).length
for f in range(1, N + 1):
    B = bpos(min(f, IMPACT))
    w = S.ease((f - 14) / 40)
    ang = math.radians(20 + 55 * S.ease((f - 40) / (IMPACT - 40)))
    off = 0.05 + 0.22 * S.ease((f - 45) / (IMPACT - 45))
    back = 0.42
    s_cam = min(prog(min(f, IMPACT)) * L - back, L - 2.8)   # la caméra s'arrête à 2 m du soldat
    s_cam -= 0.2 * S.ease((f - IMPACT) / 15) if f > IMPACT else 0
    chase = B0 + AX * s_cam + (P1 * math.cos(ang) + P2 * math.sin(ang)) * off
    cam.location = Vector((0, 0, 0)).lerp(chase, w)
    look = S.ray(0.5, 0.5) * Z_EN
    k = S.ease((f - 115) / 40)   # le regard passe de la balle au point d'impact
    tgt = look.lerp((B + AX * 0.3).lerp(T, k), w)
    S.look_at(cam, tgt, roll=math.radians(7) * w * math.sin(math.pi * S.ease((f - 20) / (N - 20))))
    if f > IMPACT:  # secousse d'impact
        r = random.Random(f); kk = (1 - (f - IMPACT) / (N - IMPACT)) * 0.025
        cam.location += Vector((r.gauss(0, kk), r.gauss(0, kk), r.gauss(0, kk)))
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    fd = (B - cam.location).length if f < 110 else (T - cam.location).length
    cam.data.dof.focus_distance = max(0.1, fd)
    cam.data.dof.keyframe_insert('focus_distance', frame=f)
    cam.data.dof.aperture_fstop = 9 - 5 * w
    cam.data.dof.keyframe_insert('aperture_fstop', frame=f)

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else ([1, 30, 60, 100, 140, 162, 170] if TEST else range(1, N + 1))
for f in frames:
    p = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(p):
        continue
    sc.frame_set(f); sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
print('DONE')
