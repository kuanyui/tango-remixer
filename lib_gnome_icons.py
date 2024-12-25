import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List, Optional, cast
from pathlib import Path
import os

def crop_svg(svg_file: str, output_dir: Path | str) -> None:
    svg_file_path = Path(svg_file)
    dom = minidom.parse(svg_file)
    icon_name = svg_file_path.stem
    baseplates: List[minidom.Element] = []
    for g in dom.getElementsByTagName("g"):
        if g.getAttribute("inkscape:label") == "baseplate":
            baseplates.append(g)

    for baseplate in baseplates:
        baseplate_parent = cast(minidom.Element, baseplate.parentNode)
        if baseplate_parent.nodeName == 'g' and baseplate_parent.getAttribute('inkscape:label') != '':
            icon_name = baseplate_parent.getAttribute('inkscape:label')
        rects = baseplate.getElementsByTagName('rect')
        for rect in rects:
            size_label = rect.getAttribute('inkscape:label')
            if size_label not in ['16x16', '22x22', '24x24', '32x32', '48x48']:
                continue
            x = float(rect.getAttribute("x"))
            y = float(rect.getAttribute("y"))
            width = float(rect.getAttribute("width"))
            height = float(rect.getAttribute("height"))
            print(f"{icon_name} {size_label} ==> {x}, {y}, {width}, {height}")
            create_svg_file(x, y, width, height, dom, output_dir, icon_name)

def create_svg_file(x: float, y: float, width: float, height: float, ori_dom: minidom.Document, output_dir: str | Path, icon_name: str):
    new_dom = cast(minidom.Document, ori_dom.cloneNode(True))
    svg_element = new_dom.getElementsByTagName("svg")[0]
    svg_element.setAttribute("viewBox", f"{x} {y} {width} {height}")
    svg_element.setAttribute("width", str(width))
    svg_element.setAttribute("height", str(height))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{icon_name}_{width}.svg"

    with output_file.open("w", encoding="utf-8") as f:
        svg_str = new_dom.toxml()
        if svg_str.startswith('<?xml'):
            svg_str = svg_str[svg_str.find('?>') + 2:]
        f.write(svg_str)


# Usage example
# crop_svg('thirdparty/gnome-icon-theme-3.9.5/src/clocks.svg', 'dist/gnome_output')
# crop_svg('thirdparty/gnome-icon-theme-3.9.5/src/displays.svg', 'dist/gnome_output')
crop_svg('thirdparty/gnome-icon-theme-3.9.5/src/accessories-calculator.svg', 'dist/gnome_output')