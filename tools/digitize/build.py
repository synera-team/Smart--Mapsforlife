import json,sys,numpy as np,cv2
sys.path.insert(0,'geo')
from tm import inv,vn2wgs
from poly2 import region
fit=json.load(open('geo/fit.json'))
def px2geo(f,pts,datum=True):
    r=fit[f]; x=pts[:,0].astype(float); y=pts[:,1].astype(float)
    la,lo=inv(r['E0']+r['s']*x, r['N0']-r['s']*y)
    if datum: la,lo=vn2wgs(la,lo)
    return np.c_[lo,la]
def lake_centroid(f):
    im=cv2.imread('maps/'+f); I=im.astype(int)
    # lake fill: light cyan
    m=((I[:,:,2]<200)&(I[:,:,1]>220)&(I[:,:,0]>230)).astype(np.uint8)
    return m
if __name__=='__main__':
    # validation Hoan Kiem lake: find cyan component near centre of ward
    f='hoan-kiem.jpg'
    m=lake_centroid(f)
    n,lab,st,cen=cv2.connectedComponentsWithStats(m)
    # pick component around (1100,1650) in full res (lake)
    i=lab[1650,1100] if lab[1650,1100] else None
    print('lake comp',i, st[i] if i else None)
    c=cen[i]
    for d in (False,True):
        print('datum',d, px2geo(f,np.array([c]),d))
