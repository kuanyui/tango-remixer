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
import sys
import asyncio
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict, field
import hashlib
import textwrap
# from lxml import etree
# from lxml.etree import _Element, _ElementTree
from xml.etree import ElementTree as ET
from pprint import pprint
from typing import List, Literal, TypeGuard, get_args, Dict, Final, Coroutine, Callable, Tuple, Optional, cast
# import cProfile
# import pstats
import argparse
import logging
import platform
import enum
from warnings import deprecated
from lib.color_converter import *
from lib.included_icons_parser import *
# from lib.download_extract_tarballs import ensure_tarballs_downloaded_and_extracted

IconThemeFolderName = str
"""Source folder name of the icon theme pack. """

IconSizeNumericType = Literal["8", "16", "22", "24", "32", "36", "48", "64", "72", "96", "128", "192", "256", "384", "512", "1024"]

DEFAULT_INPUT_SIZES: Final[List[IconSizeType]] = ['16', '22', '24', '32', '48', "scalable"]
DEFAULT_OUTPUT_SIZES: Final[List[IconSizeType]] = []
DEFAULT_OUTPUT_SIZES_FROM_SCALABLE: Final[List[IconSizeType]] = ['48']


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

def is_icon_theme_src_folder_name(x: str) -> TypeGuard[IconThemeFolderName]:
    return x in get_all_icon_themes_folders()

def get_all_icon_themes_folders() -> List[IconThemeFolderName]:
    """Get all folder names of the icon theme packs. (Built-in and user-specified extra)"""
    return BUILT_IN_ICON_THEMES + [x.id for x in OPTIONS.extra_icon_themes]

@dataclass
class IconSrcFileInfo():
    """Basic information of an SVG source file in the unmodified icon theme.
    You can use these information to generate a XDG-compatible icon path."""
    theme_src_folder_name: str
    context: IconContextType
    size: IconSizeType
    scale: IconScaleType
    """"Unused currently... This should be hardly be used on SVG source."""   # FIXME: source file of scale != 1 is not supported currently
    icon_name: str
    """Without file extension"""
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
    files: List[QrcQresourceFile] = field(default_factory=list)  # type: ignore

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
    resources: List[QrcQresource] = field(default_factory=list)    # type: ignore

class ThemeDirStructure(enum.Enum):
    CVS = "CVS"
    """
    CVS / SVN convension. Most of source file is like this.

    ex: `places/48`, `places/48@2x` (rarely used) """
    XDG = "XDG"
    """
    XDG standard, `hicolor` compatible structure.

    ex: `48x48@2x/places` """

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
        rel_file_path = f'{get_xdg_size_folder_name(size, scale)}/{context}/{icon_filename}'   # REFACTOR: a function to assemble path? (for svn convension <-> xdg standard)
        file = QrcQresourceFile(file=rel_file_path, alias="")
        self.scaled_qresource_dict[scale].files.append(file)


    def write_qrc_file(self, output_file_path: Path):
        xml_root = ET.Element("RCC")
        xml_root.set("version", "1.0")
        for resource in self.root.resources:
            qresource = ET.SubElement(xml_root, "qresource", { 'prefix': resource.prefix })
            for file in resource.files:
                if file.alias == file.file or file.alias == "":
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
    def __init__(self):
        self.ini_sections: List[IniSection] = []

    def add_index_theme_ini_section(self, context: IconContextType, size: IconSizeType, scale: IconScaleType) -> None:
        for exist_section in self.ini_sections:
            if (exist_section.context == context and
                exist_section.ori_size == size and
                exist_section.scale == scale):
                return

        directory: str = f'{get_xdg_size_folder_name(size, scale)}/{context}'   # REFACTOR: a function to assemble path? (for svn convension <-> xdg standard)
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
Name={OPTIONS.output_theme_name}
Comment={OPTIONS.output_theme_description}
Inherits=gnome,hicolor

Example=directory-x-normal

# Directory list
Directories={fmtted_directories}

