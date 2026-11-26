# Bande-son v3 : musique/jeu d'origine + inserts calés au temps + design sonore synthétisé
# usage: python3 audio3.py src.mov out.wav
import sys, os, subprocess, math, wave
import numpy as np
from scipy import signal
sys.path.insert(0, os.path.dirname(__file__))
import timeline3 as T

SR = 48000
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', sys.argv[1], '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
A = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
rng = np.random.default_rng(7)
sec = lambda x: int(round(x * SR))


def bp(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), hi / (SR / 2)], 'band'); return signal.lfilter(b, a, x, axis=0)
def lp(x, fc, order=2):
    b, a = signal.butter(order, fc / (SR / 2), 'low'); return signal.lfilter(b, a, x, axis=0)
def env(n, att, rel, shape=2.0):
    t = np.linspace(0, 1, n); return np.clip(t / max(att, 1e-4), 0, 1) ** shape * np.clip((1 - t) / max(rel, 1e-4), 0, 1) ** shape
def stereo(m, p0=0.0, p1=0.0):
    p = np.linspace(p0, p1, len(m)); return np.stack([m * np.sqrt((1 - p) / 2), m * np.sqrt((1 + p) / 2)], 1).astype(np.float32)
def sweep(x, f0, f1):
    y = np.zeros_like(x); blk = 1024; nb = int(math.ceil(len(x) / blk)); zi = None
    for i in range(nb):
        f = f0 * (f1 / f0) ** (i / max(1, nb - 1))
        b, a = signal.butter(2, [max(30, f * 0.6) / (SR / 2), min(SR / 2 - 100, f * 1.6) / (SR / 2)], 'band')
        if zi is None: zi = signal.lfilter_zi(b, a) * 0
        y[i * blk:(i + 1) * blk], zi = signal.lfilter(b, a, x[i * blk:(i + 1) * blk], zi=zi)
    return y
def norm(x): return x / (np.abs(x).max() + 1e-6)

def whoosh(d=0.45, up=True, g=0.5, p0=-0.7, p1=0.7):
    n = sec(d); y = sweep(rng.standard_normal(n).astype(np.float32), 300 if up else 3500, 3500 if up else 300)
    return stereo(norm(y * env(n, 0.7 if up else 0.15, 0.3 if up else 0.85, 1.5)) * g, p0, p1)
def boom(d=1.6, g=0.9, f0=52):
    n = sec(d); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * np.cumsum(f0 * np.exp(-t * 1.3) + 28) / SR) * np.exp(-t * 2.4)
    c = bp(rng.standard_normal(n), 80, 2500) * np.exp(-t * 45) * 0.5
    return stereo(np.tanh((s + c) * 1.7).astype(np.float32) * g)
def sub_swell(d, g=0.5):
    n = sec(d); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * 38 * t) * (t / d) ** 2 * np.clip((d - t) / 0.08, 0, 1)
    return stereo((s * g).astype(np.float32))
def riser(d, g=0.4):
    n = sec(d); t = np.arange(n) / SR
    x = norm(sweep(rng.standard_normal(n).astype(np.float32), 400, 7000)); f = 150 * (6 ** (t / d))
    y = (x * 0.7 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3) * (t / d) ** 2.2
    return stereo(y.astype(np.float32) * g)
def click(g=0.5, f=3200, d=0.05):
    n = sec(d); t = np.arange(n) / SR
    y = bp(rng.standard_normal(n), 1500, 9000) * np.exp(-t * 160) + np.sin(2 * np.pi * f * t) * np.exp(-t * 90) * 0.6
    return stereo(norm(y).astype(np.float32) * g)
def bolt(g=0.55):
    """manipulation de culasse : levée, recul, avance, verrouillage"""
    out = np.zeros((sec(0.6), 2), np.float32)
    for t0, f, gg in [(0.0, 2600, 0.8), (0.12, 1800, 0.6), (0.30, 2200, 0.7), (0.44, 3400, 1.0)]:
        c = click(g * gg, f); i = sec(t0); out[i:i + len(c)] += c
    sl = bp(rng.standard_normal(sec(0.14)), 900, 5000) * env(sec(0.14), 0.3, 0.6) * 0.25
    out[sec(0.14):sec(0.14) + len(sl)] += stereo(sl.astype(np.float32) * g)
    out[sec(0.32):sec(0.32) + len(sl)] += stereo(sl.astype(np.float32) * g)
    return out
def digital(d=0.5, g=0.35):
    """son de transition 3D : balayage FM numérique"""
    n = sec(d); t = np.arange(n) / SR
    car = 400 + 2600 * (t / d) ** 1.5
    y = np.sin(2 * np.pi * np.cumsum(car) / SR + 3 * np.sin(2 * np.pi * 90 * t)) * env(n, 0.2, 0.5, 1.2)
    return stereo(y.astype(np.float32) * g, 0.6, -0.6)
def whizz(d, g=0.5):
    n = sec(d); t = np.arange(n) / SR
    f = 1500 - 900 / (1 + np.exp(-(t - d * 0.8) * 18))
    y = (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35 + norm(bp(rng.standard_normal(n), 2000, 9000)) * 0.6) * (np.exp(-((t - d * 0.82) / (d * 0.22)) ** 2) + 0.15 * t / d)
    return stereo(y.astype(np.float32) * g, 0.8, -0.9)
