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
    PickedSvgFile,
    find_svg_files_in_theme,
    get_built_in_theme_license,
    make_licenses_json_dict,
    read_licenses_then_group_by_icon_and_license,
    read_spdx_license_identifier,
    write_licenses_json_and_csv,
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

    def file(self, theme: str, name: str, size: str, spdx: str | None, dst: str | None = None) -> PickedSvgFile:
        """A PickedSvgFile of `theme`'s apps/<name> at `size`, output as apps/<dst or name>."""
        path: Path = self.svg(f"{theme}/apps/{size}/{name}.svg", spdx)
        return PickedSvgFile(src_theme=theme, src_context_and_icon_name=f"apps/{name}", dst_context="apps",
                             dst_icon_name=dst or name, src_size=size, src_file_path=path)


class TestReadSpdxLicenseIdentifier(IconLicensesTestCase):
    def test_comment_after_the_xml_declaration(self) -> None:
        self.assertEqual(read_spdx_license_identifier(self.svg("a.svg", "GPL-2.0-only")), "GPL-2.0-only")

    def test_comment_on_the_first_line(self) -> None:
        self.assertEqual(read_spdx_license_identifier(self.svg("a.svg", NOME, xml_declaration=False)), NOME)

    def test_spaces_inside_an_expression_are_collapsed(self) -> None:
        self.assertEqual(read_spdx_license_identifier(self.svg("a.svg", "LGPL-3.0-only   OR\tCC-BY-SA-3.0")), NOME)

    def test_none_without_a_comment(self) -> None:
        self.assertIsNone(read_spdx_license_identifier(self.svg("a.svg")))


class TestGetBuiltInThemeLicense(unittest.TestCase):
    def test_built_in_theme(self) -> None:
        self.assertEqual(get_built_in_theme_license("Tango"), "GPL-2.0-only OR GPL-3.0-only")

    def test_colorized_theme_has_its_base_themes_license(self) -> None:
        self.assertEqual(get_built_in_theme_license("BlueNome"), get_built_in_theme_license("Nome"))
        self.assertEqual(get_built_in_theme_license("BlueHumanity-Dark"), get_built_in_theme_license("Humanity-Dark"))

    def test_extra_theme_has_none(self) -> None:
        self.assertIsNone(get_built_in_theme_license("AppIcon"))


class TestReadLicensesThenGroupByIconAndLicense(IconLicensesTestCase):
    def test_file_without_spdx_has_its_themes_license(self) -> None:
        [icon] = read_licenses_then_group_by_icon_and_license([self.file("Nome", "folder", "16", None)])
        self.assertEqual((icon.icon_license, icon.is_license_exception), (NOME, False))

    def test_spdx_equal_to_the_themes_is_no_exception(self) -> None:
        [icon] = read_licenses_then_group_by_icon_and_license([self.file("Nome", "folder", "16", NOME)])
        self.assertEqual((icon.icon_license, icon.is_license_exception), (NOME, False))

    def test_spdx_other_than_the_themes_is_an_exception(self) -> None:
        [icon] = read_licenses_then_group_by_icon_and_license([self.file("BlueNome", "sticky-note", "16", "GPL-2.0-only", dst="comment")])
        self.assertEqual((icon.src_theme, icon.src_context_and_icon_name, icon.dst_icon_name, icon.icon_license, icon.is_license_exception),
                         ("BlueNome", "apps/sticky-note", "comment", "GPL-2.0-only", True))

    def test_extra_theme_without_spdx_has_no_license_and_no_exception(self) -> None:
        [icon] = read_licenses_then_group_by_icon_and_license([self.file("AppIcon", "qkiss", "16", None)])
        self.assertEqual((icon.icon_license, icon.is_license_exception), (None, False))

    def test_extra_theme_has_the_license_most_of_its_files_state(self) -> None:
        icons = read_licenses_then_group_by_icon_and_license([
            self.file("AppIcon", "qkiss", "16", "GPL-3.0-or-later"),
            self.file("AppIcon", "qkiss", "22", "GPL-3.0-or-later"),
            self.file("AppIcon", "clothes", "16", "GPL-3.0-or-later"),
            self.file("AppIcon", "tux", "16", "CC0-1.0"),
            self.file("AppIcon", "rename", "16", None),
        ])
        self.assertEqual([(i.dst_icon_name, i.icon_license, i.src_theme_license, i.is_license_exception) for i in icons], [
            ("qkiss", "GPL-3.0-or-later", "GPL-3.0-or-later", False),
            ("clothes", "GPL-3.0-or-later", "GPL-3.0-or-later", False),
            ("tux", "CC0-1.0", "GPL-3.0-or-later", True),
            ("rename", None, "GPL-3.0-or-later", True),
        ])

    def test_built_in_theme_keeps_its_license_even_if_most_files_state_another(self) -> None:
        icons = read_licenses_then_group_by_icon_and_license([self.file("Nome", "sticky-note", size, "GPL-2.0-only") for size in ("16", "22")])
        self.assertEqual([(i.icon_license, i.src_theme_license, i.is_license_exception) for i in icons], [("GPL-2.0-only", NOME, True)])

    def test_sizes_of_one_icon_and_license_are_grouped_and_sorted(self) -> None:
        files = [self.file("Nome", "folder", size, None) for size in ("scalable", "48", "16", "256", "22")]
        [icon] = read_licenses_then_group_by_icon_and_license(files)
        self.assertEqual(icon.src_sizes, ["16", "22", "48", "256", "scalable"])

    def test_sizes_that_differ_in_license_are_split(self) -> None:
        icons = read_licenses_then_group_by_icon_and_license([
            self.file("Nome", "folder", "16", None),
            self.file("Nome", "folder", "22", "GPL-2.0-only"),
            self.file("Nome", "folder", "32", None),
        ])
        self.assertEqual([(i.src_sizes, i.icon_license, i.is_license_exception) for i in icons],
                         [(["16", "32"], NOME, False), (["22"], "GPL-2.0-only", True)])


