#!/usr/bin/env python3
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
# from lxml import etree
# from lxml.etree import _Element, _ElementTree
from xml.etree import ElementTree as ET
from pprint import pprint
from types import SimpleNamespace
from enum import StrEnum
from typing import List, Literal, TypeGuard, get_args, Dict, Final, Set
# import cProfile
# import pstats
import argparse
from lib_color_converter import *
from lib_download_extract_tarballs import ensure_thirdparty_files

IconThemeFolderName = Literal["Humanity", "Humanity-Dark", "Tango", "Tango-Dark", "GNOME3"]
"""Source folder name of the icon theme pack. """
IconSizeType = Literal["16", "22", "24", "32", "48", "64", "scalable"]
"""The real geometry size defined in this SVG. `16`, `22`, `24`, `32`, `48`, `64`, `scalable` (unused currently)"""
IconContextType = Literal["actions", "animations", "apps", "categories",
                             "devices", "emblems", "emotes", "intl",
                             "mimetypes", "places", "status"]
"""https://specifications.freedesktop.org/icon-naming-spec/latest/#context"""
IniContextNameType = Literal["Actions", "Animations", "Applications", "Categories",
                             "Devices", "Emblems", "Emotes", "International",
                             "MimeTypes", "Places", "Status"]
"""https://specifications.freedesktop.org/icon-naming-spec/latest/#context"""

CONTEXT_MAPPING: Final[dict[IconContextType, IniContextNameType]] = {
    "actions": "Actions",
    "animations": "Animations",
    "apps": "Applications",
    "categories": "Categories",
    "devices": "Devices",
    "emblems": "Emblems",
    "emotes": "Emotes",
    "intl": "International",
    "mimetypes": "MimeTypes",
    "places": "Places",
    "status": "Status"
}
"""
Standard context list:
https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html
https://specifications.freedesktop.org/icon-naming-spec/latest/#context
"""

def folder_context_to_ini_context (context: IconContextType) -> IniContextNameType:
    return CONTEXT_MAPPING[context]

IconScaleType = Literal["1", "2", "3", "4"]

def is_icon_theme_src_folder_name(x: str) -> TypeGuard[IconThemeFolderName]:
    return x in get_args(IconThemeFolderName)

def is_icon_size_type(x: str) -> TypeGuard[IconSizeType]:
    return x in get_args(IconSizeType)

def is_icon_context_dir_type(x: str) -> TypeGuard[IconContextType]:
    return x in get_args(IconContextType)

def is_icon_scale_type(x: str) -> TypeGuard[IconScaleType]:
    return x in get_args(IconScaleType)

@dataclass
class IconSrcFileInfo():
    """Basic information of an SVG source file in the unmodified icon theme.
    You can use these information to generate a XDG-compatible icon path."""
    theme_src_folder_name: str
    context: IconContextType
    size: IconSizeType
    file_name: str
    """ex: `totem.svg`. (this file may be a symlink, and symlink will not be resolved here """
    src_file_path: Path
    """The absolute path to the source file (Be careful: this may be a symlink, and symlink will not be resolved here)"""
    src_file_path_is_symlink: bool
    src_file_path_resolved: Path


@dataclass
class QrcQresourceFile():
    alias: str
    file: str

@dataclass
class QrcQresource():
    prefix: str
    files: List[QrcQresourceFile] = field(default_factory=list)

@dataclass
class QrcRoot():
    '''
Example:
```xml
<!DOCTYPE RCC>
<RCC version="1.0">
  <qresource prefix="/xdg_icon_themes/Humanity">
    <file>index.theme</file>
  </qresource>
  <qresource prefix="/xdg_icon_themes/Humanity">
    <file alias="apps/16/gtk-info.svg">actions/16/gtk-info.svg</file>
  </qresource>
  <qresource prefix="/xdg_icon_themes/Humanity">
    <file alias="apps/16@2x/gtk-info.svg">actions/16/gtk-info.svg</file>
  </qresource>
</RCC>
```
    '''
    resources: List[QrcQresource] = field(default_factory=list)

