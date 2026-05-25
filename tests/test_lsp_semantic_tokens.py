#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the semantic-tokens helpers in lsp/server.py.

We test `_build_tokens` (sorted (line, col, length, type) list) directly.
The delta-encoder is exercised by decoding back into absolute positions.
Skipped when pygls / lsprotocol are not installed.
"""

import sys
import unittest
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from lsp.server import (
        _build_tokens,
        _encode_tokens_delta,
        _SPAN_KEY_TO_TYPE_IDX,
        _COMMENT_TYPE_IDX,
        TOKEN_TYPES,
    )
    from lsprotocol import types as lsp
    HAS_LSP_DEPS = True
except ImportError:
    HAS_LSP_DEPS = False


def _decode_delta(data: List[int]) -> List[Tuple[int, int, int, int]]:
    """Inverse of _encode_tokens_delta -- back to (line, col, length, type)."""
    out: List[Tuple[int, int, int, int]] = []
    line, char = 0, 0
    for i in range(0, len(data), 5):
        dl, dc, length, type_idx, _mods = data[i:i + 5]
        line += dl
        char = char + dc if dl == 0 else dc
        out.append((line, char, length, type_idx))
    return out


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestBuildTokens(unittest.TestCase):

    def test_basic_line_tokens(self) -> None:
        # `Tango    document-save` -> theme + icon tokens
        tokens = _build_tokens("Tango    document-save")
        # (line, col, length, type_idx)
        self.assertIn((0, 0, 5, _SPAN_KEY_TO_TYPE_IDX["src_theme"]), tokens)
        self.assertIn((0, 9, 13, _SPAN_KEY_TO_TYPE_IDX["src_icon_name"]), tokens)

    def test_full_line_with_context_and_matrix(self) -> None:
        line = "Tango    places/folder    apps/folder-blue    {16-48}"
        tokens = _build_tokens(line)
        d: dict[tuple[int, int], int] = {(t[0], t[1]): t[3] for t in tokens}
        # theme
        self.assertEqual(d[(0, 0)], _SPAN_KEY_TO_TYPE_IDX["src_theme"])
        # src context "places"
        self.assertEqual(d[(0, 9)], _SPAN_KEY_TO_TYPE_IDX["src_context"])
        # src icon name "folder"
        self.assertEqual(d[(0, 16)], _SPAN_KEY_TO_TYPE_IDX["src_icon_name"])
        # dst context "apps"
        self.assertEqual(d[(0, 26)], _SPAN_KEY_TO_TYPE_IDX["dst_context"])
        # dst icon name "folder-blue"
        self.assertEqual(d[(0, 31)], _SPAN_KEY_TO_TYPE_IDX["dst_icon_name"])
        # matrix "16-48"
        self.assertEqual(d[(0, 47)], _SPAN_KEY_TO_TYPE_IDX["size_io_matrix"])

    def test_full_line_comment_emits_comment_token(self) -> None:
        tokens = _build_tokens("# this is a comment")
        self.assertEqual(len(tokens), 1)
        line, col, length, type_idx = tokens[0]
        self.assertEqual((line, col, type_idx), (0, 0, _COMMENT_TYPE_IDX))
        self.assertEqual(length, len("# this is a comment"))

    def test_eol_comment_emits_comment_token(self) -> None:
        line = "Tango    document-save # tail comment"
        tokens = _build_tokens(line)
        # Last token should be the comment.
        comment_token = [t for t in tokens if t[3] == _COMMENT_TYPE_IDX]
        self.assertEqual(len(comment_token), 1)
        c_line, c_col, c_len, _ = comment_token[0]
        self.assertEqual(c_line, 0)
        # Comment starts at the `#` (the leading space is not part of the token).
        self.assertEqual(line[c_col:c_col + c_len], "# tail comment")

    def test_tokens_sorted_by_position(self) -> None:
        text = (
            "# header\n"
            "Tango    document-save\n"
            "Tango    user-home    {16-32}\n"
        )
        tokens = _build_tokens(text)
        positions = [(t[0], t[1]) for t in tokens]
        self.assertEqual(positions, sorted(positions))


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestDeltaEncoding(unittest.TestCase):

    def test_roundtrip_same_line(self) -> None:
        original = [(0, 0, 5, 0), (0, 9, 13, 2)]
        decoded = _decode_delta(_encode_tokens_delta(original))
        self.assertEqual(decoded, original)

    def test_roundtrip_multi_line(self) -> None:
        original = [(0, 0, 5, 0), (0, 9, 13, 2), (2, 0, 5, 0), (2, 9, 9, 2)]
        decoded = _decode_delta(_encode_tokens_delta(original))
        self.assertEqual(decoded, original)

    def test_first_token_uses_absolute_positions(self) -> None:
        # When the first token isn't at line 0, deltaLine should equal its line.
        data = _encode_tokens_delta([(3, 5, 2, 0)])
        self.assertEqual(data[:5], [3, 5, 2, 0, 0])


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestLegend(unittest.TestCase):

    def test_legend_has_all_lsp_standard_types(self) -> None:
        # Sanity check the legend isn't accidentally empty.
        self.assertEqual(len(TOKEN_TYPES), 5)
        for t in TOKEN_TYPES:
            self.assertIsInstance(t, lsp.SemanticTokenTypes)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
