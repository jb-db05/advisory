"""Step 5: the analysis behind every figure on the pages.

Per product: one year of closes rebased to 100 today, one-year volatility, correlation (average and
minimum of the pairs), each name's lowest close against the protection, the fall to protection, the
analysts' target upside, the short reading of the basket and the swap test.
For the portfolio: the KPIs, the theme weights, the income per product, a symmetric stress at
maturity and the issuer concentration.

Levels assume a strike at today's close, unless the document gave the initial fixing levels of a
product already struck: then the protection is placed at its real price level.
"""

from __future__ import annotations

import datetime as dt
import itertools
import math
from dataclasses import dataclass, field

from .market import closes, kind, profile
from .model import Product
from .names import CoreList


@dataclass
class Leg:
    symbol: str
    short: str
    long: str
    kind: str
    dates: list[str]
    rebased: list[float]          # 100 = today
    last: float
    vol: float
    low: float                    # lowest close of the year, as a share of today
    low_date: str
    protection_today: float       # protection level as a share of today's price
    upside: float | None
    currency: str | None


@dataclass
class Card:
    product: Product
    legs: list[Leg]
    vol: float | None = None
    corr_avg: float | None = None
    corr_min: float | None = None
    upside: float | None = None
    worst_low: float | None = None
    worst_name: str | None = None
    protection_today: float | None = None   # closest name
    fall: float | None = None               # fall to protection, e.g. -0.28
    hit: bool = False
    notes: list[str] = field(default_factory=list)
    coupon_to_maturity: float | None = None


def _logret(series: list[tuple[str, float]]) -> dict[str, float]:
    out = {}
    for (d0, c0), (d1, c1) in zip(series, series[1:]):
        if c0 > 0 and c1 > 0:
            out[d1] = math.log(c1 / c0)
    return out


def _corr(a: dict[str, float], b: dict[str, float]) -> float | None:
    common = sorted(set(a) & set(b))
    if len(common) < 30:
        return None
    x, y = [a[d] for d in common], [b[d] for d in common]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sx = math.sqrt(sum((v - mx) ** 2 for v in x)); sy = math.sqrt(sum((v - my) ** 2 for v in y))
    return sum((u - mx) * (v - my) for u, v in zip(x, y)) / (sx * sy) if sx and sy else None


ASIA = (".T", ".HK", ".KS", ".AX", ".TW", ".SS", ".SZ", ".NS")
EUROPE = (".SW", ".PA", ".DE", ".AS", ".MI", ".MC", ".L", ".ST", ".CO", ".OL", ".HE", ".BR", ".LS", ".IR", ".VI", ".F")
EU_INDEX = {"^STOXX50E", "^SSMI", "^GDAXI", "^FCHI", "^FTSE", "^OMX"}


def region(symbol: str) -> str:
    if symbol in ("^N225", "^HSI") or symbol.endswith(ASIA):
        return "asia"
    if symbol in EU_INDEX or symbol.endswith(EUROPE):
        return "europe"
    return "americas"


def _weekly(series: list[tuple[str, float]]) -> dict[str, float]:
    """Friday-to-Friday log returns: markets that close at different hours are compared fairly."""
    last: dict[str, float] = {}
    for d, c in series:
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        last[f"{y}-{w:02d}"] = c
    keys = sorted(last)
    return {k1: math.log(last[k1] / last[k0]) for k0, k1 in zip(keys, keys[1:]) if last[k0] > 0 and last[k1] > 0}


def _vol(r: dict[str, float]) -> float:
    v = list(r.values())
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1) * 252)


def _year(series, asof: dt.date):
    start = (asof - dt.timedelta(days=365)).isoformat()
    return [(d, c) for d, c in series if start <= d <= asof.isoformat()]


