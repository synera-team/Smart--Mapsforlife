# M4L 2.0: Rà soát bảo mật và quyền riêng tư

Phạm vi: code M4L (Phase 1–4) và hai thay đổi nhỏ ở `web/cms/cms.js`, `server/db.py`. Đây là rà soát nội bộ bằng đọc code và test, **không** phải pentest độc lập.

| Hạng mục | Đánh giá | Chi tiết / rủi ro còn lại |
|---|---|---|
| Xác thực | Đạt | Dùng lại JWT CMS (HS256, hạn 12 giờ). Kiosk dùng khóa riêng, không dùng token người dùng |
| Lưu token | Rủi ro sẵn có | Token nằm trong `localStorage` (giống toàn hệ thống), nên một lỗi XSS sẽ lộ token. Mọi chuỗi động trong UI M4L đi qua `esc()` |
| CSRF | Không áp dụng | API dùng header `Authorization`, không dùng cookie phiên |
| XSS | Đạt (rà code) | Nội dung từ DB (tên quán, chiến dịch, voucher, ghi chú duyệt) đều escape. Khóa kiosk hiển thị qua `esc()`. Thuộc tính số lấy từ server |
| SQL injection | Đạt | Mọi giá trị dùng tham số `?`. Tên cột chỉ lấy từ dict cố định trong code |
| IDOR | Đạt (test) | Voucher theo `account_id`. Redeem/check chỉ cho OWNER đang quản lý POI của voucher (người khác nhận 404, không lộ tồn tại). Chiến dịch theo `partner_account_id`. Admin AREA lọc theo phường. Khóa kiosk theo phường |
| RBAC backend | Đạt (test) | Decorator `staff(...)` trên mọi route quản trị/đối tác; không dựa vào việc ẩn nút. Tài khoản `read_only` không ghi được |
| Race condition | Đạt (test đồng thời) | Cap voucher, per-user, redeem, mã check-in, quota random: đều nguyên tử (`BEGIN IMMEDIATE` / advisory lock + UPDATE có điều kiện) |
| Replay QR / double redeem | Đạt | Voucher đổi một lần; mã check-in dùng một lần; QR voucher hết hạn bị từ chối ở server |
| Đoán mã | Đạt | Voucher: 18 byte ngẫu nhiên (≈144 bit). Check-in: 24 byte, hạn 180 s. Khóa kiosk: 24 byte |
| Lưu bí mật | Đạt | Khóa kiosk và mã check-in chỉ lưu SHA-256; khóa kiosk chỉ hiện một lần |
| Rate limit | Một phần | Có: quota random, tần suất mở khóa GPS, 30 mã kiosk/phút. **Chưa có** giới hạn riêng cho `POST /api/m4l/events` và `/vouchers/claim` (claim đã bị chặn bởi hạn mức và per-user cap). Nên đặt rate limit ở reverse proxy |
| Gian lận số liệu | Rủi ro biết trước | Impression của khách được gộp theo hash IP theo ngày, nên đổi IP sẽ làm tăng số đếm. `nav_click` do client gửi. Không dùng hai chỉ số này để tính tiền khi chưa có chống gian lận |
| Giả mạo GPS | Giảm thiểu, không triệt để | Kiểm tra sai số, tính nhất quán, tốc độ, khoảng cách giữa các lần đo ở server. Không chống được tuyệt đối trên web |
| Mã voucher trong URL | Chấp nhận | `/m4l/v/<mã>` có thể nằm trong lịch sử trình duyệt của nhân viên. Mã chỉ dùng được bởi chủ quán đó và chỉ một lần |
| Khóa kiosk trên thiết bị | Chấp nhận, có thu hồi | Lưu trong `localStorage` của màn hình trạm. Mất máy thì thu hồi/cấp lại tại `/m4l/admin` |
| Open redirect | Đạt | `?next=` chỉ nhận `^/m4l(/[A-Za-z0-9_\-/]*)?$` |
| Dữ liệu vị trí | Tối thiểu hóa | Không lưu lộ trình. Chỉ lưu ô đã mở và 1 vị trí gần nhất (~11 m); người dùng tự xóa được. GPS chỉ chạy khi trang mở và người dùng bật. Thời hạn lưu: chờ pháp chế (D10) |
| Cảm biến chuyển động | Đạt | Chỉ bật khi người dùng bấm; iOS xin quyền qua thao tác người dùng |
| Analytics | Đạt | Báo cáo chỉ có số tổng hợp, không có tên hay tài khoản |
| Secrets trong Git | Đạt | Mật khẩu demo sinh ngẫu nhiên, ghi vào thư mục dữ liệu (`data/` và thư mục demo nằm ngoài Git). Không có mật khẩu trong code. Nên thêm `.venv/` vào `.gitignore` (thư mục này đang chưa được theo dõi) |
| Thanh toán | Không có | Không có luồng thu tiền nào |
| Giấy phép bản đồ | Đạt | Ghi công © OpenStreetMap contributors (ODbL) trên `/m4l/world`; phát hành dữ liệu lưới ra ngoài cần pháp chế xác nhận (C2) |
| Nhận diện quảng cáo | Đạt | Mọi kết quả tài trợ có nhãn “Tài trợ”/“Đối tác”; gợi ý tự nhiên khi rơi về fallback ghi “không tài trợ” |
