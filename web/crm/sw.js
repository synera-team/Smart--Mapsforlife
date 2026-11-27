// Xanh24 CRM — service worker: cho phép cài đặt như ứng dụng; giao diện tải từ mạng trước, dự phòng bản đã lưu.
const V = 'x24-crm-1.0.0';
const SHELL = ['/crm/', '/crm/crm.css', '/crm/crm.js', '/crm/icons.js', '/crm/logo.webp', '/crm/favicon.webp'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).catch(() => { })); self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('x24-crm-') && k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin || u.pathname.startsWith('/api/')) return; // dữ liệu luôn lấy trực tiếp
  e.respondWith(fetch(e.request).then(r => { if (r.ok && SHELL.includes(u.pathname)) { const cp = r.clone(); caches.open(V).then(c => c.put(e.request, cp)); } return r; })
    .catch(() => caches.match(e.request, { ignoreSearch: true })));
});
