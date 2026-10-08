import { qrSVG } from './qr.js';

const loginPanel = document.querySelector('#login-panel');
const catalogPanel = document.querySelector('#catalog-panel');
const form = document.querySelector('#pin-form');
const pinInput = document.querySelector('#pin');
const loginError = document.querySelector('#login-error');
const unlockButton = document.querySelector('#unlock');
const appList = document.querySelector('#app-list');
const emptyState = document.querySelector('#empty-state');
const catalogError = document.querySelector('#catalog-error');

function showLogin(message = '') {
  loginPanel.hidden = false;
  catalogPanel.hidden = true;
  loginError.textContent = message;
  loginError.hidden = !message;
  if (!message) pinInput.focus();
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function appCard(file) {
  const card = document.createElement('article');
  card.className = 'app-card';
  card.dataset.fileId = file.id;

  const icon = document.createElement('div');
  icon.className = 'app-icon';
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = 'X';

  const info = document.createElement('div');
  info.className = 'app-info';
  const title = document.createElement('h3');
  title.textContent = file.title;
  const version = document.createElement('span');
  version.className = 'version';
  version.textContent = `Phiên bản ${file.version}`;
  const meta = document.createElement('p');
  meta.className = 'app-meta';
  meta.textContent = `Android · ${formatSize(file.size)} · APK`;
  const filename = document.createElement('p');
  filename.className = 'app-filename';
  filename.textContent = file.name;
  info.append(title, version, meta, filename);

  const download = document.createElement('a');
  download.className = 'download-link';
  download.href = file.url;
  download.textContent = 'Tải ứng dụng';
  download.setAttribute('aria-label', `Tải ${file.name}`);
  const arrow = document.createElement('span');
  arrow.setAttribute('aria-hidden', 'true');
  arrow.textContent = '↓';
  download.append(arrow);

  const qrColumn = document.createElement('div');
  qrColumn.className = 'qr-column';
  const qr = document.createElement('div');
  qr.className = 'qr-image';
  qr.setAttribute('aria-label', `Mã QR mở trang tải ${file.name}`);
  const target = new URL('/download', window.location.origin);
  target.searchParams.set('app', file.id);
  qr.innerHTML = qrSVG(target.toString(), { size: 76, margin: 3 });
  const qrCaption = document.createElement('span');
  qrCaption.className = 'qr-caption';
  qrCaption.textContent = 'Quét để mở trang này';
  qrColumn.append(qr, qrCaption);

  card.append(icon, info, download, qrColumn);
  return card;
}

async function loadCatalog() {
  const response = await fetch('/api/download/files', { credentials: 'same-origin' });
  if (response.status === 401) {
    showLogin();
    return;
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Không thể tải danh sách ứng dụng');

  appList.replaceChildren(...result.files.map(appCard));
  emptyState.hidden = result.files.length > 0;
  loginPanel.hidden = true;
  catalogPanel.hidden = false;

  const selected = new URLSearchParams(window.location.search).get('app');
  const selectedCard = result.files.find(file => file.id === selected);
  if (selectedCard) {
    const card = [...appList.children].find(item => item.dataset.fileId === selectedCard.id);
    card?.classList.add('is-selected');
    card?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  unlockButton.disabled = true;
  unlockButton.textContent = 'Đang xác thực…';
  loginError.hidden = true;
  try {
    const response = await fetch('/api/download/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: pinInput.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Không thể xác thực mã PIN');
    pinInput.value = '';
    await loadCatalog();
  } catch (error) {
    showLogin(error.message);
    pinInput.select();
  } finally {
    unlockButton.disabled = false;
    unlockButton.innerHTML = 'Mở trang tải <span aria-hidden="true">→</span>';
  }
});

document.querySelector('#logout').addEventListener('click', async () => {
  catalogError.hidden = true;
  try {
    const response = await fetch('/api/download/logout', { method: 'POST', credentials: 'same-origin' });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || 'Không thể khóa phiên tải xuống');
    }
    showLogin();
  } catch (error) {
    catalogError.textContent = error.message;
    catalogError.hidden = false;
  }
});

loadCatalog().catch(error => showLogin(error.message));
