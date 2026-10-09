#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the project website as plain files (no server), the way GitHub Pages
and GitLab Pages publish it:

    index.html, <id>.html,    the homepage: README.md rendered into template.html, one page per
    style.css                 top-level heading, as a Clearlooks window (viewer/static/window.*,
                              clearlooks.css) with a Contents sidebar; every section has an icon
                              (SECTION_ICONS: Tango where it has it, else Nome)
    panel.css, panel.js,      the GNOME 2 panel above both windows (panel.html: main menu, launchers
    marks/                    with the GitHub / GitLab marks, window list, the build in the clock slot)
    tango-mixer-banner.svg    (and any other image README.md shows)
    viewer/                   the icon viewer (viewer/) as a static site: its page and
                              assets, api/index.json, and every indexed SVG under
                              icons/<theme>/<path>, the Blue* themes colorized with
                              the same code the build uses

Run:  python3 homepage/generate_static_site.py [OUT]     (default: homepage/_build/)
      make homepage-build        the same
      make homepage-dev-server   the same, then served on port 8000, on every interface as the viewer is
Needs Python-Markdown (the `markdown` module) and, for coloured code blocks, Pygments:
`apt install python3-markdown python3-pygments` on Debian / Ubuntu, else
`pip install markdown pygments`. (`markdown2` is a different library.)

The viewer part writes only the real files of the index (an alias is a symlink
name listed with its icon; the page never requests it), so a theme weighs what
its source SVGs weigh, and a Blue* theme is a second copy of its base theme. A
rerun rewrites only the icons whose source (or the colorizer) changed, so a
preview round trip takes seconds. Instead of a folder on some machine, each theme
gets the URL of its folder in the submodule's repository at the checked-out
commit, where the page links every file; no local path is written.

Links in README.md to files of this repository point at their page in the
repository the site is built from: told by the CI of GitLab or GitHub, else the
origin remote of the checkout.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from functools import partial
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from lib.included_icons_tokens import tokenize  # noqa: E402
from viewer.server import _COLOR_CONVERTER, _STATIC_DIR, Colorizer, SourceTheme, build_index, index_json, source_themes  # noqa: E402

_HOMEPAGE_DIR: Path = Path(__file__).resolve().parent
_ALERTS: Tuple[str, ...] = ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION")
"""GitHub's `> [!NOTE]` blockquote kinds."""


class Rendered(NamedTuple):
    """README.md as HTML, and its top-level headings (Python-Markdown's toc tokens: id, name, html, ...)."""
    html: str
    headings: List[Dict[str, object]]


class Section(NamedTuple):
    """One top-level heading of README.md with everything under it: one page of the site."""
    id: str
    title: str
    """plain text"""
    file: str
    """index.html for the first section, <id>.html for the others"""
    html: str
    """the heading and what follows it; the first section also carries what comes before it (the banner)"""


