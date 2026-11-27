import cv2, numpy as np
BGD,FGD,PBGD,PFGD=0,1,2,3
im=cv2.imread('f_32.35.png'); h,w=im.shape[:2]
poly=np.array([(125,135),(160,138),(215,165),(262,160),(300,158),(345,175),(395,180),(432,192),(432,215),(395,222),(405,260),(440,290),(458,322),(440,332),(400,322),(372,300),(335,285),(300,262),(255,240),(215,220),(170,190),(128,160)],np.int32)
m=np.full((h,w),BGD,np.uint8)
pm=np.zeros((h,w),np.uint8); cv2.fillPoly(pm,[poly],255)
m[cv2.dilate(pm,np.ones((13,13),np.uint8))>0]=PBGD
m[pm>0]=PFGD
m[cv2.erode(pm,np.ones((17,17),np.uint8))>0]=FGD
b=np.zeros((1,65));f=np.zeros((1,65))
cv2.grabCut(im,m,None,b,f,10,cv2.GC_INIT_WITH_MASK)
fg=np.where((m==1)|(m==3),255,0).astype(np.uint8)
n,lab,st,_=cv2.connectedComponentsWithStats(fg); k=1+np.argmax(st[1:,4]); fg=np.where(lab==k,255,0).astype(np.uint8)
hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
sand=((hsv[...,0]>=6)&(hsv[...,0]<=28)&(hsv[...,1]>55)&(hsv[...,2]>100)).astype(np.uint8)*255
sand=cv2.morphologyEx(sand,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
fg[sand>0]=0
n,lab,st,_=cv2.connectedComponentsWithStats(fg); k=1+np.argmax(st[1:,4]); fg=np.where(lab==k,255,0).astype(np.uint8)
fg=cv2.morphologyEx(fg,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
ff=np.zeros((h+2,w+2),np.uint8); inv=fg.copy(); cv2.floodFill(inv,ff,(0,0),255); fg=fg|cv2.bitwise_not(inv)
alpha=cv2.GaussianBlur(fg,(5,5),0)
cv2.imwrite('f_32.35_fg.png',np.dstack([im,alpha]))
hole=cv2.dilate(fg,np.ones((15,15),np.uint8))
cv2.imwrite('f_32.35_bg.png',cv2.inpaint(im,hole,9,cv2.INPAINT_TELEA))
d=np.load('f_32.35_inv.npy').astype(np.float32)
dbg=cv2.inpaint((d*255).astype(np.uint8),hole,15,cv2.INPAINT_TELEA).astype(np.float32)/255
np.save('f_32.35_bginv.npy',cv2.GaussianBlur(dbg,(0,0),2))
ys,xs=np.where(fg>128); print(xs.min(),ys.min(),xs.max(),ys.max(), np.median(d[fg>128]))
p=im.copy(); p[fg<128]=(p[fg<128]*0.2).astype(np.uint8); cv2.imwrite('char_prev.jpg',cv2.resize(p[100:360,80:500],None,fx=2,fy=2))
