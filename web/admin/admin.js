// =====================================================================
// Xanh24 — Maps for Life · Dashboard quản trị (S0 / S1 / Co-worker)
// =====================================================================
import { icon } from '/js/icons.js';
import { qrSVG } from '/js/qr.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { } }, del(k) { try { localStorage.removeItem(k); } catch { } } };
const fmtTime = (t) => t ? new Date(t * 1000).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric' }) : '—';
const ago = (t) => { if (!t) return 'chưa kết nối'; const s = Date.now() / 1000 - t; if (s < 90) return 'vừa xong'; if (s < 3600) return Math.round(s / 60) + ' phút trước'; if (s < 86400) return Math.round(s / 3600) + ' giờ trước'; return Math.round(s / 86400) + ' ngày trước'; };

const A = { token: store.get('x24_admin_token'), user: null, meta: {}, cats: [], catMap: {}, wards: [], wardMap: {}, pending: 0 };
const can = (p) => A.user?.permissions?.includes(p);

async function api(path, opt = {}) {
  const headers = { ...(opt.headers || {}) };
  if (A.token) headers.Authorization = 'Bearer ' + A.token;
  let body = opt.body;
  if (body && !(body instanceof FormData) && typeof body !== 'string') { body = JSON.stringify(body); headers['Content-Type'] = 'application/json'; }
  const r = await fetch(path, { ...opt, headers, body });
  if (r.status === 401 && !path.includes('/auth/login')) { logout(); throw new Error('Phiên đăng nhập hết hạn'); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || r.statusText);
  return d;
}
function toast(msg, kind = '') { const el = document.createElement('div'); el.className = 'toastm ' + kind; el.textContent = msg; $('#toasts').appendChild(el); setTimeout(() => el.remove(), 3800); }
const fail = (e) => toast(e.message || String(e), 'err');

// ---------------------------------------------------------------- modal
let modalClose = null;
function modal(html, { wide = false, onClose } = {}) {
  const c = $('#modalCard'); c.className = 'modal-card' + (wide ? ' wide' : ''); c.innerHTML = html; $('#modal').hidden = false;
  modalClose = onClose || null; hydrate(c); return c;
}
function closeModal() { $('#modal').hidden = true; $('#modalCard').innerHTML = ''; modalClose?.(); modalClose = null; }
$('#modal').addEventListener('click', (e) => { if (e.target.closest('[data-close]')) closeModal(); });
function confirmBox(title, text, { okText = 'Xác nhận', danger = false, input = null } = {}) {
  return new Promise((res) => {
    modal(`<div class="mh"><h3>${esc(title)}</h3></div><div class="mb"><p style="margin:0 0 12px">${text}</p>${input ? `<textarea class="in" id="cfIn" placeholder="${esc(input)}"></textarea>` : ''}</div>
      <div class="mf"><button class="btn sec" id="cfNo">Huỷ</button><button class="btn ${danger ? 'no' : 'pri'}" id="cfOk">${esc(okText)}</button></div>`);
    $('#cfNo').onclick = () => { closeModal(); res(null); };
    $('#cfOk').onclick = () => { const v = input ? $('#cfIn').value.trim() : true; closeModal(); res(v === '' ? '' : v); };
  });
}
function hydrate(root = document) { root.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon, +el.dataset.size || 20); }); }

// ---------------------------------------------------------------- auth screens
function logout() { A.token = null; A.user = null; store.del('x24_admin_token'); renderLogin(); }
function renderLogin(msg = '') {
  $('#root').innerHTML = `<div class="login">
    <div class="login-art"><img class="logo" src="/assets/logo.png" alt="Xanh24 - Maps for Life">
      <div><h1>Cổng quản trị dữ liệu bản đồ số địa phương</h1><p>Nhập liệu bằng Excel, phê duyệt nhiều cấp, quản lý màn hình tương tác, quảng cáo và kết nối VR360.</p>
      <ul><li>${icon('shield', 20)} Phân quyền Admin S0 · Admin S1 · Co-worker</li><li>${icon('upload', 20)} Nhập liệu hàng loạt kèm ảnh từ biểu mẫu Excel</li><li>${icon('device', 20)} Giám sát màn hình LCD tại các điểm công cộng</li></ul></div>
      <small style="opacity:.85">Bản quyền thuộc về Công ty TNHH Công nghệ và Truyền thông Xanh24</small></div>
    <div class="login-form"><form class="login-card" id="loginForm"><h2>Đăng nhập</h2><p class="sub">Dành cho cán bộ quản trị và cộng tác viên nhập liệu</p>
      ${msg ? `<div class="note warn" style="margin-bottom:14px">${esc(msg)}</div>` : ''}
      <div class="field"><label for="u">Tên đăng nhập</label><input class="in" id="u" autocomplete="username" required></div>
      <div class="field"><label for="p">Mật khẩu</label><input class="in" id="p" type="password" autocomplete="current-password" required></div>
      <button class="btn pri" style="width:100%;height:46px" id="loginBtn">Đăng nhập</button>
      <p class="login-foot">Xanh24 - Maps for Life · <a href="/">Mở bản đồ công khai</a></p></form></div></div>`;
  $('#loginForm').onsubmit = async (e) => {
    e.preventDefault(); $('#loginBtn').disabled = true;
    try { const d = await api('/api/auth/login', { method: 'POST', body: { username: $('#u').value, password: $('#p').value } }); A.token = d.token; store.set('x24_admin_token', d.token); A.user = d.user; await start(); }
    catch (err) { renderLogin(err.message); }
  };
}
function passwordModal(force = false) {
  modal(`<div class="mh"><h3>${force ? 'Đổi mật khẩu lần đầu' : 'Đổi mật khẩu'}</h3>${force ? '' : `<button class="btn sec icon" data-close>${icon('close', 18)}</button>`}</div>
   <div class="mb">${force ? '<div class="note warn" style="margin-bottom:14px">Vì lý do bảo mật, vui lòng đặt mật khẩu mới trước khi sử dụng.</div>' : ''}
   <div class="field"><label>Mật khẩu hiện tại</label><input class="in" type="password" id="op"></div>
   <div class="field"><label>Mật khẩu mới</label><input class="in" type="password" id="np"><span class="hint">Tối thiểu 8 ký tự, có chữ hoa, chữ thường và chữ số</span></div>
   <div class="field"><label>Nhập lại mật khẩu mới</label><input class="in" type="password" id="np2"></div></div>
   <div class="mf"><button class="btn pri" id="pwOk">Lưu mật khẩu</button></div>`);
  $('#pwOk').onclick = async () => {
    if ($('#np').value !== $('#np2').value) return toast('Mật khẩu nhập lại không khớp', 'err');
    try { await api('/api/auth/password', { method: 'POST', body: { old_password: $('#op').value, new_password: $('#np').value } }); closeModal(); toast('Đã đổi mật khẩu', 'ok'); A.user.must_change_password = 0; }
    catch (e) { fail(e); }
  };
}

// ---------------------------------------------------------------- shell
const NAV = [
  ['Tổng quan', [['dashboard', 'Bảng điều khiển', 'chart', 'stats.read']]],
  ['Dữ liệu', [['pois', 'Địa điểm', 'pin', 'poi.read'], ['import', 'Nhập Excel', 'upload', 'import.run'], ['approvals', 'Phê duyệt', 'check', 'poi.read'], ['wards', 'Ranh giới phường', 'map', 'poi.read'], ['transit', 'Xe buýt & Metro', 'metro', 'poi.read']]],
  ['Vận hành', [['devices', 'Màn hình kiosk', 'device', 'poi.read'], ['ads', 'Quảng cáo chờ', 'ad', 'poi.read'], ['modules', 'Module mở rộng', 'puzzle', 'poi.read']]],
  ['Hệ thống', [['users', 'Người dùng', 'user', 'users.manage'], ['settings', 'Cấu hình', 'settings', 'settings.manage'], ['integrations', 'API & Webhook', 'link', 'api.manage'], ['audit', 'Nhật ký', 'history', 'audit.read']]],
];
async function start() {
  try {
    if (!A.user) A.user = (await api('/api/auth/me')).user;
    const [cats, wards] = await Promise.all([api('/api/admin/categories'), api('/api/admin/wards')]);
    A.cats = cats.items; A.cats.forEach(c => A.catMap[c.id] = c); A.wards = wards.items; A.wards.forEach(w => A.wardMap[w.slug] = w);
  } catch (e) { return renderLogin(); }
  renderShell();
  window.onhashchange = route;
  route();
  if (A.user.must_change_password) passwordModal(true);
  refreshPending(); setInterval(refreshPending, 60000);
}
async function refreshPending() { try { const d = await api('/api/admin/revisions?status=pending'); A.pending = d.items.length; const b = $('#navBadge'); if (b) { b.textContent = A.pending; b.hidden = !A.pending; } } catch { } }
function renderShell() {
  const u = A.user;
  $('#root').innerHTML = `<div class="shell"><aside class="side"><a class="side-logo" href="#/dashboard"><img src="/assets/logo.png" alt="Xanh24"><span>Cổng<br>quản trị</span></a>
    <nav class="nav">${NAV.map(([g, items]) => { const vis = items.filter(i => can(i[3])); return vis.length ? `<h6>${g}</h6>` + vis.map(([k, l, ic]) => `<a href="#/${k}" data-k="${k}">${icon(ic, 19)} ${l}${k === 'approvals' ? '<span class="badge" id="navBadge" hidden>0</span>' : ''}</a>`).join('') : ''; }).join('')}</nav>
    <div class="me"><span class="av">${esc((u.full_name || u.username)[0].toUpperCase())}</span><span><b>${esc(u.full_name || u.username)}</b><small>${esc(u.role_label)}</small></span>
      <button title="Đổi mật khẩu" id="pwBtn">${icon('shield', 18)}</button><button title="Đăng xuất" id="outBtn">${icon('logout', 18)}</button></div></aside>
    <section class="main"><header class="top"><h1 id="pgTitle"></h1><span class="crumb" id="pgCrumb"></span><span class="sp"></span><span id="pgActions" style="display:flex;gap:8px"></span><span class="rolepill ${u.role}">${u.role}</span><a class="btn sec sm" href="/?mode=web" target="_blank">${icon('map', 16)} Xem bản đồ</a></header>
    <div class="page" id="page"></div><div class="foot">Bản quyền thuộc về Công ty TNHH Công nghệ và Truyền thông Xanh24 · Xanh24 - Maps for Life v${esc(A.meta.version || '1.0')}</div></section></div>`;
  $('#outBtn').onclick = logout; $('#pwBtn').onclick = () => passwordModal(false);
}
function setHead(title, crumb = '', actions = '') { $('#pgTitle').textContent = title; $('#pgCrumb').textContent = crumb; $('#pgActions').innerHTML = actions; hydrate($('#pgActions')); document.title = title + ' · Quản trị Xanh24'; }
let mapsToClean = [];
function route() {
  mapsToClean.forEach(m => { try { m.remove(); } catch { } }); mapsToClean = [];
  const h = location.hash.replace(/^#\/?/, '') || (can('stats.read') ? 'dashboard' : 'pois');
  const [page, arg] = h.split('/');
  $$('.nav a').forEach(a => a.classList.toggle('on', a.dataset.k === page));
  const fn = PAGES[page] || PAGES.dashboard;
  $('#page').innerHTML = '<div class="empty">Đang tải…</div>';
  Promise.resolve(fn(arg)).catch(fail);
}

// ---------------------------------------------------------------- helpers
const catTag = (id) => { const c = A.catMap[id]; return c ? `<span class="tag" style="border-color:${c.color}33;color:${c.color};background:${c.color}12">${esc(c.name)}</span>` : '<span class="tag">—</span>'; };
const wardName = (s) => A.wardMap[s]?.name || '<span class="muted">Ngoài ranh giới</span>';
const statusTag = (s) => ({ published: '<span class="tag green">Công khai</span>', hidden: '<span class="tag amber">Đang ẩn</span>', archived: '<span class="tag red">Lưu trữ</span>', pending: '<span class="tag amber">Chờ duyệt</span>', draft: '<span class="tag">Nháp</span>', approved: '<span class="tag green">Đã duyệt</span>', rejected: '<span class="tag red">Từ chối</span>', cancelled: '<span class="tag">Đã huỷ</span>' }[s] || `<span class="tag">${esc(s)}</span>`);
const actionTag = (a) => ({ create: '<span class="tag blue">Thêm mới</span>', update: '<span class="tag violet">Chỉnh sửa</span>', delete: '<span class="tag red">Gỡ bỏ</span>' }[a] || a);
const opt = (v, l, sel) => `<option value="${esc(v)}"${String(v) === String(sel ?? '') ? ' selected' : ''}>${esc(l)}</option>`;
const wardOptions = (sel, empty = 'Tất cả phường') => opt('', empty, sel) + A.wards.map(w => opt(w.slug, w.name, sel)).join('');
const catOptions = (sel, empty = 'Tất cả danh mục') => opt('', empty, sel) + A.cats.map(c => opt(c.id, c.name, sel)).join('');
async function upload(file, kind = 'image') { const fd = new FormData(); fd.append('file', file); fd.append('kind', kind); return api('/api/admin/upload', { method: 'POST', body: fd }); }
function pickFiles(accept, multiple = true) { return new Promise(res => { const i = document.createElement('input'); i.type = 'file'; i.accept = accept; i.multiple = multiple; i.onchange = () => res([...i.files]); i.click(); }); }
function tileStyle() {
  return 'https://tiles.openfreemap.org/styles/liberty'; // bản đồ nền nguồn mở OpenFreeMap (không cần khoá)
}

let wardGeoCache = null;
async function wardGeo() { if (!wardGeoCache) wardGeoCache = await (await fetch('/api/public/wards.geojson')).json(); return wardGeoCache; }
async function mapPicker(el, lat, lng, onPick, { wards = true } = {}) {
  const center = lat && lng ? [lng, lat] : [105.8342, 21.0278];
  const m = new maplibregl.Map({ container: el, style: tileStyle(), center, zoom: lat ? 16 : 12, dragRotate: false, attributionControl: { compact: true } });
  mapsToClean.push(m);
  m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  const mk = new maplibregl.Marker({ color: '#17A673', draggable: true }).setLngLat(center);
  if (lat && lng) mk.addTo(m);
  mk.on('dragend', () => { const p = mk.getLngLat(); onPick(p.lat, p.lng); });
  m.on('click', (e) => { mk.setLngLat(e.lngLat).addTo(m); onPick(e.lngLat.lat, e.lngLat.lng); });
  if (wards) m.on('load', async () => { const g = await wardGeo(); m.addSource('w', { type: 'geojson', data: g }); m.addLayer({ id: 'wl', type: 'line', source: 'w', paint: { 'line-color': '#14346F', 'line-width': 1.2, 'line-dasharray': [3, 2], 'line-opacity': .6 } }); });
  return { map: m, set(la, ln) { mk.setLngLat([ln, la]).addTo(m); m.flyTo({ center: [ln, la], zoom: Math.max(m.getZoom(), 15) }); } };
}
function pointInPoly(lng, lat, geom) {
  const rings = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates;
  const inR = (r) => { let ins = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const [xi, yi] = r[i], [xj, yj] = r[j]; if ((yi > lat) !== (yj > lat) && lng < (xj - xi) * (lat - yi) / (yj - yi) + xi) ins = !ins; } return ins; };
  return rings.some(p => inR(p[0]));
}

