import cv2, numpy as np, onnxruntime as ort, sys
sess=ort.InferenceSession(sys.argv[1])
for f in sys.argv[2:]:
    im=cv2.imread(f); h,w=im.shape[:2]
    x=cv2.resize(cv2.cvtColor(im,cv2.COLOR_BGR2RGB),(256,256),interpolation=cv2.INTER_CUBIC).astype(np.float32)/255
    x=(x-[0.485,0.456,0.406])/[0.229,0.224,0.225]
    d=sess.run(None,{'0':x.transpose(2,0,1)[None].astype(np.float32)})[0][0]
    d=cv2.resize(d,(w,h),interpolation=cv2.INTER_CUBIC)
    # edge-aware smoothing guided by image
    d=(d-d.min())/(d.max()-d.min())
    d=cv2.bilateralFilter(d.astype(np.float32),9,0.1,7)
    np.save(f[:-4]+'_inv.npy',d)
    cv2.imwrite(f[:-4]+'_depth.png',(d*255).astype(np.uint8))
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY); 
    print(f,'brightest',cv2.minMaxLoc(cv2.GaussianBlur(g,(31,31),0))[3])
