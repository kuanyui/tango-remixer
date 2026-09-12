#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local web UI for browsing the source icon themes that `included_icons.txt` can reference.

Run: `python3 -m viewer` (or `make viewer`), then open one of the printed URLs.

No build is needed: the viewer scans the source theme folders registered in
`build_icons.py` (the submodules), so "Show in file manager" opens the SVG you
would actually edit. Symlinks are read as aliases: an icon is listed once under
its real file name (the name to write in `included_icons.txt`) together with
every symlink name that ends up pointing at it. The Blue* variants are produced
on the fly with the same colorizers the build uses.

The server listens on every interface so the page can also be opened from
another machine (e.g. server in a VM, browser on the desktop). The reveal
request is only honoured with the per-launch token embedded in the printed
URLs, and only for files inside a registered theme folder.
"""

from __future__ import annotations

import json
import mimetypes
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, NamedTuple, Optional, Tuple
from urllib.parse import unquote

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# build_icons.py parses CLI args at import time -> spoof argv first
# (same trick as tests/test_read_included_icons_txt.py).
sys.argv = [sys.argv[0], "--included-icon-file", str(_PROJECT_ROOT / "_dummy_not_used.txt")]
from build_icons import BUILT_IN_RAW_ICON_THEMES_PATH, key_for_sorting_size, parse_size_folder_name  # noqa: E402
from lib.color_converter import humanity_colorize_svg_content, nome_colorize_svg_content  # noqa: E402
from lib.included_icons_parser import is_icon_context_dir_type  # noqa: E402

_STATIC_DIR: Path = Path(__file__).resolve().parent / "static"
_INDEX_HTML: Path = _STATIC_DIR / "index.html"
TOKEN_HEADER: str = "X-Viewer-Token"

Colorizer = Callable[[str, str], str]
"""(svg text, icon name without extension) -> svg text"""


class SourceTheme(NamedTuple):
    folder: Path
    """Resolved source folder. A Blue* variant shares its base theme's folder."""
    colorize: Optional[Colorizer]
    """Set for the Blue* variants only."""
    group: str
    """Option-group label in the page's theme dropdown."""
    icon: str
    """Representative icon shown in the dropdown, relative to `folder`."""
    license: str
    about: str
    on_dark: bool
    """Icons drawn for dark panels: the page shows the representative icon on a dark chip."""


_FULL: str = "Full icon themes"
_FLOSS: str = "FLOSS application icons"
_HUMANITY_LICENSE: str = "GPL or Public Domain per icon, see COPYING"
_BLUE: str = "with hue shifted to blue by the build"

# Dropdown order. Columns: name, built-in base theme whose folder it reads, colorizer, group,
# representative icon (a folder where the theme has one, so its hue is visible at a glance; the
# Dark themes only have panel glyphs, shown on a dark chip), license (as in README "Built-in Icon
# Themes and Licenses"), blurb, on_dark.
_PANEL_GLYPH: str = "status/24/audio-volume-high-panel.svg"
_THEME_TABLE: List[Tuple[str, str, Optional[Colorizer], str, str, str, str, bool]] = [
    ("Tango",             "Tango",         None,                          _FULL,  "48x48/places/start-here.svg",          "GPL v2 or GPL v3",        "Freedesktop's reference Tango icon theme", False),
    ("Nome",              "Nome",          None,                          _FULL,  "places/48/folder.svg",                 "LGPL v3 or CC BY-SA 3.0", "GNOME 2/3 icon theme, forked", False),
    ("BlueNome",          "Nome",          nome_colorize_svg_content,     _FULL,  "places/48/folder.svg",                 "LGPL v3 or CC BY-SA 3.0", f"Nome {_BLUE}", False),
    ("Humanity",          "Humanity",      None,                          _FULL,  "places/48/folder.svg",                 _HUMANITY_LICENSE,         "Ubuntu's Humanity icon theme", False),
    ("BlueHumanity",      "Humanity",      humanity_colorize_svg_content, _FULL,  "places/48/folder.svg",                 _HUMANITY_LICENSE,         f"Humanity {_BLUE}", False),
    ("Humanity-Dark",     "Humanity-Dark", None,                          _FULL,  _PANEL_GLYPH,                           _HUMANITY_LICENSE,         "Humanity's light glyphs for dark panels", True),
    ("BlueHumanity-Dark", "Humanity-Dark", humanity_colorize_svg_content, _FULL,  _PANEL_GLYPH,                           _HUMANITY_LICENSE,         f"Humanity-Dark {_BLUE}", True),
    ("GimpLegacy",        "GimpLegacy",    None,                          _FLOSS, "actions/scalable/gimp-wilber.svg",     "GPL v3+",                 "GIMP's legacy colour icons", False),
    ("GimpDefault",       "GimpDefault",   None,                          _FLOSS, "actions/scalable/gimp-wilber-eek.svg", "CC BY-SA 3.0",            "GIMP's current default icons", False),
    ("InkscapeTango",     "InkscapeTango", None,                          _FLOSS, "actions/scalable/inkscape-logo.svg",   "GPL v2",                  "Inkscape's Tango-style icons, removed upstream in 2025", False),
]

