# M4L 2.0: Hợp đồng API

Mọi route chỉ tồn tại khi `XANH24_M4L_ENABLED=1`; khi tắt cờ, route trả 404. Lỗi luôn có dạng `{"error": "<thông điệp tiếng Việt>", "code": "<MÃ>"}`.

Xác thực:
- Người dùng và nhân viên gửi `Authorization: Bearer <token CMS>`. Token S0 kiểu cũ dùng được cho các route admin.
- Kiosk gửi `X-Kiosk-Key`.

Thời gian là epoch giây theo **giờ máy chủ**. Route có voucher trả thêm `server_time` để client tính đồng hồ đếm ngược.

## Công khai / người dùng

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/m4l/home` | Khách / USER | Mood, tính năng, tiến độ, `vouchers {active, next}` |
| GET | `/api/m4l/moods` | Khách | Mood đang bật |
| GET | `/api/m4l/discovery?mood&q&category&lat&lng&radius&limit&cursor` | Khách | Danh sách tự nhiên kèm `offer`. Có `sponsored` (một ô có nhãn) khi có mood, trang đầu và không có từ khóa/danh mục |
| POST | `/api/m4l/discovery/random` `{mood?, lat?, lng?}` | USER | Một địa điểm duy nhất. Trả `mode: vip|organic`, `reason`, `remaining`, `item.offer`. Lỗi: `QUOTA_EXCEEDED`, `COOLDOWN` (429). Trường hợp rỗng: `NO_ELIGIBLE_POI` / `NO_VIP_PARTNER`, không trừ lượt |
| GET | `/api/m4l/offers?lat&lng&limit` | Khách | Ưu đãi đối tác đang chạy (không gồm kiosk), có ghi impression |
| GET | `/api/m4l/vouchers` | USER | Ví voucher. Chỉ voucher còn hạn mới có `code` |
| GET | `/api/m4l/vouchers/<id>` | USER (chủ voucher) | Chi tiết voucher; người khác nhận 404 |
| POST | `/api/m4l/vouchers/claim` `{campaign_id, source, idempotency_key?, kiosk_session_id?}` | USER | Trả 201 khi phát hành; 200 + `replayed` khi trùng `idempotency_key`. Lỗi 409: `CAMPAIGN_NOT_ACTIVE`, `ALREADY_CLAIMED`, `SOLD_OUT`, `NO_VOUCHER`. Lỗi 403: `KIOSK_REQUIRED`, `KIOSK_SESSION_EXPIRED`, `OUT_OF_KIOSK_RANGE` |
| POST | `/api/m4l/events` `{type: nav_click|detail_view, event_id, campaign_id?, poi_id?, voucher_id?, source?}` | Khách / USER | `event_id` dài 8–64 ký tự, chống ghi trùng; các loại khác trả 400 |
| GET | `/api/m4l/exploration?bbox&level&area` | Khách / USER | Lưới theo khung nhìn (xem `HANOI_SCALEUP.md`) |
| GET | `/api/m4l/exploration/progress?breakdown=unit` | USER | Tiến độ toàn thành phố, theo phường/xã |
| POST | `/api/m4l/exploration/unlock` `{samples:[…]}` | USER | Mở khóa bằng GPS kiểm tra ở server; trả `revealed_pins` |
| DELETE | `/api/m4l/exploration/me` | USER | Xóa dữ liệu khám phá |
| GET | `/api/m4l/mystery-pins?bbox` | Khách / USER | Ghim chưa mở chỉ lộ lời gợi ý và tâm ô |

## Kiosk

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| POST | `/api/m4l/kiosk/ticket` `{device, current?}` | Kiosk (`X-Kiosk-Key`) | `{token, path:"/m4l/k/<token>", expires_at}`. Mã còn hiệu lực và chưa dùng thì trả lại mã cũ. Lỗi: 401 `KIOSK_UNAUTHORIZED`, 403 `KIOSK_DISABLED`, 409 `KIOSK_NO_LOCATION`, 429 `RATE_LIMITED` |
| POST | `/api/m4l/kiosk/checkin` `{ticket}` | USER | `{session_id, kiosk, offers[]}`. Lỗi: 404 `INVALID_TICKET`, 409 `TICKET_USED`, 410 `TICKET_EXPIRED` |

## Đối tác (OWNER)

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/api/m4l/partner/me` | POI, mood đã gắn, chiến dịch kèm phễu, `pos_adapter` |
| POST | `/api/m4l/partner/campaigns` | Tạo nháp. Body: `{kind, name, mood?, radius_m?, starts_at, ends_at, priority?, package?, exclusive?, impression_cap?, voucher?{title, benefit, terms?, ttl_minutes?, issue_cap, per_user_cap?}}` |
| PUT | `/api/m4l/partner/campaigns/<id>` | Sửa chiến dịch nháp/bị từ chối; sau khi sửa, chiến dịch về trạng thái nháp |
| POST | `/api/m4l/partner/campaigns/<id>/submit` | Chuyển nháp sang chờ duyệt |
| POST | `/api/m4l/partner/vouchers/check` `{code}` | Xem trạng thái, không đổi (OWNER của POI đó hoặc S0) |
| POST | `/api/m4l/partner/vouchers/redeem` `{code}` | Đổi nguyên tử. Lỗi: 409 `ALREADY_REDEEMED`, 410 `EXPIRED`/`REVOKED`, 404 khi voucher thuộc cửa hàng khác |

## Quản trị

| Method | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/m4l/admin/campaigns?status` | S0, AREA (theo phường) | Danh sách chiến dịch |
| POST | `/api/m4l/admin/campaigns/<id>/review` `{action: approve|reject|pause|resume|end, note}` | S0, AREA | Bắt buộc `note` khi `reject`. Lỗi 409: `EXCLUSIVE_CONFLICT`, `MOOD_MISMATCH`, `PARTNER_LOCKED`, `CAMPAIGN_EXPIRED`, `INVALID_STATE` |
| GET | `/api/m4l/admin/kiosks` | S0, AREA | Trạng thái khóa của từng kiosk |
| POST / DELETE | `/api/m4l/admin/kiosks/<id>/key` | S0, AREA | Cấp khóa (chỉ hiện một lần) / thu hồi |
| GET | `/api/m4l/admin/analytics?days` | S0, AREA | Phễu tổng hợp, không có dữ liệu cá nhân |
| … | `/api/m4l/admin/moods`, `pois/<id>/moods`, `areas`, `zones`, `inspect`, `pins` | Như Phase 1–2 | Xem `docs/API.md` |

## Trang

| Đường dẫn | Mô tả |
|---|---|
| `/m4l` | Trang chủ |
| `/m4l/discover` | Khám phá |
| `/m4l/world` | Thế giới |
| `/m4l/vouchers` | Ví voucher |
| `/m4l/k/<mã>` | Trang check-in sau khi quét QR tại trạm |
| `/m4l/partner` | Cổng đối tác |
| `/m4l/v/<mã>` | Trang nhân viên quét QR voucher |
| `/m4l/station` | Màn hình trạm |
| `/m4l/admin` | Trang quản trị |
