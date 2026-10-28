"""Proposal charts: every product's basket against its strike and barrier.

Reads a proposal sheet (CSV: Basket, Underlying 1-3, Coupon, Downside protection, Maturity,
Weight, Fees, Stepdown, Size), loads five years of closes from Yahoo Finance and writes one
self-contained HTML page: an overview of every product's buffer, then per product the basket
rebased to 100 at today's close with the strike and barrier drawn across, and a table of
each underlying's price, strike and barrier levels.

    .\\.venv\\Scripts\\python apps\\G01\\G01_proposal.py docs\\Proposal.csv --open

Also shipped in the syz-proposal-charts skill (G01_package_skill.py) as scripts/proposal_charts.py,
next to a copy of the syz_advisory modules it needs.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGED = (HERE / "syz_advisory").is_dir()          # inside the skill: the modules sit beside this file
if PACKAGED:
    # the skill folder is read-only on claude.ai: cache and working files go to a temp folder
    os.environ.setdefault("SYZ_DATA", str(Path(tempfile.gettempdir()) / "syz-proposal-charts"))
    sys.path.insert(0, str(HERE))
else:
    sys.path.insert(0, str(HERE.parents[1] / "src"))

from syz_advisory import brand, config, pdflayout, pdfwriter  # noqa: E402
from syz_advisory.marketdata import YahooClient  # noqa: E402
from syz_advisory.structuring import proposal  # noqa: E402

P = brand.PALETTE
SERIES = [P["tiger_orange"], P["blueberry_blue"], P["mint_green"], P["gold_yellow"], P["sky_blue"]]
BARRIER = P["mulberry_pink"]
ZONE = brand.flatten(P["mulberry_pink"], 0.12)
GRID, AXIS, MUTED = pdflayout.GRID, pdflayout.AXIS, pdflayout.MUTED

# chart geometry (SVG user units)
W, H, L, R, T, B = 760, 300, 46, 150, 12, 26


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def pct(x, d=0, sign=False) -> str:
    if x is None:
        return "–"
    return f"{x:+.{d}%}" if sign else f"{x:.{d}%}"


def price(x) -> str:
    if x is None:
        return "–"
    return f"{x:,.2f}" if x < 10_000 else f"{x:,.0f}"


# House fonts: Nunito Sans for text, Nunito Bold for titles (the PDFs embed the same pair).
TEXT_FONT = "'Nunito Sans', 'Nunito', Lato, Calibri, Arial, sans-serif"
TITLE_FONT = "'Nunito', 'Nunito Sans', Lato, Calibri, Arial, sans-serif"
SYMBOL = {"EUR": "€", "USD": "$", "GBP": "£"}


def money(x, ccy: str | None = None, short: bool = False) -> str:
    """A size in its own currency (€ when the sheet gives none); `short` gives 2.4m."""
    if not x:
        return "–"
    unit = SYMBOL.get(ccy, ccy) if ccy else "€"
    return f"{unit} {x / 1e6:.1f}m" if short else f"{unit} {x:,.0f}"


def total_size(data: dict) -> tuple[str, str]:
    """(KPI value, label): one figure when the proposal is in one currency, else one per currency."""
    by_ccy = data.get("size_by_ccy") or {}
    if len(by_ccy) <= 1:
        return money(data["total_size"], next(iter(by_ccy), None)), "Proposal size"
    return f"{len(by_ccy)} currencies", "Size: " + " · ".join(money(v, c, short=True) for c, v in by_ccy.items())


def tenor(p: dict, unit: str = " m") -> str:
    return f"{p['tenor_months']}{unit}" if p.get("tenor_months") else ""


def _nice_step(span: float) -> int:
    for s in (5, 10, 20, 25, 50):
        if span / s <= 7:
            return s
    return 100


def _month(d: str) -> str:
    return date.fromisoformat(d).strftime("%b %y")


def chart_range(lines: list[list[float]], level: float) -> tuple[float, float, float]:
    """(low, high, grid step) of a chart's y axis: every line, today and the protection level."""
    flat = [v for ln in lines for v in ln]
    step = _nice_step(max(flat + [105]) - min(flat + [level - 5]))
    return step * (min(flat + [level - 5]) // step), step * -(-max(flat + [105]) // step), step


def level_labels(p: dict) -> list[tuple[float, str, bool, str]]:
    """The key levels drawn across a chart: (level, colour, dashed, label)."""
    prot = p["protection"]
    strike, barrier = prot["strike"] * 100, (prot["barrier"] or 0) * 100
    if prot["kind"] == "barrier":
        return [(100, brand.INK, False, f"Today = strike {strike:.0f}"),
                (barrier, BARRIER, True, f"{(prot['barrier_type'] or '').title()} barrier {barrier:.0f}".strip())]
    return [(100, brand.INK, False, "Today 100"),
            (strike, BARRIER, True, f"Strike {strike:.0f}" + (" (protection)" if prot["kind"] == "low_strike" else ""))]


def chart_svg(p: dict, key: str, cid: str) -> tuple[str, dict]:
    """The basket over one window, rebased to 100 today, with the protection zone and levels."""
    win = p["windows"][key]
    lines, dates = win["lines"], win["dates"]
    level = p["level"] * 100
    lo, hi, step = chart_range(lines, level)
    n = len(dates)
    x = lambda i: L + (W - L - R) * (i / max(n - 1, 1))            # noqa: E731
    y = lambda v: T + (H - T - B) * (hi - v) / (hi - lo)              # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" id="{cid}" role="img" '
           f'aria-label="{esc(" / ".join(m["name"] for m in p["members"]))}, {key}, rebased to 100 today">']
    # protection zone: below the barrier, or below a low strike
    out.append(f'<rect x="{L}" y="{y(level):.1f}" width="{W - L - R}" height="{y(lo) - y(level):.1f}" fill="{ZONE}"/>')
    v = lo
    while v <= hi + 1e-9:
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{GRID}"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" class="ax" text-anchor="end">{v:g}</text>')
        v += step
    ticks = max(1, (n - 1) // 6)
    for i in range(0, n - ticks // 2, ticks):
        out.append(f'<text x="{x(i):.1f}" y="{H - 6}" class="ax" text-anchor="middle">{_month(dates[i])}</text>')
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{H - B}" y2="{H - B}" stroke="{AXIS}"/>')

    # key levels, labelled in the right margin
    for val, col, dash, text in level_labels(p):
        dashed = ' stroke-dasharray="6 4"' if dash else ""
        out.append(f'<line x1="{L}" x2="{W - R + 6}" y1="{y(val):.1f}" y2="{y(val):.1f}" stroke="{col}" '
                   f'stroke-width="1.5"{dashed}/>'
                   f'<text x="{W - R + 10}" y="{y(val) + 4:.1f}" class="lvl" fill="{col}">{esc(text)}</text>')

    for j, ln in enumerate(lines):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(ln))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{SERIES[j % len(SERIES)]}" stroke-width="2" '
                   f'stroke-linejoin="round"/>')
    out.append(f'<circle cx="{x(n - 1):.1f}" cy="{y(100):.1f}" r="4" fill="{brand.INK}"/>')
    out.append(f'<g class="hover" visibility="hidden"><line class="hl" y1="{T}" y2="{H - B}" stroke="{AXIS}"/></g>')
    out.append(f'<rect class="hit" x="{L}" y="{T}" width="{W - L - R}" height="{H - T - B}" fill="transparent"/>')
    out.append("</svg>")
    meta = {"dates": dates, "lines": [[round(v, 2) for v in ln] for ln in lines], "x0": L, "x1": W - R,
            "names": [m["short"] for m in p["members"]]}
    return "".join(out), meta


