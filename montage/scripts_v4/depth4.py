# profondeur MiDaS image par image (30 i/s) pour la parallaxe 3D et les transitions par masquage
import cv2, numpy as np, onnxruntime as ort, sys, os
sys.path.insert(0, os.path.dirname(__file__)); import timeline4 as T
WK = sys.argv[1]; sess = ort.InferenceSession(sys.argv[2])
rng = [(a, b) for a, b, *_ in T.PARALLAX] + [(c - 0.05, c + 0.45) for c, s in T.CUTS if s == 'mask']
want = sorted({i for a, b in rng for i in range(int(a * 60), int(b * 60) + 2, 2)})
cap = cv2.VideoCapture(os.path.join(WK, 'src60.mp4')); i = 0; out = {}
wi = set(want); last = max(want)
while i <= last:
    ok, im = cap.read()
    if not ok: break
    if i in wi:
        x = cv2.resize(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), (256, 256), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        d = sess.run(None, {'0': x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
        d = (d - d.min()) / (d.max() - d.min() + 1e-6)
        out[i] = cv2.resize(d, (277, 128), interpolation=cv2.INTER_AREA).astype(np.float16)
    i += 1
np.savez(os.path.join(WK, 'depth4.npz'), idx=np.array(sorted(out)), d=np.stack([out[k] for k in sorted(out)]))
print('depth', len(out))
