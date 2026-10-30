// Add the public account entry point to the React map served by Flask.
function addMapLogin() {
  const actions = document.querySelector('.topbar-right');
  if (!actions || actions.querySelector('.top-bar-login')) return;
  const link = document.createElement('a');
  link.className = 'top-bar-login';
  link.href = '/cms/login';
  link.textContent = 'Đăng nhập/ Đăng ký';
  actions.append(link);
}

addMapLogin();
const mapLoginObserver = new MutationObserver(addMapLogin);
mapLoginObserver.observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener('pagehide', () => mapLoginObserver.disconnect());
