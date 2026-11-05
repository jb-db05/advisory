"""A small PresentationML writer on top of the SYZ template.

The template's own slides are dropped; its master, layouts, theme and media stay,
so every slide inherits the real logo, footer, page number and title styles.
Positions are in inches on the template's A4 landscape page.

Layout names used (see `apps/S00/S00_template.pptx`):
    "Cover Slide 2", "Agenda", "One Content", "Disclaimer (general)", "1_Final page - with Offices"
"""

from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from syz_advisory import config

# SYZ_TEMPLATE points at the template when the code runs outside the workspace (claude.ai skill).
TEMPLATE = Path(os.environ.get("SYZ_TEMPLATE") or config.ROOT / "apps" / "S00" / "S00_template.pptx")
EMU = 914400
PAGE_W, PAGE_H = 10691813 / EMU, 7559675 / EMU          # 11.69 x 8.27 in
FONT = "Nunito Sans"    # body text, everywhere
TITLE_FONT = "Nunito"   # slide titles and the whole cover page, always bold

# Template geometry (inches): content pages, measured off the slide master and layouts.
BODY_L, BODY_R = 0.73, 11.01
BODY_T, BODY_B = 2.55, 7.55        # the compliance footer starts at 7.76
BODY_W = BODY_R - BODY_L

# Theme colours (theme "SYZ"): dk2, accents 4/6/3/5/2/1, lt2.
INK = "202945"
ORANGE, BLUEBERRY, AMBER, MULBERRY, MINT, SKY, GOLD = "FF6C0E", "4B5F80", "FFA400", "AC5D85", "3BAF90", "79D6FF", "FFC545"
RUST = "C2500A"             # orange darkened to 4.5:1 on white, for orange text
GREY, LIGHT, RULE = "8C8C8C", "F3F4F7", "A6A9B5"
RED, GREEN = "C62828", "2E7D32"
# Tables (house reference: data/O01/in/Table ex.pptx): no fills, grey bold header over a navy
# rule, light rules between rows; status figures are coloured text, not coloured cells.
T_HEAD, T_RULE = "7A8494", "D9DCE1"
T_RED, T_AMBER, T_GREEN = "E45B5E", "FFA400", "3BAF90"
PALETTE = [ORANGE, BLUEBERRY, AMBER, MULBERRY, MINT, SKY, GOLD, INK]
TITLE_MAX = 30              # characters: titles are short labels; the message is the subtitle
# House rule: titles aside, text comes in three sizes only -- 16 (lead), 12 (body), 8 (notes).
TEXT_SIZES = (16, 12, 8)
SUBTITLE_PT = 12

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
CT_CHART = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
SLIDE_LIST = "<!--O01:sldIdLst-->"


def emu(inches: float) -> int:
    return int(round(inches * EMU))


# ------------------------------------------------------------------ text measurement
# Open Sans advance widths average 0.473 em (regular) and 0.502 em (bold) on the
# figures and names these decks carry (measured for the R01 export, see its README).
# 0.51 / 0.55 keep an ~8 % margin: enough that a line never breaks where the estimate
# said it would not, without shrinking short labels for nothing. Nunito Sans and Nunito
# set narrower than Open Sans, so these estimates stay on the safe side for the house faces.
def text_width(text: str, size_pt: float, bold: bool = False) -> float:
    """Estimated width in inches of one line of text."""
    return len(text) * size_pt * (0.55 if bold else 0.51) / 72


def wrap_lines(text: str, width_in: float, size_pt: float, bold: bool = False) -> int:
    """Lines a paragraph needs at this width (word wrap, estimated)."""
    lines, current = 0, ""
    for para in str(text).split("\n"):
        current = ""
        lines += 1
        for word in para.split(" "):
            trial = (current + " " + word).strip()
            if text_width(trial, size_pt, bold) <= width_in or not current:
                current = trial
            else:
                lines += 1
                current = word
    return max(lines, 1)


