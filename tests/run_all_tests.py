#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Custom unittest runner that prints a header whenever the current
test's class changes (so output reads class-first instead of having
the class name buried in parentheses) and colorizes status (ok green,
FAIL/ERROR red, skips yellow) when stdout is a TTY.

Run from the project root:
    python3 tests/run_all_tests.py
"""

import os
import sys
import unittest
from pathlib import Path

# Make project root importable so test files can `from build_icons import ...`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ANSI colors, disabled when not writing to a TTY or when NO_COLOR is set
# (https://no-color.org/).
_USE_COLOR: bool = sys.stdout.isatty() and "NO_COLOR" not in os.environ
_GREEN: str = "\033[32m"
_RED: str = "\033[31m"
_YELLOW: str = "\033[33m"
_RESET: str = "\033[0m"


def _c(text: str, color: str) -> str:
    return f"{color}{text}{_RESET}" if _USE_COLOR else text


class _ClassGroupedResult(unittest.TextTestResult):
    """TextTestResult that prints a class header on class change and
    colorizes the trailing status word."""

    def __init__(self, stream, descriptions, verbosity) -> None:
        super().__init__(stream, descriptions, verbosity)
        self._current_class: str | None = None

    def startTest(self, test) -> None:
        # Bookkeeping only — skip TextTestResult's default "description ... " write.
        unittest.TestResult.startTest(self, test)

        cls_name: str = type(test).__name__
        if cls_name != self._current_class:
            if self._current_class is not None:
                self.stream.writeln()
            self.stream.writeln(cls_name)
            self.stream.writeln("-" * len(cls_name))
            self._current_class = cls_name

        if self.showAll:
            self.stream.write(f"  {test._testMethodName} ... ")
            self.stream.flush()
            # Tell TextTestResult we're not at a new line, so the add* hooks
            # below don't re-print the full description before the status.
            self._newline = False

    def _write_colored_status(self, status: str, color: str) -> None:
        self.stream.writeln(_c(status, color))
        self.stream.flush()
        self._newline = True

    def addSuccess(self, test) -> None:
        unittest.TestResult.addSuccess(self, test)
        if self.showAll:
            self._write_colored_status("ok", _GREEN)
        elif self.dots:
            self.stream.write(_c(".", _GREEN))
            self.stream.flush()

    def addError(self, test, err) -> None:
        unittest.TestResult.addError(self, test, err)
        if self.showAll:
            self._write_colored_status("ERROR", _RED)
        elif self.dots:
            self.stream.write(_c("E", _RED))
            self.stream.flush()

    def addFailure(self, test, err) -> None:
        unittest.TestResult.addFailure(self, test, err)
        if self.showAll:
            self._write_colored_status("FAIL", _RED)
        elif self.dots:
            self.stream.write(_c("F", _RED))
            self.stream.flush()

    def addSkip(self, test, reason) -> None:
        unittest.TestResult.addSkip(self, test, reason)
        if self.showAll:
            self._write_colored_status(f"skipped {reason!r}", _YELLOW)
        elif self.dots:
            self.stream.write(_c("s", _YELLOW))
            self.stream.flush()


def _flatten(suite: unittest.TestSuite):
    """Yield individual test cases from a (possibly nested) TestSuite."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


def _is_integration(test: unittest.TestCase) -> bool:
    """Test belongs to an integration module (slow, depends on submodules)."""
    return "integration" in type(test).__module__.lower()


def main() -> int:
    loader = unittest.TestLoader()
    raw_suite = loader.discover("tests")

    # Run unit tests first; integration tests last (slower, deps on
    # submodules/inkscape). Within each bucket keep module/class/method
    # alphabetical so output stays stable.
    ordered = sorted(
        _flatten(raw_suite),
        key=lambda t: (
            _is_integration(t),
            type(t).__module__,
            type(t).__name__,
            t._testMethodName,
        ),
    )
    suite = unittest.TestSuite(ordered)

    runner = unittest.TextTestRunner(resultclass=_ClassGroupedResult, verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
