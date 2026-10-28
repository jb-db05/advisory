"""An HTML preview of a finished .pptx, drawn from its own XML.

PowerPoint cannot be automated here and Edge headless is blocked, so this is how a
deck is looked at before it is opened: every slide at 96 dpi, text in the
installed Open Sans (so line breaks fall where PowerPoint puts them, near enough),
tables cell by cell, charts redrawn as SVG from their cached values. Layout
placeholders (titles, subtitles) are placed with the template's own geometry.

It is a preview, not a renderer: the slide master's artwork is sketched (logo box,
footer rule), and chart insets differ from PowerPoint's.
"""

from __future__ import annotations

import base64
import math
import re
import zipfile
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

from syz_advisory.decks.ooxml import EMU, PAGE_H, PAGE_W

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DPI = 96
# Placeholder geometry (in) from the template's layouts, by layout name and placeholder.
PH = {
    "One Content": {"title": (0.73, 1.13, 10.28, 0.77, 24, "FFA400", True), "14": (0.73, 2.09, 10.28, 0.28, 12, "202945", False)},
    "Cover Slide 2": {"ctrTitle": (0.73, 5.97, 3.83, 1.12, 28, "FFA400", True), "13": (0.73, 5.37, 3.31, 0.42, 12, "202945", False)},
}
PANEL = {"Cover Slide 2": (5.85, 0, 5.85, 8.27), "Agenda": (5.85, 0, 5.85, 8.27)}


def _px(v: float) -> str:
    return f"{v * DPI:.1f}px"


def _runs_html(p) -> str:
    out = []
    for r in p.iter(A + "r"):
        rpr = r.find(A + "rPr")
        t = escape(r.find(A + "t").text or "")
        style = []
        if rpr is not None:
            if rpr.get("sz"):
                style.append(f"font-size:{int(rpr.get('sz')) / 100}pt")
            if rpr.get("b") == "1":
                style.append("font-weight:700")
            if rpr.get("i") == "1":
                style.append("font-style:italic")
            c = rpr.find(f"{A}solidFill/{A}srgbClr")
            if c is not None:
                style.append(f"color:#{c.get('val')}")
        out.append(f'<span style="{";".join(style)}">{t}</span>')
    return "".join(out)


def _para_html(p) -> str:
    ppr = p.find(A + "pPr")
    align = {"l": "left", "r": "right", "ctr": "center", "c": "center", "just": "justify"}.get(ppr.get("algn") if ppr is not None else "l", "left")
    bu = ppr.find(A + "buChar") if ppr is not None else None
    bullet = bu is not None
    gap = ppr.find(f"{A}spcAft/{A}spcPts") if ppr is not None else None
    mb = int(gap.get("val")) / 100 if gap is not None else 0
    bclr = ppr.find(f"{A}buClr/{A}srgbClr") if ppr is not None else None
    pre = (f'<span style="color:#{bclr.get("val") if bclr is not None else "202945"}">{escape(bu.get("char") or "•")}</span> '
           if bullet else "")
    pad = "padding-left:0.19in;text-indent:-0.12in;" if bullet else ""
    first = next((r.find(A + "rPr") for r in p.iter(A + "r") if r.find(A + "rPr") is not None and r.find(A + "rPr").get("sz")), None)
    size = f"font-size:{int(first.get('sz')) / 100}pt;" if first is not None else ""
    return f'<div style="text-align:{align};margin:0 0 {mb}pt 0;{pad}{size}">{pre}{_runs_html(p)}</div>'


def _geom(el):
    off, ext = el.find(".//" + A + "off"), el.find(".//" + A + "ext")
    if off is None or ext is None:
        return None
    return (int(off.get("x")) / EMU, int(off.get("y")) / EMU, int(ext.get("cx")) / EMU, int(ext.get("cy")) / EMU)


