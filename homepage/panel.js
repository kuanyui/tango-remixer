// The panel's main menu: the windows and the launchers of the panel itself (homepage/panel.html) as links, and the
// Dark Background switch (window.js's setting, shared by both windows), as a menu of window.js's kind under the
// button. Click opens it; a choice, Escape or a click elsewhere closes it.
(() => {
  const panel = $('panel'), button = $('main-menu');
  let menu = null;
  function close() {
    if (!menu) return;
    menu.remove();
    menu = null;
    button.classList.remove('open');
    button.setAttribute('aria-expanded', 'false');
  }
  function open() {
    const link = (a, label, icon) => ({ label, href: a.href, icon: icon.cloneNode() });
    menu = buildMenu(() => [
      ...[...panel.querySelectorAll('.task')].map(a => link(a, a.querySelector('span').textContent, a.querySelector('img'))),
      null,
      ...[...panel.querySelectorAll('.launcher')].map(a => link(a, a.dataset.title || a.title, a.querySelector('.mark'))),
      null,
      { label: 'Dark Background', icon: 'Tango/16x16/status/weather-clear-night.svg', check: isDark(), run: () => setDark(!isDark()) },
    ], `${panel.dataset.root}viewer/icons/`, close);
    menu.classList.add('panel-menu');
    menu.setAttribute('role', 'menu');
    panel.append(menu);
    button.classList.add('open');
    button.setAttribute('aria-expanded', 'true');
  }
  button.addEventListener('mousedown', e => { e.preventDefault(); menu ? close() : open(); });
  document.addEventListener('mousedown', e => { if (menu && !e.target.closest('.panel-menu, #main-menu')) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
})();
