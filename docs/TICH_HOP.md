# Xanh24 - Maps for Life — Hồ sơ tích hợp (v1.1.0)

Tài liệu này dành cho phiên Claude ở dự án khác cần kết nối vào **Xanh24 - Maps for Life**. Mã nguồn đầy đủ: `Xanh24-MapsForLife-v1.0.1.zip` (đọc thêm `README.md`, `docs/API.md`, `docs/MODULES.md` trong gói).

## 1. Tổng quan
- Bản đồ số 51 phường/xã Hà Nội (sau 01/07/2025) cho màn hình LCD Android tương tác (kiosk), web và mobile. Có dashboard quản trị riêng.
- Máy chủ: Python 3.10+, Flask, SQLite (WAL), JWT (PyJWT), openpyxl, Pillow. Cổng mặc định 8024.
- Giao diện: HTML + JS thuần (ES modules), MapLibre GL JS 5.24 (đóng gói sẵn trong `web/vendor/`), không có bước build.
- Bản đồ nền: OpenFreeMap (vector). Chỉ đường: OSRM qua `/api/public/route`. Dữ liệu xe buýt: OSM Overpass.
- Phân quyền: **S0** (toàn quyền) · **S1** (duyệt, sửa, công khai) · **CW** (Co-worker: nhập liệu, xin duyệt; có thể giới hạn theo phường). Mọi thay đổi địa điểm đi qua bản sửa đổi (revision): nháp → chờ duyệt → duyệt/từ chối.
- Nhận diện: tên "Xanh24 - Maps for Life", màu chủ đạo xanh navy `#14346F`/`#0B1B3F` và xanh lá `#0FA968`/`#22C98A`, font Be Vietnam Pro. Chân trang: "Bản quyền thuộc về Công ty TNHH Công nghệ và Truyền thông Xanh24".

## 2. Ba cách kết nối (không sửa mã lõi)

### A. Module giao diện (iframe) — hiện trên kiosk/web
- Đăng ký tại *Dashboard → Module mở rộng* (S0) với: mã, tên, biểu tượng, màu, `entry_url` (đường dẫn `/modules/<ten>/…` hoặc URL `https://` ngoài).
- Ứng dụng mở `entry_url?device=&ward=&lang=&lat=&lng=` toàn màn hình, rồi gửi vào module:
  `{type:'x24:context', app:'xanh24-maps', module, device, ward, lang, lat, lng}`
- Module gửi ngược lại bằng `parent.postMessage(msg,'*')`:

| Thông điệp | Tác dụng |
|---|---|
| `{type:'x24:openPoi', id}` | Mở chi tiết địa điểm |
| `{type:'x24:route', id, mode}` | Chỉ đường, `mode` = `foot`, `bike`, `driving` hoặc `transit` |
| `{type:'x24:toast', text}` | Hiện thông báo ngắn |
| `{type:'x24:track', module, data}` | Ghi thống kê |
| `{type:'x24:close'}` | Đóng module |

- Lưu ý kiosk: sau 40 giây không thao tác, ứng dụng tự đóng module và về màn hình chờ. Module nên thiết kế cho màn cảm ứng: nút lớn, không cần bàn phím thật.
- Mẫu có sẵn: `web/modules/sample/feedback.html`, `weather.html`.

### B. Module máy chủ (Python)
- Tạo tệp `server/modules/<key>.py` có hàm `register(app, ctx)`. Tệp được tự nạp khi khởi động.
- `ctx` cung cấp: `q`/`ex` (truy vấn SQLite), `require(perm)`, `audit`, `get_setting`, `set_setting`, `fire_webhook`.
- Quy ước: route `/api/modules/<key>/…`, bảng dữ liệu `mod_<key>_…`, tên endpoint không trùng.
- Mẫu: `server/modules/example_feedback.py`.

### C. Gọi API từ hệ thống ngoài
- Công khai, không cần khóa (`/api/public/*`):
  - `bootstrap?device=`
  - `wards.geojson`
  - `pois?ward=&category=&featured=`
  - `pois/{id}`
  - `transit`
  - `ads?device=`
  - `route?from=lng,lat&to=lng,lat&mode=&lang=`
  - `reverse?lat=&lng=` (địa chỉ + phường của điểm bất kỳ)
  - `version` (mốc dữ liệu để tự cập nhật)
  - `events` (POST)
  - `heartbeat` (POST)
- Quản trị (`/api/admin/*`):
  - Xác thực bằng `Authorization: Bearer <token>`, lấy token từ `POST /api/auth/login`.
  - Hoặc dùng header `X-API-Key` (chỉ đọc, chỉ cho GET).
- Webhook: ký HMAC-SHA256, header `X-Xanh24-Signature: sha256=…`. Sự kiện: `poi.*`, `revision.*`, `ward.updated`, `module.*`.
- Lỗi luôn trả `{ "error": "..." }`. Ma trận quyền xem ở `GET /api/admin/meta`.

- Mở bản đồ tại một điểm bất kỳ: `/?pt=lat,lng&name=Tên` (thêm `&dir=foot|bike|driving|transit` để chỉ đường ngay).
- Ứng dụng kiosk Android (`android/`) cung cấp `window.X24Android` cho trang web: `info()`, `openSettings()`, `reload()`.

## 3. Nguyên tắc khi tích hợp
1. Ưu tiên thứ tự A → B → C. Chỉ sửa mã lõi (`server/app.py`, `web/js/app.js`) khi không thể làm bằng module; nếu buộc phải sửa, ghi rõ tệp và dòng thay đổi.
2. Giữ phân quyền S0/S1/CW và quy trình duyệt: dữ liệu công khai phải qua duyệt.
3. Giao diện song ngữ Việt–Anh, dùng đúng màu và font Xanh24, chạy tốt trên kiosk ngang 1920×1080, kiosk dọc 1080×1920 và điện thoại.
4. Bàn giao gồm: mã module, hướng dẫn đăng ký trong Dashboard, cách kiểm thử (`python tests/test_api.py` phải vẫn đạt).
