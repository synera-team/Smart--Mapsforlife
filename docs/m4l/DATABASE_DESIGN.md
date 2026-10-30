# M4L 2.0: Thiết kế CSDL

Tất cả bảng M4L nằm ngoài `db.SCHEMA` và chỉ được tạo bởi `server/m4l_migrations.py` khi bật cờ. Bảng cũ không bị sửa cấu trúc. Hệ thống chạy SQLite (WAL) và có nhánh Postgres qua `db._PgConn`.

## Bảng cũ được tham chiếu (không sửa)

| Bảng | Dùng cho |
|---|---|
| `cms_accounts` | USER, OWNER (đối tác), AREA, CONTENT; cột `active` = khóa đối tác |
| `users` (S0) | Quản trị hệ thống |
| `cms_assignments` | OWNER ↔ POI đang quản lý |
| `cms_pins` | Hạn hiển thị của ghim đối tác (quy tắc công khai) |
| `pois`, `wards` | Địa điểm, phường |
| `devices` | Kiosk |
| `audit` | Nhật ký thao tác nhạy cảm |

## Theo phiên bản migration

| v | Bảng |
|---|---|
| 1 | `m4l_moods`, `m4l_poi_moods` |
| 2 | `m4l_areas`, `m4l_cells`, `m4l_user_unlocks`, `m4l_location_state`, `m4l_mystery_pins`, `m4l_discovery_events` |
| 3 | `m4l_units`, `m4l_area_sources`, `m4l_zones`, `m4l_grid_changes`; cột `kind`, `classification_version`, `status`, `base_status`, `unit_slug` |
| 4 | `m4l_campaigns`, `m4l_voucher_templates`, `m4l_vouchers`, `m4l_kiosk_keys`, `m4l_kiosk_sessions`, `m4l_events` |

## Chi tiết v4

**`m4l_campaigns`**:
- `kind` ∈ {`mood_sponsor`, `vip_spin`, `kiosk_o2o`}; `partner_account_id` (OWNER); `poi_id`; `mood_id`.
- Phạm vi địa lý: `center_lat/lng` + `radius_m` (NULL = toàn thành phố); `starts_at`, `ends_at`.
- Dữ liệu hợp đồng: `priority` (0–100), `package`, `exclusive`, `impression_cap`.
- `status` ∈ {draft, pending, approved, rejected, paused, ended}; `is_demo`; `review_note`, `reviewed_by`, `reviewed_at`.
- Index `(kind, status, ends_at)`.

**`m4l_voucher_templates`**: một mẫu cho mỗi chiến dịch (`campaign_id` UNIQUE), gồm `title`, `benefit`, `terms`, `ttl_minutes` (mặc định lấy từ cấu hình = 60), `issue_cap`, `per_user_cap`, `issued_count`, `status`.

**`m4l_vouchers`**:
- `code` UNIQUE (`token_urlsafe(18)`), `template_id`, `campaign_id`, `account_id`, `poi_id`.
- `source` ∈ {discovery, random, home, kiosk, pin}; `kiosk_session_id`; `idempotency_key`.
- `status` ∈ {issued, redeemed, expired, revoked}; `issued_at`, `expires_at`; `redeemed_at`, `redeemed_by`, `redeem_ref` (mã POS).
- UNIQUE `(account_id, idempotency_key)`. Index `(account_id, issued_at)`, `(campaign_id, status)`.

**`m4l_kiosk_keys`**: `device_id` PK, `key_hash` (SHA-256), `key_prefix` (9 ký tự để nhận diện), `created_by`, `created_at`, `revoked_at`.

**`m4l_kiosk_sessions`**: `token_hash` UNIQUE, `device_id`, `created_at`, `expires_at`, `used_at`, `account_id`.

**`m4l_events`**:
- `event_id` UNIQUE (chống trùng), `type` ∈ {impression, qr_scan, claim, nav_click, detail_view, redeem}.
- Các khóa liên kết: `account_id`, `campaign_id`, `poi_id`, `device_id`, `voucher_id`, `source`, `created_at`.
- Index `(campaign_id, type, created_at)`, `(created_at)`.

## Bất biến và cơ chế đồng thời

| Bất biến | Cơ chế |
|---|---|
| Không phát quá hạn mức | `UPDATE … SET issued_count=issued_count+1 WHERE issued_count<issue_cap`, kiểm `rowcount` trong `BEGIN IMMEDIATE` (Postgres: `pg_advisory_xact_lock` theo chiến dịch) |
| Mỗi người ≤ `per_user_cap` | Đếm trong cùng transaction |
| Bấm trùng không phát thêm | UNIQUE `(account_id, idempotency_key)` + trả lại voucher cũ |
| Không đổi hai lần | `UPDATE … WHERE status='issued' AND expires_at>now`, kiểm `rowcount` |
| Mã check-in dùng một lần | `UPDATE … WHERE used_at IS NULL`, kiểm `rowcount` |
| Hết hạn theo giờ server | `expires_at` do server đặt; mọi lần đổi đều kiểm lại hạn; ví ẩn `code` khi hết hạn |

`db._Cur` (Postgres) đã được bổ sung `rowcount` để các kiểm tra trên chạy đúng trên cả hai CSDL.

## Dữ liệu cá nhân

| Bảng | Dữ liệu cá nhân lưu |
|---|---|
| `m4l_events` | `account_id` (không lưu IP). Khách được gộp trùng bằng hash IP theo ngày, chỉ dùng làm `event_id` |
| `m4l_vouchers` | Gắn `account_id` theo yêu cầu “voucher gắn User ID” |

Không có bảng nào lưu lộ trình GPS.

## SQLite hay PostgreSQL/PostGIS

Truy vấn nặng nhất vẫn là lưới (đã đo ở `HANOI_SCALEUP.md`). Các bảng thương mại nhỏ và có index, nên SQLite đủ cho pilot. Đề xuất chuyển Postgres khi có tải thật hoặc chạy nhiều tiến trình ghi đồng thời (Vercel). Nhánh Postgres có trong code nhưng **chưa được chạy thử** (Q13).
