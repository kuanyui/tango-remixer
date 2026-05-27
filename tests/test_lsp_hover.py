#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `_classify_position` and the hover handler in lsp/server.py.

Direct unit tests on the helpers. No LSP server is started.
Skipped when `pygls` / `lsprotocol` are not installed.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from lsp.server import _classify_position, _HOVER_TEMPLATES
    HAS_LSP_DEPS = True
except ImportError:
    HAS_LSP_DEPS = False


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestClassifyPosition(unittest.TestCase):

    def test_src_theme_builtin(self) -> None:
        # cursor inside "Tango" (built-in)
        self.assertEqual(
            _classify_position("Tango    document-save", 0, 2),
            ("src_theme_builtin", "Tango"),
        )

    def test_src_theme_extra(self) -> None:
        # cursor inside "MyIcons" (declared via directive above)
        text = (
            "# @extra-icon-theme MyIcons /tmp\n"
            "MyIcons    document-save\n"
        )
        self.assertEqual(
            _classify_position(text, 1, 3),
            ("src_theme_extra", "MyIcons"),
        )

    def test_src_icon_name(self) -> None:
        # cursor inside "document-save" (starts at col 9, len 13)
        self.assertEqual(
            _classify_position("Tango    document-save", 0, 12),
            ("src_icon_name", "document-save"),
        )

    def test_src_context_and_icon_split(self) -> None:
        line = "Tango    places/folder    apps/folder-blue"
        # "places" at 9-15
        self.assertEqual(_classify_position(line, 0, 10), ("src_context", "places"))
        # "folder" (src icon) at 16-22
        self.assertEqual(_classify_position(line, 0, 18), ("src_icon_name", "folder"))
        # "apps" (dst context) at 26-30
        self.assertEqual(_classify_position(line, 0, 27), ("dst_context", "apps"))
        # "folder-blue" (dst icon) at 31-42
        self.assertEqual(_classify_position(line, 0, 35), ("dst_icon_name", "folder-blue"))

    def test_matrix_input_output_and_operator(self) -> None:
        line = "Tango    folder    {16>32}"
        # "{" at 19, "16" at 20-22, ">" at 22, "32" at 23-25, "}" at 25
        self.assertEqual(_classify_position(line, 0, 20), ("matrix_input_num", "16"))
        self.assertEqual(_classify_position(line, 0, 22), ("matrix_op_gt", ">"))
        self.assertEqual(_classify_position(line, 0, 23), ("matrix_output_num", "32"))

    def test_matrix_range_dash_and_scalable(self) -> None:
        line = "Tango    folder    {16-32}"
        # "16" at 20-22, "-" at 22, "32" at 23-25
        self.assertEqual(_classify_position(line, 0, 22), ("matrix_op_dash", "-"))

        line2 = "Tango    folder    {scalable>48}"
        # "scalable" at 20-28, ">" at 28, "48" at 29-31
        self.assertEqual(_classify_position(line2, 0, 23), ("matrix_scalable", "scalable"))
        self.assertEqual(_classify_position(line2, 0, 29), ("matrix_output_num", "48"))

    def test_matrix_semicolon_returns_none(self) -> None:
        # `;` is intentionally untokenized -> no hover.
        line = "Tango    folder    {16;32}"
        # ";" at col 22
        self.assertIsNone(_classify_position(line, 0, 22))

    def test_directive_pieces(self) -> None:
        # cols:  # at 0, @extra-icon-theme at 2 (len 17), MyIcons at 20 (len 7), ../foo at 28
        line = "# @extra-icon-theme MyIcons ../foo"
        self.assertEqual(_classify_position(line, 0, 5),  ("directive_keyword", "@extra-icon-theme"))
        self.assertEqual(_classify_position(line, 0, 22), ("directive_name", "MyIcons"))
        self.assertEqual(_classify_position(line, 0, 30), ("directive_path", "../foo"))

    def test_directive_with_invalid_name_still_classified(self) -> None:
        # parse_text rejects "bad/name" but _classify_position falls back to PATT_DIRECTIVE.
        line = "# @extra-icon-theme bad/name ../foo"
        self.assertEqual(_classify_position(line, 0, 22), ("directive_name", "bad/name"))

    def test_plain_comment(self) -> None:
        line = "# just a regular comment"
        result = _classify_position(line, 0, 5)
        self.assertIsNotNone(result)
        kind, _ = result
        self.assertEqual(kind, "comment")

    def test_position_on_whitespace_returns_none(self) -> None:
        # cursor on the inter-field whitespace.
        line = "Tango    document-save"
        # col 6 is in the whitespace gap.
        self.assertIsNone(_classify_position(line, 0, 6))

    def test_out_of_range_line_returns_none(self) -> None:
        self.assertIsNone(_classify_position("Tango    document-save", 5, 0))


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestHoverTemplatesCoverage(unittest.TestCase):

    def test_every_emitted_kind_has_a_template(self) -> None:
        # Each kind that _classify_position can emit should have a template.
        # We assert this as a static dict subset check.
        emitted_kinds = {
            "src_theme_builtin", "src_theme_extra",
            "src_context", "src_icon_name", "dst_context", "dst_icon_name",
            "matrix_input_num", "matrix_output_num", "matrix_op_gt", "matrix_op_dash",
            "matrix_scalable", "directive_keyword", "directive_name", "directive_path",
            "comment",
        }
        self.assertTrue(emitted_kinds.issubset(set(_HOVER_TEMPLATES.keys())))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