def _shape_html(sp, layout: str) -> str:
    ph = sp.find(f".//{P}nvPr/{P}ph")
    g = _geom(sp)
    texts = "".join(_para_html(p) for p in sp.iter(A + "p") if p.find(A + "r") is not None)
    if ph is not None and g is None:
        key = ph.get("type") if ph.get("type") in ("title", "ctrTitle") else ph.get("idx")
        spec = PH.get(layout, {}).get(key)
        if layout == "Agenda" and ph.get("idx") and 20 <= int(ph.get("idx")) <= 29:
            i = int(ph.get("idx"))
            row = (i - 20) % 5
            spec = ((1.16, 3.37 + row * 0.4, 3.12, 0.33, 12, "202945", False) if i < 25 else
                    (0.73, 3.37 + row * 0.4, 0.36, 0.33, 12, "FFFFFF", True))
        if spec is None:
            return ""
        x, y, w, h, size, color, bold = spec
        bg = "background:#FFA400;" if layout == "Agenda" and int(ph.get("idx") or 0) >= 25 else ""
        return (f'<div class="box" style="left:{_px(x)};top:{_px(y)};width:{_px(w)};height:{_px(h)};font-size:{size}pt;'
                f'color:#{color};font-weight:{700 if bold else 400};{bg}display:flex;align-items:flex-end">'
                f'<div style="width:100%">{texts}</div></div>')
    if g is None:
        return ""
    x, y, w, h = g
    if ph is not None and ph.get("type") in ("title", "ctrTitle"):          # a title box moved or resized
        size, color = PH.get(layout, {}).get(ph.get("type"), (0, 0, 0, 0, 24, "FFA400", True))[4:6]
        return (f'<div class="box" style="left:{_px(x)};top:{_px(y)};width:{_px(w)};height:{_px(h)};font-size:{size}pt;'
                f'color:#{color};font-weight:700;display:flex;align-items:flex-end"><div style="width:100%">{texts}</div></div>')
    fill = sp.find(f"{P}spPr/{A}solidFill/{A}srgbClr")
    line = sp.find(f"{P}spPr/{A}ln/{A}solidFill/{A}srgbClr")
    geom = sp.find(f"{P}spPr/{A}prstGeom")
    radius = {"roundRect": "10px", "ellipse": "50%"}.get(geom.get("prst") if geom is not None else "", "0")
    body = sp.find(".//" + A + "bodyPr")
    ins = int(body.get("lIns", 91440)) / EMU if body is not None else 0.1
    anchor = {"t": "flex-start", "ctr": "center", "b": "flex-end"}.get(body.get("anchor", "t") if body is not None else "t")
    style = (f"left:{_px(x)};top:{_px(y)};width:{_px(w)};height:{_px(h)};padding:{_px(ins)};"
             f"background:{'#' + fill.get('val') if fill is not None else 'transparent'};"
             f"border:{'1px solid #' + line.get('val') if line is not None else 'none'};border-radius:{radius};"
             f"display:flex;flex-direction:column;justify-content:{anchor}")
    return f'<div class="box" style="{style}">{texts}</div>'


def _table_html(gf) -> str:
    x, y, w, h = _geom(gf)
    cols = [int(c.get("w")) / EMU for c in gf.iter(A + "gridCol")]
    rows = []
    for tr in gf.iter(A + "tr"):
        cells = []
        for tc in tr.findall(A + "tc"):
            fill = tc.find(f"{A}tcPr/{A}solidFill/{A}srgbClr")
            edges = []
            for tag, side in (("lnT", "top"), ("lnB", "bottom")):
                c = tc.find(f"{A}tcPr/{A}{tag}/{A}solidFill/{A}srgbClr")
                edges.append(f"border-{side}:1px solid #{c.get('val')}" if c is not None else f"border-{side}:none")
            cells.append(f'<td style="background:#{fill.get("val") if fill is not None else "FFF"};{";".join(edges)}">'
                         f'{"".join(_para_html(p) for p in tc.iter(A + "p"))}</td>')
        rows.append(f'<tr style="height:{_px(int(tr.get("h")) / EMU)}">{"".join(cells)}</tr>')
    colgroup = "".join(f'<col style="width:{_px(c)}">' for c in cols)
    return (f'<table class="tbl" style="left:{_px(x)};top:{_px(y)};width:{_px(sum(cols))}"><colgroup>{colgroup}</colgroup>'
            f'{"".join(rows)}</table><div class="frame" style="left:{_px(x)};top:{_px(y)};width:{_px(w)};height:{_px(h)}" '
            f'title="table frame as stated in the file"></div>')


# ------------------------------------------------------------------ charts as SVG
def _series(root):
    out = []
    for ser in root.iter(C + "ser"):
        tx = ser.find(f"{C}tx//{C}v")
        name = tx.text if tx is not None else ""
        color = ser.find(f"{C}spPr//{A}srgbClr")
        dash = ser.find(f"{C}spPr//{A}prstDash")
        pts_colors = [d.find(f".//{A}srgbClr").get("val") for d in ser.findall(C + "dPt")]
        pt_map = {int(d.find(C + "idx").get("val")): "#" + d.find(f".//{A}srgbClr").get("val") for d in ser.findall(C + "dPt")}
        fmt = ser.find(f"{C}dLbls/{C}numFmt")
        labels = fmt.get("formatCode") if fmt is not None else None

        def values(tag):
            node = ser.find(C + tag)
            if node is None:
                return []
            cache = node.find(f".//{C}numCache")
            if cache is None:
                cache = node.find(f".//{C}strCache")
            if cache is None:
                return []
            n = int(cache.find(C + "ptCount").get("val"))
            vals = [None] * n
            for p in cache.findall(C + "pt"):
                vals[int(p.get("idx"))] = p.find(C + "v").text
            return vals
        out.append({"name": name, "color": "#" + (color.get("val") if color is not None else "888888"),
                     "dash": dash is not None, "cat": values("cat") or values("xVal"),
                     "val": [float(v) if v is not None else None for v in (values("val") or values("yVal"))],
                     "pts": pts_colors, "pt_map": pt_map, "labels": labels})
    return out


