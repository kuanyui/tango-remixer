#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration test: run the full icon-pick + SVG-collect + PNG-convert
pipeline against the real Tango submodule and assert every expected
output artifact (SVG files, PNG files, index.theme, index.qrc).

To keep this test fast:
  - we restrict the built-in themes to Tango only (skip Humanity / Nome /
    Gimp* / Inkscape* which collectively are ~100MB and irrelevant here);
  - we pick four icons that exist as SVG in Tango;
  - each line exercises a different size-matrix syntax:
      * `{16-22}`             - range (each source size maps to itself)
      * `{16;32}`             - multi-singles
      * `{16>48}`             - resize (source 16 -> output 48)
      * `{16>16;16>24;16>32}` - one source size driving multiple outputs

Skipped automatically when the Tango submodule is not checked out.
PNG-conversion assertions are skipped when Inkscape is not on PATH.
"""

import asyncio
import configparser
import re
import shutil
import struct
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
    ExtraIconTheme,
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
        # All four icons exist in Tango at sizes 16/22/32/48.
        self.included_text: str = (
            "Tango    dialog-cancel     {16-22}\n"               # range
            "Tango    system-log-out    {16;32}\n"               # multi-singles
            "Tango    go-up             {16>48}\n"               # resize: 16 src -> 48 out
            "Tango    go-down           {16>16;16>24;16>32}\n"   # one src -> multiple outs
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
            input_svg_sizes=["16", "22", "32", "scalable"],
            output_png_sizes=[],                   # no filter; let run_05 emit at all picked sizes
            output_png_sizes_from_scalable=[],
            generate_scales=["1", "2"],
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

    def _xdg_size_from_path(self, path: Path) -> tuple[int, int]:
        """Extract (base_size, scale) from an XDG icon path. Examples:
            `.../48x48/actions/foo.png`    -> (48, 1)
            `.../48x48@2/actions/foo.png`  -> (48, 2)
        """
        m = re.match(r"^(\d+)x\d+(?:@(\d+))?$", path.parent.parent.name)
        if not m:
            raise ValueError(f"path doesn't look like an XDG icon path: {path}")
        base: int = int(m.group(1))
        scale: int = int(m.group(2)) if m.group(2) else 1
        return base, scale

    def _assert_png_pixel_size_matches_folder(self, path: Path) -> None:
        """For resize / non-@1x cases - verify the PNG's actual pixel
        dimensions match the XDG size folder (base * scale). Catches the
        case where the PNG sits at the right path but wasn't rasterized
        at the intended pixel size."""
        base, scale = self._xdg_size_from_path(path)
        expected: int = base * scale
        width, height = struct.unpack(">II", path.read_bytes()[16:24])
        self.assertEqual(
            (width, height), (expected, expected),
            f"PNG pixel dims {width}x{height} != folder '{path.parent.parent.name}' (expected {expected}x{expected}) at {path}",
        )

    def _parse_index_theme(self, path: Path) -> configparser.ConfigParser:
        cp = configparser.ConfigParser()
        cp.read(path, encoding="utf-8")
        return cp

    def _qrc_file_entries(self, path: Path) -> list[str]:
        """Return every <file> text content from the qrc."""
        tree = ET.parse(path)
        return [f.text or "" for f in tree.getroot().findall(".//file")]

    def _print_major_section(self, title: str) -> None:
        bar: str = "=" * 60
        print(f"\n  {bar}\n  {title}\n  {bar}")

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

    def _print_file_content(self, path: Path) -> None:
        """Print the full text content of a (small) generated file, indented."""
        if not path.is_file():
            print(f"    (does not exist: {path})")
            return
        self._print_indented(path.read_text(encoding="utf-8"))

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

        # Echo input and outputs side-by-side - doubles as live documentation.
        # Printed AFTER the pipeline runs so the input recipe, file trees, and
        # generated configs sit adjacent in the output for eyeball-compare.
        self._print_major_section("input: included_icons.txt")
        self._print_indented(self.included_text)

        self._print_major_section("04_XDG_SVG_THEME")
        self._print_section(f"tree ({self.svg_out})")
        self._print_tree(self.svg_out)
        self._print_section("index.theme")
        self._print_file_content(self.svg_out / "index.theme")
        self._print_section("index.qrc")
        self._print_file_content(self.svg_out / "index.qrc")

        if inkscape_available:
            self._print_major_section("05_XDG_PNG_THEME")
            self._print_section(f"tree ({self.png_out})")
            self._print_tree(self.png_out)
            self._print_section("index.theme")
            self._print_file_content(self.png_out / "index.theme")
            self._print_section("index.qrc")
            self._print_file_content(self.png_out / "index.qrc")
        print()

        # ---- SVG output: every individual file --------------------------
        # Expected files per matrix:
        #   dialog-cancel  {16-22}             -> 16x16, 22x22
        #   system-log-out {16;32}             -> 16x16, 32x32
        #   go-up          {16>48}             -> 48x48 (source 16 resized to output 48)
        #   go-down        {16>16;16>24;16>32} -> 16x16, 24x24, 32x32 (one source -> 3 outs)
        self.assertTrue(self.svg_out.is_dir(), f"SVG output dir missing: {self.svg_out}")

        self._assert_svg(self.svg_out / "16x16" / "actions" / "dialog-cancel.svg")
        self._assert_svg(self.svg_out / "22x22" / "actions" / "dialog-cancel.svg")
        self._assert_svg(self.svg_out / "16x16" / "actions" / "system-log-out.svg")
        self._assert_svg(self.svg_out / "32x32" / "actions" / "system-log-out.svg")
        self._assert_svg(self.svg_out / "48x48" / "actions" / "go-up.svg")
        self._assert_svg(self.svg_out / "16x16" / "actions" / "go-down.svg")
        self._assert_svg(self.svg_out / "24x24" / "actions" / "go-down.svg")
        self._assert_svg(self.svg_out / "32x32" / "actions" / "go-down.svg")

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
            {"16x16/actions", "22x22/actions", "24x24/actions", "32x32/actions", "48x48/actions"},
        )

        # Per-size sections. SVG output is always @1x (sources are @1x), and
        # `Scale=1` is omitted by convention (defaults to 1 per XDG spec).
        for size in ("16", "22", "24", "32", "48"):
            section = f"{size}x{size}/actions"
            self.assertEqual(cp[section]["Size"], size)
            self.assertNotIn("Scale", cp[section])
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
                "16x16/actions/go-down.svg",
                "24x24/actions/go-down.svg",
                "32x32/actions/go-down.svg",
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
        # @1x scale: PNGs at `<size>x<size>/` folders.
        self._assert_png(self.png_out / "16x16" / "actions" / "dialog-cancel.png")
        self._assert_png(self.png_out / "22x22" / "actions" / "dialog-cancel.png")
        self._assert_png(self.png_out / "16x16" / "actions" / "system-log-out.png")
        self._assert_png(self.png_out / "32x32" / "actions" / "system-log-out.png")
        self._assert_png(self.png_out / "48x48" / "actions" / "go-up.png")
        self._assert_png(self.png_out / "16x16" / "actions" / "go-down.png")
        self._assert_png(self.png_out / "24x24" / "actions" / "go-down.png")
        self._assert_png(self.png_out / "32x32" / "actions" / "go-down.png")
        # @2x scale: same icons under `<size>x<size>@2/` folders, doubled pixels.
        self._assert_png(self.png_out / "16x16@2" / "actions" / "dialog-cancel.png")
        self._assert_png(self.png_out / "22x22@2" / "actions" / "dialog-cancel.png")
        self._assert_png(self.png_out / "16x16@2" / "actions" / "system-log-out.png")
        self._assert_png(self.png_out / "32x32@2" / "actions" / "system-log-out.png")
        self._assert_png(self.png_out / "48x48@2" / "actions" / "go-up.png")
        self._assert_png(self.png_out / "16x16@2" / "actions" / "go-down.png")
        self._assert_png(self.png_out / "24x24@2" / "actions" / "go-down.png")
        self._assert_png(self.png_out / "32x32@2" / "actions" / "go-down.png")

        # Resize cases need the actual pixel dimensions verified
        # (a 16x16 PNG misplaced into 48x48/ would otherwise slip through).
        self._assert_png_pixel_size_matches_folder(self.png_out / "48x48" / "actions" / "go-up.png")
        self._assert_png_pixel_size_matches_folder(self.png_out / "24x24" / "actions" / "go-down.png")
        self._assert_png_pixel_size_matches_folder(self.png_out / "32x32" / "actions" / "go-down.png")
        # @2x PNGs must be rasterized at base*2 pixels (HiDPI).
        self._assert_png_pixel_size_matches_folder(self.png_out / "16x16@2" / "actions" / "dialog-cancel.png")
        self._assert_png_pixel_size_matches_folder(self.png_out / "48x48@2" / "actions" / "go-up.png")
        self._assert_png_pixel_size_matches_folder(self.png_out / "32x32@2" / "actions" / "go-down.png")

        # ---- PNG index.theme -------------------------------------------
        png_index_theme: Path = self.png_out / "index.theme"
        self.assertTrue(png_index_theme.is_file(), f"missing {png_index_theme}")
        cp_png = self._parse_index_theme(png_index_theme)
        self.assertEqual(cp_png["Icon Theme"]["Name"], "TestTango")
        png_dirs: set[str] = set(d.strip() for d in cp_png["Icon Theme"]["Directories"].split(","))
        self.assertEqual(
            png_dirs,
            {
                "16x16/actions",   "16x16@2/actions",
                "22x22/actions",   "22x22@2/actions",
                "24x24/actions",   "24x24@2/actions",
                "32x32/actions",   "32x32@2/actions",
                "48x48/actions",   "48x48@2/actions",
            },
        )

        # ---- PNG index.qrc ---------------------------------------------
        png_index_qrc: Path = self.png_out / "index.qrc"
        self.assertTrue(png_index_qrc.is_file(), f"missing {png_index_qrc}")
        png_qrc_files: set[str] = set(self._qrc_file_entries(png_index_qrc))
        self.assertEqual(
            png_qrc_files,
            {
                "index.theme",
                # @1x
                "16x16/actions/dialog-cancel.png",
                "22x22/actions/dialog-cancel.png",
                "16x16/actions/system-log-out.png",
                "32x32/actions/system-log-out.png",
                "48x48/actions/go-up.png",
                "16x16/actions/go-down.png",
                "24x24/actions/go-down.png",
                "32x32/actions/go-down.png",
                # @2x
                "16x16@2/actions/dialog-cancel.png",
                "22x22@2/actions/dialog-cancel.png",
                "16x16@2/actions/system-log-out.png",
                "32x32@2/actions/system-log-out.png",
                "48x48@2/actions/go-up.png",
                "16x16@2/actions/go-down.png",
                "24x24@2/actions/go-down.png",
                "32x32@2/actions/go-down.png",
            },
        )

    def test_lines_without_size_matrix_keep_every_source_size(self) -> None:
        """A line without `{...}` should keep the SVG files of all found sizes."""
        included_path: Path = self.tmp / "included_no_matrix.txt"
        self.included_text = (
            "Tango    dialog-cancel\n"
            "Tango    system-log-out    actions/logout\n"   # renamed dst
        )
        included_path.write_text(self.included_text, encoding="utf-8")
        self._fresh_options.included_icon_file = included_path

        run_00_copy_icon_themes()
        run_01_no_symlink_themes()
        run_02_colorize_themes()
        run_03_copy_included_icons()
        run_04_convert_svg_to_xdg_hicolor_theme_dir_structure()

        svg_theme: Path = BUILD_FOLDERS.FOLDER_04_XDG_SVG_THEME / "TestTango"
        for size in ("16x16", "22x22", "32x32", "48x48"):
            self._assert_svg(svg_theme / size / "actions" / "dialog-cancel.svg")
            self._assert_svg(svg_theme / size / "actions" / "logout.svg")

        self.assertEqual(
            set(self._qrc_file_entries(svg_theme / "index.qrc")),
            {
                "index.theme",
                "16x16/actions/dialog-cancel.svg",
                "22x22/actions/dialog-cancel.svg",
                "32x32/actions/dialog-cancel.svg",
                "48x48/actions/dialog-cancel.svg",
                "16x16/actions/logout.svg",
                "22x22/actions/logout.svg",
                "32x32/actions/logout.svg",
                "48x48/actions/logout.svg",
            },
        )

    def test_full_pipeline_with_extra_icon_theme_from_system_hicolor(self) -> None:
        """`--extra-icon-theme` against a real external XDG-structured theme.
        We grab the first SVG in the system hicolor `scalable/apps/` folder
        and rebuild a minimal external theme around it (just that one icon)
        so we don't end up copying the entire hicolor tree."""
        # This project already depends on Inkscape (for SVG -> PNG), so its
        # icon is guaranteed available on any machine that can run the build.
        src_svg: Path = Path("/usr/share/icons/hicolor/scalable/apps/org.inkscape.Inkscape.svg")
        if not src_svg.is_file():
            self.skipTest(f"system inkscape icon not at {src_svg}")
        icon_name: str = src_svg.stem  # "org.inkscape.Inkscape"

        # Build a minimal extra theme dir that mirrors XDG hicolor layout
        # but contains only this one icon.
        extra_root: Path = self.tmp / "minimal_extra_theme"
        (extra_root / "scalable" / "apps").mkdir(parents=True)
        shutil.copy2(src_svg, extra_root / "scalable" / "apps" / src_svg.name)

        # Reconfigure OPTIONS for this test: one icon, one extra theme.
        extra_id: str = "TestExtraTheme"
        self._fresh_options.extra_icon_themes = [
            ExtraIconTheme(id=extra_id, icon_theme_root_folder_path=extra_root),
        ]
        self.included_text = f"{extra_id}    apps/{icon_name}    {{scalable>48}}\n"
        self._fresh_options.included_icon_file.write_text(self.included_text, encoding="utf-8")

        run_00_copy_icon_themes()
        run_01_no_symlink_themes()
        run_02_colorize_themes()
        run_03_copy_included_icons()
        run_04_convert_svg_to_xdg_hicolor_theme_dir_structure()
        inkscape_available: bool = SvgToPngConverter.check_inkscape_exists()
        if inkscape_available:
            asyncio.run(run_05_convert_svg_to_png())
        run_extra_copy()

        # Docs section.
        self._print_major_section(f"--extra-icon-theme test (picked: {icon_name})")
        self._print_section("input: included_icons.txt")
        self._print_indented(self.included_text)
        self._print_section(f"source: {src_svg}")
        self._print_section(f"SVG out tree ({self.svg_out})")
        self._print_tree(self.svg_out)
        if inkscape_available:
            self._print_section(f"PNG out tree ({self.png_out})")
            self._print_tree(self.png_out)
        print()

        # SVG output: the picked icon should appear at 48x48/apps/
        self._assert_svg(self.svg_out / "48x48" / "apps" / f"{icon_name}.svg")
        if inkscape_available:
            png_path: Path = self.png_out / "48x48" / "apps" / f"{icon_name}.png"
            self._assert_png(png_path)
            self._assert_png_pixel_size_matches_folder(png_path)


if __name__ == "__main__":
    # Don't let unittest see our spoofed CLI args.
    unittest.main(argv=[sys.argv[0]])
