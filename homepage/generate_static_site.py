#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the project website as plain files (no server), the way GitHub Pages
and GitLab Pages publish it:

    index.html, <id>.html,    the homepage: README.md rendered into template.html, one page per
    lsp.html, lsp-<id>.html,  top-level heading, as a Clearlooks window (viewer/static/window.*,
    style.css                 clearlooks.css) with a Contents sidebar; lsp/README.md the same, its
                              sections under an "LSP server" row of the Contents (DOCUMENTS); every
                              page has an icon (SECTION_ICONS: Tango where it has it, else Nome)
    panel.css, panel.js,      the GNOME 2 panel above both windows (panel.html: main menu, launchers
    marks/                    with the GitHub / GitLab marks, window list, the build in the clock slot)
    tango-mixer-banner.svg    (and any other image README.md shows)
    viewer/                   the icon viewer (viewer/) as a static site: its page and
                              assets, api/index.json, and every indexed SVG under
                              icons/<theme>/<path>, the Blue* themes colorized with
                              the same code the build uses

Run:  python3 homepage/generate_static_site.py [OUT] [--serve [PORT]]     (default: homepage/_build/)
      make homepage-build        the same
      make homepage-dev-server   the same, then --serve: OUT served on PORT (8000 by default) on every interface, as
                                 the viewer is, the URLs to open printed, this machine's LAN addresses among them;
                                 a change to README.md, homepage/, viewer/static/ or lib/color_converter.py
                                 rebuilds the site while it is served (reload the page); a change to the
                                 Python code it is made with restarts the server
Needs Python-Markdown (the `markdown` module) and, for coloured code blocks, Pygments:
`apt install python3-markdown python3-pygments` on Debian / Ubuntu, else
`pip install markdown pygments`. (`markdown2` is a different library.)

