#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for homepage/generate_static_site.py: the repository URLs it links to
(GitHub and GitLab forms, CI environment or checkout), the homepage rendered
from a README (GitHub's alerts, strikethrough and heading ids; links and images
of the repository; the template), and the viewer export (real files only,
rewritten only when changed).

The theme folders are synthetic; skipped where symlinks cannot be created. The
homepage tests are skipped without the Python-Markdown package."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "homepage"))

import generate_static_site as gen  # noqa: E402
from viewer import server as viewer_server  # noqa: E402
from viewer.server import SourceTheme  # noqa: E402

_SVG: bytes = b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16" fill="#f57900"/></svg>'


def _blueish(svg_text: str, icon_name: str) -> str:
    """Stand-in for the real colorizers: same signature, visible effect."""
    return svg_text.replace("#f57900", "#3465a4")


class TestRepositoryUrls(unittest.TestCase):

    def test_web_url_accepts_ssh_and_https_remotes(self) -> None:
        for remote in ["git@github.com:kuanyui/nome-icon-theme.git", "git@github.com:kuanyui/nome-icon-theme",
                       "https://github.com/kuanyui/nome-icon-theme.git", "https://github.com/kuanyui/nome-icon-theme/",
                       "https://gitlab-ci-token:s3cret@github.com/kuanyui/nome-icon-theme.git"]:   # a token in the URL is dropped
            self.assertEqual(gen.web_url(remote), "https://github.com/kuanyui/nome-icon-theme", remote)
        self.assertEqual(gen.web_url("git@gitlab.com:group/sub/project.git"), "https://gitlab.com/group/sub/project")
        with self.assertRaises(ValueError):
            gen.web_url("/home/me/repo")

    def test_file_and_folder_pages_on_github_and_gitlab(self) -> None:
        github = gen.Repository("https://github.com/o/r", "abc")
        self.assertEqual(github.url("a/b.svg"), "https://github.com/o/r/blob/abc/a/b.svg")
        self.assertEqual(github.url("dir", folder=True), "https://github.com/o/r/tree/abc/dir")
        self.assertEqual(github.url(), "https://github.com/o/r/blob/abc")
        gitlab = gen.Repository("https://gitlab.com/g/r", "abc")
        self.assertEqual(gitlab.url("a/b.svg"), "https://gitlab.com/g/r/-/blob/abc/a/b.svg")
        self.assertEqual(gitlab.url("dir", folder=True), "https://gitlab.com/g/r/-/tree/abc/dir")

    def test_source_url_is_the_theme_folder_at_the_checked_out_commit(self) -> None:
        repo = Path(tempfile.mkdtemp()).resolve() / "repo"
        (repo / "src").mkdir(parents=True)
        git = lambda *args: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com",
                                            "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, text=True).stdout.strip()
        try:
            git("init", "-q")
            git("commit", "-q", "--allow-empty", "-m", "x")
            git("remote", "add", "origin", "git@github.com:owner/repo.git")
            commit = git("rev-parse", "HEAD")
            self.assertEqual(gen.source_url(repo / "src"), f"https://github.com/owner/repo/blob/{commit}/src")
            self.assertEqual(gen.source_url(repo), f"https://github.com/owner/repo/blob/{commit}")
        finally:
            shutil.rmtree(repo.parent)

    def test_site_repository_prefers_the_ci_environment(self) -> None:
        with mock.patch.dict(os.environ, {"CI_PROJECT_URL": "https://gitlab.com/g/r", "CI_COMMIT_SHA": "f00"}, clear=True):
            self.assertEqual(gen.site_repository(Path("/nowhere")), gen.Repository("https://gitlab.com/g/r", "f00"))
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "o/r", "GITHUB_SHA": "f00"}, clear=True):
            self.assertEqual(gen.site_repository(Path("/nowhere")), gen.Repository("https://github.com/o/r", "f00"))


