#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find and repair SVG constructs that Inkscape draws but browsers do not.

Both defects below are invisible inside Inkscape (and in the PNGs it exports),
because Inkscape is more tolerant than the SVG specification. Browsers, QtSvg
and other spec-following renderers silently drop the affected artwork. They
typically appear after icons were cut out of one big drawing sheet.

1. clippath-group   A `<g>` directly inside `<clipPath>`. Only shapes, text and
                    `<use>` are allowed there; a browser ignores the group, the
                    clip region becomes empty and everything clipped disappears.
                    Repair: unwrap the group (its `transform`, if any, moves
                    onto each child).

2. mask-region      `<mask maskUnits="userSpaceOnUse">` without x / y / width /
                    height. The default region is -10 % .. 110 % of the canvas,
                    measured in the user space of the element that uses the
                    mask. After cutting an icon out of a sheet, the artwork
                    still sits at its old sheet coordinates (a wrapper group
                    translates it back), so it falls outside that default
                    region and is masked away completely.
                    Repair: write the region explicitly - the canvas as seen
                    from the masked element (all ancestor transforms applied).
                    Masks whose default region already covers the canvas are
                    left alone.

Usage:
    python3 tools/fix_svg_for_browsers.py [--check] [PATH ...]

PATH may be SVG files or folders (searched recursively, symlinks skipped).
Default: the source folders of the built-in themes, exactly the ones the build
and the viewer read (so the big drawing sheets under `raw/` are not touched).
`--check` changes nothing and exits with status 1 when something needs repair.

The files are edited as text on purpose: re-serialising them through an XML
library would reformat every Inkscape-written file and bury the real change.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

Matrix = Tuple[float, float, float, float, float, float]
"""SVG affine matrix (a, b, c, d, e, f): x' = a*x + c*y + e, y' = b*x + d*y + f"""

_IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_SHAPES: str = r"rect|path|circle|ellipse|polygon|polyline|line|use|text"
_CLIPPATH_GROUP = re.compile(r"(<clipPath\b[^>]*>)\s*<g\b([^>]*)>(.*?)\s*</g>(\s*</clipPath>)", re.S)


def _multiply(p: Matrix, q: Matrix) -> Matrix:
    return (p[0] * q[0] + p[2] * q[1], p[1] * q[0] + p[3] * q[1],
            p[0] * q[2] + p[2] * q[3], p[1] * q[2] + p[3] * q[3],
            p[0] * q[4] + p[2] * q[5] + p[4], p[1] * q[4] + p[3] * q[5] + p[5])


def parse_transform(value: Optional[str]) -> Matrix:
    """The matrix of an SVG `transform` attribute (any list of translate / scale /
    rotate / skewX / skewY / matrix)."""
    m: Matrix = _IDENTITY
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", value or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if name == "translate":
            q: Matrix = (1.0, 0.0, 0.0, 1.0, v[0], v[1] if len(v) > 1 else 0.0)
        elif name == "scale":
            q = (v[0], 0.0, 0.0, v[1] if len(v) > 1 else v[0], 0.0, 0.0)
        elif name == "rotate":
            cs, sn = math.cos(math.radians(v[0])), math.sin(math.radians(v[0]))
            cx, cy = (v[1], v[2]) if len(v) == 3 else (0.0, 0.0)
            q = (cs, sn, -sn, cs, cx - cs * cx + sn * cy, cy - sn * cx - cs * cy)
        elif name == "skewX":
            q = (1.0, 0.0, math.tan(math.radians(v[0])), 1.0, 0.0, 0.0)
        elif name == "skewY":
            q = (1.0, math.tan(math.radians(v[0])), 0.0, 1.0, 0.0, 0.0)
        elif name == "matrix":
            q = (v[0], v[1], v[2], v[3], v[4], v[5])
        else:
            raise ValueError(f"unsupported transform function `{name}`")
        m = _multiply(m, q)
    return m


def _attribute(tag: str, name: str) -> Optional[str]:
    found = re.search(r"\b" + re.escape(name) + r'="([^"]*)"', tag)
    return found.group(1) if found else None


def _canvas(src: str) -> Tuple[float, float, float, float]:
    """(x, y, width, height) of the canvas in root user units: the viewBox when
    there is one, else 0 0 width height."""
    root = re.search(r"<svg\b[^>]*>", src, re.S)
    if root is None:
        raise ValueError("no <svg> element")
    view_box = _attribute(root.group(0), "viewBox")
    if view_box:
        x, y, w, h = (float(n) for n in re.split(r"[\s,]+", view_box.strip()))
        return x, y, w, h
    size = [re.match(r"[\d.]+", _attribute(root.group(0), a) or "") for a in ("width", "height")]
    if not all(size):
        raise ValueError("<svg> has neither a viewBox nor a numeric width/height")
    return 0.0, 0.0, float(size[0].group(0)), float(size[1].group(0))   # type: ignore[union-attr]


def fix_clippath_groups(src: str) -> Tuple[str, List[str]]:
    """Unwrap a `<g>` that is the direct child of a `<clipPath>`."""
    notes: List[str] = []

    def unwrap(m: "re.Match[str]") -> str:
        head, group_attrs, body, tail = m.groups()
        if "<g" in body:
            raise ValueError("nested groups inside <clipPath>: repair by hand")
        group_transform = _attribute(group_attrs, "transform")
        if group_transform:   # the group's transform goes in front of each child's own
            def fold(child: "re.Match[str]") -> str:
                tag, attrs, close = child.groups()
                own = re.search(r'\btransform="([^"]*)"', attrs)
                if own:
                    attrs = attrs.replace(own.group(0), f'transform="{group_transform} {own.group(1)}"')
                else:
                    attrs = attrs.rstrip() + f'\n           transform="{group_transform}"'
                return f"<{tag}{attrs}{close}>"
            body = re.sub(rf"<({_SHAPES})\b([^>]*?)(\s*/?)>", fold, body)
        body = "\n".join(line[2:] if line.startswith("  ") else line for line in body.split("\n"))   # one level less
        notes.append(f"clippath-group: unwrapped <g> inside {_attribute(head, 'id')}"
                     + (f" (moved its transform `{group_transform}` onto the children)" if group_transform else ""))
        return head + body + tail

    return _CLIPPATH_GROUP.sub(unwrap, src), notes


