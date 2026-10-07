import json,numpy as np,sys
sys.path.insert(0,'geo')
from tm import fwd,inv
from values import V,MANUAL
from scipy.optimize import least_squares
sel=json.load(open('geo/labels_sel.json'))
sc=json.load(open('geo/scale_ocr.json')); sc['linh-nam.jpg']=22000
V['son-tay.jpg'].update({0:('lng',105*60+32),1:('lng',105*60+28),4:('lng',105*60+32)})
def paper_mpp(w,h):
    if w==1754: return 0.297/1754
    if w==802: return (0.297/1754)*(1461/669)
    if w==1920 and h>2000: return 0.297/1920
    if w==1920: return 0.420/1920
    if w==2000: return 0.297/2000
    if w==1204: return 0.420/1204
    return None
def obs(f):
    d=sel[f]; il,it,ir,ib=d['inner']; out=[]
    if f in MANUAL:
        for p,c,(k,v) in MANUAL[f]:
            x,y={'T':(c,it),'B':(c,ib),'L':(il,c),'R':(ir,c)}[p]
            out.append((x,y,k,v/60.0,p))
        return out
    for i,a in enumerate(d['labels']):
        if i not in V.get(f,{}): continue
        k,v=V[f][i]; p=a['pos']
        if p=='T': x,y=a['cx'],it
        elif p=='B': x,y=a['cx'],ib
        elif p=='L': x,y=il,a['cy']
        else: x,y=ir,a['cy']
        out.append((x,y,k,v/60.0,p))
    return out
def fit(f,prior_w=0.2):
    d=sel[f]; w,h=d['size']; O=obs(f)
    pm=paper_mpp(w,h); s0=(pm*sc[f]) if (pm and sc.get(f)) else None
    lngs=[o for o in O if o[2]=='lng']; lats=[o for o in O if o[2]=='lat']
    if not lngs or not lats: return None
    lat_c=np.mean([o[3] for o in lats]); lng_c=np.mean([o[3] for o in lngs])
    Ec,Nc=fwd(lat_c,lng_c)
    x0=np.mean([o[0] for o in lngs]); y0=np.mean([o[1] for o in lats])
    s_init=s0 or 5.0
    def res(p):
        E0,N0,s=p; r=[]
        for x,y,k,v,_ in O:
            la,lo=inv(E0+s*x,N0-s*y)
            r.append((lo-v)*111320*np.cos(np.radians(la)) if k=='lng' else (la-v)*110574)
        if s0: r.append((s-s0)/s0*prior_w*1000)
        return r
    p0=[Ec-s_init*x0,Nc+s_init*y0,s_init]
    R=least_squares(res,p0)
    rr=np.array(res(R.x))[:len(O)]
    return dict(E0=R.x[0],N0=R.x[1],s=R.x[2],s0=s0,rms=float(np.sqrt(np.mean(rr**2))),maxr=float(np.abs(rr).max()),n=len(O),nlng=len(lngs),nlat=len(lats))
if __name__=='__main__':
    res={}
    for f in sorted(sel):
        r=fit(f); res[f]=r
        if r: print(f"{f:18s} n={r['n']}({r['nlng']},{r['nlat']}) s={r['s']:.3f} s0={r['s0'] or 0:.3f} ratio={(r['s']/r['s0'] if r['s0'] else 0):.3f} rms={r['rms']:.1f} max={r['maxr']:.1f}")
        else: print(f,'NO FIT')
    json.dump(res,open('geo/fit.json','w'))