"""
        for entry in self.ini_sections:
            lines: List[str] = [f'[{entry.directory}]']
            ori_size = entry.ori_size
            lines.append(f'Size={ori_size}')
            if entry.scale != '1':
                lines.append(f'Scale={entry.scale}')
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



@dataclass
class RawIconTheme():
    copied_src_theme_folder: Path
    copied_dst_theme_name: str
    """This will be the name of the copied theme folder in BUILD_FOLDERS.FOLDER_00_ORIGINAL_THEMES"""
    authors: List[Path]
    licenses: List[Path]
    urls: List[str]

def init_built_in_icon_themes() -> List[RawIconTheme]:
    root: Path = Path(__file__).parent
    # repo_humanity       : Path = root / "tarballs" / "humanity_0.4.6" / "Humanity"
    # repo_humanity_dark  : Path = root / "tarballs" / "humanity_0.4.6" / "Humanity-Dark"
    repo_tango          : Path = root / "submodules" / "tango-icon-theme"
    repo_nome           : Path = root / "submodules" / "nome-icon-theme"
    repo_humanity       : Path = root / "submodules" / "humanity-icon-theme" / "Humanity"
    repo_humanity_dark  : Path = root / "submodules" / "humanity-icon-theme" / "Humanity-Dark"
    repo_gimp_default   : Path = root / "submodules" / "floss-icon-collections" / "GimpDefault"
    repo_gimp_legacy    : Path = root / "submodules" / "floss-icon-collections" / "GimpLegacy"
    repo_inkscape_tango : Path = root / "submodules" / "floss-icon-collections" / "InkscapeTango"
    return [
        RawIconTheme(
            copied_dst_theme_name="Tango",
            copied_src_theme_folder=repo_tango,
            authors=[ repo_tango / "AUTHORS" ],
            licenses=[ repo_tango / "COPYING", ],
            urls=[ "https://github.com/kuanyui/tango-icon-theme-fork" ],
        ),
        RawIconTheme(
            copied_dst_theme_name="Nome",
            copied_src_theme_folder=repo_nome / "src",
            authors=[ repo_nome / "AUTHORS" ],
            licenses=[
                repo_nome / "COPYING",
                repo_nome / "COPYING_CCBYSA3",
                repo_nome / "COPYING_LGPL",
            ],
            urls=[ "https://github.com/kuanyui/nome-icon-theme" ],
        ),
        RawIconTheme(
            copied_dst_theme_name="Humanity",
            copied_src_theme_folder=repo_humanity,
            authors=[ repo_humanity / "AUTHORS" ],
            licenses=[ repo_humanity / "COPYING" ],
            urls=[ "https://launchpad.net/humanity/+download" ],
        ),
        RawIconTheme(
            copied_dst_theme_name="Humanity-Dark",   # Maybe HumanityDark would be better....?
            copied_src_theme_folder=repo_humanity_dark,
            authors=[ repo_humanity_dark / "AUTHORS" ],
            licenses=[ repo_humanity_dark / "COPYING" ],
            urls=[ "https://launchpad.net/humanity/+download" ],
        ),
        RawIconTheme(
            copied_dst_theme_name="GimpDefault",
            copied_src_theme_folder=repo_gimp_default,
            authors=[],
            licenses=[ repo_gimp_default / "COPYING" ],
            urls=[ "https://gitlab.gnome.org/GNOME/gimp-data/-/tree/main/icons?ref_type=heads" ],
        ),
        RawIconTheme(
            copied_dst_theme_name="GimpLegacy",
            copied_src_theme_folder=repo_gimp_legacy,
            authors=[],
            licenses=[ repo_gimp_legacy / "COPYING" ],
            urls=[ "https://gitlab.gnome.org/GNOME/gimp-data/-/tree/main/icons?ref_type=heads" ],
        ),
        RawIconTheme(
            copied_dst_theme_name="InkscapeTango",
            copied_src_theme_folder=repo_inkscape_tango,
            # Inkscape had no independent COPYING & AUTHORS file for its icon theme, so these two are from root repo of Inkscape.
            authors=[ repo_inkscape_tango / "AUTHORS" ],
            licenses=[ repo_inkscape_tango / "COPYING" ],
            urls=[ "https://gitlab.com/inkscape/inkscape/-/tree/master/share/icons?ref_type=heads" ],
        )
    ]

BUILT_IN_RAW_ICON_THEMES_PATH: List[RawIconTheme] = init_built_in_icon_themes()
'''Paths of XDG icon theme packs.

According for XDG standard:
- Directly contains contexts folders (e.g. apps, actions, ... etc).
- (optional) Each icon theme pack folder should contain `index.theme`
'''



class BUILD_FOLDERS:
    FOLDER_ROOT: Final[Path] = Path(__file__).parent / "dist"
    FOLDER_00_ORIGINAL_THEMES_ROOT = FOLDER_ROOT / "00_ORIGINAL_THEMES"
    '''`00` Copy all icon themes folders here.
    Contains "Tango", "Nome", "Humanity", "Humanity-Dark"
    (Plus "GimpDefault", "GimpLegacy", "InkscapeTango")

    Folder structures can be:
    - `<context>/<size>` (convension since CVS/SVN era)
    - `<size>x<size>@<scale>` (XDG standard style)
    '''

    FOLDER_01_NO_SYMLINK_THEMES_ROOT = FOLDER_ROOT / "01_NO_SYMLINK_THEMES"
    '''`01` Delete all symlinks in this folder for simplifying and portability (Non-UNIX systems have no symlink support).
    Contains "Tango", "Nome", "Humanity", "Humanity-Dark"
    (Plus "GimpDefault", "GimpLegacy", "InkscapeTango")

    - Folder structures (of each theme) can be:
        - `<context>/<size>` (convension since CVS/SVN era)
        - `<size>x<size>@<scale>` (XDG standard style)
    '''

    FOLDER_02_COLORIZED_THEMES_ROOT = FOLDER_ROOT / "02_COLORIZED_THEMES"
    '''`02` Convert colors in SVG files to produce Blue-* hue-shifted variants.
    Currently produces:
      - `Nome`           ->  `BlueNome`           (via `nome_colorizer`)
      - `Humanity`       ->  `BlueHumanity`       (via `humanity_colorizer`)
      - `Humanity-Dark`  ->  `BlueHumanity-Dark`  (via `humanity_colorizer`)
    Tango / GimpDefault / GimpLegacy / InkscapeTango are passed through as-is
    (no Blue variant). The original input themes are always also copied through.

    Contains "Tango", "Nome", "BlueNome", "Humanity", "Humanity-Dark", "BlueHumanity", "BlueHumanity-Dark",
    (Plus "GimpDefault", "GimpLegacy", "InkscapeTango")

    - Folder structures (of each theme) can be:
        - `<context>/<size>` (convension since CVS/SVN era)
        - `<size>x<size>@<scale>` (XDG standard style)'''

    FOLDER_03_INCLUDED_SVG_ICONS = FOLDER_ROOT / "03_INCLUDED_SVG_ICONS"
    '''`03` Parse `included_icons.txt` to pick necessary SVG source files.

    1. Aggregate and copy the included icons from multiple themes' folders, according to the specified **"icon name + icon size matrix"** (See option `--included-icon-file`).
    2. Merge into the single `<output_theme_name>/` folder.


    - **Folder structure (of the merged theme): will be formalized** to `<context>/<size>` (convension since CVS/SVN era)

    - Size matrix: **only the specified input**-sizes of the icons will be picked.
                 - **The size is kept with the source icon. No duplicated icons**
                   **For example: `{16>16;16>24;16>32}` will copy only `16` SVG to output's `16/`**

    This is **NOT yet** a XDG-compatible icon theme folder.
    '''


    FOLDER_04_XDG_SVG_THEME = FOLDER_ROOT / "04_XDG_SVG_THEME"
    '''`04` Convert the (CVS/SVN convension) folder structure into XDG folder structure, then generate index.theme and index.qrc.

    - Folder structure: XDG standard's `hicolor` format `<size>x<size>/<context>` (note: `hicolor` use `<size>x<size>` instead of `<size>`), but `<scale>` is ignore (because this is SVG)

    - Size matrix: icons will be **arbitrarily copied** from source folders to destination folders, according to the specified input-sizes and output-sizes.
                 - **Duplicated input size of the same icon is possible. (ex: `{16>16;16>24;16>32}` will copy `16/` SVG to the `16x16/`, `24x24/`, `32x32/` three output folders)**

    This is already a XDG-compatible icon theme folder.
    '''

    FOLDER_05_XDG_PNG_THEME = FOLDER_ROOT / "05_XDG_PNG_THEME"
    '''`05` Convert SVG files to this folder, generate index.theme and index.qrc

    - Folder structure: XDG standard's `hicolor` format `<size>x<size>/<context>` (scale == 1) or `<size>x<size>@<scale>/<context>` (scale >= 2)

    - Size matrix: icons will be **rasterized** from source folders to destination folders, according to the specified input-sizes and output-sizes.
                 - **Duplicated input size of the same icon is possible. (ex: `{16>16;16>24;16>32}` will rasterize `16` SVG to PNG into the `16x16/`, `24x24/`, `32x32/` three folders)**

    This is already a XDG-compatible icon theme folder.
    '''


@dataclass
class ExtraIconTheme():
    """
    TODO: theme.index is ignored currently, so the scales defined in the theme pack are not supported. Because I think this should be rare...
    """
    id: str
    """Unique ID of the icon theme, this `id` can be used in included_icons.txt
    (NOTE: the following are occupied by built-in themes: `BlueHumanity`, `BlueHumanity-Dark`, `Humanity`, `Humanity-Dark`, `Nome`)
    """
    icon_theme_root_folder_path: Path
    """The root folder of the icon theme. (Contains context folders (required) and `index.theme` (optional, unused currently))"""

class MyHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    """Forked from https://qiita.com/yuji38kwmt/items/c7c4d487e3188afd781e
    - Auto wrap (`argparse.ArgumentDefaultsHelpFormatter`)
    - Keep arbitrarily added newlines
    """

    def _split_lines(self, text: str, width: int) -> List[str]:
        lines: List[str] = []
        for line in text.splitlines():
            if not line.strip():
                # Preserve manual blank lines
                lines.append("")
            else:
                lines.extend(textwrap.wrap(line, width))
        return lines

    def _format_action(self, action: argparse.Action) -> str:
        return super()._format_action(action) + "\n"

@dataclass
class IconThemeOptions:
    """The all options of the whole build process. Specified via CLI arguments."""
    clean_before_build: bool
    included_icon_file: Path
    output_stamp_file: Path
    rebuild_regardless_of_stamp_file: bool
    output_png_theme_to_dir: Path | None
    output_svg_theme_to_dir: Path | None
    output_theme_name: str
    output_theme_description: str
    input_svg_sizes: List[IconSizeType]
    output_png_sizes: List[IconSizeType]
    output_png_sizes_from_scalable: List[IconSizeType]
    generate_scales: List[IconScaleType]
    qrc_qresource_prefix: str
    verbose: bool
    debug: bool
    """To specify the extra prefix for the QRC resource path (`RCC > qresource[prefix="..."]`).

    e.g. if set to `/xdg_icon_themes/`, the icon `Humanity/apps/48/totem.svg` will be accessible in C++ as `:/xdg_icon_themes/Humanity/apps/48/totem.svg`"""
    extra_icon_themes: List[ExtraIconTheme]

    def __post_init__(self):
        """Validate types"""
        # if not self.themes_scan_path.exists():
        #     raise ValueError(f"Themes scan path does not exist: {self.themes_scan_path}")

        for size in self.input_svg_sizes:
            if not is_icon_size_type(size):
                raise ValueError(f"Invalid size in --input-svg-sizes: {size}")

        for size in self.output_png_sizes:
            if not is_icon_size_type(size):
                raise ValueError(f"Invalid size in --output-png-sizes: {size}")

        for scale in self.generate_scales:
            if not is_icon_scale_type(scale):
                raise ValueError(f"Invalid scale factor: {scale}. Must be one of {get_args(IconScaleType)}")

        # Merge in `# @extra-icon-theme NAME PATH` directives from the file.
        # CLI-supplied entries (same NAME) win. Paths are resolved relative to
        # the included-icon-file's parent dir. Hard-errors on missing path
        # (build-side strictness; LSP only warns).
        # Skip if the file isn't there yet (some tests pass a placeholder path
        # and only write the file later, or never read it at all).
        if not self.included_icon_file.exists():
            return
        text = self.included_icon_file.read_text(encoding='utf-8')
        _lines, _errors, directives = parse_text(text, built_in_themes=BUILT_IN_ICON_THEMES)
        base_dir = self.included_icon_file.resolve().parent
        cli_names = {t.id for t in self.extra_icon_themes}
        for d in directives:
            if d.name in cli_names:
                continue  # CLI override
            resolved = (base_dir / d.path_raw).resolve()
            if not resolved.exists():
                raise FileNotFoundError(
                    f"[ERROR] {self.included_icon_file}:{d.line_no}: "
                    f'@extra-icon-theme path does not exist: {resolved}')
            self.extra_icon_themes.append(ExtraIconTheme(id=d.name, icon_theme_root_folder_path=resolved))

    @staticmethod
    def parse_extra_icon_theme(value: str) -> ExtraIconTheme:
        parts = value.split(":")
        # On Windows, path may contain multiple colons... (e.g. `TangoIcon:D:/a/myapp/resources/Tango`)
        if len(parts) <= 1:
            raise ValueError("Invalid format. Must be `id:icon_theme_root_folder_path`")
        id = parts[0]
        icon_theme_dir_path_str: str = ":".join(parts[1:])
        icon_theme_dir_path = Path(icon_theme_dir_path_str).resolve()
        # resolve() will convert relative path to absolute, according to current PWD instead of __file__.

        if id in BUILT_IN_ICON_THEMES:
            raise ValueError(f"Invalid ID: {id}. This ID is reserved for built-in icon themes ({', '.join(BUILT_IN_ICON_THEMES)}) .")
        return ExtraIconTheme(
            id=id,
            icon_theme_root_folder_path=icon_theme_dir_path
        )

    @classmethod
    def from_args(cls) -> 'IconThemeOptions':
        parser = argparse.ArgumentParser(
            description='Icon theme configuration and processing tool',
            formatter_class=MyHelpFormatter
        )
        parser.add_argument(
            '--clean-before-build', '-c',
            action='store_true',
            help='Clean build folder before building. Basically means force rebuild.'
        )
        parser.add_argument(
            '--included-icon-file', '-i',
            type=Path,
            required=True,
            help='''
This file should be a plain text file, and the format of each line can be any of the following:

```
SRC_THEME_NAME\t[SRC_CONTEXT/]SRC_ICON_NAME
SRC_THEME_NAME\t[SRC_CONTEXT/]SRC_ICON_NAME\t[DST_CONTEXT/]DST_ICON_NAME
SRC_THEME_NAME\t[SRC_CONTEXT/]SRC_ICON_NAME\t{16;22;24}
SRC_THEME_NAME\t[SRC_CONTEXT/]SRC_ICON_NAME\t{16-24}
SRC_THEME_NAME\t[SRC_CONTEXT/]SRC_ICON_NAME\t{scalable>24}
SRC_THEME_NAME\t[SRC_CONTEXT/]SRC_ICON_NAME\t{16-32;48>128}
```

- Separate fields by tab, or >=4 spaces.
- SRC_CONTEXT is can be omitted. Actually, this is usually unneeded. Because in a valid XDG icon theme, all icon names are expected to be unique across all context.
- DST_CONTEXT is optional. Default is same with the context of the source icon.
- ICON_NAME should not contain the extension. All extensions will be ignored.

- Specify wanted input & output size via `{...}` in the end of line:
  - Not specified means pick all sizes (default).
  - `{16;22;24}` means picking `16`, `22`, `24` only.
  - `{16-24}` means picking sizes of `16` ~ `24`, that is to say, `16`, `22`, `24`.
  - `{scalable>24}` means picking `scalable` of this icon and copy into `24/` SVG folder, and force rasterize it into `24x24` PNG.
  - `{16-32;48>128}` means picking `16`, `22`, `24`, `32` and convert them into corresponding sizes of PNG files. Then pick `48` and convert it into `128x128`.
  - `scalable` is only valid as a resize input (`scalable>N`). `{scalable}`, `{N>scalable}`, and ranges with `scalable` are rejected.
---

In-file directive: `# @extra-icon-theme THEME_NAME THEME_PATH`

Declare extra XDG icon themes from inside this file (recommended over `--extra-icon-theme`; the LSP server also reads these).

```
# @extra-icon-theme MyIcon         ../appicons
# @extra-icon-theme AnotherIcon    /opt/themes/another
Tango       document-save
MyIcon      my-custom-thing
```

Rules:
- Paths are forward-slash only (`/`) on all OS. Backslashes are rejected.
- Relative paths resolve based on `included_icons.txt`'s directory (NOT CWD).
- `THEME_NAME` must match `[A-Za-z0-9_-]+`. Built-in theme names are reserved. Duplicates are rejected.
- `THEME_PATH` may contain inner whitespace (not recommended); trailing whitespace is trimmed.
- If the same `THEME_NAME` appears in both `--extra-icon-theme` and `# @extra-icon-theme`, the CLI flag's PATH fully replaces the directive's. The directive's path is ignored entirely (not merged or searched as a fallback).
- Build fails hard if a directive's path doesn't exist. The LSP only warns.

---

When this file is older than `--stamp-file`, the build will not be triggered.
'''
        )
        parser.add_argument(
            '--output-stamp-file', '--stamp-file', '-t',
            type=Path,
            required=False,
            default=BUILD_FOLDERS.FOLDER_ROOT / 'built.stamp',
            help='''
Briefly, this is a stamp-file to track the modification of `--included-icon-file`. If no modification detected, skip the build immediately.

This is an output stamp-file. When build finished successfully:
- The stamp-file will be created and touched.
- The SHA256 hash of the content of `included_icons.txt` will be saved into stamp file.

The rebuild logic:

- If SHA256 recorded in stamp file is same with SHA256 of the included_icons.txt, always skip rebuild.
- If stamp file doesn't exist, rebuild.
- If mtime of `--included-icon-file` is newer than stamp file, rebuild.
'''        )
        parser.add_argument(
            '--rebuild-regardless-of-stamp-file', '-r',
            action='store_true',
            help='''Ignore the hash recorded in `--stamp-file`, ignore `--included-icon-file`, merely relys on the mtime of each source SVG & output SVG file to determine whether to rebuild the SVG file.

This is useful when you need to build SVG files after modifying SVG files, but without modifying `--included-icon-file`.

OPTIMIZE: Note that checking the mtime of each SVG files is still somewhat slow, donno why, need to be optimized.'''
        )
        parser.add_argument(
            '--output-svg-theme-to-dir', '-S',
            type=Path,
            required=False,
            help="""After build finished, additionally copy the built XDG-compatible SVG icon theme pack folder (`dist/03_FINAL_SVG_THEME/{THEME_NAME}/`) as another speficied folder path.

