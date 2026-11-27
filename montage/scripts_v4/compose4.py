# Compositeur v4 (style Kaiser) : transitions uniques à chaque coupe, inserts 3D Blender raccordés en match cut,
# effets manga (impact frames, lignes de vitesse), traînées lumineuses, rayons volumétriques, étalonnage par scène.
# usage: python3 compose4.py ROOT OUT.mp4 [--preview a,b] [--stills t1,t2,...]
import sys, os, math, subprocess, glob
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
import timeline4 as T

ROOT, OUTF = sys.argv[1], sys.argv[2]
PREVIEW = STILLS = None
if '--preview' in sys.argv:
    PREVIEW = [float(x) for x in sys.argv[sys.argv.index('--preview') + 1].split(',')]
if '--stills' in sys.argv:
    STILLS = [float(x) for x in sys.argv[sys.argv.index('--stills') + 1].split(',')]
W, H, FPS = 1920, 1080, T.FPS
RD = os.path.join(ROOT, 'r')
CX0, CW = 101, 906
SRC_W, SRC_H = 1108, 510

SRC = np.load(os.path.join(ROOT, 'src60.npy'), mmap_mode='r')
NSRC = int(open(os.path.join(ROOT, 'src60.count')).read())
_dz = np.load(os.path.join(ROOT, 'depth4.npz')); DEPTH = dict(zip(_dz['idx'].tolist(), _dz['d']))
seq = lambda d: sorted(glob.glob(os.path.join(RD, d, '*.png')))
SEQ = {'frz': seq('frz_60'), 'wpn': seq('wpn_60'), 'rep': seq('rep_60'), 'fly': seq('fly'), 'flt': seq('flt')}
print('frames', NSRC, {k: len(v) for k, v in SEQ.items()}, flush=True)


def depth_at(x):
    i = int(round(x * FPS)); i -= i % 2
    for k in (i, i - 2, i + 2):
        if k in DEPTH:
            return cv2.resize(DEPTH[k].astype(np.float32), (SRC_W, SRC_H))
    return None


def to169(img_bgr_u8):
    c = img_bgr_u8[:, CX0:CX0 + CW]
    x = cv2.resize(c, (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32) / 255
    b = cv2.GaussianBlur(x, (0, 0), 1.3)
    return np.clip(x * 1.4 - b * 0.4, 0, 1)


def render169(path):
    im = cv2.imread(path)
    h, w = im.shape[:2]
    if abs(w / h - 16 / 9) > 0.02:
        cw = int(round(h * 16 / 9)); x0 = (w - cw) // 2; im = im[:, x0:x0 + cw]
    if im.shape[1] != W:
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_LANCZOS4)
    return im.astype(np.float32) / 255


def seq_frame(kind, u):
    fs = SEQ[kind]
    if not fs:
        return None
    return render169(fs[min(len(fs) - 1, max(0, int(u * len(fs))))])


# ---------------- vitesse (speed ramping) ----------------
def remap(x):
    for c, w, k in T.RAMPS:
        if abs(x - c) < w:
            u = (x - c) / w
            return c + w * (u - k / math.pi * math.sin(math.pi * u)), 1 - k * math.cos(math.pi * u)
    return x, 1.0


def src_raw(ts):
    fi = min(max(ts, 0), (NSRC - 1) / FPS) * FPS
    i0 = int(fi); a = fi - i0; i1 = min(i0 + 1, NSRC - 1)
    if a < 0.06 or a > 0.94:
        return np.asarray(SRC[min(int(round(fi)), NSRC - 1)])
    return cv2.addWeighted(np.asarray(SRC[i0]), 1 - a, np.asarray(SRC[i1]), a, 0)


GX, GY = np.meshgrid(np.arange(SRC_W, dtype=np.float32), np.arange(SRC_H, dtype=np.float32))


