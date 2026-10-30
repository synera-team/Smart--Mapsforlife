import { useEffect } from 'react';
import '../styles/admin.css';

export default function AdminPage() {
  useEffect(() => {
    // The existing controller owns the authenticated dashboard below #root.
    void import('../features/admin/controller/admin.js');
  }, []);

  return <>
    <div id="root" />
    <div id="modal" className="modal" hidden>
      <div className="modal-back" data-close="" />
      <div className="modal-card" id="modalCard" />
    </div>
    <div id="toasts" className="toasts" />
  </>;
}