# Representative icon per context for the page's context dropdown, as `<theme>/<path>` under
# /icons/, shown at 16 px. Nome where it has one; Nome has no animations or emotes.
_CONTEXT_ICONS: Dict[str, str] = {
    "actions":    "Nome/actions/16/document-save.svg",
    "animations": "Humanity/animations/48/brasero-disc-30.svg",
    "apps":       "Nome/apps/16/web-browser.svg",
    "categories": "Nome/categories/16/applications-system.svg",
    "devices":    "Nome/devices/16/media-floppy.svg",
    "emblems":    "Nome/emblems/16/emblem-default.svg",
    "emotes":     "Tango/16x16/emotes/face-cool.svg",
    "mimetypes":  "Nome/mimetypes/16/text-x-generic.svg",
    "places":     "Nome/places/16/folder.svg",
    "status":     "Nome/status/16/dialog-information.svg",
}


def source_themes() -> Dict[str, SourceTheme]:
    """Themes in dropdown order: the built-in ones from build_icons.py plus the
    Blue* variants that `run_02_colorize_themes` derives from them. Themes whose
    submodule is not checked out are skipped with a warning."""
    folders: Dict[str, Path] = {raw.copied_dst_theme_name: raw.copied_src_theme_folder for raw in BUILT_IN_RAW_ICON_THEMES_PATH}
    themes: Dict[str, SourceTheme] = {}
    for name, base, colorize, group, icon, lic, about, on_dark in _THEME_TABLE:
        if not folders[base].is_dir():
            print(f"[WARNING] {name}: {folders[base]} not found (submodule not checked out?), skipped", file=sys.stderr)
            continue
        themes[name] = SourceTheme(folders[base].resolve(), colorize, group, icon, lic, about, on_dark)
    return themes


def _context_and_size(rel: Path) -> Optional[Tuple[str, str]]:
    """(context, size) of an icon at `apps/16/x.svg` or `16x16/apps/x.svg` inside
    its theme folder; None for anything else, including scale-2 folders, which
    the build skips as well. Unknown context folders count as `apps` (as the build)."""
    if len(rel.parts) != 3:
        return None
    context, parsed = rel.parts[0], parse_size_folder_name(rel.parts[1])
    if parsed is None:
        context, parsed = rel.parts[1], parse_size_folder_name(rel.parts[0])
    if parsed is None or parsed.scale != "1":
        return None
    return (context if is_icon_context_dir_type(context) else "apps", parsed.size)


def scan_theme_folder(folder: Path) -> List[Dict[str, Any]]:
    """Real SVGs of one source theme grouped per (context, name), sizes ascending.
    Symlinks are not icons of their own: each one is followed (chains too) and
    its name recorded as an alias of the real file it ends at. Dangling symlinks
    and symlinked folders are ignored. One readlink per symlink and no resolve()
    keeps this fast on slow mounts (virtiofs, /mnt/c)."""
    files: Dict[str, Tuple[str, str]] = {}   # abs path -> (context, size)
    links: Dict[str, str] = {}               # abs symlink path -> abs target path, one hop
    pending: List[str] = [str(folder)]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    pending.append(entry.path)
                elif not entry.name.endswith(".svg"):
                    continue
                elif entry.is_symlink():
                    links[entry.path] = os.path.normpath(os.path.join(current, os.readlink(entry.path)))
                else:
                    place = _context_and_size(Path(entry.path).relative_to(folder))
                    if place:
                        files[entry.path] = place

    groups: Dict[Tuple[str, str], Dict[str, Any]] = {}   # (context, name) -> {"sizes": [(size, rel path)], "aliases": set}
    for path, (context, size) in files.items():
        group = groups.setdefault((context, Path(path).stem), {"sizes": [], "aliases": set()})
        group["sizes"].append((size, Path(path).relative_to(folder).as_posix()))
    for link, target in links.items():
        hops = 0
        while target in links and hops < 32:   # alias of an alias; the bound guards against loops
            target, hops = links[target], hops + 1
        # A same-named link in another size folder is neither a size (the build drops
        # symlinks) nor an alias; a dangling link is dropped.
        if target in files and Path(link).stem != Path(target).stem:
            groups[(files[target][0], Path(target).stem)]["aliases"].add(Path(link).stem)
    return [
        {"context": context, "name": name,
         "sizes": [{"size": size, "path": path}
                   for size, path in sorted(group["sizes"], key=key_for_sorting_size(lambda pair: pair[0]))],
         "aliases": sorted(group["aliases"])}
        for (context, name), group in sorted(groups.items())
    ]


