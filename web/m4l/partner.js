// Partner portal: an OWNER account manages campaigns for its own POI and confirms vouchers at the counter.
// Nothing here takes payment; a campaign only runs after Xanh24 staff approve it.
import { clearStaffToken, demoInfo, staffToken } from '/m4l/demo-mode.js';

const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const TOKEN_KEY = 'x24_cms_token';
const STATUS = { draft: 'Nháp', pending: 'Chờ duyệt', approved: 'Đã duyệt', rejected: 'Bị từ chối', paused: 'Tạm dừng', ended: 'Đã kết thúc' };
const VOUCHER = { issued: 'Còn hiệu lực', redeemed: 'Đã sử dụng', expired: 'Đã hết hạn', revoked: 'Đã thu hồi' };
const FUNNEL = [['impression', 'Hiển thị'], ['claim', 'Nhận voucher'], ['nav_click', 'Bấm chỉ đường'], ['redeem', 'Đổi tại quầy']];
let token = null;
try { token = staffToken() || localStorage.getItem(TOKEN_KEY); } catch { /* storage blocked */ }
const demo = await demoInfo;
const state = { me: null, editing: null, error: null, code: '', result: '' }; // code/result survive re-renders
const redeemCode = (location.pathname.match(/^\/m4l\/v\/([A-Za-z0-9_-]+)$/) || [])[1] || '';

async function api(path, { method = 'GET', body } = {}) {
  const headers = { Authorization: `Bearer ${token}` };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) { const error = new Error(result.error || `Lỗi ${response.status}`); error.status = response.status; error.code = result.code; throw error; }
  return result;
}
function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { element.hidden = true; }, 4500);
}
const date = epoch => epoch ? new Date(epoch * 1000).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : '—';
const localInput = epoch => { const d = new Date(epoch * 1000); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };
const block = (kind, title, text, actions = '') => `<div class="state-block ${kind}" role="${kind === 'error' ? 'alert' : 'status'}"><h3>${esc(title)}</h3><p>${esc(text)}</p>${actions ? `<div class="state-actions">${actions}</div>` : ''}</div>`;
const loginLink = () => demo
  ? `<a class="btn primary" href="/demo?as=partner${redeemCode ? `&voucher=${encodeURIComponent(redeemCode)}` : ''}">Vào cổng đối tác demo</a>`
  : `<a class="btn primary" href="/cms/login?next=${encodeURIComponent(location.pathname)}">Đăng nhập tài khoản đối tác</a>`;

// ---------------------------------------------------------------- redeem at the counter
function redeemPanel(prefill = '') {
  return `<section class="panel" aria-labelledby="redeemHead"><h2 id="redeemHead">Xác nhận voucher tại quầy</h2>
    <p class="muted">Quét QR trên điện thoại khách bằng camera (mở đường dẫn /m4l/v/…) hoặc nhập mã. Mỗi voucher chỉ đổi được một lần và phải còn hạn.</p>
    <form id="redeemForm" class="inline-form"><label class="field"><span>Mã voucher</span><input id="voucherCode" required minlength="10" maxlength="200" value="${esc(state.code || prefill)}" autocomplete="off" autocapitalize="off" spellcheck="false"></label>
    <button class="btn ghost" type="submit" data-mode="check">Kiểm tra</button><button class="btn primary" type="submit" data-mode="redeem">Xác nhận đã dùng</button></form>
    <div id="redeemResult" aria-live="polite">${state.result}</div></section>`;
}
function codeFrom(value) { const text = value.trim(); const match = text.match(/\/m4l\/v\/([A-Za-z0-9_-]+)/); return match ? match[1] : text; }
async function onRedeem(event) {
  event.preventDefault();
  const mode = event.submitter?.dataset.mode || 'check';
  const code = codeFrom($('#voucherCode').value);
  state.code = code;
  const show = html => { state.result = html; const out = $('#redeemResult'); if (out) out.innerHTML = html; };
  show('<p class="muted">Đang kiểm tra…</p>');
  try {
    const v = await api(`/api/m4l/partner/vouchers/${mode}`, { method: 'POST', body: { code } });
    const left = v.status === 'issued' ? Math.max(0, v.seconds_left) : 0;
    show(`<div class="redeem-card ${mode === 'redeem' ? 'ok' : ''}"><b>${mode === 'redeem' ? '✓ Đã xác nhận sử dụng' : VOUCHER[v.status]}</b>
      <p>${esc(v.title)} — ${esc(v.benefit)}</p><p class="muted">${esc(v.poi_name)} · nhận lúc ${date(v.issued_at)}${left ? ` · còn ${Math.ceil(left / 60)} phút` : ''}${v.pos_ref ? ` · mã POS ${esc(v.pos_ref)} (${esc(v.pos)})` : ''}</p></div>`);
    if (mode === 'redeem') { toast('Đã xác nhận voucher'); loadMe(); }
  } catch (error) {
    const title = { ALREADY_REDEEMED: 'Voucher đã được sử dụng', EXPIRED: 'Voucher đã hết hạn', NOT_FOUND: 'Không tìm thấy voucher của cửa hàng bạn' }[error.code] || 'Không xác nhận được';
    show(`<div class="redeem-card bad"><b>✕ ${esc(title)}</b><p>${esc(error.message)}</p></div>`);
  }
}

