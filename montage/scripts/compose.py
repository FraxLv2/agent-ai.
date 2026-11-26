# Compositeur final : assemble intro 3D, gameplay, Freeze Time, balle 3D ; effets synchronisés ; étalonnage ; encodage
# usage: python3 compose.py ROOT OUT.mp4 [--preview a,b] [--stills t1,t2,...]
import sys, os, math, subprocess, glob
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
import timeline as T

ROOT, OUTF = sys.argv[1], sys.argv[2]
PREVIEW = None; STILLS = None
if '--preview' in sys.argv:
    PREVIEW = [float(x) for x in sys.argv[sys.argv.index('--preview') + 1].split(',')]
if '--stills' in sys.argv:
    STILLS = [float(x) for x in sys.argv[sys.argv.index('--stills') + 1].split(',')]
W, H, AH = 1920, 1080, 884
TOP = (H - AH) // 2
FPS = T.FPS
WK = os.path.join(ROOT, 'work'); RD = os.path.join(ROOT, 'renders')
rng = np.random.default_rng(11)

# ---------------- chargement source (60 fps interpolé) + effacement HUD ----------------
mask = cv2.imread(os.path.join(WK, 'hudmask.png'), 0)
mroi = mask[430:510]
cap = cv2.VideoCapture(os.path.join(WK, 'src60.mp4'))
SRC = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    t = len(SRC) / FPS
    if any(a <= t < b for a, b in T.HUD_SEGS):
        f[430:510] = cv2.inpaint(f[430:510], mroi, 3, cv2.INPAINT_TELEA)
    SRC.append(f)
NSRC = len(SRC)
print('source frames', NSRC)


def seq(d):
    fs = sorted(glob.glob(os.path.join(RD, d, '*.png')))
    return fs

SEQ = {k: seq(d) for k, d in [('intro', 'intro_60'), ('freeze', 'freeze_60'), ('bullet', 'bullet'), ('sniper', 'sniper')]}
SLOW = sorted(glob.glob(os.path.join(WK, 'slow_sn', '*.png')))
TRANS = {c: sorted(glob.glob(os.path.join(RD, 'trans', f'{c:.2f}', '*.png'))) for c, _ in T.TRANS3D}
_dz = np.load(os.path.join(WK, 'depth_seq.npz'))
DEPTH = dict(zip(_dz['idx'].tolist(), _dz['d']))
print('slow', len(SLOW), {c: len(v) for c, v in TRANS.items()}, 'depth', len(DEPTH))
print({k: len(v) for k, v in SEQ.items()})


def up(img):
    """mise à l'échelle 1108x510 -> 1920x884 (Lanczos + accentuation douce)"""
    x = cv2.resize(img, (W, AH), interpolation=cv2.INTER_LANCZOS4).astype(np.float32) / 255
    b = cv2.GaussianBlur(x, (0, 0), 1.1)
    return np.clip(x * 1.4 - b * 0.4, 0, 1)


def load_seq(kind, tau, dur):
    fs = SEQ[kind]
    if not fs:
        return None
    i = min(len(fs) - 1, int(tau / dur * len(fs)))
    im = cv2.imread(fs[i])
    if im.shape[1] != W or im.shape[0] != AH:
        im = cv2.resize(im, (W, AH), interpolation=cv2.INTER_LANCZOS4)
    return im.astype(np.float32) / 255


# ---------------- caméra 3D sur le gameplay : parallaxe par profondeur ----------------
GX, GY = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(AH, dtype=np.float32))
TOPMASK = np.clip((GY - 30) / 40, 0, 1)   # le bandeau HUD du haut ne bouge pas

