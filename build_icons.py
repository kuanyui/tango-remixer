# -*- coding: utf-8 -*-
import os
import re
from pathlib import Path
import json
from typing import List, TypedDict, Optional

class IconSrcFileInfo(TypedDict):
    themeType: str
    iconCategory: str
    iconSize: str
    iconFileName: str
    srcFileAbsPath: str
    isASymlinkToAbsPath: Optional[str]

SCRIPT_DIR: str = os.path.dirname(__file__)
SRC_ROOT: Path = Path(os.path.join(SCRIPT_DIR, "humanity_0.4.6"))
SRC_SVG_FILES: List[Path] = list(SRC_ROOT.rglob("*.svg"))
SRC_SVG_FILEPATH_PATTERN: re.Pattern[str] = re.compile(r"/([A-Za-z_-]+)/([a-z]+)/([0-9]+)/(.+\.svg)$")

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
        final_arr.append({
            "themeType": m.group(1),
            "iconCategory": m.group(2),
            "iconSize": m.group(3),
            "iconFileName": m.group(4),
            "srcFileAbsPath": svg_path,
            "isASymlinkToAbsPath": symlink_target_abs_path
        })
    return final_arr

def gen_dist_files():
    pass

def main():
    src_file_arr = get_src_file_info_arr()
    print(json.dumps(src_file_arr, indent=2))

if __name__ == "__main__":
    main()
