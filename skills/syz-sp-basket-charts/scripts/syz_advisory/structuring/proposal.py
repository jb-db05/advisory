"""An investment proposal of structured products, read from its CSV and set against price history.

The proposal sheet has one row per product: a basket of up to three underlyings, a coupon,
the downside protection ("European Barrière 65%" or "Low strike 72%"), tenor, weight, fees,
step-down and size. Each product is assumed struck at today's close, so every underlying is
rebased to 100 at its latest close and the strike and barrier are drawn as a % of that level.
Prices are raw closes in the underlying's own currency: the levels a product observes.
"""

from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

# Names the reference data or Yahoo's search get wrong for this kind of sheet: (symbol, name).
_CAC, _NDX, _RUT = ("^FCHI", "CAC 40"), ("^NDX", "Nasdaq 100"), ("^RUT", "Russell 2000")
_TSM, _JPM = ("TSM", "Taiwan Semiconductor"), ("JPM", "JPMorgan Chase")
_INDICES = {
    ("NIKKEI 225", "NIKKEI"): ("^N225", "Nikkei 225"),
    ("EURO STOXX 50", "EUROSTOXX 50", "SX5E"): ("^STOXX50E", "Euro Stoxx 50"),
    ("S&P 500", "S&P500", "SPX"): ("^GSPC", "S&P 500"),
    ("SMI", "SWISS MARKET INDEX"): ("^SSMI", "SMI"),
    ("DAX",): ("^GDAXI", "DAX"),
    ("FTSE 100", "UKX"): ("^FTSE", "FTSE 100"),
    ("HANG SENG", "HSI"): ("^HSI", "Hang Seng"),
    ("OMX", "OMX STOCKHOLM 30", "OMXS30"): ("^OMX", "OMX Stockholm 30"),
}
OVERRIDES = {
    "CAC 40": _CAC, "CAC 40 INDEX": _CAC, "NASDAQ 100": _NDX, "NASDAQ 100 INDEX": _NDX,
    "RUSSELL 2000": _RUT, "RUSSELL 2000 INDEX": _RUT, "TSM": _TSM, "TSMC": _TSM,
    "JP MORGAN": _JPM, "JPMORGAN": _JPM,
    "ROCHE": ("ROP.SW", "Roche"),       # the Genussschein (ROG SE), Yahoo's liquid Roche line
    **{k: v for keys, v in _INDICES.items() for name in keys for k in (name, f"{name} INDEX")},
}
# Company-form words dropped from names for labels.
_SUFFIX = re.compile(r",? (Inc\.?|Corporation|Corp\.?|plc|S\.?A\.?|SE|SCA|AG|N\.?V\.?|NV|Ltd\.?|Limited|Holdings?|"
                     r"Holding|Group|Gruppe|Company|Incorporated|Class [A-C]|ETF)\b.*$")
_ACRONYMS = {"TSM", "ASML", "VAT", "ABBN", "UBS", "BNP", "RWE", "LVMH", "JP", "CAC", "S&P", "X", "ETF"}


def short_name(name: str) -> str:
    """'Apple Inc.' -> 'Apple', 'NVIDIA Corporation' -> 'NVIDIA', 'Eli Lilly and Company' -> 'Eli Lilly'."""
    name = re.sub(r"^The ", "", name.strip())
    return re.sub(r" and$", "", _SUFFIX.sub("", name)).strip() or name


def sheet_case(text: str) -> str:
    """A shouted sheet name in reading case, keeping tickers: 'JP MORGAN' -> 'JP Morgan'."""
    if not text.isupper():
        return text.strip()
    return " ".join(w if w in _ACRONYMS or any(c.isdigit() for c in w) else w[:1] + w[1:].lower()
                    for w in text.split() if w != "INDEX")

WINDOWS = {"1y": 365, "3y": 3 * 365, "5y": 5 * 365}


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().upper())


