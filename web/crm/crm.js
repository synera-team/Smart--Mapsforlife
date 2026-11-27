// =====================================================================
// Xanh24 CRM — trung tâm quản lý khách hàng & vận hành www.xanh24.com
// Dùng chung tài khoản quản trị (S0 / S1 / Co-worker) và dữ liệu của Maps for Life.
// =====================================================================
import { icon } from '/crm/icons.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { } }, del(k) { try { localStorage.removeItem(k); } catch { } } };
const NF = new Intl.NumberFormat('vi-VN');
const fmtN = (n) => NF.format(Math.round(n || 0));
const fmtM = (n) => NF.format(Math.round(n || 0)) + ' ₫';
const fmtShort = (n) => { n = +n || 0; if (Math.abs(n) >= 1e9) return (n / 1e9).toLocaleString('vi-VN', { maximumFractionDigits: 1 }) + ' tỷ'; if (Math.abs(n) >= 1e6) return (n / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 1 }) + ' tr'; if (Math.abs(n) >= 1e3) return (n / 1e3).toLocaleString('vi-VN', { maximumFractionDigits: 1 }) + 'k'; return String(Math.round(n)); };
const fmtDate = (t) => t ? new Date(t * 1000).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—';
const fmtTime = (t) => t ? new Date(t * 1000).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '—';
const ago = (t) => { if (!t) return 'chưa kết nối'; const s = Date.now() / 1000 - t; if (s < 90) return 'vừa xong'; if (s < 3600) return Math.round(s / 60) + ' phút trước'; if (s < 86400) return Math.round(s / 3600) + ' giờ trước'; return Math.round(s / 86400) + ' ngày trước'; };
const toTs = (v) => v ? Math.floor(new Date(v + 'T00:00:00+07:00').getTime() / 1000) : null;
const toInput = (t) => t ? new Date((t + 7 * 3600) * 1000).toISOString().slice(0, 10) : '';
const initials = (s) => String(s || '?').trim().split(/\s+/).slice(-2).map(w => w[0]).join('').toUpperCase();
const BRIDGE = window.X24CRM || null; // ứng dụng Android "Xanh24 CRM"

const C = { token: store.get('x24_crm_token'), user: null, meta: null, route: '', timer: null, wall: new URLSearchParams(location.search).get('wall') === '1' };
const can = (p) => C.user?.permissions?.includes(p);

// ---------------------------------------------------------------- theme
function applyTheme(t) { document.documentElement.dataset.theme = t; store.set('x24_crm_theme', t); }
applyTheme(store.get('x24_crm_theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

// ---------------------------------------------------------------- API
async function api(path, opt = {}) {
  const headers = { ...(opt.headers || {}) };
  if (C.token) headers.Authorization = 'Bearer ' + C.token;
  let body = opt.body;
  if (body && typeof body !== 'string') { body = JSON.stringify(body); headers['Content-Type'] = 'application/json'; }
  const r = await fetch(path, { ...opt, headers, body });
  if (r.status === 401 && !path.includes('/auth/login')) { logout('Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.'); throw new Error('Phiên đăng nhập hết hạn'); }
  if (opt.raw) { if (!r.ok) throw new Error('Không tải được tệp'); return r; }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || r.statusText);
  return d;
}
const M = '/api/modules/crm';
function toast(msg, kind = '') { const el = document.createElement('div'); el.className = 'toastm ' + kind; el.textContent = msg; $('#toasts').appendChild(el); setTimeout(() => el.remove(), 3800); }
const fail = (e) => toast(e.message || String(e), 'err');

// Gia hạn phiên định kỳ — màn hình CRM treo tường không bị đăng xuất khi đang mở
setInterval(async () => { if (!C.token) return; try { const d = await api(M + '/refresh', { method: 'POST' }); C.token = d.token; store.set('x24_crm_token', d.token); } catch { } }, 30 * 60 * 1000);

// ---------------------------------------------------------------- modal / tooltip
function modal(html, { wide = false } = {}) { const c = $('#modalCard'); c.className = 'modal-card' + (wide ? ' wide' : ''); c.innerHTML = html; $('#modal').hidden = false; return c; }
function closeModal() { $('#modal').hidden = true; $('#modalCard').innerHTML = ''; }
$('#modal').addEventListener('click', (e) => { if (e.target.closest('[data-close]')) closeModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('#modal').hidden) closeModal(); });
function confirmBox(title, text, { okText = 'Xác nhận', danger = false, input = null } = {}) {
  return new Promise((res) => {
    modal(`<div class="mh"><h3>${esc(title)}</h3></div><div class="mb"><p style="margin:0 0 12px">${text}</p>${input ? `<textarea class="in" id="cfIn" placeholder="${esc(input)}"></textarea>` : ''}</div>
      <div class="mf"><button class="btn sec" id="cfNo">Huỷ</button><button class="btn ${danger ? 'no' : 'pri'}" id="cfOk">${esc(okText)}</button></div>`);
    $('#cfNo').onclick = () => { closeModal(); res(null); };
    $('#cfOk').onclick = () => { const v = input ? $('#cfIn').value.trim() : true; closeModal(); res(v); };
  });
}
const tip = $('#tip');
function showTip(e, html) { tip.innerHTML = html; tip.hidden = false; const w = tip.offsetWidth, h = tip.offsetHeight; let x = e.clientX + 14, y = e.clientY - h - 10; if (x + w > innerWidth - 8) x = e.clientX - w - 14; if (y < 8) y = e.clientY + 16; tip.style.left = x + 'px'; tip.style.top = y + 'px'; }
document.addEventListener('pointermove', (e) => { const t = e.target.closest?.('[data-tip]'); if (t) showTip(e, t.dataset.tip); else tip.hidden = true; });

// ---------------------------------------------------------------- charts (SVG, một chuỗi số liệu / biểu đồ, có tooltip)
const CHARTS = new Map(); let chartSeq = 0;
// Biểu đồ vẽ theo đúng bề rộng khung chứa (chữ trục luôn cùng cỡ), vẽ lại khi đổi kích thước
function barChart(data, cfg = {}) { const id = 'ch' + (++chartSeq); CHARTS.set(id, { data, cfg }); return `<div class="chart" data-ch="${id}" style="height:${cfg.h || 200}px"></div>`; }
const chartRO = new ResizeObserver((ents) => ents.forEach(e => drawChart(e.target)));
function fitCharts(root = document) { $$('.chart[data-ch]', root).forEach(el => { if (!el.dataset.obs) { el.dataset.obs = 1; chartRO.observe(el); } drawChart(el); }); }
new MutationObserver(() => fitCharts()).observe(document.body, { childList: true, subtree: true });
function drawChart(el) {
  const c = CHARTS.get(el.dataset.ch); if (!c || !el.isConnected) return;
  const W = Math.max(240, Math.round(el.clientWidth)); if (+el.dataset.w === W) return; el.dataset.w = W;
  el.innerHTML = barSVG(c.data, { ...c.cfg, W });
}
function barSVG(data, { key, label, color = 'var(--s1)', h = 200, fmt = fmtN, xlab = (d) => d.day.slice(8) + '/' + d.day.slice(5, 7), W = 640 } = {}) {
  const H = h, pl = 40, pb = 22, pt = 8;
  const max = Math.max(1, ...data.map(d => d[key] || 0));
  const nice = niceMax(max), n = data.length, bw = (W - pl) / n, gap = Math.min(4, bw * .25);
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((W - pl) / 64))));
  let s = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">`;
  for (let i = 0; i <= 4; i++) { const y = pt + (H - pt - pb) * (1 - i / 4); s += `<line class="gl" x1="${pl}" x2="${W}" y1="${y}" y2="${y}"/><text class="ax" x="${pl - 6}" y="${y + 4}" text-anchor="end">${fmtShort(nice * i / 4)}</text>`; }
  data.forEach((d, i) => {
    const v = d[key] || 0, bh = (H - pt - pb) * v / nice, x = pl + i * bw + gap / 2, y = H - pb - bh, w = Math.max(1, bw - gap), r = Math.min(4, bh, w / 2);
    s += `<rect class="hit" x="${pl + i * bw}" y="${pt}" width="${bw}" height="${H - pt - pb}" data-tip="${esc(`<b>${xlab(d)}</b>${label}: ${fmt(v)}`)}"/>`;
    if (v > 0) s += `<path class="bar" fill="${color}" pointer-events="none" d="M${x},${H - pb} V${y + r} q0,-${r} ${r},-${r} H${x + w - r} q${r},0 ${r},${r} V${H - pb} Z"/>`;
    if ((n - 1 - i) % every === 0) s += i === n - 1 ? `<text class="ax" x="${W}" y="${H - 6}" text-anchor="end">${xlab(d)}</text>` : `<text class="ax" x="${pl + i * bw + bw / 2}" y="${H - 6}" text-anchor="middle">${xlab(d)}</text>`;
  });
  return s + `<line class="base" x1="${pl}" x2="${W}" y1="${H - pb}" y2="${H - pb}"/></svg>`;
}
function niceMax(v) { const p = Math.pow(10, Math.floor(Math.log10(v))); const m = v / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p; }
function hbars(items, { label = (x) => x.label, value = (x) => x.n, fmt = fmtN, color = 'var(--s1)', empty = 'Chưa có dữ liệu' } = {}) {
  if (!items.length) return `<div class="empty">${empty}</div>`;
  const max = Math.max(1, ...items.map(value));
  return items.map(x => `<div class="hbar" data-tip="${esc(`<b>${esc(label(x))}</b>${fmt(value(x))}`)}"><span class="lb">${esc(label(x))}</span><span class="tr"><span class="fl" style="width:${Math.max(2, value(x) / max * 100)}%;background:${color}"></span></span><b class="num">${fmt(value(x))}</b></div>`).join('');
}

