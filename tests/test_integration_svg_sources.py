#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration check: no built-in theme source SVG may need a repair from
tools/fix_svg_for_browsers.py. A failure lists the offending files; run
`make fix-svg` and commit the result in the affected submodule.

Reads every source SVG once (slow on network mounts). Skipped when the
submodules are not checked out."""

import contextlib
import io
import sys
import unittest
from pathlib import Path

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "tools"))

import fix_svg_for_browsers as tool  # noqa: E402


class TestSourceSvgsRenderInBrowsers(unittest.TestCase):

    @unittest.skipUnless(tool.built_in_theme_folders(), "theme submodules not checked out")
    def test_built_in_theme_sources_need_no_repair(self) -> None:
        report = io.StringIO()
        with contextlib.redirect_stdout(report):
            status = tool.main(["--check"])
        self.assertEqual(status, 0, "\n" + report.getvalue())


if __name__ == "__main__":
    unittest.main()
