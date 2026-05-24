#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration test: run the full icon-pick + SVG-collect + PNG-convert
pipeline against the real Tango submodule and assert every expected
output artifact (SVG files, PNG files, index.theme, index.qrc).

To keep this test fast:
  - we restrict the built-in themes to Tango only (skip Humanity / Nome /
    Gimp* / Inkscape* which collectively are ~100MB and irrelevant here);
  - we pick three icons that exist as SVG in Tango;
  - each line exercises a different size-matrix syntax:
      * `{16-22}` — range (each source size maps to itself)
      * `{16;32}` — multi-singles
      * `{16>48}` — resize (source 16 -> output 48)

Skipped automatically when the Tango submodule is not checked out.
PNG-conversion assertions are skipped when Inkscape is not on PATH.
"""

import asyncio
import configparser
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# build_icons parses CLI args at import time -> spoof argv to a minimal valid set.
# (We overwrite OPTIONS with our own object below anyway.)
sys.argv = [
    "test_integration",
    "--included-icon-file", str(_PROJECT_ROOT / "_dummy_not_used.txt"),
]

import build_icons  # noqa: E402
from build_icons import (  # noqa: E402
    BUILD_FOLDERS,
    IconThemeOptions,
    SvgToPngConverter,
    run_00_copy_icon_themes,
    run_01_no_symlink_themes,
    run_02_colorize_themes,
    run_03_copy_included_icons,
    run_04_convert_svg_to_xdg_hicolor_theme_dir_structure,
    run_05_convert_svg_to_png,
    run_extra_copy,
)


_TANGO_SUBMODULE: Path = _PROJECT_ROOT / "submodules" / "tango-icon-theme"


@unittest.skipUnless(
    (_TANGO_SUBMODULE / "16x16").exists(),
    f"Tango submodule not checked out at {_TANGO_SUBMODULE}",
)
class TestEndToEndPipeline(unittest.TestCase):
    """Drive the full pipeline and exhaustively assert each output file."""

    def setUp(self) -> None:
        self.tmp: Path = Path(tempfile.mkdtemp(prefix="tango_remixer_integration_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        # included_icons.txt: each line exercises a different matrix syntax.
        # All three icons exist in Tango at sizes 16/22/32/48.
        self.included_text: str = (
            "Tango    dialog-cancel     {16-22}\n"   # range
            "Tango    system-log-out    {16;32}\n"   # multi-singles
            "Tango    go-up             {16>48}\n"   # resize: 16 source -> 48 output
        )
        included_path: Path = self.tmp / "included.txt"
        included_path.write_text(self.included_text, encoding="utf-8")
        self.svg_out: Path = self.tmp / "out_svg_theme"
        self.png_out: Path = self.tmp / "out_png_theme"

        # Build a fresh OPTIONS object (bypass argparse).
        self._fresh_options: IconThemeOptions = IconThemeOptions(
            clean_before_build=True,
            included_icon_file=included_path,
            output_stamp_file=self.tmp / "stamp",
            rebuild_regardless_of_stamp_file=True,
            output_png_theme_to_dir=self.png_out,
            output_svg_theme_to_dir=self.svg_out,
            output_theme_name="TestTango",
            output_theme_description="Integration test theme",
            input_svg_sizes=["16", "22", "32"],   # source sizes needed: 16 (all), 22 (dialog-cancel), 32 (system-log-out)
            output_png_sizes=[],                   # no filter; let run_05 emit at all picked sizes
            output_png_sizes_from_scalable=[],
            generate_scales=["1"],
            qrc_qresource_prefix="/xdg_icon_themes/",
            verbose=False,
            debug=False,
            extra_icon_themes=[],
        )

        # Snapshot module-level state we'll mutate, so we can restore it.
        self._saved_options = build_icons.OPTIONS
        self._saved_built_in = build_icons.BUILT_IN_RAW_ICON_THEMES_PATH
        self._saved_folders: dict[str, Path] = {
            attr: getattr(BUILD_FOLDERS, attr)
            for attr in (
                "FOLDER_ROOT",
                "FOLDER_00_ORIGINAL_THEMES_ROOT",
                "FOLDER_01_NO_SYMLINK_THEMES_ROOT",
                "FOLDER_02_COLORIZED_THEMES_ROOT",
                "FOLDER_03_INCLUDED_SVG_ICONS",
                "FOLDER_04_XDG_SVG_THEME",
                "FOLDER_05_XDG_PNG_THEME",
            )
        }

        # Apply our patches.
        build_icons.OPTIONS = self._fresh_options
        build_icons.BUILT_IN_RAW_ICON_THEMES_PATH = [
            t for t in self._saved_built_in if t.copied_dst_theme_name == "Tango"
        ]
        dist_root: Path = self.tmp / "dist"
        BUILD_FOLDERS.FOLDER_ROOT = dist_root
        BUILD_FOLDERS.FOLDER_00_ORIGINAL_THEMES_ROOT = dist_root / "00_ORIGINAL_THEMES"
        BUILD_FOLDERS.FOLDER_01_NO_SYMLINK_THEMES_ROOT = dist_root / "01_NO_SYMLINK_THEMES"
        BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT = dist_root / "02_COLORIZED_THEMES"
        BUILD_FOLDERS.FOLDER_03_INCLUDED_SVG_ICONS = dist_root / "03_INCLUDED_SVG_ICONS"
        BUILD_FOLDERS.FOLDER_04_XDG_SVG_THEME = dist_root / "04_XDG_SVG_THEME"
        BUILD_FOLDERS.FOLDER_05_XDG_PNG_THEME = dist_root / "05_XDG_PNG_THEME"

    def tearDown(self) -> None:
        build_icons.OPTIONS = self._saved_options
        build_icons.BUILT_IN_RAW_ICON_THEMES_PATH = self._saved_built_in
        for attr, value in self._saved_folders.items():
            setattr(BUILD_FOLDERS, attr, value)

    # --- helpers ---------------------------------------------------------

    def _assert_svg(self, path: Path) -> None:
        self.assertTrue(path.is_file(), f"missing SVG: {path}")
        content: str = path.read_text(encoding="utf-8")
        self.assertIn("<svg", content, f"not an SVG: {path}")
        self.assertGreater(path.stat().st_size, 100, f"SVG suspiciously small: {path}")

    def _assert_png(self, path: Path) -> None:
        self.assertTrue(path.is_file(), f"missing PNG: {path}")
        data: bytes = path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", f"not a valid PNG header: {path}")
        self.assertGreater(len(data), 100, f"PNG suspiciously small: {path}")

    def _parse_index_theme(self, path: Path) -> configparser.ConfigParser:
        cp = configparser.ConfigParser()
        cp.read(path, encoding="utf-8")
        return cp

    def _qrc_file_entries(self, path: Path) -> list[str]:
        """Return every <file> text content from the qrc."""
        tree = ET.parse(path)
        return [f.text or "" for f in tree.getroot().findall(".//file")]

    def _print_section(self, title: str) -> None:
        print(f"\n  --- {title} ---")

    def _print_indented(self, text: str) -> None:
        for line in text.splitlines():
            print(f"    {line}")

    def _print_tree(self, root: Path) -> None:
        """Print a sorted flat list of all files under `root`."""
        if not root.exists():
            print(f"    (does not exist: {root})")
            return
        print(f"    {root.name}/")
        for p in sorted(root.rglob("*")):
            if p.is_file():
                print(f"      {p.relative_to(root)}")

    # --- the test --------------------------------------------------------

    def test_full_pipeline_produces_every_expected_output_file(self) -> None:
        run_00_copy_icon_themes()
        run_01_no_symlink_themes()
        run_02_colorize_themes()
        run_03_copy_included_icons()
        run_04_convert_svg_to_xdg_hicolor_theme_dir_structure()
        inkscape_available: bool = SvgToPngConverter.check_inkscape_exists()
        if inkscape_available:
            asyncio.run(run_05_convert_svg_to_png())
        run_extra_copy()

        # Echo input and output side-by-side — doubles as live documentation.
        # Printed AFTER the pipeline runs so the input recipe and the produced
        # trees sit adjacent in the output, easy to eyeball-compare.
        self._print_section("input: included_icons.txt")
        self._print_indented(self.included_text)
        self._print_section(f"output: SVG XDG theme tree ({self.svg_out})")
        self._print_tree(self.svg_out)
        if inkscape_available:
            self._print_section(f"output: PNG XDG theme tree ({self.png_out})")
            self._print_tree(self.png_out)
        print()

        # ---- SVG output: every individual file --------------------------
        # Expected files per matrix:
        #   dialog-cancel  {16-22} -> 16x16, 22x22
        #   system-log-out {16;32} -> 16x16, 32x32
        #   go-up          {16>48} -> 48x48 (source 16 resized to output 48)
        self.assertTrue(self.svg_out.is_dir(), f"SVG output dir missing: {self.svg_out}")

        self._assert_svg(self.svg_out / "16x16" / "actions" / "dialog-cancel.svg")
        self._assert_svg(self.svg_out / "22x22" / "actions" / "dialog-cancel.svg")
        self._assert_svg(self.svg_out / "16x16" / "actions" / "system-log-out.svg")
        self._assert_svg(self.svg_out / "32x32" / "actions" / "system-log-out.svg")
        self._assert_svg(self.svg_out / "48x48" / "actions" / "go-up.svg")

        # ---- SVG index.theme: parse and verify every key ----------------
        svg_index_theme: Path = self.svg_out / "index.theme"
        self.assertTrue(svg_index_theme.is_file(), f"missing {svg_index_theme}")
        cp = self._parse_index_theme(svg_index_theme)

        # [Icon Theme] section
        self.assertEqual(cp["Icon Theme"]["Name"], "TestTango")
        self.assertEqual(cp["Icon Theme"]["Comment"], "Integration test theme")
        self.assertEqual(cp["Icon Theme"]["Inherits"], "gnome,hicolor")
        # Directories list reflects the union of all matrix outputs.
        dirs: set[str] = set(d.strip() for d in cp["Icon Theme"]["Directories"].split(","))
        self.assertEqual(
            dirs,
            {"16x16/actions", "22x22/actions", "32x32/actions", "48x48/actions"},
        )

        # Per-size sections
        for size in ("16", "22", "32", "48"):
            section = f"{size}x{size}/actions"
            self.assertEqual(cp[section]["Size"], size)
            self.assertEqual(cp[section]["Scale"], "1")
            self.assertEqual(cp[section]["Context"], "Actions")
            self.assertEqual(cp[section]["Type"], "Fixed")

        # ---- SVG index.qrc: parse and verify entries --------------------
        svg_index_qrc: Path = self.svg_out / "index.qrc"
        self.assertTrue(svg_index_qrc.is_file(), f"missing {svg_index_qrc}")
        qrc_files: set[str] = set(self._qrc_file_entries(svg_index_qrc))
        self.assertEqual(
            qrc_files,
            {
                "index.theme",
                "16x16/actions/dialog-cancel.svg",
                "22x22/actions/dialog-cancel.svg",
                "16x16/actions/system-log-out.svg",
                "32x32/actions/system-log-out.svg",
                "48x48/actions/go-up.svg",
            },
        )
        # qresource prefix is wired correctly
        qrc_root = ET.parse(svg_index_qrc).getroot()
        prefixes: set[str] = {qr.get("prefix", "") for qr in qrc_root.findall("qresource")}
        self.assertEqual(prefixes, {"/xdg_icon_themes/TestTango"})

        # ---- PNG output (skip cleanly if Inkscape missing) --------------
        if not inkscape_available:
            self.skipTest("Inkscape not available; PNG conversion skipped")

        self.assertTrue(self.png_out.is_dir(), f"PNG output dir missing: {self.png_out}")
        self._assert_png(self.png_out / "16x16" / "actions" / "dialog-cancel.png")
        self._assert_png(self.png_out / "22x22" / "actions" / "dialog-cancel.png")
        self._assert_png(self.png_out / "16x16" / "actions" / "system-log-out.png")
        self._assert_png(self.png_out / "32x32" / "actions" / "system-log-out.png")
        # Intended behavior: go-up's matrix is {16>48}, so its PNG should be
        # at 48x48 too. EXPECTED TO FAIL on current code: run_05 ignores the
        # matrix's output size and emits PNGs at the source size (16x16).
        self._assert_png(self.png_out / "48x48" / "actions" / "go-up.png")

        # ---- PNG index.theme -------------------------------------------
        png_index_theme: Path = self.png_out / "index.theme"
        self.assertTrue(png_index_theme.is_file(), f"missing {png_index_theme}")
        cp_png = self._parse_index_theme(png_index_theme)
        self.assertEqual(cp_png["Icon Theme"]["Name"], "TestTango")
        png_dirs: set[str] = set(d.strip() for d in cp_png["Icon Theme"]["Directories"].split(","))
        self.assertEqual(
            png_dirs,
            {"16x16/actions", "22x22/actions", "32x32/actions", "48x48/actions"},
        )

        # ---- PNG index.qrc ---------------------------------------------
        png_index_qrc: Path = self.png_out / "index.qrc"
        self.assertTrue(png_index_qrc.is_file(), f"missing {png_index_qrc}")
        png_qrc_files: set[str] = set(self._qrc_file_entries(png_index_qrc))
        self.assertEqual(
            png_qrc_files,
            {
                "index.theme",
                "16x16/actions/dialog-cancel.png",
                "22x22/actions/dialog-cancel.png",
                "16x16/actions/system-log-out.png",
                "32x32/actions/system-log-out.png",
                "48x48/actions/go-up.png",   # same bug — run_05 emits at 16x16, not 48x48
            },
        )


if __name__ == "__main__":
    # Don't let unittest see our spoofed CLI args.
    unittest.main(argv=[sys.argv[0]])