def overview_svg(products: list[dict]) -> str:
    """One row per product: the protection level, and each underlying's 1-year low, as % of today."""
    rows = [p for p in products if p["members"]]
    lo = 10 * (min([p["level"] * 100 for p in rows] + [m["low_1y"] for p in rows for m in p["members"]
                                                      if m["low_1y"] is not None]) // 10) - 10
    lo = max(lo, 0)
    w, l, r, row = 760, 290, 20, 26
    h = 34 + row * len(rows)
    x = lambda v: l + (w - l - r) * (v - lo) / (100 - lo)            # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {h}" class="overview" role="img" aria-label="Buffers per product">']
    v = lo
    while v <= 100:
        out.append(f'<line x1="{x(v):.1f}" x2="{x(v):.1f}" y1="18" y2="{h - 4}" stroke="{GRID}"/>'
                   f'<text x="{x(v):.1f}" y="12" class="ax" text-anchor="middle">{v:g}%</text>')
        v += 10
    for k, p in enumerate(rows):
        cy = 30 + row * k
        lv = p["level"] * 100
        label = f'{p["no"]} · ' + " / ".join(m["short"] for m in p["members"])
        cut = label if len(label) <= 44 else label[:43].rstrip(" /") + "…"
        out.append(f'<a href="#p{p["no"]}"><text x="0" y="{cy + 4}" class="row">{esc(cut)}<title>{esc(label)}</title>'
                   f'</text></a>')
        out.append(f'<rect x="{x(lo):.1f}" y="{cy - 7}" width="{x(lv) - x(lo):.1f}" height="14" fill="{ZONE}"/>')
        out.append(f'<line x1="{x(lv):.1f}" x2="{x(100):.1f}" y1="{cy}" y2="{cy}" stroke="{AXIS}" stroke-width="1"/>')
        out.append(f'<line x1="{x(lv):.1f}" x2="{x(lv):.1f}" y1="{cy - 9}" y2="{cy + 9}" stroke="{BARRIER}" stroke-width="2.5">'
                   f'<title>{esc(p["protection"]["label"])}</title></line>')
        for j, m in enumerate(p["members"]):
            if m["low_1y"] is None:
                continue
            out.append(f'<circle cx="{x(m["low_1y"]):.1f}" cy="{cy}" r="4.5" fill="{SERIES[j % len(SERIES)]}" stroke="#fff">'
                       f'<title>{esc(m["name"])}: 1-year low {m["low_1y"]:.0f}% of today</title></circle>')
        out.append(f'<circle cx="{x(100):.1f}" cy="{cy}" r="4" fill="{brand.INK}"/>')
    out.append("</svg>")
    return "".join(out)


def member_table(p: dict) -> str:
    prot = p["protection"]
    has_barrier = prot["barrier"] is not None
    head = ["Underlying", "Last close", f"Strike ({prot['strike']:.0%})"]
    if has_barrier:
        head.append(f"Barrier ({prot['barrier']:.0%})")
    head += ["Fall to protection", "1-year low", "1-year change", "1-year vol"]
    body = []
    for j, m in enumerate(p["members"]):
        near = m["low_1y"] is not None and m["low_1y"] <= p["level"] * 100
        low = "–" if m["low_1y"] is None else f"{m['low_1y']:.0f}"
        cells = [f'<td><span class="sw" style="background:{SERIES[j % len(SERIES)]}"></span><b>{esc(m["name"])}</b> '
                 f'<small>{esc(m["yahoo"])}</small></td>',
                 f'<td class="num">{price(m["last"])} <small>{esc(m["currency"])}</small><br><small>{esc(m["last_date"])}</small></td>',
                 f'<td class="num">{price(m["strike_price"])}</td>']
        if has_barrier:
            cells.append(f'<td class="num">{price(m["barrier_price"])}</td>')
        cells += [f'<td class="num"><b>{pct(-m["buffer"], 0, True)}</b></td>',
                  f'<td class="num{" warn" if near else ""}">{low}<small> % of today</small></td>',
                  f'<td class="num">{pct(m["change_1y"], 1, True)}</td>',
                  f'<td class="num">{pct(m["vol_1y"], 0)}</td>']
        body.append("<tr>" + "".join(cells) + "</tr>")
    return ('<table class="members"><thead><tr>' +
            "".join(f'<th{" class=num" if i else ""}>{esc(h)}</th>' for i, h in enumerate(head)) +
            "</tr></thead><tbody>" + "".join(body) + "</tbody></table>")


def title_of(p: dict) -> str:
    return " / ".join(m["short"] for m in p["members"]) or " / ".join(p["names"])


def chips_of(p: dict) -> list[str]:
    # a list pasted in the chat may give only the baskets and protection: show what is there
    chips = [f"Coupon {pct(p['coupon'], 2)} p.a." if p["coupon"] is not None else None, p["protection"]["label"],
             tenor(p, " months") or None, f"Weight {pct(p['weight'])}" if p["weight"] is not None else None,
             money(p["size"], p.get("ccy")) if p["size"] else None, f"Fees {pct(p['fees'], 2)}" if p["fees"] is not None else None]
    chips = [c for c in chips if c]
    if p["stepdown"]:
        chips.append(f"Autocall step-down {p['stepdown']}")
    return chips


def reading_of(p: dict) -> str:
    """The protection in one plain sentence."""
    prot = p["protection"]
    if prot["kind"] == "barrier":
        when = "on the final date" if prot["barrier_type"] == "european" else "during the product's life"
        return (f"Capital is repaid in full at maturity unless the worst underlying closes below "
                f"{prot['barrier']:.0%} of today's level {when}; every name can fall "
                f"{1 - prot['barrier']:.0%} before the barrier is reached.")
    if prot["kind"] == "low_strike":
        return (f"No loss of capital unless the worst underlying ends below {prot['strike']:.0%} of today's "
                f"level; below it, the loss runs from the strike. Every name can fall {1 - prot['strike']:.0%} "
                f"before capital is at risk.")
    return ""


def product_card(p: dict, charts: dict) -> str:
    title, chips, reading = title_of(p), chips_of(p), reading_of(p)
    legend = "".join(f'<span><i style="background:{SERIES[j % len(SERIES)]}"></i>{esc(m["short"])}</span>'
                     for j, m in enumerate(p["members"]))
    svgs = []
    for key in proposal.WINDOWS:
        if key in p["windows"]:
            cid = f"c{p['no']}_{key}"
            svg, meta = chart_svg(p, key, cid)
            charts[cid] = meta
            short = "" if p["windows"][key]["full"] else '<p class="hint">Shorter common history than the period chosen.</p>'
            svgs.append(f'<div class="win w{key}">{svg}{short}</div>')
    missing = (f'<p class="hint warn">No price history found for: {esc(", ".join(p["missing"]))}.</p>'
               if p["missing"] else "")
    return (f'<section class="card product" id="p{p["no"]}">'
            f'<div class="head"><span class="no">{p["no"]}</span><h2>{esc(title)}</h2></div>'
            f'<div class="chips">{"".join(f"<span>{esc(c)}</span>" for c in chips)}</div>'
            f'<p class="reading">{esc(reading)}</p>{missing}'
            f'<div class="legend">{legend}<span class="readout" data-for="{p["no"]}"></span></div>'
            + "".join(svgs) + (member_table(p) if p["members"] else "") + "</section>")


CSS = """
:root{--ink:%(ink)s;--muted:%(muted)s;--rule:%(rule)s;--grid:%(grid)s;--warn:%(warn)s;--accent:%(accent)s}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font-family:%(font)s;font-weight:400;font-size:14px;line-height:1.45}
main{max-width:1000px;margin:0 auto;padding:28px 16px 60px}
h1,h2{font-family:%(title_font)s}
h1{font-weight:700;font-size:26px;margin:0 0 4px}h2{font-weight:700;font-size:17px;margin:0}
.sub,.hint,small{color:var(--muted)}small{font-size:11px}.hint{font-size:12px;margin:6px 0}
.bar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin:18px 0 10px}
.kpis{display:flex;flex-wrap:wrap;gap:28px;margin:18px 0}.kpis div b{display:block;font-size:22px;font-weight:700}
.kpis div span{font-size:12px;color:var(--muted);font-weight:300}
.seg{display:inline-flex;border:1px solid var(--rule);border-radius:6px;overflow:hidden}
.seg button{border:0;background:#fff;color:var(--ink);font:inherit;padding:5px 14px;cursor:pointer}
.seg button.on{background:var(--ink);color:#fff}
.card{border-top:2px solid var(--ink);padding:16px 0 24px;margin-top:18px}
.head{display:flex;align-items:center;gap:10px}
.no{display:inline-flex;align-items:center;justify-content:center;min-width:28px;height:28px;border-radius:14px;
  background:var(--ink);color:#fff;font-weight:700;font-size:13px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px}
.chips span{border:1px solid var(--rule);border-radius:12px;padding:1px 10px;font-size:12px}
.reading{margin:8px 0;font-weight:300}
.legend{display:flex;flex-wrap:wrap;gap:14px;align-items:center;font-size:12px;margin:6px 0 2px;min-height:20px}
.legend i{display:inline-block;width:14px;height:3px;margin-right:6px;vertical-align:middle}
.readout{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums}
svg{width:100%%;height:auto;display:block;font-family:%(font)s}
svg .ax{font-size:11px;fill:var(--muted);font-weight:300}svg .lvl{font-size:11.5px;font-weight:700}
svg .row{font-size:12px;fill:var(--ink)}svg a:hover .row{text-decoration:underline}
.win{display:none}body[data-w="1y"] .w1y,body[data-w="3y"] .w3y,body[data-w="5y"] .w5y{display:block}
table{border-collapse:collapse;width:100%%;font-size:12.5px;margin-top:10px}
th{text-align:left;font-weight:700;border-bottom:1px solid var(--rule);padding:6px 8px;white-space:nowrap}
td{border-bottom:1px solid var(--grid);padding:6px 8px;vertical-align:top}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.warn{color:var(--warn);font-weight:700}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.table-wrap{overflow-x:auto}.members{min-width:640px}.product .members{display:table}
.product{overflow-x:auto}
.key{display:flex;flex-wrap:wrap;gap:16px;font-size:12px;color:var(--muted);margin:4px 0}
.key i{display:inline-block;width:14px;height:10px;margin-right:6px;vertical-align:middle}
footer{margin-top:40px;font-size:11px;color:var(--muted);font-weight:300}
@media print{.seg{display:none}.card{break-inside:avoid}}
"""

JS = """
(function(){
  var C = JSON.parse(document.getElementById('chart-data').textContent);
  function setW(w){ document.body.dataset.w = w;
    document.querySelectorAll('.seg button').forEach(function(b){ b.classList.toggle('on', b.dataset.w === w); }); }
  document.querySelectorAll('.seg button').forEach(function(b){ b.addEventListener('click', function(){ setW(b.dataset.w); }); });
  document.querySelectorAll('svg.chart').forEach(function(svg){
    var m = C[svg.id], hit = svg.querySelector('.hit'), g = svg.querySelector('.hover'), hl = svg.querySelector('.hl');
    var out = svg.closest('.product').querySelector('.readout');
    function move(e){
      var pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
      var p = pt.matrixTransform(svg.getScreenCTM().inverse());
      var n = m.dates.length, i = Math.round((p.x - m.x0) / (m.x1 - m.x0) * (n - 1));
      i = Math.max(0, Math.min(n - 1, i));
      var x = m.x0 + (m.x1 - m.x0) * i / Math.max(n - 1, 1);
      hl.setAttribute('x1', x); hl.setAttribute('x2', x); g.setAttribute('visibility', 'visible');
      out.textContent = m.dates[i] + ':  ' + m.names.map(function(nm, j){ return nm + ' ' + m.lines[j][i].toFixed(1); }).join('  ·  ');
    }
    hit.addEventListener('mousemove', move);
    hit.addEventListener('mouseleave', function(){ g.setAttribute('visibility', 'hidden'); out.textContent = ''; });
  });
})();
"""


def render(data: dict) -> str:
    products = data["products"]
    charts: dict = {}
    cards = "".join(product_card(p, charts) for p in products)
    cash = data["cash"] or {}
    rows = []
    for p in products:
        lows = [m["low_1y"] for m in p["members"] if m["low_1y"] is not None]
        low = min(lows) if lows else None
        warn = low is not None and low <= p["level"] * 100
        rows.append(
            f'<tr><td><a href="#p{p["no"]}">{p["no"]}</a></td><td>{esc(" / ".join(p["names"]))}</td>'
            f'<td class="num">{pct(p["coupon"], 2)}</td><td>{esc(p["protection"]["label"])}</td>'
            f'<td class="num">{tenor(p) or "–"}</td><td class="num">{pct(p["weight"])}</td>'
            f'<td class="num">{money(p["size"], p.get("ccy"))}</td><td class="num"><b>{pct(-(1 - p["level"]), 0, True)}</b></td>'
            f'<td class="num{" warn" if warn else ""}">{"–" if low is None else f"{low:.0f}%"}</td></tr>')
    if cash:
        rows.append(f'<tr><td></td><td>Cash</td><td></td><td></td><td></td><td class="num">{pct(cash.get("weight"))}</td>'
                    f'<td class="num">{money(cash.get("size"), cash.get("ccy"))}</td><td></td><td></td></tr>')
    css = CSS % {"ink": brand.INK, "muted": MUTED, "rule": AXIS, "grid": GRID, "warn": BARRIER,
                 "accent": P["tiger_orange"], "font": TEXT_FONT, "title_font": TITLE_FONT}
    asof = data["asof"]
    blob = json.dumps(charts, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Structured Products Proposal</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@700&family=Nunito+Sans:wght@300;400;700&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body data-w="1y"><main>
<h1>Structured products proposal</h1>
<p class="sub">Each basket rebased to 100 at the latest close ({esc(asof)}), with its strike and barrier as a % of
today's level, as for a product struck today. Prices in each underlying's own currency.</p>
<div class="kpis">
  <div><b>{esc(total_size(data)[0])}</b><span>{esc(total_size(data)[1])}</span></div>
  <div><b>{len(products)}</b><span>Products</span></div>
  <div><b>{pct(data["coupon_invested"], 2)}</b><span>Average coupon p.a., invested part (weighted)</span></div>
  <div><b>{pct(data["coupon_total"], 2)}</b><span>Average coupon p.a., whole proposal incl. cash</span></div>
  <div><b>{pct(cash.get("weight"))}</b><span>Cash</span></div>
</div>

<section class="card"><h2>Distance to protection, all products</h2>
<p class="hint">Today = 100%. The pink tick is the level that protects capital (the barrier, or a low strike);
the shaded area is below it. Dots show each underlying's lowest close of the past year, as a % of today:
a dot inside the shaded area means that name was lower than the protection level at some point in the year.</p>
<div class="key"><span><i style="background:{ZONE};border-left:3px solid {BARRIER}"></i>Below protection level</span>
<span><i style="background:{brand.INK};border-radius:5px;width:10px"></i>Today</span>
<span>Dot colours follow each product's chart below</span></div>
{overview_svg(products)}
<div class="table-wrap"><table><thead><tr><th>#</th><th>Basket</th><th class="num">Coupon</th><th>Protection</th>
<th class="num">Tenor</th><th class="num">Weight</th><th class="num">Size</th><th class="num">Fall to protection</th>
<th class="num">Lowest 1y close</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
</section>

<div class="bar"><h2>Products</h2>
<div class="seg" role="group" aria-label="Period">
<button type="button" data-w="1y" class="on">1 year</button><button type="button" data-w="3y">3 years</button>
<button type="button" data-w="5y">5 years</button></div></div>
<p class="hint">Lines show where each underlying stood against today's level: a point at 120 means the price was 20% higher
than today. Hover a chart for the values on a date.</p>
{cards}
<footer>Source: Yahoo Finance daily closes, not adjusted for dividends, as of {esc(asof)}. Levels assume each product is
struck at the latest close; the final strike and barrier are fixed on the trade date. Past performance is not a reliable
indicator of future results. For discussion purposes only; not an offer. Built from {esc(data["source"])}
on {date.today().isoformat()}.</footer>
</main>
<script type="application/json" id="chart-data">{blob}</script>
<script>{JS}</script>
</body></html>
"""


# --- PDF: one file per period, A4 portrait, two products per page -------------------------
M = 40                                   # page margin (pt)
PERIOD = {"1y": "1 year", "3y": "3 years", "5y": "5 years"}
SHORT = {"1y": "1-year", "3y": "3-year", "5y": "5-year"}


def _pdf_chart(pg, p: dict, key: str, x0: float, y0: float, w: float, h: float) -> None:
    win = p["windows"][key]
    lines, dates = win["lines"], win["dates"]
    level = p["level"] * 100
    lo, hi, step = chart_range(lines, level)
    left, right, bottom = x0 + 26, x0 + w - 104, y0 + h - 14
    n = len(dates)
    x = lambda i: left + (right - left) * i / max(n - 1, 1)              # noqa: E731
    y = lambda v: y0 + (bottom - y0) * (hi - v) / (hi - lo)             # noqa: E731
    pg.rect(left, y(level), right - left, y(lo) - y(level), fill=ZONE)
    v = lo
    while v <= hi + 1e-9:
        pg.line(left, y(v), right, y(v), GRID, 0.5)
        pg.text(left - 4, y(v) + 2.5, f"{v:g}", 6.5, colour=MUTED, anchor="end")
        v += step
    ticks = max(1, (n - 1) // 6)
    for i in range(0, n - ticks // 2, ticks):
        pg.text(x(i), y0 + h - 3, _month(dates[i]), 6.5, colour=MUTED, anchor="middle")
    pg.line(left, bottom, right, bottom, AXIS, 0.6)
    for val, col, dash, text in level_labels(p):
        pg.line(left, y(val), right + 4, y(val), col, 1.1, [4, 3] if dash else None)
        pg.text(right + 7, y(val) + 2.5, text, 7, bold=True, colour=col)
    for j, ln in enumerate(lines):
        pg.polyline([(x(i), y(v)) for i, v in enumerate(ln)], SERIES[j % len(SERIES)], 1.3)
    pg.circle(x(n - 1), y(100), 2.8, fill=brand.INK)


_pdf_table = pdflayout.table                 # shared with P02's technical reviews


def _pdf_overview(pg, products: list[dict], key: str, y: float) -> float:
    rows = [p for p in products if p["members"]]
    lows = [m["lows"][key] for p in rows for m in p["members"]]
    lo = max(0, 10 * (min(lows + [p["level"] * 100 for p in rows]) // 10) - 10)
    left, right, row = M + 178, M + pdfwriter.A4[0] - 2 * M - 6, 19
    x = lambda v: left + (right - left) * (v - lo) / (100 - lo)          # noqa: E731
    h = 14 + row * len(rows)
    v = lo
    while v <= 100:
        pg.line(x(v), y + 8, x(v), y + h, GRID, 0.5)
        pg.text(x(v), y + 5, f"{v:g}%", 6.5, colour=MUTED, anchor="middle")
        v += 10
    for k, p in enumerate(rows):
        cy = y + 20 + row * k
        lv = p["level"] * 100
        pg.text(M, cy + 2.5, pg.fit(f"{p['no']}  " + " / ".join(m["short"] for m in p["members"]), 7.5, 172), 7.5)
        pg.rect(x(lo), cy - 5.5, x(lv) - x(lo), 11, fill=ZONE)
        pg.line(x(lv), cy, x(100), cy, AXIS, 0.6)
        pg.line(x(lv), cy - 7, x(lv), cy + 7, BARRIER, 2)
        for j, m in enumerate(p["members"]):
            pg.circle(x(m["lows"][key]), cy, 3.4, fill=SERIES[j % len(SERIES)], stroke="#FFFFFF", width=0.8)
        pg.circle(x(100), cy, 3, fill=brand.INK)
    return y + h + 6


def render_pdf(data: dict, key: str, path: Path) -> Path:
    """The proposal for one chart period as an A4 PDF: overview, summary table, two products per page."""
    doc = pdfwriter.Document(f"Structured products proposal - {PERIOD[key]}")
    pw, ph = pdfwriter.A4
    cw, bottom = pw - 2 * M, ph - 44
    products, cash, asof = data["products"], data["cash"] or {}, data["asof"]
    state = {"pg": doc.page(), "y": 48.0}

    def room(h: float) -> None:
        if state["y"] + h > bottom:
            state["pg"], state["y"] = doc.page(), 48.0

    def para(text: str, size=8.0, colour=MUTED, bold=False, gap=1.4) -> None:
        for line in state["pg"].wrap(text, size, cw, bold):
            state["y"] += size * gap
            state["pg"].text(M, state["y"], line, size, bold, colour)

    pg = state["pg"]
    pg.text(M, 66, "Structured products proposal", 20, True, brand.INK)
    pg.text(M, 84, f"{PERIOD[key].capitalize()} of history  ·  prices as of {asof}", 10, True, P["tiger_orange"])
    state["y"] = 90
    para("Each basket rebased to 100 at the latest close, with its strike and barrier as a % of today's level, "
         "as for a product struck today. Prices in each underlying's own currency.", 8)
    y = state["y"] + 26
    kpis = [total_size(data), (str(len(products)), "Products"),
            (pct(data["coupon_invested"], 2), "Average coupon p.a., invested part"),
            (pct(data["coupon_total"], 2), "Average coupon p.a., incl. cash"), (pct(cash.get("weight")), "Cash")]
    for i, (v, label) in enumerate(kpis):
        kx = M + i * cw / 5
        pg.text(kx, y, v, 13, True, brand.INK)
        for k, line in enumerate(pg.wrap(label, 7, cw / 5 - 8)):
            pg.text(kx, y + 11 + 8.5 * k, line, 7, colour=MUTED)
    state["y"] = y + 36
    pg.line(M, state["y"], M + cw, state["y"], brand.INK, 1.2)
    state["y"] += 18
    pg.text(M, state["y"], "Distance to protection, all products", 12, True, brand.INK)
    para(f"Today = 100%. The pink tick is the level that protects capital (the barrier, or a low strike); the shaded "
         f"area is below it. Dots show each underlying's lowest close over the past {PERIOD[key]}, as a % of today: "
         f"a dot inside the shaded area means that name was lower than the protection level at some point.", 7.5)
    state["y"] = _pdf_overview(pg, products, key, state["y"] + 10)

    # summary table
    cols = [("#", 16, "start"), ("Basket", 138, "start"), ("Coupon", 38, "end"), ("Protection", 88, "start"),
            ("Tenor", 32, "end"), ("Weight", 36, "end"), ("Size", 68, "end"),       # room for "CHF 2,000,000"
            ("Fall to\nprotection", 48, "end"), (f"Lowest close\n{PERIOD[key]}", cw - 464, "end")]
    rows = []
    for p in products:
        low = min((m["lows"][key] for m in p["members"]), default=None)
        warn = low is not None and low <= p["level"] * 100
        rows.append([str(p["no"]), title_of(p), pct(p["coupon"], 2), p["protection"]["label"], tenor(p) or "–",
                     pct(p["weight"]), money(p["size"], p.get("ccy")), (pct(-(1 - p["level"]), 0, True), None, True),
                     ("–" if low is None else f"{low:.0f}%", BARRIER if warn else None, warn)])
    if cash:
        rows.append(["", "Cash", "", "", "", pct(cash.get("weight")), money(cash.get("size"), cash.get("ccy")), "", ""])
    room(24 + 13 * len(rows))
    state["y"] = _pdf_table(state["pg"], M, state["y"] + 6, cols, rows) + 10

    # products
    for p in products:
        if not p["members"] or key not in p["windows"]:
            continue
        reading = state["pg"].wrap(reading_of(p), 7.8, cw)
        n_rows = len(p["members"])
        need = 26 + 20 + 10 * len(reading) + 14 + 178 + 26 + 21 * n_rows + 18
        room(need)
        pg, y = state["pg"], state["y"] + 6
        pg.line(M, y, M + cw, y, brand.INK, 1.2)
        y += 18
        pg.circle(M + 9, y - 4, 9, fill=brand.INK)
        pg.text(M + 9, y - 1, str(p["no"]), 8, True, "#FFFFFF", "middle")
        pg.text(M + 24, y, pg.fit(title_of(p), 12, cw - 24, True), 12, True, brand.INK)
        y += 10
        cx = M
        for chip in chips_of(p):
            w = pg.width(chip, 7) + 12
            if cx + w > M + cw:
                cx, y = M, y + 16
            pg.rect(cx, y, w, 12, stroke=AXIS, width=0.6, radius=6)
            pg.text(cx + 6, y + 8.5, chip, 7, colour=brand.INK)
            cx += w + 4
        y += 16
        for line in reading:
            y += 10
            pg.text(M, y, line, 7.8, colour=brand.INK)
        if p["missing"]:
            y += 10
            pg.text(M, y, f"No price history found for: {', '.join(p['missing'])}.", 7.5, True, BARRIER)
        y += 14
        lx = M
        for j, m in enumerate(p["members"]):
            pg.line(lx, y - 2.5, lx + 12, y - 2.5, SERIES[j % len(SERIES)], 2)
            lx += 16 + pg.text(lx + 16, y, m["short"], 7.5, colour=brand.INK) + 14
        y += 12
        _pdf_chart(pg, p, key, M, y, cw, 170)
        y += 176
        prot = p["protection"]
        cols = [("Last close", 72, "end"), (f"Strike\n({prot['strike']:.0%})", 52, "end")]
        if prot["barrier"] is not None:
            cols.append((f"Barrier\n({prot['barrier']:.0%})", 52, "end"))
        cols += [("Fall to\nprotection", 52, "end"), (f"{SHORT[key].capitalize()} low\n(% of today)", 62, "end"),
                 (f"{SHORT[key].capitalize()}\nchange", 48, "end"), ("1-year\nvol", 40, "end")]
        cols.insert(0, ("Underlying", cw - sum(c[1] for c in cols), "start"))
        rows = []
        for m in p["members"]:
            low = m["lows"][key]
            warn = low <= p["level"] * 100
            r = [(m["name"], None, True, m["yahoo"]), (f"{price(m['last'])} {m['currency']}", None, False, m["last_date"]),
                 price(m["strike_price"])]
            if prot["barrier"] is not None:
                r.append(price(m["barrier_price"]))
            r += [(pct(-m["buffer"], 0, True), None, True), (f"{low:.0f}", BARRIER if warn else None, warn),
                  pct(m["changes"][key], 1, True), pct(m["vol_1y"], 0)]
            rows.append(r)
        y = _pdf_table(pg, M, y, cols, rows, row_h=21)
        for j in range(len(rows)):                               # colour key in front of each name
            pg.rect(M - 7, y - 21 * (len(rows) - j) + 4, 4, 9, fill=SERIES[j % len(SERIES)])
        state["y"] = y + 8

    room(60)
    state["y"] += 10
    para(f"Source: Yahoo Finance daily closes, not adjusted for dividends, as of {asof}. Levels assume each product "
         f"is struck at the latest close; the final strike and barrier are fixed on the trade date. Past performance "
         f"is not a reliable indicator of future results. For discussion purposes only; not an offer.", 6.8)
    for i, page in enumerate(doc.pages, 1):
        page.text(M, ph - 22, f"SYZ  ·  Structured products proposal  ·  {PERIOD[key]} of history  ·  {asof}", 6.5,
                  colour=MUTED)
        page.text(pw - M, ph - 22, f"{i} / {len(doc.pages)}", 6.5, colour=MUTED, anchor="end")
    return doc.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv", nargs="?", type=Path, default=config.inputs("G01") / "Proposal.csv",
                        help="proposal sheet (default data/G01/in/Proposal.csv)")
    parser.add_argument("--out", type=Path, help="HTML file to write (default data/G01/out/G01_proposal_<date>.html)")
    parser.add_argument("--out-dir", type=Path, help="folder for the page and PDFs, named G01_proposal_<date>*")
    parser.add_argument("--tickers", type=Path, metavar="FILE",
                        help='checked symbols that win over matching: JSON {"SHEET NAME": "SYMBOL"} or a 2-column CSV')
    parser.add_argument("--offline", action="store_true", help="use cached market data only")
    parser.add_argument("--pdf", nargs="?", const="1y,3y", metavar="PERIODS",
                        help="also write one PDF per period, next to the page (default 1y,3y; 5y too)")
    parser.add_argument("--open", action="store_true", help="open the page (and PDFs) when done")
    args = parser.parse_args()
    if not args.csv.is_file():
        parser.error(f"no proposal sheet at {args.csv}")

    client = YahooClient(offline=args.offline)
    try:   # the Core List matcher, in the workspace; Yahoo's search alone elsewhere
        from syz_advisory.structuring import service
        service._universe()
        service._client = client              # the matcher's Yahoo searches use the same client
        matcher, how = service.match, "Core List, index codes, then Yahoo search"
    except Exception:
        matcher, how = proposal.search_matcher(client), "Yahoo search"
    tickers = proposal.read_tickers(args.tickers) if args.tickers else None
    print(f"Names matched by: {'tickers file, ' if tickers else ''}built-in table, {how}")
    data = proposal.build(args.csv, client, matcher, tickers)
    for name, hit in data["matches"].items():
        print(f"  {name:<26} -> {hit.get('yahoo') or '?':<10} ({hit.get('how')})")
    for p in data["products"]:
        if p["missing"]:
            print(f"  WARNING product {p['no']}: no prices for {', '.join(p['missing'])}")
    stem = f"G01_proposal_{data['asof'] or date.today().isoformat()}.html"
    out_dir = args.out_dir or (Path("/mnt/user-data/outputs") if PACKAGED and Path("/mnt/user-data/outputs").is_dir()
                               else config.outputs("G01"))
    out = args.out or out_dir / stem
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data), encoding="utf-8")
    print(f"Wrote {out}")
    written = [out]
    for key in [k.strip() for k in (args.pdf or "").split(",") if k.strip()]:
        if key not in proposal.WINDOWS:
            parser.error(f"--pdf: unknown period {key!r} (use {', '.join(proposal.WINDOWS)})")
        try:
            written.append(render_pdf(data, key, out.with_name(f"{out.stem}_{key}.pdf")))
        except PermissionError as exc:
            sys.exit(f"Cannot write {exc.filename}: close it in the PDF viewer and run again.")
        print(f"Wrote {written[-1]}")
    if args.open and hasattr(os, "startfile"):
        for f in written:
            os.startfile(f)  # noqa: S606 -- Windows only


if __name__ == "__main__":
    main()