The viewer part writes only the real files of the index (an alias is a symlink
name listed with its icon; the page never requests it), so a theme weighs what
its source SVGs weigh, and a Blue* theme is a second copy of its base theme. A
rerun rewrites only the icons whose source (or the colorizer) changed, so a
preview round trip takes seconds. Instead of a folder on some machine, each theme
gets the URL of its folder in the submodule's repository at the checked-out
commit (and the repository's home page and the commit), where the page links
every file; no local path is written.

Links in README.md to files of this repository point at their page in the
repository the site is built from: told by the CI of GitLab or GitHub, else the
origin remote of the checkout.

What README.md shows only to a reader of the repository (its table of contents,
the tip that sends them here) sits between a `<!-- homepage-hide-begin -->` line
and a `<!-- homepage-hide-end -->` line, and the homepage leaves it out (_HIDDEN).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Set, Tuple, Union

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from lib.included_icons_tokens import tokenize  # noqa: E402
from viewer.server import _COLOR_CONVERTER, _STATIC_DIR, Colorizer, SourceTheme, build_index, index_json, local_urls, source_themes  # noqa: E402

_HOMEPAGE_DIR: Path = Path(__file__).resolve().parent
_ALERTS: Tuple[str, ...] = ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION")
"""GitHub's `> [!NOTE]` blockquote kinds."""
_HIDDEN = re.compile(r"^<!-- homepage-hide-begin -->[ \t]*\n.*?^<!-- homepage-hide-end -->[ \t]*(?:\n|\Z)", re.M | re.S)
"""What a document shows on GitHub and GitLab but not on the homepage: from a `<!-- homepage-hide-begin -->` line to
a `<!-- homepage-hide-end -->` line, each comment on a line of its own."""


class Rendered(NamedTuple):
    """A document as HTML, and its top-level headings (Python-Markdown's toc tokens: id, name, children, ...; a
    token's children are its second-level headings)."""
    html: str
    headings: List[Dict[str, object]]


class Document(NamedTuple):
    """A Markdown file of the repository, shown as pages of the site."""
    path: str
    """relative to the repository root"""
    prefix: str
    """what its pages' files are named after: "" for README.md (index.html and <id>.html), else <prefix>.html for
    the document's own page and <prefix>-<id>.html for its sections (lsp.html, lsp-install.html)"""
    level: int
    """the heading level a page starts at: 1 for README.md (a page per top-level heading); 2 for a document with
    one top-level heading, which heads the document's own page, its second-level sections pages under it"""
    group: Optional[str]
    """None: its pages at the top of the Contents. A name: the document's own page is a row of that name, its
    sections rows under it."""


DOCUMENTS: Tuple[Document, ...] = (
    Document("README.md", "", 1, None),
    Document("lsp/README.md", "lsp", 2, "LSP server"),
)
"""The documents of the site, in the order the Contents list them. One missing from a checkout is left out."""


class Section(NamedTuple):
    """One page of the site: a heading of a document with everything under it."""
    doc: Document
    id: str
    title: str
    """plain text, the heading's"""
    label: str
    """in the Contents and the pager: the title, or the document's group name for the document's own page"""
    file: str
    """"./" for README.md's first page (written as index.html), <id>.html for its others; <prefix>.html and
    <prefix>-<id>.html for another document's"""
    key: str
    """SECTION_ICONS' key: the heading id for README.md's pages, the file's stem for another document's"""
    html: str
    """the heading and what follows it; a first page also carries what comes before the heading (the banner)"""
    child: bool
    """a section of a document with a group: a row under the document's own in the Contents"""


THEMES: Tuple[str, ...] = ("Tango", "Nome", "BlueHumanity")
"""Where the site's own icons come from, in order of preference: Tango, else Nome; BlueHumanity (Humanity with
its hue shifted to blue) only when neither has an icon."""
SECTION_ICONS: Dict[str, Tuple[str, str, str]] = {
    # Section.key (README.md's heading ids) -> (theme, context, icon name). Drawn at 48 px in the heading and
    # 16 px in the Contents sidebar, so every one is an icon that theme draws at both sizes.
    "tango-remixer": ("Tango", "places", "start-here"),
    "why": ("Tango", "apps", "help-browser"),
    "used-submodules": ("Nome", "mimetypes", "package-x-generic"),                  # a package (Tango's has no 16 px drawing)
    "built-in-icon-themes-and-licenses": ("Nome", "apps", "preferences-desktop-theme"),   # the colour swatches
    "included_iconstxt-reference": ("Nome", "apps", "accessories-dictionary"),   # a reference book
    "how-to-use-in-qt-project": ("Nome", "categories", "applications-engineering"),
    "build-svg-and-qrc": ("Nome", "apps", "utilities-terminal"),
    "internal-concepts": ("Nome", "categories", "preferences-system"),             # under the hood
    "acknowledgments": ("Tango", "emblems", "emblem-favorite"),
    "licenses": ("Nome", "mimetypes", "application-certificate"),
    # lsp/README.md: the document's own page, then its sections (the file stems)
    "lsp": ("Nome", "categories", "applications-development"),
    "lsp-install": ("Nome", "apps", "system-software-install"),
    "lsp-editor-setup": ("Nome", "apps", "code-viewer-c-liked"),   # code in an editor
}
_DEFAULT_ICON: Tuple[str, str, str] = ("Tango", "mimetypes", "text-x-generic")
"""For a section SECTION_ICONS does not know."""
ALERT_ICONS: Dict[str, Tuple[str, str]] = {
    # GitHub's alert kinds -> the dialog icons GNOME 2 documents and dialogs show, drawn at 22 px by the title.
    # Nome has them at that size (Tango only at 32 and 48); the colours in style.css follow the icons.
    "note": ("status", "dialog-information"),   # the light bulb
    "tip": ("emblems", "emblem-default"),       # the green check
    "important": ("emblems", "emblem-important"),
    "warning": ("status", "dialog-warning"),
    "caution": ("status", "dialog-error"),
}
IconLookup = Callable[[str, str, Tuple[int, ...], Optional[str]], Dict[int, str]]
"""(context, icon name, sizes in px, theme to try first or None) -> size -> `<theme>/<path>` under viewer/icons/, all from one theme"""
_LANGUAGES: Dict[str, str] = {"cmakelists": "cmake"}
"""Fence languages of README.md under the names Pygments knows them by."""
INCLUDED_ICONS_LANGUAGE: str = "included-icons"
_LIST_ITEM = re.compile(r"([-*+]|\d+[.)]) ")
"""The fence language of an included_icons.txt example: coloured by this project's own tokenizer, not Pygments."""


class Repository(NamedTuple):
    """A git repository on GitHub or GitLab, at one commit."""
    web: str
    """https://github.com/<owner>/<repo>, no trailing slash"""
    commit: str

    @property
    def host(self) -> str:
        return self.web.split("/")[2]

    def url(self, path: str = "", folder: bool = False) -> str:
        """The web page of `path` at `commit`: a file, or a folder with `folder`.
        A file URL is also what the viewer appends file names to (GitHub turns a
        blob URL of a folder into the folder's page; GitLab wants tree)."""
        prefix = "-/" if "gitlab" in self.host else ""   # GitLab keeps its routes under /-/
        return f"{self.web}/{prefix}{'tree' if folder else 'blob'}/{self.commit}" + (f"/{path}" if path else "")


def web_url(remote: str) -> str:
    """`https://<host>/<owner>/<repo>` for a git remote in SSH or HTTPS form (a user
    name or token in the URL is dropped)."""
    match = re.fullmatch(r"(?:\w+@([^:/\s]+):|https?://(?:[^@/\s]+@)?([^/\s]+)/)(\S+?)(?:\.git)?/?", remote.strip())
    if not match:
        raise ValueError(f"Not a GitHub/GitLab style remote: {remote!r}")
    return f"https://{match[1] or match[2]}/{match[3]}"


def checkout_of(folder: Path) -> Tuple[Repository, Path]:
    """The repository `folder` is checked out from (origin remote, HEAD) and the
    checkout's root: the folder with `.git` (a file in a submodule, else a folder)."""
    root = next((p for p in [folder, *folder.parents] if (p / ".git").exists()), None)
    if root is None:
        raise RuntimeError(f"{folder} is not inside a git checkout")

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()

    return Repository(web_url(git("remote", "get-url", "origin")), git("rev-parse", "HEAD")), root


def source_place(folder: Path) -> Dict[str, str]:
    """Where a theme's source folder is on the web, for the viewer page (index.json):
    `url`, the folder at the checked-out commit, e.g.
    https://github.com/kuanyui/nome-icon-theme/blob/<commit>/src, to which the page
    appends a file's path; `repo`, the repository's home page; `commit`, its hash."""
    repo, root = checkout_of(folder)
    sub = folder.relative_to(root).as_posix()
    return {"url": repo.url("" if sub == "." else sub), "repo": repo.web, "commit": repo.commit}


def site_repository(root: Path) -> Repository:
    """The repository the site is built from: told by the CI of GitLab or GitHub,
    else read from the checkout at `root`."""
    env = os.environ
    if env.get("CI_PROJECT_URL"):
        return Repository(env["CI_PROJECT_URL"], env["CI_COMMIT_SHA"])
    if env.get("GITHUB_REPOSITORY"):
        return Repository(f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/{env['GITHUB_REPOSITORY']}", env["GITHUB_SHA"])
    return checkout_of(root)[0]


# --- The viewer ---------------------------------------------------------------------------------------

def clean_commit(folder: Path) -> Optional[str]:
    """The commit the checkout of `folder` is at, when nothing under `folder` is
    modified or untracked. None for work in progress (or no checkout): such a
    theme is compared file by file."""
    try:
        repo, root = checkout_of(folder)
        status = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", str(folder.relative_to(root))],
                                check=True, capture_output=True, text=True).stdout
    except (RuntimeError, ValueError, subprocess.CalledProcessError):
        return None
    return None if status.strip() else repo.commit


def write_file(path: Path, data: bytes, mtime_ns: Optional[int] = None) -> None:
    """`data` into `path` in one step: written beside it, then renamed over it, so a
    reader (the browser on the dev server) gets the old file or the new one, never a
    partial one. With `mtime_ns` the file carries that stamp (write_viewer_icons)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    if mtime_ns is not None:
        os.utime(tmp, ns=(mtime_ns, mtime_ns))
    os.replace(tmp, path)


def mirror_tree(src: Path, dst: Path, ignore: Tuple[str, ...] = ()) -> None:
    """`dst` made a copy of `src` (files named in `ignore` left out), each file
    through write_file, files `src` no longer has removed. Nothing is deleted first,
    so the folder is whole at every moment (rmtree + copytree leaves a gap)."""
    wanted: Set[Path] = set()
    for path in src.rglob("*"):
        if path.is_file() and path.name not in ignore:
            wanted.add(dst / path.relative_to(src))
            write_file(dst / path.relative_to(src), path.read_bytes())
    if dst.is_dir():
        for stale in [p for p in dst.rglob("*") if p.is_file() and p not in wanted]:
            stale.unlink()


def write_viewer_page(themes: Dict[str, SourceTheme], out: Path, places: Dict[str, Dict[str, object]], panel: str, index: List[Dict[str, object]]) -> None:
    """The viewer's page and assets into `out`: index.html (with the site's `panel`
    above its window, when given), static/ from viewer/static/, and api/index.json
    with `places[name]` (source_place: url, repo, commit) in each theme's entry."""
    mirror_tree(_STATIC_DIR, out / "static", ignore=("index.html",))   # llselect, window.*, clearlooks.css
    page = (_STATIC_DIR / "index.html").read_text("utf-8")
    if panel:   # the panel's stylesheet, markup and script, from the site root above this folder
        page = page.replace("</head>", '<link rel="stylesheet" href="../panel.css">\n</head>', 1)
        page = page.replace("<body>\n", "<body>\n" + panel + "\n", 1)
        page = page.replace("</body>", '<script src="../panel.js"></script>\n</body>', 1)
    write_file(out / "index.html", page.encode("utf-8"))
    write_file(out / "api" / "index.json", index_json(themes, index, places))


