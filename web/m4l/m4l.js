import { icon } from '/js/icons.js';
import { moodIcon } from '/m4l/mood-icons.js';
import { formatPercent } from '/m4l/world.js?v=5';
import { qrSVG } from '/js/qr.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const TOKEN_KEY = 'x24_cms_token';
const REQUEST_TIMEOUT = 12000;
const RADII = [1000, 3000, 5000, 10000];

function storedToken() { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } }
function dropToken() { try { localStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ } }

const state = {
  token: storedToken(), home: null, categories: null,
  geo: null, geoStatus: 'idle', // idle | asking | ok | denied | unavailable | timeout
  filters: { mood: '', q: '', category: '', radius: '' },
  results: null, loading: false, error: null, requestId: 0,
  offers: null, offersError: null, wallet: null, walletError: null, kiosk: null, clockOffset: 0,
};
let toastTimer;
let searchTimer;

async function api(path, { method = 'GET', body } = {}) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
  try {
    const response = await fetch(path, { method, headers, signal: controller.signal, body: body === undefined ? undefined : JSON.stringify(body) });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(result.error || `Máy chủ trả lỗi ${response.status}`);
      error.status = response.status;
      error.code = result.code;
      throw error;
    }
    return result;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Máy chủ phản hồi quá lâu. Kiểm tra kết nối rồi thử lại.');
    if (error instanceof TypeError) throw new Error('Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.');
    throw error;
  } finally { clearTimeout(timer); }
}

function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { element.hidden = true; }, 4000);
}

// ---------------------------------------------------------------- routing
function route() {
  const path = location.pathname.replace(/\/+$/, '');
  if (/^\/m4l\/k\/[A-Za-z0-9_-]+$/.test(path)) return 'kiosk';
  return ({ '/m4l/discover': 'discover', '/m4l/world': 'world', '/m4l/vouchers': 'vouchers' })[path] || 'home';
}
function loginUrl() {
  const next = encodeURIComponent(location.pathname + location.search);
  return state.home?.features?.demo ? `/demo?as=user&next=${next}` : `/cms/login?next=${next}`;
}
function readQuery() {
  const params = new URLSearchParams(location.search);
  state.filters = { mood: params.get('mood') || '', q: params.get('q') || '', category: params.get('category') || '', radius: params.get('radius') || '' };
}
function discoverUrl(filters = state.filters) {
  const params = new URLSearchParams();
  for (const key of ['mood', 'q', 'category', 'radius']) if (filters[key]) params.set(key, filters[key]);
  const query = params.toString();
  return `/m4l/discover${query ? `?${query}` : ''}`;
}
function navigate(url, replace = false) {
  history[replace ? 'replaceState' : 'pushState'](null, '', url);
  render(true);
}

// ---------------------------------------------------------------- shared pieces
function moods() { return state.home?.moods || []; }
function moodBySlug(slug) { return moods().find(mood => mood.slug === slug); }
function placeImage(url, name, size) {
  return /^(\/uploads\/|https:\/\/)/.test(url || '') ? `<img src="${esc(url)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'img-fallback'}))">` : `<span class="img-fallback">${icon('pin', size)}</span>`;
}
function distanceLabel(meters) {
  if (meters == null) return '';
  return meters < 1000 ? `${Math.max(10, Math.round(meters / 10) * 10)} m` : `${(meters / 1000).toFixed(1).replace('.', ',')} km`;
}
function mapUrl(id, directions = false) { return `/?mode=web&poi=${encodeURIComponent(id)}${directions ? '&dir=foot&locate=1' : ''}`; }
function stateBlock(kind, title, message, actions = '') {
  return `<div class="state-block ${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${icon(kind === 'error' ? 'info' : 'compass', 34)}<h3>${esc(title)}</h3><p>${esc(message)}</p>${actions ? `<div class="state-actions">${actions}</div>` : ''}</div>`;
}
function skeleton(count, cls) { return Array.from({ length: count }, () => `<div class="skeleton ${cls}" aria-hidden="true"></div>`).join(''); }