def parallax(img, x):
    for a, b, amp, sgn in T.PARALLAX:
        if a <= x < b:
            break
    else:
        return img
    d = DEPTH.get(int(round(x * FPS)))
    if d is None:
        return img
    u = (x - a) / (b - a)
    fade = min(1.0, u / 0.12, (1 - u) / 0.12)        # retour à la vue d'origine aux bords du plan
    dx = amp * sgn * (2 * u - 1) * fade
    dy = -amp * 0.3 * math.sin(math.pi * u) * fade
    z = 1 + 0.045 * fade
    dd = cv2.resize(d.astype(np.float32), (W, AH), interpolation=cv2.INTER_LINEAR)
    dd = (dd - np.median(dd)) * TOPMASK
    mx = (GX - W / 2) / z + W / 2 - dd * dx
    my = (GY - AH / 2) / z + AH / 2 - dd * dy
    return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def trans_frame(x):
    for c, _ in T.TRANS3D:
        if c - T.TRANS_HALF <= x < c + T.TRANS_HALF and TRANS[c]:
            i = min(len(TRANS[c]) - 1, int((x - (c - T.TRANS_HALF)) * FPS))
            im = cv2.imread(TRANS[c][i])
            return cv2.resize(im, (W, AH), interpolation=cv2.INTER_LANCZOS4).astype(np.float32) / 255
    return None

SLOWMASK = mask[430:510]
SLOWB = sorted(glob.glob(os.path.join(WK, 'slow_sn_blend', '*.png')))
def slow_frame(tau, dur):
    # 25 % du temps : montée de la lunette à ~0,5x (fondu) ; 75 % : ralenti extrême ~0,09x sur la visée (interpolé)
    u = tau / dur
    src = 9.40 + (0.17 * u / 0.25 if u < 0.25 else 0.17 + 0.09 * (u - 0.25) / 0.75)
    i = min(len(SLOW) - 1, int((src - 9.40) * 300))
    f = cv2.imread((SLOWB if src < 9.56 else SLOW)[i])
    f[430:510] = cv2.inpaint(f[430:510], SLOWMASK, 3, cv2.INPAINT_TELEA)
    return up(f)


# ---------------- rampes de vitesse ----------------
def remap(x):
    for c, w, k in T.RAMPS:
        if abs(x - c) < w:
            u = (x - c) / w
            return c + w * (u - k / math.pi * math.sin(math.pi * u)), 1 - k * math.cos(math.pi * u)
    return x, 1.0


def src_frame(ts, lo, hi):
    fi = min(max(ts, lo), hi - 1e-3) * FPS
    i0 = int(fi); a = fi - i0
    i0 = min(i0, NSRC - 1); i1 = min(i0 + 1, NSRC - 1, int(hi * FPS) - 1 if hi * FPS - 1 > i0 else i0)
    if a < 0.04 or i1 == i0:
        return SRC[i0]
    return cv2.addWeighted(SRC[i0], 1 - a, SRC[i1], a, 0)


def src_image(x, lo, hi):
    ts, speed = remap(x)
    if speed > 1.25:  # flou de mouvement sur les accélérations
        d = 0.45 / FPS
        fr = [src_frame(remap(x + o)[0], lo, hi).astype(np.float32) for o in (-d, 0, d)]
        return up((sum(fr) / 3).astype(np.uint8)), speed
    return up(src_frame(ts, lo, hi)), speed


