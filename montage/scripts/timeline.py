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
KILLS = [1.95, 8.75, 9.72, 12.55, 13.55, 14.05, 17.15, 18.55, 22.45, 24.95, 27.95, 28.5]
# coupes de la source -> transitions (flash + flou directionnel + zoom)
CUTS = [5.0, 5.63, 7.9, 11.5, 15.6, 16.8, 18.1, 25.7, 27.0, 28.9]
# rampes de vitesse (centre, demi-fenêtre, intensité) : durée conservée => musique synchro
RAMPS = [(1.95, 0.55, 0.72), (13.55, 0.30, 0.6), (28.45, 0.25, 0.62)]
# passages en vue FPS où le filigrane et l'identifiant sont effacés
# séquence sniper : super ralenti de la visée (9.40 -> 9.66) puis freeze 3D balle -> reprise au vrai tir
SNIPER_A, SNIPER_B = 9.40, 9.66
SLOW_N = 78                       # 1.3 s de ralenti
SNIPER_N = 175                    # 2.92 s de freeze 3D
# transitions 3D (coupe, style) : cubes / retournements rendus dans Blender avec la vidéo sur les faces
TRANS_HALF = 0.2
TRANS3D = []  # transitions 3D en cube retirées à la demande
# segments sans HUD où la caméra 3D (parallaxe par profondeur) est appliquée : (début, fin, amplitude px, sens)
PARALLAX = [(0.0, 4.95, 26, 1), (5.55, 7.85, 18, -1), (10.25, 11.55, 30, 1), (15.75, 16.34, 22, -1), (25.75, 26.50, 22, 1)]
HUD_SEGS = [(7.9, 10.05), (11.6, 15.7), (16.83, 25.7), (26.92, 30.1)]


def segments():
    """Liste ordonnée : (type, durée_sortie, params)."""
    return [
        ('intro', INTRO, {}),
        ('src', SNIPER_A, {'t0': 0.0, 't1': SNIPER_A}),
        ('slow', SLOW_N / FPS, {}),
        ('sniper', SNIPER_N / FPS, {}),
        ('src', FREEZE_AT - SNIPER_B, {'t0': SNIPER_B, 't1': FREEZE_AT}),
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
