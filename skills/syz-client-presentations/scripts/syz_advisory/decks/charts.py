"""Native PowerPoint charts (DrawingML chart parts) with their data embedded as .xlsx.

The cached values in the chart XML are what PowerPoint draws; the embedded
workbook is what "Edit Data" opens. Both are written from the same table, so
they cannot disagree. Styling follows the R01 deck's CHART_BASE: no frame, no
gridlines unless asked, theme colours; ticks, labels and legends at AXIS_PT so they
read on a projected slide.
"""

from __future__ import annotations

import io
from datetime import date
from xml.sax.saxutils import escape

from openpyxl import Workbook

from syz_advisory.decks.ooxml import FONT, GREY, INK, PALETTE, RULE

C_NS = ('xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
EXCEL_EPOCH = date(1899, 12, 30)
AXIS_PT = 10


def _col(i: int) -> str:
    return chr(ord("A") + i)


def _workbook(header: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(header)
    for r in rows:
        ws.append([None if v is None else v for v in r])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _txpr(size: float = 9, color: str = INK, bold: bool = False) -> str:
    return (f'<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="{int(size * 100)}" b="{int(bold)}">'
            f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="{FONT}"/></a:defRPr></a:pPr>'
            f'<a:endParaRPr lang="en-GB"/></a:p></c:txPr>')


def _str_ref(ref: str, values: list[str]) -> str:
    pts = "".join(f'<c:pt idx="{i}"><c:v>{escape(str(v))}</c:v></c:pt>' for i, v in enumerate(values))
    return f"<c:strRef><c:f>{ref}</c:f><c:strCache><c:ptCount val=\"{len(values)}\"/>{pts}</c:strCache></c:strRef>"


def _num_ref(ref: str, values: list, fmt: str = "General") -> str:
    pts = "".join(f'<c:pt idx="{i}"><c:v>{v!r}</c:v></c:pt>' for i, v in enumerate(values) if v is not None)
    return (f"<c:numRef><c:f>{ref}</c:f><c:numCache><c:formatCode>{escape(fmt)}</c:formatCode>"
            f'<c:ptCount val="{len(values)}"/>{pts}</c:numCache></c:numRef>')


def _fill(color: str) -> str:
    return f'<c:spPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:ln><a:noFill/></a:ln></c:spPr>'


def _line(color: str, width_pt: float = 1.75, dash: str | None = None) -> str:
    d = f'<a:prstDash val="{dash}"/>' if dash else ""
    return (f'<c:spPr><a:ln w="{int(width_pt * 12700)}" cap="rnd"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{d}'
            f'<a:round/></a:ln></c:spPr>')


def _space(plot: str, legend: str | None = "b") -> bytes:
    leg = (f'<c:legend><c:legendPos val="{legend}"/><c:overlay val="0"/>{_txpr(AXIS_PT)}</c:legend>' if legend else "")
    xml = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><c:chartSpace {C_NS}>'
           '<c:date1904 val="0"/><c:roundedCorners val="0"/>'
           f'<c:chart><c:autoTitleDeleted val="1"/><c:plotArea><c:layout/>{plot}</c:plotArea>{leg}'
           '<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
           '<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>'
           f'{_txpr(AXIS_PT)}<c:externalData r:id="rId1"><c:autoUpdate val="0"/></c:externalData></c:chartSpace>')
    return xml.encode("utf-8")


def _axis_lines(show: bool) -> str:
    return (f'<c:spPr><a:ln w="6350"><a:solidFill><a:srgbClr val="{RULE}"/></a:solidFill></a:ln></c:spPr>' if show
            else '<c:spPr><a:ln><a:noFill/></a:ln></c:spPr>')


def _grid(show: bool) -> str:
    return (f'<c:majorGridlines><c:spPr><a:ln w="3175"><a:solidFill><a:srgbClr val="E3E5EB"/></a:solidFill></a:ln></c:spPr></c:majorGridlines>'
            if show else "")


def _labels(fmt: str, size: float = 9, pos: str | None = None) -> str:
    p = f'<c:dLblPos val="{pos}"/>' if pos else ""
    return (f'<c:dLbls><c:numFmt formatCode="{escape(fmt)}" sourceLinked="0"/><c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>'
            f'{_txpr(size)}{p}<c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/>'
            '<c:showSerName val="0"/><c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>')


# ------------------------------------------------------------------ doughnut
def doughnut(labels: list[str], values: list[float], colors: list[str] | None = None,
             fmt: str = "0.0%", hole: int = 62) -> tuple[bytes, bytes]:
    """Shares of a whole, largest first. `values` are fractions (0.25 = 25%).
    No labels on the ring: the builder sets a legend table beside it (R01 deck rule)."""
    colors = colors or [PALETTE[i % len(PALETTE)] for i in range(len(labels))]
    n = len(labels)
    pts = "".join(f'<c:dPt><c:idx val="{i}"/><c:bubble3D val="0"/>{_fill(colors[i])}</c:dPt>' for i in range(n))
    ser = (f'<c:ser><c:idx val="0"/><c:order val="0"/><c:tx>{_str_ref("Sheet1!$B$1", ["Share"])}</c:tx>{pts}'
           f'<c:cat>{_str_ref(f"Sheet1!$A$2:$A${n + 1}", labels)}</c:cat>'
           f'<c:val>{_num_ref(f"Sheet1!$B$2:$B${n + 1}", values, fmt)}</c:val></c:ser>')
    plot = (f'<c:doughnutChart><c:varyColors val="1"/>{ser}<c:firstSliceAng val="0"/><c:holeSize val="{hole}"/></c:doughnutChart>'
            if hole else f'<c:pieChart><c:varyColors val="1"/>{ser}<c:firstSliceAng val="0"/></c:pieChart>')
    return _space(plot, legend=None), _workbook(["Category", "Share"], [[l, v] for l, v in zip(labels, values)])


# ------------------------------------------------------------------ lines over categories
def lines(categories: list[str], series: dict[str, list[float | None]], *, fmt: str = "General",
          colors: list[str] | None = None, markers: bool = True, width_pt: float = 2.5,
          y_title: str = "", x_title: str = "", labels_on: bool = False) -> tuple[bytes, bytes]:
    """Lines over text categories (strike levels, quarters, fixings), round markers optional:
    the line chart of the Investment Solutions decks (orange, 2.5 pt, dots)."""
    colors = colors or PALETTE
    n = len(categories)
    sers = []
    for k, (name, vals) in enumerate(series.items()):
        col = _col(k + 1)
        c = colors[k % len(colors)]
        mk = (f'<c:marker><c:symbol val="circle"/><c:size val="7"/>{_fill(c)}</c:marker>'
              if markers else '<c:marker><c:symbol val="none"/></c:marker>')
        sers.append(
            f'<c:ser><c:idx val="{k}"/><c:order val="{k}"/><c:tx>{_str_ref(f"Sheet1!${col}$1", [name])}</c:tx>'
            f'{_line(c, width_pt)}{mk}{_labels(fmt, AXIS_PT, "t") if labels_on else ""}'
            f'<c:cat>{_str_ref(f"Sheet1!$A$2:$A${n + 1}", [str(x) for x in categories])}</c:cat>'
            f'<c:val>{_num_ref(f"Sheet1!${col}$2:${col}${n + 1}", vals, fmt)}</c:val><c:smooth val="0"/></c:ser>')

    def title(text: str) -> str:
        return (f'<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="{int(AXIS_PT * 100)}" b="0">'
                f'<a:solidFill><a:srgbClr val="{GREY}"/></a:solidFill><a:latin typeface="{FONT}"/></a:defRPr></a:pPr>'
                f'<a:r><a:rPr lang="en-GB" sz="{int(AXIS_PT * 100)}" b="0"><a:solidFill><a:srgbClr val="{GREY}"/></a:solidFill>'
                f'<a:latin typeface="{FONT}"/></a:rPr><a:t>{escape(text)}</a:t></a:r></a:p></c:rich></c:tx><c:overlay val="0"/></c:title>'
                if text else "")
    plot = (f'<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>{"".join(sers)}<c:marker val="1"/>'
            f'<c:axId val="4001"/><c:axId val="4002"/></c:lineChart>'
            f'<c:catAx><c:axId val="4001"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="b"/>'
            f'{title(x_title)}<c:numFmt formatCode="General" sourceLinked="0"/><c:majorTickMark val="out"/><c:minorTickMark val="none"/>'
            f'<c:tickLblPos val="low"/>{_axis_lines(True)}{_txpr(AXIS_PT, GREY)}<c:crossAx val="4002"/><c:crosses val="autoZero"/>'
            f'<c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
            f'<c:valAx><c:axId val="4002"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="l"/>'
            f'{_grid(True)}{title(y_title)}<c:numFmt formatCode="{escape(fmt)}" sourceLinked="0"/><c:majorTickMark val="none"/>'
            f'<c:minorTickMark val="none"/><c:tickLblPos val="low"/>{_axis_lines(True)}{_txpr(AXIS_PT, GREY)}<c:crossAx val="4001"/>'
            f'<c:crosses val="autoZero"/><c:crossBetween val="midCat"/></c:valAx>')
    rows = [[c] + [series[name][i] for name in series] for i, c in enumerate(categories)]
    return _space(plot, legend="b" if len(series) > 1 else None), _workbook(["Category"] + list(series), rows)


# ------------------------------------------------------------------ bars
def bars(labels: list[str], series: dict[str, list[float | None]], *, horizontal: bool = True,
         fmt: str = "0.0%", colors: list[str] | None = None, stacked: bool = False,
         gridlines: bool = False, labels_on: bool = True, ref_min: float | None = None,
         point_colors: list[str | None] | None = None, labels_bold: bool = False) -> tuple[bytes, bytes]:
    """Clustered (or stacked) bars. Horizontal bars list the first label at the top.
    `point_colors[i]` recolours bar i of the first series (e.g. to highlight the last ones)."""
    names = list(series)
    colors = colors or PALETTE
    n = len(labels)
    order_labels = list(reversed(labels)) if horizontal else labels       # bar charts draw bottom-up
    sers = []
    for k, name in enumerate(names):
        vals = list(reversed(series[name])) if horizontal else series[name]
        col = _col(k + 1)
        dpts = ""
        if k == 0 and point_colors:
            pcs = list(reversed(point_colors)) if horizontal else point_colors
            dpts = "".join(f'<c:dPt><c:idx val="{i}"/><c:invertIfNegative val="0"/><c:bubble3D val="0"/>{_fill(c)}</c:dPt>'
                           for i, c in enumerate(pcs) if c)
        lbl = _labels(fmt, AXIS_PT, "outEnd" if not stacked else "ctr")
        if labels_bold:
            lbl = lbl.replace(f'sz="{int(AXIS_PT * 100)}" b="0"', f'sz="{int(AXIS_PT * 100)}" b="1"')
        sers.append(
            f'<c:ser><c:idx val="{k}"/><c:order val="{k}"/><c:tx>{_str_ref(f"Sheet1!${col}$1", [name])}</c:tx>'
            f'{_fill(colors[k % len(colors)])}<c:invertIfNegative val="0"/>{dpts}'
            f'{lbl if labels_on else ""}'
            f'<c:cat>{_str_ref(f"Sheet1!$A$2:$A${n + 1}", order_labels)}</c:cat>'
            f'<c:val>{_num_ref(f"Sheet1!${col}$2:${col}${n + 1}", vals, fmt)}</c:val></c:ser>')
    grouping = "stacked" if stacked else "clustered"
    overlap = '<c:overlap val="100"/>' if stacked else ""
    scale = f'<c:min val="{ref_min}"/>' if ref_min is not None else ""
    plot = (f'<c:barChart><c:barDir val="{"bar" if horizontal else "col"}"/><c:grouping val="{grouping}"/><c:varyColors val="0"/>'
            f'{"".join(sers)}<c:gapWidth val="{50 if horizontal else 67}"/>{overlap}<c:axId val="1001"/><c:axId val="1002"/></c:barChart>'
            f'<c:catAx><c:axId val="1001"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/>'
            f'<c:axPos val="{"l" if horizontal else "b"}"/><c:numFmt formatCode="General" sourceLinked="0"/><c:majorTickMark val="none"/>'
            f'<c:minorTickMark val="none"/><c:tickLblPos val="low"/>{_axis_lines(not horizontal)}{_txpr(AXIS_PT)}'
            f'<c:crossAx val="1002"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
            f'<c:valAx><c:axId val="1002"/><c:scaling><c:orientation val="minMax"/>{scale}</c:scaling><c:delete val="{int(not gridlines)}"/>'
            f'<c:axPos val="{"b" if horizontal else "l"}"/>{_grid(gridlines)}<c:numFmt formatCode="{escape(fmt)}" sourceLinked="0"/>'
            f'<c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>{_axis_lines(False)}{_txpr(AXIS_PT, GREY)}'
            f'<c:crossAx val="1001"/><c:crosses val="autoZero"/><c:crossBetween val="between"/></c:valAx>')
    rows = [[l] + [series[name][i] for name in names] for i, l in enumerate(labels)]
    return _space(plot, legend="b" if len(names) > 1 else None), _workbook(["Category"] + names, rows)


# ------------------------------------------------------------------ lines over dates
def lines_over_dates(dates: list[str], series: dict[str, list[float | None]], *, fmt: str = "0",
                     colors: list[str] | None = None, styles: dict[str, tuple[str, float, str | None]] | None = None,
                     y_min: float | None = None, y_max: float | None = None) -> tuple[bytes, bytes]:
    """Daily series on a date axis. `styles[name] = (colour, width_pt, dash)` overrides
    a series' look -- used for the barrier / strike / autocall reference lines."""
    serial = [(date.fromisoformat(d) - EXCEL_EPOCH).days for d in dates]
    n = len(dates)
    colors = colors or PALETTE
    styles = styles or {}
    sers = []
    for k, (name, vals) in enumerate(series.items()):
        col = _col(k + 1)
        color, width, dash = styles.get(name, (colors[k % len(colors)], 1.75, None))
        sers.append(
            f'<c:ser><c:idx val="{k}"/><c:order val="{k}"/><c:tx>{_str_ref(f"Sheet1!${col}$1", [name])}</c:tx>'
            f'{_line(color, width, dash)}<c:marker><c:symbol val="none"/></c:marker>'
            f'<c:cat>{_num_ref(f"Sheet1!$A$2:$A${n + 1}", serial, "mmm yy")}</c:cat>'
            f'<c:val>{_num_ref(f"Sheet1!${col}$2:${col}${n + 1}", vals, fmt)}</c:val><c:smooth val="0"/></c:ser>')
    scale = (f'<c:max val="{y_max}"/>' if y_max is not None else "") + (f'<c:min val="{y_min}"/>' if y_min is not None else "")
    span = max(serial) - min(serial) if serial else 0
    unit = "months"
    major = max(1, round(span / 30 / 6)) if span else 1
    plot = (f'<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>{"".join(sers)}<c:marker val="1"/>'
            f'<c:axId val="2001"/><c:axId val="2002"/></c:lineChart>'
            f'<c:dateAx><c:axId val="2001"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="b"/>'
            f'<c:numFmt formatCode="mmm yy" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/>'
            f'<c:tickLblPos val="low"/>{_axis_lines(True)}{_txpr(AXIS_PT, GREY)}<c:crossAx val="2002"/><c:crosses val="autoZero"/>'
            f'<c:auto val="1"/><c:lblOffset val="100"/><c:baseTimeUnit val="days"/><c:majorUnit val="{major}"/><c:majorTimeUnit val="{unit}"/></c:dateAx>'
            f'<c:valAx><c:axId val="2002"/><c:scaling><c:orientation val="minMax"/>{scale}</c:scaling><c:delete val="0"/><c:axPos val="l"/>'
            f'{_grid(True)}<c:numFmt formatCode="{escape(fmt)}" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/>'
            f'<c:tickLblPos val="nextTo"/>{_axis_lines(False)}{_txpr(AXIS_PT, GREY)}<c:crossAx val="2001"/><c:crosses val="autoZero"/>'
            f'<c:crossBetween val="between"/></c:valAx>')
    rows = [[d] + [series[name][i] for name in series] for i, d in enumerate(dates)]
    return _space(plot, legend="b"), _workbook(["Date"] + list(series), rows)


# ------------------------------------------------------------------ payoff (XY)
def payoff(levels: list[float], series: dict[str, list[float | None]], *, colors: list[str] | None = None,
           styles: dict[str, tuple[str, float, str | None]] | None = None,
           markers: dict[str, tuple[float, str]] | None = None) -> tuple[bytes, bytes]:
    """Return at maturity (y, fraction) against the final level of the worst underlying
    (x, fraction of initial). A None y leaves a gap (e.g. 'barrier not hit' below the barrier).

    `markers[name] = (x, colour)` draws a vertical dashed reference line -- today's worst-of
    level, the barrier, the strike, the breakeven -- so the reader sees where the product
    stands on its own payoff, which is what the diagram is for."""
    colors = colors or PALETTE
    styles = styles or {}
    n = len(levels)
    sers = []
    for k, (name, ys) in enumerate(series.items()):
        col = _col(k + 1)
        color, width, dash = styles.get(name, (colors[k % len(colors)], 2.25, None))
        xs = [x for x, y in zip(levels, ys)]
        sers.append(
            f'<c:ser><c:idx val="{k}"/><c:order val="{k}"/><c:tx>{_str_ref(f"Sheet1!${col}$1", [name])}</c:tx>'
            f'{_line(color, width, dash)}<c:marker><c:symbol val="none"/></c:marker>'
            f'<c:xVal>{_num_ref(f"Sheet1!$A$2:$A${n + 1}", xs, "0%")}</c:xVal>'
            f'<c:yVal>{_num_ref(f"Sheet1!${col}$2:${col}${n + 1}", ys, "0%")}</c:yVal><c:smooth val="0"/></c:ser>')
    ys_all = [y for ys in series.values() for y in ys if y is not None] or [0.0]
    lo, hi = min(ys_all), max(ys_all)
    pad = (hi - lo) * 0.05 or 0.05
    extra_rows = []
    base = len(series)
    shown = [(name, x, color) for name, (x, color) in (markers or {}).items()
             if x is not None and min(levels) <= x <= max(levels)]
    for j, (name, x, color) in enumerate(shown):
        k = base + j
        r0 = n + 3 + 2 * j                       # under the curve data and one blank row, in the sheet
        sers.append(
            f'<c:ser><c:idx val="{k}"/><c:order val="{k}"/><c:tx><c:v>{escape(name)}</c:v></c:tx>'
            f'{_line(color, 1.0, "dash")}<c:marker><c:symbol val="none"/></c:marker>'
            f'<c:xVal>{_num_ref(f"Sheet1!$A${r0}:$A${r0 + 1}", [x, x], "0%")}</c:xVal>'
            f'<c:yVal>{_num_ref(f"Sheet1!$B${r0}:$B${r0 + 1}", [round(lo - pad, 4), round(hi + pad, 4)], "0%")}</c:yVal>'
            f'<c:smooth val="0"/></c:ser>')
        extra_rows += [[x, round(lo - pad, 4), name], [x, round(hi + pad, 4), name]]
    plot = (f'<c:scatterChart><c:scatterStyle val="lineMarker"/><c:varyColors val="0"/>{"".join(sers)}'
            f'<c:axId val="3001"/><c:axId val="3002"/></c:scatterChart>'
            f'<c:valAx><c:axId val="3001"/><c:scaling><c:orientation val="minMax"/><c:max val="{max(levels)}"/><c:min val="{min(levels)}"/></c:scaling>'
            f'<c:delete val="0"/><c:axPos val="b"/><c:numFmt formatCode="0%" sourceLinked="0"/><c:majorTickMark val="none"/>'
            f'<c:minorTickMark val="none"/><c:tickLblPos val="low"/>{_axis_lines(True)}{_txpr(AXIS_PT, GREY)}'
            f'<c:crossAx val="3002"/><c:crosses val="autoZero"/><c:crossBetween val="midCat"/><c:majorUnit val="0.2"/></c:valAx>'
            f'<c:valAx><c:axId val="3002"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="l"/>'
            f'{_grid(True)}<c:numFmt formatCode="0%" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/>'
            f'<c:tickLblPos val="low"/>{_axis_lines(False)}{_txpr(AXIS_PT, GREY)}<c:crossAx val="3001"/><c:crosses val="autoZero"/>'
            f'<c:crossBetween val="midCat"/></c:valAx>')
    rows = [[x] + [series[name][i] for name in series] for i, x in enumerate(levels)]
    if extra_rows:
        width = 1 + len(series)
        rows += [[None] * width] + [r[:2] + [None] * (width - 2) + [r[2]] for r in extra_rows]
    return _space(plot, legend="b"), _workbook(["Final level of worst underlying"] + list(series), rows)