Be careful, don't use the same folder as `--output-png-theme-to-dir` or its result may be against your expectation."""
        )

        parser.add_argument(
            '--output-png-theme-to-dir', '-P',
            type=Path,
            required=False,
            help="""After build finished, additionally copy the built XDG-compatible PNG icon theme pack folder (`dist/04_FINAL_PNG_THEME/{THEME_NAME}/`) as another speficied folder path.

Be careful, don't use the same folder as `--output-svg-theme-to-dir` or its result may be against your expectation."""
        )

        parser.add_argument(
            '--output-theme-name', '-on',
            type=str,
            required=False,
            default="OutputTheme",
            help='Output theme name, which will become the name of outputted folder. This folder will become a XDG icon theme folder (contains in root of this folder: context dirs, index.theme, index.qrc).'
        )

        parser.add_argument(
            '--output-theme-description', '-od',
            type=str,
            required=False,
            default="This index.theme is generated via tango-icons-remixer",
            help='Output theme description, which will be written in the `Comment=` field of the index.theme file.'
        )
        parser.add_argument(
            '--input-svg-sizes', '-iz',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=DEFAULT_INPUT_SIZES,
            help=f'''Comma-separated list of icon sizes, to decide what numeric sizes (numeric size folder, ex: `/16/`) should be picked as SVG source files.
(Available: { ", ".join(ALL_AVAILABLE_INPUT_SIZES) })'''
        )
        parser.add_argument(
            '--output-png-sizes', '-oz',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=DEFAULT_OUTPUT_SIZES,
            help=f'''Comma-separated list of icon sizes, to decide what sizes should be converted to PNGs from inputted numeric sizes (numeric size folder, ex: `/16/`). Only when the corresponding input sizes are existed, this option will be triggered (that is to say, output is `16,48`, but input only contains `16`, then `48` will not be converted to PNG.). Empty means all.
(Available: { ", ".join(ALL_AVAILABLE_OUTPUT_SIZES) })'''
        )
        parser.add_argument(
            '--output-png-sizes-from-scalable', '-oZ',
            type=lambda x: [s.strip() for s in x.split(',')],
            required=False,
            default=DEFAULT_OUTPUT_SIZES_FROM_SCALABLE,
            help=f'Comma-separated list of icon sizes to, to decide what sizes should be output from inputted `scalable/` folder (Available: { ", ".join(ALL_AVAILABLE_OUTPUT_SIZES) })'
        )

        parser.add_argument(
            '--generate-scales', '-os',
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
        parser.add_argument(
            '--extra-icon-theme', '-e',
            action='append',
            type=cls.parse_extra_icon_theme,
            required=False,
            default=[],
            help=f"""Extra icon theme. Format: `id:icon_theme_root_folder_path`. (e.g. you can refer to the icon theme installed on your system via `SystemTango:/usr/share/icons/Tango`)

`id` is an unique ID of the icon theme. You can use this `id` in included_icons.txt.
(NOTE This id must be unique, the following ids are occupied by built-in themes: { ", ".join(BUILT_IN_ICON_THEMES) })

Multiple values can be specified via repeating using this option.

NOTE: Always prefer declaring extra themes inside `included_icons.txt` via the `# @extra-icon-theme` directive (self-describing, also picked up by the LSP server -- see `--included-icon-file --help`) instead of this CLI flag. This CLI flag has higher priority and can be used to override the in-file directive: if the same `id` is declared in both, this CLI flag's path fully replaces the directive's (the directive's path is ignored entirely, not merged or searched as a fallback).

TODO: Currently the `theme.index` file under the specified path is ignored, only directory structure is handled.
"""
        )
        parser.add_argument(
            '--verbose',
            type=bool,
            default=False,
            help="Output logs verbosely."
        )
        parser.add_argument(
            '--debug',
            type=bool,
            default=False,
            help="Output debug logs."
        )
        args = parser.parse_args()

        return cls(
            clean_before_build=args.clean_before_build,
            included_icon_file=args.included_icon_file,
            output_stamp_file=args.output_stamp_file,
            rebuild_regardless_of_stamp_file=args.rebuild_regardless_of_stamp_file,
            output_png_theme_to_dir=args.output_png_theme_to_dir,
            output_svg_theme_to_dir=args.output_svg_theme_to_dir,
            output_theme_name=args.output_theme_name,
            output_theme_description=args.output_theme_description,
            input_svg_sizes=args.input_svg_sizes,
            output_png_sizes=args.output_png_sizes,
            output_png_sizes_from_scalable=args.output_png_sizes_from_scalable,
            generate_scales=args.generate_scales,
            qrc_qresource_prefix=args.qrc_qresource_prefix,
            extra_icon_themes=args.extra_icon_theme,
            debug=args.debug,
            verbose=args.verbose,
        )

OPTIONS = IconThemeOptions.from_args()
if OPTIONS.debug:
    print('Current options = \n')
    pprint(asdict(OPTIONS), indent=2)



def format_icon_name(icon_name_or_file_name: str | Path, to_type: Literal['noext', 'svg', 'png']) -> str:
    # NOTE: Don't use Path.stem: it splits at the last dot, which would wrongly
    # strip the final segment of reverse-DNS names like `org.inkscape.Inkscape` in XDG `hicolor/`.
    name: str = str(icon_name_or_file_name)
    if name.endswith('.svg'):
        fn_without_ext = name[:-4]
    elif name.endswith('.png'):
        fn_without_ext = name[:-4]
    else:
        fn_without_ext = name
    match to_type:
        case 'noext':
            return fn_without_ext
        case 'svg':
            return f"{fn_without_ext}.svg"
        case 'png':
            return f"{fn_without_ext}.png"


def copy_svg_file(src: str | Path, dst: str | Path, preprocessor: Literal["none", "humanity_colorizer", "nome_colorizer"]) -> None:
    src_path: Path = Path(src)
    if src_path.is_symlink():
        return None
    dst_path: Path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if preprocessor == 'none':
        shutil.copy2(src, dst)
        return
    with open(src, 'r', encoding='utf-8') as f:
        raw_content = f.read()
    with open(dst, 'w', encoding='utf-8') as f:
        if preprocessor == 'humanity_colorizer':
            f.write(humanity_colorize_svg_content(raw_content, dst_path.stem))
        elif preprocessor == 'nome_colorizer':
            f.write(nome_colorize_svg_content(raw_content, dst_path.stem))
    return

ICON_PATH_IN_THEME_PATTERN: re.Pattern[str] = re.compile(r"/([A-Za-z_-]+)/([a-z0-9@]+)/([a-z0-9@]+)/([^\\/]+?\.svg)$")
#                                                                ^              ^           ^           ^
#                                                            ThemeName   /   Context  /    Size    /   Icon
#                                                            ThemeName   /    Size    /   Context  /   Icon

class IconFileSearcher():
    """Recursively search an icon file in a folder."""
    def __init__(self, themes_folder: Path):
        self.all_icon_theme_folders: List[Path] = self.get_icon_theme_folder_list(themes_folder)
        self.all_found_icons: List[IconSrcFileInfo] = []
        for src_icon_theme_folder in self.all_icon_theme_folders:
            self.all_found_icons.extend(self.recursive_get_icon_list_in_theme(src_icon_theme_folder))

    def get_icon_theme_folder_list(self, icon_theme_search_root: Path) -> List[Path]:
        final_arr: List[Path] = []
        for folder in Path(icon_theme_search_root).iterdir():
            if not folder.is_dir(): continue
            # NOTE: nome-icon-theme has no index.theme file.
            # if (folder.joinpath('index.theme')).exists():
            final_arr.append(folder)
        return final_arr

    def recursive_get_icon_list_in_theme(self, icon_theme_folder: Path) -> List[IconSrcFileInfo]:
        final_arr: List[IconSrcFileInfo] = []
        for src_svg_file_path in icon_theme_folder.rglob("*.svg"):
            m: re.Match[str] | None = ICON_PATH_IN_THEME_PATTERN.search(src_svg_file_path.as_posix())  # use as_posix() to avoid potential backslashes under windows.
            if not m: continue
            _theme_src_folder_name = m.group(1)
            _context = m.group(2)
            _size = m.group(3)
            parsed_size = parse_size_folder_name(_size)
            icon_file_name: str = m.group(4)
            icon_name: str = format_icon_name(m.group(4), 'noext')
            if not parsed_size:
                _context, _size = _size, _context   # swap
                parsed_size = parse_size_folder_name(_size)
            if not parsed_size:
                continue
            if parsed_size.scale != '1':    # FIXME: source file of scale != 1 is not supported currently
                continue
            final_arr.append(IconSrcFileInfo(
                theme_src_folder_name = _theme_src_folder_name,
                context = _context if is_icon_context_dir_type(_context) else "apps",
                size = parsed_size.size,
                scale = parsed_size.scale,
                icon_name = icon_name,
                file_name = icon_file_name,
                src_file_path = src_svg_file_path,
                src_file_path_is_symlink = src_svg_file_path.is_symlink(),
                src_file_path_resolved = src_svg_file_path.resolve()
            ))
        final_arr.sort(key=key_for_sorting_size(lambda x: x.size))
        return final_arr

    def find_src_icon_of_any_size(self, theme_name: str, icon_name: str, icon_context: str | None) -> IconSrcFileInfo | None:
        icon_name = format_icon_name(icon_name, 'noext')
        for icon in self.all_found_icons:
            if icon_context:
                if icon.theme_src_folder_name == theme_name and icon.icon_name == icon_name and icon.context == icon_context:
                    return icon
            elif icon.theme_src_folder_name == theme_name and icon.icon_name == icon_name:
                return icon
        return None

    def filter_src_icons_of_all_sizes(self, theme_name: str, icon_name: str) -> List[IconSrcFileInfo]:
        """Filter icons by:
        - Theme Name
        - Icon Name

        All sizes of this icon will be returned.

        *(FIXME: source file of scale != 1 is not supported currently)*
        """
        icon_name = format_icon_name(icon_name, 'noext')
        final: List[IconSrcFileInfo] = []
        for icon in self.all_found_icons:
            if icon.theme_src_folder_name == theme_name and icon.icon_name == icon_name:
                final.append(icon)
        if len(final) == 0:
            raise FileNotFoundError(f'Icon "{icon_name}" not found in {theme_name}')
        return final

    def filter_src_icons_of_specified_sizes(self, theme_name: str, icon_name: str, sizes: list[IconSizeType] | set[IconSizeType]) -> List[IconSrcFileInfo]:
        """Filter icons by:
        - Theme Name
        - Icon Name
        - Icon Sizes

        All matched icons will be returned.

        *(FIXME: source file of scale != 1 is not supported currently)*
        """
        uniq_sizes = list(set(sizes))
        icon_name = format_icon_name(icon_name, 'noext')
        final: List[IconSrcFileInfo] = []
        for icon in self.all_found_icons:
            if icon.theme_src_folder_name == theme_name and icon.icon_name == icon_name and icon.size in uniq_sizes:
                final.append(icon)
        if len(final) == 0:
            raise FileNotFoundError(f'Icon "{icon_name}" not found in {theme_name}')
        return final

    def get_src_icon(self, theme_name: str, icon_name: str, icon_size: IconSizeType) -> IconSrcFileInfo:
        """Filter icons by:
        - Theme Name
        - Icon Name
        - Icon Sizes

        All matched icons will be returned.

        *(FIXME: source file of scale != 1 is not supported currently)*
        """
        icon_name = format_icon_name(icon_name, 'noext')
        for icon in self.all_found_icons:
            if icon.theme_src_folder_name == theme_name and icon.icon_name == icon_name and icon.size == icon_size:
                return icon
        raise FileNotFoundError(f'Icon "{icon_name}" not found in {theme_name}')

def key_for_sorting_size(getter: Callable[[T], IconSizeType]) -> Callable[[T], Tuple[int, int]]:
    def key(x: T) -> Tuple[int, int]:
        try:
            return (0, int(getter(x)))
        except (TypeError, ValueError):
            return (1, 0)
    return key

class SvgToPngConverter:
    """Call Inkscape to convert SVG to PNG using asyncio. Runs up to CPU count - 1 parallel processes."""

    @staticmethod
    def check_inkscape_exists() -> bool:
        return shutil.which("inkscape") is not None

    def __init__(self) -> None:
        self.process_count = max(1, (os.cpu_count() or 1) - 1)
        self.semaphore = asyncio.Semaphore(self.process_count)
        self.logger = logging.getLogger(__name__)

    def convert(self, src_svg: Path, dst_png: Path, size: int) -> Coroutine[None, None, bool]:
        return self._convert(src_svg, dst_png, size)

    async def _convert(self, src_svg: Path, dst_png: Path, size: int) -> bool:
        async with self.semaphore:
            try:
                if not src_svg.exists():
                    return False

                if dst_png.exists():
                    src_svg_mtime = src_svg.stat().st_mtime
                    dst_png_mtime = dst_png.stat().st_mtime
                    if src_svg_mtime <= dst_png_mtime:
                        if OPTIONS.verbose:
                            print(f"dst_png {dst_png} is newer than src_svg {src_svg}, don't need to build, skip.")
                        return True

                dst_png.parent.mkdir(parents=True, exist_ok=True)
                args: List[str] = [
                    "inkscape",
                    str(src_svg.absolute()),
                    "--export-type=png",
                    f"--export-width={size}",
                    f"--export-height={size}",
                    "--export-filename", str(dst_png.absolute()),
                ]
                if platform.system() == "Linux":
                    # Prevent crash. Linux only. https://gitlab.com/inkscape/inkscape/-/issues/4716
                    args = ["unshare", "--user", *args]

                process = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                _stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    self.logger.error(f"Conversion failed: {error_msg}")
                    return False
                return True

            except Exception as e:
                self.logger.exception(f"Error during conversion {e}")
                return False

def read_included_icons_txt(icon_searcher: IconFileSearcher, file_path: Path) -> List[ParsedIncludedIcon]:
    """Read `included_icons.txt` and return parsed lines. Two stages.

    1. parse_text() -- pure syntax pass. Errors collected; first one raises.
    2. icon_searcher -- confirm icon exists, resolve its actual context.
    """
    text = file_path.read_text(encoding='utf-8')
    parsed_lines, errors, _directives = parse_text(text, built_in_themes=get_all_icon_themes_folders())
    if errors:
        if len(errors) > 1:
            print(f"[ERROR] {len(errors)} format errors in {OPTIONS.included_icon_file}:", file=sys.stderr)
            for e in errors:
                print(f"[ERROR] {OPTIONS.included_icon_file}:{e.line_no}:{e.col_start + 1}: {e.message}", file=sys.stderr)
        first = errors[0]
        raise first.exc_type(f"[ERROR] {OPTIONS.included_icon_file}:{first.line_no}:{first.col_start + 1}: {first.message}")

    fin: List[ParsedIncludedIcon] = []
    for pline in parsed_lines:
        src_theme_name = pline.src_theme
        src_icon_name = pline.src_icon_name
        src_context = pline.src_context or None
        dst_context = pline.dst_context or None
        line_no = pline.line_no
        found_icon: IconSrcFileInfo | None = None
        if src_context:
            found_icon = icon_searcher.find_src_icon_of_any_size(src_theme_name, src_icon_name, src_context)
            if not found_icon:   # If combination theme+context+icon not found, raise an exception.
                raise FileNotFoundError(f'{OPTIONS.included_icon_file}:{line_no}: Not found icon of any size named "{src_icon_name}" in theme "{src_theme_name}" and specified context "{src_context}". (Hint: context of source icon is optional, you usually can omit it.)')
        elif not found_icon:
            found_icon = icon_searcher.find_src_icon_of_any_size(src_theme_name, src_icon_name, None)
        if not found_icon:
            raise FileNotFoundError(f'{OPTIONS.included_icon_file}:{line_no}: Not found icon of any size named "{src_icon_name}" in theme "{src_theme_name}"')
        # Overwrite src_context with the searcher's resolved one, and apply
        # the dst_context-falls-back-to-src rule.
        resolved_src_context = found_icon.context
        resolved_dst_context = dst_context if dst_context else resolved_src_context
        pline.src_context = resolved_src_context
        pline.dst_context = resolved_dst_context
        fin.append(pline)
    return fin


def sync_tree(src: Path, dst: Path, symlinks: bool = True) -> None:
    """
    Synchronize source tree to destination, copying only newer files.

    Only files newer in `src` are copied. Files existing only in `dst` will be removed.
    Essentially makes `dst` an exact mirror of `src`, like `rsync --delete`.

    Args:
        src: Source directory path.
        dst: Destination directory path.
        symlinks: Whether to preserve symbolic links.

    Returns:
        None

    Raises:
        OSError: If file operations fail.
    """
    src = Path(src)
    dst = Path(dst)

    if not src.exists():
        return

    dst.mkdir(parents=True, exist_ok=True)

    for src_path in src.rglob("*"):   # recursive glob
        if ".git" in src_path.parts:
            continue
        relative_path = src_path.relative_to(src)
        dst_path = dst / relative_path

        if src_path.is_symlink() and symlinks:
            if dst_path.exists() or dst_path.is_symlink():
                dst_path.unlink()
            dst_path.symlink_to(src_path.readlink())
        elif src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
            shutil.copystat(src_path, dst_path)
        elif src_path.is_file():
            should_copy = True
            if dst_path.exists():
                src_mtime = src_path.stat().st_mtime
                dst_mtime = dst_path.stat().st_mtime
                should_copy = src_mtime > dst_mtime

            if should_copy:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)

    for dst_path in dst.rglob("*"):   # recursive glob
        relative_path = dst_path.relative_to(dst)
        src_path = src / relative_path
        if not src_path.exists():
            if dst_path.is_dir() and not dst_path.is_symlink():
                shutil.rmtree(dst_path)
            else:
                dst_path.unlink()


