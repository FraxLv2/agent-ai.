# exporte les images du gameplay (11.6 -> 13.6 s) en RGBA avec coins arrondis animés + image de halo
import cv2, numpy as np, os, sys
WK = sys.argv[1]; A, N = 11.92, 120
mask = cv2.imread(os.path.join(WK, 'hudmask.png'), 0)[430:510]
cap = cv2.VideoCapture(os.path.join(WK, 'src60.mp4')); cap.set(cv2.CAP_PROP_POS_FRAMES, round(A * 60))
od = os.path.join(WK, 'float_src'); os.makedirs(od, exist_ok=True)
h, w = 510, 1108
def rr_mask(r):
    m = np.full((h, w), 255, np.uint8)
    if r < 1: return m
    r = int(r); m[:r, :r] = 0; m[:r, -r:] = 0; m[-r:, :r] = 0; m[-r:, -r:] = 0
    for cx, cy in [(r, r), (w - r - 1, r), (r, h - r - 1), (w - r - 1, h - r - 1)]:
        cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return m
for f in range(1, N + 1):
    ok, im = cap.read()
    im[430:510] = cv2.inpaint(im[430:510], mask, 3, cv2.INPAINT_TELEA)
    u = f / N
    r = 38 * min(1, max(0, (f - 6) / 22)) * min(1, max(0, (110 - f) / 16))
    cv2.imwrite(os.path.join(od, f'{f:04d}.png'), np.dstack([im, rr_mask(r)]))
# halo : rectangle arrondi flouté (cyan)
H2, W2 = 760, 1500
g = np.zeros((H2, W2), np.float32)
cv2.rectangle(g, ((W2 - w) // 2 + 20, (H2 - h) // 2 + 20), ((W2 + w) // 2 - 20, (H2 + h) // 2 - 20), 1.0, -1)
g = cv2.GaussianBlur(g, (0, 0), 45) * 1.6 + cv2.GaussianBlur(g, (0, 0), 14) * 0.8
g = np.clip(g, 0, 1)
halo = np.dstack([g * 255 * 1.0, g * 255 * 0.92, g * 255 * 0.25, g * 255]).astype(np.uint8)  # BGR cyan
cv2.imwrite(os.path.join(WK, 'halo.png'), halo)
print('ok', len(os.listdir(od)))
