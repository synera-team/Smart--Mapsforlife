# M4L 2.0 — AS-IS Audit

Ngày audit: 28/10/2026 · Nhánh: `main` (HEAD `e20b59a`) · Người thực hiện: Claude Code

Tài liệu ghi lại **hành vi thực tế** đọc từ mã nguồn và database, không suy đoán. Mọi đường dẫn tính từ gốc repo.

## 1. Trạng thái Git

`git status` lúc bắt đầu: working tree **không sạch** — 13 file đã sửa (`server/app.py`, `server/db.py`, `README.md`, `web/index.html`, tests…) và nhiều file chưa track (`frontend/`, `server/cms.py`, `server/cms_applications.py`, `server/user_discovery.py`, `web/cms/`, `web/user/`, tests CMS, `.venv/`). Phần lớn tính năng CMS/User Dashboard **chưa được commit**.

Hệ quả: chưa tạo nhánh `feature/m4l-v2` và chưa commit (spec yêu cầu tạo nhánh khi tree sạch; commit thay người dùng là quyết định của họ). Các thay đổi M4L chỉ thêm file mới, cộng 3 dòng đăng ký trong `server/app.py` — xem `IMPLEMENTATION_PLAN.md`. `.venv/` chưa có trong `.gitignore`.

## 2. Kiến trúc thực tế

| Thành phần | Vị trí | Ghi chú |
|---|---|---|
| Flask app | `server/app.py` (1634 dòng) | Toàn bộ route công khai + `/api/admin/*` (S0/S1/CW). `create_app()` gọi `init_db()`, `seed_all()`, `seed_plans()`, `load_plugins()` |
| Blueprint CMS | `server/cms.py` | `/api/cms/*`: login/đăng ký/hồ sơ, tài khoản, ghim, nội dung, kiosk, gói, đơn, thanh toán demo |
| Blueprint hồ sơ đối tác | `server/cms_applications.py` | `/api/cms/partner-registration`, `/api/cms/applications/*` |
| Blueprint User | `server/user_discovery.py` | Chỉ có `/api/user/saved` (GET) và `/api/user/saved/<poi_id>` (POST/DELETE) |
| DB layer | `server/db.py` | SQLite (WAL) mặc định; Postgres khi có `DATABASE_URL` (lớp `_PgConn` dịch `?`→`%s`, `AUTOINCREMENT`→`BIGSERIAL`). Helpers `q()`, `ex()`, `get_setting()`. Migration = `CREATE TABLE IF NOT EXISTS` + bảng `MIGRATIONS` thêm cột khi khởi động |
| Auth legacy | `server/auth.py` | JWT HS256 (`secret()` từ `XANH24_SECRET` hoặc `data/secret.key`), bảng `users`, vai trò S0/S1/CW, ma trận `PERMISSIONS`, decorator `require(perm)`, `audit()` ghi bảng `audit` |
| Auth CMS | `server/cms.py` `authenticate`, `role()`, `wards()`, `in_scope()` | Bearer JWT; claim `cms=True` → bảng `cms_accounts` (AREA/CONTENT/REVIEW/OWNER/USER); không có claim → bảng `users` nhưng **chỉ S0** |
| Plugin máy chủ | `server/modules/` | `register(app, ctx)`; đang có `example_feedback.py`, `smarthospital.py` |
| Frontend React | `frontend/` (Vite 5, React 18) | `src/routes/AppRoutes.jsx` chọn trang theo path: `/admin`, `/download`, `/go/*`, còn lại `MapPage`. Build ra `frontend/dist` |
| Web legacy/vanilla | `web/` | `web/cms/` (portal CMS/HRM), `web/user/` (User Dashboard), `web/js/icons.js`, `web/assets/logo.png`, `web/sw.js` |
| Triển khai | `Dockerfile`, `docker-compose.yml`, `vercel.json` + `api/index.py`, `run.sh` | Vercel route mọi path vào `api/index.py`; Docker chạy gunicorn |

## 3. Route trang (đã kiểm chứng trong code + test)

