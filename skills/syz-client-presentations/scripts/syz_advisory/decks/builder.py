"""The O01 deck types, built from a case file (JSON).

    sp_review            Structured Product Portfolio Review
    client_review        Client Portfolio Review
    portfolio_proposal   Cross-Asset Portfolio Proposal (proposed weights, no amounts)

The case file carries the client's pseudonym, the positions and the advisor's
messages. Every figure on a slide is computed here from a named source; the
messages are the only free text, and they come from the case file. Anything
missing is shown as "n/a" and listed on the "Sources and method" slide.
See apps/O01/O01_README.md for the case-file format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from syz_advisory.decks import analytics as A
from syz_advisory.decks import charts as C
from syz_advisory.decks.ooxml import (AMBER, BLUEBERRY, BODY_B, BODY_L, BODY_R, BODY_T, BODY_W, Deck, FONT, GREEN, GREY, INK,
                                      MINT, MULBERRY, ORANGE, PALETTE, RED, RUST, Run, Slide, T_AMBER, T_GREEN, T_HEAD,
                                      T_RED, para, title_run)
from syz_advisory.decks.inputs import ingest, load_terms
from syz_advisory.decks.sources import (CALCULATED, INCONSISTENT, MISSING, CsvPrices, FirstOf, Market, Terms, merge,
                                        terms_from_case)
from syz_advisory.marketdata import major_currency

NA = "n/a"
RAG = {"green": ("On track", T_GREEN), "amber": ("Watch", T_AMBER), "red": ("At risk", T_RED), "grey": ("No data", T_HEAD),
       "called": ("Called?", BLUEBERRY), "matured": ("Matured", T_HEAD)}       # (label, text colour in tables)
ROWS_PER_PAGE = 10


# ------------------------------------------------------------------ formatting
def pct(v, d: int = 1, sign: bool = False) -> str:
    if v is None:
        return NA
    return f"{v:+.{d}%}" if sign else f"{v:.{d}%}"


def pts(v) -> str:
    return NA if v is None else f"{v * 100:+.1f} pts"


def money(v, ccy: str = "", short: bool = False) -> str:
    if v is None:
        return NA
    if short and abs(v) >= 1e12:
        s = f"{v / 1e12:,.2f}tn"
    elif short and abs(v) >= 1e9:
        s = f"{v / 1e9:,.1f}bn"
    elif short and abs(v) >= 1e6:
        s = f"{v / 1e6:,.2f}m"
    elif short and abs(v) >= 1e4:
        s = f"{v / 1e3:,.0f}k"
    else:
        s = f"{v:,.0f}"
    return f"{ccy} {s.replace(',', chr(39))}".strip()


def day(d) -> str:
    return d.strftime("%d %b %Y") if isinstance(d, date) else NA


def short_name(name: str, limit: int = 30) -> str:
    """A security's name for a title: legal suffixes dropped, cut at a word under `limit`."""
    import re
    s = re.sub(r"[,.]?\s+(Inc|Corp|Corporation|AG|SA|S\.A|plc|Ltd|N\.V|SE|Holding|Holdings|Group)\.?$", "", str(name).strip(), flags=re.I)
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" -&,")


def month(d) -> str:
    return d.strftime("%b %Y") if isinstance(d, date) else NA


# ------------------------------------------------------------------ context
@dataclass
class Context:
    case: dict
    market: Market
    as_of: date
    ccy: str
    deck: Deck = field(default_factory=Deck)
    flags: list[tuple[str, str]] = field(default_factory=list)      # (where, what)
    sources: list[str] = field(default_factory=list)
    sections: list[tuple[str, Slide]] = field(default_factory=list)
    research_used: set[int] = field(default_factory=set)

    def flag(self, where: str, what: str) -> None:
        if (where, what) not in self.flags:
            self.flags.append((where, what))

    def source(self, text: str) -> None:
        if text not in self.sources:
            self.sources.append(text)


def content(ctx: Context, title: str, subtitle: str = "", section: str | None = None) -> Slide:
    s = ctx.deck.add("One Content")
    s.set_title(title)
    if subtitle:
        s.set_subtitle(subtitle)
    if section:
        ctx.sections.append((section, s))
    return s


def message_list(ctx: Context, key: str) -> list[str]:
    return [m for m in (ctx.case.get("messages") or {}).get(key, []) if m and str(m).strip()]


MARKET = ("market", "portfolio", "macro")


def research(ctx: Context, keys) -> list[tuple[str, str]]:
    """The case file's research items about any of `keys` (Yahoo symbols, Bloomberg tickers,
    names, product labels, ISINs; "market" for the market view), as (text, "source, date").
    Research is quoted with its source, never blended into a calculated figure; an item
    without a source is not shown."""
    want = {str(k).strip().lower() for k in keys if k}
    out = []
    for i, r in enumerate(ctx.case.get("research") or []):
        about = r.get("about") or []
        about = [about] if isinstance(about, str) else about
        if not want & {str(a).strip().lower() for a in about} or not str(r.get("text") or "").strip():
            continue
        if not r.get("source"):
            ctx.flag("Research", f"no source given for the item about {', '.join(map(str, about))}: not shown")
            continue
        ctx.research_used.add(i)
        out.append((r["text"].strip(), ", ".join(str(x) for x in (r["source"], r.get("date")) if x)))
    return out


def research_wrapup(ctx: Context) -> None:
    """Sources slide lines for the research quoted, open points for items nothing matched."""
    for i, r in enumerate(ctx.case.get("research") or []):
        if i in ctx.research_used:
            ctx.source(f"Research quoted: {r['source']}" + (f" ({r['date']})" if r.get("date") else ""))
        elif r.get("source"):
            ctx.flag("Research", f"not shown: 'about' {r.get('about')!r} matches no product, position or 'market'")


# ------------------------------------------------------------------ cover, agenda, closing
def cover(ctx: Context, title: str) -> None:
    s = ctx.deck.add("Cover Slide 2")
    s.placeholder('<p:ph type="ctrTitle"/>', [f"<a:p>{title_run(title)}</a:p>"], "Title")
    intro = f"{ctx.case.get('client', 'Client')} · {ctx.as_of:%d %B %Y}"
    s.placeholder('<p:ph type="body" sz="quarter" idx="13"/>', [f"<a:p>{title_run(intro)}</a:p>"], "Intro")
    s.picture_placeholder(14, ctx.deck.cover_image)
    s.title = title


def agenda(ctx: Context) -> Slide:
    s = ctx.deck.add("Agenda")
    s.picture_placeholder(14, ctx.deck.cover_image)
    s.title = "Agenda"
    return s


def fill_agenda(ctx: Context, s: Slide) -> None:
    seen = []
    for name, slide in ctx.sections:
        if name not in [n for n, _ in seen]:
            seen.append((name, ctx.deck.slides.index(slide) + 1))
    for k, (name, page) in enumerate(seen[:5]):
        s.placeholder(f'<p:ph type="body" sz="quarter" idx="{20 + k}"/>',
                      [f'<a:p><a:r><a:rPr lang="en-GB" dirty="0"/><a:t>{escape(name)}</a:t></a:r></a:p>'], "Section")
        s.placeholder(f'<p:ph type="body" sz="quarter" idx="{25 + k}"/>',
                      [f'<a:p><a:r><a:rPr lang="en-GB" dirty="0"/><a:t>{page}</a:t></a:r></a:p>'], "Page")


