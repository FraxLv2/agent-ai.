# Timeline du montage v4 (style Kaiser). Temps source en secondes, sortie 60 fps.
FPS = 60
BEAT = 0.6056                # 99,1 BPM mesuré (librosa) sur la musique de la vidéo
BEAT0 = 0.19
SRC_END = 62.7

# tirs au sniper détectés (transitoires audio + texte d'élimination), type
KILLS = [(11.01, 'sn'), (12.23, 'sn'), (12.99, 'multi'), (15.91, 'sn'), (17.89, 'sn'), (19.73, 'multi'), (22.48, 'sn'),
         (24.32, 'sn'), (28.91, 'sn'), (29.52, 'sn'), (31.35, 'fps'), (35.03, 'sn'), (36.71, 'sn'), (37.17, 'sn'),
         (40.84, 'sn'), (42.98, 'sn'), (43.75, 'multi'), (44.21, 'sn'), (45.28, 'sn'), (46.50, 'sn'), (46.96, 'multi'),
         (47.72, 'multi'),
         # SMG (rafales) : apparition du texte d'élimination
         (50.30, 'fps'), (51.50, 'fps'), (52.10, 'multi'), (53.10, 'fps'), (54.40, 'fps'), (55.45, 'fps'),
         (59.10, 'fps'), (59.85, 'fps'), (60.35, 'multi'), (61.25, 'fps')]
# transitions aux coupes de la source : style unique pour chacune
CUTS = [(3.87, 'xzoom'), (5.30, 'whip'), (7.12, 'xzoom'), (13.40, 'spin'), (15.63, 'scope'), (17.33, 'whip'),
        (23.90, 'whip'), (25.73, 'whip'), (26.35, 'spin3d'), (28.50, 'scope'), (30.20, 'mask'), (32.10, 'whip'),
        (34.17, 'xzoom'), (38.00, 'spin3d'), (40.70, 'scope'), (49.20, 'whip'), (51.15, 'whip'), (53.90, 'whip'),
        (58.00, 'mask'), (58.42, 'spin')]
# speed ramping : ralenti avant le tir puis accélération (durée conservée => musique en phase)
RAMPS = [(c - 0.08, 0.30, 0.6) for c, k in KILLS if k in ('sn', 'multi') and c < 48]
# intro : survol de la carte en caméra 3D (parallaxe par profondeur)
PARALLAX = [(0.0, 3.85, 14, 1), (3.9, 5.28, 12, -1), (5.33, 7.1, 14, 1), (7.15, 9.36, 12, -1), (13.5, 15.6, 10, 1), (26.4, 28.45, 10, -1), (32.12, 32.35, 8, 1), (38.05, 40.6, 10, 1)]
# lunette ouverte (halo + distorsion)
SCOPE_WIN = [(11.0, 11.35), (15.95, 16.3), (17.7, 18.0), (19.6, 19.95), (22.3, 22.9), (24.3, 24.6), (28.75, 29.3),
             (35.0, 35.3), (36.6, 37.0), (40.7, 41.2), (42.4, 42.95), (44.0, 44.2), (45.0, 45.5), (46.1, 46.9), (47.3, 47.9)]
FLY_A, FLY_B = 9.36, 10.98           # traversée 3D du décor (remplace le noir)
FLOAT_A, FLOAT_N = 48.45, 120        # écran flottant néon
# grade par scène : (début, fin, style)
LOOKS = [(0, 11.0, 'intro'), (11.0, 15.63, 'nuke'), (15.63, 34.17, 'desert'), (34.17, 48.8, 'gold'), (48.8, 62.8, 'electric')]


def segments():
    B = lambda n: round(n * BEAT * FPS)
    return [
        ('src', {'t0': 0.0, 't1': 32.35}),
        ('frz', {'n': B(6), 'at': 32.35, 'beats': 6}),
        ('src', {'t0': 32.35, 't1': 34.8}),
        ('wpn', {'n': B(6), 'at': 34.8, 'beats': 6}),
        ('src', {'t0': 34.8, 't1': SRC_END}),
        ('rep', {'n': B(6), 'at': SRC_END, 'beats': 6}),
    ]


def seg_starts():
    t, out = 0.0, []
    for kind, p in segments():
        dur = (p['t1'] - p['t0']) if kind == 'src' else p['n'] / FPS
        out.append((t, kind, dur, p)); t += dur
    return out, t


def src_to_out(ts):
    st, _ = seg_starts()
    for t0, kind, dur, p in st:
        if kind == 'src' and p['t0'] <= ts < p['t1']:
            return t0 + ts - p['t0']
    return None


def look_at_src(x):
    for a, b, k in LOOKS:
        if a <= x < b:
            return k
    return 'electric'
