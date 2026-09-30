/* Xanh24 - Maps for Life — Service Worker (bộ nhớ đệm ngoại tuyến cho kiosk & web)
 * - Giao diện (HTML/CSS/JS/thư viện bản đồ): dùng bản đã lưu ngay, cập nhật ngầm ở nền.
 * - Dữ liệu công khai (/api/public/*): ưu tiên máy chủ (dữ liệu mới nhất), mất mạng → dùng bản đã lưu.
 * - Bản đồ nền (vector/raster tiles, font, sprite): lưu tối đa ~6000 ô, dùng lại khi mạng chậm/mất.
 * - Ảnh tải lên (/uploads): lưu lâu dài.
 * Không lưu: trang & API quản trị, các lệnh POST.
 */
const VERSION = 'x24-1.3.0';
const SHELL = `${VERSION}-shell`, DATA = `${VERSION}-data`, TILES = 'x24-tiles-v1', MEDIA = 'x24-media-v1';
const SHELL_FILES = ['/', '/css/app.css', '/js/app.js', '/js/icons.js', '/js/qr.js', '/js/vr.js', '/js/osk.js',
  '/vendor/maplibre-gl.js', '/vendor/maplibre-gl.css', '/assets/logo.png', '/assets/favicon.png', '/manifest.webmanifest', '/go.html'];
const TILE_HOSTS = /(^|\.)(openfreemap\.org|tile\.openstreetmap\.org|arcgisonline\.com|basemaps\.cartocdn\.com|fonts\.gstatic\.com|fonts\.googleapis\.com)$/;
const MAX_TILES = 6000, MAX_MEDIA = 800;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then(c => Promise.all(SHELL_FILES.map(u => c.add(new Request(u, { cache: 'reload' })).catch(() => { })))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('x24-') && ![SHELL, DATA, TILES, MEDIA].includes(k)).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

const timeout = (ms) => new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms));
async function trim(name, max) {
  const c = await caches.open(name); const keys = await c.keys();
  for (let i = 0; i < keys.length - max; i++) await c.delete(keys[i]);
}
async function networkFirst(req, cacheName, ms) {
  const c = await caches.open(cacheName);
  try {
    const res = await Promise.race([fetch(req), timeout(ms)]);
    if (res && res.ok) c.put(req, res.clone());
    return res;
  } catch (e) {
    const hit = await c.match(req, { ignoreVary: true });
    if (hit) return hit;
    throw e;
  }
}
async function staleWhileRevalidate(req, cacheName, ev) {
  const c = await caches.open(cacheName);
  const hit = await c.match(req, { ignoreVary: true });
  const net = fetch(req).then(res => { if (res && (res.ok || res.type === 'opaque')) c.put(req, res.clone()); return res; }).catch(() => null);
  if (hit) { ev.waitUntil(net); return hit; }
  return (await net) || Response.error();
}
let tileCount = 0;
async function cacheFirst(req, cacheName, max) {
  const c = await caches.open(cacheName);
  const hit = await c.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res && (res.ok || res.type === 'opaque')) { c.put(req, res.clone()); if (++tileCount % 200 === 0) trim(cacheName, max); }
  return res;
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const same = url.origin === self.location.origin;
  if (same) {
    const p = url.pathname;
    if (p.startsWith('/admin') || p.startsWith('/api/admin') || p.startsWith('/api/auth') || p === '/sw.js') return;
    if (req.mode === 'navigate') { e.respondWith(networkFirst(req, SHELL, 5000).catch(() => caches.match('/'))); return; }
    if (p.startsWith('/api/public/')) {
      if (p.startsWith('/api/public/version')) return; // luôn hỏi máy chủ
      e.respondWith(networkFirst(req, DATA, p.startsWith('/api/public/route') || p.startsWith('/api/public/reverse') ? 12000 : 6000));
      return;
    }
    if (p.startsWith('/api/')) return;
    if (p.startsWith('/uploads/')) { e.respondWith(cacheFirst(req, MEDIA, MAX_MEDIA)); return; }
    e.respondWith(staleWhileRevalidate(req, SHELL, e));
    return;
  }
  if (TILE_HOSTS.test(url.hostname)) {
    // style.json / TileJSON thay đổi theo phiên bản dữ liệu → ưu tiên mạng; ô bản đồ, font, sprite → lưu lâu dài
    if (/\.json$|\/styles\/|\/planet$|\/planet\/?$/.test(url.pathname) && !/\/fonts\//.test(url.pathname)) e.respondWith(networkFirst(req, TILES, 6000));
    else e.respondWith(cacheFirst(req, TILES, MAX_TILES));
  }
});

self.addEventListener('message', (e) => {
  if (e.data === 'x24:clear-data') e.waitUntil(caches.delete(DATA));
});