def sources_slide(ctx: Context, extra_method: list[str]) -> None:
    research_wrapup(ctx)
    s = content(ctx, "Sources", f"{len(ctx.flags)} open point{'s' if len(ctx.flags) != 1 else ''} to check before sending"
                if ctx.flags else "Every figure shown was sourced",
                section="Sources and method")
    half = (BODY_W - 0.4) / 2
    s.notes_box(BODY_L, BODY_T, half, BODY_B - BODY_T, "Sources and method",
                [(x, "") for x in ctx.sources + extra_method], accent=BLUEBERRY, size=9, floor=7)
    flags = [(f"{w}: {t}", "") for w, t in ctx.flags] or [("Nothing open: every figure shown was sourced.", "")]
    s.notes_box(BODY_L + half + 0.4, BODY_T, half, BODY_B - BODY_T, "Open points to check before sending", flags,
                accent=RUST if ctx.flags else MINT, size=9, floor=6.5)


def closing(ctx: Context) -> None:
    ctx.deck.add("Disclaimer (general)").title = "Important information"
    ctx.deck.add("1_Final page - with Offices").title = "Syz offices"


def messages_slide(ctx: Context, title: str, section: str) -> None:
    risks, opps, steps = message_list(ctx, "risks"), message_list(ctx, "opportunities"), message_list(ctx, "next_steps")
    if not (risks or opps or steps):
        return
    s = content(ctx, title, "Risks, opportunities and next steps", section=section)
    cols = [(h, m, c) for h, m, c in (("Risks", risks, RED), ("Opportunities", opps, GREEN), ("Next steps", steps, BLUEBERRY)) if m]
    w = (BODY_W - 0.4 * (len(cols) - 1)) / len(cols)
    for k, (head, items, color) in enumerate(cols):
        s.notes_box(BODY_L + k * (w + 0.4), BODY_T, w, BODY_B - BODY_T, head, [(m, "") for m in items], accent=color,
                    size=13, floor=9)


def summary_messages(ctx: Context, s: Slide, top: float = BODY_T + 1.55) -> None:
    """The advisor's key messages under the KPIs; the research quoted on the market beside them."""
    msgs = message_list(ctx, "summary")
    market = research(ctx, MARKET)
    if not msgs:
        ctx.flag("Summary", "no advisor messages in the case file: summary shows figures only")
    w = BODY_W * 0.58 if market else BODY_W
    if msgs:
        s.notes_box(BODY_L, top, w, BODY_B - top, "Key messages", [(m, "") for m in msgs], accent=ORANGE, size=14, floor=10)
    if market:
        x = BODY_L + (w + 0.4 if msgs else 0)
        s.notes_box(x, top, BODY_R - x, BODY_B - top, "Market view", market, size=11, floor=8.5)


def kpi_row(s: Slide,items: list[tuple[str, str, str]], y: float = BODY_T, h: float = 1.2) -> float:
    gap = 0.35
    w = (BODY_W - gap * (len(items) - 1)) / len(items)
    size = min(Slide.kpi_size(w, h, v, l, n) for v, l, n in items)
    for k, (value, label, note) in enumerate(items):
        s.kpi(BODY_L + k * (w + gap), y, w, h, value, label, PALETTE[k % len(PALETTE)], note, vsize=size)
    return y + h


# ------------------------------------------------------------------ structured products
@dataclass
class Position:
    label: str
    nominal: float | None
    currency: str
    terms: Terms
    status: A.ProductStatus | None = None
    product: object = None
    payoff_notes: list[str] = field(default_factory=list)
    prices: dict = field(default_factory=dict)
    weight: float | None = None
    short: str = ""                 # for titles: the advisor's label, else the underlyings' codes

    def keys(self) -> list[str]:
        """What a research item's 'about' may name to land on this product's pages."""
        out = [self.label, self.short, self.terms.get("isin")]
        for u in self.terms.underlyings:
            out += [u.symbol, u.ticker, (u.ticker or "").split(" ")[0], u.name]
        return [k for k in out if k]


def _code(u) -> str:
    """NVDA for 'NVDA UW Equity', NESN for NESN.SW, SX5E for 'SX5E Index'."""
    raw = (u.ticker or u.symbol or u.name or "").split(" ")[0]
    return raw.split(".")[0].lstrip("^") if not u.ticker else raw


def load_position(ctx: Context, raw: dict, base: Path) -> Position:
    src = raw.get("source") or {}
    if src:
        kind, rel = next(iter(src.items()))
        path = (base / rel).resolve()
        terms = load_terms({kind: path})
        what = {"html": "HTML factsheets / pricer pages", "pdf": "PDF term sheets / factsheets",
                "text": "term-sheet text", "file": "factsheets and term sheets"}.get(kind, kind)
        ctx.source(f"Product terms: {what}, read by O01 and cross-checked with the B01 term-sheet rules")
        if raw.get("terms"):
            terms = merge(terms, raw["terms"])
    else:
        terms = terms_from_case(raw.get("terms") or {})
        ctx.source("Product terms: entered in the case file by the advisor")
    isin = terms.get("isin") or ""
    label = raw.get("label") or " ".join(x for x in (terms.get("issuer"), f"{pct(terms.get('coupon'), 2)}", "/".join(
        u.ticker.split()[0] for u in terms.underlyings[:3] if u.ticker)) if x and x != NA) or isin or "Product"
    pos = Position(label, raw.get("nominal"), raw.get("currency") or terms.get("currency") or ctx.ccy, terms)
    pos.short = raw.get("label") or "/".join(_code(u) for u in terms.underlyings[:3] if _code(u)) or label
    for f in terms.flags:
        ctx.flag(label, f)
    start = terms.get("initial_fixing") or (ctx.as_of - timedelta(days=365))
    if ctx.case.get("history_days"):     # chart further back than the fixing; status still counts from the fixing
        start = min(start, ctx.as_of - timedelta(days=int(ctx.case["history_days"])))
    for u in terms.underlyings:
        if u.symbol:
            s = ctx.market.prices(u.symbol, start)
            if s.closes:
                pos.prices[u.symbol] = s
            else:
                ctx.flag(label, f"no price history for {u.symbol} ({u.name})")
    if pos.prices:
        ctx.source("Underlying prices: daily closes, unadjusted (barriers and strikes are set on traded prices); "
                   "Yahoo Finance, or the price file given with --prices")
    elif any(u.last is not None for u in terms.underlyings):
        ctx.source("Underlying levels: market prices printed on the factsheets (no price history available)")
    pos.status = A.product_status(terms, pos.prices, ctx.as_of)
    for f in pos.status.flags:
        ctx.flag(label, f)
    pos.product, pos.payoff_notes = A.payoff_product(terms)
    for n in pos.payoff_notes:
        ctx.flag(label, n)
    return pos


def to_reporting(ctx: Context, positions: list[Position]) -> None:
    rates = {}
    total = 0.0
    for p in positions:
        if p.nominal is None:
            ctx.flag(p.label, "nominal missing: excluded from weights")
            continue
        if p.currency not in rates:
            fx = (ctx.case.get("fx") or {}).get(p.currency) or ctx.market.fx(p.currency, ctx.ccy, ctx.as_of)
            rates[p.currency] = fx
            if fx is None:
                ctx.flag("FX", f"no {p.currency}/{ctx.ccy} rate: {p.currency} positions excluded from weights")
            elif p.currency != ctx.ccy:
                ctx.source(f"FX: {p.currency}/{ctx.ccy} {fx:.4f}" + (" (case file)" if (ctx.case.get("fx") or {}).get(p.currency) else " (Yahoo Finance close)"))
        fx = rates[p.currency]
        if fx is not None:
            p.weight = p.nominal * fx
            total += p.weight
    for p in positions:
        p.weight = p.weight / total if p.weight is not None and total else None
    ctx.case["_total_reporting"] = total