def _num(v: float, fmt: str | None) -> str:
    if fmt and "%" in fmt:
        return f"{v:.{fmt.count('0') - 1 if '.' in fmt else 0}%}"
    return f"{v:,.0f}".replace(",", "'") if abs(v) >= 100 else f"{v:g}"


def _chart_svg(root, w: float, h: float) -> str:
    W, H = w * DPI, h * DPI
    ser = _series(root)
    kind = next((t.tag.split("}")[1] for t in root.find(f"{C}chart/{C}plotArea") if t.tag.endswith("Chart")), "")
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" font-family="Open Sans" font-size="11">']
    if kind in ("doughnutChart", "pieChart") and ser:
        s = ser[0]
        total = sum(v for v in s["val"] if v) or 1
        cx, cy, r0, r1 = W / 2, H / 2, (min(W, H) * 0.28 if kind == "doughnutChart" else 0.01), min(W, H) * 0.45
        ang = -math.pi / 2
        for v, col in zip(s["val"], s["pts"]):
            a2 = ang + 2 * math.pi * (v or 0) / total
            large = 1 if a2 - ang > math.pi else 0
            p = [(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)), (cx + r1 * math.cos(a2), cy + r1 * math.sin(a2)),
                 (cx + r0 * math.cos(a2), cy + r0 * math.sin(a2)), (cx + r0 * math.cos(ang), cy + r0 * math.sin(ang))]
            svg.append(f'<path d="M{p[0][0]:.1f},{p[0][1]:.1f} A{r1:.1f},{r1:.1f} 0 {large} 1 {p[1][0]:.1f},{p[1][1]:.1f} '
                       f'L{p[2][0]:.1f},{p[2][1]:.1f} A{r0:.1f},{r0:.1f} 0 {large} 0 {p[3][0]:.1f},{p[3][1]:.1f} Z" fill="#{col}"/>')
            ang = a2
    elif kind == "barChart" and ser:
        horizontal = root.find(f".//{C}barDir").get("val") == "bar"
        cats = ser[0]["cat"]
        vmax = max([v for s in ser for v in s["val"] if v is not None] + [0.0001])
        vmin = min([v for s in ser for v in s["val"] if v is not None] + [0])
        span = vmax - vmin
        n, k = len(cats), len(ser)
        if horizontal:
            left, top, right = W * 0.38, 6, W - 50
            slot = (H - top - 20) / max(n, 1)
            for i, cat in enumerate(reversed(cats)):          # cached order is bottom-up
                yy = top + i * slot
                svg.append(f'<text x="{left - 6:.0f}" y="{yy + slot / 2 + 4:.0f}" text-anchor="end" fill="#202945" font-size="11">{escape(str(cat))[:40]}</text>')
                for j, s in enumerate(ser):
                    v = list(reversed(s["val"]))[i]
                    if v is None:
                        continue
                    bw = (right - left) * (v - min(vmin, 0)) / (span or 1)
                    bh = slot * 0.6 / k
                    by = yy + slot * 0.2 + j * bh
                    col = s["pt_map"].get(n - 1 - i, s["color"])
                    svg.append(f'<rect x="{left:.0f}" y="{by:.0f}" width="{max(bw, 1):.0f}" height="{bh:.0f}" fill="{col}"/>'
                               f'<text x="{left + bw + 4:.0f}" y="{by + bh / 2 + 4:.0f}" font-size="11" fill="#202945">{_num(v, s["labels"] or "0.0%")}</text>')
        else:
            left, bottom = 40, H - 40
            slot = (W - left - 10) / max(n, 1)
            zero = bottom - (bottom - 10) * (0 - min(vmin, 0)) / (span or 1)
            for i, cat in enumerate(cats):
                xx = left + i * slot
                svg.append(f'<text x="{xx + slot / 2:.0f}" y="{bottom + 16:.0f}" text-anchor="middle" font-size="11" fill="#8C8C8C">{escape(str(cat))[:18]}</text>')
                for j, s in enumerate(ser):
                    v = s["val"][i]
                    if v is None:
                        continue
                    bh = (bottom - 24) * abs(v) / (span or 1)
                    bw = slot * 0.6 / k
                    bx = xx + slot * 0.2 + j * bw
                    by = zero - bh if v >= 0 else zero
                    svg.append(f'<rect x="{bx:.0f}" y="{by:.0f}" width="{bw:.0f}" height="{max(bh, 1):.0f}" fill="{s["pt_map"].get(i, s["color"])}"/>')
                    if s["labels"]:
                        ly = by - 5 if v >= 0 else by + bh + 13
                        svg.append(f'<text x="{bx + bw / 2:.0f}" y="{ly:.0f}" text-anchor="middle" font-size="11" font-weight="700" '
                                   f'fill="#202945">{_num(v, s["labels"])}</text>')
            svg.append(f'<line x1="{left}" x2="{W}" y1="{zero:.0f}" y2="{zero:.0f}" stroke="#A6A9B5"/>')
    elif kind in ("lineChart", "scatterChart") and ser:
        labels = None
        try:
            [float(x) for s in ser for x in s["cat"] if x not in (None, "")]
        except ValueError:                               # text categories: plot by position, label below
            labels = list(ser[0]["cat"])
            for s in ser:
                s["cat"] = [str(i) for i in range(len(s["cat"]))]
        xs_all = [float(x) for s in ser for x in s["cat"] if x not in (None, "")]
        ys_all = [v for s in ser for v in s["val"] if v is not None]
        if xs_all and ys_all:
            x0, x1, y0, y1 = min(xs_all), max(xs_all), min(ys_all), max(ys_all)
            pad = (y1 - y0) * 0.08 or 1
            y0, y1 = y0 - pad, y1 + pad
            left, right, top, bottom = 46, W - 10, 8, H - 56
            fx = lambda x: left + (x - x0) / ((x1 - x0) or 1) * (right - left)
            fy = lambda y: bottom - (y - y0) / ((y1 - y0) or 1) * (bottom - top)
            for t in range(5):
                yv = y0 + (y1 - y0) * t / 4
                label = f"{yv:.0%}" if kind == "scatterChart" else (f"{yv:.0f}" if abs(y1 - y0) > 5 else f"{yv:.3g}")
                svg.append(f'<line x1="{left}" x2="{right:.0f}" y1="{fy(yv):.0f}" y2="{fy(yv):.0f}" stroke="#E3E5EB"/>'
                           f'<text x="{left - 4}" y="{fy(yv) + 4:.0f}" text-anchor="end" font-size="10" fill="#8C8C8C">{label}</text>')
            for s in ser:
                pts, segs = [], []
                for x, y in zip(s["cat"], s["val"]):
                    if y is None or x in (None, ""):
                        if pts:
                            segs.append(pts)
                        pts = []
                        continue
                    pts.append(f"{fx(float(x)):.1f},{fy(y):.1f}")
                if pts:
                    segs.append(pts)
                for seg in segs:
                    svg.append(f'<polyline points="{" ".join(seg)}" fill="none" stroke="{s["color"]}" stroke-width="2"'
                               f'{" stroke-dasharray=\"6 4\"" if s["dash"] else ""}/>')
                    if labels is not None:
                        svg += [f'<circle cx="{pt.split(",")[0]}" cy="{pt.split(",")[1]}" r="4" fill="{s["color"]}"/>' for pt in seg]
            if labels is not None:
                for i, lab in enumerate(labels):
                    svg.append(f'<text x="{fx(i):.0f}" y="{bottom + 16:.0f}" text-anchor="middle" font-size="10" fill="#8C8C8C">'
                               f'{escape(str(lab))[:12]}</text>')
            # legend
            lx = left
            for s in ser:
                svg.append(f'<rect x="{lx:.0f}" y="{H - 22:.0f}" width="12" height="4" fill="{s["color"]}"/>'
                           f'<text x="{lx + 16:.0f}" y="{H - 16:.0f}" font-size="10" fill="#202945">{escape(s["name"])}</text>')
                lx += 24 + len(s["name"]) * 6
    svg.append("</svg>")
    return "".join(svg)


