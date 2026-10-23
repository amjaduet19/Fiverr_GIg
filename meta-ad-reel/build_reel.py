"""Builds the ark_artworks_ Meta ad reel.

    python3 build_reel.py            # 9:16 Reels/Stories version (1080x1920)
    python3 build_reel.py --feed     # 4:5 Feed version (1080x1350)
    python3 build_reel.py --preview  # a few stills only, no video

Rooms are generated in scenes.py; the four paintings are used exactly as photographed.
"""
import os
import sys
import subprocess
import wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import fftconvolve, butter, sosfilt

import scenes
from rooms import RS, W, H

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'output')
CACHE = os.path.join(HERE, '.cache')
FPS = 30
DUR = 30.0
FEED = '--feed' in sys.argv
OW, OH = (1080, 1350) if FEED else (1080, 1920)
# where the text block starts (reel: below the top 14% Reels UI zone)
TEXT_Y = 46 if FEED else 300
# vertical centre of the wide shot in room coordinates
WIDE_CY = 960
TS = 0.78 if FEED else 1.0  # text scale

F = lambda n: os.path.join(HERE, 'fonts', n)
SERIF_I = F('cormorant-garamond-latin-500-italic.woff')
SANS = F('montserrat-latin-600-normal.woff')
SANS_R = F('montserrat-latin-500-normal.woff')
INK = (31, 29, 27)

# ------------------------------------------------------------------ copy
# Each painting: (room, accent colour, kicker, headline lines, detail point as fraction of painting)
PAINTINGS = [
    ('convergence', (150, 26, 30), 'NO. 01  —  CONVERGENCE', ['Bold, but', 'never loud.'], (0.27, 0.24)),
    ('morning_light', (31, 92, 168), 'NO. 02  —  MORNING LIGHT', ['Soft light.', 'Slow mornings.'], (0.45, 0.42)),
    ('solstice', (128, 100, 0), 'NO. 03  —  SOLSTICE', ['A little sunshine', 'that never sets.'], (0.62, 0.27)),
    ('grove', (48, 92, 52), 'NO. 04  —  GROVE', ['Warm earth,', 'fresh green.'], (0.38, 0.56)),
]
HOOK = ('ORIGINAL ABSTRACT ART', ['Your walls have been', 'quiet long enough.'])
END = ('@ark_artworks_', ['Four originals.', 'One belongs on your wall.'], 'HAND-PAINTED  ·  CUSTOM SIZES')

# ------------------------------------------------------------------ rooms
def load_rooms():
    os.makedirs(CACHE, exist_ok=True)
    rooms, rects = {}, {}
    for key, build in scenes.BUILDERS.items():
        p = os.path.join(CACHE, key + '.png')
        r = os.path.join(CACHE, key + '.rect.npy')
        if not os.path.exists(p):
            print('rendering room', key, flush=True)
            sc = build()
            sc.compose().save(p)
            np.save(r, np.array(sc.arts[0]['rect']))
            if key == 'convergence':
                sc.compose(with_art=False).save(os.path.join(CACHE, 'convergence_empty.png'))
        rooms[key] = Image.open(p).convert('RGB')
        rects[key] = np.load(r)
    rooms['convergence_empty'] = Image.open(os.path.join(CACHE, 'convergence_empty.png')).convert('RGB')
    return rooms, rects


# ------------------------------------------------------------------ easing / camera
def ease(t, kind):
    t = min(max(t, 0.0), 1.0)
    if kind == 'lin':
        return t
    if kind == 'out':
        return 1 - (1 - t) ** 3
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def cam_at(keys, t):
    """keys: [(time, zoom, cx, cy, ease_into_this_key)]"""
    if t <= keys[0][0]:
        return keys[0][1:4]
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            u = ease((t - a[0]) / (b[0] - a[0]), b[4])
            z = np.exp(np.log(a[1]) + (np.log(b[1]) - np.log(a[1])) * u)
            return z, a[2] + (b[2] - a[2]) * u, a[3] + (b[3] - a[3]) * u
    return keys[-1][1:4]


