# Mở rộng Fog of War & Mystery Pins ra toàn Hà Nội

Thay đổi theo change request “Mở rộng Fog of War và Mystery Pins trên toàn thành phố Hà Nội”. Số liệu chi tiết từng phường/xã: [`HANOI_GRID_REPORT.md`](HANOI_GRID_REPORT.md) (sinh tự động).

## 1. Audit: vì sao hệ thống trước đây chỉ có Cầu Giấy

| Nguyên nhân | Vị trí |
|---|---|
| Khu vực khám phá được sinh **từ bảng `wards`** của Xanh24 — chỉ có 51 đơn vị (50 phường + 1 xã), tổng **468 km²** trên ~3.359 km² của Hà Nội. 75 xã ngoại thành không có ranh giới | `server/m4l_exploration.py` (`build_grid`), bảng `wards` |
| Migration v2 chỉ tạo một khu `cau-giay`; cấu hình `pilot_area="cau-giay"` là khu mặc định | `server/m4l_migrations.py`, `DEFAULT_CONFIG` |
| API `/api/m4l/exploration` trả **toàn bộ** danh sách ô của khu vực — chạy được với 402 ô, không chạy được với ~337 nghìn ô | `server/m4l.py` (bản Phase 2) |
| Mọi ô trong ranh giới đều bị coi là “eligible” — không phân biệt mặt nước, khu hạn chế, nơi chưa rõ có đường | `build_grid` |
| Giao diện vẽ cả lưới một lần, bản đồ khóa theo bbox khu vực | `web/m4l/world.js` (bản Phase 2) |

## 2. Kiến trúc

### 2.1 Dữ liệu địa lý (dựng offline, không tải mạng lúc chạy)

```
tools/m4l_grid/fetch.py   → OSM qua Overpass (cache .cache/, không commit)
tools/m4l_grid/build.py   → server/m4l_data/hanoi_grid_v1.json.gz  +  docs/m4l/HANOI_GRID_REPORT.md
migration v3              → nạp tệp vào bảng m4l_* (một lần, có sao lưu)
```

- Ranh giới thành phố: OSM relation **1903516** (admin_level=4). Ranh giới thành phố không đổi trong đợt sắp xếp 2025.
- Phường/xã: **126** relation admin_level=6 (51 phường + 75 xã) theo sắp xếp hiệu lực 01/07/2025; slug khớp 51/51 mã phường hiện có của Xanh24 → quyền theo phường của tài khoản CONTENT dùng lại được.
- Hệ tọa độ WGS84 (EPSG:4326). Giấy phép **ODbL** — phải ghi “© OpenStreetMap contributors”; nếu công bố CSDL phái sinh ra ngoài phải theo ODbL (xem OPEN_DECISIONS C2).
- Đây là dữ liệu cộng đồng, **chưa phải bản đồ pháp lý** (C1).

### 2.2 Lưới: giữ lưới vuông, không chuyển H3

| Tiêu chí | Lưới vuông hiện có | H3 (res 10 ≈ 66 m cạnh, ~0,015 km²) |
|---|---|---|
| Ổn định mã ô | `gx:gy` cố định theo (kích thước, vĩ độ tham chiếu); không phụ thuộc thư viện | Ổn định theo chuẩn H3 |
| Tương thích dữ liệu cũ | **Trùng khớp 100 %** với 402 ô Cầu Giấy → chuyển tiến độ không cần quy đổi | Phải quy đổi ô vuông → lục giác (gần đúng) — trái yêu cầu “không reset nếu chưa có quy đổi tin cậy” |
| Phụ thuộc | Không | `h3` (Python) + `h3-js` (thêm thư viện vào frontend offline) |
| Méo theo vĩ độ | Trong phạm vi Hà Nội (20,5°–21,4°) diện tích ô lệch < 1,5 % | Gần đều |
| Truy vấn khung nhìn | Dải `gx/gy` dùng chỉ mục B-tree | Cần `polygonToCells` |

Kết luận: giữ lưới vuông 100 m, vĩ độ tham chiếu 21,0. Toán lưới nằm duy nhất ở `server/m4l_grid.py`, dùng chung cho server và công cụ dựng (đã kiểm chéo scanline với point-in-polygon trên 4 phường: khớp tuyệt đối).

### 2.3 Phân loại ô

| Trạng thái | Quy tắc (theo thứ tự ưu tiên) | Mở khóa | Tính vào mẫu số |
|---|---|---|---|
| `restricted` | Tâm ô trong `landuse=military` hoặc vùng hạn chế do S0 khai báo (bắt buộc có nguồn) | Không | Không |
| `excluded` | Tâm ô trong mặt nước (`natural=water`, `waterway=riverbank`) hoặc vùng loại trừ do S0 khai báo | Không | Không |
| `eligible` | Có đường/lối đi công cộng OSM đi qua ô (không tính cao tốc, `access=private/no`) | Có | **Có** |
| `pending_review` | Còn lại — chưa có dữ liệu đường | Có (đến thật bằng GPS là bằng chứng) | Không; báo riêng |

`base_status` giữ phân loại gốc; vùng do quản trị khai báo áp lên trên và gỡ được. Mỗi lần đổi: `classification_version + 1`, ghi `m4l_grid_changes` (trước/sau) và `audit`.

### 2.4 Mô hình dữ liệu (migration v3, chỉ thêm)

