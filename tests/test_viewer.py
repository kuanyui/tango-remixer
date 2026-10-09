#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for viewer/server.py: source scanning (both folder layouts, symlink
aliases, alias chains, dangling links, scale-2 folders), on-the-fly
colorizing of a Blue*-style variant, static serving, and the `/api/open`
guard rails (token + path allowlist); and that every icon the page names by
path is a real file (the static export in homepage/generate_static_site.py,
tested in tests/test_generate_static_site.py, writes only those).

The theme folders are synthetic. The file-manager call is replaced by a
recorder, so nothing is opened on the desktop. Skipped where symlinks
cannot be created (Windows without developer mode).
"""

import http.client
import importlib
import ipaddress
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from viewer import server as viewer_server  # noqa: E402
from viewer.server import SourceTheme  # noqa: E402

_SVG: bytes = b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16" fill="#f57900"/></svg>'
_TOKEN: str = "test-token"
_REAL_OPEN = viewer_server.open_on_host   # kept at module level: a function stored on the class would bind `self`


def _blueish(svg_text: str, icon_name: str) -> str:
    """Stand-in for the real colorizers: same signature, visible effect."""
    return svg_text.replace("#f57900", "#3465a4")


class TestViewer(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp: Path = Path(tempfile.mkdtemp()).resolve()
        a: Path = cls.tmp / "ThemeA"   # `<context>/<size>` layout, with symlinks
        b: Path = cls.tmp / "ThemeB"   # XDG `<size>x<size>/<context>` layout
        for rel in ["apps/16/foo.svg", "apps/32/foo.svg", "apps/16@2/foo.svg", "actions/scalable/edit.svg"]:
            (a / rel).parent.mkdir(parents=True, exist_ok=True)
            (a / rel).write_bytes(_SVG)
        (a / "apps/22").mkdir()
        (b / "16x16/actions").mkdir(parents=True)
        (b / "16x16/actions/bar.svg").write_bytes(_SVG)
        (cls.tmp / "outside.svg").write_bytes(_SVG)
        try:
            os.symlink("foo.svg", a / "apps/16/bar.svg")          # alias
            os.symlink("bar.svg", a / "apps/16/baz.svg")          # alias of an alias
            os.symlink("../16/foo.svg", a / "apps/32/qux.svg")    # alias living in another size folder
            os.symlink("../16/foo.svg", a / "apps/22/foo.svg")    # same name in another size: neither size nor alias
            os.symlink("missing.svg", a / "apps/16/gone.svg")     # dangling
        except OSError as e:
            raise unittest.SkipTest(f"symlinks not supported here: {e}")

        cls.themes = {
            "ThemeA": SourceTheme(a, None, "Group A", "apps/16/foo.svg", "MIT", "synthetic A", False),
            "ThemeB": SourceTheme(b, None, "Group B", "16x16/actions/bar.svg", "MIT", "synthetic B", True),
            "BlueA": SourceTheme(a, _blueish, "Group A", "apps/16/foo.svg", "MIT", "A, colorized", False),
        }
        cls.calls: List[Tuple[Path, str]] = []
        viewer_server.open_on_host = lambda target, action: cls.calls.append((target, action))

        cls.index = viewer_server.build_index(cls.themes)
        cls.server = viewer_server.make_server(cls.themes, _TOKEN, cls.index)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        viewer_server.open_on_host = _REAL_OPEN
        shutil.rmtree(cls.tmp)

    def setUp(self) -> None:
        self.calls.clear()

    def request(self, method: str, path: str, body: Any = None, token: Optional[str] = None) -> http.client.HTTPResponse:
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1])
        headers = {viewer_server.TOKEN_HEADER: token} if token else {}
        conn.request(method, path, body=None if body is None else json.dumps(body), headers=headers)
        return conn.getresponse()

    def open(self, theme: str, path: str, action: str, token: Optional[str]) -> int:
        return self.request("POST", "/api/open", {"theme": theme, "path": path, "action": action}, token).status

    def test_index_lists_real_files_and_records_symlink_names_as_aliases(self) -> None:
        by_key = {(i["theme"], i["context"], i["name"]): i for i in self.index}
        self.assertEqual(sorted(by_key), [
            ("BlueA", "actions", "edit"), ("BlueA", "apps", "foo"),
            ("ThemeA", "actions", "edit"), ("ThemeA", "apps", "foo"),
            ("ThemeB", "actions", "bar"),
        ])
        foo = by_key[("ThemeA", "apps", "foo")]
        self.assertEqual([s["size"] for s in foo["sizes"]], ["16", "32"])   # the scale-2 folder and the same-named symlink are not sizes
        self.assertEqual(foo["sizes"][0]["path"], "apps/16/foo.svg")
        self.assertEqual(foo["aliases"], ["bar", "baz", "qux"])            # chain and cross-folder followed, dangling dropped
        self.assertEqual(by_key[("ThemeA", "actions", "edit")]["sizes"], [{"size": "scalable", "path": "actions/scalable/edit.svg"}])
        self.assertEqual(by_key[("ThemeB", "actions", "bar")]["sizes"], [{"size": "16", "path": "16x16/actions/bar.svg"}])
        self.assertEqual(by_key[("BlueA", "apps", "foo")]["sizes"], foo["sizes"])

    def test_get_page_index_and_icons(self) -> None:
        self.assertEqual(self.request("GET", f"/?token={_TOKEN}").status, 200)
        res = self.request("GET", "/api/index.json")
        self.assertEqual(res.status, 200)
        data = json.loads(res.read())
        self.assertEqual([t["name"] for t in data["themes"]], ["ThemeA", "ThemeB", "BlueA"])   # dropdown order
        self.assertEqual(data["themes"][2], {"name": "BlueA", "folder": str(self.tmp / "ThemeA"), "group": "Group A",
                                             "icon": "apps/16/foo.svg", "license": "MIT", "about": "A, colorized", "on_dark": False})
        self.assertTrue(data["themes"][1]["on_dark"])
        self.assertEqual(data["contexts"]["places"], "Nome/places/16/folder.svg")
        self.assertEqual(len(data["icons"]), 5)
        res = self.request("GET", "/icons/ThemeA/apps/16/foo.svg")
        self.assertEqual((res.status, res.getheader("Content-Type"), res.read()), (200, "image/svg+xml", _SVG))
        self.assertEqual(self.request("GET", "/icons/ThemeA/apps/16/bar.svg").read(), _SVG)   # alias path serves the real file

    def test_blue_variant_is_colorized_on_the_fly(self) -> None:
        res = self.request("GET", "/icons/BlueA/apps/16/foo.svg")
        self.assertEqual(res.status, 200)
        self.assertEqual(res.read(), _SVG.replace(b"#f57900", b"#3465a4"))

    def test_static_assets_are_served_only_from_the_static_folder(self) -> None:
        res = self.request("GET", "/static/llselect/index.umd.js")
        self.assertEqual(res.status, 200)
        self.assertIn("javascript", res.getheader("Content-Type") or "")
        self.assertEqual(self.request("GET", "/static/llselect/vanilla.css").getheader("Content-Type"), "text/css")
        for bad in ["/static/../server.py", "/static/", "/static/llselect/missing.js"]:
            self.assertEqual(self.request("GET", bad).status, 404, bad)

    def test_get_refuses_unknown_themes_and_paths_outside_them(self) -> None:
        for bad in ["/icons/Nope/apps/16/foo.svg", "/icons/ThemeA/../outside.svg", "/icons/ThemeA/apps/16",
                    "/icons/ThemeA/apps/16/missing.svg", "/build_icons.py", "/tests/"]:
            self.assertEqual(self.request("GET", bad).status, 404, bad)

    def test_open_requires_token(self) -> None:
        self.assertEqual(self.open("ThemeA", "apps/16/foo.svg", "reveal", token=None), 403)
        self.assertEqual(self.open("ThemeA", "apps/16/foo.svg", "reveal", token="wrong"), 403)
        self.assertEqual(self.calls, [])

    def test_open_rejects_unknown_themes_and_paths_outside_them(self) -> None:
        for theme, path in [("Nope", "apps/16/foo.svg"), ("ThemeA", "../outside.svg"),
                            ("ThemeA", "apps/16/missing.svg"), ("ThemeA", "apps/16")]:
            self.assertEqual(self.open(theme, path, "reveal", token=_TOKEN), 400, (theme, path))
        self.assertEqual(self.calls, [])

    def test_open_calls_file_manager_with_the_real_source_file(self) -> None:
        # Alias path on the Blue variant -> the real file of the base theme.
        self.assertEqual(self.open("BlueA", "apps/16/bar.svg", "dir", token=_TOKEN), 200)
        self.assertEqual(self.open("ThemeA", "apps/16/foo.svg", "inkscape", token=_TOKEN), 200)
        self.assertEqual(self.calls, [(self.tmp / "ThemeA/apps/16/foo.svg", "dir"), (self.tmp / "ThemeA/apps/16/foo.svg", "inkscape")])

    def test_open_with_inkscape_launches_it_detached(self) -> None:
        launched: List[Any] = []
        real_which, real_popen = viewer_server.shutil.which, viewer_server.subprocess.Popen
        viewer_server.shutil.which = lambda name: "/usr/bin/inkscape"
        viewer_server.subprocess.Popen = lambda args, **kw: launched.append((args, kw.get("start_new_session")))
        try:
            _REAL_OPEN(self.tmp / "ThemeA/apps/16/foo.svg", "inkscape")
        finally:
            viewer_server.shutil.which, viewer_server.subprocess.Popen = real_which, real_popen
        self.assertEqual(launched, [(["/usr/bin/inkscape", str(self.tmp / "ThemeA/apps/16/foo.svg")], True)])

    @unittest.skipIf(sys.platform == "darwin", "macOS falls back to `open -a Inkscape`")
    def test_missing_inkscape_gives_a_plain_language_error(self) -> None:
        real_which = viewer_server.shutil.which
        viewer_server.shutil.which = lambda name: None
        try:
            with self.assertRaisesRegex(RuntimeError, "Inkscape is not on the PATH"):
                _REAL_OPEN(self.tmp / "ThemeA/apps/16/foo.svg", "inkscape")
        finally:
            viewer_server.shutil.which = real_which

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux helper chain only")
    def test_missing_linux_helpers_give_a_plain_language_error(self) -> None:
        def no_such_program(*args: Any, **kwargs: Any) -> None:
            raise FileNotFoundError(2, "No such file or directory", args[0][0])
        real_run = viewer_server.subprocess.run
        viewer_server.subprocess.run = no_such_program
        try:
            with self.assertRaisesRegex(RuntimeError, "Copy full path"):
                _REAL_OPEN(self.tmp / "ThemeA/apps/16/foo.svg", "dir")
        finally:
            viewer_server.subprocess.run = real_run

    def test_launch_token_is_created_once_and_reused(self) -> None:
        real_file = viewer_server._TOKEN_FILE
        viewer_server._TOKEN_FILE = self.tmp / "token"
        try:
            first = viewer_server.launch_token()
            self.assertEqual(len(first), 22)   # 16 random bytes, urlsafe base64
            self.assertEqual(viewer_server.launch_token(), first)
            self.assertEqual((self.tmp / "token").read_text(), first)
        finally:
            viewer_server._TOKEN_FILE = real_file

    def test_colorizer_is_reloaded_when_its_file_changes(self) -> None:
        # A stand-in for lib/color_converter.py: the viewer re-imports it on mtime change.
        src = self.tmp / "fake_color_converter.py"
        src.write_text("def shift(text, name): return text + '-v1'\n")
        sys.path.insert(0, str(self.tmp))   # importlib.reload re-finds the module by name through sys.path
        importlib.invalidate_caches()
        module = importlib.import_module("fake_color_converter")
        real = viewer_server._COLOR_CONVERTER, viewer_server._color_converter_module, viewer_server._color_converter_mtime
        viewer_server._COLOR_CONVERTER, viewer_server._color_converter_module = src, module
        viewer_server._color_converter_mtime = src.stat().st_mtime
        try:
            colorize = viewer_server._live_colorizer("shift")
            self.assertEqual(colorize("x", "icon"), "x-v1")
            src.write_text("def shift(text, name): return text + '-v2'\n")
            os.utime(src, (0, src.stat().st_mtime + 5))   # make sure the mtime differs even on coarse clocks
            self.assertEqual(colorize("x", "icon"), "x-v2")
            src.write_text("def shift(text, name): return text + '-v3'\noops(\n")   # broken edit (SyntaxError): keep v2
            os.utime(src, (0, src.stat().st_mtime + 10))
            self.assertEqual(colorize("x", "icon"), "x-v2")
        finally:
            viewer_server._COLOR_CONVERTER, viewer_server._color_converter_module, viewer_server._color_converter_mtime = real
            sys.path.remove(str(self.tmp))
            sys.modules.pop("fake_color_converter", None)

    def test_lan_ips_are_ipv4_addresses(self) -> None:
        for ip in viewer_server.lan_ips():
            ipaddress.IPv4Address(ip)  # raises on garbage


class TestFixedIconPaths(unittest.TestCase):
    """Every icon the viewer page, the homepage template (its favicon) or the
    server tables name by path (title bar, buttons, menus, dropdown thumbnails)
    must be a real file of the index: the static site has only those, and the
    page never asks for an alias. Skipped without the submodules."""

    @unittest.skipUnless(all(raw.copied_src_theme_folder.is_dir() for raw in viewer_server.BUILT_IN_RAW_ICON_THEMES_PATH),
                         "theme submodules not checked out")
    def test_named_icons_are_indexed_real_files(self) -> None:
        themes = viewer_server.source_themes()
        names = "|".join(map(re.escape, sorted(themes, key=len, reverse=True)))   # Humanity-Dark before Humanity
        pages = [viewer_server._STATIC_DIR / "index.html", viewer_server._PROJECT_ROOT / "homepage" / "template.html",
                 viewer_server._PROJECT_ROOT / "homepage" / "panel.html"]
        named = {path for page in pages for path in re.findall(rf"\b((?:{names})/[A-Za-z0-9_./@-]+\.svg)", page.read_text("utf-8"))}
        named |= set(viewer_server._CONTEXT_ICONS.values())
        named |= {f"{name}/{theme.icon}" for name, theme in themes.items()}
        indexed = {f"{entry['theme']}/{size['path']}" for entry in viewer_server.build_index(themes) for size in entry["sizes"]}
        self.assertGreater(len(named), 20)
        self.assertEqual(sorted(named - indexed), [])


if __name__ == "__main__":
    unittest.main()