// ---------------------------------------------------------------- vouchers (the server owns issue and expiry time)
function syncClock(serverTime) { if (serverTime) state.clockOffset = serverTime - Date.now() / 1000; }
function serverNow() { return Date.now() / 1000 + state.clockOffset; }
function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const pad = n => String(n).padStart(2, '0');
  return s >= 3600 ? `${Math.floor(s / 3600)}:${pad(Math.floor(s % 3600 / 60))}:${pad(s % 60)}` : `${pad(Math.floor(s / 60))}:${pad(s % 60)}`;
}
function randomKey() {
  const raw = globalThis.crypto?.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return raw.replace(/[^A-Za-z0-9-]/g, '').slice(0, 40);
}
function trackAttrs(campaign, poi, source) { return campaign ? ` data-track="nav_click" data-campaign="${campaign}" data-poi="${poi}" data-source="${source}"` : ''; }
function offerBlock(offer, source, session = '') {
  if (!offer) return '';
  return `<div class="offer"><span class="offer-ic" aria-hidden="true">%</span><div class="offer-text"><strong>${esc(offer.title)}${offer.is_demo ? ' <b class="demo-tag">[DEMO]</b>' : ''}</strong>
    <small>${esc(offer.benefit)} · đếm ngược ${offer.ttl_minutes} phút kể từ lúc nhận · còn ${offer.remaining.toLocaleString('vi-VN')} suất</small></div>
    <button type="button" class="btn small primary" data-action="claim" data-campaign="${offer.campaign_id}" data-source="${source}"${session ? ` data-session="${session}"` : ''}>Nhận voucher</button></div>`;
}
const VOUCHER_STATUS = { issued: 'Đang hiệu lực', redeemed: 'Đã sử dụng', expired: 'Đã hết hạn', revoked: 'Đã thu hồi' };
function voucherCard(v, withQr = false) {
  const live = v.status === 'issued' && v.expires_at > serverNow();
  const qr = live && withQr && v.code
    ? `<div class="qr" role="img" aria-label="Mã QR của voucher">${qrSVG(`${location.origin}/m4l/v/${v.code}`, { size: 232 })}</div><p class="qr-note">Đưa mã cho nhân viên cửa hàng quét. Mã tự vô hiệu khi hết giờ.</p>`
    : '';
  return `<article class="voucher${live ? '' : ` is-${v.status === 'issued' ? 'expired' : v.status}`}" data-voucher="${v.id}">
    <div class="voucher-head"><span class="offer-ic" aria-hidden="true">%</span><div><p class="place-meta">${esc(v.poi_name || '')}${v.is_demo ? ' · <b class="demo-tag">[DEMO] – Dữ liệu minh họa</b>' : ''}</p><h3>${esc(v.title)}</h3><p>${esc(v.benefit)}</p></div></div>
    ${live ? `<p class="countdown">Còn <b data-expires="${v.expires_at}">${clock(v.expires_at - serverNow())}</b></p>` : `<p class="voucher-status">${VOUCHER_STATUS[v.status === 'issued' ? 'expired' : v.status] || ''}</p>`}
    ${qr}${qr && state.home?.features?.demo ? `<a class="btn small ghost demo-staff" href="/demo?as=partner&voucher=${encodeURIComponent(v.code)}" target="_blank" rel="noopener">Mô phỏng: nhân viên quán quét mã</a>` : ''}${v.terms ? `<p class="terms">${esc(v.terms)}</p>` : ''}
    <div class="dialog-actions">${live ? `<a class="btn small primary" href="${mapUrl(v.poi_id, true)}"${trackAttrs(v.campaign_id, v.poi_id, v.source)}>${icon('route', 16)} Chỉ đường</a>` : ''}${live && !withQr ? `<button type="button" class="btn small ghost" data-action="show-voucher" data-id="${v.id}">${icon('qr', 16)} Mở mã QR</button>` : ''}</div></article>`;
}
function showVoucher(voucher) {
  const dialog = $('#placeDialog');
  dialog.innerHTML = `<button type="button" class="dialog-close" data-action="close" aria-label="Đóng">${icon('close', 20)}</button>
    <div class="dialog-body voucher-dialog"><p class="eyebrow">Pioneer Voucher</p>${voucherCard(voucher, true)}<a class="text-link" href="/m4l/vouchers" data-link>Xem ví voucher ${icon('chevron', 16)}</a></div>`;
  if (!dialog.open) dialog.showModal();
  $('.dialog-close', dialog).focus();
}
async function claimOffer(button) {
  if (!state.home?.user) {
    const dialog = $('#placeDialog');
    dialog.innerHTML = `<div class="dialog-body">${stateBlock('empty', 'Đăng nhập để nhận voucher', 'Voucher gắn với tài khoản của bạn để chỉ bạn dùng được.', `<a class="btn primary" href="${loginUrl()}">Đăng nhập</a><button type="button" class="btn ghost" data-action="close">Để sau</button>`)}</div>`;
    if (!dialog.open) dialog.showModal();
    return;
  }
  if (button.disabled) return;
  button.disabled = true;
  button.dataset.key ||= randomKey(); // a double tap or a retry after a timeout replays the same claim
  const label = button.textContent;
  button.textContent = 'Đang nhận…';
  try {
    const body = { campaign_id: Number(button.dataset.campaign), source: button.dataset.source, idempotency_key: button.dataset.key };
    if (button.dataset.session) body.kiosk_session_id = Number(button.dataset.session);
    const result = await api('/api/m4l/vouchers/claim', { method: 'POST', body });
    syncClock(result.server_time);
    state.wallet = null;
    if (state.home) state.home.vouchers = { active: (state.home.vouchers?.active || 0) + (result.replayed ? 0 : 1), next: result.voucher };
    showVoucher(result.voucher);
  } catch (error) {
    toast(error.code === 'ALREADY_CLAIMED' ? `${error.message}.` : error.message);
  } finally { button.disabled = false; button.textContent = label; }
}
function track(element) {
  const body = { type: element.dataset.track, event_id: randomKey(), campaign_id: Number(element.dataset.campaign) || undefined,
    poi_id: Number(element.dataset.poi) || undefined, source: element.dataset.source };
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  fetch('/api/m4l/events', { method: 'POST', headers, body: JSON.stringify(body), keepalive: true }).catch(() => {});
}
setInterval(() => {
  for (const element of $$('[data-expires]')) {
    const left = Number(element.dataset.expires) - serverNow();
    element.textContent = left > 0 ? clock(left) : 'Đã hết hạn';
    if (left <= 0 && !element.dataset.done) {
      element.dataset.done = '1';
      const card = element.closest('[data-voucher]');
      card?.classList.add('is-expired');
      card?.querySelector('.qr')?.remove(); // the server already refuses it; hide it so nobody tries
      card?.querySelector('.qr-note')?.replaceWith(Object.assign(document.createElement('p'), { className: 'voucher-status', textContent: 'Đã hết hạn' }));
    }
  }
}, 1000);

