# -*- coding: utf-8 -*-
import os
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from pprint import pprint
from typing import List, Optional, Literal, TypeGuard, get_args

IconThemeType = Literal["light", "dark"]
IconSizeType = Literal["16", "22", "24", "32", "48", "64", "scalable"]

def is_icon_size_type(x: str) -> TypeGuard[IconSizeType]:
    return x in get_args(IconSizeType)

@dataclass
class IconSrcFileInfo():
    themeType: IconThemeType
    iconCategory: str
    """`actions`, `apps`, `categories`, `devices`, `emblems`, `emotes`, `mimetypes`, `places`, `status`"""
    iconSize: IconSizeType
    """`16`, `22`, `24`, `32`, `48`, `64`, `scalable`"""
    iconFileName: str
    """`totem.svg`. This will become the qresource > file[alias="totem.svg"]"""
    srcFileAbsPath: str
    """To find the aliases"""
    symlinkToSrcAbsPath: Optional[str]
    """If this is a symlink, this will be the absolute path to the target file.

    None if this is not a symlink"""

@dataclass
class IconDistFileInfo:
    """This class is to describe a non-symlink file."""
    themeTyype: IconThemeType
    iconSize: IconSizeType
    canonicalName: str
    """This is actually the `iconFileName`, is the file name of a non-symlink file. Will become the `qresource > file[alias="totem.svg"]`"""
    aliases: List[str]
    """A symlink file to this dist file will be seen as an alias"""
    srcFileAbsPath: str
    """The absolute path to the src file. Be careful, this may be a symlink file."""
    distFileAbsPath: str
    """The absolute path to the dist file (expected, should be copied from src file). ONLY NON-SYMLINK FILE WILL BE COPIED."""


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
        symlink_target_abs_path: str | None = None
        if os.path.islink(src_svg_path):
            symlink_target: str = os.readlink(src_svg_path)
            symlink_target_abs_path = os.path.abspath(os.path.join(os.path.dirname(src_svg_path), symlink_target))
        _iconSize = m.group(3)
        final_arr.append(IconSrcFileInfo(
            themeType = "dark" if m.group(1) == "Humanity-Dark" else "light",
            iconCategory = m.group(2),
            iconSize = _iconSize if is_icon_size_type(_iconSize) else "scalable",
            iconFileName = m.group(4),
            srcFileAbsPath = src_svg_path,
            symlinkToSrcAbsPath = symlink_target_abs_path
        ))
    return final_arr

def get_dist_file_path(src_file: IconSrcFileInfo)-> str:
    """
    lrwxrwxrwx 1 ono ono     9 Dec  4  2009 video-player.svg -> totem.svg
    /humanity-0.4.6/src/humanity/48/video-player.svg
    dist/light/48/totem.svg
    """
    return os.path.join(DIST_ROOT, src_file.themeType, src_file.iconSize, src_file.iconFileName)

def gen_canonical_dist_files(src_file_arr: List[IconSrcFileInfo]) -> List[IconDistFileInfo]:
    canonical_dist_arr: List[IconDistFileInfo] = []
    for src_real_file in src_file_arr:
        if src_real_file.symlinkToSrcAbsPath != None:    # Skip symlink files
            continue
        dist_file = IconDistFileInfo(
            themeTyype = src_real_file.themeType,
            iconSize = src_real_file.iconSize,
            canonicalName = src_real_file.iconFileName,
            aliases = [],
            srcFileAbsPath = src_real_file.srcFileAbsPath,
            distFileAbsPath = get_dist_file_path(src_real_file)
        )
        canonical_dist_arr.append(dist_file)
    for x in canonical_dist_arr:
        pprint(asdict(x), indent=2)

    for src_symlink_file in src_file_arr:
        if src_symlink_file.symlinkToSrcAbsPath == None:    # Skip non-symlink files
            continue
        dist_file: IconDistFileInfo | None = next((c for c in canonical_dist_arr if c.srcFileAbsPath == src_symlink_file.symlinkToSrcAbsPath), None)
        if dist_file == None:
            print('=================================')
            pprint(asdict(src_symlink_file), indent=2)
            print('=================================')
            raise Exception(f"Cannot find the dist file for the symlink file: {src_symlink_file}")
        dist_file.aliases.append(src_symlink_file.iconFileName)

    return canonical_dist_arr

def main():
    src_file_arr = get_src_file_info_arr()
    dist_file_arr = gen_canonical_dist_files(src_file_arr)
    for x in dist_file_arr:
        pprint(asdict(x), indent=2)

if __name__ == "__main__":
    main()