def run_00_copy_icon_themes():
    print("00_ORIGINAL_THEMES")
    if OPTIONS.clean_before_build:
        shutil.rmtree(BUILD_FOLDERS.FOLDER_ROOT, ignore_errors=True)
        BUILD_FOLDERS.FOLDER_ROOT.mkdir(parents=True, exist_ok=True)
        for raw_theme in BUILT_IN_RAW_ICON_THEMES_PATH:
            # Keep relative symlinks, but I don't sure what will happen under Windows.
            shutil.copytree(raw_theme.copied_src_theme_folder, BUILD_FOLDERS.FOLDER_00_ORIGINAL_THEMES_ROOT / raw_theme.copied_dst_theme_name, symlinks=True, ignore=shutil.ignore_patterns('.git'))
        for extra_theme in OPTIONS.extra_icon_themes:
            shutil.copytree(extra_theme.icon_theme_root_folder_path, BUILD_FOLDERS.FOLDER_00_ORIGINAL_THEMES_ROOT / extra_theme.id, symlinks=True, ignore=shutil.ignore_patterns('.git'))
    else:
        BUILD_FOLDERS.FOLDER_ROOT.mkdir(parents=True, exist_ok=True)
        for raw_theme in BUILT_IN_RAW_ICON_THEMES_PATH:
            # Keep relative symlinks, but I don't sure what will happen under Windows.
            sync_tree(raw_theme.copied_src_theme_folder, BUILD_FOLDERS.FOLDER_00_ORIGINAL_THEMES_ROOT / raw_theme.copied_dst_theme_name, symlinks=True)
        for extra_theme in OPTIONS.extra_icon_themes:
            sync_tree(extra_theme.icon_theme_root_folder_path, BUILD_FOLDERS.FOLDER_00_ORIGINAL_THEMES_ROOT / extra_theme.id, symlinks=True)


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
            if src_theme_folder.name == "Nome":
                # Copy nome icons to blue nome
                dst_nome_svg_file_path = BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT / "BlueNome" / svg_relative_file_path
                dst_nome_svg_file_path.parent.mkdir(parents=True, exist_ok=True)
                copy_svg_file(src_svg_file_path, dst_nome_svg_file_path, "nome_colorizer")
            elif src_theme_folder.name == "Humanity":
                dst_tango_svg_file_path = BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT / "BlueHumanity" / svg_relative_file_path
                dst_tango_svg_file_path.parent.mkdir(parents=True, exist_ok=True)
                copy_svg_file(src_svg_file_path, dst_tango_svg_file_path, "humanity_colorizer")
            elif src_theme_folder.name == "Humanity-Dark":
                dst_tango_svg_file_path = BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT / "BlueHumanity-Dark" / svg_relative_file_path
                dst_tango_svg_file_path.parent.mkdir(parents=True, exist_ok=True)
                copy_svg_file(src_svg_file_path, dst_tango_svg_file_path, "humanity_colorizer")



