from pathlib import Path
import re
import shutil
from datetime import datetime

ROOT = Path.cwd()

JS = ROOT / "web" / "js" / "app.js"
CSS = ROOT / "web" / "css" / "app.css"

if not JS.exists():
    raise SystemExit(f"Khong tim thay: {JS}")

if not CSS.exists():
    raise SystemExit(f"Khong tim thay: {CSS}")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# =========================================================
# BACKUP
# =========================================================
js_backup = JS.with_name(f"app.js.backup_{stamp}")
css_backup = CSS.with_name(f"app.css.backup_{stamp}")

shutil.copy2(JS, js_backup)
shutil.copy2(CSS, css_backup)

print("Backup:")
print(" ", js_backup)
print(" ", css_backup)

# =========================================================
# NEW ROUTE UI
# =========================================================
new_route = r'''  route(v) {
    const p = S.detail[v.id] || S.poiMap[v.id];
    const r = S.route;

    const modes = [
      ['foot', 'walk', t('walk')],
      ['bike', 'bike', t('bike')],
      ['driving', 'moto', t('drive')],
      ['transit', 'metro', t('bus')]
    ];

    const shareUrl = `${p.id > 0 ? `${baseUrl()}/?poi=${p.id}` : pointUrl(p)}&dir=${v.mode}&from=${S.origin.lat.toFixed(6)},${S.origin.lng.toFixed(6)}`;

    const qrBlock = `
      <div class="route-qr">
        <div class="qr">
          ${qrSVG(shareUrl, { size: 132 })}
        </div>

        <div class="route-qr__text">
          <b>${t('takeRoute')}</b>
          <small>${t('takeRouteSub')}</small>
        </div>
      </div>
    `;

    const grabBlock = S.settings.ride?.grab ? `
      <div class="ride-cta">
        <div class="ride-cta__title">
          ${LANG === 'vi' ? 'Di chuyển nhanh' : 'Quick ride'}
        </div>

        <button
          class="btn grab-cta"
          data-act="ride"
          data-p="grab"
          data-id="${p.id}"
        >
          ${icon('moto', 20)}
          ${LANG === 'vi' ? 'Gọi Grab' : t('grab')}
        </button>

        <small>
          ${LANG === 'vi'
            ? 'Đặt chuyến tới bệnh viện'
            : 'Book a ride to this destination'}
        </small>
      </div>
    ` : '';

    let body = `
      <div class="empty">
        <div
          class="spin"
          style="margin:0 auto 10px;border-color:var(--line);border-top-color:var(--blue)"
        ></div>

        ${
          v.mode === 'transit'
            ? (
                LANG === 'vi'
                  ? 'Đang tìm tuyến xe buýt & metro…'
                  : 'Finding bus & metro routes…'
              )
            : t('loading')
        }
      </div>
    `;

    if (r && r.mode === v.mode) {

      if (v.mode === 'transit') {

        body = `
          ${qrBlock}
          ${transitPlanHTML(r, p)}
        `;

      } else {

        const [n, u] = fmtDur(r.duration);

        body = `
          <div class="summary">
            <span class="big">${n}</span>
            <span class="unit">${u}</span>

            <span class="dist">
              ${fmtDist(r.distance)}
              ${r.source === 'estimate' ? ' · ' + t('estimate') : ''}
            </span>
          </div>

          ${qrBlock}

          <div class="sec route-steps-title">
            <h3>${t('steps')}</h3>

            ${
              r.steps.length > 3
                ? `<small class="route-scroll-hint">
                    ${
                      LANG === 'vi'
                        ? 'Cuộn xuống để xem tiếp'
                        : 'Scroll for more'
                    }
                  </small>`
                : ''
            }
          </div>

          <div class="steps steps-scroll">
            ${r.steps.map((s, i) => `
              <button
                class="step"
                data-act="step"
                data-i="${i}"
              >
                <span class="sn">${i + 1}</span>

                <span>
                  ${esc(s.text)}

                  ${
                    s.distance
                      ? `<small>${fmtDist(s.distance)}</small>`
                      : ''
                  }
                </span>
              </button>
            `).join('')}
          </div>

          ${
            !p.isStop
              ? `
                <div class="sec">
                  <h3>
                    ${
                      LANG === 'vi'
                        ? 'Bến xe buýt & ga Metro gần bạn'
                        : 'Nearest bus stops & metro'
                    }
                  </h3>
                </div>

                <div id="nearT">
                  ${nearbyHTML(S.nearT)}
                </div>
              `
              : ''
          }
        `;
      }
    }

    return `
      <div class="pv route-page">

        <div class="pv-head">
          ${backBtn()}

          <div style="min-width:0">
            <h2 class="pv-title">
              ${t('directions')}
            </h2>

            <div class="pv-sub">
              ${esc(p.name)}
            </div>
          </div>
        </div>

        <div class="route-top">

          <div class="fromto">

            <div class="ft">
              <span class="dotA"></span>

              <span>
                <small>${t('from')}</small>
                <b>${esc(S.origin.label)}</b>
              </span>
            </div>

            <div class="ft">
              <span class="dotB"></span>

              <span>
                <small>${t('to')}</small>
                <b>${esc(p.name)}</b>
              </span>
            </div>

          </div>

          ${grabBlock}

        </div>

        <div
          class="modes"
          style="grid-template-columns:repeat(4,1fr)"
        >
          ${modes.map(([m, ic, lb]) => `
            <button
              class="mode${v.mode === m ? ' on' : ''}"
              data-act="mode"
              data-m="${m}"
            >
              ${icon(ic, 22)}
              ${lb}
            </button>
          `).join('')}
        </div>

        ${body}

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

      </div>
    `;
  },
'''

