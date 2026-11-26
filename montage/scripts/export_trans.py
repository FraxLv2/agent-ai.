# exporte les images source autour des coupes choisies pour les transitions 3D (HUD effacé)
import cv2, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__)); import timeline as T
WK = sys.argv[1]
mask = cv2.imread(os.path.join(WK, 'hudmask.png'), 0)[430:510]
cap = cv2.VideoCapture(os.path.join(WK, 'src60.mp4')); fr = []
while True:
    ok, f = cap.read()
    if not ok: break
    fr.append(f)
HW = int(T.TRANS_HALF * 60)
for c, style in T.TRANS3D:
    ci = round(c * 60)
    d = os.path.join(WK, 'trans', f'{c:.2f}'); os.makedirs(d, exist_ok=True)
    for k in range(-HW - 2, HW + 2):
        i = min(max(ci + k, 0), len(fr) - 1)
        f = fr[i].copy()
        t = i / 60
        if any(a <= t < b for a, b in T.HUD_SEGS):
            f[430:510] = cv2.inpaint(f[430:510], mask, 3, cv2.INPAINT_TELEA)
        cv2.imwrite(os.path.join(d, f'{k + HW + 2:03d}.png'), f)
    print(c, style, len(os.listdir(d)))