def parallax_dof(img, x):
    for a, b, amp, sgn in T.PARALLAX:
        if a <= x < b:
            break
    else:
        return img
    dd = depth_at(x)
    if dd is None:
        return img
    u = (x - a) / max(b - a, 1e-3)
    fade = min(1.0, u / 0.12, (1 - u) / 0.12)
    dc = dd - np.median(dd)
    dx = amp * sgn * (2 * u - 1) * fade; dy = -amp * 0.3 * math.sin(math.pi * u) * fade
    z = 1 + 0.05 * fade
    mx = (GX - SRC_W / 2) / z + SRC_W / 2 - dc * dx
    my = (GY - SRC_H / 2) / z + SRC_H / 2 - dc * dy
    out = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    far = np.clip((0.45 - cv2.remap(dd, mx, my, cv2.INTER_LINEAR)) / 0.35, 0, 1)[..., None] * 0.9
    blur = cv2.GaussianBlur(out, (0, 0), 2.4)
    return (out * (1 - far) + blur * far).astype(np.uint8)


def src_image(x):
    ts, speed = remap(x)
    if speed > 1.25:
        d = 0.5 / FPS
        f = np.mean([src_raw(remap(x + o)[0]).astype(np.float32) for o in (-d, -d / 2, 0, d / 2, d)], axis=0).astype(np.uint8)
    else:
        f = src_raw(ts)
    return to169(parallax_dof(f, x))


