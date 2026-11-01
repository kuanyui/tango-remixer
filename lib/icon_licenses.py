#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""License info of the picked icons.

- License of an SVG file:
  1. Its `SPDX-License-Identifier` comment, in the first 4096 bytes. ex: `<!-- SPDX-License-Identifier: GPL-2.0-only -->`
  2. If not found: the license of its built-in theme. (See `BUILT_IN_THEME_LICENSES`)
  3. If not found, and the theme is not built-in (ex: `AppIcon` of qkiss): None.
- License of a theme:
  - Built-in theme: `BUILT_IN_THEME_LICENSES`.
  - Not built-in: the most common license of its picked SVG files. (None also counts. On a tie, the first one wins.)
- Exception: an SVG file whose license is not the license of its theme.
- Inkscape's RDF metadata (`<cc:license>`) is not read, because many files still have an old license in it.
  ex: most Tango files say Public Domain, but the Tango fork is `GPL-2.0-only OR GPL-3.0-only`.

`build_icons.py` writes 2 files beside `index.theme`:
- `licenses.json`: for an About dialog. Also listed in `index.qrc`. ex: `QFile(":/xdg_icon_themes/<theme>/licenses.json")`
- `licenses.csv`: one row per `IconLicenseGroup`.

This file doesn't import `build_icons.py`, so other tools can use it.
ex: print `licenses.json` of a whole theme folder:

    python3 -m lib.icon_licenses Nome submodules/nome-icon-theme/src
