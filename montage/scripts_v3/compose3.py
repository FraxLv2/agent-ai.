# Compositeur v3 : style cyan/turquoise, 16:9 plein cadre, inserts 3D Blender, effets synchronisés à la musique
# usage: python3 compose3.py ROOT OUT.mp4 [--preview a,b] [--stills t1,t2,...]
import sys, os, math, subprocess, glob
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
import timeline3 as T

ROOT, OUTF = sys.argv[1], sys.argv[2]
PREVIEW = STILLS = None
if '--preview' in sys.argv:
    PREVIEW = [float(x) for x in sys.argv[sys.argv.index('--preview') + 1].split(',')]
if '--stills' in sys.argv:
    STILLS = [float(x) for x in sys.argv[sys.argv.index('--stills') + 1].split(',')]
W, H, FPS = 1920, 1080, T.FPS
WK = os.path.join(ROOT, 'work'); RD = os.path.join(ROOT, 'renders')
CX0, CW = 101, 906          # recadrage 16:9 de la source 1108x510
SRC_W, SRC_H = 1108, 510

# ---------------- source + HUD effacé ----------------
mask = cv2.imread(os.path.join(WK, 'hudmask.png'), 0)[430:510]
cap = cv2.VideoCapture(os.path.join(WK, 'src60.mp4')); SRC = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    t = len(SRC) / FPS
    if any(a <= t < b for a, b in T.HUD_SEGS):
        f[430:510] = cv2.inpaint(f[430:510], mask, 3, cv2.INPAINT_TELEA)
    SRC.append(f)
NSRC = len(SRC)
_dz = np.load(os.path.join(WK, 'depth_seq.npz')); DEPTH = dict(zip(_dz['idx'].tolist(), _dz['d']))
seq = lambda d: sorted(glob.glob(os.path.join(RD, d, '*.png')))
SEQ = {'weapon': seq('weapon_60'), 'freeze': seq('freeze_60'), 'studio': seq('studio_60'), 'bullet': seq('bullet'),
       'replica': seq('replica_60'), 'sniper': seq('sniper'), 'float': seq('float')}
SLOW = sorted(glob.glob(os.path.join(WK, 'slow_sn', '*.png'))); SLOWB = sorted(glob.glob(os.path.join(WK, 'slow_sn_blend', '*.png')))
print('frames', NSRC, {k: len(v) for k, v in SEQ.items()}, 'slow', len(SLOW), flush=True)


def to169(img_bgr_u8):
    """image source pleine (1108x510) -> 1920x1080 recadré + accentuation"""
    c = img_bgr_u8[:, CX0:CX0 + CW]
    x = cv2.resize(c, (W, H), interpolation=cv2.INTER_LANCZOS4).astype(np.float32) / 255
    b = cv2.GaussianBlur(x, (0, 0), 1.3)
    return np.clip(x * 1.45 - b * 0.45, 0, 1)


def render169(path):
    im = cv2.imread(path)
    h, w = im.shape[:2]
    if abs(w / h - 16 / 9) > 0.02:   # rendu 2.17:1 -> recadrage central 16:9
        cw = int(round(h * 16 / 9)); x0 = (w - cw) // 2; im = im[:, x0:x0 + cw]
    if im.shape[1] != W:
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_LANCZOS4)
    return im.astype(np.float32) / 255


def seq_frame(kind, tau, dur):
    fs = SEQ[kind]
    if not fs:
        return None
    return render169(fs[min(len(fs) - 1, int(tau / dur * len(fs)))])


# ---------------- vitesse / flou de mouvement ----------------
def remap(x):
    for c, w, k in T.RAMPS:
        if abs(x - c) < w:
            u = (x - c) / w
            return c + w * (u - k / math.pi * math.sin(math.pi * u)), 1 - k * math.cos(math.pi * u)
    return x, 1.0


def src_raw(ts, lo, hi):
    fi = min(max(ts, lo), hi - 1e-3) * FPS
    i0 = min(int(fi), NSRC - 1); a = fi - int(fi); i1 = min(i0 + 1, NSRC - 1)
    if a < 0.04 or int(hi * FPS) - 1 <= i0:
        return SRC[i0]
    return cv2.addWeighted(SRC[i0], 1 - a, SRC[i1], a, 0)


GX, GY = np.meshgrid(np.arange(SRC_W, dtype=np.float32), np.arange(SRC_H, dtype=np.float32))
TOPMASK = np.clip((GY - 24) / 30, 0, 1)


