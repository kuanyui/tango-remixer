#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `parse_text` in lib/included_icons_parser.py.

Focused on the line-level parser behavior:
  - returns errors instead of raising
  - collects all errors (does not stop at first)
  - col ranges on ParseError point at the offending token
  - source spans on ParsedIncludedIcon line up with each field
"""

import sys
import unittest
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.included_icons_parser import (  # noqa: E402
    ParseError,
    ParsedIncludedIcon,
    ExtraThemeDirective,
    parse_text,
)


# =============================================
# Multi-error collection (does not raise, does not stop early)
# =============================================
class TestMultiErrorCollection(unittest.TestCase):

    def test_no_raise_on_bad_line(self) -> None:
        # Single bad line: parse_text must not raise; it must report an error.
        parsed, errors, _directives = parse_text("garbage-line-no-separator")
        self.assertEqual(parsed, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid line format", errors[0].message)

    def test_collects_all_errors_not_just_first(self) -> None:
        # Three bad lines -> three errors.
        text = "garbage-one\ngarbage-two\ngarbage-three"
        parsed, errors, _directives = parse_text(text)
        self.assertEqual(parsed, [])
        self.assertEqual(len(errors), 3)
        # Line numbers are 1-based and in order.
        self.assertEqual([e.line_no for e in errors], [1, 2, 3])

    def test_good_lines_pass_around_bad_lines(self) -> None:
        # parse_text must keep going past errors and parse the good lines.
        text = (
            "Tango    document-save\n"
            "garbage-line\n"
            "Tango    document-open\n"
        )
        parsed, errors, _directives = parse_text(text)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0].src_icon_name, "document-save")
        self.assertEqual(parsed[1].src_icon_name, "document-open")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].line_no, 2)


# =============================================
# ParseError column ranges
# =============================================
class TestParseErrorRanges(unittest.TestCase):

    def test_unknown_theme_range_points_at_theme_token(self) -> None:
        # Theme `Bogus` is rejected by known_themes; range must cover "Bogus" only.
        parsed, errors, _directives = parse_text("Bogus    document-save", built_in_themes=["Tango"])
        self.assertEqual(len(errors), 1)
        err = errors[0]
        self.assertEqual(err.line_no, 1)
        self.assertEqual(err.col_start, 0)
        self.assertEqual(err.col_end, 5)   # "Bogus" is 5 chars
        self.assertIn("Unknown theme", err.message)

    def test_bad_matrix_range_points_at_matrix_block(self) -> None:
        # `scalable` as output: line regex accepts, SizeIoMatrix rejects.
        parsed, errors, _directives = parse_text("Tango    foo    foo    {16>scalable}")
        self.assertEqual(len(errors), 1)
        err = errors[0]
        line = "Tango    foo    foo    {16>scalable}"
        # Range should cover the inside of `{...}` (the captured sizes_io_expr).
        self.assertEqual(line[err.col_start:err.col_end], "16>scalable")


# =============================================
# ParsedIncludedIcon source spans
# =============================================
class TestSourceSpans(unittest.TestCase):

    def test_spans_for_basic_line(self) -> None:
        line = "Tango    document-save"
        parsed, errors, _directives = parse_text(line)
        self.assertEqual(errors, [])
        self.assertEqual(len(parsed), 1)
        p = parsed[0]
        self.assertEqual(line[p.spans["src_theme"][0]:p.spans["src_theme"][1]], "Tango")
        self.assertEqual(line[p.spans["src_icon_name"][0]:p.spans["src_icon_name"][1]], "document-save")
        # No src_context, dst_*, or matrix in input -> not in spans.
        self.assertNotIn("src_context", p.spans)
        self.assertNotIn("dst_context", p.spans)
        self.assertNotIn("dst_icon_name", p.spans)
        self.assertNotIn("size_io_matrix", p.spans)

    def test_spans_for_full_line(self) -> None:
        line = "Tango    places/folder    apps/folder-blue    {16-48}"
        parsed, errors, _directives = parse_text(line)
        self.assertEqual(errors, [])
        p = parsed[0]
        self.assertEqual(line[p.spans["src_theme"][0]:p.spans["src_theme"][1]], "Tango")
        self.assertEqual(line[p.spans["src_context"][0]:p.spans["src_context"][1]], "places")
        self.assertEqual(line[p.spans["src_icon_name"][0]:p.spans["src_icon_name"][1]], "folder")
        self.assertEqual(line[p.spans["dst_context"][0]:p.spans["dst_context"][1]], "apps")
        self.assertEqual(line[p.spans["dst_icon_name"][0]:p.spans["dst_icon_name"][1]], "folder-blue")
        self.assertEqual(line[p.spans["size_io_matrix"][0]:p.spans["size_io_matrix"][1]], "16-48")

    def test_line_no_recorded(self) -> None:
        text = "\n\nTango    document-save"
        parsed, _, _directives = parse_text(text)
        self.assertEqual(parsed[0].line_no, 3)


# =============================================
# Comments / blanks / theme-validation off
# =============================================
class TestMisc(unittest.TestCase):

    def test_comments_and_blanks_skipped(self) -> None:
        text = (
            "# header\n"
            "\n"
            "Tango    document-save # trailing comment\n"
            "# footer\n"
        )
        parsed, errors, _directives = parse_text(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].src_icon_name, "document-save")

    def test_known_themes_none_accepts_anything(self) -> None:
        # Default built_in_themes=None -> no theme validation.
        parsed, errors, _directives = parse_text("WhateverTheme    foo", built_in_themes=None)
        self.assertEqual(errors, [])
        self.assertEqual(parsed[0].src_theme, "WhateverTheme")

    def test_dst_icon_name_falls_back_to_src(self) -> None:
        # No dst on the line -> dst_icon_name == src_icon_name.
        parsed, _, _directives = parse_text("Tango    document-save")
        self.assertEqual(parsed[0].dst_icon_name, "document-save")


# =============================================
# @extra-icon-theme directive parsing
# =============================================
class TestExtraThemeDirective(unittest.TestCase):

    def test_basic_directive_collected(self) -> None:
        text = "# @extra-icon-theme MyIcons ../../icons"
        _lines, errors, directives = parse_text(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(directives), 1)
        d = directives[0]
        self.assertEqual(d.name, "MyIcons")
        self.assertEqual(d.path_raw, "../../icons")
        self.assertEqual(d.line_no, 1)

    def test_path_can_contain_inner_whitespace(self) -> None:
        # Trim outer whitespace; everything between NAME and EOL (trimmed) is path.
        text = "# @extra-icon-theme MyIcons /home/u/My Icons/theme"
        _lines, _errors, directives = parse_text(text)
        self.assertEqual(len(directives), 1)
        self.assertEqual(directives[0].path_raw, "/home/u/My Icons/theme")

    def test_directives_coexist_with_icon_lines(self) -> None:
        text = (
            "# @extra-icon-theme MyIcons ../../icons\n"
            "Tango    document-save\n"
            "MyIcons    app-foo\n"
        )
        lines, errors, directives = parse_text(text, built_in_themes=["Tango"])
        self.assertEqual(errors, [])
        self.assertEqual(len(directives), 1)
        self.assertEqual(len(lines), 2)
        # MyIcons accepted because it came from a directive.
        self.assertEqual(lines[1].src_theme, "MyIcons")

    def test_invalid_name_emits_error(self) -> None:
        text = "# @extra-icon-theme bad/name ../../icons"
        _lines, errors, directives = parse_text(text)
        self.assertEqual(directives, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid theme NAME", errors[0].message)

    def test_builtin_collision_emits_error(self) -> None:
        text = "# @extra-icon-theme Tango ../../icons"
        _lines, errors, directives = parse_text(text, built_in_themes=["Tango"])
        self.assertEqual(directives, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("collides", errors[0].message)

    def test_duplicate_name_emits_error(self) -> None:
        text = (
            "# @extra-icon-theme MyIcons /one\n"
            "# @extra-icon-theme MyIcons /two\n"
        )
        _lines, errors, directives = parse_text(text)
        self.assertEqual(len(directives), 1)
        self.assertEqual(directives[0].path_raw, "/one")
        self.assertEqual(len(errors), 1)
        self.assertIn("Duplicate", errors[0].message)
        self.assertEqual(errors[0].line_no, 2)

    def test_backslash_in_path_emits_error(self) -> None:
        text = r"# @extra-icon-theme MyIcons C:\Users\u\icons"
        _lines, errors, directives = parse_text(text)
        self.assertEqual(directives, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Backslash", errors[0].message)

    def test_unknown_theme_after_directive_validates(self) -> None:
        # Built-in only -> "MyIcons" line should error (no such theme).
        # With matching directive -> line should pass.
        with self.subTest("without directive"):
            _lines, errors, _ = parse_text("MyIcons    foo", built_in_themes=["Tango"])
            self.assertEqual(len(errors), 1)
            self.assertIn("Unknown theme", errors[0].message)
        with self.subTest("with directive"):
            text = "# @extra-icon-theme MyIcons /tmp\nMyIcons    foo"
            _lines, errors, _ = parse_text(text, built_in_themes=["Tango"])
            self.assertEqual(errors, [])

    def test_name_span_points_at_name_token(self) -> None:
        text = "# @extra-icon-theme MyIcons /path"
        _lines, _errors, directives = parse_text(text)
        d = directives[0]
        self.assertEqual(text[d.name_span[0]:d.name_span[1]], "MyIcons")
        self.assertEqual(text[d.path_span[0]:d.path_span[1]], "/path")


# =============================================
# Format diagnostics
# =============================================
class TestFormatDiagnostics(unittest.TestCase):
    """A rejected line must say what is wrong and point at where."""

    def _only_error(self, text: str) -> ParseError:
        parsed, errors, _directives = parse_text(text)
        self.assertEqual(parsed, [])
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].message.startswith("Invalid line format: "), errors[0].message)
        return errors[0]

    def test_three_spaces_names_the_gap_and_both_neighbours(self) -> None:
        # The real-world case: `{-32}` squeezed to 3 spaces by column alignment.
        line = "Nome    package-x-generic    backend-lzh-compatibility   {-32}"
        err = self._only_error(line)
        self.assertIn("only 3 spaces between `backend-lzh-compatibility` and `{-32}`", err.message)
        self.assertIn("4 or more spaces", err.message)
        self.assertEqual(line[err.col_start:err.col_end], "   ")

    def test_single_space_is_reported_as_one_space(self) -> None:
        line = "Tango document-open"
        err = self._only_error(line)
        self.assertIn("only 1 space between `Tango` and `document-open`", err.message)
        self.assertEqual((err.col_start, err.col_end), (5, 6))

    def test_short_gap_before_size_expression(self) -> None:
        line = "Tango    a {16}"
        err = self._only_error(line)
        self.assertIn("only 1 space between `a` and `{16}`", err.message)
        self.assertEqual(line[err.col_start:err.col_end], " ")

    def test_fallback_states_the_rule(self) -> None:
        line = "garbage-line-no-separator"
        err = self._only_error(line)
        self.assertIn("4 or more spaces", err.message)
        self.assertEqual((err.col_start, err.col_end), (0, len(line)))

    def test_spaces_inside_size_expression_are_still_legal(self) -> None:
        # Spaces are part of the size-expression grammar; they must not be mistaken for a short separator.
        parsed, errors, _directives = parse_text("Tango    a    {16>16; 32>32}")
        self.assertEqual(len(parsed), 1)
        self.assertFalse(any("Invalid line format" in e.message for e in errors), errors)

if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