def run_03_copy_included_icons():
    print("03_INCLUDED_SVG_ICONS")
    this_theme_folder = BUILD_FOLDERS.FOLDER_03_INCLUDED_SVG_ICONS / OPTIONS.output_theme_name
    this_theme_folder.mkdir(parents=True, exist_ok=True)
    # Initialize icon searcher for colorized themes folder.
    icon_searcher = IconFileSearcher(BUILD_FOLDERS.FOLDER_02_COLORIZED_THEMES_ROOT)
    global PARSED_INCLUDED_ICONS_TXT_LINES
    PARSED_INCLUDED_ICONS_TXT_LINES = read_included_icons_txt(icon_searcher, OPTIONS.included_icon_file)
    for pline in PARSED_INCLUDED_ICONS_TXT_LINES:
        size_io_specified: bool = not pline.size_io_matrix.is_empty()
        if size_io_specified:
            found_src_icons_of_specified_input_sizes = icon_searcher.filter_src_icons_of_specified_sizes(pline.src_theme, pline.src_icon_name, pline.size_io_matrix.get_all_input_sizes())
        else:
            found_src_icons_of_specified_input_sizes = icon_searcher.filter_src_icons_of_all_sizes(pline.src_theme, pline.src_icon_name)

        for src_icon in found_src_icons_of_specified_input_sizes:
            if src_icon.src_file_path_is_symlink:
                print(f'[WARNING] "{src_icon.src_file_path}" is a symlink, auto follows link original file.')

            if (size_io_specified) and (src_icon.size not in OPTIONS.input_svg_sizes):
                continue
            else:
                pass
            # if src_icon.scale not in OPTIONS.generate_scales and src_icon.scale != '1':    # FIXME: source file of scale != 1 is not supported currently
            #     continue

            # copy included icon.
            dst_context = pline.dst_context
            dst_file_name = format_icon_name(pline.dst_icon_name, 'svg')
            icon_dst_file_path: Path = this_theme_folder / dst_context / src_icon.size / dst_file_name   # SVN / CVS convension
            icon_dst_file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_icon.src_file_path_resolved, icon_dst_file_path)

