#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for `read_included_icons_txt` in build_icons.py — the parser
for the `included_icons.txt` configuration file.

These tests exercise the parser's line-level behavior (separators,
comments, optional fields, .svg stripping, error cases). The real
filesystem-walking `IconFileSearcher` is replaced with a fake that
returns a synthetic IconSrcFileInfo for any lookup, so we focus on
parsing logic and not on whether SVGs exist on disk.

Note: the parser accepts either a tab or 4+ spaces as a field
separator. Most tests below use 4 spaces for readability; the few
tab-specific cases live in TestSeparators.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, List, Protocol

# build_icons.py parses CLI args at import time -> spoof argv first.
sys.argv = [
    "test_read_included_icons_txt.py",
    "--included-icon-file", str(Path(__file__).parent / "_dummy_not_used.txt"),
]

from build_icons import (  # noqa: E402
    read_included_icons_txt,
    IconSrcFileInfo,
    ParsedIncludedIcon,
)


class IconSearcherLike(Protocol):
    """Structural type that the fake searchers below conform to.
    Matches the subset of IconFileSearcher used by read_included_icons_txt."""

    def find_src_icon_of_any_size(
        self, theme: str, icon_name: str, context: Optional[str],
    ) -> Optional[IconSrcFileInfo]: ...


def _fake_icon(theme: str, icon_name: str, context: str) -> IconSrcFileInfo:
    """Build a synthetic IconSrcFileInfo for fake searchers."""
    return IconSrcFileInfo(
        theme_src_folder_name=theme,
        context=context,  # type: ignore[arg-type]
        size="16",
        scale="1",
        icon_name=icon_name,
        file_name=f"{icon_name}.svg",
        src_file_path=Path(f"/fake/{theme}/{icon_name}.svg"),
        src_file_path_is_symlink=False,
        src_file_path_resolved=Path(f"/fake/{theme}/{icon_name}.svg"),
    )


class AlwaysFoundIconFileSearcher:
    """Searcher that always finds the icon, reporting whatever `context`
    the caller asked for (or "apps" if the caller passed None).
    Used as the default happy-path searcher."""

    def find_src_icon_of_any_size(
        self, theme: str, icon_name: str, context: Optional[str],
    ) -> Optional[IconSrcFileInfo]:
        return _fake_icon(theme, icon_name, context or "apps")


class NotFoundIconFileSearcher:
    """Searcher that never finds anything — used to test the not-found branches."""

    def find_src_icon_of_any_size(
        self, theme: str, icon_name: str, context: Optional[str],
    ) -> Optional[IconSrcFileInfo]:
        return None


class FixedContextIconFileSearcher:
    """Searcher where the icon lives in exactly one context.
    Returns the icon when asked with `context=None` (any context) or with
    the matching context; returns None when asked with a different context.
    Used to test "icon exists but user asked for the wrong context".
    """

    def __init__(self, icon_context: str) -> None:
        self._icon_context = icon_context

    def find_src_icon_of_any_size(
        self, theme: str, icon_name: str, context: Optional[str],
    ) -> Optional[IconSrcFileInfo]:
        if context is not None and context != self._icon_context:
            return None
        return _fake_icon(theme, icon_name, self._icon_context)


def _parse_multi_lines(text: str, searcher: Optional[IconSearcherLike] = None) -> List[ParsedIncludedIcon]:
    """Write multi-line `included_icons.txt`-format `text` to a temp file
    and parse it. Returns the list of parsed entries (one per non-comment,
    non-blank line)."""
    s: IconSearcherLike = searcher or AlwaysFoundIconFileSearcher()
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        path: Path = Path(f.name)
    try:
        return read_included_icons_txt(s, path)  # type: ignore[arg-type]
    finally:
        path.unlink()


def _parse_line(text: str, searcher: Optional[IconSearcherLike] = None) -> ParsedIncludedIcon:
    """Parse `text` and return the (single) parsed entry.
    For tests where exactly one entry is expected."""
    return _parse_multi_lines(text, searcher)[0]


class TestBasicLines(unittest.TestCase):
    """Smallest valid line forms."""

    def test_theme_and_icon_only(self) -> None:
        # `THEME    ICON` -> src_theme + src_icon_name, no dst.
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    document-save")
        self.assertEqual(parsed_line.src_theme, "Tango")
        self.assertEqual(parsed_line.src_icon_name, "document-save")
        self.assertEqual(parsed_line.dst_icon_name, None)


