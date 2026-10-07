import cv2,numpy as np,json,sys
s=json.load(open('geo/labels_sel.json'))
def blobs(f):
    im=cv2.imread('maps/'+f); h,w=im.shape[:2]; il,it,ir,ib=s[f]['inner']
    I=im.astype(np.int16); R,G,B=I[:,:,2],I[:,:,1],I[:,:,0]
    m=(((B-R)>60)&(B>140)&(R<170)).astype(np.uint8)*255
    m_=int(90*w/1920); out={}
    bands={'L':(it,ib,max(0,il-m_),il-2,'v'),'R':(it,ib,ir+2,min(w,ir+m_),'v'),'T':(max(0,it-m_),it-2,il,ir,'h'),'B':(ib+2,min(h,ib+m_),il,ir,'h')}
    for k,(y0,y1,x0,x1,o) in bands.items():
        sub=m[y0:y1,x0:x1]
        ker=cv2.getStructuringElement(cv2.MORPH_RECT,(3,15) if o=='v' else (15,3))
        d=cv2.dilate(sub,ker)
        n,lab,st,cen=cv2.connectedComponentsWithStats(d)
        L=[]
        for i in range(1,n):
            x,y,bw,bh,a=st[i]
            if (o=='v' and bh>=18 and bh>bw) or (o=='h' and bw>=18 and bw>bh):
                L.append((round(x0+x+bw/2),round(y0+y+bh/2),int(bw),int(bh)))
        out[k]=sorted(L,key=lambda t:(t[1] if o=='v' else t[0]))
    return out
if __name__=='__main__':
    for f in sys.argv[1:]: print(f,blobs(f))
