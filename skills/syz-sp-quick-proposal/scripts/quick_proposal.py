"""Quick structured products proposal: a basket sheet in, a short SYZ PDF out.

    python scripts/quick_proposal.py <sheet.xlsx|.csv> [options]

Page 1: headline figures and one row per basket (theme, names, coupon, protection, tenor, amount, a
gauge with each name's lowest close of the past year against the protection). Up to 8 baskets the
rows are airy; above 8 they become one line each, so about 18 baskets still fit on the page.
Then two baskets per page: one-year chart rebased to 100 today, protection line, and a table per
underlying (Bloomberg code, last close, protection price, 1y low, 1y change, volatility).

Options:
  --tickers FILE   checked symbols, {"NAME AS WRITTEN": "YAHOO"}
  --themes FILE    basket themes, {"1": "Global equity core", ...} (numbers as in the sheet)
  --title TEXT     page-1 title (default: "<N> thematic baskets")
  --currency CCY   product currency when the sheet does not say (default EUR)
  --asof DATE      price date YYYY-MM-DD (default today)
  --out FILE       the PDF (default /mnt/user-data/outputs on claude.ai, else ./out)
  --offline        cached prices only
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import math
import re
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
sys.path.insert(0, str(HERE))

from syzdeck import ingest, market  # noqa: E402
from syzdeck.model import Product, Underlying  # noqa: E402
from syzdeck.names import INDICES, CoreList  # noqa: E402

INK, ORANGE, BLUE, MUL, MINT, RED, GREY = "#202945", "#FF6C0E", "#4B5F80", "#AC5D85", "#3BAF90", "#C62828", "#8A8FA0"
LINE = [ORANGE, BLUE, MINT, "#FFC545", "#79D6FF"]
WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
         11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen", 16: "Sixteen", 17: "Seventeen",
         18: "Eighteen", 19: "Nineteen", 20: "Twenty"}
CCY_SIGN = {"€": "EUR", "$": "USD", "£": "GBP", "CHF": "CHF", "EUR": "EUR", "USD": "USD", "GBP": "GBP"}
BBG_INDEX = {"^N225": "NKY Index", "^STOXX50E": "SX5E Index", "^GSPC": "SPX Index", "^SSMI": "SMI Index", "^GDAXI": "DAX Index",
             "^FCHI": "CAC Index", "^FTSE": "UKX Index", "^HSI": "HSI Index", "^OMX": "OMX Index", "^NDX": "NDX Index", "^RUT": "RTY Index"}
BBG_SUFFIX = {".AS": "NA", ".SW": "SW", ".PA": "FP", ".DE": "GY", ".L": "LN", ".MI": "IM", ".MC": "SM", ".T": "JT",
              ".HK": "HK", ".ST": "SS", ".AX": "AT", ".BR": "BB", ".CO": "DC", ".OL": "NO", ".HE": "FH", ".LS": "PL", ".TO": "CN"}
US_EXCH = {"NMS": "UW", "NGM": "UQ", "NCM": "UR", "NYQ": "UN", "PCX": "UP", "ASE": "UA", "BTS": "UF"}


# ---------------------------------------------------------------------------------------------
# reading the sheet

def read_sheet(path: Path, default_ccy: str) -> tuple[list[dict], str]:
    rows = ingest._rows(path)
    head_i = next((i for i, r in enumerate(rows) if r and str(r[0] or "").strip().lower() in ("basket", "product", "#")), None)
    if head_i is None:
        raise SystemExit(f"{path.name}: no header row starting with 'Basket'")
    header = [str(c or "").strip() for c in rows[head_i]]
    col = lambda *keys: next((j for j, h in enumerate(header) if any(h.lower().startswith(k) for k in keys)), None)
    under = [j for j, h in enumerate(header) if re.match(r"(?i)^(underlying|sous-jacent)\s*\d*$", h)]
    c_cp, c_pr, c_mt, c_fe = col("coupon"), col("downside", "protection", "strike", "barrier"), col("maturity", "tenor"), col("fee")
    c_am, c_th, c_cc, c_w = col("amount", "size", "montant", "nominal"), col("theme"), col("currency", "ccy"), col("weight")
    ccy = default_ccy
    if c_am is not None:
        m = re.search(r"\((.+?)\)", header[c_am])
        ccy = CCY_SIGN.get(m.group(1).strip(), ccy) if m else ccy
    baskets = []
    for r in rows[head_i + 1:]:
        if not r or not re.match(r"^\d+(\.0)?$", str(r[0] or "").strip()):
            continue
        get = lambda j: r[j] if j is not None and j < len(r) else None
        names = [str(r[j]).strip() for j in under if j < len(r) and r[j] not in (None, "")]
        prot_txt = str(get(c_pr) or "")
        kind = "European barrier" if re.search(r"(?i)barri", prot_txt) and not re.search(r"(?i)american", prot_txt) else \
            "American barrier" if re.search(r"(?i)american", prot_txt) else "Low strike" if re.search(r"(?i)strike", prot_txt) else "Protection"
        amount = get(c_am)
        if isinstance(amount, str):
            amount = float(re.sub(r"[^\d.]", "", amount.replace("’", "").replace(",", "")) or 0)
        baskets.append({
            "sheet_n": int(float(str(r[0]))), "names_raw": names, "coupon": ingest._pct(get(c_cp)),
            "strike": ingest._pct(get(c_pr)), "kind": kind, "tenor": ingest._months(get(c_mt)),
            "fees": ingest._pct(get(c_fe)), "amount": float(amount) if amount else None,
            "weight": ingest._pct(get(c_w)), "theme": str(get(c_th)).strip() if get(c_th) else None,
            "ccy": str(get(c_cc)).strip().upper() if get(c_cc) else ccy})
    if not baskets:
        raise SystemExit(f"{path.name}: no basket rows under the header")
    return baskets, ccy


# ---------------------------------------------------------------------------------------------
# market data per underlying

def series(symbols, asof):
    px = market.closes(sorted(set(symbols)), asof)
    start = (asof - dt.timedelta(days=365)).isoformat()
    P = {}
    for s in symbols:
        ser = [(d, c) for d, c in px.get(s, []) if start <= d <= asof.isoformat()]
        if len(ser) < 40:
            print(f"     WARNING no prices for {s}: left out of the charts")
            continue
        closes = [c for _, c in ser]
        last = closes[-1]
        rets = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0]
        mean = sum(rets) / len(rets)
        lo = min(range(len(closes)), key=closes.__getitem__)
        info = market.profile(s)
        P[s] = dict(dates=[d for d, _ in ser], close=closes, last=last, last_date=ser[-1][0],
                    low=closes[lo] / last, low_date=ser[lo][0], high=max(closes) / last, perf=last / closes[0] - 1,
                    vol=math.sqrt(sum((x - mean) ** 2 for x in rets) / (len(rets) - 1) * 252),
                    ccy=info.get("currency") or ("EUR" if s == "^STOXX50E" else "?"), exchange=info.get("exchange"))
    return P


def bbg(symbol, exchange):
    if symbol in BBG_INDEX:
        return BBG_INDEX[symbol]
    for suf, code in BBG_SUFFIX.items():
        if symbol.endswith(suf):
            return f"{symbol[:-len(suf)]} {code}"
    return f"{symbol} {US_EXCH.get(exchange or '', 'US')}"


# ---------------------------------------------------------------------------------------------
# formatting

def pct(x, d=0):
    if x is None:
        return "–"
    v = f"{x * 100:.{d}f}"
    if d == 0 and abs(x * 100 - round(x * 100)) > 1e-6:
        v = f"{x * 100:.1f}"
    return v + "%"


def f2(x):
    return f"{x:,.2f}".replace(",", "’")


def money(x):
    return f"{x:,.0f}".replace(",", "’")


def rng(vals, suf):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "–"
    lo, hi = min(vals), max(vals)
    f = lambda v: f"{v:g}"
    return f"{f(lo)}{suf}" if lo == hi else f"{f(lo)}–{f(hi)}{suf}"


def b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


# ---------------------------------------------------------------------------------------------
# drawings

def gauge(b, P, w=300, h=46, axis=True):
    """50% to 100% of today: pink below the protection, a dot per name at its 1y low, today in ink."""
    L, R, x0 = 6, 8, 0.5
    X = lambda v: L + (w - L - R) * (max(min(v, 1), x0) - x0) / (1 - x0)
    y = 24 if axis else h - 10
    k = b["strike"]
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%">',
         f'<rect x="{L}" y="{y-5}" width="{X(k)-L:.1f}" height="10" rx="5" fill="#F4E6EC"/>',
         f'<line x1="{X(k):.1f}" x2="{X(1):.1f}" y1="{y}" y2="{y}" stroke="#D9DBE3" stroke-width="2" stroke-linecap="round"/>',
         f'<line x1="{X(k):.1f}" x2="{X(k):.1f}" y1="{y-9}" y2="{y+9}" stroke="{MUL}" stroke-width="2.4" stroke-linecap="round"/>',
         f'<text x="{X(k):.1f}" y="{y-13}" text-anchor="middle" class="gl" fill="{MUL}">{pct(k)}</text>']
    for j, sym in enumerate(b["syms"]):
        if sym in P:
            s.append(f'<circle cx="{X(P[sym]["low"]):.1f}" cy="{y}" r="4.6" fill="{LINE[j % len(LINE)]}" stroke="#fff" stroke-width="1.4"/>')
    s.append(f'<circle cx="{X(1):.1f}" cy="{y}" r="4.6" fill="{INK}"/>')
    if axis:
        s.append(f'<text x="{L}" y="{h-2}" class="ga">50%</text><text x="{X(1):.1f}" y="{h-2}" text-anchor="end" class="ga">today</text>')
    s.append("</svg>")
    return "".join(s)


def chart(b, P, w=680, h=250):
    syms = [s for s in b["syms"] if s in P]
    if not syms:
        return '<p class="mu">No prices.</p>'
    L, R, T, B = 44, 92, 14, 26
    lo = min(min(P[s]["low"] for s in syms), b["strike"]) - 0.05
    hi = max(P[s]["high"] for s in syms) + 0.05
    lo, hi = max(0, int(lo * 20) / 20), int(hi * 20 + 1) / 20
    dates = sorted({d for s in syms for d in P[s]["dates"]})
    ix = {d: i for i, d in enumerate(dates)}
    X = lambda i: L + (w - L - R) * i / (len(dates) - 1)
    Y = lambda v: T + (h - T - B) * (hi - v) / (hi - lo)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%">']
    step = 0.1 if hi - lo > 0.6 else 0.05
    v = math.ceil(lo / step - 1e-9) * step
    while v <= hi + 1e-9:
        out.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{INK}" stroke-opacity=".08"/>'
                   f'<text x="{L-6}" y="{Y(v)+3:.1f}" text-anchor="end" class="ax">{v*100:.0f}</text>')
        v += step
    seen = set()
    for i, d in enumerate(dates):
        if d[:7] not in seen and int(d[5:7]) % 2 == 1 and int(d[8:10]) <= 7:
            seen.add(d[:7])
            out.append(f'<text x="{X(i):.1f}" y="{h-8}" text-anchor="middle" class="ax">{dt.date.fromisoformat(d).strftime("%b %y")}</text>')
    ys = Y(b["strike"])
    out += [f'<line x1="{L}" x2="{w-R}" y1="{Y(1):.1f}" y2="{Y(1):.1f}" stroke="{GREY}" stroke-dasharray="4 3"/>',
            f'<rect x="{L}" y="{ys:.1f}" width="{w-L-R}" height="{h-B-ys:.1f}" fill="{RED}" fill-opacity=".06"/>',
            f'<line x1="{L}" x2="{w-R}" y1="{ys:.1f}" y2="{ys:.1f}" stroke="{RED}" stroke-width="1.4" stroke-dasharray="6 3"/>',
            f'<text x="{w-R+6}" y="{ys+4:.1f}" class="lab" fill="{RED}">{b["kind"]} {pct(b["strike"])}</text>'
            f'<text x="{w-R+6}" y="{Y(1)+4:.1f}" class="lab" fill="{GREY}">Today 100</text>']
    for j, s in enumerate(b["syms"]):
        if s not in P:
            continue
        d = P[s]
        pts = " ".join(f"{X(ix[t]):.1f},{Y(c/d['last']):.1f}" for t, c in zip(d["dates"], d["close"]))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{LINE[j % len(LINE)]}" stroke-width="1.6" stroke-linejoin="round"/>')
        col = RED if d["low"] <= b["strike"] else LINE[j % len(LINE)]
        out.append(f'<circle cx="{X(ix[d["low_date"]]):.1f}" cy="{Y(d["low"]):.1f}" r="3.2" fill="{col}" stroke="#fff" stroke-width="1"/>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------------------------
# blocks

def names_html(b, sep=" · "):
    return sep.join(f'<span style="color:{LINE[j % len(LINE)]}">{escape(n)}</span>' for j, n in enumerate(b["short"]))


def below(b, P):
    return [(n, P[s]["low"]) for n, s in zip(b["short"], b["syms"]) if s in P and P[s]["low"] <= b["strike"]]


def row(b, P, ccy):
    bl = below(b, P)
    status = (f'<span class="warn">Below protection over the year: ' + ", ".join(f"{escape(n)} {lo*100:.0f}%" for n, lo in bl) + "</span>") if bl \
        else f'<span class="ok">All names stayed above {pct(b["strike"])} over the year</span>'
    meta = " · ".join(x for x in (f'{b["kind"]} {pct(b["strike"])}', f'{b["tenor"]} months' if b["tenor"] else "",
                                  f'{ccy} {money(b["amount"])}' if b["amount"] else "") if x)
    return (f'<div class="row"><span class="num">{b["n"]}</span><div class="who"><b>{escape(b["theme"])}</b>'
            f'<span class="nm">{names_html(b)}</span><span class="meta">{meta}</span></div>'
            f'<div class="cp">{pct(b["coupon"],2)}<i>p.a.</i></div><div class="gz">{gauge(b, P, w=330, h=44)}{status}</div></div>')


def crow(b, P):
    bl = below(b, P)
    status = ('<span class="warn">' + ", ".join(f"{escape(n)} {lo*100:.0f}%" for n, lo in bl) + "</span>") if bl else '<span class="ok">all above</span>'
    return (f'<div class="crow"><span class="num">{b["n"]}</span><div class="who"><b>{escape(b["theme"])}</b><span class="nm">{names_html(b)}</span></div>'
            f'<div class="cp">{pct(b["coupon"],2)}</div><div class="pr">{pct(b["strike"])} · {b["tenor"] or "–"} m</div>'
            f'<div class="gz">{gauge(b, P, w=230, h=30, axis=False)}</div><div class="sx">{status}</div></div>')


def table(b, P):
    r = ['<table class="t"><tr><th>Underlying</th><th>Ccy</th><th>Last close</th><th>Protection price</th><th>Fall to protection</th>'
         '<th>Lowest close 1Y</th><th>1Y change</th><th>Vol 1Y</th></tr>']
    for j, (n, s) in enumerate(zip(b["short"], b["syms"])):
        if s not in P:
            r.append(f'<tr><td><b>{escape(n)}</b></td><td colspan="7" class="mu">no prices</td></tr>')
            continue
        d = P[s]
        hit = d["low"] <= b["strike"]
        ld = dt.date.fromisoformat(d["low_date"]).strftime("%d.%m.%y")
        r.append(f'<tr><td><span class="sw" style="background:{LINE[j % len(LINE)]}"></span><b>{escape(n)}</b> <span class="mu">{bbg(s, d["exchange"])}</span></td>'
                 f'<td>{d["ccy"]}</td><td>{f2(d["last"])} <span class="mu">{d["last_date"][8:10]}.{d["last_date"][5:7]}</span></td>'
                 f'<td><b>{f2(d["last"] * b["strike"])}</b></td><td>{pct(b["strike"] - 1)}</td>'
                 f'<td class="{"hit" if hit else ""}">{pct(d["low"], 1)} <span class="mu">{ld}</span></td>'
                 f'<td>{d["perf"]*100:+.1f}%</td><td>{pct(d["vol"], 1)}</td></tr>')
    return "".join(r) + "</table>"


def card(b, P, ccy):
    chips = [f'{ccy} {money(b["amount"])}' if b["amount"] else None, f'Coupon {pct(b["coupon"], 2)} p.a.',
             f'{b["kind"]} {pct(b["strike"])}', f'{b["tenor"]} months' if b["tenor"] else None,
             f'Fees {pct(b["fees"], 2)}' if b["fees"] is not None else None]
    return (f'<section class="card"><div class="ch"><div><span class="num">{b["n"]}</span><h3>{escape(b["theme"])}</h3>'
            f'<span class="mu">{" / ".join(escape(n) for n in b["short"])}</span></div>'
            f'<div class="chips">{"".join(f"<span>{escape(c)}</span>" for c in chips if c)}</div></div>'
            f'<p class="cap">Daily closes over one year, rebased to 100 at today\'s close. Red dashed line: the protection level, '
            f'as for a product struck today. Dots: each name\'s lowest close.</p>{chart(b, P)}{table(b, P)}</section>')


# ---------------------------------------------------------------------------------------------

def build(baskets, P, ccy, title, asof):
    n = len(baskets)
    amounts = [b["amount"] for b in baskets]
    if all(amounts):
        tot = sum(amounts)
        avg = sum(b["amount"] * (b["coupon"] or 0) for b in baskets) / tot
        size_kpi = f'<div><b>{ccy} {money(tot/1000)}k</b><span>across {n} baskets, {len({s for b in baskets for s in b["syms"]})} underlyings</span></div>'
        avg_lab = "average coupon p.a., by size"
    else:
        ws = [b["weight"] or 1 for b in baskets]
        avg = sum(w * (b["coupon"] or 0) for w, b in zip(ws, baskets)) / sum(ws)
        size_kpi = f'<div><b>{n}</b><span>baskets, {len({s for b in baskets for s in b["syms"]})} underlyings</span></div>'
        avg_lab = "average coupon p.a."
    compact = n > 8
    pad = max(2.5, min(6.4, (190 / n - 19) / 2))
    cpad = max(0.8, min(2.4, (178 / n - 9.5) / 2))
    if compact:
        rows = ('<div class="crow ch"><span></span><div>Basket</div><div>Coupon p.a.</div><div>Protection · tenor</div>'
                '<div class="axis"><span>50%</span><span>today</span></div><div>Below protection over 1y</div></div>'
                + "".join(crow(b, P) for b in baskets))
    else:
        rows = "".join(row(b, P, ccy) for b in baskets)
    fees = sorted({b["fees"] for b in baskets if b["fees"] is not None})
    fee_txt = f"before fees ({', '.join(pct(f, 2) for f in fees)})" if fees else "before fees"
    ccys = sorted({P[s]["ccy"] for b in baskets for s in b["syms"] if s in P and P[s]["ccy"] not in (None, "?")})
    logo, reg, bold = b64(ASSETS / "logo.svg"), b64(ASSETS / "fonts" / "NunitoSans-Regular.ttf"), b64(ASSETS / "fonts" / "NunitoSans-Bold.ttf")
    asof_s = asof.strftime("%d.%m.%Y")
    cards = "".join('<div class="pb"></div>' + "".join(card(b, P, ccy) for b in baskets[i:i + 2]) for i in range(0, n, 2))
    css = f"""@font-face{{font-family:N;src:url(data:font/ttf;base64,{reg}) format('truetype')}}
