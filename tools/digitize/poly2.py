import cv2, numpy as np, json, sys, os
sys.path.insert(0,'geo')
from poly import extract
def region(f):
    im,filled,big,pink,m=extract(f)
    h,w=im.shape[:2]
    pk=cv2.morphologyEx(pink,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(15,15)))
    free=((pk==0)).astype(np.uint8)
    # restrict to frame bbox of filled's parent: use inner frame
    sel=json.load(open('geo/labels_sel.json'))
    il,it,ir,ib=sel[f]['inner']
    mask=np.zeros_like(free); mask[it+3:ib-3,il+3:ir-3]=1
    free&=mask
    n,lab=cv2.connectedComponents(free,connectivity=4)
    ids,cnt=np.unique(lab[filled>0],return_counts=True)
    cnt=cnt[ids>0]; ids=ids[ids>0]
    fa=(filled>0).sum()
    best=None
    if len(ids):
        # union of components that are mostly filled
        reg=np.zeros_like(free)
        for i,c in zip(ids,cnt):
            comp=(lab==i); a=comp.sum()
            if c/a>0.35 or a< fa*1.2 and c>0.2*a: reg|=comp.astype(np.uint8)
        ra=reg.sum()
        if 0.9*fa<ra<1.8*fa: best=reg*255
    method='pink'
    if best is None: best=filled; method='fill'
    best=best.astype(np.uint8)
    best=cv2.bitwise_or(best,filled)
    best=cv2.morphologyEx(best,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(21,21)))
    best=cv2.dilate(best,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
    cs,_=cv2.findContours(best,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    c=max(cs,key=cv2.contourArea)
    return im,c,method,fa,cv2.contourArea(c)
if __name__=='__main__':
    os.makedirs('geo/ov',exist_ok=True)
    fs=sys.argv[1:] or sorted(os.listdir('maps'))
    for f in fs:
        im,c,meth,fa,ca=region(f)
        ov=im.copy(); cv2.drawContours(ov,[c],-1,(0,0,255),5)
        cv2.imwrite('geo/ov/'+f.split('.')[0]+'.jpg',cv2.resize(ov,None,fx=0.3,fy=0.3))
        print(f,meth,int(fa),int(ca),round(ca/fa,2))
