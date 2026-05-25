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

import sys
from pathlib import Path
from typing import List

# Make project root importable so `from lib.included_icons_parser import ...` works
# when this server is launched directly by an editor.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lsprotocol import types as lsp  # noqa: E402
from pygls.lsp.server import LanguageServer  # noqa: E402   # pygls 2.x path

from lib.included_icons_parser import parse_text  # noqa: E402


SERVER_NAME: str = "tango-remixer-included-icons-lsp"
SERVER_VERSION: str = "0.1.0"

server = LanguageServer(name=SERVER_NAME, version=SERVER_VERSION)


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
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the server over stdio (the standard LSP transport for editors)."""
    server.start_io()


if __name__ == "__main__":
    main()
