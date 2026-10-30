# Xanh24 - Maps for Life

Bản đồ số hành chính & dịch vụ công cho màn hình LCD Android tương tác đặt tại nơi công cộng, kèm giao diện mobile/web và cổng quản trị dữ liệu địa phương.

> Bản quyền thuộc về Công ty TNHH Công nghệ và Truyền thông Xanh24

## Tính năng

**Bản đồ công khai (`/`)**
- Ranh giới **51 phường/xã Hà Nội mới (từ 01/07/2025)** số hoá từ bản đồ phương án của Sở Nội vụ, chuyển VN-2000 → WGS84 (xem `docs/RANH_GIOI.md`).
- Tìm kiếm không cần gõ dấu, khám phá theo danh mục, địa điểm nổi bật, địa điểm gần đây.
- **Chỉ đường** tới mọi điểm trên bản đồ: đi bộ, xe đạp, xe máy/ô tô — lộ trình vẽ trên bản đồ nền, hướng dẫn từng bước tiếng Việt/Anh, mã QR để mang lộ trình theo điện thoại.
- **Chọn điểm bất kỳ trên bản đồ**: chạm vào vị trí bất kỳ (hoặc tên cửa hàng, trường học… trên bản đồ nền) → ghim điểm, hiện địa chỉ, phường, toạ độ, địa điểm và bến xe gần đó; chỉ đường (đi bộ, xe đạp, xe máy, buýt/metro), gọi Grab/Xanh SM, QR mang theo.
- Chọn phường: vùng phường được làm nổi bật (viền xanh đậm, phần ngoài phường làm tối).
- **Xe buýt & Metro**: tự tìm tuyến buýt (dữ liệu OpenStreetMap qua Overpass) và Metro đi thẳng từ điểm xuất phát tới đích, vẽ lộ trình đi bộ → lên xe → xuống xe → đi bộ trên bản đồ, nhiều phương án để chọn; danh sách bến buýt/ga metro gần nhất kèm nút “Dẫn tới bến”; QR tra cứu xe buýt thời gian thực.
- **Gọi Grab / Xanh SM** tới địa điểm đã chọn: QR Grab là link OneLink (https) → camera điện thoại mở thẳng ứng dụng Grab đã cài, điểm đến điền sẵn (chưa cài → trang tải ứng dụng). Xanh SM chưa công bố deep link điền điểm đến → QR mở trang trung gian: Android mở thẳng ứng dụng (`com.gsm.customer`), iOS qua App Store, địa chỉ được sao chép sẵn để dán, kèm hotline.
- **VR360**: ảnh 360°, video 360°, tour nhiều cảnh có điểm nóng (trình xem WebGL nội bộ) hoặc nhúng Kuula/Matterport/3DVista/Street View.
- **Chế độ kiosk**: sau **40 giây** không thao tác (cấu hình được) tự xoá thao tác, về màn hình chờ phát quảng cáo, nút lớn “Chạm để mở Bản đồ”; cảnh báo đếm ngược; bàn phím ảo tiếng Việt; khoá menu chuột phải; menu thiết bị bảo vệ bằng PIN (giữ logo 3 giây).
- Giao diện ngang/dọc/mobile, song ngữ Việt–Anh, QR chia sẻ địa điểm.

**Dashboard quản trị (`/admin`)**
- Phân quyền 3 tầng: **Admin S0** (toàn quyền) · **Admin S1** (phê duyệt, chỉnh sửa, publish) · **Co-worker** (nhập liệu, xin phê duyệt; có thể giới hạn theo phường).
- **Nhập Excel theo biểu mẫu** có ảnh: ảnh chèn trong ô (Excel 365 “Place in Cell”, WPS `DISPIMG`), ảnh đặt trong dòng, tên tệp trong gói .zip, hoặc link. Kiểm tra lỗi từng dòng, tự nhận phường theo toạ độ, phát hiện trùng.
- Quy trình phê duyệt: so sánh thay đổi (cũ ↔ mới) có bản đồ, duyệt/từ chối kèm lý do, duyệt hàng loạt; bản công khai giữ nguyên cho tới khi được duyệt.
- Soạn địa điểm với bản đồ chọn vị trí, thư viện ảnh, **cổng kết nối VR360**.
- Quản lý màn hình kiosk (trực tuyến/ngoại tuyến, vị trí “Bạn đang ở đây”, thời gian chờ riêng, QR cài đặt), quảng cáo chờ (lịch phát, ưu tiên, theo thiết bị), ranh giới phường (đối chiếu bản đồ gốc, thay GeoJSON chính thức), xe buýt & metro, thống kê sử dụng, nhật ký thao tác.
- **Cổng mở rộng**: module iframe có giao tiếp `postMessage`, module Python phía máy chủ, API key, webhook (xem `docs/MODULES.md`).

