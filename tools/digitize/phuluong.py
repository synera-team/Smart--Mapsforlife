import json,sys,numpy as np,cv2
sys.path.insert(0,'geo')
from tm import fwd,inv,vn2wgs
from poly2 import region
from export import area_km2
from detect import profile
sel=json.load(open('geo/labels_sel.json')); fit=json.load(open('geo/fit.json'))
f='phu-luong.jpg'
p,_=profile('maps/'+f)
vx=880+np.argmax(p['v'][880:930]); hy=810+np.argmax(p['h'][810:860]); print('lines',vx,hy,p['v'][vx],p['h'][hy])
im,c,meth,fa,ca=region(f); ap=cv2.approxPolyDP(c,1.2,True)[:,0,:].astype(float)
s=0.21875e-3*18000
gj=json.load(open('geo/out/wards.geojson'))
nb=[np.array(ft['geometry']['coordinates'][0]) for ft in gj['features'] if ft['properties']['slug'] in ('kien-hung','yen-nghia','ha-dong','duong-noi')]
nbp=np.vstack(nb)
best=[]
for lm in range(44,50):
  for am in range(54,60):
    lng=105+lm/60; lat=20+am/60
    E,N=fwd(lat,lng); E0=E-s*vx; N0=N+s*hy
    la,lo=inv(E0+s*ap[:,0],N0-s*ap[:,1]); la,lo=vn2wgs(la,lo)
    pts=np.c_[lo,la]
    d=np.sqrt(((pts[:,None,0]-nbp[None,:,0])*104000)**2+((pts[:,None,1]-nbp[None,:,1])*110600)**2).min(1)
    best.append(((d<40).mean(),lm,am,E0,N0))
best.sort(reverse=True); print(best[:4])
sc,lm,am,E0,N0=best[0]
fit[f]=dict(E0=E0,N0=N0,s=s,s0=s,rms=0,maxr=0,n=0,nlng=1,nlat=1,note=f'inferred from neighbors lng 105°{lm}\' lat 20°{am}\'')
json.dump(fit,open('geo/fit.json','w'))
