# M4L 2.0 — Quyết định còn mở

Mỗi mục: câu hỏi · mặc định đang dùng trong code (an toàn, cấu hình được) · ai cần xác nhận. Mặc định **không** phải quyết định kinh doanh đã chốt.

## Từ spec §12 (D1–D12)

| ID | Câu hỏi | Mặc định đang áp dụng | Trạng thái |
|---|---|---|---|
| D1 | Mobile web/PWA hay native? | Mobile-first web tại `/m4l`, vanilla JS như `web/user`. Không làm PWA riêng | Chờ sếp |
| D2 | Pilot Cầu Giấy hay toàn Hà Nội? | Phase 2 sẽ cấu hình khu vực pilot theo slug phường (đề xuất `cau-giay`). Phase 1 không phụ thuộc | Chờ sếp |
| D3 | Unlock cần đến thật hay bấm pin? | (Phase 2) xác minh GPS server-side; chế độ demo không ghi thành tích | Chờ sếp |
| D4 | VIP pool độc quyền kết quả random? | (Phase 2/4) cờ cấu hình, mặc định TẮT; có nhãn `Tài trợ` và fallback organic | Chờ sếp |
| D5 | Tự cấp voucher mọi gợi ý? | Không. User chủ động claim | Chờ sếp |
| D6 | Điều khoản thương mại / phí / hủy | Chưa làm billing. Không tạo charge thật | Chờ sếp |
| D7 | Mẫu số %, kích thước ô, tần suất GPS | (Phase 2) lưới cấu hình, đề xuất ~100 m, chỉ đếm ô eligible | Chờ sếp |
| D8 | Fair ranking organic/sponsored | Phase 1 **không có** sponsored. Phase 4: slot riêng có nhãn, không chen vào bộ lọc | Chờ văn bản policy |
| D9 | POS nào, định danh kiosk nào | Adapter + mock. Kiosk check-in cần khóa riêng cho từng thiết bị (hiện chỉ có `device code` công khai) | Chờ sếp/kỹ thuật |
| D10 | Chính sách dữ liệu vị trí, retention, người dưới tuổi | Không tracking nền; Phase 1 chỉ gửi tọa độ làm tròn 3 chữ số thập phân (~110 m) khi user bấm “Gần tôi”, không lưu | Chờ pháp chế |
| D11 | Ảnh hero, ảnh POI, logo | Dùng `web/assets/logo.png` có sẵn; hero là nền gradient, **không** dùng ảnh trong mockup (chưa rõ bản quyền) | Chờ sếp |
| D12 | Mốc phát hành, nhân sự, ngân sách | Ước lượng theo phase trong `IMPLEMENTATION_PLAN.md` | Chờ sếp |

## Phát sinh khi audit

| ID | Vấn đề | Mặc định đang áp dụng |
|---|---|---|
| A1 | **Khác biệt PDF ↔ spec về random**: PDF nói “random() lấy từ danh sách đối tác VIP” và “quán đối tác nổ ra độc quyền”; spec yêu cầu disclosure + organic fallback, không quảng cáo lừa “ngẫu nhiên thật” | Theo spec (an toàn pháp lý quảng cáo). Cần sếp chốt |
| A2 | **Khác biệt PDF ↔ spec về voucher**: PDF “mọi gợi ý đều kèm voucher”, “60 phút sinh tử”; spec: claim chủ động, TTL cấu hình | Theo spec; TTL là cấu hình theo template |
| A3 | **PDF “Highlands mua top 1 cho Tag”** — độc quyền tag theo bán kính | Phase 4: placement có nhãn, tách khỏi kết quả organic. Không đẩy POI sai mood |
| A4 | **Dữ liệu thiếu**: DB thật không có POI ẩm thực/cafe; 4 mood mẫu sẽ trống | Không bịa POI. Màn hình trống có giải thích. Cần đội nội dung nhập POI thật và gán mood qua `/m4l/admin` |
| A5 | Ai quản lý danh mục mood? | Tạo/sửa mood: **S0** (admin hệ thống). Gán mood cho POI: **S0** và **CONTENT** (Quản trị nội dung) trong phường được giao. Không tạo vai trò mới |
| A6 | Gán mood cần qua quy trình duyệt (draft → pending → approved)? | Phase 1: CONTENT/S0 đều là vai trò kiểm duyệt nên gán trực tiếp, ghi `audit`. Nếu cần 2 bước, bổ sung ở Phase 4 |
| A7 | Cá nhân hóa cho vai trò khác USER (OWNER, AREA…) mở `/m4l`? | Chỉ USER được chào tên; vai trò khác thấy giao diện như khách |
| A8 | Đăng nhập xong không quay lại `/m4l` (cms.js luôn chuyển USER sang `/dashboard/user`) | Không sửa `web/cms/cms.js` ở Phase 1. Token dùng chung nên mở lại `/m4l` là đã cá nhân hóa. Cần quyết định có thêm `?next=` không |
| A9 | Feature flag dạng nào? | Biến môi trường `XANH24_M4L_ENABLED` (mặc định tắt). Tắt → mọi route `/m4l*`, `/api/m4l/*` trả 404 và **không tạo bảng** |
| A10 | Mood mẫu có được seed vào DB thật? | Migration v1 thêm 4 mood mẫu nếu slug chưa tồn tại (dữ liệu cấu hình, sửa/tắt được). Không seed POI, không gán mood |
| A11 | Có nên đưa liên kết `/m4l` vào `/dashboard/user` hoặc bản đồ? | Chưa. Không sửa route cũ cho tới khi nghiệm thu |
| A12 | `tests/test_frontend_static.py` fail từ trước (so sánh HTML `/` với `/admin`) | Không sửa trong phạm vi M4L; báo người dùng |
| A13 | Bảng sót `user_discovery_preferences` trong DB thật | Giữ nguyên, không xóa |

