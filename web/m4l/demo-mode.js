// Hosted demo only (XANH24_DEMO_MODE=1): "[DEMO]" ribbon, one-click sign-in links and a per-tab staff session.
// /api/m4l/demo/info answers 404 everywhere else, so on a normal deployment this module does nothing.
export const STAFF_TOKEN = 'x24_demo_staff_token';

export const demoInfo = fetch('/api/m4l/demo/info').then(response => (response.ok ? response.json() : null)).catch(() => null);

// Partner and manager demo sessions live in sessionStorage so they never replace the visitor's own user session.
export function staffToken() {
  try { return sessionStorage.getItem(STAFF_TOKEN); } catch { return null; }
}
export function clearStaffToken() {
  try { sessionStorage.removeItem(STAFF_TOKEN); } catch { /* storage blocked */ }
}

demoInfo.then(info => {
  if (!info || document.querySelector('.demo-ribbon')) return;
  const ribbon = document.createElement('div');
  ribbon.className = 'demo-ribbon';
  ribbon.setAttribute('role', 'note');
  ribbon.innerHTML = `<span>${info.label}</span><a href="/demo">Về trang demo</a>`;
  document.body.prepend(ribbon);
});