@unittest.skipUnless(importlib.util.find_spec("markdown"), "Python-Markdown not installed (apt install python3-markdown / pip install markdown)")
class TestHomepage(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp: Path = Path(tempfile.mkdtemp()).resolve()
        self.root: Path = self.tmp / "root"
        self.out: Path = self.tmp / "out"
        (self.root / "lsp").mkdir(parents=True)
        (self.root / "lsp" / "README.md").write_text("lsp")
        (self.root / "banner.svg").write_bytes(_SVG)
        self.out.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_heading_ids_follow_github(self) -> None:
        for heading, slug in [("Used Submodules / Thirdparties Tarballs", "used-submodules--thirdparties-tarballs"),
                              ("How to Use in Qt Project?", "how-to-use-in-qt-project"), ("Build .svg and .qrc", "build-svg-and-qrc"),
                              ("1. Clone this project into MY_QT_PROJ/resources/", "1-clone-this-project-into-my_qt_projresources")]:
            self.assertEqual(gen.github_slug(heading, "-"), slug)

    def test_markdown_renders_alerts_strikethrough_and_heading_ids(self) -> None:
        html = gen.render_markdown("# Used Submodules / Thirdparties Tarballs\n\n> [!WARNING]\n> ## Disclosure\n> text ~~gone~~ here\n\n"
                                   "> [!CAUTION]\n> same paragraph\n\n```sh\n~~kept~~\n```\n").html
        self.assertIn('<h1 id="used-submodules--thirdparties-tarballs">', html)
        self.assertIn('<blockquote class="alert warning">\n<p class="alert-title">Warning</p>', html)
        self.assertIn('<blockquote class="alert caution">\n<p class="alert-title">Caution</p>\n<p>same paragraph</p>', html)   # a second blockquote, as on GitHub
        self.assertIn("text <del>gone</del> here", html)
        self.assertIn("~~kept~~", html)   # inside a code fence
        self.assertNotIn("[!", html)

    def test_markdown_renders_a_fenced_block_inside_a_blockquote(self) -> None:
        html = gen.render_markdown("> [!NOTE]\n> Like this:\n> ```sh\n> ./build.py --x\n> ```\n> The built files.\n").html
        self.assertIn('<p class="alert-title">Note</p>\n<p>Like this:</p>\n<div class="highlight"><pre><span></span><code>./build.py --x\n</code></pre></div>', html)
        self.assertIn('<p>The built files.</p>\n</blockquote>', html)
        self.assertNotIn("```", html)

    def test_markdown_lists_the_top_level_headings_and_sections_split_there(self) -> None:
        rendered = gen.render_markdown("banner\n\n# Top A\n\n## Mid B\n\n### Low C\n\ntext\n\n# License**s**\n\nend\n")
        self.assertEqual([(h["id"], h["name"]) for h in rendered.headings], [("top-a", "Top A"), ("licenses", "Licenses")])
        self.assertIn('<h2 id="mid-b">Mid B</h2>', rendered.html)   # an anchor, not a section
        sections = gen.split_sections(rendered)
        self.assertEqual([(s.id, s.title, s.file) for s in sections], [("top-a", "Top A", "./"), ("licenses", "Licenses", "licenses.html")])
        self.assertTrue(sections[0].html.startswith('<p>banner</p>\n<h1 id="top-a">'))   # the banner belongs to the first section
        self.assertIn('<h3 id="low-c">', sections[0].html)
        self.assertTrue(sections[1].html.startswith('<h1 id="licenses">License<strong>s</strong></h1>'))
        self.assertTrue(sections[1].html.rstrip().endswith("<p>end</p>"))
    @unittest.skipUnless(importlib.util.find_spec("pygments"), "Pygments not installed (apt install python3-pygments / pip install pygments)")
    def test_code_blocks_are_coloured_by_pygments_under_the_names_it_knows(self) -> None:
        html = gen.render_markdown("```cpp\nint main() { return 0; }\n```\n\n```cmakelists\ncmake_minimum_required(VERSION 3.16)\n```\n\n```conf\nTango    document-save\n```\n").html
        self.assertIn('<div class="highlight"><pre><span></span><code><span class="kt">int</span>', html)   # C++
        self.assertIn('<span class="nb">cmake_minimum_required</span>', html)                              # cmakelists, read as cmake
        self.assertIn('<div class="highlight"><pre><span></span><code>Tango    document-save\n</code></pre></div>', html)   # no lexer: plain
        css = gen.highlight_css()
        self.assertIn(".highlight .kt {", css)
        self.assertIn("body.dark .highlight .kt {", css)

    def test_included_icons_examples_are_coloured_by_the_projects_own_tokenizer(self) -> None:
        html = gen.highlight_included_icons("# @extra-icon-theme MyIcons ../foo\nTango    places/folder    {16>32}   # tail\n")
        self.assertEqual(html, '<div class="highlight"><pre><span></span><code>'
                               '<span class="ii-comment">#</span> <span class="ii-directive">@extra-icon-theme</span> <span class="ii-theme">MyIcons</span> <span class="ii-string">../foo</span>\n'
                               '<span class="ii-theme ii-builtin">Tango</span>    <span class="ii-context">places</span>/<span class="ii-icon">folder</span>    '
                               '{<span class="ii-input_size">16</span><span class="ii-operator">&gt;</span><span class="ii-output_size">32</span>}   <span class="ii-comment"># tail</span>\n'
                               '</code></pre></div>')
        page = gen.render_markdown("text\n\n```included-icons\nTango    document-save\n\n# <b>\n```\n\nafter\n").html
        self.assertIn('<p>text</p>\n<div class="highlight"><pre><span></span><code><span class="ii-theme ii-builtin">Tango</span>    <span class="ii-icon">document-save</span>\n\n'
                      '<span class="ii-comment"># &lt;b&gt;</span>\n</code></pre></div>', page)
        self.assertIn("<p>after</p>", page)
        self.assertNotIn("language-included-icons", page)

    def test_localize_copies_images_and_links_repository_files(self) -> None:
        repo = gen.Repository("https://github.com/o/r", "abc")
        html = ('<img src="banner.svg" alt=""> <a href="lsp/README.md">file</a> <a href="lsp">folder</a> <a href="https://x.y/z">web</a> '
                '<a href="#why">anchor</a> <a href="missing.md">gone</a> <img src="https://x.y/i.png">')
        self.assertEqual(gen.localize(html, self.root, self.out, repo),
                         '<img src="banner.svg" alt=""> <a href="https://github.com/o/r/blob/abc/lsp/README.md">file</a> '
                         '<a href="https://github.com/o/r/tree/abc/lsp">folder</a> <a href="https://x.y/z">web</a> '
                         '<a href="#why">anchor</a> <a href="missing.md">gone</a> <img src="https://x.y/i.png">')
        self.assertEqual((self.out / "banner.svg").read_bytes(), _SVG)
        # A target outside the repository is neither copied nor linked, even when it exists.
        (self.tmp / "outside.svg").write_bytes(_SVG)
        html = '<img src="../outside.svg"> <a href="../outside.svg">x</a>'
        self.assertEqual(gen.localize(html, self.root, self.out, repo), html)
        self.assertFalse((self.tmp / "out" / ".." / "outside.svg").resolve().is_relative_to(self.out))
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["banner.svg"])

    def test_panel_marks_the_window_of_the_page(self) -> None:
        panel = gen.render_panel("../", "viewer", gen.Repository("https://github.com/o/r", "abcdef0123"))
        self.assertNotIn("{{", panel)
        self.assertIn('class="panel-button task" href=".././"', panel)               # the homepage, not pressed
        self.assertIn('class="panel-button task pressed" href="../viewer/"', panel)   # this page's window
        self.assertIn('<span class="mark github"></span>', panel)
        self.assertFalse(panel.endswith("\n"))
        self.assertIn('src="../viewer/icons/Tango/22x22/places/start-here.svg"', panel)
        self.assertIn("abcdef0</span>", panel)
        self.assertIn('<span>Applications</span>\n  </button>', panel)
        self.assertLess(panel.index('class="window-list"'), panel.index('<span class="tray"'))   # launchers in the notification area, before the clock
        self.assertLess(panel.index('<span class="tray"'), panel.index('class="panel-clock"'))
        self.assertEqual(panel.count('class="panel-button launcher"'), 2)
        self.assertGreater(panel.index('class="panel-button launcher"'), panel.index('<span class="tray"'))
        self.assertIn('class="panel-button task pressed" href="./"', gen.render_panel("", "home", gen.Repository("https://github.com/o/r", "abc")))

    def test_pages_fill_the_template_one_per_section_with_icons_and_links_across(self) -> None:
        icons = lambda context, name, size: f"Tango/{size}x{size}/{context}/{name}.svg"
        pages = gen.render_pages("# Hi\n\nSee [the lsp](lsp/README.md), [why](#why) and [its part](#part).\n\n# Why\n\nBecause. [Back](#hi)\n\n## Part\n",
                                 gen.Repository("https://gitlab.com/g/r", "abcdef0123"), self.root, self.out, '<div class="panel">P</div>', icons)
        self.assertEqual(list(pages), ["index.html", "why.html"])
        home, why = pages["index.html"], pages["why.html"]
        for page in (home, why):
            self.assertNotIn("{{", page)
            self.assertIn('<div class="panel">P</div>\n<div class="window">', page)
            self.assertIn('<nav class="menubar" id="menubar"></nav>', page)
            self.assertIn('href="https://gitlab.com/g/r" target="_blank" rel="noopener">Source on GitLab</a>', page)
            self.assertIn("commit abcdef0,", page)
            # the sidebar: every section, with its icon at 16 px (the default one for headings SECTION_ICONS does not know)
            self.assertIn('<li><a href="./"', page)
            self.assertIn('<img src="viewer/icons/Tango/16x16/mimetypes/text-x-generic.svg" width="16" height="16" alt=""><span>Hi</span></a></li>', page)
            self.assertIn('<img src="viewer/icons/Tango/16x16/apps/help-browser.svg" width="16" height="16" alt=""><span>Why</span></a></li>', page)
        self.assertIn("<title>Hi</title>", home)
        self.assertIn('<a href="./" class="current" title="Hi">', home)
        self.assertIn('<h1 id="hi"><img src="viewer/icons/Tango/48x48/mimetypes/text-x-generic.svg" width="48" height="48" alt="">Hi</h1>', home)
        self.assertIn('<a href="https://gitlab.com/g/r/-/blob/abcdef0123/lsp/README.md">the lsp</a>', home)
        self.assertIn('<a href="why.html">why</a>', home)             # another section: its page
        self.assertIn('<a href="why.html#part">its part</a>', home)   # a heading inside it: its page, at the heading
        self.assertIn('<a class="next" href="why.html">Next: Why<img', home)
        self.assertIn('<span></span>', home)   # no Previous on the first page
        self.assertIn("<title>Why - Tango Remixer</title>", why)
        self.assertIn('<span class="wm-title">Tango Remixer Documentation</span>', why)   # the window keeps its name
        self.assertIn('<span class="wm-title">Tango Remixer Documentation</span>', home)
        self.assertIn('<span id="status">Why</span>', why)
        self.assertIn('<a href="why.html" class="current" title="Why">', why)
        self.assertIn('<h1 id="why"><img src="viewer/icons/Tango/48x48/apps/help-browser.svg" width="48" height="48" alt="">Why</h1>', why)
        self.assertIn('<a href="./">Back</a>', why)   # the first section's heading: the index page
        self.assertIn('<h2 id="part">Part</h2>', why)
        self.assertIn('<a class="previous" href="./"><img src="viewer/icons/Tango/16x16/actions/go-previous.svg" width="16" height="16" alt="">Previous: Hi</a>', why)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), [])   # nothing copied: no image in this README

    @unittest.skipUnless(all(raw.copied_src_theme_folder.is_dir() for raw in viewer_server.BUILT_IN_RAW_ICON_THEMES_PATH),
                         "theme submodules not checked out")
    def test_every_section_icon_exists_in_tango_or_nome_at_both_sizes(self) -> None:
        index = viewer_server.build_index(viewer_server.source_themes())
        for context, name in [*gen.SECTION_ICONS.values(), gen._DEFAULT_ICON, ("actions", "go-previous"), ("actions", "go-next")]:
            for size in (16, 48):
                path = gen.icon_path(index, context, name, size)
                self.assertTrue(path.startswith("Tango/"), (context, name, path))   # the chosen ones all come from Tango
        self.assertEqual(gen.icon_path(index, "places", "start-here", 16), "Tango/16x16/places/start-here.svg")
        self.assertEqual(gen.icon_path(index, "mimetypes", "package-x-generic", 16), "Tango/32x32/mimetypes/package-x-generic.svg")   # no 16 or 22: the next size up
        tango = {(e["context"], e["name"]) for e in index if e["theme"] == "Tango"}
        nome_only = next(e for e in index if e["theme"] == "Nome" and (e["context"], e["name"]) not in tango)
        self.assertTrue(gen.icon_path(index, nome_only["context"], nome_only["name"], 48).startswith("Nome/"))   # Tango lacks it: Nome
        with self.assertRaises(LookupError):
            gen.icon_path(index, "apps", "no-such-icon", 16)