def sp_overview(ctx: Context, positions: list[Position], section: str) -> None:
    head = ["#", "Product", "Issuer", "Nominal", "Coupon", "Protection", "Worst-of", "Buffer", "Maturity", "Status"]
    pages = [positions[i:i + ROWS_PER_PAGE] for i in range(0, len(positions), ROWS_PER_PAGE)] or [[]]
    for n, page in enumerate(pages):
        rows, colors = [head], {}
        for i, p in enumerate(page, start=1 + n * ROWS_PER_PAGE):
            t, st = p.terms, p.status
            barrier, strike = t.get("barrier"), t.get("strike")
            rag = st.rag if st else "grey"
            # No barrier: a low strike is where capital starts to be lost, so it is the protection level.
            if barrier is not None:
                level, gap = f"{pct(barrier, 0)} barrier", st.distance_to_barrier if st else None
            elif strike is not None and strike < 1:
                level, gap = f"{pct(strike, 0)} strike", st.distance_to_strike if st else None
            else:
                level, gap = "none", None
            rows.append([str(i), p.short, t.get("issuer") or NA, money(p.nominal, p.currency, short=True),
                         pct(t.get("coupon"), 1), level,
                         pct(st.worst_level, 0) if st else NA, pts(gap) if gap is not None else NA,
                         month(t.get("final_fixing")), RAG[rag][0]])
            for j in (0, 7, len(head) - 1):          # number, distance to barrier and status, as in the reference
                colors[(len(rows) - 1, j)] = RAG[rag][1]
        title = ctx.case.get("titles", {}).get("overview") or _overview_title(positions)
        s = content(ctx, "Portfolio status" + (" (cont.)" if n else ""), f"{title} · {day(ctx.as_of)}", section=section)
        h = s.table(BODY_L, BODY_T, BODY_W, rows, size=12, max_h=BODY_B - BODY_T - 0.35, cell_colors=colors, bold_cols=(1,),
                    align=["l", "l", "l", "r", "r", "r", "r", "r", "r", "l"])
        s.caption(BODY_L, BODY_T + h + 0.08, BODY_W, "Worst-of: weakest underlying vs its initial level. Buffer: distance to "
                  "protection. On track: over 15 pts · Watch: within 15 pts · At risk: at or below.")


def _overview_title(positions: list[Position]) -> str:
    rag = [p.status.rag for p in positions if p.status]
    red, amber, called = rag.count("red"), rag.count("amber"), rag.count("called")
    live = len(positions) - called - rag.count("matured")
    lead = f"{called} probably called, " if called else ""
    if red:
        return lead + f"{red} of {live} at or below protection"
    if amber:
        return lead + f"{amber} of {live} close to protection"
    if lead:
        return lead + (f"{live} well above protection" if live > 1 else "1 well above protection")
    return "All products well above protection"


def sp_allocation(ctx: Context, positions: list[Position], section: str) -> None:
    weighted = [p for p in positions if p.weight]
    if not weighted:
        ctx.flag("Allocation", "no weights (nominals or FX missing): allocation slide skipped")
        return
    fam: dict[str, float] = {}
    iss: dict[str, float] = {}
    und: dict[str, float] = {}
    for p in weighted:
        kind = p.product.kind if p.product else (p.terms.get("product_type") or "Other")
        name = {"Autocallable": "Autocallable", "BRC": "Barrier reverse convertible", "RC": "Reverse convertible",
                "Bonus": "Bonus certificate", "Capital Protected": "Capital protected"}.get(kind, kind)
        fam[name] = fam.get(name, 0) + p.weight
        iss[p.terms.get("issuer") or NA] = iss.get(p.terms.get("issuer") or NA, 0) + p.weight
        for u in p.terms.underlyings:
            und[u.name] = und.get(u.name, 0) + p.weight / max(1, len(p.terms.underlyings))
    fam_rows = sorted(fam.items(), key=lambda kv: -kv[1])
    iss_rows = sorted(iss.items(), key=lambda kv: -kv[1])
    top_iss = iss_rows[0]
    s = content(ctx, "Exposure", f"{top_iss[0]} is the largest issuer at {pct(top_iss[1], 0)}", section=section)
    colors = PALETTE[:len(fam_rows)]
    s.heading(BODY_L, BODY_T, 4.9, "By product type")
    xml, wb = C.doughnut([k for k, _ in fam_rows], [round(v, 6) for _, v in fam_rows], colors)
    s.chart(BODY_L, BODY_T + 0.35, 2.3, 2.3, xml, wb)
    legend = [["■ " + k, pct(v, 0)] for k, v in fam_rows]
    s.table(BODY_L + 2.4, BODY_T + 0.6, 2.5, [["Type", "Share"]] + legend, size=11, max_h=2.0, align=["l", "r"])
    _colour_bullets(s, colors)
    s.heading(BODY_L + 5.4, BODY_T, BODY_W - 5.4, "By issuer")
    xml, wb = C.bars([k for k, _ in iss_rows[:8]], {"Share of portfolio": [round(v, 6) for _, v in iss_rows[:8]]},
                     colors=[BLUEBERRY], fmt="0%")
    s.chart(BODY_L + 5.4, BODY_T + 0.35, BODY_W - 5.4, 2.3, xml, wb)
    und_rows = sorted(und.items(), key=lambda kv: -kv[1])[:8]
    if und_rows:
        s.heading(BODY_L, BODY_T + 2.85, BODY_W, "By underlying")
        xml, wb = C.bars([k for k, _ in und_rows], {"Look-through weight": [round(v, 6) for _, v in und_rows]},
                         colors=[AMBER], fmt="0%")
        s.chart(BODY_L, BODY_T + 3.2, BODY_W, BODY_B - BODY_T - 3.55, xml, wb)
        s.caption(BODY_L, BODY_B - 0.28, BODY_W, "Each product's weight split equally over its underlyings; "
                  "worst-of risk sits on the weakest name.")


def _colour_bullets(s: Slide, colors: list[str]) -> None:
    """Colour the '■' markers of the last table in series order."""
    xml = s.shapes[-1]
    for c in colors:
        xml = xml.replace(f'<a:srgbClr val="{INK}"/></a:solidFill><a:latin typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:rPr><a:t>■ ',
                          f'<a:srgbClr val="{c}"/></a:solidFill><a:latin typeface="{FONT}"/><a:cs typeface="{FONT}"/></a:rPr><a:t>■ ', 1)
    s.shapes[-1] = xml


def _product_status(p: Position) -> str:
    """Where the product stands, in a few words: '34 pts above the 70% barrier'."""
    t, st = p.terms, p.status
    if st and st.called_on:
        return f"Probably called on {st.called_on:%d %b %Y} (to confirm)"
    if st and st.rag == "matured":
        return "Matured"
    if not st or st.worst_level is None:
        return "Terms and payoff"
    if t.get("barrier") is not None:
        gap, what = st.distance_to_barrier, f"the {pct(t.get('barrier'), 0)} barrier"
    elif t.get("strike") is not None:
        gap, what = st.distance_to_strike, f"the {pct(t.get('strike'), 0)} strike"
    else:
        return f"Worst underlying at {pct(st.worst_level, 0)} of initial"
    if abs(gap) < 0.005:
        return f"At {what}"
    return f"{abs(gap) * 100:.0f} pts {'above' if gap >= 0 else 'below'} {what}"


