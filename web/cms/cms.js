import { icon } from '/js/icons.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const fmt = value => new Intl.NumberFormat('vi-VN').format(value || 0);
const date = value => value ? new Date(value * 1000).toLocaleString('vi-VN') : '—';
const roleName = { S0: 'Quản trị hệ thống', AREA: 'Nhân viên quản lí', CONTENT: 'Quản trị nội dung', REVIEW: 'Kiểm duyệt đăng kí', OWNER: 'Tài khoản kiosk', USER: 'Người dùng' };
const statusName = { draft: 'Bản nháp', pending: 'Chờ duyệt', approved: 'Đã duyệt', rejected: 'Bị từ chối', paid: 'Đã thanh toán', cancelled: 'Đã hủy' };
const portal = location.pathname === '/hrm/login' || location.pathname === '/dashboard/admin' ? 'hrm' : 'cms';
const loginPath = portal === 'hrm' ? '/hrm/login' : '/cms/login';
const loginPage = location.pathname.endsWith('/login');
const portalSections = portal === 'hrm' ? [['admin', 'Quản trị viên'], ['manager', 'Nhân viên quản lí'], ['review', 'Kiểm duyệt đăng kí']] : [['user', 'Người dùng'], ['kiosk', 'Tài khoản kiosk']];
const sectionKey = `x24_cms_section_${portal}`;
const savedSection = sessionStorage.getItem(sectionKey);
const state = { token: localStorage.getItem('x24_cms_token'), user: null, wards: [], registrationWards: [], plans: [], categories: [], section: portalSections.some(([key]) => key === savedSection) ? savedSection : portalSections[0][0], registering: false, partnerRegistering: false, partnerOptions: null, partnerSubmittedId: null, accountType: 'all' };
const dashboardPath = userRole => userRole === 'USER' ? '/dashboard/user' : userRole === 'OWNER' ? '/dashboard/kiosk' : '/dashboard/admin';
// Maps for Life pages send people to the login page with ?next=/m4l/…; only same-site /m4l paths are honoured (no open redirect).
const m4lNext = () => { const next = loginPage ? new URLSearchParams(location.search).get('next') || '' : ''; return /^\/m4l(\/[A-Za-z0-9_\-/]*)?$/.test(next) ? next : ''; };
// Coming from M4L, preselect the tab that matches the page (partner pages → kiosk account, the rest → user) instead of the last tab used.
if (portal === 'cms' && m4lNext()) state.section = /^\/m4l\/(partner|v\/)/.test(m4lNext()) ? 'kiosk' : 'user';
const loginPathForRole = userRole => ['USER', 'OWNER'].includes(userRole) ? '/cms/login' : '/hrm/login';
const role = (...names) => names.includes(state.user?.role);
const cell = (label, value) => `<div class="cms-card-row"><span class="cms-muted">${esc(label)}</span><b>${esc(value)}</b></div>`;

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body && !(options.body instanceof FormData)) { headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); }
  const response = await fetch(path, { ...options, headers });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Lỗi ${response.status}`);
  return result;
}

function toast(message, kind = '') {
  const element = document.createElement('div'); element.className = `toastm ${kind}`;
  element.textContent = message; $('#toasts').append(element); setTimeout(() => element.remove(), 4000);
}
function fail(error) { toast(error.message || String(error), 'err'); }
function modal(title, body, wide = false) {
  $('#modalCard').className = `modal-card${wide ? ' wide' : ''}`;
  $('#modalCard').innerHTML = `<div class="mh"><h3>${esc(title)}</h3><button class="btn sec icon" data-close aria-label="Đóng">×</button></div><div class="mb">${body}</div>`;
  $('#modal').hidden = false;
}
function closeModal() { $('#modal').hidden = true; $('#modalCard').innerHTML = ''; }
$('#modal').addEventListener('click', e => { if (e.target.closest('[data-close]')) closeModal(); });
function field(label, id, value = '', type = 'text', required = false) {
  return `<div class="field"><label for="${id}">${label}</label><input class="in" id="${id}" type="${type}" ${type === 'number' ? 'step="any"' : ''} value="${esc(value)}" ${required ? 'required' : ''}></div>`;
}
function option(value, label, selected) { return `<option value="${esc(value)}"${String(value) === String(selected) ? ' selected' : ''}>${esc(label)}</option>`; }
function genderOptions(selected = '') { return '<option value="">Chọn giới tính</option>' + [['male', 'Nam'], ['female', 'Nữ'], ['undisclosed', 'Không tiết lộ']].map(([value, label]) => option(value, label, selected)).join(''); }
function birthDateFields(prefix, birthDate = '') {
  const [year = '', month = '', day = ''] = /^\d{4}-\d{2}-\d{2}$/.test(birthDate) ? birthDate.split('-') : [];
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 1899 }, (_, index) => currentYear - index);
  const dayCount = month ? new Date(Number(year) || 2000, Number(month), 0).getDate() : 0;
  return `<fieldset class="cms-birth-date"><legend>Ngày sinh</legend><div class="row3">
    <div class="field"><label for="${prefix}Year">Năm</label><select class="in" id="${prefix}Year" required><option value="">Chọn năm</option>${years.map(value => option(value, value, year)).join('')}</select></div>
    <div class="field"><label for="${prefix}Month">Tháng</label><select class="in" id="${prefix}Month" required><option value="">Chọn tháng</option>${Array.from({ length: 12 }, (_, index) => option(index + 1, index + 1, Number(month))).join('')}</select></div>
    <div class="field"><label for="${prefix}Day">Ngày</label><select class="in" id="${prefix}Day" required ${month ? '' : 'disabled'}><option value="">Chọn ngày</option>${Array.from({ length: dayCount }, (_, index) => option(index + 1, index + 1, Number(day))).join('')}</select></div>
  </div></fieldset>`;
}
function bindBirthDate(prefix) {
  const year = $(`#${prefix}Year`), month = $(`#${prefix}Month`), day = $(`#${prefix}Day`);
  const updateDays = () => {
    const selected = day.value;
    const count = month.value ? new Date(Number(year.value) || 2000, Number(month.value), 0).getDate() : 0;
    day.innerHTML = '<option value="">Chọn ngày</option>' + Array.from({ length: count }, (_, index) => option(index + 1, index + 1, selected)).join('');
    day.disabled = !month.value;
  };
  year.addEventListener('change', updateDays);
  month.addEventListener('change', updateDays);
}
function birthDateValue(prefix) {
  const year = $(`#${prefix}Year`).value, month = $(`#${prefix}Month`).value, day = $(`#${prefix}Day`).value;
  if (!year || !month || !day) throw new Error('Cần chọn đầy đủ năm, tháng và ngày sinh');
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
}
function wardOptions(selected = '', all = false) { return (all ? '<option value="">Tất cả khu vực</option>' : '') + state.wards.map(w => option(w.slug, w.name, selected)).join(''); }
function sectionTitle(text, actions = '') { $('#pgTitle').textContent = text; $('#pgActions').innerHTML = actions; document.title = `${text} · CMS Xanh24`; }
function badge(text, kind = '') { return `<span class="cms-status ${kind}">${esc(text)}</span>`; }
function empty(text) { return `<div class="cms-empty">${esc(text)}</div>`; }

async function openPartnerRegistration() {
  try {
    state.partnerOptions ||= await api('/api/cms/partner-registration/options');
    state.section = 'kiosk';
    state.registering = false;
    state.partnerRegistering = true;
    state.partnerSubmittedId = null;
    renderLogin();
  } catch (error) { fail(error); }
}