def write_viewer_icons(themes: Dict[str, SourceTheme], out: Path, index: List[Dict[str, object]]) -> Tuple[int, int]:
    """icons/<theme>/<path> under `out` for every file of `index`. Returns (icons
    in the site, icons written this time).

    A rerun is quick: a theme whose checkout is clean and at the commit of the last
    export (noted in .versions.json; for a Blue* theme together with the colorizer's
    mtime) is left as it is. Any other theme is compared file by file: an icon is
    rewritten when its source (or, for a Blue* theme, the colorizer) changed, and
    dropped when no longer indexed."""
    versions_file = out / ".versions.json"
    exported: Dict[str, str] = json.loads(versions_file.read_text("utf-8")) if versions_file.is_file() else {}
    colorizer_mtime: int = _COLOR_CONVERTER.stat().st_mtime_ns
    commits: Dict[Path, Optional[str]] = {}   # per source folder: the Blue* themes share their base theme's
    total = written = 0
    for name, theme in themes.items():
        files: List[str] = [size["path"] for entry in index if entry["theme"] == name for size in entry["sizes"]]
        total += len(files)
        if theme.folder not in commits:
            commits[theme.folder] = clean_commit(theme.folder)
        version: Optional[str] = commits[theme.folder]
        if version and theme.colorize:
            version += f"+{colorizer_mtime}"
        folder = out / "icons" / name
        if version and exported.get(name) == version and folder.is_dir():
            continue
        wanted: Dict[Path, Path] = {folder / rel: theme.folder / rel for rel in files}   # site file -> source file
        if folder.is_dir():
            for stale in [p for p in folder.rglob("*") if p.is_file() and p not in wanted]:
                stale.unlink()
        for dst, src in wanted.items():
            # The written file carries a stamp as its mtime: the source's, raised to the colorizer's for a
            # colorized copy. Same stamp next time = nothing to do, without reading either file.
            stamp: int = max(src.stat().st_mtime_ns, colorizer_mtime) if theme.colorize else src.stat().st_mtime_ns
            if dst.is_file() and dst.stat().st_mtime_ns == stamp:
                continue
            data: bytes = src.read_bytes()
            if theme.colorize:   # as the server does per request
                data = theme.colorize(data.decode("utf-8"), src.stem).encode("utf-8")
            write_file(dst, data, stamp)
            written += 1
        if version:
            exported[name] = version
        else:
            exported.pop(name, None)
    versions_file.write_text(json.dumps(exported, indent=1), "utf-8")
    return total, written