// ---------------------------------------------------------------- charts (SVG thuần, 1 trục, có tooltip)
function lineChart(el, days, series) {
  const W = 760, H = 250, pl = 40, pr = 16, pt = 12, pb = 28;
  const max = Math.max(4, ...days.flatMap(d => series.map(s => d[s.key] || 0)));
  const nice = Math.ceil(max / 4) * 4;
  const x = (i) => pl + i * (W - pl - pr) / Math.max(1, days.length - 1);
  const y = (v) => H - pb - v / nice * (H - pt - pb);
  let g = '';
  for (let k = 0; k <= 4; k++) { const v = nice * k / 4; g += `<line class="gridl" x1="${pl}" x2="${W - pr}" y1="${y(v)}" y2="${y(v)}"/><text class="axis" x="${pl - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`; }
  days.forEach((d, i) => { if (i % 5 === 0 || i === days.length - 1) g += `<text class="axis" x="${x(i)}" y="${H - 8}" text-anchor="middle">${d.day.slice(8)}/${d.day.slice(5, 7)}</text>`; });
  const lines = series.map(s => `<path d="${days.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(d[s.key] || 0).toFixed(1)}`).join('')}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`).join('');
  const last = days.length - 1;
  const ends = series.map(s => `<circle cx="${x(last)}" cy="${y(days[last][s.key] || 0)}" r="4" fill="${s.color}" stroke="#fff" stroke-width="2"/>`).join('');
  el.innerHTML = `<div class="legend">${series.map(s => `<span><i style="background:${s.color}"></i>${esc(s.label)}</span>`).join('')}</div>
    <div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Biểu đồ lượt tương tác 30 ngày">${g}${lines}${ends}<line id="xh" y1="${pt}" y2="${H - pb}" stroke="#9AA8BF" stroke-dasharray="3 3" opacity="0"/><rect x="${pl}" y="${pt}" width="${W - pl - pr}" height="${H - pt - pb}" fill="transparent" id="hit"/></svg><div class="tip" hidden></div></div>`;
  const svg = el.querySelector('svg'), tip = el.querySelector('.tip'), xh = el.querySelector('#xh');
  el.querySelector('#hit').addEventListener('pointermove', (e) => {
    const r = svg.getBoundingClientRect(); const px = (e.clientX - r.left) / r.width * W;
    const i = Math.max(0, Math.min(days.length - 1, Math.round((px - pl) / ((W - pl - pr) / Math.max(1, days.length - 1)))));
    xh.setAttribute('x1', x(i)); xh.setAttribute('x2', x(i)); xh.setAttribute('opacity', 1);
    tip.hidden = false; tip.style.left = (x(i) / W * r.width) + 'px'; tip.style.top = '40px';
    tip.innerHTML = `<b>${days[i].day.split('-').reverse().join('/')}</b>` + series.map(s => `<div class="r"><span><i class="dotc" style="background:${s.color}"></i>${esc(s.label)}</span><strong>${days[i][s.key] || 0}</strong></div>`).join('');
  });
  el.querySelector('#hit').addEventListener('pointerleave', () => { tip.hidden = true; xh.setAttribute('opacity', 0); });
}
function hbars(items, { color = 'var(--series-1)', empty = 'Chưa có dữ liệu' } = {}) {
  if (!items.length || !items.some(i => i.n)) return `<div class="empty">${empty}</div>`;
  const max = Math.max(...items.map(i => i.n));
  return items.map(i => `<div class="hbar" title="${esc(i.name)}: ${i.n}"><span class="lbl">${esc(i.name)}</span><span class="trk"><span class="bar" style="display:block;width:${Math.max(0.5, i.n / max * 100)}%;background:${i.color || color}"></span></span><span class="v">${i.n}</span></div>`).join('');
}

// ---------------------------------------------------------------- pages
const PAGES = {};

