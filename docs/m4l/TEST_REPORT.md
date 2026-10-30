# M4L 2.0: Báo cáo kiểm thử (29/10/2026)

## 1. Kiểm thử tự động

Lệnh chạy cho mỗi file: `python tests/<file>.py`. Môi trường: Windows 11, Python 3.12 (`.venv`), SQLite.

| Bộ test | Kết quả | Nội dung chính |
|---|---|---|
| `test_m4l.py` | **90 đạt** | Cờ, migration, mood, discovery, quyền, không hardcode, route cũ |
| `test_m4l_phase2.py` | **66 đạt** | Random (quota, cooldown, không lặp, đồng thời), GPS, ghim, pilot Cầu Giấy |
| `test_m4l_hanoi.py` | **65 đạt** | Rollback/migrate v3 giữ tiến độ, 126 đơn vị, mở khóa Cầu Giấy/Hoàn Kiếm/Long Biên/Hà Đông/xã ngoại thành, ngoài HN, mặt nước, đồng thời, khung nhìn |
| `test_m4l_commerce.py` (mới) | **108 đạt** | Xem mục 2 |
| `test_api.py` | 43 đạt | Hồi quy hệ thống cũ |
| `test_cms.py`, `test_cms_applications.py`, `test_cms_portals.py`, `test_partner_registration.py`, `test_download.py`, `test_cell_images.py` | Đạt | Hồi quy hệ thống cũ |
| `test_frontend_static.py` | **1 lỗi** | Đã hỏng từ trước đợt này: so HTML `/` với `/admin`, trong khi `web/index.html` đã bị sửa từ trước (A12). Không liên quan M4L, chưa sửa |

Kỳ vọng cũ đã được cập nhật cho đúng thay đổi đã duyệt (không đổi để ép test xanh):
- `test_m4l.py`: `features.vouchers` nay là `true`, vì voucher đã triển khai.
- `test_m4l_hanoi.py`: bản sao lưu trước lần chạy lại v3 nay mang nhãn phiên bản cuối của lần chạy (v4), nên glob đổi thành `*pre-m4l-v*.db`.

## 2. `test_m4l_commerce.py`: 108 kiểm thử

| Nhóm | Kiểm tra |
|---|---|
| Schema | v4 áp dụng, đủ 6 bảng |
| RBAC | USER, khách, CONTENT, đối tác không vào được trang duyệt. AREA phường khác không duyệt/không cấp khóa/không xem số liệu. Đối tác khác không sửa chiến dịch, không xác nhận voucher của quán khác. Người dùng không tự xác nhận voucher |
| Vòng đời chiến dịch | Validate (mood bắt buộc, thời gian, hạn mức voucher); không gắn được POI của người khác. Nháp → chờ duyệt → duyệt. Không sửa được khi đang chờ duyệt. Từ chối phải có lý do. Sửa chiến dịch bị từ chối → về nháp. Có ghi audit |
| Mood sponsorship | Ô riêng có nhãn; danh sách tự nhiên không đổi. Ngoài bán kính / không có vị trí / tìm theo từ khóa: không hiện. Độc quyền trùng vùng → `EXCLUSIVE_CONFLICT`. POI chưa gắn mood → `MOOD_MISMATCH` |
| Bộ chặn | Hết hạn, đối tác bị khóa, POI bị ẩn, hết hạn mức hiển thị: đều không hiện. Tải lại trang không thổi phồng impression |
| VIP random | Chỉ hạng ưu tiên cao nhất được chọn, có nhãn. Lịch sử ghi chiến dịch. Tạm dừng → hạng kế tiếp. Hết VIP: `organic` ghi “không tài trợ”, `none` báo trống và không trừ lượt |
| Voucher | Cần đăng nhập. Đồng hồ 3600 s theo giờ server. Mã ≥ 20 ký tự. Idempotency. Mỗi người tối đa 1. **6 người nhận đồng thời, hạn mức 3 → đúng 3**. Hết suất → `SOLD_OUT` |
| Redeem | Kiểm tra trước khi đổi. **4 lần quét đồng thời → 1 thành công**. Không đổi hai lần. Hết hạn → 410. Ví ẩn mã khi hết hạn. Ghi người xác nhận + mã POS mock. Có audit |
| Kiosk | Cấp khóa (chỉ lưu hash); sai/thiếu khóa → 401. Mã ngắn hạn, gửi lại mã chưa dùng. Mã giả → 404, mã đã dùng → 409, quá hạn → 410. Kiosk tạm ngưng → 403. Thu hồi khóa → 401. Chỉ gợi ý đối tác trong bán kính. Voucher kiosk cần phiên của chính người đó. Voucher ghi phiên trạm |
| Analytics | Phễu hiển thị → nhận → chỉ đường → đổi, không đếm trùng. Client không tự ghi được “đổi”. Chỉ đếm lượt quét QR hợp lệ. Không lộ danh tính |
| Trang và cờ | `/m4l/vouchers`, `/m4l/partner`, `/m4l/station`, `/m4l/v/<mã>` mở được. Tắt cờ → API 404. Route cũ vẫn chạy |