| Route | Handler | Nguồn giao diện |
|---|---|---|
| `/` | `index()` | `frontend/dist/index.html` (fallback `web/index.html`), chèn `/cms/map-login.{css,js}` |
| `/admin` | `admin_index()` | React `AdminPage` |
| `/cms` → 302 `/cms/login` | `cms_index()` | — |
| `/cms/login`, `/hrm/login`, `/dashboard/kiosk`, `/dashboard/admin` | `cms_portal_page()` | `web/cms/index.html` |
| `/dashboard/user` | `user_dashboard_page()` | `web/user/index.html` |
| `/download`, `/go/<provider>` | | React |
| `/<path:p>` | `static_files()` | tìm trong `frontend/dist`, rồi `web/` |
| Kiosk | `/?device=<CODE>` | Bootstrap qua `/api/public/bootstrap?device=`, heartbeat `/api/public/heartbeat` |

Không có route `/m4l` hay `/api/m4l/*` trước khi triển khai.

## 4. Database thực tế (`data/xanh24.db`, đọc chế độ `mode=ro`)

`PRAGMA integrity_check` = `ok`, `journal_mode` = `wal`.

Bảng: `ads, api_keys, audit, categories, cms_accounts, cms_applications, cms_assignments, cms_content, cms_orders, cms_payments, cms_pins, cms_plans, devices, events, import_batches, mod_feedback, modules, pois, revisions, settings, transit_lines, transit_stops, user_discovery_preferences, user_saved_places, users, wards, webhooks`.

| Bảng | Số dòng | Ghi chú |
|---|---|---|
| `users` | 2 | Tài khoản legacy S0/S1/CW |
| `cms_accounts` | 5 | AREA 1, CONTENT 1, OWNER 1, REVIEW 1, USER 1 |
| `pois` | 67 | Đã publish: hành chính 47, di tích 10, du lịch 3, công viên 2, giao thông 2, dịch vụ công 1, mua sắm 1, y tế 1. **Ẩm thực / lưu trú / cafe: 0**. Cột `tags` trống toàn bộ |
| `categories` | 12 | gồm `an-uong` (Ẩm thực), `luu-tru` nhưng chưa có POI |
| `wards` | 51 | Có `cau-giay`, `nghia-do`, `yen-hoa` (khu vực pilot gợi ý) |
| `devices` | 1 | Kiosk: `code`, `lat/lng`, `active`, `gps_*`, `last_seen` |
| `cms_pins` | 1 | Ghim trả phí: chỉ hiển thị khi `active=1 AND approved_at AND expires_at>now` |
| `events` | 15 | Analytics thô kiosk/web (`/api/public/events`) |
| `user_saved_places` | 2 | |
| `user_discovery_preferences` | 1 | **Bảng còn sót**: có trong DB nhưng không còn được tham chiếu trong code hiện tại (từ bản thử trước — log `data/flask-user-discovery-v2.*`). Không đụng tới |

Quy tắc hiển thị POI công khai (lặp lại ở `app.py` `public_pois`, `public_poi`, `bootstrap` và `user_discovery.py`): `status='published' AND NOT EXISTS (cms_pins không còn hiệu lực)`.

Tọa độ POI: lat 20.73–21.14, lng 105.48–105.93.

## 5. Auth & phân quyền

- Hai hệ tài khoản song song, chung khóa ký JWT: `users` (S0/S1/CW, đăng nhập `/api/auth/login`, dùng cho `/admin`) và `cms_accounts` (đăng nhập `/api/cms/login` theo `section`, dùng cho `/cms/login`, `/hrm/login`, dashboards).
- Token CMS được frontend lưu ở `localStorage['x24_cms_token']` và gửi `Authorization: Bearer`. Không dùng cookie → **không cần CSRF token** cho các API Bearer. Token sống 12 giờ.
- `USER` tự đăng ký qua `/api/cms/register` (họ tên, ngày sinh, giới tính, email, SĐT). Sau đăng nhập, `web/cms/cms.js` luôn chuyển USER tới `/dashboard/user` (không có tham số quay lại).
- Phạm vi theo phường: `cms.wards()` trả `None` cho S0 (toàn quyền), tập phường cho vai trò khác; `in_scope(ward)`.
- Throttle đăng nhập in-memory trong `auth.py` (`login_throttled`) — mất khi restart, không chia sẻ giữa worker.

## 6. User Dashboard hiện có (`/dashboard/user`)

