"""The five rooms of the reel. Each room's palette is pulled from its painting."""
import os
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter
from rooms import Scene, S, W, H, blank_mask, to_arr, rgb, noise

HERE = os.path.dirname(os.path.abspath(__file__))
ART = {k: os.path.join(HERE, 'paintings', k + '.png') for k in ('convergence', 'morning-light', 'solstice', 'grove')}

ART_TOP, ART_H = 560, 780


def bud_vase(t):
    neck = 15
    body = 52 * np.sin(np.pi * np.clip((t - 0.22) / 0.78, 0, 1)) ** 0.7
    s = np.clip((t - 0.12) / 0.2, 0, 1)
    s = s * s * (3 - 2 * s)
    return neck + (body - 0) * s + 3 * (t < 0.04)


def moon_jar(t):
    return 8 + 70 * np.sin(np.pi * np.clip(t * 0.96 + 0.02, 0, 1)) ** 0.75


def tall_vase(t):
    return 26 + 18 * np.sin(np.pi * t) ** 1.2 - 6 * t


def sphere(r):
    return lambda t: r * np.sqrt(np.clip(1 - (2 * t - 1) ** 2, 0, 1)) + 0.01


def bowl(t):
    return 58 * np.sqrt(np.clip(1 - t ** 2, 0, 1)) * (0.55 + 0.45 * (1 - t)) + 4


def window_quads(x0, y0, w, h, shear, cols=2, rows=3, bar=10):
    """Window panes projected on a wall, sheared like low sun."""
    qs = []
    pw, ph = (w - bar * (cols - 1)) / cols, (h - bar * (rows - 1)) / rows
    for r in range(rows):
        for c in range(cols):
            px, py = x0 + c * (pw + bar), y0 + r * (ph + bar)
            qs.append([(px + shear * (py - y0), py), (px + pw + shear * (py - y0), py),
                       (px + pw + shear * (py + ph - y0), py + ph), (px + shear * (py + ph - y0), py + ph)])
    return qs


def blurry_leaves(sc, cx, cy, col, n=7, size=260, blur=16, seed=5, spread=1.6, base_ang=-2.2):
    """Out-of-focus foreground foliage entering the frame from an edge."""
    mk = blank_mask()
    d = ImageDraw.Draw(mk)
    rng = np.random.default_rng(seed)
    for i in range(n):
        a = base_ang + (i / max(1, n - 1) - 0.5) * spread + rng.normal(0, 0.1)
        L = size * rng.uniform(0.75, 1.2)
        wd = L * 0.2
        pts = []
        for t in np.linspace(0, 1, 30):
            x = cx + np.cos(a) * L * t
            y = cy + np.sin(a) * L * t + 40 * t * t
            pts.append((x, y))
        left, right = [], []
        for k, (x, y) in enumerate(pts):
            t = k / 29
            ww = wd * np.sin(np.pi * t) ** 0.8
            left.append((S(x - np.sin(a) * ww), S(y + np.cos(a) * ww)))
            right.append((S(x + np.sin(a) * ww), S(y - np.cos(a) * ww)))
        d.polygon(left + right[::-1], fill=int(255 * rng.uniform(0.85, 1)))
    a = gaussian_filter(np.asarray(mk, np.float32) / 255, blur * RS_())
    c = rgb(col) * (1 + 0.15 * noise(S(H), S(W), S(90), seed))[..., None]
    sc.overlay(c, a * 0.96)


def RS_():
    from rooms import RS
    return RS


# --------------------------------------------------------------------------------------------
def convergence():
    """Red / black / grey painting -> warm plaster, light oak, ivory and travertine. No red, no black."""
    sc = Scene('#ECE6DC', light=(0.55, -0.45, 0.70), seed=11)
    sc.paint_wall(lx=0.95, ly=0.25, falloff=0.18)
    sc.window_light(window_quads(820, 260, 300, 1050, -0.32, cols=2, rows=3, bar=14), strength=0.08, blur=9,
                    color='#fff1de')
    sc.skirting(30)
    sc.floor('oak', '#C6A47A', plank=90, sheen=0.08)
    sc.window_light([[(720, 1722), (1080, 1722), (1080, 1920), (560, 1920)]], strength=0.07, blur=14)
    sc.hang(ART['convergence'], 540, ART_TOP, ART_H, shadow=(-12, 20, 22, 0.30))
    # light oak fluted sideboard
    sc.contact_shadow(150, 930, 1724, h=26, strength=0.5, blur=10)
    sc.contact_shadow(190, 890, 1723, h=8, strength=0.55, blur=3)
    sc.box(168, 1468, 912, 1482, '#CFB48C', top=14, top_col='#DCC49F', grad=0.0, wood='h')
    sc.flutes(176, 1482, 904, 1694, '#CBAE84', pitch=17, gaps=(419, 661))
    sc.box(205, 1694, 875, 1723, '#8c7150', grad=0.2)
    sc.cast_fg_shadow(-10, 4, 9, 0.38)
    # ivory vase with natural dried branches, travertine bowl, sand-toned books
    sc.branches(262, 1278, n=5, length=330, seed=4, lean=-0.42, spread=0.75, col='#7a6650')
    sc.lathe(262, 1464, 190, bud_vase, '#EFEAE0', spec=0.14, mouth=True, amb=0.5)
    sc.books(690, 1464, [(150, 20, '#E9E2D4'), (134, 16, '#CDBFA6'), (142, 19, '#F3EFE7')])
    sc.lathe(765, 1405, 46, bowl, '#D6C7AC', spec=0.08, amb=0.5, tex=0.03)
    sc.cast_fg_shadow(-26, 8, 13, 0.26)
    return sc


