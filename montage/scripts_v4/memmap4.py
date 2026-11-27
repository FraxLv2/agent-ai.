# décode src60.mp4 une fois dans un fichier brut adressable (accès aléatoire rapide)
import cv2, numpy as np, sys, os
WK = sys.argv[1]; cap = cv2.VideoCapture(os.path.join(WK, 'src60.mp4'))
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) + 5
mm = np.lib.format.open_memmap(os.path.join(WK, 'src60.npy'), mode='w+', dtype=np.uint8, shape=(n, 510, 1108, 3))
i = 0
while True:
    ok, f = cap.read()
    if not ok: break
    mm[i] = f; i += 1
mm.flush(); open(os.path.join(WK, 'src60.count'), 'w').write(str(i)); print('frames', i)
