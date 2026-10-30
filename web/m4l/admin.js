import { moodIcon } from '/m4l/mood-icons.js';
import { demoInfo, staffToken } from '/m4l/demo-mode.js';

const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const state = { token: null, user: null, moods: [], icons: [], canEdit: false, editing: null, pois: [], poiTotal: 0, query: '', areas: [], canEditAreas: false, pins: [], pinAreas: [], stats: null, changes: [], zones: [], zoneArea: '', canEditZones: false, inspect: null,
  campaigns: [], campaignFilter: 'pending', kiosks: [], kioskRadius: 0, issuedKey: null, analytics: null };
const STATUS = { draft: 'Nháp', pending: 'Chờ duyệt', approved: 'Đã duyệt', rejected: 'Bị từ chối', paused: 'Tạm dừng', ended: 'Đã kết thúc' };
const ACTIONS = { pending: [['approve', 'Duyệt'], ['reject', 'Từ chối']], approved: [['pause', 'Tạm dừng'], ['end', 'Kết thúc']], paused: [['resume', 'Chạy lại'], ['end', 'Kết thúc']] };
const FUNNEL = [['impression', 'Hiển thị'], ['qr_scan', 'Quét QR tại trạm'], ['claim', 'Nhận voucher'], ['nav_click', 'Bấm chỉ đường'], ['redeem', 'Đổi tại quầy']];
const date = epoch => epoch ? new Date(epoch * 1000).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : '—';
const fmt = value => Number(value || 0).toLocaleString('vi-VN');
let toastTimer;
try { state.token = staffToken() || localStorage.getItem('x24_cms_token'); } catch { /* storage blocked */ }

async function api(path, options = {}) {
  const headers = { Authorization: `Bearer ${state.token}` };
  const init = { method: options.method || 'GET', headers };
  if (options.body) { headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(options.body); }
  const response = await fetch(path, init);
  const result = await response.json().catch(() => ({}));
  if (!response.ok) { const error = new Error(result.error || `Lỗi ${response.status}`); error.status = response.status; error.code = result.code; throw error; }
  return result;
}
function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { element.hidden = true; }, 4000);
}
function blocked(title, message) {
  $('#view').innerHTML = `<div class="state-block error"><h3>${esc(title)}</h3><p>${esc(message)}</p><div class="state-actions"><a class="btn primary" href="/hrm/login?next=/m4l/admin">Đăng nhập quản trị</a></div></div>`;
  demoInfo.then(demo => { if (demo) $('#view .state-actions').insertAdjacentHTML('afterbegin', '<a class="btn primary" href="/demo?as=manager">Vào quản trị demo</a>'); });
}

function moodsPanel() {
  const rows = state.moods.map(mood => `<tr><td>${moodIcon(mood.icon, 20)}</td><td><b>${esc(mood.name)}</b><br><span class="muted">${esc(mood.slug)}</span></td><td class="status-${mood.status}">${mood.status === 'active' ? 'Đang bật' : 'Đã tắt'}</td><td>${mood.sort_order}</td><td>${mood.poi_count}</td>${state.canEdit ? `<td><button type="button" class="btn small ghost" data-action="edit" data-id="${mood.id}">Sửa</button></td>` : ''}</tr>`).join('');
  const editing = state.moods.find(mood => mood.id === state.editing);
  const form = state.canEdit ? `<form class="mood-form" id="moodForm">
      <label class="field"><span>Slug ${editing ? '(không đổi được)' : ''}</span><input class="admin-input" name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" maxlength="60" value="${esc(editing?.slug || '')}" ${editing ? 'disabled' : ''}></label>
      <label class="field"><span>Tên mood</span><input class="admin-input" name="name" required maxlength="80" value="${esc(editing?.name || '')}"></label>
      <label class="field"><span>Biểu tượng</span><select class="admin-input" name="icon">${state.icons.map(key => `<option value="${key}" ${(editing?.icon || 'compass') === key ? 'selected' : ''}>${key}</option>`).join('')}</select></label>
      <label class="field"><span>Thứ tự</span><input class="admin-input" name="sort_order" type="number" min="-1000" max="1000" value="${editing?.sort_order ?? 0}"></label>
      <label class="field"><span>Trạng thái</span><select class="admin-input" name="status"><option value="active" ${editing?.status !== 'inactive' ? 'selected' : ''}>Đang bật</option><option value="inactive" ${editing?.status === 'inactive' ? 'selected' : ''}>Đã tắt</option></select></label>
      <label class="field" style="grid-column:1/-1"><span>Mô tả</span><input class="admin-input" name="description" maxlength="300" value="${esc(editing?.description || '')}"></label>
      <div class="state-actions" style="grid-column:1/-1;justify-content:flex-start"><button class="btn primary" type="submit">${editing ? 'Lưu thay đổi' : 'Thêm mood'}</button>${editing ? '<button type="button" class="btn ghost" data-action="cancel-edit">Hủy</button>' : ''}</div>
    </form>` : '<p class="muted">Chỉ Quản trị hệ thống (S0) được thêm hoặc sửa mood.</p>';
  return `<section class="panel"><h2>Danh mục mood</h2><div class="table-wrap"><table><thead><tr><th></th><th>Mood</th><th>Trạng thái</th><th>Thứ tự</th><th>Địa điểm</th>${state.canEdit ? '<th></th>' : ''}</tr></thead><tbody>${rows || '<tr><td colspan="6" class="muted">Chưa có mood</td></tr>'}</tbody></table></div>${form}</section>`;
}