def _display(name: str) -> str:
    """'NESN/NOVN/ZURN' -> 'NESN / NOVN / ZURN' for a title."""
    return name.replace("/", " / ")


def sp_product_pages(ctx: Context, p: Position, section: str) -> None:
    t, st = p.terms, p.status
    # --- page 1: terms and payoff
    message = (ctx.case.get("titles") or {}).get(p.label) or _product_status(p)
    s = content(ctx, _display(p.short), " · ".join(x for x in (message, t.get("issuer"),
                                                               pct(t.get("coupon"), 2) + " p.a." if t.get("coupon") else None) if x),
                section=section)
    rows = [["Term", "Value"], ["Product", t.get("product_type") or NA], ["ISIN", t.get("isin") or NA],
            ["Nominal", money(p.nominal, p.currency)]]
    if not t.get("isin"):
        rows.remove(["ISIN", NA])
    spec = [("Coupon p.a.", "coupon", lambda v: pct(v, 2)),
            ("Coupon frequency", "frequency", lambda v: {1: "Monthly", 3: "Quarterly", 4: "Every 4 months", 6: "Semi-annual", 12: "Annual", 0: "In fine"}.get(v, f"{v} months")),
            ("Strike", "strike", lambda v: pct(v, 0)), ("Barrier", "barrier", lambda v: pct(v, 0)),
            ("Barrier observation", "barrier_type", lambda v: {"american": "American (daily closes)", "european": "European (at maturity)",
                                                                "none": "No barrier"}.get(str(v), str(v))),
            ("Autocall trigger", "autocall_trigger", lambda v: pct(v, 0)),
            ("Initial fixing", "initial_fixing", day), ("Final fixing", "final_fixing", day), ("Settlement", "settlement", str)]
    colors = {}
    for label, key, fmt in spec:
        v = t.fields.get(key)
        if v is None or (v.value is None and v.status != MISSING):
            continue
        shown = fmt(v.value) if v.value is not None else NA
        if v.status in (INCONSISTENT, MISSING):        # the detail is on the open-points slide
            shown += " (check)" if v.status == INCONSISTENT else ""
            colors[(len(rows), 1)] = T_RED
        rows.append([label, shown])
    names = [u.name for u in t.underlyings[:5]]
    if names:
        rows.append(["Underlyings", ", ".join(names)])
    h = s.table(BODY_L, BODY_T, 4.4, rows, size=11, max_h=BODY_B - BODY_T - 0.3, align=["l", "l"], col_weights=[1.6, 2.8],
                cell_colors=colors)
    s.caption(BODY_L, BODY_T + h + 0.06, 4.4, f"Source: {t.source_name}." + (" Red: to check." if colors else ""))
    if p.product:
        levels, series = A.payoff_lines(p.product)
        styles = {A.UNDERLYING: (GREY, 1.25, "dash"),
                  "Product, barrier breached": (RED, 2.25, None), "Product, barrier not breached": (ORANGE, 2.25, None),
                  "Product": (ORANGE, 2.25, None)}
        be = A.breakeven(p.product)
        markers = {}
        if st and st.worst_level is not None and st.rag not in ("called", "matured"):
            markers[f"Today {st.worst_level:.0%}"] = (round(st.worst_level, 4), INK)
        if p.product.barrier is not None:
            markers[f"Barrier {p.product.barrier:.0%}"] = (p.product.barrier, RED)
        if be is not None and (p.product.barrier is None or abs(be - p.product.barrier) > 0.02):
            markers[f"Breakeven {be:.0%}"] = (be, MULBERRY)
        xml, wb = C.payoff(levels, series, styles=styles, markers=markers)
        x, w = BODY_L + 4.8, BODY_W - 4.8
        calls = A.early_redemptions(p.product, t)
        chart_h = 3.05 if calls else 3.75
        s.heading(x, BODY_T, w, "Payoff at maturity")
        s.chart(x, BODY_T + 0.35, w, chart_h, xml, wb)
        y = BODY_T + 0.35 + chart_h + 0.02
        s.caption(x, y, w, "Return incl. coupons vs the worst underlying's final level; before fees, taxes and issuer risk."
                  + (f" Breakeven {be:.0%}." if be else ""))
        if calls:
            head = ["Early redemption"] + [f"{month(c['date']) if c['date'] else str(c['months']) + 'M'}" for c in calls]
            row1 = ["Trigger"] + [pct(c["trigger"], 0) for c in calls]
            row2 = ["Return"] + [pct(c["return"], 1, sign=True) for c in calls]
            s.table(x, y + 0.32, w, [head, row1, row2], size=10, max_h=BODY_B - y - 0.35,
                    align=["l"] + ["r"] * len(calls))
    else:
        ctx.flag(p.label, "payoff diagram not drawn (terms incomplete)")
    # --- page 2: performance since the initial fixing
    if not p.prices:
        return
    fixing = t.get("initial_fixing")
    start = fixing
    if fixing and ctx.case.get("history_days"):
        start = min(fixing, ctx.as_of - timedelta(days=int(ctx.case["history_days"])))
    series_list = [p.prices[u.symbol] for u in t.underlyings if u.symbol in p.prices]
    dates, cols = A.align([x.since(start) if start else x for x in series_list])
    named = {}
    for u, col in zip([u for u in t.underlyings if u.symbol in p.prices], cols):
        us = next((r for r in st.underlyings if r.symbol == u.symbol), None)
        base = us.initial if us and us.initial else next((c for c in col if c is not None), None)
        named[u.name] = [round(c / base * 100, 3) if c is not None and base else None for c in col]
    styles = {}
    for label, key, color in (("Barrier", "barrier", RED), ("Strike", "strike", GREY), ("Autocall trigger", "autocall_trigger", MINT)):
        v = t.get(key)
        if v is not None and not (key == "strike" and t.get("barrier") is not None and abs(v - 1) < 1e-9):
            named[f"{label} {v:.0%}"] = [round(v * 100, 3)] * len(dates)
            styles[f"{label} {v:.0%}"] = (color, 1.25, "dash")
    worst = st.worst
    message = (ctx.case.get("titles") or {}).get(p.label + " performance") or (
        f"Weakest: {worst.name} at {pct(worst.level, 0)} of initial" if worst else "Since the initial fixing")
    s2 = content(ctx, _display(p.short), message, section=section)
    xml, wb = C.lines_over_dates(dates, named, styles=styles, fmt="0")
    notes = research(ctx, p.keys())
    chart_h = BODY_B - BODY_T - (1.95 if notes else 0.35)
    s2.chart(BODY_L, BODY_T, 6.9, chart_h, xml, wb)
    s2.caption(BODY_L, BODY_T + chart_h + 0.02, 6.9, f"Rebased to 100 at the initial fixing ({day(fixing)}); daily closes.")
    if notes:
        y = BODY_T + chart_h + 0.4
        s2.notes_box(BODY_L, y, 6.9, BODY_B - y, "Research view", notes, size=11, floor=8)
    x = BODY_L + 7.3
    w = BODY_W - 7.3
    first_tile = ((day(st.called_on), "Autocall condition met", "probably redeemed: confirm") if st.called_on else
                  (pct(st.worst_level, 0), "Worst-of vs initial", ""))
    if t.get("barrier") is not None:
        breached = {True: "touched", False: "never touched", None: ""}[st.barrier_breached]
        protection = [(pts(st.distance_to_barrier), f"Buffer to the {pct(t.get('barrier'), 0)} barrier",
                       f"barrier {breached}" if breached and t.get("barrier_type") != "european" else "")]
    else:      # no barrier: the strike is where capital starts to be lost (e.g. a low-strike autocall)
        protection = [(pts(st.distance_to_strike), f"Buffer to the {pct(t.get('strike'), 0)} strike", "")]
    done = st.rag in ("called", "matured")
    tiles = [first_tile, *protection,
             ("none" if done else day(st.next_observation), "Next observation", "" if done else "estimated")]
    th = (BODY_B - BODY_T - 0.3 * 2) / 3
    size = min(Slide.kpi_size(w, th, v, l, n) for v, l, n in tiles)
    for k, (v, l, n) in enumerate(tiles):
        s2.kpi(x, BODY_T + k * (th + 0.3), w, th, v, l, [ORANGE, RED, BLUEBERRY][k], n, vsize=size)