class QrcCreator():
    '''To generate an `index.qrc` (virtual file system in Qt application) for a theme.'''
    def __init__(self, theme_name: str):
        self.root: QrcRoot = QrcRoot()
        self.scaled_qresource_dict: Dict[IconScaleType, QrcQresource] = {}
        """A dictionary to store the list of QrcQresourceFile for each scale factor.
        This cause the outputted .qrc XML file to be more readable. (Each scale factor has its own <qresource> tag.)"""
        # Add the first <qresource> tag for the only index.theme file.
        resource_for_index_theme = QrcQresource(
            prefix=f"{OPTIONS.qrc_qresource_prefix}{theme_name}",
            files=[QrcQresourceFile(alias="index.theme", file="index.theme")]
        )
        self.root.resources.append(resource_for_index_theme)
        # Add <qresource> tags for each scale factor.
        for scale in OPTIONS.generate_scales:
            resource = QrcQresource( prefix=f"{OPTIONS.qrc_qresource_prefix}{theme_name}", files=[])
            self.root.resources.append(resource)
            self.scaled_qresource_dict[scale] = resource


    def add_file(self, context: IconContextType, size: IconSizeType, scale: IconScaleType, icon_filename: str) -> None:
        rel_file_path = f'{context}/{size}{get_scaled_size_folder_suffix(scale)}/{icon_filename}'
        file = QrcQresourceFile(file=rel_file_path, alias="")
        self.scaled_qresource_dict[scale].files.append(file)


    def write_qrc_file(self, output_file_path: Path):
        xml_root = ET.Element("RCC")
        xml_root.set("version", "1.0")
        for resource in self.root.resources:
            qresource = ET.SubElement(xml_root, "qresource", { 'prefix': resource.prefix })
            for file in resource.files:
                if file.alias == file.file:
                    ET.SubElement(qresource, "file").text = file.file
                else:
                    ET.SubElement(qresource, "file", { 'alias': file.alias }).text = file.file

        tree = ET.ElementTree(xml_root)
        ET.indent(tree, space="  ", level=0)
        xml_string = ET.tostring(xml_root, encoding="UTF-8").decode("utf-8")
        xml_string_with_header = f'<!DOCTYPE RCC>\n{xml_string}'
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write(xml_string_with_header)
            print(f"File created: {output_file_path}")
        except Exception as e:
            print(f"Error when creating {output_file_path}: {e}")

@dataclass
class IniSection():
    directory: str
    """ex: `apps/16`, `app/16@2x`
    Used as ini section, and in `[Icon Theme] -> Directories=...`"""
    context: IconContextType
    ori_size: IconSizeType
    """Original size. If original size is 16, scale is 2, then `Size=` in index.theme should be `16 * 2 = 32` """
    scale: IconScaleType

class IndexThemeCreator():
    '''To generate an `index.theme` file (XDG icon theme configuration file to describe available scales, sizes and contexts with their directories' paths)'''
    def __init__(self, theme_name: str, comment: str):
        self.theme_name = theme_name
        self.comment = comment
        self.ini_sections: List[IniSection] = []

    def add_index_theme_ini_section(self, context: IconContextType, size: IconSizeType) -> None:
        for exist_section in self.ini_sections:
            if exist_section.context == context and exist_section.ori_size == size:
                return
        for scale in OPTIONS.generate_scales:
            directory: str = f'{context}/{size}{get_scaled_size_folder_suffix(scale)}'
            self.ini_sections.append(IniSection(
                directory=directory,
                context=context,
                scale=scale,
                ori_size=size
            ))
    def write_index_theme_file(self, output_index_theme_file_path: Path):
        fmtted_directories: str = ",".join([x.directory for x in self.ini_sections])
        file_content = f"""\
[Icon Theme]
Name={self.theme_name}
Comment={self.comment}
Inherits=gnome,hicolor

Example=directory-x-normal

# Directory list
Directories={fmtted_directories}

    """
        for entry in self.ini_sections:
            lines: List[str] = [f'[{entry.directory}]']
            if entry.scale != '1':
                lines.append(f'Scale={entry.scale}')
            lines.append(f'Size={int(entry.ori_size) * int(entry.scale)}')
            lines.append(f'Context={folder_context_to_ini_context(entry.context)}')
            lines.append(f'Type=Fixed')
            file_content += "\n".join(lines)
            file_content += "\n\n"
        try:
            with open(output_index_theme_file_path, "w", encoding="utf-8") as f:
                f.write(file_content)
            print(f"File created: {output_index_theme_file_path}")
        except Exception as e:
            print(f"Error when creating {output_index_theme_file_path}: {e}")


