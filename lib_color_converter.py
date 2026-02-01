import colorsys
from dataclasses import dataclass
from typing import List, Literal, Generic, TypeVar
import re

HumanityColorizeRule = Literal["orange_to_blue", "orange_to_dim_blue", "orange_to_green", "orange_to_dim_green", "orange_to_red", "red_to_blue", ]
NomeColorizeRule = Literal["brown_to_blue"]

T = TypeVar('T')

@dataclass
class IncludedFile(Generic[T]):
    name: str
    colorize_rules: List[T]

INCLUDED_HUMANITY_FILES: List[IncludedFile[HumanityColorizeRule]] = [
    # =================
    # places
    # =================
    IncludedFile(name="folder-documents", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-download", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-music", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-pictures", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-publicshare", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-remote", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-saved-search", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-system", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-video", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-home", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-templates", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-visiting", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="gnome-fs-web", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="gnome-fs-directory-accept", colorize_rules=["orange_to_dim_blue"]),   # folder
    IncludedFile(name="network-server", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="stock_smart-playlist", colorize_rules=["orange_to_blue"]),
    # IncludedFile(name="user-desktop", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="user-home", colorize_rules=["orange_to_dim_blue"]),   # folder
    IncludedFile(name="user-trash-full", colorize_rules=["orange_to_dim_green"]),
    IncludedFile(name="user-trash", colorize_rules=["orange_to_dim_green"]),
    IncludedFile(name="x-office-spreadsheet", colorize_rules=["orange_to_green"]),
    IncludedFile(name="x-office-document", colorize_rules=["orange_to_green"]),
    IncludedFile(name="ooo-template", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="ooo-impress", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="ooo-web", colorize_rules=["orange_to_blue"]),
    # =================
    # apps
    # =================
    IncludedFile(name="gconf-editor", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="gnome-control-centre", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="preferences-desktop-wallpaper", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="preferences-desktop-remote-desktop", colorize_rules=["red_to_blue"]),
    IncludedFile(name="session-properties", colorize_rules=["red_to_blue"]),
    IncludedFile(name="video-x-generic", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="system-file-manager", colorize_rules=["orange_to_blue"]),
    # IncludedFile(name="system-upgrade", colorize_rules=["orange_to_red"]),
    IncludedFile(name="gnome-panel-workspace-switcher", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="preferences-desktop-theme", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="gdm-setup", colorize_rules=["red_to_blue"]),
    # =================
    # actions
    # =================
    IncludedFile(name="document-open", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="folder-new", colorize_rules=["orange_to_dim_blue"]),
    IncludedFile(name="document-save-as", colorize_rules=["orange_to_green"]),
    IncludedFile(name="document-save", colorize_rules=["orange_to_green"]),
    IncludedFile(name="system-log-out", colorize_rules=["orange_to_red"]),
    IncludedFile(name="rotate", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="object-rotate-left", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="object-rotate-right", colorize_rules=["orange_to_blue"]),
    # IncludedFile(name="", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="go-up", colorize_rules=["orange_to_green"]),
    IncludedFile(name="go-down", colorize_rules=["orange_to_green"]),
    IncludedFile(name="go-previous", colorize_rules=["orange_to_green"]),
    IncludedFile(name="go-next", colorize_rules=["orange_to_green"]),
    IncludedFile(name="go-top", colorize_rules=["orange_to_green"]),
    IncludedFile(name="go-bottom", colorize_rules=["orange_to_green"]),
    IncludedFile(name="go-first", colorize_rules=["orange_to_green"]),
    IncludedFile(name="go-last", colorize_rules=["orange_to_green"]),
    # IncludedFile(name="", colorize_rules=["orange_to_green"]),
    # =================
    # categories
    # =================
    IncludedFile(name="applications-accessories", colorize_rules=[]),
    IncludedFile(name="applications-graphics", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="applications-internet", colorize_rules=["orange_to_blue"]),
    IncludedFile(name="preferences-desktop", colorize_rules=["orange_to_dim_green"]),
    IncludedFile(name="applications-multimedia", colorize_rules=["orange_to_blue"]),
    # IncludedFile(name="", colorize_rules=[]),
    # IncludedFile(name="", colorize_rules=[]),
    # IncludedFile(name="", colorize_rules=[]),
    # =================
    # devices
    # =================
    IncludedFile(name="computer", colorize_rules=["red_to_blue"]),
    # IncludedFile(name="", colorize_rules=[]),
]

INCLUDED_NOME_FILES: List[IncludedFile[NomeColorizeRule]] = [
    # =================
    # places
    # =================
    IncludedFile(name="folder", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-documents", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-download", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-drag-accept", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-music", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-new", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-open", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-pictures", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-publicshare", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-remote", colorize_rules=["brown_to_blue"]),
    # IncludedFile(name="folder-saved-search", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-templates", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-videos", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-videos", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="folder-visiting", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="user-bookmarks", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="user-desktop", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="user-home", colorize_rules=["brown_to_blue"]),
    IncludedFile(name="document-open", colorize_rules=["brown_to_blue"]),
]

def color_hex_to_hsl(hex_color: str) -> List[int]:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return [
        round(h * 360),
        round(s * 100),
        round(l * 100)
    ]

def color_hsl_to_hex(hsl_color: List[int]) -> str:
    h, s, l = hsl_color
    r, g, b = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

def humanity_colorize_hex_code_with_rule(hex_color: str, rules: List[HumanityColorizeRule]) -> str:
    h, s, l = color_hex_to_hsl(hex_color)
    for rule in rules:
        match rule:
            case "orange_to_blue":
                if 15 <= h <= 55:
                    h += 170
                    if s > 50:
                        s -= 20
                    if l > 50:
                        l += 10
                    else:
                        l -= 5
            case "orange_to_dim_blue":
                if 15 <= h <= 55:
                    h += 180
                    if s > 30:
                        s -= 30
                    if l > 50:
                        l += 5
                    else:
                        l -= 5
            case "orange_to_green":
                if 15 <= h <= 55:
                    h += 40
                    s -= 30
                    l -= 0
            case "orange_to_dim_green":
                if 15 <= h <= 55:
                    h += 40
                    s -= 50
                    l -= 10
            case "orange_to_red":
                if 15 <= h <= 55:
                    h -= 15
                    s -= 10
            case "red_to_blue":
                if 0 <= h <= 30:
                    h += 185
                    s -= 35
                    l += 20
    h = h % 360
    s = max(0, s)
    s = min(100, s)
    l = max(0, l)
    l = min(100, l)
    return color_hsl_to_hex([h, s, l])

def nome_colorize_hex_code_with_rule(hex_color: str, rules: List[NomeColorizeRule]) -> str:
    h, s, l = color_hex_to_hsl(hex_color)
    for rule in rules:
        match rule:
            case "brown_to_blue":
                if 15 <= h <= 50:
                    h += 170
                s = int(s * 1.2)

    h = h % 360
    s = max(0, s)
    s = min(100, s)
    l = max(0, l)
    l = min(100, l)
    return color_hsl_to_hex([h, s, l])

def humanity_colorize_svg_content(svg_file_content: str, svg_file_name_without_ext: str) -> str:
    included_file = next((x for x in INCLUDED_HUMANITY_FILES if x.name == svg_file_name_without_ext), None)
    if included_file is None:
        return svg_file_content
    pattern = r'#[A-Fa-f0-9]{3}(?:[A-Fa-f0-9]{3})?'
    return re.sub(pattern, lambda m: humanity_colorize_hex_code_with_rule(m.group(0), included_file.colorize_rules), svg_file_content)

def nome_colorize_svg_content(svg_file_content: str, svg_file_name_without_ext: str) -> str:
    included_file = next((x for x in INCLUDED_NOME_FILES if x.name == svg_file_name_without_ext), None)
    if included_file is None:
        return svg_file_content
    pattern = r'#[A-Fa-f0-9]{3}(?:[A-Fa-f0-9]{3})?'
    return re.sub(pattern, lambda m: nome_colorize_hex_code_with_rule(m.group(0), included_file.colorize_rules), svg_file_content)