THEMES: Tuple[str, ...] = ("Tango", "Nome", "BlueHumanity")
"""Where the site's own icons come from, in order of preference: Tango, else Nome; BlueHumanity (Humanity with
its hue shifted to blue) only when neither has an icon."""
SECTION_ICONS: Dict[str, Tuple[str, str, str]] = {
    # top-level heading id -> (theme, context, icon name). Drawn at 48 px in the heading and 16 px in the
    # Contents sidebar, so every one is an icon that theme draws at both sizes.
    "tango-remixer": ("Tango", "places", "start-here"),
    "why": ("Tango", "apps", "help-browser"),
    "used-submodules": ("Nome", "mimetypes", "package-x-generic"),                  # a package (Tango's has no 16 px drawing)
    "built-in-icon-themes-and-licenses": ("Nome", "apps", "preferences-desktop-theme"),   # the colour swatches
    "included_iconstxt-reference": ("Tango", "apps", "accessories-text-editor"),
    "how-to-use-in-qt-project": ("Nome", "categories", "applications-engineering"),
    "build-svg-and-qrc": ("Nome", "apps", "utilities-terminal"),
    "internal-concepts": ("Nome", "categories", "preferences-system"),             # under the hood
    "acknowledgments": ("Tango", "emblems", "emblem-favorite"),
    "licenses": ("Nome", "mimetypes", "application-certificate"),
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


def source_url(folder: Path) -> str:
    """Where a theme's source folder is on the web, e.g.
    https://github.com/kuanyui/nome-icon-theme/blob/<commit>/src: the viewer page
    appends a file's path to it."""
    repo, root = checkout_of(folder)
    sub = folder.relative_to(root).as_posix()
    return repo.url("" if sub == "." else sub)


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


def export_viewer(themes: Dict[str, SourceTheme], out: Path, urls: Dict[str, str], panel: str = "",
                  index: Optional[List[Dict[str, object]]] = None) -> Tuple[int, int]:
    """Write the viewer into `out`: index.html (with the site's `panel` above its
    window, when given) and static/ from viewer/static/, api/index.json with
    `urls[name]` as each theme's `url`, and icons/<theme>/<path> for every indexed
    file (`index`, built here when not given). Returns (icons in the site, icons
    written this time).

    A rerun is quick: a theme whose checkout is clean and at the commit of the last
    export (noted in .versions.json; for a Blue* theme together with the colorizer's
    mtime) is left as it is. Any other theme is compared file by file: an icon is
    rewritten when its source (or, for a Blue* theme, the colorizer) changed, and
    dropped when no longer indexed."""
    shutil.rmtree(out / "static", ignore_errors=True)
    shutil.copytree(_STATIC_DIR, out / "static", ignore=shutil.ignore_patterns("index.html"))   # llselect, window.*, clearlooks.css
    page = (_STATIC_DIR / "index.html").read_text("utf-8")
    if panel:   # the panel's stylesheet, markup and script, from the site root above this folder
        page = page.replace("</head>", '<link rel="stylesheet" href="../panel.css">\n</head>', 1)
        page = page.replace("<body>\n", "<body>\n" + panel + "\n", 1)
        page = page.replace("</body>", '<script src="../panel.js"></script>\n</body>', 1)
    (out / "index.html").write_text(page, "utf-8")
    if index is None:
        index = build_index(themes)
    (out / "api").mkdir(exist_ok=True)
    (out / "api" / "index.json").write_bytes(index_json(themes, index, "url", urls))
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
            dst.parent.mkdir(parents=True, exist_ok=True)
            if theme.colorize:   # as the server does per request
                dst.write_bytes(theme.colorize(src.read_bytes().decode("utf-8"), src.stem).encode("utf-8"))
            else:
                shutil.copyfile(src, dst)
            os.utime(dst, ns=(stamp, stamp))
            written += 1
        if version:
            exported[name] = version
        else:
            exported.pop(name, None)
    versions_file.write_text(json.dumps(exported, indent=1), "utf-8")
    return total, written


# --- The homepage -------------------------------------------------------------------------------------

def github_slug(text: str, separator: str) -> str:
    """Heading ids as GitHub makes them, so the README's own table of contents
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
    coloured by highlight_included_icons instead of Pygments."""
    try:
        import markdown
    except ImportError:
        sys.exit("The homepage needs Python-Markdown (the `markdown` module): sudo apt install python3-markdown "
                 "on Debian / Ubuntu, else pip install markdown. (markdown2 is a different library.)")
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
                           extension_configs={"toc": {"slugify": github_slug, "toc_depth": "1"}, "codehilite": {"css_class": "highlight", "guess_lang": False}})
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


def split_sections(rendered: Rendered) -> List[Section]:
    """The rendered README cut at its top-level headings, one Section each, in order."""
    parts = re.split(r'(?=<h1 id=")', rendered.html)
    if not parts[0].startswith("<h1 "):   # what comes before the first heading (the banner) belongs to the first section
        parts[1:2] = [parts[0] + parts[1]]
        del parts[0]
    assert len(parts) == len(rendered.headings), (len(parts), len(rendered.headings))
    return [Section(str(h["id"]), str(h["name"]), "./" if k == 0 else f"{h['id']}.html", part)
            for k, (h, part) in enumerate(zip(rendered.headings, parts))]


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


