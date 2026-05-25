import re
from dataclasses import dataclass, field
from typing import Final, List, Literal, Optional, TypeGuard, get_args
from warnings import deprecated


# IconSizeType = Union[IconSizeNumericType, Literal["scalable"]]   # Don't use Union[] it will cause runtime error, while the static type checking passed.
IconSizeType        = Literal["8", "16", "22", "24", "32", "36", "48", "64", "72", "96", "128", "192", "256", "384", "512", "1024", "scalable"]
"""The real geometry size defined in this SVG. Only `16`, `22`, `24`, `32`, `48`, `64`, `scalable` are used by Tango / Nome / Humanity icon themes."""

IconContextType = Literal["actions", "animations", "apps", "categories",
                             "devices", "emblems", "emotes", "intl",
                             "mimetypes", "places", "status"]
"""https://specifications.freedesktop.org/icon-naming-spec/latest/#context"""
IniContextNameType = Literal["Actions", "Animations", "Applications", "Categories",
                             "Devices", "Emblems", "Emotes", "International",
                             "MimeTypes", "Places", "Status"]
"""https://specifications.freedesktop.org/icon-naming-spec/latest/#context"""

ALL_AVAILABLE_INPUT_SIZES: Final[List[IconSizeType]] = [x for x in get_args(IconSizeType)]
ALL_AVAILABLE_OUTPUT_SIZES: Final[List[IconSizeType]] = [x for x in get_args(IconSizeType) if x != 'scalable']  # TODO: If specifying output size as `scalable`, copy it into `scalable/` and never rasterize it.
"""Only these sizes are used in Tango / Nome / Humanity icon themes."""


IconScaleType = Literal["1", "2", "3", "4"]

def is_icon_size_type(x: str) -> TypeGuard[IconSizeType]:
    return x in get_args(IconSizeType)

def is_icon_context_dir_type(x: str) -> TypeGuard[IconContextType]:
    return x in get_args(IconContextType)

def is_icon_scale_type(x: str) -> TypeGuard[IconScaleType]:
    return x in get_args(IconScaleType)


@dataclass
class ParseError():
    """One located parse error. Maps directly to an LSP diagnostic range.
    - `col_*` are 0-based. `col_end` exclusive.
    - `exc_type` is the canonical Python exception class for callers that want to re-raise (LSP ignores it)."""
    line_no: int
    col_start: int
    col_end: int
    message: str
    exc_type: type[Exception] = RuntimeError


@dataclass
class SizeIo():
    input: IconSizeType
    """Notice: This is used to describe the directives of user, doesn't mean that the inputted size is actually existed."""
    output: IconSizeType
    """Usually this should not include `scalable`."""

