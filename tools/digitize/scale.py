import cv2,json,subprocess,re,os
s=json.load(open('geo/labels_sel.json'))
out={}
for f in sorted(os.listdir('maps')):
    im=cv2.imread('maps/'+f); h,w=im.shape[:2]
    il,it,ir,ib=s[f]['inner']
    crop=im[ib+int(0.012*w):min(h,ib+int(0.06*w)), int(w*0.3):int(w*0.7)]
    g=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY); g=cv2.resize(g,None,fx=2,fy=2)
    cv2.imwrite('/tmp/sc.png',g)
    t=subprocess.run(['tesseract','/tmp/sc.png','-','--psm','6'],capture_output=True,text=True).stdout
    m=re.search(r'1\s*[:.]\s*([\d .]{3,9})',t)
    val=int(re.sub(r'\D','',m.group(1))) if m else None
    out[f]=val; print(f,val,repr(t.strip()[:60]))
json.dump(out,open('geo/scale_ocr.json','w'))
