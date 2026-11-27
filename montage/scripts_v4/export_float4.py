# images du gameplay (A -> A+2 s) en RGBA à coins arrondis animés + halo néon (cadre net + lueur)
import cv2, numpy as np, os, sys
WK = sys.argv[1]; A, N = float(os.environ.get('A', 48.45)), 120
cap = cv2.VideoCapture(os.path.join(WK, 'src60.mp4')); cap.set(cv2.CAP_PROP_POS_FRAMES, round(A * 60))
od = os.path.join(WK, 'w', 'float_src'); os.makedirs(od, exist_ok=True)
h, w = 510, 1108
def rr_mask(r, W=w, H=h):
    m = np.full((H, W), 255, np.uint8)
    if r < 1: return m
    r = int(r); m[:r, :r] = 0; m[:r, -r:] = 0; m[-r:, :r] = 0; m[-r:, -r:] = 0
    for cx, cy in [(r, r), (W - r - 1, r), (r, H - r - 1), (W - r - 1, H - r - 1)]:
        cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return m
for f in range(1, N + 1):
    ok, im = cap.read()
    r = 38 * min(1, max(0, (f - 6) / 22)) * min(1, max(0, (110 - f) / 16))
    cv2.imwrite(os.path.join(od, f'{f:04d}.png'), np.dstack([im, rr_mask(r)]))
H2, W2 = 760, 1500
x0, y0 = (W2 - w) // 2, (H2 - h) // 2
g = np.zeros((H2, W2), np.float32)
cv2.rectangle(g, (x0 + 20, y0 + 20), (x0 + w - 20, y0 + h - 20), 1.0, -1)
glow = cv2.GaussianBlur(g, (0, 0), 45) * 1.4 + cv2.GaussianBlur(g, (0, 0), 14) * 0.7
# cadre néon net qui épouse l'écran arrondi (juste à l'extérieur du bord)
ring = np.zeros((H2, W2), np.uint8)
cv2.rectangle(ring, (x0 - 6, y0 - 6), (x0 + w + 6, y0 + h + 6), 255, 5, cv2.LINE_AA)
outer = np.zeros((H2, W2), np.uint8); outer[y0 - 6:y0 + h + 7, x0 - 6:x0 + w + 7] = rr_mask(44, w + 13, h + 13)
ring = cv2.bitwise_and(ring, outer).astype(np.float32) / 255
edge = cv2.Canny((outer > 0).astype(np.uint8) * 255, 50, 150).astype(np.float32) / 255
neon = np.clip(cv2.GaussianBlur(cv2.dilate(edge, np.ones((5, 5))), (0, 0), 1.2) * 1.5, 0, 1)
a = np.clip(glow, 0, 1)
col = np.dstack([a * 1.0, a * 0.92, a * 0.25])
col = col * (1 - neon[..., None]) + neon[..., None] * np.array([1.0, 1.0, 0.85])
alpha = np.clip(np.maximum(a, neon), 0, 1)
cv2.imwrite(os.path.join(WK, 'w', 'halo.png'), np.dstack([col * 255, alpha * 255]).astype(np.uint8))
print('ok', len(os.listdir(od)))