def export_viewer(themes: Dict[str, SourceTheme], out: Path, places: Dict[str, Dict[str, object]], panel: str = "",
                  index: Optional[List[Dict[str, object]]] = None) -> Tuple[int, int]:
    """The whole viewer into `out`: its page and assets (write_viewer_page), then its
    icons (write_viewer_icons, whose count this returns). `index` is built here when
    not given."""
    if index is None:
        index = build_index(themes)
    write_viewer_page(themes, out, places, panel, index)
    return write_viewer_icons(themes, out, index)


# --- The homepage -------------------------------------------------------------------------------------

def github_slug(text: str, separator: str) -> str:
    """Heading ids as GitHub makes them, so the README's links to its own headings
    (and links into it from elsewhere) work on the homepage too: lower case,
    punctuation other than `-` and `_` dropped, each space a `-`."""
    return re.sub(r"[^\w\- ]", "", text.lower()).strip().replace(" ", separator)


def render_markdown(text: str) -> Rendered:
    """Markdown to HTML (and its table of contents) with Python-Markdown and its
    `extra` set (tables, fenced code, ...), plus what GitHub renders and it does not: `~~gone~~`, the
    `> [!NOTE]` alert blockquotes (NOTE, TIP, IMPORTANT, WARNING, CAUTION), a
    fenced code block inside a blockquote (made an indented one), two blockquotes
    separated by a blank line (kept apart), a list right after a line of text
    (given the blank line Python-Markdown wants), and a nested list indented by two
    spaces (made four, which Python-Markdown wants). An `included-icons` fence is
    coloured by highlight_included_icons instead of Pygments. What the document
    hides from the homepage (_HIDDEN, such as the README's table of contents) is
    dropped first."""
    try:
        import markdown
    except ImportError:
        sys.exit("The homepage needs Python-Markdown (the `markdown` module): sudo apt install python3-markdown "
                 "on Debian / Ubuntu, else pip install markdown. (markdown2 is a different library.)")
    text = _HIDDEN.sub("", text)
    lines: List[str] = []
    fence: Optional[str] = None   # inside a fenced block: the blockquote prefix it was opened with ("" outside a quote)
    quoted = False                # the last non-blank line was a blockquote line
    example: Optional[List[str]] = None   # the lines of an included-icons fence, coloured here and passed on as HTML
    last = ""                             # the text of the previous source line, after its blockquote marks
    items: List[Tuple[int, int]] = []     # the open list items, for nesting
    for line in text.splitlines(keepends=True):
        quote, indent, rest = re.match(r"((?:\s*>)*)( *)(.*\n?)", line).groups()   # blockquote marks, indentation, text
        depth = max(len(indent) - (1 if quote else 0), 0)   # indentation after an optional space of a `> ` mark
        if fence is None and _LIST_ITEM.match(rest):
            # GitHub nests an item two spaces in under the item above; Python-Markdown wants four per level.
            # `items` holds the open items as (depth written, depth Python-Markdown needs): a deeper item
            # goes four in from its parent, a shallower one closes what it outdents. The first item of a
            # list keeps its indentation (an item after a line of text is a list, not a nested one).
            while items and items[-1][0] >= depth:
                items.pop()
            wanted = items[-1][1] + 4 if items else depth
            items.append((depth, wanted))
            if wanted != depth:
                indent = " " * (wanted + (1 if quote else 0))
                line = quote + indent + rest
        elif fence is None and rest.strip() and depth == 0:
            items.clear()   # a line of text at the base ends the list
        prefix = quote + indent
        if rest.startswith("```"):
            if fence is None:
                fence = prefix
                language = rest[3:].strip()
                if language == INCLUDED_ICONS_LANGUAGE and not prefix.strip():
                    example = []
                    continue
                line = f"{prefix}```{_LANGUAGES.get(language, language)}\n"
            else:
                fence = None
                if example is not None:
                    lines.append("\n" + highlight_included_icons("".join(example)) + "\n\n")
                    example = None
                    last = ""
                    continue
            if prefix.strip():   # an indented code block wants a blank quoted line on each side
                lines.append(prefix.rstrip() + "\n")
                continue
        elif example is not None:
            example.append(line)
            continue
        elif fence is not None and fence.strip():
            lines.append(prefix + "    " + rest)
            continue
        elif fence is None:
            if prefix.strip() and quoted and lines and not lines[-1].strip():
                lines.append("<!-- -->\n")   # a blockquote after a blank line after a blockquote: keep it a second one
            if _LIST_ITEM.match(rest) and last.strip() and not _LIST_ITEM.match(last) and not last.startswith((" ", "|")):
                lines.append(prefix.rstrip() + "\n")   # a list straight after a line of text: GitHub starts the list, Python-Markdown wants a blank line first
            line = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", line)
        if line.strip():
            quoted = bool(prefix.strip())
        lines.append(line)
        last = rest
    md = markdown.Markdown(extensions=["extra", "toc", "codehilite"],   # codehilite colours the code with Pygments when it is installed
                           extension_configs={"toc": {"slugify": github_slug, "toc_depth": "2"}, "codehilite": {"css_class": "highlight", "guess_lang": False}})
    html: str = md.convert("".join(lines))
    headings: List[Dict[str, object]] = md.toc_tokens

    def alert(m: re.Match[str]) -> str:
        head = f'<blockquote class="alert {m[1].lower()}">\n<p class="alert-title">{m[1].capitalize()}</p>'
        return head if m[2] == "</p>" else head + "\n<p>"   # the marker shared its paragraph with the text after it

    return Rendered(re.sub(rf"<blockquote>\s*<p>\[!({'|'.join(_ALERTS)})\](</p>|\n)", alert, html), headings)


