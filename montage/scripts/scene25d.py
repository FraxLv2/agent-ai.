# Outils communs : reconstruction 2.5D d'une image de gameplay dans Blender
import bpy, bmesh, math
import numpy as np
from mathutils import Vector

W_SRC, H_SRC = 1108, 510
HFOV = math.radians(72)
SX = 2 * math.tan(HFOV / 2)
SY = SX * H_SRC / W_SRC
ZN, ZF = 3.0, 70.0


def inv_to_z(inv):
    return 1.0 / (inv * (1 / ZN - 1 / ZF) + 1 / ZF)


def ray(u, v):
    # caméra Blender à l'origine regardant +Y, Z vers le haut
    return Vector((SX * (u - 0.5), 1.0, SY * (0.5 - v)))


def setup_render(frames, test=False, samples=12, pct=100):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 4 if test else samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 16
    sc.render.resolution_x = 1920
    sc.render.resolution_y = 884
    sc.render.resolution_percentage = 33 if test else pct
    sc.render.fps = 60
    sc.frame_start, sc.frame_end = 1, frames
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.use_persistent_data = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    # 'Standard' : les pixels de l'image d'origine ressortent inchangés
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    w = bpy.data.worlds.new('w'); sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0
    return sc


def emission_image_mat(name, path, alpha=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(path)
    tex.interpolation = 'Cubic'
    tex.extension = 'EXTEND'
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(tex.outputs['Color'], em.inputs['Color'])
    if alpha:
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tex.outputs['Alpha'], mix.inputs['Fac'])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
    else:
        nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m


def depth_mesh(name, img_path, inv, step=4, zclamp=None, pad=0.25):
    """Maillage dont chaque sommet est placé à sa profondeur estimée (MiDaS).
    pad : débordement hors cadre (bords prolongés) pour les mouvements de caméra."""
    h, w = inv.shape
    us = np.arange(-int(w * pad), w + int(w * pad) + 1, step).astype(float)
    vs = np.arange(-int(h * pad * 1.4), h + int(h * pad) + 1, step).astype(float)
    verts, uvs = [], []
    for v in vs:
        for u in us:
            d = inv[int(np.clip(v, 0, h - 1)), int(np.clip(u, 0, w - 1))]
            z = inv_to_z(float(d))
            if zclamp:
                z = min(z, zclamp)
            p = ray(u / w, v / h) * z
            verts.append(p)
            uvs.append((u / w, 1 - v / h))
    nu = len(us)
    faces = []
    for j in range(len(vs) - 1):
        for i in range(nu - 1):
            a = j * nu + i
            faces.append((a, a + nu, a + nu + 1, a + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in verts], [], faces)
    uvl = me.uv_layers.new()
    for poly in me.polygons:
        for li in poly.loop_indices:
            uvl.data[li].uv = uvs[me.loops[li].vertex_index]
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(emission_image_mat(name + '_m', img_path))
    ob.visible_shadow = False
    return ob


def card(name, img_path, bbox, z):
    """Plan découpé (personnage) placé à la profondeur z, aligné pixel pour pixel avec la vue d'origine."""
    x0, y0, x1, y1 = bbox
    w, h = W_SRC, H_SRC
    corners = [(x0, y1), (x1, y1), (x1, y0), (x0, y0)]
    verts = [tuple(ray(x / w, y / h) * z) for x, y in corners]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new()
    for li, (x, y) in enumerate(corners):
        uvl.data[li].uv = (x / w, 1 - y / h)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(emission_image_mat(name + '_m', img_path, alpha=True))
    ob.visible_shadow = False
    return ob


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def look_at(cam, target, roll=0.0):
    d = (Vector(target) - cam.location).normalized()
    q = d.to_track_quat('-Z', 'Y')
    e = q.to_euler()
    cam.rotation_euler = e
    if roll:
        cam.rotation_euler.rotate_axis('Z', roll)


def make_camera(lens_from_fov=True):
    cd = bpy.data.cameras.new('cam')
    cd.sensor_fit = 'HORIZONTAL'
    cd.sensor_width = 36
    # la vidéo source (2.17:1) est cadrée dans 1920x884 : même ratio
    cd.lens = 18 / math.tan(HFOV / 2)
    cd.clip_start = 0.02
    cd.clip_end = 500
    cam = bpy.data.objects.new('cam', cd)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.rotation_mode = 'XYZ'
    cam.location = (0, 0, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    return cam


def emis_mat(name, color, strength, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color, 1)
    em.inputs['Strength'].default_value = strength
    if alpha < 1.0:
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        mix.inputs['Fac'].default_value = alpha
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs['Surface'])
    else:
        nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m
