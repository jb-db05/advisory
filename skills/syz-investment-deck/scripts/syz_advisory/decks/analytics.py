"""Figures for the decks, each labelled observed / calculated / assumed.

    observed    read from a source (factsheet, Yahoo close, case file)
    calculated  derived here from observed inputs, by a stated method
    assumed     a convention filled in because the source is silent (always flagged)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date

from syz_advisory.decks.sources import Series, Terms
from syz_advisory.structuring import payoffs as P

TRADING_DAYS = 252


# ------------------------------------------------------------------ series statistics
def total_return(closes: list[float]) -> float | None:
    return closes[-1] / closes[0] - 1 if len(closes) >= 2 and closes[0] else None


def volatility(closes: list[float]) -> float | None:
    """Annualised standard deviation of daily log returns."""
    r = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a and b]
    if len(r) < 20:
        return None
    mean = sum(r) / len(r)
    return math.sqrt(sum((x - mean) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(TRADING_DAYS)


def max_drawdown(closes: list[float]) -> float | None:
    if len(closes) < 2:
        return None
    peak, worst = closes[0], 0.0
    for c in closes:
        peak = max(peak, c)
        worst = min(worst, c / peak - 1)
    return worst


def rebase(closes: list[float], base: float | None = None, to: float = 100.0) -> list[float]:
    base = base or (closes[0] if closes else None)
    return [round(c / base * to, 4) for c in closes] if base else []


def align(series: list[Series]) -> tuple[list[str], list[list[float | None]]]:
    """Common date axis (union), each series carried forward over gaps (holidays differ by market)."""
    dates = sorted({d for s in series for d in s.dates})
    out = []
    for s in series:
        lookup = dict(zip(s.dates, s.closes))
        last, col = None, []
        for d in dates:
            last = lookup.get(d, last)
            col.append(last)
        out.append(col)
    return dates, out


# ------------------------------------------------------------------ structured products
@dataclass
class UnderlyingStatus:
    name: str
    symbol: str
    initial: float | None
    initial_source: str
    last: float | None
    last_date: str
    level: float | None            # last / initial
    min_level: float | None        # lowest close / initial since the initial fixing
    flags: list[str] = field(default_factory=list)


@dataclass
class ProductStatus:
    underlyings: list[UnderlyingStatus]
    worst: UnderlyingStatus | None
    worst_level: float | None
    distance_to_barrier: float | None      # worst level - barrier, in points of initial
    distance_to_strike: float | None
    distance_to_autocall: float | None
    barrier_breached: bool | None          # American barrier: any close at or below it since fixing
    months_left: float | None
    next_observation: date | None
    rag: str                               # green / amber / red / grey (no data) / called / matured
    flags: list[str] = field(default_factory=list)
    called_on: date | None = None          # first past observation where the autocall condition was met
    called_level: float | None = None


def months_between(a: date, b: date) -> float:
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.4


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    day = min(d.day, [31, 29 if (d.year + y) % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m])
    return date(d.year + y, m + 1, day)


def product_status(terms: Terms, prices: dict[str, Series], as_of: date) -> ProductStatus:
    fixing: date | None = terms.get("initial_fixing")
    barrier, strike = terms.get("barrier"), terms.get("strike")
    trigger = terms.get("autocall_trigger")
    flags: list[str] = []
    rows = []
    for u in terms.underlyings:
        s = prices.get(u.symbol)
        uf: list[str] = []
        if not s or not s.closes:
            if u.last is not None and u.initial:
                # No history (e.g. no internet): the market price printed on the factsheet still gives
                # today's level; whether a barrier was touched in between stays unknown.
                rows.append(UnderlyingStatus(u.name, u.symbol, u.initial, "factsheet", u.last, "factsheet date",
                                             u.last / u.initial, None, ["level from the factsheet's market price; no price history"]))
                flags.append(f"{u.name}: level from the factsheet's market price (no price history): "
                             "check the page date; barrier touches not verifiable")
            else:
                rows.append(UnderlyingStatus(u.name, u.symbol, u.initial, "factsheet" if u.initial else "", None, "", None, None,
                                             ["no price history"]))
            continue
        initial, src = u.initial, "factsheet"
        yahoo_fix = s.at_or_before(fixing) if fixing else None
        if initial is None and yahoo_fix is not None:
            initial, src = yahoo_fix, "market close on the initial fixing date (calculated)"
            uf.append("initial level not on the factsheet: market close on the fixing date used")
        elif initial and yahoo_fix and abs(yahoo_fix / initial - 1) > 0.02:
            uf.append(f"factsheet initial {initial:,.2f} vs market close {yahoo_fix:,.2f} on the fixing date "
                      f"({yahoo_fix / initial - 1:+.1%}): check symbol, currency or corporate action")
        since = s.since(fixing) if fixing else s
        last = since.closes[-1] if since.closes else None
        level = last / initial if last and initial else None
        low = min(since.closes) / initial if since.closes and initial else None
        rows.append(UnderlyingStatus(u.name, u.symbol, initial, src, last, since.dates[-1] if since.dates else "",
                                     level, low, uf))
        flags += [f"{u.name}: {x}" for x in uf]
    priced = [r for r in rows if r.level is not None]
    worst = min(priced, key=lambda r: r.level) if priced else None
    wl = worst.level if worst else None
    breached = None
    if barrier is not None and priced and len(priced) == len(rows):
        if (terms.get("barrier_type") or "american") == "american":
            if any(r.min_level is None for r in priced):
                breached = True if any(r.level <= barrier for r in priced) else None    # unknown without history
            else:
                breached = any(r.min_level <= barrier for r in priced)
        else:
            breached = False      # European: only observed at maturity
    final = terms.get("final_fixing")
    months_left = months_between(as_of, final) if final else None
    nxt = None
    freq = terms.get("frequency")
    if fixing and freq:
        k = 1
        while (cand := add_months(fixing, freq * k)) <= as_of:
            k += 1
        nxt = cand if not final or cand <= final else None
    if wl is None:
        rag = "grey"
    elif breached or (barrier is not None and wl <= barrier) or (barrier is None and strike is not None and wl < strike):
        rag = "red"
    elif (barrier is not None and wl - barrier < 0.15) or (barrier is None and strike is not None and wl - strike < 0.10):
        rag = "amber"
    else:
        rag = "green"
    if priced and len(priced) < len(rows):
        flags.append("worst-of computed on the underlyings with prices only")
    called_on, called_level = _autocall_check(terms, rows, prices, as_of)
    if called_on:
        rag = "called"
        flags.append(f"autocall condition met on {called_on:%d %b %Y} (worst-of {called_level:.0%} vs trigger {trigger:.0%}, "
                     "daily closes): the product was probably redeemed early -- confirm with the issuer")
        nxt = None
    elif final and final < as_of:
        rag = "matured"
        flags.append(f"final fixing {final:%d %b %Y} has passed: show the redemption, not a live position")
    return ProductStatus(rows, worst, wl,
                         wl - barrier if wl is not None and barrier is not None else None,
                         wl - strike if wl is not None and strike is not None else None,
                         wl - trigger if wl is not None and trigger is not None else None,
                         breached, months_left, nxt, rag, flags, called_on, called_level)


def _autocall_check(terms: Terms, rows: list[UnderlyingStatus], prices: dict[str, Series],
                    as_of: date) -> tuple[date | None, float | None]:
    """First past observation date on which every underlying closed at or above the
    autocall trigger -- estimated from daily closes and the coupon frequency, because the
    issuer's observation schedule is rarely on a factsheet."""
    trigger, fixing, freq = terms.get("autocall_trigger"), terms.get("initial_fixing"), terms.get("frequency")
    final = terms.get("final_fixing")
    if not rows or any(r.initial is None for r in rows):
        return None, None
    schedule = terms.get("autocall_schedule")       # [(date, level)] from the term sheet, when it gives one
    if schedule:
        plan = [(d, lvl) for d, lvl in schedule]
    elif trigger is not None and fixing and freq:
        first = terms.get("first_call_months") or freq
        plan, k = [], 0
        while True:
            obs = add_months(fixing, first + k * freq)
            if obs > as_of or (final and obs >= final):
                break
            plan.append((obs, trigger - (terms.get("stepdown") or 0) * k))
            k += 1
    else:
        return None, None
    for obs, level_needed in plan:
        if obs > as_of or (final and obs >= final):
            return None, None
        levels = []
        for r in rows:
            s = prices.get(r.symbol)
            close = s.at_or_before(obs) if s else None
            if close is None:
                return None, None
            levels.append(close / r.initial)
        worst = min(levels)
        if worst >= level_needed:
            return obs, worst
    return None, None


