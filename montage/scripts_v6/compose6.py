# v6 : vidéo d'origine intacte + séquence 3D « bullet-cam » insérée juste après l'animation
# de caméra de 1:54 (dernière image 3443), avant le plan à la lunette.
# usage : python3 compose6.py src.mov renders_dir out.mp4 [--test]
import sys, os, math, subprocess, wave
import numpy as np, cv2
from scipy import signal

SRC, RD, OUTF = sys.argv[1], sys.argv[2], sys.argv[3]
TEST = '--test' in sys.argv
W, H, FPS, SFPS = 1920, 886, 60, 30.0
CUT = 3443            # dernière image de l'animation de l'utilisateur
F_HIT = 114           # image d'impact dans le rendu
rend = sorted(os.path.join(RD, f) for f in os.listdir(RD) if f.endswith('.png'))
NI = len(rend); DI = NI / FPS
print('insert', NI, 'images', DI, 's', flush=True)

def up(im):
    x = cv2.resize(im, (W, H), interpolation=cv2.INTER_LANCZOS4)
    b = cv2.GaussianBlur(x, (0, 0), 1.2)
    return cv2.addWeighted(x, 1.35, b, -0.35, 0)

def post(img, k):
    o = img.astype(np.float32)
    # tir : éclair blanc chaud très bref
    fs = 0.32 * math.exp(-k / 1.6)
    # impact : flash + secousse + aberration chromatique
    d = k - F_HIT
    fi = 0.65 * math.exp(-d / 3.0) if d >= 0 else 0.0
    if fi > 0.01 or fs > 0.01:
        a = max(fs, fi)
        o = o * (1 - a) + np.float32([235, 245, 255]) * a
    if 0 <= d < 14:
        amp = 9 * math.exp(-d / 4)
        M = np.float32([[1.02, 0, -W * 0.01 + amp * math.sin(d * 2.3)], [0, 1.02, -H * 0.01 + amp * math.cos(d * 3.1)]])
        o = cv2.warpAffine(o, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        c = 6 * math.exp(-d / 5)
        b, g, r = cv2.split(o)
        b = cv2.warpAffine(b, np.float32([[1, 0, -c], [0, 1, 0]]), (W, H), borderMode=cv2.BORDER_REFLECT)
        r = cv2.warpAffine(r, np.float32([[1, 0, c], [0, 1, 0]]), (W, H), borderMode=cv2.BORDER_REFLECT)
        o = cv2.merge([b, g, r])
    # léger vignettage cinéma pendant la séquence
    return np.clip(o * VIG, 0, 255).astype(np.uint8)

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
rr = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
VIG = (1 - 0.28 * np.clip((rr - 0.25) / 0.45, 0, 1) ** 1.5)[..., None]

# ---------------------------------------------------------------- son
SR = 48000
sec = lambda x: int(round(x * SR))
rng = np.random.default_rng(11)
def lp(x, fc): b, a = signal.butter(2, fc / (SR / 2), 'low'); return signal.lfilter(b, a, x, axis=0)
def hp(x, fc): b, a = signal.butter(2, fc / (SR / 2), 'high'); return signal.lfilter(b, a, x, axis=0)
def bp(x, lo, hi): b, a = signal.butter(2, [lo / (SR / 2), hi / (SR / 2)], 'band'); return signal.lfilter(b, a, x, axis=0)
def pan(m, p0, p1):
    p = np.linspace(p0, p1, len(m)); return np.stack([m * np.sqrt((1 - p) / 2), m * np.sqrt((1 + p) / 2)], 1).astype(np.float32)

def gunshot():
    n = sec(0.9); t = np.arange(n) / SR
    crack = bp(rng.standard_normal(n), 900, 9000) * np.exp(-t * 60)
    body = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-t * 6) + 35) / SR) * np.exp(-t * 7)
    tail = lp(rng.standard_normal(n), 900) * np.exp(-t * 4) * 0.25
    return pan(np.tanh((crack * 1.4 + body + tail) * 1.5) * 0.55, 0.3, 0.1)

