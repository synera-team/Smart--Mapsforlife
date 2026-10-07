import cv2, numpy as np, json, sys, os
sys.path.insert(0,'geo')
sel=json.load(open('geo/labels_sel.json'))
def extract(f):
    im=cv2.imread('maps/'+f)
    h,w=im.shape[:2]
    il,it,ir,ib=sel[f]['inner'] if f in sel else (0,0,w,h)
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    H,S,V=hsv[:,:,0].astype(int),hsv[:,:,1].astype(int),hsv[:,:,2].astype(int)
    fill=(H>=20)&(H<=80)&(S>=45)&(S<=170)&(V>=190)
    m=np.zeros((h,w),np.uint8); m[it+2:ib-2,il+2:ir-2]=fill[it+2:ib-2,il+2:ir-2].astype(np.uint8)*255
    # remove legend box: it is white; fine
    k=max(9,int(w*0.008))
    m2=cv2.morphologyEx(m,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k)))
    m2=cv2.morphologyEx(m2,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
    cs,_=cv2.findContours(m2,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    cs=sorted(cs,key=cv2.contourArea,reverse=True)
    big=cs[0]
    filled=np.zeros_like(m2); cv2.drawContours(filled,[big],-1,255,-1)
    # grow by half pink line width to reach boundary centerline
    pink=(((H>=140)&(H<=175))&(S>=40)&(V>=180)).astype(np.uint8)*255
    return im,filled,big,pink,m
if __name__=='__main__':
    os.makedirs('geo/ov',exist_ok=True)
    for f in sys.argv[1:]:
        im,filled,big,pink,m=extract(f)
        ov=im.copy()
        cv2.drawContours(ov,[big],-1,(0,0,255),4)
        ov=cv2.resize(ov,None,fx=0.4,fy=0.4)
        cv2.imwrite('geo/ov/'+f.split('.')[0]+'.jpg',ov)
        print(f, cv2.contourArea(big), len(big))