def parallax_dof(img, x):
    """caméra 3D (parallaxe par profondeur MiDaS) + arrière-plan légèrement flouté"""
    for a, b, amp, sgn in T.PARALLAX:
        if a <= x < b:
            break
    else:
        return img
    d = DEPTH.get(int(round(x * FPS)))
    if d is None:
        return img
    u = (x - a) / max(b - a, 1e-3)
    fade = min(1.0, u / 0.12, (1 - u) / 0.12)
    dd = cv2.resize(d.astype(np.float32), (SRC_W, SRC_H))
    dc = dd - np.median(dd)
    dx = amp * sgn * (2 * u - 1) * fade; dy = -amp * 0.3 * math.sin(math.pi * u) * fade
    z = 1 + 0.04 * fade
    mx = (GX - SRC_W / 2) / z + SRC_W / 2 - dc * dx * TOPMASK
    my = (GY - SRC_H / 2) / z + SRC_H / 2 - dc * dy * TOPMASK
    out = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    far = np.clip((0.55 - cv2.remap(dd, mx, my, cv2.INTER_LINEAR)) / 0.4, 0, 1)[..., None] * 0.85
    blur = cv2.GaussianBlur(out, (0, 0), 2.6)
    return (out * (1 - far) + blur * far).astype(np.uint8)


def src_image(x, lo, hi):
    ts, speed = remap(x)
    if speed > 1.25:   # flou de mouvement directionnel pendant les accélérations
        d = 0.5 / FPS
        f = np.mean([src_raw(remap(x + o)[0], lo, hi).astype(np.float32) for o in (-d, -d / 2, 0, d / 2, d)], axis=0).astype(np.uint8)
    else:
        f = src_raw(ts, lo, hi)
    return to169(parallax_dof(f, x)), speed


def slow_frame(tau, dur):
    u = tau / dur
    src = 9.40 + (0.17 * u / 0.25 if u < 0.25 else 0.17 + 0.09 * (u - 0.25) / 0.75)
    i = min(len(SLOW) - 1, int((src - 9.40) * 300))
    f = cv2.imread((SLOWB if src < 9.56 else SLOW)[i])
    f[430:510] = cv2.inpaint(f[430:510], mask, 3, cv2.INPAINT_TELEA)
    return to169(f)


