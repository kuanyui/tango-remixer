#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for lib/included_icons_tokens.py: the tokens of included_icons.txt text
that the LSP server and the website colour. Pure, no LSP dependencies."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.included_icons_tokens import KINDS, SPAN_KINDS, Token, tokenize, tokenize_size_matrix  # noqa: E402


class TestTokenize(unittest.TestCase):

    def test_kinds_cover_the_span_kinds(self) -> None:
        self.assertEqual(len(KINDS), 10)
        self.assertTrue(set(SPAN_KINDS.values()) <= set(KINDS))

    def test_basic_line(self) -> None:
        self.assertEqual(tokenize("Tango    document-save"), [Token(0, 0, 5, "theme", True), Token(0, 9, 13, "icon")])

    def test_full_line_with_contexts_and_matrix(self) -> None:
        tokens = tokenize("Tango    places/folder    apps/folder-blue    {16-48;scalable>64}")
        self.assertEqual([(t.col, t.length, t.kind) for t in tokens], [
            (0, 5, "theme"), (9, 6, "context"), (16, 6, "icon"), (26, 4, "context"), (31, 11, "icon"),
            (47, 2, "input_size"), (49, 1, "operator"), (50, 2, "input_size"), (53, 8, "keyword"), (61, 1, "operator"), (62, 2, "output_size")])

    def test_directive_and_a_declared_theme(self) -> None:
        tokens = tokenize("# @extra-icon-theme MyIcons ../foo\nMyIcons    document-save\n")
        self.assertEqual(tokens, [Token(0, 0, 1, "comment"), Token(0, 2, 17, "directive"), Token(0, 20, 7, "theme"), Token(0, 28, 6, "string"),
                                  Token(1, 0, 7, "theme", False), Token(1, 11, 13, "icon")])

    def test_comments(self) -> None:
        self.assertEqual(tokenize("# this is a comment"), [Token(0, 0, 19, "comment")])
        tokens = tokenize("Tango    document-save # tail comment")
        self.assertEqual(tokens[-1], Token(0, 23, 14, "comment"))

    def test_sorted_by_position(self) -> None:
        tokens = tokenize("# header\nTango    document-save\nTango    user-home    {16-32}\n")
        self.assertEqual([(t.line, t.col) for t in tokens], sorted((t.line, t.col) for t in tokens))

    def test_size_matrix_pieces(self) -> None:
        pieces = lambda expr: [(t.col, t.length, t.kind) for t in tokenize_size_matrix(expr, 0, 0)]
        self.assertEqual(pieces("16"), [(0, 2, "input_size")])
        self.assertEqual(pieces("16-48"), [(0, 2, "input_size"), (2, 1, "operator"), (3, 2, "input_size")])
        self.assertEqual(pieces("16>32;scalable>48"), [(0, 2, "input_size"), (2, 1, "operator"), (3, 2, "output_size"),
                                                        (6, 8, "keyword"), (14, 1, "operator"), (15, 2, "output_size")])
        self.assertEqual(tokenize_size_matrix("16", 47, 3)[0], Token(3, 47, 2, "input_size"))   # offsets carried


if __name__ == "__main__":
    unittest.main()