def text_height(paragraphs: list[str], w: float, size: float, bold: bool = False, inset: float = 0.08,
                spacing: float = 1.3) -> float:
    """Estimated height (in) the paragraphs need in a box `w` wide with `inset` margins:
    Open Sans lines at ~1.3 em, plus the 0.45 em paragraph spacing `para()` sets."""
    inner_w = w - 2 * inset
    lines = sum(wrap_lines(p, inner_w, size, bold) for p in paragraphs)
    return lines * size * spacing / 72 + max(0, len(paragraphs) - 1) * size * 0.45 / 72 + inset


def text_size(size: float) -> int:
    """The house size nearest `size` (ties go to the larger one: fit_size steps down if it must)."""
    return min(TEXT_SIZES, key=lambda s: (abs(s - size), -s))


def fit_size(paragraphs: list[str], w: float, h: float, start: float, floor: float = 8.0,
             bold: bool = False, inset: float = 0.08, title: bool = False) -> float:
    """Largest size at which the paragraphs fit the box: one of TEXT_SIZES, no larger than
    the house size nearest `start` (the smallest if nothing fits). Titles (`title=True`)
    are free of the scale and step down by 0.5 pt from `start` to `floor`."""
    if not title:
        steps = [s for s in TEXT_SIZES if s <= text_size(start)]
        return next((s for s in steps if text_height(paragraphs, w, s, bold, inset) <= h), steps[-1])
    size = start
    while size > floor:
        if text_height(paragraphs, w, size, bold, inset) <= h:
            return size
        size -= 0.5
    return floor


# ------------------------------------------------------------------ runs and paragraphs
@dataclass
class Run:
    text: str
    size: float = 11
    bold: bool = False
    color: str = INK
    italic: bool = False
    font: str = FONT

    def xml(self) -> str:
        attrs = f'lang="en-GB" sz="{text_size(self.size) * 100}" b="{int(self.bold)}" i="{int(self.italic)}" dirty="0"'
        return (f'<a:r><a:rPr {attrs}><a:solidFill><a:srgbClr val="{self.color}"/></a:solidFill>'
                f'<a:latin typeface="{self.font}"/><a:cs typeface="{self.font}"/></a:rPr><a:t>{escape(self.text)}</a:t></a:r>')


def title_run(text: str, size: float | None = None) -> str:
    """A run in the title face: Nunito Bold. Used for slide titles and everything on the cover.
    The size is taken as given: callers outside a title pass a TEXT_SIZES value."""
    sz = f' sz="{int(size * 100)}"' if size else ""
    return (f'<a:r><a:rPr lang="en-GB"{sz} b="1" dirty="0"><a:latin typeface="{TITLE_FONT}"/>'
            f'<a:cs typeface="{TITLE_FONT}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>')


def para(runs: list[Run] | Run | str, align: str = "l", bullet: bool = False, space_after: float = 3,
         size: float = 11, color: str = INK, bold: bool = False) -> str:
    if isinstance(runs, str):
        runs = [Run(runs, size, bold, color)]
    elif isinstance(runs, Run):
        runs = [runs]
    bu = ('<a:buFont typeface="Arial"/><a:buChar char="&#8226;"/>' if bullet else "<a:buNone/>")
    indent = ' marL="171450" indent="-171450"' if bullet else ' marL="0" indent="0"'
    sz = text_size(runs[0].size if runs else size) * 100
    body = "".join(r.xml() for r in runs)
    return (f'<a:p><a:pPr algn="{align}"{indent}><a:spcAft><a:spcPts val="{int(space_after * 100)}"/></a:spcAft>{bu}</a:pPr>'
            f'{body}<a:endParaRPr lang="en-GB" sz="{sz}" dirty="0"/></a:p>')


