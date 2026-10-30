# M4L 2.0: Ma trận truy vết yêu cầu

Cập nhật 29/10/2026. Nguồn yêu cầu theo thứ tự ưu tiên:
- **P0**: PDF “Xanh24 Maps for Life (M4L) – Phân tích Yêu cầu & Tầm nhìn”, 3 trang.
- **P1**: hai mockup mobile (Home; Thế giới của [Tên]).
- **P2**: các quyết định người dùng đã xác nhận.
- **P3**: code và tài liệu nội bộ.

Trạng thái chỉ dùng: `PASS_VERIFIED` · `PARTIAL` · `MISSING` · `FAILED` · `BLOCKED` · `PENDING_APPROVAL`. Một mục chỉ là `PASS_VERIFIED` khi có đủ code, test tự động và (nếu có UI) kiểm tra trên trình duyệt. Mọi kiểm tra trình duyệt chạy trên Chromium headless, **chưa thử điện thoại thật**.

Ký hiệu bằng chứng:

| Ký hiệu | Bằng chứng |
|---|---|
| **T1** | `tests/test_m4l.py` (90 kiểm thử) |
| **T2** | `tests/test_m4l_phase2.py` (66) |
| **T3** | `tests/test_m4l_hanoi.py` (65) |
| **T4** | `tests/test_m4l_commerce.py` (108) |
| **E-A … E-F** | Hành trình end-to-end qua giao diện thật (`TEST_REPORT.md`, ảnh trong `screenshots/`) |
| **VP** | Ảnh chụp ở 5 kích thước 360/390/430/768/1280 |

## A. Yêu cầu trích từ PDF (22 mục)