ICON_THEME_PATH_PATTERN: re.Pattern[str] = re.compile(r"/([A-Za-z_-]+)/([a-z]+)/([0-9@x]+)/(.+\.svg)$")

@dataclass
class RawIconTheme():
    copied_src_theme_folder: Path
    copied_dst_theme_name: str
    """This will be the name of the copied theme folder in BUILD_FOLDERS.FOLDER_00_ORIGINAL_THEMES"""

ALL_RAW_ICON_THEMES_PATH: List[RawIconTheme] = [
    RawIconTheme(copied_src_theme_folder=Path(__file__).parent / "thirdparty" / "humanity_0.4.6" / "Humanity", copied_dst_theme_name="Humanity"),
    RawIconTheme(copied_src_theme_folder=Path(__file__).parent / "thirdparty" / "humanity_0.4.6" / "Humanity-Dark", copied_dst_theme_name="Humanity-Dark"),
    RawIconTheme(copied_src_theme_folder=Path(__file__).parent.parent / "gnome-icon-theme-cropped" / "src", copied_dst_theme_name="GNOME3"),
]
'''Paths of XDG icon theme packs.

According for XDG standard:
- Directly contains contexts folders (e.g. apps, actions, ... etc).
- (optional) Each icon theme pack folder should contain `index.theme`
'''

class BUILD_FOLDERS:
    FOLDER_ROOT: Final[Path] = Path(__file__).parent / "dist"
    FOLDER_00_ORIGINAL_THEMES_ROOT = FOLDER_ROOT / "00_ORIGINAL_THEMES"
    '''00. Copy all icon themes folders here.
    Contains "Humanity", "Humanity-Dark", "GNOME3" '''

    FOLDER_01_NO_SYMLINK_THEMES_ROOT = FOLDER_ROOT / "01_NO_SYMLINK_THEMES"
    '''01. Delete all symlinks in this folder for simplifying and portability (Non-UNIX systems have no symlink support).
    Contains "Humanity", "Humanity-Dark", "GNOME3" '''

    FOLDER_02_COLORIZED_THEMES_ROOT = FOLDER_ROOT / "02_COLORIZED_THEMES"
    '''02. Convert colors in SVG files. Currently it only converts the Humanity theme (orange) to Tango theme (blue).
    Contains "Humanity", "Humanity-Dark", "Tango", "Tango-Dark", "GNOME3" '''

    FOLDER_03_FINAL_SVG_THEME = FOLDER_ROOT / "03_FINAL_SVG_THEME"
    '''03. Copy included icons (See option `--included-icon-file`) to this folder, generate index.theme and index.qrc.'''

    FOLDER_04_FINAL_PNG_THEME = FOLDER_ROOT / "04_FINAL_PNG_THEME"
    '''04. Convert SVG files to this folder, generate index.theme and index.qrc'''