**Trang tải ứng dụng (`/download`)**
- Yêu cầu mã PIN trước khi hiển thị danh sách APK; tải tệp qua backend và không đưa URL Google Drive vào trình duyệt.
- Mã QR mở trang tải và đánh dấu ứng dụng tương ứng; người nhận vẫn cần nhập mã PIN.
- Danh sách thử nghiệm hiện có APK `LCD_kiosk_Dong_Do ver_2.0.0.apk` từ Google Drive dùng chung. Tệp được proxy qua backend, bao gồm bước xác nhận cảnh báo tải của Google; các APK trong `web/downloads/` không được đưa vào danh sách này.
- Để đưa thêm ứng dụng lên danh sách, khai báo metadata và Drive file ID trong `DOWNLOAD_APPS` ở `server/app.py`. Chỉ file ID ở backend được dùng để tải, không gửi link Drive cho trình duyệt.

## Chạy thử

Yêu cầu Python 3.10+ và Node.js 22+ để build frontend React/JavaScript.

```bash
./run.sh
# Bản đồ:    http://localhost:8024
# Kiosk:     http://localhost:8024/?device=HK-01
# CMS người dùng: http://localhost:8024/cms/login
# CMS nhân sự:    http://localhost:8024/hrm/login
# Quản trị cũ:   http://localhost:8024/admin (tài khoản: admin — mật khẩu trong data/INITIAL_ADMIN.txt)
```

Đặt trước mật khẩu S0: `XANH24_ADMIN_PASSWORD='MatKhau@2026' ./run.sh`

## Triển khai chính thức

### Docker
```bash
# sửa XANH24_ADMIN_PASSWORD và XANH24_SECRET trong docker-compose.yml
docker compose up -d --build
```
Dữ liệu (SQLite, ảnh tải lên) nằm trong `./data` — sao lưu thư mục này định kỳ.