# Product-type text -> payoff family. Words match as prefixes ("autocall" in "Autocallable"),
# the two-/three-letter desk codes (Merle's) only as whole words.
KIND_MAP = [(r"\bautocall", P.AUTOCALL), (r"\bphoenix", P.AUTOCALL), (r"\bexpress", P.AUTOCALL), (r"\btwin.?win", P.TWIN_WIN),
            (r"\bdiscount", P.DISCOUNT), (r"\btracker", P.TRACKER), (r"\btrk\b", P.TRACKER),
            (r"\bbarrier reverse", P.BRC), (r"\bbrc\b", P.BRC), (r"\breverse convertible", P.RC), (r"\brc\b", P.RC),
            (r"\bdc\b", P.DISCOUNT), (r"\bcapital protect", P.CPN), (r"\bcapital guarant", P.CPN), (r"\bcpn\b", P.CPN),
            (r"\bcpc\b", P.CPN), (r"\bbonus", P.BONUS), (r"\bbc\b", P.BONUS), (r"\bac\b", P.AUTOCALL)]


def payoff_product(terms: Terms) -> tuple[P.Product | None, list[str]]:
    """The payoffs.Product behind the diagram, and the assumptions it needed."""
    notes: list[str] = []
    raw = (terms.get("product_type") or "").lower()
    if re.search(r"credit.?linked|\bcln\b", raw):
        return None, ["credit-linked note: the payoff depends on credit events, not on an underlying's level -- no payoff diagram"]
    kind = next((k for pattern, k in KIND_MAP if re.search(pattern, raw)), None)
    if kind is None:
        kind = P.AUTOCALL if terms.get("autocall_trigger") is not None else (P.BRC if terms.get("barrier") is not None else P.RC)
        notes.append(f"product type inferred as {P.KINDS[kind]} from its terms")
    strike = terms.get("strike")
    if strike is None and kind in (P.TRACKER, P.TWIN_WIN, P.BONUS):
        strike = 1.0
    if strike is None and kind == P.CPN:
        strike = 1.0
        notes.append("capital protection: participation assumed to start at 100% of initial")
    if strike is None:
        return None, ["no strike: payoff not drawn"]
    fixing, final = terms.get("initial_fixing"), terms.get("final_fixing")
    tenor = max(1, round(months_between(fixing, final))) if fixing and final else 12
    if not (fixing and final):
        notes.append("tenor assumed 12 months")
    freq = terms.get("frequency")
    if not freq:
        freq = 3
        notes.append("coupon frequency assumed quarterly (only the coupon timing depends on it here)")
    barrier = terms.get("barrier")
    try:
        product = P.Product.from_dict({
            "kind": kind, "tenor_months": min(tenor, 120), "coupon_pa": terms.get("coupon") or 0.0,
            "coupon_type": P.CONDITIONAL if terms.get("coupon_trigger") is not None else P.GUARANTEED,
            "coupon_barrier": terms.get("coupon_trigger"), "memory": bool(terms.get("memory")),
            "frequency_months": freq or 3, "strike": strike, "barrier": barrier,
            "barrier_type": "european" if terms.get("barrier_type") == "european" else "american",
            "autocall_trigger": terms.get("autocall_trigger") if kind == P.AUTOCALL else None,
            "first_call_months": terms.get("first_call_months"), "stepdown": terms.get("stepdown") or 0.0,
            "bonus_level": terms.get("bonus_level"), "cap": terms.get("cap"),
            "participation": terms.get("participation") or 1.0, "protection": terms.get("protection") or 1.0,
        })
    except ValueError as exc:
        return None, [f"payoff not drawn: {exc}"]
    if terms.get("coupon") is None and kind in (P.RC, P.BRC, P.AUTOCALL):
        notes.append("coupon missing: diagram shows capital only")
    if kind == P.AUTOCALL and terms.get("autocall_trigger") is None:
        notes.append("autocall trigger not found in the source: early redemptions not shown (the maturity payoff is unaffected)")
    return product, notes