// ---------------------------------------------------------------- tags
const STAGE_TONE = { lead: '', contacted: 'info', quoted: 'info', negotiating: 'warn', won: 'good', lost: 'bad' };
const stageTag = (s) => `<span class="pill ${STAGE_TONE[s] || ''}">${esc(C.meta?.stages?.[s] || s)}</span>`;
const CT_TONE = { draft: '', active: 'good', ended: 'info', cancelled: 'bad' };
function contractTag(c) {
  if (c.expired) return `<span class="pill bad">${icon('clock', 13)} Quá hạn</span>`;
  if (c.expiring) return `<span class="pill warn">${icon('clock', 13)} Sắp hết hạn</span>`;
  return `<span class="pill ${CT_TONE[c.status] || ''}">${esc(C.meta?.contract_status?.[c.status] || c.status)}</span>`;
}
const onlineTag = (d) => d.online ? `<span class="pill good"><span class="dot"></span> Trực tuyến</span>` : `<span class="pill bad"><span class="dot off"></span> Mất kết nối</span>`;
const KIND_ICON = { advertiser: 'ad', partner: 'bag', site_owner: 'device', other: 'user' };
const ACT_ICON = { note: 'edit', call: 'phone', meeting: 'user', email: 'send', visit: 'pin', task: 'check', maintenance: 'settings' };
const opts = (obj, sel) => Object.entries(obj).map(([k, v]) => `<option value="${k}" ${k === sel ? 'selected' : ''}>${esc(v)}</option>`).join('');

// ---------------------------------------------------------------- đăng nhập
function logout(msg = '') { C.token = null; C.user = null; store.del('x24_crm_token'); clearInterval(C.timer); renderLogin(msg); }
function renderLogin(msg = '') {
  $('#root').innerHTML = `<div class="login">
    <div class="login-art"><img class="logo" src="/crm/logo.webp" alt="Xanh24 - Maps for Life">
      <div><h1>Xanh24 CRM — trung tâm quản lý www.xanh24.com</h1><p>Khách hàng, hợp đồng quảng cáo, màn hình kiosk và nội dung bản đồ — trên một màn hình.</p>
      <ul><li>${icon('user', 20)} Nhà quảng cáo · đối tác địa điểm · chủ điểm đặt kiosk · khách tiềm năng</li><li>${icon('device', 20)} Giám sát màn hình LCD theo thời gian thực</li><li>${icon('chart', 20)} Báo cáo lượt hiển thị quảng cáo, doanh thu, công nợ</li></ul></div>
      <small style="opacity:.85">Bản quyền thuộc về Công ty TNHH Công nghệ và Truyền thông Xanh24</small></div>
    <div class="login-form"><form class="login-card" id="loginForm"><h2>Đăng nhập CRM</h2><p class="sub">Dùng tài khoản quản trị của xanh24.com (S0 / S1 / Co-worker)</p>
      ${msg ? `<div class="note warn" style="margin-bottom:14px">${esc(msg)}</div>` : ''}
      <div class="field"><label for="u">Tên đăng nhập</label><input class="in" id="u" autocomplete="username" required></div>
      <div class="field"><label for="p">Mật khẩu</label><input class="in" id="p" type="password" autocomplete="current-password" required></div>
      <button class="btn pri" style="width:100%;height:46px" id="lgBtn">Đăng nhập</button>
      ${BRIDGE ? `<button type="button" class="btn ghost" style="width:100%;margin-top:10px" id="lgSet">${icon('settings', 16)} Đổi địa chỉ máy chủ</button>` : ''}
      <p class="sub" style="margin-top:22px;font-size:.8rem">Máy chủ: ${esc(location.host)}</p></form></div></div>`;
  $('#loginForm').onsubmit = async (e) => {
    e.preventDefault(); const b = $('#lgBtn'); b.disabled = true;
    try {
      const d = await api('/api/auth/login', { method: 'POST', body: { username: $('#u').value, password: $('#p').value } });
      C.token = d.token; store.set('x24_crm_token', d.token); C.user = d.user; await boot();
    } catch (er) { renderLogin(er.message); }
  };
  $('#lgSet')?.addEventListener('click', () => BRIDGE.openSettings());
}

// ---------------------------------------------------------------- khung ứng dụng
const NAV = [
  ['', 'chart', 'Tổng quan'], ['kiosk', 'device', 'Màn hình kiosk'], ['khach-hang', 'user', 'Khách hàng'], ['phieu', 'list', 'Phễu bán hàng'],
  ['hop-dong', 'doc', 'Hợp đồng'], ['viec', 'check', 'Việc cần làm'], ['bao-cao', 'ad', 'Báo cáo quảng cáo'], ['duyet', 'inbox', 'Duyệt nội dung'],
];
function renderShell() {
  const u = C.user;
  document.body.classList.toggle('wall', C.wall);
  $('#root').innerHTML = `<div class="shell"><aside class="side" id="side"><a class="side-logo" href="#/"><img src="/crm/logo.webp" alt="Xanh24"><b>CRM<br>xanh24.com</b></a>
    <nav class="nav">${NAV.map(([r, ic, t]) => `<a href="#/${r}" data-r="${r}">${icon(ic, 20)}<span>${t}</span>${r === 'duyet' ? '<span class="cnt" id="navApprove" hidden></span>' : r === 'viec' ? '<span class="cnt" id="navTasks" hidden></span>' : ''}</a>`).join('')}
      <div class="sep"></div><a href="/admin/" target="_blank" rel="noopener">${icon('settings', 20)}<span>Dashboard đầy đủ</span></a><a href="/" target="_blank" rel="noopener">${icon('map', 20)}<span>Mở bản đồ xanh24.com</span></a></nav>
    <div class="side-foot"><div class="who"><span class="avatar">${esc(initials(u.full_name || u.username))}</span><span style="min-width:0"><b style="display:block;color:#fff">${esc(u.full_name || u.username)}</b>${esc(u.role_label || u.role)}</span></div>
      <button id="btnTheme">${icon('sun', 16)} Giao diện sáng / tối</button><button id="btnWall">${icon('expand', 16)} Chế độ trình chiếu</button>${BRIDGE ? `<button id="btnApp">${icon('settings', 16)} Cài đặt ứng dụng</button>` : ''}<button id="btnOut">${icon('logout', 16)} Đăng xuất</button></div></aside>
    <main class="main"><header class="top"><button class="iconbtn burger" id="burger" aria-label="Menu">${icon('list', 20)}</button><h1 id="title">Tổng quan</h1>
      <span class="live"><span class="dot" id="liveDot"></span><span id="liveTxt">Đang kết nối…</span></span><span class="actions" id="topAct"></span>
      ${C.wall ? `<button class="btn sec sm" id="wallOff">${icon('close', 14)} Thoát trình chiếu</button>` : ''}</header><div class="page" id="page"></div></main></div>`;
  $('#btnOut').onclick = () => logout();
  $('#btnTheme').onclick = () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  $('#btnWall').onclick = () => { C.wall = true; renderShell(); go(); BRIDGE?.keepScreenOn?.(true); document.documentElement.requestFullscreen?.().catch(() => { }); };
  $('#wallOff')?.addEventListener('click', () => { C.wall = false; renderShell(); go(); BRIDGE?.keepScreenOn?.(false); document.exitFullscreen?.().catch(() => { }); });
  $('#btnApp')?.addEventListener('click', () => BRIDGE.openSettings());
  $('#burger').onclick = () => $('#side').classList.toggle('open');
  $('#side').addEventListener('click', (e) => { if (e.target.closest('a')) $('#side').classList.remove('open'); });
}
function setHead(title, actions = '') { $('#title').textContent = title; $('#topAct').innerHTML = actions; document.title = title + ' · Xanh24 CRM'; }
function setLive(ok, txt) { $('#liveDot')?.classList.toggle('off', !ok); const t = $('#liveTxt'); if (t) t.textContent = txt; }
async function badges() {
  try {
    const o = C.lastOverview || await api(M + '/overview');
    const a = $('#navApprove'), n = (o.approvals.revisions || 0) + (o.approvals.ads || 0);
    if (a) { a.textContent = n; a.hidden = !n; }
    const t = $('#navTasks'), m = o.tasks.filter(x => x.overdue).length;
    if (t) { t.textContent = m; t.hidden = !m; }
  } catch { }
}