class SizeIoMatrix():
    """Notice: This is used to describe the directives of user, doesn't mean that the inputted size is actually existed."""
    def __init__(self, size_io_matrix_expr: str, line_no: int):
        """Parse a matrix expression and populate `all_data`.

        Args:
            size_io_matrix_expr:
                - A matrix expression like `16;22>32;-48`.
                - An empty string produces an empty matrix (`is_empty()` is `True`), which means "no size directives specified".
            line_no: Line number in the source file, used for error messages.
        """
        self.all_data: List[SizeIo] = []
        """all definitions of `input -> output`"""
        if size_io_matrix_expr:
            self.parse_full_matrix_expr(size_io_matrix_expr, line_no)

    def add_resize_io(self, input_size: IconSizeType, output_size: Optional[IconSizeType] = None):
        """This supports resize.
        - `{16>16;16>24;16>32}` is acceptable.
        - `{16>16;24>16}` is invalid. (Ambiguity, what on earth the source size do you want for generating 16x16?)
        """
        if output_size == 'scalable':
            raise SyntaxError(f"In size conversion matrix definition, you explicitly define `scalable` as output size, this is unreasonable.")
        if output_size == None:
            output_size = input_size
        for other in self.all_data:
            if other.output == output_size:
                raise SyntaxError(f"Output size {output_size} cannot be redefined.")
        self.all_data.append(SizeIo(input=input_size, output=output_size))

    def add_by_range(self, size_range_begin: IconSizeType, size_range_end: IconSizeType):
        """This doesn't support resize."""
        for x in ALL_AVAILABLE_INPUT_SIZES:
            if x == 'scalable': continue
            if not is_icon_size_type(x): continue
            if int(size_range_begin) <= int(x) and int(x) <= int(size_range_end):
                self.add_resize_io(x, x)

    def parse_full_matrix_expr(self, size_io_matrix_expr: str, line_no: int):
        """
        A full matrix expression can contain multiple segments.
        ```sh
        # for each seg:
        # <single> : 16
        # <range>  : 16-32
        # <resize> : 16>24

        # examples:
        16;22                 # same as `16>16;22>22`
        16>16;22              # same as `16;22` or `16>16;22>22`
        16;24-48              # same as `16;24;32;48` or `16>16;24>24;32>32;48>48`
        16>32;32>64
        16;scalable>48
        16>16;16>24;16>32     # one source size (16) outputs multiple sizes
        -48                   # same as 8-48  (smallest available size up to 48)
        32-                   # same as 32-1024  (32 up to largest available size)

        # Duplicate INPUT sizes are allowed (one source -> many outputs).
        # Duplicate OUTPUT sizes are rejected (ambiguous which input wins).
        ```
        """
        segs: list[str] = size_io_matrix_expr.split(";")
        patt_seg = re.compile(r'''
                              ^
                              (?:
                              (?P<single>[0-9]+|scalable)|                                                       # ex: `16`
                              (?P<range>(?P<range_from>[0-9]+)?\s*-\s*(?P<range_to>[0-9]+)?)|                    # ex: `16-32`, `-48`   # NOTE: `scalable` cannot be used in a range expression
                              (?P<resize>(?P<resize_from>[0-9]+|scalable)\s*>\s*(?P<resize_to>[0-9]+|scalable))  # ex: `16>24`          #  ... Can `scalable` be as output size??
                              )
                              $
                              ''', re.VERBOSE)
        for _seg in segs:
            seg = _seg.strip()  # trim
            m = patt_seg.search(seg)
            if not m: raise SyntaxError(f"Invalid expression for size conversion matrix at line {line_no}: `{seg}`")
            if m.group('single') is not None:
                single = m.group('single')
                if not is_icon_size_type(single): raise SyntaxError(f"Invalid size `{single}` at line {line_no}")
                self.add_resize_io(single, single)
            if m.group('range') is not None:
                range_from = m.group('range_from')
                range_to = m.group('range_to')
                if is_icon_size_type(range_from) and is_icon_size_type(range_to):
                    self.add_by_range(range_from, range_to)
                elif is_icon_size_type(range_from) and range_to is None:
                    self.add_by_range(range_from, ALL_AVAILABLE_OUTPUT_SIZES[-1])
                elif range_from is None and is_icon_size_type(range_to):
                    self.add_by_range(ALL_AVAILABLE_OUTPUT_SIZES[0], range_to)
                else:
                    raise SyntaxError(f"Invalid size range `{m.group('range')}` at line {line_no}")
            if m.group('resize') is not None:
                resize_from = m.group('resize_from')
                resize_to = m.group('resize_to')
                if not is_icon_size_type(resize_from): raise SyntaxError(f"""Invalid size "resize from" definition in `{m.group('resize')}` at line {line_no}. (Expected: `FROM>TO`)""")
                if not is_icon_size_type(resize_to): raise SyntaxError(f"""Invalid size "resize to" definition in `{m.group('resize')}` at line {line_no}. (Expected: `FROM>TO`)""")
                self.add_resize_io(resize_from, resize_to)

    def is_empty(self) -> bool:
        return len(self.all_data) == 0

    def get_all_input_sizes(self) -> set[IconSizeType]:
        """Return values are de-duplicated."""
        fin: set[IconSizeType] = set()
        for io in self.all_data:
            fin.add(io.input)
        return fin

@dataclass
class ParsedIncludedIcon():
    """This data class describes a single parsed line in `included_icons.txt`"""
    src_theme: str
    src_context: str
    """ This is unused currently."""
    src_icon_name: str
    dst_context: str
    dst_icon_name: str
    """ Input & output sizes.
    Empty list means all. """
    size_io_matrix: SizeIoMatrix
    # LSP source positions. Optional. Defaults keep old callers working.
    # `spans` keys: same names as the str fields above (src_theme, ...).
    # `spans` value: (col_start, col_end). 0-based. Missing key = field not on the line.
    line_no: int = -1
    spans: dict[str, tuple[int, int]] = field(default_factory=dict)

@deprecated("Unused currently")
class ParsedIncludedIconsTxtFile():
    data: List[ParsedIncludedIcon]


