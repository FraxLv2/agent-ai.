# Transition « écran flottant » : le gameplay quitte le plein écran, devient un écran arrondi à halo cyan
# flottant dans un espace bleu nuit, pivote en perspective, la caméra recule puis fonce dedans.
# usage: python3 float_screen.py WORKDIR OUTDIR [--test]
import bpy, sys, os, math, random
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import scene25d as S

WD, OUT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
N = 120
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 8)), pct=int(os.environ.get('PCT', 100)))
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.cycles.max_bounces = 4
P = lambda n: os.path.join(WD, n)

D = 3.0
VFOV = math.radians(40)
PH = 2 * D * math.tan(VFOV / 2)
PW = PH * 1108 / 510

bpy.ops.object.empty_add(location=(0, D, 0)); piv = bpy.context.object

def plane(name, w, h, y):
    bpy.ops.mesh.primitive_plane_add(size=1)
    o = bpy.context.object; o.name = name
    o.scale = (w, h, 1); bpy.ops.object.transform_apply(scale=True)
    o.rotation_euler = (math.radians(90), 0, 0); o.location = (0, y, 0)
    o.parent = piv; o.matrix_parent_inverse = piv.matrix_world.inverted()
    return o

def rgba_emis(name, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial'); t = nt.nodes.new('ShaderNodeTexImage'); e = nt.nodes.new('ShaderNodeEmission')
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
    e.inputs['Strength'].default_value = strength
    nt.links.new(t.outputs['Color'], e.inputs['Color']); nt.links.new(t.outputs['Alpha'], mx.inputs['Fac'])
    nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(e.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], o.inputs['Surface'])
    return m, t, e

screen = plane('screen', PW, PH, D)
sm, stex, _ = rgba_emis('screen', 1.0)
screen.data.materials.append(sm)
halo = plane('halo', PW * 1500 / 1108, PH * 760 / 510, D + 0.04)
hm, htex, hem = rgba_emis('halo', 0.0)
htex.image = bpy.data.images.load(P('halo.png'))
halo.data.materials.append(hm)
for f, s_ in [(1, 0), (10, 0), (40, 5.0), (85, 5.0), (108, 0), (N, 0)]:
    hem.inputs['Strength'].default_value = s_; hem.inputs['Strength'].keyframe_insert('default_value', frame=f)

# sol sombre réfléchissant
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 10, -PH / 2 - 0.9))
fl = bpy.context.object
fm = bpy.data.materials.new('floor'); fm.use_nodes = True; fp = fm.node_tree.nodes['Principled BSDF']
fp.inputs['Base Color'].default_value = (0.004, 0.012, 0.03, 1); fp.inputs['Roughness'].default_value = 0.12
fp.inputs['Metallic'].default_value = 0.3
fl.data.materials.append(fm)
w = sc.world.node_tree.nodes['Background']
w.inputs['Color'].default_value = (0.003, 0.01, 0.026, 1); w.inputs['Strength'].default_value = 1.0
# lumière cyan diffuse autour de l'écran
bpy.ops.object.light_add(type='AREA', location=(0, D + 0.3, 0)); al = bpy.context.object
al.visible_camera = False; al.visible_glossy = False
al.data.size = 5; al.data.energy = 0; al.data.color = (0.2, 0.9, 1.0); al.rotation_euler = (math.radians(-90), 0, 0)
al.parent = piv; al.matrix_parent_inverse = piv.matrix_world.inverted()
for f, e in [(1, 0), (12, 0), (40, 600), (85, 600), (108, 0)]:
    al.data.energy = e; al.data.keyframe_insert('energy', frame=f)
# particules cyan dans l'espace
random.seed(2)
pm = S.emis_mat('p', (0.4, 0.95, 1.0), 6)
for i in range(120):
    p = Vector((random.uniform(-9, 9), random.uniform(-6, 14), random.uniform(-2.5, 4)))
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.008, 0.025), location=p)
    o = bpy.context.object; o.data.materials.append(pm)
    for f, hd in [(1, True), (14, False), (106, True)]:
        o.hide_render = hd; o.keyframe_insert('hide_render', frame=f)

cam = S.make_camera()
cd = cam.data; cd.sensor_fit = 'VERTICAL'; cd.sensor_height = 24; cd.lens = 12 / math.tan(VFOV / 2)
cd.dof.use_dof = True; cd.dof.aperture_fstop = 4.0

def anim(f):
    """(recul caméra, hauteur, lacet écran, tangage écran, roulis)"""
    k = [(1, 0, 0, 0, 0, 0), (12, 0, 0, 0, 0, 0), (50, 6.0, 0.5, 24, -9, 3), (82, 5.4, 0.35, -12, -5, -2), (112, 0, 0, 0, 0, 0), (N, 0, 0, 0, 0, 0)]
    for a, b in zip(k, k[1:]):
        if a[0] <= f <= b[0]:
            u = (f - a[0]) / (b[0] - a[0])
            u = u * u * u if (a[0] == 82) else S.ease(u)   # accélération franche vers l'écran
            return [a[i] + (b[i] - a[i]) * u for i in range(1, 6)]
    return [0] * 5

for f in range(1, N + 1):
    back, hz, yaw, pitch, roll = anim(f)
    cam.location = (0, -back, hz)
    S.look_at(cam, (0, D, 0), roll=math.radians(roll))
    piv.rotation_euler = (math.radians(pitch), 0, math.radians(yaw))
    for o, props in ((cam, ('location', 'rotation_euler')), (piv, ('rotation_euler',))):
        for pr in props:
            o.keyframe_insert(pr, frame=f)
    cd.dof.focus_distance = D + back; cd.dof.keyframe_insert('focus_distance', frame=f)

os.makedirs(OUT, exist_ok=True)
frames = [int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else ([1, 30, 50, 70, 95, 115] if TEST else range(1, N + 1))
for f in frames:
    p = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(p):
        continue
    stex.image = bpy.data.images.load(P(f'float_src/{f:04d}.png'), check_existing=True)
    sc.frame_set(f); sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
print('DONE')
