from pathlib import Path
import re

p = Path("web/js/app.js")

text = p.read_text(encoding="utf-8")

old = r'''
        ${
          S.settings.ride?.xanhsm
            ? `
              <div class="btn-row route-extra-ride">
                <button
                  class="btn sec"
                  data-act="ride"
                  data-p="xanhsm"
                  data-id="${p.id}"
                >
                  ${icon('taxi', 20)}
                  ${t('xanhsm')}
                </button>
              </div>
            `
            : ''
        }
'''

if old not in text:
    raise SystemExit("Khong tim thay khoi Xanh SM trong route UI.")

text = text.replace(old, "", 1)

p.write_text(text, encoding="utf-8")

print("DA XOA NUT GOI XANH SM KHOI TRANG CHI DUONG.")
