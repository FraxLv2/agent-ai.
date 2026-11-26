import cv2, numpy as np, sys
# usage: cutout.py frame.png x0 y0 x1 y1 [tagx0 tagy0 tagx1 tagy1]
f=sys.argv[1]; r=list(map(int,sys.argv[2:6])); tag=list(map(int,sys.argv[6:10])) if len(sys.argv)>9 else None
im=cv2.imread(f); h,w=im.shape[:2]
mask=np.zeros((h,w),np.uint8)
bgd=np.zeros((1,65),np.float64); fgd=np.zeros((1,65),np.float64)
cv2.grabCut(im,mask,(r[0],r[1],r[2]-r[0],r[3]-r[1]),bgd,fgd,8,cv2.GC_INIT_WITH_RECT)
fg=np.where((mask==1)|(mask==3),255,0).astype(np.uint8)
# garder la plus grande composante
n,lab,st,_=cv2.connectedComponentsWithStats(fg)
if n>1:
    k=1+np.argmax(st[1:,cv2.CC_STAT_AREA]); fg=np.where(lab==k,255,0).astype(np.uint8)
fg=cv2.morphologyEx(fg,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
if tag: fg[tag[1]:tag[3],tag[0]:tag[2]]=255
alpha=cv2.GaussianBlur(fg,(5,5),0)
rgba=np.dstack([im,alpha]); cv2.imwrite(f[:-4]+'_fg.png',rgba)
# décor : trou élargi puis inpainting
hole=cv2.dilate(fg,np.ones((15,15),np.uint8))
bg=cv2.inpaint(im,hole,9,cv2.INPAINT_TELEA)
cv2.imwrite(f[:-4]+'_bg.png',bg)
# profondeur du décor : on remplace la zone du perso par la profondeur environnante
d=np.load(f[:-4]+'_inv.npy').astype(np.float32)
d8=(d*65535).astype(np.uint16)
dbg=cv2.inpaint((d*255).astype(np.uint8),hole,15,cv2.INPAINT_TELEA).astype(np.float32)/255
dbg=cv2.GaussianBlur(dbg,(0,0),2)
np.save(f[:-4]+'_bginv.npy',dbg)
ys,xs=np.where(fg>128)
print('fg bbox',xs.min(),ys.min(),xs.max(),ys.max(),'median inv depth fg',float(np.median(d[fg>128])),'feet y',ys.max())
prev=im.copy(); prev[fg<128]=(prev[fg<128]*0.25).astype(np.uint8)
cv2.imwrite(f[:-4]+'_prev.jpg',np.vstack([prev,bg]))
