# Xanh24 frontend

Frontend dùng React, JavaScript/JSX và Vite. Flask vẫn phục vụ API tại `/api/*`.

```bash
cd frontend
npm ci
npm run dev       # http://localhost:5173, proxy API sang Flask :8024
npm run build     # tạo frontend/dist
```

`index.html` là điểm vào chung. `src/routes/AppRoutes.jsx` chọn trang cho `/`, `/admin`, `/download` và `/go/<provider>`; Flask phục vụ cùng bản build tại các URL đó. `src/pages/` chứa các trang theo tuyến, `src/features/` chứa mã theo chức năng, `src/utils/` chứa tiện ích dùng chung, `src/styles/` chứa CSS và `public/` chứa tài nguyên tĩnh thuộc frontend. Các tài nguyên bản đồ, MapLibre và service worker vẫn dùng từ `web/` qua Flask để tránh nhân đôi dữ liệu và giữ đường dẫn hiện tại. Docker và Vercel tự build frontend.

`features/download/` và `features/ride/` quản lý giao diện, dữ liệu và sự kiện bằng React/JSX. Bản đồ và dashboard có React shell; bộ điều khiển hiện có nằm trong các thư mục `features/map/controller/` và `features/admin/controller/` để giữ các luồng kiosk, bản đồ, quản trị và API. Các tệp JS trong `web/` là bản cũ để dự phòng khi chưa build frontend. Những thư mục trong mẫu bài viết như `store/`, `context/` và `types/` chưa cần thiết cho mã hiện tại nên không được tạo rỗng.