function poiRow(poi) {
  const linked = new Map(poi.moods.map(item => [item.id, item.reason]));
  return `<form class="poi-row" data-poi="${poi.id}"><h3>${esc(poi.name)} ${poi.status !== 'published' ? '<span class="muted">(đang ẩn)</span>' : ''}</h3><p>${esc([poi.ward_name, poi.address].filter(Boolean).join(' · '))}</p>
    ${state.moods.map(mood => `<div class="mood-pick"><label><input type="checkbox" name="mood" value="${mood.id}" ${linked.has(mood.id) ? 'checked' : ''}> ${esc(mood.name)}${mood.status === 'inactive' ? ' <span class="muted">(tắt)</span>' : ''}</label><input class="admin-input" name="reason-${mood.id}" maxlength="200" placeholder="Lý do phù hợp (hiển thị cho người dùng)" value="${esc(linked.get(mood.id) || '')}" aria-label="Lý do ${esc(poi.name)} phù hợp ${esc(mood.name)}"></div>`).join('')}
    <button class="btn small primary" type="submit">Lưu mood cho địa điểm</button></form>`;
}
function poisPanel() {
  return `<section class="panel"><h2>Gán mood cho địa điểm</h2><p class="muted">Chỉ địa điểm thật trong khu vực bạn được giao. Địa điểm hiện cho người dùng khi đã công khai và mood đang bật.</p>
    <form id="poiSearch" class="search" role="search" style="max-width:none;margin:10px 0"><label class="sr-only" for="poiQuery">Tìm địa điểm</label><input id="poiQuery" type="search" placeholder="Tìm theo tên, địa chỉ, phường" value="${esc(state.query)}"></form>
    <p class="muted">${state.poiTotal > state.pois.length ? `Hiển thị ${state.pois.length}/${state.poiTotal} — hãy thu hẹp từ khóa.` : `${state.poiTotal} địa điểm`}</p>
    ${state.pois.map(poiRow).join('') || '<p class="muted">Không có địa điểm phù hợp.</p>'}</section>`;
}
function areasPanel() {
  const rows = state.areas.map(area => `<tr><td><b>${esc(area.name)}</b><br><span class="muted">${esc(area.slug)} · ${esc(area.ward_slugs.join(', '))}</span></td><td>${area.cell_size_m} m</td><td>v${area.grid_version}</td><td>${area.eligible_cell_count}</td><td class="status-${area.status}">${area.status === 'active' ? 'Đang bật' : 'Đã tắt'}</td>
    ${state.canEditAreas ? `<td><form class="inline-form" data-regen="${area.id}"><input class="admin-input" name="cell_size_m" type="number" min="50" max="500" value="${area.cell_size_m}" aria-label="Kích thước ô (m)"><button class="btn small ghost" type="submit">Tạo lại lưới</button></form>
      <button type="button" class="btn small ghost" data-action="area-status" data-id="${area.id}" data-status="${area.status === 'active' ? 'inactive' : 'active'}">${area.status === 'active' ? 'Tắt' : 'Bật'}</button></td>` : ''}</tr>`).join('');
  const form = state.canEditAreas ? `<form class="mood-form" id="areaForm">
      <label class="field"><span>Slug</span><input class="admin-input" name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" maxlength="60"></label>
      <label class="field"><span>Tên khu vực</span><input class="admin-input" name="name" required maxlength="80"></label>
      <label class="field"><span>Mã phường (phân cách dấu phẩy)</span><input class="admin-input" name="wards" required placeholder="cau-giay"></label>
      <label class="field"><span>Kích thước ô (m)</span><input class="admin-input" name="cell_size_m" type="number" min="50" max="500" value="100"></label>
      <div class="state-actions" style="grid-column:1/-1;justify-content:flex-start"><button class="btn primary" type="submit">Thêm khu vực</button></div></form>
      <p class="muted">Tạo lại lưới tăng phiên bản: tiến độ tính lại theo lưới mới (ô cũ vẫn được lưu).</p>` : '<p class="muted">Chỉ Quản trị hệ thống (S0) được thêm hoặc đổi lưới khu vực.</p>';
  return `<section class="panel"><h2>Khu vực khám phá (Fog of War)</h2><div class="table-wrap"><table><thead><tr><th>Khu vực</th><th>Ô</th><th>Lưới</th><th>Số ô</th><th>Trạng thái</th>${state.canEditAreas ? '<th></th>' : ''}</tr></thead><tbody>${rows || '<tr><td colspan="6" class="muted">Chưa có khu vực</td></tr>'}</tbody></table></div>${form}</section>`;
}
const PIN_STATUS = { draft: 'Bản nháp', published: 'Đã xuất bản', archived: 'Đã lưu trữ' };
function pinsPanel() {
  if (!state.pinAreas.length) return '<section class="panel"><h2>Ghim bí ẩn</h2><p class="muted">Không có khu vực nào nằm trọn trong phạm vi bạn được giao.</p></section>';
  const areaName = id => state.pinAreas.find(area => area.id === id)?.name || id;
  const rows = state.pins.map(pin => `<tr><td><b>${esc(pin.teaser)}</b><br><span class="muted">${esc(pin.reveal_title || '')}</span></td><td>${esc(areaName(pin.area_id))}</td><td>${Number(pin.lat).toFixed(5)}, ${Number(pin.lng).toFixed(5)}${pin.poi_id ? `<br><span class="muted">POI #${pin.poi_id}</span>` : ''}</td><td>${PIN_STATUS[pin.status]}</td>
    <td>${pin.status !== 'published' ? `<button type="button" class="btn small ghost" data-action="pin-status" data-id="${pin.id}" data-status="published">Xuất bản</button>` : ''}${pin.status !== 'archived' ? `<button type="button" class="btn small ghost" data-action="pin-status" data-id="${pin.id}" data-status="archived">Lưu trữ</button>` : ''}</td></tr>`).join('');
  return `<section class="panel"><h2>Ghim bí ẩn</h2><div class="table-wrap"><table><thead><tr><th>Ghim</th><th>Khu vực</th><th>Vị trí</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows || '<tr><td colspan="5" class="muted">Chưa có ghim</td></tr>'}</tbody></table></div>
    <form class="mood-form" id="pinForm">
      <label class="field"><span>Khu vực</span><select class="admin-input" name="area">${state.pinAreas.map(area => `<option value="${esc(area.slug)}">${esc(area.name)}</option>`).join('')}</select></label>
      <label class="field"><span>Vĩ độ</span><input class="admin-input" name="lat" inputmode="decimal" placeholder="Bỏ trống nếu dùng POI"></label>
      <label class="field"><span>Kinh độ</span><input class="admin-input" name="lng" inputmode="decimal"></label>
      <label class="field"><span>Mã POI (tùy chọn)</span><input class="admin-input" name="poi_id" type="number" min="1"></label>
      <label class="field" style="grid-column:1/-1"><span>Lời gợi ý khi còn khóa (hiện công khai)</span><input class="admin-input" name="teaser" required maxlength="120"></label>
      <label class="field"><span>Tiêu đề sau khi mở</span><input class="admin-input" name="reveal_title" maxlength="120"></label>
      <label class="field"><span>Nội dung sau khi mở</span><input class="admin-input" name="reveal_text" maxlength="500"></label>
      <label class="field"><span>Trạng thái</span><select class="admin-input" name="status"><option value="draft">Bản nháp</option><option value="published">Xuất bản ngay</option></select></label>
      <div class="state-actions" style="grid-column:1/-1;justify-content:flex-start"><button class="btn primary" type="submit">Thêm ghim</button></div></form>
    <p class="muted">Chỉ đặt ghim ở nơi công cộng, an toàn và đi bộ tới được.</p></section>`;
}
const STATUS_LABEL = { eligible: 'Hợp lệ (tính tiến độ)', pending_review: 'Chờ xác minh đường đi', excluded: 'Mặt nước (loại trừ)', restricted: 'Khu hạn chế' };
const pct = value => `${Number(value || 0).toLocaleString('vi-VN', { maximumFractionDigits: 4 })}%`;
function statsPanel() {
  const st = state.stats;
  if (!st) return '';
  const options = state.areas.map(area => `<option value="${area.id}" ${area.id === st.area.id ? 'selected' : ''}>${esc(area.name)} (${area.kind === 'city' ? 'toàn thành phố' : 'pilot'})</option>`).join('');
  const totals = Object.entries(STATUS_LABEL).map(([key, label]) => `<tr><td>${label}</td><td>${(st.totals[key] || 0).toLocaleString('vi-VN')}</td><td>${pct(100 * (st.totals[key] || 0) / st.cells)}</td></tr>`).join('');
  const units = st.units.map(unit => `<tr><td>${esc(unit.name)}</td><td>${unit.cells.toLocaleString('vi-VN')}</td><td>${unit.eligible.toLocaleString('vi-VN')}</td><td>${unit.pending_review.toLocaleString('vi-VN')}</td><td>${unit.excluded.toLocaleString('vi-VN')}</td><td>${unit.restricted.toLocaleString('vi-VN')}</td><td>${unit.covered}</td><td>${unit.explorers}</td></tr>`).join('');
  const meta = st.meta || {};
  const changes = state.changes.slice(0, 15).map(change => `<li><b>${esc(change.action)}</b> · lưới v${change.grid_version} · phân loại v${change.classification_version} · ${esc(change.actor)} · ${new Date(change.created_at * 1000).toLocaleString('vi-VN')}</li>`).join('');
  return `<section class="panel"><h2>Thống kê khám phá</h2><label class="field"><span>Khu vực</span><select class="admin-input" id="statsArea">${options}</select></label>
    <p class="muted">${st.cells.toLocaleString('vi-VN')} ô · ${st.explorers} người đã khám phá · ${st.covered_eligible.toLocaleString('vi-VN')} ô hợp lệ đã có người mở (${pct(st.coverage_percentage)}) · lưới v${st.area.grid_version}, phân loại v${st.area.classification_version}</p>
    <div class="table-wrap"><table><thead><tr><th>Trạng thái ô</th><th>Số ô</th><th>Tỷ lệ</th></tr></thead><tbody>${totals}</tbody></table></div>
    ${meta.source ? `<p class="muted">Nguồn: ${esc(meta.source)}<br>Giấy phép: ${esc(meta.license || '')}${meta.osm_timestamp ? `<br>Dữ liệu OSM tại: ${esc(meta.osm_timestamp)}` : ''}${meta.admin_note ? `<br>${esc(meta.admin_note)}` : ''}</p>` : ''}
    <details><summary>Theo phường/xã (${st.units.length})</summary><div class="table-wrap scroll-box"><table><thead><tr><th>Đơn vị</th><th>Ô</th><th>Hợp lệ</th><th>Chờ</th><th>Nước</th><th>Hạn chế</th><th>Đã có người mở</th><th>Người khám phá</th></tr></thead><tbody>${units}</tbody></table></div></details>
    <details><summary>Nhật ký thay đổi lưới (${state.changes.length})</summary><ul class="change-list">${changes || '<li class="muted">Chưa có</li>'}</ul></details></section>`;
}
function geoToolsPanel() {
  const r = state.inspect;
  const result = r ? `<ul class="change-list">${r.areas.map(a => `<li><b>${esc(a.area)}</b>: ô ${esc(a.cell_id)} · ${a.in_area ? `${STATUS_LABEL[a.status] || a.status}${a.unit ? ` · ${esc(a.unit.name || a.unit.slug)}` : ''}` : 'ngoài khu vực'}</li>`).join('')}<li>Phường trong CSDL Xanh24: ${esc(r.xanh24_ward || 'không thuộc 51 phường đã số hóa')}</li></ul>` : '';
  const zones = state.zones.map(zone => `<tr><td><b>${esc(zone.name)}</b><br><span class="muted">${esc(zone.source)}</span></td><td>${zone.kind === 'restricted' ? 'Hạn chế' : 'Loại trừ'}</td><td>${zone.active ? 'Đang áp dụng' : 'Đã tắt'}</td>
    ${state.canEditZones ? `<td><button type="button" class="btn small ghost" data-action="zone-active" data-id="${zone.id}" data-active="${zone.active ? 0 : 1}">${zone.active ? 'Tắt' : 'Bật'}</button></td>` : ''}</tr>`).join('');
  const zoneForm = state.canEditZones ? `<form class="mood-form" id="zoneForm">
      <label class="field"><span>Tên vùng</span><input class="admin-input" name="name" required maxlength="120"></label>
      <label class="field"><span>Loại</span><select class="admin-input" name="kind"><option value="restricted">Khu hạn chế</option><option value="excluded">Không thể tiếp cận / loại trừ</option></select></label>
      <label class="field" style="grid-column:1/-1"><span>Nguồn căn cứ (bắt buộc)</span><input class="admin-input" name="source" required maxlength="300" placeholder="Văn bản, bản đồ hoặc dữ liệu chứng minh"></label>
      <label class="field" style="grid-column:1/-1"><span>Hình học GeoJSON (Polygon / MultiPolygon)</span><textarea class="admin-input" name="geometry" rows="4" required></textarea></label>
      <div class="state-actions" style="grid-column:1/-1;justify-content:flex-start"><button class="btn primary" type="submit">Áp dụng vùng</button></div></form>` : '';
  return `<section class="panel"><h2>Kiểm tra dữ liệu địa lý</h2>
    <form class="mood-form" id="inspectForm"><label class="field"><span>Vĩ độ</span><input class="admin-input" name="lat" required inputmode="decimal"></label><label class="field"><span>Kinh độ</span><input class="admin-input" name="lng" required inputmode="decimal"></label>
      <div class="state-actions" style="grid-column:1/-1;justify-content:flex-start"><button class="btn primary" type="submit">Tọa độ này thuộc ô nào?</button></div></form>${result}
    <h2 style="margin-top:18px">Vùng hạn chế / loại trừ (${esc(state.zoneArea || '')})</h2><p class="muted">Mỗi lần bật/tắt vùng sẽ tăng phiên bản phân loại và tính lại mẫu số tiến độ; có ghi nhật ký.</p>
    <div class="table-wrap"><table><thead><tr><th>Vùng</th><th>Loại</th><th>Trạng thái</th>${state.canEditZones ? '<th></th>' : ''}</tr></thead><tbody>${zones || '<tr><td colspan="4" class="muted">Chưa có vùng</td></tr>'}</tbody></table></div>${zoneForm}</section>`;
}
// ---------------------------------------------------------------- commerce (S0 everywhere, AREA within its wards)
function campaignsPanel() {
  const rows = state.campaigns.filter(c => !state.campaignFilter || c.status === state.campaignFilter).map(c => `<tr>
    <td><b>${esc(c.name)}</b>${c.is_demo ? ' <span class="badge demo">DEMO</span>' : ''}<br><span class="muted">${esc(c.kind_label)}${c.mood_name ? ` · ${esc(c.mood_name)}` : ''}${c.exclusive ? ' · độc quyền' : ''}</span></td>
    <td>${esc(c.poi_name)}<br><span class="muted">${esc(c.partner_name || '')} · ${esc(c.ward_slug || '')}</span></td>
    <td>${c.radius_m ? `${fmt(c.radius_m)} m` : 'Toàn TP'}<br><span class="muted">ưu tiên ${c.priority}</span></td>
    <td>${date(c.starts_at)}<br>${date(c.ends_at)}</td>
    <td>${c.voucher ? `${esc(c.voucher.title)}<br><span class="muted">${c.voucher.ttl_minutes} phút · ${fmt(c.voucher.issued_count)}/${fmt(c.voucher.issue_cap)}</span>` : '<span class="muted">—</span>'}</td>
    <td><span class="badge status-${c.status}">${STATUS[c.status]}</span>${c.live ? '<br><span class="status-active">Đang chạy</span>' : ''}${c.review_note ? `<br><span class="muted">${esc(c.review_note)}</span>` : ''}</td>
    <td>${(ACTIONS[c.status] || []).map(([action, label]) => `<button type="button" class="btn small ${action === 'approve' || action === 'resume' ? 'primary' : 'ghost'}" data-action="review" data-id="${c.id}" data-review="${action}">${label}</button>`).join(' ')}</td></tr>`).join('');
  const filters = [['pending', 'Chờ duyệt'], ['approved', 'Đã duyệt'], ['paused', 'Tạm dừng'], ['rejected', 'Từ chối'], ['ended', 'Kết thúc'], ['', 'Tất cả']];
  return `<section class="panel wide-panel"><h2>Chiến dịch đối tác</h2>
    <p class="muted">Duyệt tài trợ mood, Random VIP và kiosk O2O. Hệ thống kiểm tra mood của địa điểm, độc quyền trùng vùng/thời gian, đối tác bị khóa và hạn chiến dịch. Không có thanh toán trong hệ thống.</p>
    <div class="chip-row" role="group" aria-label="Lọc theo trạng thái">${filters.map(([key, label]) => `<button type="button" class="chip" data-action="camp-filter" data-status="${key}" aria-pressed="${state.campaignFilter === key}">${label} (${key ? state.campaigns.filter(c => c.status === key).length : state.campaigns.length})</button>`).join('')}</div>
    <div class="table-wrap"><table><thead><tr><th>Chiến dịch</th><th>Đối tác</th><th>Phạm vi</th><th>Thời gian</th><th>Voucher</th><th>Trạng thái</th><th></th></tr></thead><tbody>${rows || '<tr><td colspan="7" class="muted">Không có chiến dịch</td></tr>'}</tbody></table></div></section>`;
}
function kiosksPanel() {
  const rows = state.kiosks.map(k => `<tr><td><b>${esc(k.name)}</b><br><span class="muted">${esc(k.code)} · ${esc(k.ward_slug || '')}</span></td>
    <td>${k.lat != null ? `${k.lat.toFixed(5)}, ${k.lng.toFixed(5)}` : '<span class="muted">Chưa có tọa độ</span>'}</td>
    <td>${k.active ? '<span class="status-active">Hoạt động</span>' : '<span class="status-inactive">Tạm ngưng</span>'}</td>
    <td>${k.has_key ? `Đã cấp (${esc(k.key_prefix)}…)<br><span class="muted">${date(k.key_created_at)}</span>` : '<span class="muted">Chưa cấp</span>'}</td>
    <td><button type="button" class="btn small ghost" data-action="kiosk-key" data-id="${k.id}">${k.has_key ? 'Cấp lại khóa' : 'Cấp khóa'}</button>${k.has_key ? ` <button type="button" class="btn small ghost" data-action="kiosk-revoke" data-id="${k.id}">Thu hồi</button>` : ''}</td></tr>`).join('');
  const issued = state.issuedKey ? `<div class="key-box" role="alert"><b>Khóa cho kiosk ${esc(state.issuedKey.code)} (chỉ hiện một lần):</b><code>${esc(state.issuedKey.key)}</code><span class="muted">Mở /m4l/station trên màn hình trạm, nhập mã kiosk và khóa này.</span></div>` : '';
  return `<section class="panel"><h2>Kiosk O2O</h2><p class="muted">Mỗi trạm dùng khóa riêng để sinh mã check-in ngắn hạn, dùng một lần. Bán kính gợi ý đối tác: ${fmt(state.kioskRadius)} m (cấu hình).</p>${issued}
    <div class="table-wrap"><table><thead><tr><th>Kiosk</th><th>Tọa độ</th><th>Trạng thái</th><th>Khóa</th><th></th></tr></thead><tbody>${rows || '<tr><td colspan="5" class="muted">Không có kiosk trong phạm vi</td></tr>'}</tbody></table></div></section>`;
}
function analyticsPanel() {
  const a = state.analytics;
  if (!a) return '<section class="panel"><h2>Phân tích chuyển đổi</h2><p class="muted">Đang tải…</p></section>';
  const tiles = FUNNEL.map(([key, label]) => `<div><dt>${label}</dt><dd>${fmt(a.totals[key])}</dd></div>`).join('');
  const vouchers = Object.entries({ issued: 'Còn hạn', redeemed: 'Đã đổi', expired: 'Hết hạn', revoked: 'Thu hồi' }).map(([key, label]) => `${label}: <b>${fmt(a.vouchers[key])}</b>`).join(' · ');
  const rows = a.campaigns.map(c => `<tr><td>${esc(c.name)}${c.is_demo ? ' <span class="badge demo">DEMO</span>' : ''}<br><span class="muted">${esc(c.poi_name || '')}</span></td>${FUNNEL.filter(([k]) => k !== 'qr_scan').map(([k]) => `<td>${fmt(c[k])}</td>`).join('')}<td>${c.claim ? `${Math.round(100 * (c.redeem || 0) / c.claim)}%` : '—'}</td></tr>`).join('');
  return `<section class="panel wide-panel"><h2>Phân tích chuyển đổi (${a.days} ngày)</h2><dl class="funnel">${tiles}</dl><p>Voucher: ${vouchers}</p>
    <p class="muted">${esc(a.note)} Dữ liệu chỉ ở dạng tổng hợp, không kèm danh tính người dùng.</p>
    <div class="table-wrap"><table><thead><tr><th>Chiến dịch</th><th>Hiển thị</th><th>Nhận</th><th>Chỉ đường</th><th>Đổi</th><th>Đổi/Nhận</th></tr></thead><tbody>${rows || '<tr><td colspan="6" class="muted">Chưa có số liệu</td></tr>'}</tbody></table></div></section>`;
}
async function loadCommerce() {
  const [campaigns, kiosks, analytics] = await Promise.all([api('/api/m4l/admin/campaigns'), api('/api/m4l/admin/kiosks'), api('/api/m4l/admin/analytics')]);
  Object.assign(state, { campaigns: campaigns.items, kiosks: kiosks.items, kioskRadius: kiosks.radius_m, analytics });
}
const can = (...roles) => roles.includes(state.user?.role);
function render() {
  const commerce = can('S0', 'AREA') ? `${campaignsPanel()}${analyticsPanel()}${kiosksPanel()}` : '';
  const content = can('S0', 'CONTENT') ? `${statsPanel()}${geoToolsPanel()}${moodsPanel()}${poisPanel()}${areasPanel()}${pinsPanel()}` : '';
  $('#view').innerHTML = `<div class="page-head"><p class="eyebrow">M4L · Quản trị</p><h1>${can('AREA') ? 'Đối tác, voucher &amp; kiosk' : 'Mood, địa điểm, khám phá &amp; đối tác'}</h1></div><div class="admin-grid">${commerce}${content}</div>`;
}
async function loadStats(areaId) {
  const id = areaId || state.stats?.area.id || (state.areas.find(area => area.kind === 'city') || state.areas[0])?.id;
  if (!id) return;
  const [stats, changes] = await Promise.all([api(`/api/m4l/admin/areas/${id}/stats`), api(`/api/m4l/admin/areas/${id}/changes`)]);
  const zones = await api(`/api/m4l/admin/zones?area=${encodeURIComponent(stats.area.slug)}`);
  Object.assign(state, { stats, changes: changes.items, zones: zones.items, zoneArea: zones.area, canEditZones: zones.can_edit });
}

async function loadMoods() {
  const data = await api('/api/m4l/admin/moods');
  Object.assign(state, { moods: data.items, icons: data.icons, canEdit: data.can_edit });
}
async function loadPois() {
  const data = await api(`/api/m4l/admin/pois?q=${encodeURIComponent(state.query)}`);
  state.pois = data.items;
  state.poiTotal = data.total;
}
async function loadExploration() {
  const [areas, pins] = await Promise.all([api('/api/m4l/admin/areas'), api('/api/m4l/admin/pins')]);
  Object.assign(state, { areas: areas.items, canEditAreas: areas.can_edit, pins: pins.items, pinAreas: pins.areas });
}

document.addEventListener('click', event => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  if (button.dataset.action === 'camp-filter') { state.campaignFilter = button.dataset.status; render(); return; }
  if (button.dataset.action === 'review') {
    const action = button.dataset.review;
    const note = action === 'reject' ? prompt('Lý do từ chối (bắt buộc, đối tác sẽ thấy):') : action === 'approve' ? '' : (prompt('Ghi chú (tùy chọn):') ?? null);
    if (note === null || (action === 'reject' && !note.trim())) return;
    api(`/api/m4l/admin/campaigns/${button.dataset.id}/review`, { method: 'POST', body: { action, note } })
      .then(loadCommerce).then(() => { render(); toast('Đã cập nhật chiến dịch'); }).catch(error => toast(error.message));
    return;
  }
  if (button.dataset.action === 'kiosk-key') {
    if (!confirm('Cấp khóa mới sẽ vô hiệu khóa cũ của kiosk này. Tiếp tục?')) return;
    const kiosk = state.kiosks.find(k => String(k.id) === button.dataset.id);
    api(`/api/m4l/admin/kiosks/${button.dataset.id}/key`, { method: 'POST' })
      .then(result => { state.issuedKey = { code: kiosk?.code, key: result.key }; return loadCommerce(); }).then(render).catch(error => toast(error.message));
    return;
  }
  if (button.dataset.action === 'kiosk-revoke') {
    if (!confirm('Thu hồi khóa: màn hình trạm sẽ ngừng hiển thị mã check-in. Tiếp tục?')) return;
    api(`/api/m4l/admin/kiosks/${button.dataset.id}/key`, { method: 'DELETE' }).then(loadCommerce).then(() => { state.issuedKey = null; render(); toast('Đã thu hồi khóa'); }).catch(error => toast(error.message));
    return;
  }
  if (button.dataset.action === 'edit') { state.editing = Number(button.dataset.id); render(); $('#moodForm [name=name]').focus(); }
  if (button.dataset.action === 'cancel-edit') { state.editing = null; render(); }
  if (button.dataset.action === 'zone-active') {
    api(`/api/m4l/admin/zones/${button.dataset.id}`, { method: 'PUT', body: { active: button.dataset.active === '1' } })
      .then(() => Promise.all([loadExploration(), loadStats()])).then(() => { render(); toast('Đã tính lại phân loại ô'); }).catch(error => toast(error.message));
  }
  if (button.dataset.action === 'area-status' || button.dataset.action === 'pin-status') {
    const path = button.dataset.action === 'area-status' ? 'areas' : 'pins';
    api(`/api/m4l/admin/${path}/${button.dataset.id}`, { method: 'PUT', body: { status: button.dataset.status } })
      .then(loadExploration).then(() => { render(); toast('Đã cập nhật'); }).catch(error => toast(error.message));
  }
});
document.addEventListener('change', event => {
  if (event.target.id === 'statsArea') loadStats(Number(event.target.value)).then(render).catch(error => toast(error.message));
});
document.addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  try {
    if (form.id === 'moodForm') {
      const values = Object.fromEntries(new FormData(form));
      values.sort_order = Number(values.sort_order || 0);
      if (state.editing) { delete values.slug; await api(`/api/m4l/admin/moods/${state.editing}`, { method: 'PUT', body: values }); }
      else await api('/api/m4l/admin/moods', { method: 'POST', body: values });
      toast(state.editing ? 'Đã lưu mood' : 'Đã thêm mood');
      state.editing = null;
      await Promise.all([loadMoods(), loadPois()]);
      render();
    } else if (form.id === 'poiSearch') {
      state.query = $('#poiQuery').value.trim();
      await loadPois();
      render();
      $('#poiQuery').focus();
    } else if (form.id === 'areaForm') {
      const values = Object.fromEntries(new FormData(form));
      await api('/api/m4l/admin/areas', { method: 'POST', body: { slug: values.slug, name: values.name, cell_size_m: Number(values.cell_size_m),
        ward_slugs: values.wards.split(',').map(item => item.trim()).filter(Boolean) } });
      toast('Đã tạo khu vực và lưới');
      await loadExploration();
      render();
    } else if (form.dataset.regen) {
      if (!confirm('Tạo lại lưới sẽ tính lại tiến độ của mọi người dùng ở khu vực này. Tiếp tục?')) return;
      await api(`/api/m4l/admin/areas/${form.dataset.regen}/regenerate`, { method: 'POST', body: { cell_size_m: Number(new FormData(form).get('cell_size_m')) } });
      toast('Đã tạo lại lưới');
      await loadExploration();
      render();
    } else if (form.id === 'inspectForm') {
      const values = Object.fromEntries(new FormData(form));
      state.inspect = await api('/api/m4l/admin/inspect', { method: 'POST', body: { lat: Number(values.lat), lng: Number(values.lng) } });
      render();
    } else if (form.id === 'zoneForm') {
      const values = Object.fromEntries(new FormData(form));
      let geometry;
      try { geometry = JSON.parse(values.geometry); } catch { toast('GeoJSON không hợp lệ'); return; }
      if (geometry.type === 'Feature') geometry = geometry.geometry;
      const result = await api('/api/m4l/admin/zones', { method: 'POST', body: { area: state.zoneArea, name: values.name, kind: values.kind, source: values.source, geometry } });
      toast(`Đã áp dụng vùng · phân loại v${result.change.classification_version}`);
      await Promise.all([loadExploration(), loadStats()]);
      render();
    } else if (form.id === 'pinForm') {
      const values = Object.fromEntries(new FormData(form));
      const body = { area: values.area, teaser: values.teaser, reveal_title: values.reveal_title, reveal_text: values.reveal_text, status: values.status };
      if (values.poi_id) body.poi_id = Number(values.poi_id);
      if (values.lat || values.lng) { body.lat = Number(values.lat); body.lng = Number(values.lng); }
      await api('/api/m4l/admin/pins', { method: 'POST', body });
      toast('Đã thêm ghim');
      await loadExploration();
      render();
    } else if (form.dataset.poi) {
      const moods = [...form.querySelectorAll('input[name=mood]:checked')].map(box => ({ id: Number(box.value), reason: form.querySelector(`[name="reason-${box.value}"]`).value }));
      await api(`/api/m4l/admin/pois/${form.dataset.poi}/moods`, { method: 'PUT', body: { moods } });
      toast('Đã lưu mood cho địa điểm');
      await Promise.all([loadMoods(), loadPois()]);
      render();
    }
  } catch (error) { toast(error.message); }
});

async function start() {
  if (!state.token) { blocked('Cần đăng nhập', 'Đăng nhập bằng tài khoản Quản trị hệ thống, Quản trị nội dung hoặc Nhân viên quản lí.'); return; }
  try {
    state.user = (await api('/api/cms/me')).user;
    $('#who').textContent = state.user.full_name || state.user.username;
    if (!can('S0', 'CONTENT', 'AREA')) { blocked('Không có quyền', 'Trang này dành cho Quản trị hệ thống, Quản trị nội dung và Nhân viên quản lí khu vực.'); return; }
    await Promise.all([can('S0', 'CONTENT') ? Promise.all([loadMoods(), loadPois(), loadExploration()]) : null, can('S0', 'AREA') ? loadCommerce() : null]);
    if (can('S0', 'CONTENT')) await loadStats();
    render();
  } catch (error) {
    if (error.status === 401) blocked('Phiên đăng nhập đã hết hạn', 'Vui lòng đăng nhập lại.');
    else blocked('Chưa tải được dữ liệu', error.message);
  }
}
start();