# ---------------- outils d'effets ----------------
yy, xx = np.mgrid[0:AH, 0:W].astype(np.float32)
rr = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - AH / 2) / (AH / 2)) ** 2
VIGN = (1 - 0.30 * np.clip(rr, 0, 2) ** 1.2)[..., None].astype(np.float32)
GRAIN = [cv2.resize(rng.normal(0, 0.016, (AH // 2, W // 2)).astype(np.float32), (W, AH))[..., None] for _ in range(8)]
LEAK = np.zeros((AH, W, 3), np.float32)
g = np.exp(-(((xx - W * 0.85) / (W * 0.35)) ** 2 + ((yy - AH * 0.2) / (AH * 0.6)) ** 2))
LEAK[..., 0] = g * 0.15; LEAK[..., 1] = g * 0.45; LEAK[..., 2] = g * 1.0


def affine(img, z=1.0, dx=0.0, dy=0.0, rot=0.0):
    if abs(z - 1) < 1e-4 and abs(dx) < 0.3 and abs(dy) < 0.3 and abs(rot) < 1e-3:
        return img
    M = cv2.getRotationMatrix2D((W / 2, AH / 2), rot, z)
    M[0, 2] += dx; M[1, 2] += dy
    return cv2.warpAffine(img, M, (W, AH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def chroma(img, px):
    if px < 0.4:
        return img
    out = img.copy()
    for ch, s in ((2, px), (0, -px)):
        M = np.float32([[1 + s / W, 0, -s / 2 + s], [0, 1, 0]])
        out[..., ch] = cv2.warpAffine(img[..., ch], M, (W, AH), borderMode=cv2.BORDER_REFLECT)
    return out


def dirblur(img, L):
    L = int(L)
    if L < 3:
        return img
    k = np.ones((1, L), np.float32) / L
    return cv2.filter2D(img, -1, k, borderType=cv2.BORDER_REFLECT)


def zoomblur(img, amt):
    if amt < 0.004:
        return img
    acc = img.copy(); n = 5
    for i in range(1, n):
        acc += affine(img, 1 + amt * i / n)
    return acc / n


def bloom(img, strength=0.24, thr=0.86):
    s = cv2.resize(img, (W // 4, AH // 4), interpolation=cv2.INTER_AREA)
    b = np.clip(s - thr, 0, 1)
    b = cv2.GaussianBlur(b, (0, 0), 7) + cv2.GaussianBlur(b, (0, 0), 22)
    b = cv2.resize(b, (W, AH), interpolation=cv2.INTER_LINEAR)
    b *= np.array([0.8, 0.95, 1.15], np.float32)  # halo chaud
    return img + b * strength


def grade(img, sat=1.12, cool=0.0, contrast=0.32):
    x = np.clip(img, 0, 1)
    x = x + contrast * (x * x * (3 - 2 * x) - x)
    L = (0.114 * x[..., 0] + 0.587 * x[..., 1] + 0.299 * x[..., 2])[..., None]
    sh = (1 - L) ** 2; hi = L ** 2
    # teal dans les ombres, orangé dans les hautes lumières (BGR)
    x = x + sh * np.array([0.045, 0.018, -0.030], np.float32) + hi * np.array([-0.045, 0.012, 0.050], np.float32)
    x = L + (x - L) * sat
    if cool:
        x = x * (1 - cool) + (L * np.array([1.12, 1.0, 0.86], np.float32)) * cool
    return x


# ---------------- particules 2D (étincelles sur les kills, poussière lumineuse) ----------------
SPARKS = {}
def sparks_layer(age, seed):
    if seed not in SPARKS:
        r = np.random.default_rng(seed)
        n = 34
        ang = r.uniform(0, 2 * np.pi, n); sp = r.uniform(350, 1400, n)
        SPARKS[seed] = (np.stack([np.cos(ang) * sp, np.sin(ang) * sp - 250], 1), r.uniform(0.25, 0.6, n),
                        np.array([W / 2, AH / 2 - 20]) + r.normal(0, 18, (n, 2)))
    v, life, p0 = SPARKS[seed]
    lay = np.zeros((AH, W, 3), np.float32)
    for i in range(len(v)):
        if age > life[i]:
            continue
        a = 1 - age / life[i]
        p = p0[i] + v[i] * age + np.array([0, 900]) * age * age / 2
        q = p - (v[i] + np.array([0, 900]) * age) * 0.018
        cv2.line(lay, tuple(int(c) for c in q), tuple(int(c) for c in p), (0.35 * a, 0.75 * a, 1.0 * a), 2, cv2.LINE_AA)
    return lay + cv2.GaussianBlur(lay, (0, 0), 5) * 2.0


DUST = None
def dust_layer(t, strength):
    global DUST
    if DUST is None:
        r = np.random.default_rng(5)
        DUST = (r.uniform(0, W, 70), r.uniform(0, AH, 70), r.uniform(-25, 25, 70), r.uniform(-30, -5, 70), r.uniform(2, 7, 70), r.uniform(0, 6.28, 70))
    x0, y0, vx, vy, rad, ph = DUST
    sm = np.zeros((AH // 4, W // 4, 3), np.float32)
    for i in range(len(x0)):
        x = (x0[i] + vx[i] * t) % W; y = (y0[i] + vy[i] * t) % AH
        a = 0.5 + 0.5 * math.sin(t * 1.7 + ph[i])
        cv2.circle(sm, (int(x / 4), int(y / 4)), max(1, int(rad[i] / 2)), (0.55 * a, 0.8 * a, 1.0 * a), -1, cv2.LINE_AA)
    sm = cv2.GaussianBlur(sm, (0, 0), 1.5)
    return cv2.resize(sm, (W, AH)) * strength


# ---------------- titres ----------------
FBLACK = '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf'
FLIGHT = '/usr/share/fonts/opentype/inter/InterDisplay-Light.otf'
FJP = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'


def text_layer(lines, alpha, spread=0.0, scale=1.0, y=0.5):
    """lines: [(texte, police, taille, couleur RGB, tracking)] ; renvoie une couche RGBA flottante (W x AH)"""
    im = Image.new('RGBA', (W, AH), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    total_h = sum(int(s * scale * 1.25) for _, _, s, _, _ in lines)
    cy = int(AH * y - total_h / 2)
    for txt, font, size, col, track in lines:
        size = int(size * scale)
        segs = []
        for ch in txt:
            fp = FJP if ord(ch) > 0x2E80 else font
            segs.append((ch, ImageFont.truetype(fp, size)))
        tr = track * size + spread * size
        widths = [dr.textlength(ch, font=f) for ch, f in segs]
        tw = sum(widths) + tr * (len(segs) - 1)
        x = (W - tw) / 2
        for (ch, f), wdt in zip(segs, widths):
            dr.text((x, cy), ch, font=f, fill=(*col, int(255 * alpha)))
            x += wdt + tr
        cy += int(size * 1.25)
    a = np.asarray(im).astype(np.float32) / 255
    rgb = a[..., :3][..., ::-1].copy(); al = a[..., 3:4]
    glow = cv2.GaussianBlur(rgb * al, (0, 0), 14) * 0.9
    shadow = np.clip(cv2.GaussianBlur(al, (0, 0), 10)[..., None] * 1.6, 0, 1) if al.ndim == 2 else np.clip(cv2.GaussianBlur(al[..., 0], (0, 0), 10)[..., None] * 1.6, 0, 1)
    return rgb, al, glow, shadow


TITLE_CACHE = {}
BAND = np.exp(-((yy - AH * 0.5) / (AH * 0.16)) ** 2)[..., None].astype(np.float32)
def apply_title(img, tau, kind):
    if kind == 'intro':
        t0 = 2.1
        if tau < t0:
            return img
        u = min(1, (tau - t0) / 0.6); e = 1 - (1 - u) ** 3
        fade = 1.0 if tau < T.INTRO - 0.12 else max(0, (T.INTRO - tau) / 0.12)
        key = ('i', round(e, 2))
        if key not in TITLE_CACHE:
            TITLE_CACHE[key] = text_layer([('ジPM | NEYMAR', FBLACK, 112, (255, 255, 255), 0.04),
                                          ('CALL OF DUTY MOBILE  •  YACHT  /  CRASH', FLIGHT, 30, (255, 214, 170), 0.45)],
                                         1.0, spread=0.25 * (1 - e), scale=1.0 + 0.06 * (1 - e), y=0.5)
        rgb, al, glow, shadow = TITLE_CACHE[key]
        a = e * fade
        img = img * (1 - BAND * 0.55 * a) * (1 - shadow * 0.6 * a)
        return img * (1 - al * a) + rgb * al * a + glow * a * 0.5
    if kind == 'outro':
        u = min(1, tau / 0.5); e = 1 - (1 - u) ** 3
        key = ('o', round(e, 2))
        if key not in TITLE_CACHE:
            TITLE_CACHE[key] = text_layer([('GG', FBLACK, 150, (255, 255, 255), 0.12), ('ジPM | NEYMAR', FLIGHT, 34, (255, 214, 170), 0.4)],
                                         1.0, spread=0.2 * (1 - e), scale=1.0 + 0.05 * (1 - e), y=0.5)
        rgb, al, glow, shadow = TITLE_CACHE[key]
        a = e * max(0, min(1, (T.OUTRO - tau) / 0.35))
        return img * (1 - al * a) + rgb * al * a + glow * a * 0.5
    return img


# ---------------- événements (temps de sortie) ----------------
starts, TOTAL = T.seg_starts()

def src_to_out(ts):
    for t0, (kind, dur, p) in starts:
        if kind == 'src' and p['t0'] <= ts < p['t1']:
            return t0 + ts - p['t0']
    return None

BOUNDS = {s[0]: t0 for t0, s in starts}
seg_t = {}
for t0, s in starts:
    seg_t.setdefault(s[0], []).append(t0)
EV = []  # (temps, type, amplitude, montée, descente)
for k in T.KILLS:
    o = src_to_out(k)
    if o is not None:
        EV += [(o, 'flash', 0.22, 0.0, 0.10), (o, 'shake', 14, 0.0, 0.28), (o, 'chroma', 7, 0.0, 0.2), (o, 'zoom', 0.045, 0.03, 0.25), (o, 'sparks', 1, 0, 0.6)]
for c in T.CUTS:
    o = src_to_out(c)
    if o is not None:
        if any(abs(c - tc) < 0.05 for tc, _ in T.TRANS3D):
            EV += [(o, 'flash', 0.12, 0.03, 0.1), (o, 'leak', 0.6, 0.15, 0.3)]
            continue
        EV += [(o, 'flash', 0.28 if c != 15.6 else 0.0, 0.05, 0.12), (o, 'dirblur', 70, 0.08, 0.10), (o, 'zoom', 0.07, 0.08, 0.12), (o, 'chroma', 10, 0.06, 0.12), (o, 'leak', 0.8, 0.1, 0.3)]
# transitions entre segments
tI = seg_t['src'][0]; tF = seg_t['freeze'][0]; tF2 = seg_t['src'][2]; tB = seg_t['bullet'][0]; tB2 = seg_t['src'][3]; tO = seg_t['outro'][0]
tS = seg_t['slow'][0]; tN = seg_t['sniper'][0]; tN2 = seg_t['src'][1]
SN_IMPACT = tN + (T.SNIPER_N - 15) / FPS
EV += [(tS, 'flash', 0.25, 0.04, 0.2), (tS, 'chroma', 6, 0.04, 0.25),
       (tN, 'flash', 0.7, 0.06, 0.3), (tN, 'chroma', 12, 0.05, 0.3), (tN, 'zoomblur', 0.05, 0.08, 0.15),
       (SN_IMPACT, 'flash', 0.35, 0.0, 0.18), (SN_IMPACT, 'shake', 18, 0, 0.35), (SN_IMPACT, 'chroma', 10, 0, 0.3),
       (tN2, 'flash', 0.95, 0.15, 0.25), (tN2, 'shake', 16, 0, 0.3), (tN2, 'chroma', 12, 0, 0.25)]
EV += [(tI, 'flash', 0.9, 0.12, 0.25), (tI, 'zoomblur', 0.12, 0.15, 0.2), (tI, 'shake', 16, 0, 0.3), (tI, 'leak', 1.0, 0.1, 0.5),
       (tF, 'flash', 0.55, 0.06, 0.25), (tF, 'chroma', 12, 0.05, 0.3), (tF, 'zoomblur', 0.06, 0.1, 0.15),
       (tF2, 'flash', 0.4, 0.06, 0.15), (tF2, 'chroma', 9, 0.06, 0.2), (tF2, 'zoom', 0.05, 0.1, 0.2),
       (tB, 'flash', 0.6, 0.05, 0.3), (tB, 'chroma', 10, 0.05, 0.25),
       (tB2, 'flash', 1.0, 0.12, 0.3), (tB2, 'shake', 22, 0, 0.35), (tB2, 'chroma', 14, 0, 0.3), (tB2, 'zoom', 0.08, 0, 0.3)]
# pulsations sur le tempo (zoom léger ; plus fort sur les temps 1)
BEATS = []
k = 0
while T.BEAT0 + k * T.BEAT < T.SRC_END:
    o = src_to_out(T.BEAT0 + k * T.BEAT)
    if o is not None:
        EV.append((o, 'zoom', 0.022 if k % 4 == 0 else 0.009, 0.0, 0.14))
    k += 1


def ev_val(t, typ):
    v = 0.0; ages = []
    for te, ty, amp, rise, dec in EV:
        if ty != typ:
            continue
        d = t - te
        if -rise <= d < 0 and rise > 0:
            v += amp * (1 + d / rise) ** 2
        elif 0 <= d < dec:
            v += amp * (1 - d / dec) ** 2 if ty != 'sparks' else 0
            if ty == 'sparks':
                ages.append((d, int(te * 1000)))
    return (v, ages) if typ == 'sparks' else v


# ---------------- rendu image par image ----------------
def frame_at(t):
    for t0, (kind, dur, p) in reversed(starts):
        if t >= t0:
            break
    tau = t - t0
    sat, cool, dust = 1.12, 0.0, 0.0
    if kind == 'intro':
        img = load_seq('intro', tau, dur)
        if img is None:
            img = up(SRC[0])
        img = img * min(1, tau / 0.6)
        dust = 0.5
    elif kind == 'src':
        x = p['t0'] + tau
        img = trans_frame(x)
        if img is None:
            img, speed = src_image(x, p['t0'], p['t1'])
            img = parallax(img, x)
        if x < 5.0:
            dust = 0.35
    elif kind == 'slow':   # super ralenti pendant la visée : lente poussée vers la lunette
        u = tau / dur
        img = affine(slow_frame(tau, dur), 1 + 0.07 * u * u)
        sat = 1.0; cool = 0.15 * u
    elif kind == 'sniper':
        img = load_seq('sniper', tau, dur)
        if img is None:
            img = up(SRC[int(T.SNIPER_B * FPS)])
        sat = 1.15
    elif kind == 'freeze':
        img = load_seq('freeze', tau, dur)
        if img is None:
            img = up(SRC[int(T.FREEZE_AT * FPS)])
        u = tau / dur
        cool = 0.33 * min(1, tau / 0.25) * min(1, (dur - tau) / 0.3)  # temps figé : désaturé, froid
        sat = 1.12 - 0.6 * cool
    elif kind == 'bullet':
        img = load_seq('bullet', tau, dur)
        if img is None:
            img = up(SRC[int(T.BULLET_AT * FPS)])
        sat = 1.2
    else:  # outro
        last = up(SRC[NSRC - 1])
        img = affine(last, 1 + 0.04 * tau / dur)
        img = img * max(0, 1 - tau / 0.5) ** 1.5
        cool = 0.3

    # effets synchronisés
    z = 1 + ev_val(t, 'zoom')
    sh = ev_val(t, 'shake')
    dx = dy = rot = 0.0
    if sh > 0.3:
        r = np.random.default_rng(int(t * FPS))
        dx, dy = r.normal(0, sh, 2); rot = r.normal(0, sh * 0.04)
    img = affine(img, z, dx, dy, rot)
    img = zoomblur(img, ev_val(t, 'zoomblur'))
    img = dirblur(img, ev_val(t, 'dirblur'))
    img = chroma(img, ev_val(t, 'chroma'))
    sv, ages = ev_val(t, 'sparks')
    for age, seed in ages:
        img = img + sparks_layer(age, seed)
    if dust:
        img = img + dust_layer(t, dust)
    lk = ev_val(t, 'leak')
    if lk > 0.01:
        img = img + LEAK * min(lk, 1.2)
    img = bloom(img)
    img = grade(img, sat=sat, cool=cool)
    img = img * VIGN
    fl = min(1.0, ev_val(t, 'flash'))
    if fl > 0.005:
        img = img * (1 - fl) + fl
    img = apply_title(img, tau, kind)
    img = img + GRAIN[int(t * FPS) % len(GRAIN)]
    canvas = np.zeros((H, W, 3), np.uint8)
    canvas[TOP:TOP + AH] = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    return canvas


if STILLS:
    os.makedirs(os.path.join(WK, 'stills'), exist_ok=True)
    for t in STILLS:
        cv2.imwrite(os.path.join(WK, 'stills', f'{t:06.2f}.jpg'), frame_at(t), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print('stills ok'); sys.exit()

a, b = (PREVIEW if PREVIEW else (0, TOTAL))
nf = int(round((b - a) * FPS))
aud = os.path.join(WK, 'final_audio.wav')
cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
       '-ss', str(a), '-t', str(b - a), '-i', aud,
       '-c:v', 'libx264', '-preset', 'slow' if not PREVIEW else 'veryfast', '-crf', '17', '-maxrate', '18M', '-bufsize', '36M',
       '-profile:v', 'high', '-level', '4.2', '-pix_fmt', 'yuv420p',
       '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
       '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', '-shortest', OUTF]
pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for i in range(nf):
    t = a + i / FPS
    pr.stdin.write(frame_at(t).tobytes())
    if i % 120 == 0:
        print(f'{t:6.2f}s / {b:.2f}', flush=True)
pr.stdin.close(); pr.wait()
print('DONE', OUTF, nf, 'frames')
