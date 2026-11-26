# Transitions 3D (cube / retournement) avec la vidéo qui continue de jouer sur les faces
# usage: python3 trans3d.py WORKDIR OUTROOT [--test]
import bpy, sys, os, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import scene25d as S
import timeline as T

WD, OUTROOT = sys.argv[1], sys.argv[2]
TEST = '--test' in sys.argv
HW = int(T.TRANS_HALF * 60)
N = 2 * HW
D = 3.0                         # distance caméra -> face avant
PW = S.SX * D                   # largeur de la face (remplit exactement le cadre)
PH = S.SY * D


def build(style):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = S.setup_render(N, TEST, samples=int(os.environ.get('SAMPLES', 8)), pct=int(os.environ.get('PCT', 75)))
    sc.cycles.use_denoising = True
    cam = S.make_camera()
    horiz = style in ('cube_left', 'cube_right', 'flip')
    depth = PW if horiz else PH            # profondeur du cube = côté qui va tourner vers l'avant
    pivot = Vector((0, D + depth / 2, 0)) if style != 'flip' else Vector((0, D, 0))
    bpy.ops.object.empty_add(location=pivot); piv = bpy.context.object

    def face(name, w, h):
        bpy.ops.mesh.primitive_plane_add(size=1)
        o = bpy.context.object; o.name = name
        o.scale = (w, h, 1); bpy.ops.object.transform_apply(scale=True)
        m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial'); tex = nt.nodes.new('ShaderNodeTexImage')
        em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(tex.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
        o.data.materials.append(m)
        o.parent = piv; o.matrix_parent_inverse = piv.matrix_world.inverted()
        return o, tex

    # face A (vue de face, plan XZ), face B sur le côté qui arrive
    A, texA = face('A', PW, PH)
    A.rotation_euler = (math.radians(90), 0, 0); A.location = (0, D, 0)
    if style == 'flip':
        B, texB = face('B', PW, PH)
        B.rotation_euler = (math.radians(90), 0, math.radians(180)); B.location = (0, D + 0.001, 0)
    elif horiz:
        B, texB = face('B', PW, PH)
        s = 1 if style == 'cube_left' else -1
        B.rotation_euler = (math.radians(90), 0, math.radians(90 * s)); B.location = (s * PW / 2, D + PW / 2, 0)
    else:
        B, texB = face('B', PW, PH)
        if style == 'cube_down':   # la face du dessous remonte vers l'avant
            B.rotation_euler = (math.radians(180), 0, 0); B.location = (0, D + PH / 2, -PH / 2)
        else:                      # cube_up : la face du dessus descend vers l'avant
            B.rotation_euler = (0, 0, 0); B.location = (0, D + PH / 2, PH / 2)
    # arrière-plan : vidéo d'arrivée, sombre et floue (profondeur de champ)
    bpy.ops.mesh.primitive_plane_add(size=1)
    bk = bpy.context.object; bk.scale = (PW * 6, PH * 6, 1); bk.rotation_euler = (math.radians(90), 0, 0); bk.location = (0, D + 14, 0)
    m = bpy.data.materials.new('back'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial'); tb = nt.nodes.new('ShaderNodeTexImage'); em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 0.13
    nt.links.new(tb.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], o.inputs[0]); bk.data.materials.append(m)
    cam.data.dof.use_dof = True; cam.data.dof.focus_distance = D + 1.0; cam.data.dof.aperture_fstop = 1.2
    # la caméra recule un peu au milieu pour voir le volume, avec flou de mouvement
    return sc, cam, piv, texA, (texB, tb), horiz


def angle_for(style, u):
    e = u * u * (3 - 2 * u)
    if style == 'cube_left':
        return (0, 0, math.radians(-90 * e))
    if style == 'cube_right':
        return (0, 0, math.radians(90 * e))
    if style == 'flip':
        return (0, 0, math.radians(180 * e))
    if style == 'cube_down':
        return (math.radians(-90 * e), 0, 0)
    return (math.radians(90 * e), 0, 0)


for cut, style in T.TRANS3D:
    src = os.path.join(WD, 'trans', f'{cut:.2f}')
    out = os.path.join(OUTROOT, f'{cut:.2f}')
    os.makedirs(out, exist_ok=True)
    sc, cam, piv, texA, texB, horiz = build(style)
    frames = [1, N // 2, N - 3] if TEST else range(1, N + 1)
    for f in frames:
        p = os.path.join(out, f'{f:04d}.png')
        if not TEST and os.path.exists(p):
            continue
        u = (f - 1) / (N - 1)
        # A continue jusqu'à la coupe puis se fige ; B est figé avant la coupe puis joue
        k = f - 1 + 2  # index dans les images exportées (2 de marge)
        ia = min(k, HW + 1); ib = max(k, HW + 2)
        texA.image = bpy.data.images.load(os.path.join(src, f'{ia:03d}.png'), check_existing=True)
        imgB = bpy.data.images.load(os.path.join(src, f'{ib:03d}.png'), check_existing=True)
        texB[0].image = imgB; texB[1].image = imgB
        for t_ in (texA, texB[0], texB[1]):
            t_.image.colorspace_settings.name = 'sRGB'
        piv.rotation_euler = angle_for(style, u)
        pull = math.sin(math.pi * u)
        cam.location = (0, -1.6 * pull, 0.15 * pull * (0 if horiz else 1))
        cam.rotation_euler = (math.radians(90), 0, 0)
        sc.frame_set(f)
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
    print('done', cut, style)
print('DONE')
