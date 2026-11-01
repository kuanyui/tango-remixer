#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The licenses of icons: the license of each theme they come from, and the icons whose own license differs.

An icon's license is the `SPDX-License-Identifier` near the top of its SVG file (every Nome file has one,
Tango's newer files too), else the license of its theme (THEME_LICENSES; a theme not there, such as an extra
theme of the user's, has the license most of its picked files state). This is the rule README's
"Built-in Icon Themes and Licenses" states: the SPDX tag inside the individual SVG file prevails.
Licenses in Inkscape's RDF metadata are not read: the few files that have one predate their theme's
relicensing (two Tango files still say CC BY-SA 2.0).

build_icons.py writes, beside the output theme's index.theme (and lists the JSON in its index.qrc):

- licenses.json: each source theme with its license, its URL, how many icons the output takes from it,
  and its exceptions (the icons whose license is not the theme's). For an About dialog, e.g. in Qt:
  `QFile(":/xdg_icon_themes/<theme>/licenses.json")` read by QJsonDocument.
- licenses.csv: every icon of the output with its source and license, one row per icon.

Nothing here imports build_icons.py (which reads the command line when imported), so other tools can
use it too. Run it to see the exceptions of a whole theme folder:

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

THEME_LICENSES: Final[Dict[str, str]] = {
    "Tango":                 "GPL-2.0-only OR GPL-3.0-only",
    "Nome":                  "LGPL-3.0-only OR CC-BY-SA-3.0",
    "Humanity":              "GPL-2.0-only",   # its AUTHORS: "licensed under GNU General Public License version 2"
    "Humanity-Dark":         "GPL-2.0-only",
    "GimpLegacy":            "GPL-3.0-or-later",
    "GimpDefault":           "CC-BY-SA-3.0",
    "InkscapeTango":         "GPL-2.0-only",
    "LibreOfficeElementary": "GPL-3.0-only",
}
"""The license of each built-in theme as an SPDX expression, as README's "Built-in Icon Themes and Licenses"
has it. A theme not here (an extra theme of the user's) has the license most of its picked files state."""

BASE_THEMES: Final[Dict[str, str]] = {
    "BlueNome":          "Nome",
    "BlueHumanity":      "Humanity",
    "BlueHumanity-Dark": "Humanity-Dark",
}
"""The themes the build makes by colorizing another one: they have that one's license."""

SPDX_PATTERN: Final[re.Pattern[bytes]] = re.compile(rb"SPDX-License-Identifier:[ \t]*(.+?)[ \t]*(?:-->|\*/|\r|\n|$)")
HEAD_BYTES: Final[int] = 4096
"""How much of a file is searched: the identifier is a comment at the top (Nome's add_spdx.py looks in 1024)."""

SIZE_FOLDER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(\d+(x\d+)?(@\d+x?)?|scalable)$")


def theme_license(theme: str) -> Optional[str]:
    """The license of a theme as a whole, e.g. "LGPL-3.0-only OR CC-BY-SA-3.0" for Nome and BlueNome; None when unknown."""
    return THEME_LICENSES.get(BASE_THEMES.get(theme, theme))


def read_spdx(svg: Path) -> Optional[str]:
    """The SPDX-License-Identifier near the top of an SVG file, e.g. "GPL-2.0-only"; None when it has none."""
    with svg.open("rb") as f:
        m = SPDX_PATTERN.search(f.read(HEAD_BYTES))
    return " ".join(m.group(1).decode("utf-8", "replace").split()) if m else None


@dataclass(frozen=True)
class IconFile():
    """One SVG file of an icon: where it comes from, and what the output theme calls the icon."""
    theme: str
    """The theme it comes from, e.g. "BlueNome"."""
    source: str
    """Its context and name in that theme, e.g. "places/user-trash"."""
    context: str
    """Its context in the output theme, e.g. "actions"."""
    name: str
    """Its name in the output theme, e.g. "edit-delete"."""
    size: str
    """The size folder it comes from, e.g. "16" or "scalable"."""
    path: Path
    """The file, read for its SPDX-License-Identifier."""


@dataclass
class IconLicense():
    """An icon of the output theme and its license. An icon whose sizes differ in license has one per license."""
    theme: str
    source: str
    context: str
    name: str
    license: Optional[str]
    """None when neither its files nor its theme say."""
    theme_license: Optional[str]
    """The license of its theme as a whole: THEME_LICENSES, else the one most of the theme's picked files state."""
    exception: bool
    """Its license is not its theme's."""
    sizes: List[str] = field(default_factory=list)
    """The size folders of its source files, e.g. ["16", "22", "scalable"] (the output may resize them)."""


def _size_order(size: str) -> Tuple[int, int]:
    return (1, 0) if not size[:1].isdigit() else (0, int(re.match(r"\d+", size).group()))   # type: ignore[union-attr]


def icon_licenses(files: Iterable[IconFile]) -> List[IconLicense]:
    """The files grouped by icon and license, in the order the icons first come."""
    found: List[Tuple[IconFile, Optional[str]]] = [(f, read_spdx(f.path) or theme_license(f.theme)) for f in files]
    stated: Dict[str, Counter[Optional[str]]] = {}
    for f, license in found:
        stated.setdefault(f.theme, Counter())[license] += 1
    of_theme: Dict[str, Optional[str]] = {theme: theme_license(theme) or counts.most_common(1)[0][0] for theme, counts in stated.items()}
    groups: Dict[Tuple[str, str, str, str, Optional[str]], IconLicense] = {}
    for f, license in found:
        key = (f.theme, f.source, f.context, f.name, license)
        group: IconLicense = groups.setdefault(key, IconLicense(f.theme, f.source, f.context, f.name, license, of_theme[f.theme], license != of_theme[f.theme]))
        if f.size not in group.sizes:
            group.sizes.append(f.size)
    for group in groups.values():
        group.sizes.sort(key=_size_order)
    return list(groups.values())


def license_report(theme: str, icons: List[IconLicense], urls: Dict[str, str]) -> Dict[str, object]:
    """What licenses.json holds, for the output theme `theme`. `urls` gives each source theme's web page.

    "licenses" lists every license the icons have; "sources" lists the themes in the order the icons
    first come from them, each with "exceptions": its icons whose license is not the theme's "license".
    A colorized theme names the theme it is made from as "base" (e.g. BlueNome's is Nome), else null."""
    sources: List[Dict[str, object]] = []
    for source in dict.fromkeys(i.theme for i in icons):
        of_source: List[IconLicense] = [i for i in icons if i.theme == source]
        sources.append({
            "theme": source,
            "base": BASE_THEMES.get(source),
            "license": of_source[0].theme_license,
            "url": urls.get(source),
            "icon_count": len({(i.context, i.name) for i in of_source}),
            "exceptions": [
                {"icon": f"{i.context}/{i.name}", "source": i.source, "source_sizes": i.sizes, "license": i.license}
                for i in of_source if i.exception
            ],
        })
    return {
        "theme": theme,
        "licenses": sorted({i.license for i in icons if i.license}),
        "sources": sources,
    }


CSV_COLUMNS: Final[List[str]] = ["icon", "theme", "source", "source_sizes", "license", "exception"]

SHORT_LIST_PATTERN: Final[re.Pattern[str]] = re.compile(r"\[\n\s*([^\[\]{}]*?)\n\s*\]")
"""A list of plain values as json.dumps(indent=...) writes it, one value per line."""


def _json_text(data: object) -> str:
    """JSON indented by 2, with a short list of plain values on one line, e.g. "source_sizes": ["16", "22"]."""
    def one_line(m: re.Match[str]) -> str:
        joined: str = "[" + re.sub(r"\n\s*", " ", m.group(1)) + "]"   # JSON strings hold no raw newlines: only the breaks between values go
        return joined if len(joined) <= 60 else m.group(0)
    return SHORT_LIST_PATTERN.sub(one_line, json.dumps(data, indent=2, ensure_ascii=False))


def write_license_files(folder: Path, theme: str, icons: List[IconLicense], urls: Dict[str, str]) -> None:
    """licenses.json (license_report) and licenses.csv (one row per icon, CSV_COLUMNS) in `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "licenses.json").write_text(_json_text(license_report(theme, icons, urls)) + "\n", encoding="utf-8")
    with (folder / "licenses.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for i in icons:
            writer.writerow([f"{i.context}/{i.name}", i.theme, i.source, " ".join(i.sizes), i.license or "", "yes" if i.exception else ""])


def scan_theme(theme: str, folder: Path) -> List[IconFile]:
    """Every SVG file of a theme folder (`<context>/<size>/<name>.svg` or `<size>/<context>/<name>.svg`) as an
    icon of its own name. Symlinks are left out: they are other names of a file that is counted."""
    files: List[IconFile] = []
    for svg in sorted(folder.rglob("*.svg")):
        parts: Tuple[str, ...] = svg.relative_to(folder).parts
        if svg.is_symlink() or len(parts) < 3:
            continue
        context, size = parts[-3], parts[-2]
        if SIZE_FOLDER_PATTERN.match(context):
            context, size = size, context
        files.append(IconFile(theme, f"{context}/{svg.stem}", context, svg.stem, size, svg))
    return files


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("Usage: python3 -m lib.icon_licenses THEME FOLDER\n"
              "Print licenses.json for every icon of the theme folder, e.g. Nome submodules/nome-icon-theme/src", file=sys.stderr)
        return 2
    theme, folder = argv
    print(_json_text(license_report(theme, icon_licenses(scan_theme(theme, Path(folder))), {})))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
