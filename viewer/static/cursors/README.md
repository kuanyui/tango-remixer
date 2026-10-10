# Mouse cursors: DMZ-White

`left_ptr.svg`, `hand2.svg` and `xterm.svg` are the arrow, the hand and the I-beam of DMZ-White, the cursor theme the
GNOME 2 desktops of Ubuntu, Debian and openSUSE showed next to Clearlooks. They are cut from `dmz.svg`, the theme's
master drawing in the Debian source package dmz-cursor-theme 0.4.5.3 (one sheet, a 24 x 24 slice per cursor): each
file is its slice's one group with the gradients it uses, the page set to the slice, 24 px wide and high, so a browser
draws it sharp at any pixel density. `left_ptr.png`, `hand2.png` and `xterm.png` are the theme's own 24 px renderings,
the fallback for a browser without SVG cursors. The hotspots in `cursors.css` are the theme's for 24 px (its `.in`
files): arrow 7,4; hand 9,5; I-beam 11,11.

Copyright 2007-2010 Novell, Inc., CC BY-SA 3.0 Unported: see LICENSE. The cut files are adaptations under the same
license. Both pages credit the theme in their About window.

They belong to the website and the viewer only. They are not part of the icon theme this project builds, and nothing
under `submodules/` or `dist/` includes them. Delete the `<link>` to `cursors.css` in a page for the browser's cursors.