// ---------------------------------------------------------------- home
function homeView() {
  if (state.error && !state.home) return stateBlock('error', 'Chưa tải được trang', state.error, '<button type="button" class="btn primary" data-action="retry-home">Thử lại</button>');
  if (!state.home) {
    return `<section class="hero skeleton-hero" aria-busy="true"><div class="skeleton line w40"></div><div class="skeleton line w70"></div></section><div class="mood-grid">${skeleton(4, 'mood-skel')}</div>`;
  }
  const user = state.home.user;
  const greeting = user?.first_name ? `Xin chào ${esc(user.first_name)}!` : 'Xin chào!';
  const list = moods();
  const moodCards = list.length
    ? `<div class="mood-grid">${list.map(mood => `<a class="mood-card" href="${discoverUrl({ mood: mood.slug })}" data-link><span class="mood-icon">${moodIcon(mood.icon, 30)}</span><span class="mood-text"><strong>${esc(mood.name)}</strong><small>${esc(mood.description || '')}</small><em>${mood.poi_count ? `${mood.poi_count} địa điểm` : 'Chưa có địa điểm'}</em></span></a>`).join('')}</div>`
    : stateBlock('empty', 'Chưa có mood nào', 'Ban quản trị chưa cấu hình mood. Bạn vẫn có thể tìm địa điểm theo tên.', '<a class="btn primary" href="/m4l/discover" data-link>Tìm địa điểm</a>');
  const guestNote = user ? '' : `<p class="hero-note"><a href="${loginUrl()}">Đăng nhập</a> để nhận gợi ý mang tên bạn.</p>`;
  return `<section class="hero"><p class="eyebrow">Maps for Life</p><h1><span class="greet">${greeting}</span> Hôm nay bạn thế nào?</h1><p>Chọn tâm trạng, chúng tôi gợi ý nơi phù hợp quanh bạn.</p>${guestNote}</section>
    ${state.home.features.random ? blindBox() : ''}
    ${state.home.features.exploration ? worldCard() : ''}
    <section class="section" aria-labelledby="moodHeading"><div class="section-head"><h2 id="moodHeading">Bạn đang cần gì?</h2><a class="text-link" href="/m4l/discover" data-link>Xem tất cả ${icon('chevron', 16)}</a></div>${moodCards}</section>
    ${state.home.features.vouchers ? `<section class="section" id="pioneer" aria-labelledby="pioneerHeading">${pioneerBody()}</section>` : ''}`;
}
function pioneerBody() {
  const running = state.home.vouchers?.next;
  const head = `<div class="section-head"><h2 id="pioneerHeading">Pioneer Voucher</h2>${state.home.user ? `<a class="text-link" href="/m4l/vouchers" data-link>Ví voucher ${icon('chevron', 16)}</a>` : ''}</div>`;
  const live = running && running.expires_at > serverNow()
    ? `<a class="pioneer-live" href="/m4l/vouchers" data-link><span class="offer-ic" aria-hidden="true">%</span><span class="pioneer-text"><strong>${esc(running.title)}</strong><small>${esc(running.poi_name || '')} · ${state.home.vouchers.active} voucher đang chạy</small></span><b class="countdown-pill" data-expires="${running.expires_at}">${clock(running.expires_at - serverNow())}</b></a>`
    : '';
  let list;
  if (state.offersError) list = stateBlock('error', 'Chưa tải được ưu đãi', state.offersError, '<button type="button" class="btn primary" data-action="retry-offers">Thử lại</button>');
  else if (!state.offers) list = `<div class="offer-list">${skeleton(2, 'offer-skel')}</div>`;
  else if (!state.offers.length) list = stateBlock('empty', 'Chưa có ưu đãi đang chạy', 'Khi đối tác tham gia chương trình, ưu đãi có đồng hồ đếm ngược sẽ hiện ở đây và đi kèm gợi ý địa điểm.');
  else list = `<div class="offer-list">${state.offers.map(o => `<article class="offer-card"><p class="place-meta"><span class="badge sponsor">Đối tác</span> ${esc(o.poi_name)}${o.distance_m != null ? ` · ${distanceLabel(o.distance_m)}` : ''}</p>${offerBlock(o, 'home')}
      <div class="offer-links"><button type="button" class="btn small ghost" data-action="open" data-id="${o.poi_id}">Chi tiết</button><a class="btn small ghost" href="${mapUrl(o.poi_id, true)}"${trackAttrs(o.campaign_id, o.poi_id, 'home')}>${icon('route', 16)} Chỉ đường</a></div></article>`).join('')}</div>`;
  return head + live + list;
}
async function loadOffers() {
  try {
    state.offersError = null;
    const params = new URLSearchParams({ limit: '3' });
    if (state.geo) { params.set('lat', state.geo.lat.toFixed(3)); params.set('lng', state.geo.lng.toFixed(3)); }
    state.offers = (await api(`/api/m4l/offers?${params}`)).items;
  } catch (error) { state.offers = null; state.offersError = error.message; }
  const box = $('#pioneer');
  if (box && route() === 'home') box.innerHTML = pioneerBody();
}