// ---------------------------------------------------------------- router
const PAGES = {};
function go() {
  clearInterval(C.timer);
  const h = location.hash.replace(/^#\/?/, '');
  const [r, id] = h.split('/');
  C.route = r || '';
  $$('.nav a[data-r]').forEach(a => a.classList.toggle('on', a.dataset.r === C.route));
  const fn = PAGES[C.route] || PAGES[''];
  $('#page').innerHTML = `<div class="empty">Đang tải…</div>`;
  Promise.resolve(fn(id)).catch(e => { $('#page').innerHTML = `<div class="card"><div class="empty">${icon('info', 28)}${esc(e.message)}</div></div>`; setLive(false, 'Lỗi kết nối'); });
}
addEventListener('hashchange', go);

// ================================================================= TỔNG QUAN
PAGES[''] = async function overview() {
  setHead('Tổng quan vận hành', `<button class="btn sec sm" id="rf">${icon('refresh', 16)} Làm mới</button>`);
  $('#rf').onclick = () => go();
  const draw = async () => {
    const o = await api(M + '/overview'); C.lastOverview = o;
    setLive(true, 'Cập nhật ' + new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }));
    const k = o.kiosks, off = k.total - k.online, tasksOver = o.tasks.filter(t => t.overdue).length;
    const appr = o.approvals.revisions + o.approvals.ads;
    $('#page').innerHTML = `
    <div class="grid g4">
      ${kpi('Màn hình trực tuyến', `${k.online}<small> / ${k.total}</small>`, off ? `${off} màn hình mất kết nối` : 'Tất cả đang hoạt động', 'device', off ? 'bad' : 'good', '#/kiosk')}
      ${kpi('Lượt sử dụng hôm nay', fmtN(o.today.sessions), `${fmtN(o.today.poi_views)} lượt xem địa điểm · ${fmtN(o.today.routes)} chỉ đường`, 'touch', '', '#/kiosk')}
      ${kpi('Lượt hiển thị quảng cáo', fmtN(o.today.impressions), `${o.content.ads_live} quảng cáo đang chạy`, 'ad', '', '#/bao-cao')}
      ${kpi('Thu trong tháng', fmtShort(o.money.month_paid) + '<small> ₫</small>', `Công nợ còn lại ${fmtShort(o.money.receivable)} ₫`, 'chart', o.money.receivable ? 'warn' : 'good', '#/hop-dong')}
    </div>
    <div class="grid g4">
      ${kpi('Khách hàng', fmtN(o.customers), `${o.pipeline.filter(p => !['won', 'lost'].includes(p.stage)).reduce((a, p) => a + p.n, 0)} cơ hội đang theo`, 'user', '', '#/khach-hang')}
      ${kpi('Hợp đồng hiệu lực', fmtN(o.money.active_contracts), `Tổng giá trị ${fmtShort(o.money.active_value)} ₫`, 'doc', '', '#/hop-dong')}
      ${kpi('Chờ duyệt nội dung', fmtN(appr), `${o.approvals.revisions} địa điểm · ${o.approvals.ads} quảng cáo`, 'inbox', appr ? 'warn' : 'good', '#/duyet')}
      ${kpi('Việc quá hạn', fmtN(tasksOver), `${o.tasks_open} việc đang mở`, 'clock', tasksOver ? 'bad' : 'good', '#/viec')}
    </div>
    <div class="grid g21">
      <div class="card"><div class="hd"><h3>Lượt sử dụng màn hình — 30 ngày</h3><span class="sub">phiên chạm màn hình / ngày</span></div><div class="bd">${barChart(o.days, { key: 'sessions', label: 'Lượt sử dụng' })}</div></div>
      <div class="card"><div class="hd"><h3>Màn hình cần chú ý</h3><a class="btn ghost sm" href="#/kiosk">Tất cả</a></div><div class="bd"><div class="list">
        ${k.offline.length ? k.offline.slice(0, 7).map(d => `<div class="li"><span class="dot off"></span><span class="grow"><div class="t1">${esc(d.name)}</div><div class="t2">${esc(d.code)} · ${ago(d.last_seen)}</div></span><span class="pill bad">Mất kết nối</span></div>`).join('')
        : `<div class="empty">${icon('check', 28)}Tất cả ${k.total} màn hình đang trực tuyến</div>`}</div></div></div>
    </div>
    <div class="grid g21">
      <div class="card"><div class="hd"><h3>Lượt hiển thị quảng cáo — 30 ngày</h3></div><div class="bd">${barChart(o.days, { key: 'impressions', label: 'Lượt hiển thị', color: 'var(--s2)' })}</div></div>
      <div class="card"><div class="hd"><h3>Quảng cáo hiển thị nhiều nhất (7 ngày)</h3></div><div class="bd">${hbars(o.top_ads, { label: x => x.title, color: 'var(--s2)' })}</div></div>
    </div>
    <div class="grid g3">
      <div class="card"><div class="hd"><h3>Doanh thu đã thu — 6 tháng</h3></div><div class="bd">${barChart(o.money.revenue_6m, { key: 'amount', label: 'Đã thu', color: 'var(--s1)', fmt: fmtM, xlab: d => d.month.slice(0, 2) + '/' + d.month.slice(5), h: 200 })}</div></div>
      <div class="card"><div class="hd"><h3>Phễu bán hàng</h3><a class="btn ghost sm" href="#/phieu">Mở phễu</a></div><div class="bd">${hbars(o.pipeline, { label: x => x.label, value: x => x.n, fmt: (n) => fmtN(n) + ' KH' })}</div></div>
      <div class="card"><div class="hd"><h3>Việc đến hạn</h3><a class="btn ghost sm" href="#/viec">Tất cả</a></div><div class="bd"><div class="list">${o.tasks.length ? o.tasks.slice(0, 6).map(taskRow).join('') : `<div class="empty">${icon('check', 28)}Không có việc đến hạn</div>`}</div></div></div>
    </div>
    ${o.expiring.length ? `<div class="card"><div class="hd"><h3>Hợp đồng sắp hết hạn / quá hạn</h3></div><div class="bd tbl-wrap">${contractTable(o.expiring)}</div></div>` : ''}`;
    bindTasks($('#page'), draw); bindContractRows($('#page')); badges();
  };
  await draw();
  C.timer = setInterval(() => draw().catch(() => setLive(false, 'Mất kết nối máy chủ — thử lại sau')), C.wall ? 30000 : 60000);
};
function kpi(lb, v, ft, ic, tone = '', href = '') { return `<div class="card kpi ${tone}"><span class="ic-b">${icon(ic, 22)}</span><span class="lb">${lb}</span><span class="v num">${v}</span><span class="ft">${ft}</span>${href ? `<a class="more" href="${href}" aria-label="${esc(lb)}"></a>` : ''}</div>`; }

// ================================================================= KIOSK
PAGES.kiosk = async function kiosk() {
  setHead('Màn hình kiosk', `<div class="seg" id="kf"><button data-f="all" class="on">Tất cả</button><button data-f="off">Mất kết nối</button><button data-f="on">Trực tuyến</button></div>`);
  let filter = 'all';
  const draw = async () => {
    const d = await api(M + '/devices');
    setLive(true, 'Cập nhật ' + new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }));
    const items = d.items.filter(x => x.active && (filter === 'all' || (filter === 'on') === x.online));
    $('#page').innerHTML = items.length ? `<div class="tiles">${items.map(x => `<div class="card tile ${x.online ? '' : 'off'}">
      <div class="h"><span class="avatar" style="border-radius:12px">${icon('device', 18)}</span><span style="flex:1;min-width:0"><b>${esc(x.name)}</b><span class="sub">${esc(x.code)}${x.address ? ' · ' + esc(x.address) : ''}</span></span>${onlineTag(x)}</div>
      <div class="stats"><div><b class="num">${fmtN(x.today.sessions)}</b><span>Lượt dùng</span></div><div><b class="num">${fmtN(x.today.impressions)}</b><span>Hiển thị QC</span></div><div><b class="num">${fmtN(x.today.routes)}</b><span>Chỉ đường</span></div></div>
      <div class="sub">Kết nối: ${ago(x.last_seen)}${x.screen ? ' · ' + esc(x.screen) : ''} · 7 ngày: ${fmtN(x.sessions_7d)} lượt</div>
      ${x.contracts.length ? `<div class="sub">${icon('doc', 14, 'inl')} ${x.contracts.map(c => `<a href="#/khach-hang/${c.customer_id}">${esc(c.customer)}</a> (${esc(C.meta.contract_kinds[c.kind] || c.kind)})`).join(', ')}</div>` : ''}
      <div class="toolbar"><button class="btn sec sm" data-mt="${esc(x.code)}">${icon('settings', 14)} Tạo việc bảo trì</button>${x.open_tasks ? `<a class="pill warn" href="#/viec">${x.open_tasks} việc đang mở</a>` : ''}${(x.gps_lat || x.lat) ? `<a class="btn ghost sm" target="_blank" rel="noopener" href="/?pt=${x.gps_lat || x.lat},${x.gps_lng || x.lng}&name=${encodeURIComponent(x.name)}">${icon('pin', 14)} Bản đồ</a>` : ''}</div>
    </div>`).join('')}</div>` : `<div class="card"><div class="empty">${icon('device', 30)}Không có màn hình nào${filter === 'off' ? ' mất kết nối' : ''}. Thêm màn hình tại Dashboard → Màn hình kiosk.</div></div>`;
    $$('[data-mt]').forEach(b => b.onclick = () => activityForm({ kind: 'maintenance', device_code: b.dataset.mt, title: 'Bảo trì màn hình ' + b.dataset.mt, due_at: Math.floor(Date.now() / 1000) + 86400 }, draw));
  };
  $('#kf').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; filter = b.dataset.f; $$('#kf button').forEach(x => x.classList.toggle('on', x === b)); draw(); };
  await draw();
  C.timer = setInterval(() => draw().catch(() => setLive(false, 'Mất kết nối máy chủ')), 30000);
};

