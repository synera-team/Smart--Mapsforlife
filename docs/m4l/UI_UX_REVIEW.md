# M4L 2.0: Đánh giá UI/UX so với mockup

Phương pháp: chụp màn hình bằng Chromium headless rồi đặt cạnh hai mockup lãnh đạo cung cấp. Ảnh nằm trong `screenshots/`. **Chưa xem trên điện thoại thật.**

## Mockup 1: Home

| Thành phần mockup | Hiện trạng | Đánh giá |
|---|---|---|
| Nền navy, nhấn cyan/xanh ngọc | Cùng bảng màu (`--bg #0b2233`, `--accent #3fe0c5`, `--accent-2 #2cc6ee`) | Khớp |
| Logo, ô “Bạn muốn đi đâu hôm nay?”, avatar + tên | Có; avatar là chữ cái đầu (chưa có ảnh đại diện trong hồ sơ) | Khớp, thiếu ảnh |
| Banner “Xin chào [Tên]! Hôm nay bạn thế nào?” | Có, tên lấy từ tài khoản | Khớp về nội dung; **không có ảnh nền** vì chưa có ảnh được cấp quyền dùng (D11) |
| Hộp mù “Đi đâu cũng được? / Lắc máy để khám phá” | Có nút lớn + bật lắc máy; microcopy viết lại cho đúng chính tả | Khớp |
| “Thế giới của [Tên]”, “Đã khám phá x% Hà Nội”, thanh tiến độ | Có, số liệu từ server, ghi “≈ … tạm tính” khi còn ô chờ xác minh | Khớp; bản đồ mini là hình trang trí |
| 4 mood card 2×2 | Có, icon vector thay emoji; hiện số địa điểm hoặc “Chưa có địa điểm” | Khớp |
| Banner “Pioneer Voucher: 60 phút đếm ngược!” | **Mới**: khối Pioneer Voucher gồm voucher đang chạy (đồng hồ) và danh sách ưu đãi; có trạng thái loading/rỗng/lỗi | Khớp về chức năng; trình bày là danh sách thẻ thay vì một dải banner |

## Mockup 2: Thế giới của [Tên]

| Thành phần mockup | Hiện trạng | Đánh giá |
|---|---|---|
| Tiêu đề “Thế giới của [Tên]” | Có | Khớp |
| Thẻ “Bản đồ của bạn” + % + nút tìm/lớp | Có thẻ tiến độ, ô tìm kiếm, nút lớp trên bản đồ | Khớp về chức năng |
| Bản đồ phủ sương, vùng sáng nơi đã đi | Có; khung nhìn nhỏ hiện ô 100 m, xem tổng quan hiện khối 1 km | Khớp |
| Ghim “?” phát sáng | **Mới**: hiệu ứng phát sáng nhịp nhàng (tắt khi bật reduced-motion); ghim đã mở là ★ “Đã khám phá” | Khớp |
| Icon khóa trên vùng khóa | Khu hạn chế tô đỏ trong chú giải, không có icon khóa | Khác nhẹ |
| Nút zoom, định vị, bản đồ | Có | Khớp |
| CTA “Di chuyển để mở khóa bản đồ!” + “Lắc máy để khám phá” | Có | Khớp |
| Bố cục bản đồ toàn màn hình, thẻ nổi trên bản đồ | Thẻ tiến độ nằm **trên** bản đồ, bản đồ trong khung bo góc | **Lệch**: P2, nên làm sau khi thử trên máy thật |

## Màn hình mới (không có trong mockup)

- **Voucher**: thẻ voucher có đồng hồ lớn, QR trên nền trắng để camera đọc được. Hết giờ thì QR tự gỡ và hiện “Đã hết hạn”.
- **Hộp thoại hé lộ ghim**: hiệu ứng ★ bung ra, tên nơi, mô tả, nút Chi tiết / Chỉ đường.
- **Cổng đối tác**: form xác nhận voucher ở đầu trang (dùng ở quầy), danh sách chiến dịch kèm phễu, form tạo chiến dịch.
- **Màn hình trạm**: QR lớn, chữ ngắn gọn, tự đổi mã.

## Trạng thái và trợ năng

- Mỗi khối có trạng thái loading (skeleton), rỗng (có hướng xử lý tiếp), lỗi (có nút Thử lại) và thành công (toast/hộp thoại).
- Vùng chạm ≥ 44 px, focus hiển thị, nhãn cho icon, `aria-live` cho kết quả.
- `prefers-reduced-motion` tắt hiệu ứng ghim, bung sao và hiệu ứng hộp mù.

## Responsive

35 ảnh ở 360, 390, 430, 768 và 1280 px: không tràn ngang, không lỗi JS. Trên điện thoại, bảng ở trang quản trị cuộn ngang trong khung của bảng (trang quản trị chủ yếu dùng trên máy tính).

## Việc nên làm tiếp (P2)

1. Thế giới: bản đồ toàn màn hình, thẻ tiến độ thu gọn nổi phía trên, CTA nổi phía dưới như mockup.
2. Ảnh banner và ảnh địa điểm có bản quyền.
3. Ảnh đại diện người dùng.
4. Icon khóa cho khu hạn chế ở mức zoom gần.
5. Thử trên iPhone/Android thật để chỉnh khoảng cách và hiệu năng hiệu ứng.