// ---------------------------------------------------------------- wallet and kiosk check-in
function walletView() {
  const head = `<section class="page-head"><p class="eyebrow">Pioneer Voucher</p><h1>Ví voucher</h1><p>Voucher gắn với tài khoản của bạn, có đồng hồ đếm ngược theo giờ máy chủ.</p></section>`;
  if (!state.home) return head + `<div class="results">${skeleton(2, 'place-skel')}</div>`;
  if (!state.home.user) return head + stateBlock('empty', 'Đăng nhập để xem voucher', 'Voucher chỉ hiển thị cho chủ tài khoản.', `<a class="btn primary" href="${loginUrl()}">Đăng nhập</a>`);
  if (state.walletError) return head + stateBlock('error', 'Chưa tải được ví', state.walletError, '<button type="button" class="btn primary" data-action="retry-wallet">Thử lại</button>');
  if (!state.wallet) return head + `<div class="results">${skeleton(2, 'place-skel')}</div>`;
  if (!state.wallet.length) return head + stateBlock('empty', 'Bạn chưa có voucher nào', 'Voucher đi kèm gợi ý của đối tác: chọn một mood, mở hộp mù hoặc quét mã tại trạm Xanh24.', '<a class="btn primary" href="/m4l/discover" data-link>Khám phá</a>');
  return head + `<div class="wallet">${state.wallet.map(v => voucherCard(v)).join('')}</div>`;
}
async function loadWallet() {
  try {
    state.walletError = null;
    const data = await api('/api/m4l/vouchers');
    syncClock(data.server_time);
    state.wallet = data.items;
  } catch (error) { state.walletError = error.message; }
  if (route() === 'vouchers') $('#view').innerHTML = walletView();
}
function kioskToken() { return location.pathname.replace(/\/+$/, '').split('/').pop(); }
function kioskView() {
  const head = `<section class="page-head"><p class="eyebrow">Trạm Xanh24</p><h1>${state.kiosk?.data ? esc(state.kiosk.data.kiosk.name) : 'Check-in tại trạm'}</h1>${state.kiosk?.data?.kiosk.address ? `<p>${esc(state.kiosk.data.kiosk.address)}</p>` : ''}</section>`;
  if (!state.home) return head + skeleton(2, 'place-skel');
  if (!state.home.user) return head + stateBlock('empty', 'Đăng nhập để nhận ưu đãi quanh trạm', 'Sau khi đăng nhập bạn sẽ quay lại đúng trang này. Mã trên màn hình trạm có hiệu lực vài phút.', `<a class="btn primary" href="${loginUrl()}">Đăng nhập</a>`);
  if (!state.kiosk || state.kiosk.loading) return head + skeleton(2, 'place-skel');
  if (state.kiosk.error) return head + stateBlock('error', 'Không check-in được', state.kiosk.error, '<a class="btn primary" href="/m4l" data-link>Về trang chủ</a>');
  const { offers, session_id: session } = state.kiosk.data;
  if (!offers.length) return head + stateBlock('empty', 'Quanh trạm chưa có ưu đãi', 'Hiện chưa có đối tác nào gần trạm này tham gia chương trình. Bạn vẫn có thể khám phá theo cảm xúc.', '<a class="btn primary" href="/m4l/discover" data-link>Khám phá</a>');
  return head + `<p class="result-count">${offers.length} ưu đãi gần trạm · nhận trong vài phút sau khi quét</p><div class="offer-list">${offers.map(o => `<article class="offer-card"><p class="place-meta"><span class="badge sponsor">Đối tác</span> ${esc(o.poi_name)} · cách trạm ${distanceLabel(o.distance_m)}</p>${o.address ? `<p class="place-addr">${esc(o.address)}</p>` : ''}${offerBlock(o, 'kiosk', session)}
    <div class="offer-links"><button type="button" class="btn small ghost" data-action="open" data-id="${o.poi_id}">Chi tiết</button><a class="btn small ghost" href="${mapUrl(o.poi_id, true)}"${trackAttrs(o.campaign_id, o.poi_id, 'kiosk')}>${icon('route', 16)} Chỉ đường</a></div></article>`).join('')}</div>`;
}
async function checkIn() {
  const token = kioskToken();
  if (state.kiosk?.token === token) return;
  state.kiosk = { token, loading: true };
  try { state.kiosk = { token, data: await api('/api/m4l/kiosk/checkin', { method: 'POST', body: { ticket: token } }) }; } catch (error) { state.kiosk = { token, error: error.message }; }
  if (route() === 'kiosk') $('#view').innerHTML = kioskView();
}
function shakeToggle() {
  if (!('DeviceMotionEvent' in window)) return '';
  return `<button type="button" class="btn ghost small" data-action="shake" aria-pressed="${shake.on}">${shake.on ? 'Đang bật lắc máy' : 'Bật lắc máy'}</button>`;
}
function blindBox() {
  return `<section class="section" aria-labelledby="boxHeading"><h2 id="boxHeading" class="section-title">Hộp mù cảm xúc</h2>
    <div class="blindbox"><p class="blindbox-q">Đi đâu cũng được?</p>
      <button type="button" class="btn primary big" data-action="random">${icon('compass', 22)} Khám phá ngẫu nhiên</button>
      <div class="blindbox-foot"><span>Mỗi lượt gợi ý đúng một địa điểm.</span>${shakeToggle()}</div></div></section>`;
}
function progressBar(percentage, label) {
  return `<div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percentage}" aria-label="${esc(label)}"><span style="width:${Math.min(100, percentage)}%"></span></div>`;
}
function worldCard() {
  const { user, area, progress } = state.home;
  const owner = user?.first_name ? `Thế giới của ${esc(user.first_name)}` : 'Thế giới của bạn';
  const body = progress
    ? `<p class="world-stat">Đã khám phá <b>${progress.complete ? '' : '≈ '}${formatPercent(progress.percentage)}%</b> ${esc(area.name)}</p>${progressBar(Math.max(progress.percentage, progress.unlocked ? 0.6 : 0), `Tiến độ khám phá ${area.name}`)}<p class="world-sub">${progress.unlocked.toLocaleString('vi-VN')}/${progress.eligible.toLocaleString('vi-VN')} ô hợp lệ đã mở${progress.complete ? '' : ' · tỷ lệ tạm tính'}</p>`
    : `<p class="world-sub">${user ? 'Bật định vị trên bản đồ để bắt đầu mở khóa' : 'Đăng nhập rồi đi dạo để mở khóa'} ${esc(area.name)}.</p>`;
  return `<section class="section" aria-labelledby="worldHeading"><h2 id="worldHeading" class="section-title">${owner}</h2>
    <a class="world-card" href="/m4l/world" data-link><span class="world-text"><strong>Bản đồ của bạn</strong>${body}<span class="text-link">Mở bản đồ sương mù ${icon('chevron', 16)}</span></span><span class="world-fog" aria-hidden="true"></span></a></section>`;
}

