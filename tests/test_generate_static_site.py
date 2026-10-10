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
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr
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

    def test_source_place_is_the_theme_folder_at_the_checked_out_commit(self) -> None:
        repo = Path(tempfile.mkdtemp()).resolve() / "repo"
        (repo / "src").mkdir(parents=True)
        git = lambda *args: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com",
                                            "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, text=True).stdout.strip()
        try:
            git("init", "-q")
            git("commit", "-q", "--allow-empty", "-m", "x")
            git("remote", "add", "origin", "git@github.com:owner/repo.git")
            commit = git("rev-parse", "HEAD")
            self.assertEqual(gen.source_place(repo / "src"), {"url": f"https://github.com/owner/repo/blob/{commit}/src", "repo": "https://github.com/owner/repo", "commit": commit})
            self.assertEqual(gen.source_place(repo)["url"], f"https://github.com/owner/repo/blob/{commit}")
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

    def test_a_list_straight_after_a_line_of_text_is_a_list(self) -> None:
        html = gen.render_markdown("> [!IMPORTANT]\n> - one\n> - two\n\nIntro:\n1. first\n2. second\n\nAnd:\n- a\n  - nested\n- b\n").html
        self.assertIn('<p class="alert-title">Important</p>\n<ul>\n<li>one</li>\n<li>two</li>\n</ul>', html)   # as GitHub renders it
        self.assertIn("<p>Intro:</p>\n<ol>\n<li>first</li>\n<li>second</li>\n</ol>", html)
        self.assertIn("<li>a<ul>\n<li>nested</li>\n</ul>\n</li>\n<li>b</li>", html)   # two spaces nest, as on GitHub
        self.assertNotIn("- one", html)
        quoted = gen.render_markdown("> Note:\n> - a\n>   - nested\n> - b\n").html
        self.assertIn("<p>Note:</p>\n<ul>\n<li>a<ul>\n<li>nested</li>\n</ul>\n</li>\n<li>b</li>\n</ul>", quoted)   # the same inside a blockquote
        indented = gen.render_markdown("> Note:\n>   - a\n>   - b\n").html
        self.assertIn("<p>Note:</p>\n<ul>\n<li>a</li>\n<li>b</li>\n</ul>", indented)   # indented after text: a list, not nested, not code
        siblings = gen.render_markdown("- a\n  - n1\n  - n2\n- b\n  - n3\n").html
        self.assertIn("<li>a<ul>\n<li>n1</li>\n<li>n2</li>\n</ul>\n</li>\n<li>b<ul>\n<li>n3</li>\n</ul>\n</li>", siblings)

    def test_markdown_renders_a_fenced_block_inside_a_blockquote(self) -> None:
        html = gen.render_markdown("> [!NOTE]\n> Like this:\n> ```sh\n> ./build.py --x\n> ```\n> The built files.\n").html
        self.assertIn('<p class="alert-title">Note</p>\n<p>Like this:</p>\n<div class="highlight"><pre><span></span><code>./build.py --x\n</code></pre></div>', html)
        self.assertIn('<p>The built files.</p>\n</blockquote>', html)
        self.assertNotIn("```", html)

    def test_markdown_leaves_out_what_the_document_hides_from_the_homepage(self) -> None:
        html = gen.render_markdown("# Top\n\n<!-- homepage-hide-begin -->\n> [!TIP]\n> Read it on the homepage.\n<!-- homepage-hide-end -->\n\n"
                                   "Intro.\n\n<!-- homepage-hide-begin -->\n> **Table of Contents**\n>\n> - [Top](#top)\n<!-- homepage-hide-end -->\n\n# Next\n").html
        self.assertEqual('<h1 id="top">Top</h1>\n<p>Intro.</p>\n<h1 id="next">Next</h1>', html)   # neither the tip nor the contents, nor the markers
        mention = gen.render_markdown("Put `<!-- homepage-hide-begin -->` on a line of its own.\n\n<!-- homepage-hide-end -->\n").html
        self.assertIn("on a line of its own", mention)   # a marker within a line hides nothing

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

    def test_write_pages_drops_a_page_that_is_no_longer_one(self) -> None:
        (self.out / "old-section.html").write_text("stale")
        (self.out / "style.css").write_text("kept")
        gen.write_pages(self.out, {"index.html": "<p>home</p>", "why.html": "<p>why</p>"})
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["index.html", "style.css", "why.html"])
        self.assertEqual((self.out / "why.html").read_text("utf-8"), "<p>why</p>")

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
        self.assertIn('<span>Tango Remixer</span>\n  </button>', panel)   # the main menu, named after the project
        self.assertIn('<img src="../viewer/icons/Nome/categories/16/system-help.svg" width="16" height="16" alt=""><span>Documentation</span>', panel)
        self.assertIn('<span>Icon Viewer</span>', panel)
        self.assertLess(panel.index('class="window-list"'), panel.index('<span class="tray"'))   # launchers in the notification area, before the clock
        self.assertLess(panel.index('<span class="tray"'), panel.index('class="panel-clock"'))
        self.assertEqual(panel.count('class="panel-button launcher"'), 2)
        self.assertGreater(panel.index('class="panel-button launcher"'), panel.index('<span class="tray"'))
        self.assertIn('class="panel-button task pressed" href="./"', gen.render_panel("", "home", gen.Repository("https://github.com/o/r", "abc")))

    def test_pages_fill_the_template_one_per_section_with_icons_and_links_across(self) -> None:
        icons = lambda context, name, sizes, prefer=None: {size: f"{prefer or 'Tango'}/{size}x{size}/{context}/{name}.svg" for size in sizes}
        pages = gen.render_pages("# Hi\n\nSee [the lsp](lsp/README.md), [why](#why) and [its part](#part).\n\n> [!NOTE]\n> noted\n\n# Why\n\nBecause. [Back](#hi)\n\n## Part\n",
                                 gen.Repository("https://gitlab.com/g/r", "abcdef0123"), self.root, self.out, '<div class="panel">P</div>', icons)
        self.assertEqual(list(pages), ["index.html", "why.html", "search-index.json"])
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
        self.assertIn('<p class="alert-title"><img src="viewer/icons/Tango/22x22/status/dialog-information.svg" width="22" height="22" alt="">Note</p>', home)
        self.assertIn('<a href="why.html">why</a>', home)             # another section: its page
        self.assertIn('<a href="why.html#part">its part</a>', home)   # a heading inside it: its page, at the heading
        self.assertIn('<a class="next" href="why.html">Next: Why<img', home)
        self.assertIn('<span></span>', home)   # no Previous on the first page
        self.assertIn("<title>Why - Tango Remixer</title>", why)
        self.assertIn('<span class="wm-title">Tango Remixer Documentation</span>', why)   # the window keeps its name
        self.assertIn('id="contents-combo" aria-haspopup="menu" aria-expanded="false" title="Contents: the sections of the documentation">'
                      '<img src="viewer/icons/Tango/16x16/apps/help-browser.svg" width="16" height="16" alt=""><span class="combo-text">Why</span>', why)   # the narrow window's combo box
        self.assertIn('<span class="wm-title">Tango Remixer Documentation</span>', home)
        self.assertIn('<span id="status">Why</span>', why)
        self.assertIn('<a href="why.html" class="current" title="Why">', why)
        self.assertIn('<h1 id="why"><img src="viewer/icons/Tango/48x48/apps/help-browser.svg" width="48" height="48" alt="">Why</h1>', why)
        self.assertIn('<a href="./">Back</a>', why)   # the first section's heading: the index page
        self.assertIn('<h2 id="part">Part</h2>', why)
        self.assertIn('<a class="previous" href="./"><img src="viewer/icons/Tango/16x16/actions/go-previous.svg" width="16" height="16" alt="">Previous: Hi</a>', why)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), [])   # nothing copied: no image in this README

    def test_a_second_document_gets_a_row_of_its_own_with_its_sections_under_it(self) -> None:
        icons = lambda context, name, sizes, prefer=None: {size: f"{prefer or 'Tango'}/{size}x{size}/{context}/{name}.svg" for size in sizes}
        lsp = gen.Document("lsp/README.md", "lsp", 2, "LSP server")
        pages = gen.render_pages([(gen.DOCUMENTS[0], "# Hi\n\nSee [the lsp](lsp/README.md).\n"),
                                  (lsp, "# LSP Server for `x`\n\nIntro.\n\n## Install\n\nPip. See [the setup](#editor-setup) and [the top](#lsp-server-for-x).\n\n## Editor Setup\n\n### Emacs\n\nE.\n")],
                                 gen.Repository("https://github.com/o/r", "abc"), self.root, self.out, "", icons)
        self.assertEqual(list(pages), ["index.html", "lsp.html", "lsp-install.html", "lsp-editor-setup.html", "search-index.json"])
        home, own, install, setup = pages["index.html"], pages["lsp.html"], pages["lsp-install.html"], pages["lsp-editor-setup.html"]
        self.assertIn('<a href="lsp.html">the lsp</a>', home)   # a document of the site: its first page, not the repository
        # the Contents: the README's pages at the top, the LSP server's own page a row, its sections rows under it
        self.assertIn('<li><a href="lsp.html" title="LSP Server for x"><img src="viewer/icons/Nome/16x16/categories/applications-development.svg" width="16" height="16" alt=""><span>LSP server</span></a>\n<ul>\n'
                      '<li><a href="lsp-install.html" title="Install"><img src="viewer/icons/Nome/16x16/apps/system-software-install.svg" width="16" height="16" alt=""><span>Install</span></a></li>\n'
                      '<li><a href="lsp-editor-setup.html" title="Editor Setup">', home)
        self.assertIn('</li>\n</ul></li>', home)
        self.assertIn('<a href="lsp.html" class="current" title="LSP Server for x">', own)
        self.assertIn("<title>LSP Server for x - Tango Remixer</title>", own)
        self.assertIn('<h1 id="lsp-server-for-x"><img src="viewer/icons/Nome/48x48/categories/applications-development.svg"', own)
        self.assertIn("<p>Intro.</p>", own)
        self.assertNotIn("<p>Pip.", own)
        # a section's page opens with an h1 (promoted from h2), and so on down
        self.assertIn('<h1 id="install"><img src="viewer/icons/Nome/48x48/apps/system-software-install.svg" width="48" height="48" alt="">Install</h1>', install)
        self.assertIn('<a href="lsp-editor-setup.html">the setup</a>', install)   # another page of the same document
        self.assertIn('<a href="lsp.html">the top</a>', install)                 # the document's own heading: its own page
        self.assertIn('<h2 id="emacs">Emacs</h2>', setup)
        self.assertIn('<a class="previous" href="lsp-install.html"><img src="viewer/icons/Tango/16x16/actions/go-previous.svg" width="16" height="16" alt="">Previous: Install</a>', setup)
        self.assertIn('Next: LSP server<img', home)   # the pager names the row
        self.assertEqual([(p["href"], p["title"]) for p in json.loads(pages["search-index.json"])],
                         [("./", "Hi"), ("lsp.html", "LSP server"), ("lsp-install.html", "Install"), ("lsp-editor-setup.html", "Editor Setup")])

    @unittest.skipUnless(all(raw.copied_src_theme_folder.is_dir() for raw in viewer_server.BUILT_IN_RAW_ICON_THEMES_PATH),
                         "theme submodules not checked out")
    def test_the_search_index_holds_every_page_with_its_text(self) -> None:
        icons = lambda context, name, sizes, prefer=None: {size: f"Tango/{size}x{size}/{context}/{name}.svg" for size in sizes}
        pages = gen.render_pages("# Hi\n\nSee [why](#why) &amp; `x < y`.\n\n# Why\n\nBecause.\n", gen.Repository("https://github.com/o/r", "abc"), self.root, self.out, "", icons)
        index = json.loads(pages["search-index.json"])
        self.assertEqual([(p["href"], p["title"]) for p in index], [("./", "Hi"), ("why.html", "Why")])
        self.assertEqual(index[0]["text"], "Hi See why & x < y.")   # tags dropped, entities read, whitespace folded
        self.assertEqual(index[1]["text"], "Why Because.")

    def test_every_section_and_alert_icon_is_drawn_at_its_own_size_from_one_theme(self) -> None:
        index = viewer_server.build_index(viewer_server.source_themes())
        for theme, context, name in [*gen.SECTION_ICONS.values(), gen._DEFAULT_ICON]:
            paths = gen.icon_paths(index, context, name, (16, 48), theme)
            for size, path in paths.items():
                self.assertTrue(path.startswith(theme + "/"), (theme, context, name, path))   # the theme named draws it at both sizes
                self.assertIn(f"/{size}x{size}/" if theme == "Tango" else f"/{size}/", path, (context, name, size, path))   # drawn at its size, no scaling
        for context, name in gen.ALERT_ICONS.values():
            self.assertRegex(gen.icon_paths(index, context, name, (22,))[22], r"^Nome/\w+/22/")   # Tango has these only at 32 and 48
        for name in ("go-previous", "go-next"):
            self.assertEqual(gen.icon_paths(index, "actions", name, (16,)), {16: f"Tango/16x16/actions/{name}.svg"})
        self.assertEqual(gen.icon_paths(index, "places", "folder-remote", (16, 48), "BlueHumanity"),
                         {16: "BlueHumanity/places/16/folder-remote.svg", 48: "BlueHumanity/places/48/folder-remote.svg"})   # the theme asked for
        self.assertEqual(gen.icon_paths(index, "places", "folder-remote", (16, 48))[16], "Nome/places/16/folder-remote.svg")   # else the first of THEMES that has both
        self.assertEqual(gen.icon_paths(index, "mimetypes", "package-x-generic", (16, 48), "Tango")[16], "Nome/mimetypes/16/package-x-generic.svg")   # Tango has 48 but no 16: the next with both
        self.assertEqual(gen.icon_paths(index, "status", "dialog-warning", (48,)), {48: "Tango/48x48/status/dialog-warning.svg"})   # Tango first when it has the size
        self.assertEqual(gen.icon_paths(index, "apps", "utilities-terminal", (20,)), {20: "Tango/22x22/apps/utilities-terminal.svg"})   # no one has 20: the next size up, Tango first
        self.assertEqual(gen.icon_paths(index, "apps", "web-browser", (48,)), {48: "Nome/apps/48/web-browser.svg"})   # not in Tango (which has internet-web-browser)
        with self.assertRaises(LookupError):
            gen.icon_paths(index, "apps", "no-such-icon", (16,))

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
        places = {"ThemeA": {"url": "https://github.com/o/a/blob/0123abc"}, "BlueA": {"url": "https://github.com/o/a/blob/0123abc"}}
        self.assertEqual(gen.export_viewer(self.themes, site, places), (4, 4))
        self.assertEqual((site / "index.html").read_bytes(), (viewer_server._STATIC_DIR / "index.html").read_bytes())   # no panel given: the page as is
        self.assertTrue((site / "static/llselect/index.umd.js").is_file())
        self.assertTrue((site / "static/clearlooks.css").is_file())
        self.assertFalse((site / "static/index.html").exists())
        data = json.loads((site / "api/index.json").read_bytes())
        self.assertEqual([(t["name"], t["url"]) for t in data["themes"]], [("ThemeA", places["ThemeA"]["url"]), ("BlueA", places["BlueA"]["url"])])
        self.assertTrue(all("folder" not in t for t in data["themes"]))
        self.assertNotIn(str(self.tmp), (site / "api/index.json").read_text())   # no path of this machine
        self.assertEqual(sorted(p.relative_to(site / "icons").as_posix() for p in (site / "icons").rglob("*.svg")),
                         ["BlueA/apps/16/foo.svg", "BlueA/apps/32/foo.svg", "ThemeA/apps/16/foo.svg", "ThemeA/apps/32/foo.svg"])
        self.assertEqual((site / "icons/ThemeA/apps/16/foo.svg").read_bytes(), _SVG)
        self.assertEqual((site / "icons/BlueA/apps/16/foo.svg").read_bytes(), _SVG.replace(b"#f57900", b"#3465a4"))
        # A rerun: unchanged sources are left alone, a file no longer indexed goes.
        (site / "icons/ThemeA/apps/16/stale.svg").write_bytes(_SVG)
        self.assertEqual(gen.export_viewer(self.themes, site, places), (4, 0))
        self.assertFalse((site / "icons/ThemeA/apps/16/stale.svg").exists())
        # A changed source is rewritten, plain and colorized.
        src = self.themes["ThemeA"].folder / "apps/32/foo.svg"
        src.write_bytes(_SVG.replace(b"16", b"32"))
        later = src.stat().st_mtime_ns + 5_000_000_000
        os.utime(src, ns=(later, later))
        self.assertEqual(gen.export_viewer(self.themes, site, places), (4, 2))
        self.assertEqual((site / "icons/BlueA/apps/32/foo.svg").read_bytes(), _SVG.replace(b"16", b"32").replace(b"#f57900", b"#3465a4"))
        self.assertEqual(gen.export_viewer(self.themes, site, places), (4, 0))
        self.assertEqual(json.loads((site / ".versions.json").read_text()), {})   # not a checkout: compared file by file every time

    def test_export_puts_the_panel_above_the_viewer_window(self) -> None:
        site, places = self.tmp / "viewer3", {"ThemeA": {"url": "https://github.com/o/a/blob/0123abc"}, "BlueA": {"url": "https://github.com/o/a/blob/0123abc"}}
        gen.export_viewer(self.themes, site, places, panel='<div class="panel">P</div>')
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
        site, places = self.tmp / "viewer2", {"R": {"url": "https://github.com/o/r/blob/abc"}, "BlueR": {"url": "https://github.com/o/r/blob/abc"}}
        self.assertEqual(gen.export_viewer(themes, site, places), (2, 2))
        versions = json.loads((site / ".versions.json").read_text())
        self.assertEqual(versions["R"], git("rev-parse", "HEAD"))
        self.assertTrue(versions["BlueR"].startswith(git("rev-parse", "HEAD") + "+"))
        (site / "icons/R/apps/16/stale.svg").write_bytes(_SVG)
        self.assertEqual(gen.export_viewer(themes, site, places), (2, 0))
        self.assertTrue((site / "icons/R/apps/16/stale.svg").exists())   # the theme was skipped, not compared
        (repo / "apps/16/foo.svg").write_bytes(_SVG.replace(b"16", b"24"))   # work in progress: compared file by file
        self.assertEqual(gen.export_viewer(themes, site, places), (2, 2))
        self.assertFalse((site / "icons/R/apps/16/stale.svg").exists())
        self.assertNotIn("R", json.loads((site / ".versions.json").read_text()))
        git("commit", "-q", "-a", "-m", "y")
        self.assertEqual(gen.export_viewer(themes, site, places), (2, 0))   # clean again: files already match
        self.assertEqual(json.loads((site / ".versions.json").read_text())["R"], git("rev-parse", "HEAD"))


