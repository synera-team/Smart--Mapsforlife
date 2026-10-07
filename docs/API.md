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
