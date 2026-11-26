# Bande-son : musique/jeu d'origine + inserts étouffés (synchro au tempo) + SFX synthétisés
# usage: python3 audio.py src.mov out.wav
import sys, os, subprocess, math
import numpy as np
from scipy import signal
sys.path.insert(0, os.path.dirname(__file__))
import timeline as T

SR = 48000
src, out = sys.argv[1], sys.argv[2]
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                     capture_output=True, check=True).stdout
A = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
rng = np.random.default_rng(3)


def sec(x):
    return int(round(x * SR))


def bandnoise(n, lo, hi):
    b, a = signal.butter(2, [lo / (SR / 2), hi / (SR / 2)], 'band')
    return signal.lfilter(b, a, rng.standard_normal(n)).astype(np.float32)


def env(n, attack, release, shape=2.0):
    t = np.linspace(0, 1, n)
    a = np.clip(t / max(attack, 1e-4), 0, 1) ** shape
    r = np.clip((1 - t) / max(release, 1e-4), 0, 1) ** shape
    return a * r


def sweep_filter(x, f0, f1):
    """filtre passe-bande glissant (traitement par blocs)."""
    y = np.zeros_like(x); blk = 1024
    nb = int(math.ceil(len(x) / blk))
    zi = None
    for i in range(nb):
        f = f0 * (f1 / f0) ** (i / max(1, nb - 1))
        b, a = signal.butter(2, [max(30, f * 0.6) / (SR / 2), min(SR / 2 - 100, f * 1.6) / (SR / 2)], 'band')
        seg = x[i * blk:(i + 1) * blk]
        if zi is None or zi.shape[0] != max(len(a), len(b)) - 1:
            zi = signal.lfilter_zi(b, a) * 0
        y[i * blk:(i + 1) * blk], zi = signal.lfilter(b, a, seg, zi=zi)
    return y


def stereo(m, pan_from=0.0, pan_to=0.0):
    p = np.linspace(pan_from, pan_to, len(m))
    return np.stack([m * np.sqrt((1 - p) / 2), m * np.sqrt((1 + p) / 2)], 1).astype(np.float32)


def whoosh(d=0.45, up=True, gain=0.5):
    n = sec(d)
    x = rng.standard_normal(n).astype(np.float32)
    y = sweep_filter(x, 300 if up else 3000, 3000 if up else 300)
    y *= env(n, 0.7 if up else 0.15, 0.3 if up else 0.85, 1.5)
    y /= np.abs(y).max() + 1e-6
    return stereo(y * gain, -0.7, 0.7)


def boom(d=1.6, gain=0.9):
    n = sec(d); t = np.arange(n) / SR
    f = 55 * np.exp(-t * 1.2) + 30
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6)
    click = bandnoise(n, 80, 2500) * np.exp(-t * 40) * 0.6
    y = np.tanh((s + click) * 1.6)
    return stereo(y.astype(np.float32) * gain)


def riser(d, gain=0.45):
    n = sec(d); t = np.arange(n) / SR
    x = sweep_filter(rng.standard_normal(n).astype(np.float32), 400, 6000)
    x /= np.abs(x).max() + 1e-6
    f = 140 * (6 ** (t / d))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35
    y = (x * 0.7 + tone) * (t / d) ** 2.2
    return stereo(y.astype(np.float32) * gain)


def whizz(d, gain=0.55):
    """sifflement de balle avec effet Doppler, de droite à gauche"""
    n = sec(d); t = np.arange(n) / SR
    f = 1500 - 900 * (1 / (1 + np.exp(-(t - d * 0.8) * 18)))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    hiss = bandnoise(n, 2000, 9000)
    hiss /= np.abs(hiss).max() + 1e-6
    a = np.exp(-((t - d * 0.82) / (d * 0.22)) ** 2) + 0.15 * (t / d)
    y = (tone * 0.35 + hiss * 0.6) * a
    return stereo(y.astype(np.float32) * gain, 0.8, -0.9)


def muffle(x, cutoff=650):
    b, a = signal.butter(2, cutoff / (SR / 2), 'low')
    y = signal.lfilter(b, a, x, axis=0)
    # pseudo-réverbération (échos décroissants)
    r = y.copy()
    for d, g in [(0.083, 0.45), (0.131, 0.33), (0.197, 0.25), (0.293, 0.17)]:
        k = sec(d)
        r[k:] += y[:-k] * g
    return (r * 0.8).astype(np.float32)


def add(buf, clip, at):
    i = sec(at)
    if i < 0:
        clip = clip[-i:]; i = 0
    j = min(len(buf), i + len(clip))
    buf[i:j] += clip[:j - i]


def fade(x, fi=0.01, fo=0.01):
    x = x.copy()
    a, b = sec(fi), sec(fo)
    if a: x[:a] *= np.linspace(0, 1, a)[:, None]
    if b: x[-b:] *= np.linspace(1, 0, b)[:, None]
    return x


