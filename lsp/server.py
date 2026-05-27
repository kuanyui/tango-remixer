#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LSP server for `included_icons.txt`.

Install + editor setup: see `docs/lsp_server.md`.
Run via stdio: `python -m lsp`.

Wires up pygls. Reacts to didOpen / didChange / didSave.
`_validate()` runs `parse_text` and turns each `ParseError` into an LSP
`Diagnostic` (line + column range, severity Error).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Make project root importable so `from lib.included_icons_parser import ...` works
# when this server is launched directly by an editor.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lsprotocol import types as lsp  # noqa: E402
from pygls.lsp.server import LanguageServer  # noqa: E402   # pygls 2.x path

from lib.included_icons_parser import (  # noqa: E402
    parse_text,
    BUILT_IN_ICON_THEMES,
    PATT_DIRECTIVE,
)
from urllib.parse import urlparse, unquote  # noqa: E402


SERVER_NAME: str = "tango-remixer-included-icons-lsp"
SERVER_VERSION: str = "0.1.0"

server = LanguageServer(name=SERVER_NAME, version=SERVER_VERSION)


# Semantic token legend. Editors color tokens by these LSP-standard types.
# The order is the index used by `tokenType` in the wire format.
TOKEN_TYPES: List[lsp.SemanticTokenTypes] = [
    lsp.SemanticTokenTypes.Namespace,   # 0  theme name (also: directive NAME)
    lsp.SemanticTokenTypes.Type,        # 1  context    (e.g. "apps")
    lsp.SemanticTokenTypes.Variable,    # 2  icon name  (e.g. "document-save")
    lsp.SemanticTokenTypes.Number,      # 3  input size  (e.g. "16" in "16>32")
    lsp.SemanticTokenTypes.Comment,     # 4  comments + leading `#` on directive
    lsp.SemanticTokenTypes.Property,    # 5  output size (e.g. "32" in "16>32")
    lsp.SemanticTokenTypes.Operator,    # 6  `>` and `-`
    lsp.SemanticTokenTypes.Keyword,     # 7  `scalable`
    lsp.SemanticTokenTypes.Decorator,   # 8  `@extra-icon-theme` directive keyword
    lsp.SemanticTokenTypes.String,      # 9  directive PATH
]
TOKEN_LEGEND: lsp.SemanticTokensLegend = lsp.SemanticTokensLegend(
    token_types=[t.value for t in TOKEN_TYPES],
    token_modifiers=[],
)

# Map ParsedIncludedIcon.spans key -> index into TOKEN_TYPES.
# `size_io_matrix` is split into per-piece tokens via _tokenize_size_matrix.
_SPAN_KEY_TO_TYPE_IDX: dict[str, int] = {
    "src_theme":      0,
    "src_context":    1,
    "src_icon_name":  2,
    "dst_context":    1,
    "dst_icon_name":  2,
}
_NAMESPACE_TYPE_IDX: int = 0
_COMMENT_TYPE_IDX: int = 4
_INPUT_NUMBER_TYPE_IDX: int = 3
_OUTPUT_NUMBER_TYPE_IDX: int = 5
_OPERATOR_TYPE_IDX: int = 6
_KEYWORD_TYPE_IDX: int = 7
_DECORATOR_TYPE_IDX: int = 8
_STRING_TYPE_IDX: int = 9

_DIRECTIVE_KEYWORD = "@extra-icon-theme"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _uri_to_path(uri: str) -> Optional[Path]:
    """Convert a `file://` URI to a local Path. Returns None for other schemes."""
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


