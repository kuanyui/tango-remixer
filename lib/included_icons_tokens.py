#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tokens of `included_icons.txt` text, for colouring. The LSP server's semantic
tokens (lsp/server.py) and the website's code blocks
(homepage/generate_static_site.py) both come from here, so an editor and the
site colour the same pieces the same way.

Pure: the parser's spans plus three regexes, no I/O."""

from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Set, Tuple

from lib.included_icons_parser import BUILT_IN_ICON_THEMES, PATT_DIRECTIVE, parse_text

KINDS: Tuple[str, ...] = ("theme", "context", "icon", "input_size", "comment", "output_size", "operator", "keyword", "directive", "string")
"""The kinds of token, in the order of the LSP server's token legend: a theme name
(also a directive's NAME), a context (`apps`), an icon name, an input size (`16`
in `16>32`), a comment (and the `#` of a directive), an output size (`32` in
`16>32`), `>` and `-`, `scalable`, the `@extra-icon-theme` keyword, a directive's
PATH."""

SPAN_KINDS: Dict[str, str] = {"src_theme": "theme", "src_context": "context", "src_icon_name": "icon",
                              "dst_context": "context", "dst_icon_name": "icon"}
"""ParsedIncludedIcon.spans key -> kind. The size matrix is split into pieces by tokenize_size_matrix."""

DIRECTIVE_KEYWORD: str = "@extra-icon-theme"


class Token(NamedTuple):
    line: int
    """0-based"""
    col: int
    """0-based"""
    length: int
    kind: str
    """one of KINDS"""
    builtin: bool = False
    """a built-in theme's name"""


# Comment regexes. Full-line: starts with `#` (after optional indent).
# EOL: `#` preceded by space/tab (matches what parse_text strips).
COMMENT_FULL_LINE = re.compile(r'^\s*(#.*)$')
COMMENT_EOL = re.compile(r'[ \t](#.*)$')
# Lexer for the inside of `{...}`. Recognized pieces only; whitespace and anything else falls through silently.
_SIZE_PIECE = re.compile(r'(scalable|\d+|>|-|;)')


def tokenize_size_matrix(matrix_text: str, base_col: int, line: int) -> List[Token]:
    """The pieces inside `{...}`: input and output sizes, `>` and `-`, `scalable`.
    State machine: a `>` flips `expect_output`; the next number or keyword consumes
    it. `;` resets the state and, like whitespace, gets no token. `-` does not switch."""
    out: List[Token] = []
    expect_output = False
    for m in _SIZE_PIECE.finditer(matrix_text):
        piece, col = m.group(1), base_col + m.start(1)
        if piece == ';':
            expect_output = False
        elif piece == '>':
            out.append(Token(line, col, 1, "operator"))
            expect_output = True
        elif piece == '-':
            out.append(Token(line, col, 1, "operator"))
        elif piece == 'scalable':
            out.append(Token(line, col, len(piece), "keyword"))
            expect_output = False
        elif expect_output:
            out.append(Token(line, col, len(piece), "output_size"))
            expect_output = False
        else:
            out.append(Token(line, col, len(piece), "input_size"))
    return out


def tokenize(text: str) -> List[Token]:
    """Every token of `text`, sorted by position."""
    parsed_lines, _errors, _directives = parse_text(text, built_in_themes=None)
    raw_lines = text.splitlines()
    tokens: List[Token] = []
    for p in parsed_lines:
        for span_key, kind in SPAN_KINDS.items():
            if span_key in p.spans:
                col_start, col_end = p.spans[span_key]
                builtin = span_key == "src_theme" and raw_lines[p.line_no - 1][col_start:col_end] in BUILT_IN_ICON_THEMES
                tokens.append(Token(p.line_no - 1, col_start, col_end - col_start, kind, builtin))
        if "size_io_matrix" in p.spans:
            col_start, col_end = p.spans["size_io_matrix"]
            tokens.extend(tokenize_size_matrix(raw_lines[p.line_no - 1][col_start:col_end], col_start, p.line_no - 1))
    # Directive lines: `#`, `@extra-icon-theme`, NAME and PATH separately (like TS's `// @ts-ignore`). Found
    # with PATT_DIRECTIVE, so a directive that fails validation is coloured like one too.
    directive_lines: Set[int] = set()
    for line_idx, raw in enumerate(raw_lines):
        md = PATT_DIRECTIVE.search(raw)
        if not md:
            continue
        directive_lines.add(line_idx)
        hash_col = raw.find('#')
        if hash_col >= 0:
            tokens.append(Token(line_idx, hash_col, 1, "comment"))
        kw_col = raw.find(DIRECTIVE_KEYWORD)
        if kw_col >= 0:
            tokens.append(Token(line_idx, kw_col, len(DIRECTIVE_KEYWORD), "directive"))
        tokens.append(Token(line_idx, md.start('name'), md.end('name') - md.start('name'), "theme"))
        tokens.append(Token(line_idx, md.start('path'), md.end('path') - md.start('path'), "string"))
    # Comments, except on directive lines (coloured piece by piece above).
    for line_idx, raw in enumerate(raw_lines):
        if line_idx in directive_lines:
            continue
        m = COMMENT_FULL_LINE.match(raw)
        if m:
            tokens.append(Token(line_idx, m.start(1), len(m.group(1)), "comment"))
            continue
        m = COMMENT_EOL.search(raw)
        if m:
            tokens.append(Token(line_idx, m.start(1), len(m.group(1)), "comment"))
    tokens.sort(key=lambda t: (t.line, t.col))
    return tokens
