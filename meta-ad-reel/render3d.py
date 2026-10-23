"""Physically based (Cycles) interior renders for the reel.

    python3 render3d.py [room ...] [--draft]

Each room is modelled in metres: back wall on y=0, floor z=0, camera on the
centre line looking straight at the wall. Paintings hang as 4 cm panels with a
neutral grey front; after rendering, the exact painting pixels are pasted onto
that panel and modulated by the light the grey panel received, so the artwork
keeps its true colours but sits in the room's real light.
Writes .cache/<room>.png (2160x3840) + .rect.npy in reel coordinates.
"""
import os
import sys
import math
import numpy as np
import bpy
import bmesh
from mathutils import Vector
from PIL import Image
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
ART = {k: os.path.join(HERE, 'paintings', k + '.png') for k in ('convergence', 'morning-light', 'solstice', 'grove')}
DRAFT = '--draft' in sys.argv
RX, RY = (540, 960) if DRAFT else (1080, 1920)
OUT_W, OUT_H = 2160, 3840          # cache resolution (reel 1080x1920 at 2x)
SAMPLES = 32 if DRAFT else 96

# camera: 3.0 m of wall height in frame, centred at z=1.15
CAM_Y, CAM_Z, FRAME_H, FRAME_CZ = -4.0, 1.30, 3.0, 1.20
ART_H, ART_CZ = 1.0, 1.36


def hex_lin(h, a=1.0):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*c, a)


# ------------------------------------------------------------------ scene setup
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = SAMPLES
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 4
    sc.cycles.glossy_bounces = 3
    sc.cycles.sample_clamp_indirect = 8
    sc.render.resolution_x, sc.render.resolution_y = RX, RY
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Base Contrast'
        sc.view_settings.exposure = 0.75
    except Exception:
        pass
    sc.render.threads_mode = 'AUTO'
    return sc