class MyHelpFormatter(argparse.RawTextHelpFormatter, argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    """Copied from https://qiita.com/yuji38kwmt/items/c7c4d487e3188afd781e """
    def _format_action(self, action: argparse.Action) -> str:
        return super()._format_action(action) + "\n"
@dataclass
class IconThemeOptions:
    included_icon_file: Path
    output_theme_name: str
    sizes: List[IconSizeType]
    generate_scales: List[IconScaleType]
    qrc_qresource_prefix: str
    """To specify the extra prefix for the QRC resource path (`RCC > qresource[prefix="..."]`).

    e.g. if set to `/xdg_icon_themes/`, the icon `Humanity/apps/48/totem.svg` will be accessible in C++ as `:/xdg_icon_themes/Humanity/apps/48/totem.svg`"""

    def __post_init__(self):
        """Validate types"""
        # if not self.themes_scan_path.exists():
        #     raise ValueError(f"Themes scan path does not exist: {self.themes_scan_path}")

        for size in self.sizes:
            if not is_icon_size_type(size):
                raise ValueError(f"Invalid size: {size}")

        for scale in self.generate_scales:
            if not is_icon_scale_type(scale):
                raise ValueError(f"Invalid scale factor: {scale}. Must be one of {get_args(IconScaleType)}")


    @classmethod
    def from_args(cls) -> 'IconThemeOptions':
        parser = argparse.ArgumentParser(
            description='Icon theme configuration and processing tool',
            formatter_class=MyHelpFormatter
        )
        parser.add_argument(
            '--included-icon-file', '-i',
            type=Path,
            required=True,
            help='''
This file should be a plain text file, and the format of each line should be:

SRC_THEME_NAME\tSRC_CONTEXT/SRC_ICON_NAME\tDST_CONTEXT/DST_ICON_NAME

- CONTEXT is optional.
- ICON_NAME should not contain the extension.
'''
        )

        parser.add_argument(
            '--output-theme-name', '-o',
            type=Path,
            required=True,
            default="Output Theme",
            help='Output theme name, which will become the name of outputted folder. This folder will become a XDG icon theme folder (contains in root of this folder: context dirs, index.theme, index.qrc).'
        )
        parser.add_argument(
            '--sizes', '-S',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=list(get_args(IconSizeType)),
            help=f'Comma-separated list of icon sizes (Available: { ", ".join(get_args(IconSizeType)) })'
        )

        parser.add_argument(
            '--generate-scales', '-s',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=['1', '2'],
            help=f'Comma-separated list of scaling factors. (Available: { ", ".join(get_args(IconScaleType)) }).'
        )

        parser.add_argument(
            '--qrc-qresource-prefix', '-q',
            type=str,
            required=False,
            default="/xdg_icon_themes/",
            help= """To specify the extra prefix for the QRC resource path (`RCC > qresource[prefix="..."]`).

e.g. if set to `/xdg_icon_themes/` (default value), the icon `Humanity/apps/48/totem.svg` will be accessible in C++ as `:/xdg_icon_themes/Humanity/apps/48/totem.svg`"""
        )

        args = parser.parse_args()

        return cls(
            included_icon_file=args.included_icon_file,
            output_theme_name=args.output_theme_name,
            sizes=args.sizes,
            generate_scales=args.generate_scales,
            qrc_qresource_prefix=args.qrc_qresource_prefix
        )

OPTIONS = IconThemeOptions.from_args()
pprint(asdict(OPTIONS), indent=2)


def get_icon_theme_folder_list(icon_theme_search_root: Path) -> List[Path]:
    final_arr: List[Path] = []
    for folder in Path(icon_theme_search_root).iterdir():
        if not folder.is_dir(): continue
        if (folder.joinpath('index.theme')).exists():
            final_arr.append(folder)
    return final_arr

def recursive_get_icon_list_in_theme(icon_theme_folder: Path) -> List[IconSrcFileInfo]:
    final_arr: List[IconSrcFileInfo] = []
    for src_svg_file_path in icon_theme_folder.rglob("*.svg"):
        m: re.Match[str] | None = ICON_THEME_PATH_PATTERN.search(str(src_svg_file_path))
        if not m: continue
        _theme_src_folder_name = m.group(1)
        _context = m.group(2)
        _size = m.group(3)
        final_arr.append(IconSrcFileInfo(
            theme_src_folder_name = _theme_src_folder_name,
            context = _context if is_icon_context_dir_type(_context) else "apps",
            size = _size if is_icon_size_type(_size) else "scalable",
            file_name = m.group(4),
            src_file_path = src_svg_file_path,
            src_file_path_is_symlink = src_svg_file_path.is_symlink(),
            src_file_path_resolved = src_svg_file_path.resolve()
        ))
    final_arr.sort(key=lambda x: (x.size))
    return final_arr



def copy_svg_file(src: str | Path, dst: str | Path, preprocessor: Literal["none", "tango_colorizer"]) -> None:
    src_path: Path = Path(src)
    if src_path.is_symlink():
        return None
    dst_path: Path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if preprocessor == 'none':
        shutil.copy2(src, dst)
        return
    if preprocessor == 'tango_colorizer':
        with open(src, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        with open(dst, 'w', encoding='utf-8') as f:
            f.write(tango_colorize_svg_content(raw_content, dst_path.stem))
        return

def search_symlinked_canonical_icon(symlink_icon: IconSrcFileInfo, all_icons: List[IconSrcFileInfo]) -> IconSrcFileInfo:
    for canonical_icon in all_icons:
        if canonical_icon.src_file_path_is_symlink:
            continue
        if canonical_icon.src_file_path == symlink_icon.src_file_path_resolved:
            return canonical_icon
    raise FileNotFoundError(f"Cannot find symlink target for {symlink_icon.src_file_path}")



def scan_used_icon_in_file(all_available_icon_patterns: Dict[str, re.Pattern[str]], file_path: Path) -> Set[str]:
    used_icons: Set[str] = set()
    try:
        file_content = file_path.read_text(encoding='utf-8')

        # if 'QFileIconProvider' in file_content:
        #     for icon_name in all_icon_names:
        #         if ('-x-' in icon_name) or (icon_name.startswith('application-')) or ('folder' in icon_name) :
        #             used_icons.add(icon_name)

        for icon_name in all_available_icon_patterns:
            if all_available_icon_patterns[icon_name].search(file_content):
                used_icons.add(icon_name)
    except (UnicodeDecodeError, PermissionError):
        pass
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        pass
    return used_icons

@dataclass
class IncludedIcon():
    src_theme: str
    src_context: str
    """ This is unused currently."""
    src_filename: str
    dst_context: str
    dst_filename: str

def read_included_icons_as_lines(file_path: Path) -> List[IncludedIcon]:
    fin: List[IncludedIcon] = []
    # patt_theme: re.Pattern[str] = re.compile(r'^[A-Za-z0-9_- ]+$')
    patt_src_icon: re.Pattern[str] = re.compile(r'^(?:([a-z]+?)/)?(.+?)(?:\.svg)?$')
    patt_dst_icon: re.Pattern[str] = re.compile(r'^(?:([a-z]+?)/)?(.+?)(?:\.svg)?$')
    patt_separator: re.Pattern[str] = re.compile(r'(\s+|  +)')
    for line in file_path.read_text(encoding='utf-8').splitlines():
        src_theme: str = ""
        src_icon: str = ""
        dst_icon: str = ""
        if line.startswith('#'): continue
        segs: List[str] = re.split(patt_separator, line)
        if len(segs) == 0: continue
        if len(segs) == 1:
            raise RuntimeError(f"Invalid line: {line}")
            exit(1)
        if len(segs) == 2:
            src_theme = segs[0].strip()
            src_icon = segs[1].strip()
            dst_icon = segs[1].strip()
        if len(segs) == 3:
            src_theme = segs[0].strip()
            src_icon = segs[1].strip()
            dst_icon = segs[2].strip()
        if is_icon_theme_src_folder_name(src_theme):
            raise RuntimeError(f"[ERROR] Invalid theme: {src_theme}")
        src_m = patt_src_icon.match(src_icon)
        dst_m = patt_dst_icon.match(dst_icon)
        if not src_m or not dst_m:
            raise RuntimeError(f"[ERROR] Invalid line: {line}")
        fin.append(IncludedIcon(
            src_theme=src_theme,
            src_context=src_m.group(1) or "",
            src_filename=src_m.group(2) or "",
            dst_context=dst_m.group(1) or "",
            dst_filename=dst_m.group(2) or "",
        ))
    return fin


class IconSearcher():
    def __init__(self, themes_folder: Path):
        self.all_icon_theme_folders: List[Path] = get_icon_theme_folder_list(themes_folder)
        self.all_found_icons: List[IconSrcFileInfo] = []
        for src_icon_theme_folder in self.all_icon_theme_folders:
            self.all_found_icons.extend(recursive_get_icon_list_in_theme(src_icon_theme_folder))
    def search_src_icon_by_icon_name(self, theme_name: str, icon_name: str) -> IconSrcFileInfo:
        for icon in self.all_found_icons:
            if icon.theme_src_folder_name == theme_name and icon.src_file_path.stem == icon_name:
                return icon
        raise FileNotFoundError(f'Icon "{icon_name}" not found in {theme_name}')

def run_00_copy_icon_themes():
    print("00_ORIGINAL_THEMES")
    shutil.rmtree(BUILD_FOLDERS.FOLDER_ROOT, ignore_errors=True)
    BUILD_FOLDERS.FOLDER_ROOT.mkdir(parents=True, exist_ok=True)
    for raw_theme in ALL_RAW_ICON_THEMES_PATH:
        # Keep relative symlinks, but I don't sure what happens under Windows.
        shutil.copytree(raw_theme.copied_src_theme_folder, BUILD_FOLDERS.FOLDER_00_ORIGINAL_THEMES_ROOT / raw_theme.copied_dst_theme_name, symlinks=True)

def run_01_no_symlink_themes():
    print("01_NO_SYMLINK_THEMES")
    BUILD_FOLDERS.FOLDER_01_NO_SYMLINK_THEMES_ROOT.mkdir(parents=True, exist_ok=True)
    for src_theme_folder in BUILD_FOLDERS.FOLDER_00_ORIGINAL_THEMES_ROOT.iterdir():
        dst_theme_folder = BUILD_FOLDERS.FOLDER_01_NO_SYMLINK_THEMES_ROOT / src_theme_folder.name
        dst_theme_folder.mkdir(parents=True, exist_ok=True)
        for src_svg_file_path in src_theme_folder.rglob("*.svg"):
            if src_svg_file_path.is_symlink(): continue
            relative_path = src_svg_file_path.relative_to(src_theme_folder)   # apps/16/totem.svg
            dst_svg_file_path = dst_theme_folder / relative_path
            dst_svg_file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_svg_file_path, dst_svg_file_path)

def run_02_colorize_themes():
    print("02_COLORIZED_THEMES")
    BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT.mkdir(parents=True, exist_ok=True)
    for src_theme_folder in BUILD_FOLDERS.FOLDER_01_NO_SYMLINK_THEMES_ROOT.iterdir():
        dst_theme_folder = BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT / src_theme_folder.name
        dst_theme_folder.mkdir(parents=True, exist_ok=True)
        for src_svg_file_path in src_theme_folder.rglob("*.svg"):
            if src_svg_file_path.is_symlink(): continue
            svg_relative_file_path = src_svg_file_path.relative_to(src_theme_folder)  # apps/16/totem.svg
            # copy svg files
            dst_svg_file_path = dst_theme_folder / svg_relative_file_path
            dst_svg_file_path.parent.mkdir(parents=True, exist_ok=True)
            copy_svg_file(src_svg_file_path, dst_svg_file_path, "none")
            if src_theme_folder.name == "Humanity":
                dst_tango_svg_file_path = BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT / "Tango" / svg_relative_file_path
                dst_tango_svg_file_path.parent.mkdir(parents=True, exist_ok=True)
                copy_svg_file(src_svg_file_path, dst_tango_svg_file_path, "tango_colorizer")
            elif src_theme_folder.name == "Humanity-Dark":
                dst_tango_svg_file_path = BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT / "Tango-Dark" / svg_relative_file_path
                dst_tango_svg_file_path.parent.mkdir(parents=True, exist_ok=True)
                copy_svg_file(src_svg_file_path, dst_tango_svg_file_path, "tango_colorizer")

def run_03_copy_included_icons():
    print("03_FINAL_SVG_THEME")
    this_theme_folder = BUILD_FOLDERS.FOLDER_03_FINAL_SVG_THEME / OPTIONS.output_theme_name
    this_theme_folder.mkdir(parents=True, exist_ok=True)
    # Initialize icon searcher for colorized themes folder.
    icon_searcher = IconSearcher(BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT)

    qrc = QrcCreator(OPTIONS.output_theme_name)
    index_theme = IndexThemeCreator(OPTIONS.output_theme_name, "Generated by build_icons.py")

    for line in read_included_icons_as_lines(OPTIONS.included_icon_file):
        src_icon = icon_searcher.search_src_icon_by_icon_name(line.src_theme, line.src_filename)
        if src_icon.src_file_path_is_symlink:
            print(f'[WARNING] "{src_icon.src_file_path}" is a symlink, auto follows link original file.')

        # copy included icon.
        icon_dst_file_path: Path = this_theme_folder / src_icon.context / src_icon.size / src_icon.file_name
        shutil.copy2(src_icon.src_file_path_resolved, icon_dst_file_path)

        # add to qrc
        for scale in OPTIONS.generate_scales:
            qrc.add_file(src_icon.context, src_icon.size, scale, src_icon.file_name)
        # index.theme
        index_theme.add_index_theme_ini_section(src_icon.context, src_icon.size)

    qrc.write_qrc_file(this_theme_folder / "index.qrc")
    index_theme.write_index_theme_file(this_theme_folder / "index.theme")


def get_scaled_size_folder_suffix(scale: IconScaleType) -> str:
    if scale == "1":
        return ""
    else:
        return f"@{scale}x"


def main():
    ensure_thirdparty_files(Path(__file__).parent / "thirdparty")
    run_00_copy_icon_themes()
    run_01_no_symlink_themes()
    run_02_colorize_themes()
    run_03_copy_included_icons()


if __name__ == "__main__":
    # profiler = cProfile.Profile()
    # profiler.enable()
    main()
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats('cumulative')
    # stats.print_stats()
