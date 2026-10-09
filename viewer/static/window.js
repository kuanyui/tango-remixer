// The Clearlooks application window, shared by the icon viewer (viewer/static/index.html) and the website's
// homepage (homepage/template.html): DOM helpers, the menu bar with its menus, and the one tooltip of the page.
// A plain script for <head>; the page calls buildMenuBar() and installTooltips() once its body exists.
const $ = id => document.getElementById(id);

function el(tag, props, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

// --- Menu bar -------------------------------------------------------------------------------------------
// GNOME 2 behaviour: `_` in a label marks the underlined letter, as in GTK. A menu is rebuilt each time it opens,
// so its check items and disabled items always show the current state. Click opens a menu; while one is open,
// pointing at another title switches to it; Escape or a click elsewhere closes it.
// `menus` is [[label, () => items], ...]; an item is null (separator) or { label, run, icon?, accel?, disabled?,
// check? (a check item), radio? (a radio item) }. Item icons are theme paths under `iconBase`; a check item with
// an icon shows the icon in place of the check mark, drawn pressed while checked.
function mnemonic(label) {   // '_File' -> 'F' underlined, then 'ile'
  const k = label.indexOf('_');
  return k < 0 ? [label] : [label.slice(0, k), el('u', {}, label[k + 1]), label.slice(k + 2)];
}
let openTitle = null;
function buildMenu(items, iconBase, close) {   // the rows of a menu; `close` runs before a chosen item's action
  return el('div', { className: 'menu' }, ...items().map(item => {
    if (!item) return el('div', { className: 'menu-sep' });
    const slot = el('span', { className: 'slot' });
    if (item.icon) {
      slot.append(el('img', { src: `${iconBase}${item.icon}`, width: 16, height: 16, alt: '' }));
      if ('check' in item) slot.classList.toggle('on', !!item.check);
    } else if ('check' in item || 'radio' in item) {
      const mark = el('span', { className: 'check' in item ? 'check' : 'radio' });
      mark.dataset.state = (item.check ?? item.radio) ? 'checked' : 'unchecked';
      slot.append(mark);
    }
    const row = el('div', { className: item.disabled ? 'menu-item disabled' : 'menu-item' }, slot, el('span', {}, ...mnemonic(item.label)));
    if (item.accel) row.append(el('span', { className: 'accel' }, item.accel));
    if (!item.disabled) row.addEventListener('click', () => { close(); item.run(); });
    return row;
  }));
}
function openMenu(title, items, iconBase) {
  closeMenu();
  const menu = buildMenu(items, iconBase, closeMenu);
  menu.style.left = title.offsetLeft + 'px';
  title.classList.add('open');
  $('menubar').append(menu);
  openTitle = title;
}
function closeMenu() {
  if (!openTitle) return;
  openTitle.classList.remove('open');
  $('menubar').querySelector('.menu').remove();
  openTitle = null;
}
function buildMenuBar(menus, iconBase = 'icons/') {
  for (const [label, items] of menus) {
    const title = el('div', { className: 'menu-title' }, ...mnemonic(label));
    title.addEventListener('mousedown', e => { e.preventDefault(); openTitle === title ? closeMenu() : openMenu(title, items, iconBase); });
    title.addEventListener('mouseenter', () => { if (openTitle && openTitle !== title) openMenu(title, items, iconBase); });
    $('menubar').append(title);
  }
  document.addEventListener('mousedown', e => { if (openTitle && !e.target.closest('.menu, .menu-title')) closeMenu(); });   // titles toggle themselves
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeMenu(); });
}

// --- Context menu ---------------------------------------------------------------------------------------
// The same rows, at the pointer (a right click, or a long press on a phone), kept on screen; Escape or a
// click elsewhere closes it. `items` as for the menu bar.
let contextMenu = null;
function closeContextMenu() { if (contextMenu) { contextMenu.remove(); contextMenu = null; } }
function openContextMenu(items, x, y, iconBase = 'icons/') {
  closeContextMenu();
  contextMenu = buildMenu(items, iconBase, closeContextMenu);
  contextMenu.classList.add('context-menu');
  document.body.append(contextMenu);
  contextMenu.style.left = Math.max(0, Math.min(x, innerWidth - contextMenu.offsetWidth - 4)) + 'px';
  contextMenu.style.top = Math.max(0, Math.min(y, innerHeight - contextMenu.offsetHeight - 4)) + 'px';
}
document.addEventListener('mousedown', e => { if (contextMenu && !e.target.closest('.context-menu')) closeContextMenu(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeContextMenu(); });

// --- Tooltips ------------------------------------------------------------------------------------------
// One tooltip element for the whole page, styled by CSS, shown without delay. Every `title` in the page is
// shown through it instead of by the browser: on first hover the attribute moves to data-title, so the
// browser's own tooltip never appears (code that sets a new title later is picked up the same way). A page can
// add a card of its own: installTooltips({ selector, show }) hands it the targets matching `selector`.
let tip = null, tipTarget = null;
function placeTip(x, y) {   // top-left corner, kept on screen
  tip.style.left = Math.max(4, Math.min(x, innerWidth - tip.offsetWidth - 4)) + 'px';
  tip.style.top = Math.max(4, Math.min(y, innerHeight - tip.offsetHeight - 4)) + 'px';
}
function showTextTip(target, text, e) {
  tip.replaceChildren(text);
  tip.hidden = false;
  // GTK puts a tooltip under the pointer, centred on it; above the pointer when it would not fit below
  const below = e.clientY + 20;
  placeTip(e.clientX - tip.offsetWidth / 2, below + tip.offsetHeight <= innerHeight - 4 ? below : e.clientY - tip.offsetHeight - 8);
}
function hideTip() { tipTarget = null; if (tip) tip.hidden = true; }
function installTooltips(card) {
  tip = el('div', { className: 'tooltip', hidden: true });
  document.body.append(tip);
  const selector = card ? `[title], [data-title], ${card.selector}` : '[title], [data-title]';
  document.addEventListener('mouseover', e => {
    const target = e.target.closest(selector);
    if (!target || target === tipTarget) return;
    hideTip();
    tipTarget = target;
    if (card && target.matches(card.selector)) { card.show(target); return; }
    if (target.hasAttribute('title')) { target.dataset.title = target.getAttribute('title'); target.removeAttribute('title'); }
    if (target.dataset.title) showTextTip(target, target.dataset.title, e);
  });
  document.addEventListener('mouseout', e => { if (tipTarget && !tipTarget.contains(e.relatedTarget)) hideTip(); });
  document.addEventListener('mousedown', hideTip);
  document.addEventListener('keydown', hideTip);
  document.addEventListener('scroll', () => { if (!tip.hidden) hideTip(); }, true);   // any scrolling box; a card still loading is left alone
}
