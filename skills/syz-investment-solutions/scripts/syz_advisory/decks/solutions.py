"""Investment Solutions decks (O02): a storyline written as JSON, drawn in the SYZ slide format.

The format is the advisory team's weekly "Investment Solutions" deck: the template's cover
with a photograph, content pages with a short gradient title and an italic orange section
label, white pages (no grey boxes), orange rules and outlines, native charts, a source line
at the foot, then the Important Information and the orange closing page.

A slide is a title, an optional section label (`subtitle`), an optional big `statement`, and
blocks arranged as `top` (full width), `columns` (side by side) and `bottom` (full width), or
simply `blocks` (one column). Each block is one of:

    text     bullet points ("→"), "- " for a sub-point, **bold**, __orange bold__
    card     outlined card with an icon, a heading and points
    cards    cards side by side
    kpis     big figures with a label and a note ("rule", "box" or "strip" style)
    table    header + rows, orange rules; optional red/green numbers
    terms    two-column term sheet; highlighted terms in orange
    chart    line / column / bar / pie / doughnut / dates / price (market data)
    image    a PNG or JPEG (a chart screenshot) fitted to the box
    levels   key levels box (resistance / support)
    steps    numbered process (1 → 5)
    flags    label + text rows (risks, "things to say")
    callout  one outlined line ("Key point: ...")

Every figure comes from the spec (taken from the sources) or from market data for `price`
charts. `build()` returns warnings: slides with figures but no source, long titles, dense text.
The spec format is in .claude/skills/syz-investment-solutions/references/spec-format.md.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from syz_advisory.decks import charts as C
from syz_advisory.decks.ooxml import (AMBER, BLUEBERRY, BODY_B, BODY_L, BODY_R, BODY_W, FONT, GREY, INK, MINT, ORANGE,
                                      PALETTE, RULE, T_GREEN, T_RED, T_RULE, TITLE_FONT, TITLE_MAX, Deck, Run, Slide, emu,
                                      fit_size, text_height, title_run)

TOP = 2.45                     # body top under the section label
GAP = 0.35                     # between columns and blocks
LIGHT_RULE = "E3E5EB"
SERIES_COLORS = [ORANGE, BLUEBERRY, AMBER, MINT, "AC5D85", INK, "79D6FF"]
ICONS = {"check": ("✓", MINT), "cross": ("✕", ORANGE), "question": ("?", ORANGE), "warning": ("!", ORANGE),
         "money": ("$", MINT), "shield": ("◆", MINT), "arrow": ("→", ORANGE)}


@dataclass
class Build:
    deck: Deck
    base: Path
    market: object = None
    as_of: date | None = None
    warnings: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def warn(self, page: int, what: str) -> None:
        self.warnings.append(f"slide {page}: {what}")


# ------------------------------------------------------------------ rich text
def runs(text: str, size: float, color: str = INK, bold: bool = False, italic: bool = False,
         font: str = FONT) -> list[Run]:
    """**bold** keeps the colour, __text__ is orange bold (the decks' emphasis)."""
    out = []
    for part in re.split(r"(\*\*.+?\*\*|__.+?__)", str(text)):
        if not part:
            continue
        if part.startswith("**"):
            out.append(Run(part[2:-2], size, True, color, italic, font))
        elif part.startswith("__"):
            out.append(Run(part[2:-2], size, True, ORANGE, italic, font))
        else:
            out.append(Run(part, size, bold, color, italic, font))
    return out


def plain(text: str) -> str:
    return re.sub(r"\*\*|__", "", str(text))


def paragraph(rs: list[Run], *, bullet: str | None = None, bullet_color: str = ORANGE, level: int = 0,
              align: str = "l", space_after: float = 4, space_before: float = 0) -> str:
    size = rs[0].size if rs else 11
    if bullet:
        mar = 228600 + level * 228600
        ind = ' marL="%d" indent="-228600"' % mar
        bu = (f'<a:buClr><a:srgbClr val="{bullet_color}"/></a:buClr><a:buSzPct val="100000"/>'
              f'<a:buFont typeface="Arial"/><a:buChar char="{escape(bullet)}"/>')
    else:
        ind, bu = ' marL="0" indent="0"', "<a:buNone/>"
    return (f'<a:p><a:pPr algn="{align}"{ind}><a:lnSpc><a:spcPct val="105000"/></a:lnSpc>'
            f'<a:spcBef><a:spcPts val="{int(space_before * 100)}"/></a:spcBef><a:spcAft><a:spcPts val="{int(space_after * 100)}"/></a:spcAft>'
            f'{bu}</a:pPr>{"".join(r.xml() for r in rs)}<a:endParaRPr lang="en-GB" sz="{int(size * 100)}" dirty="0"/></a:p>')


def shape(s: Slide, x: float, y: float, w: float, h: float, paras: list[str] | None = None, *, geom: str = "rect",
          line: str | None = None, line_w: float = 1.0, fill: str | None = None, anchor: str = "t", inset: float = 0.0,
          name: str = "Text", adj: int | None = None) -> None:
    """A shape on white: outline only unless `fill` (kept for accents and number badges)."""
    sid = s._id()
    fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    line_xml = (f'<a:ln w="{int(line_w * 12700)}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
                if line else "<a:ln><a:noFill/></a:ln>")
    av = f'<a:avLst><a:gd name="adj" fmla="val {adj}"/></a:avLst>' if adj is not None else "<a:avLst/>"
    ins = emu(inset)
    body = "".join(paras or ['<a:p><a:endParaRPr lang="en-GB" dirty="0"/></a:p>'])
    s.shapes.append(
        f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name} {sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f'<a:prstGeom prst="{geom}">{av}</a:prstGeom>{fill_xml}{line_xml}</p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" lIns="{ins}" rIns="{ins}" tIns="{ins}" bIns="{ins}" anchor="{anchor}"><a:normAutofit/></a:bodyPr>'
        f'<a:lstStyle/>{body}</p:txBody></p:sp>')


def fit(items: list[str], w: float, h: float, start: float, floor: float = 9.0, bold: bool = False) -> float:
    return fit_size([plain(t) for t in items], w, h, start, floor, bold, inset=0.02)


def _items(block: dict) -> list[str]:
    items = block.get("items") or ([block["text"]] if block.get("text") else [])
    return [str(i) for i in items if str(i).strip()]


def text_paras(items: list[str], size: float, *, bullets: bool = True, color: str = INK) -> list[str]:
    out = []
    for it in items:
        if it.startswith("- "):
            out.append(paragraph(runs(it[2:], size - 0.5, color), bullet="•", bullet_color=INK, level=1,
                                 space_after=size * 0.35))
        elif it.startswith("> ") or not bullets:
            out.append(paragraph(runs(it.removeprefix("> "), size, color), space_after=size * 0.6))
        else:
            out.append(paragraph(runs(it, size, color), bullet="→", space_after=size * 0.55))
    return out


def _text_need(items: list[str], w: float, size: float) -> float:
    return text_height([plain(i) for i in items], w - 0.3, size, inset=0.02, spacing=1.3) + 0.05


# ------------------------------------------------------------------ blocks: height
def natural(block: dict, w: float) -> tuple[float, bool]:
    """(height in inches, flexible?). Flexible blocks share what is left."""
    if block.get("height"):
        return float(block["height"]), False
    t = block.get("type", "text")
    head = 0.42 if block.get("heading") else 0
    if t == "text":
        return head + _text_need(_items(block), w, block.get("size", 12)), False
    if t == "kpis":
        style = block.get("style", "rule")
        note = any(i.get("note") for i in block.get("items", []))
        return {"rule": 1.15, "box": 1.4, "strip": 0.7}[style] + (0.3 if note and style == "rule" else
                                                                  0.1 if note and style == "box" else 0) + head, False
    if t in ("table", "terms"):                          # rows keep their height; the table takes the room left
        n = len(block.get("rows", [])) + 1
        return head + n * block.get("row_h", 0.34) + 0.05, True
    if t == "card":
        items = _items(block)
        body = _text_need(items, w - 0.5, block.get("size", 11.5)) if items else 0
        return max(1.5, body + (0.55 if block.get("heading") else 0) + 0.3), False
    if t == "cards":
        return max((natural({**c, "type": "card"}, (w - 0.3 * (len(block.get("cards", [])) - 1)) /
                            max(1, len(block.get("cards", []))))[0] for c in block.get("cards", [])), default=1.6), False
    if t == "levels":
        return 0.75 + 0.85 * len(block.get("groups", [])), False
    if t == "steps":
        return 2.05 + head, False
    if t == "flags":
        width = w - 1.9
        return head + sum(max(0.45, text_height([plain(i.get("text", ""))], width, 10.5, inset=0.02) + 0.18)
                          for i in block.get("items", [])), True
    if t == "callout":
        return text_height([plain(block.get("label", "") + " " + block.get("text", ""))], w - 0.5, 12, inset=0.02) + 0.35, False
    return head + 1.5, True                              # chart, image


def stack(b: Build, s: Slide, blocks: list[dict], x: float, y: float, w: float, h: float, page: int,
          center: bool = False) -> None:
    """Blocks one under the other. Flexible blocks (charts, images, tables) share the room the
    others leave; with none, the group sits a little above the middle of the space (`center`)."""
    if not blocks:
        return
    sizes = [natural(bl, w) for bl in blocks]
    gaps = GAP * (len(blocks) - 1)
    fixed = sum(hh for hh, flex in sizes if not flex)
    flex_n = sum(1 for _, flex in sizes if flex)
    room = h - gaps - fixed
    if flex_n:
        share = max(room, 1.2 * flex_n) / flex_n
        heights = [share if flex else hh for hh, flex in sizes]
    else:
        heights = [hh for hh, _ in sizes]
    total = sum(heights) + gaps
    if total > h:                                         # squeeze: text and tables shrink to fit
        k = (h - gaps) / (total - gaps)
        heights = [hh * k for hh in heights]
    yy = y + ((h - total) * 0.35 if center and not flex_n and total < h else 0)
    for bl, hh in zip(blocks, heights):
        used = draw(b, s, bl, x, yy, w, hh, page)
        yy += (used if used else hh) + GAP              # a table reports the height it really took


# ------------------------------------------------------------------ blocks: drawing
def heading(s: Slide, x: float, y: float, w: float, text: str, size: float = 14, color: str = INK) -> float:
    shape(s, x, y, w, 0.38, [paragraph(runs(text, size, color, bold=True), space_after=0)], inset=0.02, name="Heading")
    return 0.42


def draw(b: Build, s: Slide, block: dict, x: float, y: float, w: float, h: float, page: int) -> float | None:
    """Draw one block in its box; returns the height used when it is less than the box (tables)."""
    t = block.get("type", "text")
    head = 0.0
    if block.get("heading") and t not in ("card", "levels"):
        head = heading(s, x, y, w, block["heading"], block.get("heading_size", 14),
                       ORANGE if block.get("heading_color") == "orange" else INK)
        y, h = y + head, h - head
    fn = {"text": _text, "card": _card, "cards": _cards, "kpis": _kpis, "table": _table, "terms": _terms,
          "chart": _chart, "image": _image, "levels": _levels, "steps": _steps, "flags": _flags,
          "callout": _callout}.get(t)
    if fn is None:
        b.warn(page, f"unknown block type {t!r}: skipped")
        return None
    used = fn(b, s, block, x, y, w, h, page)
    return head + used if isinstance(used, (int, float)) and used < h else None


def _text(b, s, block, x, y, w, h, page):
    items = _items(block)
    size = fit(items, w - 0.3, h * 0.9, block.get("size", 12), block.get("floor", 9.5))
    shape(s, x, y, w, h, text_paras(items, size, bullets=block.get("bullets", True)), inset=0.02)
    words = sum(len(plain(i).split()) for i in items)
    if words > block.get("max_words", 90):
        b.warn(page, f"{words} words in one text block: cut to the key points or split the slide")


def _card(b, s, block, x, y, w, h, page):
    tone = block.get("tone", "orange")
    border = {"orange": ORANGE, "amber": AMBER, "ink": INK, "light": RULE, "green": MINT}.get(tone, ORANGE)
    shape(s, x, y, w, h, geom="roundRect", line=border, line_w=1.0, adj=4000, name="Card")
    pad = 0.25
    yy = y + 0.2
    icon = ICONS.get(block.get("icon", ""))
    if block.get("heading"):
        rs = ([Run(icon[0] + "  ", 16, True, icon[1])] if icon else []) + runs(block["heading"], 15, ORANGE, bold=True)
        shape(s, x + pad, yy, w - 2 * pad, 0.42, [paragraph(rs, space_after=0)], inset=0.0, name="Heading")
        yy += 0.55
    items = _items(block)
    if items:
        size = fit(items, w - 2 * pad - 0.3, (y + h - yy - 0.15) * 0.92, block.get("size", 11.5), 9)
        shape(s, x + pad, yy, w - 2 * pad, y + h - yy - 0.15, text_paras(items, size, bullets=block.get("bullets", True)),
              inset=0.0)


def _cards(b, s, block, x, y, w, h, page):
    cards = block.get("cards", [])
    if not cards:
        return
    g = 0.3
    cw = (w - g * (len(cards) - 1)) / len(cards)
    for k, c in enumerate(cards):
        _card(b, s, {**c, "type": "card"}, x + k * (cw + g), y, cw, h, page)


def _kpis(b, s, block, x, y, w, h, page):
    items = block.get("items", [])
    if not items:
        return
    style = block.get("style", "rule")
    g = 0.3 if style != "strip" else 0.2
    iw = (w - g * (len(items) - 1)) / len(items)
    vals = [str(i.get("value", "")) for i in items]
    if style == "strip":
        vsize = min(fit([v], iw - 0.3, 0.45, 18, 11, True) for v in vals)
        for k, it in enumerate(items):
            xx = x + k * (iw + g)
            if k:
                s.shapes.append(_vline(s, xx - g / 2, y + 0.05, h - 0.1))
            shape(s, xx, y, iw, h, [paragraph([Run(vals[k], vsize, True, INK)], space_after=2),
                                    paragraph([Run(it.get("label", ""), 10, False, GREY)], space_after=0)],
                  inset=0.02, anchor="ctr", name="KPI")
        return
    color = AMBER if style == "box" else ORANGE
    # bold figures and % run wider than the average glyph the estimate assumes: keep a margin
    noted = any(i.get("note") for i in items)
    start = block.get("size", (24 if noted else 32) if style == "box" else 30)
    vsize = min(fit([v], (iw - 0.4) * 0.8, 0.75, start, 14, True) for v in vals)
    for k, it in enumerate(items):
        xx = x + k * (iw + g)
        paras = [paragraph([Run(vals[k], vsize, True, it.get("color") and {"ink": INK, "orange": ORANGE, "amber": AMBER,
                                                                           "red": T_RED, "green": T_GREEN}[it["color"]] or color)],
                           space_after=vsize * 0.25),
                 paragraph([Run(it.get("label", ""), 11, False, INK)], space_after=3)]
        if it.get("note"):
            paras.append(paragraph([Run(it["note"], 9 if style == "box" else 9.5, False, GREY)], space_after=0))
        if style == "box":
            shape(s, xx, y, iw, h, paras, geom="roundRect", line=ORANGE, line_w=1.0, adj=6000, inset=0.15, name="KPI")
        else:
            s.rule(xx, y, iw, LIGHT_RULE)
            shape(s, xx, y + 0.1, iw, h - 0.1, paras, inset=0.02, name="KPI")


def _vline(s: Slide, x: float, y: float, h: float) -> str:
    sid = s._id()
    return (f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{sid}" name="Rule {sid}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="0" cy="{emu(h)}"/></a:xfrm><a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
            f'<a:ln w="6350"><a:solidFill><a:srgbClr val="{RULE}"/></a:solidFill></a:ln></p:spPr></p:cxnSp>')


_NUM = re.compile(r"^[−-]?\d")


def _table(b, s, block, x, y, w, h, page):
    header = block.get("header")
    rows = [[str(c) for c in r] for r in block.get("rows", [])]
    if not rows:
        return
    if not header:                                        # the first row is the header
        header, rows = rows[0], rows[1:]
    table = [list(map(str, header))] + rows
    colors = {}
    hi = set(block.get("highlight_rows", []))
    hic = set(block.get("highlight_cols", []))
    for i, r in enumerate(rows, start=1):
        for j, c in enumerate(r):
            if ((i - 1) in hi and j > 0) or j in hic:
                colors[(i, j)] = ORANGE
            elif block.get("color_numbers") and j > 0 and _NUM.match(c.strip()):
                colors[(i, j)] = T_RED if c.strip()[0] in "-−" else T_GREEN
            elif block.get("color_negative") and j > 0 and c.strip()[:1] in "-−" and _NUM.match(c.strip()):
                colors[(i, j)] = T_RED
    n = len(table[0])
    align = block.get("align") or (["l"] + ["r"] * (n - 1) if block.get("numeric", False) else ["l"] * n)
    return s.table(x, y, w, table, size=block.get("size", 11.5), max_h=h, col_weights=block.get("widths"), align=align,
                   cell_colors=colors, bold_cols=(0,) if block.get("bold_first", True) else (), floor=block.get("floor", 7.0),
                   head_color=ORANGE, head_rule=ORANGE, last_rule=ORANGE, row_h=block.get("row_h", 0.34))


def _terms(b, s, block, x, y, w, h, page):
    rows = [list(r) for r in block.get("rows", [])]
    hi = {k.lower() for k in block.get("highlight", [])}
    return _table(b, s, {"header": block.get("header", ["Term", "Detail"]), "rows": rows, "widths": block.get("widths", [1, 2.4]),
                  "highlight_rows": [i for i, r in enumerate(rows) if str(r[0]).lower() in hi],
                  "size": block.get("size", 12), "row_h": block.get("row_h", 0.36)}, x, y, w, h, page)


def _levels(b, s, block, x, y, w, h, page):
    shape(s, x, y, w, h, geom="roundRect", line=ORANGE, line_w=1.0, adj=5000, name="Card")
    pad = 0.3
    shape(s, x + pad, y + 0.22, w - 2 * pad, 0.4, [paragraph(runs(block.get("heading", "KEY LEVELS"), 15, ORANGE, True),
                                                             space_after=0)], name="Heading")
    yy = y + 0.75
    for g in block.get("groups", []):
        vals = "     ".join(str(v) for v in g.get("values", []))
        shape(s, x + pad, yy, w - 2 * pad, 0.75, [paragraph(runs(g.get("label", ""), 14, INK, True), space_after=5),
                                                  paragraph([Run(vals, 13, False, INK)], space_after=0)], name="Levels")
        yy += 0.85


def _steps(b, s, block, x, y, w, h, page):
    items = block.get("items", [])
    if not items:
        return
    g = 0.25
    iw = (w - g * (len(items) - 1)) / len(items)
    hi = block.get("highlight")
    d = 0.36
    for k, it in enumerate(items):
        xx = x + k * (iw + g)
        if k < len(items) - 1:
            s.rule(xx + d + 0.08, y + d / 2, iw + g - d - 0.16, RULE)
        fill = ORANGE if hi is not None and k == hi else INK
        shape(s, xx, y, d, d, [paragraph([Run(str(k + 1), 12, True, "FFFFFF")], align="ctr", space_after=0)],
              geom="ellipse", fill=fill, anchor="ctr", name="Accent")
        paras = [paragraph(runs(it.get("title", ""), 13, INK, True), space_after=5),
                 paragraph(runs(it.get("text", ""), 11, INK), space_after=5)]
        if it.get("tag"):
            paras.append(paragraph(runs(it["tag"], 9.5, ORANGE, True), space_after=0))
        shape(s, xx, y + d + 0.15, iw, h - d - 0.15, paras, inset=0.0, name="Step")


def _flags(b, s, block, x, y, w, h, page):
    items = block.get("items", [])
    if not items:
        return
    lw = block.get("label_width", 1.6)
    need = [max(0.45, text_height([plain(i.get("text", ""))], w - lw - 0.2, 10.5, inset=0.02) + 0.18) for i in items]
    k = min(1.0, h / sum(need)) if sum(need) else 1
    size = 10.5 if k >= 0.98 else max(8.5, 10.5 * k)
    yy = y
    for it, hh in zip(items, need):
        hh *= k
        shape(s, x, yy, lw, hh, [paragraph(runs(it.get("label", ""), 12, ORANGE, True), space_after=0)], inset=0.04,
              name="Flag")
        shape(s, x + lw + 0.2, yy, w - lw - 0.2, hh, [paragraph(runs(it.get("text", ""), size, INK), space_after=0)],
              inset=0.04, name="Flag")
        yy += hh
        if it is not items[-1]:
            s.rule(x, yy, w, T_RULE)


def _callout(b, s, block, x, y, w, h, page):
    rs = (runs(block["label"] + "  ", 12, INK, True) if block.get("label") else []) + runs(block.get("text", ""), 12, INK)
    shape(s, x, y, w, h, [paragraph(rs, space_after=0)], geom="roundRect", line=AMBER, line_w=1.25, adj=12000,
          anchor="ctr", inset=0.22, name="Callout")


# ------------------------------------------------------------------ charts and images
def _fmt(block: dict, values: list) -> str:
    if block.get("fmt"):
        return block["fmt"]
    nums = [abs(v) for v in values if isinstance(v, (int, float))]
    if nums and max(nums) <= 1.5 and block.get("percent"):
        return "0%"
    return "#,##0" if nums and max(nums) >= 100 else "General"


def _chart(b, s, block, x, y, w, h, page):
    kind = block.get("chart", "line")
    colors = [{"orange": ORANGE, "blueberry": BLUEBERRY, "amber": AMBER, "mint": MINT, "ink": INK, "grey": GREY}.get(c, c)
              for c in block.get("colors", [])] or SERIES_COLORS
    if kind == "price":
        cats, series = _price_series(b, block, page)
        if not series:
            return
        xml, wb = C.lines_over_dates(cats, series, colors=colors, fmt=block.get("fmt", "0.00" if not block.get("rebase") else "0"))
    else:
        cats = [str(c) for c in block.get("categories", [])]
        series = {k: [None if v is None else float(v) for v in vals] for k, vals in (block.get("series") or {}).items()}
        if not series or not cats:
            b.warn(page, "chart without categories or series: skipped")
            return
        allv = [v for vals in series.values() for v in vals]
        fmt = _fmt(block, allv)
        if kind == "line":
            xml, wb = C.lines(cats, series, fmt=fmt, colors=colors, markers=block.get("markers", True),
                              y_title=block.get("y_title", ""), x_title=block.get("x_title", ""),
                              labels_on=block.get("labels", False))
        elif kind == "dates":
            xml, wb = C.lines_over_dates(cats, series, colors=colors, fmt=fmt)
        elif kind in ("column", "bar"):
            pc = None
            if block.get("highlight"):
                hl = block["highlight"]
                pc = [None] * len(cats)
                for i, c in (hl.items() if isinstance(hl, dict) else ((i, AMBER) for i in hl)):
                    pc[int(i)] = {"orange": ORANGE, "amber": AMBER, "mint": MINT}.get(c, c)
            xml, wb = C.bars(cats, series, horizontal=kind == "bar", fmt=fmt, colors=colors or [BLUEBERRY],
                             gridlines=kind == "column", point_colors=pc, labels_on=block.get("labels", True),
                             labels_bold=True)
        elif kind in ("pie", "doughnut"):
            name, vals = next(iter(series.items()))
            total = sum(v or 0 for v in vals) or 1
            shares = [round((v or 0) / total, 6) for v in vals]
            cw = min(h, w * 0.5)
            xml, wb = C.doughnut(cats, shares, colors[:len(cats)] if len(colors) >= len(cats) else None,
                                 hole=0 if kind == "pie" else 55)
            s.chart(x, y, cw, cw, xml, wb)
            pal = colors if len(colors) >= len(cats) else [PALETTE[i % len(PALETTE)] for i in range(len(cats))]
            leg = [paragraph([Run("■  ", 13, True, pal[i]), Run(c + "  ", 11.5, False, INK),
                              Run(block.get("value_labels", [None] * len(cats))[i] or f"{shares[i]:.0%}", 11.5, True, INK)],
                             space_after=7) for i, c in enumerate(cats)]
            shape(s, x + cw + 0.25, y, w - cw - 0.25, cw, leg, anchor="ctr", name="Legend")
            return
        else:
            b.warn(page, f"unknown chart type {kind!r}: skipped")
            return
    s.chart(x, y, w, h, xml, wb)


def _price_series(b: Build, block: dict, page: int) -> tuple[list[str], dict]:
    """Daily closes from market data (cut at the deck's as-of date), optionally rebased to 100."""
    if b.market is None:
        b.warn(page, "price chart: no market data available")
        return [], {}
    from syz_advisory.decks import analytics as A
    end = date.fromisoformat(block["end"]) if block.get("end") else (b.as_of or date.today())
    years = {"6m": 0.5, "1y": 1, "2y": 2, "3y": 3, "5y": 5}.get(block.get("period", "1y"), 1)
    start = date.fromisoformat(block["start"]) if block.get("start") else end - timedelta(days=int(365.25 * years))
    syms = block.get("symbols") or [block["symbol"]]
    names = block.get("names") or syms
    got = []
    for sym in syms:
        ser = b.market.prices(sym, start)
        keep = [i for i, d in enumerate(ser.dates) if d <= end.isoformat()]
        ser = type(ser)(ser.symbol, [ser.dates[i] for i in keep], [ser.closes[i] for i in keep], ser.source, ser.adjusted)
        if not ser.closes:
            b.warn(page, f"price chart: no prices for {sym}")
            continue
        got.append(ser)
    if not got:
        return [], {}
    dates, cols = A.align(got)
    series = {}
    for name, col in zip(names, cols):
        first = next((c for c in col if c), None)
        series[name] = ([round(c / first * 100, 3) if c and first else None for c in col] if block.get("rebase")
                        else [round(c, 5) if c else None for c in col])
    b.sources.append(f"{', '.join(syms)}: daily closes {dates[0]} to {dates[-1]}")
    return dates, series


def image_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) in pixels of a PNG or JPEG, read from its header."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                hgt, wid = struct.unpack(">HH", data[i + 5:i + 9])
                return wid, hgt
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None


