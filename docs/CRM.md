# Xanh24 CRM — quản lý www.xanh24.com

CRM là module máy chủ (`server/modules/crm.py`, tự phục vụ trang `/crm/`) + giao diện tĩnh `web/crm/` + ứng dụng Android **Xanh24 CRM** (`android/crm-app`). Đăng nhập bằng tài khoản quản trị sẵn có (S0 / S1 / Co-worker).

## Chức năng
| Mục | Nội dung |
|---|---|
| Tổng quan | Màn hình trực tuyến/mất kết nối, lượt sử dụng & lượt hiển thị quảng cáo hôm nay và 30 ngày, doanh thu tháng, công nợ, phễu bán hàng, việc đến hạn, hợp đồng sắp hết hạn. Tự làm mới 60 giây (trình chiếu: 30 giây). |
| Màn hình kiosk | Trạng thái từng màn hình, số liệu hôm nay, hợp đồng gắn máy, tạo việc bảo trì. |
| Khách hàng | Nhà quảng cáo, đối tác địa điểm / voucher, chủ điểm đặt kiosk, khách khác; liên hệ, MST, phụ trách, thẻ, gắn địa điểm bản đồ; nhật ký. Xuất CSV. |
| Phễu bán hàng | Tiềm năng → Đã liên hệ → Đã báo giá → Đàm phán → Đã ký / Không thành; kéo thả để chuyển. |
| Hợp đồng | Quảng cáo, thuê mặt bằng, đối tác; giá trị, thời hạn, màn hình & quảng cáo áp dụng; ghi nhận thanh toán; cảnh báo sắp hết hạn/quá hạn. |
| Việc cần làm | Gọi điện, gặp, khảo sát, bảo trì… có hạn, người phụ trách, đánh dấu xong. |
| Báo cáo quảng cáo | Lượt hiển thị theo ngày, màn hình, quảng cáo — theo khách hàng hoặc hợp đồng; tải CSV gửi khách. |
| Duyệt nội dung | Duyệt/từ chối địa điểm và quảng cáo chờ duyệt (dùng API quản trị sẵn có). |

## Phân quyền
`crm.read` CW · `crm.edit` CW (khách hàng, nhật ký, việc) · `crm.finance` S1 (hợp đồng, thanh toán) · `crm.delete` S1.

## API (`/api/modules/crm/…`, Bearer token)
`meta`, `overview`, `devices`, `customers` (GET/POST), `customers/<id>` (GET/PUT/DELETE), `contracts` (GET/POST), `contracts/<id>` (PUT/DELETE),
`contracts/<id>/payments` (POST), `payments/<id>` (DELETE), `activities` (GET/POST), `activities/<id>` (PUT/DELETE), `activities/<id>/done` (POST),
`report?customer=|contract=|ad=&from=&to=&format=csv`, `pois?q=`, `refresh` (POST, gia hạn phiên).

Bảng dữ liệu: `mod_crm_customers`, `mod_crm_contracts`, `mod_crm_payments`, `mod_crm_activities` (tự tạo khi khởi động, chạy được SQLite và Postgres/Neon).

## Cài lên màn hình
- **Android (máy tính bảng, màn hình LCD, TV box):** cài `Xanh24-CRM-1.0.0.apk` (chép qua USB, hoặc đưa lên Google Drive và khai báo trong `DOWNLOAD_APPS` để tải qua trang `/download` có mã PIN — thư mục `/downloads/` bị chặn công khai). Mặc định mở `https://www.xanh24.com/crm/`. Cài đặt trong ứng dụng: đổi máy chủ, bật *chế độ trình chiếu* (màn hình treo tường, luôn sáng). Tệp CSV lưu vào *Tải xuống/Xanh24*.
- **Máy tính / màn hình Windows, macOS, ChromeOS:** mở Chrome/Edge → `https://www.xanh24.com/crm/` → biểu tượng *Cài đặt ứng dụng* trên thanh địa chỉ.
- **Màn hình treo tường:** đăng nhập → *Chế độ trình chiếu* (ẩn menu, toàn màn hình, tự làm mới 30 giây). Hoặc mở `/crm/?wall=1`.
- Ứng dụng CRM khác gói với ứng dụng kiosk (`com.xanh24.crm` ≠ `com.xanh24.mapsforlife.kiosk`) — cài song song không ảnh hưởng nhau.

## Kiểm thử
`python tests/test_crm.py` (29 kiểm thử).