def _number(text: str) -> float | None:
    """'€ 1’040’000.00 ' -> 1040000.0, '7.00%' -> 7.0; None when there is no number."""
    cleaned = re.sub(r"[^\d.\-]", "", text or "")
    try:
        return float(cleaned) if re.search(r"\d", cleaned) else None
    except ValueError:
        return None


def _pct(text: str) -> float | None:
    value = _number(text)
    return value / 100 if value is not None else None


def parse_protection(text: str) -> dict:
    """'European Barrière 65%' -> strike 100%, European barrier 65%;
    'Low strike 72%' -> strike 72%, no barrier (the strike is the protection)."""
    level = _pct(text)
    low = text.lower()
    if "strike" in low:
        return {"kind": "low_strike", "strike": level, "barrier": None, "barrier_type": None,
                "label": f"Low strike {level:.0%}" if level else text.strip()}
    if "barri" in low:
        kind = "european" if "europ" in low else "american" if "americ" in low else ""
        return {"kind": "barrier", "strike": 1.0, "barrier": level, "barrier_type": kind or None,
                "label": f"{kind.title() + ' b' if kind else 'B'}arrier {level:.0%}" if level else text.strip()}
    return {"kind": "other", "strike": 1.0, "barrier": None, "barrier_type": None, "label": text.strip()}


def read_csv(path: Path) -> dict:
    """The products and the cash line of a proposal sheet: a CSV file, or a table pasted in a chat and
    saved as text (tab-separated when copied from Excel; semicolons from a French or Swiss Excel).
    Only Basket, the Underlying columns and Downside protection are needed."""
    text = path.read_text(encoding="utf-8-sig")
    head_line = next((ln for ln in text.splitlines() if ln.strip().lower().startswith("basket")), "")
    delimiter = max("\t;,", key=head_line.count) if head_line else ","
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    head = next((i for i, r in enumerate(rows) if r and r[0].strip().lower() == "basket"), None)
    if head is None:
        raise ValueError(f"{path.name}: no header row starting with 'Basket'")
    cols = {c.strip().lower(): j for j, c in enumerate(rows[head]) if c.strip()}

    def cell(r: list[str], name: str) -> str:
        j = cols.get(name)
        return r[j].strip() if j is not None and j < len(r) else ""

    under = [j for c, j in sorted(cols.items(), key=lambda x: x[1]) if c.startswith("underlying")]

    def ccy(r: list[str]) -> str | None:
        return (cell(r, "ccy") or cell(r, "currency")).upper() or None
    products, cash = [], None
    for r in rows[head + 1:]:
        first = r[0].strip() if r else ""
        if first.upper() == "CASH":
            cash = {"weight": _pct(cell(r, "weight")), "size": _number(cell(r, "size")), "ccy": ccy(r)}
        elif first.isdigit():
            names = [r[j].strip() for j in under if j < len(r) and r[j].strip()]
            tenor = _number(cell(r, "maturity"))
            products.append({
                "no": int(first), "names": names,
                "coupon": _pct(cell(r, "coupon")),
                "protection": parse_protection(cell(r, "downside protection")),
                "tenor_months": int(tenor) if tenor else None,
                "weight": _pct(cell(r, "weight")), "fees": _pct(cell(r, "fees")),
                "stepdown": cell(r, "stepdown") or None, "size": _number(cell(r, "size")), "ccy": ccy(r),
            })
    if not products:
        raise ValueError(f"{path.name}: no product rows")
    return {"products": products, "cash": cash}


def search_matcher(client):
    """A matcher on Yahoo's search alone, for use without the Core List: the hit whose name shares
    most words with the query, an index before a share before an ETF."""
    rank = {"INDEX": 0, "EQUITY": 1, "ETF": 2}

    def words(s: str) -> set[str]:
        plain = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()   # Nestlé -> nestle
        return set(re.findall(r"[a-z0-9&]+", plain)) - {"index", "inc", "the", "sa", "ag", "plc", "corp"}

    def match(payload: dict) -> dict:
        out = []
        for text in payload.get("names") or []:
            try:
                hits = [h for h in client.search(text) if h.get("type") in rank]
            except Exception:
                hits = []
            q = words(text)
            best = min(hits, key=lambda h: (-len(q & words(h.get("name") or "")), rank[h["type"]]), default=None)
            out.append({"query": text, "yahoo": best and best["symbol"], "name": best and best.get("name"),
                        "how": "search" if best else ""})
        return {"results": out}
    return match