UNDERLYING = "Direct investment in the worst underlying"


def payoff_lines(product: P.Product) -> tuple[list[float], dict[str, list[float | None]]]:
    """Return at maturity per unit of nominal (incl. coupons) against the final level of the
    worst underlying, for each state of the barrier, next to holding the underlying itself."""
    levels = [x / 100 for x in range(20, 161, 5)]
    rows = P.payoff_curve(product, levels)
    direct = [round(x - 1, 4) for x in levels]
    if product.kind in (P.RC, P.CPN, P.TRACKER, P.DISCOUNT) or product.barrier is None:
        return levels, {"Product": [r["barrier_hit"] for r in rows], UNDERLYING: direct}
    return levels, {"Product, barrier not breached": [r["no_barrier_hit"] for r in rows],
                    "Product, barrier breached": [r["barrier_hit"] for r in rows],
                    UNDERLYING: direct}


def breakeven(product: P.Product) -> float | None:
    """Lowest final level of the worst underlying at which the product returns its capital
    (coupons included, barrier assumed breached): the real downside cushion. None when the
    capital comes back even at the lowest level checked (a capital-protected product)."""
    for x in [i / 1000 for i in range(200, 1601)]:
        coupons = product.coupon_pa * product.tenor_months / 12
        if product.coupon_type == P.CONDITIONAL:
            floor = product.coupon_barrier if product.coupon_barrier is not None else product.protection_level
            coupons = coupons if x >= floor else 0.0
        if P._redemption(product, x, True) + coupons >= 1.0 - 1e-9:
            return x if x > 0.2 else None
    return None


