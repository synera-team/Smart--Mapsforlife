// Demo landing (/demo): one tap opens a limited demo session and lands on the right screen.
// Visitors get their own throw-away USER account (localStorage, like a normal sign-in); partner and manager
// sessions stay in this tab only (sessionStorage) so they never replace the visitor's user session.
import { STAFF_TOKEN, clearStaffToken } from '/m4l/demo-mode.js';

const $ = (selector, root = document) => root.querySelector(selector);
const TOKEN_KEY = 'x24_cms_token';
const NAME_KEY = 'x24_demo_name';
const params = new URLSearchParams(location.search);
const safeNext = value => (/^\/m4l(\/[A-Za-z0-9_\-/]*)?(\?[A-Za-z0-9_\-=&%.]*)?(#[a-z-]*)?$/.test(value || '') ? value : '');
const storage = (area, key, value) => {
  try {
    if (value === undefined) return area.getItem(key);
    if (value === null) area.removeItem(key); else area.setItem(key, value);
  } catch { /* storage blocked: the session lasts for this page only */ }
  return null;
};
let busy = false;

function status(message, error = false) {
  const element = $('#status');
  element.textContent = message;
  element.classList.toggle('error', error);
}

async function session(body) {
  const response = await fetch('/api/m4l/demo/session', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Lỗi ${response.status}`);
  return result;
}

async function hasUserSession() {
  const token = storage(localStorage, TOKEN_KEY);
  if (!token) return false;
  const response = await fetch('/api/m4l/home', { headers: { Authorization: `Bearer ${token}` } }).catch(() => null);
  const home = response?.ok ? await response.json() : null;
  return Boolean(home?.user);
}

async function go(role, destination, extra = {}) {
  if (busy) return;
  busy = true;
  status('Đang mở phiên demo…');
  try {
    if (role === 'user') {
      if (!(await hasUserSession())) {
        const name = $('#displayName').value.trim() || storage(localStorage, NAME_KEY) || '';
        const result = await session({ role: 'user', name });
        storage(localStorage, TOKEN_KEY, result.token);
        if (name) storage(localStorage, NAME_KEY, name);
      }
    } else if (role === 'partner' || role === 'manager') {
      const result = await session({ role, ...extra });
      storage(sessionStorage, STAFF_TOKEN, result.token);
    }
    location.assign(destination);
  } catch (error) {
    busy = false;
    status(`${error.message} Nhấn lại để thử tiếp.`, true);
  }
}

$('#displayName').value = storage(localStorage, NAME_KEY) || '';
$('#startForm').onsubmit = event => { event.preventDefault(); go('user', '/m4l'); };
document.querySelectorAll('.demo-card').forEach(card => { card.onclick = () => go(card.dataset.role, card.dataset.go); });
$('#restart').onclick = () => {
  storage(localStorage, TOKEN_KEY, null);
  storage(localStorage, NAME_KEY, null);
  clearStaffToken();
  $('#displayName').value = '';
  status('Đã xóa phiên trên máy này. Nhấn một thẻ để bắt đầu lại.');
};

// Arriving from a sign-in link inside the app (/demo?as=…): continue straight away.
const as = params.get('as');
if (as === 'user') go('user', safeNext(params.get('next')) || '/m4l');
else if (as === 'partner') {
  const voucher = (params.get('voucher') || '').replace(/[^A-Za-z0-9_-]/g, '');
  go('partner', voucher ? `/m4l/v/${voucher}` : '/m4l/partner', voucher ? { voucher } : {});
} else if (as === 'manager') go('manager', '/m4l/admin');