def fix_mask_regions(src: str) -> Tuple[str, List[str]]:
    """Give harmful userSpaceOnUse masks an explicit region (see module docstring)."""
    notes: List[str] = []
    cx, cy, cw, ch = _canvas(src)
    for mask in list(re.finditer(r"<mask\b([^>]*)>", src)):
        attrs = mask.group(1)
        if _attribute(attrs, "maskUnits") != "userSpaceOnUse" or re.search(r'\b(x|y|width|height)="', attrs):
            continue
        mask_id = _attribute(attrs, "id")
        users = list(re.finditer(r'(?:mask="url\(#' + re.escape(mask_id or "") + r'\)"|mask:\s*url\(#'
                                 + re.escape(mask_id or "") + r"\))", src))
        corners: List[Tuple[float, float]] = []
        for user in users:   # a shared mask must cover the canvas as seen from every element using it
            start = src.rfind("<", 0, user.start())
            end = src.index(">", user.start())
            ancestors: List[Optional[str]] = []
            for g in re.finditer(r"<g\b[^>]*>|</g>", src[:start]):
                if g.group(0) == "</g>":
                    ancestors.pop()
                elif not g.group(0).endswith("/>"):
                    ancestors.append(_attribute(g.group(0), "transform"))
            ctm: Matrix = _IDENTITY
            for transform in ancestors + [_attribute(src[start:end + 1], "transform")]:
                ctm = _multiply(ctm, parse_transform(transform))
            a, b, c, d, e, f = ctm
            det = a * d - b * c
            to_local: Callable[[float, float], Tuple[float, float]] = (
                lambda X, Y: ((d * (X - e) - c * (Y - f)) / det, (-b * (X - e) + a * (Y - f)) / det))
            corners += [to_local(X, Y) for X in (cx, cx + cw) for Y in (cy, cy + ch)]
        if not corners:
            continue   # defined but never used
        x, y = min(p[0] for p in corners), min(p[1] for p in corners)
        w, h = max(p[0] for p in corners) - x, max(p[1] for p in corners) - y
        eps = 1e-6
        if x >= -0.1 * cw - eps and y >= -0.1 * ch - eps and x + w <= 1.1 * cw + eps and y + h <= 1.1 * ch + eps:
            continue   # the default region already covers the canvas: harmless
        new_tag = mask.group(0)[:-1].rstrip() + f'\n       x="{x:g}"\n       y="{y:g}"\n       width="{w:g}"\n       height="{h:g}">'
        src = src.replace(mask.group(0), new_tag, 1)
        notes.append(f'mask-region: {mask_id} now has x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}"')
    return src, notes


def fix(src: str) -> Tuple[str, List[str]]:
    """Apply every repair to one SVG document. Returns (new text, what was done)."""
    src, notes = fix_clippath_groups(src)
    src, more = fix_mask_regions(src)
    return src, notes + more


def svg_files(paths: List[Path]) -> List[Path]:
    """Real `.svg` files below the given files / folders. os.walk instead of rglob + stat: one directory
    listing per folder matters on slow mounts (virtiofs, /mnt/c)."""
    found: List[Path] = []
    for path in paths:
        if not path.is_dir():
            found.append(path)
            continue
        for folder, _dirs, names in os.walk(path):
            found += [Path(folder, n) for n in names if n.endswith(".svg") and not os.path.islink(os.path.join(folder, n))]
    return sorted(found)


def built_in_theme_folders() -> List[Path]:
    """Source folders of the built-in themes, from build_icons.py's registry."""
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    # build_icons.py parses CLI args at import time -> spoof argv first (same trick as the tests and the viewer).
    saved_argv, sys.argv = sys.argv, [sys.argv[0], "--included-icon-file", str(root / "_dummy_not_used.txt")]
    try:
        from build_icons import BUILT_IN_RAW_ICON_THEMES_PATH
    finally:
        sys.argv = saved_argv
    return [theme.copied_src_theme_folder for theme in BUILT_IN_RAW_ICON_THEMES_PATH if theme.copied_src_theme_folder.is_dir()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--check", action="store_true", help="report only; exit 1 when something needs repair")
    parser.add_argument("paths", nargs="*", type=Path, help="SVG files or folders (default: the built-in themes' source folders)")
    args = parser.parse_args(argv)
    paths: List[Path] = args.paths or built_in_theme_folders()
    affected = 0
    for file in svg_files(paths):
        text = file.read_text(encoding="utf-8", errors="surrogateescape")
        if "<mask" not in text and "<clipPath" not in text:
            continue
        try:
            new_text, notes = fix(text)
        except ValueError as e:
            print(f"{file}: SKIPPED, {e}", file=sys.stderr)
            continue
        if not notes:
            continue
        affected += 1
        print(f"{file}")
        for note in notes:
            print(f"    {note}")
        if not args.check:
            with open(file, "w", encoding="utf-8", errors="surrogateescape", newline="") as out:
                out.write(new_text)
    print(f"{affected} file(s) {'need repair' if args.check else 'repaired'}.")
    return 1 if args.check and affected else 0


if __name__ == "__main__":
    sys.exit(main())