def muffle(x, fc=700):
    y = lp(x, fc); r = y.copy()
    for d, g in [(0.083, 0.45), (0.131, 0.33), (0.197, 0.25), (0.293, 0.17)]:
        k = sec(d); r[k:] += y[:-k] * g
    return (r * 0.8).astype(np.float32)
def fade(x, a=0.01, b=0.01):
    x = x.copy(); na, nb = sec(a), sec(b)
    if na: x[:na] *= np.linspace(0, 1, na)[:, None]
    if nb: x[-nb:] *= np.linspace(1, 0, nb)[:, None]
    return x
def add(buf, clip, at):
    i = sec(at)
    if i < 0: clip = clip[-i:]; i = 0
    j = min(len(buf), i + len(clip)); buf[i:j] += clip[:j - i]

starts, TOTAL = T.seg_starts()
OUT = np.zeros((sec(TOTAL) + SR, 2), np.float32)
for t0, kind, dur, p in starts:
    if kind == 'src':
        add(OUT, fade(A[sec(p['t0']):sec(p['t1'])], 0.006, 0.006), t0)
    elif kind == 'slow':
        Dn = (T.SLOW_N + T.SNIPER_N) / T.FPS
        add(OUT, fade(muffle(A[sec(9.66 - Dn):sec(9.66)], 750), 0.03, 0.03) * 0.85, t0)
        add(OUT, riser(dur, 0.3), t0)
        for k in range(3):
            add(OUT, boom(0.45, 0.32), t0 + 0.12 + k * dur / 3)
        tn = t0 + dur; SN = T.SNIPER_N / T.FPS
        add(OUT, boom(1.6, 0.85), tn); add(OUT, whoosh(0.35, False, 0.45), tn)
        add(OUT, whizz(SN - 0.35, 0.55), tn + 0.08)
        add(OUT, boom(1.0, 0.8), tn + (T.SNIPER_N - 15) / T.FPS)
        add(OUT, whoosh(0.3, True, 0.4), tn + SN - 0.28)
    elif kind in ('weapon', 'freeze', 'studio', 'bullet', 'replica'):
        at, L = p['at'], p['beats'] * T.BEAT
        loop = A[sec(at - L):sec(at)]
        if kind in ('freeze', 'bullet'):
            m = muffle(loop, 650 if kind == 'freeze' else 900) * 0.85
        else:   # cinématiques : musique pleine mais filtrée + basses renforcées
            m = lp(loop, 5000).astype(np.float32) * 0.8 + lp(loop, 120).astype(np.float32) * 0.6
        add(OUT, fade(m, 0.02, 0.03), t0)
        add(OUT, boom(1.4, 0.7), t0)
        add(OUT, whoosh(0.35, False, 0.4), t0)
        add(OUT, digital(0.45, 0.25), t0 + 0.02)
        if kind == 'weapon':
            for fr in (34, 80, 100, 140, 168):          # changements de plan caméra
                add(OUT, whoosh(0.32, True, 0.3, 0.6, -0.6), t0 + fr / T.FPS - 0.25)
            add(OUT, bolt(0.6), t0 + 1.1); add(OUT, click(0.4, 2900), t0 + 2.5)
            add(OUT, sub_swell(0.8, 0.4), t0 + dur - 0.8)
        elif kind == 'studio':
            add(OUT, riser(dur - 0.2, 0.25), t0 + 0.1); add(OUT, sub_swell(1.2, 0.45), t0 + dur - 1.2)
        elif kind == 'replica':
            add(OUT, whoosh(1.0, True, 0.3, -0.8, 0.8), t0 + 0.3); add(OUT, bolt(0.55), t0 + 0.9)
            add(OUT, riser(0.9, 0.3), t0 + dur - 0.9)
        elif kind == 'freeze':
            add(OUT, riser(T.BEAT * 2, 0.35), t0 + dur - T.BEAT * 2)
        else:
            add(OUT, whizz(dur - 0.1, 0.55), t0 + 0.05)
        add(OUT, whoosh(0.3, True, 0.42), t0 + dur - 0.28)
        add(OUT, boom(0.8, 0.55), t0 + dur)

# écran flottant : sortie du plein écran, balayage 3D, ruée vers l'écran
fo = T.src_to_out(T.FLOAT_A)
add(OUT, whoosh(0.6, False, 0.4), fo + 0.15); add(OUT, digital(0.6, 0.3), fo + 0.2)
add(OUT, sub_swell(1.3, 0.4), fo + 0.4); add(OUT, whoosh(0.5, True, 0.5), fo + 1.4); add(OUT, boom(0.9, 0.6), fo + 1.86)
# éliminations : impacts graves ; coupes : whoosh / rotation
for ks, kind in T.KILLS:
    o = T.src_to_out(ks)
    if o is not None:
        add(OUT, boom(0.55, 0.4 if kind != 'sniper' else 0.6, 60), o)
for c, style in T.CUTS:
    o = T.src_to_out(c)
    if o is not None:
        add(OUT, whoosh(0.3, True, 0.3) if style == 'push' else digital(0.3, 0.22), o - 0.22)

OUT = OUT[:sec(TOTAL)]
peak = np.abs(OUT).max()
OUT = np.tanh(OUT / peak * 1.35) / np.tanh(1.35) * 0.93
OUT[:sec(0.25)] *= np.linspace(0, 1, sec(0.25))[:, None]
OUT[-sec(0.45):] *= np.linspace(1, 0, sec(0.45))[:, None]
with wave.open(sys.argv[2], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((OUT * 32767).astype(np.int16).tobytes())
print('audio3', round(TOTAL, 3))