def analyse(products: list[Product], asof: dt.date, core: CoreList, swap_test: bool = True, log=print) -> list[Card]:
    used = {u.symbol for p in products for u in p.underlyings if u.symbol}
    syms = sorted({u.symbol for p in products for u in p.underlyings if u.symbol})
    px = closes(syms, asof)
    for s in syms:
        if s not in px:
            log(f"    WARNING no prices for {s}: it is left out of the charts and figures.")
    cards = []
    for p in products:
        if p.product_type == "cash":
            continue
        legs, rets, series = [], {}, {}
        for u in p.underlyings:
            ser = _year(px.get(u.symbol, []), asof)
            if len(ser) < 20:
                continue
            last = ser[-1][1]
            low_d, low_c = min(ser, key=lambda t: t[1])
            prot = p.protection or 1.0
            prot_today = prot * (u.initial_level / last) if u.initial_level and p.initial_fixing and \
                p.initial_fixing <= asof.isoformat() else prot
            info = profile(u.symbol)
            target = info.get("targetMeanPrice")
            k = kind(u.symbol, info)
            r = _logret(ser)
            rets[u.symbol], series[u.symbol] = r, ser
            legs.append(Leg(u.symbol, u.short_name or u.name, u.long_name or u.name, k,
                            [d for d, _ in ser], [100 * c / last for _, c in ser], last, _vol(r),
                            low_c / last, low_d, prot_today,
                            (target / info.get("currentPrice", last) - 1) if (target and k == "share" and info.get("numberOfAnalystOpinions")) else
                            (target / last - 1) if (target and k == "share") else None,
                            u.currency))
        c = Card(product=p, legs=legs)
        if legs:
            c.vol = sum(l.vol for l in legs) / len(legs)
            mixed = len({region(l.symbol) for l in legs}) > 1
            cr = {l.symbol: _weekly(series[l.symbol]) for l in legs} if mixed else rets
            pairs = [_corr(cr[a.symbol], cr[b.symbol]) for a, b in itertools.combinations(legs, 2)]
            pairs = [x for x in pairs if x is not None]
            if pairs:
                c.corr_avg, c.corr_min = sum(pairs) / len(pairs), min(pairs)
            ups = [l.upside for l in legs if l.upside is not None]
            c.upside = sum(ups) / len(ups) if ups else None
            worst = min(legs, key=lambda l: l.low - l.protection_today)
            c.worst_low, c.worst_name = worst.low, worst.short
            c.protection_today = max(l.protection_today for l in legs)
            c.fall = c.protection_today - 1
            c.hit = any(l.low <= l.protection_today for l in legs)
        if p.coupon is not None and p.tenor_months:
            c.coupon_to_maturity = p.coupon * p.tenor_months / 12
        c.notes = reading(c, core, asof, swap_test, used)
        cards.append(c)
    return cards


def reading(c: Card, core: CoreList, asof: dt.date, swap_test: bool, used: set = frozenset()) -> list[str]:
    """The two-line reading of the basket, in the deck's wording."""
    legs = c.legs
    if len(legs) == 1:
        return ["Single underlying: no worst-of effect, company risk in one name.",
                "Single-name product: chosen on conviction, no swap test."]
    if c.corr_min is None:
        first = "Correlation not available."
    elif c.corr_min >= 0.60:
        first = "Names move together: low worst-of risk."
    elif c.corr_min < 0.40:
        first = "One low-correlation pair: worst-of risk is the key risk, hence the low strike."
    else:
        first = "Moderate dispersion between names, part of what pays the coupon."
    if any(l.kind in ("index", "etf") for l in legs):
        return [first, "Index or ETF basket: no swap test."]
    if not swap_test:
        return [first]
    return [first, swap(c, core, asof, used)]


def swap(c: Card, core: CoreList, asof: dt.date, used: set = frozenset()) -> str:
    """Try each same-theme Core List name in place of each basket name; suggest one only when it
    clearly improves the weakest correlation (by 0.15 or more, to at least 0.40). Names already in
    another product of the proposal are not suggested, to keep the portfolio spread."""
    themes = [core.theme_of(l.symbol) for l in c.legs]
    themes = [t for t in themes if t]
    if not themes or c.corr_min is None:
        return "Swap test: names outside the Core List, not tested."
    theme = max(set(themes), key=themes.count)
    cands = [r for r in core.by_theme(theme) if r["symbol"] not in used]
    if not cands:
        return "Swap test: no better combination within the theme."
    px = closes([r["symbol"] for r in cands], asof)
    rets = {l.symbol: _logret(_year(closes([l.symbol], asof).get(l.symbol, []), asof)) for l in c.legs}
    best = None
    for r in cands:
        if r["symbol"] not in px:
            continue
        rr = _logret(_year(px[r["symbol"]], asof))
        for out in c.legs:
            keep = [l for l in c.legs if l is not out]
            pairs = [_corr(rets[a.symbol], rets[b.symbol]) for a, b in itertools.combinations(keep, 2)]
            pairs += [_corr(rr, rets[k.symbol]) for k in keep]
            if any(x is None for x in pairs):
                continue
            mn = min(pairs)
            if mn >= max(0.40, c.corr_min + 0.15) and (best is None or mn > best[0]):
                best = (mn, r["name"], out.short)
    if best:
        sym = next(r["symbol"] for r in cands if r["name"] == best[1])
        name = profile(sym).get("longName") or best[1].title()
        return f"Alternative worth pricing: {name} for {best[2]}."
    return "Swap test: no better combination within the theme."


