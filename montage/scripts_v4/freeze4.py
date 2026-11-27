# Freeze Time 3D : orbite caméra autour du joueur figé (reconstruction 2.5D + particules 3D)
# usage: python3 freeze_time.py WORKDIR OUTDIR [--test]
import bpy, sys, os, math, random
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import scene25d as S

WD, OUT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
N = int(os.environ.get('N', 217))  # 6 temps @99.4 BPM
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 10)))

F = os.path.join(WD, 'f_32.35')
bginv = np.load(F + '_bginv.npy')
bg = S.depth_mesh('bg', F + '_bg.png', bginv, step=3, pad=0.9)
wb = sc.world.node_tree.nodes['Background']; wb.inputs['Color'].default_value = (0.42, 0.62, 0.9, 1); wb.inputs['Strength'].default_value = 1.0
BBOX = (130, 138, 462, 334)
ZC = S.inv_to_z(0.29)  # profondeur médiane du personnage
zs = S.inv_to_z(bginv[BBOX[1]:BBOX[3], BBOX[0]:BBOX[2]])
ZCARD = float(np.percentile(zs, 3)) * 0.93
ZC = ZCARD
print('card z', ZCARD)
S.card('player', F + '_fg.png', BBOX, ZCARD)
# point pivot = centre du personnage
P = S.ray(300 / S.W_SRC, 235 / S.H_SRC) * ZC
print('pivot', P, 'zc', ZC)

cam = S.make_camera()
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = ZC
cam.data.dof.aperture_fstop = 2.8

# ---- particules figées : poussière (petites sphères) et étincelles (traînées) ----
random.seed(7)
dust_m = S.emis_mat('dust', (1.0, 0.86, 0.66), 0.9, alpha=0.75)
spark_m = S.emis_mat('spark', (0.3, 0.9, 1.0), 6)
ring_m = S.emis_mat('ring', (0.25, 0.9, 1.0), 5, alpha=0.6)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1)
proto = bpy.context.object; proto.data.materials.append(dust_m); proto.hide_render = True
dust = []
for i in range(170):
    z = random.uniform(3.6, ZC + 6)
    u, v = random.uniform(-0.1, 1.1), random.uniform(0.05, 1.0)
    p = S.ray(u, v) * z
    o = proto.copy(); o.data = proto.data; o.hide_render = False
    sc.collection.objects.link(o)
    r = random.uniform(0.004, 0.011) * (z / 4) ** 0.5
    o.scale = (r, r, r); o.location = p
    drift = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-0.3, 1))) * 0.04
    o.keyframe_insert('location', frame=1)
    o.location = p + drift
    o.keyframe_insert('location', frame=N)
    dust.append(o)
# étincelles/éclats près de l'arme (main levée du joueur)
muzzle = S.ray(430 / S.W_SRC, 330 / S.H_SRC) * (ZC * 0.97)   # gerbe de sable sous les pieds
for i in range(16):
    d = Vector((random.gauss(0, 1), random.gauss(-0.6, 0.6), random.gauss(0.2, 0.8))).normalized()
    dist = random.uniform(0.05, 0.8)
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.004, depth=random.uniform(0.02, 0.06))
    s = bpy.context.object
    s.data.materials.append(spark_m)
    s.location = muzzle + d * dist
    s.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    s.keyframe_insert('location', frame=1)
    s.location = muzzle + d * (dist + 0.03)
    s.keyframe_insert('location', frame=N)
# lumière chaude des étincelles
bpy.ops.object.light_add(type='POINT', location=muzzle)
bpy.context.object.data.energy = 30; bpy.context.object.data.color = (0.3, 0.9, 1.0)
bpy.ops.object.light_add(type='AREA', location=(0, 0, 3))
bpy.context.object.data.energy = 300; bpy.context.object.data.size = 6

# onde de choc "temps figé" : anneau qui s'étend autour du joueur au début
bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.012, major_segments=96, minor_segments=8)
ring = bpy.context.object; ring.data.materials.append(ring_m)
ring.location = P
ring.rotation_euler = (math.radians(90), 0, 0)
for f, s, vis in [(1, 0.2, True), (40, 9.0, True), (41, 9.0, False)]:
    ring.scale = (s, s, s); ring.keyframe_insert('scale', frame=f)
    ring.hide_render = not vis; ring.keyframe_insert('hide_render', frame=f)

# ---- orbite caméra : part de la vue d'origine, tourne, revient exactement ----
YAW, PITCH, DOLLY = math.radians(float(os.environ.get('YAW', 18))), math.radians(4), 0.18
R0 = P.length
os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else [1, 50, 90, 110, 150, 217] if TEST else sorted(set(list(range(1, N + 1, int(os.environ.get('STEP', 1)))) + [N]))


def cam_at(f):
    t = (f - 1) / (N - 1)
    a = math.sin(math.pi * S.ease(t))          # 0 -> 1 -> 0
    yaw = YAW * math.sin(math.pi * t) * 1.0 if t < 1 else 0
    yaw = YAW * a * (1 if t < 0.5 else 1)
    # second mouvement : léger dépassement de l'autre côté à la fin
    yaw -= YAW * 0.35 * math.sin(2 * math.pi * S.ease(t)) if t > 0.5 else 0
    pitch = PITCH * a
    dolly = DOLLY * a
    off = -P  # vecteur pivot -> caméra
    rot_off = Vector(off)
    rot_off.rotate(__import__('mathutils').Euler((pitch, 0, yaw)))
    loc = P + rot_off * (1 - dolly)
    return loc, a


for f in range(1, N + 1):
    loc, a = cam_at(f)
    cam.location = loc
    tgt = P.lerp(Vector((0, P.length, 0)) * 0 + S.ray(0.5, 0.5) * R0, 1 - a)
    S.look_at(cam, tgt if a < 1 else P, roll=math.radians(3) * a)
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.dof.aperture_fstop = 8 - 5.6 * a
    cam.data.dof.keyframe_insert('aperture_fstop', frame=f)

for f in frames:
    p = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(p):
        continue
    sc.frame_set(f)
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
print('DONE')
