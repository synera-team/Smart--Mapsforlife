# M4L 2.0: Phân tích khoảng trống (audit 29/10/2026)

Bản này đối chiếu PDF (P0) và hai mockup (P1) với code lúc **bắt đầu** đợt hoàn thiện, rồi ghi phần đã xử lý. Chi tiết từng yêu cầu nằm trong `REQUIREMENT_TRACEABILITY.md`.

## 1. Tầm nhìn trong PDF (tóm tắt)

“Kinh doanh cảm xúc, Vận hành thực dụng.” M4L không phải công cụ tra bản đồ mà là **trợ lý phong cách sống** cho người “không biết đi đâu”. Sản phẩm có hai lớp:

- **B2C (lớp trò chơi):**
  - bản đồ sương mù Hà Nội, sáng dần theo nơi đã đi, có % khám phá và ghim bí ẩn;
  - lời chào theo tên và các nút mood;
  - hộp mù “lắc máy” trả về đúng một địa điểm;
  - mọi gợi ý kèm một voucher đếm ngược 60 phút để thúc người dùng đi ngay.
- **B2B (lớp thu tiền):**
  - tài trợ độc quyền một mood trong bán kính;
  - Random VIP lấy trong nhóm đối tác trả phí cao nhất trong ngày;
  - kiosk Xanh24 dẫn khách tới đối tác cách trạm khoảng 200 m;
  - tính phí theo khách thực tế, đo bằng voucher.
- **Kỹ thuật:** filter DB thay vì AI, `random()` từ danh sách VIP, countdown gắn User ID, lưới hoặc geofence, overlay trong suốt, API tới POS/kiosk.

## 2. Thực trạng lúc audit

| Nhóm | Thực trạng | Phân loại |
|---|---|---|
| Home, mood, discovery | Có, chạy với dữ liệu thật; DB thật chưa có POI F&B nên mood trống | Có, thiếu dữ liệu |
| Random | Có quota/cooldown/không lặp/chống race, nhưng rút từ **mọi POI có mood**, không phải pool VIP | **Làm sai so với PDF (P0)** |
| Fog of War toàn Hà Nội | Có (migration v3, 337.035 ô); đã kiểm lại trên dữ liệu hiện tại | Có |
| Mystery Pins | Có backend; UI là icon tĩnh, mở khóa chỉ báo toast, không có chỉ đường | Thiếu UX (P1) |
| Pioneer Voucher 60 phút | Không có | **Thiếu (P0)** |
| Mood Sponsorship | Không có | **Thiếu (P0)** |
| VIP Random Spin | Không có | **Thiếu (P0)** |
| Kiosk O2O | Có bảng `devices` + mã thiết bị công khai; không có check-in an toàn | **Thiếu (P0)** |
| Analytics funnel | Chỉ có bảng `events` chung của kiosk | **Thiếu (P0)** |
| Cổng đối tác | Tài khoản OWNER chỉ quản lý nội dung ghim | **Thiếu (P0)** |
| Đăng nhập quay lại M4L | `cms.js` luôn chuyển USER sang `/dashboard/user` (A8) | Lỗi trải nghiệm (P1) |
| Khối Pioneer Voucher trên Home (mockup) | Không có | Thiếu (P1) |
| Bố cục Thế giới như mockup | Thẻ tiến độ nằm trên bản đồ, chưa toàn màn hình | Lệch UI (P2) |

## 3. Module đã bổ sung

| Module | Mục đích | Tái sử dụng |
|---|---|---|
| Migration v4 `commerce_vouchers_kiosk` | 6 bảng mới: chiến dịch, mẫu voucher, voucher, khóa kiosk, phiên check-in, sự kiện | Khung migration v1–v3, backup tự động |
| `server/m4l_commerce.py` | Chiến dịch, duyệt, độc quyền, chọn tài trợ, pool VIP, voucher, kiosk, phễu analytics, `MockPOS` | `cms_accounts` OWNER + `cms_assignments` (đối tác), `devices` (kiosk), `audit` |
| Route trong `server/m4l.py` | `/api/m4l/offers`, `vouchers*`, `events`, `kiosk/*`, `partner/*`, `admin/campaigns|kiosks|analytics` | Decorator `staff()`, `record()` |
| `random_pick()` | Pool VIP + fallback cấu hình được | Quota/cooldown sẵn có |
| `web/m4l/m4l.js` | Khối Pioneer Voucher, ô tài trợ, nhận voucher, ví, check-in kiosk | `qr.js` sẵn có |
| `web/m4l/partner.*`, `station.*` | Cổng đối tác + xác nhận voucher; màn hình trạm | CSS M4L |
| `web/m4l/admin.js` | Duyệt chiến dịch, cấp khóa kiosk, analytics; mở cho AREA | Trang admin sẵn có |
| `world.js` | Ghim phát sáng, hộp thoại hé lộ, chỉ đường, trạng thái “Đã khám phá” | — |
| `web/cms/cms.js` | `?next=/m4l/…` (chỉ đường dẫn /m4l) | — |
| `server/seed_m4l_demo.py` | Demo tái lập được, gắn nhãn | API thật (đi qua kiểm tra quyền) |

Không tạo hệ đăng nhập mới, không tạo bộ quản lý địa điểm mới, không tạo vai trò mới.

## 4. Chưa làm được và lý do

| Gap | Lý do | Hướng xử lý |
|---|---|---|
| Voucher cho **mọi** gợi ý (R10) | Địa điểm không phải đối tác thì không có ai phát hành ưu đãi | Sếp quyết: chỉ đối tác, hay Xanh24 tự tài trợ ưu đãi chung (D-C1) |
| Thu phí theo foot traffic (R16) | Không làm thanh toán khi chưa được duyệt; voucher chỉ đo được lượt đổi | D-C4 |
| “Trả tiền là được gắn tag” (R17) | Có thể gắn sai mood cho POI (ví dụ trụ sở hành chính) | Giữ bước kiểm duyệt nội dung, chờ xác nhận (A3) |
| POS thật (R22) | Chưa có API/quyền | Adapter `MockPOS`; thay bằng adapter thật khi có |
| Quét thẻ tại trạm (R15) | Chưa rõ phần cứng thẻ/NFC | Chỉ QR (D9) |
| Bố cục Thế giới toàn màn hình (M02) | Ưu tiên chức năng; đổi bố cục cần kiểm lại trên máy thật | P2 |
| Điện thoại thật, Postgres | Không có trong môi trường | Xem `RELEASE_READINESS.md` |
