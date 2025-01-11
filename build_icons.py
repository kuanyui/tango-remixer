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

IconFileFormat = Literal["svg", "png"]

def is_icon_theme_src_folder_name(x: str) -> TypeGuard[IconThemeFolderName]:
    return x in get_args(IconThemeFolderName)

def is_icon_size_type(x: str) -> TypeGuard[IconSizeType]:
    return x in get_args(IconSizeType)

def is_icon_context_dir_type(x: str) -> TypeGuard[IconContextType]:
    return x in get_args(IconContextType)

def is_icon_scale_type(x: str) -> TypeGuard[IconScaleType]:
    return x in get_args(IconScaleType)

def is_icon_file_format(x: str) -> TypeGuard[IconFileFormat]:
    return x in get_args(IconFileFormat)

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
    resources: List[QrcQresource] = field(default_factory=list)

@dataclass
class IniSection():
    directory: str
    """ex: `apps/16`, `app/16@2x`
    Used as ini section, and in `[Icon Theme] -> Directories=...`"""
    context: IconContextType
    ori_size: IconSizeType
    """Original size. If original size is 16, scale is 2, then `Size=` in index.theme should be `16 * 2 = 32` """
    scale: IconScaleType

ICON_THEME_PATH_PATTERN: re.Pattern[str] = re.compile(r"/([A-Za-z_-]+)/([a-z]+)/([0-9@x]+)/(.+\.svg)$")



