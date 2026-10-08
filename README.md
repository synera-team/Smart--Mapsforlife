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
- Danh sách thử nghiệm hiện có APK `LCD_kiosk_Dong_Do_ver 1.0.0.apk` từ Google Drive dùng chung. Tệp được proxy qua backend, bao gồm bước xác nhận cảnh báo tải của Google; các APK trong `web/downloads/` không được đưa vào danh sách này.
- Để đưa thêm ứng dụng lên danh sách, khai báo metadata và Drive file ID trong `DOWNLOAD_APPS` ở `server/app.py`. Chỉ file ID ở backend được dùng để tải, không gửi link Drive cho trình duyệt.

## Chạy thử

Yêu cầu Python 3.10+.

```bash
./run.sh
# Bản đồ:    http://localhost:8024
# Kiosk:     http://localhost:8024/?device=HK-01
# Quản trị:  http://localhost:8024/admin   (tài khoản: admin — mật khẩu trong data/INITIAL_ADMIN.txt)
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
```
server/            Flask API + SQLite
  app.py           Toàn bộ API công khai & quản trị
  auth.py          Xác thực JWT, ma trận quyền S0/S1/CW, nhật ký
  importer.py      Đọc Excel (ảnh Excel 365 / WPS / ảnh nổi / zip), sinh biểu mẫu
  routing.py       Proxy định tuyến + hướng dẫn tiếng Việt
  seed.py          Dữ liệu nền, wards_seed.geojson (51 ranh giới)
  modules/         Module máy chủ (cổng mở rộng)
web/
  index.html js/app.js css/app.css   Ứng dụng bản đồ (kiosk/mobile/web)
  js/vr.js         Trình xem VR360 WebGL   js/qr.js  Tạo mã QR offline   js/osk.js  Bàn phím ảo
  admin/           Dashboard quản trị
  go.html          Trang trung gian gọi xe trên điện thoại
  modules/sample/  Module mẫu (iframe)
  vendor/          MapLibre GL JS 5.24 (đóng gói sẵn, chạy offline)
  assets/maps/     Ảnh 50 bản đồ phương án gốc (đối chiếu)
tools/digitize/    Quy trình số hoá ranh giới từ ảnh bản đồ
tests/test_api.py  Kiểm thử luồng phân quyền, phê duyệt, nhập Excel
docs/              API, module, phương pháp số hoá ranh giới
```

## Kiểm thử
```bash
python tests/test_api.py
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