"""
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter
from typing import Dict, Final, Iterable, List, Optional, Tuple

BUILT_IN_THEME_LICENSES: Final[Dict[str, str]] = {
    "Tango":                 "GPL-2.0-only OR GPL-3.0-only",
    "Nome":                  "LGPL-3.0-only OR CC-BY-SA-3.0",
    "Humanity":              "GPL-2.0-only",   # Humanity's AUTHORS: "licensed under GNU General Public License version 2"
    "Humanity-Dark":         "GPL-2.0-only",
    "GimpLegacy":            "GPL-3.0-or-later",
    "GimpDefault":           "CC-BY-SA-3.0",
    "InkscapeTango":         "GPL-2.0-only",
    "LibreOfficeElementary": "GPL-3.0-only",
}
"""Built-in theme name -> license of the theme (SPDX expression)."""

BASE_THEME_OF_COLORIZED_THEME: Final[Dict[str, str]] = {
    "BlueNome":          "Nome",
    "BlueHumanity":      "Humanity",
    "BlueHumanity-Dark": "Humanity-Dark",
}
"""Colorized theme -> base theme. ex: "BlueNome" -> "Nome". A colorized theme has the license of its base theme."""

SPDX_LICENSE_IDENTIFIER_PATTERN: Final[re.Pattern[bytes]] = re.compile(rb"SPDX-License-Identifier:[ \t]*(.+?)[ \t]*(?:-->|\*/|\r|\n|$)")
"""ex: <!-- SPDX-License-Identifier: GPL-2.0-only -->  ->  "GPL-2.0-only" """
SPDX_SEARCH_BYTE_COUNT: Final[int] = 4096
"""Only the first 4096 bytes of an SVG file are searched for the SPDX comment."""


def get_built_in_theme_license(src_theme: str) -> Optional[str]:
    """License of a built-in theme. None if the theme is not built-in.
    ex:
    - "Nome"     -> "LGPL-3.0-only OR CC-BY-SA-3.0"
    - "BlueNome" -> same as "Nome" (colorized from "Nome")
    - "AppIcon"  -> None
    """
    return BUILT_IN_THEME_LICENSES.get(BASE_THEME_OF_COLORIZED_THEME.get(src_theme, src_theme))


def read_spdx_license_identifier(src_svg_file_path: Path) -> Optional[str]:
    """ex: <!-- SPDX-License-Identifier: GPL-2.0-only --> -> "GPL-2.0-only". None if not found in the first 4096 bytes."""
    with src_svg_file_path.open("rb") as svg_file:
        spdx_match = SPDX_LICENSE_IDENTIFIER_PATTERN.search(svg_file.read(SPDX_SEARCH_BYTE_COUNT))
    return " ".join(spdx_match.group(1).decode("utf-8", "replace").split()) if spdx_match else None


@dataclass(frozen=True)
class PickedSvgFile():
    """One SVG file picked by `included_icons.txt`.
    ex: the line `Nome    user-trash    edit-delete    {16}` gives
        src_theme="Nome", src_context_and_icon_name="places/user-trash", src_size="16",
        dst_context="places", dst_icon_name="edit-delete"
        (The line has no dst context, so dst_context = the src context.)
    """
    src_theme: str
    src_context_and_icon_name: str
    """Without size or extension. ex: "places/user-trash" """
    dst_context: str
    dst_icon_name: str
    """Without extension. ex: "edit-delete" """
    src_size: str
    """ex: "16", "scalable". The size, not the folder name: folder `16x16/` -> "16"."""
    src_file_path: Path
    """Read for its SPDX comment."""


@dataclass
class IconLicenseGroup():
    """Picked SVG files with the same source icon, the same output icon, and the same license.
    ex:
    - `apps/obj-id`: sizes 16, 22, 24, 32 are all LGPL-2.1-only -> 1 group, src_sizes=["16", "22", "24", "32"]
    - If size 22 had another license -> 2 groups: ["16", "24", "32"] and ["22"]
    """
    src_theme: str
    src_context_and_icon_name: str
    dst_context: str
    dst_icon_name: str
    icon_license: Optional[str]
    """None if neither the SVG files nor their built-in theme has a license."""
    src_theme_license: Optional[str]
    """License of `src_theme`. (For a theme that is not built-in, see the module docstring.)"""
    is_license_exception: bool
    """True if `icon_license` is not `src_theme_license`. ex: GPL-2.0-only vs LGPL-3.0-only -> True. None vs None -> False."""
    src_sizes: List[str] = field(default_factory=list)
    """ex: ["16", "22", "scalable"]. Sizes of the source SVG files, not the output sizes."""


def _get_size_sort_key(src_size: str) -> Tuple[int, int]:
    """ex: "16" -> (0, 16), "scalable" -> (1, 0). So "scalable" comes last."""
    if not src_size.isdigit():
        return (1, 0)
    return (0, int(src_size))


def read_licenses_then_group_by_icon_and_license(picked_files: Iterable[PickedSvgFile]) -> List[IconLicenseGroup]:
    """Read the license of each picked SVG file, then group the files by source icon + output icon + license.
    Returns:
        List[IconLicenseGroup], in the order of `picked_files`.
    """
    picked_files_with_licenses: List[Tuple[PickedSvgFile, Optional[str]]] = [
        (picked_file, read_spdx_license_identifier(picked_file.src_file_path) or get_built_in_theme_license(picked_file.src_theme))
        for picked_file in picked_files
    ]
    license_counts_by_src_theme: Dict[str, Counter[Optional[str]]] = {}
    for picked_file, icon_license in picked_files_with_licenses:
        license_counts_by_src_theme.setdefault(picked_file.src_theme, Counter())[icon_license] += 1
    # Theme not built-in (ex: AppIcon): use the most common license of its picked files. (None also counts.)
    src_theme_licenses: Dict[str, Optional[str]] = {
        src_theme: get_built_in_theme_license(src_theme) or license_counts.most_common(1)[0][0]
        for src_theme, license_counts in license_counts_by_src_theme.items()
    }
    icon_license_groups_by_key: Dict[Tuple[str, str, str, str, Optional[str]], IconLicenseGroup] = {}
    for picked_file, icon_license in picked_files_with_licenses:
        group_key = (picked_file.src_theme, picked_file.src_context_and_icon_name, picked_file.dst_context, picked_file.dst_icon_name, icon_license)
        if group_key not in icon_license_groups_by_key:
            src_theme_license: Optional[str] = src_theme_licenses[picked_file.src_theme]
            icon_license_groups_by_key[group_key] = IconLicenseGroup(
                src_theme=picked_file.src_theme,
                src_context_and_icon_name=picked_file.src_context_and_icon_name,
                dst_context=picked_file.dst_context,
                dst_icon_name=picked_file.dst_icon_name,
                icon_license=icon_license,
                src_theme_license=src_theme_license,
                is_license_exception=(icon_license != src_theme_license),
            )
        icon_license_group: IconLicenseGroup = icon_license_groups_by_key[group_key]
        if picked_file.src_size not in icon_license_group.src_sizes:
            icon_license_group.src_sizes.append(picked_file.src_size)
    for icon_license_group in icon_license_groups_by_key.values():
        icon_license_group.src_sizes.sort(key=_get_size_sort_key)
    return list(icon_license_groups_by_key.values())


def make_licenses_json_dict(dst_theme: str, icon_license_groups: List[IconLicenseGroup], src_theme_urls: Dict[str, str]) -> Dict[str, object]:
    """Content of licenses.json. ex:
    {
      "dst_theme": "CustomizedTango",
      "all_icon_licenses": ["GPL-3.0-only", "LGPL-2.1-only", ...],
      "src_themes": [
        {
          "src_theme": "Nome",
          "base_theme": null,
          "src_theme_license": "LGPL-3.0-only OR CC-BY-SA-3.0",
          "src_theme_url": "https://github.com/kuanyui/nome-icon-theme",
          "picked_icon_count": 32,
          "icon_license_exceptions": [
            {
              "dst_context_and_icon_name": "apps/obj-id",
              "src_context_and_icon_name": "apps/tomboy-tag",
              "src_sizes": ["16", "22", "24", "32"],
              "icon_license": "LGPL-2.1-only"
            }
          ]
        },
        ...
      ]
    }
    """
    src_theme_dicts: List[Dict[str, object]] = []
    for src_theme in dict.fromkeys(group.src_theme for group in icon_license_groups):
        src_theme_icon_license_groups: List[IconLicenseGroup] = [group for group in icon_license_groups if group.src_theme == src_theme]
        src_theme_dicts.append({
            "src_theme": src_theme,
            "base_theme": BASE_THEME_OF_COLORIZED_THEME.get(src_theme),
            "src_theme_license": src_theme_icon_license_groups[0].src_theme_license,
            "src_theme_url": src_theme_urls.get(src_theme),
            "picked_icon_count": len({(group.dst_context, group.dst_icon_name) for group in src_theme_icon_license_groups}),
            "icon_license_exceptions": [
                {
                    "dst_context_and_icon_name": f"{group.dst_context}/{group.dst_icon_name}",
                    "src_context_and_icon_name": group.src_context_and_icon_name,
                    "src_sizes": group.src_sizes,
                    "icon_license": group.icon_license,
                }
                for group in src_theme_icon_license_groups if group.is_license_exception
            ],
        })
    return {
        "dst_theme": dst_theme,
        "all_icon_licenses": sorted({group.icon_license for group in icon_license_groups if group.icon_license}),
        "src_themes": src_theme_dicts,
    }


LICENSES_CSV_COLUMN_NAMES: Final[List[str]] = [
    "dst_context_and_icon_name", "src_theme", "src_context_and_icon_name", "src_sizes", "icon_license", "is_license_exception",
]
"""Columns of licenses.csv. ex row: `apps/obj-id,Nome,apps/tomboy-tag,16 22 24 32,LGPL-2.1-only,yes`"""

JSON_MULTILINE_LIST_PATTERN: Final[re.Pattern[str]] = re.compile(r"\[\n\s*([^\[\]{}]*?)\n\s*\]")
"""A list written by `json.dumps(indent=2)`, one value per line, with no list or dict inside. ex:
    [
      "16",
      "22"
    ]