# ------------------------------------------------------------------ slide
@dataclass
class Slide:
    layout: str
    shapes: list[str] = field(default_factory=list)
    rels: list[tuple[str, str, str]] = field(default_factory=list)     # (rId, type, target)
    charts: list[tuple[str, bytes, bytes]] = field(default_factory=list)  # (rId, chart xml, xlsx)
    title: str = ""
    notes: list[str] = field(default_factory=list)                     # source / flag notes for QC
    _next_id: int = 2
    _next_rid: int = 1                                                 # rId1 is the layout

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _new_rid(self) -> str:
        self._next_rid += 1
        return f"rId{self._next_rid}"

    def _rel(self, kind: str, target: str) -> str:
        rid = self._new_rid()
        self.rels.append((rid, kind, target))
        return rid

    # --- placeholders (position and style come from the layout) ----------------
    def placeholder(self, ph: str, paragraphs: list[str], name: str = "Placeholder") -> None:
        sid = self._id()
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name} {sid}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
            f'<p:nvPr>{ph}</p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>{"".join(paragraphs)}</p:txBody></p:sp>')

    def set_title(self, text: str, size: float | None = None) -> None:
        """The slide's short label, in the layout's title placeholder (amber, 24 pt): one to four
        words, under TITLE_MAX characters (QC warns above that). The message goes in the subtitle."""
        self.title = text
        size = size or fit_size([text], BODY_W, 0.95, 24, 16, bold=True, inset=0.05, title=True)
        self.placeholder('<p:ph type="title"/>', [f"<a:p>{title_run(text, size)}</a:p>"], "Title")

    def set_subtitle(self, text: str, idx: int = 14) -> None:
        """The slide's takeaway, one line under the title, in ink."""
        size = fit_size([text], BODY_W, 0.3, SUBTITLE_PT, 8, inset=0.0)
        run = (f'<a:r><a:rPr lang="en-GB" sz="{int(size * 100)}" dirty="0"><a:solidFill><a:srgbClr val="{INK}"/></a:solidFill>'
               f'<a:latin typeface="{FONT}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>')
        self.placeholder(f'<p:ph type="body" sz="quarter" idx="{idx}"/>', [f"<a:p>{run}</a:p>"], "Subtitle")

    def picture_placeholder(self, idx: int, media_target: str, crop_lr: int = 26434) -> None:
        rid = self._rel(f"{REL}/image", media_target)
        sid = self._id()
        self.shapes.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name="Picture {sid}" descr=""/><p:cNvPicPr><a:picLocks noGrp="1" noChangeAspect="1"/></p:cNvPicPr>'
            f'<p:nvPr><p:ph type="pic" sz="quarter" idx="{idx}"/></p:nvPr></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:srcRect l="{crop_lr}" r="{crop_lr}"/><a:stretch/></p:blipFill><p:spPr/></p:pic>')

    # --- free shapes --------------------------------------------------------------
    def box(self, x: float, y: float, w: float, h: float, paragraphs: list[str] | None = None, *,
            fill: str | None = None, line: str | None = None, anchor: str = "t", inset: float = 0.08,
            radius: bool = False, name: str = "Text") -> None:
        sid = self._id()
        geom = "roundRect" if radius else "rect"
        fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
        line_xml = f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>' if line else "<a:ln><a:noFill/></a:ln>"
        adj = '<a:avLst><a:gd name="adj" fmla="val 6000"/></a:avLst>' if radius else "<a:avLst/>"
        ins = emu(inset)
        body = "".join(paragraphs or ['<a:p><a:endParaRPr lang="en-GB" dirty="0"/></a:p>'])
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name} {sid}"/><p:cNvSpPr txBox="{int(not fill and not line)}"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="{geom}">{adj}</a:prstGeom>{fill_xml}{line_xml}</p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="{ins}" rIns="{ins}" tIns="{ins}" bIns="{ins}" anchor="{anchor}"><a:normAutofit/></a:bodyPr>'
            f'<a:lstStyle/>{body}</p:txBody></p:sp>')

    def rule(self, x: float, y: float, w: float, color: str = RULE) -> None:
        sid = self._id()
        self.shapes.append(
            f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{sid}" name="Rule {sid}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="0"/></a:xfrm><a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
            f'<a:ln w="6350"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln></p:spPr></p:cxnSp>')

    def text(self, x: float, y: float, w: float, h: float, lines: list[str], size: float = 11, *,
             color: str = INK, bold: bool = False, bullets: bool = False, align: str = "l",
             fit: bool = True, floor: float = 8.0) -> float:
        """Text box; the size shrinks (not below `floor`) until the estimate fits. Returns the size used."""
        if fit:
            size = fit_size(lines, w - (0.19 if bullets else 0), h, size, floor, bold)   # bullets indent 0.19 in
        paras = [para([Run(t, size, bold, color)], align=align, bullet=bullets, space_after=size * 0.45) for t in lines]
        self.box(x, y, w, h, paras)
        return size

    KPI_TOP = 0.14          # the accent rule and the gap under it

    def heading(self, x: float, y: float, w: float, text: str, size: float = 12) -> None:
        """A section heading over a chart or table (bold, ink), 0.35 in high."""
        self.box(x, y, w, 0.35, [para([Run(text, size, True, INK)], space_after=0)], inset=0.02, name="Heading")

    @staticmethod
    def kpi_size(w: float, h: float, value: str, label: str, note: str = "") -> float:
        """Largest value size (pt) that leaves room for the label and note in a tile."""
        rest = text_height([label], w, 12, inset=0.02) - 0.02 + 12 * 0.45 / 72
        if note:
            rest += text_height([note], w, 8, inset=0.02) - 0.02 + 8 * 0.45 / 72
        # 0.1 in: the gap after the figure (0.3 of its size) and a small margin.
        return fit_size([value], w, h - Slide.KPI_TOP - rest - 0.1, 26, 11, bold=True, inset=0.02)

    def kpi(self, x: float, y: float, w: float, h: float, value: str, label: str,
            accent: str = ORANGE, note: str = "", vsize: float | None = None) -> None:
        """A figure on white: a short accent rule, the value large, its label under it. No
        fill: grey boxes make a slide heavy. Tiles in a row share one `vsize`, so their
        figures read as a set."""
        self.box(x, y, min(0.6, w), 0.05, fill=accent, name="Accent")
        vsize = vsize or self.kpi_size(w, h, value, label, note)
        lines = [para([Run(value, vsize, True, INK)], space_after=vsize * 0.3),
                 para([Run(label, 12, False, BLUEBERRY)], space_after=0)]
        if note:
            lines.append(para([Run(note, 8, False, GREY)], space_after=0))
        self.box(x, y + self.KPI_TOP, w, h - self.KPI_TOP, lines, anchor="t", inset=0.02, name="KPI")

    def table(self, x: float, y: float, w: float, rows: list[list[str]], *, col_weights: list[float] | None = None,
              size: float = 10, max_h: float | None = None, align: list[str] | None = None,
              cell_colors: dict[tuple[int, int], str] | None = None, bold_cols: tuple[int, ...] = (),
              bold_rows: tuple[int, ...] = (), floor: float = 7.0, head_color: str = T_HEAD,
              head_rule: str = INK, last_rule: str | None = None, row_h: float = 0.236) -> float:
        """A table whose first row is the header, in the house style (see T_HEAD). Columns are
        sized from their content (or `col_weights`), the font shrinks until the rows fit `max_h`.
        `cell_colors` colours a cell's text (bold) to flag it. `head_color` / `head_rule` /
        `last_rule` restyle it (the Investment Solutions decks: orange header and rules).
        Returns its height."""
        ncol = len(rows[0])
        align = align or ["l"] + ["r"] * (ncol - 1)
        colors = cell_colors or {}
        while True:
            widths = self._col_widths(rows, w, size, col_weights)
            heights = [max(max(wrap_lines(str(c), widths[j] - 0.18, size, True) for j, c in enumerate(r)) * size * 1.22 / 72 + 0.04,
                           max(0.283, row_h) if i == 0 else row_h)          # row heights of the reference table
                       for i, r in enumerate(rows)]
            total = sum(heights)
            if max_h is None or total <= max_h or size <= floor:
                break
            size -= 0.5

        def line(tag: str, color: str | None) -> str:
            if color is None:
                return f'<a:{tag} w="0"><a:noFill/></a:{tag}>'
            return f'<a:{tag} w="9525" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:prstDash val="solid"/></a:{tag}>'

        grid = "".join(f'<a:gridCol w="{emu(cw)}"/>' for cw in widths)
        trs = []
        for i, (r, rh) in enumerate(zip(rows, heights)):
            header = i == 0
            top = (head_rule if header and last_rule else None) if header else (head_rule if i == 1 else T_RULE)
            bottom = head_rule if header else (last_rule if last_rule and i == len(rows) - 1 else T_RULE)
            cells = []
            for j, c in enumerate(r):
                color = head_color if header else colors.get((i, j), INK)
                bold = header or (i, j) in colors or j in bold_cols or i in bold_rows
                run = Run(str(c), size, bold, color)
                cells.append(
                    f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="{align[j]}"><a:lnSpc><a:spcPct val="100000"/></a:lnSpc>'
                    f'<a:spcBef><a:spcPts val="0"/></a:spcBef><a:spcAft><a:spcPts val="0"/></a:spcAft><a:buNone/></a:pPr>{run.xml()}</a:p></a:txBody>'
                    f'<a:tcPr marL="90000" marR="72000" marT="18000" marB="18000" anchor="ctr">'
                    f'{line("lnL", None)}{line("lnR", None)}{line("lnT", top)}{line("lnB", bottom)}<a:noFill/></a:tcPr></a:tc>')
            trs.append(f'<a:tr h="{emu(rh)}">{"".join(cells)}</a:tr>')
        sid = self._id()
        self.shapes.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{sid}" name="Table {sid}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(total)}"/></p:xfrm>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
            f'<a:tbl><a:tblPr firstRow="1"/><a:tblGrid>{grid}</a:tblGrid>{"".join(trs)}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>')
        return total

    @staticmethod
    def _col_widths(rows, w, size, weights):
        if weights:
            total = sum(weights)
            return [w * k / total for k in weights]
        need = [max(text_width(str(r[j]), size, i == 0) + 0.2 for i, r in enumerate(rows)) for j in range(len(rows[0]))]
        if sum(need) <= w:
            spare = w - sum(need)
            return [n + spare * n / sum(need) for n in need]
        # Long free-text columns give way first; short figure columns keep their width.
        fixed = [n if n <= w * 0.18 else None for n in need]
        free_w = w - sum(n for n in fixed if n)
        flex = [n for n, f in zip(need, fixed) if f is None]
        if not flex or free_w <= 0:
            return [w * n / sum(need) for n in need]
        return [f if f is not None else free_w * n / sum(flex) for n, f in zip(need, fixed)]

    def chart(self, x: float, y: float, w: float, h: float, chart_xml: bytes, workbook: bytes) -> None:
        rid = self._new_rid()
        self.charts.append((rid, chart_xml, workbook))
        sid = self._id()
        self.shapes.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{sid}" name="Chart {sid}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></p:xfrm>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
            f'<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" r:id="{rid}"/></a:graphicData></a:graphic></p:graphicFrame>')

    def picture(self, x: float, y: float, w: float, h: float, media_target: str, name: str = "Picture",
                crop: tuple[int, int, int, int] = (0, 0, 0, 0)) -> None:
        """An image from the package (see Deck.add_media); `crop` = l, t, r, b in 1/1000 %."""
        rid = self._rel(f"{REL}/image", media_target)
        sid = self._id()
        l, t, r, b = crop
        src = f'<a:srcRect l="{l}" t="{t}" r="{r}" b="{b}"/>' if any(crop) else ""
        self.shapes.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name="{name} {sid}" descr=""/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/>{src}<a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')

    def caption(self, x: float, y: float, w: float, text: str, size: float = 8) -> float:
        """Source / method note under a chart or table: one short line, two at most. At the
        smallest house size (8 pt) a long note takes a second line rather than shrinking."""
        size = fit_size([text], w, 0.3, size, 8, inset=0.02)
        h = max(0.3, min(text_height([text], w, size, inset=0.02) + 0.02, 0.42))
        self.box(x, y, w, h, [para([Run(text, size, False, GREY)], space_after=0)], inset=0.02)
        return h

    def notes_box(self, x: float, y: float, w: float, h: float, head: str, items: list[tuple[str, str]],
                  accent: str = MINT, size: float = 11, floor: float = 8.5) -> float:
        """A short list under a heading and an accent rule, on white: each item is its text
        then, in grey, where it comes from (e.g. research quoted with its source and date).
        Returns the size used."""
        self.box(x, y, min(0.6, w), 0.05, fill=accent, name="Accent")
        self.text(x, y + 0.1, w, 0.35, [head], 12, bold=True, fit=False)
        body_h = h - 0.5
        size = fit_size([f"{t}  {src}".strip() for t, src in items], w - 0.19, body_h, size, floor)
        paras = [para([Run(t, size, False, INK)] + ([Run("  " + src, size - 1.5, False, GREY)] if src else []),
                      bullet=True, space_after=size * 0.45) for t, src in items]
        self.box(x, y + 0.5, w, body_h, paras)
        return size

    def xml(self) -> str:
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld {NS}><p:cSld><p:spTree>'
                f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
                f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
                f'{"".join(self.shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')


