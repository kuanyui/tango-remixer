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
TOKEN_MODIFIERS: List[lsp.SemanticTokenModifiers] = [
    lsp.SemanticTokenModifiers.DefaultLibrary,   # 0  bit 0: built-in theme
]
TOKEN_LEGEND: lsp.SemanticTokensLegend = lsp.SemanticTokensLegend(
    token_types=[t.value for t in TOKEN_TYPES],
    token_modifiers=[m.value for m in TOKEN_MODIFIERS],
)
_MOD_DEFAULT_LIBRARY: int = 1 << 0

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


def _tokenize_size_matrix(matrix_text: str, base_col: int, line_no: int) -> List[Tuple[int, int, int, int, int]]:
    """Yield per-piece tokens for the inside of `{...}`.

    Tuple format: `(line, col, length, type_idx, mods)`. `mods` is always 0
    here (no built-in concept for matrix pieces).

    State machine: a `>` flips `expect_output`; the next number/keyword
    consumes it. `;` resets state. `-` doesn't switch.
    `;` and whitespace deliberately get no token (default face)."""
    out: List[Tuple[int, int, int, int, int]] = []
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
            out.append((line, col, length, _OPERATOR_TYPE_IDX, 0))
            expect_output = True
        elif piece == '-':
            out.append((line, col, length, _OPERATOR_TYPE_IDX, 0))
        elif piece == 'scalable':
            out.append((line, col, length, _KEYWORD_TYPE_IDX, 0))
            expect_output = False
        else:  # digits
            if expect_output:
                out.append((line, col, length, _OUTPUT_NUMBER_TYPE_IDX, 0))
                expect_output = False
            else:
                out.append((line, col, length, _INPUT_NUMBER_TYPE_IDX, 0))
    return out


def _build_tokens(text: str) -> List[Tuple[int, int, int, int, int]]:
    """Collect `(line, col, length, type_idx, mods)` tokens. Sorted by position.
    Lines are 0-based for LSP. `mods` is a bitmask over `TOKEN_MODIFIERS`."""
    parsed_lines, _errors, _directives = parse_text(text, built_in_themes=None)
    raw_lines = text.splitlines()
    tokens: List[Tuple[int, int, int, int, int]] = []

    for p in parsed_lines:
        for span_key, type_idx in _SPAN_KEY_TO_TYPE_IDX.items():
            if span_key in p.spans:
                col_start, col_end = p.spans[span_key]
                # Mark built-in theme NAME so editors can color it distinctly.
                mods = 0
                if span_key == "src_theme":
                    value = raw_lines[p.line_no - 1][col_start:col_end]
                    if value in BUILT_IN_ICON_THEMES:
                        mods = _MOD_DEFAULT_LIBRARY
                tokens.append((p.line_no - 1, col_start, col_end - col_start, type_idx, mods))
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
            tokens.append((line_idx, hash_col, 1, _COMMENT_TYPE_IDX, 0))
        kw_col = raw.find(_DIRECTIVE_KEYWORD)
        if kw_col >= 0:
            tokens.append((line_idx, kw_col, len(_DIRECTIVE_KEYWORD), _DECORATOR_TYPE_IDX, 0))
        n_start, n_end = md.start('name'), md.end('name')
        tokens.append((line_idx, n_start, n_end - n_start, _NAMESPACE_TYPE_IDX, 0))
        p_start, p_end = md.start('path'), md.end('path')
        tokens.append((line_idx, p_start, p_end - p_start, _STRING_TYPE_IDX, 0))

    # Comments. Skip directive lines (already tokenized piece-by-piece above).
    for line_idx, raw in enumerate(raw_lines):
        if line_idx in directive_lines:
            continue
        m = _COMMENT_FULL_LINE.match(raw)
        if m:
            tokens.append((line_idx, m.start(1), len(m.group(1)), _COMMENT_TYPE_IDX, 0))
            continue
        m = _COMMENT_EOL.search(raw)
        if m:
            tokens.append((line_idx, m.start(1), len(m.group(1)), _COMMENT_TYPE_IDX, 0))

    tokens.sort(key=lambda t: (t[0], t[1]))
    return tokens


