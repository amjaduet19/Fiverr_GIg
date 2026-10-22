"""Procedural interior scenes for the ark_artworks_ reel.

Every scene is drawn in 1x reel coordinates (1080x1920) and rendered at RS times
that size so the camera can push into the paintings without going soft.
The paintings themselves are pasted pixel-for-pixel from the source photos;
only the room around them is generated.
"""
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

RS = 2
W, H = 1080, 1920


def S(v):
    return int(round(v * RS))


def rgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def noise(h, w, scale, seed):
    """Smooth value noise with unit std, feature size ~scale px."""
    rng = np.random.default_rng(seed)
    sh, sw = max(2, int(h / scale)) + 3, max(2, int(w / scale)) + 3
    n = rng.standard_normal((sh, sw)).astype(np.float32)
    im = Image.fromarray(n, mode='F').resize((w, h), Image.BICUBIC)
    a = np.asarray(im)
    return (a - a.mean()) / (a.std() + 1e-6)


def streaks(h, w, vertical, seed):
    """Anisotropic noise for wood grain."""
    rng = np.random.default_rng(seed)
    sh, sw = (int(h / S(90)) + 3, int(w / S(1.6)) + 3) if not vertical else (int(h / S(1.6)) + 3, int(w / S(90)) + 3)
    n = rng.standard_normal((sh, sw)).astype(np.float32)
    a = np.asarray(Image.fromarray(n, mode='F').resize((w, h), Image.BICUBIC))
    return (a - a.mean()) / (a.std() + 1e-6)


def blank_mask(w=W, h=H):
    return Image.new('L', (S(w), S(h)), 0)


def to_arr(mask, blur=0.6):
    a = np.asarray(mask, np.float32) / 255
    if blur:
        a = gaussian_filter(a, blur * RS)
    return a


def blend(img, mask, color, opacity=1.0):
    """Paint color (rgb vector or HxWx3 array) through a float mask."""
    m = mask * opacity
    ys, xs = np.nonzero(m > 0.002)
    if len(ys) == 0:
        return
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    mm = m[y0:y1, x0:x1, None]
    c = color[y0:y1, x0:x1] if np.ndim(color) == 3 else color
    img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - mm) + c * mm


def darken(img, mask, strength, tint=(1.0, 0.97, 0.94)):
    """Multiply-shadow; the slight warm-to-cool tint keeps shadows from going muddy."""
    m = mask * strength
    ys, xs = np.nonzero(m > 0.002)
    if len(ys) == 0:
        return
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    mm = m[y0:y1, x0:x1, None]
    t = np.array(tint, np.float32)
    img[y0:y1, x0:x1] *= 1 - mm * t


def lighten(img, mask, strength, color):
    m = mask * strength
    ys, xs = np.nonzero(m > 0.002)
    if len(ys) == 0:
        return
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    mm = m[y0:y1, x0:x1, None]
    img[y0:y1, x0:x1] += mm * color