| ID | PDF | Yêu cầu | Trạng thái trước đợt này | File / API / Bảng | Test · Bằng chứng | Gap còn lại | Trạng thái sau |
|---|---|---|---|---|---|---|---|
| R01 | tr.1 “Định vị” | Lifestyle Companion: giải “không biết đi đâu”, gamification ở trước, phân phối traffic cho đối tác ở sau | PARTIAL (thiếu toàn bộ lớp thương mại) | Toàn bộ `server/m4l*.py`, `web/m4l/*` | T1–T4, E-A…E-F | Chưa có đối tác thật; chưa thử máy thật | PARTIAL |
| R02 | tr.1 I.1 UI/UX | Bản đồ phủ sương, chỉ nơi đã đi qua mới sáng | PASS_VERIFIED | `web/m4l/world.js`; `GET /api/m4l/exploration`; `m4l_cells`, `m4l_user_unlocks` | T2, T3, E-C, `C-world.png` | Bố cục chưa toàn màn hình như mockup (xem M02) | PASS_VERIFIED |
| R03 | tr.1 I.1 Tính năng | Hiển thị % khám phá thành phố | PASS_VERIFIED | `m4l_exploration.progress()`; `/api/m4l/exploration/progress` | T3 (mẫu số 200.444 ô hợp lệ toàn Hà Nội), E-C (0% → <0,01%) | Ranh giới OSM chưa đối chiếu bản đồ chính thức trước khi công bố ra ngoài (C1) | PASS_VERIFIED |
| R04 | tr.1–2 I.1 Gamification | Ghim bí ẩn phát sáng trong sương, thôi thúc di chuyển tới mở khóa | PARTIAL (icon tĩnh, mở khóa chỉ báo toast, thiếu chỉ đường) | `world.js` (`pin-marker.glow`, `revealPins`); `/api/m4l/mystery-pins`; `m4l_mystery_pins` | T2 (không lộ nội dung/tọa độ chính xác trước khi mở), E-C (`C-pin-reveal.png`) | Mật độ ghim chưa có quy định (C8) | PASS_VERIFIED |
| R05 | tr.1 I.2 UI/UX | Lời chào “Xin chào [Tên]! Hôm nay bạn thế nào?” | PASS_VERIFIED | `m4l.js homeView`; `/api/m4l/home` | T1, E-A | Mockup vẫn giữ ô tìm kiếm nên giữ cả hai | PASS_VERIFIED |
| R06 | tr.1 I.2 Tính năng | Nút mood: Góc chạy deadline, Cần xả stress, Hẹn hò lãng mạn, Ẩm thực đêm khuya… | PASS_VERIFIED | `m4l_moods` (migration v1), `/m4l/admin` | T1, VP | — | PASS_VERIFIED |
| R07 | tr.1 I.2 Trải nghiệm | Chọn mood → app tự liệt kê địa điểm phù hợp | PASS_VERIFIED trên code; DB thật không có POI F&B | `/api/m4l/discovery`; `m4l_poi_moods` | T1, E-A (3 địa điểm tự nhiên + 1 ô tài trợ) | **Dữ liệu**: DB thật chưa có quán; demo dùng POI gắn nhãn [DEMO] | PASS_VERIFIED (code), dữ liệu thật: BLOCKED (đội nội dung) |
| R08 | tr.2 I.3 UI/UX | Nút “Đi đâu cũng được? – Lắc máy để khám phá” nổi bật | PASS_VERIFIED | `blindBox()` trong `m4l.js`, CTA trên `/m4l/world` | E-B, VP | — | PASS_VERIFIED |
| R09 | tr.2 I.3 Tính năng | Lắc máy → nổ ra DUY NHẤT 1 địa điểm | PASS_VERIFIED (1 kết quả); lắc chưa thử máy thật | `random_pick()`; `POST /api/m4l/discovery/random`; `devicemotion` | T2 (4 yêu cầu song song → 1 kết quả), T4, E-B | Cảm biến chuyển động chỉ kiểm được trên máy thật | PARTIAL |
| R10 | tr.2 I.4 Chiến thuật | **Mọi** gợi ý đều kèm 1 voucher | MISSING | `m4l_commerce.attach_offers()`; `offer` trên mọi item discovery/random/kiosk | T4, E-B | Chỉ địa điểm có chiến dịch voucher mới kèm voucher. “Mọi gợi ý” cần quyết định ai tài trợ voucher cho địa điểm không phải đối tác (D-C1) | PENDING_APPROVAL |
| R11 | tr.2 I.4 Tâm lý học | Đồng hồ đếm ngược 60 phút | MISSING | `m4l_voucher_templates.ttl_minutes` (mặc định từ `voucher_default_ttl_min`=60), `expires_at` do server đặt; UI `[data-expires]` | T4 (3600 s theo giờ server), E-B (59:59 → 59:58) | — | PASS_VERIFIED |
| R12 | tr.2 II.1 | Mood Sponsorship: đối tác mua độc quyền tag; ví dụ top 1 cho tag trong bán kính 3 km, hiện đầu tiên | MISSING | `m4l_campaigns(kind='mood_sponsor')`; `sponsor_for()`; ô `sponsored` trong `/api/m4l/discovery` | T4 (độc quyền trùng vùng → 409, ngoài bán kính không hiện, hết hạn/khóa/ẩn/hết hạn mức), E-A | Thu phí, giá gói: ngoài hệ thống (D-C4) | PASS_VERIFIED (cơ chế) |
| R13 | tr.2 II.2 | VIP Random Spin: quay ngẫu nhiên trong pool đối tác VIP trả phí cao nhất hôm đó | MISSING (random lấy từ mọi POI có mood) | `vip_pool()`; `m4l_campaigns(kind='vip_spin', priority)`; `m4l_discovery_events.sponsored/campaign_id` | T4 (chỉ hạng ưu tiên cao nhất vào pool; tạm dừng → hạng kế), E-B | “Trả phí cao nhất” = trường `priority` do Xanh24 nhập theo hợp đồng; fallback khi pool rỗng cần chốt (D-C2) | PASS_VERIFIED (cơ chế) |
| R14 | tr.2 II.2 Lợi ích | Quán đối tác nổ ra độc quyền, không đặt cạnh đối thủ | MISSING | Hộp mù chỉ hiển thị 1 địa điểm | E-B (`B-random.png`) | — | PASS_VERIFIED |
| R15 | tr.3 II.3 | Kiosk: khách check-in/quét thẻ tại trạm → voucher dẫn đường tới đối tác ~200 m | MISSING | `m4l_kiosk_keys`, `m4l_kiosk_sessions`; `/api/m4l/kiosk/ticket`, `/kiosk/checkin`; `/m4l/station`, `/m4l/k/<mã>`; `kiosk_radius_m`=200 | T4 (khóa sai, mã giả, dùng lại, hết hạn, kiosk tắt, ngoài bán kính), E-F | Chỉ có QR; **“quét thẻ”** (thẻ vật lý/NFC) chưa có vì chưa rõ phần cứng (D9) | PARTIAL |
| R16 | tr.3 II.3 Đo lường | Thu phí theo khách thực tế bước vào quán (đo bằng voucher) | MISSING | Phễu `m4l_events` + `m4l_vouchers.status='redeemed'`; `/api/m4l/admin/analytics` | T4, E-F | Hệ thống chỉ đo **lượt đổi voucher được đối tác xác nhận**, không phải foot traffic; thu phí chưa làm | PENDING_APPROVAL |
| R17 | tr.3 III | Mood Tags là filter DB; “đối tác trả tiền cho tag nào thì được gán tag đó” | PARTIAL | `m4l_poi_moods` + duyệt nội dung; `MOOD_MISMATCH` khi duyệt tài trợ | T4 (POI chưa được gắn mood → không mua được mood đó) | Lệch với PDF: trả tiền **không** tự gán tag; tag phải qua kiểm duyệt nội dung (A3) | PENDING_APPROVAL |
| R18 | tr.3 III | “Lắc máy” là random() từ danh sách đối tác VIP | MISSING | Như R13; `random_mode`="vip_pool" | T4 | Như R13 | PASS_VERIFIED |
| R19 | tr.3 III | Module countdown cho voucher gắn User ID; hết hạn tự thu hồi/disable QR | MISSING | `m4l_vouchers.account_id/expires_at`; `redeem()` kiểm tra hạn; ví ẩn mã khi hết hạn | T4 (QR hết hạn → 410, ví ẩn `code`), E-D | — | PASS_VERIFIED |
| R20 | tr.3 III | Fog: lưới hoặc geofencing để lưu trạng thái unlocked | PASS_VERIFIED | Lưới 100 m toàn Hà Nội (337.035 ô) | T2, T3 | — | PASS_VERIFIED |
| R21 | tr.3 III | Overlay có độ trong suốt theo trạng thái trên Mapbox/Google Maps | PASS_VERIFIED (MapLibre) | MapLibre trong `web/vendor` | E-C, VP | Dùng MapLibre (mã nguồn mở, cùng API kiểu Mapbox) thay Mapbox/Google, xem `DECISION_LOG.md` DL-08 | PASS_VERIFIED |
| R22 | tr.3 III | Đồng bộ O2O: API với POS/màn hình kiosk để phát voucher tại trạm | MISSING | Kiosk: có. POS: `MockPOS` trong `m4l_commerce.py` | T4 (mã POS `MOCK-…`), E-D, E-F | **Chưa có POS thật** (chưa có API/quyền) | PARTIAL |

