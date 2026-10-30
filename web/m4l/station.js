// Kiosk screen: shows a short-lived, single-use check-in QR. The kiosk authenticates with its own key
// (issued in /m4l/admin), never with a staff or user login. Scanning opens /m4l/k/<token> on the phone.
import { qrSVG } from '/js/qr.js';
import { demoInfo } from '/m4l/demo-mode.js';

const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const STORE = 'x24_m4l_station';
const REFRESH_MS = 8000;
let config = null;
try { config = JSON.parse(localStorage.getItem(STORE) || 'null'); } catch { config = null; }
let current = null;
let timer = null;

function setup(message = '') {
  clearTimeout(timer);
  $('#station').innerHTML = `<div class="station-card"><img src="/assets/logo.png" alt="Xanh24" class="station-logo"><h1>Cài đặt màn hình trạm</h1>
    <p>Nhập mã kiosk và khóa kiosk do quản lý khu vực cấp tại trang quản trị M4L. Khóa chỉ lưu trên thiết bị này.</p>
    ${message ? `<p class="station-error" role="alert">${esc(message)}</p>` : ''}
    <form id="setup" class="grid-form"><label class="field"><span>Mã kiosk</span><input name="device" required pattern="[A-Za-z0-9_\\-]{2,40}" value="${esc(config?.device || '')}"></label>
    <label class="field"><span>Khóa kiosk</span><input name="key" required minlength="20" autocomplete="off" type="password"></label>
    <button class="btn primary" type="submit">Bắt đầu hiển thị mã</button></form></div>`;
  $('#setup').onsubmit = event => {
    event.preventDefault();
    const form = new FormData(event.target);
    config = { device: form.get('device').trim(), key: form.get('key').trim() };
    try { localStorage.setItem(STORE, JSON.stringify(config)); } catch { /* kept in memory only */ }
    tick();
  };
}

async function tick() {
  clearTimeout(timer);
  try {
    const response = await fetch('/api/m4l/kiosk/ticket', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Kiosk-Key': config.key },
      body: JSON.stringify({ device: config.device, current: current?.token }) });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) { try { localStorage.removeItem(STORE); } catch { /* ignore */ } return setup(data.error || 'Khóa kiosk không hợp lệ'); }
    if (!response.ok) throw new Error(data.error || `Lỗi ${response.status}`);
    if (!current || current.token !== data.token) {
      current = data;
      const url = `${location.origin}${data.path}`;
      $('#station').innerHTML = `<div class="station-card"><img src="/assets/logo.png" alt="Xanh24" class="station-logo">
        <p class="eyebrow">${esc(data.kiosk?.name || config.device)}</p><h1>Quét mã để nhận ưu đãi quanh trạm</h1>
        <div class="qr station-qr">${qrSVG(url, { size: 320 })}</div>
        <p>Mở camera điện thoại và quét. Mỗi mã chỉ dùng một lần và tự đổi sau mỗi lượt quét.</p>
        <p class="muted small">Maps for Life · Xanh24</p>${demo ? `<p class="station-demo"><a href="${esc(url)}" target="_blank" rel="noopener">Không có điện thoại? Mô phỏng lượt quét trên máy này</a></p>` : ''}</div>`;
    }
  } catch (error) {
    $('#station').innerHTML = `<div class="station-card"><h1>Tạm thời chưa hiển thị được mã</h1><p class="station-error">${esc(error.message)}</p><p class="muted">Tự thử lại sau vài giây.</p></div>`;
    current = null;
  }
  timer = setTimeout(tick, REFRESH_MS);
}

const demo = await demoInfo;
if (!(config?.device && config?.key) && demo) {
  // Demo station: fetch the demo kiosk's own key instead of asking a visitor to type one.
  const response = await fetch('/api/m4l/demo/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role: 'kiosk' }) }).catch(() => null);
  const data = response?.ok ? await response.json() : null;
  if (data?.kiosk) config = data.kiosk;
}
if (config?.device && config?.key) tick(); else setup();
