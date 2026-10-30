import { createRoot } from 'react-dom/client';
import App from './App';

const path = window.location.pathname;
if (path === '/admin' || path === '/admin/' || path === '/download' || path === '/download/') {
  const robots = document.createElement('meta');
  robots.name = 'robots';
  robots.content = path.startsWith('/download') ? 'noindex, nofollow' : 'noindex';
  document.head.append(robots);
}
if (path === '/admin' || path === '/admin/') document.title = 'Quản trị · Xanh24 - Maps for Life';
else if (path === '/download' || path === '/download/') document.title = 'Tải ứng dụng · Xanh24';
else if (path.startsWith('/go/')) document.title = 'Đặt xe · Xanh24 Maps for Life';

createRoot(document.getElementById('react-root')).render(<App />);