def sp_scenarios(ctx: Context, positions: list[Position], section: str) -> None:
    usable = [p for p in positions if p.product and p.status and p.status.worst_level is not None
              and p.status.rag not in ("called", "matured")]
    for p in positions:
        if p.status and p.status.rag in ("called", "matured"):
            ctx.flag(p.label, f"left out of the scenarios ({RAG[p.status.rag][0].rstrip('?').lower()})")
    if not usable:
        return
    shocks = (0.10, 0.0, -0.10, -0.20, -0.30)
    head = ["Product", "Worst-of today"] + [f"{s:+.0%}" if s else "Unchanged" for s in shocks]
    rows, colors = [head], {}
    port = [0.0] * len(shocks)
    wsum = 0.0
    for p in usable:
        sc = A.scenarios(p.product, p.status, shocks)
        rows.append([p.short, pct(p.status.worst_level, 0)] + [pct(x["total"], 1, sign=True) for x in sc])
        for j, x in enumerate(sc):
            if x["total"] < 0:
                colors[(len(rows) - 1, 2 + j)] = T_RED
        if p.weight:
            wsum += p.weight
            for j, x in enumerate(sc):
                port[j] += p.weight * x["total"]
    if wsum:
        rows.append(["Portfolio (weighted)", ""] + [pct(v / wsum, 1, sign=True) for v in port])
    worst_case = min(port) / wsum if wsum else None
    title = (ctx.case.get("titles") or {}).get("scenarios") or (
        (f"After a 30% fall, still {pct(worst_case, 0, sign=True)} at maturity" if worst_case >= 0 else
         f"A 30% fall would cost {pct(-worst_case, 0)} at maturity") if worst_case is not None else "Return at maturity by scenario")
    s = content(ctx, "Scenarios", title, section=section)
    h = s.table(BODY_L, BODY_T, BODY_W, rows, size=12, max_h=BODY_B - BODY_T - 0.6, cell_colors=colors,
                bold_rows=(len(rows) - 1,) if wsum else ())
    s.caption(BODY_L, BODY_T + h + 0.08, BODY_W, "Worst underlying moves from today and stays there until maturity. "
              "Total return incl. coupons, before fees, taxes and issuer risk. Not a forecast.")


def build_sp_review(ctx: Context, base: Path) -> Deck:
    positions = [load_position(ctx, raw, base) for raw in ctx.case.get("products", [])]
    if not positions:
        raise ValueError("an sp_review case needs at least one product")
    to_reporting(ctx, positions)
    cover(ctx, ctx.case.get("title") or "Structured Products Portfolio Review")
    ag = agenda(ctx)
    # summary
    total = ctx.case.get("_total_reporting")
    coupons = [(p.weight, p.terms.get("coupon")) for p in positions if p.weight and p.terms.get("coupon") is not None]
    avg_coupon = sum(w * c for w, c in coupons) / sum(w for w, _ in coupons) if coupons else None
    rag = [p.status.rag for p in positions]
    nxt = min((p.status.next_observation for p in positions if p.status.next_observation), default=None)
    title = ctx.case.get("titles", {}).get("summary") or (
        f"{money(total, ctx.ccy, short=True)} in {len(positions)} products, {pct(avg_coupon, 1)} average coupon"
        if total and avg_coupon is not None else f"{len(positions)} structured products")
    s = content(ctx, "Summary", f"{title} · {day(ctx.as_of)}", section="Summary")
    kpi_row(s, [(money(total, ctx.ccy, short=True), "Total nominal", ""),
                (pct(avg_coupon, 2), "Average coupon p.a.", ""),
                (f"{rag.count('green')} / {rag.count('amber')} / {rag.count('red')}", "On track / watch / at risk", ""),
                (str(rag.count("called") + rag.count("matured")), "Called or matured", "to confirm"),
                (day(nxt), "Next observation", "estimated")])
    summary_messages(ctx, s)
    sp_overview(ctx, positions, "Portfolio overview")
    sp_allocation(ctx, positions, "Portfolio overview")
    for p in positions:
        sp_product_pages(ctx, p, "Products")
    sp_scenarios(ctx, positions, "Scenarios and risks")
    messages_slide(ctx, ctx.case.get("titles", {}).get("assessment") or "Our assessment", "Scenarios and risks")
    sources_slide(ctx, ["Worst-of: lowest underlying level relative to its initial fixing.",
                        "Barrier touched: any daily close at or below the barrier since the initial fixing (American barriers). "
                        "The issuer's own fixing is authoritative.",
                        "Payoff and scenarios: at maturity, per unit of nominal, before fees and taxes; issuer credit risk comes on top.",
                        "Next observation: initial fixing plus whole coupon periods; check the term sheet's schedule."])
    closing(ctx)
    fill_agenda(ctx, ag)
    return ctx.deck


