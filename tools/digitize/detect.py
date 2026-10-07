import cv2, numpy as np, sys, os
def profile(path):
    im=cv2.imread(path).astype(np.int16)
    h,w=im.shape[:2]
    R,G,B=im[:,:,2],im[:,:,1],im[:,:,0]
    out={}
    for axis in ('v','h'):
        ax=1 if axis=='v' else 0
        nbR=np.minimum(np.roll(R,3,ax),np.roll(R,-3,ax)); nbB=np.minimum(np.roll(B,3,ax),np.roll(B,-3,ax))
        m=((nbR-R)>20)&((nbB-B)>-5)&((nbR-R)-(nbB-B)>8)
        prof=m.sum(0 if axis=='v' else 1).astype(float)
        out[axis]=prof
    return out,(w,h)
def lines(path,frac=0.3):
    p,(w,h)=profile(path)
    res={}
    for axis in ('v','h'):
        prof=p[axis]; n=h if axis=='v' else w
        cand=np.where(prof>frac*n)[0]
        groups=[]
        for c in cand:
            if groups and c-groups[-1][-1]<=3: groups[-1].append(c)
            else: groups.append([c])
        res[axis]=[(float(np.average(g,weights=prof[g])),int(prof[g].max())) for g in groups]
    return res,(w,h)
if __name__=='__main__':
    for f in sorted(os.listdir(sys.argv[1])):
        r,sz=lines(os.path.join(sys.argv[1],f))
        print(f,sz,'V',[(round(x),c) for x,c in r['v']],'H',[(round(x),c) for x,c in r['h']])
