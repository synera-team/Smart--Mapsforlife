import numpy as np
a=6378137.0; f=1/298.257223563; e2=f*(2-f); ep2=e2/(1-e2); k0=0.9996; lon0=np.radians(105.0); FE=500000.0
def fwd(lat,lon):
    phi=np.radians(lat); lam=np.radians(lon)-lon0
    N=a/np.sqrt(1-e2*np.sin(phi)**2); T=np.tan(phi)**2; C=ep2*np.cos(phi)**2; A=np.cos(phi)*lam
    M=a*((1-e2/4-3*e2**2/64-5*e2**3/256)*phi-(3*e2/8+3*e2**2/32+45*e2**3/1024)*np.sin(2*phi)+(15*e2**2/256+45*e2**3/1024)*np.sin(4*phi)-(35*e2**3/3072)*np.sin(6*phi))
    x=k0*N*(A+(1-T+C)*A**3/6+(5-18*T+T*T+72*C-58*ep2)*A**5/120)
    y=k0*(M+N*np.tan(phi)*(A*A/2+(5-T+9*C+4*C*C)*A**4/24+(61-58*T+T*T+600*C-330*ep2)*A**6/720))
    return x+FE,y
def inv(E,N):
    x=E-FE; M=N/k0; mu=M/(a*(1-e2/4-3*e2**2/64-5*e2**3/256))
    e1=(1-np.sqrt(1-e2))/(1+np.sqrt(1-e2))
    phi1=mu+(3*e1/2-27*e1**3/32)*np.sin(2*mu)+(21*e1**2/16-55*e1**4/32)*np.sin(4*mu)+(151*e1**3/96)*np.sin(6*mu)+(1097*e1**4/512)*np.sin(8*mu)
    N1=a/np.sqrt(1-e2*np.sin(phi1)**2); T1=np.tan(phi1)**2; C1=ep2*np.cos(phi1)**2; R1=a*(1-e2)/(1-e2*np.sin(phi1)**2)**1.5; D=x/(N1*k0)
    phi=phi1-(N1*np.tan(phi1)/R1)*(D*D/2-(5+3*T1+10*C1-4*C1*C1-9*ep2)*D**4/24+(61+90*T1+298*C1+45*T1*T1-252*ep2-3*C1*C1)*D**6/720)
    lam=(D-(1+2*T1+C1)*D**3/6+(5-2*C1+28*T1-3*C1*C1+8*ep2+24*T1*T1)*D**5/120)/np.cos(phi1)
    return np.degrees(phi),np.degrees(lam+lon0)
# VN-2000 -> WGS84 (EPSG:4756 towgs84, position-vector)
TW=[-191.90441429,-39.30318279,-111.45032835,-0.00928836,0.01975479,-0.00427372,0.252906278]
def geo2ecef(lat,lon,h=0):
    p,l=np.radians(lat),np.radians(lon); N=a/np.sqrt(1-e2*np.sin(p)**2)
    return (N+h)*np.cos(p)*np.cos(l),(N+h)*np.cos(p)*np.sin(l),(N*(1-e2)+h)*np.sin(p)
def ecef2geo(X,Y,Z):
    lon=np.arctan2(Y,X); p=np.hypot(X,Y); lat=np.arctan2(Z,p*(1-e2))
    for _ in range(6):
        N=a/np.sqrt(1-e2*np.sin(lat)**2); h=p/np.cos(lat)-N; lat=np.arctan2(Z,p*(1-e2*N/(N+h)))
    return np.degrees(lat),np.degrees(lon)
def vn2wgs(lat,lon):
    X,Y,Z=geo2ecef(lat,lon)
    dx,dy,dz,rx,ry,rz,s=TW; r=np.radians(np.array([rx,ry,rz])/3600); m=1+s*1e-6
    X2=dx+m*(X-r[2]*Y+r[1]*Z); Y2=dy+m*(r[2]*X+Y-r[0]*Z); Z2=dz+m*(-r[1]*X+r[0]*Y+Z)
    return ecef2geo(X2,Y2,Z2)
if __name__=='__main__':
    E,N=fwd(21.03,105.85); print(E,N, inv(E,N))
    print(vn2wgs(21.03,105.85))