# ------------------------------------------------------------------ client portfolio review / cross-asset proposal
def build_client_review(ctx: Context, base: Path, proposal: bool = False) -> Deck:
    """The client's portfolio as held (`client_review`), or a proposed cross-asset allocation
    (`portfolio_proposal`: weights only, no amounts; performance is a back-test of the weights)."""
    raw = ctx.case.get("holdings", [])
    if not raw:
        raise ValueError(f"a {'portfolio_proposal' if proposal else 'client_review'} case needs holdings")
    if proposal and any(h.get("value") is not None for h in raw):
        ctx.flag("Holdings", "a proposal shows weights only: the amounts given were used for the weights and not shown")
    if all(h.get("value") is not None for h in raw):
        # values are what the custody statement reports; weights are derived from them
        stated = [h.get("weight") for h in raw]
        holdings = A.weights([{**h, "weight": None} for h in raw])
        off = [h.get("name") for h, w in zip(holdings, stated) if w is not None and abs(w - h["weight"]) > 0.005]
        if off:
            ctx.flag("Holdings", f"weights in the input differ from the values for {len(off)} positions "
                                 f"(e.g. {off[0]}): weights recalculated from the values")
    else:
        holdings = A.weights(raw)
    if abs(sum(h["weight"] or 0 for h in holdings) - 1) > 0.01:
        ctx.flag("Holdings", f"weights sum to {sum(h['weight'] or 0 for h in holdings):.1%}, not 100%")
    ctx.source("Proposed weights: case file (advisor)" if proposal else "Positions and values: case file (advisor)")
    mix = "Proposed allocation" if proposal else "Current allocation"
    for h in holdings:
        if not h.get("symbol") and h.get("isin") and (h.get("asset_class") or "") not in ("Cash", "Bonds", "Structured products"):
            sym = ctx.market.search(h["isin"])
            if sym:
                h["symbol"] = sym
                ctx.flag(h.get("name") or h["isin"], f"Yahoo symbol {sym} found from the ISIN -- check it is the right listing")
    period = ctx.case.get("period_days", 365)
    start = ctx.as_of - timedelta(days=period)
    prices = {}
    for h in holdings:
        sym = h.get("symbol")
        if sym:
            ser = ctx.market.prices(sym, start, adjusted=True)
            if ser.closes:
                prices[sym] = ser
            else:
                ctx.flag(h.get("name", sym), f"no Yahoo prices for {sym}")
    bench_sym = ctx.case.get("benchmark", {}).get("symbol") if isinstance(ctx.case.get("benchmark"), dict) else ctx.case.get("benchmark")
    bench_name = ctx.case.get("benchmark", {}).get("name", bench_sym) if isinstance(ctx.case.get("benchmark"), dict) else bench_sym
    bench = ctx.market.prices(bench_sym, start, adjusted=True) if bench_sym else None
    if prices:
        ctx.source(f"Prices: Yahoo Finance daily closes adjusted for dividends and splits, {day(start)} to {day(ctx.as_of)}")
    # Portfolio-level comparisons are made in the reporting currency: a USD fund and a
    # CHF stock only add up once both are in CHF. Single-position figures stay local.
    fx_cache: dict[str, object] = {}

    def to_base(symbol: str, ser, stated: str | None):
        quote = major_currency(ctx.market.info(symbol).get("currency") or stated or ctx.ccy)[0]
        if quote == ctx.ccy:
            return ser
        if quote not in fx_cache:
            fx = ctx.market.prices(f"{quote}{ctx.ccy}=X", start - timedelta(days=10))
            fx_cache[quote] = fx if fx.closes else None
            if fx.closes:
                ctx.source(f"FX: {quote}/{ctx.ccy} daily closes, Yahoo Finance")
            else:
                ctx.flag("FX", f"no {quote}/{ctx.ccy} history: {quote} prices left in {quote} on the performance chart")
        return A.in_currency(ser, fx_cache[quote])

    prices_base = {h["symbol"]: to_base(h["symbol"], prices[h["symbol"]], h.get("currency"))
                   for h in holdings if h.get("symbol") in prices}
    bench_base = to_base(bench_sym, bench, None) if bench and bench.closes else bench
    cover(ctx, ctx.case.get("title") or ("Cross-Asset Portfolio Proposal" if proposal else "Client Portfolio Review"))
    ag = agenda(ctx)
    conc = A.concentration(holdings)
    dates, proxy, covered = A.proxy_performance(holdings, prices_base)
    proxy_ret = proxy[-1] / 100 - 1 if proxy and proxy[-1] else None
    total = None if proposal else sum(h.get("value") or 0 for h in holdings) or None
    top_n, top_w = (10, conc["top10"]) if conc["positions"] > 12 else (5, conc["top5"])
    classes = A.breakdown(holdings, "asset_class")
    months = period // 30
    # summary
    titles = ctx.case.get("titles", {})
    s = content(ctx, "Summary", (titles.get("summary") or (
                f"{conc['positions']} positions across {len(classes)} asset classes" if proposal or not total else
                f"{money(total, ctx.ccy, short=True)} in {conc['positions']} positions, top {top_n} at {pct(top_w, 0)}"))
                + f" · {day(ctx.as_of)}", section="Summary")
    first_kpi = (str(len(classes)), "Asset classes", "") if proposal or not total else (money(total, ctx.ccy, short=True), "Portfolio value", "")
    kpi_row(s, [first_kpi,
                (str(conc["positions"]), "Positions", ""),
                (pct(top_w, 0), f"Top {top_n} weight", ""),
                (f"{conc['effective_n']:.1f}" if conc["effective_n"] else NA, "Effective positions", ""),
                (pct(proxy_ret, 1, sign=True), f"{months} months, back-test" if proposal else f"{months} months, illustrative", f"in {ctx.ccy}")])
    summary_messages(ctx, s)
    # allocation
    target = ctx.case.get("target_allocation") or {}
    lead, lead_w = classes[0]
    gap = max(((k, v - target[k]) for k, v in classes if k in target), key=lambda kv: abs(kv[1]), default=None)
    if gap and abs(gap[1]) >= 0.005:
        auto = f"{gap[0]} {abs(gap[1]) * 100:.0f} pts {'above' if gap[1] > 0 else 'below'} the strategy"
    elif gap:
        auto = "In line with the strategic allocation"
    else:
        auto = f"{lead} is the largest asset class at {pct(lead_w, 0)}"
    s = content(ctx, "Proposed allocation" if proposal else "Allocation", titles.get("allocation") or auto, section="Allocation")
    colors = PALETTE[:len(classes)]
    xml, wb = C.doughnut([k for k, _ in classes], [round(v, 6) for _, v in classes], colors)
    s.chart(BODY_L, BODY_T + 0.2, 3.6, 3.6, xml, wb)
    head = ["Asset class", "Proposed" if proposal else "Actual"] + (["Strategy", "Gap"] if target else [])
    rows = [head] + [["■ " + k, pct(v, 0)] + ([pct(target.get(k), 0), pts(v - target[k]) if k in target else NA] if target else [])
                     for k, v in classes]
    s.table(BODY_L + 4.2, BODY_T + 0.3, BODY_W - 4.2, rows, size=12, max_h=BODY_B - BODY_T - 0.6)
    _colour_bullets(s, colors)
    # concentration
    top = sorted(holdings, key=lambda h: -(h.get("weight") or 0))[:10]
    s = content(ctx, "Concentration", titles.get("concentration") or
                f"Largest position: {top[0].get('name')} at {pct(top[0].get('weight'), 0)}", section="Allocation")
    xml, wb = C.bars([h.get("name", "") for h in top], {"Weight": [round(h.get("weight") or 0, 6) for h in top]}, colors=[ORANGE])
    s.chart(BODY_L, BODY_T, 6.3, BODY_B - BODY_T - 0.3, xml, wb)
    ccys = A.breakdown(holdings, "currency")
    xml, wb = C.bars([k for k, _ in ccys], {"Weight": [round(v, 6) for _, v in ccys]}, colors=[BLUEBERRY])
    s.heading(BODY_L + 6.6, BODY_T, BODY_W - 6.6, "By currency")
    s.chart(BODY_L + 6.6, BODY_T + 0.35, BODY_W - 6.6, 1.95, xml, wb)
    regions = A.breakdown(holdings, "region")
    if any(h.get("region") for h in holdings):
        xml, wb = C.bars([k for k, _ in regions[:6]], {"Weight": [round(v, 6) for _, v in regions[:6]]}, colors=[AMBER])
        s.heading(BODY_L + 6.6, BODY_T + 2.4, BODY_W - 6.6, "By region")
        s.chart(BODY_L + 6.6, BODY_T + 2.75, BODY_W - 6.6, 1.95, xml, wb)
    s.caption(BODY_L, BODY_B - 0.28, BODY_W, f"Top 5: {pct(conc['top5'], 0)} · top 10: {pct(conc['top10'], 0)} · "
              f"effective positions: {conc['effective_n']:.1f}" if conc["effective_n"] else "")
    # performance
    if proxy:
        series = {f"{mix} ({'back-test' if proposal else 'illustrative'})": proxy}
        bench = bench_base
        if bench and bench.closes:
            bdates, bcols = A.align([bench])
            lookup = dict(zip(bdates, bcols[0]))
            first = next((lookup.get(d) for d in dates if lookup.get(d)), None)
            last = None
            vals = []
            for d in dates:
                last = lookup.get(d, last)
                vals.append(round(last / first * 100, 4) if last and first else None)
            series[bench_name] = vals
            ctx.source(f"Benchmark: {bench_name} ({bench_sym}), Yahoo Finance")
        bench_ret = (series[bench_name][-1] / 100 - 1) if bench and bench_name in series and series[bench_name][-1] else None
        title = titles.get("performance") or (
            f"{pct(proxy_ret, 1, sign=True)} over {months} months"
            + (f" vs {pct(bench_ret, 1, sign=True)} for the benchmark" if bench_ret is not None else ""))
        s = content(ctx, "Performance", title, section="Performance")
        xml, wb = C.lines_over_dates(dates, series, colors=[ORANGE, BLUEBERRY])
        s.chart(BODY_L, BODY_T, 6.4, BODY_B - BODY_T - 0.35, xml, wb)
        s.caption(BODY_L, BODY_B - 0.3, 6.4, ("Back-test" if proposal else "Illustration") + f" in {ctx.ccy}, rebased to 100: "
                  "today's weights on past prices, no trades or fees"
                  + (f", covers {pct(covered, 0)}" if covered < 0.995 else "") + ". Past performance is no guide to the future.")
        rows = [["Position", "Return", "Vol.", "Drawdown"]]
        for h in sorted(holdings, key=lambda h: -(h.get("weight") or 0)):
            ser = prices.get(h.get("symbol"))
            if ser:
                rows.append([h.get("name", h.get("symbol")), pct(A.total_return(ser.closes), 0, sign=True),
                             pct(A.volatility(ser.closes), 0), pct(A.max_drawdown(ser.closes), 0)])
        s.table(BODY_L + 6.65, BODY_T, BODY_W - 6.65, rows[:13], size=11, max_h=BODY_B - BODY_T - 0.35)
        s.caption(BODY_L + 6.65, BODY_B - 0.3, BODY_W - 6.65, "Local currency, daily closes; vol. annualised.")
        ctx.flag("Performance", f"the performance chart is {'a back-test of the proposed weights' if proposal else 'an illustration of the current allocation'}, "
                                "not the account's track record")
    else:
        ctx.flag("Performance", "no price history for any position: performance slide skipped")
    bond_page(ctx, holdings)
    # spotlights: single securities and funds
    for h in holdings:
        if h.get("spotlight") and h.get("symbol"):
            security_page(ctx, h, prices_base.get(h["symbol"]), bench_base, bench_name)
        if h.get("fund_detail") and h.get("symbol"):
            fund_page(ctx, h)
    # structured products held
    if ctx.case.get("products"):
        positions = [load_position(ctx, raw, base) for raw in ctx.case["products"]]
        to_reporting(ctx, positions)
        sp_overview(ctx, positions, "Structured products")
        for p in positions:
            sp_product_pages(ctx, p, "Structured products")
    messages_slide(ctx, titles.get("assessment") or ("Why this allocation" if proposal else "Our assessment"), "Assessment")
    sources_slide(ctx, [("Weights: proposed by the advisor; no amounts shown." if proposal else
                         "Weights: market values from the case file, in " + ctx.ccy + "."),
                        "Effective number of positions: 1 / sum of squared weights.",
                        "Return, volatility and drawdown: from adjusted daily closes over the period shown; past performance is no guide to the future.",
                        "Fund data: Yahoo Finance fund profile; check fees and holdings against the latest factsheet before sending."])
    closing(ctx)
    fill_agenda(ctx, ag)
    return ctx.deck


