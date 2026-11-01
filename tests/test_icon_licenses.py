#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for lib/icon_licenses.py: reading an icon's SPDX-License-Identifier, falling back to its theme's
license, grouping by icon and license, and the licenses.json / licenses.csv that build_icons.py writes.

Run:
    python3 -m unittest tests/test_icon_licenses.py -v
"""

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from lib.icon_licenses import (  # noqa: E402
    IconFile,
    icon_licenses,
    license_report,
    read_spdx,
    scan_theme,
    theme_license,
    write_license_files,
)

NOME: str = "LGPL-3.0-only OR CC-BY-SA-3.0"


class IconLicensesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp: Path = Path(tempfile.mkdtemp(prefix="tango_remixer_licenses_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def svg(self, rel: str, spdx: str | None = None, xml_declaration: bool = True) -> Path:
        """A small SVG file at `rel` under the temporary folder, with the SPDX comment Nome's add_spdx.py writes."""
        path: Path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        head: str = '<?xml version="1.0" encoding="UTF-8"?>\n' if xml_declaration else ""
        comment: str = f"<!-- SPDX-License-Identifier: {spdx} -->\n" if spdx else ""
        path.write_text(f'{head}{comment}<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"/>\n', encoding="utf-8")
        return path

    def file(self, theme: str, name: str, size: str, spdx: str | None, dst: str | None = None) -> IconFile:
        """An IconFile of `theme`'s apps/<name> at `size`, output as apps/<dst or name>."""
        path: Path = self.svg(f"{theme}/apps/{size}/{name}.svg", spdx)
        return IconFile(theme=theme, source=f"apps/{name}", context="apps", name=dst or name, size=size, path=path)


class TestReadSpdx(IconLicensesTestCase):
    def test_comment_after_the_xml_declaration(self) -> None:
        self.assertEqual(read_spdx(self.svg("a.svg", "GPL-2.0-only")), "GPL-2.0-only")

    def test_comment_on_the_first_line(self) -> None:
        self.assertEqual(read_spdx(self.svg("a.svg", NOME, xml_declaration=False)), NOME)

    def test_spaces_inside_an_expression_are_collapsed(self) -> None:
        self.assertEqual(read_spdx(self.svg("a.svg", "LGPL-3.0-only   OR\tCC-BY-SA-3.0")), NOME)

    def test_none_without_a_comment(self) -> None:
        self.assertIsNone(read_spdx(self.svg("a.svg")))


class TestThemeLicense(unittest.TestCase):
    def test_built_in_theme(self) -> None:
        self.assertEqual(theme_license("Tango"), "GPL-2.0-only OR GPL-3.0-only")

    def test_colorized_theme_has_its_base_themes_license(self) -> None:
        self.assertEqual(theme_license("BlueNome"), theme_license("Nome"))
        self.assertEqual(theme_license("BlueHumanity-Dark"), theme_license("Humanity-Dark"))

    def test_extra_theme_has_none(self) -> None:
        self.assertIsNone(theme_license("AppIcon"))


class TestIconLicenses(IconLicensesTestCase):
    def test_file_without_spdx_has_its_themes_license(self) -> None:
        [icon] = icon_licenses([self.file("Nome", "folder", "16", None)])
        self.assertEqual((icon.license, icon.exception), (NOME, False))

    def test_spdx_equal_to_the_themes_is_no_exception(self) -> None:
        [icon] = icon_licenses([self.file("Nome", "folder", "16", NOME)])
        self.assertEqual((icon.license, icon.exception), (NOME, False))

    def test_spdx_other_than_the_themes_is_an_exception(self) -> None:
        [icon] = icon_licenses([self.file("BlueNome", "sticky-note", "16", "GPL-2.0-only", dst="comment")])
        self.assertEqual((icon.theme, icon.source, icon.name, icon.license, icon.exception),
                         ("BlueNome", "apps/sticky-note", "comment", "GPL-2.0-only", True))

    def test_extra_theme_without_spdx_has_no_license_and_no_exception(self) -> None:
        [icon] = icon_licenses([self.file("AppIcon", "qkiss", "16", None)])
        self.assertEqual((icon.license, icon.exception), (None, False))

    def test_extra_theme_has_the_license_most_of_its_files_state(self) -> None:
        icons = icon_licenses([
            self.file("AppIcon", "qkiss", "16", "GPL-3.0-or-later"),
            self.file("AppIcon", "qkiss", "22", "GPL-3.0-or-later"),
            self.file("AppIcon", "clothes", "16", "GPL-3.0-or-later"),
            self.file("AppIcon", "tux", "16", "CC0-1.0"),
            self.file("AppIcon", "rename", "16", None),
        ])
        self.assertEqual([(i.name, i.license, i.theme_license, i.exception) for i in icons], [
            ("qkiss", "GPL-3.0-or-later", "GPL-3.0-or-later", False),
            ("clothes", "GPL-3.0-or-later", "GPL-3.0-or-later", False),
            ("tux", "CC0-1.0", "GPL-3.0-or-later", True),
            ("rename", None, "GPL-3.0-or-later", True),
        ])

    def test_built_in_theme_keeps_its_license_even_if_most_files_state_another(self) -> None:
        icons = icon_licenses([self.file("Nome", "sticky-note", size, "GPL-2.0-only") for size in ("16", "22")])
        self.assertEqual([(i.license, i.theme_license, i.exception) for i in icons], [("GPL-2.0-only", NOME, True)])

    def test_sizes_of_one_icon_and_license_are_grouped_and_sorted(self) -> None:
        files = [self.file("Nome", "folder", size, None) for size in ("scalable", "48", "16", "256", "22")]
        [icon] = icon_licenses(files)
        self.assertEqual(icon.sizes, ["16", "22", "48", "256", "scalable"])

    def test_sizes_that_differ_in_license_are_split(self) -> None:
        icons = icon_licenses([
            self.file("Nome", "folder", "16", None),
            self.file("Nome", "folder", "22", "GPL-2.0-only"),
            self.file("Nome", "folder", "32", None),
        ])
        self.assertEqual([(i.sizes, i.license, i.exception) for i in icons],
                         [(["16", "32"], NOME, False), (["22"], "GPL-2.0-only", True)])