def _encode_tokens_delta(tokens: List[Tuple[int, int, int, int, int]]) -> List[int]:
    """Encode tokens into LSP's flat int array using delta encoding.
    Each token = [deltaLine, deltaStartChar, length, tokenType, tokenModifiers]."""
    data: List[int] = []
    prev_line = 0
    prev_char = 0
    for line, char, length, type_idx, mods in tokens:
        delta_line = line - prev_line
        delta_char = char - prev_char if delta_line == 0 else char
        data.extend([delta_line, delta_char, length, type_idx, mods])
        prev_line = line
        prev_char = char
    return data


@server.feature(lsp.TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL, TOKEN_LEGEND)
def on_semantic_tokens_full(ls: LanguageServer, params: lsp.SemanticTokensParams) -> lsp.SemanticTokens:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    tokens = _build_tokens(doc.source)
    return lsp.SemanticTokens(data=_encode_tokens_delta(tokens))


# ---------------------------------------------------------------------------
# Hover
# ---------------------------------------------------------------------------

# Matrix piece type_idx -> kind (operators discriminated by literal value).
_MATRIX_TYPE_IDX_TO_KIND: dict[int, str] = {
    _INPUT_NUMBER_TYPE_IDX:  "matrix_input_num",
    _OUTPUT_NUMBER_TYPE_IDX: "matrix_output_num",
    _KEYWORD_TYPE_IDX:       "matrix_scalable",
}


def _classify_position(text: str, line: int, character: int) -> Optional[Tuple[str, str]]:
    """Return `(kind, value)` under the cursor, or None.

    `line` / `character` are 0-based LSP coordinates.
    Kinds map 1:1 to entries in `_HOVER_TEMPLATES`.

    `src_theme` is split into `src_theme_builtin` vs `src_theme_extra` so the
    hover message can explain which list the NAME comes from."""
    parsed_lines, _errors, directives = parse_text(text, built_in_themes=None)
    raw_lines = text.splitlines()
    if not (0 <= line < len(raw_lines)):
        return None
    raw = raw_lines[line]
    line_no = line + 1

    def hit_keyword(c: int) -> bool:
        kw_col = raw.find(_DIRECTIVE_KEYWORD)
        return kw_col >= 0 and kw_col <= c < kw_col + len(_DIRECTIVE_KEYWORD)

    # Directive line (parsed successfully).
    for d in directives:
        if d.line_no != line_no:
            continue
        if hit_keyword(character):
            return ("directive_keyword", _DIRECTIVE_KEYWORD)
        if d.name_span[0] <= character < d.name_span[1]:
            return ("directive_name", d.name)
        if d.path_span[0] <= character < d.path_span[1]:
            return ("directive_path", d.path_raw)
        return None

    # Directive-like line that failed validation (still want hover on pieces).
    md = PATT_DIRECTIVE.search(raw)
    if md:
        if hit_keyword(character):
            return ("directive_keyword", _DIRECTIVE_KEYWORD)
        n_s, n_e = md.start('name'), md.end('name')
        if n_s <= character < n_e:
            return ("directive_name", md.group('name'))
        p_s, p_e = md.start('path'), md.end('path')
        if p_s <= character < p_e:
            return ("directive_path", md.group('path'))
        return None

    # Icon line.
    for p in parsed_lines:
        if p.line_no != line_no:
            continue
        for span_key in ("src_theme", "src_context", "src_icon_name", "dst_context", "dst_icon_name"):
            if span_key not in p.spans:
                continue
            start, end = p.spans[span_key]
            if start <= character < end:
                value = raw[start:end]
                if span_key == "src_theme":
                    return ("src_theme_builtin" if value in BUILT_IN_ICON_THEMES else "src_theme_extra", value)
                return (span_key, value)
        if "size_io_matrix" in p.spans:
            start, end = p.spans["size_io_matrix"]
            if start <= character < end:
                matrix_text = raw[start:end]
                for _l, col, length, type_idx in _tokenize_size_matrix(matrix_text, start, line_no):
                    if col <= character < col + length:
                        piece = raw[col:col + length]
                        if type_idx == _OPERATOR_TYPE_IDX:
                            return ("matrix_op_gt" if piece == '>' else "matrix_op_dash", piece)
                        kind = _MATRIX_TYPE_IDX_TO_KIND.get(type_idx)
                        if kind:
                            return (kind, piece)
                return None  # in matrix but on `;` / whitespace
        return None

    # Comment.
    mf = _COMMENT_FULL_LINE.match(raw)
    if mf and mf.start(1) <= character < mf.end(1):
        return ("comment", mf.group(1))
    me = _COMMENT_EOL.search(raw)
    if me and me.start(1) <= character < me.end(1):
        return ("comment", me.group(1))
    return None