starts, total = T.seg_starts()
OUT = np.zeros((sec(total) + SR, 2), np.float32)

for t0, (kind, dur, p) in starts:
    if kind == 'intro':
        n = sec(dur)
        sea = bandnoise(n, 120, 900); sea = sea / (np.abs(sea).max() + 1e-6)
        sea *= (0.6 + 0.4 * np.sin(np.linspace(0, 5, n)) ** 2) * env(n, 0.25, 0.2, 1)
        add(OUT, stereo(sea * 0.18), t0)
        drone = np.sin(2 * np.pi * 55 * np.arange(n) / SR) * 0.12 + np.sin(2 * np.pi * 82.4 * np.arange(n) / SR) * 0.08
        add(OUT, stereo((drone * env(n, 0.4, 0.1, 1)).astype(np.float32)), t0)
        add(OUT, riser(dur - 0.3, 0.4), t0 + 0.3)
        add(OUT, boom(1.8, 0.9), t0 + dur - 0.02)
        add(OUT, whoosh(0.5, True, 0.45), t0 + dur - 0.45)
    elif kind == 'src':
        a, b = sec(p['t0']), sec(p['t1'])
        add(OUT, fade(A[a:b], 0.006, 0.006), t0)
    elif kind == 'slow':   # bloc sniper = ralenti + freeze 3D (durée = 10 temps + 0,26 s source)
        Dn = (T.SLOW_N + T.SNIPER_N) / T.FPS
        loop = A[sec(T.SNIPER_B - Dn):sec(T.SNIPER_B)]
        m = fade(muffle(loop, 750), 0.03, 0.03)
        # pendant la visée le son s'étouffe progressivement, il reste étouffé pendant le freeze
        add(OUT, m * 0.85, t0)
        add(OUT, riser(dur, 0.32), t0)
        hb = boom(0.45, 0.35)
        for k in range(3):   # battements de cœur pendant la visée
            add(OUT, hb, t0 + 0.12 + k * dur / 3)
        tn = t0 + dur
        SN = T.SNIPER_N / T.FPS
        add(OUT, boom(1.6, 0.85), tn)
        add(OUT, whoosh(0.35, False, 0.45), tn)
        add(OUT, whizz(SN - 0.35, 0.6), tn + 0.08)
        add(OUT, boom(1.0, 0.8), tn + (T.SNIPER_N - 15) / T.FPS)
        add(OUT, whoosh(0.3, True, 0.4), tn + SN - 0.28)
    elif kind == 'sniper':
        pass
    elif kind in ('freeze', 'bullet'):
        at = T.FREEZE_AT if kind == 'freeze' else T.BULLET_AT
        nb = T.FREEZE_BEATS if kind == 'freeze' else T.BULLET_BEATS
        L = nb * T.BEAT
        loop = A[sec(at - L):sec(at)]
        m = muffle(loop, 600 if kind == 'freeze' else 900)
        m = fade(m, 0.02, 0.03)
        # le son revient progressivement (filtre qui s'ouvre) sur le dernier temps
        add(OUT, m * 0.85, t0)
        add(OUT, boom(1.4, 0.75), t0)
        add(OUT, whoosh(0.35, False, 0.4), t0)
        if kind == 'freeze':
            add(OUT, riser(T.BEAT * 2, 0.35), t0 + dur - T.BEAT * 2)
        else:
            add(OUT, whizz(dur - 0.1, 0.6), t0 + 0.05)
        add(OUT, whoosh(0.3, True, 0.4), t0 + dur - 0.28)
    elif kind == 'outro':
        tail = A[sec(T.SRC_END - 1.0):sec(T.SRC_END)]
        m = muffle(tail, 500)
        m *= np.linspace(1, 0, len(m))[:, None] ** 1.5
        add(OUT, m, t0)
        add(OUT, boom(1.5, 0.6), t0)

# impacts graves sur les éliminations et souffles sur les coupes (en temps de sortie)
def src_to_out(ts):
    for t0, (kind, dur, p) in starts:
        if kind == 'src' and p['t0'] <= ts < p['t1']:
            return t0 + ts - p['t0']
    return None

for k in T.KILLS:
    o = src_to_out(k)
    if o is not None:
        add(OUT, boom(0.5, 0.32), o)
for c in T.CUTS:
    o = src_to_out(c)
    if o is not None:
        add(OUT, whoosh(0.3, True, 0.28), o - 0.25)

OUT = OUT[:sec(total)]
# mastering : compression douce + limiteur
peak = np.abs(OUT).max()
OUT = np.tanh(OUT / max(peak, 1e-6) * 1.3) / np.tanh(1.3) * 0.93
OUT[:sec(0.4)] *= np.linspace(0, 1, sec(0.4))[:, None]
OUT[-sec(0.5):] *= np.linspace(1, 0, sec(0.5))[:, None]
pcm = (OUT * 32767).astype(np.int16)
import wave
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('audio', round(total, 3), 's ->', out)