`web/user/user.js` (vanilla ES module): yêu cầu token USER (không có chế độ guest); tải toàn bộ `/api/public/pois` rồi **lọc/tìm/xếp hạng trên client**; khoảng cách tính bằng haversine trên client; lưu địa điểm qua `/api/user/saved`. Lời chào dùng tên cuối của `full_name`. Không có mood, random, voucher, fog.

## 7. Kiosk

- Thiết bị = bảng `devices`; mã thiết bị trong URL `?device=`; quản lý qua `/api/admin/devices` (S1) và `/api/cms/kiosks`.
- **“Tài khoản kiosk” trong CMS (`OWNER`) là người mua ghim (đối tác)**, không phải thiết bị kiosk. Đây là điểm dễ nhầm khi đọc spec (spec gọi “Kiosk Service” và “Partner”).
- Không có cơ chế định danh thiết bị bằng khóa bí mật: heartbeat chỉ dựa vào `device` code (công khai trong URL). Phase 4 cần thêm khóa riêng cho kiosk check-in.

## 8. Những gì liên quan M4L đã có / chưa có

| Năng lực | Hiện trạng |
|---|---|
| Danh sách POI công khai, chi tiết, ảnh, khoảng cách | **Có** (`/api/public/pois`, `/api/public/pois/<id>`) |
| Phân loại POI | **Có** theo `category`; cột `tags` tồn tại nhưng trống |
| Mood | **Chưa có** |
| Random | **Chưa có** |
| Lưới / fog / unlock | **Chưa có**; có ranh giới phường (`wards.geometry`) và `geoutil.point_in_geom`, `haversine_m` |
| Voucher | **Chưa có** |
| Đối tác | **Có một phần**: OWNER + `cms_pins` + gói/đơn/thanh toán demo + hồ sơ đăng ký đối tác |
| Quảng cáo | **Có** bảng `ads` cho màn hình chờ kiosk (khác native sponsorship) |
| Analytics | **Có thô**: bảng `events`, không chống trùng, không funnel |
| Audit log | **Có** bảng `audit` |

## 9. Baseline test & build (trước khi sửa code)

Môi trường: Windows 11, `.venv` Python 3.12.4, Node v24.21.0. Mỗi test tự tạo DB tạm trong `tests/` hoặc `%TEMP%` — không chạm `data/xanh24.db` (trừ `test_frontend_static.py` chỉ đọc file tĩnh).

```
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/<file>.py
```

| Test | Kết quả |
|---|---|
| `tests/test_api.py` | `TẤT CẢ 43 KIỂM THỬ ĐẠT` |
| `tests/test_cell_images.py` | `ĐẠT` |
| `tests/test_cms.py` | `CMS lifecycle and scope checks passed` |
| `tests/test_cms_applications.py` | `CMS application intake, scope, approval and email checks passed` |
| `tests/test_cms_portals.py` | `CMS public user and portal route checks passed` |
| `tests/test_download.py` | exit 0 |
| `tests/test_partner_registration.py` | `Partner registration and regional document checks passed` |
| `tests/test_frontend_static.py` | **FAIL (có sẵn từ trước)**: `test_pages_and_bundles` khẳng định HTML của `/` giống hệt `/admin`, nhưng `index()` chèn `map-login.css/js` vào `/` → khác. Test lỗi thời so với code; không do M4L gây ra |

```
npm.cmd --prefix frontend run build   →  ✓ built in 1.41s
```

## 10. Rủi ro đã nhận diện

1. Dữ liệu POI thật không có quán ăn/cafe → mood “Góc chạy deadline”, “Ẩm thực đêm khuya” sẽ **trống** cho tới khi có dữ liệu thật. Không được bịa POI.
2. Hai hệ auth — M4L phải chọn một: dùng **CMS token** (vì USER chỉ tồn tại trong `cms_accounts`).
3. Postgres trên Vercel: SQL mới phải chạy được qua `_PgConn` (không cú pháp SQLite-only).
4. `web/sw.js` (đăng ký bởi trang bản đồ) dùng stale-while-revalidate cho mọi file tĩnh cùng origin không thuộc danh sách loại trừ → JS của `/m4l` có thể cũ một lượt sau khi cập nhật; điều hướng offline rơi về trang `/`.
5. Rate limit in-memory không chia sẻ giữa gunicorn worker → quota random/claim (Phase 2–3) phải dựa vào DB.
6. Working tree chưa commit — rủi ro mất việc nếu thao tác git sai.