# =============================================
# Line-level parser (no I/O, no icon-search)
# =============================================
# Single regex used by both `parse_text` (this module) and the build-side
# `read_included_icons_txt` (build_icons.py) so both stay in sync.
#
# Quoted from XDG Spec ( https://specifications.freedesktop.org/icon-naming/latest/#guidelines ):
# "all icon names may only contain lowercase letters, numbers, underscore, dash, or period characters. Spaces, colons, slashes, and backslashes are not allowed"
# NOTE: we allow uppercase in icon name to accept real-world AppStream / Flatpak ids (e.g. `org.inkscape.Inkscape`).
PATT_LINE: re.Pattern[str] = re.compile(r'''
                                        ^
                                        (?P<src_theme_name>[A-Za-z0-9_-]+)
                                        (?:\t+|[ ][ ][ ][ ]+)
                                        (?P<src>(?:(?P<src_context>[a-z]+?)/)?(?P<src_icon_name>[A-Za-z0-9_.-]+?)(?:\.svg)?)
                                        (?:
                                            (?:\t+|[ ][ ][ ][ ]+)
                                            (?P<dst>(?:(?P<dst_context>[a-z]+?)/)?(?P<dst_icon_name>[A-Za-z0-9_.-]+?)(?:\.svg)?)
                                        )?
                                        (?:
                                            (?:\t+|[ ][ ][ ][ ]+)
                                            (?:\{(?P<sizes_io_expr>[ 0-9>;scalable-]+)\})
                                        )?
                                        $
                                        ''', re.VERBOSE)

# Map regex group name -> the public field name used in ParsedIncludedIcon.spans
_GROUP_TO_SPAN_KEY: dict[str, str] = {
    "src_theme_name": "src_theme",
    "src_context":    "src_context",
    "src_icon_name":  "src_icon_name",
    "dst_context":    "dst_context",
    "dst_icon_name":  "dst_icon_name",
    "sizes_io_expr":  "size_io_matrix",
}


def parse_text(text: str, known_themes: Optional[List[str]] = None) -> tuple[List[ParsedIncludedIcon], List[ParseError]]:
    """Pure syntax pass over `included_icons.txt`-format text.

    No icon-file existence checks. No raises.
    All errors collected with line + col ranges.

    `known_themes` validates `src_theme_name` if given. None skips it.

    Returns `(parsed_lines, errors)`.
    Bad line: error only. No parsed entry.
    Bad matrix / unknown theme: error AND parsed entry (LSP can still highlight).
    """
    parsed_lines: List[ParsedIncludedIcon] = []
    errors: List[ParseError] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = re.sub(r'[ \t]#.*$', '', raw)  # strip EOL comment
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = PATT_LINE.search(line)
        if not m:
            errors.append(ParseError(line_no=line_no, col_start=0, col_end=len(line),
                                     message=f"Invalid line format: {line}",
                                     exc_type=RuntimeError))
            continue

        # Theme validation (only if caller passed a list).
        src_theme_name = m.group('src_theme_name')
        if known_themes is not None and src_theme_name not in known_themes:
            errors.append(ParseError(
                line_no=line_no,
                col_start=m.start('src_theme_name'),
                col_end=m.end('src_theme_name'),
                message=f'Unknown theme "{src_theme_name}". Known: {known_themes}',
                exc_type=FileNotFoundError,
            ))

        # Matrix; if SyntaxError, capture but keep going with an empty matrix.
        sizes_io_expr = m.group('sizes_io_expr') or ""
        try:
            size_io_matrix = SizeIoMatrix(sizes_io_expr, line_no)
        except SyntaxError as e:
            size_io_matrix = SizeIoMatrix("", line_no)
            errors.append(ParseError(
                line_no=line_no,
                col_start=m.start('sizes_io_expr') if m.group('sizes_io_expr') else 0,
                col_end=m.end('sizes_io_expr') if m.group('sizes_io_expr') else len(line),
                message=str(e),
                exc_type=SyntaxError,
            ))

        # Spans (only for groups that actually matched).
        spans: dict[str, tuple[int, int]] = {}
        for group_name, span_key in _GROUP_TO_SPAN_KEY.items():
            if m.group(group_name) is not None:
                spans[span_key] = (m.start(group_name), m.end(group_name))

        # Fallbacks (mirror build_icons.py behavior).
        src_icon_name = m.group('src_icon_name')
        dst_icon_name = m.group('dst_icon_name') or src_icon_name
        src_context = m.group('src_context') or ""
        dst_context = m.group('dst_context') or src_context

        parsed_lines.append(ParsedIncludedIcon(
            src_theme=src_theme_name,
            src_context=src_context,
            src_icon_name=src_icon_name,
            dst_context=dst_context,
            dst_icon_name=dst_icon_name,
            size_io_matrix=size_io_matrix,
            line_no=line_no,
            spans=spans,
        ))
    return parsed_lines, errors
