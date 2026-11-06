"""Find Syz icons and logos, and render them as PNG where SVG cannot be used.

    python scripts/icons.py list [--set syz|finance] [--search WORD]
    python scripts/icons.py path NAME [--way gradient|flat|white]
    python scripts/icons.py png NAME --out icon.png [--way gradient|flat|white] [--colour HEX] [--size 512]
    python scripts/icons.py logo --out logo.png [--variant private-banking|signature]
                                 [--way gradient|mango|black|white] [--width 1200]

NAME is the icon's name without number or extension ("home", "piggy-bank"), searched in both
sets. --colour recolours the flat icon with any palette colour (e.g. 4B5F80 for Blueberry Blue).
PNG output needs cairosvg (pip install cairosvg). SVG files can be used directly in HTML,
WeasyPrint PDFs and PowerPoint (Insert > Pictures); python-pptx needs the PNG.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
ICONS = KIT / "assets" / "icons"
LOGOS = KIT / "assets" / "logo"
PALETTE = {
    "tiger-orange": "FF6C0E", "mango-amber": "FFA400", "gold-yellow": "FFC545",
    "blueberry-blue": "4B5F80", "space-blue": "202945", "mint-green": "3BAF90",
    "teal-green": "9DD9D2", "sky-blue": "79D6FF", "peach-pink": "E6A4AD", "mulberry-pink": "AC5D85",
}


def all_icons(way: str = "gradient", which: str | None = None):
    sets = [which] if which else ["syz", "finance"]
    for s in sets:
        for f in sorted((ICONS / s / way).glob("*.svg")):
            yield s, re.sub(r"^F?\d+-", "", f.stem), f


def find(name: str, way: str) -> Path:
    hits = [f for _, n, f in all_icons(way) if n == name.lower()]
    if not hits:
        close = [n for _, n, _ in all_icons(way) if name.lower() in n]
        sys.exit(f"no icon '{name}'" + (f"; did you mean: {', '.join(close)}" if close else ""))
    return hits[0]


def to_png(svg_text: str, out: Path, width: int, height: int | None = None):
    try:
        import cairosvg
    except ImportError:
        sys.exit("PNG output needs cairosvg: pip install cairosvg")
    cairosvg.svg2png(bytestring=svg_text.encode(), write_to=str(out), output_width=width,
                     output_height=height)
    print(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list"); l.add_argument("--set", choices=["syz", "finance"]); l.add_argument("--search")
    p = sub.add_parser("path"); p.add_argument("name"); p.add_argument("--way", default="gradient",
                                                                       choices=["gradient", "flat", "white"])
    g = sub.add_parser("png"); g.add_argument("name"); g.add_argument("--out", required=True, type=Path)
    g.add_argument("--way", default="gradient", choices=["gradient", "flat", "white"])
    g.add_argument("--colour", help="hex or palette name, recolours the flat icon")
    g.add_argument("--size", type=int, default=512)
    o = sub.add_parser("logo"); o.add_argument("--out", required=True, type=Path)
    o.add_argument("--variant", default="private-banking", choices=["private-banking", "signature"])
    o.add_argument("--way", default="gradient", choices=["gradient", "mango", "black", "white"])
    o.add_argument("--width", type=int, default=1200)
    a = ap.parse_args()

    if a.cmd == "list":
        for s, n, f in all_icons("gradient", a.set):
            if not a.search or a.search.lower() in n:
                print(f"{s:8} {n:16} {f.relative_to(KIT)}")
    elif a.cmd == "path":
        print(find(a.name, a.way))
    elif a.cmd == "png":
        if a.colour:
            hexv = PALETTE.get(a.colour.lower(), a.colour).lstrip("#").upper()
            svg = find(a.name, "flat").read_text().replace("#FF6C0E", f"#{hexv}")
        else:
            svg = find(a.name, a.way).read_text()
        to_png(svg, a.out, a.size, a.size)
    elif a.cmd == "logo":
        suffix = "" if a.way == "gradient" else f"-{a.way}"
        to_png((LOGOS / f"syz-{a.variant}{suffix}.svg").read_text(), a.out, a.width)


if __name__ == "__main__":
    main()