PAGES.dashboard = async () => {
  if (!can('stats.read')) return PAGES.pois();
  setHead('Bảng điều khiển', 'Tổng quan 30 ngày gần nhất', `<a class="btn grad sm" href="#/import">${icon('upload', 16)} Nhập Excel</a>`);
  const d = await api('/api/admin/stats');
  const t = d.types || {};
  $('#page').innerHTML = `
    <div class="grid g4">
      <div class="card kpi"><span class="ki">${icon('pin')}</span><span><b>${d.pois}</b><small>Địa điểm công khai</small><div class="delta">${d.pois_hidden} đang ẩn · ${d.wards} phường/xã</div></span></div>
      <a class="card kpi" href="#/approvals" style="text-decoration:none;color:inherit"><span class="ki" style="background:#FFF5E6;color:#A8640F">${icon('inbox')}</span><span><b>${d.pending}</b><small>Yêu cầu chờ duyệt</small><div class="delta">${d.ads_pending} quảng cáo chờ duyệt</div></span></a>
      <a class="card kpi" href="#/devices" style="text-decoration:none;color:inherit"><span class="ki" style="background:#E9F8F1;color:var(--green)">${icon('device')}</span><span><b>${d.devices_online}/${d.devices}</b><small>Màn hình trực tuyến</small><div class="delta">Cập nhật mỗi phút</div></span></a>
      <div class="card kpi"><span class="ki" style="background:#EFE9FF;color:var(--violet)">${icon('vr')}</span><span><b>${d.vr}</b><small>Địa điểm có VR360</small><div class="delta">${t.vr_open || 0} lượt xem 360° / 30 ngày</div></span></div>
    </div>
    <div class="grid" style="grid-template-columns:minmax(0,2fr) minmax(0,1fr);margin-top:16px">
      <div class="card"><div class="card-h"><h3>Lượt tương tác trên màn hình & web</h3><span class="sp"></span><button class="btn sec sm" id="tblToggle">${icon('list', 16)} Xem bảng</button></div><div class="card-b" id="lc"></div><div class="card-b" id="lcTable" hidden></div></div>
      <div class="card"><div class="card-h"><h3>Tổng 30 ngày</h3></div><div class="card-b">
        ${[['session_start', 'Phiên sử dụng', 'touch'], ['search', 'Lượt tìm kiếm', 'search'], ['poi_view', 'Xem địa điểm', 'eye'], ['route_request', 'Yêu cầu chỉ đường', 'route'], ['ride_click', 'Gọi xe (Grab/Xanh SM)', 'taxi'], ['ad_impression', 'Lượt hiển thị quảng cáo', 'ad']].map(([k, l, ic]) => `<div class="hbar" style="grid-template-columns:24px 1fr auto"><span class="muted">${icon(ic, 18)}</span><span class="lbl">${l}</span><span class="v" style="color:var(--navy)">${t[k] || 0}</span></div>`).join('')}
      </div></div>
    </div>
    <div class="grid g2" style="margin-top:16px">
      <div class="card"><div class="card-h"><h3>Địa điểm được xem nhiều nhất</h3></div><div class="card-b">${hbars(d.top)}</div></div>
      <div class="card"><div class="card-h"><h3>Số địa điểm theo danh mục</h3></div><div class="card-b">${hbars(d.by_category.map(c => ({ ...c, color: 'var(--series-1)' })))}</div></div>
    </div>`;
  const series = [{ key: 'poi_view', label: 'Xem địa điểm', color: 'var(--series-1)' }, { key: 'route_request', label: 'Chỉ đường', color: 'var(--series-2)' }, { key: 'search', label: 'Tìm kiếm', color: 'var(--series-3)' }];
  const cs = getComputedStyle(document.documentElement); series.forEach(s => s.color = cs.getPropertyValue(s.color.slice(4, -1)).trim());
  lineChart($('#lc'), d.days, series);
  $('#lcTable').innerHTML = `<table class="tbl"><thead><tr><th>Ngày</th>${series.map(s => `<th>${s.label}</th>`).join('')}</tr></thead><tbody>${d.days.slice().reverse().map(r => `<tr><td>${r.day.split('-').reverse().join('/')}</td>${series.map(s => `<td>${r[s.key] || 0}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  $('#tblToggle').onclick = () => { $('#lcTable').hidden = !$('#lcTable').hidden; $('#lc').hidden = !$('#lcTable').hidden; };
};

// ---- POIs list
PAGES.pois = async (arg) => {
  if (arg) return PAGES.poiEdit(arg);
  setHead('Địa điểm', 'Dữ liệu địa phương hiển thị trên bản đồ', `${can('poi.propose') ? `<a class="btn pri sm" href="#/pois/new">${icon('plus', 16)} Thêm địa điểm</a>` : ''}`);
  const f = JSON.parse(sessionStorage.getItem('x24_pf') || '{}');
  $('#page').innerHTML = `<div class="toolbar">
      <input class="in search" id="fq" placeholder="Tìm theo tên, địa chỉ, mã…" value="${esc(f.q || '')}">
      <select class="in" id="fw">${wardOptions(f.ward)}</select><select class="in" id="fc">${catOptions(f.category)}</select>
      <select class="in" id="fs">${opt('', 'Đang hoạt động', f.status)}${opt('published', 'Công khai', f.status)}${opt('hidden', 'Đang ẩn', f.status)}${opt('archived', 'Lưu trữ', f.status)}</select>
      <label style="display:flex;gap:6px;align-items:center;font-weight:600"><input type="checkbox" id="fvr" ${f.vr ? 'checked' : ''}> Có VR360</label></div>
    <div class="card"><div id="plist"></div></div>`;
  let page = 1;
  const load = async () => {
    const q = { q: $('#fq').value, ward: $('#fw').value, category: $('#fc').value, status: $('#fs').value, vr: $('#fvr').checked ? '1' : '', page, size: 50 };
    sessionStorage.setItem('x24_pf', JSON.stringify(q));
    const d = await api('/api/admin/pois?' + new URLSearchParams(Object.entries(q).filter(([, v]) => v)).toString());
    $('#plist').innerHTML = d.items.length ? `<table class="tbl"><thead><tr><th></th><th>Địa điểm</th><th>Danh mục</th><th>Phường</th><th>Trạng thái</th><th>Cập nhật</th><th></th></tr></thead><tbody>
      ${d.items.map(p => `<tr><td>${p.images?.[0] ? `<img class="th" src="${esc(p.images[0].thumb || p.images[0].url)}" alt="">` : `<span class="th" style="display:grid;place-items:center;color:${A.catMap[p.category]?.color}">${icon(A.catMap[p.category]?.icon || 'pin', 22)}</span>`}</td>
        <td><div class="name">${esc(p.name)}</div><div class="sub">${esc(p.code || '')} · ${esc(p.address || '')}</div></td>
        <td>${catTag(p.category)} ${p.vr360 ? '<span class="tag violet">VR360</span>' : ''}</td><td>${wardName(p.ward_slug)}</td>
        <td>${statusTag(p.status)} ${p.pending ? `<span class="tag amber">${p.pending} chờ duyệt</span>` : ''}</td><td class="sub">${fmtTime(p.updated_at)}</td>
        <td style="text-align:right;white-space:nowrap"><a class="btn sec sm" href="#/pois/${p.id}">${icon('edit', 16)} Sửa</a>
        ${can('poi.publish') ? `<button class="btn sec sm icon" data-st="${p.id}" data-to="${p.status === 'published' ? 'hidden' : 'published'}" title="${p.status === 'published' ? 'Ẩn' : 'Công khai'}">${icon(p.status === 'published' ? 'eyeoff' : 'eye', 16)}</button>` : ''}
        <a class="btn sec sm icon" href="/?mode=web&poi=${p.id}" target="_blank" title="Xem trên bản đồ">${icon('map', 16)}</a></td></tr>`).join('')}</tbody></table>
      <div class="toolbar" style="padding:12px 16px;margin:0"><span class="muted">${d.total} địa điểm</span><span style="flex:1"></span>${page > 1 ? '<button class="btn sec sm" id="pv">‹ Trước</button>' : ''}${page * 50 < d.total ? '<button class="btn sec sm" id="nx">Sau ›</button>' : ''}</div>`
      : `<div class="empty">${icon('inbox', 36)}<p>Chưa có địa điểm phù hợp bộ lọc</p></div>`;
    $('#pv') && ($('#pv').onclick = () => { page--; load(); }); $('#nx') && ($('#nx').onclick = () => { page++; load(); });
    $$('[data-st]').forEach(b => b.onclick = async () => { try { await api(`/api/admin/pois/${b.dataset.st}/status`, { method: 'POST', body: { status: b.dataset.to } }); toast('Đã cập nhật trạng thái', 'ok'); load(); } catch (e) { fail(e); } });
  };
  let tmo; $('#fq').oninput = () => { clearTimeout(tmo); tmo = setTimeout(() => { page = 1; load(); }, 250); };
  ['#fw', '#fc', '#fs', '#fvr'].forEach(s => $(s).onchange = () => { page = 1; load(); });
  await load();
};

// ---- POI editor
PAGES.poiEdit = async (id) => {
  const isNew = id === 'new';
  let p = { name: '', category: A.cats[0]?.id, images: [], vr360: null, lat: null, lng: null, featured: 0 };
  let revs = [];
  if (!isNew) { p = await api(`/api/admin/pois/${id}`); revs = p.revisions || []; }
  const direct = can('poi.publish');
  setHead(isNew ? 'Thêm địa điểm' : p.name, isNew ? 'Tạo mới' : `${p.code} · ${direct ? 'Admin chỉnh sửa trực tiếp' : 'Thay đổi sẽ gửi Admin S1 phê duyệt'}`, `<a class="btn sec sm" href="#/pois">${icon('back', 16)} Danh sách</a>`);
  const v = p.vr360 || {};
  $('#page').innerHTML = `<div class="editor">
    <div class="grid">
      <div class="card"><div class="card-h"><h3>Thông tin chính</h3></div><div class="card-b">
        <div class="field"><label>Tên địa điểm *</label><input class="in" id="e_name" value="${esc(p.name)}"></div>
        <div class="row2"><div class="field"><label>Danh mục *</label><select class="in" id="e_category">${A.cats.map(c => opt(c.id, c.name, p.category)).join('')}</select></div>
          <div class="field"><label>Tên tiếng Anh</label><input class="in" id="e_name_en" value="${esc(p.name_en || '')}"></div></div>
        <div class="field"><label>Địa chỉ</label><input class="in" id="e_address" value="${esc(p.address || '')}"></div>
        <div class="row3"><div class="field"><label>Điện thoại</label><input class="in" id="e_phone" value="${esc(p.phone || '')}"></div>
          <div class="field"><label>Giờ mở cửa</label><input class="in" id="e_hours" value="${esc(p.hours || '')}" placeholder="08:00–17:00 (T2–T6)"></div>
          <div class="field"><label>Website</label><input class="in" id="e_website" value="${esc(p.website || '')}"></div></div>
        <div class="field"><label>Mô tả / nội dung</label><textarea class="in" id="e_description" rows="6">${esc(p.description || '')}</textarea></div>
        <div class="row2"><div class="field"><label>Từ khoá tìm kiếm</label><input class="in" id="e_tags" value="${esc(p.tags || '')}" placeholder="một cửa, hành chính"></div>
          <div class="field"><label>Hiển thị</label><label style="display:flex;gap:8px;align-items:center;height:42px;font-weight:600"><input type="checkbox" id="e_featured" ${p.featured ? 'checked' : ''}> Địa điểm nổi bật</label></div></div>
      </div></div>
      <div class="card"><div class="card-h"><h3>Hình ảnh</h3><span class="sp"></span><span class="muted">Ảnh đầu tiên là ảnh đại diện</span></div><div class="card-b"><div class="imgs" id="imgs"></div></div></div>
      <div class="card"><div class="card-h"><h3>${icon('vr', 20)} Cổng kết nối VR360</h3></div><div class="card-b">
        <div class="field"><label>Loại nội dung 360°</label><select class="in" id="vr_type">${opt('', 'Không có', v.type)}${opt('pano', 'Ảnh 360° (equirectangular 2:1)', v.type)}${opt('embed', 'Nhúng tour (Kuula, Matterport, 3DVista, Street View…)', v.type)}${opt('video', 'Video 360° (MP4)', v.type)}${opt('tour', 'Tour nhiều cảnh có điểm nóng (JSON)', v.type)}</select></div>
        <div id="vrBox"></div>
      </div></div>
    </div>
    <div class="grid">
      <div class="card"><div class="card-h"><h3>Vị trí trên bản đồ</h3></div><div class="card-b">
        <div class="minimap" id="mm"></div>
        <div class="row2" style="margin-top:12px"><div class="field"><label>Vĩ độ (lat)</label><input class="in" id="e_lat" value="${p.lat ?? ''}"></div><div class="field"><label>Kinh độ (lng)</label><input class="in" id="e_lng" value="${p.lng ?? ''}"></div></div>
        <div class="note info" id="wardInfo">Nhấn vào bản đồ hoặc kéo ghim để đặt vị trí. Có thể dán “21.0285, 105.8542” vào ô Vĩ độ.</div>
      </div></div>
      ${!isNew ? `<div class="card"><div class="card-h"><h3>Lịch sử thay đổi</h3></div><div>${revs.length ? revs.map(r => `<div class="revitem" style="cursor:default"><span>${actionTag(r.action)}</span><span style="flex:1"><b>${statusTag(r.status)} bởi ${esc(r.created_by_name || '—')}</b><small>${fmtTime(r.created_at)}${r.review_note ? ' · ' + esc(r.review_note) : ''}</small></span></div>`).join('') : '<div class="empty">Chưa có</div>'}</div></div>
        ${can('poi.propose') ? `<div class="card"><div class="card-b"><button class="btn no" id="delBtn">${icon('trash', 16)} ${direct ? 'Gỡ khỏi bản đồ (lưu trữ)' : 'Đề xuất gỡ bỏ'}</button>${can('poi.purge') ? ` <button class="btn no" id="purgeBtn">${icon('trash', 16)} Xoá vĩnh viễn</button>` : ''}</div></div>` : ''}` : ''}
    </div></div>
    <div class="savebar">${!direct ? '<span class="muted" style="margin-right:auto;align-self:center">Bạn là Co-worker: thay đổi sẽ được gửi Admin S1 duyệt trước khi công khai.</span>' : ''}
      <button class="btn sec" data-save="draft">Lưu nháp</button><button class="btn ${direct ? 'sec' : 'pri'}" data-save="submit">${icon('send', 16)} Gửi phê duyệt</button>${direct ? `<button class="btn pri" data-save="publish">${icon('check', 16)} Lưu & công khai</button>` : ''}</div>`;
  // images
  let images = [...(p.images || [])];
  const drawImgs = () => {
    $('#imgs').innerHTML = images.map((im, i) => `<div class="im"><img src="${esc(im.thumb || im.url)}" alt="">${i === 0 ? '<span class="tag green first">Đại diện</span>' : ''}<button class="x" data-rm="${i}">${icon('close', 14)}</button><span class="mv">${i > 0 ? `<button data-l="${i}">${icon('back', 14)}</button>` : ''}${i < images.length - 1 ? `<button data-r="${i}">${icon('chevron', 14)}</button>` : ''}</span></div>`).join('') + `<div class="drop" id="imgDrop">${icon('upload', 26)}<br>Tải ảnh lên<br><small>hoặc kéo thả</small></div>`;
    $$('[data-rm]').forEach(b => b.onclick = () => { images.splice(+b.dataset.rm, 1); drawImgs(); });
    $$('[data-l]').forEach(b => b.onclick = () => { const i = +b.dataset.l;[images[i - 1], images[i]] = [images[i], images[i - 1]]; drawImgs(); });
    $$('[data-r]').forEach(b => b.onclick = () => { const i = +b.dataset.r;[images[i + 1], images[i]] = [images[i], images[i + 1]]; drawImgs(); });
    const dz = $('#imgDrop');
    const doUp = async (files) => { for (const f of files) { try { dz.textContent = 'Đang tải…'; images.push(await upload(f)); } catch (e) { fail(e); } } drawImgs(); };
    dz.onclick = async () => doUp(await pickFiles('image/*'));
    dz.ondragover = (e) => { e.preventDefault(); dz.classList.add('over'); }; dz.ondragleave = () => dz.classList.remove('over');
    dz.ondrop = (e) => { e.preventDefault(); doUp([...e.dataTransfer.files].filter(f => f.type.startsWith('image/'))); };
  };
  drawImgs();
  // VR
  let vr = p.vr360 ? JSON.parse(JSON.stringify(p.vr360)) : null;
  const drawVR = () => {
    const tp = $('#vr_type').value; const box = $('#vrBox');
    if (!tp) { vr = null; box.innerHTML = '<p class="muted" style="margin:0">Chọn loại nội dung để kết nối tham quan 360° cho địa điểm này.</p>'; return; }
    vr = { ...(vr || {}), type: tp };
    if (tp === 'tour') box.innerHTML = `<div class="field"><label>Cấu hình cảnh (JSON)</label><textarea class="in" id="vr_json" rows="10" style="font-family:monospace;font-size:.8rem">${esc(JSON.stringify(vr.scenes || [{ id: 'canh-1', title: 'Cảnh 1', url: '', yaw: 0, hotspots: [{ yaw: 40, pitch: 0, scene: 'canh-2', title: 'Sang cảnh 2' }] }, { id: 'canh-2', title: 'Cảnh 2', url: '', hotspots: [] }], null, 2))}</textarea><span class="hint">Mỗi cảnh: id, title, url (ảnh 360), yaw (hướng nhìn ban đầu, độ); hotspots: yaw, pitch, scene (id cảnh đích) hoặc url.</span></div><button class="btn sec sm" id="vrUpTour">${icon('upload', 16)} Tải ảnh 360 & chép link</button> <span id="vrUpOut" class="muted"></span>`;
    else box.innerHTML = `<div class="field"><label>${tp === 'embed' ? 'Link nhúng (https://)' : 'Đường dẫn tệp'}</label><input class="in" id="vr_url" value="${esc(vr.url || '')}" placeholder="${tp === 'embed' ? 'https://kuula.co/share/…  ·  https://my.matterport.com/show/?m=…' : '/uploads/… hoặc https://…'}"></div>
      ${tp !== 'embed' ? `<button class="btn sec sm" id="vrUp">${icon('upload', 16)} Tải ${tp === 'video' ? 'video' : 'ảnh'} 360° lên</button>` : ''}
      <div class="field" style="margin-top:12px"><label>Hướng nhìn ban đầu (độ)</label><input class="in" id="vr_yaw" type="number" value="${vr.yaw || 0}" style="max-width:140px"></div>
      ${vr.url && tp === 'pano' ? `<img src="${esc(vr.thumb || vr.url)}" style="width:100%;border-radius:10px;margin-top:6px">` : ''}`;
    $('#vrUp') && ($('#vrUp').onclick = async () => { const [f] = await pickFiles(tp === 'video' ? 'video/*' : 'image/*', false); if (!f) return; try { toast('Đang tải lên…'); const r = await upload(f, tp === 'video' ? 'video' : 'pano'); vr.url = r.url; vr.thumb = r.thumb; if (r.w && Math.abs(r.w / r.h - 2) > 0.05) toast('Lưu ý: ảnh 360 chuẩn nên có tỉ lệ 2:1', 'err'); drawVR(); } catch (e) { fail(e); } });
    $('#vrUpTour') && ($('#vrUpTour').onclick = async () => { const [f] = await pickFiles('image/*', false); if (!f) return; const r = await upload(f, 'pano'); $('#vrUpOut').innerHTML = `<code>${esc(r.url)}</code>`; });
  };
  $('#vr_type').onchange = drawVR; drawVR();
  // map
  const setWardInfo = async () => {
    const la = parseFloat($('#e_lat').value), ln = parseFloat($('#e_lng').value); if (!la || !ln) return;
    const g = await wardGeo(); const f = g.features.find(f => pointInPoly(ln, la, f.geometry));
    $('#wardInfo').innerHTML = f ? `${icon('check', 16)} Thuộc <b>${esc(f.properties.name)}</b> (tự xác định theo ranh giới)` : 'Vị trí nằm ngoài các ranh giới phường đã số hoá.';
  };
  const pk = await mapPicker($('#mm'), p.lat, p.lng, (la, ln) => { $('#e_lat').value = la.toFixed(6); $('#e_lng').value = ln.toFixed(6); setWardInfo(); });
  setWardInfo();
  $('#e_lat').onchange = () => { const m = $('#e_lat').value.match(/(-?\d+\.\d+)\s*[, ]\s*(-?\d+\.\d+)/); if (m) { $('#e_lat').value = m[1]; $('#e_lng').value = m[2]; } const la = parseFloat($('#e_lat').value), ln = parseFloat($('#e_lng').value); if (la && ln) { pk.set(la, ln); setWardInfo(); } };
  $('#e_lng').onchange = $('#e_lat').onchange;
  // save
  const collect = () => {
    const d = {}; ['name', 'name_en', 'category', 'address', 'phone', 'hours', 'website', 'description', 'tags'].forEach(k => d[k] = $('#e_' + k).value);
    d.lat = parseFloat($('#e_lat').value); d.lng = parseFloat($('#e_lng').value); d.featured = $('#e_featured').checked ? 1 : 0; d.images = images;
    if (vr) {
      if (vr.type === 'tour') { try { vr.scenes = JSON.parse($('#vr_json').value); } catch { throw new Error('JSON cấu hình tour không hợp lệ'); } }
      else { vr.url = $('#vr_url').value.trim(); vr.yaw = +$('#vr_yaw').value || 0; if (!vr.url) throw new Error('Vui lòng nhập link/tệp VR360'); }
    }
    d.vr360 = vr; return d;
  };
  $$('[data-save]').forEach(b => b.onclick = async () => {
    try {
      const data = collect(); const mode = b.dataset.save;
      const r = isNew ? await api('/api/admin/pois', { method: 'POST', body: { data, mode } }) : await api(`/api/admin/pois/${id}`, { method: 'PUT', body: { data, mode } });
      if (r.unchanged) return toast('Không có thay đổi');
      toast(r.status === 'approved' ? 'Đã lưu và công khai' : r.status === 'pending' ? 'Đã gửi yêu cầu phê duyệt' : 'Đã lưu nháp', 'ok');
      refreshPending();
      location.hash = r.status === 'approved' && r.poi_id ? `#/pois/${r.poi_id}` : '#/approvals';
    } catch (e) { fail(e); }
  });
  $('#delBtn') && ($('#delBtn').onclick = async () => { const reason = await confirmBox('Gỡ địa điểm', `Gỡ “${esc(p.name)}” khỏi bản đồ công khai?`, { okText: 'Gỡ bỏ', danger: true, input: 'Lý do (không bắt buộc)' }); if (reason === null) return; try { const r = await api(`/api/admin/pois/${id}`, { method: 'DELETE', body: { reason } }); toast(r.status === 'approved' ? 'Đã gỡ khỏi bản đồ' : 'Đã gửi đề xuất gỡ bỏ', 'ok'); location.hash = '#/pois'; } catch (e) { fail(e); } });
  $('#purgeBtn') && ($('#purgeBtn').onclick = async () => { if (await confirmBox('Xoá vĩnh viễn', 'Thao tác không thể hoàn tác. Tiếp tục?', { okText: 'Xoá vĩnh viễn', danger: true }) === null) return; try { await api(`/api/admin/pois/${id}?purge=1`, { method: 'DELETE' }); toast('Đã xoá', 'ok'); location.hash = '#/pois'; } catch (e) { fail(e); } });
};