- `m4l_areas` + `kind` (`city`/`pilot`), `classification_version`.
- `m4l_cells` + `status`, `base_status`, `unit_slug`; chỉ mục `(area_id, grid_version, gy, gx)` cho truy vấn khung nhìn và `(area_id, grid_version, unit_slug, status)` cho thống kê.
- Bảng mới: `m4l_units` (126 phường/xã), `m4l_area_sources` (ranh giới hiển thị + metadata nguồn), `m4l_zones`, `m4l_grid_changes`.
- Không đổi bảng ngoài M4L.

### 2.5 API (mở rộng endpoint cũ, không tạo trùng)

| Endpoint | Thay đổi |
|---|---|
| `GET /api/m4l/exploration` | Thêm `bbox`, `level=auto|cells|blocks`. Không có bbox ở khu lớn → khối 1 km (~3.600 khối, ~86 KB). `level=cells` chỉ khi khung nhìn ≤ 8.000 ô, ngược lại 400 `VIEWPORT_TOO_LARGE`. Ô trả dạng gọn `[gx, gy, mã trạng thái]` |
| `GET /api/m4l/exploration/progress` | Thêm `unlocked_pending`, `pending_review`, `excluded`, `restricted`, `complete`, `classification_version`; `?breakdown=unit` → theo phường/xã |
| `POST /api/m4l/exploration/unlock` | Mặc định khu Hà Nội; ô `excluded/restricted` → 422 `CELL_NOT_COUNTED`; ghi đồng thời cho pilot nếu ô nằm trong pilot |
| `GET /api/m4l/mystery-pins` | Thêm `bbox` |
| **Mới** `GET /api/m4l/areas`, `GET /api/m4l/areas/{slug}/boundary` | Danh sách khu, ranh giới + nguồn/giấy phép |
| **Mới (admin)** `GET /api/m4l/admin/areas/{id}/stats`, `…/changes`, `POST /api/m4l/admin/inspect`, `GET/POST /api/m4l/admin/zones`, `PUT /api/m4l/admin/zones/{id}` | Thống kê, nhật ký lưới, tra tọa độ, vùng hạn chế |

### 2.6 Hiệu năng

- Tổng hợp theo trạng thái / phường / khối được tính một lần cho mỗi (khu, phiên bản lưới, phiên bản phân loại), nạp sẵn lúc khởi động.
- Đo trên SQLite, máy phát triển (test `tests/test_m4l_hanoi.py`): khung nhìn ~400 ô **~7 ms**; tổng quan khối 1 km ~1,3 s nếu chưa nạp sẵn, sau đó lấy từ bộ nhớ.
- Migration v3 nạp ~337 nghìn ô trong vài giây (executemany trong một giao dịch). DB tăng khoảng 25–35 MB.
- Frontend: dưới zoom 14 chỉ vẽ khối; từ zoom 14 vẽ ô của khung nhìn; yêu cầu mới hủy yêu cầu cũ (debounce 250 ms).

**SQLite có đủ không?** Với tải pilot (đọc theo chỉ mục, ghi một dòng mỗi lần mở khóa, WAL) là đủ. Cân nhắc PostgreSQL/PostGIS khi: nhiều worker ghi đồng thời liên tục, cần truy vấn không gian tùy ý (vùng hạn chế phức tạp, bán kính), hoặc chạy trên Vercel. **Không tự chuyển DB** — xem OPEN_DECISIONS C6. Lưu ý: trên Postgres (Vercel), migration v3 nên chạy bằng CLI trước, không để chạy lúc cold-start.

## 3. Migration v2 → v3 và rollback

1. Tự sao lưu SQLite (`data/backups/<db>-pre-m4l-v3-*.db`, kiểm `integrity_check`).
2. Thêm cột/chỉ mục/bảng (kiểm tra tồn tại trước → chạy lặp an toàn; sổ `m4l_migrations` chặn chạy lại).
3. Gán `unit_slug` cho 402 ô Cầu Giấy (không đổi trạng thái, không xóa ô).
4. Nạp lưới Hà Nội từ `server/m4l_data/hanoi_grid_v1.json.gz`.
5. **Chuyển tiến độ**: mọi ô đã mở ở pilot cùng kích thước ô + vĩ độ tham chiếu được chép sang khu Hà Nội (`validation_method='migrated:cau-giay'`); bản ghi pilot giữ nguyên.
6. Ghi báo cáo `data/backups/m4l-v3-report-*.json` (số ô, số ô chuyển, nguồn dữ liệu).

Rollback: `python server/m4l_migrations.py downgrade --to 2 --yes` — sao lưu trước, gỡ khu Hà Nội cùng ô/tiến độ/ghim thuộc khu đó và các bảng/cột v3; dữ liệu pilot giữ nguyên. Muốn giữ tiến độ toàn thành phố đã phát sinh thì **khôi phục từ bản sao lưu** thay vì downgrade.

Dựng lại dữ liệu khi OSM thay đổi: chạy `fetch.py --roads` + `build.py` → tệp `hanoi_grid_v2…` + migration mới tăng `grid_version` (không ghi đè v1 đã phát hành).

## 4. Kiểm chứng

```
python tools/m4l_grid/fetch.py --roads      # tải OSM (cache)
python tools/m4l_grid/build.py              # dựng dữ liệu + báo cáo
python tests/test_m4l_hanoi.py              # 64 kiểm thử phạm vi Hà Nội
python tests/test_m4l.py && python tests/test_m4l_phase2.py
```

Kiểm chứng phạm vi: số ô × 0,01 km² so với diện tích ranh giới OSM và số liệu công bố (xem báo cáo); 126/126 đơn vị có ô; công cụ `/m4l/admin` → “Tọa độ này thuộc ô nào?”.
