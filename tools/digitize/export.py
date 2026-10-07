import json,sys,numpy as np,cv2,os
sys.path.insert(0,'geo')
from build import px2geo
from poly2 import region
fit=json.load(open('geo/fit.json'))
NAMES={'ba-dinh':'Ba Đình','bach-mai':'Bạch Mai','bo-de':'Bồ Đề','cau-giay':'Cầu Giấy','chuong-my':'Chương Mỹ','cua-nam':'Cửa Nam','dai-mo':'Đại Mỗ','dinh-cong':'Định Công','dong-da':'Đống Đa','dong-ngac':'Đông Ngạc','duong-noi':'Dương Nội','giang-vo':'Giảng Võ','ha-dong':'Hà Đông','hai-ba-trung':'Hai Bà Trưng','hoan-kiem':'Hoàn Kiếm','hoang-liet':'Hoàng Liệt','hoang-mai':'Hoàng Mai','hong-ha':'Hồng Hà','khuong-dinh':'Khương Đình','kien-hung':'Kiến Hưng','kim-lien':'Kim Liên','lang':'Láng','linh-nam':'Lĩnh Nam','long-bien':'Long Biên','nghia-do':'Nghĩa Đô','ngoc-ha':'Ngọc Hà','o-cho-dua':'Ô Chợ Dừa','phu-dien':'Phú Diễn','phu-luong':'Phú Lương','phu-thuong':'Phú Thượng','phuc-loi':'Phúc Lợi','phuong-liet':'Phương Liệt','son-tay':'Sơn Tây','tay-ho':'Tây Hồ','tay-mo':'Tây Mỗ','tay-tuu':'Tây Tựu','thanh-liet':'Thanh Liệt','thanh-xuan':'Thanh Xuân','thuong-cat':'Thượng Cát','tu-liem':'Từ Liêm','tung-thien':'Tùng Thiện','tuong-mai':'Tương Mai','viet-hung':'Việt Hưng','vinh-hung':'Vĩnh Hưng','vinh-tuy':'Vĩnh Tuy','xa-hong-son':'Hồng Sơn','xuan-dinh':'Xuân Đỉnh','xuan-phuong':'Xuân Phương','yen-hoa':'Yên Hòa','yen-nghia':'Yên Nghĩa','yen-so':'Yên Sở'}
def area_km2(ll):
    lat0=np.radians(ll[:,1].mean()); x=ll[:,0]*111320*np.cos(lat0); y=ll[:,1]*110574
    return abs(0.5*np.sum(x*np.roll(y,1)-np.roll(x,1)*y))/1e6
def process(f):
    im,c,meth,fa,ca=region(f)
    eps=1.2
    ap=cv2.approxPolyDP(c,eps,True)[:,0,:]
    I=im.astype(int)
    red=((I[:,:,2]>215)&(I[:,:,1]<60)&(I[:,:,0]<60)).astype(np.uint8)
    n,lab,st,cen=cv2.connectedComponentsWithStats(red)
    hq=None
    for j in range(1,n):
        if 40<st[j][4]<900 and 0.6<st[j][2]/max(st[j][3],1)<1.6:
            if cv2.pointPolygonTest(c,(float(cen[j][0]),float(cen[j][1])),False)>0:
                hq=cen[j]; break
    return ap,hq,meth
if __name__=='__main__':
    feats=[]; os.makedirs('geo/out',exist_ok=True)
    for f in sorted(os.listdir('maps')):
        if not fit.get(f): print('skip',f); continue
        ap,hq,meth=process(f)
        ll=px2geo(f,ap)
        ring=[[round(a,6),round(b,6)] for a,b in ll]; ring.append(ring[0])
        slug=f.split('.')[0]
        props=dict(slug=slug,name=('Xã ' if slug.startswith('xa-') else 'Phường ')+NAMES[slug],short=NAMES[slug],
            type='xa' if slug.startswith('xa-') else 'phuong',area_km2=round(area_km2(ll),2),
            source='Số hoá từ Bản đồ phương án thành lập đơn vị hành chính (Sở Nội vụ TP Hà Nội), VN-2000 → WGS84',
            fit_rms_m=round(fit[f]['rms'],1),method=meth,scale=None)
        if hq is not None:
            h=px2geo(f,np.array([hq]))[0]; props['hq']=[round(h[0],6),round(h[1],6)]
        feats.append(dict(type='Feature',properties=props,geometry=dict(type='Polygon',coordinates=[ring])))
        print(slug,props['area_km2'],len(ring),props.get('hq'))
    json.dump(dict(type='FeatureCollection',features=feats),open('geo/out/wards.geojson','w'),ensure_ascii=False)