def highlight_included_icons(code: str) -> str:
    """An included_icons.txt example as HTML in the shape Pygments writes (a
    div.highlight), every token in a span of its kind: ii-theme (plus ii-builtin
    for a built-in theme), ii-context, ii-icon, ii-input_size, ii-output_size,
    ii-operator, ii-keyword, ii-comment, ii-directive, ii-string. The tokens are
    the LSP server's (lib/included_icons_tokens.py), so the site and an editor agree."""
    tokens = tokenize(code)
    lines: List[str] = []
    for n, raw in enumerate(code.splitlines()):
        pos, parts = 0, []
        for t in [t for t in tokens if t.line == n]:
            parts.append(html.escape(raw[pos:t.col]))
            parts.append(f'<span class="ii-{t.kind}{" ii-builtin" if t.builtin else ""}">{html.escape(raw[t.col:t.col + t.length])}</span>')
            pos = t.col + t.length
        parts.append(html.escape(raw[pos:]))
        lines.append("".join(parts))
    return '<div class="highlight"><pre><span></span><code>' + "\n".join(lines) + '\n</code></pre></div>'


def highlight_css() -> str:
    """The colours of the code blocks: Pygments' tango style, and its native style for
    View > Dark Background. Empty without Pygments, when the blocks stay plain."""
    try:
        from pygments.formatters import HtmlFormatter
    except ImportError:
        return ""
    return ("/* Code blocks: Pygments' tango style, native for the dark background (written by generate_static_site.py) */\n"
            f"{HtmlFormatter(style='tango').get_style_defs('.highlight')}\n{HtmlFormatter(style='native').get_style_defs('body.dark .highlight')}\n")


def split_sections(rendered: Rendered, doc: Document = DOCUMENTS[0]) -> List[Section]:
    """The rendered document cut into pages. At level 1 (README.md): one per top-level
    heading, what comes before the first (the banner) in the first. At level 2: the
    document's own page first, its top-level heading and what follows it up to the
    first second-level heading, then a page per second-level heading, their headings
    promoted a level (h2 to h1, h3 to h2, ...) so that every page opens with an h1."""
    if doc.level == 1:
        parts = re.split(r'(?=<h1 id=")', rendered.html)
        if not parts[0].startswith("<h1 "):   # what comes before the first heading (the banner) belongs to the first section
            parts[1:2] = [parts[0] + parts[1]]
            del parts[0]
        assert len(parts) == len(rendered.headings), (len(parts), len(rendered.headings))
        return [Section(doc, str(h["id"]), str(h["name"]), str(h["name"]), "./" if k == 0 else f"{h['id']}.html", str(h["id"]), part, False)
                for k, (h, part) in enumerate(zip(rendered.headings, parts))]
    parts = re.split(r'(?=<h2 id=")', rendered.html)
    own, heads = rendered.headings[0], [c for h in rendered.headings for c in h["children"]]   # the document's heading, its sections'
    assert len(parts) == len(heads) + 1 and parts[0].startswith("<h1 "), (len(parts), len(heads))
    promote = lambda html: re.sub(r"<(/?)h([2-6])\b", lambda m: f"<{m[1]}h{int(m[2]) - 1}", html)
    return [Section(doc, str(own["id"]), str(own["name"]), doc.group or str(own["name"]), f"{doc.prefix}.html", doc.prefix, parts[0], False)] + [
        Section(doc, str(h["id"]), str(h["name"]), str(h["name"]), f"{doc.prefix}-{h['id']}.html", f"{doc.prefix}-{h['id']}", promote(part), True)
        for h, part in zip(heads, parts[1:])]


def icon_paths(index: List[Dict[str, object]], context: str, name: str, sizes: Tuple[int, ...], prefer: Optional[str] = None) -> Dict[int, str]:
    """`<theme>/<path>` under viewer/icons/ of the icon `name` for each of `sizes`
    (px), all from one theme: `prefer` if it draws the icon at every one of those
    sizes, else the first of THEMES that does, so a section's 16 px sidebar entry
    and its 48 px heading show the same drawing; failing that, the first that has
    the icon at all, at the smallest of its sizes that is the wanted one or larger
    (else its largest). `index` is the viewer's (build_index)."""
    found: List[Tuple[str, Dict[int, str]]] = []   # (theme, its sizes of the icon), in order of preference
    for theme in ([prefer] if prefer else []) + [theme for theme in THEMES if theme != prefer]:
        for entry in index:
            if entry["theme"] == theme and entry["context"] == context and entry["name"] == name:
                found.append((theme, {int(s["size"]): str(s["path"]) for s in entry["sizes"] if s["size"] != "scalable"}))   # type: ignore[index]
                break
    for theme, have in found:
        if all(size in have for size in sizes):
            return {size: f"{theme}/{have[size]}" for size in sizes}
    if found:
        theme, have = found[0]
        return {size: f"{theme}/{have[min(s for s in have if s >= size) if any(s >= size for s in have) else max(have)]}" for size in sizes}
    raise LookupError(f"None of {', '.join(THEMES)} has {context}/{name}")