def html(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    slides = sorted((n for n in parts if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
    pages = []
    for k, n in enumerate(slides, start=1):
        root = ET.fromstring(parts[n])
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(parts[n.replace("slides/", "slides/_rels/") + ".rels"])}
        layout_file = next(t for t in rels.values() if "slideLayout" in t)
        layout_xml = parts["ppt/slideLayouts/" + layout_file.split("/")[-1]].decode("utf-8")
        layout = re.search(r'<p:cSld name="([^"]*)"', layout_xml).group(1).strip()
        items = []
        if layout in PANEL:
            x, y, w, h = PANEL[layout]
            items.append(f'<div class="box" style="left:{_px(x)};top:0;width:{_px(w)};height:100%;background:linear-gradient(135deg,#FFA400,#FF6C0E)"></div>')
        if layout in ("Disclaimer (general)", "1_Final page - with Offices", "Final page - Orange", "Final page - blank"):
            bg = "background:linear-gradient(110deg,#FF6C0E,#FFA400 60%,#FFE9C2);color:#fff;height:100%;top:0;left:0;width:100%;padding:40% 0 0 20%;font-size:34pt;font-weight:700" \
                if layout == "Final page - Orange" else f"left:{_px(0.73)};top:{_px(1.2)};width:{_px(10)}"
            label = "Welcome to Syzerland" if layout == "Final page - Orange" else f"[{escape(layout)}: the template page itself, with its own text]"
            items.append(f'<div class="box note" style="{bg}">{label}</div>')
        for el in root.find(f"{P}cSld/{P}spTree"):
            if el.tag == P + "pic":
                blip = el.find(f".//{A}blip")
                target = rels.get(blip.get(R + "embed")) if blip is not None else None
                part = "ppt/" + target.replace("../", "") if target else None
                g = _geom(el) or PANEL.get(layout)
                if part in parts and g:
                    mime = "image/png" if part.endswith(".png") else "image/jpeg"
                    data = base64.b64encode(parts[part]).decode()
                    size = "cover" if _geom(el) is None else "100% 100%"     # a placeholder photo fills its panel
                    items.append(f'<div class="box" style="left:{_px(g[0])};top:{_px(g[1])};width:{_px(g[2])};height:{_px(g[3])};'
                                 f'background:url(data:{mime};base64,{data}) center/{size} no-repeat"></div>')
                continue
            if el.tag == P + "sp":
                items.append(_shape_html(el, layout))
            elif el.tag == P + "graphicFrame":
                if el.find(f".//{A}tbl") is not None:
                    items.append(_table_html(el))
                else:
                    rid = el.find(f".//{C}chart").get(R + "id")
                    chart = ET.fromstring(parts["ppt/charts/" + rels[rid].split("/")[-1]])
                    x, y, w, h = _geom(el)
                    items.append(f'<div class="box" style="left:{_px(x)};top:{_px(y)};width:{_px(w)};height:{_px(h)}">{_chart_svg(chart, w, h)}</div>')
        if layout not in ("Cover Slide 2", "Agenda", "Disclaimer (general)", "1_Final page - with Offices",
                          "Final page - Orange", "Final page - blank"):
            items.append(f'<div class="box logo" style="left:{_px(11.01)};top:{_px(0.43)};width:{_px(0.47)};height:{_px(0.42)}">SYZ</div>'
                         f'<div class="box foot" style="left:{_px(0.73)};top:{_px(7.76)};width:{_px(10)}">Please see important information at the end of the document</div>'
                         f'<div class="box foot" style="left:{_px(11.11)};top:{_px(7.76)};width:{_px(0.3)}">{k}</div>')
        pages.append(f'<section class="slide" id="s{k}" data-layout="{escape(layout)}">{"".join(items)}</section>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Deck preview</title><style>
body{{margin:0;background:#E9EBF0;font-family:'Open Sans',sans-serif;color:#202945}}
.slide{{position:relative;width:{_px(PAGE_W)};height:{_px(PAGE_H)};background:#fff;margin:24px auto;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.2);font-family:'Open Sans',sans-serif;color:#202945}}
.box{{position:absolute;box-sizing:border-box;overflow:visible}}
.box div{{line-height:1.3}}
.tbl{{position:absolute;border-collapse:collapse;table-layout:fixed}}
.tbl td{{padding:0.02in 0.08in 0.02in 0.1in;vertical-align:middle;overflow:hidden}}
.tbl td div{{line-height:1.25}}
.frame{{position:absolute;outline:1px dashed rgba(255,0,0,.35);pointer-events:none}}
.logo{{border:1px solid #202945;font:700 9px 'Open Sans';text-align:center;line-height:40px}}
.foot{{font-size:8pt;color:#8C8C8C}}
.note{{font-size:12pt;color:#8C8C8C}}
</style></head><body>{"".join(pages)}</body></html>"""


def write(path: Path, out: Path | None = None) -> Path:
    out = out or path.with_suffix(".preview.html")
    out.write_text(html(path), encoding="utf-8")
    return out
