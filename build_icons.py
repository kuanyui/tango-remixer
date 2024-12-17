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
from typing import List, Optional, Literal, TypeGuard, get_args, Dict
import cProfile
import pstats
import argparse

IconThemeName = Literal["Humanity", "Humanity-Dark"]
IconSizeType = Literal["16", "22", "24", "32", "48", "64", "scalable"]
"""The real geometry size defined in this SVG. `16`, `22`, `24`, `32`, `48`, `64`, `scalable` (unused currently)"""
IconContextType = Literal["actions", "apps", "categories", "devices", "emblems", "emotes", "mimetypes", "places", "status"]
"""
Standard context list:
https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html"""
IconScaleType = Literal["1", "2", "3", "4"]

def is_icon_theme_name(x: str) -> TypeGuard[IconThemeName]:
    return x in get_args(IconThemeName)

def is_icon_size_type(x: str) -> TypeGuard[IconSizeType]:
    return x in get_args(IconSizeType)

def is_icon_context_type(x: str) -> TypeGuard[IconContextType]:
    return x in get_args(IconContextType)

def is_icon_scale_type(x: str) -> TypeGuard[IconScaleType]:
    return x in get_args(IconScaleType)

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
    """The absolute path to the source file (Be careful: this may be a symlink, and symlink will not be resolved here)"""
    src_file_path_is_symlink: bool
    src_file_path_resolved: Path


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



@dataclass
class IconThemeOptions:
    themes_scan_path: Path
    output_dist_path: Path
    sizes: List[IconSizeType]
    contexts: List[IconContextType]
    generate_scales: List[IconScaleType]

    def __post_init__(self):
        """Validate types"""
        if not self.themes_scan_path.exists():
            raise ValueError(f"Themes scan path does not exist: {self.themes_scan_path}")

        self.output_dist_path.mkdir(parents=True, exist_ok=True)

        for size in self.sizes:
            if not is_icon_size_type(size):
                raise ValueError(f"Invalid size: {size}")

        for context in self.contexts:
            if not is_icon_context_type(context):
                raise ValueError(f"Invalid context: {context}")

        for scale in self.generate_scales:
            if not is_icon_scale_type(scale):
                raise ValueError(f"Invalid scale factor: {scale}. Must be one of {get_args(IconScaleType)}")

    @classmethod
    def from_args(cls) -> 'IconThemeOptions':
        parser = argparse.ArgumentParser(
            description='Icon theme configuration and processing tool',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        parser.add_argument(
            '--themes-scan-path', '-i',
            type=Path,
            required=False,
            default=Path(SRC_ICON_THEME_FOLDER_SEARCH_ROOT),
            help='Path to scan for XDG icon theme packs'
        )

        parser.add_argument(
            '--output-dist-path', '-o',
            type=Path,
            required=False,
            default=Path(DIST_ROOT),
            help='Output directory for generated files'
        )

        parser.add_argument(
            '--sizes', '-s',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=list(get_args(IconSizeType)),
            help=f'Comma-separated list of icon sizes (Available: "{", ".join(get_args(IconSizeType))}") Default: all'
        )

        parser.add_argument(
            '--contexts', '-c',
            type=lambda x: [c.strip() for c in x.split(',')],
            required=False,
            default=list(get_args(IconContextType)),
            help=f'Comma-separated list of icon contexts. (Available: "{", ".join(get_args(IconContextType))}"). Default: all'
        )

        parser.add_argument(
            '--generate-scales', '-S',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=['1', '2'],
            help=f'Comma-separated list of scaling factors. (Available: "{", ".join(get_args(IconScaleType))}). Default: 1,2'
        )

        args = parser.parse_args()

        return cls(
            themes_scan_path=args.themes_scan_path,
            output_dist_path=args.output_dist_path,
            sizes=args.sizes,
            contexts=args.contexts,
            generate_scales=args.generate_scales
        )

OPTIONS = IconThemeOptions.from_args()
pprint(asdict(OPTIONS), indent=2)

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
            src_file_path_is_symlink = src_svg_file_path.is_symlink(),
            src_file_path_resolved = src_svg_file_path.resolve()
        ))
    final_arr.sort(key=lambda x: (x.size))
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
    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(xml_string_with_header)
        print(f"File created: {output_file_path}")
    except Exception as e:
        print(f"Error when creating {output_file_path}: {e}")


def main():
    icon_theme_folders = get_icon_theme_folder_list(SRC_ICON_THEME_FOLDER_SEARCH_ROOT)
    dist_root = Path(DIST_ROOT).joinpath()
    clear_dist()
    for src_icon_theme_folder in icon_theme_folders:
        qrc = QrcRoot()
        # e.g. /xdg_icon_themes/Humanity
        scaled_qresource_file_list_dict: Dict[IconScaleType, List[QrcFile]] = {}
        for icon_scale in OPTIONS.generate_scales:
            scaled_qresource = QrcQresource(
                prefix=f"{QRC_QRESOURCE_PREFIX}{src_icon_theme_folder.name}",
                files=[]
            )
            scaled_qresource_file_list_dict[icon_scale] = scaled_qresource.files
            qrc.resources.append(scaled_qresource)
        icon_list = get_icon_list_in_theme(src_icon_theme_folder)
        for icon in icon_list:
            dist_icon_theme_folder = dist_root.joinpath(icon.theme_name)
            qrc_resource_file_path: Path  # string in <file>...</file> tag.
            if icon.src_file_path.is_symlink():
                canonical_icon = search_symlinked_canonical_icon(icon, icon_list)
                dist_icon_file_path = dist_root / canonical_icon.theme_name / canonical_icon.context / canonical_icon.size / canonical_icon.file_name
                qrc_resource_file_path = dist_icon_file_path.resolve().relative_to(dist_icon_theme_folder)
            else:
                dist_icon_file_path = dist_root / icon.theme_name / icon.context / icon.size / icon.file_name
                qrc_resource_file_path = dist_icon_file_path.relative_to(dist_icon_theme_folder)
                easy_copy_file(icon.src_file_path, dist_icon_file_path)

            for scale_int in OPTIONS.generate_scales:
                scale_suffix = ""
                if scale_int != "1":
                    scale_suffix = f"@{scale_int}x"
                scaled_qresource_file_list_dict[scale_int].append(QrcFile(
                    alias=f"{icon.context}/{icon.size}{scale_suffix}/{icon.file_name}",
                    file=str(qrc_resource_file_path)
                ))
            # print(asdict(qrc.resources[0].files[-1]))
        write_qrc_file(qrc, dist_root / src_icon_theme_folder.name / "index.qrc")



if __name__ == "__main__":
    # profiler = cProfile.Profile()
    # profiler.enable()
    main()
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats('cumulative')
    # stats.print_stats()
