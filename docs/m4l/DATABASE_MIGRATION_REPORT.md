# M4L 2.0: Báo cáo migration

## Môi trường đã chạy

| CSDL | v1–v3 | v4 | Ghi chú |
|---|---|---|---|
| `data/xanh24.db` (DB thật) | **Chưa** | **Chưa** | Không có bảng `m4l_*`, đã kiểm lại ngày 29/10/2026. Cần phê duyệt trước khi chạy |
| Bản sao DB thật, scratch `m4l-hn` | Có (đợt trước) | Không | Nguồn để tạo các bản bên dưới |
| Bản sao kiểm thử v4, scratch `mig4` | Có | Có → rollback → chạy lại | Mục 2 |
| Bản sao demo, scratch `m4l-demo` | Có | Có + seed demo | Môi trường demo |
| DB tạm của từng bộ test | Có | Có | Được xóa sau khi chạy |
| Postgres | Không | Không | Chưa có môi trường |

Ghi chú về `data/xanh24.db`: trong đợt này tôi chỉ mở file để **đọc** (đếm bảng `m4l_*`). SQLite có thể gộp file WAL còn sót khi đóng kết nối, làm đổi thời điểm sửa file, nhưng không đổi schema hay dữ liệu.

## Kết quả v4 trên bản sao dữ liệu thật (`mig4`)

| Bước | Lệnh | Kết quả |
|---|---|---|
| Trạng thái | `python server/m4l_migrations.py status` | Đã có [1, 2, 3]; đang chờ [4] |
| Nâng cấp | `python server/m4l_migrations.py migrate` | Sao lưu `xanh24-pre-m4l-v4-…db` rồi áp dụng v4. Thêm 6 bảng |
| Rollback | `python server/m4l_migrations.py downgrade --to 3 --yes` | Sao lưu `xanh24-pre-m4l-down-v3-…db` rồi gỡ 6 bảng v4 |
| Chạy lại | `migrate` | Áp dụng v4 lần nữa; trạng thái [1, 2, 3, 4] |

Số dòng bảng cũ và bảng M4L trước đó **giống hệt** sau nâng cấp, sau rollback và sau khi chạy lại:

| Bảng | Số dòng |
|---|---|
| `users` | 2 |
| `cms_accounts` | 7 |
| `pois` | 67 |
| `wards` | 51 |
| `devices` | 1 |
| `audit` | 2 |
| `events` | 16 |
| `m4l_cells` | 337.437 (= 337.035 ô Hà Nội + 402 ô Cầu Giấy) |
| `m4l_user_unlocks` | 4 |
| `m4l_moods` | 4 |

## Kiểm chứng lại lưới Hà Nội

Kiểm trên dữ liệu hiện tại theo yêu cầu FR-02:

| Khu vực | Mục | Số ô |
|---|---|---|
| `ha-noi` (city, grid v1, classification v1) | eligible | 200.444 |
| | pending_review | 114.784 |
| | excluded (mặt nước) | 18.974 |
| | restricted (quân sự) | 2.833 |
| | Tổng | **337.035** ô trên 126 phường/xã |
| `cau-giay` (pilot) | Giữ nguyên | 402 ô |

## Rollback

- **v4**: `downgrade --to 3 --yes` chỉ xóa 6 bảng thương mại. Mọi voucher, chiến dịch và sự kiện bị mất, nhưng luôn có bản sao lưu tạo trước khi gỡ.
- **v3**: xem `HANOI_SCALEUP.md`.
- **Postgres**: không có sao lưu tự động. Phải dùng công cụ của nhà cung cấp trước khi chạy CLI.

## Khi được duyệt chạy trên DB thật (đề xuất)

1. Dừng server.
2. `python server/m4l_migrations.py backup`, đồng thời sao lưu ngoài máy.
3. `XANH24_M4L_ENABLED=1 python server/m4l_migrations.py migrate`.
4. `status`; chạy test hồi quy và mở các route cũ.
5. Bật cờ trên server. **Không** chạy `seed_m4l_demo.py` (script cũng tự từ chối).