## Phát sinh ở Phase 2

Mọi giá trị số dưới đây nằm trong `DEFAULT_CONFIG` (`server/m4l_service.py`) và ghi đè được bằng setting JSON `m4l_config`, không cần khởi động lại.

| ID | Vấn đề | Mặc định đang áp dụng |
|---|---|---|
| B1 | Khu vực pilot (D2) | Migration v2 tự tạo khu `cau-giay` từ ranh giới phường thật (402 ô × 100 m trên DB hiện tại). Tắt/đổi/thêm khu tại `/m4l/admin` |
| B2 | “Ô eligible” nghĩa là gì (D7) | Tâm ô nằm trong ranh giới phường. **Chưa** loại trừ hồ, khu quân sự, khuôn viên kín vì chưa có dữ liệu đường/không gian công cộng. Mẫu số vì thế lớn hơn diện tích thực đi được |
| B3 | Điều kiện mở khóa (D3) | ≥ 2 lần đo, mỗi lần sai số ≤ 50 m, các lần đo cách nhau ≤ 120 s và lệch nhau ≤ 75 m, tốc độ ≤ 40 m/s (so giữa các lần đo và với vị trí lần trước), ≥ 5 s giữa hai lần thử. Không chặn được tuyệt đối GPS giả trên web |
| B4 | Đồng hồ điện thoại có thể lệch | Server chỉ dùng **khoảng cách thời gian giữa các mẫu** do client gửi; thời điểm mở khóa và kiểm tra tốc độ so với lần trước dùng giờ server |
| B5 | Lưu gì về vị trí (D10) | Chỉ lưu ô đã mở + **một** vị trí gần nhất (làm tròn 4 chữ số ≈ 11 m) để chống dịch chuyển tức thời. Người dùng tự xóa được (`DELETE /api/m4l/exploration/me`). Chưa có chính sách thời hạn lưu |
| B6 | Đổi kích thước ô | Tăng `grid_version`; tiến độ hiển thị về 0 theo lưới mới, ô cũ vẫn giữ trong DB. Cần sếp quyết có quy đổi ô cũ sang lưới mới không |
| B7 | Random khi không chọn mood (A1/D4) | Chỉ rút từ POI **đã gắn ít nhất một mood đang bật** (`random_requires_mood_tag`). Lý do: rút từ mọi POI công khai sẽ gợi ý trụ sở UBND. Trên DB thật hiện chưa có POI nào gắn mood → random trả “chưa có địa điểm” cho tới khi đội nội dung gắn mood |
| B8 | Random cho khách | Không hỗ trợ: quota cần định danh. Khách được mời đăng nhập |
| B9 | Hạn mức random | 10 lượt / 24 giờ trượt, cách nhau ≥ 3 s, không lặp POI trong 24 giờ (hết POI mới thì cho lặp và nói rõ). Chưa có VIP pool (Phase 4) |
| B10 | Ghim bí ẩn do ai tạo | S0 mọi khu; CONTENT chỉ khi khu vực nằm trọn trong các phường được giao. Ghim chưa mở chỉ lộ lời gợi ý và tâm ô, không lộ tọa độ chính xác hay POI |
| B11 | Lắc máy | Bật thủ công (iOS bắt buộc xin quyền qua thao tác người dùng); nút bấm luôn dùng được |
| B12 | Bản đồ nền | Dùng style đang chọn trong cấu hình bản đồ (`settings.tiles`), phủ lớp sương tối; không có style tối riêng như mockup |

## Phát sinh khi mở rộng toàn Hà Nội (migration v3)