# ---------------- outils d'image ----------------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
RR = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
RPIX = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2)
ANG = np.arctan2(yy - H / 2, xx - W / 2)
VIGN = (1 - 0.36 * np.clip(RR / 1.4, 0, 1) ** 1.6)[..., None]
rng = np.random.default_rng(4)
GRAIN = [cv2.resize(rng.normal(0, 0.011, (H // 2, W // 2)).astype(np.float32), (W, H))[..., None] for _ in range(8)]
NAVY = np.array([0.09, 0.035, 0.012], np.float32)


def affine(img, z=1.0, dx=0.0, dy=0.0, rot=0.0):
    if abs(z - 1) < 1e-4 and abs(dx) < 0.3 and abs(dy) < 0.3 and abs(rot) < 1e-3:
        return img
    M = cv2.getRotationMatrix2D((W / 2, H / 2), rot, z); M[0, 2] += dx; M[1, 2] += dy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def chroma(img, px):
    if px < 0.4:
        return img
    out = img.copy()
    # aberration radiale : plus forte sur les bords
    for ch, s in ((2, px), (0, -px)):
        z = 1 + s / (W / 2)
        out[..., ch] = affine(img[..., ch], z)
    return out


def dirblur(img, L, vertical=False):
    L = int(L)
    if L < 3:
        return img
    k = np.ones((1, L), np.float32) / L
    return cv2.filter2D(img, -1, k.T if vertical else k, borderType=cv2.BORDER_REFLECT)


def zoomblur(img, amt):
    if amt < 0.004:
        return img
    acc = img.copy()
    for i in range(1, 7):
        acc += affine(img, 1 + amt * i / 7)
    return acc / 7


def lens_distort(img, k, radius=0.42):
    if abs(k) < 0.005:
        return img
    nx = (xx - W / 2) / (H * radius); ny = (yy - H / 2) / (H * radius)
    r2 = nx * nx + ny * ny
    f = 1 + k * np.exp(-r2) * (1 - r2 * 0.5)
    return cv2.remap(img, (W / 2 + (xx - W / 2) / f).astype(np.float32), (H / 2 + (yy - H / 2) / f).astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


SCOPE_RING = (np.exp(-((RPIX - H * 0.52) / (H * 0.03)) ** 2)[..., None] * np.array([1.0, 0.92, 0.2], np.float32)).astype(np.float32)


def deep_glow(img, strength=0.3, thr=0.75, tint=(1.15, 1.05, 0.8)):
    """Deep Glow : plusieurs halos superposés (court, moyen, large) sur les hautes lumières"""
    s = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    b = np.clip(s - thr, 0, 1)
    b = cv2.GaussianBlur(b, (0, 0), 3) * 0.6 + cv2.GaussianBlur(b, (0, 0), 9) + cv2.GaussianBlur(b, (0, 0), 28) * 0.8
    return img + cv2.resize(b, (W, H)) * np.array(tint, np.float32) * strength


def god_rays(img, strength, cx=0.62, cy=-0.15):
    """éclairage volumétrique : flou radial des hautes lumières depuis la source (soleil)"""
    if strength < 0.01:
        return img
    s = cv2.resize(img, (W // 6, H // 6), interpolation=cv2.INTER_AREA)
    b = np.clip(cv2.cvtColor(s, cv2.COLOR_BGR2GRAY) - 0.72, 0, 1)
    acc = np.zeros_like(b); h, w = b.shape
    for i in range(14):
        z = 1 - i * 0.045
        M = np.float32([[z, 0, cx * w * (1 - z)], [0, z, cy * h * (1 - z)]])
        acc += cv2.warpAffine(b, M, (w, h)) * (1 - i / 14)
    acc = cv2.GaussianBlur(acc / 7, (0, 0), 2)
    return img + cv2.resize(acc, (W, H))[..., None] * np.array([1.0, 0.95, 0.8], np.float32) * strength


# ---------------- étalonnage par scène ----------------
def scurve(x, c):
    return x + c * (x * x * (3 - 2 * x) - x)


LOOKS = {   # (saturation, contraste, teinte ombres BGR, teinte hautes lumières BGR, gain ombres, gain HL)
    'intro':    (0.85, 0.35, (0.30, 0.20, 0.02), (0.02, 0.08, 0.12), 0.20, 0.10),
    'nuke':     (0.95, 0.40, (0.30, 0.22, 0.00), (0.00, 0.05, 0.08), 0.18, 0.08),
    'desert':   (0.92, 0.45, (0.32, 0.22, 0.00), (0.00, 0.06, 0.14), 0.22, 0.10),
    'gold':     (0.95, 0.45, (0.34, 0.20, 0.00), (0.00, 0.10, 0.16), 0.24, 0.12),
    'electric': (0.80, 0.50, (0.38, 0.22, 0.00), (0.18, 0.12, 0.00), 0.26, 0.12),
    'frz':      (0.90, 0.40, (0.32, 0.22, 0.02), (0.00, 0.06, 0.12), 0.20, 0.08),
    'render':   (1.00, 0.20, (0.20, 0.12, 0.00), (0.00, 0.00, 0.00), 0.10, 0.00),
}


def grade(img, look):
    sat, con, sh, hl, gs, gh = LOOKS[look]
    x = np.clip(img, 0, 1)
    L = (0.114 * x[..., 0] + 0.587 * x[..., 1] + 0.299 * x[..., 2])[..., None]
    y = L + (x - L) * sat
    y = scurve(np.clip(y, 0, 1), con)
    Ls = scurve(np.clip(L, 0, 1), con)
    y = y + (1 - Ls) ** 2 * np.array(sh, np.float32) * gs * 2 - (1 - Ls) ** 2 * gs * 0.5 * 0.6
    y = y + Ls ** 2 * np.array(hl, np.float32) * gh * 2
    return np.clip(y, 0, 1.2)


# ---------------- particules, traînées, manga ----------------
RED = {}
def red_particles(age, seed, cx=W / 2, cy=H / 2):
    if seed not in RED:
        r = np.random.default_rng(seed); n = 50
        ang = r.uniform(0, 2 * np.pi, n); sp = r.uniform(250, 1400, n)
        RED[seed] = (np.stack([np.cos(ang) * sp, np.sin(ang) * sp - 300], 1), r.uniform(0.2, 0.5, n), r.normal(0, 14, (n, 2)), r.uniform(1.5, 4.0, n))
    v, life, off, sz = RED[seed]
    lay = np.zeros((H, W, 3), np.float32)
    for i in range(len(v)):
        if age > life[i]:
            continue
        a = (1 - age / life[i]) ** 0.7
        p = np.array([cx, cy]) + off[i] + v[i] * age + np.array([0, 1400]) * age * age / 2
        q = p - (v[i] + np.array([0, 1400]) * age) * 0.014
        col = (0.05 * a, 0.10 * a, 1.0 * a) if i % 3 else (0.1 * a, 0.4 * a, 1.0 * a)
        cv2.line(lay, tuple(int(c) for c in q), tuple(int(c) for c in p), col, int(sz[i]), cv2.LINE_AA)
    if age < 0.22:
        m = np.exp(-(((xx - cx) / 110) ** 2 + ((yy - cy) / 110) ** 2)) * (1 - age / 0.22) * 0.5
        lay += m[..., None] * np.array([0.02, 0.03, 0.7], np.float32)
    return lay + cv2.GaussianBlur(lay, (0, 0), 6) * 1.5


def tracer(age, seed):
    """traînée lumineuse de la balle : du canon (bas droite) vers le réticule"""
    L = 0.16
    if age > L:
        return None
    r = np.random.default_rng(seed)
    p0 = np.array([W * 0.70 + r.normal(0, 20), H * 0.80]); p1 = np.array([W / 2, H / 2])
    u = min(1, age / 0.05)
    head = p0 + (p1 - p0) * u; tail = p0 + (p1 - p0) * max(0, u - 0.6)
    lay = np.zeros((H, W, 3), np.float32)
    a = 1 - age / L
    cv2.line(lay, tuple(map(int, tail)), tuple(map(int, head)), (1.0 * a, 0.95 * a, 0.5 * a), 5, cv2.LINE_AA)
    cv2.line(lay, tuple(map(int, tail)), tuple(map(int, head)), (1.0 * a, 1.0 * a, 1.0 * a), 2, cv2.LINE_AA)
    return lay + cv2.GaussianBlur(lay, (0, 0), 9) * 2.5


_sl = np.random.default_rng(11)
SPEED_ANG = _sl.uniform(-np.pi, np.pi, 90); SPEED_W = _sl.uniform(0.004, 0.016, 90)
SPEED_MASK = None
def speed_lines(strength, seed):
    """lignes de vitesse manga (radiales, partant des bords vers le centre)"""
    r = np.random.default_rng(seed)
    angs = SPEED_ANG + r.uniform(-0.05, 0.05)
    m = np.zeros((H // 2, W // 2), np.float32)
    c = (W // 4, H // 4)
    for a, w in zip(angs, SPEED_W):
        r0 = r.uniform(0.38, 0.6) * H / 2
        p0 = (int(c[0] + math.cos(a) * r0), int(c[1] + math.sin(a) * r0))
        p1 = (int(c[0] + math.cos(a) * W), int(c[1] + math.sin(a) * W))
        pts = np.array([p0, (int(p1[0] + math.cos(a + math.pi / 2) * w * W), int(p1[1] + math.sin(a + math.pi / 2) * w * W)),
                        (int(p1[0] - math.cos(a + math.pi / 2) * w * W), int(p1[1] - math.sin(a + math.pi / 2) * w * W))], np.int32)
        cv2.fillConvexPoly(m, pts, 1.0, cv2.LINE_AA)
    m = cv2.resize(m, (W, H))[..., None] * np.clip((RR - 0.35) / 0.4, 0, 1)[..., None]
    return m * strength


def impact_frame(img, k):
    """impact frame façon anime : image inversée, contrastée, noir/blanc avec touche rouge"""
    g = cv2.cvtColor(np.clip(img, 0, 1).astype(np.float32), cv2.COLOR_BGR2GRAY)
    e = cv2.GaussianBlur(g, (0, 0), 1.2)
    bw = (e > np.percentile(e, 58)).astype(np.float32)
    inv = 1 - bw if k % 2 == 0 else bw
    out = np.dstack([inv, inv, inv])
    if k % 2 == 1:
        out = out * np.array([0.15, 0.15, 1.0], np.float32) + (1 - out) * 0.02
    return out


# ---------------- transitions ----------------
def scope_portal(prev_img, next_img, u):
    """à travers la lunette : l'image suivante apparaît dans un cercle de lunette qui grandit"""
    r = (0.02 + 0.33 * min(1, u / 0.5)) * H if u < 0.5 else (0.35 * H + (u - 0.5) / 0.5 * 1.3 * W)
    m = np.clip((r - RPIX) / 6, 0, 1)[..., None]
    base = affine(prev_img, 1 + 0.9 * min(1, u * 1.6)) * 0.55
    out = base * (1 - m) + next_img * m
    ring = np.clip(1 - np.abs(RPIX - r - 14) / 22, 0, 1)[..., None]
    out = out * (1 - ring * 0.92)
    rim = np.exp(-((RPIX - r) / 5) ** 2)[..., None] * np.array([1.0, 0.92, 0.3], np.float32)
    return out + rim * (1.4 if u < 0.9 else 0)


def mask_reveal(prev_img, next_img, dnext, u):
    """masquage par l'arme : les éléments proches (arme, mains) de l'image suivante apparaissent d'abord"""
    if dnext is None:
        return next_img if u > 0.5 else prev_img
    d = cv2.resize(dnext[:, CX0:CX0 + CW], (W, H))
    thr = 1.0 - 1.15 * u
    m = np.clip((d - thr) / 0.06, 0, 1)[..., None]
    edge = np.clip(1 - np.abs(d - thr) / 0.03, 0, 1)[..., None] * np.array([1.0, 0.95, 0.4], np.float32) * (1 - u)
    return zoomblur(prev_img, 0.06 * u) * (1 - m) + next_img * m + edge * 1.2


def spin3d(img, ang_deg, dark=True):
    """rotation 3D autour de l'axe vertical (perspective)"""
    a = math.radians(ang_deg); f = W * 1.1
    pts = []
    for X, Y in ((-W / 2, -H / 2), (W / 2, -H / 2), (W / 2, H / 2), (-W / 2, H / 2)):
        x3, z3 = X * math.cos(a), X * math.sin(a) + f
        pts.append((W / 2 + x3 * f / z3, H / 2 + Y * f / z3))
    M = cv2.getPerspectiveTransform(np.float32([(0, 0), (W, 0), (W, H), (0, H)]), np.float32(pts))
    out = cv2.warpPerspective(img, M, (W, H), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    msk = cv2.warpPerspective(np.ones((H, W), np.float32), M, (W, H))[..., None]
    bg = NAVY + np.exp(-RR * 1.5)[..., None] * np.array([0.25, 0.18, 0.02], np.float32)
    return out * msk + bg * (1 - msk)


def whip(img, s, direction=1):
    """whip pan : glissement latéral avec flou directionnel"""
    off = direction * s * W * 0.45
    return dirblur(affine(img, 1 + 0.05 * abs(s), off, 0), 10 + 140 * abs(s))


# ---------------- événements ----------------
starts, TOTAL = T.seg_starts()
segt = {k: (t0, d, p) for t0, k, d, p in starts if k != 'src'}
EV = []
def ev(t, typ, amp, rise, dec, **kw):
    EV.append((t, typ, amp, rise, dec, kw))

BEATS_OUT = []
k = 0
while T.BEAT0 + k * T.BEAT < T.SRC_END:
    s = T.BEAT0 + k * T.BEAT
    o = T.src_to_out(s)
    if o is not None and ((12.0 <= s < 44.0) or s >= 48.4):
        BEATS_OUT.append((o, k))
    k += 1
for o, k in BEATS_OUT:   # pulsations calées sur le tempo pendant les passages intenses
    ev(o, 'zoom', 0.018 if k % 4 == 0 else 0.007, 0, 0.16)
    if k % 4 == 0:
        ev(o, 'glow', 0.18, 0, 0.22); ev(o, 'chroma', 2.5, 0, 0.15)

for ks, kind in T.KILLS:
    o = T.src_to_out(ks)
    if o is None:
        continue
    big = kind == 'multi'
    ev(o, 'shake', 22 if big else (15 if kind == 'sn' else 9), 0, 0.26)
    ev(o, 'flash', 0.5 if big else 0.3, 0, 0.05)
    ev(o, 'zoom', 0.09 if big else 0.06, 0.04, 0.3)
    ev(o, 'chroma', 9 if big else 5, 0, 0.2)
    ev(o, 'red', 1, 0, 0.55)
    if kind in ('sn', 'multi') and ks < 48:
        ev(o, 'distort', 0.24, 0.05, 0.3); ev(o, 'tracer', 1, 0, 0.16); ev(o, 'speed', 0.55 if big else 0.35, 0, 0.32)
    if big:
        ev(o, 'impact', 1, 0, 3.5 / FPS)
    if kind == 'fps' and ks > 48:
        ev(o, 'speed', 0.25, 0, 0.25)

TRANS = []   # (out_time, style, src_cut)
for c, style in T.CUTS:
    o = T.src_to_out(c)
    if o is not None:
        TRANS.append((o, style, c))
        if style in ('xzoom', 'scope', 'spin3d'):
            ev(o, 'flash', 0.18, 0.03, 0.08)

FLY0, FLY1 = T.src_to_out(T.FLY_A), T.src_to_out(T.FLY_B)
ev(FLY1, 'flash', 1.0, 0.22, 0.12); ev(FLY1, 'shake', 26, 0, 0.35); ev(FLY1, 'chroma', 14, 0.1, 0.3)
tf, df, _ = segt['frz']; tw, dw, _ = segt['wpn']; tr, dr, _ = segt['rep']
ev(tf, 'flash', 0.35, 0, 0.12); ev(tf, 'chroma', 12, 0, 0.3); ev(tf, 'zoom', 0.06, 0, 0.3)
ev(tf + df, 'zoomblur', 0.08, 0.1, 0.12); ev(tf + df, 'flash', 0.2, 0.05, 0.1)
ev(tw, 'chroma', 8, 0, 0.25); ev(tw + dw, 'zoom', 0.06, 0.08, 0.2); ev(tw + dw, 'flash', 0.25, 0.05, 0.1)
ev(tr, 'flash', 0.5, 0.06, 0.15); ev(tr, 'zoomblur', 0.1, 0.1, 0.14)
FL0 = T.src_to_out(T.FLOAT_A)
ev(FL0 + T.FLOAT_N / FPS, 'shake', 18, 0, 0.3); ev(FL0 + T.FLOAT_N / FPS, 'flash', 0.3, 0.04, 0.1)


def ev_val(t, typ):
    v = 0.0; hits = []
    for te, ty, amp, rise, dec, kw in EV:
        if ty != typ:
            continue
        d = t - te
        if rise > 0 and -rise <= d < 0:
            v += amp * (1 + d / rise) ** 2
        elif 0 <= d < dec:
            if ty in ('red', 'tracer', 'impact', 'speed'):
                hits.append((d, int(te * 1000), amp, kw))
            else:
                v += amp * (1 - d / dec) ** 2
    return v, hits


def src_frame(x):
    """image source à l'instant x (avec écran flottant et traversée 3D qui remplacent la source)"""
    if T.FLY_A <= x < T.FLY_B and SEQ['fly']:
        return render169(SEQ['fly'][min(len(SEQ['fly']) - 1, int((x - T.FLY_A) * FPS))]), 'render'
    if T.FLOAT_A <= x < T.FLOAT_A + T.FLOAT_N / FPS and SEQ['flt']:
        return render169(SEQ['flt'][min(len(SEQ['flt']) - 1, int((x - T.FLOAT_A) * FPS))]), 'render'
    return src_image(x), T.look_at_src(x)


TW = {'xzoom': 0.22, 'whip': 0.13, 'spin': 0.16, 'scope': 0.30, 'mask': 0.36, 'spin3d': 0.22}


def transition(x, base):
    """applique la transition si x est proche d'une coupe source"""
    for o, style, c in TRANS:
        w = TW[style]
        if c - w <= x < c + w:
            u = (x - (c - w)) / (2 * w)          # 0 -> 1 sur toute la transition, coupe à 0.5
            before = x < c
            e = (u / 0.5) ** 2 if before else (1 - (u - 0.5) / 0.5) ** 2     # 0 aux extrémités, 1 à la coupe
            if style == 'xzoom':
                z = 1 + 0.35 * e if before else 1 + 0.35 * e
                return zoomblur(affine(base, z), 0.18 * e)
            if style == 'whip':
                off = -e * W * 0.45 if before else e * W * 0.45
                return dirblur(affine(base, 1 + 0.06 * e, off, 0), 160 * e)
            if style == 'spin':
                ang = 45 * e if before else -45 * e
                return dirblur(affine(base, 1 + 0.25 * e, 0, 0, ang), 60 * e)
            if style == 'spin3d':
                return spin3d(base, 88 * e if before else -88 * e)
            if style == 'scope':
                if before:
                    nxt = src_image(c + 0.02)
                    return scope_portal(base, nxt, u)
                prv = src_image(c - 0.02)
                return scope_portal(prv, base, u)
            if style == 'mask':
                if before:
                    return affine(base, 1 + 0.04 * u)
                return mask_reveal(src_image(c - 0.02), base, depth_at(x), (u - 0.5) * 2)
    return base


def frame_at(t):
    for t0, kind, dur, p in reversed(starts):
        if t >= t0 - 1e-9:
            break
    tau = t - t0
    rays = 0.0; glow_base = 0.28; x = None
    if kind == 'src':
        x = p['t0'] + tau
        img, look = src_frame(x)
        if look != 'render':
            img = transition(x, img)
        scoped = any(a <= x < b for a, b in T.SCOPE_WIN)
        if x < 9.4:
            rays = 0.35; img = affine(img, 1.02 + 0.03 * x / 9.4)    # poussée lente de l'intro
        if look == 'render':
            look = 'nuke' if x < 20 else 'electric'
    else:
        u = tau / dur
        img = seq_frame(kind, u)
        if img is None:
            img = to169(np.asarray(SRC[min(NSRC - 1, int(p['at'] * FPS))]))
        scoped = False
        look = 'frz' if kind == 'frz' else 'render'
        if kind == 'frz':
            rays = 0.45
        glow_base = 0.4
    z = 1 + ev_val(t, 'zoom')[0]
    sh = ev_val(t, 'shake')[0]
    dx = dy = rot = 0.0
    if sh > 0.3:
        r = np.random.default_rng(int(t * FPS)); dx, dy = r.normal(0, sh, 2); rot = r.normal(0, sh * 0.03)
    img = affine(img, z, dx, dy, rot)
    img = zoomblur(img, ev_val(t, 'zoomblur')[0])
    dist = ev_val(t, 'distort')[0] + (0.06 if scoped else 0)
    img = lens_distort(img, dist)
    img = chroma(img, ev_val(t, 'chroma')[0] + (1.5 if scoped else 0.5))
    img = god_rays(img, rays)
    img = deep_glow(img, glow_base + ev_val(t, 'glow')[0])
    img = grade(img, look)
    if scoped:
        img = img + SCOPE_RING * 0.22
    for age, seed, amp, kw in ev_val(t, 'red')[1]:
        img = img + red_particles(age, seed)
    for age, seed, amp, kw in ev_val(t, 'tracer')[1]:
        tl = tracer(age, seed)
        if tl is not None:
            img = img + tl
    for age, seed, amp, kw in ev_val(t, 'speed')[1]:
        img = img + speed_lines(amp * (1 - age / 0.32), seed + int(age * 30)) * np.array([1.0, 1.0, 1.0], np.float32)
    img = img * VIGN
    imp = ev_val(t, 'impact')[1]
    if imp:
        age = imp[0][0]
        img = impact_frame(img, int(age * FPS))
    flv = min(1.0, ev_val(t, 'flash')[0])
    if flv > 0.005:
        img = img * (1 - flv) + flv * np.array([1.0, 1.0, 0.94], np.float32)
    if t > TOTAL - 0.4:
        img = img * max(0.0, (TOTAL - t) / 0.4)
    img = img + GRAIN[int(t * FPS) % len(GRAIN)]
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


if STILLS:
    od = os.path.join(ROOT, 'stills4'); os.makedirs(od, exist_ok=True)
    for t in STILLS:
        cv2.imwrite(os.path.join(od, f'{t:06.2f}.jpg'), frame_at(t), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print('stills ok'); sys.exit()

a, b = (PREVIEW if PREVIEW else (0, TOTAL))
nf = int(round((b - a) * FPS))
aud = os.path.join(ROOT, 'audio4.wav')
cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
       '-ss', str(a), '-t', str(b - a), '-i', aud,
       '-c:v', 'libx264', '-preset', 'slow' if not PREVIEW else 'veryfast', '-crf', '18', '-maxrate', '16M', '-bufsize', '32M',
       '-profile:v', 'high', '-level', '4.2', '-pix_fmt', 'yuv420p',
       '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
       '-c:a', 'aac', '-b:a', '320k', '-movflags', '+faststart', '-shortest', OUTF]
pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for i in range(nf):
    t = a + i / FPS
    pr.stdin.write(frame_at(t).tobytes())
    if i % 240 == 0:
        print(f'{t:6.2f}s / {b:.2f}', flush=True)
pr.stdin.close(); pr.wait()
print('DONE', OUTF, nf)