**Tổng 22 yêu cầu PDF:**

| Trạng thái | Số mục | Các mục |
|---|---|---|
| PASS_VERIFIED | 15 | R02–R08, R11–R14, R18–R21 |
| PARTIAL | 4 | R01, R09, R15, R22 |
| PENDING_APPROVAL | 3 | R10, R16, R17 |
| MISSING / FAILED / BLOCKED | 0 | (R07 có phần dữ liệu thật đang BLOCKED) |

Trước đợt này, 11 trong 22 mục là MISSING.

## B. Yêu cầu từ mockup

| ID | Nguồn | Yêu cầu | Trạng thái sau | Ghi chú |
|---|---|---|---|---|
| M01 | Mockup 1 | Home: logo, tìm kiếm, avatar + tên, banner chào, hộp mù, “Thế giới của [Tên]” + tiến độ, 4 mood card, khối Pioneer Voucher | PARTIAL | Đủ các khối có chức năng thật (VP, E-A, E-B). Chưa có: ảnh nền banner (chưa rõ bản quyền ảnh, D11); bản đồ mini trong thẻ Thế giới là hình trang trí |
| M02 | Mockup 2 | Thế giới: tiêu đề, thẻ tiến độ có tìm kiếm/lớp, bản đồ sương có ghim ?/khóa, nút zoom/định vị/bản đồ, CTA “Di chuyển để mở khóa” + “Lắc máy” | PARTIAL | Đủ chức năng (E-C). Bố cục: thẻ tiến độ nằm **trên** bản đồ chứ chưa nổi trên bản đồ toàn màn hình; ô hạn chế tô màu chứ không vẽ icon khóa |