def bond_page(ctx: Context, holdings: list[dict]) -> None:
    """Direct bonds: yield, duration, maturity ladder, issuer and rating -- when the inputs give
    at least a maturity per bond (plus a price or a yield)."""
    rows, notes = A.bond_rows(holdings, ctx.as_of)
    bonds_w = sum(h.get("weight") or 0 for h in holdings if (h.get("asset_class") or "").lower() == "bonds")
    if not rows:
        if bonds_w > 0:
            ctx.flag("Bonds", "no bond detail (maturity, coupon, price or yield): bond analysis slide skipped")
        return
    for n in notes:
        ctx.flag("Bonds", n)
    w = sum(r.get("weight") or 0 for r in rows) or 1
    def wavg(key):
        vals = [(r.get("weight") or 0, r.get(key)) for r in rows if r.get(key) is not None]
        tot = sum(x for x, _ in vals)
        return sum(x * v for x, v in vals) / tot if tot else None
    ytm, dur, yrs = wavg("ytm"), wavg("mod_duration"), wavg("years")
    s = content(ctx, "Bonds", ctx.case.get("titles", {}).get("bonds") or
                (f"{len(rows)} bonds yielding {pct(ytm, 1)}, duration {dur:.1f} years" if ytm is not None and dur is not None
                 else f"{len(rows)} direct bonds, {pct(w, 0)} of the portfolio"), section="Allocation")
    kpi_row(s, [(pct(w, 1), "Direct bonds", "share of the portfolio"), (pct(ytm, 2), "Yield to maturity", "weighted"),
                (f"{dur:.1f}" if dur is not None else NA, "Modified duration", "years"),
                (f"{yrs:.1f}" if yrs is not None else NA, "Average maturity", "years"),
                (f"{-dur * 0.01:+.1%}" if dur is not None else NA, "If yields rise 1%", "price effect")], h=1.05)
    ladder: dict[int, float] = {}
    for r in rows:
        ladder[r["maturity_date"].year] = ladder.get(r["maturity_date"].year, 0) + (r.get("weight") or 0) / w
    years = sorted(ladder)
    xml, wb = C.bars([str(y) for y in years], {"Share of bonds": [round(ladder[y], 6) for y in years]},
                     horizontal=False, colors=[BLUEBERRY], fmt="0%")
    top = BODY_T + 1.25
    s.heading(BODY_L, top, 4.3, "Maturity ladder")
    s.chart(BODY_L, top + 0.35, 4.3, BODY_B - top - 0.7, xml, wb)
    table = [["Bond", "Coupon", "Maturity", "YTM", "Mod. dur.", "Rating"]]
    for r in sorted(rows, key=lambda r: r["maturity_date"])[:12]:
        table.append([r.get("name") or r.get("isin") or NA, pct(r.get("coupon"), 2), day(r["maturity_date"]),
                      pct(r.get("ytm"), 2) + ("*" if r.get("ytm_source") == "calculated" else ""),
                      f"{r['mod_duration']:.1f}" if r.get("mod_duration") is not None else NA, r.get("rating") or NA])
    s.table(BODY_L + 4.6, top, BODY_W - 4.6, table, size=10, max_h=BODY_B - top - 0.35)
    s.caption(BODY_L, BODY_B - 0.3, BODY_W, "* yield calculated from price, coupon and maturity. Duration effects are "
              "first-order estimates. Ratings as given.")
    ctx.source("Bond analytics: yield to maturity and duration calculated by O01 where the inputs give only price, coupon and maturity")