// ================================================================= KHÁCH HÀNG
PAGES['khach-hang'] = async function customers(id) {
  if (id) return customerDetail(+id);
  setHead('Khách hàng', can('crm.edit') ? `<button class="btn pri sm" id="addC">${icon('plus', 16)} Thêm khách hàng</button>` : '');
  $('#addC')?.addEventListener('click', () => customerForm({}, () => go()));
  $('#page').innerHTML = `<div class="card"><div class="bd"><div class="toolbar">
      <label class="search">${icon('search', 18)}<input class="in" id="cq" placeholder="Tìm tên, người liên hệ, điện thoại, email, MST…"></label>
      <select class="in" id="ck"><option value="">Mọi loại khách hàng</option>${opts(C.meta.kinds)}</select>
      <select class="in" id="cs"><option value="">Mọi giai đoạn</option>${opts(C.meta.stages)}</select>
      <span class="grow"></span><button class="btn sec sm" id="cx">${icon('download', 16)} Xuất CSV</button></div></div>
    <div class="tbl-wrap" id="clist"></div></div>`;
  let items = [];
  const load = async () => {
    const p = new URLSearchParams({ q: $('#cq').value, kind: $('#ck').value, stage: $('#cs').value });
    items = (await api(M + '/customers?' + p)).items; setLive(true, `${items.length} khách hàng`);
    $('#clist').innerHTML = items.length ? `<table class="tbl"><thead><tr><th>Khách hàng</th><th>Loại</th><th>Giai đoạn</th><th>Liên hệ</th><th class="r">HĐ hiệu lực</th><th class="r">Giá trị</th><th>Phụ trách</th><th>Cập nhật</th></tr></thead><tbody>
      ${items.map(c => `<tr class="click" data-id="${c.id}"><td><div class="t1">${esc(c.name)}</div><div class="t2">${esc(c.tax_code ? 'MST ' + c.tax_code : c.address || '')}</div></td>
        <td><span class="pill">${icon(KIND_ICON[c.kind] || 'user', 13)} ${esc(C.meta.kinds[c.kind] || c.kind)}</span></td><td>${stageTag(c.stage)}</td>
        <td><div>${esc(c.contact_name)}</div><div class="t2">${esc(c.phone)}${c.email ? ' · ' + esc(c.email) : ''}</div></td>
        <td class="r num">${c.active || '—'}</td><td class="r num">${c.value ? fmtShort(c.value) : (c.expected_value ? '<span class="t2">~' + fmtShort(c.expected_value) + '</span>' : '—')}</td>
        <td>${esc(c.owner)}</td><td class="t2">${ago(c.last_activity || c.updated_at)}</td></tr>`).join('')}</tbody></table>`
      : `<div class="empty">${icon('user', 30)}Chưa có khách hàng phù hợp</div>`;
    $$('#clist tr[data-id]').forEach(tr => tr.onclick = () => location.hash = '#/khach-hang/' + tr.dataset.id);
  };
  let t; $('#cq').oninput = () => { clearTimeout(t); t = setTimeout(load, 250); };
  $('#ck').onchange = $('#cs').onchange = load;
  $('#cx').onclick = () => saveCSV('xanh24-khach-hang.csv', [['Tên', 'Loại', 'Giai đoạn', 'Người liên hệ', 'Điện thoại', 'Email', 'MST', 'Địa chỉ', 'Nguồn', 'Giá trị dự kiến', 'HĐ hiệu lực', 'Giá trị HĐ', 'Phụ trách'],
    ...items.map(c => [c.name, C.meta.kinds[c.kind], C.meta.stages[c.stage], c.contact_name, c.phone, c.email, c.tax_code, c.address, c.source, c.expected_value, c.active, c.value, c.owner])]);
  await load();
};