function renderPartnerRegistration() {
  document.title = 'Đăng ký làm đối tác · Xanh24';
  const options = state.partnerOptions || { categories: [], wards: [] };
  const weekdays = [['mon', 'Thứ 2'], ['tue', 'Thứ 3'], ['wed', 'Thứ 4'], ['thu', 'Thứ 5'], ['fri', 'Thứ 6'], ['sat', 'Thứ 7'], ['sun', 'Chủ nhật']];
  $('#root').innerHTML = `<div class="login"><div class="login-art"><img class="logo" src="/assets/logo.png" alt="Xanh24">
    <div><h1>Đăng ký thương hiệu của bạn trên bản đồ</h1><p>Thông tin đăng ký sẽ được gửi đến quản lý khu vực phụ trách để xem xét.</p>
    <ul><li>${icon('doc', 20)} Gửi thông tin và giấy tờ liên quan</li><li>${icon('pin', 20)} Xác định vị trí ghim sau khi duyệt</li><li>${icon('check', 20)} Nhận kết quả qua email</li></ul></div>
    <small>Xanh24 · Maps for Life</small></div><div class="login-form partner-login-form"><div class="login-card partner-card">
    <h2>Đăng ký làm đối tác</h2>
    ${state.partnerSubmittedId ? `<div class="note info cms-section"><b>Đã gửi hồ sơ #${state.partnerSubmittedId}.</b><p>Quản lý khu vực sẽ tiếp nhận và xem xét thông tin đăng ký của bạn.</p></div>` : `
    <p class="cms-login-note">Điền thông tin thương hiệu và chọn khu vực có người quản lý phụ trách.</p>
    <form id="partnerForm" class="cms-form">
      ${field('Họ tên người đại diện đăng ký', 'partnerName', '', 'text', true)}
      <div class="row2">${field('Email', 'partnerEmail', '', 'email', true)}${field('Số điện thoại', 'partnerPhone', '', 'tel', true)}</div>
      <div class="field"><label for="partnerRole">Vai trò của người đại diện</label><select class="in" id="partnerRole" name="representative_role" required>
        <option value="">Chọn vai trò</option><option value="owner">Chủ sở hữu</option><option value="legal_representative">Người đại diện pháp luật</option><option value="manager">Quản lý cơ sở</option><option value="authorized_staff">Nhân viên được ủy quyền</option><option value="other">Khác</option></select></div>
      ${field('Tên thương hiệu', 'partnerBrand', '', 'text', true)}
      <div class="row2"><div class="field"><label for="partnerCategory">Danh mục</label><select class="in" id="partnerCategory" name="category" required><option value="">Chọn danh mục</option>${options.categories.map(item => option(item.id, item.name)).join('')}</select></div>
        <div class="field"><label for="partnerWard">Phường / khu vực</label><select class="in" id="partnerWard" name="ward_slug" required><option value="">Chọn khu vực</option>${options.wards.map(item => option(item.slug, item.name)).join('')}</select></div></div>
      <div class="field"><label for="partnerAddress">Vị trí đầy đủ</label><textarea class="in" id="partnerAddress" name="address" rows="2" placeholder="Số nhà, đường, phường, thành phố" required></textarea></div>
      <div class="field"><label for="partnerPin">Vị trí ghim trên bản đồ (nếu có)</label><input class="in" id="partnerPin" placeholder="Quản lý khu vực sẽ xác định sau khi duyệt" disabled><small class="cms-help">Chức năng chọn ghim sẽ được bổ sung sau.</small></div>
      <div class="row3 partner-hours"><div class="field"><label for="partnerOpeningDay">Ngày mở cửa</label><select class="in" id="partnerOpeningDay" name="opening_days" required><option value="">Chọn ngày</option>${weekdays.map(([value, label]) => option(value, label)).join('')}</select></div>
        ${field('Giờ mở cửa', 'partnerOpening', '', 'time', true)}${field('Giờ đóng cửa', 'partnerClosing', '', 'time', true)}</div>
      <div class="field"><label for="partnerDocuments">Giấy tờ liên quan</label><input class="in partner-files" id="partnerDocuments" name="documents" type="file" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.webp" multiple required><small class="cms-help">Tối đa 8 tệp; mỗi tệp không quá 10 MB. Hỗ trợ PDF, Word và ảnh.</small></div>
      ${options.wards.length ? '' : '<p class="note warn">Chưa có quản lý khu vực nào được phân công. Vui lòng thử lại sau.</p>'}
      <button class="btn pri" style="width:100%" ${options.wards.length ? '' : 'disabled'}>Gửi hồ sơ đăng ký</button>
    </form>`}
    <p class="cms-register-link"><button type="button" class="cms-auth-link" id="backPartnerLogin">Quay lại đăng nhập tài khoản kiosk</button></p>
    <p class="login-foot"><a href="/">Mở bản đồ công khai</a></p></div></div></div>`;
  $('#backPartnerLogin').onclick = () => { state.partnerRegistering = false; state.partnerSubmittedId = null; history.replaceState(null, '', '/cms/login'); renderLogin(); };
  $('#partnerForm')?.addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const files = $('#partnerDocuments').files;
    if (!files.length || files.length > 8 || [...files].some(file => file.size > 10 * 1024 * 1024)) {
      toast('Chọn từ 1 đến 8 giấy tờ, mỗi tệp không quá 10 MB', 'err'); return;
    }
    const payload = new FormData(form);
    payload.set('owner_name', $('#partnerName').value);
    payload.set('email', $('#partnerEmail').value);
    payload.set('phone', $('#partnerPhone').value);
    payload.set('business_name', $('#partnerBrand').value);
    payload.set('opening_time', $('#partnerOpening').value);
    payload.set('closing_time', $('#partnerClosing').value);
    const submit = $('button[type="submit"], button.btn.pri', form);
    submit.disabled = true;
    try {
      const result = await api('/api/cms/partner-registration', { method: 'POST', body: payload });
      state.partnerSubmittedId = result.id;
      renderPartnerRegistration();
    } catch (error) { fail(error); submit.disabled = false; }
  });
}

function renderLogin(message = '') {
  if (state.partnerRegistering) { renderPartnerRegistration(); return; }
  const registering = portal === 'cms' && state.registering;
  document.title = `${registering ? 'Đăng ký' : 'Đăng nhập'} · Xanh24`;
  $('#root').innerHTML = `<div class="login"><div class="login-art"><img class="logo" src="/assets/logo.png" alt="Xanh24">
    <div><h1>Quản lý ghim, nội dung và kiosk trên bản đồ</h1><p>Hệ thống CMS Xanh24 Maps for Life.</p>
    <ul><li>${icon('pin', 20)} Quản lý ghim theo khu vực</li><li>${icon('check', 20)} Duyệt nội dung trước khi hiển thị</li><li>${icon('device', 20)} Theo dõi kiosk và đơn hàng demo</li></ul></div>
    <small>Xanh24 · Maps for Life</small></div><div class="login-form"><form class="login-card" id="loginForm">
    <h2>${registering ? 'Đăng ký người dùng' : portal === 'hrm' ? 'Đăng nhập nhân sự' : 'Đăng nhập CMS'}</h2>
    ${registering ? '<p class="cms-login-note">Tạo tài khoản cá nhân chưa gắn ghim.</p>' : `<div class="login-switch ${portal}">${portalSections.map(([key, label]) => `<button type="button" data-section="${key}" class="${state.section === key ? 'on' : ''}">${label}</button>`).join('')}</div>
    <p class="cms-login-note">${state.section === 'user' ? 'Dành cho người dùng cá nhân, chưa gắn ghim.' : state.section === 'kiosk' ? 'Dành cho người mua ghim để quản lý nội dung ghim của mình.' : state.section === 'manager' ? 'Dành cho người quản lý khu vực được phân công.' : state.section === 'review' ? 'Dành cho nhân viên kiểm duyệt hồ sơ đăng kí theo phường.' : 'Hệ thống tự xác định quản trị hệ thống hoặc quản trị nội dung.'}</p>`}
    ${message ? `<div class="note warn">${esc(message)}</div>` : ''}
    ${registering ? `${field('Họ tên', 'registerName', '', 'text', true)}
      ${birthDateFields('register')}
      <div class="field"><label for="registerGender">Giới tính</label><select class="in" id="registerGender" required>${genderOptions()}</select></div>
      ${field('Email', 'registerEmail', '', 'email', true)}${field('Số điện thoại', 'registerPhone', '', 'tel', true)}` : ''}
    ${field('Tên đăng nhập', 'loginName', '', 'text', true)}${field('Mật khẩu', 'loginPassword', '', 'password', true)}
    ${registering ? field('Nhập lại mật khẩu', 'registerConfirm', '', 'password', true) : ''}
    <button class="btn pri" style="width:100%">${registering ? 'Tạo tài khoản' : 'Đăng nhập'}</button>
    ${portal === 'cms' && state.section === 'user' ? `<p class="cms-register-link"><button type="button" class="cms-auth-link" id="toggleRegister">${registering ? 'Đã có tài khoản? Đăng nhập' : 'Chưa có tài khoản? Đăng ký'}</button></p>` : ''}
    ${!registering && state.section === 'kiosk' ? '<p class="cms-register-link"><button type="button" class="cms-auth-link" id="openPartnerRegister">Đăng ký làm đối tác</button></p>' : ''}
    <p class="login-foot"><a href="/">Mở bản đồ công khai</a></p></form></div></div>`;
  $$('[data-section]').forEach(button => button.onclick = () => { state.section = button.dataset.section; state.registering = false; sessionStorage.setItem(sectionKey, state.section); renderLogin(); });
  $('#toggleRegister')?.addEventListener('click', () => { state.registering = !state.registering; renderLogin(); });
  $('#openPartnerRegister')?.addEventListener('click', openPartnerRegistration);
  if (registering) bindBirthDate('register');
  $('#loginForm').onsubmit = async event => {
    event.preventDefault();
    try {
      let result;
      if (registering) {
        if ($('#loginPassword').value !== $('#registerConfirm').value) throw new Error('Mật khẩu nhập lại chưa khớp');
        result = await api('/api/cms/register', { method: 'POST', body: { full_name: $('#registerName').value,
          birth_date: birthDateValue('register'), gender: $('#registerGender').value, email: $('#registerEmail').value,
          phone: $('#registerPhone').value, username: $('#loginName').value, password: $('#loginPassword').value } });
      } else {
        result = await api('/api/cms/login', { method: 'POST', body: { section: state.section, username: $('#loginName').value, password: $('#loginPassword').value } });
      }
      state.token = result.token; state.user = result.user; localStorage.setItem('x24_cms_token', state.token);
      location.assign(m4lNext() || dashboardPath(state.user.role));
    } catch (error) { renderLogin(error.message); }
  };
}

