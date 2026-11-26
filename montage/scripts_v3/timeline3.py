# Timeline du montage v3 (style cyan/turquoise). Temps source en secondes, sortie 60 fps.
FPS = 60
BEAT = 60 / 151.7
BEAT0 = 6.055
SRC_END = 30.1

# éliminations importantes (temps du tir, source) ; 'sniper' = effets lunette
KILLS = [(1.95, 'tp'), (8.72, 'sniper'), (9.70, 'sniper'), (12.55, 'fps'), (13.55, 'fps'), (14.05, 'fps'),
         (17.15, 'fps'), (18.55, 'fps'), (22.45, 'fps'), (24.95, 'fps'), (27.95, 'fps'), (28.5, 'fps'), (29.0, 'fps')]
# coupes source -> transitions (rapprochement caméra / rotation)
CUTS = [(5.0, 'push'), (5.63, 'push'), (7.9, 'spin'), (15.6, 'push'), (16.8, 'push'), (18.1, 'spin'), (25.7, 'push'), (27.0, 'spin')]
# speed ramping : ralenti juste avant le tir, accélération pendant la visée (durée conservée => synchro musique)
RAMPS = [(1.88, 0.45, 0.7), (8.62, 0.28, 0.65), (14.0, 0.28, 0.6), (17.08, 0.3, 0.6), (18.48, 0.3, 0.6),
         (22.38, 0.3, 0.6), (24.88, 0.3, 0.6), (27.88, 0.3, 0.6), (28.42, 0.2, 0.55)]
HUD_SEGS = [(7.9, 10.05), (11.6, 15.6), (16.8, 25.7), (27.0, 30.1)]
PARALLAX = [(0.0, 4.95, 15, 1), (5.65, 7.85, 10, -1), (10.25, 11.55, 17, 1), (15.75, 16.34, 12, -1), (25.75, 25.78, 1, 1)]
SCOPE_WIN = [(8.50, 8.80), (9.56, 9.72)]   # lunette ouverte (halo + distorsion)
FLOAT_A, FLOAT_N = 11.92, 120              # écran flottant : remplace 11.92 -> 13.92

SLOW_N, SNIPER_N = 78, 175                 # ralenti visée + freeze 3D balle (10 temps au total avec 0,26 s source)


def segments():
    B = lambda n: round(n * BEAT * FPS)    # inserts = nombre entier de temps
    return [
        ('src', {'t0': 0.0, 't1': 9.10}),
        ('weapon', {'n': B(8), 'at': 9.10, 'beats': 8}),
        ('src', {'t0': 9.10, 't1': 9.40}),
        ('slow', {'n': SLOW_N}),
        ('sniper', {'n': SNIPER_N}),
        ('src', {'t0': 9.66, 't1': 16.34}),
        ('freeze', {'n': B(8), 'at': 16.34, 'beats': 8}),
        ('src', {'t0': 16.34, 't1': 25.78}),
        ('studio', {'n': B(8), 'at': 25.78, 'beats': 8}),
        ('src', {'t0': 25.78, 't1': 26.50}),
        ('bullet', {'n': B(6), 'at': 26.50, 'beats': 6}),
        ('src', {'t0': 26.50, 't1': 28.90}),
        ('replica', {'n': B(6), 'at': 28.90, 'beats': 6}),
        ('src', {'t0': 28.90, 't1': SRC_END}),
    ]


def seg_starts():
    t, out = 0.0, []
    for kind, p in segments():
        dur = (p['t1'] - p['t0']) if kind == 'src' else p['n'] / FPS
        out.append((t, kind, dur, p))
        t += dur
    return out, t


def src_to_out(ts):
    st, _ = seg_starts()
    for t0, kind, dur, p in st:
        if kind == 'src' and p['t0'] <= ts < p['t1']:
            return t0 + ts - p['t0']
    return None