def run_04_convert_svg_to_xdg_hicolor_theme_dir_structure():
    print("04_XDG_SVG_THEME")
    this_theme_folder = BUILD_FOLDERS.FOLDER_04_XDG_SVG_THEME / OPTIONS.output_theme_name
    this_theme_folder.mkdir(parents=True, exist_ok=True)
    # Initialize icon searcher for previous folder.
    icon_searcher = IconFileSearcher(BUILD_FOLDERS.FOLDER_03_INCLUDED_SVG_ICONS)

    qrc = QrcCreator(OPTIONS.output_theme_name)
    index_theme = IndexThemeCreator()
    for pline in PARSED_INCLUDED_ICONS_TXT_LINES:
        dst_icon_name = format_icon_name(pline.dst_icon_name, 'noext')
        icon_size_io_list = pline.size_io_matrix.all_data     # all definitions of `input -> output of an icon.
        if not icon_size_io_list:   # No `{...}` specified in this icon line, grab all sizes via `IconFileSearcher`
            icon_size_io_list = [SizeIo(input=i.size, output=i.size) for i in icon_searcher.filter_src_icons_of_all_sizes(OPTIONS.output_theme_name, dst_icon_name)]
        for size_io in icon_size_io_list:
            src_icon_file = icon_searcher.get_src_icon(OPTIONS.output_theme_name, dst_icon_name, size_io.input)  # OPTIMIZE: Very inefficient but unmatured optimization is source of evil so ignore it for now.
            if not src_icon_file:
                raise FileNotFoundError(f'''Impossible. Not found icon "{dst_icon_name}" in "{BUILD_FOLDERS.FOLDER_03_INCLUDED_SVG_ICONS}".''')

            # copy files
            if src_icon_file.src_file_path_is_symlink:
                print("Impossible bug.")
                continue
            icon_dst_file_path: Path = this_theme_folder / get_xdg_size_folder_name(size_io.output, src_icon_file.scale) / src_icon_file.context / src_icon_file.file_name   # SVN / CVS convension
            icon_dst_file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_icon_file.src_file_path_resolved, icon_dst_file_path)

            # add to qrc
            qrc.add_file(src_icon_file.context, size_io.output, src_icon_file.scale, src_icon_file.file_name)

            # index.theme
            index_theme.add_index_theme_ini_section(src_icon_file.context, size_io.output, src_icon_file.scale)

    qrc.write_qrc_file(this_theme_folder / "index.qrc")
    index_theme.write_index_theme_file(this_theme_folder / "index.theme")