def morning_light():
    """Blue / yellow / grey painting -> warm greige, walnut bench, cream linen, white ceramic. No blue, no yellow."""
    sc = Scene('#E9E3D9', light=(-0.6, -0.45, 0.66), seed=21)
    sc.paint_wall(lx=0.0, ly=0.15, falloff=0.18)
    leaves = sc.leaf_shadow_mask(40, 1050, n=8, length=520, spread=1.2, blur=11, seed=3, kind='palm')
    sc.window_light(window_quads(-120, 140, 400, 1260, 0.30, cols=2, rows=3, bar=16), strength=0.13,
                    blur=8, leaves=leaves, color='#fff0d6')
    sc.skirting(30)
    sc.floor('oak', '#CDB089', plank=92, sheen=0.10)
    sc.window_light([[(0, 1722), (330, 1722), (480, 1920), (0, 1920)]], strength=0.10, blur=16, color='#fff0d6')
    sc.hang(ART['morning-light'], 540, ART_TOP, ART_H, shadow=(14, 20, 22, 0.30))
    # walnut bench
    for x in (255, 812):
        sc.contact_shadow(x - 40, x + 50, 1738, h=14, strength=0.5, blur=5)
    sc.contact_shadow(220, 860, 1730, h=40, strength=0.25, blur=16)
    sc.box(262, 1452, 300, 1738, '#5E4330', grad=0.12, wood='v')
    sc.box(780, 1452, 818, 1738, '#5E4330', grad=0.12, wood='v')
    sc.box(236, 1420, 846, 1454, '#6B4D37', top=12, top_col='#7C5B42', grad=0.06, wood='h')
    sc.cast_fg_shadow(10, 4, 8, 0.35)
    sc.throw(650, 1414, 772, 1572, '#E8E0D2', folds=4)
    sc.books(300, 1416, [(136, 22, '#EFE9DE'), (124, 16, '#B9A58A'), (128, 19, '#F6F2EA')])
    sc.lathe(510, 1416, 110, sphere(56), '#F1EEE8', spec=0.12, amb=0.5)
    sc.cast_fg_shadow(24, 6, 12, 0.25)
    blurry_leaves(sc, -60, 1980, '#2f4a2a', n=8, size=520, blur=14, seed=8, spread=1.3, base_ang=-1.05)
    return sc


def solstice():
    """Yellow / black / lavender-grey painting -> warm sand wall, light oak + travertine console. No yellow, no black."""
    sc = Scene('#EAE2D5', light=(-0.55, -0.5, 0.68), seed=31)
    sc.paint_wall(lx=0.05, ly=0.2, falloff=0.18)
    sc.window_light(window_quads(-60, 320, 320, 1000, 0.42, cols=3, rows=4, bar=10), strength=0.10, blur=6,
                    color='#fff6e6')
    sc.skirting(30)
    sc.floor('oak', '#C9AD86', plank=90, sheen=0.08)
    sc.window_light([[(0, 1722), (300, 1722), (520, 1920), (0, 1920)]], strength=0.08, blur=16)
    sc.hang(ART['solstice'], 540, ART_TOP, ART_H, shadow=(14, 20, 22, 0.30))
    # oak legs, travertine top
    for x in (232, 848):
        sc.contact_shadow(x - 22, x + 26, 1734, h=10, strength=0.5, blur=4)
    sc.contact_shadow(200, 900, 1726, h=22, strength=0.22, blur=14)
    sc.box(214, 1478, 250, 1734, '#BE9F78', grad=0.10, wood='v')
    sc.box(830, 1478, 866, 1734, '#BE9F78', grad=0.10, wood='v')
    sc.box(206, 1456, 874, 1478, '#C4A57D', grad=0.1, wood='h')
    sc.box(198, 1430, 882, 1458, '#DCD0BC', top=12, top_col='#E6DCCB', grad=0.05, tex=0.025)
    sc.cast_fg_shadow(10, 4, 8, 0.30)
    sc.branches(282, 1240, n=4, length=300, seed=12, lean=-0.40, spread=0.6, col='#7a6650')
    sc.lathe(282, 1428, 188, tall_vase, '#F4F1EB', spec=0.10, mouth=True, amb=0.5)
    sc.books(690, 1428, [(150, 20, '#F1ECE3'), (132, 17, '#C9B79C'), (140, 18, '#E4DACA')])
    sc.lathe(762, 1373, 84, sphere(42), '#CDBFA8', spec=0.06, amb=0.5, tex=0.03)
    sc.cast_fg_shadow(26, 8, 13, 0.26)
    return sc