def early_redemptions(product: P.Product, terms: Terms, n: int = 4) -> list[dict]:
    """For an autocallable: what the holder receives if called at each of the first `n`
    observations (capital plus the coupons paid by then; memory coupons assumed caught up)."""
    # Only with a trigger read from the source: payoffs.Product defaults a missing trigger to
    # 100 %, which is fine for the shape of a diagram but must not be printed as a term.
    if product.kind != P.AUTOCALL or terms.get("autocall_trigger") is None:
        return []
    schedule = terms.get("autocall_schedule")
    fixing = terms.get("initial_fixing")
    out = []
    first = product.first_call_months or product.frequency_months
    for k in range(n):
        months = first + k * product.frequency_months
        if months >= product.tenor_months:
            break
        when = schedule[k][0] if schedule and k < len(schedule) else (add_months(fixing, months) if fixing else None)
        level = schedule[k][1] if schedule and k < len(schedule) else product.autocall_trigger - product.stepdown * k
        out.append({"months": months, "date": when, "trigger": level,
                    "return": product.coupon_pa * months / 12})
    return out


def scenarios(product: P.Product, status: ProductStatus, shocks=(0.10, 0.0, -0.10, -0.20, -0.30)) -> list[dict]:
    """Return at maturity if the worst underlying moved by `shock` from today and stayed there.
    Ignores early redemption and path; an American barrier already breached stays breached."""
    if status.worst_level is None or status.rag in ("called", "matured"):
        return []
    out = []
    coupons = product.coupon_pa * product.tenor_months / 12
    for s in shocks:
        final = status.worst_level * (1 + s)
        hit = bool(status.barrier_breached) or (product.barrier is not None and final <= product.barrier)
        paid = coupons
        if product.coupon_type == P.CONDITIONAL:
            floor = product.coupon_barrier if product.coupon_barrier is not None else product.protection_level
            paid = coupons if final >= floor else 0.0
        redemption = P._redemption(product, final, hit)
        out.append({"shock": s, "final_level": final, "redemption": redemption, "total": redemption + paid - 1})
    return out


# ------------------------------------------------------------------ bonds
def _cashflows(coupon: float, maturity: date, as_of: date, freq: int = 1) -> list[tuple[float, float]]:
    """(years from as_of, amount per 100 nominal), coupons counted back from maturity."""
    flows, k = [], 0
    while True:
        d = add_months(maturity, -12 // freq * k)
        if d <= as_of:
            break
        flows.append(((d - as_of).days / 365.25, 100 * coupon / freq))
        k += 1
    flows.sort()
    if flows:
        t, c = flows[-1]
        flows[-1] = (t, c + 100)
    return flows


def bond_price(ytm: float, coupon: float, maturity: date, as_of: date, freq: int = 1) -> float:
    return sum(cf / (1 + ytm / freq) ** (freq * t) for t, cf in _cashflows(coupon, maturity, as_of, freq))


def bond_yield(price: float, coupon: float, maturity: date, as_of: date, freq: int = 1) -> float | None:
    """Yield to maturity (annual, compounded `freq` times) from a dirty price per 100, by bisection."""
    if not price or maturity <= as_of:
        return None
    lo, hi = -0.5, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if bond_price(mid, coupon, maturity, as_of, freq) > price:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 6)


