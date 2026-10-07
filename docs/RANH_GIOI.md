# Ranh giới hành chính — phương pháp số hoá & độ tin cậy

## Nguồn
50 tệp **“Bản đồ phương án thành lập phường/xã … thuộc Thành phố Hà Nội”** (Sở Nội vụ TP Hà Nội; biên tập: Công ty TNHH Tài nguyên Môi trường và Bản đồ TP.HCM), áp dụng từ 01/07/2025. Hệ quy chiếu trên bản đồ: **VN-2000, kinh tuyến trục 105°, múi 6°**.

## Quy trình (mã nguồn trong `tools/digitize/`)
1. **Tách vùng phường**: nhận diện màu nền vàng/xanh của đơn vị hành chính và đường ranh giới hồng “ĐGHC cấp xã phương án”; lấp vùng khép kín bởi đường ranh giới (bao gồm cả mặt nước sông/hồ thuộc phường), làm mịn và lấy đường tâm dải ranh giới (`poly.py`, `poly2.py`).
2. **Đọc lưới toạ độ**: phát hiện khung bản đồ, vị trí các nhãn kinh độ/vĩ độ màu xanh ở lề (mỗi 1′ hoặc 2′), đọc giá trị nhãn (`frame.py`, `labels.py`, `values.py`) và tỷ lệ bản đồ bằng OCR (`scale.py`).
3. **Khớp toạ độ**: bình sai bình phương nhỏ nhất (tham số: gốc E, N và tỷ lệ m/pixel) giữa các nhãn lưới và phép chiếu **UTM/TM kinh tuyến trục 105°, k₀ = 0,9996**, kết hợp ràng buộc tỷ lệ in (`fit.py`, `tm.py`).
4. **Chuyển hệ**: VN-2000 → WGS84 bằng phép Helmert 7 tham số chuẩn (EPSG:4756).
5. **Kiểm chứng**: tâm Hồ Hoàn Kiếm tính từ bản đồ số hoá = 21,02872° N, 105,85257° E — trùng khớp vị trí thực tế (sai lệch ≈ 10–20 m). Toàn bộ 51 đa giác ghép khít nhau khi chồng lên cùng một bản đồ.

## Độ tin cậy
- Sai số khớp lưới (RMS) phần lớn **dưới 5 m**; một số tệp độ phân giải thấp 10–30 m.
- Sai số tổng thể ước tính **10–40 m** (độ rộng nét vẽ ranh giới trên bản in, độ phân giải ảnh quét). Đủ cho hiển thị tra cứu công khai, **không thay thế hồ sơ địa giới pháp lý**.
- Khi có tệp ranh giới chính thức (shapefile/GeoJSON của Sở Tài nguyên & Môi trường), Admin S0 thay thế tại *Dashboard → Ranh giới phường → Tải GeoJSON*; có tuỳ chọn gán lại phường cho toàn bộ địa điểm.
- Chưa có trong bộ dữ liệu: phường **Văn Miếu – Quốc Tử Giám** và các phường/xã khác không có bản đồ trong dữ liệu gửi kèm. Địa điểm tại các khu vực đó vẫn hiển thị, chỉ không được gán phường.

## Bảng chi tiết

