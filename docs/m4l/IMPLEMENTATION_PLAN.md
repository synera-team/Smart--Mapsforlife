# M4L 2.0 — Kế hoạch triển khai

Mỗi phase hoàn tất khi có: code chạy được + migration + test pass + docs + cách demo + không regression + giới hạn đã biết. Phase sau chỉ bắt đầu khi phase trước đạt.

## Phase 0 — Audit & kiến trúc ✅

Sản phẩm: `docs/m4l/AS_IS_AUDIT.md`, `REQUIREMENTS_TRACEABILITY.md`, `ARCHITECTURE.md`, `OPEN_DECISIONS.md`, file này. Baseline test/build ghi trong audit §9.

## Phase 1 — Mobile shell + Mood Tags + Discovery ✅

| Loại | File |
|---|---|
| Mới | `server/m4l.py`, `server/m4l_service.py`, `server/m4l_migrations.py` |
| Mới | `web/m4l/index.html`, `web/m4l/m4l.js`, `web/m4l/m4l.css`, `web/m4l/admin.html`, `web/m4l/admin.js` |
| Mới | `tests/test_m4l.py` |
| Sửa (tối thiểu) | `server/app.py`: import + `register_blueprint(m4l)` + `init_m4l()` trong `create_app()` |
| Sửa docs | `README.md` (mục M4L), `docs/API.md` (bảng `/api/m4l`) |

Definition of done:
- Cờ tắt → 404, không tạo bảng. Cờ bật → backup + migrate, `/m4l` chạy.
- Home: chào tên USER từ DB, khách thấy “Xin chào!”; mood từ DB kèm số POI thật.
- Discovery: lọc mood/từ khóa/danh mục/bán kính, phân trang, xếp hạng xác định, loading/empty/error/timeout.
- Admin: S0 CRUD mood; S0/CONTENT gán mood cho POI trong phường được giao; ghi `audit`.
- Test: quyền, bộ lọc, POI ẩn, mood inactive, validate, migration idempotent, downgrade, route cũ.

Demo: xem `README.md` → mục “M4L 2.0 (thử nghiệm)”.

## Phase 2 — Random/Mystery + Fog PoC ✅

Đã làm với mặc định an toàn (xem `OPEN_DECISIONS.md` B1–B12). Phụ thuộc chờ chốt: D2, D3, D4, D7, A1.

Kết quả: `tests/test_m4l_phase2.py` 66 kiểm thử đạt; nâng cấp v1→v2 chạy thử trên bản sao DB thật (khu Cầu Giấy 402 ô). Thiết kế ban đầu bên dưới giữ để đối chiếu.

| File | Nội dung |
|---|---|
| `server/m4l_migrations.py` v2 | `m4l_areas`, `m4l_cells`, `m4l_user_unlocks UNIQUE(account_id,cell_id)`, `m4l_mystery_pins`, `m4l_discovery_events` |
| `server/m4l_exploration.py` | Sinh lưới cố định (`grid_version`) cho khu vực pilot từ `wards.geometry`; ánh xạ lat/lng → `cell_id` |
| `server/m4l_service.py` | `random_pick()`: pool = POI hợp lệ theo mood/bán kính, loại POI đã hiện 24h, quota theo DB, ghi lý do |
| `server/m4l.py` | Routes random, exploration, unlock, progress, mystery-pins |
| `web/m4l/` | Nút “Khám phá ngẫu nhiên” + DeviceMotion (xin quyền iOS, fallback nút), `/m4l/world` dùng MapLibre có sẵn, overlay ô, legend có chữ |

Test: 1 request ≤ 1 kết quả; double-click song song không vượt quota (khóa giao dịch SQLite `BEGIN IMMEDIATE` / Postgres `SELECT … FOR UPDATE`); accuracy > ngưỡng → không unlock; unlock 2 lần → 1 bản ghi; tốc độ phi lý (teleport) → từ chối; đổi `grid_version` → mẫu số đúng.

Rủi ro: GPS web dễ giả mạo (chỉ giảm thiểu, không chặn tuyệt đối); hiệu năng overlay trên máy yếu (giới hạn số ô theo viewport).

