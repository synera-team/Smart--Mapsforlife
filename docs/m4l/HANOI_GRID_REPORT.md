# Lưới Fog of War toàn Hà Nội — báo cáo dữ liệu

Sinh bởi `tools/m4l_grid/build.py` lúc 2026-10-29T02:29:57+00:00 · dữ liệu OSM tại 2026-10-29T02:27:36Z.

## Nguồn và giấy phép

- Nguồn: OpenStreetMap relation 1903516 (admin_level=4) + 126 relations admin_level=6; highway, natural=water, waterway=riverbank, landuse=military.
- Giấy phép: ODbL 1.0 — © OpenStreetMap contributors (https://www.openstreetmap.org/copyright). Bắt buộc ghi công trên giao diện; CSDL phái sinh công bố ra ngoài phải theo ODbL.
- Hệ tọa độ: EPSG:4326 (WGS84). Lưới: ô 100 m, vĩ độ tham chiếu 21.0 (trùng lưới pilot Cầu Giấy).
- Ghi chú hiệu lực: Ranh giới cấp xã theo sắp xếp có hiệu lực 01/07/2025 do cộng đồng OSM số hóa; chưa đối chiếu bản đồ chính thức.

## Kiểm chứng phạm vi

- Số ô có tâm nằm trong ranh giới thành phố: **337,035** ≈ 3,370 km² (mỗi ô ~0,01 km²).
- Diện tích vòng ranh giới ngoài tính từ OSM: 3,371 km² (Hà Nội công bố ~3.359 km²).
- Đơn vị cấp xã trong OSM: 126 (51 phường, 75 xã).
- Khớp mã phường trong CSDL Xanh24 (`wards`, 51 đơn vị): 51; có trong CSDL nhưng khác tên ở OSM: không.

## Số ô theo trạng thái

| Trạng thái | Số ô | Tỷ lệ | Ý nghĩa |
|---|---:|---:|---|
| `eligible` | 200,444 | 59.5% | Có đường/lối đi công cộng — tính vào mẫu số |
| `pending_review` | 114,784 | 34.1% | Chưa có dữ liệu đường — chưa tính vào mẫu số, vẫn mở khóa được khi đến thật |
| `excluded` | 18,974 | 5.6% | Mặt nước — không tính, không mở khóa |
| `restricted` | 2,833 | 0.8% | Khu quân sự — không tính, không mở khóa |

## Số ô theo phường/xã

| Đơn vị | Loại | Tổng ô | eligible | pending | excluded | restricted |
|---|---|---:|---:|---:|---:|---:|
| Phường Ba Đình (`ba-dinh`) | phuong | 292 | 224 | 11 | 25 | 32 |
| Phường Bạch Mai (`bach-mai`) | phuong | 289 | 276 | 0 | 13 | 0 |
| Phường Bồ Đề (`bo-de`) | phuong | 1,278 | 913 | 57 | 274 | 34 |
| Phường Chương Mỹ (`chuong-my`) | phuong | 3,925 | 2,521 | 1,342 | 62 | 0 |
| Phường Cầu Giấy (`cau-giay`) | phuong | 403 | 381 | 2 | 19 | 1 |
| Phường Cửa Nam (`cua-nam`) | phuong | 168 | 159 | 0 | 0 | 9 |
| Phường Dương Nội (`duong-noi`) | phuong | 782 | 735 | 40 | 7 | 0 |
| Phường Giảng Võ (`giang-vo`) | phuong | 260 | 225 | 3 | 31 | 1 |
| Phường Hai Bà Trưng (`hai-ba-trung`) | phuong | 263 | 233 | 1 | 29 | 0 |
| Phường Hoàn Kiếm (`hoan-kiem`) | phuong | 194 | 178 | 1 | 9 | 6 |
| Phường Hoàng Liệt (`hoang-liet`) | phuong | 410 | 309 | 21 | 80 | 0 |
| Phường Hoàng Mai (`hoang-mai`) | phuong | 879 | 716 | 12 | 151 | 0 |
| Phường Hà Đông (`ha-dong`) | phuong | 937 | 917 | 3 | 17 | 0 |
| Phường Hồng Hà (`hong-ha`) | phuong | 1,546 | 880 | 174 | 492 | 0 |
| Phường Khương Đình (`khuong-dinh`) | phuong | 312 | 284 | 12 | 14 | 2 |
| Phường Kim Liên (`kim-lien`) | phuong | 247 | 235 | 0 | 7 | 5 |
| Phường Kiến Hưng (`kien-hung`) | phuong | 649 | 580 | 63 | 6 | 0 |
| Phường Long Biên (`long-bien`) | phuong | 1,938 | 1,426 | 193 | 205 | 114 |
| Phường Láng (`lang`) | phuong | 189 | 178 | 1 | 10 | 0 |
| Phường Lĩnh Nam (`linh-nam`) | phuong | 1,080 | 638 | 159 | 283 | 0 |
| Phường Nghĩa Đô (`nghia-do`) | phuong | 433 | 385 | 12 | 14 | 22 |
| Phường Ngọc Hà (`ngoc-ha`) | phuong | 261 | 252 | 2 | 2 | 5 |
| Phường Phú Diễn (`phu-dien`) | phuong | 632 | 529 | 79 | 24 | 0 |
| Phường Phú Lương (`phu-luong`) | phuong | 944 | 669 | 275 | 0 | 0 |
| Phường Phú Thượng (`phu-thuong`) | phuong | 760 | 487 | 107 | 166 | 0 |
| Phường Phúc Lợi (`phuc-loi`) | phuong | 1,034 | 787 | 109 | 120 | 18 |
| Phường Phương Liệt (`phuong-liet`) | phuong | 331 | 252 | 1 | 21 | 57 |
| Phường Sơn Tây (`son-tay`) | phuong | 2,350 | 1,477 | 669 | 197 | 7 |
| Phường Thanh Liệt (`thanh-liet`) | phuong | 643 | 576 | 47 | 20 | 0 |
| Phường Thanh Xuân (`thanh-xuan`) | phuong | 330 | 316 | 1 | 12 | 1 |
| Phường Thượng Cát (`thuong-cat`) | phuong | 1,465 | 793 | 399 | 273 | 0 |
| Phường Tây Hồ (`tay-ho`) | phuong | 1,058 | 486 | 12 | 558 | 2 |
| Phường Tây Mỗ (`tay-mo`) | phuong | 554 | 505 | 31 | 14 | 4 |
| Phường Tây Tựu (`tay-tuu`) | phuong | 759 | 606 | 144 | 8 | 1 |
| Phường Tùng Thiện (`tung-thien`) | phuong | 3,264 | 2,127 | 804 | 175 | 158 |
| Phường Tương Mai (`tuong-mai`) | phuong | 355 | 340 | 0 | 11 | 4 |
| Phường Từ Liêm (`tu-liem`) | phuong | 1,009 | 885 | 59 | 55 | 10 |
| Phường Việt Hưng (`viet-hung`) | phuong | 1,302 | 1,064 | 109 | 127 | 2 |
| Phường Văn Miếu - Quốc Tử Giám (`van-mieu-quoc-tu-giam`) | phuong | 196 | 188 | 0 | 8 | 0 |
| Phường Vĩnh Hưng (`vinh-hung`) | phuong | 439 | 392 | 14 | 29 | 4 |
| Phường Vĩnh Tuy (`vinh-tuy`) | phuong | 234 | 228 | 0 | 6 | 0 |
| Phường Xuân Phương (`xuan-phuong`) | phuong | 1,085 | 846 | 154 | 29 | 56 |
| Phường Xuân Đỉnh (`xuan-dinh`) | phuong | 555 | 497 | 46 | 12 | 0 |
| Phường Yên Hòa (`yen-hoa`) | phuong | 414 | 394 | 4 | 6 | 10 |
| Phường Yên Nghĩa (`yen-nghia`) | phuong | 1,323 | 925 | 375 | 16 | 7 |
| Phường Yên Sở (`yen-so`) | phuong | 558 | 330 | 21 | 207 | 0 |
| Phường Ô Chợ Dừa (`o-cho-dua`) | phuong | 184 | 170 | 0 | 13 | 1 |
| Phường Đông Ngạc (`dong-ngac`) | phuong | 892 | 691 | 102 | 91 | 8 |
| Phường Đại Mỗ (`dai-mo`) | phuong | 805 | 628 | 132 | 38 | 7 |
| Phường Định Công (`dinh-cong`) | phuong | 532 | 489 | 8 | 34 | 1 |
| Phường Đống Đa (`dong-da`) | phuong | 206 | 196 | 0 | 7 | 3 |
| Xã An Khánh (`xa-an-khanh`) | xa | 2,908 | 2,066 | 786 | 51 | 5 |
| Xã Ba Vì (`xa-ba-vi`) | xa | 8,079 | 2,672 | 4,994 | 337 | 76 |
| Xã Bát Tràng (`xa-bat-trang`) | xa | 2,103 | 1,486 | 226 | 379 | 12 |
| Xã Bình Minh (`xa-binh-minh`) | xa | 2,995 | 1,821 | 1,098 | 76 | 0 |
| Xã Bất Bạt (`xa-bat-bat`) | xa | 5,508 | 3,396 | 1,216 | 736 | 160 |
| Xã Chuyên Mỹ (`xa-chuyen-my`) | xa | 3,577 | 1,886 | 1,691 | 0 | 0 |
| Xã Chương Dương (`xa-chuong-duong`) | xa | 2,885 | 1,751 | 948 | 186 | 0 |
| Xã Cổ Đô (`xa-co-do`) | xa | 4,759 | 2,964 | 379 | 1,416 | 0 |
| Xã Dân Hòa (`xa-dan-hoa`) | xa | 3,867 | 2,210 | 1,641 | 16 | 0 |
| Xã Dương Hòa (`xa-duong-hoa`) | xa | 1,744 | 1,282 | 458 | 4 | 0 |
| Xã Gia Lâm (`xa-gia-lam`) | xa | 2,565 | 1,973 | 411 | 172 | 9 |
| Xã Hoài Đức (`xa-hoai-duc`) | xa | 1,684 | 1,182 | 478 | 7 | 17 |
| Xã Hát Môn (`xa-hat-mon`) | xa | 3,771 | 2,483 | 1,281 | 7 | 0 |
| Xã Hòa Lạc (`xa-hoa-lac`) | xa | 4,323 | 2,220 | 1,398 | 170 | 535 |
| Xã Hòa Phú (`xa-hoa-phu`) | xa | 3,006 | 1,830 | 1,067 | 106 | 3 |
| Xã Hòa Xá (`xa-hoa-xa`) | xa | 4,053 | 2,198 | 1,852 | 3 | 0 |
| Xã Hưng Đạo (`xa-hung-dao`) | xa | 2,491 | 1,578 | 901 | 12 | 0 |
| Xã Hương Sơn (`xa-huong-son`) | xa | 6,888 | 2,161 | 4,716 | 11 | 0 |
| Xã Hạ Bằng (`xa-ha-bang`) | xa | 3,149 | 1,963 | 1,147 | 39 | 0 |
| Xã Hồng Sơn (`xa-hong-son`) | xa | 5,483 | 2,335 | 2,700 | 448 | 0 |
| Xã Hồng Vân (`xa-hong-van`) | xa | 2,467 | 1,639 | 617 | 211 | 0 |
| Xã Kim Anh (`xa-kim-anh`) | xa | 5,348 | 3,680 | 1,541 | 127 | 0 |
| Xã Kiều Phú (`xa-kieu-phu`) | xa | 3,476 | 2,250 | 1,212 | 14 | 0 |
| Xã Liên Minh (`xa-lien-minh`) | xa | 2,410 | 1,473 | 625 | 312 | 0 |
| Xã Minh Châu (`xa-minh-chau`) | xa | 1,023 | 317 | 403 | 303 | 0 |
| Xã Mê Linh (`xa-me-linh`) | xa | 3,498 | 1,999 | 1,245 | 254 | 0 |
| Xã Mỹ Đức (`xa-my-duc`) | xa | 5,307 | 2,187 | 3,037 | 83 | 0 |
| Xã Nam Phù (`xa-nam-phu`) | xa | 1,358 | 957 | 221 | 180 | 0 |
| Xã Ngọc Hồi (`xa-ngoc-hoi`) | xa | 1,343 | 854 | 456 | 33 | 0 |
| Xã Nội Bài (`xa-noi-bai`) | xa | 5,188 | 3,061 | 2,011 | 115 | 1 |
| Xã Phù Đổng (`xa-phu-dong`) | xa | 4,201 | 2,433 | 1,267 | 491 | 10 |
| Xã Phú Cát (`xa-phu-cat`) | xa | 5,132 | 3,346 | 1,784 | 2 | 0 |
| Xã Phú Nghĩa (`xa-phu-nghia`) | xa | 4,030 | 2,349 | 1,678 | 3 | 0 |
| Xã Phú Xuyên (`xa-phu-xuyen`) | xa | 6,053 | 3,435 | 2,304 | 314 | 0 |
| Xã Phúc Lộc (`xa-phuc-loc`) | xa | 4,270 | 2,258 | 997 | 1,015 | 0 |
| Xã Phúc Sơn (`xa-phuc-son`) | xa | 4,939 | 2,235 | 1,979 | 468 | 257 |
| Xã Phúc Thịnh (`xa-phuc-thinh`) | xa | 4,295 | 2,885 | 1,255 | 155 | 0 |
| Xã Phúc Thọ (`xa-phuc-tho`) | xa | 3,997 | 2,411 | 1,583 | 3 | 0 |
| Xã Phượng Dực (`xa-phuong-duc`) | xa | 4,489 | 2,535 | 1,948 | 6 | 0 |
| Xã Quang Minh (`xa-quang-minh`) | xa | 3,215 | 2,236 | 971 | 7 | 1 |
| Xã Quảng Bị (`xa-quang-bi`) | xa | 3,741 | 2,355 | 1,367 | 19 | 0 |
| Xã Quảng Oai (`xa-quang-oai`) | xa | 4,801 | 3,074 | 1,255 | 366 | 106 |
| Xã Quốc Oai (`xa-quoc-oai`) | xa | 2,451 | 1,813 | 636 | 2 | 0 |
| Xã Suối Hai (`xa-suoi-hai`) | xa | 5,412 | 2,668 | 1,796 | 911 | 37 |
| Xã Sóc Sơn (`xa-soc-son`) | xa | 6,908 | 4,237 | 2,522 | 148 | 1 |
| Xã Sơn Đồng (`xa-son-dong`) | xa | 2,176 | 1,638 | 505 | 33 | 0 |
| Xã Tam Hưng (`xa-tam-hung`) | xa | 2,949 | 1,503 | 1,410 | 36 | 0 |
| Xã Thanh Oai (`xa-thanh-oai`) | xa | 2,694 | 1,779 | 905 | 10 | 0 |
| Xã Thanh Trì (`xa-thanh-tri`) | xa | 1,008 | 755 | 128 | 119 | 6 |
| Xã Thiên Lộc (`xa-thien-loc`) | xa | 2,854 | 1,739 | 815 | 300 | 0 |
| Xã Thuận An (`xa-thuan-an`) | xa | 2,960 | 2,226 | 547 | 174 | 13 |
| Xã Thư Lâm (`xa-thu-lam`) | xa | 4,372 | 3,094 | 1,260 | 13 | 5 |
| Xã Thường Tín (`xa-thuong-tin`) | xa | 2,837 | 1,945 | 841 | 51 | 0 |
| Xã Thượng Phúc (`xa-thuong-phuc`) | xa | 2,920 | 1,789 | 1,073 | 58 | 0 |
| Xã Thạch Thất (`xa-thach-that`) | xa | 3,204 | 1,705 | 1,488 | 11 | 0 |
| Xã Tiến Thắng (`xa-tien-thang`) | xa | 3,663 | 2,236 | 1,393 | 34 | 0 |
| Xã Trung Giã (`xa-trung-gia`) | xa | 7,788 | 5,203 | 2,420 | 165 | 0 |
| Xã Trần Phú (`xa-tran-phu`) | xa | 4,219 | 2,336 | 1,581 | 301 | 1 |
| Xã Tây Phương (`xa-tay-phuong`) | xa | 3,101 | 1,759 | 1,325 | 17 | 0 |
| Xã Vân Đình (`xa-van-dinh`) | xa | 4,134 | 2,189 | 1,926 | 19 | 0 |
| Xã Vĩnh Thanh (`xa-vinh-thanh`) | xa | 2,191 | 1,327 | 488 | 376 | 0 |
| Xã Vật Lại (`xa-vat-lai`) | xa | 5,206 | 3,415 | 1,243 | 500 | 48 |
| Xã Xuân Mai (`xa-xuan-mai`) | xa | 5,319 | 3,253 | 1,899 | 122 | 45 |
| Xã Yên Bài (`xa-yen-bai`) | xa | 6,900 | 2,967 | 3,304 | 159 | 470 |
| Xã Yên Lãng (`xa-yen-lang`) | xa | 4,513 | 2,409 | 1,644 | 460 | 0 |
| Xã Yên Xuân (`xa-yen-xuan`) | xa | 7,071 | 2,882 | 4,110 | 65 | 14 |
| Xã Ô Diên (`xa-o-dien`) | xa | 3,219 | 1,857 | 942 | 420 | 0 |
| Xã Đa Phúc (`xa-da-phuc`) | xa | 5,589 | 2,727 | 2,692 | 170 | 0 |
| Xã Đan Phượng (`xa-dan-phuong`) | xa | 1,535 | 1,234 | 294 | 7 | 0 |
| Xã Đoài Phương (`xa-doai-phuong`) | xa | 5,798 | 2,831 | 1,493 | 1,079 | 395 |
| Xã Đông Anh (`xa-dong-anh`) | xa | 4,944 | 3,461 | 1,148 | 321 | 14 |
| Xã Đại Thanh (`xa-dai-thanh`) | xa | 1,901 | 1,264 | 617 | 20 | 0 |
| Xã Đại Xuyên (`xa-dai-xuyen`) | xa | 5,159 | 2,962 | 2,063 | 134 | 0 |
| Xã Ứng Hòa (`xa-ung-hoa`) | xa | 6,794 | 3,326 | 3,440 | 28 | 0 |
| Xã Ứng Thiên (`xa-ung-thien`) | xa | 3,879 | 1,971 | 1,881 | 27 | 0 |
| (Không thuộc đơn vị nào — dải ven ranh giới) | — | 0 | 0 | 0 | 0 | 0 |

## Hạn chế

- `eligible` dựa trên đường OSM: thiếu đường ngõ nhỏ chưa vẽ thì ô bị xếp `pending_review`, không bị coi là bắt buộc.
- Mặt nước nhỏ hơn một ô vẫn có thể khiến ô bị loại nếu phủ đúng tâm ô.
- Khu hạn chế chỉ gồm `landuse=military` trong OSM; khu hạn chế khác do quản trị viên khai báo trong `/m4l/admin`.
- Ranh giới do cộng đồng OSM số hóa, chưa phải dữ liệu pháp lý; cần đối chiếu nguồn chính thức trước khi công bố số liệu.
