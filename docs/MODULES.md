# Cổng mở rộng module

Xanh24 - Maps for Life có 3 lớp mở rộng để bổ sung tính năng mà **không sửa mã lõi**:

## 1. Module giao diện (iframe) — hiển thị trên kiosk / web
Đăng ký tại *Dashboard → Module mở rộng* (Admin S0): mã, tên, biểu tượng, màu, `entry_url`.
Khi người dùng mở, ứng dụng tải `entry_url?device=…&ward=…&lang=…&lat=…&lng=…` trong khung toàn màn hình, sau đó gửi:

```js
{ type: 'x24:context', app: 'xanh24-maps', module: 'feedback', device: 'HK-01', ward: 'hoan-kiem', lang: 'vi', lat: 21.03, lng: 105.85 }
```

Module có thể gửi ngược về ứng dụng bằng `parent.postMessage(msg, '*')`:

| Thông điệp | Tác dụng |
|---|---|
| `{type:'x24:openPoi', id}` | Đóng module, mở chi tiết địa điểm |
| `{type:'x24:route', id, mode:'foot'\|'bike'\|'driving'\|'transit'}` | Đóng module, chỉ đường tới địa điểm |
| `{type:'x24:toast', text}` | Hiện thông báo ngắn |
| `{type:'x24:track', module, data}` | Ghi nhận thống kê vào Dashboard |
| `{type:'x24:close'}` | Đóng module |

Đặt tệp tĩnh trong `web/modules/<ten-module>/` (phục vụ tại `/modules/<ten-module>/…`) hoặc dùng URL `https://` bên ngoài. Mẫu: `web/modules/sample/feedback.html`, `weather.html`.
Module kiểu **link** trên kiosk hiển thị QR để mở trên điện thoại người dân.

## 2. Module máy chủ (Python)
Tạo `server/modules/<ten>.py` có hàm `register(app, ctx)` — tự nạp khi khởi động:

```python
def register(app, ctx):
    ctx.ex("CREATE TABLE IF NOT EXISTS mod_x(...)")
    @app.route("/api/modules/x/items", endpoint="mod_x_items")
    @ctx.require("poi.read")            # phân quyền S0/S1/CW
    def items(): ...
```
`ctx` gồm: `q`, `ex` (SQLite), `require(perm)`, `audit`, `get_setting`, `set_setting`, `fire_webhook`. Quy ước route: `/api/modules/<key>/…`, bảng dữ liệu: `mod_<key>_…`. Mẫu: `server/modules/example_feedback.py`.

## 3. Tích hợp hệ thống ngoài
- **API công khai** (không cần khoá): `/api/public/*` — xem `docs/API.md`.
- **API key chỉ đọc** cho `/api/admin/*` (GET) qua header `X-API-Key`.
- **Webhook** ký HMAC-SHA256 (`X-Xanh24-Signature: sha256=…`) cho các sự kiện `poi.*`, `revision.*`, `ward.updated`, `module.*`.
- **Nguồn dữ liệu nền** có thể thay: bản đồ nền (tile), máy chủ định tuyến (OSRM/Valhalla tương thích), deep link gọi xe — tại *Cấu hình*.
