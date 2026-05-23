#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for `SizeIoMatrix` in build_icons.py.

These tests describe the *intended* behavior per the docstring of
`SizeIoMatrix.parse_full_matrix_expr`. Several of them are expected to
fail on the current implementation because of two known bugs:

1. `add_resize_io` appends to `self.all_data` from inside its own
   `for other in self.all_data` loop. As a result:
   - When `all_data` is empty (the very first add), the loop body
     never runs, so nothing is appended at all.
   - When `all_data` has N items and none conflicts, the new entry
     gets appended N times.

2. `add_by_range` compares sizes as strings (e.g. `"16" <= "128"`),
   which is lexicographic, not numeric. Any range that crosses a
   digit-count boundary (e.g. `16-128`, `22-256`) silently excludes
   some sizes it should include.

Run:
    python3 -m unittest test_size_io_matrix.py -v
"""

import sys
import unittest
from pathlib import Path

# build_icons.py parses CLI args at module import time, so we have to
# spoof sys.argv before importing it. The path doesn't need to exist
# because argparse only converts the string to a Path object.
sys.argv = [
    "test_size_io_matrix.py",
    "--included-icon-file", str(Path(__file__).parent / "_dummy_not_used.txt"),
]

from build_icons import SizeIoMatrix, SizeIo  # noqa: E402


class TestSingleSize(unittest.TestCase):
    """Single size expression, e.g. `16` -> input=16 output=16."""

    def test_single_size(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("16", line_no=1)
        self.assertEqual(m.all_data, [SizeIo(input="16", output="16")])

    def test_single_with_explicit_self_resize(self) -> None:
        # Per docstring: `16>16` should be equivalent to `16`.
        m: SizeIoMatrix = SizeIoMatrix("16>16", line_no=1)
        self.assertEqual(m.all_data, [SizeIo(input="16", output="16")])


class TestMultipleSegments(unittest.TestCase):
    """Multiple expressions separated by `;`."""

    def test_two_singles(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("16;22", line_no=1)
        self.assertEqual(m.all_data, [
            SizeIo(input="16", output="16"),
            SizeIo(input="22", output="22"),
        ])

    def test_self_resize_then_single(self) -> None:
        # Per docstring: `16>16;22` is the same as `16;22`.
        m: SizeIoMatrix = SizeIoMatrix("16>16;22", line_no=1)
        self.assertEqual(m.all_data, [
            SizeIo(input="16", output="16"),
            SizeIo(input="22", output="22"),
        ])

    def test_single_plus_range(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("16;24-48", line_no=1)
        inputs: list[str] = [io.input for io in m.all_data]
        self.assertEqual(inputs, ["16", "24", "32", "36", "48"])


class TestResize(unittest.TestCase):
    """Resize expression `INPUT>OUTPUT`."""

    def test_simple_resize(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("16>32", line_no=1)
        self.assertEqual(m.all_data, [SizeIo(input="16", output="32")])

    def test_two_resizes(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("16>32;32>64", line_no=1)
        self.assertEqual(m.all_data, [
            SizeIo(input="16", output="32"),
            SizeIo(input="32", output="64"),
        ])

    def test_scalable_as_input(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("scalable>48", line_no=1)
        self.assertEqual(m.all_data, [SizeIo(input="scalable", output="48")])

    def test_scalable_as_output_is_rejected(self) -> None:
        with self.assertRaises(SyntaxError):
            SizeIoMatrix("16>scalable", line_no=1)


class TestRange(unittest.TestCase):
    """Range expression `FROM-TO`. Each size in range maps to itself."""

    def test_range_within_two_digits(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("16-32", line_no=1)
        inputs: list[str] = [io.input for io in m.all_data]
        self.assertEqual(inputs, ["16", "22", "24", "32"])
        for io in m.all_data:
            self.assertEqual(io.input, io.output)

    def test_range_to_48(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("16-48", line_no=1)
        inputs: list[str] = [io.input for io in m.all_data]
        self.assertEqual(inputs, ["16", "22", "24", "32", "36", "48"])

    def test_range_crossing_digit_boundary(self) -> None:
        # Exposes bug 2: string compare fails when digit count differs.
        # `"16" <= "128"` is False lexically, so 16 wrongly gets excluded.
        m: SizeIoMatrix = SizeIoMatrix("16-128", line_no=1)
        inputs: list[str] = [io.input for io in m.all_data]
        self.assertEqual(
            inputs,
            ["16", "22", "24", "32", "36", "48", "64", "72", "96", "128"],
        )

    def test_open_range_left(self) -> None:
        # Per docstring: `-48` is the same as `16-48`.
        m: SizeIoMatrix = SizeIoMatrix("-48", line_no=1)
        inputs: list[str] = [io.input for io in m.all_data]
        self.assertEqual(inputs, ["16", "22", "24", "32", "36", "48"])

    def test_open_range_right(self) -> None:
        # Per docstring: `32-` is the same as `32-128`.
        m: SizeIoMatrix = SizeIoMatrix("32-", line_no=1)
        inputs: list[str] = [io.input for io in m.all_data]
        self.assertEqual(inputs, ["32", "36", "48", "64", "72", "96", "128"])


class TestInvalidSyntax(unittest.TestCase):
    """Bad input should raise SyntaxError."""

    def test_garbage(self) -> None:
        with self.assertRaises(SyntaxError):
            SizeIoMatrix("foo", line_no=1)

    def test_empty_segment(self) -> None:
        with self.assertRaises(SyntaxError):
            SizeIoMatrix("16;;22", line_no=1)

    def test_duplicate_input_size(self) -> None:
        # Once the append-in-loop bug is fixed, the second `16>...` should
        # be rejected as a duplicate input size.
        with self.assertRaises(SyntaxError):
            SizeIoMatrix("16>32;16>48", line_no=1)

    def test_duplicate_output_size(self) -> None:
        # Once the append-in-loop bug is fixed, the second `...>32` should
        # be rejected as a duplicate output size.
        with self.assertRaises(SyntaxError):
            SizeIoMatrix("16>32;24>32", line_no=1)


class TestHelpers(unittest.TestCase):
    """`is_empty()` and `get_all_input_sizes()`."""

    def test_get_all_input_sizes_deduplicates(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("16-32", line_no=1)
        self.assertEqual(m.get_all_input_sizes(), {"16", "22", "24", "32"})

    def test_is_empty_after_parsing(self) -> None:
        m: SizeIoMatrix = SizeIoMatrix("16", line_no=1)
        self.assertFalse(m.is_empty())


if __name__ == "__main__":
    unittest.main()