def _load_image(b: Build, path: str, page: int) -> tuple[str, tuple[int, int]] | None:
    p = (b.base / path) if not Path(path).is_absolute() else Path(path)
    if not p.exists():
        b.warn(page, f"image not found: {path}")
        return None
    data = p.read_bytes()
    size = image_size(data)
    if not size:
        b.warn(page, f"{path}: only PNG and JPEG images are supported")
        return None
    return b.deck.add_media(data, "png" if data[:4] == b"\x89PNG" else "jpg"), size


def _image(b, s, block, x, y, w, h, page):
    got = _load_image(b, block.get("path", ""), page)
    if not got:
        return
    target, (pw, ph) = got
    cap = 0.3 if block.get("caption") else 0
    ratio = pw / ph
    iw, ih = (w, w / ratio) if w / ratio <= h - cap else ((h - cap) * ratio, h - cap)
    ix = x + (w - iw) / 2 if block.get("center", True) else x
    s.picture(ix, y, iw, ih, target, name="Image")
    if cap:
        shape(s, x, y + ih + 0.04, w, 0.28, [paragraph([Run(block["caption"], 9, False, GREY, italic=True)], space_after=0)],
              name="Caption")


# ------------------------------------------------------------------ slides
def _title(s: Slide, text: str) -> None:
    size = fit_size([text], BODY_W, 0.77, 30, 20, bold=True, inset=0.05)
    s.set_title(text, size)


