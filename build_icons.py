# -*- coding: utf-8 -*-
import os
import re
from pathlib import Path
import json
from typing import List, Dict

SCRIPT_DIR: str = os.path.dirname(__file__)
SRC_ROOT: Path = Path(os.path.join(SCRIPT_DIR, "humanity_0.4.6"))
SRC_SVG_FILES: List[Path] = list(SRC_ROOT.rglob("*.svg"))
SRC_SVG_FILEPATH_PATTERN: re.Pattern = re.compile(r"/([A-Za-z_-]+)/([a-z]+)/([0-9]+)/(.+\.svg)$")
SRC_SVG_FILE_INFO_ARR: List[Dict[str, str]] = []

def get_src_file_info_arr() -> List[Dict[str, str]]:
    for svg_file in SRC_SVG_FILES:
        svg_path: str = str(svg_file)
        m: re.Match | None = SRC_SVG_FILEPATH_PATTERN.search(svg_path)
        if not m: continue
        symlink_target_abs_path: str | None = None
        if os.path.islink(svg_path):
            symlink_target: str = os.readlink(svg_path)
            symlink_target_abs_path: str = os.path.abspath(os.path.join(os.path.dirname(svg_path), symlink_target))
        SRC_SVG_FILE_INFO_ARR.append({
            "themeType": m.group(1),
            "iconCategory": m.group(2),
            "iconSize": m.group(3),
            "iconFileName": m.group(4),
            "srcFileAbsPath": svg_path,
            "isASymlinkToAbsPath": symlink_target_abs_path
        })
    print(json.dumps(SRC_SVG_FILE_INFO_ARR, indent=2))

def main():
    get_src_file_info_arr()

if __name__ == "__main__":
    main()