_HOVER_TEMPLATES: dict[str, str] = {
    "src_theme_builtin": "**Built-in theme**: `{value}`\n\nOne of the themes bundled with tango-remixer.",
    "src_theme_extra":   "**Extra theme**: `{value}`\n\nDeclared in this file via `# @extra-icon-theme`, or passed via the `--extra-icon-theme` CLI flag.",
    "src_context":       "**Source icon context**: `{value}`\n\nXDG context (e.g. apps, places, mimetypes). Optional. Usually omitted since XDG icon names are unique within a theme.",
    "src_icon_name":     "**Source icon name**: `{value}`\n\nName of the icon picked from the source theme. No extension.",
    "dst_context":       "**Destination icon context**: `{value}`\n\nContext under which the icon is written in the output theme. Falls back to source context if omitted.",
    "dst_icon_name":     "**Destination icon name**: `{value}`\n\nName the icon is written as in the output theme. Falls back to source name if omitted.",
    "matrix_input_num":  "**Input size**: `{value}`\n\nPick this size from the source theme.",
    "matrix_output_num": "**Output size**: `{value}`\n\nWrite the picked source at this size.",
    "matrix_op_gt":      "**Resize operator** `>`\n\n`INPUT>OUTPUT` -- pick the source at INPUT size, write at OUTPUT size.",
    "matrix_op_dash":    "**Range operator** `-`\n\n`LOW-HIGH` picks every available size in `[LOW..HIGH]`. Open ranges: `-N` from min, `N-` to max.",
    "matrix_scalable":   "**`scalable`** (SVG source)\n\nUse with `>OUTPUT` to rasterize the SVG at the OUTPUT size.",
    "directive_keyword": "**`@extra-icon-theme`** directive\n\nDeclare an extra XDG icon theme inline. NAME becomes usable in icon lines below. The LSP also reads this for theme-name validation.",
    "directive_name":    "**Extra theme NAME**: `{value}`\n\nDeclared by this directive. Use as the first column in icon lines below.",
    "directive_path":    "**Extra theme PATH**: `{value}`\n\nResolved relative to this file's directory. Forward-slash only.",
    "comment":           "Comment.",
}


@server.feature(lsp.TEXT_DOCUMENT_HOVER)
def on_hover(ls: LanguageServer, params: lsp.HoverParams) -> Optional[lsp.Hover]:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    classified = _classify_position(doc.source, params.position.line, params.position.character)
    if not classified:
        return None
    kind, value = classified
    template = _HOVER_TEMPLATES.get(kind)
    if not template:
        return None
    return lsp.Hover(contents=lsp.MarkupContent(
        kind=lsp.MarkupKind.Markdown,
        value=template.format(value=value),
    ))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the server over stdio (the standard LSP transport for editors)."""
    server.start_io()


if __name__ == "__main__":
    main()
