// Fog of War map for the whole city. The grid is fetched per viewport (cells when zoomed in, 1 km blocks
// when zoomed out) — never the full city. Geolocation runs only while the user has switched exploration on
// and the page is visible; samples go to the server, which alone decides whether a cell unlocks.
const SEND_EVERY_MS = 15000;
const SAMPLE_WINDOW_MS = 30000;
const CELL_ZOOM = 14;            // below this zoom only blocks are requested
let mapLibrary;

function loadMapLibre() {
  if (window.maplibregl) return Promise.resolve(window.maplibregl);
  mapLibrary ??= new Promise((resolve, reject) => {
    const css = Object.assign(document.createElement('link'), { rel: 'stylesheet', href: '/vendor/maplibre-gl.css' });
    const script = Object.assign(document.createElement('script'), { src: '/vendor/maplibre-gl.js', async: true });
    script.onload = () => resolve(window.maplibregl);
    script.onerror = () => { mapLibrary = null; reject(new Error('Không tải được thư viện bản đồ')); };
    document.head.append(css, script);
  });
  return mapLibrary;
}

function baseStyle(settings) {
  const tiles = settings?.tiles || {};
  const option = (tiles.options || []).find(item => item.id === tiles.active) || (tiles.options || [])[0];
  if (option?.style) return option.style;
  if (option?.tiles) {
    return { version: 8, sources: { base: { type: 'raster', tiles: option.tiles, tileSize: option.tileSize || 256, attribution: option.attribution || '', maxzoom: option.maxzoom || 19 } },
      layers: [{ id: 'base', type: 'raster', source: 'base' }] };
  }
  return { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#0b2233' } }] };
}

export function formatPercent(value) {
  if (!value) return '0';
  const text = value < 0.01 ? '<0,01' : value < 1 ? value.toFixed(3).replace(/0+$/, '') : value.toFixed(2);
  return text.replace('.', ',');
}

export function mountWorld(root, ctx) {
  const { api, toast, esc, icon, stateBlock, progressBar } = ctx;
  const user = ctx.home().user;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const s = {
    area: null, rules: null, progress: null, units: null, showUnits: false, unlocked: new Set(), view: null, pins: [],
    demo: new Set(), demoMode: false, fog: true, statusLayer: true, boundary: null,
    watchId: null, samples: [], lastSend: 0, sending: false, status: '', statusKind: '', map: null, markers: new Map(),
    userMarker: null, dead: false, request: null, searchResults: [],
  };
  const step = () => ({ dlat: s.area.dlat, dlng: s.area.dlng });
  const cellId = (lat, lng) => `${Math.floor(lng / s.area.dlng)}:${Math.floor(lat / s.area.dlat)}`;
  const rect = (x0, y0, x1, y1) => [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]];

  // ---------- panels
  function progressCard() {
    const p = s.progress;
    if (!s.area) return '';
    const name = esc(s.area.name);
    if (!p) return `<p class="world-sub">${user ? 'Bật khám phá để mở khóa các ô bạn đi qua.' : 'Đăng nhập để lưu những nơi bạn đã khám phá.'}</p>`;
    const approx = p.complete ? '' : '≈ ';
    const note = p.complete ? '' : `<p class="world-note">Tạm tính: ${p.pending_review.toLocaleString('vi-VN')} ô chưa xác minh đường đi nên chưa tính vào mẫu số${p.unlocked_pending ? ` (bạn đã đến ${p.unlocked_pending} ô như vậy)` : ''}.</p>`;
    const units = s.showUnits && s.units ? `<ul class="unit-list">${s.units.filter(u => u.unlocked).slice(0, 12).map(u => `<li><span>${esc(u.name)}</span><b>${formatPercent(u.percentage)}%</b><small>${u.unlocked}/${u.eligible} ô</small></li>`).join('') || '<li class="muted">Chưa mở ô nào.</li>'}</ul>` : '';
    return `<p class="world-stat">Đã khám phá <b>${approx}${formatPercent(p.percentage)}%</b> ${name}</p>${progressBar(Math.max(p.percentage, p.unlocked ? 0.6 : 0), `Tiến độ khám phá ${s.area.name}`)}
      <p class="world-sub">${p.unlocked.toLocaleString('vi-VN')}/${p.eligible.toLocaleString('vi-VN')} ô hợp lệ đã mở</p>${note}
      <button type="button" class="text-link" data-w="units" aria-expanded="${s.showUnits}">${s.showUnits ? 'Ẩn' : 'Xem'} theo phường/xã</button>${units}`;
  }
  function header() {
    const owner = user?.first_name ? `Thế giới của ${esc(user.first_name)}` : 'Thế giới của bạn';
    return `<h1>${owner}</h1><div class="world-progress"><p class="eyebrow">Bản đồ của bạn</p>${progressCard()}
      <ul class="legend" aria-label="Chú giải"><li><span class="swatch fog"></span>Chưa khám phá</li><li><span class="swatch open"></span>Đã mở khóa</li>
      <li><span class="swatch water"></span>Mặt nước (không tính)</li><li><span class="swatch restricted"></span>Khu hạn chế</li><li><span class="swatch pin">?</span>Ghim bí ẩn</li>${s.demoMode ? '<li><span class="swatch demo"></span>Demo (không lưu)</li>' : ''}</ul></div>`;
  }
  function controls() {
    const exploring = s.watchId !== null;
    const explore = user
      ? `<button type="button" class="btn ${exploring ? 'ghost active' : 'primary'}" data-w="explore" aria-pressed="${exploring}">${icon('locate', 18)} ${exploring ? 'Tắt khám phá' : 'Bật khám phá bằng định vị'}</button>`
      : `<a class="btn primary" href="${ctx.loginUrl()}">Đăng nhập để mở khóa</a>`;
    const shake = 'DeviceMotionEvent' in window ? `<button type="button" class="btn ghost small" data-action="shake" aria-pressed="${ctx.shakeOn()}">${ctx.shakeOn() ? 'Đang bật lắc máy' : 'Bật lắc máy'}</button>` : '';
    return `<div class="world-cta"><p>${icon('walk', 18)} Di chuyển để mở khóa bản đồ!</p><div class="world-actions">${explore}
      <button type="button" class="btn primary" data-action="random">${icon('compass', 18)} Lắc máy để khám phá</button>${shake}
      <button type="button" class="btn ghost small" data-w="demo" aria-pressed="${s.demoMode}">${s.demoMode ? 'Thoát demo' : 'Thử chế độ demo'}</button></div>
      <p class="geo-hint" role="status" data-kind="${s.statusKind}">${esc(s.status || 'Định vị chỉ chạy khi trang đang mở và bạn bật. Kéo hay phóng to bản đồ không mở khóa ô.')}</p></div>`;
  }
  function pinActions(pin) {
    if (!pin.poi) return '';
    return `<div class="pin-actions"><button type="button" class="btn small ghost" data-action="open" data-id="${pin.poi.id}">Chi tiết</button>
      <a class="btn small primary" href="/?mode=web&poi=${encodeURIComponent(pin.poi.id)}&dir=foot&locate=1">${icon('route', 16)} Chỉ đường</a></div>`;
  }
  function pinList() {
    if (!s.pins.length) return `<p class="muted">Không có ghim bí ẩn trong khung nhìn hiện tại${s.view?.level === 'blocks' ? ' — phóng to để xem' : ''}.</p>`;
    return `<ul class="pin-list">${s.pins.map(pin => pin.unlocked
      ? `<li class="pin-open"><span class="found-tag">Đã khám phá</span><b>${esc(pin.reveal_title || pin.teaser)}</b>${pin.reveal_text ? `<p>${esc(pin.reveal_text)}</p>` : ''}${pin.poi ? `<p class="muted">${esc(pin.poi.name)}</p>` : ''}${pinActions(pin)}</li>`
      : `<li class="pin-locked"><span class="pin-q" aria-hidden="true">?</span><span><b>Ghim bí ẩn</b> · ${esc(pin.teaser)}<br><small>Đi tới khu vực này (vị trí làm tròn ~100 m) để mở khóa</small></span></li>`).join('')}</ul>`;
  }
  function revealPins(pins) {
    const dialog = document.querySelector('#placeDialog');
    if (!pins.length || !dialog) return;
    dialog.innerHTML = `<button type="button" class="dialog-close" data-action="close" aria-label="Đóng">${icon('close', 20)}</button>
      <div class="dialog-body pin-reveal"><div class="reveal-burst" aria-hidden="true">★</div><p class="eyebrow">Bạn vừa mở một ghim bí ẩn</p>
      ${pins.map(pin => `<h2 id="placeTitle">${esc(pin.reveal_title || pin.teaser)}</h2>${pin.reveal_text ? `<p class="desc">${esc(pin.reveal_text)}</p>` : ''}${pin.poi ? `<p class="place-addr">${esc(pin.poi.name)}${pin.poi.address ? ` · ${esc(pin.poi.address)}` : ''}</p>` : ''}${pinActions(pin)}`).join('<hr>')}</div>`;
    if (!dialog.open) dialog.showModal();
  }
  function paintPanels() {
    if (s.dead) return;
    root.querySelector('#worldHead').innerHTML = header();
    root.querySelector('#worldCta').innerHTML = controls();
    root.querySelector('#worldPins').innerHTML = pinList();
  }
  function setStatus(text, kind = '') { s.status = text; s.statusKind = kind; paintPanels(); }

  root.innerHTML = `<div class="world-page"><section class="world-head" id="worldHead"></section>
    <div class="map-wrap"><div id="fogMap" class="fog-map" role="region" aria-label="Bản đồ khám phá"></div>
      <form class="map-search" id="mapSearch" role="search"><label class="sr-only" for="mapQuery">Tìm nơi trên bản đồ</label><input id="mapQuery" type="search" placeholder="Tìm nơi ở Hà Nội…" maxlength="120" autocomplete="off"><div id="mapResults" class="map-results" hidden></div></form>
      <div class="map-tools"><button type="button" data-w="center" aria-label="Định vị tôi">${icon('locate', 20)}</button><button type="button" data-w="overview" aria-label="Xem toàn khu vực">${icon('map', 20)}</button><button type="button" data-w="layers" aria-pressed="true" aria-label="Bật/tắt lớp trạng thái ô">${icon('layers', 20)}</button><button type="button" data-w="fog" aria-pressed="true" aria-label="Bật/tắt sương mù">${icon('eye', 20)}</button></div>
      <p class="map-level" id="mapLevel" aria-live="polite"></p></div>
    <section id="worldCta"></section>
    <section class="section"><h2 class="section-title">Ghim bí ẩn quanh đây</h2><div id="worldPins"></div></section>
    ${user ? '<section class="section privacy"><h2 class="section-title">Dữ liệu vị trí</h2><p class="muted">Chúng tôi chỉ lưu danh sách ô bạn đã mở và một vị trí gần nhất (làm tròn ~11 m) để chống gian lận.</p><button type="button" class="btn ghost small" data-w="forget">Xóa dữ liệu khám phá của tôi</button></section>' : ''}
    <p class="muted attribution">Lưới khám phá dựng từ dữ liệu © OpenStreetMap contributors (ODbL).</p></div>`;

  // ---------- map data
  function features() {
    const v = s.view;
    if (!v || !s.area) return [];
    const { dlat, dlng } = step();
    if (v.level === 'blocks') {
      const size = v.block_size;
      return v.blocks.map(([bx, by, e, p, n, mine]) => {
        const reachable = e + p;
        return { type: 'Feature', properties: { kind: 'block', ratio: reachable ? Math.min(1, mine / reachable) : 0, water: n ? 1 - reachable / n : 0 },
          geometry: { type: 'Polygon', coordinates: rect(bx * size * dlng, by * size * dlat, (bx + 1) * size * dlng, (by + 1) * size * dlat) } };
      });
    }
    return v.cells.map(([gx, gy, code]) => {
      const id = `${gx}:${gy}`;
      const state = s.unlocked.has(id) ? 'open' : s.demo.has(id) ? 'demo' : code === 'x' ? 'water' : code === 'r' ? 'restricted' : code === 'p' ? 'pending' : 'fog';
      return { type: 'Feature', properties: { kind: 'cell', state }, geometry: { type: 'Polygon', coordinates: rect(gx * dlng, gy * dlat, (gx + 1) * dlng, (gy + 1) * dlat) } };
    });
  }
  function outsideMask() {
    const holes = (s.boundary?.coordinates || []).map(poly => poly[0]);
    return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]], ...holes] } };
  }
  function paintMap() {
    if (!s.map?.getSource('grid')) return;
    s.map.getSource('grid').setData({ type: 'FeatureCollection', features: features() });
    root.querySelector('#mapLevel').textContent = s.view?.level === 'blocks'
      ? 'Đang xem tổng quan theo khối 1 km — phóng to để thấy từng ô 100 m.' : `Đang xem ${s.view?.cells.length.toLocaleString('vi-VN') || 0} ô trong khung nhìn.`;
    drawPins();
  }
  function drawPins() {
    const keep = new Set();
    for (const pin of s.pins) {
      const key = `${pin.id}:${pin.unlocked}`;
      keep.add(key);
      if (s.markers.has(key)) continue;
      const el = document.createElement('button');
      el.type = 'button';
      el.className = `pin-marker ${pin.unlocked ? 'open' : 'glow'}`;
      el.textContent = pin.unlocked ? '★' : '?';
      el.setAttribute('aria-label', pin.unlocked ? `Ghim đã mở: ${pin.reveal_title || pin.teaser}` : `Ghim bí ẩn: ${pin.teaser}`);
      const popup = new window.maplibregl.Popup({ offset: 18 }).setHTML(pin.unlocked
        ? `<span class="found-tag">Đã khám phá</span><b>${esc(pin.reveal_title || pin.teaser)}</b>${pin.reveal_text ? `<p>${esc(pin.reveal_text)}</p>` : ''}${pinActions(pin)}`
        : `<b>Ghim bí ẩn</b><p>${esc(pin.teaser)}</p><small>Đi tới khu vực này để mở khóa</small>`);
      s.markers.set(key, new window.maplibregl.Marker({ element: el }).setLngLat([pin.lng, pin.lat]).setPopup(popup).addTo(s.map));
    }
    for (const [key, marker] of s.markers) if (!keep.has(key)) { marker.remove(); s.markers.delete(key); }
  }
  function flash(id) {
    if (reduced || !s.map?.getSource('flash')) return;
    const [gx, gy] = id.split(':').map(Number);
    const { dlat, dlng } = step();
    s.map.getSource('flash').setData({ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: rect(gx * dlng, gy * dlat, (gx + 1) * dlng, (gy + 1) * dlat) } });
    const started = performance.now();
    const tick = now => {
      if (s.dead || !s.map) return;
      const t = Math.min(1, (now - started) / 1200);
      s.map.setPaintProperty('flash', 'fill-opacity', 0.75 * (1 - t));
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  async function loadView() {
    if (!s.map || s.dead) return;
    const b = s.map.getBounds();
    const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(5)).join(',');
    const level = s.map.getZoom() >= CELL_ZOOM ? 'auto' : 'blocks';
    const id = Symbol('view');
    s.request = id;
    try {
      const data = await api(`/api/m4l/exploration?area=${encodeURIComponent(s.area.slug)}&bbox=${bbox}&level=${level}`);
      if (s.dead || s.request !== id) return;
      s.view = data;
      for (const cid of data.unlocked) s.unlocked.add(cid);
      s.pins = data.pins;
      if (data.progress) s.progress = data.progress;
      paintMap();
      paintPanels();
    } catch (error) {
      if (s.request === id) setStatus(`Chưa tải được lưới: ${error.message}`, 'warn');
    }
  }
  let viewTimer;
  const scheduleView = () => { clearTimeout(viewTimer); viewTimer = setTimeout(loadView, 250); };

  async function initMap(settings) {
    let maplibregl;
    try { maplibregl = await loadMapLibre(); } catch (error) {
      root.querySelector('#fogMap').innerHTML = stateBlock('error', 'Chưa tải được bản đồ', error.message);
      return;
    }
    if (s.dead) return;
    const ring = s.boundary.coordinates.flatMap(poly => poly[0]);
    const xs = ring.map(p => p[0]); const ys = ring.map(p => p[1]);
    s.map = new maplibregl.Map({ container: root.querySelector('#fogMap'), style: baseStyle(settings),
      bounds: [[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], fitBoundsOptions: { padding: 16 },
      maxBounds: [[Math.min(...xs) - 0.3, Math.min(...ys) - 0.3], [Math.max(...xs) + 0.3, Math.max(...ys) + 0.3]],
      attributionControl: { compact: true }, fadeDuration: reduced ? 0 : 300, pixelRatio: Math.min(window.devicePixelRatio || 1, 2) });
    s.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    s.map.on('load', () => {
      if (s.dead) return;
      s.map.addSource('outside', { type: 'geojson', data: outsideMask() });
      s.map.addLayer({ id: 'outside', type: 'fill', source: 'outside', paint: { 'fill-color': '#050f17', 'fill-opacity': 0.82 } });
      s.map.addSource('grid', { type: 'geojson', data: { type: 'FeatureCollection', features: [] }, tolerance: 0 });
      s.map.addLayer({ id: 'fog', type: 'fill', source: 'grid', paint: {
        'fill-color': ['case', ['==', ['get', 'kind'], 'block'], '#0a1c2a',
          ['match', ['get', 'state'], 'water', '#1f5a7a', 'restricted', '#6b2f2f', 'pending', '#132a3c', 'demo', '#2cc6ee', '#0a1c2a']],
        'fill-opacity': ['case', ['==', ['get', 'kind'], 'block'], ['*', 0.86, ['-', 1, ['get', 'ratio']]],
          ['match', ['get', 'state'], 'open', 0, 'demo', 0.25, 'water', 0.45, 'restricted', 0.6, 0.86]],
        'fill-antialias': false } });  // adjacent cells would otherwise show hairline seams through the fog
      s.map.addLayer({ id: 'open-edge', type: 'line', source: 'grid', filter: ['in', ['get', 'state'], ['literal', ['open', 'demo']]],
        paint: { 'line-color': '#3fe0c5', 'line-width': 1.2, 'line-opacity': 0.9 } });
      s.map.addSource('boundary', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: s.boundary } });
      s.map.addLayer({ id: 'boundary', type: 'line', source: 'boundary', paint: { 'line-color': '#3fe0c5', 'line-width': 1.5, 'line-opacity': 0.7 } });
      s.map.addSource('flash', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      s.map.addLayer({ id: 'flash', type: 'fill', source: 'flash', paint: { 'fill-color': '#9ff7e6', 'fill-opacity': 0 } });
      loadView();
    });
    s.map.on('moveend', scheduleView);
    s.map.on('click', event => {
      if (!s.demoMode) return;
      const id = cellId(event.lngLat.lat, event.lngLat.lng);
      const cell = s.view?.level === 'cells' && s.view.cells.find(([gx, gy]) => `${gx}:${gy}` === id);
      if (!cell) { toast(s.view?.level === 'cells' ? 'Ô này nằm ngoài khu vực khám phá' : 'Phóng to để chọn từng ô'); return; }
      if (cell[2] === 'x' || cell[2] === 'r') { toast('Ô này không tính khám phá'); return; }
      s.demo.add(id);
      paintMap();
      flash(id);
    });
  }

  // ---------- exploration (foreground geolocation only)
  async function refreshProgress() {
    if (!user) return;
    const data = await api(`/api/m4l/exploration/progress?area=${encodeURIComponent(s.area.slug)}${s.showUnits ? '&breakdown=unit' : ''}`);
    s.progress = data;
    if (data.units) s.units = data.units;
    paintPanels();
  }
  async function sendSamples() {
    const now = Date.now();
    const { max_accuracy_m: maxAccuracy, min_samples: minSamples } = s.rules;
    s.samples = s.samples.filter(sample => now - sample.t <= SAMPLE_WINDOW_MS);
    const good = s.samples.filter(sample => sample.accuracy <= maxAccuracy);
    if (s.sending || good.length < minSamples || now - s.lastSend < SEND_EVERY_MS) return;
    const latest = good[good.length - 1];
    if (s.unlocked.has(cellId(latest.lat, latest.lng)) && s.lastSend) return;
    s.sending = true;
    s.lastSend = now;
    try {
      const result = await api('/api/m4l/exploration/unlock', { method: 'POST', body: { area: s.area.slug, samples: good.slice(-Math.max(3, minSamples)) } });
      if (s.dead) return;
      s.unlocked.add(result.cell_id);
      s.progress = result.progress;
      if (result.revealed_pins?.length) revealPins(result.revealed_pins);
      if (!result.already_unlocked) {
        toast(result.counted ? 'Đã mở khóa thêm một ô!' : 'Đã ghi nhận ô này (chưa tính vào tỷ lệ vì đường đi chưa được xác minh)');
        flash(result.cell_id);
        loadView();
      }
      setStatus(result.already_unlocked ? 'Ô này bạn đã mở rồi — đi tiếp để mở ô mới.' : 'Đã mở khóa ô hiện tại.', 'ok');
      if (s.showUnits) refreshProgress();
    } catch (error) {
      if (error.status === 401) { stopExploring(); setStatus('Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.', 'warn'); return; }
      setStatus(error.message, 'warn');
    } finally { s.sending = false; }
  }
  function placeMe(lat, lng) {
    if (!s.map) return;
    s.userMarker ??= new window.maplibregl.Marker({ element: Object.assign(document.createElement('span'), { className: 'me-marker' }) }).setLngLat([lng, lat]).addTo(s.map);
    s.userMarker.setLngLat([lng, lat]);
  }
  function onPosition(position) {
    const { latitude: lat, longitude: lng, accuracy } = position.coords;
    s.samples.push({ lat, lng, accuracy, t: position.timestamp || Date.now() });
    s.samples = s.samples.slice(-6);
    placeMe(lat, lng);
    if (accuracy > s.rules.max_accuracy_m) setStatus(`Đang chờ định vị chính xác hơn (sai số ~${Math.round(accuracy)} m, cần ≤ ${s.rules.max_accuracy_m} m). Hãy ra chỗ thoáng và bật “Vị trí chính xác”.`, 'warn');
    sendSamples();
  }
  function geoErrorText(error) {
    return error.code === 1 ? 'Bạn đã từ chối quyền vị trí. Bản đồ vẫn xem được; có thể thử chế độ demo.'
      : error.code === 3 ? 'Lấy vị trí quá lâu. Hãy thử lại ở nơi thoáng.' : 'Thiết bị không xác định được vị trí.';
  }
  function startExploring() {
    if (!navigator.geolocation) { setStatus('Trình duyệt không hỗ trợ định vị. Bạn có thể thử chế độ demo.', 'warn'); return; }
    s.samples = [];
    s.watchId = navigator.geolocation.watchPosition(onPosition, error => {
      // only a denied permission ends the session; unavailable/timeout are often transient (indoors, signal loss)
      if (error.code === 1) stopExploring();
      setStatus(error.code === 1 ? geoErrorText(error) : `${geoErrorText(error)} Vẫn đang thử lại…`, 'warn');
    }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
    setStatus('Đang lấy vị trí… hãy giữ trang này mở khi đi dạo.');
  }
  function stopExploring() {
    if (s.watchId !== null) navigator.geolocation.clearWatch(s.watchId);
    s.watchId = null;
    s.samples = [];
  }
  function onVisibility() {
    if (document.hidden && s.watchId !== null) { stopExploring(); setStatus('Đã tạm dừng định vị vì trang bị ẩn. Bấm bật lại khi tiếp tục.'); }
  }
  document.addEventListener('visibilitychange', onVisibility);

  // ---------- search (existing /api/public/geocode)
  async function search(text) {
    const box = root.querySelector('#mapResults');
    if (!text) { box.hidden = true; return; }
    try {
      const center = s.map?.getCenter();
      const data = await api(`/api/public/geocode?q=${encodeURIComponent(text)}${center ? `&lat=${center.lat.toFixed(4)}&lng=${center.lng.toFixed(4)}` : ''}`);
      s.searchResults = data.items || [];
      box.innerHTML = s.searchResults.length ? s.searchResults.slice(0, 6).map((item, i) => `<button type="button" data-w="goto" data-i="${i}">${esc(item.name || item.label || '')}<small>${esc(item.address || item.label || '')}</small></button>`).join('') : '<p class="muted">Không tìm thấy</p>';
      box.hidden = false;
    } catch (error) { toast(error.message); }
  }

  async function onClick(event) {
    const button = event.target.closest('[data-w]');
    if (event.target.closest('[data-action="shake"]')) setTimeout(paintPanels, 400);
    if (!button) return;
    const action = button.dataset.w;
    if (action === 'explore') { if (s.watchId !== null) { stopExploring(); setStatus('Đã tắt khám phá.'); } else startExploring(); }
    if (action === 'demo') { s.demoMode = !s.demoMode; if (!s.demoMode) s.demo.clear(); paintMap(); setStatus(s.demoMode ? 'Chế độ demo: phóng to rồi chạm vào bản đồ để thắp sáng ô. Không lưu thành tích.' : ''); }
    if (action === 'units') { s.showUnits = !s.showUnits; if (s.showUnits) refreshProgress().catch(error => toast(error.message)); else paintPanels(); }
    if (action === 'fog' && s.map?.getLayer('fog')) {
      s.fog = !s.fog;
      for (const id of ['fog', 'outside']) s.map.setLayoutProperty(id, 'visibility', s.fog ? 'visible' : 'none');
      button.setAttribute('aria-pressed', String(s.fog));
    }
    if (action === 'layers' && s.map?.getLayer('fog')) {
      s.statusLayer = !s.statusLayer;
      s.map.setPaintProperty('fog', 'fill-color', s.statusLayer
        ? ['case', ['==', ['get', 'kind'], 'block'], '#0a1c2a', ['match', ['get', 'state'], 'water', '#1f5a7a', 'restricted', '#6b2f2f', 'pending', '#132a3c', 'demo', '#2cc6ee', '#0a1c2a']]
        : ['case', ['==', ['get', 'state'], 'demo'], '#2cc6ee', '#0a1c2a']);
      button.setAttribute('aria-pressed', String(s.statusLayer));
    }
    if (action === 'overview' && s.map) {
      const ring = s.boundary.coordinates.flatMap(poly => poly[0]);
      s.map.fitBounds([[Math.min(...ring.map(p => p[0])), Math.min(...ring.map(p => p[1]))], [Math.max(...ring.map(p => p[0])), Math.max(...ring.map(p => p[1]))]], { padding: 16, duration: reduced ? 0 : 800 });
    }
    if (action === 'center' && s.map) {
      const latest = s.samples[s.samples.length - 1];
      if (latest) { s.map.flyTo({ center: [latest.lng, latest.lat], zoom: 16, duration: reduced ? 0 : 800 }); return; }
      if (!navigator.geolocation) { setStatus('Trình duyệt không hỗ trợ định vị.', 'warn'); return; }
      navigator.geolocation.getCurrentPosition(position => {
        placeMe(position.coords.latitude, position.coords.longitude);
        s.map.flyTo({ center: [position.coords.longitude, position.coords.latitude], zoom: 16, duration: reduced ? 0 : 800 });
      }, error => setStatus(geoErrorText(error), 'warn'), { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 });
    }
    if (action === 'goto') {
      const item = s.searchResults[Number(button.dataset.i)];
      root.querySelector('#mapResults').hidden = true;
      if (item && s.map) s.map.flyTo({ center: [item.lng, item.lat], zoom: 16, duration: reduced ? 0 : 800 });
    }
    if (action === 'forget' && confirm('Xóa toàn bộ ô đã mở và vị trí gần nhất của bạn? Không thể hoàn tác.')) {
      try {
        await api('/api/m4l/exploration/me', { method: 'DELETE' });
        stopExploring();
        s.unlocked.clear();
        await refreshProgress();
        loadView();
        toast('Đã xóa dữ liệu khám phá');
      } catch (error) { toast(error.message); }
    }
  }
  root.addEventListener('click', onClick);
  root.querySelector('#mapSearch').addEventListener('submit', event => { event.preventDefault(); search(root.querySelector('#mapQuery').value.trim()); });

  async function load() {
    const [first, boot] = await Promise.all([api('/api/m4l/exploration?level=blocks'), api('/api/public/bootstrap').catch(() => ({}))]);
    if (s.dead) return;
    s.area = first.area;
    s.rules = first.rules;
    s.progress = first.progress;
    s.view = first;
    s.pins = first.pins;
    const bound = await api(`/api/m4l/areas/${encodeURIComponent(s.area.slug)}/boundary`);
    if (s.dead) return;
    s.boundary = bound.boundary;
    paintPanels();
    await initMap(boot?.settings);
  }
  load().catch(error => {
    if (s.dead) return;
    root.querySelector('.world-page').innerHTML = error.code === 'AREA_NOT_FOUND'
      ? stateBlock('empty', 'Chưa có khu vực khám phá', 'Ban quản trị chưa bật khu vực khám phá nào.', '<a class="btn primary" href="/m4l" data-link>Về trang chủ</a>')
      : stateBlock('error', 'Chưa tải được bản đồ', error.message, '<button type="button" class="btn primary" data-action="retry-home">Thử lại</button>');
  });

  return {
    unmount() {
      s.dead = true;
      clearTimeout(viewTimer);
      stopExploring();
      document.removeEventListener('visibilitychange', onVisibility);
      root.removeEventListener('click', onClick);
      s.map?.remove();
    },
  };
}
