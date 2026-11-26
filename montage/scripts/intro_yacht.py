# Intro cinématique 3D : yacht procédural au coucher du soleil (Blender / Cycles CPU)
# usage: python3 intro_yacht.py OUTDIR [--test]  (test = quelques images basse résolution)
import bpy, bmesh, math, sys, os
from mathutils import Vector

OUT = sys.argv[1]
TEST = '--test' in sys.argv
FRAMES = 240  # 4 s @ 60 fps

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 6 if TEST else int(os.environ.get('SAMPLES', 10))
sc.cycles.use_adaptive_sampling = True
sc.render.use_persistent_data = True
sc.cycles.use_denoising = True
sc.cycles.denoiser = 'OPENIMAGEDENOISE'
sc.cycles.max_bounces = 4
sc.cycles.glossy_bounces = 2
sc.cycles.transmission_bounces = 2
sc.cycles.diffuse_bounces = 2
sc.render.resolution_x = 1920
sc.render.resolution_y = 884
sc.render.resolution_percentage = 33 if TEST else int(os.environ.get('PCT', 100))
sc.render.fps = 60
sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.5
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_depth = '16'
sc.view_settings.view_transform = 'AgX'
try:
    sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass

def mat(name, base, rough=0.4, metal=0.0, emit=None, estr=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*base, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if coat:
        p.inputs['Coat Weight'].default_value = coat
    if emit:
        p.inputs['Emission Color'].default_value = (*emit, 1)
        p.inputs['Emission Strength'].default_value = estr
    return m

M_HULL = mat('hull', (0.86, 0.84, 0.80), 0.18, coat=0.6)
M_GLASS = mat('glass', (0.02, 0.025, 0.03), 0.05, metal=0.6)
M_WOOD = mat('teak', (0.30, 0.17, 0.08), 0.5)
M_STRIPE = mat('stripe', (0.05, 0.12, 0.22), 0.2, coat=0.6)
M_LIGHT = mat('lamp', (1, 0.8, 0.5), 0.5, emit=(1.0, 0.72, 0.4), estr=12)
M_CHROME = mat('chrome', (0.9, 0.9, 0.9), 0.1, metal=1.0)

def box(name, loc, size, m, bevel=0.08):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        b = o.modifiers.new('bev', 'BEVEL'); b.width = bevel; b.segments = 3
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    return o

# ---------- coque : grille déformée (étrave effilée, quille en V) ----------
L, W, H = 34.0, 7.6, 3.4
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=12, use_grid_fill=True)
for v in bm.verts:
    x, y, z = v.co.x * L, v.co.y * W, v.co.z * H   # x in [-L/2, L/2]
    t = (x + L / 2) / L                              # 0 = poupe, 1 = proue
    # largeur : effilée vers la proue
    wf = 1.0 if t < 0.55 else max(0.0, 1 - ((t - 0.55) / 0.45) ** 1.7)
    # fond en V et relevé vers l'avant
    zb = z
    if z < 0:
        zb = z * (0.6 + 0.4 * (1 - abs(y) / (W / 2))) * (1 - 0.35 * max(0, t - 0.5) / 0.5)
    # étrave inclinée : le haut avance plus loin que le bas
    rake = (z / H + 0.5) * 2.6 * t ** 3
    v.co = Vector((x + rake, y * (wf * (0.92 + 0.08 * (z / H + 0.5))), zb))
me = bpy.data.meshes.new('hull'); bm.to_mesh(me); bm.free()
hull = bpy.data.objects.new('hull', me); sc.collection.objects.link(hull)
hull.location = (0, 0, 0.9)
hull.data.materials.append(M_HULL)
s = hull.modifiers.new('sub', 'SUBSURF'); s.levels = s.render_levels = 2
for p in me.polygons:
    p.use_smooth = True

# bande décorative sombre le long de la coque
for side in (-1, 1):
    box('stripe', (-2, side * 3.63, 1.55), (24, 0.08, 0.35), M_STRIPE, bevel=0.03)
    # hublots de coque
    for i in range(7):
        box('port', (-10 + i * 2.4, side * 3.66, 0.95), (1.2, 0.05, 0.28), M_GLASS, bevel=0.1)

# pont en teck
box('deck', (1.5, 0, 2.62), (29, 6.8, 0.06), M_WOOD, bevel=0.0)

# superstructure (3 niveaux) avec bandes vitrées
lv = [(-3.5, 18.5, 6.4, 2.3, 2.6), (-5.0, 13.5, 5.6, 2.0, 4.9), (-6.5, 7.5, 4.6, 1.8, 6.9)]
for i, (cx, ln, wd, ht, zc) in enumerate(lv):
    box(f'deck{i}', (cx, 0, zc + ht / 2), (ln, wd, ht), M_HULL, bevel=0.25)
    for side in (-1, 1):
        box(f'win{i}', (cx + 0.6, side * (wd / 2 + 0.01), zc + ht * 0.55), (ln * 0.8, 0.04, ht * 0.5), M_GLASS, bevel=0.15)
    box(f'front{i}', (cx + ln / 2 + 0.01, 0, zc + ht * 0.55), (0.04, wd * 0.8, ht * 0.5), M_GLASS, bevel=0.1)
    # toit débordant
    box(f'roof{i}', (cx + 0.4, 0, zc + ht + 0.06), (ln + 1.2, wd + 0.5, 0.14), M_HULL, bevel=0.05)
    # spots sous le toit
    for k in range(6):
        for side in (-1, 1):
            box('spot', (cx - ln / 2 + 1.5 + k * (ln - 3) / 5, side * (wd / 2 + 0.15), zc + ht - 0.05), (0.18, 0.18, 0.04), M_LIGHT, bevel=0)
