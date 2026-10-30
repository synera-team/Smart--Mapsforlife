# M4L 2.0: bản demo trên Internet (staging)

Mục đích: tạo một link HTTPS để lãnh đạo mở trên điện thoại hoặc máy tính, không cần cài đặt gì. Bản demo **không** phải production. Nó chạy trên CSDL demo riêng, dựng từ dữ liệu mẫu trong repo (không dùng `data/xanh24.db`), và không có thanh toán.

## Vì sao chọn Fly.io, không dùng Vercel

| Tiêu chí | Vercel (cấu hình hiện có) | Fly.io (đề xuất) |
|---|---|---|
| Ghi dữ liệu SQLite | Không ổn định: máy chủ dạng serverless, ổ đĩa tạm (`/tmp`) mất khi hàm khởi động lại; mỗi phiên bản có bản sao riêng | Có ổ đĩa bền (volume 1 GB) gắn vào một máy chủ cố định |
| Lưới Hà Nội (337.437 ô, CSDL ~52 MB) | Phải dựng lại sau mỗi lần khởi động nguội, hoặc chuyển sang Postgres (luồng M4L chưa được kiểm thử trên Postgres) | Dựng một lần lúc khởi động đầu tiên (~10 giây), sau đó giữ nguyên |
| Voucher, chiến dịch, đếm ngược (cần ghi và khóa giao dịch) | Rủi ro mất dữ liệu giữa các lượt gọi | Ổn định: một máy, SQLite chế độ WAL |
| HTTPS | Có | Có (`https://<tên-app>.fly.dev`, tự cấp chứng chỉ) |
| Triển khai từ máy, không cần đẩy code lên GitHub | Có | Có (`fly deploy` gửi trực tiếp thư mục code) |

Phương án khác dùng được: Railway (có volume, khoảng 5 USD/tháng) hoặc Render (gói Starter kèm ổ đĩa, khoảng 7 USD/tháng, cần kết nối repo GitHub).

## Cấu hình

- `deploy/demo/Dockerfile`: dùng cùng mã nguồn với `Dockerfile` gốc, bật sẵn `XANH24_M4L_ENABLED=1` và `XANH24_DEMO_MODE=1`, CSDL đặt tại `/data/xanh24.db`.
- `deploy/demo/entrypoint.sh`: lần khởi động đầu tiên tạo schema, nạp dữ liệu mẫu, chạy migration M4L v1–v4, seed dữ liệu `[DEMO]` rồi lưu bản gốc `demo-template.db`. Các lần sau chỉ khởi động server.
- `deploy/demo/fly.toml`: 1 máy `shared-cpu-1x` 512 MB tại Singapore (`sin`, gần Việt Nam), volume 1 GB, luôn bật (không tắt khi không có người dùng), kiểm tra sức khỏe qua `/api/health`.
- `.dockerignore`: loại `data/`, mọi file `*.db`, `secret.key`, file mật khẩu, `.venv`, `tools/`, `tests/`, `docs/` khỏi image.

## Triển khai (cần bạn xác nhận vì có phát sinh chi phí)

```powershell
iwr https://fly.io/install.ps1 -useb | iex        # 1. cài flyctl
fly auth login                                    # 2. đăng nhập (mở trình duyệt; Fly yêu cầu thẻ thanh toán)
powershell -ExecutionPolicy Bypass -File deploy\demo\deploy-fly.ps1   # 3. tạo app + volume + deploy
```

Link sau khi deploy: `https://xanh24-m4l-demo.fly.dev/demo`. Nếu tên app đã có người dùng, chạy lại với `-App <tên-khác>`.

## Vận hành

| Việc | Lệnh |
|---|---|
| Xem log | `fly logs -a xanh24-m4l-demo` |
| Đặt lại dữ liệu demo (xóa khách, voucher, chiến dịch phát sinh; giữ dữ liệu seed) | `fly ssh console -a xanh24-m4l-demo -C "python server/m4l_demo.py reset"` |
| Xem tài khoản demo có mật khẩu (chỉ khi cần đăng nhập bằng form) | `fly ssh console -a xanh24-m4l-demo -C "cat /data/M4L_DEMO_ACCOUNTS.txt"` |
| Tạm tắt (không mất dữ liệu) | `fly scale count 0 -a xanh24-m4l-demo` (bật lại: `fly scale count 1`) |
| Xóa hẳn (xóa cả dữ liệu demo) | `fly apps destroy xanh24-m4l-demo` |

## Chi phí ước tính

| Hạng mục | Ước tính/tháng |
|---|---|
| 1 máy shared-cpu-1x, 512 MB, chạy liên tục | khoảng 3–4 USD |
| Volume 1 GB | khoảng 0,15 USD |
| Băng thông ra | không đáng kể với lượng truy cập demo |
| **Tổng** | **khoảng 4–5 USD/tháng (≈ 100.000–130.000 đ)** |

Đơn giá có thể thay đổi; kiểm tra lại tại fly.io/pricing trước khi xác nhận. Tắt máy khi không demo (`fly scale count 0`) thì gần như chỉ còn phí volume.

## An toàn

- Phiên "một chạm" chỉ cấp vai trò khách (tài khoản tạm riêng cho từng lần nhấn), đối tác demo và quản lý khu vực demo. Không bao giờ cấp quản trị hệ thống (S0).
- Mỗi mạng được tạo tối đa 30 phiên khách mỗi giờ; tổng số tối đa 2.000 khách, sau đó cần đặt lại dữ liệu.
- Mọi trang có `noindex`; dải vàng “[DEMO] – Dữ liệu minh họa” hiển thị ở đầu mỗi trang M4L.
- Ai có link đều vào được bản demo. Đây là chủ đích, để lãnh đạo không phải đăng nhập. Dữ liệu chỉ là dữ liệu minh họa và đặt lại được.
