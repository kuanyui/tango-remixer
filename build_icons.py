# -*- coding: utf-8 -*-
import os
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from pprint import pprint
from typing import List, Optional

@dataclass
class _IconFileInfo_Base():
    themeType: str
    iconCategory: str
    iconSize: str
    iconFileName: str
    """totem.svg"""

    srcFileAbsPath: str
    """To find the aliases"""

@dataclass
class IconSrcFileInfo(_IconFileInfo_Base):
    isASymlinkToAbsPath: Optional[str]

@dataclass
class IconDistFileInfo(_IconFileInfo_Base):
    distFileAbsPath: str
    aliases: List[str]

SCRIPT_DIR: str = os.path.dirname(__file__)
SRC_REPO_ROOT: Path = Path(os.path.join(SCRIPT_DIR, "humanity_0.4.6"))
SRC_SVG_FILES: List[Path] = list(SRC_REPO_ROOT.rglob("*.svg"))
SRC_SVG_FILEPATH_PATTERN: re.Pattern[str] = re.compile(r"/([A-Za-z_-]+)/([a-z]+)/([0-9]+)/(.+\.svg)$")

DIST_ROOT: Path = Path(os.path.join(SCRIPT_DIR, "dist"))
DIST_SVG_ROOT: Path = Path(os.path.join(DIST_ROOT, "svg"))

def get_src_file_info_arr() -> List[IconSrcFileInfo]:
    final_arr: List[IconSrcFileInfo] = []
    for svg_file in SRC_SVG_FILES:
        svg_path: str = str(svg_file)
        m: re.Match[str] | None = SRC_SVG_FILEPATH_PATTERN.search(svg_path)
        if not m: continue
        symlink_target_abs_path: str | None = None
        if os.path.islink(svg_path):
            symlink_target: str = os.readlink(svg_path)
            symlink_target_abs_path = os.path.abspath(os.path.join(os.path.dirname(svg_path), symlink_target))
        final_arr.append(IconSrcFileInfo(
            themeType = m.group(1),
            iconCategory = m.group(2),
            iconSize = m.group(3),
            iconFileName = m.group(4),
            srcFileAbsPath = svg_path,
            isASymlinkToAbsPath = symlink_target_abs_path
        ))
    return final_arr

def gen_dist_files(src_file_arr: List[IconSrcFileInfo]) -> List[IconDistFileInfo]:
    final_arr: List[IconDistFileInfo] = []
    for src_file in src_file_arr:
        if src_file.isASymlinkToAbsPath:
            existed_dist_file: IconDistFileInfo | None = None
            for dist_file in final_arr:
                if dist_file.distFileAbsPath == src_file.isASymlinkToAbsPath:
                    existed_dist_file = dist_file
                    existed_dist_file.aliases.append(src_file.iconFileName)
                    existed_dist_file.srcFileAbsPath = src_file.srcFileAbsPath
                    break
        else:
            dist_file_path: str = os.path.join(DIST_SVG_ROOT, src_file.iconSize, src_file.iconFileName)
            final_arr.append(IconDistFileInfo(
                themeType = src_file.themeType,
                iconCategory = src_file.iconCategory,
                iconSize = src_file.iconSize,
                iconFileName = src_file.iconFileName,
                srcFileAbsPath = src_file.srcFileAbsPath,
                distFileAbsPath = dist_file_path,
                aliases = [src_file.iconFileName]
            ))
    return final_arr

def main():
    src_file_arr = get_src_file_info_arr()
    dist_file_arr = gen_dist_files(src_file_arr)
    for x in dist_file_arr:
        pprint(asdict(x), indent=2)

if __name__ == "__main__":
    main()