async def run_05_convert_svg_to_png():
    print("05_XDG_PNG_THEME")
    if (SvgToPngConverter.check_inkscape_exists() == False):
        print("Inkscape is not found. Please install Inkscape.")
        return
    dst_theme_folder = BUILD_FOLDERS.FOLDER_05_XDG_PNG_THEME / OPTIONS.output_theme_name
    dst_theme_folder.mkdir(parents=True, exist_ok=True)

    # Initialize icon searcher for previous folder.
    icon_searcher = IconFileSearcher(BUILD_FOLDERS.FOLDER_04_XDG_SVG_THEME)

    qrc = QrcCreator(OPTIONS.output_theme_name)
    index_theme = IndexThemeCreator()

    svg2png = SvgToPngConverter()
    deferred: List[Coroutine[None, None, bool]] = []
    for icon in icon_searcher.all_found_icons:
        for scale in OPTIONS.generate_scales:
            # qrc & index.theme
            if icon.size != 'scalable':    # FIXME: source file of scale != 1 is not supported currently
                if OPTIONS.output_png_sizes and icon.size not in OPTIONS.output_png_sizes:
                    continue
                qrc.add_file(icon.context, icon.size, scale, f"{icon.icon_name}.png")
                index_theme.add_index_theme_ini_section(icon.context, icon.size, scale)
                dst_png_file_path = dst_theme_folder / get_xdg_size_folder_name(icon.size, scale) / icon.context / f"{icon.icon_name}.png"   # REFACTOR: a function to assemble path? (for svn convension <-> xdg standard)
                dst_png_file_path.parent.mkdir(parents=True, exist_ok=True)
                deferred.append(svg2png.convert(icon.src_file_path_resolved, dst_png_file_path, int(icon.size) * int(scale)))
                print(f"Convert {dst_png_file_path}")
            else:
                for fixed_px_size in OPTIONS.output_png_sizes_from_scalable:
                    if fixed_px_size == 'scalable': continue
                    qrc.add_file(icon.context, fixed_px_size, scale, f"{icon.icon_name}.png")   # OPTIMIZE: Use QRC alias to reduce duplicated PNG files
                    index_theme.add_index_theme_ini_section(icon.context, fixed_px_size, scale)
                    dst_png_file_path = dst_theme_folder / get_xdg_size_folder_name(fixed_px_size, scale) / icon.context / f"{icon.icon_name}.png"   # REFACTOR: a function to assemble path? (for svn convension <-> xdg standard)
                    dst_png_file_path.parent.mkdir(parents=True, exist_ok=True)
                    deferred.append(svg2png.convert(icon.src_file_path_resolved, dst_png_file_path, int(fixed_px_size) * int(scale)))
                    print(f"Convert {dst_png_file_path}")

    qrc.write_qrc_file(dst_theme_folder / "index.qrc")
    index_theme.write_index_theme_file(dst_theme_folder / "index.theme")

    await asyncio.gather(*deferred)

