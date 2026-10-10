// The Clearlooks application window, shared by the icon viewer (viewer/static/index.html) and the website's
// homepage (homepage/template.html): DOM helpers, the menu bar with its menus, the one tooltip of the page, the
// dark-background setting, and links for the bare URLs in a text.
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
// `menus` is [[label, () => items], ...]; an item is null (separator) or { label, run?, href?, icon?, accel?,
// disabled?, check? (a check item), radio? (a radio item) }. An item with `href` is a link (the panel's main menu);
// `run` runs once the menu has closed. An icon is a theme path under `iconBase`, or an element the caller made.
// A check item with an icon gives its menu two columns, marks then icons, every row keeping both so that the
// labels line up.
function mnemonic(label) {   // '_File' -> 'F' underlined, then 'ile'
  const k = label.indexOf('_');
  return k < 0 ? [label] : [label.slice(0, k), el('u', {}, label[k + 1]), label.slice(k + 2)];
}
let openTitle = null;
function buildMenu(items, iconBase, close) {   // the rows of a menu; `close` runs before a chosen item's action
  const rows = items();
  const twoColumns = rows.some(item => item && item.icon && ('check' in item || 'radio' in item));
  const slot = content => el('span', { className: 'slot' }, ...(content ? [content] : []));
  return el('div', { className: 'menu' }, ...rows.map(item => {
    if (!item) return el('div', { className: 'menu-sep' });
    let mark = null;
    if ('check' in item || 'radio' in item) {
      mark = el('span', { className: 'check' in item ? 'check' : 'radio' });
      mark.dataset.state = (item.check ?? item.radio) ? 'checked' : 'unchecked';
    }
    const icon = !item.icon ? null : item.icon instanceof Node ? item.icon : el('img', { src: `${iconBase}${item.icon}`, width: 16, height: 16, alt: '' });
    const slots = twoColumns ? [slot(mark), slot(icon)] : [slot(mark || icon)];
    const row = el(item.href ? 'a' : 'div', { className: item.disabled ? 'menu-item disabled' : 'menu-item', ...(item.href ? { href: item.href } : {}) },
      ...slots, el('span', {}, ...mnemonic(item.label)));
    if (item.accel) row.append(el('span', { className: 'accel' }, item.accel));
    if (!item.disabled && !item.href) row.addEventListener('click', () => { close(); item.run?.(); });   // a link navigates, which takes the menu with it
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

// --- Dark background ------------------------------------------------------------------------------------
// One setting for every page of the website and for the viewer served alone, kept in localStorage under a key of
// its own (the pages' other state is per page). setDark() paints the page and says so with a `darkchange` event
// on the document, so a control that shows the state (the viewer's check box) can follow a menu's toggle.
const DARK_KEY = 'tango-remixer-dark';
function isDark() { return document.body.classList.contains('dark'); }
function setDark(on) {
  document.body.classList.toggle('dark', on);
  try { localStorage.setItem(DARK_KEY, on ? '1' : '0'); } catch {}
  document.dispatchEvent(new CustomEvent('darkchange', { detail: on }));
}
function savedDark(fallback = false) {   // the choice kept, else `fallback` (a page's setting from before it was shared)
  try { const kept = localStorage.getItem(DARK_KEY); return kept === null ? fallback : kept === '1'; } catch { return fallback; }
}

// --- Links in plain text --------------------------------------------------------------------------------
// A bare URL in a piece of text becomes a link: README.md's prose on the homepage (GitHub links bare URLs,
// Python-Markdown does not) and the metadata an SVG carries (the viewer's file window). A trailing full stop,
// comma or unbalanced bracket is left out of the link, as GitHub leaves it. `blank`: open in a new tab (from a
// dialog, which a navigation would take down with the page).
const URL_IN_TEXT = /https?:\/\/[^\s<>"'`]+/g;
function linkify(text, blank = false) {   // the text as strings and <a> elements
  const parts = [];
  let last = 0;
  for (const m of text.matchAll(URL_IN_TEXT)) {
    let url = m[0];
    while (/[.,;:!?]$/.test(url) || (url.endsWith(')') && url.split('(').length < url.split(')').length) || (url.endsWith(']') && !url.includes('['))) url = url.slice(0, -1);
    parts.push(text.slice(last, m.index), el('a', { href: url, ...(blank ? { target: '_blank', rel: 'noopener' } : {}) }, url));
    last = m.index + url.length;
  }
  parts.push(text.slice(last));
  return parts.filter(part => part !== '');
}
function linkifyTree(root, blank = false) {   // every text node under `root`, but inside a link or code
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, node =>
    node.parentElement.closest('a, code, pre, script, style') ? NodeFilter.FILTER_REJECT : /https?:\/\//.test(node.data) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP);
  const nodes = [];
  for (let node = walker.nextNode(); node; node = walker.nextNode()) nodes.push(node);
  for (const node of nodes) node.replaceWith(...linkify(node.data, blank));
}

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
// llselect opens its lists as popovers, in the top layer, which no z-index reaches: the tooltip is a popover too,
// shown after them and so above them (a browser without popovers draws it through z-index as before).
function showTip() { tip.hidden = false; if (tip.popover && !tip.matches(':popover-open')) tip.showPopover(); }
function showTextTip(target, text, e) {
  tip.replaceChildren(text);
  showTip();
  // GTK puts a tooltip under the pointer, centred on it; above the pointer when it would not fit below
  const below = e.clientY + 20;
  placeTip(e.clientX - tip.offsetWidth / 2, below + tip.offsetHeight <= innerHeight - 4 ? below : e.clientY - tip.offsetHeight - 8);
}
function hideTip() { tipTarget = null; if (!tip) return; tip.hidden = true; if (tip.popover && tip.matches(':popover-open')) tip.hidePopover(); }
function installTooltips(card) {
  tip = el('div', { className: 'tooltip', hidden: true });
  if ('showPopover' in tip) tip.popover = 'manual';
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
