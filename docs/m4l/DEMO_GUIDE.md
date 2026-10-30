# M4L 2.0: Hướng dẫn demo

Toàn bộ dữ liệu demo có tên “[DEMO] …” và cờ `is_demo=1`. Đây **không** phải đối tác hay ưu đãi thật. Không có thanh toán, và POS chỉ là bản giả lập.

## 1. Dựng môi trường (máy dev)

```sh
# 1. Tạo thư mục demo, chép một bản DB (KHÔNG dùng data/xanh24.db trực tiếp)
mkdir -p /path/demo && python -c "import sqlite3; s=sqlite3.connect('data/xanh24.db'); d=sqlite3.connect('/path/demo/xanh24.db'); s.backup(d)"
# 2. Migrate + seed (script từ chối data/xanh24.db và Postgres)
cd server && XANH24_M4L_ENABLED=1 XANH24_DATA_DIR=/path/demo XANH24_DB=/path/demo/xanh24.db python seed_m4l_demo.py
# 3. Chạy server
cd .. && XANH24_M4L_ENABLED=1 XANH24_DATA_DIR=/path/demo XANH24_DB=/path/demo/xanh24.db PORT=8125 python server/app.py
```

Tài khoản (mật khẩu ngẫu nhiên) và khóa kiosk nằm trong `/path/demo/M4L_DEMO_ACCOUNTS.txt`. Chạy seed lần thứ hai sẽ không làm gì.

## 2. Dữ liệu demo

| Loại | Nội dung |
|---|---|
| Tài khoản | 1 S0 (`m4l_demo_admin`), 1 nhân viên quản lí khu vực (`m4l_demo_manager`), 1 người dùng (`m4l_demo_user`), 5 đối tác (`m4l_demo_cafe`, `_bun`, `_tra`, `_banh`, `_gym`) |
| Địa điểm | 5 quán đối tác + 4 địa điểm tự nhiên, đều đã gắn mood (đủ 4 mood chính) |
| Chiến dịch | Tài trợ “Góc chạy deadline” 3 km (độc quyền); tài trợ “Cần xả stress” 3 km; 2 VIP hộp mù cùng hạng; 1 kiosk O2O. Tất cả có voucher |
| Kiosk | `M4L-DEMO-01` cạnh Hồ Gươm, đã cấp khóa |
| Ghim bí ẩn | 6 ghim: Hoàn Kiếm, Tây Hồ, Long Biên, Cầu Giấy, Hà Đông |

## 3. Đường dẫn

| Trang | Đường dẫn | Đăng nhập |
|---|---|---|
| Trang chủ | `/m4l` | `/cms/login?next=/m4l`, chọn “Người dùng” |
| Khám phá theo mood | `/m4l/discover?mood=chay-deadline` | Không bắt buộc |
| Thế giới (Fog of War) | `/m4l/world` | Người dùng |
| Ví voucher | `/m4l/vouchers` | Người dùng |
| Cổng đối tác | `/m4l/partner` | `/cms/login?next=/m4l/partner`, chọn “Tài khoản kiosk” |
| Nhân viên quét voucher | `/m4l/v/<mã>` (mở bằng camera điện thoại) | Đối tác của quán đó |
| Quản trị (chiến dịch, kiosk, analytics, mood, lưới, ghim) | `/m4l/admin` | `/hrm/login?next=/m4l/admin`, chọn “Quản trị viên” hoặc “Nhân viên quản lí” |
| Màn hình trạm | `/m4l/station` | Mã kiosk + khóa kiosk |
| Check-in tại trạm | `/m4l/k/<mã>` (từ QR của trạm) | Người dùng |

## 4. Kịch bản trình diễn (khoảng 10 phút)

1. **A. Mood**: người dùng mở “Góc chạy deadline”, bấm “Gần tôi”. Ô **Tài trợ** của Cà phê Trang Sách hiện ở đầu, các địa điểm tự nhiên bên dưới. Mở Chi tiết, rồi Chỉ đường.
2. **B. Hộp mù**: về Trang chủ, bấm “Khám phá ngẫu nhiên”. Một trong hai quán VIP hiện ra, có nhãn Tài trợ và lý do chọn. Bấm “Nhận voucher” để thấy QR và đồng hồ 60:00.
3. **D. Đổi voucher**: đăng nhập đối tác của quán đó trên máy khác, mở QR của khách (hoặc dán mã), bấm “Xác nhận đã dùng”. Quét lại sẽ bị từ chối. Ví của khách hiện “Đã sử dụng”.
4. **C. Bản đồ**: trên điện thoại thật (cần HTTPS) hoặc dùng chế độ demo trên `/m4l/world`. Đến Công viên Cầu Giấy và bật khám phá: ô sáng lên, hộp thoại hé lộ ghim.
5. **E. Đối tác**: Cà phê Trang Sách tạo chiến dịch VIP và gửi duyệt. `m4l_demo_manager` duyệt ở `/m4l/admin`; chiến dịch chuyển sang Đang chạy.
6. **F. Kiosk**: mở `/m4l/station` (nhập mã + khóa). Người dùng quét QR, thấy Tiệm Bánh Sáng Sớm cách khoảng 80 m, bấm Nhận voucher. Tiệm bánh xác nhận. Xem phễu ở `/m4l/admin`.

## 5. Giới hạn khi trình diễn

- Chưa thử trên máy thật: GPS, lắc máy và camera cần HTTPS và thiết bị thật.
- Xác nhận voucher dùng POS giả lập (mã `MOCK-…`).
- Số “đổi tại quầy” là lượt đối tác xác nhận voucher, **không** phải số khách thực tế vào quán.
- Ranh giới Hà Nội lấy từ OSM, chưa đối chiếu bản đồ chính thức.