def get_xdg_size_folder_name(size: IconSizeType, scale: IconScaleType) -> str:
    '''Follow the directory structure of `hicolor` (Fallback icon theme pack in XDG standard) `<size>x<size>@<scale>/<context>`
    So that the generated directory structure can be directly copied into `/usr/share/icons/hicolor/` and compatible with the existed icons in it.'''
    if size == 'scalable':
        return 'scalable'
    elif scale == "1":
        return f'{size}x{size}'
    else:
        return f"{size}x{size}@{scale}"

def sha256_file_content(file_path: Path) -> str:
    with file_path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def all_icons_need_regenerate() -> bool:
    '''Return True if icons need to be regenerated (compare the SHA256 hash of `included_icon_file`).'''
    # TODO: Also record the commit hash of this repo.
    if OPTIONS.rebuild_regardless_of_stamp_file:
        return True
    if OPTIONS.clean_before_build:
        return True
    if not OPTIONS.output_stamp_file.exists():
        print(f"""Stamp file "{OPTIONS.output_stamp_file}" doesn't exist, so start to build all icons.""")
        return True
    old_hash: str = OPTIONS.output_stamp_file.read_text().strip()
    new_hash: str = sha256_file_content(OPTIONS.included_icon_file)
    print(f"""SHA256 hash of {OPTIONS.included_icon_file}:""")
    print(f"""Old: {old_hash}""")
    print(f"""New: {new_hash}""")
    if old_hash != new_hash:
        print(f"""The SHA256 hash of "{OPTIONS.included_icon_file}" has been changed, start to build all icons.""")
        return True
    else:
        print(f"""The SHA256 hash of "{OPTIONS.included_icon_file}" doesn't change, skip icon building.""")
        return False
    # This Python script should not rely on mtime of included_icons.txt. mtime is designed for other build tools such as Makefile.
    # if OPTIONS.included_icon_file.stat().st_mtime > OPTIONS.output_stamp_file.stat().st_mtime:
    #     print(f"""The "{OPTIONS.included_icon_file}" is newer than stamp file "{OPTIONS.output_stamp_file}", so start to build all icons.""")
    #     return True
    return False


@dataclass
class ParsedIconSizeFolder():
    size: IconSizeType
    scale: IconScaleType

def parse_size_folder_name(folder_name: str) -> ParsedIconSizeFolder | None:
    """Acceptable inputs:
    - `24`
    - `24@2`
    - `24x24`
    - `24x24@2`
    - `24x24@2x`
    - 'scalable' (`scale` will be `1`)
    """
    if folder_name == 'scalable':
        return ParsedIconSizeFolder(size = 'scalable', scale = '1')
    m = re.match(r"^(\d+)(?:x\d+)?(?:@(\d+))?x?$", folder_name)
    if not m:
        return None
    _size = m.group(1)
    _scale = m.group(2)
    return ParsedIconSizeFolder(
        size = _size if is_icon_size_type(_size) else 'scalable',
        scale = _scale if is_icon_scale_type(_scale) else '1'
    )

def run_extra_copy():
    svg_theme_folder = BUILD_FOLDERS.FOLDER_04_XDG_SVG_THEME / OPTIONS.output_theme_name
    png_theme_folder = BUILD_FOLDERS.FOLDER_05_XDG_PNG_THEME / OPTIONS.output_theme_name
    if OPTIONS.output_svg_theme_to_dir:
        shutil.copytree(svg_theme_folder, OPTIONS.output_svg_theme_to_dir, dirs_exist_ok=True)
    if OPTIONS.output_png_theme_to_dir:
        shutil.copytree(png_theme_folder, OPTIONS.output_png_theme_to_dir, dirs_exist_ok=True)


def write_stamp_file():
    OPTIONS.output_stamp_file.parent.mkdir(parents=True, exist_ok=True)
    OPTIONS.output_stamp_file.touch()
    new_hash: str = sha256_file_content(OPTIONS.included_icon_file)
    OPTIONS.output_stamp_file.write_text(new_hash)

def main():
    # ensure_tarballs_downloaded_and_extracted(Path(__file__).parent / "tarballs")
    if not all_icons_need_regenerate():
        print('''Icons don't need regenerating. Skip.''')
        exit(0)
    run_00_copy_icon_themes()
    run_01_no_symlink_themes()
    run_02_colorize_themes()
    run_03_copy_included_icons()
    run_04_convert_svg_to_xdg_hicolor_theme_dir_structure()
    asyncio.run(run_05_convert_svg_to_png())
    run_extra_copy()
    write_stamp_file()

if __name__ == "__main__":
    # profiler = cProfile.Profile()
    # profiler.enable()
    main()
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats('cumulative')
    # stats.print_stats()