## C. Yêu cầu chất lượng từ master prompt

| ID | Yêu cầu | Trạng thái | Bằng chứng / gap |
|---|---|---|---|
| Q01 | GPS xác thực ở backend, ≥2 mẫu, accuracy, chống nhảy, chống đồng thời | PASS_VERIFIED | T2, T3 (Cầu Giấy, Hoàn Kiếm, Long Biên, Hà Đông, An Khánh; ngoài HN bị từ chối; 4 request đồng thời → 1 bản ghi). Không chống được tuyệt đối GPS giả |
| Q02 | Không tải toàn bộ 337.035 ô xuống frontend | PASS_VERIFIED | T3; tổng quan 3.613 khối ~89 KB; khung nhìn ≤ 8.000 ô |
| Q03 | pending_review mở được nhưng không tính %, có giải thích | PASS_VERIFIED | T3; UI “≈ … (tạm tính)” + dòng giải thích (`vp-768x1024-world.png`) |
| Q04 | Random: quota/cooldown/không lặp/không trừ lượt khi rỗng, cấu hình được | PASS_VERIFIED | T2, T4 (`random_daily_quota`, `random_cooldown_s`, `random_repeat_window_h`, `random_vip_fallback`) |
| Q05 | Voucher: QR duy nhất, cap, không redeem 2 lần, chỉ nhân viên có quyền, đồng thời | PASS_VERIFIED | T4 (6 người/cap 3 → 3; 4 lần quét đồng thời → 1 thành công), E-D |
| Q06 | Kiosk: xác thực thiết bị, mã chống giả, chống dùng lại, gắn User/Kiosk/Campaign/Voucher | PASS_VERIFIED | T4, E-F |
| Q07 | Phân biệt impression / QR scan / claim / nav click / redeem | PASS_VERIFIED | T4, E-F; báo cáo ghi rõ không phải foot traffic |
| Q08 | RBAC ở backend (USER, CONTENT, PARTNER, MANAGER, ADMIN) | PASS_VERIFIED | T1–T4. Ánh xạ vai trò sẵn có: PARTNER=OWNER, MANAGER=AREA, ADMIN=S0 (DL-01) |
| Q09 | CMS: mood, POI-mood, khu vực, lưới, ghim, đối tác, chiến dịch, VIP, voucher, kiosk, analytics, nhật ký | PARTIAL | `/m4l/admin` + `/m4l/partner`. Quản lý địa điểm/hình ảnh và tài khoản đối tác vẫn ở CMS hiện có (`/dashboard/*`), không làm trùng |
| Q10 | Audit log | PASS_VERIFIED | Bảng `audit`: duyệt chiến dịch, đổi voucher, cấp/thu hồi khóa kiosk, mood, ghim, vùng (T4) |
| Q11 | Responsive 360/390/430/768/1280, không tràn ngang, không lỗi JS | PASS_VERIFIED (headless) | VP: 35 ảnh, 0 tràn ngang, 0 lỗi JS. **Chưa thử máy thật** |
| Q12 | Kiểm thử trên điện thoại thật | BLOCKED | Không có thiết bị/HTTPS trong môi trường này |
| Q13 | Postgres | PARTIAL | Code có nhánh PG (advisory lock, `rowcount`, `RETURNING id`) nhưng **chưa chạy** trên Postgres |
| Q14 | Dữ liệu demo tách biệt, tái lập được | PASS_VERIFIED | `server/seed_m4l_demo.py` từ chối `data/xanh24.db` và Postgres; nhãn `[DEMO]`, `is_demo=1` |
| Q15 | Chính sách lưu dữ liệu vị trí, đồng ý dùng GPS/cảm biến | PENDING_APPROVAL | Đã tối thiểu hóa (1 vị trí gần nhất, làm tròn ~11 m; người dùng tự xóa được). Thời hạn lưu cần pháp chế (D10) |
| Q16 | Không phá route cũ | PASS_VERIFIED | T1–T4 + test cũ đều đạt. `test_frontend_static` đã hỏng từ trước, không liên quan (A12) |
