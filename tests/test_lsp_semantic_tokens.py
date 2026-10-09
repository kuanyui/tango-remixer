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
        _tokenize_size_matrix,
        _SPAN_KEY_TO_TYPE_IDX,
        _COMMENT_TYPE_IDX,
        _INPUT_NUMBER_TYPE_IDX,
        _OUTPUT_NUMBER_TYPE_IDX,
        _OPERATOR_TYPE_IDX,
        _KEYWORD_TYPE_IDX,
        _NAMESPACE_TYPE_IDX,
        _DECORATOR_TYPE_IDX,
        _STRING_TYPE_IDX,
        _MOD_DEFAULT_LIBRARY,
        TOKEN_TYPES,
        TOKEN_MODIFIERS,
    )
    from lsprotocol import types as lsp
    HAS_LSP_DEPS = True
except ImportError:
    HAS_LSP_DEPS = False


def _decode_delta(data: List[int]) -> List[Tuple[int, int, int, int, int]]:
    """Inverse of _encode_tokens_delta -- back to (line, col, length, type, mods)."""
    out: List[Tuple[int, int, int, int, int]] = []
    line, char = 0, 0
    for i in range(0, len(data), 5):
        dl, dc, length, type_idx, mods = data[i:i + 5]
        line += dl
        char = char + dc if dl == 0 else dc
        out.append((line, char, length, type_idx, mods))
    return out


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestBuildTokens(unittest.TestCase):

    def test_legend_follows_the_shared_token_kinds(self) -> None:
        # lib/included_icons_tokens.py's KINDS are the legend's indices.
        from lib.included_icons_tokens import KINDS
        self.assertEqual([t.value for t in TOKEN_TYPES], ["namespace", "type", "variable", "number", "comment", "property", "operator", "keyword", "decorator", "string"])
        self.assertEqual(KINDS, ("theme", "context", "icon", "input_size", "comment", "output_size", "operator", "keyword", "directive", "string"))

    def test_basic_line_tokens(self) -> None:
        # `Tango    document-save` -> theme (built-in) + icon tokens
        tokens = _build_tokens("Tango    document-save")
        # (line, col, length, type_idx, mods). Tango is built-in -> defaultLibrary bit.
        self.assertIn((0, 0, 5, _SPAN_KEY_TO_TYPE_IDX["src_theme"], _MOD_DEFAULT_LIBRARY), tokens)
        self.assertIn((0, 9, 13, _SPAN_KEY_TO_TYPE_IDX["src_icon_name"], 0), tokens)

    def test_builtin_theme_gets_default_library_modifier(self) -> None:
        # Sanity: Tango is built-in.
        tokens = _build_tokens("Tango    document-save")
        theme_token = next(t for t in tokens if t[1] == 0)
        self.assertEqual(theme_token[4], _MOD_DEFAULT_LIBRARY)

    def test_extra_theme_no_default_library_modifier(self) -> None:
        # Declared via directive -> NOT built-in. Should NOT have defaultLibrary bit.
        text = (
            "# @extra-icon-theme MyIcons /tmp\n"
            "MyIcons    document-save\n"
        )
        tokens = _build_tokens(text)
        # The icon line's theme token is on line 1, col 0.
        theme_token = next(t for t in tokens if t[0] == 1 and t[1] == 0)
        self.assertEqual(theme_token[4], 0)

    def test_directive_declaration_name_no_modifier(self) -> None:
        # The NAME on the directive's own line is being declared, not built-in.
        line = "# @extra-icon-theme MyIcons ../foo"
        tokens = _build_tokens(line)
        # MyIcons is at col 20.
        name_token = next(t for t in tokens if t[1] == 20)
        self.assertEqual(name_token[4], 0)

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
        # matrix "16-48" splits into: 16 (input num), - (op), 48 (input num).
        self.assertEqual(d[(0, 47)], _INPUT_NUMBER_TYPE_IDX)   # "16"
        self.assertEqual(d[(0, 49)], _OPERATOR_TYPE_IDX)       # "-"
        self.assertEqual(d[(0, 50)], _INPUT_NUMBER_TYPE_IDX)   # "48"

    def test_full_line_comment_emits_comment_token(self) -> None:
        tokens = _build_tokens("# this is a comment")
        self.assertEqual(len(tokens), 1)
        line, col, length, type_idx, _mods = tokens[0]
        self.assertEqual((line, col, type_idx), (0, 0, _COMMENT_TYPE_IDX))
        self.assertEqual(length, len("# this is a comment"))

    def test_eol_comment_emits_comment_token(self) -> None:
        line = "Tango    document-save # tail comment"
        tokens = _build_tokens(line)
        # Last token should be the comment.
        comment_token = [t for t in tokens if t[3] == _COMMENT_TYPE_IDX]
        self.assertEqual(len(comment_token), 1)
        c_line, c_col, c_len, _, _ = comment_token[0]
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
class TestMatrixTokenization(unittest.TestCase):
    """Per-piece tokens inside the `{...}` block."""

    def _run(self, expr: str):
        # base_col=0, line_no=1 keeps positions easy to assert.
        # mods is always 0 for matrix pieces -- omit from comparisons.
        return [(col, length, type_idx)
                for (_line, col, length, type_idx, _mods)
                in _tokenize_size_matrix(expr, 0, 1)]

    def test_single_number_is_input(self) -> None:
        # "16" -> single input number, no other tokens
        self.assertEqual(self._run("16"), [(0, 2, _INPUT_NUMBER_TYPE_IDX)])

    def test_range_uses_input_for_both_sides(self) -> None:
        # "16-32" -> 16 (input), - (op), 32 (input)
        self.assertEqual(self._run("16-32"), [
            (0, 2, _INPUT_NUMBER_TYPE_IDX),
            (2, 1, _OPERATOR_TYPE_IDX),
            (3, 2, _INPUT_NUMBER_TYPE_IDX),
        ])

    def test_resize_splits_input_and_output(self) -> None:
        # "16>32" -> 16 (input), > (op), 32 (output property)
        self.assertEqual(self._run("16>32"), [
            (0, 2, _INPUT_NUMBER_TYPE_IDX),
            (2, 1, _OPERATOR_TYPE_IDX),
            (3, 2, _OUTPUT_NUMBER_TYPE_IDX),
        ])

    def test_scalable_keyword_then_output(self) -> None:
        # "scalable>48" -> scalable (keyword), > (op), 48 (output)
        self.assertEqual(self._run("scalable>48"), [
            (0, 8, _KEYWORD_TYPE_IDX),
            (8, 1, _OPERATOR_TYPE_IDX),
            (9, 2, _OUTPUT_NUMBER_TYPE_IDX),
        ])

    def test_semicolon_emits_no_token(self) -> None:
        # "16;32" -> just the two input numbers; no token for ";".
        # Both are input because ";" resets the expect_output flag.
        result = self._run("16;32")
        self.assertEqual(result, [
            (0, 2, _INPUT_NUMBER_TYPE_IDX),
            (3, 2, _INPUT_NUMBER_TYPE_IDX),
        ])

    def test_semicolon_resets_output_state(self) -> None:
        # "16>32;16-22" -> output state must reset across `;`.
        self.assertEqual(self._run("16>32;16-22"), [
            (0, 2, _INPUT_NUMBER_TYPE_IDX),   # 16
            (2, 1, _OPERATOR_TYPE_IDX),       # >
            (3, 2, _OUTPUT_NUMBER_TYPE_IDX),  # 32
            (6, 2, _INPUT_NUMBER_TYPE_IDX),   # 16 (NOT output, reset by ";")
            (8, 1, _OPERATOR_TYPE_IDX),       # -
            (9, 2, _INPUT_NUMBER_TYPE_IDX),   # 22
        ])

    def test_open_range_dash_prefix(self) -> None:
        # "-32" -> - (op), 32 (input)
        self.assertEqual(self._run("-32"), [
            (0, 1, _OPERATOR_TYPE_IDX),
            (1, 2, _INPUT_NUMBER_TYPE_IDX),
        ])

    def test_open_range_dash_suffix(self) -> None:
        # "32-" -> 32 (input), - (op)
        self.assertEqual(self._run("32-"), [
            (0, 2, _INPUT_NUMBER_TYPE_IDX),
            (2, 1, _OPERATOR_TYPE_IDX),
        ])


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestDirectiveTokens(unittest.TestCase):
    """`# @extra-icon-theme NAME PATH` lines get directive-style coloring."""

    def test_basic_directive_emits_four_token_types(self) -> None:
        line = "# @extra-icon-theme MyIcons ../foo"
        # cols: # at 0, @extra-icon-theme at 2, MyIcons at 20, ../foo at 28
        tokens = _build_tokens(line)
        d: dict[tuple[int, int], int] = {(t[0], t[1]): t[3] for t in tokens}
        self.assertEqual(d[(0, 0)], _COMMENT_TYPE_IDX)       # `#`
        self.assertEqual(d[(0, 2)], _DECORATOR_TYPE_IDX)     # `@extra-icon-theme`
        self.assertEqual(d[(0, 20)], _NAMESPACE_TYPE_IDX)    # `MyIcons`
        self.assertEqual(d[(0, 28)], _STRING_TYPE_IDX)       # `../foo`

    def test_directive_not_double_emitted_as_comment(self) -> None:
        # The whole-line Comment fallback must not also fire on directive lines.
        line = "# @extra-icon-theme MyIcons ../foo"
        tokens = _build_tokens(line)
        # No token should span the whole comment line (start=0, length=full len).
        whole_line_tokens = [t for t in tokens if t[0] == 0 and t[1] == 0 and t[2] == len(line)]
        self.assertEqual(whole_line_tokens, [])

    def test_plain_comment_still_one_token(self) -> None:
        # Non-directive comment lines still get a single whole-line Comment token.
        line = "# just a regular comment"
        tokens = _build_tokens(line)
        comment_tokens = [t for t in tokens if t[3] == _COMMENT_TYPE_IDX]
        self.assertEqual(len(comment_tokens), 1)
        self.assertEqual(comment_tokens[0][:3], (0, 0, len(line)))

    def test_directive_with_bad_name_still_colored(self) -> None:
        # Even though parse_text rejects the directive (bad NAME), the LSP
        # still re-detects via PATT_DIRECTIVE and colors the pieces.
        line = "# @extra-icon-theme bad/name ../foo"
        tokens = _build_tokens(line)
        types = {t[3] for t in tokens}
        # Decorator + Namespace (for the bad NAME) + String all present.
        self.assertIn(_DECORATOR_TYPE_IDX, types)
        self.assertIn(_NAMESPACE_TYPE_IDX, types)
        self.assertIn(_STRING_TYPE_IDX, types)


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestDeltaEncoding(unittest.TestCase):

    def test_roundtrip_same_line(self) -> None:
        original = [(0, 0, 5, 0, 0), (0, 9, 13, 2, 0)]
        decoded = _decode_delta(_encode_tokens_delta(original))
        self.assertEqual(decoded, original)

    def test_roundtrip_multi_line(self) -> None:
        original = [(0, 0, 5, 0, 0), (0, 9, 13, 2, 0), (2, 0, 5, 0, 0), (2, 9, 9, 2, 0)]
        decoded = _decode_delta(_encode_tokens_delta(original))
        self.assertEqual(decoded, original)

    def test_first_token_uses_absolute_positions(self) -> None:
        # When the first token isn't at line 0, deltaLine should equal its line.
        data = _encode_tokens_delta([(3, 5, 2, 0, 0)])
        self.assertEqual(data[:5], [3, 5, 2, 0, 0])

    def test_modifier_bits_passed_through(self) -> None:
        # 5th element of each quintet should be the modifier mask.
        data = _encode_tokens_delta([(0, 0, 5, 0, _MOD_DEFAULT_LIBRARY)])
        self.assertEqual(data[:5], [0, 0, 5, 0, _MOD_DEFAULT_LIBRARY])


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestLegend(unittest.TestCase):

    def test_legend_has_all_lsp_standard_types(self) -> None:
        # Sanity check the legend isn't accidentally empty.
        self.assertEqual(len(TOKEN_TYPES), 10)
        for t in TOKEN_TYPES:
            self.assertIsInstance(t, lsp.SemanticTokenTypes)

    def test_legend_modifiers(self) -> None:
        self.assertEqual(len(TOKEN_MODIFIERS), 1)
        self.assertEqual(TOKEN_MODIFIERS[0], lsp.SemanticTokenModifiers.DefaultLibrary)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