class TestSeparators(unittest.TestCase):
    """Field separator can be one-or-more tabs OR four-or-more spaces."""

    def test_single_tab_separator(self) -> None:
        parsed_line: ParsedIncludedIcon = _parse_line("Tango\tuser-home")
        self.assertEqual(parsed_line.src_icon_name, "user-home")

    def test_double_tab_separator(self) -> None:
        # Multiple consecutive tabs collapse to a single separator (regex `\t+`).
        parsed_line: ParsedIncludedIcon = _parse_line("Tango\t\tuser-home")
        self.assertEqual(parsed_line.src_icon_name, "user-home")

    def test_four_space_separator(self) -> None:
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    user-home")
        self.assertEqual(parsed_line.src_icon_name, "user-home")

    def test_many_spaces_separator(self) -> None:
        # More than 4 spaces also valid (regex `[ ][ ][ ][ ]+`).
        parsed_line: ParsedIncludedIcon = _parse_line("Tango        user-home")
        self.assertEqual(parsed_line.src_icon_name, "user-home")

    def test_mixed_tab_then_spaces(self) -> None:
        # Tab between theme/src, 4 spaces between src/dst.
        parsed_line: ParsedIncludedIcon = _parse_line("Tango\tfolder    folder-blue")
        self.assertEqual(parsed_line.src_icon_name, "folder")
        self.assertEqual(parsed_line.dst_icon_name, "folder-blue")

    def test_mixed_spaces_then_tab(self) -> None:
        # 4 spaces between theme/src, tab between src/dst.
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    folder\tfolder-blue")
        self.assertEqual(parsed_line.src_icon_name, "folder")
        self.assertEqual(parsed_line.dst_icon_name, "folder-blue")

    def test_mixed_tabs_and_many_spaces(self) -> None:
        # Multiple tabs in one slot, many spaces in the other.
        parsed_line: ParsedIncludedIcon = _parse_line("Tango\t\tfolder      folder-blue")
        self.assertEqual(parsed_line.src_icon_name, "folder")
        self.assertEqual(parsed_line.dst_icon_name, "folder-blue")


class TestComments(unittest.TestCase):
    """Comments and blank lines should be ignored."""

    def test_full_line_comment(self) -> None:
        # Comment line is skipped, only the data line produces an entry.
        result: List[ParsedIncludedIcon] = _parse_multi_lines(
            "# Section: file actions\nTango    document-open"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].src_icon_name, "document-open")

    def test_end_of_line_comment_after_space(self) -> None:
        # EOL comment must be preceded by space or tab to be stripped.
        # Single-line input — EOL comment is stripped, the line still parses.
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    document-open # used in File>Open")
        self.assertEqual(parsed_line.src_icon_name, "document-open")

    def test_blank_line_skipped(self) -> None:
        # Leading blank line is skipped, only the data line produces an entry.
        result: List[ParsedIncludedIcon] = _parse_multi_lines("\nTango    go-up")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].src_icon_name, "go-up")

    def test_whitespace_only_line_skipped(self) -> None:
        # Whitespace-only line is skipped, only the data line produces an entry.
        result: List[ParsedIncludedIcon] = _parse_multi_lines("   \nTango    go-down")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].src_icon_name, "go-down")


class TestContext(unittest.TestCase):
    """Optional context in src and dst (specified via the `context/icon` syntax)."""

    def test_dst_context_override_preserved(self) -> None:
        # User explicitly specifies destination context different from src.
        # Per the comment in build_icons.py: an explicit dst context should
        # let user forcibly change the context of an icon.
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    network-server    places/network-blue")
        self.assertEqual(parsed_line.src_context, "apps")     # fake default
        self.assertEqual(parsed_line.src_icon_name, "network-server")
        self.assertEqual(parsed_line.dst_context, "places")
        self.assertEqual(parsed_line.dst_icon_name, "network-blue")

    def test_dst_context_defaults_to_src(self) -> None:
        # When dst has no context, dst_context should fall back to src_context.
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    document-save    document-export")
        self.assertEqual(parsed_line.src_context, "apps")     # fake default
        self.assertEqual(parsed_line.src_icon_name, "document-save")
        self.assertEqual(parsed_line.dst_context, "apps")     # fallback
        self.assertEqual(parsed_line.dst_icon_name, "document-export")

    def test_src_context_no_dst(self) -> None:
        # src has explicit context, no dst at all: dst_context should still
        # fall back to the src's context (not stay None).
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    places/folder-documents")
        self.assertEqual(parsed_line.src_context, "places")
        self.assertEqual(parsed_line.src_icon_name, "folder-documents")
        self.assertEqual(parsed_line.dst_context, "places")
        self.assertEqual(parsed_line.dst_icon_name, None)

    def test_src_context_dst_no_context(self) -> None:
        # src has explicit context, dst doesn't: dst_context falls back
        # to the src's user-specified context, not to a generic default.
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    places/folder-documents    folder-docs")
        self.assertEqual(parsed_line.src_context, "places")
        self.assertEqual(parsed_line.src_icon_name, "folder-documents")
        self.assertEqual(parsed_line.dst_context, "places")
        self.assertEqual(parsed_line.dst_icon_name, "folder-docs")

    def test_both_contexts_explicit_and_different(self) -> None:
        # src and dst each have their own explicit, different context.
        # Both should be retained independently.
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    places/folder-documents    actions/folder-doc")
        self.assertEqual(parsed_line.src_context, "places")
        self.assertEqual(parsed_line.src_icon_name, "folder-documents")
        self.assertEqual(parsed_line.dst_context, "actions")
        self.assertEqual(parsed_line.dst_icon_name, "folder-doc")