// ---- Import Excel
PAGES.import = async () => {
  setHead('Nhập dữ liệu từ Excel', 'Tải biểu mẫu → điền dữ liệu & chèn ảnh → tải lên → kiểm tra → gửi phê duyệt');
  const batches = await api('/api/admin/import/batches');
  $('#page').innerHTML = `<div class="grid g3">
      <div class="card"><div class="card-b"><div class="kpi" style="padding:0"><span class="ki">${icon('download')}</span><span><b style="font-size:1.05rem">1 · Tải biểu mẫu</b><small>Có sẵn danh sách danh mục, phường, hướng dẫn</small></span></div><a class="btn pri" style="margin-top:14px;width:100%" href="/api/admin/import/template">${icon('download', 18)} Tải biểu mẫu Excel</a></div></div>
      <div class="card"><div class="card-b"><div class="kpi" style="padding:0"><span class="ki">${icon('edit')}</span><span><b style="font-size:1.05rem">2 · Điền dữ liệu</b><small>Mỗi dòng 1 địa điểm. Ảnh: chèn thẳng vào ô, hoặc ghi tên tệp và nén .zip</small></span></div><p class="muted" style="margin:12px 0 0;font-size:.8rem">Hỗ trợ Excel 365 (Place in Cell), WPS (DISPIMG), ảnh nổi trong dòng, link ảnh. VR360: link tour hoặc tệp ảnh 360.</p></div></div>
      <div class="card"><div class="card-b"><div class="kpi" style="padding:0"><span class="ki">${icon('check')}</span><span><b style="font-size:1.05rem">3 · Tải lên & gửi duyệt</b><small>${can('poi.publish') ? 'Admin có thể công khai ngay' : 'Admin S1 sẽ phê duyệt trước khi công khai'}</small></span></div></div></div>
    </div>
    <div class="card" style="margin-top:16px"><div class="card-b">
      <div class="row2"><div><div class="drop bigdrop" id="xDrop">${icon('upload', 30)}<br><b>Chọn tệp Excel (.xlsx)</b><br><small>hoặc kéo thả vào đây</small></div><div class="muted" id="xName" style="margin-top:8px"></div></div>
        <div><div class="drop bigdrop" id="zDrop">${icon('upload', 30)}<br><b>Gói ảnh .zip (không bắt buộc)</b><br><small>chứa các tệp ảnh được ghi tên trong Excel</small></div><div class="muted" id="zName" style="margin-top:8px"></div></div></div>
      <div style="margin-top:14px;display:flex;gap:10px"><button class="btn grad" id="xGo" disabled>${icon('eye', 18)} Kiểm tra dữ liệu</button></div></div></div>
    <div id="xPrev"></div>
    <div class="card" style="margin-top:16px"><div class="card-h"><h3>Các lần nhập gần đây</h3></div>${batches.items.length ? `<table class="tbl"><thead><tr><th>Tệp</th><th>Thời gian</th><th>Dòng</th><th>Hợp lệ</th><th>Trạng thái</th></tr></thead><tbody>${batches.items.map(b => `<tr><td class="name">${esc(b.filename)}</td><td class="sub">${fmtTime(b.created_at)}</td><td>${b.total}</td><td>${b.valid}</td><td>${b.status === 'preview' ? '<span class="tag">Chưa gửi</span>' : `<a class="tag green" href="#/approvals" style="text-decoration:none">${esc(b.status.replace('committed:', 'Đã gửi · '))}</a>`}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">Chưa có</div>'}</div>`;
  let xf = null, zf = null;
  const bindDrop = (el, accept, set) => {
    el.onclick = async () => { const [f] = await pickFiles(accept, false); if (f) set(f); };
    el.ondragover = (e) => { e.preventDefault(); el.classList.add('over'); }; el.ondragleave = () => el.classList.remove('over');
    el.ondrop = (e) => { e.preventDefault(); el.classList.remove('over'); const f = e.dataTransfer.files[0]; if (f) set(f); };
  };
  bindDrop($('#xDrop'), '.xlsx,.xlsm', (f) => { xf = f; $('#xName').textContent = '✓ ' + f.name; $('#xGo').disabled = false; });
  bindDrop($('#zDrop'), '.zip', (f) => { zf = f; $('#zName').textContent = '✓ ' + f.name; });
  $('#xGo').onclick = async () => {
    const fd = new FormData(); fd.append('file', xf); if (zf) fd.append('zip', zf);
    $('#xGo').disabled = true; $('#xGo').textContent = 'Đang đọc tệp…';
    try { const r = await api('/api/admin/import/preview', { method: 'POST', body: fd }); showPreview(r); }
    catch (e) { fail(e); } finally { $('#xGo').disabled = false; $('#xGo').innerHTML = `${icon('eye', 18)} Kiểm tra dữ liệu`; }
  };
  function showPreview(r) {
    const bad = r.total - r.valid;
    $('#xPrev').innerHTML = `<div class="card" style="margin-top:16px"><div class="card-h"><h3>Kết quả kiểm tra: ${r.valid}/${r.total} dòng hợp lệ</h3><span class="sp"></span>${bad ? `<span class="tag red">${bad} dòng lỗi sẽ bị bỏ qua</span>` : '<span class="tag green">Tất cả hợp lệ</span>'}</div>
      <div style="max-height:560px;overflow:auto"><table class="tbl"><thead><tr><th>Dòng</th><th></th><th>Địa điểm</th><th>Danh mục</th><th>Phường</th><th>Toạ độ</th><th>Ảnh</th><th>VR360</th><th>Ghi chú</th></tr></thead><tbody>
      ${r.rows.map(x => { const d = x.data; return `<tr style="${x.errors.length ? 'background:#FFF8F8' : ''}"><td>${x.row}</td><td>${x.errors.length ? `<span class="tag red">Lỗi</span>` : x.action === 'update' ? '<span class="tag violet">Cập nhật</span>' : '<span class="tag blue">Mới</span>'}</td>
        <td><div class="name">${esc(d.name)}</div><div class="sub">${esc(d.address || '')}</div></td><td>${d.category ? catTag(d.category) : '—'}</td><td>${d.ward_slug ? esc(A.wardMap[d.ward_slug]?.short || d.ward_slug) : '—'}</td>
        <td class="sub">${d.lat != null ? `${(+d.lat).toFixed(5)}, ${(+d.lng).toFixed(5)}` : '—'}</td>
        <td><div style="display:flex;gap:4px">${(d.images || []).slice(0, 4).map(i => `<img class="th" style="width:40px;height:40px" src="${esc(i.thumb)}">`).join('')}${d.images?.length > 4 ? `<span class="tag">+${d.images.length - 4}</span>` : ''}</div></td>
        <td>${d.vr360 ? `<span class="tag violet">${esc(d.vr360.type)}</span>` : ''}</td>
        <td style="font-size:.78rem">${x.errors.map(e => `<div style="color:#B03030">✕ ${esc(e)}</div>`).join('')}${x.warnings.map(e => `<div style="color:#A8640F">! ${esc(e)}</div>`).join('')}</td></tr>`; }).join('')}</tbody></table></div>
      <div class="mf" style="position:static">${r.valid ? `<button class="btn sec" data-commit="draft">Lưu thành bản nháp</button><button class="btn ${can('poi.publish') ? 'sec' : 'pri'}" data-commit="submit">${icon('send', 16)} Gửi phê duyệt ${r.valid} địa điểm</button>${can('poi.publish') ? `<button class="btn pri" data-commit="publish">${icon('check', 16)} Công khai ngay</button>` : ''}` : '<span class="muted">Không có dòng hợp lệ để nhập</span>'}</div></div>`;
    $$('[data-commit]').forEach(b => b.onclick = async () => {
      try { const res = await api(`/api/admin/import/${r.batch_id}/commit`, { method: 'POST', body: { mode: b.dataset.commit } }); toast(`Đã xử lý ${res.done} địa điểm`, 'ok'); refreshPending(); location.hash = b.dataset.commit === 'publish' ? '#/pois' : '#/approvals'; }
      catch (e) { fail(e); }
    });
    $('#xPrev').scrollIntoView({ behavior: 'smooth' });
  }
};

// ---- Approvals
PAGES.approvals = async () => {
  const approver = can('poi.approve');
  setHead('Phê duyệt', approver ? 'Duyệt yêu cầu thay đổi dữ liệu từ Co-worker' : 'Theo dõi yêu cầu bạn đã gửi');
  const tab = sessionStorage.getItem('x24_apt') || 'pending';
  $('#page').innerHTML = `<div class="tabs" id="aptabs">${[['pending', 'Chờ duyệt'], ['draft', 'Bản nháp'], ['rejected', 'Bị từ chối'], ['approved', 'Đã duyệt']].map(([k, l]) => `<button data-t="${k}" class="${k === tab ? 'on' : ''}">${l}</button>`).join('')}</div>
    <div class="split"><div class="card" style="overflow:hidden"><div class="card-h">${approver ? '<label style="display:flex;gap:8px;align-items:center;font-weight:700"><input type="checkbox" id="selAll"> Chọn tất cả</label>' : '<h3>Danh sách</h3>'}<span class="sp"></span><span id="bulkBox"></span></div><div id="rlist" style="max-height:calc(100vh - 260px);overflow:auto"></div></div>
    <div class="card" id="rdet"><div class="empty">${icon('inbox', 36)}<p>Chọn một yêu cầu để xem chi tiết</p></div></div></div>`;
  $$('#aptabs button').forEach(b => b.onclick = () => { sessionStorage.setItem('x24_apt', b.dataset.t); PAGES.approvals(); });
  const d = await api('/api/admin/revisions?status=' + tab);
  const items = d.items;
  $('#rlist').innerHTML = items.length ? items.map(r => `<div class="revitem" data-id="${r.id}">${approver && tab === 'pending' ? `<input type="checkbox" class="rsel" value="${r.id}" onclick="event.stopPropagation()">` : ''}<span style="flex:1;min-width:0"><b>${esc(r.data?.name || r.poi_name || '(không tên)')}</b><small>${actionTag(r.action)} · ${esc(r.submitted_by_name || r.created_by_name || '')} · ${fmtTime(r.submitted_at || r.created_at)}${r.batch_id ? ' · Excel' : ''}</small></span>${statusTag(r.status)}</div>`).join('') : `<div class="empty">Không có yêu cầu</div>`;
  if (approver && tab === 'pending' && items.length) {
    $('#bulkBox').innerHTML = `<button class="btn ok sm" id="bOk">${icon('check', 16)} Duyệt đã chọn</button> <button class="btn no sm" id="bNo">Từ chối</button>`;
    $('#selAll').onchange = (e) => $$('.rsel').forEach(c => c.checked = e.target.checked);
    const bulk = async (action) => {
      const ids = $$('.rsel').filter(c => c.checked).map(c => +c.value); if (!ids.length) return toast('Chưa chọn yêu cầu nào', 'err');
      let note = ''; if (action === 'reject') { note = await confirmBox('Từ chối hàng loạt', `Từ chối ${ids.length} yêu cầu?`, { okText: 'Từ chối', danger: true, input: 'Lý do từ chối (bắt buộc)' }); if (!note) return; }
      try { const r = await api('/api/admin/revisions/bulk', { method: 'POST', body: { ids, action, note } }); toast(`Đã xử lý ${r.ok} yêu cầu`, 'ok'); refreshPending(); PAGES.approvals(); } catch (e) { fail(e); }
    };
    $('#bOk').onclick = () => bulk('approve'); $('#bNo').onclick = () => bulk('reject');
  }
  $$('.revitem').forEach(el => el.onclick = () => { $$('.revitem').forEach(x => x.classList.toggle('on', x === el)); showRev(+el.dataset.id); });
  async function showRev(id) {
    const r = await api(`/api/admin/revisions/${id}`); const cur = r.current || {}; const data = r.data || {};
    const LABEL = { name: 'Tên', name_en: 'Tên tiếng Anh', category: 'Danh mục', ward_slug: 'Phường', address: 'Địa chỉ', phone: 'Điện thoại', website: 'Website', hours: 'Giờ mở cửa', description: 'Mô tả', lat: 'Vĩ độ', lng: 'Kinh độ', images: 'Hình ảnh', vr360: 'VR360', tags: 'Từ khoá', featured: 'Nổi bật', reason: 'Lý do gỡ' };
    const show = (k, v) => { if (v == null || v === '') return '<span class="muted">—</span>'; if (k === 'images') return `<div style="display:flex;gap:4px;flex-wrap:wrap">${v.map(i => `<img src="${esc(i.thumb || i.url)}" style="width:54px;height:54px;object-fit:cover;border-radius:8px">`).join('')}</div>`; if (k === 'vr360') return `${esc(v.type)} · ${esc(v.url || (v.scenes || []).length + ' cảnh')}`; if (k === 'category') return esc(A.catMap[v]?.name || v); if (k === 'ward_slug') return esc(A.wardMap[v]?.name || v); if (k === 'featured') return v ? 'Có' : 'Không'; return esc(String(v)); };
    const keys = Object.keys(data);
    $('#rdet').innerHTML = `<div class="card-h"><h3>${esc(data.name || cur.name || '')}</h3>${actionTag(r.action)} ${statusTag(r.status)}</div><div class="card-b">
      <p class="muted" style="margin-top:0">Gửi bởi <b>${esc(r.submitted_by_name || r.created_by_name || '')}</b> lúc ${fmtTime(r.submitted_at || r.created_at)}${r.reviewed_by_name ? ` · Xử lý bởi <b>${esc(r.reviewed_by_name)}</b> ${fmtTime(r.reviewed_at)}` : ''}</p>
      ${r.review_note ? `<div class="note ${r.status === 'rejected' ? 'warn' : ''}" style="margin-bottom:12px">Ghi chú duyệt: ${esc(r.review_note)}</div>` : ''}
      <div class="diff"><div class="dr hd"><div>Trường</div><div>${r.action === 'create' ? '' : 'Hiện tại'}</div><div>${r.action === 'delete' ? '' : 'Đề xuất'}</div></div>
      ${keys.map(k => `<div class="dr"><div class="k">${LABEL[k] || k}</div><div class="${r.action === 'update' ? 'old' : ''}">${r.action === 'create' ? '' : show(k, cur[k])}</div><div class="${r.action !== 'delete' ? 'new' : ''}">${show(k, data[k])}</div></div>`).join('')}</div>
      ${data.lat ? `<div class="minimap" id="rmap" style="height:220px;margin-top:14px"></div>` : ''}
    </div>
    <div class="mf" style="position:static">
      ${r.status === 'pending' && approver ? `<button class="btn no" id="rNo">${icon('x', 16)} Từ chối</button><button class="btn ok" id="rOk">${icon('check', 16)} Duyệt & công khai</button>` : ''}
      ${['draft', 'rejected'].includes(r.status) ? `<button class="btn sec" id="rCancel">Huỷ yêu cầu</button><button class="btn pri" id="rSubmit">${icon('send', 16)} Gửi phê duyệt</button>` : ''}
      ${r.status === 'pending' && !approver ? `<button class="btn sec" id="rCancel">Rút yêu cầu</button>` : ''}
    </div>`;
    if (data.lat) { const m = new maplibregl.Map({ container: 'rmap', style: tileStyle(), center: [data.lng, data.lat], zoom: 16, attributionControl: false }); mapsToClean.push(m); new maplibregl.Marker({ color: '#17A673' }).setLngLat([data.lng, data.lat]).addTo(m); if (cur.lat && r.action === 'update' && (cur.lat !== data.lat || cur.lng !== data.lng)) new maplibregl.Marker({ color: '#D64545' }).setLngLat([cur.lng, cur.lat]).addTo(m); }
    const act = async (a, note = '') => { try { await api(`/api/admin/revisions/${id}/${a}`, { method: 'POST', body: { note } }); toast('Đã cập nhật', 'ok'); refreshPending(); PAGES.approvals(); } catch (e) { fail(e); } };
    $('#rOk') && ($('#rOk').onclick = () => act('approve'));
    $('#rNo') && ($('#rNo').onclick = async () => { const n = await confirmBox('Từ chối yêu cầu', 'Người gửi sẽ thấy lý do để chỉnh sửa và gửi lại.', { okText: 'Từ chối', danger: true, input: 'Lý do từ chối (bắt buộc)' }); if (n) act('reject', n); else if (n === '') toast('Cần nhập lý do', 'err'); });
    $('#rSubmit') && ($('#rSubmit').onclick = () => act('submit'));
    $('#rCancel') && ($('#rCancel').onclick = () => act('cancel'));
  }
};

// ---- Ads
PAGES.ads = async () => {
  setHead('Quảng cáo màn hình chờ', 'Nội dung phát khi kiosk không có thao tác (idle)', can('ads.propose') ? `<button class="btn pri sm" id="adNew">${icon('plus', 16)} Thêm nội dung</button>` : '');
  const [d, devs] = await Promise.all([api('/api/admin/ads'), api('/api/admin/devices')]);
  const prev = (a) => a.media_type === 'image' ? `<img src="${esc(a.media_url)}">` : a.media_type === 'video' ? `<video src="${esc(a.media_url)}" muted></video>` : a.media_type === 'url' ? `<div class="empty" style="color:#fff">${esc(a.media_url)}</div>` : a.html;
  $('#page').innerHTML = `<div class="note info" style="margin-bottom:16px">Nội dung phát theo thứ tự ưu tiên (cao trước). Co-worker tạo nội dung ở trạng thái chờ duyệt; Admin S1 duyệt để phát. Có thể giới hạn theo thời gian, thiết bị hoặc phường.</div>
    <div class="grid g3">${d.items.map(a => `<div class="card"><div class="card-b"><div class="adprev">${prev(a)}</div>
      <div style="display:flex;gap:8px;align-items:center;margin-top:12px"><b style="flex:1">${esc(a.title)}</b>${statusTag(a.status === 'published' ? 'published' : a.status)}</div>
      <div class="sub muted" style="font-size:.8rem">${esc(a.media_type)} · ${a.duration_sec}s · ưu tiên ${a.priority}${a.start_at ? ' · từ ' + fmtTime(a.start_at) : ''}${a.end_at ? ' đến ' + fmtTime(a.end_at) : ''}${a.target_devices?.length ? ' · ' + a.target_devices.length + ' thiết bị' : ''}</div>
      <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap">${can('ads.propose') ? `<button class="btn sec sm" data-edit="${a.id}">${icon('edit', 16)} Sửa</button>` : ''}${can('ads.publish') && a.status !== 'published' ? `<button class="btn ok sm" data-ad="${a.id}" data-a="approve">Duyệt phát</button>` : ''}${can('ads.publish') && a.status === 'published' ? `<button class="btn sec sm" data-ad="${a.id}" data-a="archive">Dừng phát</button>` : ''}${can('ads.publish') ? `<button class="btn no sm icon" data-del="${a.id}">${icon('trash', 16)}</button>` : ''}</div></div></div>`).join('') || '<div class="empty">Chưa có nội dung</div>'}</div>`;
  $$('[data-ad]').forEach(b => b.onclick = async () => { try { await api(`/api/admin/ads/${b.dataset.ad}/${b.dataset.a}`, { method: 'POST' }); toast('Đã cập nhật', 'ok'); PAGES.ads(); } catch (e) { fail(e); } });
  $$('[data-del]').forEach(b => b.onclick = async () => { if (await confirmBox('Xoá nội dung', 'Xoá nội dung quảng cáo này?', { danger: true, okText: 'Xoá' }) === null) return; await api(`/api/admin/ads/${b.dataset.del}`, { method: 'DELETE' }); PAGES.ads(); });
  const edit = (a = { title: '', media_type: 'image', duration_sec: 10, priority: 0, target_devices: [], target_wards: [] }) => {
    const dt = (t) => t ? new Date(t * 1000 - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '';
    modal(`<div class="mh"><h3>${a.id ? 'Sửa nội dung' : 'Thêm nội dung quảng cáo'}</h3><button class="btn sec icon" data-close>${icon('close', 18)}</button></div><div class="mb">
      <div class="field"><label>Tiêu đề</label><input class="in" id="a_title" value="${esc(a.title)}"></div>
      <div class="row3"><div class="field"><label>Loại</label><select class="in" id="a_type">${opt('image', 'Ảnh', a.media_type)}${opt('video', 'Video', a.media_type)}${opt('html', 'HTML (mẫu Xanh24)', a.media_type)}${opt('url', 'Trang web (iframe)', a.media_type)}</select></div>
        <div class="field"><label>Thời lượng (giây)</label><input class="in" type="number" id="a_dur" value="${a.duration_sec}"></div><div class="field"><label>Ưu tiên</label><input class="in" type="number" id="a_pri" value="${a.priority}"></div></div>
      <div id="a_media"></div>
      <div class="row2"><div class="field"><label>Bắt đầu</label><input class="in" type="datetime-local" id="a_start" value="${dt(a.start_at)}"></div><div class="field"><label>Kết thúc</label><input class="in" type="datetime-local" id="a_end" value="${dt(a.end_at)}"></div></div>
      <div class="field"><label>Chỉ phát trên thiết bị (để trống = tất cả)</label><select class="in" id="a_dev" multiple style="height:96px">${devs.items.map(dv => `<option value="${esc(dv.code)}" ${a.target_devices?.includes(dv.code) ? 'selected' : ''}>${esc(dv.code)} — ${esc(dv.name)}</option>`).join('')}</select></div></div>
      <div class="mf"><button class="btn sec" data-close>Huỷ</button>${can('ads.publish') ? `<button class="btn sec" id="a_save">Lưu (chờ duyệt)</button><button class="btn pri" id="a_pub">Lưu & phát ngay</button>` : `<button class="btn pri" id="a_save">${icon('send', 16)} Gửi duyệt</button>`}</div>`);
    const media = () => { const tp = $('#a_type').value; $('#a_media').innerHTML = tp === 'html' ? `<div class="field"><label>Nội dung HTML</label><textarea class="in" id="a_html" rows="6" style="font-family:monospace;font-size:.8rem">${esc(a.html || "<div class='ad-hero ad-g1'><div class='ad-kicker'>Thông báo</div><h1>Tiêu đề lớn</h1><p>Nội dung ngắn gọn.</p></div>")}</textarea><span class="hint">Lớp có sẵn: ad-hero, ad-kicker, ad-g1/ad-g2/ad-g3 (nền thương hiệu)</span></div>` : `<div class="field"><label>${tp === 'url' ? 'Địa chỉ trang' : 'Tệp'}</label><div style="display:flex;gap:8px"><input class="in" id="a_url" value="${esc(a.media_url || '')}">${tp !== 'url' ? `<button class="btn sec" id="a_up">${icon('upload', 16)}</button>` : ''}</div><span class="hint">Khuyến nghị 1920×1080 (ngang) hoặc 1080×1920 (dọc)</span></div>`; $('#a_up') && ($('#a_up').onclick = async () => { const [f] = await pickFiles(tp === 'video' ? 'video/*' : 'image/*', false); if (!f) return; try { toast('Đang tải…'); $('#a_url').value = (await upload(f, tp)).url; } catch (e) { fail(e); } }); };
    $('#a_type').onchange = media; media();
    const save = async (publish) => {
      const ts = (v) => v ? Math.floor(new Date(v).getTime() / 1000) : null;
      const body = { title: $('#a_title').value, media_type: $('#a_type').value, duration_sec: +$('#a_dur').value || 10, priority: +$('#a_pri').value || 0, media_url: $('#a_url')?.value || '', html: $('#a_html')?.value || '', start_at: ts($('#a_start').value), end_at: ts($('#a_end').value), target_devices: [...$('#a_dev').selectedOptions].map(o => o.value), publish };
      try { await api('/api/admin/ads' + (a.id ? '/' + a.id : ''), { method: a.id ? 'PUT' : 'POST', body }); closeModal(); toast('Đã lưu', 'ok'); PAGES.ads(); } catch (e) { fail(e); }
    };
    $('#a_save').onclick = () => save(false); $('#a_pub') && ($('#a_pub').onclick = () => save(true));
  };
  $('#adNew') && ($('#adNew').onclick = () => edit());
  $$('[data-edit]').forEach(b => b.onclick = () => edit(d.items.find(x => x.id === +b.dataset.edit)));
};

// ---- Devices
PAGES.devices = async () => {
  setHead('Màn hình kiosk', 'Màn hình LCD Android tương tác đặt tại điểm công cộng', can('devices.manage') ? `<button class="btn pri sm" id="dvNew">${icon('plus', 16)} Thêm màn hình</button>` : '');
  const d = await api('/api/admin/devices');
  const base = location.origin;
  $('#page').innerHTML = `<div class="card">${d.items.length ? `<table class="tbl"><thead><tr><th>Trạng thái</th><th>Màn hình</th><th>Phường</th><th>Vị trí</th><th>Chờ (giây)</th><th>Lần cuối</th><th></th></tr></thead><tbody>
    ${d.items.map(v => `<tr><td><span class="devdot ${v.online ? 'on' : ''}"></span>${v.online ? 'Trực tuyến' : 'Ngoại tuyến'}</td><td><div class="name">${esc(v.name)}</div><div class="sub">${esc(v.code)} · ${esc(v.address || '')}</div></td>
      <td>${wardName(v.ward_slug)}</td><td class="sub">${v.lat ? `${(+v.lat).toFixed(5)}, ${(+v.lng).toFixed(5)}` : '—'}${v.gps_lat ? `<br><span title="Vị trí thiết bị tự báo về">📡 GPS ${(+v.gps_lat).toFixed(5)}, ${(+v.gps_lng).toFixed(5)} ±${Math.round(v.gps_acc || 0)} m · ${ago(v.gps_at)}</span>` : ''}<br>${({ auto: 'Tự động', fixed: 'Cố định', gps: 'Theo GPS' })[v.location_mode || 'auto']}</td><td>${v.idle_timeout || 'Mặc định'}</td><td class="sub">${ago(v.last_seen)}<br>${esc(v.screen || '')}</td>
      <td style="text-align:right;white-space:nowrap"><button class="btn sec sm" data-setup="${v.id}">${icon('qr', 16)} Cài đặt</button> ${can('devices.manage') ? `<button class="btn sec sm" data-dev="${v.id}">${icon('edit', 16)} Sửa</button>` : ''}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">Chưa có màn hình</div>'}</div>
    <div class="card" style="margin-top:16px"><div class="card-h"><h3>Hướng dẫn cài đặt trên màn hình Android</h3></div><div class="card-b note" style="border:0;border-radius:0 0 18px 18px">
      <b>Khuyến nghị:</b> cài ứng dụng <a href="/downloads/Xanh24-Kiosk.apk" download>Xanh24 Kiosk (APK Android)</a> → mở lần đầu nhập địa chỉ máy chủ và mã màn hình; ứng dụng tự chạy toàn màn hình, lưu bộ nhớ đệm và tự cập nhật dữ liệu. Menu ẩn: chạm nhanh 5 lần góc trên bên phải + PIN.<br>Hoặc dùng trình duyệt: 1. Cài trình duyệt kiosk (VD: Fully Kiosk Browser hoặc Chrome ở chế độ ghim ứng dụng). 2. Đặt trang khởi động là liên kết cài đặt của thiết bị (nút “Cài đặt”). 3. Bật tự khởi động cùng máy, tắt tắt-màn-hình, khoá điều hướng hệ thống. 4. Màn hình tự về chế độ chờ và phát quảng cáo sau ${esc(String((await api('/api/admin/settings')).idle_timeout || 40))} giây không có thao tác. Giữ logo 3 giây + nhập PIN để mở menu thiết bị.</div></div>`;
  $$('[data-setup]').forEach(b => b.onclick = () => { const v = d.items.find(x => x.id === +b.dataset.setup); const url = `${base}/?device=${encodeURIComponent(v.code)}`; modal(`<div class="mh"><h3>Cài đặt ${esc(v.code)}</h3><button class="btn sec icon" data-close>${icon('close', 18)}</button></div><div class="mb"><div class="qrwrap"><div class="q">${qrSVG(url, { size: 180 })}</div><div><p>Mở liên kết sau trên màn hình kiosk (hoặc quét QR bằng máy tính bảng):</p><p><code>${esc(url)}</code></p><a class="btn sec sm" href="${esc(url)}" target="_blank">${icon('eye', 16)} Xem thử</a></div></div></div>`); });
  const edit = async (v = { code: '', name: '', active: 1 }) => {
    modal(`<div class="mh"><h3>${v.id ? 'Sửa màn hình' : 'Thêm màn hình'}</h3><button class="btn sec icon" data-close>${icon('close', 18)}</button></div><div class="mb">
      <div class="row2"><div class="field"><label>Mã thiết bị</label><input class="in" id="d_code" value="${esc(v.code)}" ${v.id ? 'disabled' : ''} placeholder="HK-02"></div><div class="field"><label>Tên hiển thị</label><input class="in" id="d_name" value="${esc(v.name)}"></div></div>
      <div class="row2"><div class="field"><label>Phường</label><select class="in" id="d_ward">${wardOptions(v.ward_slug, '— Không gán —')}</select></div><div class="field"><label>Thời gian chờ về idle (giây)</label><input class="in" type="number" id="d_idle" value="${v.idle_timeout || ''}" placeholder="Mặc định hệ thống"></div></div>
      <div class="field"><label>Vị trí lắp đặt</label><input class="in" id="d_addr" value="${esc(v.address || '')}"></div>
      <div class="minimap" id="dmap" style="height:260px"></div><div class="row2" style="margin-top:10px"><input class="in" id="d_lat" value="${v.lat ?? ''}" placeholder="Vĩ độ"><input class="in" id="d_lng" value="${v.lng ?? ''}" placeholder="Kinh độ"></div>
      <div class="row2" style="margin-top:10px"><div class="field"><label>Nguồn vị trí “Bạn đang ở đây”</label><select class="in" id="d_mode">
        <option value="auto" ${(v.location_mode || 'auto') === 'auto' ? 'selected' : ''}>Tự động — GPS thiết bị khi chính xác (≤ 100 m) hoặc khi toạ độ trên lệch xa vị trí thật</option>
        <option value="fixed" ${v.location_mode === 'fixed' ? 'selected' : ''}>Cố định — luôn dùng toạ độ khai báo ở trên</option>
        <option value="gps" ${v.location_mode === 'gps' ? 'selected' : ''}>Theo GPS — luôn dùng vị trí thiết bị báo về</option></select></div>
        <div class="field"><label>Vị trí thiết bị báo về</label><div class="sub" style="padding-top:8px">${v.gps_lat ? `${(+v.gps_lat).toFixed(6)}, ${(+v.gps_lng).toFixed(6)} · sai số ±${Math.round(v.gps_acc || 0)} m · ${esc(v.gps_src || '')} · ${ago(v.gps_at)} <button type="button" class="btn sec sm" id="d_usegps" style="margin-left:6px">Dùng vị trí này</button>` : 'Chưa nhận được (cài ứng dụng Xanh24 Kiosk và cho phép Vị trí)'}</div></div></div>
      <label style="display:flex;gap:8px;align-items:center;margin-top:12px;font-weight:600"><input type="checkbox" id="d_act" ${v.active ? 'checked' : ''}> Đang hoạt động</label></div>
      <div class="mf">${v.id ? `<button class="btn no" id="d_del" style="margin-right:auto">Xoá</button>` : ''}<button class="btn sec" data-close>Huỷ</button><button class="btn pri" id="d_save">Lưu</button></div>`, { wide: true });
    await mapPicker($('#dmap'), v.lat, v.lng, (la, ln) => { $('#d_lat').value = la.toFixed(6); $('#d_lng').value = ln.toFixed(6); });
    $('#d_usegps') && ($('#d_usegps').onclick = () => { $('#d_lat').value = (+v.gps_lat).toFixed(6); $('#d_lng').value = (+v.gps_lng).toFixed(6); toast('Đã điền vị trí GPS — bấm Lưu để áp dụng', 'ok'); });
    $('#d_save').onclick = async () => { try { await api('/api/admin/devices' + (v.id ? '/' + v.id : ''), { method: v.id ? 'PUT' : 'POST', body: { code: $('#d_code').value.trim(), name: $('#d_name').value, ward_slug: $('#d_ward').value || null, idle_timeout: +$('#d_idle').value || null, address: $('#d_addr').value, lat: parseFloat($('#d_lat').value) || null, lng: parseFloat($('#d_lng').value) || null, location_mode: $('#d_mode').value, active: $('#d_act').checked ? 1 : 0 } }); closeModal(); toast('Đã lưu', 'ok'); PAGES.devices(); } catch (e) { fail(e); } };
    $('#d_del') && ($('#d_del').onclick = async () => { if (await confirmBox('Xoá màn hình', 'Xoá thiết bị này?', { danger: true, okText: 'Xoá' }) === null) return; await api('/api/admin/devices/' + v.id, { method: 'DELETE' }); PAGES.devices(); });
  };
  $('#dvNew') && ($('#dvNew').onclick = () => edit());
  $$('[data-dev]').forEach(b => b.onclick = () => edit(d.items.find(x => x.id === +b.dataset.dev)));
};

// ---- Wards
PAGES.wards = async (slug) => {
  setHead('Ranh giới phường / xã', 'Số hoá từ bản đồ phương án thành lập ĐVHC (VN-2000 → WGS84)', `<a class="btn sec sm" href="/api/admin/wards/export.geojson" id="wExp">${icon('download', 16)} Xuất GeoJSON</a>`);
  $('#wExp').onclick = async (e) => { e.preventDefault(); const r = await fetch('/api/admin/wards/export.geojson', { headers: { Authorization: 'Bearer ' + A.token } }); const b = await r.blob(); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'xanh24_ranh_gioi.geojson'; a.click(); };
  const d = await api('/api/admin/wards?geometry=1');
  $('#page').innerHTML = `<div class="split"><div class="card" style="overflow:hidden"><div class="card-h"><input class="in" id="wq" placeholder="Tìm phường…"></div><div id="wl" style="max-height:calc(100vh - 240px);overflow:auto"></div></div>
    <div class="grid"><div class="card"><div class="minimap" id="wmap" style="height:420px;border:0;border-radius:18px 18px 0 0"></div><div class="card-b" id="wdet"><p class="muted" style="margin:0">Chọn phường để xem chi tiết, đối chiếu bản đồ gốc và cập nhật ranh giới.</p></div></div></div></div>`;
  const draw = () => { const q = $('#wq').value.toLowerCase(); $('#wl').innerHTML = d.items.filter(w => w.name.toLowerCase().includes(q)).map(w => `<div class="revitem" data-s="${w.slug}"><span style="flex:1"><b>${esc(w.name)}</b><small>${w.area_km2 ?? '—'} km² · ${w.n} địa điểm · sai số khớp ${w.info?.fit_rms_m ?? '—'} m</small></span>${w.published ? '' : '<span class="tag amber">Ẩn</span>'}</div>`).join(''); $$('#wl .revitem').forEach(el => el.onclick = () => pick(el.dataset.s)); };
  $('#wq').oninput = draw; draw();
  const m = new maplibregl.Map({ container: 'wmap', style: tileStyle(), center: [105.83, 21.02], zoom: 10.5, attributionControl: { compact: true } }); mapsToClean.push(m);
  const fc = { type: 'FeatureCollection', features: d.items.filter(w => w.geometry).map(w => ({ type: 'Feature', id: w.slug, properties: { slug: w.slug, name: w.name }, geometry: w.geometry })) };
  m.on('load', () => {
    m.addSource('w', { type: 'geojson', data: fc, promoteId: 'slug' });
    m.addLayer({ id: 'wf', type: 'fill', source: 'w', paint: { 'fill-color': ['case', ['boolean', ['feature-state', 'sel'], false], '#22C98A', '#2A62B8'], 'fill-opacity': ['case', ['boolean', ['feature-state', 'sel'], false], 0.3, 0.08] } });
    m.addLayer({ id: 'wlines', type: 'line', source: 'w', paint: { 'line-color': '#14346F', 'line-width': 1.2 } });
    m.on('click', 'wf', (e) => pick(e.features[0].properties.slug));
    if (slug) pick(slug);
  });
  let sel = null;
  function pick(s) {
    const w = d.items.find(x => x.slug === s); if (!w) return;
    if (sel) m.setFeatureState({ source: 'w', id: sel }, { sel: false }); sel = s; m.setFeatureState({ source: 'w', id: s }, { sel: true });
    $$('#wl .revitem').forEach(el => el.classList.toggle('on', el.dataset.s === s));
    if (w.geometry) { const b = new maplibregl.LngLatBounds(); const add = (c) => typeof c[0] === 'number' ? b.extend(c) : c.forEach(add); add(w.geometry.coordinates); m.fitBounds(b, { padding: 40, duration: 600 }); }
    $('#wdet').innerHTML = `<div style="display:flex;gap:10px;align-items:center;margin-bottom:12px"><h3 style="margin:0;color:var(--navy);flex:1">${esc(w.name)}</h3>${can('wards.edit_info') ? `<label style="display:flex;gap:8px;align-items:center;font-weight:600">Hiển thị công khai <span class="switch ${w.published ? 'on' : ''}" id="wPub"></span></label>` : ''}</div>
      <div class="grid g3" style="margin-bottom:14px"><div class="note"><b>${w.area_km2 ?? '—'} km²</b><br><small>Diện tích tính từ polygon</small></div><div class="note"><b>${w.n}</b><br><small>Địa điểm công khai</small></div><div class="note"><b>${w.info?.fit_rms_m ?? '—'} m</b><br><small>Sai số khớp lưới toạ độ</small></div></div>
      <p class="muted" style="font-size:.8rem">Nguồn: ${esc(w.source || '')}<br>Cập nhật: ${fmtTime(w.updated_at)} · ${esc(w.updated_by || '')}</p>
      <div class="row2"><div><b style="font-size:.85rem">Bản đồ phương án gốc</b><div class="scan" style="margin-top:6px"><a href="${esc(w.scan_image || '')}" target="_blank"><img src="${esc(w.scan_image || '')}" alt="" loading="lazy"></a></div></div>
      <div>${can('wards.edit_geometry') ? `<b style="font-size:.85rem">Cập nhật ranh giới (S0)</b><p class="muted" style="font-size:.8rem">Tải lên tệp GeoJSON (Polygon/MultiPolygon, WGS84) từ dữ liệu chính thức của Sở TN&MT để thay thế ranh giới số hoá.</p>
        <button class="btn sec sm" id="wUp">${icon('upload', 16)} Tải GeoJSON</button><label style="display:flex;gap:8px;align-items:center;margin-top:10px;font-size:.82rem"><input type="checkbox" id="wRe" checked> Gán lại phường cho các địa điểm</label>` : '<div class="note">Chỉ Admin S0 được thay đổi ranh giới hành chính.</div>'}</div></div>`;
    $('#wPub') && ($('#wPub').onclick = async () => { try { await api('/api/admin/wards/' + s, { method: 'PUT', body: { published: w.published ? 0 : 1 } }); w.published = w.published ? 0 : 1; wardGeoCache = null; pick(s); draw(); } catch (e) { fail(e); } });
    $('#wUp') && ($('#wUp').onclick = async () => {
      const [f] = await pickFiles('.geojson,.json', false); if (!f) return;
      try { const g = JSON.parse(await f.text()); if (await confirmBox('Thay ranh giới', `Thay ranh giới <b>${esc(w.name)}</b> bằng dữ liệu từ ${esc(f.name)}?`, { okText: 'Cập nhật' }) === null) return; await api('/api/admin/wards/' + s, { method: 'PUT', body: { geometry: g, source: 'Tải lên: ' + f.name, reassign: $('#wRe').checked } }); toast('Đã cập nhật ranh giới', 'ok'); wardGeoCache = null; PAGES.wards(s); } catch (e) { fail(e); }
    });
  }
};

// ---- Transit
PAGES.transit = async () => {
  setHead('Xe buýt & Metro', 'Tuyến, nhà ga, trạm dừng dùng cho gợi ý lộ trình', can('transit.manage') ? `<button class="btn sec sm" id="stNew">${icon('plus', 16)} Trạm dừng</button><button class="btn pri sm" id="lnNew">${icon('plus', 16)} Tuyến</button>` : '');
  const d = await api('/api/admin/transit');
  $('#page').innerHTML = `<div class="grid g2"><div class="card"><div class="card-h"><h3>Tuyến</h3></div><table class="tbl"><tbody>${d.lines.map(l => `<tr><td><span class="tag" style="background:${esc(l.color)};color:#fff;border:0">${esc(l.code)}</span></td><td><div class="name">${esc(l.name)}</div><div class="sub">${esc(l.kind)} · ${(l.stops || []).length} trạm · ${esc(l.status)}</div></td><td style="text-align:right">${can('transit.manage') ? `<button class="btn sec sm" data-ln="${l.id}">${icon('edit', 16)}</button>` : ''}</td></tr>`).join('')}</tbody></table></div>
    <div class="card"><div class="card-h"><h3>Trạm dừng / Nhà ga (${d.stops.length})</h3></div><div style="max-height:600px;overflow:auto"><table class="tbl"><tbody>${d.stops.map(s => `<tr><td><div class="name">${esc(s.name)}</div><div class="sub">${esc((s.lines || []).join(', '))} · ${(+s.lat).toFixed(5)}, ${(+s.lng).toFixed(5)}</div></td><td>${s.verified ? '<span class="tag green">Đã xác minh</span>' : '<span class="tag amber">Cần xác minh</span>'}</td><td style="text-align:right">${can('transit.manage') ? `<button class="btn sec sm" data-st="${s.id}">${icon('edit', 16)}</button>` : ''}</td></tr>`).join('')}</tbody></table></div></div></div>`;
  const editStop = async (s = { kind: 'bus', name: '', lines: [], verified: 0 }) => {
    modal(`<div class="mh"><h3>${s.id ? 'Sửa trạm' : 'Thêm trạm'}</h3><button class="btn sec icon" data-close>${icon('close', 18)}</button></div><div class="mb">
      <div class="row3"><div class="field"><label>Loại</label><select class="in" id="s_kind">${opt('bus', 'Xe buýt', s.kind)}${opt('metro', 'Metro', s.kind)}${opt('brt', 'BRT', s.kind)}</select></div><div class="field" style="grid-column:span 2"><label>Tên</label><input class="in" id="s_name" value="${esc(s.name)}"></div></div>
      <div class="field"><label>Mã tuyến đi qua (cách nhau dấu phẩy)</label><input class="in" id="s_lines" value="${esc((s.lines || []).join(', '))}"></div>
      <div class="minimap" id="smap" style="height:260px"></div><div class="row2" style="margin-top:10px"><input class="in" id="s_lat" value="${s.lat ?? ''}"><input class="in" id="s_lng" value="${s.lng ?? ''}"></div>
      <label style="display:flex;gap:8px;align-items:center;margin-top:10px;font-weight:600"><input type="checkbox" id="s_ver" ${s.verified ? 'checked' : ''}> Đã xác minh thực địa</label></div>
      <div class="mf">${s.id ? '<button class="btn no" id="s_del" style="margin-right:auto">Xoá</button>' : ''}<button class="btn pri" id="s_save">Lưu</button></div>`, { wide: true });
    await mapPicker($('#smap'), s.lat, s.lng, (la, ln) => { $('#s_lat').value = la.toFixed(6); $('#s_lng').value = ln.toFixed(6); });
    $('#s_save').onclick = async () => { try { await api('/api/admin/transit/stops' + (s.id ? '/' + s.id : ''), { method: s.id ? 'PUT' : 'POST', body: { kind: $('#s_kind').value, name: $('#s_name').value, lines: $('#s_lines').value.split(',').map(x => x.trim()).filter(Boolean), lat: +$('#s_lat').value, lng: +$('#s_lng').value, verified: $('#s_ver').checked ? 1 : 0 } }); closeModal(); PAGES.transit(); } catch (e) { fail(e); } };
    $('#s_del') && ($('#s_del').onclick = async () => { await api('/api/admin/transit/stops/' + s.id, { method: 'DELETE' }); closeModal(); PAGES.transit(); });
  };
  const editLine = (l = { kind: 'bus', code: '', name: '', color: '#2A62B8', status: 'operating', stops: [] }) => {
    modal(`<div class="mh"><h3>${l.id ? 'Sửa tuyến' : 'Thêm tuyến'}</h3><button class="btn sec icon" data-close>${icon('close', 18)}</button></div><div class="mb">
      <div class="row3"><div class="field"><label>Loại</label><select class="in" id="l_kind">${opt('bus', 'Xe buýt', l.kind)}${opt('metro', 'Metro', l.kind)}${opt('brt', 'BRT', l.kind)}</select></div><div class="field"><label>Mã tuyến</label><input class="in" id="l_code" value="${esc(l.code)}"></div><div class="field"><label>Màu</label><input class="in" type="color" id="l_color" value="${esc(l.color)}"></div></div>
      <div class="field"><label>Tên tuyến</label><input class="in" id="l_name" value="${esc(l.name)}"></div>
      <div class="row2"><div class="field"><label>Đơn vị vận hành</label><input class="in" id="l_op" value="${esc(l.operator || '')}"></div><div class="field"><label>Trạng thái</label><select class="in" id="l_st">${opt('operating', 'Đang khai thác', l.status)}${opt('construction', 'Đang xây dựng', l.status)}${opt('suspended', 'Tạm dừng', l.status)}</select></div></div>
      <div class="field"><label>Các trạm theo thứ tự (giữ Ctrl để chọn nhiều; thứ tự theo danh sách)</label><select class="in" id="l_stops" multiple style="height:180px">${d.stops.map(s => `<option value="${s.id}" ${(l.stops || []).includes(s.id) ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Thông tin</label><textarea class="in" id="l_info">${esc(l.info || '')}</textarea></div></div>
      <div class="mf">${l.id ? '<button class="btn no" id="l_del" style="margin-right:auto">Xoá</button>' : ''}<button class="btn pri" id="l_save">Lưu</button></div>`);
    $('#l_save').onclick = async () => {
      const ids = [...$('#l_stops').selectedOptions].map(o => +o.value);
      const ordered = (l.stops || []).filter(i => ids.includes(i)).concat(ids.filter(i => !(l.stops || []).includes(i)));
      const geom = { type: 'LineString', coordinates: ordered.map(i => d.stops.find(s => s.id === i)).filter(Boolean).map(s => [s.lng, s.lat]) };
      try { await api('/api/admin/transit/lines' + (l.id ? '/' + l.id : ''), { method: l.id ? 'PUT' : 'POST', body: { kind: $('#l_kind').value, code: $('#l_code').value, name: $('#l_name').value, color: $('#l_color').value, operator: $('#l_op').value, status: $('#l_st').value, info: $('#l_info').value, stops: ordered, geometry: geom.coordinates.length > 1 ? geom : null } }); closeModal(); PAGES.transit(); } catch (e) { fail(e); }
    };
    $('#l_del') && ($('#l_del').onclick = async () => { await api('/api/admin/transit/lines/' + l.id, { method: 'DELETE' }); closeModal(); PAGES.transit(); });
  };
  $('#stNew') && ($('#stNew').onclick = () => editStop()); $('#lnNew') && ($('#lnNew').onclick = () => editLine());
  $$('[data-st]').forEach(b => b.onclick = () => editStop(d.stops.find(s => s.id === +b.dataset.st)));
  $$('[data-ln]').forEach(b => b.onclick = () => editLine(d.lines.find(s => s.id === +b.dataset.ln)));
};

// ---- Modules
PAGES.modules = async () => {
  setHead('Module mở rộng', 'Cổng mở cho các tính năng phát triển sau', can('modules.manage') ? `<button class="btn pri sm" id="mdNew">${icon('plus', 16)} Đăng ký module</button>` : '');
  const d = await api('/api/admin/modules');
  $('#page').innerHTML = `<div class="note info" style="margin-bottom:16px">Module kiểu <b>iframe</b> được mở trong kiosk và nhận ngữ cảnh (thiết bị, phường, ngôn ngữ, vị trí) qua <code>postMessage</code> — có thể yêu cầu mở địa điểm/chỉ đường. Module kiểu <b>link</b> hiển thị QR để mở trên điện thoại. Module phía máy chủ đặt tệp Python trong <code>server/modules/</code>. Xem <code>docs/MODULES.md</code>.</div>
    <div class="grid g3">${d.items.map(m => `<div class="card"><div class="card-b"><div style="display:flex;gap:12px;align-items:center"><span class="ki" style="width:46px;height:46px;border-radius:14px;display:grid;place-items:center;background:${esc(m.color)};color:#fff">${icon(m.icon || 'grid', 22)}</span><span style="flex:1"><b>${esc(m.name)}</b><div class="sub muted" style="font-size:.78rem">${esc(m.key)} · ${esc(m.kind)} · v${esc(m.version || '1.0')}</div></span>${can('modules.manage') ? `<span class="switch ${m.enabled ? 'on' : ''}" data-tg="${esc(m.key)}"></span>` : (m.enabled ? '<span class="tag green">Bật</span>' : '<span class="tag">Tắt</span>')}</div>
      <p class="muted" style="font-size:.85rem;min-height:40px">${esc(m.description || '')}</p><div class="sub" style="font-size:.78rem;word-break:break-all"><code>${esc(m.entry_url || '(chưa cấu hình)')}</code></div>
      ${can('modules.manage') ? `<div style="margin-top:10px"><button class="btn sec sm" data-md="${esc(m.key)}">${icon('edit', 16)} Cấu hình</button></div>` : ''}</div></div>`).join('')}</div>`;
  $$('[data-tg]').forEach(s => s.onclick = async () => { const m = d.items.find(x => x.key === s.dataset.tg); try { await api('/api/admin/modules/' + m.key, { method: 'PUT', body: { enabled: m.enabled ? 0 : 1 } }); PAGES.modules(); } catch (e) { fail(e); } });
  const edit = (m = { key: '', name: '', kind: 'iframe', entry_url: '', icon: 'grid', color: '#2A62B8', placement: 'kiosk_menu', enabled: 0, config: {}, sort: 10 }) => {
    modal(`<div class="mh"><h3>${m.name ? 'Cấu hình module' : 'Đăng ký module'}</h3><button class="btn sec icon" data-close>${icon('close', 18)}</button></div><div class="mb">
      <div class="row2"><div class="field"><label>Mã module</label><input class="in" id="m_key" value="${esc(m.key)}" ${m.name ? 'disabled' : ''}></div><div class="field"><label>Tên hiển thị</label><input class="in" id="m_name" value="${esc(m.name)}"></div></div>
      <div class="row3"><div class="field"><label>Kiểu</label><select class="in" id="m_kind">${opt('iframe', 'iframe (mở trong kiosk)', m.kind)}${opt('link', 'link (QR trên kiosk)', m.kind)}${opt('api', 'api (chỉ máy chủ)', m.kind)}</select></div><div class="field"><label>Biểu tượng</label><input class="in" id="m_icon" value="${esc(m.icon)}"></div><div class="field"><label>Màu</label><input class="in" type="color" id="m_color" value="${esc(m.color)}"></div></div>
      <div class="field"><label>Địa chỉ (entry URL)</label><input class="in" id="m_url" value="${esc(m.entry_url || '')}" placeholder="/modules/ten-module/index.html hoặc https://…"></div>
      <div class="row2"><div class="field"><label>Thứ tự</label><input class="in" type="number" id="m_sort" value="${m.sort || 0}"></div><div class="field"><label>Phiên bản</label><input class="in" id="m_ver" value="${esc(m.version || '1.0')}"></div></div>
      <div class="field"><label>Mô tả</label><textarea class="in" id="m_desc">${esc(m.description || '')}</textarea></div>
      <div class="field"><label>Cấu hình riêng (JSON)</label><textarea class="in" id="m_cfg" style="font-family:monospace;font-size:.8rem">${esc(JSON.stringify(m.config || {}, null, 2))}</textarea></div></div>
      <div class="mf">${m.name ? '<button class="btn no" id="m_del" style="margin-right:auto">Gỡ module</button>' : ''}<button class="btn pri" id="m_save">Lưu</button></div>`);
    $('#m_save').onclick = async () => { let cfg; try { cfg = JSON.parse($('#m_cfg').value || '{}'); } catch { return toast('JSON cấu hình không hợp lệ', 'err'); } const body = { key: $('#m_key').value, name: $('#m_name').value, kind: $('#m_kind').value, icon: $('#m_icon').value, color: $('#m_color').value, entry_url: $('#m_url').value, sort: +$('#m_sort').value, version: $('#m_ver').value, description: $('#m_desc').value, config: cfg };
      try { await api('/api/admin/modules' + (m.name ? '/' + m.key : ''), { method: m.name ? 'PUT' : 'POST', body }); closeModal(); PAGES.modules(); } catch (e) { fail(e); } };
    $('#m_del') && ($('#m_del').onclick = async () => { if (await confirmBox('Gỡ module', 'Gỡ đăng ký module này?', { danger: true }) === null) return; await api('/api/admin/modules/' + m.key, { method: 'DELETE' }); PAGES.modules(); });
  };
  $('#mdNew') && ($('#mdNew').onclick = () => edit());
  $$('[data-md]').forEach(b => b.onclick = () => edit(d.items.find(x => x.key === b.dataset.md)));
};

// ---- Users
PAGES.users = async () => {
  setHead('Người dùng & phân quyền', 'Admin S0 · Admin S1 · Co-worker', `<button class="btn pri sm" id="usNew">${icon('plus', 16)} Thêm người dùng</button>`);
  const d = await api('/api/admin/users');
  $('#page').innerHTML = `<div class="grid g3" style="margin-bottom:16px">
      <div class="card card-b"><span class="rolepill S0">S0</span><h3 style="margin:10px 0 4px;color:var(--navy)">Admin S0 — Toàn quyền</h3><p class="muted" style="margin:0;font-size:.85rem">Quản lý người dùng, cấu hình hệ thống, module, API, ranh giới hành chính, xoá vĩnh viễn.</p></div>
      <div class="card card-b"><span class="rolepill S1">S1</span><h3 style="margin:10px 0 4px;color:var(--navy)">Admin S1 — Phê duyệt</h3><p class="muted" style="margin:0;font-size:.85rem">Duyệt/từ chối, chỉnh sửa & publish trực tiếp, quản lý quảng cáo, màn hình, giao thông, xem nhật ký.</p></div>
      <div class="card card-b"><span class="rolepill CW">CW</span><h3 style="margin:10px 0 4px;color:var(--navy)">Co-worker — Nhập liệu</h3><p class="muted" style="margin:0;font-size:.85rem">Thêm/sửa địa điểm, nhập Excel, đề xuất quảng cáo; mọi thay đổi phải được phê duyệt. Có thể giới hạn theo phường.</p></div></div>
    <div class="card"><table class="tbl"><thead><tr><th>Người dùng</th><th>Vai trò</th><th>Phạm vi phường</th><th>Đăng nhập gần nhất</th><th>Trạng thái</th><th></th></tr></thead><tbody>
    ${d.items.map(u => `<tr><td><div class="name">${esc(u.full_name || u.username)}</div><div class="sub">${esc(u.username)} · ${esc(u.email || '')}</div></td><td><span class="rolepill ${u.role}">${u.role}</span></td><td class="sub">${u.wards?.length ? u.wards.map(s => esc(A.wardMap[s]?.short || s)).join(', ') : 'Tất cả'}</td><td class="sub">${fmtTime(u.last_login)}</td><td>${u.active ? '<span class="tag green">Hoạt động</span>' : '<span class="tag red">Đã khoá</span>'}</td><td style="text-align:right"><button class="btn sec sm" data-u="${u.id}">${icon('edit', 16)} Sửa</button></td></tr>`).join('')}</tbody></table></div>`;
  const edit = (u = { username: '', role: 'CW', wards: [], active: 1 }) => {
    modal(`<div class="mh"><h3>${u.id ? 'Sửa người dùng' : 'Thêm người dùng'}</h3><button class="btn sec icon" data-close>${icon('close', 18)}</button></div><div class="mb">
      <div class="row2"><div class="field"><label>Tên đăng nhập</label><input class="in" id="u_un" value="${esc(u.username)}" ${u.id ? 'disabled' : ''}></div><div class="field"><label>Họ tên</label><input class="in" id="u_fn" value="${esc(u.full_name || '')}"></div></div>
      <div class="row2"><div class="field"><label>Email</label><input class="in" id="u_em" value="${esc(u.email || '')}"></div><div class="field"><label>Điện thoại</label><input class="in" id="u_ph" value="${esc(u.phone || '')}"></div></div>
      <div class="row2"><div class="field"><label>Vai trò</label><select class="in" id="u_role">${Object.entries(d.roles).map(([k, l]) => opt(k, l, u.role)).join('')}</select></div><div class="field"><label>${u.id ? 'Đặt lại mật khẩu' : 'Mật khẩu'}</label><input class="in" id="u_pw" type="text" placeholder="${u.id ? 'Để trống nếu không đổi' : 'Tối thiểu 8 ký tự, Hoa/thường/số'}"></div></div>
      <div class="field"><label>Giới hạn phường (Ctrl để chọn nhiều, để trống = tất cả)</label><select class="in" id="u_w" multiple style="height:140px">${A.wards.map(w => `<option value="${w.slug}" ${u.wards?.includes(w.slug) ? 'selected' : ''}>${esc(w.name)}</option>`).join('')}</select></div>
      <label style="display:flex;gap:8px;align-items:center;font-weight:600"><input type="checkbox" id="u_act" ${u.active ? 'checked' : ''}> Cho phép đăng nhập</label></div>
      <div class="mf"><button class="btn sec" data-close>Huỷ</button><button class="btn pri" id="u_save">Lưu</button></div>`);
    $('#u_save').onclick = async () => { const body = { username: $('#u_un').value, full_name: $('#u_fn').value, email: $('#u_em').value, phone: $('#u_ph').value, role: $('#u_role').value, wards: [...$('#u_w').selectedOptions].map(o => o.value), active: $('#u_act').checked ? 1 : 0 }; if ($('#u_pw').value) body.password = $('#u_pw').value;
      try { await api('/api/admin/users' + (u.id ? '/' + u.id : ''), { method: u.id ? 'PUT' : 'POST', body }); closeModal(); toast('Đã lưu', 'ok'); PAGES.users(); } catch (e) { fail(e); } };
  };
  $('#usNew').onclick = () => edit(); $$('[data-u]').forEach(b => b.onclick = () => edit(d.items.find(x => x.id === +b.dataset.u)));
};

// ---- Settings
PAGES.settings = async () => {
  setHead('Cấu hình hệ thống', 'Chỉ Admin S0', `<button class="btn pri sm" id="sSave">${icon('check', 16)} Lưu cấu hình</button>`);
  const s = await api('/api/admin/settings');
  const J = (v) => esc(JSON.stringify(v, null, 2));
  $('#page').innerHTML = `<div class="grid g2">
    <div class="card"><div class="card-h"><h3>Thông tin chung</h3></div><div class="card-b">
      <div class="field"><label>Tên phần mềm</label><input class="in" id="s_app_name" value="${esc(s.app_name)}"></div>
      <div class="field"><label>Dòng bản quyền (chân trang)</label><input class="in" id="s_copyright" value="${esc(s.copyright)}"></div>
      <div class="row2"><div class="field"><label>Tên khu vực mặc định</label><input class="in" id="s_region_name" value="${esc(s.region_name)}"></div><div class="field"><label>Địa chỉ công khai (cho mã QR)</label><input class="in" id="s_public_base_url" value="${esc(s.public_base_url || '')}" placeholder="https://maps.xanh24.vn"></div></div>
      <div class="row3"><div class="field"><label>Idle sau (giây)</label><input class="in" type="number" id="s_idle_timeout" value="${s.idle_timeout}"></div><div class="field"><label>Cảnh báo trước (giây)</label><input class="in" type="number" id="s_idle_warning" value="${s.idle_warning}"></div><div class="field"><label>Zoom mặc định</label><input class="in" type="number" step="0.1" id="s_default_zoom" value="${s.default_zoom}"></div></div>
      <div class="field"><label>Tâm bản đồ mặc định [kinh độ, vĩ độ]</label><input class="in" id="s_default_center" value="${esc(JSON.stringify(s.default_center))}"></div></div></div>
    <div class="card"><div class="card-h"><h3>Kiosk</h3></div><div class="card-b">
      <div class="row2"><div class="field"><label>PIN mở menu thiết bị</label><input class="in" id="k_pin" value="${esc(s.kiosk?.admin_exit_pin || '')}"></div><div class="field"><label>Màn hình khởi động</label><select class="in" id="k_start">${opt('idle', 'Chế độ chờ (quảng cáo)', s.kiosk?.start_screen)}${opt('map', 'Bản đồ', s.kiosk?.start_screen)}</select></div></div>
      <label style="display:flex;gap:8px;align-items:center;font-weight:600"><input type="checkbox" id="k_osk" ${s.kiosk?.on_screen_keyboard !== false ? 'checked' : ''}> Bàn phím ảo tiếng Việt</label>
      <div class="field" style="margin-top:14px"><label>Bản đồ nền (JSON)</label><textarea class="in" id="s_tiles" rows="10" style="font-family:monospace;font-size:.78rem">${J(s.tiles)}</textarea><span class="hint">Có thể thêm nguồn tile riêng (Vietmap, MapTiler, máy chủ nội bộ…). "active" là nguồn mặc định.</span></div></div></div>
    <div class="card"><div class="card-h"><h3>Định tuyến (chỉ đường)</h3></div><div class="card-b"><textarea class="in" id="s_routing" rows="9" style="font-family:monospace;font-size:.78rem">${J(s.routing)}</textarea><p class="hint muted" style="font-size:.78rem">Tương thích OSRM (/route/v1). Khuyến nghị tự triển khai OSRM với dữ liệu OSM Việt Nam cho vận hành chính thức.</p></div></div>
    <div class="card"><div class="card-h"><h3>Gọi xe & giao thông công cộng</h3></div><div class="card-b"><div class="field"><label>Cấu hình Grab / Xanh SM (JSON)</label><textarea class="in" id="s_ride" rows="10" style="font-family:monospace;font-size:.78rem">${J(s.ride)}</textarea><span class="hint">app_url hỗ trợ {lat} {lng} {name} {addr}. Cập nhật deep link chính thức khi có hợp tác với đối tác.</span></div>
      <div class="field"><label>Tra cứu xe buýt (JSON)</label><textarea class="in" id="s_transit" rows="4" style="font-family:monospace;font-size:.78rem">${J(s.transit)}</textarea></div></div></div></div>`;
  $('#sSave').onclick = async () => {
    try {
      const P = (id) => JSON.parse($(id).value);
      const body = { app_name: $('#s_app_name').value, copyright: $('#s_copyright').value, region_name: $('#s_region_name').value, public_base_url: $('#s_public_base_url').value.trim(), idle_timeout: +$('#s_idle_timeout').value, idle_warning: +$('#s_idle_warning').value, default_zoom: +$('#s_default_zoom').value, default_center: P('#s_default_center'),
        kiosk: { ...(s.kiosk || {}), admin_exit_pin: $('#k_pin').value, start_screen: $('#k_start').value, on_screen_keyboard: $('#k_osk').checked }, tiles: P('#s_tiles'), routing: P('#s_routing'), ride: P('#s_ride'), transit: P('#s_transit') };
      await api('/api/admin/settings', { method: 'PUT', body }); toast('Đã lưu — các màn hình kiosk sẽ tự cập nhật khi về chế độ chờ', 'ok');
    } catch (e) { fail(e.name === 'SyntaxError' ? new Error('JSON không hợp lệ: ' + e.message) : e); }
  };
};

// ---- Integrations
PAGES.integrations = async () => {
  setHead('API & Webhook', 'Kết nối hệ thống bên ngoài');
  const d = await api('/api/admin/webhooks');
  $('#page').innerHTML = `<div class="grid g2">
    <div class="card"><div class="card-h"><h3>API key (chỉ đọc)</h3><span class="sp"></span><button class="btn pri sm" id="kNew">${icon('plus', 16)} Tạo key</button></div><div class="card-b"><p class="muted" style="margin-top:0;font-size:.85rem">Gửi header <code>X-API-Key</code> để đọc <code>/api/admin/*</code> (GET). API công khai <code>/api/public/*</code> không cần key.</p>
      ${d.api_keys.map(k => `<div class="revitem" style="cursor:default"><span style="flex:1"><b>${esc(k.name)}</b><small><code>${esc(k.prefix)}…</code> · tạo ${fmtTime(k.created_at)} · dùng ${fmtTime(k.last_used)}</small></span>${k.active ? `<button class="btn no sm" data-k="${k.id}">Thu hồi</button>` : '<span class="tag red">Đã thu hồi</span>'}</div>`).join('') || '<div class="empty">Chưa có</div>'}</div></div>
    <div class="card"><div class="card-h"><h3>Webhook</h3><span class="sp"></span><button class="btn pri sm" id="wNew">${icon('plus', 16)} Thêm webhook</button></div><div class="card-b"><p class="muted" style="margin-top:0;font-size:.85rem">Sự kiện: poi.created, poi.updated, poi.archived, poi.status, revision.pending, revision.approved, ward.updated, module.* — ký HMAC-SHA256 trong header <code>X-Xanh24-Signature</code>.</p>
      ${d.webhooks.map(w => `<div class="revitem" style="cursor:default"><span style="flex:1;min-width:0"><b style="word-break:break-all">${esc(w.url)}</b><small>${esc((w.events || []).join(', '))} · ${esc(w.last_status || 'chưa gửi')}</small></span><button class="btn no sm" data-w="${w.id}">Xoá</button></div>`).join('') || '<div class="empty">Chưa có</div>'}</div></div></div>`;
  $('#kNew').onclick = async () => { const n = await confirmBox('Tạo API key', 'Tên gợi nhớ cho key:', { input: 'VD: Cổng thông tin phường', okText: 'Tạo' }); if (n === null) return; const r = await api('/api/admin/apikeys', { method: 'POST', body: { name: n || 'API key' } }); modal(`<div class="mh"><h3>API key mới</h3></div><div class="mb"><div class="note warn">Sao chép ngay — key chỉ hiển thị một lần.</div><p><code style="font-size:.95rem">${esc(r.key)}</code></p></div><div class="mf"><button class="btn pri" data-close>Đã sao chép</button></div>`, { onClose: () => PAGES.integrations() }); };
  $('#wNew').onclick = async () => { const u = await confirmBox('Thêm webhook', 'Địa chỉ nhận (https://…):', { input: 'https://', okText: 'Thêm' }); if (!u) return; try { const r = await api('/api/admin/webhooks', { method: 'POST', body: { url: u } }); modal(`<div class="mh"><h3>Webhook đã tạo</h3></div><div class="mb"><p>Secret ký HMAC (chỉ hiển thị một lần):</p><p><code>${esc(r.secret)}</code></p></div><div class="mf"><button class="btn pri" data-close>Đóng</button></div>`, { onClose: () => PAGES.integrations() }); } catch (e) { fail(e); } };
  $$('[data-k]').forEach(b => b.onclick = async () => { await api('/api/admin/apikeys/' + b.dataset.k, { method: 'DELETE' }); PAGES.integrations(); });
  $$('[data-w]').forEach(b => b.onclick = async () => { await api('/api/admin/webhooks/' + b.dataset.w, { method: 'DELETE' }); PAGES.integrations(); });
};

// ---- Audit
PAGES.audit = async () => {
  setHead('Nhật ký hoạt động', '300 thao tác gần nhất');
  $('#page').innerHTML = `<div class="toolbar"><input class="in search" id="aq" placeholder="Lọc theo người dùng, thao tác…"></div><div class="card" id="al"></div>`;
  const load = async () => { const d = await api('/api/admin/audit?q=' + encodeURIComponent($('#aq').value)); $('#al').innerHTML = `<table class="tbl"><thead><tr><th>Thời gian</th><th>Người dùng</th><th>Thao tác</th><th>Đối tượng</th><th>Chi tiết</th><th>IP</th></tr></thead><tbody>${d.items.map(a => `<tr><td class="sub">${fmtTime(a.at)}</td><td>${esc(a.username)}</td><td><code>${esc(a.action)}</code></td><td class="sub">${esc(a.entity)} ${esc(a.entity_id)}</td><td class="sub" style="max-width:360px;word-break:break-word">${esc(JSON.stringify(a.detail) === '{}' ? '' : JSON.stringify(a.detail))}</td><td class="sub">${esc(a.ip || '')}</td></tr>`).join('')}</tbody></table>`; };
  let t; $('#aq').oninput = () => { clearTimeout(t); t = setTimeout(load, 250); }; load();
};

// ---------------------------------------------------------------- go
(async () => { try { A.meta = await (await fetch('/api/health')).json(); } catch { } if (A.token) start(); else renderLogin(); })();
