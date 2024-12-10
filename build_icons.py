# -*- coding: utf-8 -*-
"""
References:

https://specifications.freedesktop.org/icon-theme-spec/latest/
https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html

https://gist.github.com/peteristhegreat/c0ca6e1a57e5d4b9cd0bb1d7b3be1d6a
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from pprint import pprint
from typing import List, Optional, Literal, TypeGuard, get_args

IconThemeBrightnessType = Literal["light", "dark"]
IconSizeType = Literal["16", "22", "24", "32", "48", "64", "scalable"]
IconContextType = Literal["actions", "apps", "categories", "devices", "emblems", "emotes", "mimetypes", "places", "status"]
"""
Standard context list:
https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html"""

def is_icon_size_type(x: str) -> TypeGuard[IconSizeType]:
    return x in get_args(IconSizeType)

def is_icon_context_type(x: str) -> TypeGuard[IconContextType]:
    return x in get_args(IconContextType)

@dataclass
class IconSrcFileInfo():
    theme_brightness_type: IconThemeBrightnessType
    icon_context: IconContextType
    """`actions`, `apps`, `categories`, `devices`, `emblems`, `emotes`, `mimetypes`, `places`, `status`"""
    icon_size: IconSizeType
    """`16`, `22`, `24`, `32`, `48`, `64`, `scalable`"""
    icon_file_name: str
    """`totem.svg`. This will become the qresource > file[alias="totem.svg"]"""
    src_file_abs_path: str
    """To find the aliases"""
    symlink_to_src_canonical_abs_path: Optional[str]
    """If this is a symlink, this will be the absolute path to the target file.

    None if this is not a symlink"""

@dataclass
class IconDistFileInfo:
    """This class is to describe a non-symlink file."""
    theme_brightness_type: IconThemeBrightnessType
    icon_size: IconSizeType
    icon_context: IconContextType
    canonical_name: str
    """This is actually the `iconFileName`, is the file name of a non-symlink file. Will become the `qresource > file[alias="totem.svg"]`"""
    aliases: List[str]
    """A symlink file to this dist file will be seen as an alias"""
    src_canonical_file_abs_path: str
    """The absolute path to the canonical (non-symlink) src file."""
    dest_canonical_file_abs_path: str
    """The absolute path to the canonical (non-symlink) dist file (expected, should be copied from canonical src file). ONLY NON-SYMLINK FILE WILL BE COPIED.
    ```sh
    lrwxrwxrwx 1 ono ono     9 Dec  4  2009 video-player.svg -> totem.svg
    /humanity-0.4.6/src/humanity/48/video-player.svg

    # will be copied to {LIGHT|DARK}/{ICON_SIZE}/{ICON_CANONICAL_FILE_NAME}
    dist/light/48/totem.svg
    ```
    """


SCRIPT_DIR: str = os.path.dirname(__file__)
SRC_REPO_ROOT: Path = Path(os.path.join(SCRIPT_DIR, "src/humanity_0.4.6"))
SRC_SVG_FILES: List[Path] = list(SRC_REPO_ROOT.rglob("*.svg"))
SRC_SVG_FILEPATH_PATTERN: re.Pattern[str] = re.compile(r"/([A-Za-z_-]+)/([a-z]+)/([0-9]+)/(.+\.svg)$")

DIST_ROOT: Path = Path(os.path.join(SCRIPT_DIR, "dist"))


def get_src_file_info_arr() -> List[IconSrcFileInfo]:
    final_arr: List[IconSrcFileInfo] = []
    for src_svg_file in SRC_SVG_FILES:
        src_svg_path: str = str(src_svg_file)
        m: re.Match[str] | None = SRC_SVG_FILEPATH_PATTERN.search(src_svg_path)
        if not m: continue
        symlink_target_canonical_path: str | None = None
        if os.path.islink(src_svg_path):
            symlink_target: str = os.readlink(src_svg_path)
            symlink_target_canonical_path = str(Path(os.path.join(os.path.dirname(src_svg_path), symlink_target)).resolve())
        _size = m.group(3)
        _context = m.group(2)
        final_arr.append(IconSrcFileInfo(
            theme_brightness_type = "dark" if m.group(1) == "Humanity-Dark" else "light",
            icon_context = _context if is_icon_context_type(_context) else "apps",
            icon_size = _size if is_icon_size_type(_size) else "scalable",
            icon_file_name = m.group(4),
            src_file_abs_path = src_svg_path,
            symlink_to_src_canonical_abs_path = symlink_target_canonical_path
        ))
    return final_arr


def find_or_create_canonical_dist_file (canonical_dist_arr: List[IconDistFileInfo], src_file: IconSrcFileInfo) -> IconDistFileInfo:
    if src_file.symlink_to_src_canonical_abs_path == None:    # This is 100% a canonical file (non-symlink file)
        canonical_dist_file = next((c for c in canonical_dist_arr if c.src_canonical_file_abs_path == src_file.src_file_abs_path), None)
        if canonical_dist_file == None:
            canonical_src_file_path = Path(src_file.src_file_abs_path).resolve()
            canonical_dist_file = IconDistFileInfo(
              theme_brightness_type=src_file.theme_brightness_type,
              icon_context=src_file.icon_context,
              icon_size=src_file.icon_size,
              aliases=[],
              canonical_name=src_file.icon_file_name,
              src_canonical_file_abs_path=str(canonical_src_file_path),
              dest_canonical_file_abs_path=os.path.join(DIST_ROOT, src_file.theme_brightness_type, src_file.icon_size, str(canonical_src_file_path.name))
            )
            canonical_dist_arr.append(canonical_dist_file)
        return canonical_dist_file
    else:    # This is a symlink file
        dist_file_ref = next((c for c in canonical_dist_arr if c.src_canonical_file_abs_path == src_file.symlink_to_src_canonical_abs_path), None)
        if dist_file_ref == None:
            canonical_src_file_abs_path_obj = Path(src_file.symlink_to_src_canonical_abs_path).resolve()
            dist_file_ref = IconDistFileInfo(
              theme_brightness_type=src_file.theme_brightness_type,
              icon_context=src_file.icon_context,
              icon_size=src_file.icon_size,
              aliases=[],
              canonical_name=canonical_src_file_abs_path_obj.name,
              src_canonical_file_abs_path=str(canonical_src_file_abs_path_obj),
              dest_canonical_file_abs_path=os.path.join(DIST_ROOT, src_file.theme_brightness_type, src_file.icon_size, canonical_src_file_abs_path_obj.name)
            )
            canonical_dist_arr.append(dist_file_ref)
        dist_file_ref.aliases.append(src_file.icon_file_name)
        return dist_file_ref



def gen_canonical_dist_files(src_file_arr: List[IconSrcFileInfo]) -> List[IconDistFileInfo]:
    canonical_dist_arr: List[IconDistFileInfo] = []
    for src_file in src_file_arr:
        find_or_create_canonical_dist_file(canonical_dist_arr, src_file)
    return canonical_dist_arr

def main():
    src_file_arr = get_src_file_info_arr()
    dist_file_arr = gen_canonical_dist_files(src_file_arr)
    for x in dist_file_arr:
        pprint(asdict(x), indent=2)

if __name__ == "__main__":
    main()