"""
MAX_ONE_LINE_LIST_LENGTH: Final[int] = 60


def _format_json_text(data: object) -> str:
    """Same as `json.dumps(data, indent=2, ensure_ascii=False)`, but a list of at most 60 characters is on one line. ex: "src_sizes": ["16", "22"]"""
    def format_list_on_one_line_if_short(list_match: re.Match[str]) -> str:
        """Return the matched list on one line if it has at most 60 characters. Else return the matched text as it is."""
        # A JSON string never contains a raw newline (it is escaped as \n).
        # So only the line breaks between list values are replaced.
        one_line_list_text: str = "[" + re.sub(r"\n\s*", " ", list_match.group(1)) + "]"
        return one_line_list_text if len(one_line_list_text) <= MAX_ONE_LINE_LIST_LENGTH else list_match.group(0)
    return JSON_MULTILINE_LIST_PATTERN.sub(format_list_on_one_line_if_short, json.dumps(data, indent=2, ensure_ascii=False))


def write_licenses_json_and_csv(dst_theme_folder: Path, dst_theme: str, icon_license_groups: List[IconLicenseGroup], src_theme_urls: Dict[str, str]) -> None:
    """Write `licenses.json` and `licenses.csv` into `dst_theme_folder`. (One CSV row per `IconLicenseGroup`.)"""
    dst_theme_folder.mkdir(parents=True, exist_ok=True)
    licenses_json_dict: Dict[str, object] = make_licenses_json_dict(dst_theme, icon_license_groups, src_theme_urls)
    (dst_theme_folder / "licenses.json").write_text(_format_json_text(licenses_json_dict) + "\n", encoding="utf-8")
    with (dst_theme_folder / "licenses.csv").open("w", encoding="utf-8", newline="") as csv_file:
        csv_writer = csv.writer(csv_file, lineterminator="\n")
        csv_writer.writerow(LICENSES_CSV_COLUMN_NAMES)
        for icon_license_group in icon_license_groups:
            csv_writer.writerow([
                f"{icon_license_group.dst_context}/{icon_license_group.dst_icon_name}",
                icon_license_group.src_theme,
                icon_license_group.src_context_and_icon_name,
                " ".join(icon_license_group.src_sizes),
                icon_license_group.icon_license or "",
                "yes" if icon_license_group.is_license_exception else "",
            ])


def _parse_size_folder_name(size_folder_name: str) -> Optional[str]:
    """ex: "16" -> "16", "16x16" -> "16", "16x16@2" -> "16", "scalable" -> "scalable", "symbolic" -> None"""
    if size_folder_name == "scalable":
        return "scalable"
    size_match = re.match(r"^(\d+)(?:x\d+)?(?:@\d+x?)?$", size_folder_name)
    return size_match.group(1) if size_match else None


def find_svg_files_in_theme(src_theme: str, src_theme_folder: Path) -> List[PickedSvgFile]:
    """Every SVG file in `src_theme_folder`, with output name = source name. For the command line only.
    - Folder structure can be `<context>/<size>/` or `<size>/<context>/`. ex: `apps/16/totem.svg`, `16x16/apps/totem.svg`
    - Symlinks are skipped.
    - Files not in a size folder are skipped. ex: `actions/symbolic/list-add-symbolic.svg`
    """
    src_svg_files: List[PickedSvgFile] = []
    for src_svg_file_path in sorted(src_theme_folder.rglob("*.svg")):
        relative_path_parts: Tuple[str, ...] = src_svg_file_path.relative_to(src_theme_folder).parts
        if src_svg_file_path.is_symlink() or len(relative_path_parts) < 3:
            continue
        src_context, size_folder_name = relative_path_parts[-3], relative_path_parts[-2]
        if _parse_size_folder_name(src_context):   # ex: 16x16/apps/totem.svg
            src_context, size_folder_name = size_folder_name, src_context
        src_size: Optional[str] = _parse_size_folder_name(size_folder_name)
        if src_size is None:
            continue
        src_svg_files.append(PickedSvgFile(
            src_theme=src_theme,
            src_context_and_icon_name=f"{src_context}/{src_svg_file_path.stem}",
            dst_context=src_context,
            dst_icon_name=src_svg_file_path.stem,
            src_size=src_size,
            src_file_path=src_svg_file_path,
        ))
    return src_svg_files


def main(argv: List[str]) -> int:
    """Print licenses.json of a whole theme folder. Return 2 if argv is not [THEME, FOLDER]."""
    if len(argv) != 2:
        print("Usage: python3 -m lib.icon_licenses THEME FOLDER\n"
              "Print licenses.json of a whole theme folder. ex: Nome submodules/nome-icon-theme/src", file=sys.stderr)
        return 2
    src_theme, src_theme_folder = argv
    picked_files: List[PickedSvgFile] = find_svg_files_in_theme(src_theme, Path(src_theme_folder))
    licenses_json_dict: Dict[str, object] = make_licenses_json_dict(src_theme, read_licenses_then_group_by_icon_and_license(picked_files), {})
    print(_format_json_text(licenses_json_dict))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