class TestReportAndFiles(IconLicensesTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.icons = icon_licenses([
            self.file("Tango", "help-browser", "16", None),
            self.file("Nome", "folder", "16", None),
            self.file("Nome", "text-x-readme", "16", "GPL-2.0-only"),
            self.file("Nome", "text-x-readme", "22", "GPL-2.0-only"),
            self.file("BlueNome", "sticky-note", "16", "GPL-2.0-only", dst="comment"),
            self.file("AppIcon", "qkiss", "48", None),
        ])
        self.urls = {"Tango": "https://example.org/tango", "Nome": "https://example.org/nome", "BlueNome": "https://example.org/nome"}

    def test_report(self) -> None:
        report = license_report("MyTheme", self.icons, self.urls)
        self.assertEqual(report["theme"], "MyTheme")
        self.assertEqual(report["licenses"], ["GPL-2.0-only", "GPL-2.0-only OR GPL-3.0-only", NOME])
        self.assertEqual(report["sources"], [
            {"theme": "Tango", "base": None, "license": "GPL-2.0-only OR GPL-3.0-only", "url": "https://example.org/tango",
             "icon_count": 1, "exceptions": []},
            {"theme": "Nome", "base": None, "license": NOME, "url": "https://example.org/nome", "icon_count": 2,
             "exceptions": [{"icon": "apps/text-x-readme", "source": "apps/text-x-readme", "source_sizes": ["16", "22"], "license": "GPL-2.0-only"}]},
            {"theme": "BlueNome", "base": "Nome", "license": NOME, "url": "https://example.org/nome", "icon_count": 1,
             "exceptions": [{"icon": "apps/comment", "source": "apps/sticky-note", "source_sizes": ["16"], "license": "GPL-2.0-only"}]},
            {"theme": "AppIcon", "base": None, "license": None, "url": None, "icon_count": 1, "exceptions": []},
        ])

    def test_files(self) -> None:
        out: Path = self.tmp / "out"
        write_license_files(out, "MyTheme", self.icons, self.urls)
        text: str = (out / "licenses.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(text), license_report("MyTheme", self.icons, self.urls))
        self.assertIn('"source_sizes": ["16", "22"]', text)   # a short list on one line
        self.assertIn('"licenses": [\n    "GPL-2.0-only",', text)   # a long one keeps a value per line
        with (out / "licenses.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows, [
            ["icon", "theme", "source", "source_sizes", "license", "exception"],
            ["apps/help-browser", "Tango", "apps/help-browser", "16", "GPL-2.0-only OR GPL-3.0-only", ""],
            ["apps/folder", "Nome", "apps/folder", "16", NOME, ""],
            ["apps/text-x-readme", "Nome", "apps/text-x-readme", "16 22", "GPL-2.0-only", "yes"],
            ["apps/comment", "BlueNome", "apps/sticky-note", "16", "GPL-2.0-only", "yes"],
            ["apps/qkiss", "AppIcon", "apps/qkiss", "48", "", ""],
        ])


class TestScanTheme(IconLicensesTestCase):
    def test_both_folder_layouts_and_symlinks_left_out(self) -> None:
        self.svg("Theme/places/16/folder.svg")
        self.svg("Theme/48x48/apps/help-browser.svg", "GPL-2.0-only")
        (self.tmp / "Theme/places/16/folder-alias.svg").symlink_to("folder.svg")
        files = scan_theme("Theme", self.tmp / "Theme")
        self.assertEqual(sorted((f.source, f.context, f.size) for f in files),
                         [("apps/help-browser", "apps", "48x48"), ("places/folder", "places", "16")])


if __name__ == "__main__":
    unittest.main()