def localize(html: str, root: Path, out: Path, repo: Repository) -> str:
    """Relative `src` and `href` targets in `html` name files of the repository at
    `root`: an image the page shows is copied into `out` under the same path, any
    other existing file or folder links to its page in `repo`. Unknown targets are
    left alone."""
    def repl(m: re.Match[str]) -> str:
        attr, target = m[1], m[2]
        path = (root / target.split("#")[0]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.exists():   # not a file of the repository (e.g. ../): left alone
            return m[0]
        if attr == "src" and path.is_file():
            (out / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, out / target)
            return m[0]
        return f'{attr}="{repo.url(target, folder=path.is_dir())}"'
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


def render_pages(readme: str, repo: Repository, root: Path, out: Path, panel: str, icons: IconLookup) -> Dict[str, str]:
    """The pages of the site, file name -> HTML: one per top-level heading of
    README.md, from template.html with the panel, the Contents sidebar (every
    section with its icon, this page's selected), the section with its icon in the
    heading, and Previous / Next links. A link to a heading of another section
    goes to that section's page."""
    sections = split_sections(render_markdown(readme))
    page_of: Dict[str, str] = {}   # heading id -> file
    for section in sections:
        for anchor in re.findall(r' id="([^"]+)"', section.html):
            page_of.setdefault(anchor, section.file)

    def cross_link(m: re.Match[str], here: Section) -> str:
        anchor = m[1]
        if page_of.get(anchor, here.file) == here.file:
            return m[0]
        return f'href="{page_of[anchor]}"' if anchor in {s.id for s in sections} else f'href="{page_of[anchor]}#{anchor}"'

    def icon(context: str, name: str, size: int, sizes: Tuple[int, ...] = (16, 48), theme: Optional[str] = None) -> str:
        """The icon's <img> at `size`, from `theme` (else the first that has it) drawing it at all of `sizes`."""
        return f'<img src="viewer/icons/{icons(context, name, sizes, theme)[size]}" width="{size}" height="{size}" alt="">'

    def section_icon(s: Section, size: int) -> str:
        theme, context, name = SECTION_ICONS.get(s.id, _DEFAULT_ICON)
        return icon(context, name, size, theme=theme)

    host = "GitHub" if "github" in repo.host else "GitLab" if "gitlab" in repo.host else repo.host
    template = (_HOMEPAGE_DIR / "template.html").read_text("utf-8")
    pages: Dict[str, str] = {}
    for k, section in enumerate(sections):
        html = re.sub(r'href="#([^"]+)"', lambda m: cross_link(m, section), localize(section.html, root, out, repo))   # localize first: "./" is a page here, not the repository's root
        html = html.replace(f'<h1 id="{section.id}">', f'<h1 id="{section.id}">{section_icon(section, 48)}', 1)
        for kind, (alert_context, alert_name) in ALERT_ICONS.items():   # the alerts' titles get their dialog icon
            html = html.replace(f'<p class="alert-title">{kind.capitalize()}</p>', f'<p class="alert-title">{icon(alert_context, alert_name, 22, (22,))}{kind.capitalize()}</p>')
        sidebar = "\n".join(
            f'<li><a href="{s.file}"{" class=\"current\"" if s is section else ""} title="{s.title}">'   # the title again as a tooltip: a long one is cut short in the list
            f'{section_icon(s, 16)}<span>{s.title}</span></a></li>'
            for s in sections)
        previous, following = (sections[k - 1] if k else None), (sections[k + 1] if k + 1 < len(sections) else None)
        pager = "".join([
            f'<a class="previous" href="{previous.file}">{icon("actions", "go-previous", 16, (16,))}Previous: {previous.title}</a>' if previous else "<span></span>",
            f'<a class="next" href="{following.file}">Next: {following.title}{icon("actions", "go-next", 16, (16,))}</a>' if following else "<span></span>"])
        page = template
        for key, value in [("repo_url", repo.web), ("repo_host", host), ("commit", repo.commit[:7]), ("date", date.today().isoformat()),
                           ("page_title", section.title if k == 0 else f"{section.title} - Tango Remixer"), ("title", section.title),
                           ("panel", panel), ("section_icon", section_icon(section, 16)), ("sidebar", sidebar), ("content", html), ("pager", pager)]:
            page = page.replace("{{" + key + "}}", value)
        pages["index.html" if k == 0 else section.file] = page
    return pages


def write_pages(out: Path, pages: Dict[str, str]) -> None:
    """The pages into `out`; a page of an earlier build that is no longer one (a
    section renamed or removed) goes, so a preview never shows a stale one."""
    for stale in out.glob("*.html"):
        if stale.name not in pages:
            stale.unlink()
    for file, html in pages.items():
        (out / file).write_text(html, "utf-8")


def generate(out: Path, root: Path = _PROJECT_ROOT) -> None:
    """The whole site into `out`."""
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    repo = site_repository(root)
    for name in ["style.css", "panel.css", "panel.js"]:
        shutil.copyfile(_HOMEPAGE_DIR / name, out / name)
    (out / "highlight.css").write_text(highlight_css(), "utf-8")
    shutil.copytree(_HOMEPAGE_DIR / "marks", out / "marks", dirs_exist_ok=True)   # the launchers' GitHub and GitLab marks, with their note
    themes = source_themes()
    index = build_index(themes)
    pages = render_pages((root / "README.md").read_text("utf-8"), repo, root, out, render_panel("", "home", repo), partial(icon_paths, index))
    write_pages(out, pages)
    urls: Dict[Path, str] = {}   # per source folder: the Blue* themes share their base theme's
    for theme in themes.values():
        urls.setdefault(theme.folder, source_url(theme.folder))
    total, written = export_viewer(themes, out / "viewer", {name: urls[theme.folder] for name, theme in themes.items()}, render_panel("../", "viewer", repo), index)
    print(f"{len(pages)} pages from README.md at {repo.web} ({repo.commit[:7]}). Viewer: {total} icons of {len(themes)} themes, "
          f"{written} written, the rest unchanged. {out} ready in {time.perf_counter() - started:.0f}s.", flush=True)


def main(argv: List[str]) -> None:
    generate(Path(argv[0]).resolve() if argv else _HOMEPAGE_DIR / "_build")


if __name__ == "__main__":
    main(sys.argv[1:])
