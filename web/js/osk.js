// Bàn phím ảo tiếng Việt cho kiosk (tìm kiếm không phân biệt dấu nên chỉ cần gõ không dấu).
const ROWS = [
  ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
  ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
  ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'đ'],
  ['z', 'x', 'c', 'v', 'b', 'n', 'm', 'ă', 'â', 'ê'],
];
const VN = ['ô', 'ơ', 'ư', 'á', 'à', 'ả', 'ã', 'ạ', 'ế', 'ộ'];

export class OSK {
  constructor(el, { onClose } = {}) {
    this.el = el; this.onClose = onClose; this.input = null;
    el.addEventListener('pointerdown', (e) => e.preventDefault()); // giữ focus ở ô nhập
    el.addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b || !this.input) return;
      const k = b.dataset.k;
      const inp = this.input;
      const s = inp.selectionStart ?? inp.value.length, en = inp.selectionEnd ?? inp.value.length;
      if (k === 'bk') { const a = s === en ? Math.max(0, s - 1) : s; inp.value = inp.value.slice(0, a) + inp.value.slice(en); inp.setSelectionRange(a, a); }
      else if (k === 'sp') this._ins(' ');
      else if (k === 'clr') inp.value = '';
      else if (k === 'ok') { this.hide(); this.onClose?.(); inp.blur(); return; }
      else this._ins(k);
      inp.dispatchEvent(new Event('input', { bubbles: true }));
    });
    this.render();
  }
  _ins(ch) { const inp = this.input, s = inp.selectionStart ?? inp.value.length, e = inp.selectionEnd ?? inp.value.length; inp.value = inp.value.slice(0, s) + ch + inp.value.slice(e); inp.setSelectionRange(s + 1, s + 1); }
  render() {
    const row = (keys, cls = '') => `<div class="osk-row">${keys.map(k => `<button data-k="${k}" class="${cls}">${k}</button>`).join('')}</div>`;
    this.el.innerHTML = ROWS.map(r => row(r)).join('') + row(VN, 'vn') +
      `<div class="osk-row"><button data-k="clr" class="mid">Xoá hết</button><button data-k="sp" class="wide">Dấu cách</button><button data-k="bk" class="mid">⌫</button><button data-k="ok" class="mid ok">Xong</button></div>`;
  }
  show(input) { this.input = input; this.el.hidden = false; document.body.classList.add('osk-open'); }
  hide() { this.el.hidden = true; document.body.classList.remove('osk-open'); }
}