class TestViewerExport(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp: Path = Path(tempfile.mkdtemp()).resolve()
        a: Path = cls.tmp / "ThemeA"
        for rel in ["apps/16/foo.svg", "apps/32/foo.svg"]:
            (a / rel).parent.mkdir(parents=True, exist_ok=True)
            (a / rel).write_bytes(_SVG)
        try:
            os.symlink("foo.svg", a / "apps/16/bar.svg")   # alias: a name, not a file of the site
        except OSError as e:
            raise unittest.SkipTest(f"symlinks not supported here: {e}")
        cls.themes = {
            "ThemeA": SourceTheme(a, None, "Group A", "apps/16/foo.svg", "MIT", "synthetic A", False),
            "BlueA": SourceTheme(a, _blueish, "Group A", "apps/16/foo.svg", "MIT", "A, colorized", False),
        }

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp)

    def test_export_writes_real_files_only_and_rewrites_only_what_changed(self) -> None:
        site = self.tmp / "viewer"
        urls = {"ThemeA": "https://github.com/o/a/blob/0123abc", "BlueA": "https://github.com/o/a/blob/0123abc"}
        self.assertEqual(gen.export_viewer(self.themes, site, urls), (4, 4))
        self.assertEqual((site / "index.html").read_bytes(), (viewer_server._STATIC_DIR / "index.html").read_bytes())   # no panel given: the page as is
        self.assertTrue((site / "static/llselect/index.umd.js").is_file())
        self.assertTrue((site / "static/clearlooks.css").is_file())
        self.assertFalse((site / "static/index.html").exists())
        data = json.loads((site / "api/index.json").read_bytes())
        self.assertEqual([(t["name"], t["url"]) for t in data["themes"]], [("ThemeA", urls["ThemeA"]), ("BlueA", urls["BlueA"])])
        self.assertTrue(all("folder" not in t for t in data["themes"]))
        self.assertNotIn(str(self.tmp), (site / "api/index.json").read_text())   # no path of this machine
        self.assertEqual(sorted(p.relative_to(site / "icons").as_posix() for p in (site / "icons").rglob("*.svg")),
                         ["BlueA/apps/16/foo.svg", "BlueA/apps/32/foo.svg", "ThemeA/apps/16/foo.svg", "ThemeA/apps/32/foo.svg"])
        self.assertEqual((site / "icons/ThemeA/apps/16/foo.svg").read_bytes(), _SVG)
        self.assertEqual((site / "icons/BlueA/apps/16/foo.svg").read_bytes(), _SVG.replace(b"#f57900", b"#3465a4"))
        # A rerun: unchanged sources are left alone, a file no longer indexed goes.
        (site / "icons/ThemeA/apps/16/stale.svg").write_bytes(_SVG)
        self.assertEqual(gen.export_viewer(self.themes, site, urls), (4, 0))
        self.assertFalse((site / "icons/ThemeA/apps/16/stale.svg").exists())
        # A changed source is rewritten, plain and colorized.
        src = self.themes["ThemeA"].folder / "apps/32/foo.svg"
        src.write_bytes(_SVG.replace(b"16", b"32"))
        later = src.stat().st_mtime_ns + 5_000_000_000
        os.utime(src, ns=(later, later))
        self.assertEqual(gen.export_viewer(self.themes, site, urls), (4, 2))
        self.assertEqual((site / "icons/BlueA/apps/32/foo.svg").read_bytes(), _SVG.replace(b"16", b"32").replace(b"#f57900", b"#3465a4"))
        self.assertEqual(gen.export_viewer(self.themes, site, urls), (4, 0))
        self.assertEqual(json.loads((site / ".versions.json").read_text()), {})   # not a checkout: compared file by file every time

    def test_export_puts_the_panel_above_the_viewer_window(self) -> None:
        site, urls = self.tmp / "viewer3", {"ThemeA": "https://github.com/o/a/blob/0123abc", "BlueA": "https://github.com/o/a/blob/0123abc"}
        gen.export_viewer(self.themes, site, urls, panel='<div class="panel">P</div>')
        page = (site / "index.html").read_text("utf-8")
        for once in ['<link rel="stylesheet" href="../panel.css">\n</head>', '<body>\n<div class="panel">P</div>\n<div class="window">',
                     '<script src="../panel.js"></script>\n</body>']:
            self.assertEqual(page.count(once), 1, once)
        self.assertNotIn('class="panel"', (viewer_server._STATIC_DIR / "index.html").read_text("utf-8"))   # the viewer page itself knows no panel

    def test_export_skips_a_clean_theme_at_the_commit_of_the_last_export(self) -> None:
        repo = self.tmp / "repo"
        (repo / "apps/16").mkdir(parents=True)
        (repo / "apps/16/foo.svg").write_bytes(_SVG)
        git = lambda *args: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com",
                                            "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, text=True).stdout.strip()
        git("init", "-q")
        git("remote", "add", "origin", "git@github.com:owner/repo.git")
        git("add", "."), git("commit", "-q", "-m", "x")
        themes = {"R": SourceTheme(repo, None, "G", "apps/16/foo.svg", "MIT", "r", False),
                  "BlueR": SourceTheme(repo, _blueish, "G", "apps/16/foo.svg", "MIT", "r", False)}
        site, urls = self.tmp / "viewer2", {"R": "https://github.com/o/r/blob/abc", "BlueR": "https://github.com/o/r/blob/abc"}
        self.assertEqual(gen.export_viewer(themes, site, urls), (2, 2))
        versions = json.loads((site / ".versions.json").read_text())
        self.assertEqual(versions["R"], git("rev-parse", "HEAD"))
        self.assertTrue(versions["BlueR"].startswith(git("rev-parse", "HEAD") + "+"))
        (site / "icons/R/apps/16/stale.svg").write_bytes(_SVG)
        self.assertEqual(gen.export_viewer(themes, site, urls), (2, 0))
        self.assertTrue((site / "icons/R/apps/16/stale.svg").exists())   # the theme was skipped, not compared
        (repo / "apps/16/foo.svg").write_bytes(_SVG.replace(b"16", b"24"))   # work in progress: compared file by file
        self.assertEqual(gen.export_viewer(themes, site, urls), (2, 2))
        self.assertFalse((site / "icons/R/apps/16/stale.svg").exists())
        self.assertNotIn("R", json.loads((site / ".versions.json").read_text()))
        git("commit", "-q", "-a", "-m", "y")
        self.assertEqual(gen.export_viewer(themes, site, urls), (2, 0))   # clean again: files already match
        self.assertEqual(json.loads((site / ".versions.json").read_text())["R"], git("rev-parse", "HEAD"))


if __name__ == "__main__":
    unittest.main()