| Đơn vị | Diện tích (km²) | Số nhãn lưới | RMS (m) | Lớn nhất (m) | Ghi chú |
|---|---|---|---|---|---|
| Phường Ba Đình | 3.01 | 7 | 0.6 | 1.0 |  |
| Phường Bạch Mai | 2.99 | 3 | 0.3 | 0.3 |  |
| Phường Bồ Đề | 12.83 | 5 | 4.5 | 5.7 |  |
| Phường Chương Mỹ | 39.72 | 12 | 2.4 | 4.5 |  |
| Phường Cầu Giấy | 4.01 | 8 | 0.6 | 1.3 |  |
| Phường Cửa Nam | 1.7 | 4 | 1.9 | 2.4 |  |
| Phường Dương Nội | 7.97 | 4 | 0.1 | 0.2 |  |
| Phường Giảng Võ | 2.64 | 3 | 0.1 | 0.1 |  |
| Phường Hai Bà Trưng | 2.67 | 3 | 1.2 | 1.5 |  |
| Phường Hoàn Kiếm | 1.97 | 4 | 0.6 | 0.6 |  |
| Phường Hoàng Liệt | 4.2 | 6 | 9.0 | 15.9 |  |
| Phường Hoàng Mai | 8.93 | 10 | 1.4 | 2.1 |  |
| Phường Hà Đông | 9.55 | 6 | 7.4 | 11.2 |  |
| Phường Hồng Hà | 15.68 | 10 | 3.4 | 8.0 |  |
| Xã Hồng Sơn | 56.7 | 8 | 1.2 | 1.7 |  |
| Phường Khương Đình | 3.18 | 6 | 0.3 | 0.5 |  |
| Phường Kim Liên | 2.55 | 5 | 7.9 | 12.8 |  |
| Phường Kiến Hưng | 6.51 | 3 | 6.9 | 8.5 |  |
| Phường Long Biên | 19.74 | 7 | 0.7 | 0.9 |  |
| Phường Láng | 1.93 | 5 | 2.7 | 3.7 |  |
| Phường Lĩnh Nam | 11.13 | 7 | 1.1 | 1.6 |  |
| Phường Nghĩa Đô | 4.45 | 6 | 0.5 | 0.9 |  |
| Phường Ngọc Hà | 2.64 | 5 | 10.5 | 16.7 |  |
| Phường Phú Diễn | 6.47 | 7 | 1.5 | 2.9 |  |
| Phường Phú Lương | 9.72 | 0 | 0.0 | 0.0 | Suy từ phường lân cận (bản đồ không ghi nhãn toạ độ) |
| Phường Phú Thượng | 7.37 | 3 | 5.2 | 6.4 |  |
| Phường Phúc Lợi | 9.89 | 7 | 2.5 | 4.0 |  |
| Phường Phương Liệt | 3.29 | 5 | 9.2 | 14.3 |  |
| Phường Sơn Tây | 21.78 | 5 | 4.3 | 5.9 |  |
| Phường Thanh Liệt | 6.58 | 4 | 0.9 | 1.3 |  |
| Phường Thanh Xuân | 3.34 | 3 | 0.0 | 0.0 |  |
| Phường Thượng Cát | 14.91 | 8 | 4.8 | 6.6 |  |
| Phường Tây Hồ | 10.73 | 6 | 1.6 | 3.0 |  |
| Phường Tây Mỗ | 5.72 | 3 | 0.1 | 0.1 |  |
| Phường Tây Tựu | 7.71 | 4 | 0.3 | 0.3 |  |
| Phường Tùng Thiện | 33.03 | 8 | 28.8 | 61.3 |  |
| Phường Tương Mai | 3.65 | 2 | 0.0 | 0.0 |  |
| Phường Từ Liêm | 10.24 | 4 | 0.1 | 0.1 |  |
| Phường Việt Hưng | 13.13 | 4 | 0.4 | 0.6 |  |
| Phường Vĩnh Hưng | 4.55 | 4 | 12.6 | 18.1 |  |
| Phường Vĩnh Tuy | 2.35 | 3 | 0.6 | 0.8 |  |
| Phường Xuân Phương | 11.18 | 4 | 2.7 | 3.7 |  |
| Phường Xuân Đỉnh | 5.57 | 7 | 0.4 | 0.5 |  |
| Phường Yên Hòa | 4.13 | 4 | 4.1 | 5.8 |  |
| Phường Yên Nghĩa | 13.38 | 3 | 0.0 | 0.0 |  |
| Phường Yên Sở | 5.73 | 10 | 13.0 | 25.4 |  |
| Phường Ô Chợ Dừa | 1.87 | 8 | 1.3 | 2.8 |  |
| Phường Đông Ngạc | 9.03 | 11 | 1.6 | 4.7 |  |
| Phường Đại Mỗ | 8.22 | 4 | 2.3 | 3.8 |  |
| Phường Định Công | 5.54 | 5 | 14.2 | 22.8 |  |
| Phường Đống Đa | 2.16 | 6 | 1.3 | 2.2 |  |