# ---------------- effets ----------------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
RR = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
VIGN = (1 - 0.38 * np.clip(RR / 1.4, 0, 1) ** 1.6)[..., None]
rng = np.random.default_rng(4)
GRAIN = [cv2.resize(rng.normal(0, 0.012, (H // 2, W // 2)).astype(np.float32), (W, H))[..., None] for _ in range(8)]


def affine(img, z=1.0, dx=0.0, dy=0.0, rot=0.0):
    if abs(z - 1) < 1e-4 and abs(dx) < 0.3 and abs(dy) < 0.3 and abs(rot) < 1e-3:
        return img
    M = cv2.getRotationMatrix2D((W / 2, H / 2), rot, z); M[0, 2] += dx; M[1, 2] += dy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def chroma(img, px):
    if px < 0.4:
        return img
    out = img.copy()
    for ch, s in ((2, px), (0, -px)):
        M = np.float32([[1, 0, s], [0, 1, 0]])
        out[..., ch] = cv2.warpAffine(img[..., ch], M, (W, H), borderMode=cv2.BORDER_REFLECT)
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
    for i in range(1, 6):
        acc += affine(img, 1 + amt * i / 6)
    return acc / 6


def lens_distort(img, k, radius=0.42):
    """distorsion optique en barillet autour de la lunette (centre de l'écran)"""
    if abs(k) < 0.005:
        return img
    nx = (xx - W / 2) / (H * radius); ny = (yy - H / 2) / (H * radius)
    r2 = nx * nx + ny * ny
    f = 1 + k * np.exp(-r2) * (1 - r2 * 0.5)
    mx = W / 2 + (xx - W / 2) / f; my = H / 2 + (yy - H / 2) / f
    return cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


SCOPE_RING = None
def scope_glow(strength):
    global SCOPE_RING
    if SCOPE_RING is None:
        r = RR * (W / 2) / (H / 2)  # approx. rayon normalisé à la hauteur
        ring = np.exp(-((np.sqrt(((xx - W / 2) ** 2 + (yy - H / 2) ** 2)) - H * 0.52) / (H * 0.03)) ** 2)
        SCOPE_RING = (ring[..., None] * np.array([1.0, 0.92, 0.2], np.float32)).astype(np.float32)
    return SCOPE_RING * strength


def bloom(img, strength=0.3, thr=0.8):
    s = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    b = np.clip(s - thr, 0, 1)
    b = cv2.GaussianBlur(b, (0, 0), 6) + cv2.GaussianBlur(b, (0, 0), 20)
    b = cv2.resize(b, (W, H)) * np.array([1.15, 1.05, 0.75], np.float32)   # halo cyan
    return img + b * strength


# rampe de couleur cyan/turquoise : noir profond -> bleu-sarcelle -> cyan -> blanc lumineux (BGR)
RAMP_L = np.array([0.0, 0.12, 0.30, 0.55, 0.80, 1.0], np.float32)
RAMP_C = np.array([[0.0, 0.0, 0.0], [0.11, 0.075, 0.0], [0.40, 0.33, 0.03], [0.82, 0.74, 0.22], [1.0, 0.98, 0.78], [1, 1, 1]], np.float32)


def grade(img, amount=0.66, contrast=0.5, keep=0.55):
    x = np.clip(img, 0, 1)
    L = 0.114 * x[..., 0] + 0.587 * x[..., 1] + 0.299 * x[..., 2]
    Lc = L + contrast * (L * L * (3 - 2 * L) - L)
    tone = np.stack([np.interp(Lc, RAMP_L, RAMP_C[:, i]) for i in range(3)], -1).astype(np.float32)
    Lx = L[..., None]
    desat = Lx + (x - Lx) * keep
    desat = desat * (Lc / np.maximum(L, 1e-4))[..., None]
    out = desat * (1 - amount) + tone * amount
    # tirs / impacts : rouges et oranges vifs préservés
    hsv = cv2.cvtColor((x * 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[..., 0], hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    warm = (((hue < 24) | (hue > 170)) & (sat > 0.5) & (val > 0.88)).astype(np.float32)
    warm = cv2.GaussianBlur(warm, (0, 0), 3)[..., None]
    return out * (1 - warm) + np.clip(x * 1.08, 0, 1) * warm


# ---------------- particules rouges d'impact ----------------
RED = {}
def red_particles(age, seed, cx=W / 2, cy=H / 2):
    if seed not in RED:
        r = np.random.default_rng(seed); n = 55
        ang = r.uniform(0, 2 * np.pi, n); sp = r.uniform(250, 1500, n)
        RED[seed] = (np.stack([np.cos(ang) * sp, np.sin(ang) * sp - 300], 1), r.uniform(0.2, 0.55, n), r.normal(0, 14, (n, 2)), r.uniform(1.5, 4.5, n))
    v, life, off, sz = RED[seed]
    lay = np.zeros((H, W, 3), np.float32)
    for i in range(len(v)):
        if age > life[i]:
            continue
        a = (1 - age / life[i]) ** 0.7
        p = np.array([cx, cy]) + off[i] + v[i] * age + np.array([0, 1400]) * age * age / 2
        q = p - (v[i] + np.array([0, 1400]) * age) * 0.014
        col = (0.05 * a, 0.12 * a, 1.0 * a) if i % 3 else (0.1 * a, 0.45 * a, 1.0 * a)   # rouge / orange (BGR)
        cv2.line(lay, tuple(int(c) for c in q), tuple(int(c) for c in p), col, int(sz[i]), cv2.LINE_AA)
    # brume rouge
    if age < 0.25:
        m = np.exp(-(((xx - cx) / 120) ** 2 + ((yy - cy) / 120) ** 2)) * (1 - age / 0.25) * 0.5
        lay += m[..., None] * np.array([0.02, 0.03, 0.7], np.float32)
    return lay + cv2.GaussianBlur(lay, (0, 0), 6) * 1.6


# ---------------- événements (temps de sortie), synchronisés au tempo ----------------
starts, TOTAL = T.seg_starts()
segt = {}
for t0, k, d, p in starts:
    segt.setdefault(k, []).append((t0, d))
BEATS_OUT = []
for t0, k, d, p in starts:   # temps forts dans le repère de sortie (la musique reste en phase grâce aux inserts entiers)
    pass
def snap(t, tol=0.09):
    """cale un effet sur le temps fort le plus proche s'il est assez près"""
    best = min(BEATS_OUT, key=lambda b: abs(b - t)) if BEATS_OUT else t
    return best if abs(best - t) <= tol else t
k = 0
while T.BEAT0 + k * T.BEAT < T.SRC_END:
    o = T.src_to_out(T.BEAT0 + k * T.BEAT)
    if o is not None:
        BEATS_OUT.append(o)
    k += 1

EV = []
def ev(t, typ, amp, rise, dec, **kw):
    EV.append((t, typ, amp, rise, dec, kw))

for ks, kind in T.KILLS:
    o = T.src_to_out(ks)
    if o is None:
        continue
    s = snap(o)
    ev(o, 'shake', 13 if kind != 'sniper' else 18, 0, 0.22)
    ev(s, 'flash', 0.32, 0, 0.055)                       # flash très court
    ev(s, 'zoom', 0.06, 0.06, 0.28)                       # zoom dynamique
    ev(o, 'chroma', 5, 0, 0.18)
    ev(o, 'red', 1, 0, 0.6)
    if kind == 'sniper':
        ev(o, 'distort', 0.22, 0.05, 0.3)
for c, style in T.CUTS:
    o = T.src_to_out(c)
    if o is None:
        continue
    if style == 'spin':
        ev(o, 'spin', 1, 0.12, 0.14); ev(o, 'zoomblur', 0.08, 0.1, 0.1); ev(o, 'flash', 0.15, 0.04, 0.08)
    else:
        ev(o, 'zoom', 0.10, 0.10, 0.12); ev(o, 'zoomblur', 0.10, 0.08, 0.1); ev(o, 'dirblur', 50, 0.06, 0.08); ev(o, 'flash', 0.12, 0.04, 0.08)
for b in BEATS_OUT:
    i = BEATS_OUT.index(b)
    ev(b, 'zoom', 0.016 if i % 4 == 0 else 0.006, 0, 0.14)
    if i % 4 == 0:
        ev(b, 'glow', 0.12, 0, 0.18)

def seg_bound(kind, idx=0):
    return segt[kind][idx]
tw, dw = seg_bound('weapon'); ts_, ds_ = seg_bound('slow'); tn, dn = seg_bound('sniper'); tf, df = seg_bound('freeze')
tst, dst = seg_bound('studio'); tb, db = seg_bound('bullet'); tr, dr = seg_bound('replica')
# entrées / sorties des inserts 3D
ev(tw, 'zoomblur', 0.05, 0.08, 0.1); ev(tw + dw, 'zoomblur', 0.05, 0.08, 0.1)
ev(ts_, 'flash', 0.18, 0.03, 0.12)
ev(tn, 'flash', 0.6, 0.05, 0.22); ev(tn, 'chroma', 10, 0.05, 0.25); ev(tn, 'zoomblur', 0.06, 0.08, 0.14)
SN_IMPACT = tn + (T.SNIPER_N - 15) / FPS
ev(SN_IMPACT, 'flash', 0.3, 0, 0.12); ev(SN_IMPACT, 'shake', 18, 0, 0.3); ev(SN_IMPACT, 'red', 1, 0, 0.6, cx=W * 0.52, cy=H * 0.45)
ev(tn + dn, 'flash', 0.55, 0.12, 0.2); ev(tn + dn, 'shake', 14, 0, 0.25)
ev(tf, 'flash', 0.4, 0.05, 0.2); ev(tf, 'chroma', 10, 0.05, 0.25); ev(tf + df, 'flash', 0.3, 0.06, 0.15); ev(tf + df, 'zoom', 0.05, 0.1, 0.2)
ev(tst, 'spin', 1, 0.14, 0.16); ev(tst, 'zoomblur', 0.1, 0.12, 0.12); ev(tst, 'flash', 0.25, 0.06, 0.12)
ev(tst + dst, 'zoom', 0.12, 0.12, 0.1); ev(tst + dst, 'zoomblur', 0.12, 0.12, 0.1)
ev(tb, 'flash', 0.5, 0.05, 0.25); ev(tb, 'chroma', 10, 0.05, 0.25)
ev(tb + db, 'flash', 0.6, 0.12, 0.25); ev(tb + db, 'shake', 20, 0, 0.3); ev(tb + db, 'red', 1, 0, 0.6)
ev(tr, 'flash', 0.4, 0.06, 0.18); ev(tr, 'zoomblur', 0.08, 0.1, 0.14)
ev(tr + dr, 'flash', 0.5, 0.1, 0.2); ev(tr + dr, 'zoomblur', 0.1, 0.1, 0.12)
FL0 = T.src_to_out(T.FLOAT_A)


def ev_val(t, typ):
    v = 0.0; hits = []
    for te, ty, amp, rise, dec, kw in EV:
        if ty != typ:
            continue
        d = t - te
        if rise > 0 and -rise <= d < 0:
            v += amp * (1 + d / rise) ** 2
            if ty == 'spin':
                hits.append(d / rise)          # -1 -> 0
        elif 0 <= d < dec:
            if ty in ('red',):
                hits.append((d, int(te * 1000), kw))
            elif ty == 'spin':
                hits.append(d / dec)           # 0 -> 1
            else:
                v += amp * (1 - d / dec) ** 2
    return (v, hits)


def frame_at(t):
    for t0, kind, dur, p in reversed(starts):
        if t >= t0 - 1e-9:
            break
    tau = t - t0
    amount = 0.5
    keep = 0.55
    if kind == 'src':
        x = p['t0'] + tau
        fl = None
        if T.FLOAT_A <= x < T.FLOAT_A + T.FLOAT_N / FPS and SEQ['float']:
            fl = render169(SEQ['float'][min(len(SEQ['float']) - 1, int((x - T.FLOAT_A) * FPS))])
        img = fl if fl is not None else src_image(x, p['t0'], p['t1'])[0]
        scoped = any(a <= x < b for a, b in T.SCOPE_WIN)
    elif kind == 'slow':
        u = tau / dur
        img = affine(slow_frame(tau, dur), 1 + 0.08 * u * u)
        scoped = u > 0.3
    else:
        img = seq_frame(kind, tau, dur)
        if img is None:
            img = to169(SRC[min(NSRC - 1, int(p.get('at', 9.66) * FPS))])
        scoped = False
        if kind in ('studio',):
            amount = 0.35; keep = 0.8
        if kind in ('replica', 'weapon'):
            amount = 0.12; keep = 1.0   # garder l'or et les reflets cyan rendus
    # effets synchronisés
    z = 1 + ev_val(t, 'zoom')[0]
    sh = ev_val(t, 'shake')[0]
    dx = dy = rot = 0.0
    if sh > 0.3:
        r = np.random.default_rng(int(t * FPS)); dx, dy = r.normal(0, sh, 2); rot = r.normal(0, sh * 0.03)
    _, spins = ev_val(t, 'spin')
    for s in spins:   # transition par rotation (avant: 0 -> 28°, après: -28° -> 0)
        rot += 28 * (s + 1) ** 2 if s < 0 else -28 * (1 - s) ** 2
        z *= 1 + 0.15 * (1 - abs(s))
    img = affine(img, z, dx, dy, rot)
    if spins:
        img = dirblur(img, 40 * max(1 - abs(s) for s in spins))
    img = zoomblur(img, ev_val(t, 'zoomblur')[0])
    img = dirblur(img, ev_val(t, 'dirblur')[0])
    dist = ev_val(t, 'distort')[0]
    if scoped:
        dist += 0.06
    img = lens_distort(img, dist)
    img = chroma(img, ev_val(t, 'chroma')[0] + (1.5 if scoped else 0.6))
    img = bloom(img, 0.3 + ev_val(t, 'glow')[0])
    img = grade(img, amount, keep=keep)
    if scoped:
        img = img + scope_glow(0.22)
    for age, seed, kw in ev_val(t, 'red')[1]:
        img = img + red_particles(age, seed, kw.get('cx', W / 2), kw.get('cy', H / 2))
    img = img * VIGN
    flv = min(1.0, ev_val(t, 'flash')[0])
    if flv > 0.005:
        img = img * (1 - flv) + flv * np.array([1.0, 1.0, 0.92], np.float32)   # flash blanc légèrement cyan
    # fin cinématique : ralenti visuel + fondu très court
    if t > TOTAL - 0.45:
        img = img * max(0.0, (TOTAL - t) / 0.45)
    img = img + GRAIN[int(t * FPS) % len(GRAIN)]
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


if STILLS:
    os.makedirs(os.path.join(WK, 'stills3'), exist_ok=True)
    for t in STILLS:
        cv2.imwrite(os.path.join(WK, 'stills3', f'{t:06.2f}.jpg'), frame_at(t), [cv2.IMWRITE_JPEG_QUALITY, 88])
    print('stills ok'); sys.exit()

a, b = (PREVIEW if PREVIEW else (0, TOTAL))
nf = int(round((b - a) * FPS))
aud = os.path.join(WK, 'audio3.wav')
cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
       '-ss', str(a), '-t', str(b - a), '-i', aud,
       '-c:v', 'libx264', '-preset', 'slow' if not PREVIEW else 'veryfast', '-crf', '18', '-maxrate', '14M', '-bufsize', '28M',
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