def material(name, color, rough=0.6, metal=0.0, bump=0.0, bump_scale=40.0, var=0.0, var_scale=3.0,
             wood=None, coat=0.0, sheen=0.0, bricks=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    p = N['Principled BSDF']
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if coat:
        p.inputs['Coat Weight'].default_value = coat
        p.inputs['Coat Roughness'].default_value = 0.08
    if sheen:
        p.inputs['Sheen Weight'].default_value = sheen
    tc = N.new('ShaderNodeTexCoord')
    base = hex_lin(color)
    col_out = None
    if wood:  # wood grain: stretched noise + wave rings, along local axis
        mp = N.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = wood
        L.new(tc.outputs['Object'], mp.inputs['Vector'])
        wv = N.new('ShaderNodeTexWave')
        wv.wave_type = 'RINGS'
        wv.inputs['Scale'].default_value = 1.2
        wv.inputs['Distortion'].default_value = 9.0
        wv.inputs['Detail'].default_value = 3
        L.new(mp.outputs['Vector'], wv.inputs['Vector'])
        nz = N.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 6
        nz.inputs['Detail'].default_value = 8
        L.new(mp.outputs['Vector'], nz.inputs['Vector'])
        mix = N.new('ShaderNodeMix')
        mix.data_type = 'FLOAT'
        mix.inputs['Factor'].default_value = 0.5
        L.new(wv.outputs['Fac'], mix.inputs['A'])
        L.new(nz.outputs['Fac'], mix.inputs['B'])
        ramp = N.new('ShaderNodeValToRGB')
        dark = [c * 0.72 for c in base[:3]] + [1]
        ramp.color_ramp.elements[0].color = dark
        ramp.color_ramp.elements[1].color = base
        ramp.color_ramp.elements[0].position = 0.25
        ramp.color_ramp.elements[1].position = 0.75
        L.new(mix.outputs['Result'], ramp.inputs['Fac'])
        col_out = ramp.outputs['Color']
    elif var:
        nz = N.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = var_scale
        nz.inputs['Detail'].default_value = 6
        L.new(tc.outputs['Object'], nz.inputs['Vector'])
        ramp = N.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = [c * (1 - var) for c in base[:3]] + [1]
        ramp.color_ramp.elements[1].color = [min(1, c * (1 + var * 0.6)) for c in base[:3]] + [1]
        ramp.color_ramp.elements[0].position = 0.3
        ramp.color_ramp.elements[1].position = 0.7
        L.new(nz.outputs['Fac'], ramp.inputs['Fac'])
        col_out = ramp.outputs['Color']
    if bricks:  # floor planks: brick texture gives seams + per-plank tint
        bw, bh = bricks
        mp = N.new('ShaderNodeMapping')
        L.new(tc.outputs['Object'], mp.inputs['Vector'])
        br = N.new('ShaderNodeTexBrick')
        br.offset = 0.5
        br.inputs['Scale'].default_value = 1.0
        br.inputs['Brick Width'].default_value = bw
        br.inputs['Row Height'].default_value = bh
        br.inputs['Mortar Size'].default_value = 0.0012
        br.inputs['Mortar Smooth'].default_value = 0.3
        br.inputs['Bias'].default_value = 0.0
        if col_out is not None:   # multiplier around 1 on top of the wood colour
            br.inputs['Color1'].default_value = (0.90, 0.90, 0.90, 1)
            br.inputs['Color2'].default_value = (1.0, 1.0, 1.0, 1)
            br.inputs['Mortar'].default_value = (0.45, 0.45, 0.45, 1)
        else:
            br.inputs['Color1'].default_value = [c * 0.92 for c in base[:3]] + [1]
            br.inputs['Color2'].default_value = [min(1, c * 1.06) for c in base[:3]] + [1]
            br.inputs['Mortar'].default_value = [c * 0.45 for c in base[:3]] + [1]
        L.new(mp.outputs['Vector'], br.inputs['Vector'])
        if col_out is not None:
            mm = N.new('ShaderNodeMix')
            mm.data_type = 'RGBA'
            mm.blend_type = 'MULTIPLY'
            mm.inputs['Factor'].default_value = 1.0
            L.new(col_out, mm.inputs['A'])
            L.new(br.outputs['Color'], mm.inputs['B'])
            col_out = mm.outputs['Result']
        else:
            col_out = br.outputs['Color']
        bmp2 = N.new('ShaderNodeBump')
        bmp2.inputs['Strength'].default_value = 0.25
        L.new(br.outputs['Fac'], bmp2.inputs['Height'])
        L.new(bmp2.outputs['Normal'], p.inputs['Normal'])
    if col_out is not None:
        L.new(col_out, p.inputs['Base Color'])
    else:
        p.inputs['Base Color'].default_value = base
    if bump and not bricks:
        nb = N.new('ShaderNodeTexNoise')
        nb.inputs['Scale'].default_value = bump_scale
        nb.inputs['Detail'].default_value = 10
        L.new(tc.outputs['Object'], nb.inputs['Vector'])
        b = N.new('ShaderNodeBump')
        b.inputs['Strength'].default_value = bump
        L.new(nb.outputs['Fac'], b.inputs['Height'])
        L.new(b.outputs['Normal'], p.inputs['Normal'])
    return m


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.004):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    ob.data.materials.append(mat)
    if bevel:
        md = ob.modifiers.new('bev', 'BEVEL')
        md.width = bevel
        md.segments = 3
        md.limit_method = 'NONE'
    for f in ob.data.polygons:
        f.use_smooth = True
    return ob