def flyby(d):
    """sifflement de balle au ralenti : bruit filtré + ton glissant, effet Doppler, panoramique"""
    n = sec(d); t = np.arange(n) / SR
    f = 700 + 500 * np.sin(np.pi * t / d)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR + 0.6 * np.sin(2 * np.pi * 23 * t))
    air = bp(rng.standard_normal(n), 500, 4000)
    air = air / (np.abs(air).max() + 1e-6)
    e = np.clip(t / 0.15, 0, 1) * np.clip((d - t) / 0.08, 0, 1) * (0.55 + 0.45 * np.sin(np.pi * t / d))
    spin = 0.75 + 0.25 * np.sin(2 * np.pi * 9 * t)          # « rotation » audible
    return pan((tone * 0.25 + air * 0.6) * e * spin * 0.32, -0.6, 0.6)

def impact():
    n = sec(1.2); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * np.cumsum(70 * np.exp(-t * 2.5) + 30) / SR) * np.exp(-t * 3.2)
    c = bp(rng.standard_normal(n), 150, 5000) * np.exp(-t * 30) * 0.7
    sq = bp(rng.standard_normal(n), 2000, 7000) * np.exp(-t * 18) * 0.25
    return pan(np.tanh((s + c + sq) * 1.8) * 0.8, 0.1, -0.1)

def build_audio(wav):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', SRC, '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    A = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
    cut = sec((CUT + 1) / SFPS); n = sec(DI)
    seg = A[cut:cut + n]
    m = lp(lp(seg, 480), 480); r = m.copy()
    for dl, g in [(0.071, 0.5), (0.113, 0.38), (0.173, 0.28), (0.251, 0.2), (0.367, 0.14)]:
        k = sec(dl); r[k:] += m[:-k] * g
    tt = np.arange(n) / SR
    xf = np.clip(tt / 0.08, 0, 1)[:, None]
    lvl = (1 - 0.68 * xf) * np.clip((DI - tt) / 0.04, 0, 1)[:, None]
    ins = ((seg * (1 - xf) + r * 0.5 * xf) * lvl).astype(np.float32)
    def put(clip, at):
        i = sec(at); j = min(n, i + len(clip)); ins[i:j] += clip[:j - i]
    put(gunshot(), 0.0)
    put(flyby(F_HIT / FPS - 0.12), 0.1)
    put(impact(), F_HIT / FPS - 0.01)
    Y = np.concatenate([A[:cut], ins, A[cut:]])
    pk = np.abs(Y).max()
    if pk > 0.98: Y = np.tanh(Y / pk * 1.2) * 0.97
    with wave.open(wav, 'wb') as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((np.clip(Y, -1, 1) * 32767).astype(np.int16).tobytes())

def main():
    cap = cv2.VideoCapture(SRC)
    lo, hi = (CUT - 60, CUT + 61) if TEST else (0, 10 ** 9)
    wav = OUTF + '.wav'; build_audio(wav)
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-ss', f'{max(0, lo) / SFPS:.4f}', '-i', wav, '-map', '0:v', '-map', '1:a', '-shortest',
                           '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
                           '-c:a', 'aac', '-b:a', '320k', '-movflags', '+faststart', OUTF], stdin=subprocess.PIPE)
    fi = 0
    while True:
        ok, im = cap.read()
        if not ok or fi >= hi: break
        if fi >= lo:
            b = up(im).tobytes(); ff.stdin.write(b); ff.stdin.write(b)
            if fi == CUT:
                for k, p in enumerate(rend):
                    ff.stdin.write(post(cv2.imread(p), k).tobytes())
                print('insert ok', flush=True)
        fi += 1
    ff.stdin.close(); ff.wait(); print('DONE', OUTF, flush=True)

if __name__ == '__main__':
    main()
