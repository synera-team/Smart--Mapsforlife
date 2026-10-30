import { icon } from '/js/icons.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const norm = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[đĐ]/g, 'd').toLowerCase();
const state = {
  token: localStorage.getItem('x24_cms_token'), user: null, categories: [], wards: [], pois: [],
  saved: new Set(), geo: null, query: '', category: '', ward: '', detail: null,
};
let toastTimer;

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token && (path.startsWith('/api/user/') || path.startsWith('/api/cms/'))) headers.Authorization = `Bearer ${state.token}`;
  const init = { ...options, headers };
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, init);
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(result.error || `Lỗi ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return result;
}

function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { element.hidden = true; }, 4000);
}

function category(id) { return state.categories.find(item => item.id === id) || {}; }
function wardName(slug) { return state.wards.find(item => item.slug === slug)?.name || ''; }
function color(id) { const value = category(id).color || ''; return /^#[0-9a-fA-F]{6}$/.test(value) ? value : '#287ab0'; }
function imageUrl(place) {
  const image = place.images?.[0];
  const path = image?.thumb || image?.url || '';
  return typeof path === 'string' && (/^\/uploads\//.test(path) || /^https:\/\//.test(path)) ? path : '';
}
function safeLink(value) {
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : '';
  } catch { return ''; }
}
function distance(place) {
  if (!state.geo || place.lat == null || place.lng == null || !Number.isFinite(Number(place.lat)) || !Number.isFinite(Number(place.lng))) return null;
  const r = Math.PI / 180;
  const dLat = (place.lat - state.geo.lat) * r;
  const dLng = (place.lng - state.geo.lng) * r;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(state.geo.lat * r) * Math.cos(place.lat * r) * Math.sin(dLng / 2) ** 2;
  return 6371000 * 2 * Math.asin(Math.sqrt(a));
}
function distanceLabel(place) {
  const meters = distance(place);
  return meters === null ? '' : meters < 1000 ? `${Math.round(meters / 10) * 10} m` : `${(meters / 1000).toFixed(1).replace('.', ',')} km`;
}
function mapUrl(place, directions = false) {
  return `/?mode=web&poi=${encodeURIComponent(place.id)}${directions ? '&dir=foot&locate=1' : ''}`;
}
function media(place, detail = false) {
  const picture = imageUrl(place);
  const style = `--accent:${color(place.category)}`;
  return `<div class="${detail ? 'detail-media' : 'place-media'}" style="${style}">${picture ? `<img src="${esc(picture)}" alt="${esc(place.name)}" loading="lazy">` : icon(category(place.category).icon || 'pin', detail ? 85 : 58)}${detail ? '' : `<button type="button" class="place-media-button" data-action="open" data-id="${place.id}" aria-label="Xem ${esc(place.name)}"></button><button type="button" class="save-button ${state.saved.has(place.id) ? 'saved' : ''}" data-action="save" data-id="${place.id}" aria-label="${state.saved.has(place.id) ? 'Bỏ lưu' : 'Lưu'} ${esc(place.name)}" title="${state.saved.has(place.id) ? 'Bỏ lưu' : 'Lưu địa điểm'}">${icon('star', 19)}</button>`}</div>`;
}
function card(place) {
  const name = category(place.category).name || 'Địa điểm';
  const location = wardName(place.ward_slug) || place.address || 'Hà Nội';
  return `<article class="place-card" style="--accent:${color(place.category)}">${media(place)}<div class="place-body"><div class="place-meta"><span>${esc(name)}</span><span>${esc(location)}</span></div><button type="button" class="place-title" data-action="open" data-id="${place.id}">${esc(place.name)}</button><p class="place-address">${esc(place.address || location)}</p><div class="place-foot"><span>${distanceLabel(place) || (place.has_vr ? 'Có tham quan 360°' : 'Khám phá địa điểm')}</span><button type="button" data-action="open" data-id="${place.id}">Xem chi tiết →</button></div></div></article>`;
}
function cards(items, layout = '') { return `<div class="place-grid ${layout}">${items.map(card).join('')}</div>`; }
function section(title, subtitle, items, action = '', layout = '') {
  if (!items.length) return '';
  return `<section class="section"><div class="section-heading"><div><h2>${esc(title)}</h2>${subtitle ? `<p>${esc(subtitle)}</p>` : ''}</div>${action}</div>${cards(items, layout)}</section>`;
}
function empty(title, message, action = '') {
  return `<div class="empty-state">${icon('compass', 34)}<h3>${esc(title)}</h3><p>${esc(message)}</p>${action}</div>`;
}
function placesInCategory(categoryId) {
  return state.pois.filter(place => place.category === categoryId)
    .sort((a, b) => Number(b.featured) - Number(a.featured) || a.name.localeCompare(b.name, 'vi'));
}
function savedPlaces() { return [...state.saved].map(id => state.pois.find(place => place.id === id)).filter(Boolean); }

function discover() {
  const firstName = (state.user.full_name || state.user.username).trim().split(/\s+/).pop();
  const tourism = placesInCategory('du-lich').slice(0, 4);
  const heritage = placesInCategory('di-tich').slice(0, 4);
  const nearby = state.geo ? [...state.pois].filter(place => distance(place) !== null).sort((a, b) => distance(a) - distance(b)).slice(0, 4) : [];
  return `<div class="hero"><div class="hero-copy"><div class="eyebrow">Xanh24 · Khám phá Hà Nội</div><h1>Chào ${esc(firstName)}, hôm nay bạn muốn đi đâu?</h1><p>Khám phá những nơi thú vị, tìm địa điểm phù hợp với bạn và lưu lại hành trình của riêng mình.</p><div class="hero-actions"><a class="light-btn" href="#browse">${icon('search', 18)} Khám phá địa điểm</a><a class="outline-btn" href="/?mode=web">${icon('map', 18)} Mở bản đồ</a></div></div><div class="hero-visual"><div class="hero-orbit">${icon('pin', 92)}</div><div class="hero-badge">${state.pois.length} địa điểm để khám phá</div></div></div>
    ${section('Địa điểm du lịch nổi bật', 'Những điểm du lịch đáng khám phá tại Hà Nội', tourism, '<button type="button" class="text-link" data-action="browse-category" data-category="du-lich">Xem tất cả →</button>', tourism.length === 3 ? 'three' : '')}
    ${section('Di tích lịch sử', 'Tìm hiểu lịch sử và văn hóa qua những địa danh', heritage, '<button type="button" class="text-link" data-action="browse-category" data-category="di-tich">Xem tất cả →</button>')}
    <section class="section"><div class="section-heading"><div><h2>${state.geo ? 'Gần bạn' : 'Khám phá gần bạn'}</h2><p>${state.geo ? 'Các địa điểm gần vị trí hiện tại của bạn' : 'Chỉ cần bật vị trí khi bạn muốn tìm quanh mình'}</p></div>${!state.geo ? '<button type="button" class="text-link" data-action="use-location">Dùng vị trí hiện tại →</button>' : ''}</div>${nearby.length ? cards(nearby) : `<div class="notice-panel near-panel"><div><h3>Tìm địa điểm quanh bạn</h3><p>Bạn có thể cho phép sử dụng vị trí hoặc lọc theo khu vực trong mục Khám phá.</p></div><button type="button" class="primary-btn" data-action="use-location">${icon('locate', 18)} Dùng vị trí</button></div>`}</section>
    ${section('Địa điểm đã lưu', 'Những nơi bạn muốn ghé thăm', savedPlaces().slice(0, 4), '<a class="text-link" href="#saved">Xem danh sách →</a>')}`;
}

function browse() {
  let places = state.pois.filter(place =>
    (!state.category || place.category === state.category) &&
    (!state.ward || place.ward_slug === state.ward) &&
    (!state.query || norm(`${place.name} ${place.address} ${place.tags || ''} ${category(place.category).name || ''} ${wardName(place.ward_slug)}`).includes(norm(state.query)))
  );
  places = places.sort((a, b) => state.geo ? (distance(a) ?? Infinity) - (distance(b) ?? Infinity) : Number(b.featured) - Number(a.featured) || a.name.localeCompare(b.name, 'vi'));
  return `<div class="page-title"><div class="eyebrow">Bộ sưu tập địa điểm</div><h1>${state.query ? `Kết quả cho “${esc(state.query)}”` : 'Khám phá địa điểm'}</h1><p>Tìm nơi phù hợp rồi xem trên bản đồ hoặc lưu để ghé thăm sau.</p></div>
    <div class="filterbar"><select id="categoryFilter" aria-label="Lọc theo danh mục"><option value="">Tất cả danh mục</option>${state.categories.map(item => `<option value="${esc(item.id)}" ${state.category === item.id ? 'selected' : ''}>${esc(item.name)}</option>`).join('')}</select><select id="wardFilter" aria-label="Lọc theo khu vực"><option value="">Toàn bộ khu vực</option>${state.wards.map(item => `<option value="${esc(item.slug)}" ${state.ward === item.slug ? 'selected' : ''}>${esc(item.name)}</option>`).join('')}</select><button type="button" class="outline-btn" data-action="use-location">${icon('locate', 16)} ${state.geo ? 'Đang xếp theo khoảng cách' : 'Gần tôi'}</button><span class="result-count">${places.length} địa điểm</span></div>
    ${places.length ? cards(places) : empty('Chưa tìm thấy địa điểm', 'Thử từ khóa, danh mục hoặc khu vực khác.', '<button type="button" class="outline-btn" data-action="reset-filters">Xóa bộ lọc</button>')}`;
}

function savedView() {
  const places = savedPlaces();
  return `<div class="page-title"><div class="eyebrow">Bộ sưu tập của bạn</div><h1>Địa điểm đã lưu</h1><p>Lưu những nơi muốn ghé thăm và mở lại bất cứ lúc nào.</p></div>${places.length ? cards(places) : empty('Chưa lưu địa điểm nào', 'Khi thấy một địa điểm yêu thích, bấm biểu tượng ngôi sao để lưu.', '<a class="primary-btn" href="#browse">Khám phá ngay</a>')}`;
}

function birthParts() {
  const value = state.user.birth_date || '';
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').map(Number) : [0, 0, 0];
}
function numberOptions(start, end, selected, placeholder, descending = false) {
  const numbers = Array.from({ length: end - start + 1 }, (_, index) => descending ? end - index : start + index);
  return `<option value="">${placeholder}</option>` + numbers.map(value => `<option value="${value}" ${value === selected ? 'selected' : ''}>${value}</option>`).join('');
}
function daysIn(year, month) { return month ? new Date(year || 2000, month, 0).getDate() : 0; }
function profile() {
  const user = state.user;
  const [year, month, day] = birthParts();
  return `<div class="page-title"><div class="eyebrow">Tài khoản cá nhân</div><h1>Góc của ${esc((user.full_name || user.username).split(/\s+/).pop())}</h1><p>Quản lý thông tin cá nhân của bạn.</p></div><div class="profile-layout">
    <section class="panel"><h2>Thông tin cá nhân</h2><p class="panel-intro">Tên đăng nhập: <b>${esc(user.username)}</b></p><form id="profileForm"><div class="form-field"><label for="profileName">Họ tên</label><input id="profileName" value="${esc(user.full_name)}" required></div><span class="form-label">Ngày sinh</span><div class="birth-row"><div class="form-field"><label for="birthYear">Năm</label><select id="birthYear" required>${numberOptions(1900, new Date().getFullYear(), year, 'Năm', true)}</select></div><div class="form-field"><label for="birthMonth">Tháng</label><select id="birthMonth" required>${numberOptions(1, 12, month, 'Tháng')}</select></div><div class="form-field"><label for="birthDay">Ngày</label><select id="birthDay" required ${month ? '' : 'disabled'}>${numberOptions(1, daysIn(year, month), day, 'Ngày')}</select></div></div><div class="form-field"><label for="profileGender">Giới tính</label><select id="profileGender" required><option value="">Chọn giới tính</option><option value="male" ${user.gender === 'male' ? 'selected' : ''}>Nam</option><option value="female" ${user.gender === 'female' ? 'selected' : ''}>Nữ</option><option value="undisclosed" ${user.gender === 'undisclosed' ? 'selected' : ''}>Không tiết lộ</option></select></div><div class="form-field"><label for="profileEmail">Email</label><input id="profileEmail" type="email" value="${esc(user.email)}" required></div><div class="form-field"><label for="profilePhone">Số điện thoại</label><input id="profilePhone" type="tel" value="${esc(user.phone || '')}" required></div><div class="form-separator"></div><div class="form-field"><label for="currentPassword">Mật khẩu hiện tại</label><input id="currentPassword" type="password" autocomplete="current-password" placeholder="Chỉ nhập khi đổi mật khẩu"></div><div class="form-field"><label for="newPassword">Mật khẩu mới</label><input id="newPassword" type="password" autocomplete="new-password" placeholder="Để trống nếu không đổi"></div><button type="submit" class="primary-btn">Lưu hồ sơ</button></form></section>
    </div><section class="section"><div class="inline-actions"><a class="outline-btn" href="/cms/login?partner=1">Đăng ký làm đối tác</a><button type="button" class="outline-btn" data-action="logout">Đăng xuất</button></div></section>`;
}

function render() {
  const page = location.hash.replace(/^#/, '') || 'discover';
  const current = ['discover', 'browse', 'saved', 'profile'].includes(page) ? page : 'discover';
  $('#view').innerHTML = ({ discover, browse, saved: savedView, profile })[current]();
  $$('[data-nav]').forEach(link => link.classList.toggle('active', link.dataset.nav === current || (current === 'browse' && link.dataset.nav === 'discover')));
  $('#accountName').textContent = state.user.full_name || state.user.username;
  $('#avatar').textContent = (state.user.full_name || state.user.username).trim().charAt(0).toUpperCase();
  $('#searchInput').value = state.query;
  document.title = `${current === 'saved' ? 'Đã lưu' : current === 'profile' ? 'Cá nhân' : 'Khám phá'} · Xanh24 Maps for Life`;
}

async function openPlace(id) {
  try {
    const place = await api(`/api/public/pois/${id}`);
    state.detail = place;
    renderDetail();
    $('#placeDialog').showModal();
  } catch (error) { toast(error.message); }
}
function renderDetail() {
  const place = state.detail;
  if (!place) return;
  const website = safeLink(place.website);
  const phone = String(place.phone || '').replace(/[^+\d]/g, '');
  $('#placeDialog').innerHTML = `${media(place, true)}<button type="button" class="detail-close" data-action="close-detail" aria-label="Đóng">${icon('close', 20)}</button><div class="detail-body"><div class="place-meta" style="--accent:${color(place.category)}"><span>${esc(category(place.category).name || 'Địa điểm')}</span><span>${esc(place.ward_name || wardName(place.ward_slug) || 'Hà Nội')}</span></div><h2>${esc(place.name)}</h2><p class="detail-address">${esc(place.address || '')}</p><div class="detail-facts">${place.hours ? `<div>${icon('clock', 18)}<span>${esc(place.hours)}</span></div>` : ''}${phone ? `<div>${icon('phone', 18)}<a href="tel:${esc(phone)}">${esc(place.phone)}</a></div>` : ''}${website ? `<div>${icon('globe', 18)}<a href="${esc(website)}" target="_blank" rel="noopener noreferrer">Website địa điểm</a></div>` : ''}${place.vr360 ? `<div>${icon('vr', 18)}<span>Có tham quan 360° trên bản đồ</span></div>` : ''}</div>${place.description ? `<p class="detail-description">${esc(place.description)}</p>` : ''}<div class="detail-actions"><a class="primary-btn" href="${mapUrl(place)}">${icon('map', 18)} Xem trên bản đồ</a><a class="outline-btn" href="${mapUrl(place, true)}">${icon('route', 18)} Chỉ đường</a><button type="button" class="save-button ${state.saved.has(place.id) ? 'saved' : ''}" data-action="save" data-id="${place.id}">${icon('star', 18)} ${state.saved.has(place.id) ? 'Đã lưu' : 'Lưu địa điểm'}</button></div></div>`;
}

function updateDays() {
  const year = Number($('#birthYear')?.value), month = Number($('#birthMonth')?.value), day = $('#birthDay');
  if (!day) return;
  const selected = Number(day.value);
  day.innerHTML = numberOptions(1, daysIn(year, month), selected, 'Ngày');
  day.disabled = !month;
}

async function toggleSave(id) {
  const wasSaved = state.saved.has(id);
  try {
    await api(`/api/user/saved/${id}`, { method: wasSaved ? 'DELETE' : 'POST' });
    if (wasSaved) state.saved.delete(id); else state.saved = new Set([id, ...state.saved]);
    render();
    if ($('#placeDialog').open) renderDetail();
    toast(wasSaved ? 'Đã bỏ lưu địa điểm' : 'Đã lưu địa điểm');
  } catch (error) { toast(error.message); }
}

function useLocation() {
  if (!navigator.geolocation) { toast('Trình duyệt không hỗ trợ lấy vị trí'); return; }
  navigator.geolocation.getCurrentPosition(position => {
    state.geo = { lat: position.coords.latitude, lng: position.coords.longitude };
    render();
    toast('Đã cập nhật các địa điểm gần bạn');
  }, () => toast('Không lấy được vị trí. Bạn có thể chọn khu vực trong mục Cá nhân.'),
  { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
}

document.addEventListener('click', event => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const action = button.dataset.action;
  if (action === 'open') openPlace(Number(button.dataset.id));
  if (action === 'save') toggleSave(Number(button.dataset.id));
  if (action === 'browse-category') {
    state.category = button.dataset.category;
    state.query = '';
    location.hash = '#browse';
    render();
  }
  if (action === 'use-location') useLocation();
  if (action === 'reset-filters') { state.category = ''; state.ward = ''; state.query = ''; render(); }
  if (action === 'close-detail') $('#placeDialog').close();
  if (action === 'logout') { localStorage.removeItem('x24_cms_token'); location.assign('/cms/login'); }
});
$('#placeDialog').addEventListener('click', event => { if (event.target === $('#placeDialog')) $('#placeDialog').close(); });
$('#searchForm').addEventListener('submit', event => {
  event.preventDefault();
  state.query = $('#searchInput').value.trim();
  state.category = '';
  state.ward = '';
  location.hash = '#browse';
  render();
});
document.addEventListener('change', event => {
  if (event.target.id === 'categoryFilter') { state.category = event.target.value; render(); }
  if (event.target.id === 'wardFilter') { state.ward = event.target.value; render(); }
  if (['birthYear', 'birthMonth'].includes(event.target.id)) updateDays();
});
document.addEventListener('submit', async event => {
  if (event.target.id === 'profileForm') {
    event.preventDefault();
    const year = $('#birthYear').value, month = $('#birthMonth').value, day = $('#birthDay').value;
    if (!year || !month || !day) { toast('Cần chọn đầy đủ năm, tháng và ngày sinh'); return; }
    try {
      const result = await api('/api/cms/profile', { method: 'PUT', body: {
        full_name: $('#profileName').value,
        birth_date: `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`,
        gender: $('#profileGender').value, email: $('#profileEmail').value, phone: $('#profilePhone').value,
        current_password: $('#currentPassword').value, new_password: $('#newPassword').value,
      } });
      state.user = result.user;
      render();
      toast('Đã lưu hồ sơ');
    } catch (error) { toast(error.message); }
  }
});
window.addEventListener('hashchange', () => { if (state.user) { render(); window.scrollTo(0, 0); } });

async function start() {
  $$('[data-icon]').forEach(element => { element.innerHTML = icon(element.dataset.icon, 22); });
  $('#searchIcon').innerHTML = icon('search', 19);
  if (!state.token) { location.replace('/cms/login'); return; }
  try {
    state.user = (await api('/api/cms/me')).user;
    if (state.user.role !== 'USER') {
      location.replace(state.user.role === 'OWNER' ? '/dashboard/kiosk' : '/dashboard/admin');
      return;
    }
    const [bootstrap, places, saved] = await Promise.all([
      api('/api/public/bootstrap'), api('/api/public/pois'), api('/api/user/saved'),
    ]);
    state.categories = bootstrap.categories || [];
    state.wards = bootstrap.wards || [];
    state.pois = places.items || [];
    state.saved = new Set(saved.items || []);
    render();
  } catch (error) {
    if (error.status === 401) { localStorage.removeItem('x24_cms_token'); location.replace('/cms/login'); return; }
    $('#view').innerHTML = empty('Chưa tải được dữ liệu', error.message, '<button type="button" class="primary-btn" data-action="retry">Thử lại</button>');
  }
}
document.addEventListener('click', event => { if (event.target.closest('[data-action="retry"]')) start(); });
start();
