import cv2, numpy as np
def frame(path):
    im=cv2.imread(path,0); h,w=im.shape
    d=(im<110)
    rows=np.where(d.sum(1)>0.55*w)[0]; cols=np.where(d.sum(0)>0.45*h)[0]
    def grp(a):
        g=[]
        for c in a:
            if g and c-g[-1][-1]<=2: g[-1].append(c)
            else: g.append([c])
        return [(g_[0],g_[-1]) for g_ in g]
    return grp(rows),grp(cols),(w,h)
if __name__=='__main__':
    import os
    for f in sorted(os.listdir('maps')):
        print(f,*frame('maps/'+f))
