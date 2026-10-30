import { lazy, Suspense } from 'react';

const MapPage = lazy(() => import('../pages/MapPage'));
const AdminPage = lazy(() => import('../pages/AdminPage'));
const DownloadPage = lazy(() => import('../pages/DownloadPage'));
const RidePage = lazy(() => import('../pages/RidePage'));

export function AppRoutes() {
  const path = window.location.pathname;
  let Page = MapPage;
  if (path === '/admin' || path === '/admin/') Page = AdminPage;
  else if (path === '/download' || path === '/download/') Page = DownloadPage;
  else if (path.startsWith('/go/')) Page = RidePage;

  return <Suspense fallback={null}><Page /></Suspense>;
}