@font-face{{font-family:N;font-weight:700;src:url(data:font/ttf;base64,{bold}) format('truetype')}}
@page{{size:A4;margin:14mm 14mm 18mm}}*{{box-sizing:border-box}}body{{font-family:N,sans-serif;color:{INK};font-size:9.2pt;margin:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.p1h{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:7mm}}
.p1h .k{{color:{ORANGE};font-weight:700;font-size:7.6pt;letter-spacing:.04em}}
.p1h h1{{font-size:24pt;margin:2mm 0 1mm;letter-spacing:-.01em}}.p1h .s{{color:{GREY};font-size:9.6pt}}
.band{{display:grid;grid-template-columns:repeat(4,1fr);margin:2mm 0 11mm}}
.band b{{display:block;font-size:20pt;line-height:1.1}}.band b.o{{color:{ORANGE}}}.band span{{font-size:7.4pt;color:{GREY}}}
.h2s{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4mm}}.h2s h2{{margin:0;font-size:12.5pt}}.h2s span{{font-size:7.2pt;color:{GREY}}}
.num{{display:inline-flex;align-items:center;justify-content:center;border-radius:50%;background:{ORANGE};color:#fff;font-weight:700;width:22px;height:22px;font-size:10pt}}
.row{{display:grid;grid-template-columns:8.5mm 60mm 24mm 1fr;align-items:start;padding:{pad:.1f}mm 0}}
.row .num{{width:6.2mm;height:6.2mm;font-size:8pt;margin-top:.3mm}}
.row .who b{{display:block;font-size:11pt;line-height:1.25}}.row .nm{{display:block;font-size:7.6pt;font-weight:700;margin-top:.9mm}}
.row .meta{{display:block;font-size:7.2pt;color:{GREY};margin-top:.9mm}}
.row .cp{{color:{ORANGE};font-weight:700;font-size:15pt;line-height:1.05;white-space:nowrap}}.row .cp i{{font-style:normal;font-size:7pt;margin-left:.8mm;color:{GREY}}}
.row .gz svg{{display:block;margin-top:-1.5mm}}.row .gz span{{display:block;font-size:7.2pt;font-weight:700;margin-top:.6mm}}
.crow{{display:grid;grid-template-columns:7.5mm 58mm 17mm 21mm 1fr 34mm;align-items:center;column-gap:2mm;padding:{cpad:.1f}mm 0}}
.crow .num{{width:5.4mm;height:5.4mm;font-size:7pt}}
.crow .who b{{display:block;font-size:8.8pt;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.crow .nm{{display:block;font-size:6.6pt;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.crow .cp{{color:{ORANGE};font-weight:700;font-size:11pt}}.crow .pr{{font-size:7.2pt;color:{GREY}}}.crow .sx{{font-size:6.8pt;font-weight:700;line-height:1.25}}
.crow.ch{{font-size:6.6pt;color:{GREY};padding:0 0 1.2mm}}.crow.ch .axis{{display:flex;justify-content:space-between;padding:0 1.5mm 0 1mm}}
.ok{{color:{MINT};font-weight:700}}.warn{{color:{MUL}}}
.gl{{font-size:9px;font-weight:700;font-family:N}}.ga{{font-size:8px;fill:{GREY};font-family:N}}
.legend{{font-size:7pt;color:{GREY};margin-top:5mm;line-height:1.5}}
.pb{{break-before:page}}.card{{break-inside:avoid;margin-bottom:16px}}
.ch{{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}}h3{{display:inline;font-size:12pt;margin:0 6px 0 4px}}
.chips span{{border:1px solid rgba(32,41,69,.3);border-radius:10px;padding:2px 8px;margin-left:4px;font-size:8pt}}
.cap{{color:{BLUE};font-size:7.8pt;margin:6px 0 2px}}.mu{{color:{GREY};font-size:7.6pt}}
.t{{width:100%;border-collapse:collapse;margin-top:6px;font-size:8.3pt}}.t th{{text-align:left;font-size:7.4pt;color:{BLUE};font-weight:700;border-bottom:1px solid rgba(32,41,69,.4);padding:4px}}
.t td{{padding:5px 4px;border-bottom:1px solid rgba(32,41,69,.12)}}.hit{{color:{RED};font-weight:700;background:#C628280F}}
.sw{{display:inline-block;width:10px;height:3px;margin-right:5px;vertical-align:middle}}
.ax{{font-size:9px;fill:{GREY};font-family:N}}.lab{{font-size:10.5px;font-weight:700;font-family:N}}
.note{{font-size:7.4pt;color:{GREY};margin-top:10px;line-height:1.35;text-align:justify}}"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{escape(title)}</title><style>{css}</style></head><body>
<div class="p1h"><div><div class="k">STRUCTURED PRODUCTS · PROPOSAL</div><h1>{escape(title)}</h1>
<div class="s">One-year view of the underlyings · prices as of {asof_s}</div></div><img src="data:image/svg+xml;base64,{logo}" style="height:46px"></div>
<div class="band"><div><b class="o">{pct(avg, 2)}</b><span>{avg_lab}</span></div>{size_kpi}
<div><b>{rng([b["tenor"] for b in baskets], " m")}</b><span>maturities</span></div>
<div><b>{rng([round(b["strike"]*100, 2) for b in baskets], "%")}</b><span>protection levels, struck today</span></div></div>
<div class="h2s"><h2>The baskets</h2><span>Gauge: each underlying's lowest close of the past year, as a % of today</span></div>
<div class="rows">{rows}</div>
<div class="legend">Dots in each name's colour: its lowest close over the year. Pink zone: below the protection level. A dot in the pink zone means that name traded below today's protection level at some point; it is not a backtest or a forecast. Coupons {fee_txt}, indicative and subject to issuer pricing.</div>
{cards}
<p class="note"><b>Important information.</b> Daily closes from market data providers, not adjusted for dividends, up to {asof_s}. Levels assume each product is struck at today's close; actual levels are fixed on the trade date. Lowest closes show how far each name has traded below today's price; they are not a backtest of the products and not a forecast. Coupons and protection levels are indicative, {fee_txt}, and subject to issuer pricing. The products are in {ccy} on underlyings quoted in {", ".join(ccys)}. For information purposes only; not an offer or a recommendation within the meaning of FinSA. Capital is at risk. SYZ · {dt.date.today().strftime("%d.%m.%Y")}</p>
</body></html>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet", type=Path)
    ap.add_argument("--tickers", type=Path)
    ap.add_argument("--themes", type=Path)
    ap.add_argument("--title")
    ap.add_argument("--currency", default="EUR")
    ap.add_argument("--asof")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)

    asof = dt.date.fromisoformat(a.asof) if a.asof else dt.date.today()
    outdir = Path("/mnt/user-data/outputs") if Path("/mnt/user-data/outputs").is_dir() else Path.cwd() / "out"
    out = a.out or outdir / f"SYZ_quick_proposal_{asof.isoformat()}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    market.use_cache(out.parent / ".market_cache.json", a.offline)
    core = CoreList(ASSETS / "core_list.csv")

    print("1  Reading the sheet")
    baskets, ccy = read_sheet(a.sheet, a.currency)
    for i, b in enumerate(baskets, 1):
        b["n"] = i                                   # continuous numbering 1..n
    print(f"   {len(baskets)} baskets, product currency {ccy}" +
          ("" if [b["sheet_n"] for b in baskets] == list(range(1, len(baskets) + 1))
           else f"; renumbered 1-{len(baskets)} (sheet: {', '.join(str(b['sheet_n']) for b in baskets)})"))
    for b in baskets:
        if b["coupon"] is None or b["strike"] is None:
            print(f"   WARNING basket {b['n']}: missing {'coupon' if b['coupon'] is None else 'protection'}: ask for it, never estimate it")
    missing = [b for b in baskets if b["coupon"] is None or b["strike"] is None]
    if missing:
        return 1

    print("2  Matching names to symbols")
    tickers = json.loads(a.tickers.read_text(encoding="utf-8")) if a.tickers else {}
    prods = [Product(number=b["n"], underlyings=[Underlying(name=x) for x in b["names_raw"]]) for b in baskets]
    market.resolve(prods, tickers, core)
    market.complete(prods, asof, log=lambda *_: None)
    themes = json.loads(a.themes.read_text(encoding="utf-8")) if a.themes else {}
    auto = []
    for b, p in zip(baskets, prods):
        b["syms"] = [u.symbol for u in p.underlyings]
        b["short"] = [u.short_name or u.name for u in p.underlyings]
        th = themes.get(str(b["sheet_n"])) or themes.get(str(b["n"])) or b["theme"]
        if not th:
            found = [core.theme_of(s) for s in b["syms"] if s]
            found = [t for t in found if t]
            if all(s in INDICES for s in b["syms"] if s):
                th = "Global equity indices"
            elif found:
                th = max(set(found), key=found.count)
            else:
                th = f"Basket {b['n']}"
            auto.append(b["n"])
        b["theme"] = th

    print("3  Loading one year of prices")
    P = series([s for b in baskets for s in b["syms"] if s], asof)
    market.save_cache()
    if P:
        asof = max(dt.date.fromisoformat(P[s]["last_date"]) for s in P)

    print("4  Drawing the pages")
    title = a.title or (f"{WORDS.get(len(baskets), len(baskets))} thematic baskets" if len(baskets) != 1 else "One thematic basket")
    html = out.with_suffix(".html")
    html.write_text(build(baskets, P, ccy, title, asof), encoding="utf-8")
    from syzdeck.pdf import to_pdf
    engine = to_pdf(html, out)
    print(f"   Wrote {out} ({engine})")

    print("\nCheck before sending")
    tot = [b["amount"] for b in baskets]
    if auto:
        print(f"  themes written automatically for baskets {', '.join(map(str, auto))}: give them with --themes")
    for b in baskets:
        bl = below(b, P)
        if bl:
            print(f"  basket {b['n']} ({b['theme']}): " + ", ".join(f"{n} 1y low {lo*100:.0f}%" for n, lo in bl) + f" vs protection {pct(b['strike'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
