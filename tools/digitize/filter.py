import json, cv2, numpy as np, sys
sys.path.insert(0,'geo')
from frame import frame
c=json.load(open('geo/cands.json'))
res={}
tiles=[]
for f,d in c.items():
    rows,cols,(w,h)=frame('maps/'+f)
    rows=[r for r in rows if r[0]>5 and r[1]<h-5]; cols=[k for k in cols if k[0]>5 and k[1]<w-5]
    ot,it,ib,ob=rows[0][1],rows[1][0],rows[-2][1],rows[-1][0]
    ol,il,ir,orr=cols[0][1],cols[1][0],cols[-2][1],cols[-1][0]
    sel=[]
    for a in d['labels']:
        cx,cy=a['cx'],a['cy']; pos=None
        if ot<cy<it and il<cx<ir: pos='T'
        elif ib<cy<ob and il<cx<ir: pos='B'
        elif ol<cx<il+5 and it<cy<ib: pos='L'
        elif ir-5<cx<orr and it<cy<ib: pos='R'
        if pos: sel.append(dict(pos=pos,cx=cx,cy=cy,x=a['x'],y=a['y'],w=a['w'],h=a['h']))
    res[f]=dict(size=[w,h],inner=[il,it,ir,ib],labels=sel)
    im=cv2.imread('maps/'+f)
    for j,a in enumerate(sel):
        crop=im[max(0,a['y']-3):a['y']+a['h']+3, max(0,a['x']-3):a['x']+a['w']+3]
        if a['pos'] in 'LR' and crop.shape[0]>crop.shape[1]*1.5: crop=cv2.rotate(crop,cv2.ROTATE_90_CLOCKWISE)
        s=34/max(crop.shape[0],1); crop=cv2.resize(crop,None,fx=s,fy=s)
        if crop.shape[1]>260: crop=cv2.resize(crop,(260,max(1,int(crop.shape[0]*260/crop.shape[1]))))
        tile=np.full((44,420,3),255,np.uint8); tile[4:4+crop.shape[0],150:150+crop.shape[1]]=crop
        cv2.putText(tile,f"{f[:11]} {j}{a['pos']}",(2,28),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,255),1)
        tiles.append(tile)
json.dump(res,open('geo/labels_sel.json','w'),default=int)
per=30
blank=np.full((44,420,3),255,np.uint8)
for k in range(0,len(tiles),per*3):
    ch=tiles[k:k+per*3]; cols_=[]
    for q in range(3):
        cc=ch[q*per:(q+1)*per]; cc+= [blank]*(per-len(cc)); cols_.append(np.vstack(cc))
    cv2.imwrite(f'geo/sel{k//(per*3)}.png',np.hstack(cols_))
print(len(tiles), {f:len(v['labels']) for f,v in res.items()})
