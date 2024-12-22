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

IconThemeSrcFolderName = Literal["Humanity", "Humanity-Dark"]
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


def is_icon_theme_src_folder_name(x: str) -> TypeGuard[IconThemeSrcFolderName]:
    return x in get_args(IconThemeSrcFolderName)

def is_icon_size_type(x: str) -> TypeGuard[IconSizeType]:
    return x in get_args(IconSizeType)

def is_icon_context_dir_type(x: str) -> TypeGuard[IconContextType]:
    return x in get_args(IconContextType)

def is_icon_scale_type(x: str) -> TypeGuard[IconScaleType]:
    return x in get_args(IconScaleType)

ColorizationType = Literal["humanity", "tango"]
"""Colorization type of the icon theme pack. `humanity` is vanilla Humanity icon theme, `tango` will try to colorize the orange to blue."""

def is_colorization_type(x: str) -> TypeGuard[ColorizationType]:
    return x in get_args(ColorizationType)

@dataclass
class IconSrcFileInfo():
    """Basic information of an SVG source file in the unmodified icon theme.
    You can use these information to generate a XDG-compatible icon path."""
    theme_src_folder_name: IconThemeSrcFolderName
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
    """
According for XDG standard:
- This search root should directly (instead of recursively) contain the XDG icon theme pack folders (e.g. `Humanity`, `Humanity-Dark`).
- Each icon theme pack folder should contain `index.theme`
    """
    optimizer_scan_path: Path | None
    output_dist_path: Path
    sizes: List[IconSizeType]
    contexts: List[IconContextType]
    generate_scales: List[IconScaleType]
    colorizations: List[ColorizationType]
    qrc_qresource_prefix: str
    """To specify the extra prefix for the QRC resource path (`RCC > qresource[prefix="..."]`).

    e.g. if set to `/xdg_icon_themes/`, the icon `Humanity/apps/48/totem.svg` will be accessible in C++ as `:/xdg_icon_themes/Humanity/apps/48/totem.svg`"""
    SCRIPT_DIR: Path = Path(os.path.dirname(__file__))


    def __post_init__(self):
        """Validate types"""
        # if not self.themes_scan_path.exists():
        #     raise ValueError(f"Themes scan path does not exist: {self.themes_scan_path}")

        self.output_dist_path.mkdir(parents=True, exist_ok=True)

        for size in self.sizes:
            if not is_icon_size_type(size):
                raise ValueError(f"Invalid size: {size}")

        for context in self.contexts:
            if not is_icon_context_dir_type(context):
                raise ValueError(f"Invalid context: {context}")

        for scale in self.generate_scales:
            if not is_icon_scale_type(scale):
                raise ValueError(f"Invalid scale factor: {scale}. Must be one of {get_args(IconScaleType)}")

        for colorization in self.colorizations:
            if not is_colorization_type(colorization):
                raise ValueError(f"Invalid colorization: {colorization}. Must be one of {get_args(ColorizationType)}")

    @classmethod
    def from_args(cls) -> 'IconThemeOptions':
        parser = argparse.ArgumentParser(
            description='Icon theme configuration and processing tool',
            formatter_class=MyHelpFormatter
        )
        parser.add_argument(
            '--optimizer-scan-path', '-O',
            type=Path,
            required=False,
            help='''The root path of your Qt project (which contains C++ / QML files).

            If specified, this will try to scan all .cpp, .h, .hpp, .c, .qml files and generate minimalized .qrc files. '''
        )
        parser.add_argument(
            '--themes-scan-path', '-i',
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
            '--output-dist-path', '-o',
            type=Path,
            required=False,
            default=IconThemeOptions.SCRIPT_DIR / "dist",
            help='Output directory for generated files'
        )
        parser.add_argument(
            '--colorize', '-c',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=['humanity', 'tango'],
            help='Comma-separated list of colorization types (Available: "humanity", "tango")'
        )

        parser.add_argument(
            '--sizes', '-S',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=list(get_args(IconSizeType)),
            help=f'Comma-separated list of icon sizes (Available: "{", ".join(get_args(IconSizeType))}")'
        )

        parser.add_argument(
            '--contexts', '-C',
            type=lambda x: [c.strip() for c in x.split(',')],
            required=False,
            default=list(get_args(IconContextType)),
            help=f'Comma-separated list of icon contexts. (Available: "{", ".join(get_args(IconContextType))}").'
        )

        parser.add_argument(
            '--generate-scales', '-s',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=['1', '2'],
            help=f'Comma-separated list of scaling factors. (Available: "{", ".join(get_args(IconScaleType))}).'
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
            optimizer_scan_path=args.optimizer_scan_path,
            themes_scan_path=args.themes_scan_path,
            output_dist_path=args.output_dist_path,
            sizes=args.sizes,
            contexts=args.contexts,
            generate_scales=args.generate_scales,
            colorizations=args.colorize,
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
            theme_src_folder_name = _theme_src_folder_name if is_icon_theme_src_folder_name(_theme_src_folder_name) else "Humanity",
            context = _context if is_icon_context_dir_type(_context) else "apps",
            size = _size if is_icon_size_type(_size) else "scalable",
            file_name = m.group(4),
            src_file_path = src_svg_file_path,
            src_file_path_is_symlink = src_svg_file_path.is_symlink(),
            src_file_path_resolved = src_svg_file_path.resolve()
        ))
    final_arr.sort(key=lambda x: (x.size))
    return final_arr

def clear_dist():
    shutil.rmtree(OPTIONS.output_dist_path, ignore_errors=True)



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