// ---------------------------------------------------------------- random (one result per request; the server owns quota)
const shake = { on: false, last: 0, prev: null };
let randomBusy = false;
async function openRandom() {
  if (randomBusy) return;
  const dialog = $('#placeDialog');
  if (!state.home?.user) {
    dialog.innerHTML = `<div class="dialog-body">${stateBlock('empty', 'Đăng nhập để khám phá ngẫu nhiên', 'Mỗi tài khoản có số lượt mỗi ngày để gợi ý không lặp lại.', `<a class="btn primary" href="${loginUrl()}">Đăng nhập</a><button type="button" class="btn ghost" data-action="close">Để sau</button>`)}</div>`;
    if (!dialog.open) dialog.showModal();
    return;
  }
  randomBusy = true;
  let skip = false;
  dialog.innerHTML = `<div class="dialog-body reveal" aria-busy="true"><div class="reveal-orb" aria-hidden="true">${icon('compass', 56)}</div><p class="reveal-text">Vũ trụ đang chọn cho bạn…</p><button type="button" class="btn ghost small" data-action="skip-reveal">Bỏ qua hiệu ứng</button></div>`;
  dialog.onclick = event => { if (event.target.closest('[data-action="skip-reveal"]')) skip = true; };
  if (!dialog.open) dialog.showModal();
  const mood = route() === 'discover' ? state.filters.mood : '';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const minDelay = new Promise(resolve => {
    const started = Date.now();
    const tick = () => (skip || reduced || Date.now() - started > 1400 ? resolve() : setTimeout(tick, 80));
    tick();
  });
  let html;
  try {
    const body = mood ? { mood } : {};
    if (state.geo) { body.lat = state.geo.lat.toFixed(3); body.lng = state.geo.lng.toFixed(3); }
    const [result] = await Promise.all([api('/api/m4l/discovery/random', { method: 'POST', body }), minDelay]);
    if (!result.item) {
      html = stateBlock('empty', 'Chưa có địa điểm để gợi ý', result.message || 'Hãy thử mood khác.', '<button type="button" class="btn primary" data-action="close">Đóng</button>');
    } else {
      const place = result.item;
      const meta = [place.category_name, place.ward_name].filter(Boolean).join(' · ');
      html = `<p class="eyebrow">Thông điệp từ vũ trụ</p>${place.sponsored ? `<span class="badge sponsor">${esc(place.sponsor_label || 'Tài trợ')}</span>` : ''}
        <div class="reveal-media">${placeImage(place.image, place.name, 56)}</div>
        <p class="place-meta">${esc(meta)}</p><h2 id="placeTitle">${esc(place.name)}</h2>${place.address ? `<p class="place-addr">${esc(place.address)}</p>` : ''}
        ${place.reasons.length ? `<p class="reason"><b>Phù hợp vì:</b> ${esc(place.reasons.join('; '))}</p>` : ''}
        <p class="pick-reason">${esc(result.reason)} · còn ${result.remaining} lượt trong 24 giờ.</p>
        ${offerBlock(place.offer, 'random')}
        <div class="dialog-actions"><a class="btn primary" href="${mapUrl(place.id, true)}"${trackAttrs(place.campaign_id || place.offer?.campaign_id, place.id, 'random')}>${icon('route', 18)} Chỉ đường</a><button type="button" class="btn ghost" data-action="open" data-id="${place.id}">Chi tiết</button><button type="button" class="btn ghost" data-action="random-again">Thử lại</button></div>`;
    }
  } catch (error) {
    html = stateBlock('error', error.code === 'QUOTA_EXCEEDED' ? 'Hết lượt hôm nay' : 'Chưa khám phá được', error.message, '<button type="button" class="btn primary" data-action="close">Đóng</button>');
  } finally { randomBusy = false; }
  dialog.onclick = null;
  dialog.innerHTML = `<button type="button" class="dialog-close" data-action="close" aria-label="Đóng">${icon('close', 20)}</button><div class="dialog-body">${html}</div>`;
  $('.dialog-close', dialog).focus();
}
function onMotion(event) {
  const a = event.accelerationIncludingGravity;
  if (!a || a.x == null || document.hidden || $('#placeDialog').open) return;
  const current = { x: a.x, y: a.y, z: a.z };
  if (shake.prev) {
    const delta = Math.abs(current.x - shake.prev.x) + Math.abs(current.y - shake.prev.y) + Math.abs(current.z - shake.prev.z);
    if (delta > 25 && Date.now() - shake.last > 2500) { shake.last = Date.now(); openRandom(); }
  }
  shake.prev = current;
}
async function toggleShake() {
  if (shake.on) { window.removeEventListener('devicemotion', onMotion); shake.on = false; render(); return; }
  try {
    if (typeof DeviceMotionEvent.requestPermission === 'function' && await DeviceMotionEvent.requestPermission() !== 'granted') {
      toast('Chưa được phép dùng cảm biến chuyển động. Bạn vẫn có thể bấm nút.');
      return;
    }
    window.addEventListener('devicemotion', onMotion);
    shake.on = true;
    toast('Đã bật: lắc máy để khám phá');
  } catch { toast('Thiết bị không hỗ trợ lắc máy. Bạn vẫn có thể bấm nút.'); }
  render();
}