## Phase 2b — Fog of War & Mystery Pins toàn Hà Nội ✅

Theo change request mở rộng toàn thành phố (ưu tiên trước Phase 3). Thiết kế, audit, rollback: `HANOI_SCALEUP.md`; số liệu: `HANOI_GRID_REPORT.md`; quyết định mở: `OPEN_DECISIONS.md` C1–C8.

| Loại | File |
|---|---|
| Mới | `server/m4l_grid.py`, `server/m4l_data/hanoi_grid_v1.json.gz`, `tools/m4l_grid/{overpass,fetch,build}.py`, `tests/test_m4l_hanoi.py`, `docs/m4l/HANOI_*.md` |
| Sửa | `server/m4l_exploration.py` (khung nhìn, phân loại, vùng, thống kê), `server/m4l_migrations.py` (v3), `server/m4l.py`, `server/m4l_service.py` (`primary_area`), `web/m4l/{world.js,m4l.js,admin.js,m4l.css,admin.html,index.html}`, `.gitignore` |

## Phase 3 — Voucher ✅ (29/10/2026, xem IMPLEMENTATION_REPORT.md)

Đã triển khai theo thiết kế dưới đây, với hai điều chỉnh: mẫu voucher gắn với chiến dịch, và mã QR là token ngẫu nhiên 144 bit lưu trực tiếp (chỉ dùng một lần, có hạn, chỉ chủ quán xác nhận được) thay vì lưu hash.


Phụ thuộc: D5, A2, D6 (không billing).

- Bảng `m4l_voucher_templates` (POI đối tác qua `cms_assignments`, TTL, quota tổng/người, trạng thái duyệt) và `m4l_user_vouchers` (`token_hash` UNIQUE, `issued_at/expires_at` server).
- Claim: giao dịch giữ chỗ quota → token ngẫu nhiên 128-bit → lưu SHA-256. QR chỉ chứa token.
- Redeem: OWNER của đúng POI; `UPDATE … SET status='redeemed' WHERE token_hash=? AND status='active' AND expires_at>?` — kiểm tra `rowcount==1` để chống double redeem; idempotency key.
- Test T12–T16 bao gồm 2 luồng redeem song song.

## Phase 4 — Sponsor + Kiosk + Analytics ✅ (29/10/2026)

Đã triển khai. Duyệt bởi S0/AREA theo phường. Mã check-in là token ngẫu nhiên dùng một lần, lưu SHA-256 (thay cho HMAC + nonce). Bảng sự kiện là `m4l_events`. Chưa có POS thật (mock).


Phụ thuộc: D6, D8, D9.

- Campaign `draft → pending_review → approved → active → paused/ended/rejected`; duyệt bởi AREA/CONTENT theo phường; placement theo mood + khu vực + lịch; slot có nhãn `Tài trợ` tách khỏi organic.
- Kiosk: khóa bí mật riêng cho từng `devices` (chỉ lưu hash), QR check-in ký HMAC hạn ngắn, chống replay bằng `nonce` UNIQUE.
- `m4l_analytics_events` với `event_id` UNIQUE; funnel impression → scan → claim → redeem.

## Phase 5 — Pilot & phát hành 🟡 (xem RELEASE_READINESS.md)

Ma trận vai trò, QA thiết bị 360/390/430 + desktop, đo LCP/CLS, dry-run migration trên **bản sao** `data/xanh24.db`, kế hoạch rollback, runbook, demo script. **Chỉ deploy khi người dùng duyệt.**

## Rủi ro xuyên suốt

| Rủi ro | Giảm thiểu |
|---|---|
| Thiếu POI F&B thật | Đội nội dung nhập POI + gán mood trước pilot; UI có empty state |
| Postgres (Vercel) khác SQLite | SQL chỉ dùng cú pháp chung; kiểm thử thêm trên Postgres trước Phase 5 (chưa có trong môi trường này) |
| Service worker cache JS cũ | Đổi tên file/tham số version khi phát hành; cân nhắc loại trừ `/m4l` trong `sw.js` (cần duyệt vì sw.js phục vụ kiosk) |
| Working tree chưa commit | Người dùng commit/branch trước khi merge M4L |
