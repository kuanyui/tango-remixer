#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for tools/fix_svg_for_browsers.py: the two repairs (group inside
`<clipPath>`, userSpaceOnUse `<mask>` without a region), the cases that must be
left alone, idempotency and `--check`. All documents are tiny synthetic SVGs."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "tools"))

import fix_svg_for_browsers as tool  # noqa: E402


def _svg(body: str, root: str = 'width="48" height="48"') -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" {root}>\n{body}\n</svg>\n'


_MASK: str = '<defs><mask maskUnits="userSpaceOnUse" id="m"><rect x="16" y="100" width="48" height="48" fill="#fff"/></mask></defs>'


class TestClipPathGroup(unittest.TestCase):

    def test_group_is_unwrapped(self) -> None:
        new, notes = tool.fix(_svg('<clipPath id="c">\n  <g id="g1">\n    <rect width="4" height="4"/>\n  </g>\n</clipPath>'))
        self.assertNotIn("<g", new)
        self.assertIn('<rect width="4" height="4"/>', new)
        self.assertEqual(len(notes), 1)

    def test_group_transform_moves_onto_every_child(self) -> None:
        new, _ = tool.fix(_svg('<clipPath id="c"><g transform="translate(0,-1)">'
                               '<rect width="4" height="4" transform="scale(2)"/><path d="M0 0h1"/></g></clipPath>'))
        self.assertIn('transform="translate(0,-1) scale(2)"', new)      # in front of the child's own transform
        self.assertRegex(new, r'<path d="M0 0h1"\s+transform="translate\(0,-1\)"')
        self.assertNotIn("<g", new)


class TestMaskRegion(unittest.TestCase):

    def region(self, new: str) -> tuple:
        tag = new[new.index("<mask"):new.index(">", new.index("<mask"))]
        return tuple(round(float(tool._attribute(tag, k)), 2) for k in ("x", "y", "width", "height"))

    def test_canvas_is_expressed_in_the_masked_elements_user_space(self) -> None:
        new, notes = tool.fix(_svg(_MASK + '<g mask="url(#m)" transform="translate(-16,-100)"><path d="M20 110h30"/></g>'))
        self.assertEqual(self.region(new), (16, 100, 48, 48))
        self.assertEqual(len(notes), 1)

    def test_ancestor_transforms_count_too(self) -> None:
        # Nome's edit-redo: a mirrored outer group around the masked one.
        new, _ = tool.fix(_svg(_MASK + '<g transform="matrix(-1,0,0,1,124,-100)"><g transform="translate(60)" mask="url(#m)"/></g>'))
        self.assertEqual(self.region(new), (16, 100, 48, 48))

    def test_rotation_yields_the_bounding_box_of_the_canvas(self) -> None:
        new, _ = tool.fix(_svg(_MASK + '<g mask="url(#m)" transform="translate(200,0) rotate(45)"/>'))
        self.assertEqual(self.region(new)[2:], (67.88, 67.88))

    def test_a_shared_mask_covers_every_user(self) -> None:
        new, _ = tool.fix(_svg(_MASK + '<g mask="url(#m)" transform="translate(-16,-100)"/><g style="mask:url(#m)" transform="translate(-116,-100)"/>'))
        self.assertEqual(self.region(new), (16, 100, 148, 48))

    def test_view_box_defines_the_canvas(self) -> None:
        new, _ = tool.fix(_svg(_MASK + '<g mask="url(#m)" transform="translate(-16,-100)"/>', root='width="96" height="96" viewBox="0 0 48 48"'))
        self.assertEqual(self.region(new), (16, 100, 48, 48))

    def test_masks_that_are_fine_are_left_alone(self) -> None:
        for body in [
            _MASK + '<g mask="url(#m)"/>',                                                        # default region covers the canvas
            _MASK.replace('id="m"', 'id="m" x="0" y="0" width="9" height="9"') + '<g mask="url(#m)" transform="translate(-16,-100)"/>',   # explicit
            _MASK.replace(' maskUnits="userSpaceOnUse"', "") + '<g mask="url(#m)" transform="translate(-16,-100)"/>',                      # objectBoundingBox
            _MASK + '<g transform="translate(-16,-100)"/>',                                       # never used
        ]:
            src = _svg(body)
            self.assertEqual(tool.fix(src), (src, []), body)

    def test_repair_is_idempotent(self) -> None:
        once, _ = tool.fix(_svg(_MASK + '<clipPath id="c"><g><rect width="1" height="1"/></g></clipPath><g mask="url(#m)" transform="translate(-16,-100)"/>'))
        self.assertEqual(tool.fix(once), (once, []))


class TestCommandLine(unittest.TestCase):

    def test_check_reports_without_writing_and_fix_writes(self) -> None:
        broken = _svg(_MASK + '<g mask="url(#m)" transform="translate(-16,-100)"/>')
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            file = Path(tmp) / "icon.svg"
            file.write_text(broken)
            self.assertEqual(tool.main(["--check", tmp]), 1)
            self.assertEqual(file.read_text(), broken)
            self.assertEqual(tool.main([tmp]), 0)
            self.assertNotEqual(file.read_text(), broken)
            self.assertEqual(tool.main(["--check", tmp]), 0)


if __name__ == "__main__":
    unittest.main()