def view(img, z, cx, cy):
    vw, vh = OW / z, OH / z
    cx = min(max(cx, vw / 2), W - vw / 2)
    cy = min(max(cy, vh / 2), H - vh / 2)
    box = ((cx - vw / 2) * RS, (cy - vh / 2) * RS, (cx + vw / 2) * RS, (cy + vh / 2) * RS)
    return img.resize((OW, OH), Image.BICUBIC, box=box, reducing_gap=2.0)


# ------------------------------------------------------------------ text
_fonts = {}


def font(path, size):
    if (path, size) not in _fonts:
        _fonts[path, size] = ImageFont.truetype(path, size)
    return _fonts[path, size]


def spaced(draw, y, text, fnt, fill, tracking):
    widths = [draw.textlength(ch, font=fnt) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (OW - total) / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += w + tracking


def text_layer(block, t, t_in, t_out):
    """block = (kicker, kicker_rgb, lines, sub). Lines stagger in, all fade out together."""
    kicker, kcol, lines, sub = block
    layer = Image.new('RGBA', (OW, OH), (0, 0, 0, 0))
    out = 1 - ease((t - t_out) / 0.45, 'inout') if t_out is not None else 1.0
    items = [('k', kicker)] + [('l', l) for l in lines] + ([('s', sub)] if sub else [])
    y = TEXT_Y
    for i, (kind, txt) in enumerate(items):
        u = ease((t - t_in - i * 0.14) / 0.7, 'out')
        a = u * out
        h = int({'k': 50, 'l': 84, 's': 52}[kind] * TS)
        if a > 0.01:
            lay = Image.new('RGBA', (OW, h + 30), (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            if kind == 'k':
                spaced(d, 6, txt, font(SANS, int(25 * TS)), kcol + (255,), (7.5 if txt.isupper() else 2.5) * TS)
            elif kind == 'l':
                f = font(SERIF_I, int(84 * TS))
                d.text(((OW - d.textlength(txt, font=f)) / 2, 0), txt, font=f, fill=INK + (255,))
            else:
                spaced(d, int(18 * TS), txt, font(SANS_R, int(21 * TS)), (90, 86, 80, 255), 5 * TS)
            if a < 1:
                al = lay.getchannel('A').point(lambda v: int(v * a))
                lay.putalpha(al)
            layer.alpha_composite(lay, (0, int(y + (1 - u) * 22)))
        y += h
    return layer


# ------------------------------------------------------------------ timeline
X = 0.6  # crossfade length


def build_timeline(rects):
    def detail(key, frac, z=1.75):
        x0, y0, x1, y1 = rects[key]
        return z, x0 + (x1 - x0) * frac[0], y0 + (y1 - y0) * frac[1]

    shots = []
    # 1. hook + Convergence: empty wall, painting appears, then push into the texture
    k, _, _, _, fr = PAINTINGS[0]
    dz, dx, dy = detail(k, fr)
    shots.append(dict(room=k, start=0.0, end=6.3 + X, keys=[
        (0.0, 1.00, 540, WIDE_CY, 'lin'), (5.0, 1.07, 540, WIDE_CY - 25, 'lin'), (6.9, dz, dx, dy, 'inout')]))
    starts = [6.3, 12.6, 18.9]
    for (k, _, _, _, fr), s in zip(PAINTINGS[1:], starts):
        dz, dx, dy = detail(k, fr)
        ez, ex, ey = detail(k, (1 - fr[0], fr[1] + 0.12), 1.65)
        shots.append(dict(room=k, start=s, end=s + 6.3 + X, keys=[
            (s, dz * 1.04, dx, dy, 'lin'), (s + 0.5, dz, dx, dy, 'lin'),
            (s + 2.6, 1.02, 540, WIDE_CY, 'inout'), (s + 5.0, 1.07, 540, WIDE_CY - 25, 'lin'),
            (s + 6.6, ez, ex, ey, 'inout')]))
    s = 25.2
    shots.append(dict(room='collection', start=s, end=DUR + 0.1, keys=[
        (s, 1.45, 540, 980, 'lin'), (s + 2.2, 1.0, 540, WIDE_CY, 'inout'), (DUR, 1.03, 540, WIDE_CY - 10, 'lin')]))

    texts = [((HOOK[0], (110, 104, 96), HOOK[1], None), 0.25, 2.45)]
    for (k, col, kick, lines, _), s in zip(PAINTINGS, [0.0] + starts):
        t_in = 3.1 if s == 0 else s + 2.0
        texts.append(((kick, col, lines, None), t_in, (5.0 if s == 0 else s + 5.0)))
    texts.append(((END[0], (110, 104, 96), END[1], END[2]), 26.6, None))
    return shots, texts


def render_frame(t, rooms, shots, texts):
    frame = None
    for sh in shots:
        if not (sh['start'] <= t < sh['end']):
            continue
        z, cx, cy = cam_at(sh['keys'], t)
        img = view(rooms[sh['room']], z, cx, cy)
        if sh['room'] == 'convergence' and t < 2.6:
            reveal = ease((t - 1.55) / 0.9, 'inout')
            if reveal < 1:
                empty = view(rooms['convergence_empty'], z, cx, cy)
                img = Image.blend(empty, img, reveal)
        if frame is None:
            frame = img
        else:  # crossfade into the incoming shot
            frame = Image.blend(frame, img, ease((t - sh['start']) / X, 'inout'))
    frame = frame.convert('RGBA')
    for block, t_in, t_out in texts:
        if t_in - 0.05 <= t and (t_out is None or t < t_out + 0.5):
            frame.alpha_composite(text_layer(block, t, t_in, t_out))
    return frame.convert('RGB')


# ------------------------------------------------------------------ finishing
def finisher():
    yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32)
    r = ((xx / OW - 0.5) ** 2 + (yy / OH - 0.5) ** 2 * 0.6)
    vig = (1 - 0.18 * np.clip(r - 0.08, 0, None))[..., None]
    rng = np.random.default_rng(5)
    grains = [rng.normal(0, 2.0, (OH, OW, 1)).astype(np.float32) for _ in range(6)]

    def fin(img, i):
        a = np.asarray(img, np.float32) * vig + grains[i % 6]
        return np.clip(a + 0.5, 0, 255).astype(np.uint8)
    return fin


# ------------------------------------------------------------------ music
def music(path, sr=44100):
    """Calm ambient bed: warm pad, soft bell arpeggio, gentle swells into each transition."""
    n = int(sr * (DUR + 0.5))
    t = np.arange(n) / sr
    rng = np.random.default_rng(3)
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    # Fmaj9 - Am7 - Dm9 - Bbmaj9, 3 s each
    chords = [[53, 60, 64, 67, 69], [57, 60, 64, 67, 71], [50, 57, 60, 64, 65], [46, 53, 57, 60, 62]]
    pad = np.zeros(n)
    bells = np.zeros(n)
    bass = np.zeros(n)
    beat = 0.75
    for ci in range(int(DUR / 3) + 1):
        ch = chords[ci % 4]
        s0 = ci * 3.0
        seg = (t >= s0 - 0.6) & (t < s0 + 3.8)
        tt = t[seg] - s0
        env = np.clip((tt + 0.6) / 1.2, 0, 1) * np.clip((3.8 - tt) / 1.2, 0, 1)
        for m in ch[1:]:
            for det in (-0.07, 0.0, 0.07):
                f = hz(m) * 2 ** (det / 12)
                ph = rng.random() * 6.28
                pad[seg] += env * (np.sin(2 * np.pi * f * tt + ph) + 0.25 * np.sin(4 * np.pi * f * tt + ph)) / 3
        bass[seg] += env * np.sin(2 * np.pi * hz(ch[0] - 12) * tt) * 1.2
        pattern = [ch[1] + 12, ch[3] + 12, ch[2] + 12, ch[4] + 12]
        for bi, m in enumerate(pattern):
            st = s0 + bi * beat
            if st >= DUR - 1.5:
                continue
            i0 = int(st * sr)
            L = int(2.5 * sr)
            tb = np.arange(min(L, n - i0)) / sr
            f = hz(m)
            vel = 0.55 + 0.25 * rng.random()
            tone = (np.sin(2 * np.pi * f * tb) + 0.30 * np.sin(2 * np.pi * 2 * f * tb) * np.exp(-tb * 3)
                    + 0.12 * np.sin(2 * np.pi * 3.01 * f * tb) * np.exp(-tb * 6))
            bells[i0:i0 + len(tb)] += vel * tone * np.exp(-tb * 1.8) * np.clip(tb / 0.004, 0, 1)
    # a brighter chime when the first painting appears
    i0 = int(1.6 * sr)
    tb = np.arange(int(3 * sr)) / sr
    for m in (72, 76, 79, 84):
        bells[i0:i0 + len(tb)] += 0.5 * np.sin(2 * np.pi * hz(m) * tb) * np.exp(-tb * 1.3)
    # filtered noise swells into each crossfade
    sw = np.zeros(n)
    sos = butter(2, [300, 2500], btype='band', fs=sr, output='sos')
    nz = sosfilt(sos, rng.standard_normal(n))
    for c in (6.6, 12.9, 19.2, 25.5):
        sw += nz * np.exp(-((t - c) / 0.35) ** 2) * 0.6
    lp = butter(2, 1800, fs=sr, output='sos')
    pad = sosfilt(lp, pad)
    dry = 0.20 * pad + 0.16 * bells + 0.22 * bass + 0.10 * sw
    # stereo reverb from decaying noise impulses
    ir_t = np.arange(int(2.8 * sr)) / sr
    out = []
    for ch_seed in (11, 12):
        ir = np.random.default_rng(ch_seed).standard_normal(len(ir_t)) * np.exp(-ir_t * 2.4)
        ir = sosfilt(butter(1, 4000, fs=sr, output='sos'), ir)
        ir /= np.sqrt((ir ** 2).sum())
        wet = fftconvolve(dry, ir)[:n]
        out.append(0.62 * dry + 0.55 * wet)
    st = np.stack(out, 1)
    fade = np.clip(t / 0.4, 0, 1) * np.clip((DUR - t) / 2.0, 0, 1)
    st *= fade[:, None]
    st /= np.abs(st).max() / 0.6   # peak ~ -4.4 dBFS
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((st * 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ main
def main():
    os.makedirs(OUT, exist_ok=True)
    rooms, rects = load_rooms()
    shots, texts = build_timeline(rects)
    fin = finisher()
    tag = 'feed-4x5' if FEED else 'reels-9x16'
    if '--preview' in sys.argv:
        for ts in [float(a) for a in sys.argv[sys.argv.index('--preview') + 1:]] or [1.0, 4.0, 10.0, 28.0]:
            Image.fromarray(fin(render_frame(ts, rooms, shots, texts), 0)).save(
                os.path.join(CACHE, f'prev_{tag}_{ts:05.2f}.png'))
        return
    wav = os.path.join(CACHE, 'music.wav')
    music(wav)
    silent = os.path.join(OUT, f'ark_artworks_ad_{tag}_no-music.mp4')
    final = os.path.join(OUT, f'ark_artworks_ad_{tag}.mp4')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{OW}x{OH}',
           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-profile:v', 'high',
           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nf = int(DUR * FPS)
    for i in range(nf):
        t = i / FPS
        p.stdin.write(fin(render_frame(t, rooms, shots, texts), i).tobytes())
        if i % 60 == 0:
            print(f'{tag}: frame {i}/{nf}', flush=True)
    p.stdin.close()
    p.wait()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', silent, '-i', wav, '-c:v', 'copy', '-c:a', 'aac',
                    '-b:a', '192k', '-shortest', '-movflags', '+faststart', final], check=True)
    cover = render_frame(2.4, rooms, shots, texts)
    Image.fromarray(fin(cover, 0)).save(os.path.join(OUT, f'cover_{tag}.jpg'), quality=92)
    print('wrote', final)


if __name__ == '__main__':
    main()
