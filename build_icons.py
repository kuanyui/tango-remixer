# -*- coding: utf-8 -*-
"""
References:

https://specifications.freedesktop.org/icon-theme-spec/latest/
https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html

https://gist.github.com/peteristhegreat/c0ca6e1a57e5d4b9cd0bb1d7b3be1d6a
"""

import os
import re
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict, field
from pprint import pprint
from typing import List, Optional, Literal, TypeGuard, get_args

IconThemeName = Literal["Humanity", "Humanity-Dark"]
IconSizeType = Literal["16", "22", "24", "32", "48", "64", "scalable"]
"""The real geometry size defined in this SVG. `16`, `22`, `24`, `32`, `48`, `64`, `scalable` (unused currently)"""
IconContextType = Literal["actions", "apps", "categories", "devices", "emblems", "emotes", "mimetypes", "places", "status"]
""" `actions`, `apps`, `categories`, `devices`, `emblems`, `emotes`, `mimetypes`, `places`, `status`

Standard context list:
https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html"""

def is_icon_theme_name(x: str) -> TypeGuard[IconThemeName]:
    return x in get_args(IconThemeName)

def is_icon_size_type(x: str) -> TypeGuard[IconSizeType]:
    return x in get_args(IconSizeType)

def is_icon_context_type(x: str) -> TypeGuard[IconContextType]:
    return x in get_args(IconContextType)

@dataclass
class IconSrcFileInfo():
    """Basic information of an SVG source file in the unmodified icon theme.
    You can use these information to generate a XDG-compatible icon path."""
    theme_name: IconThemeName
    context: IconContextType
    size: IconSizeType
    file_name: str
    """ex: `totem.svg`. (this file may be a symlink, and symlink will not be resolved here """
    src_file_path: Path
    """The absolute path to the source file (Be careful this may be a symlink, and symlink will not be resolved here)"""

@dataclass
class QrcFile():
    alias: str
    file: str

@dataclass
class QrcQresource():
    prefix: str
    files: List[QrcFile] = field(default_factory=list)

@dataclass
class QrcRoot():
    resources: List[QrcQresource] = field(default_factory=list)

SCRIPT_DIR: str = os.path.dirname(__file__)

SRC_ICON_THEME_FOLDER_SEARCH_ROOT: str = os.path.join(SCRIPT_DIR, "thirdparty/humanity_0.4.6")
"""
According for XDG standard:
- This search root should directly (instead of recursively) contain the XDG icon theme pack folders (e.g. `Humanity`, `Humanity-Dark`).
- Each icon theme pack folder should contain `index.theme`
"""

ICON_THEME_PATH_PATTERN: re.Pattern[str] = re.compile(r"/([A-Za-z_-]+)/([a-z]+)/([0-9@x]+)/(.+\.svg)$")

QRC_QRESOURCE_PREFIX: str = "/xdg_icon_themes/"
"""The extra prefix for the QRC resource path.

e.g. if set to `/xdg_icon_themes/`, the icon `Humanity/apps/48/totem.svg` will be accessible in C++ as `:/xdg_icon_themes/Humanity/apps/48/totem.svg`"""

DIST_ROOT: str = os.path.join(SCRIPT_DIR, "dist")


def get_icon_theme_folder_list(icon_theme_search_root: str) -> List[Path]:
    final_arr: List[Path] = []
    for folder in Path(icon_theme_search_root).iterdir():
        if not folder.is_dir(): continue
        if (folder.joinpath('index.theme')).exists():
            final_arr.append(folder)
    return final_arr

def get_icon_list_in_theme(icon_theme_folder: Path) -> List[IconSrcFileInfo]:
    final_arr: List[IconSrcFileInfo] = []
    for src_svg_file_path in icon_theme_folder.rglob("*.svg"):
        m: re.Match[str] | None = ICON_THEME_PATH_PATTERN.search(str(src_svg_file_path))
        if not m: continue
        _theme_name = m.group(1)
        _context = m.group(2)
        _size = m.group(3)
        final_arr.append(IconSrcFileInfo(
            theme_name = _theme_name if is_icon_theme_name(_theme_name) else "Humanity",
            context = _context if is_icon_context_type(_context) else "apps",
            size = _size if is_icon_size_type(_size) else "scalable",
            file_name = m.group(4),
            src_file_path = src_svg_file_path,
        ))
    return final_arr

def clear_dist():
    shutil.rmtree(DIST_ROOT, ignore_errors=True)

def easy_copy_file(src: str | Path, dst: str | Path) -> None:
    src_path: Path = Path(src)
    if src_path.is_symlink():
        return None
    dst_path: Path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# def copy_icon_to_dist(icon: IconSrcFileInfo):
#     dist_root = Path(DIST_ROOT).joinpath()
#     dist_file_path = dist_root.joinpath(icon.theme_name, icon.context, icon.size, icon.file_name)
#     easy_copy_file(icon.src_file_path, dist_file_path)

def search_symlinked_canonical_icon(symlink_icon: IconSrcFileInfo, all_icons: List[IconSrcFileInfo]) -> IconSrcFileInfo:
    for canonical_icon in all_icons:
        if canonical_icon.src_file_path.is_symlink():
            continue
        if canonical_icon.src_file_path == symlink_icon.src_file_path.resolve():
            return canonical_icon
    raise FileNotFoundError(f"Cannot find symlink target for {symlink_icon.src_file_path}")

def main():
    icon_theme_folders = get_icon_theme_folder_list(SRC_ICON_THEME_FOLDER_SEARCH_ROOT)
    dist_root = Path(DIST_ROOT).joinpath()
    clear_dist()
    for src_icon_theme_folder in icon_theme_folders:
        qrc = QrcRoot()
        # e.g. /xdg_icon_themes/Humanity
        qrc.resources.append(QrcQresource(prefix=QRC_QRESOURCE_PREFIX + src_icon_theme_folder.name))
        icon_list = get_icon_list_in_theme(src_icon_theme_folder)
        for icon in icon_list:
            dist_icon_theme_folder = dist_root.joinpath(icon.theme_name)
            qrc_resource_file_path: Path  # string in <file>...</file> tag.
            if icon.src_file_path.is_symlink():
                canonical_icon = search_symlinked_canonical_icon(icon, icon_list)
                dist_icon_file_path = dist_root / canonical_icon.theme_name / canonical_icon.context / canonical_icon.size / canonical_icon.file_name
                qrc_resource_file_path = dist_icon_file_path.resolve().relative_to(dist_icon_theme_folder)
                # print(dist_icon_file_path)
                # print(dist_icon_file_path.resolve())
                # print()
            else:
                dist_icon_file_path = dist_root / icon.theme_name / icon.context / icon.size / icon.file_name
                qrc_resource_file_path = dist_icon_file_path.relative_to(dist_icon_theme_folder)

            qrc.resources[0].files.append(QrcFile(
                alias=f"{icon.context}/{icon.size}/{icon.file_name}",
                file=str(qrc_resource_file_path)
            ))
            # qrc.resources[0].files.append(QrcFile(
            #     alias=f"{icon.context}/{icon.size}@2x/{icon.file_name}",
            #     file=str(qrc_resource_file_path)
            # ))
            print(asdict(qrc.resources[0].files[-1]))

        # print(f"Icon Theme: {icon_theme_folder.name}")
        # for icon in icon_list:
        #     pprint(asdict(icon), indent=2)

if __name__ == "__main__":
    main()