function navigation() {
  const items = [['dashboard', 'Tổng quan', 'chart']];
  if (role('USER')) items.push(['profile', 'Hồ sơ cá nhân', 'user']);
  if (role('S0', 'AREA')) items.push(['accounts', 'Tài khoản', 'user']);
  if (role('S0', 'REVIEW', 'AREA')) items.push(['applications', role('AREA') ? 'Hồ sơ đối tác' : 'Đăng kí ghim', 'inbox']);
  if (role('S0', 'AREA', 'CONTENT', 'OWNER')) items.push(['pins', role('OWNER') ? 'Ghim của tôi' : 'Ghim', 'pin']);
  if (role('S0', 'CONTENT', 'OWNER')) items.push(['content', role('OWNER') ? 'Nội dung của tôi' : 'Duyệt nội dung', 'check']);
  if (role('S0', 'AREA')) items.push(['kiosks', 'Kiosk', 'device']);
  if (role('S0', 'AREA', 'OWNER')) items.push(['plans', 'Gói', 'grid'], ['orders', 'Đơn hàng', 'inbox'], ['payments', 'Thanh toán', 'history']);
  return items;
}
function renderShell() {
  const user = state.user;
  $('#root').innerHTML = `<div class="shell"><aside class="side"><a class="side-logo" href="#/dashboard"><img src="/assets/logo.png" alt="Xanh24"><span>CMS<br>Xanh24</span></a>
    <nav class="nav"><h6>Quản lý</h6>${navigation().map(([key, label, glyph]) => `<a href="#/${key}" data-page="${key}">${icon(glyph, 19)} ${label}</a>`).join('')}</nav>
    <div class="me"><span class="av">${esc((user.full_name || user.username)[0].toUpperCase())}</span><span><b>${esc(user.full_name || user.username)}</b><small>${esc(roleName[user.role])}</small></span><button id="logout" title="Đăng xuất">${icon('logout', 18)}</button></div></aside>
    <section class="main"><header class="top"><h1 id="pgTitle"></h1><span class="sp"></span><span id="pgActions"></span><span class="rolepill">${esc(roleName[user.role])}</span></header>
    <div class="page" id="page"></div><div class="foot">Xanh24 · Maps for Life</div></section></div>`;
  $('#logout').onclick = () => { const target = loginPathForRole(user.role); state.token = null; state.user = null; localStorage.removeItem('x24_cms_token'); location.assign(target); };
}
async function start() {
  try {
    state.user = (await api('/api/cms/me')).user;
    const destination = dashboardPath(state.user.role);
    if (loginPage && loginPathForRole(state.user.role) !== loginPath) { renderLogin(); return; }
    if (m4lNext()) { location.replace(m4lNext()); return; }
    if (location.pathname !== destination) { location.replace(destination); return; }
    state.wards = role('OWNER', 'REVIEW', 'USER') ? [] : (await api('/api/cms/wards')).items;
    state.registrationWards = role('S0', 'REVIEW') ? (await api('/api/cms/registration-wards')).items : [];
    state.plans = role('REVIEW', 'USER') ? [] : (await api('/api/cms/plans')).items;
    renderShell(); await route();
  } catch (error) { state.token = null; localStorage.removeItem('x24_cms_token'); if (loginPage) renderLogin(error.message); else location.replace(loginPath); }
}
async function route() {
  if (!state.user) return;
  const name = location.hash.replace(/^#\/?/, '') || 'dashboard';
  const pages = { dashboard, profile, accounts, applications, pins, content, kiosks, plans, orders, payments };
  const page = navigation().some(([key]) => key === name) ? name : 'dashboard';
  $$('[data-page]').forEach(link => link.classList.toggle('on', link.dataset.page === page));
  $('#page').innerHTML = empty('Đang tải…');
  try { await pages[page](); } catch (error) { $('#page').innerHTML = empty(error.message); fail(error); }
}
window.addEventListener('hashchange', route);

async function dashboard() {
  sectionTitle('Tổng quan');
  if (role('USER')) {
    $('#page').innerHTML = `<div class="cms-summary"><div class="card"><b>1</b><small>Tài khoản cá nhân</small></div><div class="card"><b>0</b><small>Ghim đã cấp</small></div></div>
      <div class="card card-b"><h3>Xin chào, ${esc(state.user.full_name || state.user.username)}</h3><p class="cms-muted">Bạn đang dùng tài khoản người dùng chưa gắn ghim.</p>
      <div class="cms-inline"><a class="btn sec" href="#/profile">Xem hồ sơ cá nhân</a><a class="btn pri" href="/cms/login?partner=1">Đăng ký làm đối tác</a></div></div>`;
    return;
  }
  if (role('REVIEW')) {
    const rows = (await api('/api/cms/applications')).items;
    $('#page').innerHTML = `<div class="cms-summary"><div class="card"><b>${fmt(rows.filter(row => row.status === 'pending').length)}</b><small>Hồ sơ chờ duyệt</small></div><div class="card"><b>${fmt(rows.length)}</b><small>Hồ sơ trong phường</small></div></div>
      <div class="card card-b"><h3>Xin chào, ${esc(state.user.full_name || state.user.username)}</h3><p>Chọn Đăng kí ghim ở thanh bên để xem hồ sơ được phân công.</p></div>`;
    return;
  }
  const paths = role('OWNER') ? ['pins', 'content', 'orders', 'payments'] : role('CONTENT') ? ['pins', 'content'] : ['pins', 'accounts', 'kiosks', 'orders'];
  const results = await Promise.all(paths.map(path => api(`/api/cms/${path}`)));
  const counts = Object.fromEntries(paths.map((path, index) => [path, results[index].items.length]));
  const cards = role('CONTENT') ? [['Ghim trong khu vực', counts.pins], ['Nội dung chờ duyệt', results[1].items.filter(x => x.status === 'pending').length]]
    : role('OWNER') ? [['Ghim được cấp', counts.pins], ['Nội dung đã gửi', counts.content], ['Đơn hàng', counts.orders], ['Thanh toán', counts.payments]]
      : [['Ghim', counts.pins], ['Tài khoản', counts.accounts], ['Kiosk', counts.kiosks], ['Đơn hàng', counts.orders]];
  $('#page').innerHTML = `<div class="cms-summary">${cards.map(([name, value]) => `<div class="card"><b>${fmt(value)}</b><small>${esc(name)}</small></div>`).join('')}</div>
    <div class="card card-b"><h3>Xin chào, ${esc(state.user.full_name || state.user.username)}</h3><p class="cms-muted">${esc(roleName[state.user.role])}${state.user.wards?.length ? ' · ' + state.user.wards.map(slug => (role('REVIEW') ? state.registrationWards : state.wards).find(w => w.slug === slug)?.name || slug).join(', ') : ''}</p>
    <p>Chọn một chức năng ở thanh bên để tiếp tục.</p></div>`;
}


async function profile() {
  sectionTitle('Hồ sơ cá nhân');
  const user = state.user;
  $('#page').innerHTML = `<div class="card card-b cms-profile"><h3>Thông tin tài khoản</h3>
    ${cell('Tên đăng nhập', user.username)}${cell('Vai trò', roleName[user.role])}
    <form id="profileForm" class="cms-form cms-section">
      ${field('Họ tên', 'profileName', user.full_name, 'text', true)}
      ${birthDateFields('profile', user.birth_date || '')}
      <div class="field"><label for="profileGender">Giới tính</label><select class="in" id="profileGender" required>${genderOptions(user.gender)}</select></div>
      ${field('Email', 'profileEmail', user.email, 'email', true)}
      ${field('Số điện thoại', 'profilePhone', user.phone || '', 'tel', true)}
      <h3>Đổi mật khẩu</h3><p class="cms-help">Để trống nếu bạn chưa muốn đổi mật khẩu.</p>
      ${field('Mật khẩu hiện tại', 'profileCurrentPassword', '', 'password')}
      ${field('Mật khẩu mới', 'profileNewPassword', '', 'password')}
      <button class="btn pri" type="submit">Lưu hồ sơ</button></form></div>`;
  bindBirthDate('profile');
  $('#profileForm').onsubmit = async event => {
    event.preventDefault();
    try {
      const result = await api('/api/cms/profile', { method: 'PUT', body: {
        full_name: $('#profileName').value, birth_date: birthDateValue('profile'), gender: $('#profileGender').value,
        email: $('#profileEmail').value, phone: $('#profilePhone').value,
        current_password: $('#profileCurrentPassword').value, new_password: $('#profileNewPassword').value,
      } });
      state.user = result.user;
      renderShell(); await route(); toast('Đã lưu hồ sơ', 'ok');
    } catch (error) { fail(error); }
  };
}

async function applications() {
  const rows = (await api('/api/cms/applications')).items;
  sectionTitle(role('AREA') ? 'Hồ sơ đối tác trong khu vực' : 'Đăng kí ghim doanh nghiệp', role('S0') ? `<button class="btn sec sm" id="syncApplications">${icon('history', 16)} Đồng bộ Google Form</button>` : '');
  $('#page').innerHTML = `<div class="card cms-table"><table class="tbl"><thead><tr><th>Hồ sơ</th><th>Doanh nghiệp</th><th>Gmail</th><th>Phường</th><th>Kết quả</th><th>Email</th><th></th></tr></thead><tbody>
    ${rows.map(item => `<tr><td>#${item.id}<div class="sub">${item.source_id?.startsWith('partner:') ? 'Đối tác' : 'Google Form'} · ${date(item.submitted_at)}</div></td>
      <td><div class="name">${esc(item.business_name || 'Chưa có tên')}</div><div class="sub">${esc(item.owner_name || item.tax_id || '')}</div></td>
      <td>${esc(item.email || 'Chưa có')}</td><td>${esc(applicationWardName(item.ward_slug))}</td>
      <td>${badge(item.status === 'pending' ? 'Chờ duyệt' : item.status === 'approved' ? 'Đã duyệt' : 'Từ chối', item.status)}</td>
      <td>${badge(item.email_status === 'sent' ? 'Đã gửi' : item.email_status === 'failed' ? 'Gửi lỗi' : 'Chưa gửi', item.email_status === 'sent' ? 'live' : 'off')}</td>
      <td><button class="btn sec sm" data-application="${item.id}">Chi tiết</button></td></tr>`).join('') || `<tr><td colspan="7">${empty('Chưa có hồ sơ đăng kí')}</td></tr>`}</tbody></table></div>`;
  $$('[data-application]').forEach(button => button.onclick = () => applicationDetail(rows.find(item => item.id === +button.dataset.application)));
  $('#syncApplications')?.addEventListener('click', async () => {
    try { const result = await api('/api/cms/applications/sync', { method: 'POST' });
      toast(`Đồng bộ xong: ${result.created} hồ sơ mới, ${result.duplicate} hồ sơ đã có`, 'ok'); applications(); } catch (error) { fail(error); }
  });
}

function applicationWardName(slug) {
  return state.registrationWards.find(ward => ward.slug === slug)?.name || state.wards.find(ward => ward.slug === slug)?.name || slug || 'Chưa phân phường';
}

async function applicationDetail(item, draft = {}) {
  const answers = item.answers && typeof item.answers === 'object' ? item.answers : {};
  const partner = item.source_id?.startsWith('partner:');
  const licenseUrl = /^https:\/\/(drive|docs)\.google\.com\//.test(item.license_file || '') ? item.license_file : '';
  const partnerRoles = { owner: 'Chủ sở hữu', legal_representative: 'Người đại diện pháp luật', manager: 'Quản lý cơ sở', authorized_staff: 'Nhân viên được ủy quyền', other: 'Khác' };
  const dayNames = { mon: 'Thứ 2', tue: 'Thứ 3', wed: 'Thứ 4', thu: 'Thứ 5', fri: 'Thứ 6', sat: 'Thứ 7', sun: 'Chủ nhật' };
  const documents = Array.isArray(answers.documents) ? answers.documents : [];
  const availableCategories = partner || (item.status === 'pending' && item.ward_slug)
    ? (await fetch('/api/public/bootstrap').then(response => response.json())).categories : [];
  const categoryOptions = item.status === 'pending' && item.ward_slug
    ? availableCategories.map(category => option(category.id, category.name, draft.category ?? answers.category)).join('') : '';
  modal(`Hồ sơ đăng kí #${item.id}`, `<div class="cms-application-detail">
    ${cell('Người đăng kí', item.owner_name || '—')}${cell('Doanh nghiệp', item.business_name || '—')}
    ${partner ? cell('Vai trò người đăng kí', partnerRoles[answers.representative_role] || '—') : cell('Mã số thuế', item.tax_id || '—')}${cell('Email', item.email || '—')}${cell('Số điện thoại', item.phone || '—')}
    ${cell('Phường', applicationWardName(item.ward_slug))}${cell('Địa chỉ chi tiết', item.address || '—')}
    ${partner ? `${cell('Danh mục', availableCategories.find(category => category.id === answers.category)?.name || answers.category || '—')}
      ${cell('Ngày mở cửa', (answers.opening_days || []).map(day => dayNames[day] || day).join(', ') || '—')}${cell('Giờ mở cửa', answers.opening_time || '—')}${cell('Giờ đóng cửa', answers.closing_time || '—')}
      <div class="cms-section"><h3>Giấy tờ liên quan</h3>${documents.map((document, index) => `<button type="button" class="btn sec sm cms-document-link" data-application-file="${index}" data-filename="${esc(document.name || `giay-to-${index + 1}`)}">${icon('download', 16)} ${esc(document.name || `Giấy tờ ${index + 1}`)}</button>`).join('') || '<p>Chưa có giấy tờ</p>'}</div>` : ''}
    ${licenseUrl ? `<p><a href="${esc(licenseUrl)}" target="_blank" rel="noopener noreferrer">Xem hồ sơ kinh doanh trên Google Drive</a></p>` : ''}
    ${partner ? '' : `<details><summary>Câu trả lời gốc từ Google Form</summary>${Object.entries(answers).map(([key, value]) => cell(key, Array.isArray(value) ? value.join(', ') : value)).join('') || '<p>Chưa có dữ liệu</p>'}</details>`}
    ${role('S0') && !partner && item.status === 'pending' ? `<div class="field"><label for="applicationWard">Phường phụ trách</label><select class="in" id="applicationWard"><option value="">Chọn phường</option>${state.registrationWards.map(ward => option(ward.slug, ward.name, item.ward_slug)).join('')}</select></div><button class="btn sec sm" id="assignApplication">Lưu phường</button>` : ''}
    ${item.status === 'pending' && item.ward_slug ? `<div class="cms-section"><h3>Kiểm duyệt và cấp tài khoản kiosk</h3>
      <div class="row2">${field('Gmail nhận kết quả', 'applicationEmail', draft.email ?? item.email, 'email', true)}${field('Tên doanh nghiệp', 'applicationName', draft.business_name ?? item.business_name, 'text', true)}</div>
      ${field('Địa chỉ ghim cố định', 'applicationAddress', draft.address ?? item.address, 'text', true)}
      <div class="row3">${field('Vĩ độ', 'applicationLat', draft.lat ?? '', 'number', true)}${field('Kinh độ', 'applicationLng', draft.lng ?? '', 'number', true)}
        <div class="field"><label for="applicationCategory">Danh mục ghim</label><select class="in" id="applicationCategory">${categoryOptions}</select></div></div>
      <div class="field"><label for="applicationNote">Kết quả đối chiếu / lý do từ chối</label><textarea class="in" id="applicationNote" rows="3">${esc(draft.note ?? item.review_note ?? '')}</textarea></div>
      <p class="cms-help">${partner ? 'Đối chiếu giấy tờ và xác định tọa độ ghim trong phường đăng kí trước khi duyệt.' : 'Kiểm tra mã số thuế, hồ sơ kinh doanh và tọa độ ghim trong phường đăng kí trước khi duyệt.'} Ghim chỉ hiển thị sau khi người mua gửi nội dung được duyệt và đăng kí gói.</p>
      <div class="cms-inline cms-application-actions"><button class="btn sec" id="rejectApplication">Từ chối và gửi mail</button><button class="btn pri" id="approveApplication">${partner ? 'Tiến hành tạo tài khoản' : 'Duyệt, tạo tài khoản và gửi Gmail'}</button></div></div>` : ''}
    ${item.status !== 'pending' ? `<div class="cms-section">${cell('Kết quả', item.status === 'approved' ? 'Đã duyệt' : 'Từ chối')}${cell('Thông tin kiểm duyệt', item.review_note || '—')}
      ${item.account_id ? cell('Tài khoản kiosk / ghim', `#${item.account_id} / #${item.poi_id}`) : ''}${cell('Email', item.email_status === 'sent' ? 'Đã gửi' : item.email_status === 'failed' ? `Gửi lỗi: ${item.email_error}` : 'Chưa gửi')}
      ${item.email_status === 'failed' ? '<button class="btn sec sm" id="resendApplication">Gửi lại Gmail</button>' : ''}</div>` : ''}</div>`, true);
  $('#assignApplication')?.addEventListener('click', async () => {
    try { await api(`/api/cms/applications/${item.id}/assign`, { method: 'POST', body: { ward: $('#applicationWard').value } }); closeModal(); toast('Đã phân phường', 'ok'); applications(); } catch (error) { fail(error); }
  });
  $$('[data-application-file]').forEach(button => button.onclick = async () => {
    try {
      const response = await fetch(`/api/cms/applications/${item.id}/files/${button.dataset.applicationFile}`, { headers: { Authorization: `Bearer ${state.token}` } });
      if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || 'Không tải được giấy tờ');
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a'); link.href = url; link.download = button.dataset.filename; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (error) { fail(error); }
  });
  const reviewPayload = action => {
    const payload = { action, email: $('#applicationEmail').value, note: $('#applicationNote').value };
    if (action === 'approve') Object.assign(payload, { business_name: $('#applicationName').value, address: $('#applicationAddress').value,
      lat: $('#applicationLat').value, lng: $('#applicationLng').value, category: $('#applicationCategory').value });
    return payload;
  };
  const review = async payload => {
    try { const result = await api(`/api/cms/applications/${item.id}/review`, { method: 'POST', body: payload }); closeModal();
      toast(result.email_status === 'sent' ? 'Đã lưu kết quả và gửi Gmail' : 'Đã lưu kết quả; gửi Gmail lỗi, cần gửi lại', result.email_status === 'sent' ? 'ok' : 'err'); applications(); } catch (error) { fail(error); }
  };
  $('#approveApplication')?.addEventListener('click', () => {
    if (!partner) { review(reviewPayload('approve')); return; }
    const payload = reviewPayload('approve');
    modal('Tạo tài khoản kiosk', `<form id="partnerAccountForm" class="cms-form">
      <p class="cms-login-note">Tài khoản và mật khẩu sẽ được gửi đến ${esc(payload.email)} sau khi xác nhận.</p>
      ${field('Tên tài khoản', 'partnerAccountUsername', '', 'text', true)}
      ${field('Mật khẩu', 'partnerAccountPassword', '', 'password', true)}
      <p class="cms-help">Tên tài khoản gồm 3–40 ký tự a-z, 0-9, dấu chấm, gạch dưới hoặc gạch ngang. Mật khẩu có ít nhất 8 ký tự, chữ hoa, chữ thường và số.</p>
      <div class="mf partner-account-actions"><button type="button" class="btn sec" id="exitPartnerAccount">Thoát</button><button type="submit" class="btn pri cms-confirm-account" id="confirmPartnerAccount">Xác nhận đăng kí thành công và gửi mail tài khoản mật khẩu</button></div>
    </form>`);
    $('#exitPartnerAccount').onclick = () => applicationDetail(item, payload).catch(fail);
    $('#partnerAccountForm').onsubmit = async event => {
      event.preventDefault();
      payload.username = $('#partnerAccountUsername').value.trim().toLowerCase();
      payload.password = $('#partnerAccountPassword').value;
      const submit = $('#confirmPartnerAccount'); submit.disabled = true;
      try { const result = await api(`/api/cms/applications/${item.id}/review`, { method: 'POST', body: payload }); closeModal();
        toast(result.email_status === 'sent' ? 'Đã tạo tài khoản và gửi mail' : 'Đã tạo tài khoản; gửi mail lỗi, cần gửi lại', result.email_status === 'sent' ? 'ok' : 'err'); applications();
      } catch (error) { fail(error); submit.disabled = false; }
    };
  });
  $('#rejectApplication')?.addEventListener('click', () => review(reviewPayload('reject')));
  $('#resendApplication')?.addEventListener('click', async () => {
    try { const result = await api(`/api/cms/applications/${item.id}/resend`, { method: 'POST' }); closeModal();
      toast(result.email_status === 'sent' ? 'Đã gửi Gmail' : 'Gửi Gmail vẫn lỗi', result.email_status === 'sent' ? 'ok' : 'err'); applications(); } catch (error) { fail(error); }
  });
}

async function accounts() {
  const rows = (await api('/api/cms/accounts')).items;
  const accountTypes = role('AREA') ? [['OWNER', 'Tài khoản kiosk']] : [
    ['all', 'Tất cả tài khoản'], ['AREA', roleName.AREA], ['CONTENT', roleName.CONTENT], ['REVIEW', roleName.REVIEW], ['OWNER', roleName.OWNER], ['USER', roleName.USER],
  ];
  if (!accountTypes.some(([value]) => value === state.accountType)) state.accountType = accountTypes[0][0];
  sectionTitle('Tài khoản', `<button class="btn pri sm" id="newAccount">${icon('plus', 16)} Cấp tài khoản</button>`);
  $('#page').innerHTML = `<div class="toolbar"><label for="accountType">Loại tài khoản</label><select class="in" id="accountType">${accountTypes.map(([value, label]) => option(value, label, state.accountType)).join('')}</select></div>
    <div class="card cms-table"><table class="tbl"><thead id="accountHead"></thead><tbody id="accountRows"></tbody></table></div>`;
  const draw = () => {
    state.accountType = $('#accountType').value;
    const showPin = state.accountType === 'OWNER';
    const filtered = rows.filter(row => state.accountType === 'all' || row.role === state.accountType);
    $('#accountHead').innerHTML = `<tr><th>Tài khoản</th><th>Vai trò</th><th>Khu vực</th>${showPin ? '<th>Ghim</th>' : ''}<th>Trạng thái</th><th></th></tr>`;
    $('#accountRows').innerHTML = filtered.map(row => `<tr><td><div class="name">${esc(row.full_name || row.username)}</div><div class="sub">${esc(row.username)} · ${esc(row.email)}</div></td><td>${esc(roleName[row.role])}</td>
      <td>${esc((row.wards || []).map(slug => (row.role === 'REVIEW' ? state.registrationWards : state.wards).find(w => w.slug === slug)?.name || slug).join(', '))}</td>
      ${showPin ? `<td>${row.pin_id ? `#${row.pin_id}${row.pin_released ? ' (đã deactive)' : ''}` : '—'}</td>` : ''}
      <td>${badge(row.read_only ? 'Chỉ đọc' : row.active ? 'Hoạt động' : 'Đã khóa', row.read_only || !row.active ? 'off' : 'live')}</td>
      <td><button class="btn sec sm" data-edit-account="${row.id}">Chi tiết / sửa</button></td></tr>`).join('') || `<tr><td colspan="${showPin ? 6 : 5}">${empty('Chưa có tài khoản')}</td></tr>`;
    $$('[data-edit-account]').forEach(button => button.onclick = () => accountForm(rows.find(row => row.id === +button.dataset.editAccount)));
  };
  $('#accountType').onchange = draw; draw();
  $('#newAccount').onclick = () => accountForm();
}

async function accountForm(account) {
  const isNew = !account;
  const selectedRole = account?.role || (role('AREA') ? 'OWNER' : 'AREA');
  const inactive = isNew ? (await api('/api/cms/pins')).items.filter(pin => !pin.active && !pin.owner_id) : [];
  const roleSelect = role('AREA') ? '<option value="OWNER">Tài khoản kiosk (người mua ghim)</option>' : ['AREA', 'CONTENT', 'REVIEW', 'OWNER', 'USER'].map(key => option(key, roleName[key], selectedRole)).join('');
  modal(isNew ? 'Cấp tài khoản' : 'Hồ sơ tài khoản', `<form id="accountForm" class="cms-form">
    <div class="row2">${field('Tên đăng nhập', 'aUsername', account?.username || '', 'text', isNew)}${field('Họ tên', 'aName', account?.full_name || '')}</div>
    <div class="row2">${field('Email', 'aEmail', account?.email || '', 'email')}${field('Điện thoại', 'aPhone', account?.phone || '')}</div>
    <div class="row2"><div class="field"><label>Vai trò</label><select class="in" id="aRole" ${isNew ? '' : 'disabled'}>${roleSelect}</select></div>${field(isNew ? 'Mật khẩu' : 'Mật khẩu mới (để trống nếu giữ nguyên)', 'aPassword', '', 'password', isNew)}</div>
    <div id="scopeBox" class="field"><label id="scopeLabel">Khu vực phụ trách</label><select class="in" id="aWards" multiple style="height:115px"></select></div>
    <div id="ownerBox" hidden><div class="field"><label>Ghim deactive có thể cấp lại</label><select class="in" id="aExistingPin"><option value="">Tạo ghim mới</option>${inactive.map(pin => option(pin.poi_id, `#${pin.poi_id} · ${pin.name} · ${pin.address}`)).join('')}</select></div>
      <div id="newPinFields"><div class="row2">${field('Tên ghim', 'pName')}${field('Địa chỉ cố định', 'pAddress')}</div>
      <div class="row3">${field('Vĩ độ', 'pLat', '', 'number')}${field('Kinh độ', 'pLng', '', 'number')}<div class="field"><label>Danh mục</label><select class="in" id="pCategory"></select></div></div></div>
      <p class="cms-help">Một tài khoản gắn với một ghim suốt vòng đời. Địa chỉ và tọa độ không đổi sau khi cấp.</p></div>
    ${!isNew ? `<label><input type="checkbox" id="aActive" ${account.active ? 'checked' : ''}> Cho phép đăng nhập</label>` : ''}
    <div class="mf"><button type="button" class="btn sec" data-close>Hủy</button><button class="btn pri" type="submit">Lưu</button></div></form>`, true);
  if (!isNew) $('#aUsername').disabled = true;
  if (!isNew && !['OWNER', 'USER'].includes(account.role)) {
    $('#accountForm').insertAdjacentHTML('afterbegin', `<p class="cms-help">Tạo ngày ${date(account.created_at)} · Đăng nhập gần nhất ${date(account.last_login)} · Được phân công ${account.wards?.length || 0} khu vực.</p>`);
  }
  const showRole = () => {
    const kind = $('#aRole').value;
    $('#ownerBox').hidden = kind !== 'OWNER' || !isNew;
    $('#scopeBox').hidden = kind === 'OWNER' || kind === 'USER' || role('AREA');
    $('#scopeLabel').textContent = kind === 'REVIEW' ? 'Phường phụ trách' : 'Khu vực phụ trách';
    const places = kind === 'REVIEW' ? state.registrationWards : state.wards;
    $('#aWards').innerHTML = places.map(place => `<option value="${esc(place.slug)}" ${account?.role === kind && account.wards?.includes(place.slug) ? 'selected' : ''}>${esc(place.name)}</option>`).join('');
  };
  $('#aRole').onchange = showRole; showRole();
  if (isNew) {
    const bootstrap = await fetch('/api/public/bootstrap').then(r => r.json());
    $('#pCategory').innerHTML = bootstrap.categories.map(c => option(c.id, c.name)).join('');
    $('#aExistingPin').onchange = () => $('#newPinFields').hidden = Boolean($('#aExistingPin').value);
  }
  $('#accountForm').onsubmit = async event => {
    event.preventDefault();
    const payload = { full_name: $('#aName').value, email: $('#aEmail').value, phone: $('#aPhone').value };
    if ($('#aPassword').value) payload.password = $('#aPassword').value;
    if (isNew) {
      payload.username = $('#aUsername').value; payload.role = $('#aRole').value;
      if (payload.role === 'OWNER') {
        if ($('#aExistingPin').value) payload.pin_id = +$('#aExistingPin').value;
        else payload.pin = { name: $('#pName').value, address: $('#pAddress').value, lat: $('#pLat').value, lng: $('#pLng').value, category: $('#pCategory').value };
      } else if (payload.role !== 'USER') payload.wards = [...$('#aWards').selectedOptions].map(o => o.value);
    } else { payload.active = $('#aActive').checked; if (!['OWNER', 'USER'].includes(account.role)) payload.wards = [...$('#aWards').selectedOptions].map(o => o.value); }
    try { await api(`/api/cms/accounts${account ? '/' + account.id : ''}`, { method: account ? 'PUT' : 'POST', body: payload }); closeModal(); toast('Đã lưu tài khoản', 'ok'); accounts(); } catch (error) { fail(error); }
  };
}

async function pins() {
  const rows = (await api('/api/cms/pins')).items;
  sectionTitle(role('OWNER') ? 'Ghim của tôi' : 'Danh sách ghim');
  $('#page').innerHTML = `<div class="card cms-table"><table class="tbl"><thead><tr><th>Ghim</th><th>Khu vực</th><th>Người sở hữu</th><th>Gói đến</th><th>Hiển thị</th><th></th></tr></thead><tbody>
    ${rows.map(pin => `<tr><td><div class="name">${esc(pin.name)}</div><div class="sub">#${pin.poi_id} · ${esc(pin.address)}</div></td><td>${esc(state.wards.find(w => w.slug === pin.ward_slug)?.name || pin.ward_slug)}</td>
    <td>${pin.owner_id ? `#${pin.owner_id}` : 'Chưa cấp'}</td><td>${date(pin.expires_at)}</td><td>${badge(pin.live ? 'Đang hiển thị' : pin.active ? 'Đang ẩn' : 'Deactive', pin.live ? 'live' : 'off')}</td>
    <td class="cms-actions">${role('S0', 'AREA') ? `<button class="btn sec sm" data-pin="${pin.poi_id}">${pin.active ? 'Deactive' : 'Active'}</button>` : ''}</td></tr>`).join('')}</tbody></table>${rows.length ? '' : empty('Chưa có ghim')}</div>
    ${role('OWNER') && rows[0]?.active && !rows[0]?.live ? '<p class="note info">Ghim chỉ hiển thị khi nội dung đã được duyệt và gói còn hạn.</p>' : ''}`;
  $$('[data-pin]').forEach(button => button.onclick = async () => {
    const pin = rows.find(item => item.poi_id === +button.dataset.pin);
    if (pin.active && !confirm('Deactive ghim này? Tài khoản hiện tại sẽ chuyển sang chỉ đọc.')) return;
    try { await api(`/api/cms/pins/${pin.poi_id}/active`, { method: 'POST', body: { active: !pin.active } }); toast('Đã cập nhật ghim', 'ok'); pins(); } catch (error) { fail(error); }
  });
}

async function content() {
  const rows = (await api('/api/cms/content')).items;
  if (role('OWNER')) return ownerContent(rows);
  sectionTitle('Duyệt nội dung', '');
  const pending = rows.filter(item => item.status === 'pending');
  $('#page').innerHTML = `<div class="split"><div class="card"><div class="card-h"><h3>Chờ duyệt (${pending.length})</h3></div>
    ${rows.map(item => `<button class="revitem" data-content="${item.id}" style="width:100%;text-align:left;background:none;border:0"><span style="flex:1"><b>${esc(item.data.name || item.current_name)}</b><small>Ghim #${item.poi_id} · ${date(item.submitted_at || item.created_at)}</small></span>${badge(statusName[item.status], item.status)}</button>`).join('') || empty('Chưa có nội dung')}</div>
    <div class="card" id="reviewDetail">${empty('Chọn một nội dung để xem và duyệt')}</div></div>`;
  $$('[data-content]').forEach(button => button.onclick = async () => {
    const item = rows.find(row => row.id === +button.dataset.content);
    const pin = (await api('/api/cms/pins')).items.find(row => row.poi_id === item.poi_id);
    const labels = { name: 'Tên ghim', name_en: 'Tên tiếng Anh', description: 'Mô tả', phone: 'Điện thoại', website: 'Website', hours: 'Giờ mở cửa', images: 'Hình ảnh', vr360: 'VR360', tags: 'Từ khóa' };
    const view = value => esc(typeof value === 'object' ? JSON.stringify(value) : value);
    $('#reviewDetail').innerHTML = `<div class="card-h"><h3>${esc(item.current_name)}</h3>${badge(statusName[item.status], item.status)}</div><div class="card-b"><p>Ghim #${item.poi_id} · ${esc(item.ward_slug)}</p>
      <div class="diff"><div class="dr hd"><div>Trường</div><div>Đang công khai</div><div>Đề xuất</div></div>${Object.entries(item.data).map(([key, value]) => `<div class="dr"><div class="k">${esc(labels[key] || key)}</div><div class="old">${view(pin?.[key])}</div><div class="new">${view(value)}</div></div>`).join('')}</div>
      ${item.review_note ? `<p class="note warn">${esc(item.review_note)}</p>` : ''}</div>
      ${item.status === 'pending' && role('S0', 'CONTENT') ? `<div class="mf"><button class="btn no" id="reject">Từ chối</button><button class="btn ok" id="approve">Duyệt & công khai</button></div>` : ''}`;
    const review = async (action, note = '') => { try { await api(`/api/cms/content/${item.id}/review`, { method: 'POST', body: { action, note } }); toast('Đã xử lý nội dung', 'ok'); content(); } catch (error) { fail(error); } };
    $('#approve')?.addEventListener('click', () => review('approve'));
    $('#reject')?.addEventListener('click', () => { const note = prompt('Nhập lý do từ chối'); if (note) review('reject', note); });
  });
}

async function ownerContent(rows) {
  sectionTitle('Nội dung ghim');
  const pin = (await api('/api/cms/pins')).items[0];
  if (!pin) { $('#page').innerHTML = empty('Tài khoản chưa được cấp ghim'); return; }
  const readOnly = state.user.read_only || !pin.active;
  $('#page').innerHTML = `<div class="grid g2"><div class="card"><div class="card-h"><h3>Ghim #${pin.poi_id}</h3></div><div class="card-b">
    ${cell('Địa chỉ cố định', pin.address)}${cell('Tọa độ cố định', `${pin.lat}, ${pin.lng}`)}${cell('Khu vực', pin.ward_slug)}
    <p>${badge(readOnly ? 'Tài khoản chỉ đọc' : pin.live ? 'Đang hiển thị' : 'Đang ẩn', readOnly || !pin.live ? 'off' : 'live')}</p></div></div>
    <div class="card"><div class="card-h"><h3>Nội dung hiển thị</h3></div><div class="card-b"><form id="contentForm" class="cms-form">
      ${field('Tên ghim', 'cName', pin.name)}${field('Tên tiếng Anh', 'cEnglish', pin.name_en || '')}
      <div class="field"><label>Mô tả</label><textarea class="in" id="cDescription" rows="5">${esc(pin.description || '')}</textarea></div>
      <div class="row2">${field('Điện thoại', 'cPhone', pin.phone || '')}${field('Giờ mở cửa', 'cHours', pin.hours || '')}</div>
      ${field('Website', 'cWebsite', pin.website || '')}${field('Từ khóa', 'cTags', pin.tags || '')}
      <div class="field"><label>Ảnh</label><div id="imageList" class="cms-inline"></div><input class="in" type="file" id="cImage" accept="image/*"><small class="cms-help">Có thể gỡ ảnh và tải ảnh mới lên.</small></div>
      <div class="row2"><div class="field"><label>VR360</label><select class="in" id="cVrType">${[['', 'Không có'], ['pano', 'Ảnh 360°'], ['video', 'Video 360°'], ['embed', 'Link tour nhúng'], ['tour', 'Tour nhiều cảnh']].map(([value, label]) => option(value, label, pin.vr360?.type || '')).join('')}</select></div>
      ${field('Link VR360', 'cVrUrl', pin.vr360?.url || '')}</div>
      <div class="field" id="vrTourBox" hidden><label>Cảnh tour (JSON)</label><textarea class="in" id="cVrScenes" rows="5">${esc(JSON.stringify(pin.vr360?.scenes || [], null, 2))}</textarea></div>
      <div class="field" id="vrFileBox" hidden><label>Tải ảnh/video 360°</label><input class="in" id="cVrFile" type="file" accept="image/*,video/*"></div>
      <div class="cms-inline"><button class="btn sec" type="button" id="saveDraft">Lưu nháp</button><button class="btn pri" type="submit">Gửi duyệt</button></div>
    </form></div></div></div><div class="card cms-section"><div class="card-h"><h3>Lịch sử nội dung</h3></div><div class="card-b">
    ${rows.map(item => `<div class="cms-card-row"><span>#${item.id} · ${date(item.created_at)} · ${esc(Object.keys(item.data).join(', '))}${item.review_note ? `<br><small>${esc(item.review_note)}</small>` : ''}</span>${badge(statusName[item.status], item.status)}${!readOnly && ['draft', 'rejected'].includes(item.status) ? `<button class="btn sec sm" data-resume="${item.id}">Sửa & gửi lại</button>` : ''}</div>`).join('') || 'Chưa có nội dung gửi duyệt'}</div></div>`;
  let images = [...(pin.images || [])];
  const drawImages = () => { $('#imageList').innerHTML = images.map((image, index) => `<div><img class="cms-preview" src="${esc(image.thumb || image.url)}" alt="Ảnh ghim"><br><button class="btn sec sm" type="button" data-remove-image="${index}">Gỡ</button></div>`).join('');
    $$('[data-remove-image]').forEach(button => button.onclick = () => { images.splice(+button.dataset.removeImage, 1); drawImages(); });
  };
  drawImages();
  const updateVr = () => { const type = $('#cVrType').value; $('#vrTourBox').hidden = type !== 'tour'; $('#vrFileBox').hidden = !['pano', 'video'].includes(type); };
  $('#cVrType').onchange = updateVr; updateVr();
  if (readOnly) { $$('#contentForm input, #contentForm textarea, #contentForm button, #contentForm select').forEach(el => el.disabled = true); return; }
  let editing = null;
  $$('[data-resume]').forEach(button => button.onclick = () => {
    editing = rows.find(row => row.id === +button.dataset.resume);
    for (const [key, id] of Object.entries({ name: 'cName', name_en: 'cEnglish', description: 'cDescription', phone: 'cPhone', hours: 'cHours', website: 'cWebsite', tags: 'cTags' })) {
      if (key in editing.data) $(`#${id}`).value = editing.data[key] || '';
    }
    images = [...(editing.data.images || pin.images || [])]; drawImages();
    if ('vr360' in editing.data) {
      $('#cVrType').value = editing.data.vr360?.type || '';
      $('#cVrUrl').value = editing.data.vr360?.url || '';
      $('#cVrScenes').value = JSON.stringify(editing.data.vr360?.scenes || [], null, 2);
      updateVr();
    }
    $('#cName').focus(); toast(`Đang sửa bản #${editing.id}`);
  });
  const save = async submit => {
    try {
      const changes = { name: $('#cName').value, name_en: $('#cEnglish').value, description: $('#cDescription').value, phone: $('#cPhone').value, hours: $('#cHours').value, website: $('#cWebsite').value, tags: $('#cTags').value };
      const image = $('#cImage').files[0];
      if (image) { const form = new FormData(); form.append('file', image); images.push(await api('/api/cms/upload', { method: 'POST', body: form })); }
      changes.images = images;
      const vrType = $('#cVrType').value;
      let vrUrl = $('#cVrUrl').value.trim();
      const vrFile = $('#cVrFile').files[0];
      if (vrFile && ['pano', 'video'].includes(vrType)) { const form = new FormData(); form.append('file', vrFile); form.append('kind', vrType); vrUrl = (await api('/api/cms/upload', { method: 'POST', body: form })).url; }
      if (vrType === 'tour') changes.vr360 = { type: 'tour', scenes: JSON.parse($('#cVrScenes').value) };
      else if (vrType) changes.vr360 = { type: vrType, url: vrUrl };
      else changes.vr360 = null;
      await api(`/api/cms/content${editing ? '/' + editing.id : ''}`, { method: editing ? 'PUT' : 'POST', body: { data: changes, submit } }); toast(submit ? 'Đã gửi duyệt' : 'Đã lưu nháp', 'ok'); content();
    } catch (error) { fail(error); }
  };
  $('#contentForm').onsubmit = e => { e.preventDefault(); save(true); };
  $('#saveDraft').onclick = () => save(false);
}

async function kiosks() {
  const rows = (await api('/api/cms/kiosks')).items;
  sectionTitle('Danh sách kiosk', role('AREA') ? `<button class="btn pri sm" id="newKiosk">${icon('plus', 16)} Thêm kiosk</button>` : '');
  $('#page').innerHTML = `<div class="toolbar"><select class="in" id="kioskWard">${wardOptions('', true)}</select></div>
    <div class="card cms-table"><table class="tbl"><thead><tr><th>Mã</th><th>Tên / địa chỉ</th><th>Khu vực</th><th>Vị trí</th><th>Kết nối</th><th></th></tr></thead><tbody id="kioskRows"></tbody></table></div>`;
  const draw = () => {
    const selected = $('#kioskWard').value;
    const filtered = rows.filter(row => !selected || row.ward_slug === selected);
    $('#kioskRows').innerHTML = filtered.map(row => `<tr><td>${esc(row.code)}</td><td><div class="name">${esc(row.name)}</div><div class="sub">${esc(row.address)}</div></td>
      <td>${esc(state.wards.find(w => w.slug === row.ward_slug)?.name || row.ward_slug)}</td><td>${row.lat}, ${row.lng}</td>
      <td>${badge(row.last_seen && Date.now() / 1000 - row.last_seen < 180 ? 'Trực tuyến' : 'Ngoại tuyến', row.last_seen && Date.now() / 1000 - row.last_seen < 180 ? 'live' : 'off')}</td>
      <td>${role('AREA') ? `<button class="btn sec sm" data-kiosk="${row.id}">Sửa</button>` : ''}</td></tr>`).join('') || `<tr><td colspan="6">${empty('Không có kiosk')}</td></tr>`;
    $$('[data-kiosk]').forEach(button => button.onclick = () => kioskForm(rows.find(row => row.id === +button.dataset.kiosk)));
  };
  $('#kioskWard').onchange = draw; draw();
  $('#newKiosk')?.addEventListener('click', () => kioskForm());
}

function kioskForm(kiosk) {
  modal(kiosk ? 'Sửa kiosk' : 'Thêm kiosk', `<form id="kioskForm" class="cms-form">
    <div class="row2">${field('Mã kiosk', 'kCode', kiosk?.code || '', 'text', !kiosk)}${field('Tên kiosk', 'kName', kiosk?.name || '', 'text', true)}</div>
    <div class="field"><label>Khu vực</label><select class="in" id="kWard">${wardOptions(kiosk?.ward_slug)}</select></div>
    ${field('Địa chỉ lắp đặt', 'kAddress', kiosk?.address || '')}<div class="row2">${field('Vĩ độ', 'kLat', kiosk?.lat || '', 'number')}${field('Kinh độ', 'kLng', kiosk?.lng || '', 'number')}</div>
    ${kiosk ? `<label><input type="checkbox" id="kActive" ${kiosk.active ? 'checked' : ''}> Hoạt động</label>` : ''}
    <div class="mf"><button type="button" class="btn sec" data-close>Hủy</button><button class="btn pri">Lưu</button></div></form>`);
  if (kiosk) $('#kCode').disabled = true;
  $('#kioskForm').onsubmit = async e => {
    e.preventDefault();
    const payload = { name: $('#kName').value, ward_slug: $('#kWard').value, address: $('#kAddress').value, lat: $('#kLat').value || null, lng: $('#kLng').value || null };
    if (!kiosk) payload.code = $('#kCode').value;
    else payload.active = $('#kActive').checked ? 1 : 0;
    try { await api(`/api/cms/kiosks${kiosk ? '/' + kiosk.id : ''}`, { method: kiosk ? 'PUT' : 'POST', body: payload }); closeModal(); toast('Đã lưu kiosk', 'ok'); kiosks(); } catch (error) { fail(error); }
  };
}

async function plans() {
  state.plans = (await api('/api/cms/plans')).items;
  sectionTitle('Gói', role('S0') ? `<button class="btn pri sm" id="newPlan">${icon('plus', 16)} Thêm gói</button>` : '');
  $('#page').innerHTML = `<div class="grid g3">${state.plans.map(plan => `<div class="card"><div class="card-h"><h3>${esc(plan.name)}</h3></div><div class="card-b">
    <strong style="font-size:1.5rem;color:var(--navy)">${fmt(plan.price)} ₫</strong><p>${fmt(plan.duration_days)} ngày</p><p class="cms-muted">${esc(plan.description)}</p>
    ${role('S0') ? `<button class="btn sec sm" data-plan="${plan.id}">Sửa</button>` : ''}</div></div>`).join('')}</div>`;
  $('#newPlan')?.addEventListener('click', () => planForm());
  $$('[data-plan]').forEach(button => button.onclick = () => planForm(state.plans.find(plan => plan.id === +button.dataset.plan)));
}
function planForm(plan) {
  modal(plan ? 'Sửa gói' : 'Thêm gói', `<form id="planForm" class="cms-form">${field('Tên gói', 'planName', plan?.name || '', 'text', true)}
    <div class="row2">${field('Giá (VND)', 'planPrice', plan?.price ?? '', 'number', true)}${field('Thời hạn (ngày)', 'planDays', plan?.duration_days ?? '', 'number', true)}</div>
    <div class="field"><label>Mô tả</label><textarea class="in" id="planDescription">${esc(plan?.description || '')}</textarea></div>
    <div class="mf"><button type="button" class="btn sec" data-close>Hủy</button><button class="btn pri">Lưu</button></div></form>`);
  $('#planForm').onsubmit = async e => { e.preventDefault(); try {
    await api(`/api/cms/plans${plan ? '/' + plan.id : ''}`, { method: plan ? 'PUT' : 'POST', body: { name: $('#planName').value, price: +$('#planPrice').value, duration_days: +$('#planDays').value, description: $('#planDescription').value } });
    closeModal(); toast('Đã lưu gói', 'ok'); plans();
  } catch (error) { fail(error); } };
}

async function orders() {
  const rows = (await api('/api/cms/orders')).items;
  sectionTitle('Đơn hàng', role('OWNER') && !state.user.read_only ? `<button class="btn pri sm" id="newOrder">${icon('plus', 16)} Đăng ký gói</button>` : '');
  $('#page').innerHTML = `<div class="card cms-table"><table class="tbl"><thead><tr><th>Đơn</th><th>Tài khoản</th><th>Ghim</th><th>Gói</th><th>Số tiền</th><th>Trạng thái</th><th></th></tr></thead><tbody>
    ${rows.map(row => `<tr><td>#${row.id}<div class="sub">${date(row.created_at)}</div></td><td>${esc(row.username)}</td><td>#${row.poi_id} · ${esc(row.ward_slug)}</td><td>${esc(row.plan_name)}</td>
      <td>${fmt(row.amount)} ₫</td><td>${badge(statusName[row.status], row.status)}</td><td class="cms-actions">${row.status === 'pending' && ((role('OWNER') && !state.user.read_only) || role('S0')) ? `<button class="btn ok sm" data-pay="${row.id}">Thanh toán demo</button>` : ''}${row.status === 'pending' && role('S0') ? `<button class="btn no sm" data-cancel="${row.id}">Hủy</button>` : ''}</td></tr>`).join('')}</tbody></table>${rows.length ? '' : empty('Chưa có đơn')}</div>`;
  $('#newOrder')?.addEventListener('click', () => { modal('Đăng ký gói demo', `<form id="orderForm" class="cms-form"><div class="field"><label>Gói</label><select class="in" id="orderPlan">${state.plans.map(plan => option(plan.id, `${plan.name} · ${fmt(plan.price)} ₫ · ${plan.duration_days} ngày`)).join('')}</select></div><p class="note info">Đây là thanh toán demo, không chuyển tiền thật.</p><div class="mf"><button type="button" class="btn sec" data-close>Hủy</button><button class="btn pri">Tạo đơn</button></div></form>`);
    $('#orderForm').onsubmit = async e => { e.preventDefault(); try { await api('/api/cms/orders', { method: 'POST', body: { plan_id: +$('#orderPlan').value } }); closeModal(); orders(); } catch (error) { fail(error); } };
  });
  $$('[data-pay]').forEach(button => button.onclick = async () => { if (!confirm('Xác nhận thanh toán demo cho đơn này? Không có tiền thật được chuyển.')) return;
    try { await api(`/api/cms/orders/${button.dataset.pay}/demo-pay`, { method: 'POST', body: {} }); toast('Đã thanh toán demo', 'ok'); orders(); } catch (error) { fail(error); }
  });
  $$('[data-cancel]').forEach(button => button.onclick = async () => { if (!confirm('Hủy đơn chưa thanh toán này?')) return;
    try { await api(`/api/cms/orders/${button.dataset.cancel}/cancel`, { method: 'POST', body: {} }); toast('Đã hủy đơn', 'ok'); orders(); } catch (error) { fail(error); }
  });
}

async function payments() {
  const rows = (await api('/api/cms/payments')).items;
  sectionTitle('Thanh toán demo');
  $('#page').innerHTML = `<div class="card cms-table"><table class="tbl"><thead><tr><th>Giao dịch</th><th>Đơn</th><th>Tài khoản</th><th>Khu vực</th><th>Số tiền</th><th>Thời gian</th></tr></thead><tbody>
    ${rows.map(row => `<tr><td>${esc(row.reference)}</td><td>#${row.order_id}</td><td>${esc(row.username)}</td><td>${esc(row.ward_slug)}</td><td>${fmt(row.amount)} ₫</td><td>${date(row.paid_at)}</td></tr>`).join('')}</tbody></table>${rows.length ? '' : empty('Chưa có thanh toán')}</div>`;
}

if (portal === 'cms' && loginPage && new URLSearchParams(location.search).get('partner') === '1') {
  state.section = 'kiosk'; renderLogin(); openPartnerRegistration();
} else if (state.token) start(); else if (loginPage) renderLogin(); else location.replace(loginPath);
