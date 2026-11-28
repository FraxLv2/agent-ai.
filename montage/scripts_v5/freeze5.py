# v5 : arrêt du temps 3D sur chaque plan où l'on voit le personnage.
# La vidéo d'origine reste intacte ; on insère à chaque moment un « freeze » 2.5D :
# caméra virtuelle qui avance vers le personnage (parallaxe par profondeur MiDaS),
# mise au point sur lui, particules lumineuses en 3D (occultées par le décor), son étouffé.
# usage : python3 freeze5.py src.mov out.mp4 [--test k] [--stills]
import sys, os, math, subprocess
import numpy as np, cv2, onnxruntime as ort

SRC = sys.argv[1]; OUTF = sys.argv[2]
TEST = int(sys.argv[sys.argv.index('--test') + 1]) if '--test' in sys.argv else None
STILLS = '--stills' in sys.argv
W, H = 1920, 886            # sortie (même format que la source 1110x512, agrandi)
FPS = 60
D = 1.4                     # durée de chaque arrêt du temps (s)
NF = int(round(D * FPS))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models', 'midas_small.onnx')

# (instant du gel en s, position du personnage en px source 1110x512)
EVENTS_ALL = [  # (t, x, y, demi-hauteur du perso, demi-largeur) en px source
    (1.75, 290, 240, 170, 110), (3.40, 610, 200, 120, 80), (4.60, 580, 170, 160, 90), (27.85, 510, 250, 250, 200),
    (32.50, 300, 256, 130, 150), (33.80, 490, 236, 100, 70), (39.60, 380, 334, 140, 100), (75.00, 450, 205, 140, 90),
    (78.60, 520, 385, 120, 150), (79.90, 580, 300, 170, 120), (81.90, 560, 268, 170, 110), (84.85, 750, 288, 220, 150),
    (89.90, 500, 236, 110, 120), (96.90, 620, 276, 240, 110), (115.90, 470, 285, 130, 240),
]
# demandé : uniquement 1:29.9 (2e capture) et 39.6 s (1re capture)
EVENTS = [e for e in EVENTS_ALL if e[0] in (39.60, 89.90)]
SX, SY = W / 1110, H / 512

# ---------------------------------------------------------------- source
def read_src():
    cap = cv2.VideoCapture(SRC); fr = []
    while True:
        ok, im = cap.read()
        if not ok: break
        fr.append(im)
    return fr

def up(im):
    x = cv2.resize(im, (W, H), interpolation=cv2.INTER_LANCZOS4)
    b = cv2.GaussianBlur(x, (0, 0), 1.2)
    return cv2.addWeighted(x, 1.35, b, -0.35, 0)