// ---------------------------------------------------------------- discover
function chips() {
  const active = state.filters.mood;
  const items = [{ slug: '', name: 'Tất cả', icon: 'compass' }, ...moods()];
  return `<div class="chip-row" role="group" aria-label="Chọn mood">${items.map(mood => `<button type="button" class="chip" data-action="mood" data-slug="${esc(mood.slug)}" aria-pressed="${active === mood.slug}">${moodIcon(mood.icon, 18)}<span>${esc(mood.name)}</span></button>`).join('')}</div>`;
}
function geoText() {
  return ({
    asking: 'Đang lấy vị trí…', ok: 'Đang xếp theo khoảng cách', denied: 'Bạn đã từ chối quyền vị trí — kết quả không theo khoảng cách.',
    unavailable: 'Thiết bị không xác định được vị trí.', timeout: 'Lấy vị trí quá lâu, hãy thử lại.',
  })[state.geoStatus] || '';
}
function filterBar() {
  const categories = state.categories || [];
  const hasGeo = state.geoStatus === 'ok';
  return `<div class="filters">
    <label class="field"><span>Loại địa điểm</span><select id="categoryFilter"><option value="">Tất cả</option>${categories.map(item => `<option value="${esc(item.id)}" ${state.filters.category === item.id ? 'selected' : ''}>${esc(item.name)}</option>`).join('')}</select></label>
    <label class="field"><span>Bán kính</span><select id="radiusFilter" ${hasGeo ? '' : 'disabled aria-describedby="geoHint"'}><option value="">Không giới hạn</option>${RADII.map(value => `<option value="${value}" ${String(value) === state.filters.radius ? 'selected' : ''}>${value / 1000} km</option>`).join('')}</select></label>
    <button type="button" class="btn ${hasGeo ? 'ghost active' : 'ghost'}" data-action="locate" ${state.geoStatus === 'asking' ? 'disabled' : ''}>${icon('locate', 18)} ${hasGeo ? 'Cập nhật vị trí' : 'Gần tôi'}</button>
  </div><p id="geoHint" class="geo-hint" role="status">${esc(geoText() || 'Vị trí chỉ dùng khi bạn bấm “Gần tôi” và không được lưu lại.')}</p>`;
}
function resultCard(place) {
  const meta = [place.category_name, place.ward_name].filter(Boolean).join(' · ');
  const reasons = place.reasons.length ? `<p class="reason"><b>Phù hợp vì:</b> ${esc(place.reasons.join('; '))}</p>` : '';
  return `<article class="place">
    <div class="place-img">${placeImage(place.image, place.name, 40)}</div>
    <div class="place-body">
      ${place.sponsored ? `<span class="badge sponsor">${esc(place.sponsor_label || 'Tài trợ')}</span>` : ''}
      <p class="place-meta">${esc(meta)}</p>
      <h3><button type="button" class="link-btn" data-action="open" data-id="${place.id}">${esc(place.name)}</button></h3>
      ${place.address ? `<p class="place-addr">${esc(place.address)}</p>` : ''}
      ${reasons}${place.sponsor_reason ? `<p class="sponsor-reason">${esc(place.sponsor_reason)}</p>` : ''}
      ${offerBlock(place.offer, 'discovery')}
      <div class="place-foot">${place.distance_m != null ? `<span class="distance">${icon('walk', 16)} ${distanceLabel(place.distance_m)}</span>` : '<span></span>'}
        <span class="place-actions"><button type="button" class="btn small ghost" data-action="open" data-id="${place.id}">Chi tiết</button><a class="btn small primary" href="${mapUrl(place.id, true)}"${trackAttrs(place.campaign_id || place.offer?.campaign_id, place.id, 'discovery')}>${icon('route', 16)} Chỉ đường</a></span></div>
    </div></article>`;
}
function resultsBlock() {
  if (state.error) return stateBlock('error', 'Chưa tải được kết quả', state.error, '<button type="button" class="btn primary" data-action="retry">Thử lại</button>');
  if (!state.results) return `<div class="results">${skeleton(3, 'place-skel')}</div>`;
  const { items, total, mood } = state.results;
  if (!items.length) {
    const others = moods().filter(item => item.slug !== state.filters.mood && item.poi_count).slice(0, 3);
    const suggestion = others.map(item => `<a class="btn ghost" href="${discoverUrl({ mood: item.slug })}" data-link>${esc(item.name)}</a>`).join('');
    const title = mood ? `Chưa có địa điểm cho “${mood.name}”` : 'Không tìm thấy địa điểm';
    const message = mood && !state.filters.q && !state.filters.category && !state.filters.radius
      ? 'Mood này chưa được gán địa điểm nào. Hãy thử một mood khác.'
      : 'Thử bỏ bớt bộ lọc, mở rộng bán kính hoặc đổi từ khóa.';
    return stateBlock('empty', title, message, `${suggestion}<button type="button" class="btn primary" data-action="clear">Xóa bộ lọc</button>`);
  }
  const more = state.results.next_cursor != null ? `<button type="button" class="btn ghost wide" data-action="more" ${state.loading ? 'disabled' : ''}>${state.loading ? 'Đang tải…' : 'Xem thêm'}</button>` : '';
  const sponsored = state.results.sponsored ? `<div class="sponsored-slot" aria-label="Nội dung tài trợ">${resultCard(state.results.sponsored)}</div>` : '';
  return `${sponsored}<p class="result-count">${total} địa điểm${state.results.sort === 'distance' ? ' · gần nhất trước' : ''}</p><div class="results">${items.map(resultCard).join('')}</div>${more}`;
}
function discoverView() {
  const mood = moodBySlug(state.filters.mood);
  const title = state.filters.q ? `Kết quả cho “${esc(state.filters.q)}”` : mood ? esc(mood.name) : 'Khám phá theo cảm xúc';
  return `<section class="page-head"><p class="eyebrow">Khám phá</p><h1>${title}</h1>${mood?.description ? `<p>${esc(mood.description)}</p>` : ''}</section>
    ${state.home ? chips() : ''}${filterBar()}<div id="results" aria-busy="${state.loading}">${resultsBlock()}</div>`;
}

