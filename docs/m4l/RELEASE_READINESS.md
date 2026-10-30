# M4L 2.0: Mức sẵn sàng phát hành

**Kết luận: sẵn sàng cho demo nội bộ và pilot có kiểm soát. CHƯA sẵn sàng cho production thương mại.**

## Đã có bằng chứng

- 22 yêu cầu trong PDF: **15 PASS_VERIFIED**, 4 PARTIAL, 3 PENDING_APPROVAL, 0 MISSING/FAILED (`REQUIREMENT_TRACEABILITY.md`).
- 329 kiểm thử M4L đạt (90 + 66 + 65 + 108); test hồi quy của hệ thống cũ đạt. Riêng `test_frontend_static` đã hỏng từ trước.
- 6 hành trình A–F chạy hết qua giao diện thật (headless).
- 5 kích thước màn hình: không tràn ngang, không lỗi JS.
- Migration v4: có sao lưu, rollback và chạy lại trên bản sao dữ liệu thật; số dòng bảng cũ không đổi.
- Mọi thứ nằm sau cờ `XANH24_M4L_ENABLED` (mặc định tắt). Tắt cờ thì toàn bộ API M4L trả 404 và route cũ chạy như cũ.

## Chặn production

| # | Việc | Người quyết / làm |
|---|---|---|
| 1 | Thử trên điện thoại thật qua HTTPS (GPS, lắc, camera, iOS/Android) | QA |
| 2 | Chạy và kiểm thử trên Postgres nếu triển khai Vercel | Kỹ thuật |
| 3 | Phê duyệt chạy migration trên DB thật (sao lưu trước) | Sếp + vận hành |
| 4 | Chốt các quyết định thương mại D-C1…D-C6 (`OPEN_DECISIONS.md`) và D5, D6, D8 | Sếp |
| 5 | Dữ liệu thật: POI F&B + gắn mood; ghim bí ẩn; đối tác ký hợp đồng | Đội nội dung / kinh doanh |
| 6 | Chính sách dữ liệu vị trí và thời hạn lưu; điều khoản voucher | Pháp chế |
| 7 | Đối chiếu ranh giới OSM với bản đồ chính thức trước khi công bố “% Hà Nội”; xác nhận ODbL | Pháp chế / GIS |
| 8 | Rate limit ở reverse proxy cho `/api/m4l/events` và `/vouchers/claim` | DevOps |
| 9 | POS thật (nếu cần tự động xác nhận) | Đối tác + kỹ thuật |

## Không làm trong đợt này (theo nguyên tắc an toàn)

- Không deploy production.
- Không chạy migration trên `data/xanh24.db`.
- Không thu tiền.
- Không kích hoạt chiến dịch tính phí thật.
- Không tạo tài khoản admin trong code.
- Không commit Git.