def security_page(ctx: Context, h: dict, ser, bench, bench_name) -> None:
    info = ctx.market.info(h["symbol"])
    name = h.get("name") or info.get("longName") or h["symbol"]
    ret = A.total_return(ser.closes) if ser else None
    s = content(ctx, short_name(name), ctx.case.get("titles", {}).get(h["symbol"]) or
                f"{pct(ret, 1, sign=True)} over the period · {info.get('sector') or h['symbol']} · weight {pct(h.get('weight'), 1)}",
                section="Positions")
    notes = research(ctx, [h["symbol"], h.get("name"), h.get("isin"), h["symbol"].split(".")[0]])
    if ser and ser.closes:
        series_list = [ser] + ([bench] if bench and bench.closes else [])
        dates, cols = A.align(series_list)
        named = {name: [round(c / cols[0][0] * 100, 3) if c and cols[0][0] else None for c in cols[0]]}
        if len(cols) > 1:
            first = next((c for c in cols[1] if c), None)
            named[bench_name] = [round(c / first * 100, 3) if c and first else None for c in cols[1]]
        xml, wb = C.lines_over_dates(dates, named, colors=[ORANGE, BLUEBERRY])
        chart_h = BODY_B - BODY_T - (1.95 if notes else 0.35)
        s.chart(BODY_L, BODY_T, 6.4, chart_h, xml, wb)
        s.caption(BODY_L, BODY_T + chart_h + 0.02, 6.4, f"In {ctx.ccy}, rebased to 100; adjusted daily closes and FX.")
    if notes:
        y = BODY_B - 1.55
        s.notes_box(BODY_L, y, 6.4, BODY_B - y, "Research view", notes, size=11, floor=8)
    facts = [("Market cap", money(info.get("marketCap"), info.get("currency") or "", short=True)),
             ("P/E trailing", f"{info['trailingPE']:.1f}" if info.get("trailingPE") else NA),
             ("P/E forward", f"{info['forwardPE']:.1f}" if info.get("forwardPE") else NA),
             ("Dividend yield", pct(info.get("dividendYield") / 100 if info.get("dividendYield") and info["dividendYield"] > 1 else info.get("dividendYield"), 2)),
             ("52-week range", f"{info['fiftyTwoWeekLow']:,.2f} – {info['fiftyTwoWeekHigh']:,.2f}" if info.get("fiftyTwoWeekLow") else NA),
             ("Analyst target", f"{info['targetMeanPrice']:,.2f}" if info.get("targetMeanPrice") else NA),
             ("Volatility", pct(A.volatility(ser.closes) if ser else None, 0)),
             ("Max drawdown", pct(A.max_drawdown(ser.closes) if ser else None, 0))]
    s.table(BODY_L + 6.65, BODY_T, BODY_W - 6.65, [["Fact", "Value"]] + [list(f) for f in facts], size=12, max_h=BODY_B - BODY_T - 0.35)
    s.caption(BODY_L + 6.65, BODY_B - 0.3, BODY_W - 6.65, "Analyst target: third-party consensus, not a SYZ view.")
    if not info:
        ctx.flag(name, "no Yahoo profile: facts shown as n/a")
    ctx.source("Company facts and consensus: Yahoo Finance quote summary")


def fund_page(ctx: Context, h: dict) -> None:
    f = ctx.market.fund(h["symbol"])
    name = h.get("name") or f.get("name") or h["symbol"]
    if not f:
        ctx.flag(name, f"no Yahoo fund data for {h['symbol']}: fund page skipped")
        return
    r, rc = f.get("returns") or {}, f.get("category_returns") or {}
    one, one_c = r.get("oneYearTotalReturn"), rc.get("oneYearTotalReturn")
    message = ctx.case.get("titles", {}).get(h["symbol"]) or (
        f"{pct(one, 1, sign=True)} in a year vs {pct(one_c, 1, sign=True)} for its category" if one is not None
        else f"{f.get('category') or 'Fund'} profile")
    s = content(ctx, short_name(name), f"{message} · weight {pct(h.get('weight'), 1)}", section="Positions")
    facts = [["Fact", "Value"], ["Fund family", f.get("family") or NA], ["Category", f.get("category") or NA],
             ["Legal type", f.get("legal_type") or NA], ["Expense ratio", pct(f.get("expense_ratio"), 2)],
             ["Turnover", pct(f.get("turnover"), 0)],
             ["Stocks / bonds / cash", " / ".join(pct((f.get("asset_mix") or {}).get(k), 0) for k in ("stock", "bond", "cash"))]]
    s.table(BODY_L, BODY_T, 4.3, facts, size=10, max_h=2.6)
    labels = ["YTD", "1 year", "3 years", "5 years (avg p.a.)"]
    keys = ["ytdReturnPct", "oneYearTotalReturn", "threeYearTotalReturn", "fiveYrAvgReturnPct"]
    xml, wb = C.bars(labels, {"Fund": [r.get(k) for k in keys], "Category": [rc.get(k) for k in keys]},
                     horizontal=False, colors=[ORANGE, GREY])
    s.heading(BODY_L, BODY_T + 2.25, 4.3, "Returns vs category")
    s.chart(BODY_L, BODY_T + 2.6, 4.3, BODY_B - BODY_T - 2.95, xml, wb)
    top = (f.get("top_holdings") or [])[:10]
    if top:
        xml, wb = C.bars([t["name"] or t["symbol"] for t in top], {"Weight in fund": [t["weight"] for t in top]}, colors=[BLUEBERRY])
        s.heading(BODY_L + 4.6, BODY_T, BODY_W - 4.6, "Ten largest holdings")
        s.chart(BODY_L + 4.6, BODY_T + 0.35, BODY_W - 4.6, BODY_B - BODY_T - 0.7, xml, wb)
    s.caption(BODY_L, BODY_B - 0.28, BODY_W, "Source: Yahoo Finance fund profile; check fees and holdings against the fund's latest factsheet.")
    ctx.source("Fund facts: Yahoo Finance fund profile, holdings and performance modules")
    ctx.flag(name, "fund fees and holdings come from Yahoo: confirm against the official factsheet")


# ------------------------------------------------------------------ entry point
def build(case_path: Path, market: Market, out: Path) -> tuple[Path, Context]:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    base = case_path.parent
    # "inputs": any files (PDF, HTML, CSV, Excel) read and sorted automatically; what the case
    # file states itself wins over what was read.
    if case.get("inputs"):
        found = ingest([(base / p).resolve() for p in case["inputs"]], currency=case.get("currency"))
        for key in ("holdings", "products", "prices"):
            if found.case.get(key) and not case.get(key):
                case[key] = found.case[key]
        case.setdefault("type", found.case["type"])
        case.setdefault("_ingest_flags", []).extend(found.flags)
    as_of = date.fromisoformat(case["as_of"]) if case.get("as_of") else date.today()
    market.as_of = market.as_of or as_of
    price_files = [(base / (p["file"] if isinstance(p, dict) else p)).resolve() for p in case.get("prices", [])]
    if price_files:
        market.client = FirstOf(market.client, CsvPrices(price_files))
    ctx = Context(case, market, as_of, case.get("currency", "CHF"))
    for where, what in case.get("_ingest_flags", []):
        ctx.flag(where, what)
    if price_files:
        ctx.source("Price files: " + ", ".join(p.name for p in price_files))
    kind = case.get("type")
    if kind == "sp_review":
        build_sp_review(ctx, base)
    elif kind in ("client_review", "portfolio_proposal"):
        build_client_review(ctx, case_path.parent, proposal=kind == "portfolio_proposal")
    else:
        raise ValueError(f"case type must be 'sp_review', 'client_review' or 'portfolio_proposal', not {kind!r}")
    ctx.deck.save(out)
    return out, ctx
