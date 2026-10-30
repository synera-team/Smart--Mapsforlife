# M4L 2.0: Báo cáo triển khai (đợt hoàn thiện 29/10/2026)

## Tóm tắt

Trước đợt này, M4L chỉ có lớp B2C: mood, discovery, random, Fog of War toàn Hà Nội và ghim bí ẩn. Lớp B2B, phần tạo ra doanh thu theo PDF, chưa có gì. Đợt này bổ sung các phần sau, tái sử dụng tài khoản OWNER, POI và kiosk sẵn có:

- **Pioneer Voucher**: đếm ngược theo giờ server, QR dùng một lần.
- **Mood Sponsorship**: có nhãn, kiểm tra độc quyền.
- **VIP Random Spin**.
- **Kiosk O2O**: khóa thiết bị, mã check-in dùng một lần.
- **Phễu analytics**.
- **Cổng đối tác** và **màn hình trạm**.
- Cải thiện Mystery Pins và đăng nhập quay lại M4L.

Kết quả 22 yêu cầu PDF:

| Trạng thái | Số mục |
|---|---|
| PASS_VERIFIED | 15 |
| PARTIAL | 4 |
| PENDING_APPROVAL | 3 |
| MISSING | 0 (trước đợt này: 11) |

Chi tiết: `REQUIREMENT_TRACEABILITY.md`.

## Chức năng đã bổ sung

| Chức năng | Người dùng thấy gì | Trạng thái |
|---|---|---|
| Ưu đãi kèm gợi ý | Thẻ “%” kèm tên ưu đãi, số suất còn lại, thời gian đếm ngược sau khi nhận; xuất hiện ở discovery, hộp mù, Trang chủ, trang trạm | PASS_VERIFIED |
| Nhận voucher | Bấm “Nhận voucher” → QR + đồng hồ; bấm hai lần không phát thêm | PASS_VERIFIED |
| Ví voucher `/m4l/vouchers` | Còn hiệu lực / Đã sử dụng / Đã hết hạn; QR tự gỡ khi hết giờ | PASS_VERIFIED |
| Tài trợ mood | Một ô “Tài trợ” ở đầu danh sách mood, theo bán kính; danh sách tự nhiên không đổi | PASS_VERIFIED |
| VIP hộp mù | Hộp mù trả một quán VIP hạng cao nhất, có nhãn và lý do; rơi về gợi ý tự nhiên “không tài trợ” khi không có VIP | PASS_VERIFIED (chính sách fallback: PENDING_APPROVAL) |
| Cổng đối tác `/m4l/partner` | Tạo/sửa/gửi duyệt chiến dịch kèm voucher, xem phễu, xác nhận voucher tại quầy (`/m4l/v/<mã>`) | PASS_VERIFIED |
| Quản trị `/m4l/admin` | Duyệt/từ chối/tạm dừng/chạy lại/kết thúc chiến dịch; cấp/thu hồi khóa kiosk; phễu analytics. Nay mở cho Nhân viên quản lí (AREA) trong phường được giao | PASS_VERIFIED |
| Màn hình trạm `/m4l/station` | QR check-in, tự đổi sau mỗi lượt quét | PASS_VERIFIED |
| Check-in `/m4l/k/<mã>` | Ưu đãi của đối tác trong bán kính trạm, nhận voucher tại chỗ | PASS_VERIFIED (QR; chưa có quét thẻ) |
| Mystery Pins | Ghim phát sáng; hộp thoại hé lộ khi mở khóa; Chi tiết/Chỉ đường; trạng thái “Đã khám phá”; không lộ tọa độ thật trước khi mở | PASS_VERIFIED |
| Đăng nhập quay lại | `/cms/login?next=/m4l/...` và `/hrm/login?next=/m4l/admin` đưa người dùng về đúng trang | PASS_VERIFIED |
| Dữ liệu demo | `server/seed_m4l_demo.py`, gắn nhãn, tái lập được | PASS_VERIFIED |

## File đã thay đổi trong đợt này

Mới:
- `server/m4l_commerce.py`: chiến dịch, voucher, kiosk, analytics, `MockPOS`.
- `server/seed_m4l_demo.py`.
- `web/m4l/partner.html`, `web/m4l/partner.js`, `web/m4l/station.html`, `web/m4l/station.js`.
- `tests/test_m4l_commerce.py`.
- Tài liệu trong `docs/m4l/`:
  - `REQUIREMENT_TRACEABILITY.md`, `GAP_ANALYSIS.md`, `IMPLEMENTATION_REPORT.md`, `TEST_REPORT.md`, `UI_UX_REVIEW.md`;
  - `SECURITY_REVIEW.md`, `DATABASE_MIGRATION_REPORT.md`, `DATABASE_DESIGN.md`, `API_CONTRACT.md`;
  - `DECISION_LOG.md`, `DEMO_GUIDE.md`, `RELEASE_READINESS.md`;
  - thư mục `screenshots/` (20 ảnh + `e2e-report.json`).

Sửa:
- `server/m4l_migrations.py`: migration v4.
- `server/m4l.py`: route mới, trang mới, ô tài trợ trong discovery, voucher trên Home.
- `server/m4l_service.py`: cấu hình thương mại, pool VIP trong `random_pick`.
- `server/db.py`: `_Cur.rowcount` cho Postgres (thay đổi cộng thêm).
- `web/m4l/m4l.js`, `web/m4l/world.js`, `web/m4l/admin.js`, `web/m4l/index.html`, `web/m4l/admin.html`, `web/m4l/m4l.css`.
- `web/cms/cms.js`: `?next=` chỉ cho `/m4l`.
- `tests/test_m4l.py`, `tests/test_m4l_hanoi.py`: cập nhật kỳ vọng, xem `TEST_REPORT.md`.
- `docs/m4l/OPEN_DECISIONS.md`, `IMPLEMENTATION_PLAN.md`, `ARCHITECTURE.md`, `REQUIREMENTS_TRACEABILITY.md` (nay trỏ sang file mới).
- `README.md`, `docs/API.md`.
- `.gitignore`: thêm `tests/m4l-*/`.

Không đổi: route `/`, `/dashboard/*`, `/cms/login` (trừ hỗ trợ `?next=/m4l`), `/hrm/login`, `/admin`, kiosk cũ, `web/sw.js`, bảng cũ.

## Lệnh đã chạy

```sh
python tests/test_m4l.py; python tests/test_m4l_phase2.py; python tests/test_m4l_hanoi.py; python tests/test_m4l_commerce.py
python tests/test_api.py ... (toàn bộ tests/)            # hồi quy
python server/m4l_migrations.py status|migrate|downgrade --to 3 --yes|migrate   # trên bản sao dữ liệu thật
python server/seed_m4l_demo.py                           # trên DB demo riêng; chạy lần 2 không làm gì; từ chối data/xanh24.db
python e2e.py http://localhost:8125 <accounts> <out>     # Playwright, 6 hành trình + 35 ảnh responsive
```

## Còn lại

Xem `RELEASE_READINESS.md` (chặn production) và `OPEN_DECISIONS.md` (D-C1…D-C7).
