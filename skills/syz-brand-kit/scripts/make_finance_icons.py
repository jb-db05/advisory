"""Draw the Syz-style finance icons (assets/icons/finance/).

New icons, not part of the official guidelines library, drawn to match its style (Visual
Guidelines 5.1-5.3): filled shapes, round corners, the orange gradient left to right, details cut
out of the shape. Written in three colourways like assets/icons/syz/: gradient, flat (Tiger Orange)
and white.

    python scripts/make_finance_icons.py assets/icons/finance
"""
import sys
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "assets/icons/finance")


def circle(cx, cy, r):
    return f"M{cx - r},{cy} a{r},{r} 0 1,0 {2 * r},0 a{r},{r} 0 1,0 {-2 * r},0 Z"


def rrect(x, y, w, h, r):
    return (f"M{x + r},{y} H{x + w - r} a{r},{r} 0 0 1 {r},{r} V{y + h - r} a{r},{r} 0 0 1 {-r},{r} "
            f"H{x + r} a{r},{r} 0 0 1 {-r},{-r} V{y + r} a{r},{r} 0 0 1 {r},{-r} Z")


def fill(d):          # a filled shape; holes by even-odd
    return f'<path fill-rule="evenodd" d="{d}"/>'


def line(d, w=6):     # a thick line with round ends, drawn in the icon colour
    return (f'<path d="{d}" fill="none" stroke="{{C}}" stroke-width="{w}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def rounded(d, w=4):  # a filled shape whose corners are rounded by a same-colour outline
    return (f'<path d="{d}" stroke="{{C}}" stroke-width="{w}" stroke-linejoin="round"/>')


ICONS = {
    "coins": [
        fill(rrect(4, 38, 24, 8, 4)), fill(rrect(4, 28, 24, 8, 4)), fill(rrect(4, 18, 24, 8, 4)),
        fill(circle(44, 32, 14) + " " + circle(44, 32, 10.5) + " " + circle(44, 32, 8)),
    ],
    "wallet": [
        fill(rrect(14, 8, 32, 14, 4)),
        fill(rrect(6, 18, 52, 38, 9) + " " + rrect(36, 30, 16, 14, 5)),
        fill(circle(44, 37, 2.6)),
    ],
    "piggy-bank": [
        fill("M32,20 C46,20 54,27 54,36 C54,44 48,50 40,51 V56 a2,2 0 0 1 -2,2 H34 a2,2 0 0 1 -2,-2 V52 "
             "H26 V56 a2,2 0 0 1 -2,2 H20 a2,2 0 0 1 -2,-2 V50 C12,47 9,42 9,36 C9,27 18,20 32,20 Z "
             + rrect(26, 25, 12, 3.5, 1.75) + " " + circle(45, 33, 2.2)),
        rounded("M20,24 L24,13 L32,21 Z", 3),
        fill(rrect(52, 31, 8, 9, 3)),
    ],
    "chart-up": [
        line("M8,46 L24,30 L34,38 L52,18"),
        rounded("M42,13 L56,11 L54,25 Z", 3),
        fill(rrect(6, 53, 52, 4, 2)),
    ],
    "chart-down": [
        line("M8,14 L24,30 L34,22 L52,42"),
        rounded("M42,47 L56,49 L54,35 Z", 3),
        fill(rrect(6, 53, 52, 4, 2)),
    ],
    "pie-chart": [
        fill("M29,10 A24,24 0 1,0 53,34 H29 Z"),
        fill("M35,5 A24,24 0 0,1 59,29 H35 Z"),
    ],
    "candlestick": [
        fill(rrect(13.5, 14, 3, 40, 1.5)), fill(rrect(9, 22, 12, 22, 3)),
        fill(rrect(30.5, 6, 3, 38, 1.5)), fill(rrect(26, 13, 12, 21, 3)),
        fill(rrect(47.5, 20, 3, 38, 1.5)), fill(rrect(43, 29, 12, 19, 3)),
    ],
    "shield": [
        f'<path fill-rule="evenodd" stroke="{{C}}" stroke-width="3" stroke-linejoin="round" '
        f'd="M32,6 L53,14 V30 C53,44 44,53 32,58 C20,53 11,44 11,30 V14 Z '
        f'M21.5,31 L28,37.5 L42,23.5 L46,27.5 L28,45.5 L17.5,35 Z"/>',
    ],
    "umbrella": [
        fill("M8,33 C8,18 19,9 32,9 C45,9 56,18 56,33 C52,29 48,29 44,33 C40,29 36,29 32,33 "
             "C28,29 24,29 20,33 C16,29 12,29 8,33 Z"),
        fill(rrect(30.5, 4, 3, 7, 1.5)),
        line("M32,32 V50 C32,57 23,57 23,50", 5),
    ],
    "percent": [
        fill(circle(19, 19, 9) + " " + circle(19, 19, 4)),
        fill(circle(45, 45, 9) + " " + circle(45, 45, 4)),
        line("M47,13 L17,51", 7),
    ],
    "briefcase": [
        line("M24,21 V16 a4,4 0 0 1 4,-4 H36 a4,4 0 0 1 4,4 V21", 5),
        fill(rrect(6, 20, 52, 34, 7) + " " + rrect(27, 31, 10, 9, 2.5)),
    ],
    "safe": [
        fill(rrect(8, 6, 48, 46, 8) + " " + circle(32, 29, 12) + " " + circle(32, 29, 7.5)
             + " " + circle(32, 29, 3)),
        fill(rrect(14, 51, 7, 7, 2.5)), fill(rrect(43, 51, 7, 7, 2.5)),
    ],
    "globe": [
        line(circle(32, 32, 23), 5),
        f'<ellipse cx="32" cy="32" rx="10" ry="23" fill="none" stroke="{{C}}" stroke-width="5"/>',
        line("M10,32 H54", 5), line("M14,20 H50", 4), line("M14,44 H50", 4),
    ],
    "balance-scale": [
        fill(circle(32, 9, 4)),
        fill(rrect(30, 10, 4, 42, 2)), fill(rrect(18, 51, 28, 6, 3)),
        fill(rrect(9, 14, 46, 4, 2)),
        line("M16,17 L8,36 M16,17 L24,36 M48,17 L40,36 M48,17 L56,36", 2.5),
        fill("M5,36 H27 A11,11 0 0 1 5,36 Z"), fill("M37,36 H59 A11,11 0 0 1 37,36 Z"),
    ],
    "target": [
        fill(circle(30, 34, 24) + " " + circle(30, 34, 18) + " " + circle(30, 34, 12) + " "
             + circle(30, 34, 6)),
        line("M30,34 L52,12", 4),
        rounded("M47,9 L57,7 L55,17 Z", 3),
    ],
    "calendar": [
        fill(rrect(18, 5, 4, 12, 2)), fill(rrect(42, 5, 4, 12, 2)),
        fill(rrect(7, 11, 50, 46, 8) + " " + rrect(14, 28, 9, 8, 2) + " " + rrect(27.5, 28, 9, 8, 2)
             + " " + rrect(41, 28, 9, 8, 2) + " " + rrect(14, 41, 9, 8, 2) + " "
             + rrect(27.5, 41, 9, 8, 2)),
    ],
    "document": [
        fill("M18,6 H36 L52,22 V52 a6,6 0 0 1 -6,6 H18 a6,6 0 0 1 -6,-6 V12 a6,6 0 0 1 6,-6 Z "
             + rrect(19, 29, 26, 4, 2) + " " + rrect(19, 38, 26, 4, 2) + " " + rrect(19, 47, 16, 4, 2)),
        fill("M39,6 L52,19 H43 a4,4 0 0 1 -4,-4 Z"),
    ],
    "exchange": [
        line("M11,22 H49"), line("M41,13 L51,22 L41,31"),
        line("M53,42 H15"), line("M23,33 L13,42 L23,51"),
    ],
    "gold-bars": [
        rounded("M24,18 H40 L44,30 H20 Z", 3),
        rounded("M9,35 H27 L31,47 H5 Z", 3),
        rounded("M37,35 H55 L59,47 H33 Z", 3),
    ],
    "credit-card": [
        fill(rrect(6, 14, 52, 36, 7) + " M6,21 H58 V27 H6 Z " + rrect(13, 34, 12, 9, 2) + " "
             + rrect(39, 39, 12, 4, 2)),
    ],
    "euro": [
        line("M46,19 A16,16 0 1,0 46,45", 6),
        line("M11,28 H34", 5), line("M11,36 H34", 5),
    ],
    "growth": [
        line("M32,52 V30", 5),
        fill("M32,35 C19,35 11,27 11,15 C24,15 32,23 32,35 Z"),
        fill("M32,29 C32,17 40,9 54,9 C54,21 46,29 32,29 Z"),
        fill(rrect(16, 51, 32, 7, 3.5)),
    ],
    "analysis": [
        fill(rrect(8, 38, 8, 18, 2.5)), fill(rrect(20, 30, 8, 26, 2.5)), fill(rrect(32, 42, 8, 14, 2.5)),
        line(circle(41, 21, 11), 5), line("M49,29 L57,37", 6),
    ],
    "banknote": [
        fill(rrect(5, 15, 54, 34, 6) + " " + circle(32, 32, 9) + " " + circle(32, 32, 5) + " "
             + circle(14, 23, 2.5) + " " + circle(50, 41, 2.5)),
    ],
}

GRAD = ('<defs><linearGradient id="g" gradientUnits="userSpaceOnUse" x1="4" y1="0" x2="60" y2="0">'
        '<stop offset="0" stop-color="#FF6C0E"/><stop offset=".5" stop-color="#FFA400"/>'
        '<stop offset="1" stop-color="#FFC545"/></linearGradient></defs>')
KINDS = {"gradient": ("url(#g)", GRAD), "flat": ("#FF6C0E", ""), "white": ("#FFFFFF", "")}

for kind, (colour, defs) in KINDS.items():
    (OUT / kind).mkdir(parents=True, exist_ok=True)
    for i, (name, parts) in enumerate(ICONS.items(), 1):
        body = "".join(parts).replace("{C}", colour)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{defs}'
               f'<g fill="{colour}">{body}</g></svg>\n')
        (OUT / kind / f"F{i:02d}-{name}.svg").write_text(svg)
print(f"{len(ICONS)} icons x {len(KINDS)} colourways -> {OUT}")