async function customerDetail(id) {
  const d = await api(`${M}/customers/${id}`); const c = d.customer;
  setHead(c.name, `<a class="btn sec sm" href="#/khach-hang">${icon('back', 16)} Danh sách</a>`);
  const total = d.contracts.filter(x => x.status === 'active').reduce((a, x) => a + (+x.value || 0), 0);
  const paid = d.contracts.filter(x => x.status === 'active').reduce((a, x) => a + x.paid, 0);
  const ward = C.meta.wards.find(w => w.slug === c.ward_slug);
  $('#page').innerHTML = `
  <div class="card"><div class="bd"><div class="dhead"><span class="big">${esc(initials(c.name))}</span>
    <div style="flex:1;min-width:240px"><h2>${esc(c.name)}</h2><div class="toolbar"><span class="pill">${icon(KIND_ICON[c.kind] || 'user', 13)} ${esc(C.meta.kinds[c.kind] || c.kind)}</span>${stageTag(c.stage)}${(c.tags || []).map(t => `<span class="pill">#${esc(t)}</span>`).join('')}</div></div>
    <div class="toolbar">${can('crm.edit') ? `<select class="in" id="stg" style="min-width:190px" aria-label="Giai đoạn">${opts(C.meta.stages, c.stage)}</select><button class="btn sec sm" id="edC">${icon('edit', 16)} Sửa</button>` : ''}
      ${c.phone ? `<a class="btn sec sm" href="tel:${esc(c.phone)}">${icon('phone', 16)} Gọi</a>` : ''}${can('crm.delete') ? `<button class="btn ghost sm" id="delC">${icon('trash', 16)}</button>` : ''}</div></div></div></div>
  <div class="grid g4">
    ${kpi('Hợp đồng hiệu lực', d.contracts.filter(x => x.status === 'active').length, `${d.contracts.length} hợp đồng tất cả`, 'doc')}
    ${kpi('Giá trị hiệu lực', fmtShort(total) + '<small> ₫</small>', c.expected_value ? 'Dự kiến ' + fmtShort(c.expected_value) + ' ₫' : '—', 'chart')}
    ${kpi('Đã thu', fmtShort(paid) + '<small> ₫</small>', `Còn lại ${fmtShort(Math.max(0, total - paid))} ₫`, 'check', total - paid > 0 ? 'warn' : 'good')}
    ${kpi('Hiển thị quảng cáo (30 ngày)', fmtN(c.ads.reduce((a, x) => a + x.impressions_30d, 0)), `${c.ads.length} quảng cáo gắn hợp đồng`, 'ad')}
  </div>
  <div class="grid g21">
    <div class="grid">
      <div class="card"><div class="hd"><h3>Hợp đồng</h3>${can('crm.finance') ? `<button class="btn pri sm" id="addK">${icon('plus', 16)} Hợp đồng</button>` : ''}</div><div class="bd tbl-wrap">${d.contracts.length ? contractTable(d.contracts, true) : `<div class="empty">Chưa có hợp đồng</div>`}</div></div>
      <div class="card"><div class="hd"><h3>Quảng cáo của khách hàng</h3>${c.ads.length ? `<a class="btn ghost sm" href="#/bao-cao/c${c.id}">${icon('chart', 16)} Báo cáo</a>` : ''}</div><div class="bd">${c.ads.length ? `<div class="list">${c.ads.map(a => `<div class="li">${icon('ad', 20)}<span class="grow"><div class="t1">${esc(a.title)}</div><div class="t2">${esc(a.media_type)} · ${a.status === 'published' ? 'đang chạy' : esc(a.status)}</div></span><b class="num">${fmtN(a.impressions_30d)}</b><span class="t2">lượt / 30 ngày</span></div>`).join('')}</div>` : `<div class="empty">Gắn quảng cáo vào hợp đồng để theo dõi lượt hiển thị</div>`}</div></div>
      <div class="card"><div class="hd"><h3>Nhật ký & việc cần làm</h3>${can('crm.edit') ? `<button class="btn pri sm" id="addA">${icon('plus', 16)} Ghi chú / việc</button>` : ''}</div><div class="bd"><div class="timeline">${d.activities.length ? d.activities.map(a => `<div class="tl"><span class="ib">${icon(ACT_ICON[a.kind] || 'edit', 16)}</span><div><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><b>${esc(a.title || C.meta.act_kinds[a.kind])}</b>${a.due_at ? (a.done ? '<span class="pill good">Đã xong</span>' : `<span class="pill ${a.due_at < Date.now() / 1000 ? 'bad' : 'warn'}">Hạn ${fmtDate(a.due_at)}</span>`) : ''}${a.due_at && !a.done && can('crm.edit') ? `<button class="btn ghost sm" data-done="${a.id}">${icon('check', 14)} Xong</button>` : ''}</div>${a.content ? `<div style="white-space:pre-wrap">${esc(a.content)}</div>` : ''}<div class="t2">${esc(C.meta.act_kinds[a.kind] || a.kind)} · ${esc(a.author)} · ${fmtTime(a.created_at)}${a.assignee ? ' · phụ trách: ' + esc(a.assignee) : ''}</div></div></div>`).join('') : `<div class="empty">Chưa có hoạt động</div>`}</div></div></div>
    </div>
    <div class="grid" style="align-content:start">
      <div class="card"><div class="hd"><h3>Thông tin</h3></div><div class="bd"><dl class="kv">
        <dt>Người liên hệ</dt><dd>${esc(c.contact_name) || '—'}</dd><dt>Điện thoại</dt><dd>${esc(c.phone) || '—'}</dd><dt>Email</dt><dd>${c.email ? `<a href="mailto:${esc(c.email)}">${esc(c.email)}</a>` : '—'}</dd>
        <dt>Mã số thuế</dt><dd>${esc(c.tax_code) || '—'}</dd><dt>Địa chỉ</dt><dd>${esc(c.address) || '—'}</dd><dt>Phường / xã</dt><dd>${esc(ward?.name || '') || '—'}</dd>
        <dt>Nguồn</dt><dd>${esc(c.source) || '—'}</dd><dt>Phụ trách</dt><dd>${esc(c.owner) || '—'}</dd><dt>Tạo lúc</dt><dd>${fmtTime(c.created_at)}</dd></dl>
        ${c.notes ? `<div class="note" style="margin-top:14px;white-space:pre-wrap">${esc(c.notes)}</div>` : ''}</div></div>
      <div class="card"><div class="hd"><h3>Địa điểm trên bản đồ</h3></div><div class="bd">${c.pois.length ? `<div class="list">${c.pois.map(p => `<div class="li">${icon('pin', 18)}<span class="grow"><div class="t1">${esc(p.name)}</div><div class="t2">${esc(p.status)}</div></span><a class="btn ghost sm" target="_blank" rel="noopener" href="/?poi=${p.id}">Xem</a></div>`).join('')}</div>` : `<div class="empty">Chưa gắn địa điểm (sửa khách hàng để gắn)</div>`}</div></div>
    </div>
  </div>`;
  const reload = () => customerDetail(id);
  $('#stg')?.addEventListener('change', async (e) => { try { await api(`${M}/customers/${id}`, { method: 'PUT', body: { stage: e.target.value } }); toast('Đã chuyển giai đoạn', 'ok'); reload(); } catch (er) { fail(er); } });
  $('#edC')?.addEventListener('click', () => customerForm(c, reload));
  $('#delC')?.addEventListener('click', async () => { if (await confirmBox('Xoá khách hàng', `Xoá <b>${esc(c.name)}</b> cùng toàn bộ hợp đồng, thanh toán và nhật ký? Không thể hoàn tác.`, { okText: 'Xoá', danger: true })) { try { await api(`${M}/customers/${id}`, { method: 'DELETE' }); toast('Đã xoá', 'ok'); location.hash = '#/khach-hang'; } catch (er) { fail(er); } } });
  $('#addK')?.addEventListener('click', () => contractForm({ customer_id: id, status: 'active', kind: c.kind === 'site_owner' ? 'placement' : c.kind === 'partner' ? 'partner' : 'ads' }, reload));
  $('#addA')?.addEventListener('click', () => activityForm({ customer_id: id }, reload));
  $$('[data-done]').forEach(b => b.onclick = async () => { try { await api(`${M}/activities/${b.dataset.done}/done`, { method: 'POST', body: {} }); reload(); } catch (er) { fail(er); } });
  bindContractRows($('#page'), reload);
}

function customerForm(c, after) {
  const isNew = !c.id;
  const card = modal(`<div class="mh"><h3>${isNew ? 'Thêm khách hàng' : 'Sửa khách hàng'}</h3><button class="iconbtn" data-close aria-label="Đóng">${icon('close', 18)}</button></div><form class="mb" id="cf">
    <div class="field"><label>Tên khách hàng / doanh nghiệp *</label><input class="in" name="name" value="${esc(c.name)}" required></div>
    <div class="frow"><div class="field"><label>Loại</label><select class="in" name="kind">${opts(C.meta.kinds, c.kind || 'advertiser')}</select></div><div class="field"><label>Giai đoạn</label><select class="in" name="stage">${opts(C.meta.stages, c.stage || 'lead')}</select></div></div>
    <div class="frow"><div class="field"><label>Người liên hệ</label><input class="in" name="contact_name" value="${esc(c.contact_name)}"></div><div class="field"><label>Điện thoại</label><input class="in" name="phone" inputmode="tel" value="${esc(c.phone)}"></div></div>
    <div class="frow"><div class="field"><label>Email</label><input class="in" name="email" type="email" value="${esc(c.email)}"></div><div class="field"><label>Mã số thuế</label><input class="in" name="tax_code" value="${esc(c.tax_code)}"></div></div>
    <div class="field"><label>Địa chỉ</label><input class="in" name="address" value="${esc(c.address)}"></div>
    <div class="frow"><div class="field"><label>Phường / xã</label><select class="in" name="ward_slug"><option value="">—</option>${C.meta.wards.map(w => `<option value="${w.slug}" ${w.slug === c.ward_slug ? 'selected' : ''}>${esc(w.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Phụ trách</label><select class="in" name="owner_id"><option value="">—</option>${C.meta.users.map(u => `<option value="${u.id}" ${u.id === (c.owner_id ?? C.meta.me.id) ? 'selected' : ''}>${esc(u.name)}</option>`).join('')}</select></div></div>
    <div class="frow"><div class="field"><label>Nguồn khách</label><input class="in" name="source" list="srcs" value="${esc(c.source)}"><datalist id="srcs"><option>Giới thiệu</option><option>Website xanh24.com</option><option>Khảo sát thực địa</option><option>Sự kiện</option><option>Mạng xã hội</option></datalist></div>
      <div class="field"><label>Giá trị dự kiến (₫)</label><input class="in" name="expected_value" inputmode="numeric" value="${c.expected_value || ''}"></div></div>
    <div class="field"><label>Thẻ (cách nhau bằng dấu phẩy)</label><input class="in" name="tags" value="${esc((c.tags || []).join(', '))}" placeholder="VD: F&B, Cầu Giấy, VIP"></div>
    <div class="field"><label>Địa điểm trên bản đồ</label><div id="poiSel"></div><input class="in" id="poiQ" placeholder="Gõ tên địa điểm để gắn…" autocomplete="off"><div class="list" id="poiRes"></div></div>
    <div class="field"><label>Ghi chú</label><textarea class="in" name="notes">${esc(c.notes)}</textarea></div></form>
    <div class="mf"><button class="btn sec" data-close>Huỷ</button><button class="btn pri" id="cfOk">Lưu</button></div>`, { wide: true });
  let pois = (c.pois || []).map(p => ({ id: p.id, name: p.name }));
  const drawSel = () => { $('#poiSel', card).innerHTML = pois.map(p => `<span class="pill info" style="margin:0 6px 6px 0">${esc(p.name)} <button type="button" data-rm="${p.id}" aria-label="Bỏ">${icon('x', 12)}</button></span>`).join(''); $$('[data-rm]', card).forEach(b => b.onclick = () => { pois = pois.filter(p => p.id !== +b.dataset.rm); drawSel(); }); };
  drawSel();
  let pt; $('#poiQ', card).oninput = (e) => { clearTimeout(pt); pt = setTimeout(async () => { const v = e.target.value.trim(); if (v.length < 2) { $('#poiRes', card).innerHTML = ''; return; } const r = await api(M + '/pois?q=' + encodeURIComponent(v)); $('#poiRes', card).innerHTML = r.items.slice(0, 6).map(p => `<button type="button" class="li" data-add="${p.id}" data-n="${esc(p.name)}" style="text-align:left">${icon('plus', 14)}<span class="grow">${esc(p.name)}</span></button>`).join(''); $$('[data-add]', card).forEach(b => b.onclick = () => { if (!pois.some(p => p.id === +b.dataset.add)) pois.push({ id: +b.dataset.add, name: b.dataset.n }); drawSel(); $('#poiRes', card).innerHTML = ''; $('#poiQ', card).value = ''; }); }, 250); };
  $('#cfOk').onclick = async () => {
    const f = $('#cf'); if (!f.reportValidity()) return;
    const v = Object.fromEntries(new FormData(f));
    v.tags = v.tags.split(',').map(s => s.trim()).filter(Boolean); v.poi_ids = pois.map(p => p.id);
    v.expected_value = +String(v.expected_value).replace(/\D/g, '') || 0; v.owner_id = v.owner_id ? +v.owner_id : null;
    try { const r = await api(isNew ? M + '/customers' : `${M}/customers/${c.id}`, { method: isNew ? 'POST' : 'PUT', body: v }); closeModal(); toast('Đã lưu khách hàng', 'ok'); if (isNew) location.hash = '#/khach-hang/' + r.id; else after?.(); } catch (e) { fail(e); }
  };
}

// ================================================================= PHỄU BÁN HÀNG (kéo thả)
PAGES.phieu = async function pipeline() {
  setHead('Phễu bán hàng', can('crm.edit') ? `<button class="btn pri sm" id="addC">${icon('plus', 16)} Khách tiềm năng</button>` : '');
  $('#addC')?.addEventListener('click', () => customerForm({ stage: 'lead' }, () => go()));
  const items = (await api(M + '/customers')).items; setLive(true, `${items.length} khách hàng`);
  const cols = Object.entries(C.meta.stages);
  $('#page').innerHTML = `<div class="note">${can('crm.edit') ? 'Kéo thẻ khách hàng sang cột khác để chuyển giai đoạn. ' : ''}Chạm vào thẻ để mở hồ sơ khách hàng.</div><div class="kanban">${cols.map(([k, label]) => {
    const list = items.filter(c => c.stage === k), sum = list.reduce((a, c) => a + (+c.value || +c.expected_value || 0), 0);
    return `<div class="col" data-stage="${k}"><h4>${stageTag(k).replace(esc(label), esc(label))}<span class="n">${list.length}</span></h4><div class="sum">${sum ? fmtShort(sum) + ' ₫' : '&nbsp;'}</div>
      ${list.map(c => `<div class="deal" draggable="${can('crm.edit')}" data-id="${c.id}"><b>${esc(c.name)}</b><div class="t2"><span>${esc(C.meta.kinds[c.kind] || '')}</span><span class="num">${(c.value || c.expected_value) ? fmtShort(c.value || c.expected_value) : ''}</span></div><div class="t2"><span>${esc(c.owner)}</span><span>${ago(c.last_activity || c.updated_at)}</span></div></div>`).join('')}</div>`;
  }).join('')}</div>`;
  $$('.deal').forEach(el => {
    el.onclick = () => location.hash = '#/khach-hang/' + el.dataset.id;
    el.ondragstart = (e) => { e.dataTransfer.setData('text/plain', el.dataset.id); };
  });
  $$('.col').forEach(col => {
    col.ondragover = (e) => { e.preventDefault(); col.classList.add('drop'); };
    col.ondragleave = () => col.classList.remove('drop');
    col.ondrop = async (e) => { e.preventDefault(); col.classList.remove('drop'); const id = e.dataTransfer.getData('text/plain'); try { await api(`${M}/customers/${id}`, { method: 'PUT', body: { stage: col.dataset.stage } }); toast('Đã chuyển sang ' + C.meta.stages[col.dataset.stage], 'ok'); go(); } catch (er) { fail(er); } };
  });
};

// ================================================================= HỢP ĐỒNG
PAGES['hop-dong'] = async function contracts() {
  setHead('Hợp đồng & thanh toán', can('crm.finance') ? `<button class="btn pri sm" id="addK">${icon('plus', 16)} Hợp đồng</button>` : '');
  $('#page').innerHTML = `<div class="card"><div class="bd"><div class="toolbar"><select class="in" id="ks"><option value="">Mọi trạng thái</option>${opts(C.meta.contract_status)}</select><select class="in" id="kk"><option value="">Mọi loại</option>${opts(C.meta.contract_kinds)}</select><span class="grow"></span><span class="sub" id="ksum"></span><button class="btn sec sm" id="kx">${icon('download', 16)} Xuất CSV</button></div></div><div class="tbl-wrap" id="klist"></div></div>`;
  let items = [];
  const load = async () => {
    items = (await api(M + '/contracts?' + new URLSearchParams({ status: $('#ks').value, kind: $('#kk').value }))).items;
    const val = items.reduce((a, c) => a + (+c.value || 0), 0), paid = items.reduce((a, c) => a + c.paid, 0);
    $('#ksum').innerHTML = `${items.length} hợp đồng · giá trị <b>${fmtM(val)}</b> · đã thu <b>${fmtM(paid)}</b>`;
    $('#klist').innerHTML = items.length ? contractTable(items) : `<div class="empty">${icon('doc', 30)}Chưa có hợp đồng</div>`;
    bindContractRows($('#klist'), load); setLive(true, `${items.length} hợp đồng`);
  };
  $('#ks').onchange = $('#kk').onchange = load;
  $('#addK')?.addEventListener('click', () => contractForm({ status: 'active', kind: 'ads' }, load));
  $('#kx').onclick = () => saveCSV('xanh24-hop-dong.csv', [['Mã HĐ', 'Khách hàng', 'Loại', 'Nội dung', 'Giá trị', 'Đã thu', 'Còn lại', 'Bắt đầu', 'Kết thúc', 'Trạng thái', 'Màn hình'],
    ...items.map(c => [c.code, c.customer_name, C.meta.contract_kinds[c.kind], c.title, c.value, c.paid, c.due, fmtDate(c.start_at), fmtDate(c.end_at), C.meta.contract_status[c.status], (c.device_codes || []).join(' ')])]);
  await load();
};
function contractTable(items, noCustomer = false) {
  return `<table class="tbl"><thead><tr><th>Mã HĐ</th>${noCustomer ? '' : '<th>Khách hàng</th>'}<th>Loại / nội dung</th><th>Thời hạn</th><th class="r">Giá trị</th><th style="min-width:140px">Đã thu</th><th>Trạng thái</th></tr></thead><tbody>
  ${items.map(c => `<tr class="click" data-k="${c.id}"><td class="t1">${esc(c.code)}</td>${noCustomer ? '' : `<td>${esc(c.customer_name)}</td>`}<td><div>${esc(C.meta.contract_kinds[c.kind] || c.kind)}</div><div class="t2">${esc(c.title)}${(c.device_codes || []).length ? ' · ' + c.device_codes.length + ' màn hình' : ''}</div></td>
    <td class="t2">${fmtDate(c.start_at)} → ${fmtDate(c.end_at)}</td><td class="r num">${fmtM(c.value)}</td>
    <td><div class="progress" data-tip="${esc(`<b>${esc(c.code)}</b>Đã thu ${fmtM(c.paid)} / ${fmtM(c.value)}`)}"><i style="width:${c.value ? Math.min(100, c.paid / c.value * 100) : 0}%"></i></div><div class="t2 num">${fmtShort(c.paid)} / ${fmtShort(c.value)}</div></td><td>${contractTag(c)}</td></tr>`).join('')}</tbody></table>`;
}
function bindContractRows(root, after) {
  $$('tr[data-k]', root).forEach(tr => tr.onclick = async () => {
    const all = (await api(M + '/contracts')).items; const c = all.find(x => x.id === +tr.dataset.k); if (!c) return;
    const det = await api(`${M}/customers/${c.customer_id}`); const full = det.contracts.find(x => x.id === c.id) || c;
    contractView(full, det.customer, after || (() => go()));
  });
}
function contractView(c, cust, after) {
  const devs = (c.device_codes || []).map(code => C.meta.devices.find(d => d.code === code)?.name || code);
  const ads = (c.ad_ids || []).map(id => C.meta.ads.find(a => a.id === id)?.title || '#' + id);
  modal(`<div class="mh"><h3>${esc(c.code)} · ${esc(cust.name)}</h3>${contractTag(c)}<button class="iconbtn" data-close aria-label="Đóng">${icon('close', 18)}</button></div><div class="mb">
    <dl class="kv"><dt>Loại</dt><dd>${esc(C.meta.contract_kinds[c.kind] || c.kind)}</dd><dt>Nội dung</dt><dd>${esc(c.title) || '—'}</dd><dt>Thời hạn</dt><dd>${fmtDate(c.start_at)} → ${fmtDate(c.end_at)}</dd>
      <dt>Giá trị</dt><dd><b>${fmtM(c.value)}</b></dd><dt>Đã thu</dt><dd>${fmtM(c.paid)} · còn lại <b>${fmtM(c.due)}</b></dd>
      <dt>Màn hình</dt><dd>${devs.length ? devs.map(esc).join(', ') : 'Tất cả / không gắn'}</dd><dt>Quảng cáo</dt><dd>${ads.length ? ads.map(esc).join(', ') : '—'}</dd>${c.notes ? `<dt>Ghi chú</dt><dd style="white-space:pre-wrap">${esc(c.notes)}</dd>` : ''}</dl>
    <h4 style="margin:20px 0 6px">Các lần thanh toán</h4><div class="list">${(c.payments || []).length ? c.payments.map(p => `<div class="li">${icon('check', 18)}<span class="grow"><div class="t1 num">${fmtM(p.amount)}</div><div class="t2">${fmtDate(p.paid_at)}${p.method ? ' · ' + esc(p.method) : ''}${p.note ? ' · ' + esc(p.note) : ''}</div></span>${can('crm.finance') ? `<button class="iconbtn" data-dp="${p.id}" aria-label="Xoá">${icon('trash', 16)}</button>` : ''}</div>`).join('') : '<div class="empty" style="padding:14px">Chưa có thanh toán</div>'}</div>
    ${can('crm.finance') ? `<form class="toolbar" id="payF" style="margin-top:12px"><input class="in" name="amount" inputmode="numeric" placeholder="Số tiền (₫)" style="min-width:140px;flex:1" required><input class="in" type="date" name="paid_at" value="${toInput(Math.floor(Date.now() / 1000))}" style="min-width:150px"><input class="in" name="method" placeholder="Hình thức" value="Chuyển khoản" style="min-width:130px"><button class="btn ok sm">${icon('plus', 14)} Ghi nhận</button></form>` : ''}
  </div><div class="mf">${can('crm.delete') ? `<button class="btn ghost" id="kDel">${icon('trash', 16)} Xoá</button><span style="flex:1"></span>` : ''}${(c.ad_ids || []).length ? `<a class="btn sec" href="#/bao-cao/k${c.id}" data-close>${icon('chart', 16)} Báo cáo hiển thị</a>` : ''}${can('crm.finance') ? `<button class="btn pri" id="kEd">${icon('edit', 16)} Sửa hợp đồng</button>` : ''}</div>`, { wide: true });
  $('#payF')?.addEventListener('submit', async (e) => { e.preventDefault(); const v = Object.fromEntries(new FormData(e.target)); try { await api(`${M}/contracts/${c.id}/payments`, { method: 'POST', body: { amount: +String(v.amount).replace(/\D/g, ''), paid_at: toTs(v.paid_at), method: v.method } }); toast('Đã ghi nhận thanh toán', 'ok'); closeModal(); after(); } catch (er) { fail(er); } });
  $$('[data-dp]').forEach(b => b.onclick = async () => { try { await api(`${M}/payments/${b.dataset.dp}`, { method: 'DELETE' }); closeModal(); after(); } catch (er) { fail(er); } });
  $('#kEd')?.addEventListener('click', () => contractForm(c, after));
  $('#kDel')?.addEventListener('click', async () => { if (await confirmBox('Xoá hợp đồng', `Xoá hợp đồng <b>${esc(c.code)}</b> và các thanh toán?`, { okText: 'Xoá', danger: true })) { try { await api(`${M}/contracts/${c.id}`, { method: 'DELETE' }); toast('Đã xoá', 'ok'); after(); } catch (er) { fail(er); } } });
}
async function contractForm(c, after) {
  const isNew = !c.id;
  const custs = isNew && !c.customer_id ? (await api(M + '/customers')).items : null;
  const chk = (list, sel, name, label) => `<div style="display:flex;flex-wrap:wrap;gap:6px;max-height:140px;overflow:auto">${list.map(x => `<label class="pill" style="cursor:pointer"><input type="checkbox" name="${name}" value="${x.v}" ${sel.includes(x.v) ? 'checked' : ''}> ${esc(x.t)}</label>`).join('') || `<span class="sub">${label}</span>`}</div>`;
  const card = modal(`<div class="mh"><h3>${isNew ? 'Hợp đồng mới' : 'Sửa hợp đồng ' + esc(c.code)}</h3><button class="iconbtn" data-close aria-label="Đóng">${icon('close', 18)}</button></div><form class="mb" id="kf">
    ${custs ? `<div class="field"><label>Khách hàng *</label><select class="in" name="customer_id" required><option value="">— Chọn —</option>${custs.map(x => `<option value="${x.id}">${esc(x.name)}</option>`).join('')}</select></div>` : ''}
    <div class="frow"><div class="field"><label>Loại hợp đồng</label><select class="in" name="kind">${opts(C.meta.contract_kinds, c.kind)}</select></div><div class="field"><label>Trạng thái</label><select class="in" name="status">${opts(C.meta.contract_status, c.status)}</select></div></div>
    <div class="frow"><div class="field"><label>Mã hợp đồng</label><input class="in" name="code" value="${esc(c.code)}" placeholder="Để trống: tự sinh HD-năm-số"></div><div class="field"><label>Giá trị (₫)</label><input class="in" name="value" inputmode="numeric" value="${c.value || ''}"></div></div>
    <div class="field"><label>Nội dung</label><input class="in" name="title" value="${esc(c.title)}" placeholder="VD: Quảng cáo video 15s, 3 tháng, 4 màn hình Cầu Giấy"></div>
    <div class="frow"><div class="field"><label>Bắt đầu</label><input class="in" type="date" name="start_at" value="${toInput(c.start_at)}"></div><div class="field"><label>Kết thúc</label><input class="in" type="date" name="end_at" value="${toInput(c.end_at)}"></div></div>
    <div class="field"><label>Màn hình kiosk áp dụng</label>${chk(C.meta.devices.map(d => ({ v: d.code, t: d.code + ' · ' + d.name })), c.device_codes || [], 'device_codes', 'Chưa có màn hình')}</div>
    <div class="field"><label>Quảng cáo thuộc hợp đồng (để báo cáo lượt hiển thị)</label>${chk(C.meta.ads.map(a => ({ v: String(a.id), t: a.title })), (c.ad_ids || []).map(String), 'ad_ids', 'Chưa có quảng cáo — tạo tại Dashboard → Quảng cáo')}</div>
    <div class="field"><label>Ghi chú</label><textarea class="in" name="notes">${esc(c.notes)}</textarea></div></form>
    <div class="mf"><button class="btn sec" data-close>Huỷ</button><button class="btn pri" id="kfOk">Lưu hợp đồng</button></div>`, { wide: true });
  $('#kfOk').onclick = async () => {
    const f = $('#kf'); if (!f.reportValidity()) return;
    const fd = new FormData(f), v = Object.fromEntries(fd);
    const body = { kind: v.kind, status: v.status, code: v.code, title: v.title, notes: v.notes, value: +String(v.value).replace(/\D/g, '') || 0,
      start_at: toTs(v.start_at), end_at: toTs(v.end_at) ? toTs(v.end_at) + 86399 : null, device_codes: fd.getAll('device_codes'), ad_ids: fd.getAll('ad_ids').map(Number),
      customer_id: v.customer_id ? +v.customer_id : c.customer_id };
    try { await api(isNew ? M + '/contracts' : `${M}/contracts/${c.id}`, { method: isNew ? 'POST' : 'PUT', body }); closeModal(); toast('Đã lưu hợp đồng', 'ok'); after?.(); } catch (e) { fail(e); }
  };
  void card;
}

// ================================================================= VIỆC CẦN LÀM
PAGES.viec = async function tasks() {
  setHead('Việc cần làm', can('crm.edit') ? `<button class="btn pri sm" id="addT">${icon('plus', 16)} Việc mới</button>` : '');
  $('#page').innerHTML = `<div class="card"><div class="bd"><div class="toolbar"><div class="seg" id="ts"><button data-s="open" class="on">Đang mở</button><button data-s="done">Đã xong</button></div><label class="pill" style="cursor:pointer"><input type="checkbox" id="tm"> Chỉ việc của tôi</label><select class="in" id="tk"><option value="">Mọi loại</option>${opts(C.meta.act_kinds)}</select></div></div><div class="bd" style="padding-top:0"><div class="list" id="tlist"></div></div></div>`;
  let st = 'open';
  const load = async () => {
    const r = await api(M + '/activities?' + new URLSearchParams({ status: st, mine: $('#tm').checked ? '1' : '', kind: $('#tk').value }));
    $('#tlist').innerHTML = r.items.length ? r.items.map(taskRow).join('') : `<div class="empty">${icon('check', 30)}${st === 'open' ? 'Không còn việc nào — tuyệt vời!' : 'Chưa có việc đã xong'}</div>`;
    bindTasks($('#tlist'), load); setLive(true, `${r.items.length} việc`); badges();
  };
  $('#ts').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; st = b.dataset.s; $$('#ts button').forEach(x => x.classList.toggle('on', x === b)); load(); };
  $('#tm').onchange = $('#tk').onchange = load;
  $('#addT')?.addEventListener('click', () => activityForm({ kind: 'task', due_at: Math.floor(Date.now() / 1000) + 86400 }, load));
  await load();
};
function taskRow(t) {
  const due = t.due_at ? `<span class="pill ${t.done ? 'good' : t.overdue ? 'bad' : 'warn'}">${t.done ? 'Xong ' + fmtDate(t.done_at) : (t.overdue ? 'Quá hạn ' : 'Hạn ') + fmtDate(t.due_at)}</span>` : '';
  return `<div class="li"><button class="chk ${t.done ? 'on' : ''}" data-t="${t.id}" data-d="${t.done ? 1 : 0}" aria-label="Đánh dấu hoàn thành" ${can('crm.edit') ? '' : 'disabled'}>${t.done ? icon('check', 14) : ''}</button>
    <span class="grow"><div class="t1">${icon(ACT_ICON[t.kind] || 'check', 14, 'inl')} ${esc(t.title || C.meta.act_kinds[t.kind])}</div><div class="t2">${t.customer_id ? `<a href="#/khach-hang/${t.customer_id}">${esc(t.customer_name || '')}</a> · ` : ''}${t.device_code ? 'Màn hình ' + esc(t.device_code) + ' · ' : ''}${esc(t.assignee || 'chưa giao')}</div></span>${due}</div>`;
}
function bindTasks(root, after) {
  $$('[data-t]', root).forEach(b => b.onclick = async () => { try { await api(`${M}/activities/${b.dataset.t}/done`, { method: 'POST', body: { done: b.dataset.d !== '1' } }); toast(b.dataset.d === '1' ? 'Đã mở lại việc' : 'Đã hoàn thành', 'ok'); after(); } catch (e) { fail(e); } });
}
async function activityForm(a, after) {
  const custs = a.customer_id ? null : (await api(M + '/customers')).items;
  modal(`<div class="mh"><h3>${a.kind === 'maintenance' ? 'Việc bảo trì màn hình' : 'Ghi chú / việc cần làm'}</h3><button class="iconbtn" data-close aria-label="Đóng">${icon('close', 18)}</button></div><form class="mb" id="af">
    <div class="frow"><div class="field"><label>Loại</label><select class="in" name="kind">${opts(C.meta.act_kinds, a.kind || 'note')}</select></div>
      ${custs ? `<div class="field"><label>Khách hàng</label><select class="in" name="customer_id"><option value="">— Không —</option>${custs.map(x => `<option value="${x.id}">${esc(x.name)}</option>`).join('')}</select></div>` : '<div></div>'}</div>
    <div class="field"><label>Tiêu đề</label><input class="in" name="title" value="${esc(a.title)}"></div>
    <div class="field"><label>Nội dung</label><textarea class="in" name="content"></textarea></div>
    <div class="frow"><div class="field"><label>Hạn xử lý (để trống = chỉ ghi nhật ký)</label><input class="in" type="date" name="due_at" value="${toInput(a.due_at)}"></div>
      <div class="field"><label>Người phụ trách</label><select class="in" name="assignee_id"><option value="">—</option>${C.meta.users.map(u => `<option value="${u.id}" ${u.id === C.meta.me.id ? 'selected' : ''}>${esc(u.name)}</option>`).join('')}</select></div></div>
    <div class="field"><label>Màn hình liên quan</label><select class="in" name="device_code"><option value="">—</option>${C.meta.devices.map(d => `<option value="${esc(d.code)}" ${d.code === a.device_code ? 'selected' : ''}>${esc(d.code)} · ${esc(d.name)}</option>`).join('')}</select></div></form>
    <div class="mf"><button class="btn sec" data-close>Huỷ</button><button class="btn pri" id="afOk">Lưu</button></div>`);
  $('#afOk').onclick = async () => {
    const v = Object.fromEntries(new FormData($('#af')));
    const body = { ...v, customer_id: a.customer_id || (v.customer_id ? +v.customer_id : null), due_at: v.due_at ? toTs(v.due_at) + 17 * 3600 : null, assignee_id: v.assignee_id ? +v.assignee_id : null };
    try { await api(M + '/activities', { method: 'POST', body }); closeModal(); toast('Đã lưu', 'ok'); after?.(); } catch (e) { fail(e); }
  };
}