def _validate(text: str, doc_uri: Optional[str] = None) -> List[lsp.Diagnostic]:
    """Return LSP diagnostics for `included_icons.txt` content.

    - Lines: parse_text errors -> Error diagnostics.
    - Directives: theme NAME validation via BUILT_IN_ICON_THEMES.
    - Directive PATHs: existence checked relative to the doc's parent dir;
      missing -> Warning (build-time still hard-errors)."""
    _lines, errors, directives = parse_text(text, built_in_themes=BUILT_IN_ICON_THEMES)
    diags: List[lsp.Diagnostic] = [
        lsp.Diagnostic(
            range=lsp.Range(
                start=lsp.Position(line=e.line_no - 1, character=e.col_start),
                end=lsp.Position(line=e.line_no - 1, character=e.col_end),
            ),
            message=e.message,
            severity=lsp.DiagnosticSeverity.Error,
            source=SERVER_NAME,
        )
        for e in errors
    ]

    # Directive path existence check (LSP-side, warning only).
    doc_path = _uri_to_path(doc_uri) if doc_uri else None
    if doc_path is not None:
        base_dir = doc_path.resolve().parent
        for d in directives:
            resolved = (base_dir / d.path_raw).resolve()
            if not resolved.exists():
                diags.append(lsp.Diagnostic(
                    range=lsp.Range(
                        start=lsp.Position(line=d.line_no - 1, character=d.path_span[0]),
                        end=lsp.Position(line=d.line_no - 1, character=d.path_span[1]),
                    ),
                    message=f"@extra-icon-theme path does not exist: {resolved}",
                    severity=lsp.DiagnosticSeverity.Warning,
                    source=SERVER_NAME,
                ))
    return diags


# ---------------------------------------------------------------------------
# Document lifecycle handlers
# ---------------------------------------------------------------------------

def _publish(ls: LanguageServer, uri: str, diagnostics: List[lsp.Diagnostic]) -> None:
    # pygls 2.x renamed `publish_diagnostics` to a namespaced method that
    # takes a Params object.
    ls.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
    )


@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def on_did_open(ls: LanguageServer, params: lsp.DidOpenTextDocumentParams) -> None:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    _publish(ls, doc.uri, _validate(doc.source, doc.uri))


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def on_did_change(ls: LanguageServer, params: lsp.DidChangeTextDocumentParams) -> None:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    _publish(ls, doc.uri, _validate(doc.source, doc.uri))


@server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def on_did_save(ls: LanguageServer, params: lsp.DidSaveTextDocumentParams) -> None:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    _publish(ls, doc.uri, _validate(doc.source, doc.uri))


# ---------------------------------------------------------------------------
# Semantic tokens
# ---------------------------------------------------------------------------

# Comment regexes. Full-line: starts with `#` (after optional indent).
# EOL: `#` preceded by space/tab (matches what parse_text strips).
_COMMENT_FULL_LINE = re.compile(r'^\s*(#.*)$')
_COMMENT_EOL = re.compile(r'[ \t](#.*)$')

# Lexer for the inside of `{...}`. Recognized pieces only -- whitespace and
# anything else falls through silently (uncolored).
_SIZE_PIECE = re.compile(r'(scalable|\d+|>|-|;)')


def _tokenize_size_matrix(matrix_text: str, base_col: int, line_no: int) -> List[Tuple[int, int, int, int]]:
    """Yield per-piece tokens for the inside of `{...}`.

    State machine: a `>` flips `expect_output`; the next number/keyword
    consumes it. `;` resets state. `-` doesn't switch.
    `;` and whitespace deliberately get no token (default face)."""
    out: List[Tuple[int, int, int, int]] = []
    expect_output = False
    for m in _SIZE_PIECE.finditer(matrix_text):
        piece = m.group(1)
        col = base_col + m.start(1)
        length = len(piece)
        line = line_no - 1
        if piece == ';':
            expect_output = False
            continue
        if piece == '>':
            out.append((line, col, length, _OPERATOR_TYPE_IDX))
            expect_output = True
        elif piece == '-':
            out.append((line, col, length, _OPERATOR_TYPE_IDX))
        elif piece == 'scalable':
            out.append((line, col, length, _KEYWORD_TYPE_IDX))
            expect_output = False
        else:  # digits
            if expect_output:
                out.append((line, col, length, _OUTPUT_NUMBER_TYPE_IDX))
                expect_output = False
            else:
                out.append((line, col, length, _INPUT_NUMBER_TYPE_IDX))
    return out