js_text = JS.read_text(encoding="utf-8")

pattern = re.compile(
    r'  route\(v\) \{.*?(?=\n  transit\(v\) \{)',
    re.S
)

if not pattern.search(js_text):
    raise SystemExit(
        "Khong tim thay ham route(v). File app.js co the da thay doi cau truc."
    )

js_text = pattern.sub(new_route.rstrip(), js_text, count=1)

JS.write_text(js_text, encoding="utf-8")

print("Da cap nhat app.js")

# =========================================================
# CSS
# =========================================================

css_patch = r'''

/* =========================================================
   X24 ROUTE UX PATCH START
   Grab + QR + compact route steps
   ========================================================= */

.route-page .route-top{
  display:grid;
  grid-template-columns:minmax(0,1fr) 160px;
  gap:12px;
  align-items:stretch;
  margin-bottom:14px;
}

.route-page .route-top .fromto{
  margin-bottom:0;
}

.route-page .ride-cta{
  border:1px solid var(--line);
  border-radius:var(--r-lg);
  padding:12px;
  background:#fff;
  display:flex;
  flex-direction:column;
  justify-content:center;
  align-items:center;
  text-align:center;
  gap:8px;
  min-width:0;
}

.route-page .ride-cta__title{
  font-size:.75rem;
  font-weight:800;
  color:var(--muted);
}

.route-page .grab-cta{
  width:100%;
  min-height:48px;
  height:auto;
  padding:10px 8px;
  background:#F2FFF7;
  border:1.5px solid #B8EBCB;
  color:#00A84F;
  font-size:.88rem;
}

.route-page .grab-cta:active{
  background:#E6F9ED;
}

.route-page .ride-cta small{
  font-size:.69rem;
  color:var(--muted);
  line-height:1.3;
}

.route-page .route-qr{
  display:flex;
  align-items:center;
  justify-content:center;
  gap:18px;
  padding:14px 16px;
  margin:0 0 14px;
  border-radius:var(--r-lg);
  background:var(--grad-soft);
  border:1px solid var(--line);
}

.route-page .route-qr .qr{
  flex:none;
  background:#fff;
  border-radius:14px;
  padding:8px;
  box-shadow:var(--sh-1);
}

.route-page .route-qr__text{
  max-width:250px;
}

.route-page .route-qr__text b{
  display:block;
  color:var(--navy);
  font-size:1rem;
  line-height:1.25;
}

.route-page .route-qr__text small{
  display:block;
  margin-top:5px;
  color:var(--muted);
  font-size:.79rem;
  line-height:1.45;
}

.route-page .route-steps-title{
  margin-top:0;
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:10px;
}

.route-page .route-scroll-hint{
  font-size:.7rem;
  color:var(--muted);
  font-weight:500;
}

.route-page .steps-scroll{
  max-height:235px;
  overflow-y:auto;
  overscroll-behavior:contain;
  scrollbar-width:thin;
}

.route-page .steps-scroll::-webkit-scrollbar{
  width:7px;
}

.route-page .steps-scroll::-webkit-scrollbar-thumb{
  background:#C8D1E0;
  border-radius:10px;
}

.route-page .steps-scroll .step{
  min-height:72px;
}

.route-page .route-extra-ride{
  grid-template-columns:1fr;
}

@media (max-width:640px){

  .route-page .route-top{
    grid-template-columns:1fr;
  }

  .route-page .ride-cta{
    flex-direction:row;
  }

  .route-page .ride-cta__title{
    display:none;
  }

  .route-page .ride-cta small{
    display:none;
  }

  .route-page .grab-cta{
    width:100%;
  }

  .route-page .route-qr{
    align-items:center;
  }
}

/* X24 ROUTE UX PATCH END */
'''

css_text = CSS.read_text(encoding="utf-8")

# Nếu chạy script lần 2 thì xóa patch cũ trước để không bị CSS trùng
css_text = re.sub(
    r'/\* =========================================================\n'
    r'   X24 ROUTE UX PATCH START.*?'
    r'/\* X24 ROUTE UX PATCH END \*/',
    '',
    css_text,
    flags=re.S
)

css_text = css_text.rstrip() + "\n" + css_patch.strip() + "\n"

CSS.write_text(css_text, encoding="utf-8")

print("Da cap nhat app.css")
print()
print("==========================================")
print("HOAN TAT")
print("==========================================")
print("1. Grab da dua len canh khoi Tu / Den")
print("2. QR da dua len tren")
print("3. Huong dan chi hien khoang 3 buoc")
print("4. Co thanh cuon xem cac buoc con lai")
print()
print("Hay Ctrl + F5 tren trinh duyet de test.")
