// Trình xem VR360 nội bộ (WebGL, không phụ thuộc thư viện): ảnh/video equirectangular 2:1,
// tour nhiều cảnh với điểm nóng (hotspot). Loại 'embed' (Kuula, Matterport, 3DVista...) dùng iframe.
const VS = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
const FS = `precision highp float;uniform sampler2D t;uniform vec2 r;uniform float yaw,pitch,fov;const float PI=3.14159265;
void main(){vec2 q=(gl_FragCoord.xy/r)*2.-1.;q.x*=r.x/r.y;float f=1./tan(fov*.5);vec3 d=normalize(vec3(q.x,q.y,-f));
float cp=cos(pitch),sp=sin(pitch);d=vec3(d.x,d.y*cp-d.z*sp,d.y*sp+d.z*cp);float cy=cos(yaw),sy=sin(yaw);d=vec3(d.x*cy-d.z*sy,d.y,d.x*sy+d.z*cy);
float u=atan(d.x,-d.z)/(2.*PI)+.5;float v=acos(clamp(d.y,-1.,1.))/PI;gl_FragColor=texture2D(t,vec2(u,v));}`;

export class VRViewer {
  constructor(el, opts = {}) {
    this.el = el; this.opts = opts;
    this.yaw = 0; this.pitch = 0; this.fov = 75 * Math.PI / 180;
    this.auto = opts.autoRotate !== false; this.lastInteract = 0;
    el.classList.add('vr-root');
    el.innerHTML = `<canvas class="vr-canvas"></canvas><div class="vr-hotspots"></div><div class="vr-loading"><div class="spin"></div><span>Đang tải không gian 360°…</span></div>`;
    this.canvas = el.querySelector('canvas'); this.hsLayer = el.querySelector('.vr-hotspots'); this.loading = el.querySelector('.vr-loading');
    const gl = this.gl = this.canvas.getContext('webgl', { antialias: false, preserveDrawingBuffer: false });
    if (!gl) { this.loading.innerHTML = '<span>Thiết bị không hỗ trợ WebGL để xem 360°</span>'; return; }
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const pr = this.prog = gl.createProgram();
    gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(pr); gl.useProgram(pr);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    this.u = { r: gl.getUniformLocation(pr, 'r'), yaw: gl.getUniformLocation(pr, 'yaw'), pitch: gl.getUniformLocation(pr, 'pitch'), fov: gl.getUniformLocation(pr, 'fov') };
    this.tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, this.tex);
    for (const [k, v] of [[gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
    this.maxTex = gl.getParameter(gl.MAX_TEXTURE_SIZE);
    this._bind();
    this.scenes = opts.scenes || null;
    this._loop = this._loop.bind(this); this.raf = requestAnimationFrame(this._loop);
  }
  _bind() {
    const c = this.canvas; let drag = null; const pts = new Map();
    const down = (e) => { c.setPointerCapture?.(e.pointerId); pts.set(e.pointerId, e); drag = { x: e.clientX, y: e.clientY, yaw: this.yaw, pitch: this.pitch }; this.lastInteract = performance.now(); if (pts.size === 2) { const [a, b] = [...pts.values()]; this.pinch = { d: Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY), fov: this.fov }; } };
    const move = (e) => {
      if (!pts.has(e.pointerId)) return; pts.set(e.pointerId, e); this.lastInteract = performance.now();
      if (pts.size === 2 && this.pinch) { const [a, b] = [...pts.values()]; const d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY); this.setFov(this.pinch.fov * this.pinch.d / d); return; }
      if (!drag) return;
      const k = this.fov / c.clientHeight;
      this.yaw = drag.yaw - (e.clientX - drag.x) * k; this.pitch = Math.max(-1.45, Math.min(1.45, drag.pitch + (e.clientY - drag.y) * k));
    };
    const up = (e) => { pts.delete(e.pointerId); if (pts.size < 2) this.pinch = null; if (!pts.size) drag = null; };
    c.addEventListener('pointerdown', down); c.addEventListener('pointermove', move); c.addEventListener('pointerup', up); c.addEventListener('pointercancel', up);
    c.addEventListener('wheel', (e) => { e.preventDefault(); this.lastInteract = performance.now(); this.setFov(this.fov * (e.deltaY > 0 ? 1.08 : 0.92)); }, { passive: false });
  }
  setFov(f) { this.fov = Math.max(30 * Math.PI / 180, Math.min(100 * Math.PI / 180, f)); }
  zoom(dir) { this.lastInteract = performance.now(); this.setFov(this.fov * (dir > 0 ? 0.85 : 1.15)); }
  async load(src, type = 'pano', yaw = 0) {
    this.loading.style.display = 'flex'; this.video?.pause();
    this.yaw = yaw * Math.PI / 180; this.pitch = 0; this.video = null;
    if (type === 'video') {
      const v = document.createElement('video'); v.src = src; v.crossOrigin = 'anonymous'; v.loop = true; v.muted = true; v.playsInline = true;
      await v.play().catch(() => {}); this.video = v; this.loading.style.display = 'none'; return;
    }
    const img = new Image(); img.crossOrigin = 'anonymous';
    await new Promise((ok, bad) => { img.onload = ok; img.onerror = bad; img.src = src; }).catch(() => { this.loading.innerHTML = '<span>Không tải được ảnh 360°</span>'; throw new Error('load'); });
    let source = img;
    if (img.width > this.maxTex) {
      const cv = document.createElement('canvas'); cv.width = this.maxTex; cv.height = this.maxTex / 2;
      cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height); source = cv;
    }
    const gl = this.gl; gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, source);
    this.ready = true; this.loading.style.display = 'none';
  }
  async showScene(id) {
    const s = this.scenes?.find(x => x.id === id) || this.scenes?.[0]; if (!s) return;
    this.scene = s; this.hsLayer.innerHTML = '';
    await this.load(s.url, s.type || 'pano', s.yaw || 0);
    (s.hotspots || []).forEach(h => {
      const b = document.createElement('button'); b.className = 'vr-hs'; b.innerHTML = `<span class="vr-hs-dot"></span><span class="vr-hs-label">${(h.title || '').replace(/</g, '&lt;')}</span>`;
      b.onclick = () => h.scene ? this.showScene(h.scene) : (h.url && window.open(h.url, '_blank'));
      b._h = h; this.hsLayer.appendChild(b);
    });
    this.opts.onScene?.(s);
  }
  _project(yawD, pitchD) {
    const a = yawD * Math.PI / 180, p = pitchD * Math.PI / 180;
    let x = Math.sin(a) * Math.cos(p), y = Math.sin(p), z = -Math.cos(a) * Math.cos(p);
    const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw);
    [x, z] = [x * cy + z * sy, -x * sy + z * cy];
    const cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
    [y, z] = [y * cp + z * sp, -y * sp + z * cp];
    if (z >= -0.05) return null;
    const f = 1 / Math.tan(this.fov / 2), W = this.canvas.clientWidth, H = this.canvas.clientHeight;
    const nx = (x / -z) * f / (W / H), ny = (y / -z) * f;
    return [(nx + 1) / 2 * W, (1 - (ny + 1) / 2) * H];
  }
  _loop(t) {
    this.raf = requestAnimationFrame(this._loop);
    const gl = this.gl; if (!gl) return;
    const c = this.canvas, dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.round(c.clientWidth * dpr), h = Math.round(c.clientHeight * dpr);
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    if (this.video && this.video.readyState >= 2) { gl.bindTexture(gl.TEXTURE_2D, this.tex); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, this.video); this.ready = true; }
    if (!this.ready) return;
    if (this.auto && t - this.lastInteract > 4000) this.yaw += 0.0012;
    gl.viewport(0, 0, w, h);
    gl.uniform2f(this.u.r, w, h); gl.uniform1f(this.u.yaw, this.yaw); gl.uniform1f(this.u.pitch, this.pitch); gl.uniform1f(this.u.fov, this.fov);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    for (const b of this.hsLayer.children) {
      const pos = this._project(b._h.yaw || 0, b._h.pitch || 0);
      if (!pos) { b.style.display = 'none'; continue; }
      b.style.display = ''; b.style.transform = `translate(${pos[0]}px,${pos[1]}px)`;
    }
  }
  destroy() {
    cancelAnimationFrame(this.raf); this.video?.pause();
    const ext = this.gl?.getExtension('WEBGL_lose_context'); ext?.loseContext();
    this.el.innerHTML = '';
  }
}

/** Nhận dạng link nhúng VR360 phổ biến và chuẩn hoá thành URL iframe */
export function embedUrl(url) {
  try {
    const u = new URL(url);
    if (/kuula\.co$/.test(u.hostname) && u.pathname.startsWith('/share/') && !u.searchParams.has('fs')) u.searchParams.set('fs', '1');
    if (/matterport\.com$/.test(u.hostname)) { u.searchParams.set('play', '1'); u.searchParams.set('qs', '1'); }
    if (/youtube\.com$/.test(u.hostname) && u.searchParams.get('v')) return `https://www.youtube.com/embed/${u.searchParams.get('v')}?autoplay=1&mute=1`;
    if (/youtu\.be$/.test(u.hostname)) return `https://www.youtube.com/embed${u.pathname}?autoplay=1&mute=1`;
    return u.toString();
  } catch { return url; }
}
