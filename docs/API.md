# API

Tất cả trả JSON UTF-8. Lỗi: `{ "error": "..." }` với mã HTTP 4xx/5xx.

## Công khai (kiosk / web / đối tác)
| Phương thức | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/api/health` | Kiểm tra dịch vụ |
| GET | `/api/public/bootstrap?device=CODE` | Cấu hình, danh mục, phường, module, thông tin thiết bị |
| GET | `/api/public/wards.geojson` | Ranh giới phường (WGS84) |
| GET | `/api/public/pois?ward=&category=a,b&featured=1` | Danh sách địa điểm công khai (rút gọn) |
| GET | `/api/public/pois/{id}` | Chi tiết + VR360 + điểm dừng giao thông gần |
| GET | `/api/public/transit` | Tuyến & trạm xe buýt/metro |
| GET | `/api/public/ads?device=CODE` | Danh sách quảng cáo đang phát cho thiết bị |
| GET | `/api/public/route?from=lng,lat&to=lng,lat&mode=foot\|bike\|driving&lang=vi` | Chỉ đường (proxy OSRM, dự phòng ước lượng) |
| GET | `/api/public/reverse?lat=&lng=&lang=vi` | Thông tin điểm bất kỳ: phường (ranh giới nội bộ) + địa chỉ (Nominatim/OSM, có đệm) |
| GET | `/api/public/version` | `data_version`, `config_version`, `kiosk_app` — kiosk/ứng dụng Android dùng để tự cập nhật |
| POST | `/api/public/events` | Thống kê: `{device, session, events:[{type, poi_id, ward, data, at}]}` |
| POST | `/api/public/heartbeat` | Kiosk báo trực tuyến: `{device, screen}` |
| POST | `/api/public/kiosk/unlock` | Kiểm tra PIN menu thiết bị |
| GET | `/go/{grab\|xanhsm}?lat&lng&name&addr` | Trang trung gian mở ứng dụng gọi xe trên điện thoại |

## Quản trị (Bearer token từ `/api/auth/login`, hoặc `X-API-Key` chỉ đọc)
- `POST /api/auth/login` `{username,password}` → `{token,user}` · `GET /api/auth/me` · `POST /api/auth/password`
- Địa điểm: `GET/POST /api/admin/pois`, `GET/PUT/DELETE /api/admin/pois/{id}` (`mode`: `draft` \| `submit` \| `publish`), `POST /api/admin/pois/{id}/status`
- Phê duyệt: `GET /api/admin/revisions?status=pending`, `GET/PUT /api/admin/revisions/{id}`, `POST /api/admin/revisions/{id}/{submit|approve|reject|cancel}`, `POST /api/admin/revisions/bulk`
- Nhập Excel: `GET /api/admin/import/template`, `POST /api/admin/import/preview` (multipart `file`, `zip`), `POST /api/admin/import/{batch}/commit`
- Tải tệp: `POST /api/admin/upload` (multipart `file`, `kind`=image\|pano\|video)
- Khác: `ads`, `devices`, `wards` (+ `export.geojson`), `categories`, `transit/stops`, `transit/lines`, `users`, `settings`, `modules`, `webhooks`, `apikeys`, `audit`, `stats`

Ma trận quyền: `GET /api/admin/meta`.

## M4L 2.0 (chỉ có khi `XANH24_M4L_ENABLED=1`)
Lỗi: `{ "error": "...", "code": "INVALID_PARAMETER|INVALID_LOCATION|MOOD_NOT_FOUND|FORBIDDEN|NOT_FOUND|CONFLICT|M4L_UNAVAILABLE" }`. Token: Bearer token CMS (`/api/cms/login`). Chi tiết: `docs/m4l/ARCHITECTURE.md`.

| Phương thức | Đường dẫn | Quyền | Mô tả |
|---|---|---|---|
| GET | `/api/m4l/home` | Tùy chọn | Lời chào (chỉ USER), mood, cờ tính năng |
| GET | `/api/m4l/moods` | — | Mood đang bật + số địa điểm công khai |
| GET | `/api/m4l/discovery?mood=&q=&category=&lat=&lng=&radius=&limit=&cursor=` | — | Địa điểm lọc theo mood, xếp hạng xác định |
| GET/POST | `/api/m4l/admin/moods` | GET: S0, CONTENT · POST: S0 | Danh sách / tạo mood |
| PUT | `/api/m4l/admin/moods/{id}` | S0 | Sửa mood (không đổi slug) |
| GET | `/api/m4l/admin/pois?q=&mood=` | S0, CONTENT (theo phường) | Địa điểm kèm mood đã gán |
| PUT | `/api/m4l/admin/pois/{id}/moods` | S0, CONTENT (theo phường) | `{moods:[{id, reason}]}` thay tập mood của địa điểm |
| POST | `/api/m4l/discovery/random` | USER | Đúng 1 địa điểm (hoặc `item:null`), quota/cooldown theo tài khoản |
| GET | `/api/m4l/exploration?area=` | Tùy chọn | Lưới ô, ô đã mở, tiến độ, ghim bí ẩn |
| POST | `/api/m4l/exploration/unlock` | USER | `{samples:[{lat,lng,accuracy,t}]}` → mở khóa idempotent |
| GET | `/api/m4l/exploration/progress?area=` | USER | Ô đã mở / ô đủ điều kiện |
| DELETE | `/api/m4l/exploration/me` | USER | Xóa dữ liệu khám phá của mình |
| GET | `/api/m4l/mystery-pins?area=` | Tùy chọn | Ghim đã xuất bản (chưa mở: chỉ lời gợi ý) |
| GET/POST | `/api/m4l/admin/areas` · POST `/{id}/regenerate` · PUT `/{id}` | S0 (GET: + CONTENT) | Khu vực khám phá và lưới |
| GET/POST/PUT | `/api/m4l/admin/pins` | S0, CONTENT (theo phường) | Ghim bí ẩn |
| GET | `/api/m4l/exploration?area=&bbox=minLng,minLat,maxLng,maxLat&level=auto\|cells\|blocks` | Tùy chọn | (v3) Lưới theo khung nhìn: ô `[gx,gy,mã]` khi ≤ 8.000 ô, ngược lại khối 1 km; không bao giờ trả cả thành phố |
| GET | `/api/m4l/exploration/progress?area=&breakdown=unit` | USER | (v3) kèm `unlocked_pending`, `pending_review`, `complete`, theo phường/xã |
| GET | `/api/m4l/areas` · `/api/m4l/areas/{slug}/boundary` | — | Danh sách khu; ranh giới + nguồn/giấy phép |
| GET | `/api/m4l/admin/areas/{id}/stats` · `/changes` | S0, CONTENT | Thống kê ô/phường/người khám phá; nhật ký lưới |
| POST | `/api/m4l/admin/inspect` | S0, CONTENT | `{lat,lng}` → ô, trạng thái, phường/xã ở mọi khu |
| GET/POST | `/api/m4l/admin/zones` · PUT `/{id}` | GET S0/CONTENT · ghi S0 | Vùng hạn chế/loại trừ có nguồn; mỗi thay đổi tăng `classification_version` |


## M4L 2.0 — voucher, đối tác, kiosk, analytics

Xem `docs/m4l/API_CONTRACT.md` (các route `/api/m4l/offers`, `/vouchers*`, `/events`, `/kiosk/*`, `/partner/*`, `/admin/campaigns|kiosks|analytics`).
