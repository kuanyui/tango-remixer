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
from typing import List, Tuple

# Make project root importable so `from lib.included_icons_parser import ...` works
# when this server is launched directly by an editor.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lsprotocol import types as lsp  # noqa: E402
from pygls.lsp.server import LanguageServer  # noqa: E402   # pygls 2.x path

from lib.included_icons_parser import parse_text  # noqa: E402


SERVER_NAME: str = "tango-remixer-included-icons-lsp"
SERVER_VERSION: str = "0.1.0"

server = LanguageServer(name=SERVER_NAME, version=SERVER_VERSION)


# Semantic token legend. Editors color tokens by these LSP-standard types.
# The order is the index used by `tokenType` in the wire format.
TOKEN_TYPES: List[lsp.SemanticTokenTypes] = [
    lsp.SemanticTokenTypes.Namespace,   # 0  theme name (e.g. "Tango")
    lsp.SemanticTokenTypes.Type,        # 1  context    (e.g. "apps")
    lsp.SemanticTokenTypes.Variable,    # 2  icon name  (e.g. "document-save")
    lsp.SemanticTokenTypes.Number,      # 3  size matrix block {...}
    lsp.SemanticTokenTypes.Comment,     # 4  comments  (# ...)
]
TOKEN_LEGEND: lsp.SemanticTokensLegend = lsp.SemanticTokensLegend(
    token_types=[t.value for t in TOKEN_TYPES],
    token_modifiers=[],
)

# Map ParsedIncludedIcon.spans key -> index into TOKEN_TYPES.
_SPAN_KEY_TO_TYPE_IDX: dict[str, int] = {
    "src_theme":      0,
    "src_context":    1,
    "src_icon_name":  2,
    "dst_context":    1,
    "dst_icon_name":  2,
    "size_io_matrix": 3,
}
_COMMENT_TYPE_IDX: int = 4


# ---------------------------------------------------------------------------
# Validation (placeholder)
# ---------------------------------------------------------------------------

def _validate(text: str) -> List[lsp.Diagnostic]:
    """Return LSP diagnostics for `included_icons.txt` content.
    Runs `parse_text` and maps each ParseError to a Diagnostic.
    `known_themes=None` because the LSP has no access to the user's
    `--extra-icon-theme` list; theme validation is best left to the build step."""
    _parsed, errors = parse_text(text, known_themes=None)
    return [
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
    _publish(ls, doc.uri, _validate(doc.source))


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def on_did_change(ls: LanguageServer, params: lsp.DidChangeTextDocumentParams) -> None:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    _publish(ls, doc.uri, _validate(doc.source))


@server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def on_did_save(ls: LanguageServer, params: lsp.DidSaveTextDocumentParams) -> None:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    _publish(ls, doc.uri, _validate(doc.source))


# ---------------------------------------------------------------------------
# Semantic tokens
# ---------------------------------------------------------------------------

# Comment regexes. Full-line: starts with `#` (after optional indent).
# EOL: `#` preceded by space/tab (matches what parse_text strips).
_COMMENT_FULL_LINE = re.compile(r'^\s*(#.*)$')
_COMMENT_EOL = re.compile(r'[ \t](#.*)$')


def _build_tokens(text: str) -> List[Tuple[int, int, int, int]]:
    """Collect (line, col, length, type_idx) tokens for the whole document.
    Sorted by position. Lines are 0-based for LSP."""
    parsed_lines, _errors = parse_text(text, known_themes=None)
    tokens: List[Tuple[int, int, int, int]] = []

    for p in parsed_lines:
        for span_key, type_idx in _SPAN_KEY_TO_TYPE_IDX.items():
            if span_key in p.spans:
                col_start, col_end = p.spans[span_key]
                tokens.append((p.line_no - 1, col_start, col_end - col_start, type_idx))

    # Comments are stripped by parse_text before parsing, so scan raw text.
    for line_idx, raw in enumerate(text.splitlines()):
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