// ================================================================= BÁO CÁO QUẢNG CÁO
PAGES['bao-cao'] = async function report(sel) {
  setHead('Báo cáo hiển thị quảng cáo');
  const [custs, cts] = await Promise.all([api(M + '/customers?kind=advertiser'), api(M + '/contracts')]);
  const today = Math.floor(Date.now() / 1000);
  $('#page').innerHTML = `<div class="card"><div class="bd"><div class="toolbar">
    <select class="in" id="rs" style="min-width:260px"><option value="">Tất cả quảng cáo</option><optgroup label="Theo khách hàng">${custs.items.map(c => `<option value="c${c.id}">${esc(c.name)}</option>`).join('')}</optgroup><optgroup label="Theo hợp đồng">${cts.items.filter(k => (k.ad_ids || []).length).map(k => `<option value="k${k.id}">${esc(k.code)} · ${esc(k.customer_name)}</option>`).join('')}</optgroup></select>
    <input class="in" type="date" id="rf" value="${toInput(today - 29 * 86400)}"><input class="in" type="date" id="rt" value="${toInput(today)}"><span class="grow"></span><button class="btn sec sm" id="rx">${icon('download', 16)} Tải CSV gửi khách hàng</button></div></div></div><div id="rbody"></div>`;
  if (sel) $('#rs').value = sel;
  const params = () => { const v = $('#rs').value, p = new URLSearchParams({ from: toTs($('#rf').value), to: toTs($('#rt').value) + 86400 }); if (v[0] === 'c') p.set('customer', v.slice(1)); if (v[0] === 'k') p.set('contract', v.slice(1)); return p; };
  const load = async () => {
    const r = await api(M + '/report?' + params()); setLive(true, `${fmtN(r.total)} lượt hiển thị`);
    $('#rbody').innerHTML = `<div class="grid g3">${kpi('Tổng lượt hiển thị', fmtN(r.total), r.title, 'ad')}${kpi('Trung bình / ngày', fmtN(r.total / Math.max(1, r.days.length)), `${r.days.length} ngày`, 'chart')}${kpi('Số màn hình phát', fmtN(r.devices.length), r.devices[0] ? 'Nhiều nhất: ' + esc(r.devices[0].name || r.devices[0].code) : '—', 'device')}</div>
      <div class="card"><div class="hd"><h3>Lượt hiển thị theo ngày</h3></div><div class="bd">${barChart(r.days, { key: 'n', label: 'Lượt hiển thị', color: 'var(--s2)' })}</div></div>
      <div class="grid g2"><div class="card"><div class="hd"><h3>Theo màn hình</h3></div><div class="bd">${hbars(r.devices, { label: x => x.name ? `${x.name} (${x.code})` : x.code })}</div></div>
      <div class="card"><div class="hd"><h3>Theo quảng cáo</h3></div><div class="bd">${hbars(r.ads, { label: x => x.title, color: 'var(--s2)' })}</div></div></div>`;
  };
  $('#rs').onchange = $('#rf').onchange = $('#rt').onchange = () => load().catch(fail);
  $('#rx').onclick = async () => { try { const p = params(); p.set('format', 'csv'); const r = await api(M + '/report?' + p, { raw: true }); saveText((r.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/)?.[1] || 'bao-cao.csv', await r.text(), 'text/csv'); } catch (e) { fail(e); } };
  await load();
};