def lathe(name, profile, x, y, z, mat, segs=96, close_top=False):
    """profile: list of (radius, height) bottom->top; revolved around Z."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for r, h in profile:
        ring = [bm.verts.new((r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs), h))
                for i in range(segs)]
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            bm.faces.new((a[i], a[(i + 1) % segs], b[(i + 1) % segs], b[i]))
    bm.faces.new(list(reversed(rings[0])))
    if close_top:
        bm.faces.new(rings[-1])
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    ob.location = (x, y, z)
    ob.data.materials.append(mat)
    for f in ob.data.polygons:
        f.use_smooth = True
    sd = ob.modifiers.new('sub', 'SUBSURF')
    sd.levels = sd.render_levels = 1
    return ob


def vessel(name, rad_fn, height, x, y, z, mat, wall=0.006, n=40):
    """Hollow ceramic vessel from a radius function r(t), t=0 bottom..1 top."""
    ts = np.linspace(0, 1, n)
    outer = [(max(0.004, rad_fn(t)), t * height) for t in ts]
    inner = [(max(0.002, rad_fn(t) - wall), t * height) for t in ts[::-1]][:n // 3]
    prof = [(0.0001, 0.0)] + outer + [(outer[-1][0] - wall * 0.5, height + wall * 0.3)] + inner
    return lathe(name, prof, x, y, z, mat)


def branch_set(name, x, y, z, mat, n=5, length=0.75, lean=-0.4, spread=0.8, seed=1, thick=0.0035):
    rng = np.random.default_rng(seed)
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = thick
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    for i in range(n):
        ang = lean + (i - (n - 1) / 2) / max(1, n - 1) * spread + rng.normal(0, 0.08)
        yaw = rng.normal(0, 0.35)
        L = length * rng.uniform(0.75, 1.1)
        pts = [(0, 0, 0)]
        a = ang
        for s in range(14):
            a += rng.normal(0, 0.07)
            px, py, pz = pts[-1]
            st = L / 14
            pts.append((px + math.sin(a) * st * math.cos(yaw), py + math.sin(yaw) * st * 0.4, pz + math.cos(a) * st))
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for p, (px, py, pz) in zip(sp.points, pts):
            p.co = (px, py, pz, 1)
            p.radius = 1.0 - 0.7 * (pts.index((px, py, pz)) / len(pts))
        for j in range(4, 13, 3):  # twigs
            bx, by, bz = pts[j]
            b = a + rng.choice([-1, 1]) * rng.uniform(0.5, 0.9)
            bl = L * rng.uniform(0.12, 0.22)
            tw = cu.splines.new('POLY')
            tw.points.add(1)
            tw.points[0].co = (bx, by, bz, 1)
            tw.points[1].co = (bx + math.sin(b) * bl, by, bz + math.cos(b) * bl, 1)
            tw.points[0].radius, tw.points[1].radius = 0.5, 0.2
    ob = link(bpy.data.objects.new(name, cu))
    ob.location = (x, y, z)
    ob.data.materials.append(mat)
    return ob


def books(x0, y, z, specs, rng_seed=3):
    rng = np.random.default_rng(rng_seed)
    paper = material('paper', '#f2eee6', rough=0.9)
    for i, (w, d, h, col) in enumerate(specs):
        cx = x0 + rng.uniform(-0.01, 0.01)
        m = material(f'book{i}{col}', col, rough=0.75)
        box(f'cover{i}', cx - w / 2, cx + w / 2, y - d / 2, y + d / 2, z, z + h, m, bevel=0.002)
        box(f'pages{i}', cx - w / 2 + 0.004, cx + w / 2 + 0.001, y - d / 2 - 0.001, y + d / 2 - 0.004,
            z + 0.003, z + h - 0.003, paper, bevel=0.0)
        z += h
    return z


def fluted_front(x0, x1, y, z0, z1, mat, pitch=0.032):
    n = int((x1 - x0) / pitch)
    r = pitch / 2
    for i in range(n):
        cx = x0 + r + i * pitch
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=r * 0.98, depth=z1 - z0,
                                            location=(cx, y, (z0 + z1) / 2))
        ob = bpy.context.active_object
        ob.scale.y = 0.45
        ob.data.materials.append(mat)
        for f in ob.data.polygons:
            f.use_smooth = True


# ------------------------------------------------------------------ room shell + light
def room(wall_hex, floor_kind, floor_hex, sun_side=-1, window=True, leaves=None, sun_strength=4.0,
         sun_elev=28, seed=1):
    wall = material('wall', wall_hex, rough=0.92, bump=0.06, bump_scale=60, var=0.035, var_scale=1.5)
    if floor_kind == 'oak':
        floor = material('floor', floor_hex, rough=0.38, wood=(1.2, 14, 1.2), bricks=(1.6, 0.16), coat=0.15)
    else:
        floor = material('floor', floor_hex, rough=0.42, var=0.06, var_scale=1.2, bump=0.02, bump_scale=80, coat=0.1)
    box('floor', -2.15, 2.15, -8, 0.0, -0.05, 0.0, floor, bevel=0)
    box('backwall', -2.15, 2.15, 0.0, 0.1, 0, 3.0, wall, bevel=0)
    box('ceiling', -2.15, 2.15, -8, 0.1, 3.0, 3.1, wall, bevel=0)
    skirt = material('skirt', wall_hex, rough=0.5)
    box('skirting', -2.1, 2.1, -0.012, 0.0, 0, 0.10, skirt, bevel=0.003)
    # side wall with window (built from panels around the opening)
    sx = sun_side * 2.1
    side = (sx - 0.05, sx + 0.05) if sun_side < 0 else (sx - 0.05, sx + 0.05)
    other = -sx
    box('otherwall', other - 0.05, other + 0.05, -8, 0.1, 0, 3.0, wall, bevel=0)
    wy0, wy1, wz0, wz1 = -0.95, -0.30, 0.40, 2.50
    for name, y0, y1, z0, z1 in [('sw_a', -8, wy0, 0, 3), ('sw_b', wy1, 0.1, 0, 3),
                                 ('sw_c', wy0, wy1, 0, wz0), ('sw_d', wy0, wy1, wz1, 3)]:
        box(name, side[0], side[1], y0, y1, z0, z1, wall, bevel=0)
    frame = material('winframe', '#2a2a2a', rough=0.5)
    # mullions
    for zz in (wz0 + (wz1 - wz0) / 3, wz0 + 2 * (wz1 - wz0) / 3):
        box('mull_h', side[0], side[1], wy0, wy1, zz - 0.025, zz + 0.025, frame, bevel=0)
    ym = (wy0 + wy1) / 2
    box('mull_v', side[0], side[1], ym - 0.025, ym + 0.025, wz0, wz1, frame, bevel=0)
    # wall behind camera (keeps light realistic but lets the camera see through)
    box('frontwall', -2.15, 2.15, -8.1, -8.0, 0, 3.0, wall, bevel=0)
    # sky + sun
    world = bpy.data.worlds.new('w')
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes['Background']
    az = math.radians(90 if sun_side < 0 else -90) + math.radians(-35 * (-sun_side))
    try:
        sky = nt.nodes.new('ShaderNodeTexSky')
        for t in ('MULTIPLE_SCATTERING', 'NISHITA', 'SINGLE_SCATTERING'):
            try:
                sky.sky_type = t
                break
            except Exception:
                continue
        sky.sun_elevation = math.radians(sun_elev)
        sky.sun_rotation = az
        try:
            sky.sun_disc = False
        except Exception:
            pass
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 0.35
    except Exception:
        bg.inputs['Color'].default_value = (0.6, 0.75, 1.0, 1)
        bg.inputs['Strength'].default_value = 1.0
    sun = bpy.data.lights.new('sun', 'SUN')
    sun.energy = sun_strength
    sun.angle = math.radians(1.2)
    sun.color = (1.0, 0.93, 0.84)
    so = link(bpy.data.objects.new('sun', sun))
    # direction: light travels from the window side, into the room, toward the back wall
    d = Vector((-sun_side * 0.80, 0.42, -math.tan(math.radians(sun_elev)) * 0.9)).normalized()
    so.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    # soft fill from behind the camera (photographer's bounce)
    fill = bpy.data.lights.new('fill', 'AREA')
    fill.shape = 'RECTANGLE'
    fill.size, fill.size_y = 4.0, 2.5
    fill.energy = 160
    fill.color = (1.0, 0.97, 0.93)
    fo = link(bpy.data.objects.new('fill', fill))
    fo.location = (0, -6.5, 2.2)
    fo.rotation_euler = (math.radians(80), 0, 0)
    if leaves:
        foliage(sx + sun_side * 0.9, ym - 0.45, (wz0 + wz1) / 2 + 0.5, leaves, seed)
    return wall


def foliage(x, y, z, kind, seed):
    """Branches outside the window: they only exist to cast leaf shadows."""
    rng = np.random.default_rng(seed)
    m = material('leaf', '#2f4a2a', rough=0.6)
    for i in range(260 if kind == 'olive' else 140):
        if kind == 'palm':
            frond = rng.integers(0, 7)
            ang = -1.2 + frond * 0.4
            t = rng.uniform(0.1, 1.0)
            px, pz = math.cos(ang) * t * 0.8, math.sin(ang) * t * 0.8 - 0.25 * t * t
            sx_, sy_, sz_ = 0.03, 0.02, 0.22 * math.sin(math.pi * t) + 0.05
            rot = (rng.normal(0, 0.2), rng.normal(0, 0.3), ang + math.pi / 2 + rng.choice([-0.9, 0.9]))
        else:
            px, pz = rng.normal(0, 0.35), rng.normal(0, 0.4)
            sx_, sy_, sz_ = 0.012, 0.008, 0.05
            rot = (rng.uniform(0, 3), rng.uniform(0, 3), rng.uniform(0, 3))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1,
                                             location=(x + rng.normal(0, 0.15), y + px, z + pz))
        ob = bpy.context.active_object
        ob.scale = (sy_, sx_, sz_) if kind == 'palm' else (sy_, sx_, sz_)
        ob.rotation_euler = rot
        ob.data.materials.append(m)
        ob.visible_camera = False


def camera():
    cd = bpy.data.cameras.new('cam')
    cd.sensor_fit = 'VERTICAL'
    cd.sensor_height = 36
    dist = -CAM_Y
    cd.lens = cd.sensor_height / 2 / ((FRAME_H / 2) / dist)
    cd.shift_y = (FRAME_CZ - CAM_Z) / FRAME_H
    cd.clip_start = 0.1
    co = link(bpy.data.objects.new('cam', cd))
    co.location = (0, CAM_Y, CAM_Z)
    co.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.scene.camera = co
    return co


def to_px(x, z, y=0.0):
    """World point -> 1x reel pixel coordinates (1080x1920) for the straight-on camera."""
    dist = y - CAM_Y
    scale = FRAME_H * dist / (-CAM_Y)       # wall-plane-equivalent frame height at that depth
    u = 0.5 + x / (scale * 9 / 16)
    v = 0.5 - (z - (CAM_Z + (FRAME_CZ - CAM_Z) * dist / (-CAM_Y))) / scale
    return u * 1080, v * 1920


def painting(key, cx, cz, h, side_hex, depth=0.04):
    im = Image.open(ART[key])
    w = h * im.width / im.height
    grey = material('canvas_grey', '#7f7f7f', rough=0.7)
    sidem = material('frame_side', side_hex, rough=0.55, wood=(40, 4, 4) if side_hex != '#1c1c1c' else None)
    box('frame_' + key, cx - w / 2, cx + w / 2, -0.005 - depth, -0.005, cz - h / 2, cz + h / 2, sidem, bevel=0.002)
    # grey front face (light probe) a hair in front of the frame box
    box('face_' + key, cx - w / 2 + 0.0005, cx + w / 2 - 0.0005, -0.0062 - depth, -0.0058 - depth,
        cz - h / 2 + 0.0005, cz + h / 2 - 0.0005, grey, bevel=0)
    x0, y0 = to_px(cx - w / 2, cz + h / 2, -depth - 0.006)
    x1, y1 = to_px(cx + w / 2, cz - h / 2, -depth - 0.006)
    return dict(key=key, rect=(x0, y0, x1, y1))


# ------------------------------------------------------------------ rooms
def sideboard(x0, x1, depth, h, body_hex, kind='oak', fluted=True, legs_hex=None, plinth=0.06):
    if kind == 'oak':
        body = material('sb', body_hex, rough=0.45, wood=(3, 30, 3))
    else:
        body = material('sb', body_hex, rough=0.35, coat=0.2)
    y0, y1 = -depth - 0.02, -0.02
    box('sb_top', x0, x1, y0, y1, h - 0.03, h, body, bevel=0.004)
    box('sb_body', x0 + 0.01, x1 - 0.01, y0 + 0.02, y1, plinth, h - 0.03, body, bevel=0.003)
    if fluted:
        fluted_front(x0 + 0.02, x1 - 0.02, y0 + 0.02, plinth + 0.004, h - 0.034, body)
    pl = material('plinth', legs_hex or body_hex, rough=0.6)
    box('sb_plinth', x0 + 0.06, x1 - 0.06, y0 + 0.06, y1 - 0.02, 0, plinth, pl, bevel=0.002)
    return h, (y0 + y1) / 2


def build(key):
    reset()
    camera()
    arts = []
    if key in ('convergence', 'convergence_empty'):
        room('#ECE6DC', 'oak', '#B8946A', sun_side=1, leaves=None, sun_strength=4.5, seed=2)
        top, ymid = sideboard(-0.62, 0.62, 0.42, 0.70, '#C9A67C')
        ivory = material('ivory', '#EFE9DF', rough=0.3, coat=0.3)
        vessel('vase', lambda t: 0.018 + 0.075 * math.sin(math.pi * min(1, t * 1.15)) ** 0.9 * (1 - 0.6 * t),
               0.32, -0.47, ymid, top, ivory)
        branch_set('br', -0.47, ymid, top + 0.30, material('twig', '#6b5640', rough=0.8), lean=-0.45, seed=4)
        trav = material('trav', '#D9CCB3', rough=0.55, var=0.08, var_scale=8, bump=0.15, bump_scale=120)
        zb = books(0.42, ymid, top, [(0.26, 0.19, 0.035, '#E8E0D0'), (0.23, 0.17, 0.028, '#C8B89C'),
                                      (0.24, 0.18, 0.03, '#F2EEE6')])
        vessel('bowl', lambda t: 0.04 + 0.075 * math.sqrt(max(0, t)), 0.07, 0.44, ymid, zb, trav, wall=0.008)
        if key == 'convergence':
            arts.append(painting('convergence', 0, ART_CZ, ART_H, '#B89A6E'))
    elif key == 'morning_light':
        room('#E8E1D6', 'oak', '#C2A27A', sun_side=-1, leaves='palm', sun_strength=5.0, seed=3)
        walnut = material('walnut', '#5A3F2C', rough=0.45, wood=(30, 3, 3))
        y0, y1, h = -0.40, -0.04, 0.46
        box('bench_top', -0.75, 0.75, y0, y1, h - 0.045, h, walnut, bevel=0.005)
        for lx in (-0.68, 0.62):
            box('bench_leg', lx, lx + 0.06, y0 + 0.02, y1 - 0.02, 0, h - 0.045, walnut, bevel=0.004)
        linen = material('linen', '#E6DED0', rough=1.0, sheen=0.6, bump=0.3, bump_scale=900)
        throw(0.25, 0.55, y0, y1, h, linen)
        ym = (y0 + y1) / 2
        zb = books(-0.50, ym, h, [(0.25, 0.18, 0.04, '#EFE9DE'), (0.22, 0.16, 0.03, '#B39E82'),
                                  (0.23, 0.17, 0.032, '#F6F2EA')])
        white = material('white_glaze', '#F1EEE8', rough=0.35, coat=0.2)
        vessel('jug', lambda t: 0.035 + 0.07 * math.sin(math.pi * min(1, t * 1.05)) ** 0.8, 0.22, -0.16, ym, h, white)
        arts.append(painting('morning-light', 0, ART_CZ, ART_H, '#B89A6E'))
    elif key == 'solstice':
        room('#E9E0D2', 'oak', '#C4A57E', sun_side=-1, leaves=None, sun_strength=4.5, seed=4)
        oak = material('oak2', '#BE9C72', rough=0.5, wood=(30, 3, 3))
        trav = material('trav', '#DDD1BD', rough=0.5, var=0.1, var_scale=10, bump=0.2, bump_scale=140)
        y0, y1, h = -0.36, -0.04, 0.80
        box('con_top', -0.72, 0.72, y0, y1, h - 0.045, h, trav, bevel=0.004)
        for lx in (-0.68, 0.62):
            box('con_leg', lx, lx + 0.06, y0 + 0.02, y1 - 0.02, 0, h - 0.045, oak, bevel=0.004)
        box('con_shelf', -0.68, 0.68, y0 + 0.03, y1 - 0.03, 0.12, 0.15, oak, bevel=0.003)
        ym = (y0 + y1) / 2
        white = material('white_matte', '#F3F0EA', rough=0.6)
        vessel('vase', lambda t: 0.05 + 0.035 * math.sin(math.pi * t) ** 1.2 - 0.012 * t, 0.36, -0.52, ym, h, white)
        branch_set('br', -0.52, ym, h + 0.34, material('twig', '#6b5640', rough=0.8), lean=-0.4, spread=0.6, seed=12)
        zb = books(0.45, ym, h, [(0.26, 0.19, 0.035, '#F1ECE3'), (0.23, 0.17, 0.03, '#C7B597'),
                                  (0.24, 0.18, 0.03, '#E4DACA')])
        stone = material('stone', '#CBBDA5', rough=0.7, var=0.08, var_scale=12, bump=0.2, bump_scale=200)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=0.06, location=(0.46, ym, zb + 0.06))
        o = bpy.context.active_object
        o.data.materials.append(stone)
        bpy.ops.object.shade_smooth()
        books(0.0, ym, 0.15, [(0.30, 0.22, 0.05, '#D9CFBF'), (0.27, 0.2, 0.04, '#EFEAE2')], rng_seed=8)
        arts.append(painting('solstice', 0, ART_CZ, ART_H, '#1c1c1c'))
    elif key == 'grove':
        room('#EDEDEA', 'concrete', '#C9C7C3', sun_side=-1, leaves='olive', sun_strength=4.5, seed=5)
        top, ymid = sideboard(-0.62, 0.62, 0.42, 0.70, '#E9E7E3', kind='lacquer', legs_hex='#9a9894')
        char = material('charcoal', '#33312E', rough=0.45, coat=0.2)
        vessel('vase', lambda t: 0.045 + 0.03 * math.sin(math.pi * t) ** 1.2 - 0.01 * t, 0.33, -0.47, ymid, top, char)
        branch_set('br', -0.47, ymid, top + 0.31, material('twig', '#3a3430', rough=0.8), lean=-0.45, seed=21)
        white = material('white_glaze', '#F2F0EC', rough=0.3, coat=0.25)
        vessel('jar', lambda t: 0.03 + 0.13 * math.sin(math.pi * min(1, t * 0.97 + 0.02)) ** 0.75, 0.28, 0.43, ymid, top,
               white)
        books(0.12, ymid, top, [(0.2, 0.15, 0.03, '#F4F2EE'), (0.18, 0.14, 0.026, '#8E8C88')])
        arts.append(painting('grove', 0, ART_CZ, ART_H, '#B89A6E'))
    elif key == 'collection':
        room('#EFECE7', 'oak', '#C9AE88', sun_side=-1, leaves=None, sun_strength=2.5, seed=6)
        h, gx, gz = 0.60, 0.08, 0.07
        order = [['convergence', 'morning-light'], ['solstice', 'grove']]
        rows_cz = [1.36 + h / 2 + gz / 2 + 0.02, 1.36 - h / 2 - gz / 2 + 0.02]
        for r, row in enumerate(order):
            ws = [h * Image.open(ART[k]).width / Image.open(ART[k]).height for k in row]
            x = -(sum(ws) + gx) / 2
            for k, w in zip(row, ws):
                arts.append(painting(k, x + w / 2, rows_cz[r], h, '#1c1c1c' if k == 'solstice' else '#B89A6E'))
                x += w + gx
        leather = material('leather', '#26221F', rough=0.45, bump=0.1, bump_scale=300)
        chrome = material('chrome', '#d0d0d0', rough=0.15, metal=1.0)
        box('bench', -0.50, 0.50, -0.50, -0.14, 0.40, 0.46, leather, bevel=0.02)
        for lx in (-0.44, 0.415):
            for ly in (-0.47, -0.19):
                box('leg', lx, lx + 0.025, ly, ly + 0.025, 0, 0.40, chrome, bevel=0.003)
        # picture lights from the ceiling
        for x in (-0.36, 0.36):
            sl = bpy.data.lights.new('spot', 'SPOT')
            sl.energy = 120
            sl.spot_size = math.radians(55)
            sl.spot_blend = 0.6
            sl.shadow_soft_size = 0.05
            sl.color = (1.0, 0.92, 0.8)
            so = link(bpy.data.objects.new('spot', sl))
            so.location = (x, -1.1, 2.95)
            so.rotation_euler = (math.radians(35), 0, 0)
    return arts


def throw(x0, x1, y0, y1, h, mat):
    """A folded linen throw lying on the bench and hanging over its front edge."""
    me = bpy.data.meshes.new('throw')
    bm = bmesh.new()
    nx, nt = 40, 40
    grid = []
    hang = 0.26
    for j in range(nt + 1):
        t = j / nt
        row = []
        for i in range(nx + 1):
            u = i / nx
            x = x0 + (x1 - x0) * u
            fold = 0.006 * math.sin(u * math.pi * 7 + t * 2)
            # path: across the top (back->front), round the edge, then down
            s = t * (abs(y1 - y0) * 0.7 + 0.03 + hang)
            top_len = abs(y1 - y0) * 0.7
            if s < top_len:
                y, z = y1 - 0.05 - s, h + 0.008 + fold * 0.3
            elif s < top_len + 0.03:
                a = (s - top_len) / 0.03 * math.pi / 2
                y, z = y1 - 0.05 - top_len - math.sin(a) * 0.012, h + 0.008 - (1 - math.cos(a)) * 0.012
            else:
                d = s - top_len - 0.03
                y, z = y0 - 0.014 - fold - 0.01 * d, h - 0.004 - d
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for j in range(nt):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new('throw', me))
    ob.data.materials.append(mat)
    so = ob.modifiers.new('solid', 'SOLIDIFY')
    so.thickness = 0.008
    for f in ob.data.polygons:
        f.use_smooth = True


# ------------------------------------------------------------------ render + paste art
def render(key):
    arts = build(key)
    path = os.path.join(CACHE, f'raw_{key}.png')
    sc = bpy.context.scene
    sc.render.filepath = path
    sc.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    im = Image.open(path).convert('RGB').resize((OUT_W, OUT_H), Image.LANCZOS)
    out = np.asarray(im, np.float32) / 255
    for a in arts:
        x0, y0, x1, y1 = [v * 2 for v in a['rect']]
        X0, Y0, X1, Y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        w, h = X1 - X0, Y1 - Y0
        src = Image.open(ART[a['key']]).convert('RGB')
        big = src.resize((w, h), Image.LANCZOS)
        # gentle sharpening to counter the upscale
        from PIL import ImageFilter
        big = big.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=2))
        art = np.asarray(big, np.float32) / 255
        probe = out[Y0:Y1, X0:X1].mean(-1)
        probe = gaussian_filter(probe, 6)
        ref = np.median(probe)
        f = np.clip(probe / max(ref, 1e-3), 0.72, 1.35) ** 0.85
        tint = out[Y0:Y1, X0:X1] / np.maximum(out[Y0:Y1, X0:X1].mean(-1, keepdims=True), 1e-3)
        tint = gaussian_filter(tint, (8, 8, 0))
        tint = 1 + (tint - 1) * 0.5
        out[Y0:Y1, X0:X1] = np.clip(art * f[..., None] * tint, 0, 1)
    Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(os.path.join(CACHE, key + '.png'))
    if arts:
        np.save(os.path.join(CACHE, key + '.rect.npy'), np.array(arts[0]['rect']))
    print('wrote', key, flush=True)


if __name__ == '__main__':
    os.makedirs(CACHE, exist_ok=True)
    keys = [a for a in sys.argv[1:] if not a.startswith('--')] or \
        ['convergence', 'convergence_empty', 'morning_light', 'solstice', 'grove', 'collection']
    for k in keys:
        render(k)
