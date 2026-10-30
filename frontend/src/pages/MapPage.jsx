import { useEffect } from 'react';
import { MapShell } from '../features/map/components/MapShell';
import '../styles/map.css';

export default function MapPage() {
  useEffect(() => {
    // The existing controller owns the dynamic map, panel and kiosk workflows.
    void import('../features/map/controller/app.js');
  }, []);

  return <MapShell />;
}