## 3. Hành trình end-to-end qua giao diện thật

Chạy bằng Playwright, Chromium headless, trên server demo với DB demo mới tạo lại. Script: scratchpad `e2e.py`. Ảnh nằm trong `docs/m4l/screenshots/`. Mọi bước đều thao tác trên giao diện (form đăng nhập, nút bấm), không gọi API thay cho người dùng; API chỉ dùng để **đọc** mã voucher, phục vụ việc mô phỏng camera quét QR.

| Journey | Các bước đã chứng minh | Ảnh |
|---|---|---|
| **A**: Theo cảm xúc | Đăng nhập qua form, quay lại `/m4l` nhờ `?next=` → chọn “Góc chạy deadline” → “Gần tôi” → ô tài trợ có nhãn + 3 địa điểm → Chi tiết → Chỉ đường (`/?mode=web&poi=…&dir=foot`) | `A-discover-mood.png`, `A-detail.png` |
| **B**: Hộp mù | Bấm “Khám phá ngẫu nhiên” → đúng 1 địa điểm VIP, kèm lý do và lượt còn lại → Nhận voucher → QR + đồng hồ chạy (59:59 → 59:58) → Home hiện khối voucher đang chạy | `B-random.png`, `B-voucher.png`, `vp-390x844-home.png` |
| **C**: Khám phá bản đồ | GPS giả lập tại Công viên Cầu Giấy → bật khám phá → mở khóa ô → hộp thoại hé lộ ghim “Công viên Cầu Giấy” → tiến độ 0% → <0,01% | `C-pin-reveal.png`, `C-world.png` |
| **D**: Voucher | Đối tác đăng nhập qua `/m4l/v/<mã>` → Kiểm tra “Còn hiệu lực” → Xác nhận đã dùng → quét lần 2 bị từ chối “đã được sử dụng” → ví người dùng hiện “Đã sử dụng” | `D-redeem.png`, `D-wallet.png` |
| **E**: Đối tác | Đối tác tạo chiến dịch VIP qua form → Gửi duyệt → nhân viên quản lí khu vực duyệt trên `/m4l/admin` → Đang chạy → cổng đối tác thấy trạng thái + phễu | `E-admin.png`, `E-partner` (viewport 1280) |
| **F**: Kiosk O2O | Màn hình trạm nhập mã + khóa → QR → người dùng mở mã → 1 ưu đãi cách trạm 80 m → Nhận voucher (nguồn kiosk) → trạm tự đổi mã → tiệm bánh xác nhận (POS mock) → analytics: hiển thị 4, quét QR 1, nhận 2, đổi 2 | `F-station.png`, `F-kiosk-offers.png`, `F-analytics.png` |

Lỗi console duy nhất là lỗi 409 khi cố ý quét lại voucher đã dùng.

Hai lỗi thật do E2E phát hiện và đã sửa:
1. Sau khi submit form đăng nhập, `cms.js` bỏ qua `?next=`.
2. Cổng đối tác vẽ lại trang làm mất kết quả xác nhận voucher.

## 4. Responsive

Chụp 7 trang (home, discover, world, vouchers, partner, admin, home của khách) ở 360×800, 390×844, 430×932, 768×1024, 1280×800, tổng 35 ảnh. **0 trang tràn ngang, 0 lỗi JS** (`screenshots/e2e-report.json`).

## 5. Chưa kiểm được

| Chưa kiểm | Lý do / ghi chú |
|---|---|
| Điện thoại thật | GPS thật, cảm biến lắc, camera quét QR, iOS Safari |
| Postgres | Chưa có môi trường |
| POS thật | Chưa có API/quyền |
| Tải lớn / nhiều tiến trình ghi đồng thời | Chưa đo |
| Kiểm tra trợ năng bằng công cụ tự động (axe) | Mới kiểm thủ công: nhãn, focus, `prefers-reduced-motion` |