def _section(s: Slide, text: str) -> None:
    run = (f'<a:r><a:rPr lang="en-GB" sz="2000" b="0" i="1" dirty="0"><a:solidFill><a:srgbClr val="{ORANGE}"/></a:solidFill>'
           f'<a:latin typeface="{FONT}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>')
    s.placeholder('<p:ph type="body" sz="quarter" idx="14"/>', [f"<a:p>{run}</a:p>"], "Subtitle")


def content_slide(b: Build, spec: dict, page: int) -> None:
    s = b.deck.add("One Content")
    title = spec.get("title") or "Untitled"
    _title(s, title)
    if len(title) > TITLE_MAX:
        b.warn(page, f"title is {len(title)} characters (keep it under {TITLE_MAX}): {title!r}")
    if spec.get("subtitle"):
        _section(s, spec["subtitle"])
    top = TOP if spec.get("subtitle") else 2.15
    bottom = BODY_B
    # foot: source line, then the note, then the takeaway above them
    foot = []
    if spec.get("source"):
        foot.append(("Source: " + spec["source"].removeprefix("Source: "), 8, GREY, False))
    if spec.get("note"):
        foot.append((spec["note"], 9, GREY, True))
    for text, size, color, italic in foot:
        hh = 0.26 if len(text) < 180 else 0.4
        shape(s, BODY_L, bottom - hh, BODY_W, hh, [paragraph([Run(text, size, False, color, italic)], space_after=0)],
              inset=0.0, anchor="b", name="Source")
        bottom -= hh + 0.02
    if spec.get("takeaway"):
        shape(s, BODY_L, bottom - 0.45, BODY_W, 0.42,
              [paragraph([Run("➢  ", 12, True, ORANGE)] + runs(spec["takeaway"], 12.5, INK, bold=True, italic=True),
                         space_after=0)], inset=0.0, anchor="ctr", name="Takeaway")
        bottom -= 0.6
    else:
        bottom -= 0.1
    y = top
    if spec.get("statement"):
        shape(s, BODY_L, y, BODY_W, 0.75, [paragraph(runs(spec["statement"], 28, ORANGE, bold=True), align="ctr",
                                                     space_after=0)], anchor="ctr", name="Statement")
        y += 0.95
        if spec.get("lead"):
            shape(s, BODY_L, y, BODY_W, 0.45, [paragraph(runs(spec["lead"], 16, INK, bold=True), align="ctr",
                                                         space_after=0)], anchor="ctr", name="Lead")
            y += 0.6
    top_blocks, bottom_blocks = spec.get("top", []), spec.get("bottom", [])
    cols = spec.get("columns")
    if spec.get("blocks") and not cols:
        cols = [{"blocks": spec["blocks"]}]
    th = sum(natural(bl, BODY_W)[0] for bl in top_blocks) + GAP * len(top_blocks)
    bh = sum(natural(bl, BODY_W)[0] for bl in bottom_blocks) + GAP * len(bottom_blocks)
    if cols:
        mid = bottom - y - th - bh
        if mid < 1.0:                                      # squeeze the full-width rows first
            k = max(0.3, (bottom - y - 1.0) / max(th + bh, 0.01))
            th, bh, mid = th * k, bh * k, 1.0
    else:
        th = th if bottom_blocks else bottom - y
        bh = bottom - y - th if bottom_blocks else 0
        mid = 0
    if top_blocks:
        stack(b, s, top_blocks, BODY_L, y, BODY_W, th - (GAP if cols or bottom_blocks else 0), page)
        y += th
    if cols:
        cols = [c if isinstance(c, dict) else {"blocks": c} for c in cols]
        widths = [c.get("width") for c in cols]
        if any(wd is None for wd in widths):
            widths = [1 / len(cols)] * len(cols)
        tot = sum(widths)
        avail = BODY_W - GAP * (len(cols) - 1)
        xx = BODY_L
        any_flex = any(natural(bl, 3.0)[1] for c in cols for bl in c["blocks"])
        for c, wd in zip(cols, widths):
            cw = avail * wd / tot
            stack(b, s, c["blocks"], xx, y, cw, mid, page, center=not any_flex)
            xx += cw + GAP
        y += mid + GAP
    if bottom_blocks:
        stack(b, s, bottom_blocks, BODY_L, y, BODY_W, bottom - y, page)
    # sources: figures need one
    text = json.dumps({k: v for k, v in spec.items() if k not in ("source", "note", "title")}, ensure_ascii=False)
    if re.search(r"\d", re.sub(r'"(path|height|width|widths|size|row_h|highlight|style|end|start|period)": [^,}\]]+', "", text)) \
            and not spec.get("source"):
        b.warn(page, "figures on the slide but no source: add 'source'")
    if spec.get("source"):
        b.sources.append(f"Slide {page}: {spec['source']}")


