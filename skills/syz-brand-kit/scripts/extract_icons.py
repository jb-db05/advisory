"""Extract the 40 Syz icons (Visual Guidelines p.24) from the page SVG into one SVG per icon.

Each icon is drawn in the PDF as clip paths filled with a gradient. We keep the precise clip
shapes, group them by position into the 10 x 4 grid, and write each icon twice: with the Syz
orange gradient (Tiger Orange -> Mango Amber -> Gold Yellow) and in flat Tiger Orange.

    pdftocairo -svg -f 24 -l 24 assets/source/SyzVisualGuidelines_WIP_V2_2.pdf /tmp/page24.svg
    python scripts/extract_icons.py /tmp/page24.svg assets/icons/syz

Then make the white set from flat/ (fill #FF6C0E -> #FFFFFF).
"""
import re, sys, collections
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
s = src.read_text()
NUM = re.compile(r'-?\d+\.?\d*(?:e-?\d+)?')

shapes = []   # (cx, cy, x0, y0, x1, y1, d, rule)
for cid, body in re.findall(r'<clipPath id="([^"]+)"[^>]*>(.*?)</clipPath>', s, re.S):
    for attrs in re.findall(r'<path([^>]*)/?>', body):
        d = re.search(r' d="([^"]+)"', attrs).group(1)
        rule = (re.search(r'clip-rule="([^"]+)"', attrs) or [None, "nonzero"])[1]
        v = [float(x) for x in NUM.findall(d)]
        xs, ys = v[0::2], v[1::2]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        # icon grid area only; skip the plain bounding rectangles (integer corners, 4 points)
        if not (600 < x0 and x1 < 1760 and 400 < y0 and y1 < 900 and x1 - x0 < 120):
            continue
        if len(v) <= 10 and all(abs(c - round(c)) < 1e-6 for c in v):
            continue
        shapes.append(((x0 + x1) / 2, (y0 + y1) / 2, x0, y0, x1, y1, d, rule))

def clusters(vals, n):
    vals = sorted(vals)
    gaps = sorted(range(1, len(vals)), key=lambda i: vals[i] - vals[i - 1], reverse=True)[: n - 1]
    cuts = sorted(vals[i] for i in gaps)
    return lambda v: sum(v >= c for c in cuts)

col = clusters([sh[0] for sh in shapes], 10)
row = clusters([sh[1] for sh in shapes], 4)
icons = collections.defaultdict(list)
for sh in shapes:
    icons[(row(sh[1]), col(sh[0]))].append(sh)

NAMES = [
    "cloud", "play", "presentation", "home", "bank", "folder", "archive", "stack", "bookmark", "crown",
    "lock", "clock", "key", "microphone", "phone", "location", "bell", "send", "speaker", "calculator",
    "dollar", "strategy", "chess-queen", "megaphone", "ship", "drop", "hourglass", "truck", "bag", "moon",
    "lightning", "headphones", "brain", "apple", "star", "bar-chart", "paperclip", "contrast", "image", "sun",
]
GRAD = ('<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#FF6C0E"/><stop offset=".5" stop-color="#FFA400"/>'
        '<stop offset="1" stop-color="#FFC545"/></linearGradient></defs>')
(out / "gradient").mkdir(parents=True, exist_ok=True)
(out / "flat").mkdir(parents=True, exist_ok=True)
for (r, c), parts in sorted(icons.items()):
    name = f"{r * 10 + c + 1:02d}-{NAMES[r * 10 + c]}"
    x0 = min(p[2] for p in parts); y0 = min(p[3] for p in parts)
    x1 = max(p[4] for p in parts); y1 = max(p[5] for p in parts)
    pad = 1
    vb = f"{x0 - pad:.2f} {y0 - pad:.2f} {x1 - x0 + 2 * pad:.2f} {y1 - y0 + 2 * pad:.2f}"
    paths = "".join(f'<path fill-rule="{p[7]}" d="{p[6]}"/>' for p in parts)
    for kind, fill, defs in (("gradient", "url(#g)", GRAD), ("flat", "#FF6C0E", "")):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">{defs}'
               f'<g fill="{fill}">{paths}</g></svg>\n')
        (out / kind / f"{name}.svg").write_text(svg)
print(f"{len(shapes)} shapes -> {len(icons)} icons; rows/cols:",
      sorted(collections.Counter(k[0] for k in icons).items()))