def get_tango_theme_folder_name(src_theme_folder_name: IconThemeSrcFolderName) -> str:
    match src_theme_folder_name:
        case "Humanity":
            return "Tango"
        case "Humanity-Dark":
            return "Tango-Dark"

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

def scan_used_icon_in_project(all_icon_names: Set[str]) -> Set[str]:
    """Scan Qt project, and returns a minimal set of referenced icon names. For generate an optimized and minimal qrc file."""
    used_icons: Set[str] = set()
    all_icon_patterns: Dict[str, re.Pattern[str]] = {}
    if OPTIONS.optimizer_scan_path is None:
        return all_icon_names
    for icon_name in all_icon_names:
        candidates: List[str] = []
        candidates.append(icon_name)
        candidates.append(re.sub(r'-', '_', icon_name))
        candidates.append(re.sub(r'-', '', icon_name))
        patt_str: str = '|'.join(candidates)
        # all_icon_patterns[icon_name] = re.compile(rf'\b{icon_name}\b', re.IGNORECASE)
        all_icon_patterns[icon_name] = re.compile(patt_str, re.IGNORECASE)

    for file_path in OPTIONS.optimizer_scan_path.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            file_content = file_path.read_text(encoding='utf-8')

            if 'QFileIconProvider' in file_content:
                for icon_name in all_icon_names:
                    if ('-x-' in icon_name) or (icon_name.startswith('application-')) or ('folder' in icon_name) :
                        used_icons.add(icon_name)

            for icon_name in all_icon_patterns:
                if icon_name in used_icons:
                    continue
                if all_icon_patterns[icon_name].search(file_content):
                    used_icons.add(icon_name)
        except (UnicodeDecodeError, PermissionError):
            continue
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    return used_icons

def main():
    ensure_thirdparty_files(OPTIONS.SCRIPT_DIR / "thirdparty")
    icon_theme_folders = get_icon_theme_folder_list(OPTIONS.themes_scan_path)
    dist_root = OPTIONS.output_dist_path
    clear_dist()
    for src_icon_theme_folder in icon_theme_folders:
        src_icon_theme_name = src_icon_theme_folder.name
        if not is_icon_theme_src_folder_name(src_icon_theme_name):
            print(f'Folder "{src_icon_theme_name}" is not explicitly supported. Skip.')
            continue
        tango_theme_foler_name = get_tango_theme_folder_name(src_icon_theme_name)
        qrc = QrcRoot()
        qrc.resources.append(
            QrcQresource(
                    prefix=f"{OPTIONS.qrc_qresource_prefix}{src_icon_theme_folder.name}",
                    files=[QrcQresourceFile(alias="index.theme", file="index.theme")]
            )
        )
        ini_sections: List[IniSection] = []
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
        for icon in icon_list:
            ALL_ICON_NAMES.add(icon.src_file_path.stem)
        icons_used_in_project = scan_used_icon_in_project(ALL_ICON_NAMES)
        # iterate over all icon files in this theme folder
        for icon in icon_list:
            dist_icon_theme_folder = dist_root.joinpath(icon.theme_src_folder_name)
            qrc_resource_file_path: Path  # string in <file>...</file> tag.
            if icon.src_file_path.is_symlink():
                canonical_icon = search_symlinked_canonical_icon(icon, icon_list)
                dist_icon_file_path = dist_root / canonical_icon.theme_src_folder_name / canonical_icon.context / canonical_icon.size / canonical_icon.file_name
                qrc_resource_file_path = dist_icon_file_path.resolve().relative_to(dist_icon_theme_folder)
            else:
                dist_icon_file_path = dist_root / icon.theme_src_folder_name / icon.context / icon.size / icon.file_name
                copy_svg_file(icon.src_file_path, dist_icon_file_path, "none")
                qrc_resource_file_path = dist_icon_file_path.relative_to(dist_icon_theme_folder)
                if "tango" in OPTIONS.colorizations:
                    dist_icon_file_path = dist_root / tango_theme_foler_name / icon.context / icon.size / icon.file_name
                    copy_svg_file(icon.src_file_path, dist_icon_file_path, "tango_colorizer")

            for scale_int in OPTIONS.generate_scales:
                scale_suffix = ""
                if scale_int != "1":
                    scale_suffix = f"@{scale_int}x"
                if icon.src_file_path.stem in icons_used_in_project:
                    scaled_qresource_file_list_dict[scale_int].append(QrcQresourceFile(
                        alias=f"{icon.context}/{icon.size}{scale_suffix}/{icon.file_name}",
                        file=str(qrc_resource_file_path)
                    ))
            add_ini_section(ini_sections, icon.context, icon.size)
            # print(asdict(qrc.resources[0].files[-1]))
        write_qrc_file(qrc, dist_root / src_icon_theme_folder.name / "index.qrc")
        write_index_theme_file(src_icon_theme_name, "Humanity from Ubuntu", ini_sections,
                               dist_root / src_icon_theme_folder.name / "index.theme")
        if "tango" in OPTIONS.colorizations:
            for resource in qrc.resources:
                resource.prefix = f"{OPTIONS.qrc_qresource_prefix}{tango_theme_foler_name}"
            write_qrc_file(qrc, dist_root / tango_theme_foler_name / "index.qrc")
            write_index_theme_file(tango_theme_foler_name, "Tango flavour icon (forked from Ubuntu Humanity)", ini_sections,
                                dist_root / tango_theme_foler_name / "index.theme")



if __name__ == "__main__":
    # profiler = cProfile.Profile()
    # profiler.enable()
    main()
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats('cumulative')
    # stats.print_stats()
