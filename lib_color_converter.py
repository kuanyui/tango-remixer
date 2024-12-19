import colorsys
from typing import List
import re

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

def color_tango_colorizer(hex_color: str) -> str:
    h, s, l = color_hex_to_hsl(hex_color)
    if 15 <= h <= 55:
        h += 170
        h = h % 360
        if s > 50:
            s -= 10
    return color_hsl_to_hex([h, s, l])

def tango_colorize_svg_content(svg_file_content: str) -> str:
    pattern = r'#[A-Fa-f0-9]{3}(?:[A-Fa-f0-9]{3})?'
    return re.sub(pattern, lambda m: color_tango_colorizer(m.group(0)), svg_file_content)
