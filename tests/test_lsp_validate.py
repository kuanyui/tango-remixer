#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for `_validate` in lsp/server.py.

Direct unit tests on the function. No LSP server is started.
Skipped when `pygls` / `lsprotocol` are not installed.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from lsp.server import _validate
    from lsprotocol import types as lsp
    HAS_LSP_DEPS = True
except ImportError:
    HAS_LSP_DEPS = False


@unittest.skipUnless(HAS_LSP_DEPS, "pygls / lsprotocol not installed")
class TestValidate(unittest.TestCase):

    def test_good_text_yields_no_diagnostics(self) -> None:
        diags = _validate("Tango    document-save")
        self.assertEqual(diags, [])

    def test_bad_line_yields_one_error_diagnostic(self) -> None:
        diags = _validate("garbage-no-separator")
        self.assertEqual(len(diags), 1)
        d = diags[0]
        self.assertEqual(d.severity, lsp.DiagnosticSeverity.Error)
        # Line 0 (LSP is 0-based) -- our line_no=1 maps to LSP line=0.
        self.assertEqual(d.range.start.line, 0)
        self.assertEqual(d.range.end.line, 0)
        self.assertEqual(d.range.start.character, 0)
        self.assertEqual(d.range.end.character, len("garbage-no-separator"))

    def test_collects_multiple_errors(self) -> None:
        text = "garbage-one\nTango    document-save\ngarbage-two"
        diags = _validate(text)
        # 2 bad lines -> 2 diagnostics. Good line in the middle skipped.
        self.assertEqual(len(diags), 2)
        # First bad line at LSP line 0; second at LSP line 2.
        self.assertEqual(diags[0].range.start.line, 0)
        self.assertEqual(diags[1].range.start.line, 2)

    def test_bad_matrix_diagnostic_points_at_matrix(self) -> None:
        # `scalable` as OUTPUT is rejected by SizeIoMatrix.
        line = "Tango    foo    foo    {16>scalable}"
        diags = _validate(line)
        self.assertEqual(len(diags), 1)
        d = diags[0]
        # Range should cover the `16>scalable` expression inside the braces.
        self.assertEqual(line[d.range.start.character:d.range.end.character], "16>scalable")

    def test_unknown_theme_now_validated_against_builtin(self) -> None:
        # _validate passes BUILT_IN_ICON_THEMES, so unknown themes get flagged.
        diags = _validate("BogusTheme    document-save")
        self.assertTrue(any("Unknown theme" in d.message for d in diags))

    def test_directive_path_missing_emits_warning(self) -> None:
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmp:
            txt = os.path.join(tmp, "included_icons.txt")
            with open(txt, "w") as f:
                f.write("# @extra-icon-theme MyIcons /definitely/not/a/real/path\n")
            uri = "file://" + txt
            diags = _validate(open(txt).read(), uri)
        warnings = [d for d in diags if d.severity == lsp.DiagnosticSeverity.Warning]
        self.assertEqual(len(warnings), 1)
        self.assertIn("does not exist", warnings[0].message)

    def test_directive_unlocks_theme_validation(self) -> None:
        # Directive adds MyIcons -> the icon line referencing MyIcons must pass.
        text = (
            "# @extra-icon-theme MyIcons /tmp\n"
            "MyIcons    document-save\n"
        )
        diags = _validate(text)
        # No "Unknown theme" errors (path-missing warning is OK).
        errors = [d for d in diags if d.severity == lsp.DiagnosticSeverity.Error]
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