# ---------------------------------------------------------------------------------------------
# portfolio

def portfolio(products: list[Product], cards: list[Card], clusters: dict[str, list[int]]) -> dict:
    cash = sum(p.weight or 0 for p in products if p.product_type == "cash")
    invest = [c for c in cards]
    if any(c.product.weight is None for c in invest):          # no weights: equal shares of the invested part
        for c in invest:
            c.product.weight = (1 - cash) / len(invest)
    w = {c.product.number: c.product.weight or 0 for c in invest}
    wi = sum(w.values())
    coupon_inv = sum(w[c.product.number] * (c.product.coupon or 0) for c in invest) / wi if wi else 0
    idx = sum(w[c.product.number] for c in invest if c.legs and all(l.kind == "index" for l in c.legs))
    fall = sum(w[c.product.number] * -(c.fall or 0) for c in invest) / wi if wi else 0
    coupons_full = sum(w[c.product.number] * (c.coupon_to_maturity or 0) for c in invest)
    stress = []
    for move in (0, -0.10, -0.20, -0.30, -0.40):
        loss, below = 0.0, []
        for c in invest:
            p = c.product
            level = 1 + move
            prot = c.protection_today or p.protection or 1
            if level < prot - 1e-12:
                below.append(p.number)
                if p.protection_type and "barrier" in p.protection_type:
                    # below the barrier the product pays the worst performance against the strike
                    redemption = level * (p.barrier or prot) / (prot * (p.strike or 1))
                else:
                    # low strike: shares delivered at the strike price
                    redemption = level / prot
                loss += w[p.number] * (1 - redemption)
        stress.append({"move": move, "coupons": coupons_full, "loss": -loss, "net": coupons_full - loss,
                       "below": below})
    issuers: dict[str, float] = {}
    for c in invest:
        issuers[c.product.issuer or "TBD"] = issuers.get(c.product.issuer or "TBD", 0) + w[c.product.number]
    cluster_w = {name: sum(w.get(n, 0) for n in nums) for name, nums in clusters.items()}
    return {"cash": cash, "invested": wi, "coupon_invested": coupon_inv, "coupon_total": coupon_inv * wi,
            "index_weight": idx, "fall": fall, "coupons_full": coupons_full, "stress": stress,
            "issuers": issuers, "cluster_weights": cluster_w, "n": len(invest),
            "n_issuers": len([i for i in issuers if i != "TBD"]),
            "issuers_tbd": sum(1 for c in invest if (c.product.issuer or "TBD") == "TBD"),
            "max_issuer": max([v for k, v in issuers.items() if k != "TBD"] or [0]),
            "strike_min": min((c.product.strike for c in invest if c.product.protection_type == "low strike" and c.product.strike), default=None),
            "strike_max": max((c.product.strike for c in invest if c.product.protection_type == "low strike" and c.product.strike), default=None),
            "barriers": sorted({c.product.barrier for c in invest if c.product.barrier}),
            "tenor_min": min((c.product.tenor_months for c in invest if c.product.tenor_months), default=None),
            "tenor_max": max((c.product.tenor_months for c in invest if c.product.tenor_months), default=None),
            "n_stepdown": sum(1 for c in invest if c.product.stepdown),
            "n_index": sum(1 for c in invest if c.legs and all(l.kind == "index" for l in c.legs))}
