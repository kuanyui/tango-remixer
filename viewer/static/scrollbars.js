// Scrollbars drawn by the page, shared by the icon viewer and the homepage: the same Clearlooks bar in every
// browser (Firefox has no scrollbar parts to style, and Chrome's styled ones still differ). An element's own
// scrolling stays what it is (wheel, keys, touch, scrollTop); the bar beside it follows and drives it: a trough,
// a slider, a stepper button at each end. scrollbox(scroller) puts the scroller and its bar in a grid, the
// content first, then a 15 px column that is there only while the content overflows (GTK's bars take room, they
// do not float over the text); the native bar is hidden by CSS. installScrollbars() does it for every .scroller of
// the page. window.css lays the bar out, clearlooks.css paints it. A plain script for <head>, after window.js.
const SCROLL_STEP = 40;   // px a stepper scrolls: about three lines, as GTK's step increment

function scrollbox(scroller, boxClass = '') {   // the box, in the scroller's place (nothing happens to a detached scroller's place)
  const box = el('div', { className: `scrollbox ${boxClass}`.trim() });
  if (scroller.id) box.id = `${scroller.id}-box`;
  scroller.classList.add('scroller');
  if (scroller.parentNode) scroller.replaceWith(box);
  box.append(scroller, scrollbar(scroller));
  return box;
}

function installScrollbars(root = document) {   // every .scroller: a bar for one already in a box (the markup's), a box for the rest
  for (const scroller of root.querySelectorAll('.scroller')) {
    const box = scroller.parentElement;
    if (box?.classList.contains('scrollbox')) { if (!box.querySelector(':scope > .sbar')) box.append(scrollbar(scroller)); }
    else scrollbox(scroller, scroller.dataset.box || '');
  }
}

function scrollbar(scroller) {
  const slider = el('div', { className: 'slider' }), trough = el('div', { className: 'trough' }, slider);
  const up = el('button', { type: 'button', className: 'step up', tabIndex: -1, ariaLabel: 'Scroll up' });     // no title: no tooltip while scrolling
  const down = el('button', { type: 'button', className: 'step down', tabIndex: -1, ariaLabel: 'Scroll down' });
  const bar = el('div', { className: 'sbar', hidden: true }, up, trough, down);

  // The slider's length is the visible share of the content, its place the scrolled share of the rest.
  let size = 0;   // the slider's length, for the drag
  function update() {
    const { scrollTop, scrollHeight, clientHeight } = scroller;
    const needed = scrollHeight > clientHeight + 1;
    if (bar.hidden !== !needed) bar.hidden = !needed;   // written only when it changes: it is a relayout
    if (!needed) return;
    const room = trough.clientHeight, atStart = scrollTop <= 0, atEnd = scrollTop >= scrollHeight - clientHeight - 1;
    size = Math.min(room, Math.max(30, Math.round(room * clientHeight / scrollHeight)));   // GTK's min-slider-length
    // Touching a stepper, the slider grows a pixel over the stepper's border line, as GTK's junction does.
    const shown = size + (atStart ? 1 : 0) + (atEnd ? 1 : 0);
    slider.style.top = `${Math.round((room - size) * scrollTop / (scrollHeight - clientHeight)) - (atStart ? 1 : 0)}px`;
    slider.style.height = `${shown}px`;
    slider.style.setProperty('--grip-y', `${Math.floor(shown / 2) - 4}px`);   // the grip's rows (clearlooks.css): whole pixels keep its lines crisp
    up.disabled = atStart;   // a stepper with nothing further that way is insensitive, as GTK's
    down.disabled = atEnd;
  }
  scroller.addEventListener('scroll', update, { passive: true });
  // The content's height changes without a scroll event: when a child grows (an image loads, a list fills).
  // The scroller and each of its children are watched for size; the children anew whenever they change.
  const sizes = new ResizeObserver(update);
  const watch = () => { sizes.disconnect(); sizes.observe(scroller); for (const child of scroller.children) sizes.observe(child); update(); };
  new MutationObserver(watch).observe(scroller, { childList: true });
  watch();

  // Dragging the slider; a click on the trough pages towards the pointer; a stepper scrolls a step and repeats
  // while held, as GTK's do.
  let grab = null;   // where in the slider it was grabbed
  slider.addEventListener('pointerdown', e => {
    grab = e.clientY - slider.getBoundingClientRect().top;
    slider.setPointerCapture(e.pointerId);
    slider.classList.add('active');
    e.preventDefault();
  });
  slider.addEventListener('pointermove', e => {
    if (grab === null) return;
    const room = trough.clientHeight - size;
    const share = room > 0 ? Math.min(1, Math.max(0, (e.clientY - trough.getBoundingClientRect().top - grab) / room)) : 0;
    scroller.scrollTop = share * (scroller.scrollHeight - scroller.clientHeight);
  });
  for (const done of ['pointerup', 'pointercancel']) slider.addEventListener(done, () => { grab = null; slider.classList.remove('active'); });
  trough.addEventListener('pointerdown', e => {
    if (e.target !== trough) return;
    scroller.scrollBy({ top: (e.clientY < slider.getBoundingClientRect().top ? -0.9 : 0.9) * scroller.clientHeight });
  });
  for (const [button, direction] of [[up, -1], [down, 1]]) {
    let timer = null;
    const step = () => scroller.scrollBy({ top: direction * SCROLL_STEP });
    button.addEventListener('pointerdown', e => {
      step();
      timer = setTimeout(function again() { if (button.disabled) return; step(); timer = setTimeout(again, 50); }, 300);   // held: repeats until the end
      button.setPointerCapture(e.pointerId);
      e.preventDefault();   // no focus, no text selection
    });
    for (const done of ['pointerup', 'pointercancel']) button.addEventListener(done, () => clearTimeout(timer));
    document.addEventListener('pointerup', () => clearTimeout(timer));   // a button that went insensitive under the pointer gets no pointerup of its own
  }
  return bar;
}
