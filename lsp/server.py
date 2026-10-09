#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LSP server for `included_icons.txt`.

Install + editor setup: see `lsp/README.md`.
Run via stdio: `python -m lsp`.

Wires up pygls. Reacts to didOpen / didChange / didSave.
`_validate()` runs `parse_text` and turns each `ParseError` into an LSP
`Diagnostic` (line + column range, severity Error).
"""

from __future__ import annotations

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
from lib.included_icons_tokens import (  # noqa: E402
    KINDS, SPAN_KINDS, DIRECTIVE_KEYWORD, COMMENT_FULL_LINE, COMMENT_EOL, tokenize, tokenize_size_matrix,
)
from urllib.parse import urlparse, unquote  # noqa: E402


SERVER_NAME: str = "tango-remixer-included-icons-lsp"
SERVER_VERSION: str = "0.1.0"

server = LanguageServer(name=SERVER_NAME, version=SERVER_VERSION)


# Semantic token legend. Editors color tokens by these LSP-standard types.
# The order is the index used by `tokenType` in the wire format, and the order of
# lib/included_icons_tokens.py's KINDS, where the tokens come from.
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
_SPAN_KEY_TO_TYPE_IDX: dict[str, int] = {key: KINDS.index(kind) for key, kind in SPAN_KINDS.items()}
_NAMESPACE_TYPE_IDX: int = KINDS.index("theme")
_COMMENT_TYPE_IDX: int = KINDS.index("comment")
_INPUT_NUMBER_TYPE_IDX: int = KINDS.index("input_size")
_OUTPUT_NUMBER_TYPE_IDX: int = KINDS.index("output_size")
_OPERATOR_TYPE_IDX: int = KINDS.index("operator")
_KEYWORD_TYPE_IDX: int = KINDS.index("keyword")
_DECORATOR_TYPE_IDX: int = KINDS.index("directive")
_STRING_TYPE_IDX: int = KINDS.index("string")

_DIRECTIVE_KEYWORD = DIRECTIVE_KEYWORD
_COMMENT_FULL_LINE, _COMMENT_EOL = COMMENT_FULL_LINE, COMMENT_EOL   # hover classifies comments with the tokenizer's regexes


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

# The tokens come from lib/included_icons_tokens.py (shared with the website's code blocks); here they are
# put into the legend's indices and the wire format.

def _tokenize_size_matrix(matrix_text: str, base_col: int, line_no: int) -> List[Tuple[int, int, int, int, int]]:
    """Per-piece tokens for the inside of `{...}`, as `(line, col, length, type_idx, mods)`;
    `line_no` is 1-based, the line in the tuples 0-based. `mods` is always 0 here."""
    return [(t.line, t.col, t.length, KINDS.index(t.kind), 0) for t in tokenize_size_matrix(matrix_text, base_col, line_no - 1)]


def _build_tokens(text: str) -> List[Tuple[int, int, int, int, int]]:
    """Collect `(line, col, length, type_idx, mods)` tokens. Sorted by position.
    Lines are 0-based for LSP. `mods` is a bitmask over `TOKEN_MODIFIERS`: a
    built-in theme's name gets defaultLibrary, so editors can color it distinctly."""
    return [(t.line, t.col, t.length, KINDS.index(t.kind), _MOD_DEFAULT_LIBRARY if t.builtin else 0) for t in tokenize(text)]


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
            # Extend the hover region to include the surrounding `{` and `}` so
            # hovering anywhere on the block (braces, separators, whitespace)
            # still shows the overview.
            brace_start = start - 1 if start > 0 and raw[start - 1] == '{' else start
            brace_end = end + 1 if end < len(raw) and raw[end] == '}' else end
            if brace_start <= character < brace_end:
                matrix_text = raw[start:end]
                for _l, col, length, type_idx, _mods in _tokenize_size_matrix(matrix_text, start, line_no):
                    if col <= character < col + length:
                        piece = raw[col:col + length]
                        if type_idx == _OPERATOR_TYPE_IDX:
                            return ("matrix_op_gt" if piece == '>' else "matrix_op_dash", piece)
                        kind = _MATRIX_TYPE_IDX_TO_KIND.get(type_idx)
                        if kind:
                            return (kind, piece)
                # Fallback: on `{`, `}`, `;`, or whitespace -- block-level hover.
                return ("size_matrix_block", raw[brace_start:brace_end])
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
    "size_matrix_block": "**Size matrix** `{value}`\n\nRestricts which input sizes are picked from the source theme and optionally remaps them to output sizes. Segments are separated by `;`.\n\n- `16` -- single (= `16>16`)\n- `16-32` -- range; picks every available size in `[16..32]`\n- `-N` / `N-` -- open range from min / to max\n- `16>32` -- resize: pick size 16, write at 32\n- `scalable>48` -- rasterize the SVG at 48\n\n`scalable` is only valid as a resize input. `{scalable}`, `{N>scalable}`, and ranges with `scalable` are rejected.",
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