class TestSiteServer(unittest.TestCase):
    """--serve: the generated folder over HTTP, the viewer's icon requests kept out of the terminal."""

    def test_serves_the_folder_quietly(self) -> None:
        out = Path(tempfile.mkdtemp()).resolve()
        (out / "index.html").write_text("<p>hi</p>", "utf-8")
        server = gen.site_server(out, 0)   # any free port
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            with redirect_stderr(io.StringIO()) as log:
                with urllib.request.urlopen(f"{base}/index.html") as res:
                    self.assertEqual(res.read(), b"<p>hi</p>")
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(f"{base}/missing.html")
            self.assertEqual(caught.exception.code, 404)
            self.assertEqual(log.getvalue(), "")   # no request log, not even for the 404
        finally:
            server.shutdown()
            server.server_close()
            shutil.rmtree(out)


class TestWatch(unittest.TestCase):
    """The dev server's watch: which files count, and a settled change calling for a rebuild."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()
        for rel in ["README.md", "lib/color_converter.py", "homepage/style.css", "homepage/marks/x.svg", "homepage/_build/index.html",
                    "homepage/__pycache__/x.pyc", "homepage/site/index.html", "viewer/static/window.css", "viewer/static/llselect/a.js",
                    "viewer/server.py", "build_icons.py"]:
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text("x", "utf-8")
        self.out = self.root / "homepage" / "site"   # a site written inside homepage/ is not a source either

    def tearDown(self) -> None:
        shutil.rmtree(self.root)

    def test_watched_sources_are_what_the_pages_are_made_from(self) -> None:
        found = {p.relative_to(self.root).as_posix() for p in gen.watched_sources(self.root, self.out)}
        self.assertEqual(found, {"README.md", "build_icons.py", "lib/color_converter.py", "viewer/server.py", "homepage/style.css",
                                 "homepage/marks/x.svg", "viewer/static/window.css", "viewer/static/llselect/a.js"})

    def test_a_change_to_the_code_restarts_to_the_colorizer_redoes_the_icons_else_the_pages(self) -> None:
        root = self.root
        self.assertEqual(gen.rebuild_plan([root / "README.md", root / "homepage" / "style.css"], root), "pages")
        self.assertEqual(gen.rebuild_plan([root / "lib" / "color_converter.py", root / "README.md"], root), "icons")
        for code in ["homepage/generate_static_site.py", "viewer/server.py", "build_icons.py", "lib/included_icons_tokens.py"]:
            self.assertEqual(gen.rebuild_plan([root / "lib" / "color_converter.py", root / code], root), "restart", code)

    def test_a_settled_change_calls_for_a_rebuild_with_the_changed_files(self) -> None:
        calls, done, stop = [], threading.Event(), threading.Event()

        def rebuild(changed):
            calls.append(changed)
            done.set()

        threading.Thread(target=gen.watch, args=(self.root, self.out, rebuild, 0.05, stop), daemon=True).start()
        time.sleep(0.3)   # the first snapshot is taken
        (self.root / "homepage" / "style.css").write_text("changed", "utf-8")
        (self.out / "index.html").write_text("the output changing is not a change", "utf-8")
        self.assertTrue(done.wait(5))
        stop.set()
        self.assertEqual(calls, [[self.root / "homepage" / "style.css"]])


if __name__ == "__main__":
    unittest.main()