class TestLicensesJsonAndCsv(IconLicensesTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.icons = read_licenses_then_group_by_icon_and_license([
            self.file("Tango", "help-browser", "16", None),
            self.file("Nome", "folder", "16", None),
            self.file("Nome", "text-x-readme", "16", "GPL-2.0-only"),
            self.file("Nome", "text-x-readme", "22", "GPL-2.0-only"),
            self.file("BlueNome", "sticky-note", "16", "GPL-2.0-only", dst="comment"),
            self.file("AppIcon", "qkiss", "48", None),
        ])
        self.urls = {"Tango": "https://example.org/tango", "Nome": "https://example.org/nome", "BlueNome": "https://example.org/nome"}

    def test_licenses_json_dict(self) -> None:
        report = make_licenses_json_dict("MyTheme", self.icons, self.urls)
        self.assertEqual(report["dst_theme"], "MyTheme")
        self.assertEqual(report["all_icon_licenses"], ["GPL-2.0-only", "GPL-2.0-only OR GPL-3.0-only", NOME])
        self.assertEqual(report["src_themes"], [
            {"src_theme": "Tango", "base_theme": None, "src_theme_license": "GPL-2.0-only OR GPL-3.0-only",
             "src_theme_url": "https://example.org/tango", "picked_icon_count": 1, "icon_license_exceptions": []},
            {"src_theme": "Nome", "base_theme": None, "src_theme_license": NOME, "src_theme_url": "https://example.org/nome", "picked_icon_count": 2,
             "icon_license_exceptions": [{"dst_context_and_icon_name": "apps/text-x-readme", "src_context_and_icon_name": "apps/text-x-readme",
                                          "src_sizes": ["16", "22"], "icon_license": "GPL-2.0-only"}]},
            {"src_theme": "BlueNome", "base_theme": "Nome", "src_theme_license": NOME, "src_theme_url": "https://example.org/nome", "picked_icon_count": 1,
             "icon_license_exceptions": [{"dst_context_and_icon_name": "apps/comment", "src_context_and_icon_name": "apps/sticky-note",
                                          "src_sizes": ["16"], "icon_license": "GPL-2.0-only"}]},
            {"src_theme": "AppIcon", "base_theme": None, "src_theme_license": None, "src_theme_url": None, "picked_icon_count": 1,
             "icon_license_exceptions": []},
        ])

    def test_files(self) -> None:
        out: Path = self.tmp / "out"
        write_licenses_json_and_csv(out, "MyTheme", self.icons, self.urls)
        text: str = (out / "licenses.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(text), make_licenses_json_dict("MyTheme", self.icons, self.urls))
        self.assertIn('"src_sizes": ["16", "22"]', text)   # a short list on one line
        self.assertIn('"all_icon_licenses": [\n    "GPL-2.0-only",', text)   # a long one keeps a value per line
        with (out / "licenses.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows, [
            ["dst_context_and_icon_name", "src_theme", "src_context_and_icon_name", "src_sizes", "icon_license", "is_license_exception"],
            ["apps/help-browser", "Tango", "apps/help-browser", "16", "GPL-2.0-only OR GPL-3.0-only", ""],
            ["apps/folder", "Nome", "apps/folder", "16", NOME, ""],
            ["apps/text-x-readme", "Nome", "apps/text-x-readme", "16 22", "GPL-2.0-only", "yes"],
            ["apps/comment", "BlueNome", "apps/sticky-note", "16", "GPL-2.0-only", "yes"],
            ["apps/qkiss", "AppIcon", "apps/qkiss", "48", "", ""],
        ])


class TestFindSvgFilesInTheme(IconLicensesTestCase):
    def test_both_folder_layouts_and_symlinks_left_out(self) -> None:
        self.svg("Theme/places/16/folder.svg")
        self.svg("Theme/48x48/apps/help-browser.svg", "GPL-2.0-only")
        (self.tmp / "Theme/places/16/folder-alias.svg").symlink_to("folder.svg")
        self.svg("Theme/actions/symbolic/list-add-symbolic.svg")   # not in a size folder
        files = find_svg_files_in_theme("Theme", self.tmp / "Theme")
        self.assertEqual(sorted((f.src_context_and_icon_name, f.dst_context, f.src_size) for f in files),
                         [("apps/help-browser", "apps", "48"), ("places/folder", "places", "16")])


if __name__ == "__main__":
    unittest.main()