// ---------------------------------------------------------------- data
async function loadHome() {
  try {
    state.error = null;
    state.home = await api('/api/m4l/home');
    if (state.home.session_expired) { dropToken(); state.token = null; }
  } catch (error) { state.error = error.message; }
}
async function loadCategories() {
  if (state.categories) return;
  try { state.categories = (await api('/api/public/bootstrap')).categories || []; } catch { state.categories = []; }
}
function discoveryParams(cursor = 0) {
  const params = new URLSearchParams();
  const { mood, q, category, radius } = state.filters;
  if (mood) params.set('mood', mood);
  if (q) params.set('q', q);
  if (category) params.set('category', category);
  if (state.geo) {
    // ~110 m precision is enough for ranking and avoids sending the exact position.
    params.set('lat', state.geo.lat.toFixed(3));
    params.set('lng', state.geo.lng.toFixed(3));
    if (radius) params.set('radius', radius);
  }
  if (cursor) params.set('cursor', cursor);
  return params.toString();
}
async function loadResults(append = false) {
  const id = ++state.requestId;
  state.loading = true;
  state.error = null;
  if (!append) state.results = null;
  paintResults();
  try {
    const data = await api(`/api/m4l/discovery?${discoveryParams(append ? state.results.next_cursor : 0)}`);
    if (id !== state.requestId) return;
    state.results = append ? { ...data, items: [...state.results.items, ...data.items] } : data;
  } catch (error) {
    if (id !== state.requestId) return;
    if (error.code === 'MOOD_NOT_FOUND') { toast('Mood này không còn hoạt động'); state.filters.mood = ''; history.replaceState(null, '', discoverUrl()); return loadResults(); }
    state.error = error.message;
  } finally {
    if (id === state.requestId) { state.loading = false; paintResults(); }
  }
}
function paintResults() {
  const box = $('#results');
  if (!box) return;
  box.innerHTML = resultsBlock();
  box.setAttribute('aria-busy', String(state.loading));
}

// ---------------------------------------------------------------- render
function paintAccount() {
  const user = state.home?.user;
  const name = user?.display_name || '';
  $('#accountName').textContent = user ? user.first_name || name : 'Đăng nhập';
  $('#avatar').innerHTML = user ? esc((name.charAt(0) || '?').toUpperCase()) : icon('user', 18);
  const target = user ? '/dashboard/user#profile' : loginUrl();
  $('#account').href = target;
  $('#bottomAccount').href = target;
  $('#bottomAccountLabel').textContent = user ? 'Cá nhân' : 'Đăng nhập';
}
// ---------------------------------------------------------------- world (lazy module; keeps the map alive across re-renders)
let world = null;
const worldContext = { api, toast, esc, icon, stateBlock, progressBar, openPlace, openRandom, home: () => state.home, shakeOn: () => shake.on, loginUrl };
function worldShell() {
  if (state.error && !state.home) return stateBlock('error', 'Chưa tải được bản đồ', state.error, '<button type="button" class="btn primary" data-action="retry-home">Thử lại</button>');
  return `<div class="world-page" aria-busy="true"><div class="skeleton line w40"></div><div class="skeleton map-skel"></div></div>`;
}
async function mountWorld() {
  const pending = { unmount() { this.dead = true; } };
  world = pending;
  try {
    const module = await import('/m4l/world.js?v=5');
    if (pending.dead || route() !== 'world') return;
    world = module.mountWorld($('#view'), worldContext);
  } catch (error) {
    if (!pending.dead) $('#view').innerHTML = stateBlock('error', 'Chưa tải được bản đồ', error.message, '<button type="button" class="btn primary" data-action="retry-home">Thử lại</button>');
  }
}