def read_tickers(path: Path) -> dict[str, str]:
    """Advisor-checked symbols, {"sheet name": "SYMBOL"}, from JSON or a two-column CSV."""
    if path.suffix.lower() == ".json":
        return {str(k): str(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r[0].strip(): r[1].strip() for r in csv.reader(f) if len(r) >= 2 and r[0].strip() and r[1].strip()}


def resolve(names: list[str], matcher, extra: dict[str, str] | None = None) -> dict[str, dict]:
    """Sheet names to Yahoo symbols: `extra` (checked by the advisor) first, then OVERRIDES, then
    `matcher` (service.match's shape: {"names": [...]} -> {"results": [{"query", "yahoo", "name",
    "how"}]}), 20 at a time."""
    out, rest = {}, []
    given = {_key(k): v for k, v in (extra or {}).items()}
    for n in dict.fromkeys(names):
        if _key(n) in given:
            out[n] = {"yahoo": given[_key(n)], "name": None, "how": "tickers file"}
        elif _key(n) in OVERRIDES:
            sym, name = OVERRIDES[_key(n)]
            out[n] = {"yahoo": sym, "name": name, "how": "override"}
        else:
            rest.append(n)
    for i in range(0, len(rest), 20):
        for hit in matcher({"names": rest[i:i + 20]})["results"]:
            out[hit["query"]] = {"yahoo": hit.get("yahoo"), "name": hit.get("name"), "how": hit.get("how") or ""}
    return out


def closes(client, symbol: str) -> list[tuple[str, float]]:
    """Five years of raw daily closes, oldest first; [] when Yahoo has none."""
    try:
        bars = client.chart(symbol, "5y", "1d")
    except Exception:
        return []
    return [(b["date"], float(b["close"])) for b in bars if b.get("close")]


def _aligned(series: list[list[tuple[str, float]]]) -> tuple[list[str], list[list[float]]]:
    """One date axis for the basket (any market open), each name carried forward over its
    holidays, from the first date every name has a close."""
    start = max(s[0][0] for s in series)
    dates = sorted({d for s in series for d, _ in s if d >= start})
    maps = [dict(s) for s in series]
    rows, last = [], [None] * len(series)
    for d in dates:
        for j, m in enumerate(maps):
            if d in m:
                last[j] = m[d]
            elif last[j] is None:   # no close on `start` itself: take the one before
                last[j] = next((v for k, v in reversed(series[j]) if k <= d), None)
        rows.append(list(last))
    return dates, rows


def _vol(values: list[float]) -> float | None:
    rets = [math.log(b / a) for a, b in zip(values, values[1:]) if a and b]
    if len(rets) < 20:
        return None
    m = sum(rets) / len(rets)
    return math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1) * 252)