# ---------------------------------------------------------------- profondeur
_sess = None
def depth(im):
    global _sess
    if _sess is None: _sess = ort.InferenceSession(MODEL)
    x = cv2.resize(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), (256, 256), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    d = _sess.run(None, {'0': x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
    d = (d - np.percentile(d, 1)) / (np.percentile(d, 99.5) - np.percentile(d, 1) + 1e-6)
    d = np.clip(cv2.resize(d, (W, H), interpolation=cv2.INTER_CUBIC), 0, 1).astype(np.float32)
    # filtre guidé : bords de profondeur collés aux contours de l'image
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    r, eps = 12, 1e-3
    bf = lambda a: cv2.boxFilter(a, -1, (r, r))
    mI, mp = bf(g), bf(d); cIp = bf(g * d) - mI * mp; vI = bf(g * g) - mI * mI
    a = cIp / (vI + eps); b = mp - a * mI
    return np.clip(bf(a) * g + bf(b), 0, 1)

def inv_to_z(inv): return 1.0 / (0.025 + 0.64 * inv)

# ---------------------------------------------------------------- outils
def ease(u): u = min(max(float(u), 0.0), 1.0); return u * u * (3 - 2 * u)
def eout(u): u = min(max(float(u), 0.0), 1.0); return 1 - (1 - u) ** 3
F = W / (2 * math.tan(math.radians(72) / 2))
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
hs = 2  # champ de déplacement calculé en demi-résolution
yh, xh = np.mgrid[0:H // hs, 0:W // hs].astype(np.float32) * hs

def zoom_blur(img, c, amt, n=6):
    if amt < 0.004: return img
    acc = img.astype(np.float32); cx, cy = c
    for k in range(1, n):
        s = 1 + amt * k / n
        M = np.float32([[s, 0, cx * (1 - s)], [0, s, cy * (1 - s)]])
        acc += cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    return np.clip(acc / n, 0, 255).astype(np.uint8)

# ---------------------------------------------------------------- caméra 2.5D
# Projection simplifiée mais robuste : zoom vers le personnage + parallaxe bornée par la
# profondeur relative (inv - ic). Les objets proches bougent et grossissent plus que le fond.
def cam_params(u, cx, cy, side):
    if u < 0.84: s = eout(u / 0.84) * 0.9 + 0.1 * (u / 0.84); back = 0.0
    else: b = (u - 0.84) / 0.16; s = 1 - b * b; back = b
    gx = cx + (W / 2 - cx) * 0.25 * s; gy = cy + (H * 0.5 - cy) * 0.25 * s
    return dict(s=s, back=back, S=1 + 0.22 * s, kd=0.16 * s, Lx=-side * 52 * s, Ly=-12 * s,
                roll=math.radians(-1.4 * side * s), gx=gx, gy=gy, cx=cx, cy=cy)

def fwd(x, y, dinv, c):
    f = c['S'] * (1 + c['kd'] * dinv)
    qx = (x - c['cx']) * f + c['Lx'] * dinv; qy = (y - c['cy']) * f + c['Ly'] * dinv
    cr, sr = math.cos(c['roll']), math.sin(c['roll'])
    return qx * cr - qy * sr + c['gx'], qx * sr + qy * cr + c['gy']

# ---------------------------------------------------------------- particules (espace écran + profondeur)
def make_particles(seed, cx, cy, ic, warm, rx=100, ry=150):
    rng = np.random.default_rng(seed)
    n1, n2, n3 = 90, 250, 9
    # éclat : naissent sur le personnage, s'écartent en ralentissant
    a = rng.uniform(0, 2 * np.pi, n1); sp = rng.uniform(120, 520, n1)
    rr0 = rng.uniform(0.55, 0.95, n1)   # naissent sur le contour du perso et s'en échappent (aura)
    p1 = dict(x=cx + np.cos(a) * rx * rr0, y=cy + np.sin(a) * ry * rr0, vx=np.cos(a) * sp, vy=np.sin(a) * sp * 0.8 - 40,
              tau=rng.uniform(0.2, 0.42, n1), ip=ic + rng.normal(0, 0.06, n1), r=rng.uniform(1.4, 3.2, n1),
              al=rng.uniform(0.7, 1.0, n1), t0=np.zeros(n1))
    # poussière lumineuse en suspension, répartie dans la profondeur
    bias = rng.random(n2) < 0.5
    p2 = dict(x=np.where(bias, rng.normal(cx, W * 0.2, n2), rng.uniform(0, W, n2)),
              y=np.where(bias, rng.normal(cy, H * 0.22, n2), rng.uniform(0, H, n2)),
              vx=rng.normal(0, 8, n2), vy=-rng.uniform(8, 34, n2), tau=np.full(n2, 1e9), ip=rng.uniform(0.05, 1.0, n2),
              r=rng.uniform(1.0, 3.0, n2), al=rng.uniform(0.35, 0.95, n2), t0=rng.uniform(0.02, 0.4, n2))
    # gros bokehs flous devant la caméra
    bx, by = [], []
    while len(bx) < n3:   # bokehs loin du perso pour ne pas le masquer
        x0, y0 = rng.uniform(-0.05, 1.05) * W, rng.uniform(-0.05, 1.05) * H
        if ((x0 - cx) / (rx * 1.8)) ** 2 + ((y0 - cy) / (ry * 1.5)) ** 2 > 1: bx.append(x0); by.append(y0)
    p3 = dict(x=np.array(bx), y=np.array(by), vx=rng.normal(0, 10, n3), vy=-rng.uniform(5, 15, n3),
              tau=np.full(n3, 1e9), ip=rng.uniform(1.2, 1.6, n3), r=rng.uniform(26, 58, n3), al=rng.uniform(0.05, 0.1, n3),
              t0=rng.uniform(0.05, 0.3, n3))
    P = {k: np.concatenate([p1[k], p2[k], p3[k]]).astype(np.float64) for k in p1}
    n = n1 + n2 + n3
    # BGR : or, cyan, blanc chaud
    pal = np.float32([[0.55, 0.85, 1.0], [1.0, 0.9, 0.5], [0.92, 0.97, 1.0]])
    pw = [0.2, 0.5, 0.3] if warm else [0.45, 0.3, 0.25]
    P['col'] = pal[rng.choice(3, n, p=pw)]
    P['ph'] = rng.uniform(0, 2 * np.pi, n); P['om'] = rng.uniform(4, 10, n)
    P['kind'] = np.concatenate([np.zeros(n1), np.ones(n2), np.full(n3, 2)])
    return P

def draw_particles(P, t, c, ic, inv_w, fade_all):
    dt = np.maximum(t - P['t0'], 0); tau = P['tau']
    x = P['x'] + P['vx'] * tau * (1 - np.exp(-dt / tau)) + np.sin(P['ph'] + dt * 1.7) * 6
    y = P['y'] + P['vy'] * tau * (1 - np.exp(-dt / tau))
    dinv = np.clip(P['ip'] - ic, -0.6, 0.9)
    px, py = fwd(x, y, dinv, c)
    zoom = c['S'] * (1 + c['kd'] * dinv)
    rad = P['r'] * (0.6 + 0.9 * np.clip(P['ip'], 0, 1)) * zoom
    coc = np.abs(P['ip'] - ic) * 5.0
    life = np.clip(dt / 0.1, 0, 1)
    tw = 0.6 + 0.4 * np.sin(P['ph'] + P['om'] * t)
    alpha = P['al'] * life * tw * fade_all
    ix = np.clip(px.astype(int), 0, W - 1); iy = np.clip(py.astype(int), 0, H - 1)
    occl = (P['ip'] < inv_w[iy, ix] - 0.06) & (P['kind'] != 2)
    sharp = np.zeros((H, W, 3), np.float32); soft = np.zeros((H, W, 3), np.float32); bok = np.zeros((H, W, 3), np.float32)
    for i in range(len(alpha)):
        if occl[i] or alpha[i] < 0.02: continue
        X, Y = px[i], py[i]
        if X < -90 or X > W + 90 or Y < -90 or Y > H + 90: continue
        col = P['col'][i]; ctr = (int(X * 4), int(Y * 4))
        if P['kind'][i] == 2:
            R = rad[i]
            cv2.circle(bok, ctr, int(R * 4), (col * alpha[i]).tolist(), -1, cv2.LINE_AA, 2)
            cv2.circle(bok, ctr, int(R * 4), (col * alpha[i] * 0.9).tolist(), 4, cv2.LINE_AA, 2)
            continue
        R = rad[i] + coc[i] * 2.0
        a = alpha[i] * min(1.0, (rad[i] / R) ** 1.2 * 1.2)
        if coc[i] < 0.9:
            cv2.circle(sharp, ctr, max(1, int(R * 4)), (col * a).tolist(), -1, cv2.LINE_AA, 2)
        else:
            cv2.circle(soft, ctr, max(1, int(R * 4)), (col * a * 0.9).tolist(), -1, cv2.LINE_AA, 2)
    soft = cv2.GaussianBlur(soft, (0, 0), 1.4)
    bok = cv2.GaussianBlur(bok, (0, 0), 2.2)
    core = sharp + soft
    glow = cv2.GaussianBlur(core, (0, 0), 4) * 1.4 + cv2.GaussianBlur(core, (0, 0), 14) * 0.9
    return core * 1.3 + glow + bok

# ---------------------------------------------------------------- un arrêt du temps
def render_freeze(img, cx, cy, seed, ry=150, rx=100):
    inv = depth(img)
    ic = float(np.median(inv[max(0, int(cy) - 12):int(cy) + 12, max(0, int(cx) - 12):int(cx) + 12]))
    dmap = np.clip(inv - ic, -0.6, 0.4).astype(np.float32)   # premiers plans très proches : parallaxe bornée
    dmap = cv2.GaussianBlur(dmap, (0, 0), 3.0)           # adoucit les marches de profondeur (moins d'étirements)
    side = 1 if cx < W / 2 else -1
    m = img.reshape(-1, 3).mean(0); warm = m[2] > m[0] * 1.2
    P = make_particles(seed, cx, cy, ic, warm, rx, ry)
    frames = []
    dh = dmap[::hs, ::hs]
    for k in range(NF):
        u = k / (NF - 1); t = k / FPS
        c = cam_params(u, cx, cy, side); back = c['back']
        fx, fy = fwd(xh, yh, dh, c)
        dx = (fx - xh).astype(np.float32); dy = (fy - yh).astype(np.float32)
        mx, my = xh.copy(), yh.copy()
        for _ in range(5):
            ddx = cv2.remap(dx, mx / hs, my / hs, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            ddy = cv2.remap(dy, mx / hs, my / hs, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            mx, my = (xh - ddx).astype(np.float32), (yh - ddy).astype(np.float32)
        MX = cv2.resize(mx, (W, H)); MY = cv2.resize(my, (W, H))
        if k < 16:   # onde de choc
            e = k / 15; R = 40 + 1500 * eout(e); amp = 14 * (1 - e) ** 1.5
            rx, ry = MX - cx, MY - cy; rr = np.sqrt(rx * rx + ry * ry) + 1e-3
            wv = np.exp(-((rr - R) / 55) ** 2) * amp
            MX = (MX - rx / rr * wv).astype(np.float32); MY = (MY - ry / rr * wv).astype(np.float32)
        out = cv2.remap(img, MX, MY, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        inv_w = cv2.remap(inv, MX, MY, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        foc = ease(u / 0.3) * (1 - back)
        of = out.astype(np.float32)
        coc = np.zeros((H, W), np.float32)
        if foc > 0.01:
            coc = np.clip(np.abs(inv_w - ic) * 3.6 - 0.15, 0, 1) * foc
            ex = (xx - c['gx']) / (rx * c['S'] * 1.15); ey = (yy - c['gy']) / (ry * c['S'] * 1.1)
            coc = coc * np.clip((np.sqrt(ex * ex + ey * ey) - 0.75) / 0.5, 0, 1)   # le perso reste net
            b1 = cv2.GaussianBlur(out, (0, 0), 2.4).astype(np.float32); b2 = cv2.GaussianBlur(out, (0, 0), 6.0).astype(np.float32)
            c3 = coc[..., None]; w1 = np.clip(c3 * 2, 0, 1); w2 = np.clip(c3 * 2 - 1, 0, 1)
            of = of * (1 - w1) + b1 * w1; of = of * (1 - w2) + b2 * w2
        g = ease(u / 0.18) * (1 - back)
        if g > 0.01:
            L = of.mean(2, keepdims=True)
            bgw = (np.clip(coc * 1.5, 0, 1) * 0.55 + 0.2)[..., None] * g
            of = of * (1 - bgw * 0.45) + L * bgw * 0.45
            of = of * (1 + np.float32([0.05, 0.0, -0.035]) * bgw)
            rr = np.sqrt(((xx - c['gx']) / W) ** 2 + ((yy - c['gy']) / H) ** 2)
            vig = 1 - g * 0.4 * np.clip((rr - 0.13) / 0.55, 0, 1) ** 1.3
            of = of * vig[..., None] * (1 + 0.05 * g)
        fade_all = 1.0 if u < 0.84 else max(0.0, 1 - (u - 0.84) / 0.12)
        of = of + draw_particles(P, t, c, ic, inv_w, fade_all) * 255
        if k < 14:
            e = k / 13; R = 40 + 1500 * eout(e)
            ring = np.zeros((H, W), np.float32)
            cv2.circle(ring, (int(cx), int(cy)), int(R), 1.0, 3, cv2.LINE_AA)
            ring = cv2.GaussianBlur(ring, (0, 0), 2.2) * 2.0 + cv2.GaussianBlur(ring, (0, 0), 10) * 2.2
            of = of + ring[..., None] * np.float32([255, 240, 205]) * (1 - e) ** 1.3 * 0.75
        fl = 0.26 * math.exp(-k / 2.0)
        if fl > 0.01: of = of * (1 - fl) + 255 * fl
        o8 = np.clip(of, 0, 255).astype(np.uint8)
        if back > 0:
            o8 = zoom_blur(o8, (c['gx'], c['gy']), 0.09 * math.sin(math.pi * min(1, back * 1.05)) + 0.015 * back)
        if back > 0 or k < 6:
            a = (back if back > 0 else (1 - k / 6)) * 5
            bch, gch, rch = cv2.split(o8)
            M1 = np.float32([[1 + a / W, 0, -a / 2], [0, 1 + a / H, -a / 2 * H / W]])
            M2 = np.float32([[1 - a / W, 0, a / 2], [0, 1 - a / H, a / 2 * H / W]])
            o8 = cv2.merge([cv2.warpAffine(bch, M1, (W, H), borderMode=cv2.BORDER_REFLECT), gch,
                            cv2.warpAffine(rch, M2, (W, H), borderMode=cv2.BORDER_REFLECT)])
        frames.append(o8)
    return frames


# ---------------------------------------------------------------- son
SR = 48000
def build_audio(ev_idx_frames, n_src, src_fps, out_wav, keep=None):
    from scipy import signal
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', SRC, '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    A = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    rng = np.random.default_rng(3)
    sec = lambda x: int(round(x * SR))
    def lp(x, fc): b, a = signal.butter(2, fc / (SR / 2), 'low'); return signal.lfilter(b, a, x, axis=0)
    def bp(x, lo, hi): b, a = signal.butter(2, [lo / (SR / 2), hi / (SR / 2)], 'band'); return signal.lfilter(b, a, x, axis=0)
    def st(m): return np.stack([m, m], 1).astype(np.float32)
    def sweep(n, f0, f1):
        x = rng.standard_normal(n).astype(np.float32); y = np.zeros_like(x); blk = 512; nb = int(math.ceil(n / blk)); zi = None
        for i in range(nb):
            f = f0 * (f1 / f0) ** (i / max(1, nb - 1))
            b, a = signal.butter(2, [max(30, f * 0.6) / (SR / 2), min(SR / 2 - 100, f * 1.6) / (SR / 2)], 'band')
            if zi is None: zi = signal.lfilter_zi(b, a) * 0
            y[i * blk:(i + 1) * blk], zi = signal.lfilter(b, a, x[i * blk:(i + 1) * blk], zi=zi)
        return y / (np.abs(y).max() + 1e-6)
    def hit():
        n = sec(1.3); t = np.arange(n) / SR
        s = np.sin(2 * np.pi * np.cumsum(60 * np.exp(-t * 1.6) + 26) / SR) * np.exp(-t * 2.8)
        c = bp(rng.standard_normal(n), 100, 3000) * np.exp(-t * 40) * 0.4
        return st(np.tanh((s + c) * 1.6) * 0.75)
    def shimmer(d):
        n = sec(d); t = np.arange(n) / SR
        y = sum(np.sin(2 * np.pi * f * t + p) * (0.5 + 0.5 * np.sin(2 * np.pi * r * t)) for f, p, r in ((2093, 0, 3.1), (2637, 1, 4.3), (3136, 2, 2.7), (4186, .5, 5.2)))
        e = np.clip(t / 0.25, 0, 1) * np.clip((d - t) / 0.3, 0, 1)
        return st(y / 4 * e * 0.07)
    def whoosh(d, up):
        n = sec(d); y = sweep(n, 300 if up else 4000, 4000 if up else 300)
        t = np.linspace(0, 1, n); e = (t ** 2.2 if up else (1 - t) ** 1.5) * np.clip(t / 0.05, 0, 1)
        return st(y * e * 0.42)
    # assemblage : la piste source avance avec l'image, inserts = passage suivant étouffé et plus bas
    out = []; pos = 0
    for f_idx in sorted(ev_idx_frames):
        cut = sec((f_idx + 1) / src_fps)
        out.append(A[pos:cut]); pos = cut
        seg = A[cut:cut + sec(D)]
        if len(seg) < sec(D): seg = np.concatenate([seg, np.zeros((sec(D) - len(seg), 2), np.float32)])
        m = lp(lp(seg, 520), 520)
        r = m.copy()
        for dl, g in [(0.071, 0.5), (0.113, 0.38), (0.173, 0.28), (0.251, 0.2), (0.367, 0.14)]:
            kk = sec(dl); r[kk:] += m[:-kk] * g
        n = len(r); tt = np.arange(n) / SR
        # passage progressif du son normal au son étouffé (évite le clic), puis niveau plus bas
        xf = np.clip(tt / 0.09, 0, 1)[:, None]
        lvl = (1 - 0.62 * xf) * np.clip((D - tt) / 0.05, 0.0, 1)[:, None]
        ins = (seg * (1 - xf) + r * 0.55 * xf) * lvl
        ins = ins.astype(np.float32)
        ins[:len(h := hit())] += h[:n]
        ins += shimmer(D)[:n]
        wb = whoosh(0.5, True); ins[n - len(wb):] += wb
        out.append(ins)
    out.append(A[pos:])
    Y = np.concatenate(out)
    # impact à la reprise
    Y = Y.astype(np.float32)
    peak = np.abs(Y).max()
    if peak > 0.98: Y = np.tanh(Y / peak * 1.2) * 0.97
    import wave
    with wave.open(out_wav, 'wb') as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((np.clip(Y, -1, 1) * 32767).astype(np.int16).tobytes())

# ---------------------------------------------------------------- principal
def main():
    src = read_src(); n = len(src); sfps = 30.0
    print('source', n, 'images', flush=True)
    evs = [(int(round(t * sfps)), x * SX, y * SY, i, ry * SY, rx * SX) for i, (t, x, y, ry, rx) in enumerate(EVENTS)]
    if TEST is not None: evs = [evs[TEST]]
    ev_map = {e[0]: e for e in evs}
    if STILLS:
        os.makedirs('stills5', exist_ok=True)
        for fi, cx, cy, i, ry, rx in evs:
            fr = render_freeze(up(src[fi]), cx, cy, 100 + i, ry, rx)
            for k in (0, 6, 20, 45, 70, NF - 6, NF - 1):
                cv2.imwrite(f'stills5/e{i:02d}_{k:02d}.jpg', fr[k], [cv2.IMWRITE_JPEG_QUALITY, 90])
            print('stills', i, flush=True)
        return
    lo, hi = 0, n
    if TEST is not None: lo, hi = max(0, evs[0][0] - 45), min(n, evs[0][0] + 46)
    wav = OUTF + '.wav'
    build_audio([e[0] for e in evs], n, sfps, wav)
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-ss', f'{lo / sfps:.4f}', '-i', wav, '-map', '0:v', '-map', '1:a', '-shortest',
                           '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
                           '-c:a', 'aac', '-b:a', '320k', '-movflags', '+faststart', OUTF], stdin=subprocess.PIPE)
    for fi in range(lo, hi):
        im = up(src[fi]); b = im.tobytes()
        ff.stdin.write(b); ff.stdin.write(b)          # 30 → 60 i/s sans interpolation (aucun artefact)
        if fi in ev_map:
            _, cx, cy, i, ry, rx = ev_map[fi]
            for fr in render_freeze(im, cx, cy, 100 + i, ry, rx): ff.stdin.write(fr.tobytes())
            print('freeze', i, 'ok', flush=True)
    ff.stdin.close(); ff.wait(); print('DONE', OUTF, flush=True)

if __name__ == '__main__':
    main()
