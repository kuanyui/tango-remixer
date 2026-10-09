#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the project website as plain files (no server), the way GitHub Pages
and GitLab Pages publish it:

    index.html, style.css     the homepage: README.md rendered into template.html
    tango-mixer-banner.svg    (and any other image README.md shows)
    viewer/                   the icon viewer (viewer/) as a static site: its page and
                              assets, api/index.json, and every indexed SVG under
                              icons/<theme>/<path>, the Blue* themes colorized with
                              the same code the build uses

Run:  python3 homepage/generate_static_site.py [OUT]     (default: homepage/_build/)
      make homepage-build        the same
      make homepage-dev-server   the same, then served on port 8000, on every interface as the viewer is
Needs Python-Markdown (the `markdown` module): `apt install python3-markdown` on
Debian / Ubuntu, else `pip install markdown`. (`markdown2` is a different library.)

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

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from viewer.server import _COLOR_CONVERTER, _STATIC_DIR, Colorizer, SourceTheme, build_index, index_json, source_themes  # noqa: E402

_HOMEPAGE_DIR: Path = Path(__file__).resolve().parent
_ALERTS: Tuple[str, ...] = ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION")
"""GitHub's `> [!NOTE]` blockquote kinds."""


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


def export_viewer(themes: Dict[str, SourceTheme], out: Path, urls: Dict[str, str]) -> Tuple[int, int]:
    """Write the viewer into `out`: index.html and static/ from viewer/static/,
    api/index.json with `urls[name]` as each theme's `url`, and icons/<theme>/<path>
    for every indexed file. Returns (icons in the site, icons written this time).

    A rerun is quick: a theme whose checkout is clean and at the commit of the last
    export (noted in .versions.json; for a Blue* theme together with the colorizer's
    mtime) is left as it is. Any other theme is compared file by file: an icon is
    rewritten when its source (or, for a Blue* theme, the colorizer) changed, and
    dropped when no longer indexed."""
    shutil.rmtree(out / "static", ignore_errors=True)
    shutil.copytree(_STATIC_DIR, out / "static", ignore=shutil.ignore_patterns("index.html"))   # llselect, clearlooks.css
    shutil.copyfile(_STATIC_DIR / "index.html", out / "index.html")
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


def render_markdown(text: str) -> str:
    """Markdown to HTML with Python-Markdown and its `extra` set (tables, fenced
    code, ...), plus what GitHub renders and it does not: `~~gone~~`, the
    `> [!NOTE]` alert blockquotes (NOTE, TIP, IMPORTANT, WARNING, CAUTION), a
    fenced code block inside a blockquote (made an indented one), and two
    blockquotes separated by a blank line (kept apart)."""
    try:
        import markdown
    except ImportError:
        sys.exit("The homepage needs Python-Markdown (the `markdown` module): sudo apt install python3-markdown "
                 "on Debian / Ubuntu, else pip install markdown. (markdown2 is a different library.)")
    lines: List[str] = []
    fence: Optional[str] = None   # inside a fenced block: the blockquote prefix it was opened with ("" outside a quote)
    quoted = False                # the last non-blank line was a blockquote line
    for line in text.splitlines(keepends=True):
        prefix, rest = re.match(r"(\s*(?:>\s*)*)(.*\n?)", line).groups()
        if rest.startswith("```"):
            if fence is None:
                fence = prefix
            else:
                fence = None
            if prefix.strip():   # an indented code block wants a blank quoted line on each side
                lines.append(prefix.rstrip() + "\n")
                continue
        elif fence is not None and fence.strip():
            lines.append(prefix + "    " + rest)
            continue
        elif fence is None:
            if prefix.strip() and quoted and lines and not lines[-1].strip():
                lines.append("<!-- -->\n")   # a blockquote after a blank line after a blockquote: keep it a second one
            line = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", line)
        if line.strip():
            quoted = bool(prefix.strip())
        lines.append(line)
    html: str = markdown.markdown("".join(lines), extensions=["extra", "toc"], extension_configs={"toc": {"slugify": github_slug}})

    def alert(m: re.Match[str]) -> str:
        head = f'<blockquote class="alert {m[1].lower()}">\n<p class="alert-title">{m[1].capitalize()}</p>'
        return head if m[2] == "</p>" else head + "\n<p>"   # the marker shared its paragraph with the text after it

    return re.sub(rf"<blockquote>\s*<p>\[!({'|'.join(_ALERTS)})\](</p>|\n)", alert, html)


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


def render_homepage(readme: str, repo: Repository, root: Path, out: Path) -> str:
    """index.html of the site: template.html with README.md rendered into it."""
    html = localize(render_markdown(readme), root, out, repo)
    host = "GitHub" if "github" in repo.host else "GitLab" if "gitlab" in repo.host else repo.host
    page = (_HOMEPAGE_DIR / "template.html").read_text("utf-8")
    for key, value in [("repo_url", repo.web), ("repo_host", host), ("commit", repo.commit[:7]), ("date", date.today().isoformat()), ("readme", html)]:
        page = page.replace("{{" + key + "}}", value)
    return page


def generate(out: Path, root: Path = _PROJECT_ROOT) -> None:
    """The whole site into `out`."""
    started = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    repo = site_repository(root)
    shutil.copyfile(_HOMEPAGE_DIR / "style.css", out / "style.css")
    (out / "index.html").write_text(render_homepage((root / "README.md").read_text("utf-8"), repo, root, out), "utf-8")
    themes = source_themes()
    urls: Dict[Path, str] = {}   # per source folder: the Blue* themes share their base theme's
    for theme in themes.values():
        urls.setdefault(theme.folder, source_url(theme.folder))
    total, written = export_viewer(themes, out / "viewer", {name: urls[theme.folder] for name, theme in themes.items()})
    print(f"Homepage from README.md at {repo.web} ({repo.commit[:7]}). Viewer: {total} icons of {len(themes)} themes, "
          f"{written} written, the rest unchanged. {out} ready in {time.perf_counter() - started:.0f}s.", flush=True)


def main(argv: List[str]) -> None:
    generate(Path(argv[0]).resolve() if argv else _HOMEPAGE_DIR / "_build")


if __name__ == "__main__":
    main(sys.argv[1:])