def shift(mask, dx, dy):
    out = np.zeros_like(mask)
    dx, dy = S(dx), S(dy)
    h, w = mask.shape
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = \
        mask[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    return out


class Scene:
    """A wall + floor room with a light source; layers are composited back to front."""

    def __init__(self, wall, floor_y=1720, vp=(540, 1000), light=(-0.55, -0.45, 0.70), seed=1):
        self.wall_col = rgb(wall)
        self.floor_y = floor_y
        self.vp = vp
        L = np.array(light, np.float32)
        self.L = L / np.linalg.norm(L)
        self.seed = seed
        self.img = np.zeros((S(H), S(W), 3), np.float32)
        self.fg = np.zeros((S(H), S(W), 3), np.float32)
        self.fg_a = np.zeros((S(H), S(W)), np.float32)
        yy, xx = np.mgrid[0:S(H), 0:S(W)].astype(np.float32)
        self.yy, self.xx = yy / RS, xx / RS

    # ---------- architecture ----------
    def paint_wall(self, lx=0.0, ly=0.0, falloff=0.16, texture=1.0):
        h, w = S(H), S(W)
        nx, ny = self.xx / W, self.yy / H
        d2 = (nx - lx) ** 2 + (ny - ly) ** 2 * 0.55
        bright = 1.03 - falloff * 0.45 * d2
        tex = (noise(h, w, S(260), self.seed) * 0.005 + noise(h, w, S(40), self.seed + 1) * 0.004
               + noise(h, w, S(3), self.seed + 2) * 0.004) * texture
        self.img[:] = self.wall_col * (bright + tex)[..., None]

    def brick_wall(self, mortar='#d9d6d1', lx=0.0, ly=0.0, falloff=0.16):
        """Whitewashed painted brick."""
        self.paint_wall(lx, ly, falloff, texture=0.8)
        bh, bw, mt = 46, 150, 7
        rng = np.random.default_rng(self.seed + 7)
        row = np.floor(self.yy / bh).astype(int)
        off = (row % 2) * bw / 2
        col = np.floor((self.xx + off) / bw).astype(int)
        fy = self.yy - row * bh
        fx = (self.xx + off) - col * bw
        tone = rng.normal(0, 1, (row.max() + 2, col.max() + 3)).astype(np.float32)
        t = tone[row, col]
        mort = np.clip(np.minimum(fy, fx) - mt / 2, 0, 1.5) / 1.5
        mort = gaussian_filter(mort, 0.6 * RS)
        edge_hi = np.exp(-((fy - mt / 2) ** 2) / 6) * 0.05
        edge_lo = np.exp(-((fy - bh + 1) ** 2) / 6) * 0.06
        wash = noise(S(H), S(W), S(30), self.seed + 9)
        brick = 1 + t * 0.018 + edge_hi - edge_lo + np.clip(wash, -3, 0) * 0.012
        mortar_shade = 0.90
        f = brick * mort + mortar_shade * (1 - mort)
        self.img *= f[..., None]
        self.img[self.yy > self.floor_y] = self.img[self.yy > self.floor_y]  # untouched floor rows get repainted later

    def skirting(self, height=34, col=None):
        fy = self.floor_y
        c = self.wall_col * 1.04 if col is None else rgb(col)
        m = (self.yy >= fy - height) & (self.yy < fy)
        sh = 1 + 0.03 * noise(S(H), S(W), S(12), self.seed + 3)
        self.img[m] = (c * sh[m][:, None])
        lip = np.exp(-((self.yy - (fy - height)) ** 2) / 2.0)
        self.img += (lip * 0.05)[..., None] * (self.yy < fy)[..., None]
        under = np.exp(-np.clip((fy - height) - self.yy, 0, None) / 4) * (self.yy < fy - height)
        darken(self.img, under.astype(np.float32), 0.06)
        # ambient occlusion where wall meets floor
        ao = np.exp(-np.clip(fy - self.yy, 0, None) / 10) * (self.yy < fy)
        darken(self.img, ao.astype(np.float32), 0.10)

    def floor(self, kind, col, plank=86, sheen=0.06):
        fy, (vx, vy) = self.floor_y, self.vp
        m = self.yy >= fy
        y, x = self.yy[m], self.xx[m]
        d = (y - vy)
        u = vx + (x - vx) * (fy - vy) / d
        z = (fy - vy) / d                     # 1 at wall, smaller toward camera
        base = rgb(col)
        rng = np.random.default_rng(self.seed + 11)
        if kind == 'oak':
            pi = np.floor(u / plank).astype(int) + 200
            tone = rng.normal(0, 1, 600).astype(np.float32)
            joff = rng.random(600).astype(np.float32)
            # grain streaks run along the planks (toward the camera)
            gtex = noise(48, 4096, 1.5, self.seed + 12)
            gi = ((1 / z) * 30 + pi * 7).astype(int) % 48
            gj = (u * 6 * RS).astype(int) % 4096
            grain = gtex[gi, gj]
            shade = 1 + tone[pi] * 0.05 + grain * 0.03
            seam_px = np.abs(((u + plank / 2) % plank) - plank / 2) * (d / (fy - vy))
            seam = np.clip(seam_px * RS / 1.2, 0, 1)
            along = (1 / z) * 1.6 + joff[pi] * 3
            jpx = np.abs(((along + 0.5) % 3.0) - 0.5) * 40 * z
            joint = np.clip(jpx, 0, 1)
            shade *= 0.72 + 0.28 * np.minimum(seam, joint)
        else:  # microcement / polished concrete
            n1 = noise(S(H), S(W), S(160), self.seed + 13)[m]
            n2 = noise(S(H), S(W), S(18), self.seed + 14)[m]
            shade = 1 + n1 * 0.025 + n2 * 0.010
        t = (y - fy) / (H - fy)
        light = 1 + sheen * np.exp(-((x / W - 0.5 + self.L[0] * 0.4) ** 2) / 0.08) * (1 - t * 0.4)
        ao = 1 - 0.16 * np.exp(-(y - fy) / 7)
        self.img[m] = base * (shade * light * ao * (0.97 - 0.06 * t))[:, None]

    def window_light(self, quads, color='#fff3dc', strength=0.10, blur=7, leaves=None, clip_rect=None):
        """Sun patches through a window: list of 4-point polygons (1x coords)."""
        mk = blank_mask()
        d = ImageDraw.Draw(mk)
        for q in quads:
            d.polygon([(S(x), S(y)) for x, y in q], fill=255)
        m = to_arr(mk, blur)
        if leaves is not None:
            m *= 1 - leaves
        if clip_rect is not None:
            x0, y0, x1, y1 = clip_rect
            m[S(y0):S(y1), S(x0):S(x1)] = 0
            m = gaussian_filter(m, 2 * RS)
        lighten(self.img, m, strength, rgb(color))

    def leaf_shadow_mask(self, cx, cy, n=9, length=260, spread=1.1, blur=10, seed=0, kind='palm'):
        """Blurry palm/olive leaf silhouettes used to break up window light."""
        mk = blank_mask()
        d = ImageDraw.Draw(mk)
        rng = np.random.default_rng(seed)
        for i in range(n):
            ang = -np.pi / 2 + (i - n / 2) / n * spread * 2 + rng.normal(0, 0.12)
            L = length * rng.uniform(0.7, 1.1)
            pts = []
            for t in np.linspace(0, 1, 26):
                bend = 0.35 * t * t
                a = ang + bend * np.sign(np.cos(ang))
                pts.append((cx + np.cos(a) * L * t, cy + np.sin(a) * L * t))
            d.line([(S(x), S(y)) for x, y in pts], fill=255, width=S(3))
            if kind == 'palm':
                for k in range(3, 25, 1):
                    x, y = pts[k]
                    tx, ty = pts[k + 1][0] - pts[k - 1][0], pts[k + 1][1] - pts[k - 1][1]
                    nrm = np.hypot(tx, ty) + 1e-6
                    px, py = -ty / nrm, tx / nrm
                    ll = 70 * np.sin(np.pi * k / 26) + 10
                    for s in (-1, 1):
                        ex, ey = x + s * px * ll + tx / nrm * ll * 0.55, y + s * py * ll + ty / nrm * ll * 0.55
                        d.line([(S(x), S(y)), (S(ex), S(ey))], fill=255, width=S(7))
            else:
                for k in range(2, 25, 2):
                    x, y = pts[k]
                    for s in (-1, 1):
                        a = ang + s * 0.8 + rng.normal(0, 0.2)
                        ll = 34
                        ex, ey = x + np.cos(a) * ll, y + np.sin(a) * ll
                        d.line([(S(x), S(y)), (S(ex), S(ey))], fill=255, width=S(11))
        return to_arr(mk, blur)

    # ---------- foreground objects ----------
    def _put(self, color, alpha):
        ys, xs = np.nonzero(alpha > 0.002)
        if len(ys) == 0:
            return
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        a = alpha[y0:y1, x0:x1, None]
        c = color[y0:y1, x0:x1] if np.ndim(color) == 3 else color
        self.fg[y0:y1, x0:x1] = self.fg[y0:y1, x0:x1] * (1 - a) + c * a
        self.fg_a[y0:y1, x0:x1] = self.fg_a[y0:y1, x0:x1] * (1 - a[..., 0]) + a[..., 0]

    def box(self, x0, y0, x1, y1, col, top=0, top_col=None, grad=0.10, radius=0, tex=0.0, grain=None, wood=None):
        """Front-facing slab with an optional visible top surface (we look down on it)."""
        mk = blank_mask()
        ImageDraw.Draw(mk).rounded_rectangle([S(x0), S(y0 - top), S(x1), S(y1)], radius=S(radius), fill=255)
        a = to_arr(mk, 0.4)
        c = rgb(col)
        t = np.clip((self.yy - y0) / max(1, (y1 - y0)), 0, 1)
        shade = (1 + grad * 0.5 - grad * t) * (1 + 0.04 * (0.5 - self.xx / W) * np.sign(-self.L[0]))
        if tex:
            shade = shade + tex * noise(S(H), S(W), S(6), self.seed + int(x0))
        if grain is not None:
            shade = shade + grain
        if wood:
            shade = shade + 0.045 * streaks(S(H), S(W), wood == 'v', self.seed + int(x0 + y0))
        colr = c * shade[..., None]
        if top:
            tc = rgb(top_col) if top_col else c * 1.18
            tm = (self.yy < y0)
            colr[tm] = tc * (1 + (tex * noise(S(H), S(W), S(6), self.seed + 5)[tm] if tex else 0))[..., None] \
                if tex else tc
            edge = np.exp(-((self.yy - y0) ** 2) / 1.2)
            colr += (edge * 0.10)[..., None]
        self._put(colr, a)
        return a

    def flutes(self, x0, y0, x1, y1, col, pitch=18, depth=0.55, gaps=()):
        mk = blank_mask()
        ImageDraw.Draw(mk).rectangle([S(x0), S(y0), S(x1), S(y1)], fill=255)
        a = to_arr(mk, 0.4)
        f = ((self.xx - x0) % pitch) / pitch
        nx = (2 * f - 1) * depth
        nz = np.sqrt(1 - nx ** 2)
        diff = np.clip(nx * self.L[0] * 1.4 + nz * self.L[2], 0, 1)
        t = np.clip((self.yy - y0) / (y1 - y0), 0, 1)
        shade = (0.55 + 0.55 * diff) * (1.04 - 0.10 * t)
        groove = np.exp(-((f * pitch) ** 2) / 1.5) + np.exp(-(((1 - f) * pitch) ** 2) / 1.5)
        shade *= 1 - 0.25 * groove
        for gx in gaps:
            shade *= 1 - 0.55 * np.exp(-((self.xx - gx) ** 2) / 1.0)
        self._put(rgb(col) * shade[..., None], a)
        return a

    def lathe(self, cx, ybot, height, prof, col, spec=0.18, shin=24, mouth=False, tex=0.008, amb=0.42):
        """Surface of revolution (vases, bowls, spheres). prof(t), t=0 top..1 bottom -> radius."""
        y0, y1 = S(ybot - height), S(ybot)
        ys = np.arange(y0, y1)
        t = (ys - y0) / max(1, (y1 - y0 - 1))
        r = np.maximum(prof(t) * RS, 0.01)
        dr = np.gradient(r)
        rmax = r.max()
        xs = np.arange(int(S(cx) - rmax - 3), int(S(cx) + rmax + 4))
        X = (xs[None, :] - S(cx)).astype(np.float32)
        R = r[:, None]
        alpha = np.clip(R - np.abs(X) + 0.5, 0, 1)
        xn = np.clip(X / R, -0.999, 0.999)
        k = 1 / np.sqrt(1 + dr[:, None] ** 2)
        n = np.stack([xn * k, -dr[:, None] * k * np.ones_like(xn), np.sqrt(1 - xn ** 2) * k], -1)
        L = self.L
        diff = np.clip((n * L).sum(-1), 0, 1)
        Hv = L + np.array([0, 0, 1], np.float32)
        Hv /= np.linalg.norm(Hv)
        sp = np.clip((n * Hv).sum(-1), 0, 1) ** shin
        rim = (1 - n[..., 2]) ** 3 * 0.10
        c = rgb(col)
        nz = noise(len(ys), len(xs), 5, int(cx + ybot)) * tex
        colr = c * (amb + (1 - amb) * diff + nz)[..., None] + (sp * spec + rim)[..., None]
        full_c = np.zeros_like(self.fg)
        full_a = np.zeros_like(self.fg_a)
        full_c[y0:y1, xs[0]:xs[-1] + 1] = colr
        full_a[y0:y1, xs[0]:xs[-1] + 1] = alpha
        self._put(full_c, full_a)
        if mouth:
            rt = prof(0.0)
            mk = blank_mask()
            ImageDraw.Draw(mk).ellipse([S(cx - rt * 0.8), S(ybot - height - rt * 0.12),
                                        S(cx + rt * 0.8), S(ybot - height + rt * 0.16)], fill=255)
            self._put(c * 0.25, to_arr(mk, 0.4))
        return full_a

    def contact_shadow(self, x0, x1, y, h=10, strength=0.5, blur=6, on='img'):
        mk = blank_mask()
        ImageDraw.Draw(mk).ellipse([S(x0), S(y - h / 2), S(x1), S(y + h / 2)], fill=255)
        m = to_arr(mk, blur)
        darken(self.img if on == 'img' else self.fg, m, strength)

    def branches(self, x, y, n=5, length=330, col='#2b2723', seed=3, leaves=None, leaf_col='#6f7d55', spread=0.9, lean=0.0):
        """Dried branches / olive stems rising out of a vase."""
        mk = blank_mask()
        lk = blank_mask()
        d, dl = ImageDraw.Draw(mk), ImageDraw.Draw(lk)
        rng = np.random.default_rng(seed)
        for i in range(n):
            ang = -np.pi / 2 + lean + (i - (n - 1) / 2) / max(1, n - 1) * spread + rng.normal(0, 0.08)
            L = length * rng.uniform(0.75, 1.1)
            pts = [(x, y)]
            a = ang
            for s in range(18):
                a += rng.normal(0, 0.07)
                px, py = pts[-1]
                pts.append((px + np.cos(a) * L / 18, py + np.sin(a) * L / 18))
            for j in range(len(pts) - 1):
                wdt = max(1, S(3.2 * (1 - j / 20)))
                d.line([(S(pts[j][0]), S(pts[j][1])), (S(pts[j + 1][0]), S(pts[j + 1][1]))], fill=255, width=wdt)
            for j in range(4, 17, 3):
                px, py = pts[j]
                b = a + rng.choice([-1, 1]) * rng.uniform(0.4, 0.8)
                bl = L * rng.uniform(0.1, 0.22)
                d.line([(S(px), S(py)), (S(px + np.cos(b) * bl), S(py + np.sin(b) * bl))], fill=255, width=S(1.5))
            if leaves:
                for j in range(3, 18):
                    px, py = pts[j]
                    for sgn in (-1, 1):
                        b = ang + sgn * rng.uniform(0.5, 0.9)
                        ll = rng.uniform(16, 26)
                        ex, ey = px + np.cos(b) * ll, py + np.sin(b) * ll
                        dl.line([(S(px), S(py)), (S(ex), S(ey))], fill=255, width=S(5))
        a = to_arr(mk, 0.35)
        self._put(rgb(col), a)
        if leaves:
            la = to_arr(lk, 0.5)
            lc = rgb(leaf_col) * (1 + 0.12 * noise(S(H), S(W), S(8), seed))[..., None]
            self._put(lc, la)
            a = np.maximum(a, la)
        return a

    def books(self, x0, ybot, specs):
        """specs: list of (width, height, colour) from bottom up."""
        y = ybot
        for w, h, c in specs:
            self.box(x0, y - h, x0 + w, y, c, grad=0.06)
            # page edge on the right
            self.box(x0 + w - 3, y - h + 2, x0 + w, y - 2, '#efe9df', grad=0.0)
            y -= h
            x0 += np.random.default_rng(int(w * h)).uniform(-8, 8)

    def throw(self, x0, y0, x1, y1, col, folds=5):
        mk = blank_mask()
        d = ImageDraw.Draw(mk)
        pts = [(S(x0), S(y0))] + [(S(x0 + (x1 - x0) * i / 10), S(y1 + 6 * np.sin(i * 1.3))) for i in range(11)] + [(S(x1), S(y0))]
        d.polygon(pts, fill=255)
        a = to_arr(mk, 0.5)
        f = (self.xx - x0) / (x1 - x0)
        sh = 0.86 + 0.14 * np.sin(f * np.pi * folds) * (0.4 + 0.6 * np.clip((self.yy - y0) / (y1 - y0), 0, 1))
        weave = 1 + 0.035 * noise(S(H), S(W), S(2.2), 77)
        self._put(rgb(col) * (sh * weave)[..., None], a)

    def cushion(self, x0, y0, x1, y1, col):
        mk = blank_mask()
        ImageDraw.Draw(mk).rounded_rectangle([S(x0), S(y0), S(x1), S(y1)], radius=S((y1 - y0) * 0.45), fill=255)
        a = to_arr(mk, 0.6)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        nx = (self.xx - cx) / ((x1 - x0) / 2)
        ny = (self.yy - cy) / ((y1 - y0) / 2)
        nz = np.sqrt(np.clip(1 - 0.5 * nx ** 2 - 0.7 * ny ** 2, 0.05, 1))
        diff = np.clip(nx * self.L[0] * 0.6 + ny * self.L[1] * 0.8 + nz * self.L[2], 0, 1)
        bou = 1 + 0.06 * noise(S(H), S(W), S(2.5), 31)
        self._put(rgb(col) * ((0.5 + 0.55 * diff) * bou)[..., None], a)

    # ---------- shadows from the foreground onto the room ----------
    def cast_fg_shadow(self, dx, dy, blur, strength, wall_only=True):
        """Soft shadow of everything currently in the foreground layer, kept until compose()."""
        m = gaussian_filter(shift(self.fg_a, dx, dy), blur * RS) * strength
        if wall_only:
            m *= (self.yy < self.floor_y)
        self.fg_shadow = np.maximum(getattr(self, 'fg_shadow', np.zeros_like(m)), m)

    def overlay(self, color, alpha):
        """Out-of-focus foreground (leaves etc.) that sits in front of everything."""
        self.top_c, self.top_a = color, alpha

    # ---------- the artwork ----------
    def hang(self, path, cx, top, height, shadow=(10, 20, 22, 0.30)):
        """Hang a painting: pasted unchanged (only resized), with a soft wall shadow."""
        art = Image.open(path).convert('RGB')
        w = height * art.width / art.height
        x0, y0 = cx - w / 2, top
        art = art.resize((S(w), S(height)), Image.LANCZOS)
        if not hasattr(self, 'arts'):
            self.arts = []
        dx, dy, blur, st = shadow
        mk = blank_mask()
        ImageDraw.Draw(mk).rectangle([S(x0), S(y0), S(x0 + w), S(y0 + height)], fill=255)
        base = to_arr(mk, 0)
        soft = gaussian_filter(shift(base, dx, dy), blur * RS) * st
        tight = gaussian_filter(shift(base, dx * 0.2, 4), 2.5 * RS) * 0.35
        self.arts.append(dict(img=np.asarray(art, np.float32) / 255, xy=(S(x0), S(y0)),
                              rect=(x0, y0, x0 + w, y0 + height),
                              shadow=np.clip(soft + tight, 0, 1)))
        return self.arts[-1]

    def compose(self, with_art=True):
        out = self.img.copy()
        if with_art:
            for a in getattr(self, 'arts', []):
                darken(out, a['shadow'], 1.0)
                x, y = a['xy']
                h, w = a['img'].shape[:2]
                out[y:y + h, x:x + w] = a['img']
        if hasattr(self, 'fg_shadow'):
            darken(out, self.fg_shadow * (1 - self.fg_a), 1.0)
        al = self.fg_a[..., None]
        out = out * (1 - al) + self.fg * al
        if hasattr(self, 'top_a'):
            ta = self.top_a[..., None]
            out = out * (1 - ta) + self.top_c * ta
        return Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))
