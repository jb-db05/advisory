"""Step 3 and 4: match every name to a Yahoo symbol, then fill what the documents did not say.

Market data comes from Yahoo Finance through yfinance: daily closes (not adjusted for dividends,
the levels a product observes), long names, currencies and the analysts' mean target price.
Answers are cached in a JSON file, so a rebuild with --offline works without the network.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from .model import Product
from .names import BUILTIN, ETFS, INDICES, SHORT, CoreList, norm

CACHE: dict = {}
CACHE_PATH: Path | None = None
OFFLINE = False


def use_cache(path: Path, offline: bool = False) -> None:
    global CACHE, CACHE_PATH, OFFLINE
    CACHE_PATH, OFFLINE = path, offline
    if path.exists():
        CACHE = json.loads(path.read_text(encoding="utf-8"))


def save_cache() -> None:
    if CACHE_PATH:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(CACHE), encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# symbols

def yahoo_search(name: str) -> str | None:
    key = f"search:{norm(name)}"
    if key in CACHE or OFFLINE:
        return CACHE.get(key)
    try:
        import yfinance as yf
        quotes = yf.Search(name, max_results=8, news_count=0).quotes
    except Exception:
        quotes = []
    best = next((q["symbol"] for q in quotes if q.get("quoteType") in ("EQUITY", "ETF", "INDEX")), None)
    CACHE[key] = best
    return best


def resolve(products: list[Product], tickers: dict[str, str], core: CoreList, log=print) -> None:
    for p in products:
        for u in p.underlyings:
            key = norm(u.name)
            if u.name in tickers or key in {norm(k) for k in tickers}:
                u.symbol = tickers.get(u.name) or next(v for k, v in tickers.items() if norm(k) == key)
                u.match = "tickers file"
            elif u.symbol:
                pass                                   # Bloomberg ticker in the document
            elif key in BUILTIN:
                u.symbol, u.match = BUILTIN[key], "built-in table"
            elif core.find(u.name):
                u.symbol, u.match = core.find(u.name)["symbol"], "Core List"
            else:
                u.symbol, u.match = yahoo_search(u.name), "Yahoo search (confirm)"
            flag = "" if u.symbol else "   <-- not found: add it to the tickers file"
            log(f"    {p.number:>2} {u.name:<28} -> {u.symbol or '?':<11} ({u.match}){flag}")


# ---------------------------------------------------------------------------------------------
# prices and profiles

def closes(symbols: list[str], asof: dt.date, years: float = 1.0) -> dict[str, list[tuple[str, float]]]:
    """Daily closes per symbol, from one year (plus a margin) before `asof` up to `asof`."""
    out, missing = {}, []
    for s in symbols:
        key = f"px:{s}:{asof}"
        if key in CACHE:
            out[s] = CACHE[key]
        else:
            missing.append(s)
    if missing and not OFFLINE:
        import yfinance as yf
        start = asof - dt.timedelta(days=int(366 * years) + 10)
        df = yf.download(missing, start=start.isoformat(), end=(asof + dt.timedelta(days=1)).isoformat(),
                         auto_adjust=False, progress=False, threads=True)
        close = df["Close"] if "Close" in df else df
        for s in missing:
            if s in close:
                ser = close[s].dropna()
                if len(ser) > 20:
                    out[s] = CACHE[f"px:{s}:{asof}"] = [(d.strftime("%Y-%m-%d"), round(float(v), 6)) for d, v in ser.items()]
    return out


def profile(symbol: str) -> dict:
    key = f"info:{symbol}"
    if key in CACHE or OFFLINE:
        return CACHE.get(key, {})
    info = {}
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        raw = t.info or {}
        info = {k: raw.get(k) for k in ("longName", "shortName", "currency", "targetMeanPrice", "quoteType",
                                        "numberOfAnalystOpinions", "sector", "currentPrice", "exchange")}
        if not info.get("currency"):
            info["currency"] = t.fast_info.currency
    except Exception:
        try:
            import yfinance as yf
            info = {"currency": yf.Ticker(symbol).fast_info.currency}
        except Exception:
            info = {}
    CACHE[key] = info
    return info


def kind(symbol: str | None, info: dict | None = None) -> str:
    if not symbol:
        return "unknown"
    if symbol in INDICES or symbol.startswith("^") or (info or {}).get("quoteType") == "INDEX":
        return "index"
    if symbol in ETFS or (info or {}).get("quoteType") == "ETF":
        return "etf"
    return "share"


def complete(products: list[Product], asof: dt.date, log=print) -> None:
    """Fill the gaps with market data, and say which fields are still missing."""
    for p in products:
        for u in p.underlyings:
            if not u.symbol:
                continue
            info = profile(u.symbol)
            u.currency = u.currency or info.get("currency")
            u.long_name = info.get("longName") or info.get("shortName") or SHORT.get(u.symbol) or u.name
            u.short_name = SHORT.get(u.symbol) or _short(u.long_name)
        # initial levels of a product already struck: the close on the initial fixing date
        if p.initial_fixing and dt.date.fromisoformat(p.initial_fixing) <= asof:
            for u in p.underlyings:
                if u.initial_level is None and u.symbol:
                    px = closes([u.symbol], asof).get(u.symbol, [])
                    on = [c for d, c in px if d <= p.initial_fixing]
                    if on:
                        u.initial_level = on[-1]
                        p.sources[f"initial level {u.short_name}"] = "market data (close on the initial fixing date)"
        if p.tenor_months is None and p.initial_fixing and p.final_fixing:
            a, b = (dt.date.fromisoformat(x) for x in (p.initial_fixing, p.final_fixing))
            p.tenor_months = round((b - a).days / 30.44)
            p.sources["tenor_months"] = "calculated from the fixing dates"
        if not p.issuer:
            p.issuer, p.sources["issuer"] = "TBD", "missing (shown as TBD)"
        if not p.currency:
            ccys = {u.currency for u in p.underlyings if u.currency}
            p.sources["currency"] = "missing"
        if p.protection is None:
            log(f"    WARNING product {p.number}: no strike or barrier found.")
        if p.tenor_months is None:
            log(f"    WARNING product {p.number}: no maturity found.")


def _short(name: str) -> str:
    name = re.sub(r",?\s+(Inc\.?|Corporation|Corp\.?|plc|AG|SA|S\.A\.|SE|N\.V\.|Ltd\.?|Limited|Holding|Holdings|Group|Company|Co\.)\b.*$", "", name or "")
    return name.strip() or name