def grove():
    """Green / orange / yellow / brown painting -> soft white wall, pale grey concrete, white + charcoal ceramics.
    No green, no orange, no yellow, no wood brown."""
    sc = Scene('#EEEDEA', light=(-0.55, -0.45, 0.70), seed=41)
    sc.paint_wall(lx=0.0, ly=0.1, falloff=0.18)
    leaves = sc.leaf_shadow_mask(30, 1100, n=7, length=560, spread=1.3, blur=9, seed=6, kind='olive')
    sc.window_light(window_quads(-100, 240, 380, 1180, 0.30, cols=2, rows=3, bar=14), strength=0.10,
                    blur=8, leaves=leaves, color='#fff6ea')
    sc.skirting(30)
    sc.floor('concrete', '#CFCDCA', sheen=0.08)
    sc.window_light([[(0, 1722), (320, 1722), (470, 1920), (0, 1920)]], strength=0.08, blur=16, color='#fff6ea')
    sc.hang(ART['grove'], 540, ART_TOP, ART_H, shadow=(14, 20, 22, 0.30))
    # matte white fluted sideboard
    sc.contact_shadow(150, 930, 1724, h=26, strength=0.45, blur=10)
    sc.contact_shadow(200, 880, 1723, h=8, strength=0.5, blur=3)
    sc.box(170, 1468, 910, 1482, '#E9E7E3', top=14, top_col='#F4F3F0', grad=0.0)
    sc.flutes(178, 1482, 902, 1694, '#E6E4E0', pitch=34, depth=0.35, gaps=(419, 661))
    sc.box(210, 1694, 870, 1723, '#9a9894', grad=0.2)
    sc.cast_fg_shadow(10, 4, 9, 0.34)
    sc.branches(285, 1290, n=5, length=310, seed=21, lean=-0.42, spread=0.8, col='#3a3633')
    sc.lathe(285, 1464, 175, tall_vase, '#3B3936', spec=0.12, mouth=True, amb=0.45)
    sc.lathe(768, 1464, 150, moon_jar, '#F2F0EC', spec=0.12, shin=28, amb=0.5, tex=0.02)
    sc.books(600, 1464, [(96, 16, '#F4F2EE'), (88, 14, '#8E8C88')])
    sc.cast_fg_shadow(24, 8, 13, 0.26)
    return sc


def collection():
    """Gallery wall with all four originals under picture lights."""
    sc = Scene('#EFECE7', light=(0.0, -0.6, 0.8), seed=51)
    sc.paint_wall(lx=0.5, ly=0.35, falloff=0.22)
    order = ['convergence', 'morning-light', 'solstice', 'grove']
    h, gap, row_gap, top = 400, 52, 46, 615
    widths = {k: h * Image.open(ART[k]).width / Image.open(ART[k]).height for k in order}
    yy, xx = sc.yy, sc.xx
    for r, row in enumerate([order[:2], order[2:]]):
        y0 = top + r * (h + row_gap)
        x = (W - (widths[row[0]] + widths[row[1]] + gap)) / 2
        for k in row:
            w = widths[k]
            cx = x + w / 2
            spread = 30 + np.clip(yy - (y0 - 140), 0, None) * 0.45
            pool = (np.exp(-((xx - cx) / spread) ** 2) * np.clip((yy - (y0 - 140)) / 120, 0, 1)
                    * np.exp(-np.clip(yy - (y0 + 40), 0, None) / 160))
            sc.img += (pool * 0.06)[..., None] * rgb('#fff4e2')
            sc.hang(ART[k], cx, y0, h, shadow=(0, 18, 16, 0.28))
            x += w + gap
    sc.skirting(30)
    sc.floor('oak', '#CDB28C', plank=90, sheen=0.05)
    # gallery bench
    sc.contact_shadow(300, 780, 1736, h=30, strength=0.35, blur=14)
    for lx in (340, 730):
        sc.box(lx, 1580, lx + 10, 1736, '#b9b9b9', grad=0.3)
    sc.box(290, 1530, 790, 1584, '#232120', top=16, top_col='#34312f', radius=6, grad=0.15, tex=0.02)
    sc.cast_fg_shadow(0, 6, 10, 0.3)
    return sc


BUILDERS = dict(convergence=convergence, morning_light=morning_light, solstice=solstice, grove=grove,
                collection=collection)