// ---------------------------------------------------------------- campaigns
function stats(c) {
  const s = c.stats || {};
  return `<dl class="funnel">${FUNNEL.map(([key, label]) => `<div><dt>${label}</dt><dd>${(s[key] || 0).toLocaleString('vi-VN')}</dd></div>`).join('')}</dl>`;
}
function campaignCard(c) {
  const editable = ['draft', 'rejected'].includes(c.status) && !state.me.partner.read_only;
  const voucher = c.voucher ? `<p>Voucher: <b>${esc(c.voucher.title)}</b> · ${esc(c.voucher.benefit)} · ${c.voucher.ttl_minutes} phút · đã phát ${c.voucher.issued_count}/${c.voucher.issue_cap}</p>` : '<p class="muted">Không kèm voucher</p>';
  return `<article class="camp"><div class="camp-head"><span class="badge status-${c.status}">${STATUS[c.status]}</span>${c.live ? '<span class="badge live">Đang chạy</span>' : ''}${c.is_demo ? '<span class="badge demo">DEMO</span>' : ''}<span class="muted">${esc(c.kind_label)}</span></div>
    <h3>${esc(c.name)}</h3><p class="muted">${c.mood_name ? `Mood “${esc(c.mood_name)}” · ` : ''}${c.radius_m ? `bán kính ${(c.radius_m / 1000).toLocaleString('vi-VN')} km` : 'toàn thành phố'} · ưu tiên ${c.priority}${c.exclusive ? ' · độc quyền' : ''} · ${date(c.starts_at)} → ${date(c.ends_at)}</p>
    ${voucher}${c.review_note ? `<p class="note">Ghi chú duyệt: ${esc(c.review_note)}</p>` : ''}${stats(c)}
    ${editable ? `<div class="row-actions"><button type="button" class="btn small ghost" data-act="edit" data-id="${c.id}">Sửa</button><button type="button" class="btn small primary" data-act="submit" data-id="${c.id}">Gửi duyệt</button></div>` : ''}</article>`;
}
function campaignForm() {
  const c = state.editing || {};
  const now = Math.floor(Date.now() / 1000);
  const v = c.voucher || {};
  const moods = state.me.moods.map(m => `<option value="${esc(m.slug)}" ${c.mood_id === m.id ? 'selected' : ''}>${esc(m.name)}${state.me.poi.moods.includes(m.slug) ? '' : ' (địa điểm chưa được gắn mood này)'}</option>`).join('');
  return `<section class="panel" aria-labelledby="formHead"><h2 id="formHead">${c.id ? 'Sửa chiến dịch' : 'Tạo chiến dịch mới'}</h2>
    <p class="muted">Chiến dịch chỉ chạy sau khi Xanh24 duyệt. Hệ thống không thu tiền; giá và hợp đồng do hai bên thỏa thuận ngoài hệ thống.</p>
    <form id="campForm" class="grid-form">
      <label class="field"><span>Loại</span><select name="kind">${Object.entries(state.me.kinds).map(([k, label]) => `<option value="${k}" ${c.kind === k ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select></label>
      <label class="field wide"><span>Tên chiến dịch</span><input name="name" required maxlength="120" value="${esc(c.name || '')}"></label>
      <label class="field"><span>Mood (bắt buộc với tài trợ mood)</span><select name="mood"><option value="">— Không —</option>${moods}</select></label>
      <label class="field"><span>Bán kính (km, để trống = toàn thành phố)</span><input name="radius_km" type="number" min="0.1" max="50" step="0.1" value="${c.radius_m ? c.radius_m / 1000 : ''}"></label>
      <label class="field"><span>Bắt đầu</span><input name="starts_at" type="datetime-local" required value="${localInput(c.starts_at || now)}"></label>
      <label class="field"><span>Kết thúc</span><input name="ends_at" type="datetime-local" required value="${localInput(c.ends_at || now + 30 * 86400)}"></label>
      <label class="field"><span>Mức ưu tiên theo hợp đồng (0–100)</span><input name="priority" type="number" min="0" max="100" value="${c.priority ?? 0}"></label>
      <label class="field"><span>Gói tài trợ</span><input name="package" maxlength="80" value="${esc(c.package || '')}"></label>
      <label class="field"><span>Hạn mức lượt hiển thị</span><input name="impression_cap" type="number" min="1" value="${c.impression_cap || ''}"></label>
      <label class="check"><input name="exclusive" type="checkbox" ${c.exclusive ? 'checked' : ''}> Độc quyền mood trong khu vực</label>
      <fieldset class="wide"><legend>Voucher kèm gợi ý (tùy chọn)</legend>
        <label class="field"><span>Tên voucher</span><input name="v_title" maxlength="120" value="${esc(v.title || '')}"></label>
        <label class="field"><span>Ưu đãi</span><input name="v_benefit" maxlength="200" value="${esc(v.benefit || '')}"></label>
        <label class="field wide"><span>Điều kiện áp dụng</span><input name="v_terms" maxlength="500" value="${esc(v.terms || '')}"></label>
        <label class="field"><span>Đếm ngược (phút)</span><input name="v_ttl" type="number" min="5" max="1440" value="${v.ttl_minutes || state.me.defaults.voucher_ttl_minutes}"></label>
        <label class="field"><span>Tổng số voucher</span><input name="v_cap" type="number" min="1" value="${v.issue_cap || ''}"></label>
        <label class="field"><span>Mỗi người tối đa</span><input name="v_per_user" type="number" min="1" max="10" value="${v.per_user_cap || 1}"></label>
      </fieldset>
      <div class="row-actions wide"><button class="btn primary" type="submit">${c.id ? 'Lưu nháp' : 'Tạo nháp'}</button>${c.id ? '<button class="btn ghost" type="button" data-act="cancel">Hủy</button>' : ''}</div>
    </form></section>`;
}
function readForm(form) {
  const f = new FormData(form);
  const epoch = name => Math.floor(new Date(f.get(name)).getTime() / 1000);
  const body = { kind: f.get('kind'), name: f.get('name'), mood: f.get('mood') || '', starts_at: epoch('starts_at'), ends_at: epoch('ends_at'),
    priority: Number(f.get('priority') || 0), package: f.get('package'), exclusive: f.get('exclusive') === 'on',
    radius_m: f.get('radius_km') ? Math.round(Number(f.get('radius_km')) * 1000) : null, impression_cap: f.get('impression_cap') ? Number(f.get('impression_cap')) : null };
  if (f.get('v_title') || f.get('v_benefit') || f.get('v_cap')) {
    body.voucher = { title: f.get('v_title'), benefit: f.get('v_benefit'), terms: f.get('v_terms'), ttl_minutes: Number(f.get('v_ttl')),
      issue_cap: f.get('v_cap') ? Number(f.get('v_cap')) : null, per_user_cap: Number(f.get('v_per_user') || 1) };
  }
  return body;
}

function render() {
  const view = $('#view');
  if (!token) { view.innerHTML = `<h1>Cổng đối tác</h1>${block('empty', 'Cần đăng nhập', 'Dùng tài khoản đối tác (tài khoản kiosk) đã được Xanh24 cấp.', loginLink())}`; return; }
  if (state.error) { view.innerHTML = `<h1>Cổng đối tác</h1>${block('error', 'Không mở được cổng đối tác', state.error, state.errorStatus === 401 || state.errorStatus === 403 ? loginLink() : '<button class="btn primary" data-act="reload">Thử lại</button>')}`; return; }
  if (redeemCode && !state.me) { view.innerHTML = `<h1>Xác nhận voucher</h1>${redeemPanel(redeemCode)}`; return; }
  if (!state.me) { view.innerHTML = '<div class="skeleton line w40"></div><div class="skeleton place-skel"></div>'; return; }
  const { partner, poi, campaigns } = state.me;
  view.innerHTML = `<section class="page-head"><p class="eyebrow">Cổng đối tác</p><h1>${esc(poi.name)}</h1><p>${esc(poi.address || '')} · tài khoản ${esc(partner.name)}${partner.read_only ? ' (chỉ xem)' : ''}</p>
      <p class="muted">Xác nhận voucher đang dùng adapter POS: <b>${esc(state.me.pos_adapter)}</b> (chưa kết nối POS thật).</p></section>
    ${redeemPanel(redeemCode)}
    <section class="section" aria-labelledby="campHead"><h2 id="campHead">Chiến dịch của bạn</h2>${campaigns.length ? `<div class="camp-list">${campaigns.map(campaignCard).join('')}</div>` : block('empty', 'Chưa có chiến dịch', 'Tạo chiến dịch đầu tiên ở bên dưới rồi gửi Xanh24 duyệt.')}</section>
    ${partner.read_only ? '' : campaignForm()}`;
}
async function loadMe() {
  try { state.me = await api('/api/m4l/partner/me'); state.error = null; } catch (error) {
    // S0 staff may open /m4l/v/<code> to confirm a voucher without a partner profile.
    if (redeemCode && error.status === 403) { state.me = null; state.error = null; } else { state.error = error.message; state.errorStatus = error.status; }
  }
  render();
}

document.addEventListener('submit', async event => {
  if (event.target.id === 'redeemForm') return onRedeem(event);
  if (event.target.id !== 'campForm') return;
  event.preventDefault();
  const button = event.target.querySelector('button[type=submit]');
  button.disabled = true;
  try {
    const body = readForm(event.target);
    if (state.editing?.id) await api(`/api/m4l/partner/campaigns/${state.editing.id}`, { method: 'PUT', body });
    else await api('/api/m4l/partner/campaigns', { method: 'POST', body });
    toast('Đã lưu nháp. Bấm “Gửi duyệt” khi sẵn sàng.');
    state.editing = null;
    await loadMe();
  } catch (error) { toast(error.message); } finally { button.disabled = false; }
});
document.addEventListener('click', async event => {
  const target = event.target.closest('[data-act]');
  if (!target) return;
  const { act, id } = target.dataset;
  if (act === 'reload') return loadMe();
  if (act === 'cancel') { state.editing = null; return render(); }
  if (act === 'edit') { state.editing = state.me.campaigns.find(c => String(c.id) === id); render(); $('#campForm')?.scrollIntoView({ behavior: 'smooth' }); return; }
  if (act === 'submit') {
    try { await api(`/api/m4l/partner/campaigns/${id}/submit`, { method: 'POST' }); toast('Đã gửi Xanh24 duyệt'); await loadMe(); } catch (error) { toast(error.message); }
  }
});
$('#logout').hidden = !token;
$('#logout').onclick = () => {
  if (staffToken()) { clearStaffToken(); location.assign('/demo'); return; } // demo staff tab: keep the visitor's own session
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } location.assign('/cms/login');
};
render();
if (token) loadMe();