// ================================================================= DUYỆT NỘI DUNG (dùng API quản trị sẵn có)
PAGES.duyet = async function approvals() {
  setHead('Duyệt nội dung xanh24.com', `<a class="btn sec sm" href="/admin/#/approvals" target="_blank" rel="noopener">${icon('link', 16)} Mở trong Dashboard</a>`);
  const [revs, ads] = await Promise.all([api('/api/admin/revisions?status=pending'), api('/api/admin/ads')]);
  const pAds = ads.items.filter(a => a.status === 'pending');
  const canP = can('poi.approve'), canA = can('ads.publish');
  $('#page').innerHTML = `${!canP && !canA ? '<div class="note warn">Tài khoản Co-worker chỉ xem được danh sách; Admin S1 trở lên mới duyệt được.</div>' : ''}
  <div class="grid g2"><div class="card"><div class="hd"><h3>Địa điểm chờ duyệt (${revs.items.length})</h3></div><div class="bd"><div class="list">${revs.items.length ? revs.items.map(r => `<div class="li">${icon('pin', 18)}<span class="grow"><div class="t1">${esc(r.data?.name || r.poi_name || '(không tên)')}</div><div class="t2">${esc({ create: 'Thêm mới', update: 'Sửa', delete: 'Xoá', hide: 'Ẩn', publish: 'Công khai' }[r.action] || r.action)} · ${esc(r.submitted_by_name || r.created_by_name || '')} · ${fmtTime(r.submitted_at || r.created_at)}</div></span>${canP ? `<button class="btn ok sm" data-ra="approve" data-id="${r.id}">${icon('check', 14)} Duyệt</button><button class="btn sec sm" data-ra="reject" data-id="${r.id}">Từ chối</button>` : ''}</div>`).join('') : `<div class="empty">${icon('check', 28)}Không có địa điểm chờ duyệt</div>`}</div></div></div>
  <div class="card"><div class="hd"><h3>Quảng cáo chờ duyệt (${pAds.length})</h3></div><div class="bd"><div class="list">${pAds.length ? pAds.map(a => `<div class="li">${a.media_type === 'image' && a.media_url ? `<img src="${esc(a.media_url)}" alt="" style="width:56px;height:40px;object-fit:cover;border-radius:8px">` : icon('ad', 18)}<span class="grow"><div class="t1">${esc(a.title)}</div><div class="t2">${esc(a.media_type)} · ${a.duration_sec || 10}s${(a.target_devices || []).length ? ' · ' + a.target_devices.length + ' màn hình' : ' · mọi màn hình'}</div></span>${a.media_url ? `<a class="btn ghost sm" href="${esc(a.media_url)}" target="_blank" rel="noopener">${icon('eye', 14)}</a>` : ''}${canA ? `<button class="btn ok sm" data-aa="approve" data-id="${a.id}">${icon('check', 14)} Duyệt</button><button class="btn sec sm" data-aa="reject" data-id="${a.id}">Từ chối</button>` : ''}</div>`).join('') : `<div class="empty">${icon('check', 28)}Không có quảng cáo chờ duyệt</div>`}</div></div></div></div>`;
  setLive(true, `${revs.items.length + pAds.length} mục chờ duyệt`);
  $$('[data-ra]').forEach(b => b.onclick = async () => {
    let note = '';
    if (b.dataset.ra === 'reject') { note = await confirmBox('Từ chối địa điểm', 'Nhập lý do để cộng tác viên chỉnh sửa:', { okText: 'Từ chối', danger: true, input: 'Lý do từ chối' }); if (!note) return; }
    try { await api(`/api/admin/revisions/${b.dataset.id}/${b.dataset.ra}`, { method: 'POST', body: { note } }); toast(b.dataset.ra === 'approve' ? 'Đã duyệt — hiển thị trên xanh24.com' : 'Đã từ chối', 'ok'); C.lastOverview = null; go(); } catch (e) { fail(e); }
  });
  $$('[data-aa]').forEach(b => b.onclick = async () => { try { await api(`/api/admin/ads/${b.dataset.id}/${b.dataset.aa}`, { method: 'POST', body: {} }); toast(b.dataset.aa === 'approve' ? 'Đã duyệt quảng cáo — kiosk sẽ phát ở lần cập nhật tới' : 'Đã từ chối', 'ok'); C.lastOverview = null; go(); } catch (e) { fail(e); } });
};

// ---------------------------------------------------------------- tệp tải về
function csvLine(r) { return r.map(v => { const s = String(v ?? ''); return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; }).join(','); }
function saveCSV(name, rows) { saveText(name, '﻿' + rows.map(csvLine).join('\r\n'), 'text/csv'); }
function saveText(name, text, mime) {
  if (BRIDGE?.saveFile) { const r = BRIDGE.saveFile(name, text); toast(r || 'Đã lưu ' + name, 'ok'); return; }
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: mime + ';charset=utf-8' })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

// ---------------------------------------------------------------- khởi động
async function boot() {
  try {
    if (!C.user) C.user = (await api('/api/auth/me')).user;
    if (!C.user.permissions?.includes('crm.read')) { logout('Máy chủ chưa cài module CRM (cần xanh24.com bản 1.4.0 trở lên).'); return; }
    C.meta = await api(M + '/meta');
  } catch (e) { if (C.token) renderLogin(e.message); return; }
  renderShell(); go();
}
if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost')) navigator.serviceWorker.register('/crm/sw.js', { scope: '/crm/' }).catch(() => { });
window.X24CRMRefresh = () => go(); // ứng dụng Android gọi khi mở lại
if (C.token) boot(); else renderLogin();