Chi tiết kỹ thuật: `HANOI_SCALEUP.md`; số liệu: `HANOI_GRID_REPORT.md`. B1 (pilot Cầu Giấy là khu mặc định) và B2 (mọi ô trong ranh giới đều eligible) **được thay thế** bởi các mục dưới.

| ID | Vấn đề | Mặc định đang áp dụng |
|---|---|---|
| C1 | Nguồn ranh giới chính thức | Dùng OpenStreetMap (thành phố: relation 1903516; 126 phường/xã admin_level=6 theo sắp xếp 01/07/2025). Là dữ liệu cộng đồng — **cần đối chiếu bản đồ chính thức (Sở Nội vụ/Sở TN&MT) trước khi công bố số liệu “% Hà Nội” ra ngoài** |
| C2 | Giấy phép ODbL | Ghi công “© OpenStreetMap contributors” trên `/m4l/world`. Nếu Xanh24 phát hành CSDL lưới ra bên ngoài, phần đó phải theo ODbL — cần pháp chế xác nhận |
| C3 | “Ô hợp lệ” cho mẫu số | Ô có đường/lối đi công cộng trong OSM. Ô chưa có dữ liệu đường → `pending_review`: mở khóa được khi đến thật nhưng **không** tính vào mẫu số; giao diện ghi “≈ … (tạm tính)” khi còn ô chờ xác minh |
| C4 | Khu hạn chế | Mặc định chỉ `landuse=military` của OSM. Khu khác (sân bay, khu công nghiệp kín, công trình an ninh) do S0 khai báo kèm nguồn căn cứ tại `/m4l/admin`. Cần danh sách chính thức |
| C5 | Mặt nước nhỏ | Ô có tâm nằm trong ao/hồ bị loại trừ dù bờ có đường. Có thể đổi quy tắc sang “tỷ lệ diện tích nước > 50 %” nếu cần chính xác hơn |
| C6 | CSDL | Giữ SQLite (đo được đủ nhanh cho pilot). Chuyển PostgreSQL/PostGIS chỉ khi có số liệu tải thực và được phê duyệt; trên Vercel/Postgres chạy migration v3 bằng CLI trước khi bật cờ |
| C7 | Tiến độ khi đổi phân loại | Không reset: ô đã mở được giữ; tỷ lệ tính lại theo tập ô hợp lệ hiện hành và phiên bản phân loại được trả kèm. Ô đã mở nay thành `excluded` thì không còn được tính |
| C8 | Mật độ ghim bí ẩn | Không tự sinh ghim. Quản trị tạo từng ghim; hệ thống chặn ghim trên mặt nước/khu hạn chế. Cần quy định mật độ (vd. ≤ N ghim/phường) |

## Phát sinh ở Phase 3–4 (thương mại) — cần sếp xác nhận

Lý do kỹ thuật cho từng mặc định: `DECISION_LOG.md`. Mọi mục dưới đây là `PENDING_APPROVAL`, đều cấu hình được và không phát sinh giao dịch thật.

| ID | Câu hỏi | Mặc định đang áp dụng |
|---|---|---|
| D-C1 | PDF: “**mọi** gợi ý đều kèm voucher”. Địa điểm không phải đối tác thì lấy voucher ở đâu? | Chỉ địa điểm có chiến dịch voucher mới kèm voucher. Các địa điểm khác không có voucher |
| D-C2 | Pool VIP rỗng thì hộp mù làm gì? | `random_vip_fallback="organic"`: gợi ý tự nhiên, ghi rõ “không tài trợ”. Phương án khác: `"none"` (báo trống, không trừ lượt) |
| D-C3 | Hai đối tác cùng muốn độc quyền một mood | Chiến dịch được duyệt trước giữ quyền; chiến dịch sau bị chặn lúc duyệt (`EXCLUSIVE_CONFLICT`). Không đấu giá |
| D-C4 | Giá gói, ngân sách, cách tính phí (theo lượt đổi voucher?) | Không có thanh toán. `priority`/`package`/`impression_cap`/`issue_cap` là dữ liệu hợp đồng do Xanh24 nhập; hạn mức được thực thi |
| D-C5 | Ai tự động nhận voucher? (D5) | Người dùng bấm “Nhận voucher”; đồng hồ chạy từ lúc nhận. Ưu đãi hiện cạnh mọi gợi ý của đối tác |
| D-C6 | Bán kính kiosk, cửa sổ nhận sau check-in | 200 m (theo ví dụ PDF), 30 phút; mã trạm hạn 180 s. Chỉ có QR, chưa có quét thẻ (D9) |
| D-C7 | Tài trợ mood có cần POI đã được kiểm duyệt gắn mood đó? | Có (`MOOD_MISMATCH`). PDF viết “trả tiền là được gắn tag” (A3) |