def build_index(themes: Dict[str, SourceTheme]) -> List[Dict[str, Any]]:
    """Index entries for every theme, in the given order. A Blue* variant reuses
    its base theme's scan, since it lists the same files."""
    scanned: Dict[Path, List[Dict[str, Any]]] = {}
    index: List[Dict[str, Any]] = []
    for name, theme in themes.items():
        if theme.folder not in scanned:
            scanned[theme.folder] = scan_theme_folder(theme.folder)
        index.extend({"theme": name, **entry} for entry in scanned[theme.folder])
    return index


def _freedesktop_file_manager(method: str, uri: str) -> None:
    """Call org.freedesktop.FileManager1 (implemented by Nautilus, Dolphin,
    Thunar, Nemo, ...): `ShowItems` selects a file, `ShowFolders` opens a folder."""
    subprocess.run(
        ["dbus-send", "--session", "--print-reply", "--dest=org.freedesktop.FileManager1",
         "/org/freedesktop/FileManager1", f"org.freedesktop.FileManager1.{method}",
         f"array:string:{uri}", "string:"],
        check=True, capture_output=True)


def _open_with_inkscape(target: Path) -> None:
    """Launch Inkscape on `target` without waiting for it (it is a GUI app)."""
    exe = shutil.which("inkscape")
    if exe:
        subprocess.Popen([exe, str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    elif sys.platform == "darwin":
        subprocess.run(["open", "-a", "Inkscape", str(target)], check=True)
    else:
        raise RuntimeError("Inkscape is not on the PATH of the machine running the viewer.")


def open_on_host(target: Path, action: Literal["reveal", "dir", "inkscape"]) -> None:
    """`reveal`: show `target` selected in the file manager.
    `dir`: open the folder containing `target`.
    `inkscape`: open `target` in Inkscape.
    Runs on the machine hosting the server. Raises with a plain-language
    message when the needed program cannot be reached (e.g. a headless VM)."""
    if action == "inkscape":
        _open_with_inkscape(target)
    elif sys.platform == "win32":
        if action == "dir":
            os.startfile(str(target.parent))
        else:
            # One string on purpose: as a list, subprocess would quote the whole
            # `/select,C:\...` argument and explorer would not parse it.
            # explorer exits 1 even on success, hence no check=True.
            subprocess.run(f'explorer /select,"{target}"')
    elif sys.platform == "darwin":
        subprocess.run(["open", str(target.parent)] if action == "dir" else ["open", "-R", str(target)], check=True)
    else:
        try:
            if action == "dir":
                _freedesktop_file_manager("ShowFolders", target.parent.as_uri())
            else:
                _freedesktop_file_manager("ShowItems", target.as_uri())
        except (OSError, subprocess.CalledProcessError):   # no session bus / no file manager on it / no dbus-send
            try:
                subprocess.run(["xdg-open", str(target.parent)], check=True)
            except OSError:
                raise RuntimeError(
                    "No file manager is reachable on the machine running the viewer: the D-Bus "
                    "FileManager1 service is not available and xdg-open is not installed. If your "
                    "browser is on another machine, use \"Copy full path\" instead.") from None


class ViewerHandler(BaseHTTPRequestHandler):
    """GET  /                       -> the single-page UI
    GET  /static/<path>            -> page assets (vendored llselect) from viewer/static/
    GET  /api/index.json           -> icon index built at startup
    GET  /icons/<theme>/<path>.svg -> SVG from that theme's source folder, colorized for Blue* themes
    POST /api/open                 -> {"theme": ..., "path": ..., "action": "reveal" | "dir" | "inkscape"},
                                      requires the launch token in the X-Viewer-Token header."""

    def __init__(self, *args: Any, themes: Dict[str, SourceTheme], token: str, index_json: bytes, **kwargs: Any) -> None:
        self.themes: Dict[str, SourceTheme] = themes
        self.token: str = token
        self.index_json: bytes = index_json
        super().__init__(*args, **kwargs)

    def _icon_file(self, theme_name: str, rel: str) -> Optional[Path]:
        """The file `rel` names inside the theme's source folder (symlinks followed),
        or None when the theme is unknown or the path escapes the folder / is not a file."""
        theme = self.themes.get(theme_name)
        if theme is None:
            return None
        target: Path = (theme.folder / rel).resolve()
        return target if target.is_relative_to(theme.folder) and target.is_file() else None

    def do_GET(self) -> None:
        route: str = unquote(self.path.split("?", 1)[0])
        if route == "/":
            self._send(200, "text/html; charset=utf-8", _INDEX_HTML.read_bytes())
        elif route == "/api/index.json":
            self._send(200, "application/json", self.index_json)
        elif route.startswith("/static/"):
            asset: Path = (_STATIC_DIR / route[len("/static/"):]).resolve()
            if not (asset.is_relative_to(_STATIC_DIR) and asset.is_file()):
                self.send_error(404)
                return
            self._send(200, mimetypes.guess_type(asset.name)[0] or "application/octet-stream", asset.read_bytes())
        elif route.startswith("/icons/"):
            theme_name, _, rel = route[len("/icons/"):].partition("/")
            target = self._icon_file(theme_name, rel)
            if target is None:
                self.send_error(404)
                return
            data: bytes = target.read_bytes()
            colorize = self.themes[theme_name].colorize
            if colorize:
                data = colorize(data.decode("utf-8"), target.stem).encode("utf-8")
            self._send(200, "image/svg+xml", data)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/api/open":
            self.send_error(404)
            return
        if self.headers.get(TOKEN_HEADER) != self.token:
            self.send_error(403, "Bad or missing token")
            return
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        target = self._icon_file(body["theme"], body["path"])
        if target is None:
            self.send_error(400, "Path is not an indexed icon")
            return
        try:
            open_on_host(target, body["action"])
        except Exception as e:
            self._send(500, "text/plain; charset=utf-8", str(e).encode())
            return
        self._send(200, "text/plain; charset=utf-8", b"ok")

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # a page load requests thousands of icons; keep the terminal quiet


def make_server(themes: Dict[str, SourceTheme], token: str, index: List[Dict[str, Any]]) -> ThreadingHTTPServer:
    index_json: bytes = json.dumps({
        "themes": [{"name": name, "folder": str(t.folder), "group": t.group, "icon": t.icon,
                    "license": t.license, "about": t.about, "on_dark": t.on_dark}
                   for name, t in themes.items()],   # dropdown order
        "contexts": _CONTEXT_ICONS,
        "icons": index,
    }).encode()
    handler = partial(ViewerHandler, themes=themes, token=token, index_json=index_json)
    return ThreadingHTTPServer(("0.0.0.0", 0), handler)


def lan_ips() -> List[str]:
    """Addresses of the interfaces this machine would use towards each private
    range and the internet, without duplicates, so a box with e.g. a 192.168
    LAN and a 10.x VPN lists both. Nothing is sent: connect() on a UDP socket
    only picks the source address. Empty when offline."""
    found: List[str] = []
    for probe in ("10.255.255.255", "192.168.255.255", "172.31.255.255", "1.1.1.1"):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.connect((probe, 1))
            except OSError:
                continue
            ip: str = s.getsockname()[0]
            if ip not in found and ip != "127.0.0.1":
                found.append(ip)
    return found


def main() -> None:
    themes = source_themes()
    started = time.perf_counter()
    index = build_index(themes)
    print(f"Indexed {len(index)} icons across {len(themes)} themes in {time.perf_counter() - started:.1f}s", flush=True)
    token: str = secrets.token_urlsafe(16)
    server = make_server(themes, token, index)
    port: int = server.server_address[1]
    urls: List[str] = [f"http://{host}:{port}/?token={token}" for host in ["127.0.0.1"] + lan_ips()]
    print("Icon viewer listening on all interfaces (Ctrl-C to stop). Open one of:\n  " + "\n  ".join(urls), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
