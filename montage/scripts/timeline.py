# Timeline du montage (temps en secondes). Source = vidéo d'origine 30,1 s.
FPS = 60
BEAT = 60 / 151.7          # tempo mesuré de la musique
BEAT0 = 6.055              # premier temps fort détecté
INTRO = 4.0
FREEZE_AT, FREEZE_BEATS = 16.34, 8
BULLET_AT, BULLET_BEATS = 26.50, 6
SRC_END = 30.1
OUTRO = 1.5
FREEZE_N = 190             # = 8 temps à 60 fps
BULLET_N = 142             # = 6 temps à 60 fps

# éliminations (temps source) -> secousse, aberration chromatique, flash, étincelles
KILLS = [1.95, 9.45, 12.55, 13.55, 14.05, 17.15, 18.55, 22.45, 24.95, 27.95, 28.5]
# coupes de la source -> transitions (flash + flou directionnel + zoom)
CUTS = [5.0, 5.5, 7.9, 11.6, 15.7, 16.83, 18.1, 25.7, 26.92, 28.9]
# rampes de vitesse (centre, demi-fenêtre, intensité) : durée conservée => musique synchro
RAMPS = [(1.95, 0.55, 0.72), (9.40, 0.18, 0.6), (13.55, 0.30, 0.6), (28.45, 0.35, 0.62)]
# passages en vue FPS où le filigrane et l'identifiant sont effacés
HUD_SEGS = [(7.9, 9.6), (11.6, 15.7), (16.83, 25.7), (26.92, 30.1)]


def segments():
    """Liste ordonnée : (type, durée_sortie, params)."""
    return [
        ('intro', INTRO, {}),
        ('src', FREEZE_AT - 0.0, {'t0': 0.0, 't1': FREEZE_AT}),
        ('freeze', FREEZE_N / FPS, {}),
        ('src', BULLET_AT - FREEZE_AT, {'t0': FREEZE_AT, 't1': BULLET_AT}),
        ('bullet', BULLET_N / FPS, {}),
        ('src', SRC_END - BULLET_AT, {'t0': BULLET_AT, 't1': SRC_END}),
        ('outro', OUTRO, {}),
    ]


def seg_starts():
    t, out = 0.0, []
    for s in segments():
        out.append((t, s))
        t += s[1]
    return out, t
