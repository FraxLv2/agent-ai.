# Traversée du décor : depuis le survol de Nuketown, la caméra quitte sa trajectoire, accélère,
# vire vers le garage ouvert et s'engouffre dedans (reconstruction 2.5D par profondeur MiDaS).
# usage: python3 flythrough4.py WORKDIR OUTDIR [--test]
import bpy, sys, os, math, random
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import scene25d as S

WD, OUT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
N = int(os.environ.get('N', 97))
STEP = int(os.environ.get('STEP', 1))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 6)))
sc.render.motion_blur_shutter = 0.8
F = os.path.join(WD, 'f_9.36')
inv = np.load(F + '_inv.npy')
S.depth_mesh('bg', F + '.png', inv, step=3, pad=0.7)
# ciel lointain pour masquer le vide derrière le maillage
w = sc.world.node_tree.nodes['Background']
w.inputs['Color'].default_value = (0.55, 0.72, 0.9, 1); w.inputs['Strength'].default_value = 1.0

GAR = S.ray(1000 / S.W_SRC, 235 / S.H_SRC)              # direction de l'entrée du garage
zg = S.inv_to_z(float(np.median(inv[200:280, 930:1060])))
TGT = GAR * zg
print('garage z', zg)
# traînées lumineuses cyan (lignes de vitesse 3D) qui apparaissent avec l'accélération
random.seed(4)
sm = S.emis_mat('streak', (0.2, 0.85, 1.0), 2.5)
streaks = []
for i in range(38):
    t = random.uniform(0.15, 1.0)
    base = TGT * t + Vector((random.uniform(-1.6, 1.6), 0, random.uniform(-0.9, 1.2)))
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=random.uniform(0.004, 0.012), depth=random.uniform(0.6, 1.8), location=base)
    o = bpy.context.object; o.data.materials.append(sm)
    o.rotation_euler = TGT.normalized().to_track_quat('Z', 'Y').to_euler()
    for f, hd in [(1, True), (int(N * 0.45), False)]:
        o.hide_render = hd; o.keyframe_insert('hide_render', frame=f)

cam = S.make_camera()
cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 5.6
O = Vector((0, 0, 0))
for f in range(1, N + 1):
    t = (f - 1) / (N - 1)
    # avance douce (continuité du survol) puis accélération franche vers le garage
    s = 0.10 * t + 0.92 * t ** 3.2
    loc = O.lerp(TGT * 0.97, s)
    loc.z += 0.25 * math.sin(math.pi * min(1, t * 1.3)) * (1 - t)
    look = S.ray(0.5, 0.5) * 6
    tgt = look.lerp(TGT * 1.6, S.ease(min(1, t * 1.4)))
    cam.location = loc
    S.look_at(cam, tgt, roll=math.radians(-14) * math.sin(math.pi * min(1, t * 1.1)))
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    cam.data.dof.focus_distance = max(0.3, (TGT - loc).length)
    cam.data.dof.keyframe_insert('focus_distance', frame=f)

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else (
    [1, 30, 55, 75, 88, 97] if TEST else sorted(set(list(range(1, N + 1, STEP)) + [N])))
for f in frames:
    p = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(p):
        continue
    sc.frame_set(f); sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
print('DONE')