def bond_duration(ytm: float, coupon: float, maturity: date, as_of: date, freq: int = 1) -> dict:
    """Macaulay and modified duration (years) and convexity."""
    flows = _cashflows(coupon, maturity, as_of, freq)
    disc = [(t, cf / (1 + ytm / freq) ** (freq * t)) for t, cf in flows]
    price = sum(v for _, v in disc)
    if not price:
        return {}
    mac = sum(t * v for t, v in disc) / price
    conv = sum(v * t * (t + 1 / freq) for t, v in disc) / (price * (1 + ytm / freq) ** 2)
    return {"macaulay": mac, "modified": mac / (1 + ytm / freq), "convexity": conv}


def bond_rows(holdings: list[dict], as_of: date) -> tuple[list[dict], list[str]]:
    """Bond positions with yield and duration -- as given in the input, else calculated
    from price, coupon and maturity (clean price used as dirty: accrued interest ignored)."""
    out, notes = [], []
    for h in holdings:
        if (h.get("asset_class") or "").lower() != "bonds" or not h.get("maturity"):
            continue
        mat = date.fromisoformat(h["maturity"]) if isinstance(h["maturity"], str) else h["maturity"]
        coupon = h.get("coupon") or 0.0
        ytm, src = h.get("ytm"), "input"
        if ytm is None and h.get("price"):
            ytm, src = bond_yield(h["price"], coupon, mat, as_of, h.get("frequency") or 1), "calculated"
        dur = h.get("duration")
        if dur is None and ytm is not None:
            dur = bond_duration(ytm, coupon, mat, as_of, h.get("frequency") or 1).get("modified")
        out.append({**h, "maturity_date": mat, "ytm": ytm, "ytm_source": src, "mod_duration": dur,
                    "years": (mat - as_of).days / 365.25})
        if ytm is None:
            notes.append(f"{h.get('name')}: no yield (needs a price or a yield column)")
    return out, notes


# ------------------------------------------------------------------ portfolios
def weights(holdings: list[dict]) -> list[dict]:
    """Adds `weight` from `value` when only values are given; checks the weights sum to 1."""
    total = sum(h.get("value") or 0 for h in holdings)
    out = []
    for h in holdings:
        w = h.get("weight")
        if w is None and total:
            w = (h.get("value") or 0) / total
        out.append({**h, "weight": w})
    return out


def breakdown(holdings: list[dict], key: str) -> list[tuple[str, float]]:
    agg: dict[str, float] = {}
    for h in holdings:
        agg[h.get(key) or "Other / not classified"] = agg.get(h.get(key) or "Other / not classified", 0) + (h.get("weight") or 0)
    return sorted(agg.items(), key=lambda kv: -kv[1])


def concentration(holdings: list[dict]) -> dict:
    w = sorted((h.get("weight") or 0 for h in holdings), reverse=True)
    hhi = sum(x * x for x in w)
    return {"positions": len(w), "top1": w[0] if w else None, "top5": sum(w[:5]), "top10": sum(w[:10]),
            "hhi": hhi, "effective_n": 1 / hhi if hhi else None}


def in_currency(series: Series, fx: Series | None) -> Series:
    """A price series restated in another currency with daily FX (carried over FX holidays).
    `fx` is units of the target currency per unit of the series' currency."""
    if fx is None:
        return series
    rates = dict(zip(fx.dates, fx.closes))
    last = fx.at_or_before(date.fromisoformat(series.dates[0])) if series.dates else None
    closes = []
    for d, c in zip(series.dates, series.closes):
        last = rates.get(d, last)
        closes.append(c * last if last else None)
    pairs = [(d, c) for d, c in zip(series.dates, closes) if c is not None]
    return Series(series.symbol, [d for d, _ in pairs], [c for _, c in pairs], series.source + " in reporting currency", series.adjusted)


def proxy_performance(holdings: list[dict], prices: dict[str, Series]) -> tuple[list[str], list[float], float]:
    """Today's weights applied to past prices, rebased to 100: an illustration of the current
    allocation, NOT the portfolio's actual performance (no trades, flows or fees).
    Returns dates, values and the share of the portfolio covered by price history."""
    priced = [h for h in holdings if h.get("symbol") in prices and prices[h["symbol"]].closes]
    covered = sum(h["weight"] or 0 for h in priced)
    if not priced or covered <= 0:
        return [], [], 0.0
    dates, cols = align([prices[h["symbol"]] for h in priced])
    values = []
    for i in range(len(dates)):
        v, wsum = 0.0, 0.0
        for h, col in zip(priced, cols):
            first = next((c for c in col if c is not None), None)
            if col[i] is not None and first:
                v += h["weight"] * col[i] / first
                wsum += h["weight"]
        values.append(round(v / wsum * 100, 4) if wsum else None)
    return dates, values, covered