def localize(html: str, root: Path, out: Path, repo: Repository, base: Optional[Path] = None, pages: Optional[Dict[str, str]] = None) -> str:
    """Relative `src` and `href` targets in `html`, read from `base` (the document's
    folder; `root`, the repository's, by default), name files of the repository: an
    image the page shows is copied into `out` under its repository path, which the
    page then names; a document of the site (`pages`: repository path -> its first
    page) links to that page; any other existing file or folder links to its page in
    `repo`. Targets outside the repository, or missing, are left alone."""
    base = base or root

    def repl(m: re.Match[str]) -> str:
        attr, target = m[1], m[2]
        path = (base / target.split("#")[0]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.exists():   # not a file of the repository (e.g. ../): left alone
            return m[0]
        rel = path.relative_to(root.resolve()).as_posix()
        if attr == "src" and path.is_file():
            write_file(out / rel, path.read_bytes())
            return f'src="{rel}"'
        if pages and rel in pages:
            return f'href="{pages[rel]}"'
        return f'{attr}="{repo.url(rel, folder=path.is_dir())}"'
    return re.sub(r'\b(src|href)="(?![a-z]+:|#|/)([^"]+)"', repl, html)


def render_panel(root: str, active: str, repo: Repository) -> str:
    """homepage/panel.html for a page `root` away from the site root ("" for the
    homepage, "../" for the viewer), with the window of the page (`home` or
    `viewer`) pressed in the window list."""
    panel = (_HOMEPAGE_DIR / "panel.html").read_text("utf-8")
    for key, value in [("root", root), ("home_pressed", " pressed" if active == "home" else ""),
                       ("viewer_pressed", " pressed" if active == "viewer" else ""), ("commit", repo.commit[:7]), ("date", date.today().isoformat())]:
        panel = panel.replace("{{" + key + "}}", value)
    return panel.rstrip("\n")


def page_text(html_: str) -> str:
    """A page's text as the find bar reads it in the page: tags dropped (the
    line breaks between blocks keep their words apart), entities read,
    whitespace folded."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", html_)).split())


def render_pages(sources: Union[str, Sequence[Tuple[Document, str]]], repo: Repository, root: Path, out: Path, panel: str, icons: IconLookup) -> Dict[str, str]:
    """The pages of the site, file name -> HTML, from template.html with the panel,
    the Contents sidebar (every page with its icon, this one selected; a document
    with a group under a row of its own), the page with its icon in the heading, and
    Previous / Next links. `sources`: README.md's text alone, or (document, its text)
    in the order the Contents list them. A link to a heading of another page of the
    same document goes to that page; a link to a document of the site to its first
    page. Plus search-index.json: every page's link, label and text, for the find bar
    to search the whole documentation."""
    if isinstance(sources, str):
        sources = [(DOCUMENTS[0], sources)]
    docs: List[Tuple[Document, List[Section]]] = [(doc, split_sections(render_markdown(text), doc)) for doc, text in sources]
    sections: List[Section] = [section for _, parts in docs for section in parts]
    own_page: Dict[str, str] = {doc.path: parts[0].file for doc, parts in docs}   # a document's repository path -> its first page
    page_of: Dict[Tuple[Document, str], str] = {}   # (document, heading id) -> file
    for section in sections:
        for anchor in re.findall(r' id="([^"]+)"', section.html):
            page_of.setdefault((section.doc, anchor), section.file)

    def cross_link(m: re.Match[str], here: Section) -> str:
        anchor = m[1]
        target = page_of.get((here.doc, anchor), here.file)
        if target == here.file:
            return m[0]
        return f'href="{target}"' if any(s.doc is here.doc and s.id == anchor for s in sections) else f'href="{target}#{anchor}"'

    def icon(context: str, name: str, size: int, sizes: Tuple[int, ...] = (16, 48), theme: Optional[str] = None) -> str:
        """The icon's <img> at `size`, from `theme` (else the first that has it) drawing it at all of `sizes`."""
        return f'<img src="viewer/icons/{icons(context, name, sizes, theme)[size]}" width="{size}" height="{size}" alt="">'

    def section_icon(s: Section, size: int) -> str:
        theme, context, name = SECTION_ICONS.get(s.key, _DEFAULT_ICON)
        return icon(context, name, size, theme=theme)

    def sidebar(current: Section) -> str:
        def row(s: Section) -> str:   # the title again as a tooltip: a long one is cut short in the list
            return f'<li><a href="{s.file}"{" class=\"current\"" if s is current else ""} title="{s.title}">{section_icon(s, 16)}<span>{s.label}</span></a>'
        rows: List[str] = []
        for doc, parts in docs:
            if doc.group:   # the document's own page, its sections under it
                rows.append(row(parts[0]) + "\n<ul>\n" + "\n".join(row(s) + "</li>" for s in parts[1:]) + "\n</ul></li>")
            else:
                rows.extend(row(s) + "</li>" for s in parts)
        return "\n".join(rows)

    host = "GitHub" if "github" in repo.host else "GitLab" if "gitlab" in repo.host else repo.host
    template = (_HOMEPAGE_DIR / "template.html").read_text("utf-8")
    pages: Dict[str, str] = {}
    index: List[Dict[str, str]] = []
    for k, section in enumerate(sections):
        html = localize(section.html, root, out, repo, base=root / Path(section.doc.path).parent, pages=own_page)   # localize first: "./" is a page here, not the repository's root
        html = re.sub(r'href="#([^"]+)"', lambda m: cross_link(m, section), html)
        html = html.replace(f'<h1 id="{section.id}">', f'<h1 id="{section.id}">{section_icon(section, 48)}', 1)
        for kind, (alert_context, alert_name) in ALERT_ICONS.items():   # the alerts' titles get their dialog icon
            html = html.replace(f'<p class="alert-title">{kind.capitalize()}</p>', f'<p class="alert-title">{icon(alert_context, alert_name, 22, (22,))}{kind.capitalize()}</p>')
        previous, following = (sections[k - 1] if k else None), (sections[k + 1] if k + 1 < len(sections) else None)
        pager = "".join([
            f'<a class="previous" href="{previous.file}">{icon("actions", "go-previous", 16, (16,))}Previous: {previous.label}</a>' if previous else "<span></span>",
            f'<a class="next" href="{following.file}">Next: {following.label}{icon("actions", "go-next", 16, (16,))}</a>' if following else "<span></span>"])
        page = template
        for key, value in [("repo_url", repo.web), ("repo_host", host), ("commit", repo.commit[:7]), ("date", date.today().isoformat()),
                           ("page_title", section.title if k == 0 else f"{section.title} - Tango Remixer"), ("title", section.title),
                           ("panel", panel), ("section_icon", section_icon(section, 16)), ("sidebar", sidebar(section)), ("content", html), ("pager", pager)]:
            page = page.replace("{{" + key + "}}", value)
        pages["index.html" if k == 0 else section.file] = page
        index.append({"href": section.file, "title": section.label, "text": page_text(html)})
    pages["search-index.json"] = json.dumps(index, ensure_ascii=False)
    return pages


def write_pages(out: Path, pages: Dict[str, str]) -> None:
    """The pages into `out`; a page of an earlier build that is no longer one (a
    section renamed or removed) goes, so a preview never shows a stale one."""
    for stale in out.glob("*.html"):
        if stale.name not in pages:
            stale.unlink()
    for file, html in pages.items():
        write_file(out / file, html.encode("utf-8"))


class Site:
    """The site in `out`, from the checkout at `root`. The slow inputs are read once,
    when the object is made: the theme scan (build_index) and the submodules'
    repository URLs (git), seconds each on a slow mount. build() writes the site and
    can run again (the dev server's watch does): in well under a second when the
    icons are left alone."""

    def __init__(self, out: Path, root: Path = _PROJECT_ROOT) -> None:
        self.out: Path = out
        self.root: Path = root
        self.themes: Dict[str, SourceTheme] = source_themes()
        self.index: List[Dict[str, object]] = build_index(self.themes)
        by_folder: Dict[Path, Dict[str, str]] = {}   # per source folder: the Blue* themes share their base theme's
        for theme in self.themes.values():
            by_folder.setdefault(theme.folder, source_place(theme.folder))
        self.places: Dict[str, Dict[str, object]] = {name: by_folder[theme.folder] for name, theme in self.themes.items()}

    def build(self, icons: bool = True) -> str:
        """Write the site: the pages, the viewer's page and, unless `icons` is False,
        the viewer's icons (write_viewer_icons rewrites only what changed). Returns a
        line saying what was done."""
        started = time.perf_counter()
        out, root = self.out, self.root
        out.mkdir(parents=True, exist_ok=True)
        repo = site_repository(root)
        for name in ["style.css", "panel.css", "panel.js"]:
            write_file(out / name, (_HOMEPAGE_DIR / name).read_bytes())
        write_file(out / "highlight.css", highlight_css().encode("utf-8"))
        mirror_tree(_HOMEPAGE_DIR / "marks", out / "marks")   # the launchers' GitHub and GitLab marks, with their note
        sources = [(doc, (root / doc.path).read_text("utf-8")) for doc in DOCUMENTS if (root / doc.path).is_file()]
        pages = render_pages(sources, repo, root, out, render_panel("", "home", repo), partial(icon_paths, self.index))
        write_pages(out, pages)
        write_viewer_page(self.themes, out / "viewer", self.places, render_panel("../", "viewer", repo), self.index)
        about_icons = ""
        if icons:
            total, written = write_viewer_icons(self.themes, out / "viewer", self.index)
            about_icons = f" Viewer: {total} icons of {len(self.themes)} themes, {written} written, the rest unchanged."
        return (f"{sum(file.endswith('.html') for file in pages)} pages from {', '.join(doc.path for doc, _ in sources)} at {repo.web} ({repo.commit[:7]})."
                f"{about_icons} {out} ready in {time.perf_counter() - started:.1f}s.")


def generate(out: Path, root: Path = _PROJECT_ROOT) -> None:
    """The whole site into `out`."""
    print(Site(out, root).build(), flush=True)


# --- The dev server -----------------------------------------------------------------------------------

def watched_sources(root: Path, out: Path) -> Dict[Path, Tuple[int, int]]:
    """The files the site is made from, each with its (mtime, size): the documents (DOCUMENTS),
    everything under homepage/ (but a _build folder, the site in `out` and
    __pycache__) and under viewer/static/, and the code that makes it: build_icons.py
    (the theme table), lib/*.py (the colorizer, the included_icons.txt tokenizer) and
    viewer/*.py (homepage/*.py is under homepage/). The theme folders are not among
    them: thousands of files, slow to poll on a slow mount, and `make viewer` shows
    an edited SVG without any build."""
    found: Dict[Path, Tuple[int, int]] = {}

    def note(path: Path) -> None:
        try:
            stat = path.stat()
        except OSError:   # gone between the listing and here
            return
        found[path] = (stat.st_mtime_ns, stat.st_size)

    for file in [*(root / doc.path for doc in DOCUMENTS), root / "build_icons.py", *(root / "lib").glob("*.py"), *(root / "viewer").glob("*.py")]:
        note(file)
    skipped = {out.resolve(), (root / "homepage" / "_build").resolve()}
    pending: List[Path] = [root / "homepage", root / "viewer" / "static"]
    while pending:
        folder = pending.pop()
        if folder.name == "__pycache__" or folder.resolve() in skipped:
            continue
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                pending.append(Path(entry.path))
            elif entry.is_file():
                note(Path(entry.path))
    return found


def rebuild_plan(changed: List[Path], root: Path) -> str:
    """What a change to `changed` calls for. "restart": Python code changed, which this
    process would go on running the old version of (homepage/*.py, viewer/*.py,
    build_icons.py, lib/*.py but the colorizer). "icons": the colorizer changed; it is
    reloaded on the fly (viewer/server.py) and the Blue* icons are made from it.
    "pages": anything else."""
    colorizer = root / "lib" / "color_converter.py"
    if any(path.suffix == ".py" and path != colorizer for path in changed):
        return "restart"
    return "icons" if colorizer in changed else "pages"


def watch(root: Path, out: Path, rebuild: Callable[[List[Path]], None], interval: float = 1.0,
          stop: Optional[threading.Event] = None) -> None:
    """Poll watched_sources every `interval` seconds until `stop` is set. When they
    changed, wait for the change to settle (a poll that finds nothing new: editors
    save in bursts), then call rebuild() with the files that changed, came or went."""
    stop = stop or threading.Event()
    before = watched_sources(root, out)
    while not stop.wait(interval):
        now = watched_sources(root, out)
        if now == before:
            continue
        while not stop.wait(interval):
            again = watched_sources(root, out)
            if again == now:
                break
            now = again
        if stop.is_set():
            return
        rebuild(sorted(path for path in set(before) | set(now) if before.get(path) != now.get(path)))
        before = now


class _QuietHandler(SimpleHTTPRequestHandler):
    """The site's files, nothing logged: a page load of the viewer requests thousands of icons (as viewer/server.py notes)."""

    def log_message(self, format: str, *args: object) -> None:
        pass


def site_server(out: Path, port: int = 0) -> ThreadingHTTPServer:
    """An HTTP server for the generated site in `out`, on every interface (as the viewer is), not yet running."""
    return ThreadingHTTPServer(("0.0.0.0", port), partial(_QuietHandler, directory=str(out)))


def serve(out: Path, port: int, site: Optional[Site] = None) -> None:
    """`--serve`: the site over HTTP until Ctrl-C, the URLs to open printed first,
    this machine's LAN addresses among them (local_urls), so a browser on another
    machine (the host of a VM) can open it too. Given the `site`, a change to one of
    watched_sources rebuilds it while it is served (the Blue* icons too when the
    colorizer changed); reload the page to see it."""
    try:
        server = site_server(out, port)
    except OSError as e:
        sys.exit(f"Cannot listen on port {port} ({e.strerror}). Is another server still running? Stop it first.")
    if site:
        def rebuild(changed: List[Path]) -> None:
            names = ", ".join(str(p.relative_to(site.root)) if p.is_relative_to(site.root) else str(p) for p in changed[:3]) + (", …" if len(changed) > 3 else "")
            plan = rebuild_plan(changed, site.root)
            if plan == "restart":   # this process runs the code it started with: start over with the new one
                print(f"{names} changed: restarting to run the new code (the whole site is built again, give it a moment).", flush=True)
                server.server_close()
                os.execv(sys.executable, [sys.executable, *sys.argv])
            try:
                print(f"{names} changed. " + site.build(icons=plan == "icons"), flush=True)
            except Exception as e:   # a half-written README, a section icon that is not there, ...: whatever was written so far stays whole (write_file)
                print(f"[ERROR] Rebuild failed: {e}", file=sys.stderr, flush=True)

        threading.Thread(target=watch, args=(site.root, out, rebuild), daemon=True).start()
    print("Website listening on all interfaces (Ctrl-C to stop). Open one of:\n  " + "\n  ".join(local_urls(port))
          + "\nThe icon viewer is at viewer/ under each."
          + ("\nWatching README.md, homepage/, viewer/static/ and lib/color_converter.py: a change rebuilds the site (reload the page);\n"
             "a change to the Python code it is made with restarts this server." if site else ""),
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser(description="Generate the project website as plain files (see the module docstring).")
    parser.add_argument("out", nargs="?", default=_HOMEPAGE_DIR / "_build", type=Path, help="where the site is written (default: homepage/_build)")
    parser.add_argument("--serve", nargs="?", const=8000, type=int, metavar="PORT",
                        help="then serve OUT on PORT (default 8000) on every interface, printing the URLs to open, and rebuild it when its sources change")
    args = parser.parse_args(argv)
    out: Path = args.out.resolve()
    site = Site(out)
    print(site.build(), flush=True)
    if args.serve is not None:
        serve(out, args.serve, site)


if __name__ == "__main__":
    main(sys.argv[1:])