def analyse(product: dict, hits: list[dict], client, quotes: dict) -> dict:
    """Chart windows rebased to 100 at the latest close, and each underlying against the levels.
    `hits` are resolve()'s entries for the product's names, in order."""
    prot = product["protection"]
    level = prot["barrier"] or prot["strike"]
    symbols = [h.get("yahoo") for h in hits]
    found = [(n, s, closes(client, s) if s else []) for n, s in zip(product["names"], symbols)]
    missing = [n for n, s, h in found if not h]
    ok = [(n, s, h) for n, s, h in found if h]
    named = {n: h.get("name") for n, h in zip(product["names"], hits)}
    out = {**product, "symbols": symbols, "missing": missing, "level": level, "windows": {}, "members": []}
    if not ok:
        return out
    dates, rows = _aligned([h for _, _, h in ok])
    last = rows[-1]
    out["asof"] = dates[-1]
    end = date.fromisoformat(dates[-1])
    for key, days in WINDOWS.items():
        cut = (end - timedelta(days=days)).isoformat()
        idx = [i for i, d in enumerate(dates) if d >= cut]
        if key != "1y":                                   # weekly points beyond a year, plus the last
            idx = idx[::5] + ([idx[-1]] if (len(idx) - 1) % 5 else [])
        out["windows"][key] = {"dates": [dates[i] for i in idx],
                               "lines": [[100 * rows[i][j] / last[j] for i in idx] for j in range(len(ok))],
                               "full": dates[idx[0]] <= (end - timedelta(days=days - 7)).isoformat()}
    year = (end - timedelta(days=365)).isoformat()
    for j, (name, sym, hist) in enumerate(ok):
        y = [v for d, v in hist if d >= year]
        q = quotes.get(sym) or {}
        spot = hist[-1][1]
        full = named.get(name) or q.get("name") or sheet_case(name)
        short = short_name(full)
        out["members"].append({
            "sheet_name": name, "yahoo": sym, "name": full, "currency": q.get("currency") or "",
            "short": short if len(short) <= 18 else sheet_case(name),
            "last": spot, "last_date": hist[-1][0],
            "strike_price": spot * prot["strike"] if prot["strike"] else None,
            "barrier_price": spot * prot["barrier"] if prot["barrier"] else None,
            "buffer": 1 - level if level else None,
            "low_1y": 100 * min(y) / spot if y else None, "high_1y": 100 * max(y) / spot if y else None,
            "change_1y": spot / y[0] - 1 if y else None, "vol_1y": _vol(y),
            # per chart window: lowest point (% of today) and change to today
            "lows": {k: min(w["lines"][j]) for k, w in out["windows"].items()},
            "changes": {k: 100 / w["lines"][j][0] - 1 for k, w in out["windows"].items()},
        })
    # The 1y low that came closest to the protection level, as a % of today.
    lows = [m["low_1y"] for m in out["members"] if m["low_1y"] is not None]
    out["closest_low_1y"] = min(lows) if lows else None
    return out


def build(path: Path, client, matcher, tickers: dict[str, str] | None = None) -> dict:
    """The whole proposal, ready to draw. `tickers` are advisor-checked symbols that win over matching."""
    sheet = read_csv(path)
    names = [n for p in sheet["products"] for n in p["names"]]
    found = resolve(names, matcher, tickers)
    symbols = sorted({v["yahoo"] for v in found.values() if v.get("yahoo")})
    try:
        quotes = client.quotes(symbols)
    except Exception:
        quotes = {}
    products = [analyse(p, [found.get(n, {}) for n in p["names"]], client, quotes)
                for p in sheet["products"]]
    if hasattr(client, "save"):
        client.save()
    invested = [p for p in products if p["weight"] and p["coupon"] is not None]
    w = sum(p["weight"] for p in invested)
    # Sizes are only added up within one currency: a mixed proposal gets a total per currency.
    sized = [x for x in products + [sheet["cash"] or {}] if x.get("size")]
    by_ccy: dict[str | None, float] = {}
    for x in sized:
        by_ccy[x.get("ccy")] = by_ccy.get(x.get("ccy"), 0) + x["size"]
    return {
        "source": path.name, "products": products, "cash": sheet["cash"],
        "matches": found,
        "total_size": sum(p["size"] or 0 for p in products) + ((sheet["cash"] or {}).get("size") or 0),
        "size_by_ccy": by_ccy,
        "coupon_invested": sum(p["weight"] * p["coupon"] for p in invested) / w if w else None,
        "coupon_total": sum(p["weight"] * p["coupon"] for p in invested) if invested else None,
        "asof": max((p.get("asof") or "" for p in products), default=""),
    }