# ------------------------------------------------------------------ deck
class Deck:
    """Slides on the SYZ template. `save()` writes a complete .pptx."""

    def __init__(self, template: Path = TEMPLATE):
        with zipfile.ZipFile(template) as z:
            self.parts = {n: z.read(n) for n in z.namelist()}
        self.slides: list[Slide] = []
        self.layouts = self._layouts()
        self._strip_template_slides()
        self._set_fonts()

    def _layouts(self) -> dict[str, str]:
        out = {}
        for name, data in self.parts.items():
            if re.fullmatch(r"ppt/slideLayouts/slideLayout\d+\.xml", name):
                m = re.search(rb'<p:cSld name="([^"]*)"', data)
                if m:
                    out[m.group(1).decode().strip()] = name.split("/")[-1]
        return out

    def _strip_template_slides(self) -> None:
        for name in [n for n in self.parts if re.fullmatch(r"ppt/slides/(_rels/)?slide\d+\.xml(\.rels)?", n)]:
            del self.parts[name]
        pres = self.parts["ppt/presentation.xml"].decode("utf-8")
        # Keep the list's position: PresentationML fixes the order of these elements.
        self.parts["ppt/presentation.xml"] = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>", SLIDE_LIST, pres, flags=re.S).encode("utf-8")
        rels = self.parts["ppt/_rels/presentation.xml.rels"].decode("utf-8")
        rels = re.sub(r'<Relationship [^>]*Type="[^"]*/slide"[^>]*/>', "", rels)
        self.parts["ppt/_rels/presentation.xml.rels"] = rels.encode("utf-8")
        ct = self.parts["[Content_Types].xml"].decode("utf-8")
        self.parts["[Content_Types].xml"] = re.sub(r'<Override PartName="/ppt/slides/slide\d+\.xml"[^>]*/>', "", ct).encode("utf-8")

    def _set_fonts(self) -> None:
        """House rule: headings in Nunito (bold), body in Nunito Sans. The template's theme
        names Nunito Sans ExtraBold for headings, so point the theme fonts at the house faces."""
        for name in [n for n in self.parts if re.fullmatch(r"ppt/theme/theme\d+\.xml", n)]:
            x = self.parts[name].decode("utf-8")
            for slot, face in (("majorFont", TITLE_FONT), ("minorFont", FONT)):
                x = re.sub(rf"(<a:{slot}>.*?</a:{slot}>)",
                           lambda m: re.sub(r'(<a:(?:latin|ea) typeface=")[^"]*(")', rf"\g<1>{face}\2", m.group(1)),
                           x, count=1, flags=re.S)
            self.parts[name] = x.encode("utf-8")

    def add(self, layout: str) -> Slide:
        if layout not in self.layouts:
            raise KeyError(f"template has no layout {layout!r}; it has {sorted(self.layouts)}")
        slide = Slide(layout)
        self.slides.append(slide)
        return slide

    def add_media(self, data: bytes, ext: str) -> str:
        """Put an image in the package; returns the target to use from a slide."""
        ext = ext.lower().lstrip(".").replace("jpeg", "jpg")
        n = sum(1 for k in self.parts if k.startswith("ppt/media/o02_image")) + 1
        self.parts[f"ppt/media/o02_image{n}.{ext}"] = data
        return f"../media/o02_image{n}.{ext}"

    @property
    def cover_image(self) -> str:
        """The template's own cover photograph."""
        return "../media/image6.jpg"

    def save(self, path: Path) -> Path:
        parts = dict(self.parts)
        pres = parts["ppt/presentation.xml"].decode("utf-8")
        prels = parts["ppt/_rels/presentation.xml.rels"].decode("utf-8")
        ct = parts["[Content_Types].xml"].decode("utf-8")
        if 'Extension="xlsx"' not in ct:
            ct = ct.replace("<Default ", '<Default Extension="xlsx" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"/><Default ', 1)
        ids, overrides, chart_no = [], [], 0
        for n, slide in enumerate(self.slides, start=1):
            rels = [f'<Relationship Id="rId1" Type="{REL}/slideLayout" Target="../slideLayouts/{self.layouts[slide.layout]}"/>']
            rels += [f'<Relationship Id="{rid}" Type="{kind}" Target="{target}"/>' for rid, kind, target in slide.rels]
            for rid, chart_xml, workbook in slide.charts:
                chart_no += 1
                parts[f"ppt/charts/chart{chart_no}.xml"] = chart_xml
                parts[f"ppt/embeddings/O01_chart_data{chart_no}.xlsx"] = workbook
                parts[f"ppt/charts/_rels/chart{chart_no}.xml.rels"] = (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    f'<Relationship Id="rId1" Type="{REL}/package" Target="../embeddings/O01_chart_data{chart_no}.xlsx"/></Relationships>').encode("utf-8")
                rels.append(f'<Relationship Id="{rid}" Type="{REL}/chart" Target="../charts/chart{chart_no}.xml"/>')
                overrides.append(f'<Override PartName="/ppt/charts/chart{chart_no}.xml" ContentType="{CT_CHART}"/>')
            parts[f"ppt/slides/slide{n}.xml"] = slide.xml().encode("utf-8")
            parts[f"ppt/slides/_rels/slide{n}.xml.rels"] = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(rels)}</Relationships>').encode("utf-8")
            overrides.append(f'<Override PartName="/ppt/slides/slide{n}.xml" ContentType="{CT_SLIDE}"/>')
            rid = f"rIdO{n}"
            prels = prels.replace("</Relationships>", f'<Relationship Id="{rid}" Type="{REL}/slide" Target="slides/slide{n}.xml"/></Relationships>')
            ids.append(f'<p:sldId id="{255 + n}" r:id="{rid}"/>')
        pres = pres.replace(SLIDE_LIST, "<p:sldIdLst>" + "".join(ids) + "</p:sldIdLst>" if ids else "")
        parts["ppt/presentation.xml"] = pres.encode("utf-8")
        parts["ppt/_rels/presentation.xml.rels"] = prels.encode("utf-8")
        parts["[Content_Types].xml"] = ct.replace("</Types>", "".join(overrides) + "</Types>").encode("utf-8")
        if "docProps/app.xml" in parts:
            app = parts["docProps/app.xml"].decode("utf-8")
            parts["docProps/app.xml"] = re.sub(r"<Slides>\d+</Slides>", f"<Slides>{len(self.slides)}</Slides>", app).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", parts.pop("[Content_Types].xml"))
            for name, data in parts.items():
                z.writestr(name, data)
        return path