def _build_tokens(text: str) -> List[Tuple[int, int, int, int]]:
    """Collect (line, col, length, type_idx) tokens for the whole document.
    Sorted by position. Lines are 0-based for LSP."""
    parsed_lines, _errors, _directives = parse_text(text, built_in_themes=None)
    raw_lines = text.splitlines()
    tokens: List[Tuple[int, int, int, int]] = []

    for p in parsed_lines:
        for span_key, type_idx in _SPAN_KEY_TO_TYPE_IDX.items():
            if span_key in p.spans:
                col_start, col_end = p.spans[span_key]
                tokens.append((p.line_no - 1, col_start, col_end - col_start, type_idx))
        # Matrix is tokenized piece by piece (input num / output num / op / keyword).
        if "size_io_matrix" in p.spans:
            col_start, col_end = p.spans["size_io_matrix"]
            matrix_text = raw_lines[p.line_no - 1][col_start:col_end]
            tokens.extend(_tokenize_size_matrix(matrix_text, col_start, p.line_no))

    # Directive lines: highlight `#`, `@extra-icon-theme`, NAME, PATH separately
    # (like TS's `// @ts-ignore`). Re-scan via PATT_DIRECTIVE so even directives
    # that fail validation still get the directive-style colors.
    directive_lines: set[int] = set()
    for line_idx, raw in enumerate(raw_lines):
        md = PATT_DIRECTIVE.search(raw)
        if not md:
            continue
        directive_lines.add(line_idx)
        hash_col = raw.find('#')
        if hash_col >= 0:
            tokens.append((line_idx, hash_col, 1, _COMMENT_TYPE_IDX))
        kw_col = raw.find(_DIRECTIVE_KEYWORD)
        if kw_col >= 0:
            tokens.append((line_idx, kw_col, len(_DIRECTIVE_KEYWORD), _DECORATOR_TYPE_IDX))
        n_start, n_end = md.start('name'), md.end('name')
        tokens.append((line_idx, n_start, n_end - n_start, _NAMESPACE_TYPE_IDX))
        p_start, p_end = md.start('path'), md.end('path')
        tokens.append((line_idx, p_start, p_end - p_start, _STRING_TYPE_IDX))

    # Comments. Skip directive lines (already tokenized piece-by-piece above).
    for line_idx, raw in enumerate(raw_lines):
        if line_idx in directive_lines:
            continue
        m = _COMMENT_FULL_LINE.match(raw)
        if m:
            tokens.append((line_idx, m.start(1), len(m.group(1)), _COMMENT_TYPE_IDX))
            continue
        m = _COMMENT_EOL.search(raw)
        if m:
            tokens.append((line_idx, m.start(1), len(m.group(1)), _COMMENT_TYPE_IDX))

    tokens.sort(key=lambda t: (t[0], t[1]))
    return tokens


def _encode_tokens_delta(tokens: List[Tuple[int, int, int, int]]) -> List[int]:
    """Encode tokens into LSP's flat int array using delta encoding.
    Each token = [deltaLine, deltaStartChar, length, tokenType, tokenModifiers]."""
    data: List[int] = []
    prev_line = 0
    prev_char = 0
    for line, char, length, type_idx in tokens:
        delta_line = line - prev_line
        delta_char = char - prev_char if delta_line == 0 else char
        data.extend([delta_line, delta_char, length, type_idx, 0])
        prev_line = line
        prev_char = char
    return data


@server.feature(lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL, TOKEN_LEGEND)
def on_semantic_tokens_full(ls: LanguageServer, params: lsp.SemanticTokensParams) -> lsp.SemanticTokens:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    tokens = _build_tokens(doc.source)
    return lsp.SemanticTokens(data=_encode_tokens_delta(tokens))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the server over stdio (the standard LSP transport for editors)."""
    server.start_io()


if __name__ == "__main__":
    main()