### Máy chủ Linux (không Docker)
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
export XANH24_SECRET="$(openssl rand -hex 32)" XANH24_DATA_DIR=/var/lib/xanh24
python server/manage.py init
cd server && gunicorn -w 4 --threads 4 -b 127.0.0.1:8024 wsgi:app
```
Đặt Nginx phía trước với HTTPS (bắt buộc để điện thoại quét QR mở ổn định và dùng định vị):
```nginx
server {
  server_name maps.example.vn;
  client_max_body_size 200m;
  location / { proxy_pass http://127.0.0.1:8024; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $remote_addr; }
}
```
Sau khi có tên miền: *Dashboard → Cấu hình → Địa chỉ công khai* = `https://maps.example.vn` (dùng cho mọi mã QR).

### Biến môi trường
| Biến | Ý nghĩa |
|---|---|
| `XANH24_SECRET` | Khoá ký phiên đăng nhập (bắt buộc đặt khi chạy nhiều worker) |
| `XANH24_ADMIN_PASSWORD` | Mật khẩu tài khoản `admin` (S0) ở lần khởi tạo đầu |
| `XANH24_DOWNLOAD_PIN` | Mã PIN bắt buộc để mở `/download` (không đặt mặc định) |
| `XANH24_SESSION_COOKIE_SECURE` | Đặt `true` nếu chạy HTTPS ngoài Vercel; Vercel tự bật cookie Secure |
| `XANH24_DATA_DIR` | Thư mục dữ liệu (mặc định `./data`) |
| `XANH24_MAX_UPLOAD_MB` | Dung lượng tải lên tối đa (mặc định 200) |
| `PORT` | Cổng (mặc định 8024) |

Dòng lệnh: `python server/manage.py create-user <user> <S0|S1|CW> <mật khẩu>` · `reset-password <user> <mật khẩu>`.

## CMS quản lý ghim (demo)

Để tạo năm tài khoản thử nghiệm riêng (quản trị, quản lí khu vực, nhân viên nội dung, kiểm duyệt đăng kí, người mua ghim), chạy `python server/seed_cms_demo.py`. Tên đăng nhập và mật khẩu ngẫu nhiên được ghi vào `data/CMS_DEMO_ACCOUNTS.txt` (thư mục `data/` không được commit). Dùng trang đăng nhập phù hợp bên dưới và chọn đúng mục ghi trong file. Lệnh này không đổi mật khẩu tài khoản `admin` hiện có.

Sau khi khởi động Flask, người dùng và tài khoản kiosk đăng nhập tại `/cms/login`; quản trị viên, nhân viên quản lí và kiểm duyệt đăng kí đăng nhập tại `/hrm/login`. Tài khoản `USER` tự đăng ký tại `/cms/login`, chưa có ghim và mở `/dashboard/user`. Tài khoản kiosk mở `/dashboard/kiosk`; các vai trò nhân sự mở `/dashboard/admin`. Đường dẫn `/cms` chuyển sang `/cms/login`. Giao diện CMS dùng lại kiểu bảng, thẻ, biểu mẫu và hộp thoại của trang `/admin`; mã giao diện nằm trong `web/cms`, độc lập với `frontend`. Trang bản đồ Flask có nút “Đăng nhập/ Đăng ký” ở bên phải topbar.

- **Quản trị viên:** chọn “Quản trị viên”, đăng nhập bằng tài khoản Admin S0 hiện có. Admin cấp tài khoản Nhân viên quản lí, Quản trị nội dung và Kiểm duyệt đăng kí, phân khu vực, xem kiosk, quản lý gói và đơn toàn hệ thống.
- **Nhân viên quản lí:** Admin cấp tài khoản và khu vực. Người này nhận hồ sơ đăng ký đối tác tại mục “Hồ sơ đối tác”, xem giấy tờ, duyệt hoặc từ chối trong khu vực được giao; khi duyệt, xác định tọa độ ghim và cấp tài khoản kiosk. Người này cũng quản lý trạng thái ghim, kiosk, đơn và thanh toán trong khu vực.
- **Quản trị nội dung:** Admin cấp tài khoản và khu vực. Người này duyệt hoặc từ chối nội dung ghim trong khu vực được giao.
- **Kiểm duyệt đăng kí:** Admin cấp tài khoản riêng và phân phường theo lựa chọn trong Google Form. Người này chỉ thấy hồ sơ đăng kí thuộc phường được giao; sau khi đối chiếu giấy phép, họ duyệt để cấp tài khoản kiosk và gửi email kết quả, hoặc từ chối kèm lý do. Phạm vi của quản lí khu vực và nhân viên nội dung giữ nguyên.
- **Tài khoản kiosk:** là tài khoản **người mua ghim**. Người mua chỉnh nội dung, gửi duyệt, đăng ký gói và dùng nút thanh toán demo. Không có giao dịch tiền thật.
- **Người dùng:** tự tạo tài khoản cá nhân với họ tên, ngày sinh, giới tính (Nam/Nữ/Không tiết lộ), email và số điện thoại. `/dashboard/user` là trang khám phá riêng: có hàng địa điểm du lịch nổi bật, hàng di tích lịch sử, tìm kiếm và lọc theo danh mục/khu vực, xem địa điểm gần mình khi cho phép vị trí và lưu địa điểm. Mục Cá nhân chứa hồ sơ. Danh sách đã lưu được lưu theo tài khoản trong SQLite hoặc PostgreSQL. Trang này dùng dữ liệu địa điểm công khai và chỉ hiển thị ghim còn đủ điều kiện hiển thị. Giao diện nằm tại `web/user`, không thuộc dashboard nhân sự/kiosk và không thay đổi `frontend`. Tài khoản USER chưa được gắn ghim và không có quyền thao tác ghim, nội dung hoặc đơn hàng kiosk.

### Đăng ký đối tác trực tiếp

Tại `/cms/login`, chọn **Tài khoản kiosk → Đăng ký làm đối tác** (hoặc mở `/cms/login?partner=1`). Biểu mẫu nhận họ tên người đại diện, email, số điện thoại, vai trò, tên thương hiệu, danh mục, phường/khu vực, địa chỉ đầy đủ, ngày mở cửa (dropdown Thứ 2–Chủ nhật), giờ mở/đóng cửa, cùng tối đa 8 giấy tờ PDF/Word/ảnh (mỗi tệp tối đa 10 MB). Ô vị trí ghim hiển thị nhưng bị vô hiệu hóa; quản lý khu vực xác định tọa độ khi duyệt. Chỉ những phường đã có tài khoản quản lý khu vực đang hoạt động mới xuất hiện trong danh sách chọn. Giấy tờ được lưu riêng, tải qua API có kiểm tra quyền; tài khoản quản lý chỉ thấy hồ sơ thuộc khu vực được giao. Trong chi tiết hồ sơ, quản lý có thể từ chối và gửi mail hoặc mở bước tạo tài khoản để nhập tên đăng nhập, mật khẩu rồi xác nhận duyệt và gửi thông tin đăng nhập. CMS dùng cấu hình Gmail bên dưới để gửi kết quả. Đặt `CMS_MAIL_MODE=outbox` nếu muốn thử luồng duyệt cục bộ mà chưa gửi Gmail thật.

### Kết nối Google Form cũ và Gmail

Tích hợp Google Form cũ vẫn dùng được để xử lý các hồ sơ đã gửi trước đây; biểu mẫu đối tác mới không cần Apps Script. Form cũ có các trường Email, Tên chủ kinh doanh, Tên công ti/quán/doanh nghiệp, **Phường**, **Nhập địa chỉ Chi tiết**, Mã số thuế và Hồ sơ kinh doanh. Mã Apps Script đọc đúng tên hai câu hỏi Phường và Nhập địa chỉ Chi tiết, rồi chuyển hồ sơ tới nhân viên kiểm duyệt được phân phường. Nếu câu trả lời cũ chưa có Phường hoặc giá trị không khớp lựa chọn đã hỗ trợ, chỉ Admin thấy hồ sơ và có thể phân phường thủ công. Tọa độ ghim được nhân viên nhập khi duyệt và phải nằm trong ranh giới phường đăng kí. Riêng **Văn Miếu - Quốc Tử Giám** có trong Form nhưng chưa có ranh giới trong dữ liệu bản đồ của dự án: hồ sơ vẫn được nhận và phân cho nhân viên, nhưng chưa thể duyệt tạo ghim tại phường này cho đến khi bổ sung ranh giới. Các tệp giấy phép vẫn nằm trên Google Drive của Form; cấp quyền xem cho nhân viên kiểm duyệt tương ứng.

1. Với Flask chạy cục bộ, mở **Apps Script** từ trình chỉnh sửa Google Form; dán mã từ `integrations/google_form_to_cms.gs`. Trong **Script properties**, đặt `CMS_PULL_SECRET` thành chuỗi ngẫu nhiên dài. Triển khai Apps Script dạng **Web app**, chọn **Execute as me** và quyền truy cập **Anyone**. Ghi lại URL `/exec`. Web app kiểm tra khóa trong mỗi yêu cầu; giữ kín khóa.
2. Đặt `CMS_FORMS_PULL_URL` bằng URL `/exec` ấy và `CMS_FORMS_PULL_SECRET` bằng cùng khóa trong môi trường tiến trình Flask. Khởi động lại Flask. Admin mở mục “Đăng kí ghim” và bấm **Đồng bộ Google Form** để lấy cả hồ sơ cũ lẫn mới. API chống nhận trùng theo mã phản hồi Form. Flask không cần URL công khai cho cách này.
3. Cấu hình gửi Gmail trong môi trường Flask: `CMS_SMTP_HOST=smtp.gmail.com`, `CMS_SMTP_PORT=587`, `CMS_SMTP_USER=anvan16022005@gmail.com`, `CMS_SMTP_PASSWORD` ([App Password của Gmail](https://support.google.com/mail/answer/185833?hl=en)), `CMS_SMTP_FROM=anvan16022005@gmail.com`, và `CMS_PUBLIC_URL` (URL `/cms/login` mà người mua truy cập được). Không commit mật khẩu vào dự án. Có thể đặt `CMS_MAIL_MODE=outbox` để thử cục bộ; email được ghi vào `data/cms-mail-outbox` thay vì gửi thật.
4. Admin tạo tài khoản vai trò **Kiểm duyệt đăng kí**, chọn các phường phụ trách. Nếu đã tạo tài khoản kiểm duyệt theo quận ở bản trước, Admin cần sửa phạm vi tài khoản thành các phường tương ứng. Nhân viên đăng nhập tab **Kiểm duyệt đăng kí**. Sau duyệt, CMS tạo một tài khoản kiosk và một ghim cố định; Gmail gửi kết quả, tài khoản và mật khẩu ngẫu nhiên cho người đăng kí. Nếu gửi lỗi, hồ sơ hiển thị “Gửi lỗi” và có nút gửi lại (mật khẩu kiosk được tạo lại trước khi gửi).

Khi Flask có URL HTTPS công khai, có thể chuyển sang chế độ đẩy tự động: đặt `CMS_FORMS_WEBHOOK_SECRET` ở Flask, `CMS_API_URL` và `CMS_WEBHOOK_SECRET` trong Script properties; chạy `installCmsTrigger()` một lần. Trigger gửi hồ sơ mới về API `/api/cms/applications/intake`; chạy thêm `importExistingResponses()` nếu cần nhập hồ sơ cũ. Không bật trigger đẩy tới `localhost`.

Ghim chỉ hiển thị khi đang active, nội dung đã duyệt và gói còn hạn. Deactive ghim chuyển tài khoản cũ sang chỉ đọc; sau đó mới có thể cấp ghim ấy cho tài khoản mới. Địa chỉ và tọa độ ghim không thể sửa từ tài khoản người mua.

Các bảng CMS được tạo khi server khởi động. Nếu Flask đang chạy từ trước khi cập nhật mã, hãy khởi động lại để nạp các route và schema mới.

## Chạy thật trên www.xanh24.com (Vercel + Postgres)

Vercel không có ổ đĩa bền: nếu chỉ dùng SQLite, dữ liệu quản trị (địa điểm, vị trí kiosk, ảnh tải lên…) **sẽ mất** mỗi khi máy chủ khởi động lại. Từ v1.2 hệ thống hỗ trợ Postgres:

1. Vercel → dự án → **Storage → Create Database → Neon (Postgres)** → Connect vào dự án (tự thêm biến `DATABASE_URL`/`POSTGRES_URL`). Hoặc dùng Supabase/Neon bất kỳ và tự thêm `DATABASE_URL=postgresql://…?sslmode=require`.
2. **Settings → Environment Variables**: `XANH24_SECRET` (chuỗi ngẫu nhiên dài), `XANH24_ADMIN_PASSWORD` (mật khẩu `admin`), `XANH24_DOWNLOAD_PIN` (PIN để mở trang tải APK).
3. Đẩy mã lên nhánh `main` → Vercel tự triển khai. Lần chạy đầu tự tạo bảng và dữ liệu mẫu trong Postgres; ảnh tải lên được lưu trong CSDL (bảng `media_files`).
4. Kiểm tra: `https://www.xanh24.com/api/public/version` phải trả JSON có `data_version`.

Máy chủ riêng (VPS/Docker) vẫn dùng SQLite mặc định; đặt `DATABASE_URL` nếu muốn dùng Postgres.

## Vị trí “Bạn đang ở đây”
- **Định vị kiosk qua Wi-Fi (khuyến nghị):** tạo khoá *Geolocation API* trong Google Cloud (bật thanh toán; dịch vụ thuộc nhóm Essentials có hạn mức miễn phí hằng tháng), thêm biến môi trường `GOOGLE_GEOLOCATION_API_KEY` trên Vercel. Mỗi kiosk chỉ hỏi vài lần/ngày. Không có khoá, hệ thống dùng beaconDB (miễn phí, dữ liệu Việt Nam còn ít).
- **Điện thoại / máy tính:** tự hỏi quyền vị trí khi mở, dùng vị trí thật (vòng tròn thể hiện sai số) làm điểm xuất phát chỉ đường; nếu từ chối, dùng điểm tạm và nhắc bật định vị.
- **Kiosk (ứng dụng Android):** ưu tiên (1) vị trí kỹ thuật viên ghim trong menu cài đặt của ứng dụng → (2) GPS/Wi-Fi của thiết bị nếu sai số ≤ 100 m (hoặc khi toạ độ khai báo lệch xa vị trí thật) → (3) toạ độ khai báo ở Dashboard. Kiosk báo vị trí về máy chủ mỗi phút; Dashboard → Màn hình kiosk hiển thị “Vị trí thiết bị báo về” và nút *Dùng vị trí này*; chọn nguồn vị trí: Tự động / Cố định / Theo GPS.
- Màn hình LCD thường **không có chip GPS** — vị trí lấy theo Wi-Fi (sai số 20–100 m). Để chính xác tuyệt đối, ghim toạ độ khi lắp đặt (đứng tại máy, mở Google Maps trên điện thoại, nhấn giữ vị trí để lấy toạ độ, nhập vào menu cài đặt của ứng dụng hoặc Dashboard).

## Cài đặt màn hình LCD Android

**Cách khuyến nghị: ứng dụng `Xanh24 Kiosk` (APK)** — xem `android/README.md`. Mở `https://<tên-miền>/download`, nhập mã PIN và tải APK, mở lần đầu nhập địa chỉ máy chủ + mã màn hình. Ứng dụng tự chạy toàn màn hình, tự tải lại khi mất mạng/treo, tự cập nhật dữ liệu khi quản trị duyệt nội dung mới.

Cách khác (trình duyệt kiosk):

1. Thêm màn hình tại *Dashboard → Màn hình kiosk* (mã, phường, vị trí đặt máy trên bản đồ — hiển thị “Bạn đang ở đây” và là điểm xuất phát chỉ đường).
2. Trên thiết bị: cài **Fully Kiosk Browser** (khuyến nghị) hoặc Chrome + ghim ứng dụng. Trang khởi động = `https://<tên-miền>/?device=<MÃ>` (nút “Cài đặt” có sẵn QR).
3. Fully Kiosk: bật *Kiosk Mode*, *Launch on Boot*, *Keep Screen On*, tắt thanh điều hướng, bật *Autoplay Videos*, cho phép *Web Content → Enable WebGL*.
4. Màn hình khởi động ở chế độ chờ (quảng cáo). Thời gian chờ mặc định 40 giây — đổi ở *Cấu hình* hoặc riêng từng thiết bị. Thay đổi cấu hình được áp dụng tự động khi kiosk về chế độ chờ.
5. Menu thiết bị: giữ logo 3 giây → nhập PIN (mặc định `2424`, đổi ở *Cấu hình → Kiosk*).

Khuyến nghị phần cứng: Android 9+, RAM ≥ 3 GB, GPU hỗ trợ WebGL; màn hình 43–55" ngang 1920×1080 hoặc dọc 1080×1920 (giao diện tự điều chỉnh).

## Nhập liệu bằng Excel

1. *Dashboard → Nhập Excel → Tải biểu mẫu* (`Xanh24_Mau_Nhap_Dia_Diem.xlsx`, có sheet hướng dẫn và danh sách thả xuống).
2. Mỗi dòng một địa điểm. Bắt buộc: Tên, Danh mục, Vĩ độ, Kinh độ (có thể dán `21.0285, 105.8542` hoặc link Google Maps vào cột Vĩ độ). Để trống Phường — hệ thống tự xác định theo ranh giới.
3. Ảnh: chèn trực tiếp vào ô “Ảnh đại diện”, hoặc ghi tên tệp rồi nén ảnh thành .zip tải kèm. VR360: link tour hoặc tên tệp ảnh 360 (tỉ lệ 2:1).
4. Tải lên → xem kết quả kiểm tra → *Gửi phê duyệt* (Co-worker) hoặc *Công khai ngay* (Admin). Điền cột Mã (X24-xxxxx) để cập nhật địa điểm đã có.

## Cần cấu hình trước khi vận hành

| Hạng mục | Hiện trạng mặc định | Khuyến nghị |
|---|---|---|
| Bản đồ nền | OpenFreeMap (vector, không cần khoá) / OSM / Esri | Hợp đồng nhà cung cấp tile (Vietmap, MapTiler…) hoặc máy chủ tile riêng |
| Định tuyến | Máy chủ công cộng FOSSGIS (chỉ để dùng thử) | Tự dựng OSRM/Valhalla với dữ liệu OSM Việt Nam, khai báo ở *Cấu hình → Định tuyến* |
| Gọi xe | Grab: OneLink + deep link `grab://open?screenType=BOOKING…` (tham số không chính thức); Xanh SM: mở ứng dụng + sao chép địa chỉ + hotline | Xác nhận deep link/đối tác chính thức với Grab và Xanh SM (cấu hình tại *Cấu hình → Gọi xe*) |
| Xe buýt | Bến & tuyến lấy trực tiếp từ OpenStreetMap (Overpass công cộng, cần Internet); thời gian là ước tính | Tự dựng Overpass hoặc kết nối API Transerco qua module; khai báo máy chủ tại `transit.overpass` |
| Metro | Tuyến 2A và 3 (đoạn trên cao), toạ độ ga tham khảo | Xác minh toạ độ ga, cập nhật đoạn ngầm tuyến 3 khi khai thác |
| Địa điểm mẫu | Trụ sở UBND (theo ký hiệu bản đồ gốc) + 20 địa danh | Cán bộ xác minh, bổ sung giờ làm việc, điện thoại, ảnh |
| Ranh giới | Số hoá từ ảnh bản đồ, sai số ước tính 10–40 m | Thay bằng dữ liệu chính thức của Sở TN&MT khi có |

## Cấu trúc mã nguồn

Frontend React/JavaScript nằm trong `frontend/`; chạy `npm --prefix frontend ci` và `npm --prefix frontend run build` trước khi chạy Flask cục bộ để dùng giao diện mới. Xem `frontend/README.md` để chạy Vite khi phát triển.
```
frontend/
  index.html        Điểm vào chung cho bản đồ, quản trị, tải ứng dụng và gọi xe
  public/           Tài nguyên tĩnh thuộc frontend
  src/main.jsx      Khởi tạo React
  src/App.jsx       Ứng dụng gốc
  src/routes/       Chọn trang theo URL
  src/pages/        Các trang theo tuyến
  src/features/     Mã theo chức năng: map, admin, download, ride, kiosk, vr
  src/utils/        Icon và QR dùng chung
  src/styles/       CSS của từng trang
server/            Flask API + SQLite
  app.py           Toàn bộ API công khai & quản trị
  auth.py          Xác thực JWT, ma trận quyền S0/S1/CW, nhật ký
  importer.py      Đọc Excel (ảnh Excel 365 / WPS / ảnh nổi / zip), sinh biểu mẫu
  routing.py       Proxy định tuyến + hướng dẫn tiếng Việt
  seed.py          Dữ liệu nền, wards_seed.geojson (51 ranh giới)
  modules/         Module máy chủ (cổng mở rộng)
web/               Giao diện cũ dự phòng và tài nguyên dùng chung
  modules/sample/  Module mẫu (iframe)
  vendor/          MapLibre GL JS 5.24 (đóng gói sẵn, chạy offline)
  assets/maps/     Ảnh 50 bản đồ phương án gốc (đối chiếu)
tools/digitize/    Quy trình số hoá ranh giới từ ảnh bản đồ
tests/test_api.py  Kiểm thử luồng phân quyền, phê duyệt, nhập Excel
docs/              API, module, phương pháp số hoá ranh giới
```

## M4L 2.0 (thử nghiệm, mặc định tắt)

Trang khám phá theo cảm xúc tại `/m4l` (Home, hộp mù khám phá ngẫu nhiên), `/m4l/discover` (Mood & tìm kiếm), `/m4l/world` (bản đồ sương mù Fog of War) và `/m4l/admin` (mood, khu vực khám phá, ghim bí ẩn). Thiết kế, audit và kế hoạch: `docs/m4l/`.

- Fog of War phủ **toàn Hà Nội** (126 phường/xã, ~337 nghìn ô 100 m) dựng từ OpenStreetMap; Cầu Giấy giữ làm khu pilot. Ô chỉ mở khi server xác nhận nhiều lần đo GPS đủ chính xác; định vị chỉ chạy khi người dùng bật trên `/m4l/world` và trang đang mở. Chi tiết: `docs/m4l/HANOI_SCALEUP.md`, số liệu: `docs/m4l/HANOI_GRID_REPORT.md`.
- Dựng lại dữ liệu lưới (cần Internet, chỉ làm khi cập nhật dữ liệu): `python tools/m4l_grid/fetch.py --roads` rồi `python tools/m4l_grid/build.py`. Lần khởi động đầu sau khi có dữ liệu chạy migration v3 (sao lưu trước, nạp lưới, chuyển tiến độ Cầu Giấy sang Hà Nội).
- Random mặc định quay trong nhóm đối tác VIP đang chạy chiến dịch (có nhãn Tài trợ). Khi không có VIP, random rơi về gợi ý tự nhiên đã gắn mood và ghi rõ “không tài trợ”. Mỗi tài khoản có 10 lượt/24 giờ. Các ngưỡng chỉnh qua setting JSON `m4l_config` (xem `DEFAULT_CONFIG` trong `server/m4l_service.py`).
- Thương mại (migration v4): voucher đếm ngược (`/m4l/vouchers`), cổng đối tác và xác nhận voucher tại quầy (`/m4l/partner`, `/m4l/v/<mã>`), màn hình trạm (`/m4l/station`), duyệt chiến dịch / khóa kiosk / analytics trong `/m4l/admin`. Không có thanh toán; POS là bản giả lập. Demo tái lập được: `server/seed_m4l_demo.py` (từ chối chạy trên `data/xanh24.db`). Xem `docs/m4l/DEMO_GUIDE.md`, `API_CONTRACT.md`, `RELEASE_READINESS.md`.

- Bật bằng biến môi trường `XANH24_M4L_ENABLED=1`. Khi tắt, mọi route `/m4l*`, `/api/m4l/*` trả 404 và không bảng nào được tạo.
- Lần khởi động đầu khi bật cờ: sao lưu SQLite vào `data/backups/` rồi tạo bảng `m4l_*` và 4 mood mẫu (có thể sửa/tắt). Không tạo hoặc gán địa điểm.
- Quản lý: đăng nhập `/hrm/login` (mục Quản trị viên) rồi mở `/m4l/admin`. Admin S0 thêm/sửa mood; Quản trị nội dung gán mood cho địa điểm trong phường được giao.
- Người dùng đăng nhập ở `/cms/login`; mở lại `/m4l` để thấy lời chào theo tên.
- Migration: `python server/m4l_migrations.py status | backup | migrate | downgrade --to 0 --yes` (downgrade chỉ gỡ bảng `m4l_*`, có sao lưu trước).

```powershell
$env:XANH24_M4L_ENABLED = "1"; .\.venv\Scripts\python.exe server\app.py   # http://localhost:8024/m4l
```

## Kiểm thử
```bash
python tests/test_api.py
python tests/test_m4l.py
python tests/test_m4l_phase2.py
python tests/test_m4l_hanoi.py
```

## Nhật ký thay đổi

**v1.3.0 (30/09/2026)**
- Tìm **địa chỉ / địa điểm bất kỳ** ngay trong ô tìm kiếm (OpenStreetMap: Photon, dự phòng Nominatim; khoanh vùng Hà Nội) → chạm để ghim và chỉ đường.
- Kiosk không có GPS: ứng dụng Android quét Wi-Fi xung quanh và hỏi `/api/public/geolocate` (Google Geolocation API nếu đặt `GOOGLE_GEOLOCATION_API_KEY`, dự phòng beaconDB). Ghim vị trí máy bằng cách chạm bản đồ → menu thiết bị → *Ghim điểm vừa chạm*.
- Chế độ nhẹ cho kiosk/TV: vẽ 1×, bỏ nhà 3D/hiệu ứng, tái sử dụng marker; WebView không ép hardware layer.

**v1.2.0 (30/09/2026)**
- Vị trí thật: web/điện thoại tự định vị; kiosk dùng GPS/Wi-Fi của thiết bị hoặc vị trí ghim trong ứng dụng, báo về máy chủ; Dashboard chọn nguồn vị trí.
- Hỗ trợ Postgres qua `DATABASE_URL` (dữ liệu và ảnh không mất khi chạy trên Vercel).
- Ứng dụng Android 1.1.0: quyền Vị trí, ghim vị trí đặt máy, tương thích máy chủ cũ.

**v1.1.0 (30/09/2026)**
- Chọn điểm bất kỳ trên bản đồ + chỉ đường/gọi xe/QR tới điểm đó; API `/api/public/reverse` (Nominatim, có đệm, 1 yêu cầu/giây; đổi máy chủ tại cấu hình `geocode.reverse_url`).
- Bộ nhớ đệm ngoại tuyến (`web/sw.js`): giao diện, dữ liệu công khai, ô bản đồ nền, ảnh — kiosk khởi động nhanh và vẫn chạy khi mất mạng.
- Tự cập nhật dữ liệu: `data_version` trong heartbeat/`/api/public/version`; kiosk tự nạp lại khi về chế độ chờ.
- Ứng dụng Android kiosk `android/` (APK ký sẵn trong `web/downloads/`).

**v1.0.1 (25/09/2026)** — theo góp ý chạy thử:
1. Chọn phường: viền xanh đậm + quầng trắng, tô nhạt vùng phường, làm tối phần ngoài phường.
2. Lộ trình được vẽ trên bản đồ nền (nét liền cho xe, nét chấm cho đi bộ). Lỗi không hiện đường chỉ có ở bản chạy thử 1 tệp (dữ liệu giả lập tạo ở khung ngoài), bản cài đặt thật không bị.
3. Bản chạy thử: gộp thanh công cụ demo vào nút trong thanh tiêu đề của ứng dụng.
4. QR Grab dùng link OneLink → mở thẳng ứng dụng Grab; Xanh SM mở ứng dụng trên Android + sao chép địa chỉ.
5. Chế độ Buýt · Metro tìm tuyến buýt OSM đi thẳng, vẽ tuyến theo đường thực tế, liệt kê bến gần nhất (nút “Dẫn tới bến”); các chế độ khác có mục “Bến xe buýt & ga Metro gần bạn”.
6. Bản đồ nền mặc định chuyển sang OpenFreeMap (CARTO đã yêu cầu API key).
