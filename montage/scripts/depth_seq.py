# profondeur MiDaS image par image pour les segments à parallaxe (lissée dans le temps)
import cv2, numpy as np, onnxruntime as ort, sys, os
sys.path.insert(0, os.path.dirname(__file__)); import timeline as T
WK, MODEL = sys.argv[1], sys.argv[2]
sess = ort.InferenceSession(MODEL)
cap = cv2.VideoCapture(os.path.join(WK, 'src60.mp4')); i = 0; out = {}
need = set()
for a, b, *_ in T.PARALLAX:
    need |= set(range(int(a * 60), int(b * 60) + 2))
prev = None
while True:
    ok, f = cap.read()
    if not ok: break
    if i in need:
        x = cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2RGB), (256, 256), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        d = sess.run(None, {'0': x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
        d = (d - np.percentile(d, 2)) / (np.percentile(d, 98) - np.percentile(d, 2) + 1e-6)
        d = np.clip(cv2.resize(d, (320, 148), interpolation=cv2.INTER_CUBIC), 0, 1)
        if prev is not None and (i - 1) in out:
            d = 0.6 * d + 0.4 * prev   # anti-scintillement
        prev = d; out[i] = d.astype(np.float16)
    i += 1
np.savez_compressed(os.path.join(WK, 'depth_seq.npz'), idx=np.array(sorted(out)), d=np.stack([out[k] for k in sorted(out)]))
print('depth frames', len(out))
