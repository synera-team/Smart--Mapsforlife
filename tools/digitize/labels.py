import cv2, numpy as np, sys, os, subprocess, re, json
def find_labels(path, debug=False):
    im=cv2.imread(path)
    h,w=im.shape[:2]
    I=im.astype(np.int16); R,G,B=I[:,:,2],I[:,:,1],I[:,:,0]
    m=((B-R)>70)&(G>100)&(B>140)&(R<150)
    m=m.astype(np.uint8)*255
    k=cv2.getStructuringElement(cv2.MORPH_RECT,(int(w*0.008)+3,int(w*0.003)+2))
    d=cv2.dilate(m,k)
    n,lab,st,cen=cv2.connectedComponentsWithStats(d)
    out=[]
    for i in range(1,n):
        x,y,bw,bh,a=st[i]
        if bh<6 or bh>w*0.04 or bw<w*0.012 or bw>w*0.15: continue
        # density of real pixels
        sub=m[y:y+bh,x:x+bw]
        if sub.mean()<8: continue
        crop=im[max(0,y-4):y+bh+4, max(0,x-4):x+bw+4]
        g=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
        # text mask -> black on white
        c=crop.astype(np.int16)
        tm=((c[:,:,0]-c[:,:,2])>60)&(c[:,:,2]<170)
        bw_img=np.where(tm,0,255).astype(np.uint8)
        bw_img=cv2.resize(bw_img,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
        bw_img=cv2.copyMakeBorder(bw_img,20,20,20,20,cv2.BORDER_CONSTANT,value=255)
        cv2.imwrite('/tmp/lbl.png',bw_img)
        txt="";0 and subprocess.run(['tesseract','/tmp/lbl.png','-','--psm','7','-c','tessedit_char_whitelist=0123456789°\'"’'],capture_output=True,text=True).stdout.strip()
        out.append(dict(x=int(x),y=int(y),w=int(bw),h=int(bh),cx=x+bw/2,cy=y+bh/2,txt=txt))
    return out,(w,h)
if __name__=='__main__':
    fs=sys.argv[1:]
    for f in fs:
        o,sz=find_labels(f)
        print(os.path.basename(f),sz,[(round(a['cx']),round(a['cy']),a['txt']) for a in o])