class TestExtensionStripping(unittest.TestCase):
    """`.svg` extensions in icon names should be stripped."""

    def test_strip_svg_from_src(self) -> None:
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    document-open.svg")
        self.assertEqual(parsed_line.src_icon_name, "document-open")

    def test_strip_svg_from_dst(self) -> None:
        parsed_line: ParsedIncludedIcon = _parse_line("Tango    document-save    document-save-as.svg")
        self.assertEqual(parsed_line.dst_icon_name, "document-save-as")


class TestErrors(unittest.TestCase):
    """Invalid input raises clear errors."""

    def test_invalid_theme_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            _parse_line("DefinitelyNotATheme    document-open")

    def test_garbage_line_raises(self) -> None:
        # A line that doesn't match the line format at all.
        with self.assertRaises(RuntimeError):
            _parse_line("nonsense-without-separator")

    def test_single_space_separator_is_invalid(self) -> None:
        # The parser requires tab or 4+ spaces; a single space is not a separator.
        with self.assertRaises(RuntimeError):
            _parse_line("Tango document-open")

    def test_icon_not_found_in_specified_context_raises(self) -> None:
        # The icon DOES exist (in "apps"), but the user asked for it in
        # "places" -> the wrong-context lookup returns None.
        # Must hit the "specified context" raise (build_icons line ~1108).
        searcher = FixedContextIconFileSearcher(icon_context="apps")
        with self.assertRaises(FileNotFoundError) as cm:
            _parse_line("Tango    places/folder-documents", searcher=searcher)
        msg: str = str(cm.exception)
        self.assertIn("specified context", msg)
        self.assertIn('"places"', msg)

    def test_icon_not_found_in_any_context_raises(self) -> None:
        # No src context specified, and searcher can't find the icon anywhere.
        # Must hit the "no specified context" raise (build_icons line ~1112)
        # — verify by ensuring the message does NOT contain the
        # "specified context" phrase that's unique to the other branch.
        with self.assertRaises(FileNotFoundError) as cm:
            _parse_line("Tango    folder-documents", searcher=NotFoundIconFileSearcher())
        msg: str = str(cm.exception)
        self.assertNotIn("specified context", msg)
        self.assertIn("folder-documents", msg)
        self.assertIn("Tango", msg)


class TestMultipleLines(unittest.TestCase):
    """Multiple lines parse independently and order is preserved."""

    def test_three_lines(self) -> None:
        text: str = (
            "Tango    document-open\n"
            "Tango    document-save    document-export\n"
            "Tango    folder-pictures\n"
        )
        result: List[ParsedIncludedIcon] = _parse_multi_lines(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].src_theme, "Tango")
        self.assertEqual(result[0].src_icon_name, "document-open")
        self.assertEqual(result[1].src_icon_name, "document-save")
        self.assertEqual(result[1].dst_icon_name, "document-export")
        self.assertEqual(result[2].src_icon_name, "folder-pictures")

    def test_comments_interleaved_with_lines(self) -> None:
        text: str = (
            "# Section: file actions\n"
            "Tango    document-open\n"
            "\n"
            "# Section: places\n"
            "Tango    folder-documents\n"
        )
        result: List[ParsedIncludedIcon] = _parse_multi_lines(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].src_icon_name, "document-open")
        self.assertEqual(result[1].src_icon_name, "folder-documents")


if __name__ == "__main__":
    unittest.main()