function render(fetchResults = false) {
  const page = route();
  if (page !== 'world' && world) { world.unmount(); world = null; }
  if (page === 'world' && world) { paintAccount(); return; }
  if (page === 'discover') readQuery();
  $('#view').innerHTML = ({ discover: discoverView, world: worldShell, vouchers: walletView, kiosk: kioskView })[page]?.() ?? homeView();
  $$('[data-nav]').forEach(link => { if (link.dataset.nav === page) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current'); });
  $('#searchInput').value = page === 'discover' ? state.filters.q : '';
  document.title = `${({ discover: 'Khám phá', world: 'Bản đồ của bạn', vouchers: 'Ví voucher', kiosk: 'Check-in tại trạm' })[page] || 'Trang chủ'} · Maps for Life`;
  paintAccount();
  if (page === 'vouchers' && state.home?.user && !state.wallet && !state.walletError) loadWallet();
  if (page === 'kiosk' && state.home?.user) checkIn();
  if (page === 'home' && state.home?.features.vouchers && !state.offers && !state.offersError) loadOffers();
  if (page === 'home' && state.home && location.hash === '#pioneer') requestAnimationFrame(() => $('#pioneer')?.scrollIntoView({ block: 'start' }));
  if (page === 'world' && state.home) mountWorld();
  if (page === 'discover' && fetchResults) loadResults();
  if (page === 'discover' && !state.categories && state.home) {
    loadCategories().then(() => { if (route() === 'discover') { $('#view').innerHTML = discoverView(); } });
  }
}

function useLocation() {
  if (!navigator.geolocation) { state.geoStatus = 'unavailable'; render(); return; }
  state.geoStatus = 'asking';
  render();
  navigator.geolocation.getCurrentPosition(position => {
    state.geo = { lat: position.coords.latitude, lng: position.coords.longitude };
    state.geoStatus = 'ok';
    render(true);
  }, error => {
    state.geo = null;
    state.geoStatus = error.code === 1 ? 'denied' : error.code === 3 ? 'timeout' : 'unavailable';
    state.filters.radius = '';
    render();
  }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
}

async function openPlace(id) {
  const dialog = $('#placeDialog');
  dialog.innerHTML = `<div class="dialog-body"><div class="skeleton line w70"></div><div class="skeleton line w40"></div></div>`;
  if (!dialog.open) dialog.showModal();
  try {
    const place = await api(`/api/public/pois/${encodeURIComponent(id)}`);
    const image = place.images?.[0]?.url || place.images?.[0]?.thumb || '';
    const phone = String(place.phone || '').replace(/[^+\d]/g, '');
    let website = '';
    try { const url = new URL(place.website); if (['http:', 'https:'].includes(url.protocol)) website = url.href; } catch { /* not a link */ }
    dialog.innerHTML = `<div class="dialog-media">${placeImage(image, place.name, 64)}</div>
      <button type="button" class="dialog-close" data-action="close" aria-label="Đóng">${icon('close', 20)}</button>
      <div class="dialog-body"><p class="place-meta">${esc(place.ward_name || '')}</p><h2 id="placeTitle">${esc(place.name)}</h2>
      ${place.address ? `<p class="place-addr">${esc(place.address)}</p>` : ''}
      <ul class="facts">${place.hours ? `<li>${icon('clock', 18)}<span>${esc(place.hours)}</span></li>` : ''}${phone ? `<li>${icon('phone', 18)}<a href="tel:${esc(phone)}">${esc(place.phone)}</a></li>` : ''}${website ? `<li>${icon('globe', 18)}<a href="${esc(website)}" target="_blank" rel="noopener noreferrer">Website</a></li>` : ''}</ul>
      ${place.description ? `<p class="desc">${esc(place.description)}</p>` : ''}
      <div class="dialog-actions"><a class="btn primary" href="${mapUrl(place.id, true)}">${icon('route', 18)} Chỉ đường</a><a class="btn ghost" href="${mapUrl(place.id)}">${icon('map', 18)} Xem trên bản đồ</a></div></div>`;
    $('.dialog-close', dialog).focus();
  } catch (error) {
    dialog.innerHTML = `<div class="dialog-body">${stateBlock('error', 'Không mở được địa điểm', error.message, '<button type="button" class="btn primary" data-action="close">Đóng</button>')}</div>`;
  }
}

// ---------------------------------------------------------------- events
document.addEventListener('click', event => {
  const tracked = event.target.closest('[data-track]');
  if (tracked) track(tracked);
  const link = event.target.closest('a[data-link]');
  if (link && !event.ctrlKey && !event.metaKey && !event.shiftKey && event.button === 0) {
    event.preventDefault();
    navigate(link.getAttribute('href'));
    window.scrollTo(0, 0);
    $('#view').focus({ preventScroll: true });
    return;
  }
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const action = button.dataset.action;
  if (action === 'mood') navigate(discoverUrl({ ...state.filters, mood: button.dataset.slug }), true);
  if (action === 'locate') useLocation();
  if (action === 'open') openPlace(button.dataset.id);
  if (action === 'close') $('#placeDialog').close();
  if (action === 'more') loadResults(true);
  if (action === 'retry') loadResults();
  if (action === 'clear') navigate(discoverUrl({ mood: '', q: '', category: '', radius: '' }), true);
  if (action === 'retry-home') start();
  if (action === 'random' || action === 'random-again') openRandom();
  if (action === 'shake') toggleShake();
  if (action === 'claim') claimOffer(button);
  if (action === 'retry-offers') { state.offersError = null; state.offers = null; render(); }
  if (action === 'retry-wallet') { state.walletError = null; render(); }
  if (action === 'show-voucher') {
    api(`/api/m4l/vouchers/${encodeURIComponent(button.dataset.id)}`).then(v => { syncClock(v.server_time); showVoucher(v); }).catch(error => toast(error.message));
  }
});
$('#placeDialog').addEventListener('click', event => { if (event.target === $('#placeDialog')) $('#placeDialog').close(); });
document.addEventListener('change', event => {
  if (event.target.id === 'categoryFilter') navigate(discoverUrl({ ...state.filters, category: event.target.value }), true);
  if (event.target.id === 'radiusFilter') navigate(discoverUrl({ ...state.filters, radius: event.target.value }), true);
});
$('#searchForm').addEventListener('submit', event => {
  event.preventDefault();
  clearTimeout(searchTimer);
  navigate(discoverUrl({ ...(route() === 'discover' ? state.filters : { mood: '', category: '', radius: '' }), q: $('#searchInput').value.trim() }));
});
$('#searchInput').addEventListener('input', () => {
  if (route() !== 'discover') return;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => navigate(discoverUrl({ ...state.filters, q: $('#searchInput').value.trim() }), true), 400);
});
window.addEventListener('popstate', () => render(true));

async function start() {
  $$('[data-icon]').forEach(element => { element.innerHTML = icon(element.dataset.icon, 22); });
  $('#searchIcon').innerHTML = icon('search', 18);
  render(route() === 'discover');
  await Promise.all([loadHome(), route() === 'discover' ? loadCategories() : null]);
  if (route() === 'discover') {
    $('#view').innerHTML = discoverView();
    paintAccount();
    paintResults();
  } else render();
}
start();