# arche radar + mât
box('arch', (-7.0, 0, 9.4), (1.4, 4.0, 0.25), M_HULL, bevel=0.08)
for side in (-1, 1):
    box('archleg', (-7.0, side * 1.9, 8.8), (1.2, 0.25, 1.3), M_HULL, bevel=0.08)
bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=2.2, location=(-7.0, 0, 10.6))
bpy.context.object.data.materials.append(M_CHROME)
# garde-corps à l'avant
for side in (-1, 1):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=13, location=(9.5, side * 3.0, 3.6), rotation=(0, math.pi / 2, side * -0.12))
    bpy.context.object.data.materials.append(M_CHROME)
    for k in range(9):
        x = 3.5 + k * 1.45
        bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=0.95, location=(x, side * (3.3 - max(0, x - 6) * 0.28), 3.12))
        bpy.context.object.data.materials.append(M_CHROME)

# ---------- océan ----------
bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))
sea = bpy.context.object
oc = sea.modifiers.new('ocean', 'OCEAN')
oc.geometry_mode = 'GENERATE'
oc.size = 1.0
oc.spatial_size = 120
oc.resolution = 10 if not TEST else 6
oc.repeat_x = oc.repeat_y = 5
oc.wave_scale = 0.9
oc.choppiness = 1.1
oc.wind_velocity = 9
oc.time = 1.0
oc.keyframe_insert('time', frame=1)
oc.time = 5.0
oc.keyframe_insert('time', frame=FRAMES)
sea.location = (-300, -300, 0)
M_SEA = mat('sea', (0.01, 0.035, 0.05), 0.04)
M_SEA.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value = 1.33
sea.data.materials.append(M_SEA)
for p in sea.data.polygons:
    p.use_smooth = True

# ---------- ciel couchant + soleil ----------
world = bpy.data.worlds.new('w'); sc.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes['Background']
sky = nt.nodes.new('ShaderNodeTexSky')
sky.sky_type = 'MULTIPLE_SCATTERING'
sky.sun_elevation = math.radians(2.5)
sky.sun_rotation = math.radians(160)
sky.air_density = 1.6
try:
    sky.aerosol_density = 2.5
except Exception:
    pass
sky.ozone_density = 1.5
sky.sun_intensity = 0.6
nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 0.35

bpy.ops.object.light_add(type='SUN', rotation=(math.radians(87.5), 0, math.radians(160 + 90)))
sun = bpy.context.object
sun.data.energy = 3.2
sun.data.color = (1.0, 0.55, 0.3)
sun.data.angle = math.radians(1.5)
# lumière d'appoint froide (ciel opposé)
bpy.ops.object.light_add(type='AREA', location=(30, -40, 25))
fill = bpy.context.object
fill.data.energy = 9000; fill.data.size = 30; fill.data.color = (0.55, 0.65, 1.0)
fill.rotation_euler = (Vector((0, 0, 3)) - fill.location).to_track_quat('-Z', 'Y').to_euler()

# ---------- caméra drone ----------
bpy.ops.object.empty_add(location=(10, 0, 3))
tgt = bpy.context.object
bpy.ops.object.camera_add()
cam = bpy.context.object
sc.camera = cam
cam.data.lens = 24
cam.data.sensor_width = 36
cam.data.dof.use_dof = True
cam.data.dof.focus_object = tgt
cam.data.dof.aperture_fstop = 4.0
c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

keys = [  # frame, cam pos, target pos, lens
    (1,   (30, -9, 0.9),   (16, 0, 2.6), 22),
    (90,  (14, -13, 2.2),  (4, 0, 4.0), 24),
    (170, (-3, -24, 4.5),  (-3, 0, 5.0), 30),
    (240, (-26, -26, 13),  (0, 0, 4.5), 32),
]
for f, cp, tp, ln in keys:
    cam.location = cp; cam.keyframe_insert('location', frame=f)
    tgt.location = tp; tgt.keyframe_insert('location', frame=f)
    cam.data.lens = ln; cam.data.keyframe_insert('lens', frame=f)
# petite oscillation "drone" (bruit sur la rotation de la caméra via un parent)
for o in (cam, tgt):
    if o.animation_data and o.animation_data.action:
        for fc in getattr(o.animation_data.action, 'fcurves', []):
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.easing = 'EASE_IN_OUT'

os.makedirs(OUT, exist_ok=True)
frames = [1, 90, 170, 240] if TEST else ([int(x) for x in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else range(1, FRAMES + 1, int(os.environ.get('STEP', 1))))
for f in frames:
    path = os.path.join(OUT, f'{f:04d}.png')
    if not TEST and os.path.exists(path):
        continue
    sc.frame_set(f)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
print('DONE')