class MyHelpFormatter(argparse.RawTextHelpFormatter, argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    """Copied from https://qiita.com/yuji38kwmt/items/c7c4d487e3188afd781e """
    def _format_action(self, action: argparse.Action) -> str:
        return super()._format_action(action) + "\n"
@dataclass
class IconThemeOptions:
    themes_scan_path: Path
    included_icon_file: Path
    output_theme_folder_path: Path
    sizes: List[IconSizeType]
    generate_scales: List[IconScaleType]
    output_icon_file_format: IconFileFormat
    qrc_qresource_prefix: str
    """To specify the extra prefix for the QRC resource path (`RCC > qresource[prefix="..."]`).

    e.g. if set to `/xdg_icon_themes/`, the icon `Humanity/apps/48/totem.svg` will be accessible in C++ as `:/xdg_icon_themes/Humanity/apps/48/totem.svg`"""
    SCRIPT_DIR: Path = Path(os.path.dirname(__file__))


    def __post_init__(self):
        """Validate types"""
        # if not self.themes_scan_path.exists():
        #     raise ValueError(f"Themes scan path does not exist: {self.themes_scan_path}")

        self.output_theme_folder_path.mkdir(parents=True, exist_ok=True)

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
            required=False,
            help='''
This file should be a plain text file, and the format of each line should be:

SRC_THEME_NAME\tSRC_CONTEXT/SRC_ICON_NAME\tDST_CONTEXT/DST_ICON_NAME

- CONTEXT is optional.
- ICON_NAME should not contain the extension.
'''
        )
        parser.add_argument(
            '--themes-scan-path', '-t',
            type=Path,
            required=False,
            default=IconThemeOptions.SCRIPT_DIR / "thirdparty" / "humanity_0.4.6",
            help='''Path to scan for XDG icon theme packs.

According for XDG standard:
- This search root should directly (instead of recursively) contain the XDG icon theme pack folders (e.g. `Humanity`, `Humanity-Dark`).
- Each icon theme pack folder should contain `index.theme`
'''
        )

        parser.add_argument(
            '--output-theme-folder-path', '-o',
            type=Path,
            required=False,
            default=IconThemeOptions.SCRIPT_DIR / "dist",
            help='Output path for the generated icon theme pack. This folder will be cleared and become a XDG icon theme (contains in root of this folder: context dirs, index.theme, index.qrc).'
        )

        parser.add_argument(
            '--output-icon-file-format', '-f',
            type=str,
            required=False,
            default="svg",
            help=f'Output icon format, default is "svg". "png" requires Inkscape installed. (Available: {  ", ".join(get_args(IconFileFormat)) })'
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

e.g. if set to `/xdg_icon_themes/`, the icon `Humanity/apps/48/totem.svg` will be accessible in C++ as `:/xdg_icon_themes/Humanity/apps/48/totem.svg`"""
        )

        args = parser.parse_args()

        return cls(
            included_icon_file=args.included_icon_file,
            themes_scan_path=args.themes_scan_path,
            output_theme_folder_path=args.output_theme_folder_path,
            output_icon_file_format=args.output_icon_file_format,
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


# def copy_icon_to_dist(icon: IconSrcFileInfo):
#     dist_root = Path(DIST_ROOT).joinpath()
#     dist_file_path = dist_root.joinpath(icon.theme_name, icon.context, icon.size, icon.file_name)
#     copy_svg_file(icon.src_file_path, dist_file_path)

def search_symlinked_canonical_icon(symlink_icon: IconSrcFileInfo, all_icons: List[IconSrcFileInfo]) -> IconSrcFileInfo:
    for canonical_icon in all_icons:
        if canonical_icon.src_file_path_is_symlink:
            continue
        if canonical_icon.src_file_path == symlink_icon.src_file_path_resolved:
            return canonical_icon
    raise FileNotFoundError(f"Cannot find symlink target for {symlink_icon.src_file_path}")


def write_qrc_file(qrc_root: QrcRoot, output_file_path: Path):
    root = ET.Element("RCC")
    root.set("version", "1.0")
    for resource in qrc_root.resources:
        qresource = ET.SubElement(root, "qresource", { 'prefix': resource.prefix })
        for file in resource.files:
            if file.alias == file.file:
                ET.SubElement(qresource, "file").text = file.file
            else:
                ET.SubElement(qresource, "file", { 'alias': file.alias }).text = file.file

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    xml_string = ET.tostring(root, encoding="UTF-8").decode("utf-8")
    xml_string_with_header = f'<!DOCTYPE RCC>\n{xml_string}'
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(xml_string_with_header)
        print(f"File created: {output_file_path}")
    except Exception as e:
        print(f"Error when creating {output_file_path}: {e}")

def write_index_theme_file(name: str, comment: str, entries: List[IniSection], output_index_theme_file_path: Path):
    fmtted_directories: str = ",".join([x.directory for x in entries])
    file_content = f"""\
[Icon Theme]
Name={name}
Comment={comment}
Inherits=gnome,hicolor

Example=directory-x-normal

# Directory list
Directories={fmtted_directories}

"""
    for entry in entries:
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

def get_tango_theme_folder_name(src_theme_folder_name: IconThemeFolderName) -> str:
    match src_theme_folder_name:
        case "Humanity":
            return "Tango"
        case "Humanity-Dark":
            return "Tango-Dark"
        case _:
            return "Tango"

def add_ini_section(ini_sections: List[IniSection], context: IconContextType, size: IconSizeType) -> None:
    for exist_section in ini_sections:
        if exist_section.context == context and exist_section.ori_size == size:
            return
    for scale in OPTIONS.generate_scales:
        scale_int: int = int(scale)
        directory: str = f'{context}/{size}'
        if scale != '1':
            directory = f'{context}/{size}@{scale_int}x'
        ini_sections.append(IniSection(
            directory=directory,
            context=context,
            scale=scale,
            ori_size=size
        ))


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
        theme: str = ""
        src_icon: str = ""
        dst_icon: str = ""
        if line.startswith('#'): continue
        segs: List[str] = re.split(patt_separator, line)
        if len(segs) == 0: continue
        if len(segs) == 1:
            raise RuntimeError(f"Invalid line: {line}")
            exit(1)
        if len(segs) == 2:
            theme = segs[0].strip()
            src_icon = segs[1].strip()
            dst_icon = segs[1].strip()
        if len(segs) == 3:
            theme = segs[0].strip()
            src_icon = segs[1].strip()
            dst_icon = segs[2].strip()
        if is_icon_theme_src_folder_name(theme):
            raise RuntimeError(f"[ERROR] Invalid theme: {theme}")
        src_m = patt_src_icon.match(src_icon)
        dst_m = patt_dst_icon.match(dst_icon)
        if not src_m or not dst_m:
            raise RuntimeError(f"[ERROR] Invalid line: {line}")
        fin.append(IncludedIcon(
            src_theme=theme,
            src_context=src_m.group(1) or "",
            src_filename=src_m.group(2) or "",
            dst_context=dst_m.group(1) or "",
            dst_filename=dst_m.group(2) or "",
        ))
    return fin


class IconSearcher():
    def __init__(self):
        self.all_icon_theme_folders: List[Path] = get_icon_theme_folder_list(OPTIONS.themes_scan_path)
        self.all_found_icons: List[IconSrcFileInfo] = []
        for src_icon_theme_folder in self.all_icon_theme_folders:
            self.all_found_icons.extend(recursive_get_icon_list_in_theme(src_icon_theme_folder))
    def search_src_icon_by_icon_name(self, theme_name: str, icon_name: str) -> IconSrcFileInfo:
        for icon in self.all_found_icons:
            if icon.theme_src_folder_name == theme_name and icon.src_file_path.stem == icon_name:
                return icon
        raise FileNotFoundError(f'Icon "{icon_name}" not found in {theme_name}')

def main():
    output_icon_theme_folder = OPTIONS.output_theme_folder_path
    output_theme_name = OPTIONS.output_theme_folder_path.name
    shutil.rmtree(OPTIONS.output_theme_folder_path, ignore_errors=True)
    # model of `index.theme` and `index.qrc`
    ini_sections: List[IniSection] = []
    qrc = QrcRoot()
    qrc.resources.append(
        QrcQresource(
                prefix=f"{OPTIONS.qrc_qresource_prefix}{output_theme_name}",
                files=[QrcQresourceFile(alias="index.theme", file="index.theme")]
        )
    )
    icon_searcher = IconSearcher()
    for line in read_included_icons_as_lines(OPTIONS.included_icon_file):
        src_icon = icon_searcher.search_src_icon_by_icon_name(line.src_theme, line.src_filename)
        if src_icon.src_file_path_is_symlink:
            print(f'[WARNING] "{src_icon.src_file_path}" is a symlink, auto follows link original file.')

        icon_dst_path: Path = output_icon_theme_folder / line.theme_src_folder_name / line.context / line.size / line.file_name
        copy_svg_file(src_icon.src_file_path_resolved, , "none")

    for src_icon_theme_folder in all_icon_theme_folders:
        if not is_icon_theme_src_folder_name(src_icon_theme_folder.name):
            print(f'Folder "{src_icon_theme_folder.name}" is not explicitly supported. Skip.')
            continue
        tango_theme_foler_name = get_tango_theme_folder_name(src_icon_theme_folder.name)

        # e.g. /xdg_icon_themes/Humanity
        scaled_qresource_file_list_dict: Dict[IconScaleType, List[QrcQresourceFile]] = {}
        for icon_scale in OPTIONS.generate_scales:
            scaled_qresource = QrcQresource(
                prefix=f"{OPTIONS.qrc_qresource_prefix}{src_icon_theme_folder.name}",
                files=[]
            )
            scaled_qresource_file_list_dict[icon_scale] = scaled_qresource.files
            qrc.resources.append(scaled_qresource)
        icon_list = recursive_get_icon_list_in_theme(src_icon_theme_folder)
        # Optimizer
        ALL_ICON_NAMES: Set[str] = set()
        for line in icon_list:
            ALL_ICON_NAMES.add(line.src_file_path.stem)
        icons_used_in_project = scan_used_icon_in_project(ALL_ICON_NAMES)
        # iterate over all icon files in this theme folder
        for line in icon_list:
            dist_icon_theme_folder = output_icon_theme_folder.joinpath(line.theme_src_folder_name)
            qrc_resource_file_path: Path  # string in <file>...</file> tag.
            if line.src_file_path.is_symlink():
                canonical_icon = search_symlinked_canonical_icon(line, icon_list)
                icon_dst_path = output_icon_theme_folder / canonical_icon.theme_src_folder_name / canonical_icon.context / canonical_icon.size / canonical_icon.file_name
                qrc_resource_file_path = icon_dst_path.resolve().relative_to(dist_icon_theme_folder)
            else:
                icon_dst_path = output_icon_theme_folder / line.theme_src_folder_name / line.context / line.size / line.file_name
                copy_svg_file(line.src_file_path, icon_dst_path, "none")
                qrc_resource_file_path = icon_dst_path.relative_to(dist_icon_theme_folder)

                icon_dst_path = output_icon_theme_folder / tango_theme_foler_name / line.context / line.size / line.file_name
                copy_svg_file(line.src_file_path, icon_dst_path, "tango_colorizer")

            for scale_int in OPTIONS.generate_scales:
                scale_suffix = ""
                if scale_int != "1":
                    scale_suffix = f"@{scale_int}x"
                if line.src_file_path.stem in icons_used_in_project:
                    scaled_qresource_file_list_dict[scale_int].append(QrcQresourceFile(
                        alias=f"{line.context}/{line.size}{scale_suffix}/{line.file_name}",
                        file=str(qrc_resource_file_path)
                    ))
            add_ini_section(ini_sections, line.context, line.size)
            # print(asdict(qrc.resources[0].files[-1]))
        write_qrc_file(qrc, output_icon_theme_folder / src_icon_theme_folder.name / "index.qrc")
        write_index_theme_file(src_icon_theme_folder.name, "Humanity from Ubuntu", ini_sections,
                               output_icon_theme_folder / src_icon_theme_folder.name / "index.theme")



if __name__ == "__main__":
    # profiler = cProfile.Profile()
    # profiler.enable()
    main()
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats('cumulative')
    # stats.print_stats()
