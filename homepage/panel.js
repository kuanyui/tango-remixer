// The panel's main menu: the windows and the launchers of the panel itself (homepage/panel.html), as a menu of
// window.js's kind under the button. Click opens it; a choice, Escape or a click elsewhere closes it.
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
    const entry = (link, label, slot) => el('a', { className: 'menu-item', href: link.href, role: 'menuitem' }, el('span', { className: 'slot' }, slot), el('span', {}, label));
    menu = el('div', { className: 'menu panel-menu', role: 'menu' },
      ...[...panel.querySelectorAll('.task')].map(link => entry(link, link.querySelector('span').textContent, link.querySelector('img').cloneNode())),
      el('div', { className: 'menu-sep' }),
      ...[...panel.querySelectorAll('.launcher')].map(link => entry(link, link.dataset.title || link.title, link.querySelector('.mark').cloneNode())));
    panel.append(menu);
    button.classList.add('open');
    button.setAttribute('aria-expanded', 'true');
  }
  button.addEventListener('mousedown', e => { e.preventDefault(); menu ? close() : open(); });
  document.addEventListener('mousedown', e => { if (menu && !e.target.closest('.panel-menu, #main-menu')) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
})();