def cover(b: Build, spec: dict) -> None:
    s = b.deck.add("Cover Slide 2")
    lines = (spec.get("title") or "Investment Solutions\nby your Advisory Team").split("\n")
    size = fit_size(lines, 4.9, 1.35, 26, 18, bold=True, inset=0.1)
    paras = "".join(f"<a:p>{title_run(l, size)}</a:p>" for l in lines)
    sid = s._id()      # the layout's title box is 3.8 in wide: widened to the photo's edge, as in the reference decks
    s.shapes.append(
        f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="Title {sid}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f'<p:nvPr><p:ph type="ctrTitle"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x="{emu(0.73)}" y="{emu(5.8)}"/>'
        f'<a:ext cx="{emu(4.9)}" cy="{emu(1.5)}"/></a:xfrm></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/>{paras}</p:txBody></p:sp>')
    when = spec.get("date") or date.today().isoformat()
    try:
        d = date.fromisoformat(when)
        when = f"{d.day} {d:%B %Y}"
    except ValueError:
        pass
    s.placeholder('<p:ph type="body" sz="quarter" idx="13"/>',
                  [f"<a:p>{title_run(when)}</a:p>"], "Intro")
    got = _load_image(b, spec["cover_image"], 1) if spec.get("cover_image") else None
    if got:
        target, (pw, ph) = got
        box = 5.85 / 8.27
        r = pw / ph
        crop = (int((1 - box / r) / 2 * 100000), 0, int((1 - box / r) / 2 * 100000), 0) if r > box else \
            (0, int((1 - r / box) / 2 * 100000), 0, int((1 - r / box) / 2 * 100000))
        rid = s._rel("http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", target)
        sid = s._id()
        l, t, rr, bb = crop
        s.shapes.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name="Picture {sid}" descr=""/><p:cNvPicPr><a:picLocks noGrp="1" noChangeAspect="1"/></p:cNvPicPr>'
            f'<p:nvPr><p:ph type="pic" sz="quarter" idx="14"/></p:nvPr></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:srcRect l="{l}" t="{t}" r="{rr}" b="{bb}"/><a:stretch/></p:blipFill><p:spPr/></p:pic>')
    else:
        s.picture_placeholder(14, b.deck.cover_image)
    if spec.get("cover_caption"):
        shape(s, 6.1, 6.75, 5.35, 1.2, [paragraph(runs(l, 24, ORANGE, bold=True, font=TITLE_FONT), align="r", space_after=0)
                                        for l in spec["cover_caption"].split("\n")], anchor="b", name="Caption")
    s.title = lines[0]


def build(spec_path: Path, out: Path, market=None) -> tuple[Path, Build]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    b = Build(Deck(), spec_path.parent, market,
              date.fromisoformat(spec["date"]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(spec.get("date", ""))) else None)
    if b.market is not None and b.as_of:
        b.market.as_of = b.as_of
    cover(b, spec)
    for k, sl in enumerate(spec.get("slides", []), start=2):
        content_slide(b, sl, k)
    b.deck.add("Disclaimer (general)").title = "Important information"
    closing = {"offices": "1_Final page - with Offices", "orange": "Final page - Orange"}.get(spec.get("closing", "orange"))
    b.deck.add(closing).title = "Syz"
    b.deck.save(out)
    return out, b
