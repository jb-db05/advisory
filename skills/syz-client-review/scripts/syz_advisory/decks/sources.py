"""Inputs for client presentations: product terms from HTML, market and fund data from Yahoo.

Every value carries where it came from and how sure we are of it. Nothing is
filled in by guesswork: a term that cannot be read is `missing`, two readings that
disagree are `inconsistent`, and both are listed on the deck's sources slide.

HTML factsheets and pricers come in many layouts, so the reader does not depend on
one: it collects label/value pairs from every common pattern (label + value
elements, dt/dd, two-cell table rows, "Label: value" lines), reads underlyings
from tables that carry Bloomberg tickers, and cross-checks the result with the
term-sheet text extractor Merle (B01) uses on PDFs.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from html.parser import HTMLParser

from syz_advisory.termsheets.extract import extract_fields, isin_is_valid, parse_date

OK, MISSING, INCONSISTENT, CALCULATED, ASSUMED = "ok", "missing", "inconsistent", "calculated", "assumed"


@dataclass
class Value:
    value: object = None
    source: str = ""          # "html: 'Coupon Rate'", "text extractor", "case file", "Yahoo Finance", "calculated"
    status: str = MISSING
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (OK, CALCULATED) and self.value is not None


@dataclass
class Underlying:
    name: str
    ticker: str = ""          # Bloomberg, as printed on the factsheet
    symbol: str = ""          # Yahoo
    initial: float | None = None
    currency: str = ""
    symbol_source: str = ""
    last: float | None = None   # market price printed on the page (a fallback when no price history)


@dataclass
class Terms:
    fields: dict[str, Value] = field(default_factory=dict)
    underlyings: list[Underlying] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    source_name: str = ""

    def get(self, key: str, default=None):
        v = self.fields.get(key)
        return v.value if v is not None and v.value is not None else default

    def to_dict(self) -> dict:
        return {"fields": {k: asdict(v) for k, v in self.fields.items()},
                "underlyings": [asdict(u) for u in self.underlyings], "flags": self.flags, "source": self.source_name}


# ------------------------------------------------------------------ HTML -> tree
class _Node:
    __slots__ = ("tag", "attrs", "children", "parent", "text")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children: list = []
        self.text = ""

    @property
    def cls(self) -> str:
        return (self.attrs.get("class") or "").lower()

    def all_text(self) -> str:
        parts = [self.text] + [c.all_text() if isinstance(c, _Node) else c for c in self.children]
        return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, _Node):
                yield from c.iter()


_VOID = {"br", "img", "input", "meta", "link", "hr", "col", "source", "wbr", "area", "base"}


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", [], None)
        self.cur = self.root
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "svg"):
            self.skip += 1
            return
        if self.skip:
            return
        node = _Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in _VOID:
            self.cur = node

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.cur.children.append(data.strip())


def html_text(html: str) -> str:
    """Visible text, one block per line (for the term-sheet text extractor)."""
    t = _Tree()
    t.feed(html)
    lines = []

    def walk(n):
        for c in n.children:
            if isinstance(c, _Node):
                if c.tag in ("tr", "p", "div", "li", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6", "label", "table", "section"):
                    lines.append("\n")
                walk(c)
            else:
                lines.append(c + " ")

    walk(t.root)
    return re.sub(r"[ \t]*\n[\s]*", "\n", "".join(lines)).strip()


def html_pairs(html: str) -> list[tuple[str, str, str]]:
    """(label, value, pattern) pairs from every common factsheet / pricer layout."""
    t = _Tree()
    t.feed(html)
    out: list[tuple[str, str, str]] = []
    for n in t.root.iter():
        kids = [c for c in n.children if isinstance(c, _Node)]
        # dt / dd
        if n.tag == "dl":
            for a, b in zip(kids, kids[1:]):
                if a.tag == "dt" and b.tag == "dd":
                    out.append((a.all_text(), b.all_text(), "dt/dd"))
        # two-cell rows (th/td or td/td)
        if n.tag == "tr":
            cells = [c for c in kids if c.tag in ("td", "th")]
            if len(cells) == 2:
                out.append((cells[0].all_text(), cells[1].all_text(), "table row"))
        # label element followed by a value element in the same parent
        if n.tag == "label" or re.search(r"\b(label|header|key|name|title)\b", n.cls):
            parent = n.parent
            if parent is None:
                continue
            siblings = [c for c in parent.children if isinstance(c, _Node)]
            try:
                after = siblings[siblings.index(n) + 1:]
            except ValueError:
                after = []
            for s in after:
                hit = next((x for x in s.iter() if re.search(r"\b(value|main-content|data-block-value|val)\b", x.cls)), None)
                if hit is None and re.search(r"\b(value|content)\b", s.cls):
                    hit = s
                if hit is not None:
                    out.append((n.all_text(), hit.all_text(), "label/value"))
                    break
    # "Label: value" lines in plain text blocks
    for line in html_text(html).splitlines():
        m = re.match(r"^\s*([A-Za-z][A-Za-z ./()%-]{2,40}?)\s*:\s*(.+?)\s*$", line)
        if m:
            out.append((m.group(1), m.group(2), "text line"))
    return [(re.sub(r"\s+", " ", a).strip(), re.sub(r"\s+", " ", b).strip(), p) for a, b, p in out if a and b]


# ------------------------------------------------------------------ labels -> fields
LABELS: dict[str, list[str]] = {
    "isin": [r"^isin$", r"^isin code$"],
    "valor": [r"^valor", r"^valoren"],
    "issuer": [r"^issuer$", r"^issuer name$", r"^emittent$", r"^issuing entity$"],
    "currency": [r"^(product |settlement |issue )?currency$", r"^ccy$"],
    "product_type": [r"^product type$", r"^type$", r"^sspa (category|type)", r"^product category$"],
    "coupon": [r"^coupon( rate| p\.?a\.?| amount)?$", r"^coupon \(p\.?a\.?\)$"],
    "frequency": [r"(coupon |payment |observation )?frequency$"],
    "strike": [r"^strike( level)?$", r"^strike \(%\)$"],
    "barrier": [r"^(knock-?in |capital protection )?barrier( level)?$", r"^ki level$", r"^barrier \(%\)$"],
    "barrier_type": [r"^barrier (type|observation)$", r"^observation type$"],
    "autocall_trigger": [r"^autocall( trigger)?( level)?$", r"^early redemption (level|trigger)$", r"^call trigger$"],
    "coupon_trigger": [r"^coupon (trigger|barrier)( level)?$"],
    "memory": [r"^memory( coupon| effect)?$"],
    "denomination": [r"^denomination$", r"^nominal (amount )?per note$", r"^specified denomination$"],
    "settlement": [r"^settlement( type)?$", r"^redemption type$", r"^type of settlement$"],
    "initial_fixing": [r"^initial fixing( date)?$", r"^strike date$", r"^pricing date$"],
    "issue_date": [r"^issue date$", r"^initial payment date$"],
    "final_fixing": [r"^final fixing( date)?$", r"^(final )?valuation date$"],
    "maturity": [r"^(redemption|maturity) date$", r"^maturity$"],
    "tenor": [r"^tenor$", r"^term$", r"^duration$"],
    "issue_price": [r"^issue price$"],
    "status": [r"^status$"],
    "participation": [r"^participation( rate)?$", r"^(upside )?participation", r"^gearing$"],
    "cap": [r"^cap( level)?$", r"^maximum (redemption|return)$"],
    "bonus_level": [r"^bonus( level)?$"],
    "protection": [r"^(capital )?protection( level)?$", r"^minimum redemption$"],
}
PERCENT = {"coupon", "strike", "barrier", "autocall_trigger", "coupon_trigger", "issue_price",
           "participation", "cap", "bonus_level", "protection"}
DATES = {"initial_fixing", "issue_date", "final_fixing", "maturity"}
FREQ_MONTHS = {"monthly": 1, "bi-monthly": 2, "bimonthly": 2, "quarterly": 3, "every 4 months": 4, "4 months": 4,
               "semi-annually": 6, "semi-annual": 6, "semiannual": 6, "annually": 12, "annual": 12, "yearly": 12,
               "in fine": 0, "at maturity": 0}

# Bloomberg exchange code -> Yahoo suffix (the common ones on SYZ term sheets).
EXCHANGE = {"US": "", "UN": "", "UW": "", "UQ": "", "UR": "", "UA": "", "UP": "", "GY": ".DE", "GR": ".DE", "GF": ".F",
            "FP": ".PA", "NA": ".AS", "BB": ".BR", "IM": ".MI", "SM": ".MC", "SQ": ".MC", "LN": ".L", "SW": ".SW",
            "SE": ".SW", "VX": ".SW", "SS": ".ST", "DC": ".CO", "FH": ".HE", "NO": ".OL", "AV": ".VI", "ID": ".IR",
            "PL": ".LS", "JP": ".T", "JT": ".T", "HK": ".HK", "AU": ".AX", "AT": ".AX", "CN": ".TO", "CT": ".TO",
            "KS": ".KS", "TT": ".TW", "SP": ".SI", "NZ": ".NZ"}
INDEX = {"SX5E": "^STOXX50E", "SPX": "^GSPC", "NDX": "^NDX", "RTY": "^RUT", "SMI": "^SSMI", "DAX": "^GDAXI",
         "NKY": "^N225", "UKX": "^FTSE", "CAC": "^FCHI", "HSI": "^HSI", "SX7E": "^SX7E", "INDU": "^DJI"}


def yahoo_symbol(bbg: str) -> str:
    """'HNR1 GY Equity' -> 'HNR1.DE'; 'SX5E Index' -> '^STOXX50E'; '' when unsure."""
    parts = bbg.replace("Equity", "").replace("Index", "").split()
    if not parts:
        return ""
    code = parts[0].upper()
    if "index" in bbg.lower() or code in INDEX:
        return INDEX.get(code, "")
    if len(parts) > 1 and parts[1].upper() in EXCHANGE:
        suffix = EXCHANGE[parts[1].upper()]
        if suffix == ".HK":
            code = code.zfill(4)
        return code.replace("/", "-") + suffix
    return ""


def _pct(text: str) -> float | None:
    m = re.search(r"(-?\d+(?:[.,]\d+)?)\s*%", text)
    if not m:
        m = re.fullmatch(r"\s*(-?\d+(?:[.,]\d+)?)\s*", text)
        if not m:
            return None
    v = float(m.group(1).replace(",", "."))
    return round(v / 100, 6)


def _date(text: str) -> date | None:
    m = re.search(r"\d{1,2}[./]\d{1,2}[./]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)? [A-Za-z]+\.? \d{4}|[A-Za-z]+\.? \d{1,2}(?:st|nd|rd|th)?,? \d{4}", text)
    return parse_date(m.group(0)) if m else None


def _parse(key: str, raw: str):
    if key in PERCENT:
        return _pct(raw)
    if key in DATES:
        return _date(raw)
    if key == "frequency":
        low = raw.lower()
        for word, months in sorted(FREQ_MONTHS.items(), key=lambda kv: -len(kv[0])):
            if word in low:
                return months
        return None
    if key == "memory":
        return bool(re.search(r"\b(yes|true|with)\b", raw, re.I)) if raw else None
    if key == "barrier_type":
        low = raw.lower()
        return ("american" if re.search(r"american|continuous|daily", low) else
                "european" if re.search(r"european|at maturity|final", low) else
                "none" if re.search(r"no barrier|none", low) else raw)
    if key == "denomination":
        m = re.search(r"([A-Z]{3})?\s*([\d'’,. ]+)", raw)
        return float(re.sub(r"[^\d.]", "", m.group(2).replace(",", ""))) if m and re.search(r"\d", m.group(2)) else None
    if key == "isin":
        m = re.search(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", raw)
        return m.group(0) if m else None
    if key == "currency":
        m = re.search(r"\b[A-Z]{3}\b", raw)
        return m.group(0) if m else None
    return raw.strip() or None


def _underlying_rows(html: str) -> list[Underlying]:
    """Rows of any table that carry a Bloomberg ticker '(XXX YY Equity)' or 'XXX Index'.

    The initial fixing level is read only from a column whose header names it
    ("Initial", "Initial fixing level", "Strike price" is not it) -- never guessed by position."""
    t = _Tree()
    t.feed(html)
    out = []
    for table in (n for n in t.root.iter() if n.tag == "table"):
        rows = [n for n in table.iter() if n.tag == "tr"]
        initial_col = price_col = None
        for tr in rows:
            heads = [c.all_text().lower() for c in tr.children if isinstance(c, _Node) and c.tag == "th"]
            hit = next((i for i, h in enumerate(heads) if "initial" in h), None)
            if hit is not None:
                initial_col = hit
                price_col = next((i for i, h in enumerate(heads)
                                  if re.search(r"market price|last price|spot|current price|^price$|^last$", h)), None)
                break
        for tr in rows:
            cells = [c.all_text() for c in tr.children if isinstance(c, _Node) and c.tag == "td"]
            joined = " | ".join(cells)
            m = re.search(r"\(?\b([A-Z0-9./]{1,10} (?:[A-Z]{2} )?(?:Equity|Index))\b\)?", joined)
            if not m:
                continue
            ticker = m.group(1)
            name = cells[0].replace(m.group(0), "").strip(" ()|") or ticker
            initial, ccy = None, ""
            if initial_col is not None and initial_col < len(cells):
                n = re.search(r"([A-Z]{3})?\s*(-?\d[\d',]*\.?\d*)", cells[initial_col])
                if n:
                    initial = float(n.group(2).replace("'", "").replace(",", ""))
                    ccy = n.group(1) or ""
            last = None
            if price_col is not None and price_col < len(cells):
                n = re.search(r"([A-Z]{3})?\s*(-?\d[\d',]*\.?\d*)", cells[price_col])
                if n:
                    last = float(n.group(2).replace("'", "").replace(",", ""))
            out.append(Underlying(name=name, ticker=ticker, symbol=yahoo_symbol(ticker), initial=initial,
                                  currency=ccy, symbol_source="mapped from Bloomberg ticker", last=last))
    return out


def read_html_terms(html: str, source_name: str = "factsheet") -> Terms:
    """Product terms from an HTML factsheet, product page or pricer, validated."""
    terms = Terms(source_name=source_name)
    found: dict[str, list[tuple[object, str]]] = {}
    for label, raw, how in html_pairs(html):
        low = label.lower().strip(" :")
        for key, patterns in LABELS.items():
            if any(re.search(p, low) for p in patterns):
                value = _parse(key, raw)
                if value is not None:
                    found.setdefault(key, []).append((value, f"html {how}: '{label}' = '{raw[:60]}'"))
                break
    for key, cands in found.items():
        distinct = list(dict.fromkeys(repr(v) for v, _ in cands))
        value, src = cands[0]
        if len(distinct) > 1:
            terms.fields[key] = Value(value, src, INCONSISTENT, "other readings: " + "; ".join(s for _, s in cands[1:3]))
        else:
            terms.fields[key] = Value(value, src, OK)
    # a coupon quoted per period is annualised -- and flagged, never silently
    raw_coupon = next((raw for label, raw, _ in html_pairs(html) if re.search(LABELS["coupon"][0], label.lower())), "")
    if "coupon" in terms.fields and re.search(r"per (period|event)|monthly coupon|quarterly coupon", raw_coupon, re.I):
        months = terms.get("frequency")
        if months:
            v = terms.fields["coupon"]
            terms.fields["coupon"] = Value(round(v.value * 12 / months, 6), v.source, CALCULATED,
                                           f"annualised from {v.value:.2%} per period x {12 // months}/yr")
    terms.underlyings = _underlying_rows(html)
    _cross_check(html_text(html), terms)
    _validate(terms)
    return terms


def _cross_check(text: str, terms: Terms) -> None:
    """Compare with the B01 term-sheet extractor; fill only what it read off the page."""
    try:
        ts = extract_fields(text)
    except Exception as exc:          # the text extractor is a second opinion, not a dependency
        terms.flags.append(f"text extractor failed: {exc}")
        return
    checks = {
        "isin": ts.identifier.value or None,
        "currency": ts.currency.value or None,
        "coupon": _pct(ts.coupon.value) if re.fullmatch(r"\s*\d+(?:\.\d+)?%\s*", ts.coupon.value or "") else None,
        "final_fixing": parse_date(ts.final_fixing_date.value) if ts.final_fixing_date.value else None,
        "initial_fixing": (date(2000 + int(ts.fixing_date.value[:2]), int(ts.fixing_date.value[2:4]), int(ts.fixing_date.value[4:6]))
                           if re.fullmatch(r"\d{6}", ts.fixing_date.value or "") else None),
    }
    for key, other in checks.items():
        if other is None:
            continue
        mine = terms.fields.get(key)
        if mine is None or mine.value is None:
            terms.fields[key] = Value(other, "text extractor (B01 rules)", OK)
        elif mine.status == OK and (abs(mine.value - other) > 1e-4 if isinstance(other, float) else mine.value != other):
            mine.status = INCONSISTENT
            mine.note = f"text extractor reads {other}"
    if ts.issuer.value and "issuer" not in terms.fields:
        terms.fields["issuer"] = Value(ts.issuer.value, "text extractor (issuer code)", OK)


def _validate(terms: Terms) -> None:
    f = terms.fields
    required = ["isin", "issuer", "currency", "coupon", "strike", "initial_fixing", "final_fixing"]
    for key in required:
        if key not in f or f[key].value is None:
            f[key] = Value(None, "", MISSING, "not found in the source")
    isin = f["isin"].value
    if isin and not isin_is_valid(isin):
        f["isin"].status, f["isin"].note = INCONSISTENT, "ISIN check digit does not match"
    s, b = f["strike"].value, f.get("barrier", Value()).value
    if s is not None and not 0.2 <= s <= 1.5:
        f["strike"].status, f["strike"].note = INCONSISTENT, f"implausible strike {s:.0%}"
    if b is not None and s is not None and b > s + 1e-9:
        f["barrier"].status, f["barrier"].note = INCONSISTENT, "barrier above the strike"
    c = f["coupon"].value
    if c is not None and not 0 <= c <= 0.4:
        f["coupon"].status, f["coupon"].note = INCONSISTENT, f"implausible coupon {c:.2%} p.a."
    i, fin = f["initial_fixing"].value, f["final_fixing"].value
    if i and fin and fin <= i:
        f["final_fixing"].status, f["final_fixing"].note = INCONSISTENT, "final fixing is not after the initial fixing"
    if not terms.underlyings:
        terms.flags.append("no underlyings found in the source")
    for u in terms.underlyings:
        if not u.symbol:
            terms.flags.append(f"no Yahoo symbol for {u.ticker or u.name}: performance not charted")
        if u.initial is None:
            terms.flags.append(f"initial fixing level of {u.name} not found")
    for key, v in f.items():
        if v.status in (MISSING, INCONSISTENT):
            terms.flags.append(f"{key}: {v.status}{' - ' + v.note if v.note else ''}")


def terms_from_case(data: dict) -> Terms:
    """Terms typed into the case file by the advisor (source 'case file')."""
    terms = Terms(source_name="case file")
    for key, raw in data.items():
        if key == "underlyings":
            for u in raw:
                terms.underlyings.append(Underlying(name=u.get("name", ""), ticker=u.get("ticker", ""),
                                                    symbol=u.get("symbol") or yahoo_symbol(u.get("ticker", "")),
                                                    initial=u.get("initial"), currency=u.get("currency", ""),
                                                    symbol_source="case file" if u.get("symbol") else "mapped from Bloomberg ticker"))
            continue
        value = _parse(key, str(raw)) if key in DATES else raw
        if key in PERCENT and isinstance(raw, str):
            value = _pct(raw)
        terms.fields[key] = Value(value, "case file", OK)
    _validate(terms)
    return terms


def merge(primary: Terms, override: dict) -> Terms:
    """Advisor overrides from the case file win, and are labelled as such."""
    extra = terms_from_case({k: v for k, v in override.items() if k != "underlyings"})
    for key, v in extra.fields.items():
        if v.value is not None and v.source == "case file":
            old = primary.fields.get(key)
            note = f"overrides {old.value!r} from {old.source}" if old and old.value is not None and old.value != v.value else ""
            primary.fields[key] = Value(v.value, "case file (advisor)", OK, note)
    if override.get("underlyings"):
        primary.underlyings = terms_from_case({"underlyings": override["underlyings"]}).underlyings
    primary.flags = []
    _validate(primary)
    return primary


# ------------------------------------------------------------------ market data
@dataclass
class Series:
    symbol: str
    dates: list[str]
    closes: list[float]
    source: str = "Yahoo Finance"
    adjusted: bool = False

    def since(self, start: date) -> "Series":
        iso = start.isoformat()
        pairs = [(d, c) for d, c in zip(self.dates, self.closes) if d >= iso]
        return Series(self.symbol, [d for d, _ in pairs], [c for _, c in pairs], self.source, self.adjusted)

    def at_or_before(self, day: date) -> float | None:
        iso = day.isoformat()
        best = None
        for d, c in zip(self.dates, self.closes):
            if d <= iso:
                best = c
            else:
                break
        return best


class CsvPrices:
    """Prices from CSV files, for when Yahoo cannot be reached (e.g. a sandbox without
    internet): columns `date,symbol,close` and optionally `adj_close`; one file or several.
    Company and fund facts are not available this way and show as n/a."""

    def __init__(self, paths: list):
        import csv
        self.rows: dict[str, list[tuple[str, float, float]]] = {}
        for path in paths:
            with open(path, newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    keys = {k.lower().strip(): v for k, v in r.items() if k}
                    try:
                        d = (parse_date(keys["date"]) or date.fromisoformat(keys["date"][:10])).isoformat()
                        close = float(str(keys["close"]).replace("'", "").replace(",", ""))
                    except (KeyError, ValueError, TypeError):
                        continue
                    adj = keys.get("adj_close") or keys.get("adj close")
                    adj = float(adj) if adj not in (None, "") else close
                    self.rows.setdefault(keys.get("symbol", "").strip(), []).append((d, close, adj))
        for v in self.rows.values():
            v.sort()

    def chart(self, symbol, rng="1y", interval="1d", max_age=None):
        return [{"date": d, "close": c} for d, c, _ in self.rows.get(symbol, [])]

    def history(self, symbol, rng="2y"):
        return [(d, a) for d, _, a in self.rows.get(symbol, [])]

    def info(self, symbol, max_age=None):
        return {}

    def fund(self, symbol, max_age=None):
        return {}


class FirstOf:
    """Ask several price clients in turn (e.g. Yahoo, then an uploaded CSV); first non-empty answer wins."""

    def __init__(self, *clients):
        self.clients = [c for c in clients if c is not None]

    def _ask(self, method, *args):
        for c in self.clients:
            try:
                out = getattr(c, method)(*args)
            except Exception:
                continue
            if out:
                return out
        return [] if method in ("chart", "history") else {}

    def chart(self, symbol, rng="1y", interval="1d", max_age=None):
        return self._ask("chart", symbol, rng, interval)

    def history(self, symbol, rng="2y"):
        return self._ask("history", symbol, rng)

    def info(self, symbol, max_age=None):
        return self._ask("info", symbol)

    def fund(self, symbol, max_age=None):
        return self._ask("fund", symbol)


class Market:
    """Yahoo data for the decks. `client` is a syz_advisory.marketdata.YahooClient (or a fake in tests).
    Series stop at `as_of`, so a deck dated in the past shows what was known on that date."""

    def __init__(self, client, as_of: date | None = None):
        self.client = client
        self.as_of = as_of

    def prices(self, symbol: str, start: date, *, adjusted: bool = False) -> Series:
        s = self._prices(symbol, start, adjusted)
        if self.as_of:
            end = self.as_of.isoformat()
            keep = [i for i, d in enumerate(s.dates) if d <= end]
            s = Series(s.symbol, [s.dates[i] for i in keep], [s.closes[i] for i in keep], s.source, s.adjusted)
        return s

    def _prices(self, symbol: str, start: date, adjusted: bool) -> Series:
        """Daily closes from `start`. Unadjusted by default: barrier and strike levels are
        set on the traded price, and dividend adjustment would shift every past level."""
        years = (date.today() - start).days / 365
        rng = "1y" if years < 0.9 else "2y" if years < 1.9 else "5y" if years < 4.9 else "10y"
        try:
            if adjusted:
                pairs = self.client.history(symbol, rng)
                s = Series(symbol, [d for d, _ in pairs], [c for _, c in pairs], adjusted=True)
            else:
                bars = self.client.chart(symbol, rng, "1d")
                s = Series(symbol, [b["date"][:10] for b in bars], [b["close"] for b in bars])
        except Exception:           # unknown symbol or no connection: the caller flags the gap
            return Series(symbol, [], [], adjusted=adjusted)
        return s.since(start - timedelta(days=7))

    def fx(self, currency: str, base: str, as_of: date) -> float | None:
        """Units of `base` per unit of `currency` (last Yahoo close on or before `as_of`)."""
        if not currency or currency == base:
            return 1.0
        s = self.prices(f"{currency}{base}=X", as_of - timedelta(days=14))
        return s.at_or_before(as_of)

    def info(self, symbol: str) -> dict:
        try:
            return self.client.info(symbol) or {}
        except Exception:
            return {}

    def search(self, query: str) -> str:
        """A Yahoo symbol for an ISIN or a name ('' when nothing listed is found)."""
        for c in getattr(self.client, "clients", [self.client]):
            try:
                hits = c.search(query) if hasattr(c, "search") else []
            except Exception:
                continue
            for h in hits or []:
                sym = h.get("symbol") if isinstance(h, dict) else None
                if sym and (h.get("quoteType") or h.get("type") or "").upper() in ("EQUITY", "ETF", "MUTUALFUND", "INDEX", ""):
                    return sym
        return ""

    def fund(self, symbol: str) -> dict:
        try:
            return self.client.fund(symbol) or {}
        except Exception:
            return {}
