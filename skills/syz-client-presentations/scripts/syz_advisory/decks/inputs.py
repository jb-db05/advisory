"""Any input file -> structured data for the decks: HTML, PDF, CSV / TSV / Excel.

    detect(path)           'html' | 'pdf' | 'table' | 'json' | 'text' | 'unknown', by content, not extension alone
    read_pdf_terms(path)   product terms from a term sheet / factsheet / product report PDF
    read_table(path)       a CSV / TSV / Excel / HTML table, headers found and mapped to known fields,
                           classified as holdings, products or prices
    ingest(paths)          all of the above at once -> a draft case file and a report of what was found

Every value keeps its source; anything not found is missing, never guessed.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from syz_advisory.decks.sources import (INDEX, MISSING, OK, Terms, Underlying, Value, _Node, _Tree, _validate,
                                        html_text, read_html_terms, yahoo_symbol)
from syz_advisory.termsheets.extract import extract_fields, parse_date, pdf_text

ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")


# ------------------------------------------------------------------ format detection
def detect(path: Path) -> str:
    head = Path(path).read_bytes()[:4096]
    suffix = Path(path).suffix.lower()
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK") and suffix in (".xlsx", ".xlsm"):
        return "table"
    text = head.decode("utf-8", "ignore").lstrip("﻿ \r\n\t").lower()
    if text.startswith(("<!doctype html", "<html", "<?xml")) or "<table" in text or "<body" in text \
            or suffix in (".html", ".htm", ".mhtml") or text.startswith(("mime-version", "from:")):
        return "html"
    if suffix == ".json" or text.startswith(("{", "[")):
        return "json"
    if suffix in (".csv", ".tsv", ".txt") or _sniff(text):
        return "table" if _sniff(text) else "text"
    return "unknown"


def _sniff(text: str) -> str | None:
    lines = [l for l in text.splitlines()[:20] if l.strip()]
    for delim in ("\t", ";", ",", "|"):
        counts = [l.count(delim) for l in lines]
        if len(lines) >= 2 and sum(1 for c in counts if c >= 1) >= max(2, len(lines) // 2):
            return delim
    return None


# ------------------------------------------------------------------ PDF terms
PRODUCT_NAMES = {"AC": "Autocallable", "BRC": "Barrier Reverse Convertible", "RC": "Reverse Convertible",
                 "DC": "Discount Certificate", "CPN": "Capital Protected Note", "CLN": "Credit Linked Note",
                 "BTB": "Beat the Benchmark", "TRK": "Tracker Certificate", "BC": "Bonus Certificate", "SN": "Shark Note"}
FREQ_WORDS = {"monthly": 1, "bi-monthly": 2, "quarterly": 3, "every 4 months": 4, "semi-annual": 6, "semi-annually": 6,
              "annual": 12, "annually": 12, "in fine": 0}


def _num(text: str) -> float:
    return float(text.replace("'", "").replace("’", "").replace(",", "."))


def _pct_after(flat: str, label: str, lo: float = 1, hi: float = 200) -> tuple[float, str] | None:
    """The first percentage within a short window after `label` (regex), as a fraction."""
    for m in re.finditer(label, flat, re.I):
        w = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", flat[m.end(): m.end() + 90])
        if w:
            v = _num(w.group(1))
            if lo <= v <= hi:
                return round(v / 100, 6), flat[max(0, m.start() - 10): m.end() + w.end() + 10].strip()
    return None


def read_pdf_terms(path: Path) -> Terms:
    data = Path(path).read_bytes()
    try:
        text = pdf_text(data)
    except Exception as exc:
        t = Terms(source_name=Path(path).name)
        t.flags.append(f"PDF could not be read: {exc}")
        _validate(t)
        return t
    if len(text.strip()) < 50:
        t = Terms(source_name=Path(path).name)
        t.flags.append("the PDF has no text layer (a scan?): OCR it or type the terms into the case file")
        _validate(t)
        return t
    return read_text_terms(text, Path(path).name)


def read_text_terms(text: str, source_name: str = "text") -> Terms:
    """Terms from the text of a term sheet / factsheet / product report (PDF or pasted text)."""
    flat = re.sub(r"\s+", " ", text)
    ts = extract_fields(text)
    terms = Terms(source_name=source_name)
    f = terms.fields

    def put(key, value, src, status=OK, note=""):
        if value not in (None, "") and key not in f:
            f[key] = Value(value, f"PDF: {src[:80]}" if src else "PDF", status, note)

    put("isin", ts.identifier.value or None, ts.identifier.source, note=ts.identifier.warning)
    put("currency", ts.currency.value or None, ts.currency.source)
    put("issuer", ts.issuer.value or None, ts.issuer.source, note="issuer code (B01 rules)")
    if ts.product_type.value:
        put("product_type", PRODUCT_NAMES.get(ts.product_type.value, ts.product_type.value), ts.product_type.source)
    if re.fullmatch(r"\s*\d+(?:\.\d+)?%\s*", ts.coupon.value or ""):
        put("coupon", round(float(ts.coupon.value.strip(" %")) / 100, 6), ts.coupon.source,
            status="calculated" if "annualised" in (ts.coupon.warning or "").lower() or "calculated" in (ts.coupon.warning or "").lower() else OK,
            note=ts.coupon.warning)
    if re.fullmatch(r"\d{6}", ts.fixing_date.value or ""):
        v = ts.fixing_date.value
        put("initial_fixing", date(2000 + int(v[:2]), int(v[2:4]), int(v[4:])), ts.fixing_date.source)
    if ts.final_fixing_date.value:
        put("final_fixing", parse_date(ts.final_fixing_date.value), ts.final_fixing_date.source)
    if ts.frequency.value:
        put("frequency", FREQ_WORDS.get(ts.frequency.value.lower()), ts.frequency.source)
    if ts.strike.value:
        put("strike", round(float(ts.strike.value.strip(" %")) / 100, 6) if re.fullmatch(r"\s*\d+(?:\.\d+)?%\s*", ts.strike.value) else None,
            ts.strike.source)
    if ts.settlement.value:
        put("settlement", ts.settlement.value, ts.settlement.source)

    # what the naming rules do not need, read here
    for key, label in (("barrier", r"(?:knock[- ]?in|kick[- ]?in|barrier)(?:\s+(?:level|event|price))?"),
                       ("strike", r"strike(?:\s+(?:level|price))?"),
                       ("coupon_trigger", r"coupon\s+(?:barrier|trigger)(?:\s+level)?"),
                       ("participation", r"participation(?:\s+rate)?"),
                       ("cap", r"\bcap(?:\s+level)?\b"),
                       ("bonus_level", r"bonus\s+level"),
                       ("protection", r"capital\s+protection(?:\s+level)?")):
        hit = _pct_after(flat, label, 10, 400 if key == "participation" else 200)
        if hit:
            put(key, hit[0], hit[1])
    if "barrier" in f:
        european = re.search(r"European|at\s+(?:the\s+)?(?:final\s+fixing|maturity)\s+only|final\s+fixing\s+date\s+only", flat, re.I)
        put("barrier_type", "european" if european else "american", "barrier observation wording",
            note="" if european or re.search(r"continuous|daily|american|any\s+(?:exchange\s+)?(?:business|trading)\s+day", flat, re.I)
            else "no observation wording found: American assumed, check")
    if re.search(r"\bmemory\b", flat, re.I):
        put("memory", True, "memory wording")
    m = re.search(r"(?:Specified\s+)?Denomination[^0-9A-Z]{0,30}([A-Z]{3})?\s*([\d'’,.]+)", flat)
    if m:
        try:
            put("denomination", float(re.sub(r"[^\d.]", "", m.group(2).replace(",", ""))), m.group(0))
        except ValueError:
            pass
    _autocall(flat, terms)
    _pdf_underlyings(text, flat, ts, terms)
    _validate(terms)
    return terms


def _autocall(flat: str, terms: Terms) -> None:
    """Trigger level and observation schedule, with the reader G01 / the proposition tool use."""
    try:
        from syz_advisory.proposition.termsheet_fill import autocall_trigger, observations
    except Exception:              # the skill bundle may not carry it: fall back to the plain level
        observations, autocall_trigger = None, None
    schedule = []
    if observations:
        try:
            schedule = [(o.observation, o.level / 100 if o.level > 3 else o.level) for o in observations(flat)]
        except Exception:
            schedule = []
    if schedule:
        terms.fields["autocall_trigger"] = Value(schedule[0][1], "PDF: early redemption schedule", OK,
                                                 f"{len(schedule)} observations")
        terms.fields["autocall_schedule"] = Value(schedule, "PDF: early redemption schedule", OK)
        fixing = terms.get("initial_fixing")
        if fixing:
            first = schedule[0][0]
            terms.fields["first_call_months"] = Value(max(1, (first.year - fixing.year) * 12 + first.month - fixing.month),
                                                      "calculated from the schedule", "calculated")
        return
    hit = _pct_after(flat, r"(?:autocall(?:\s+trigger)?|early\s+redemption\s+(?:level|trigger|barrier)|trigger\s+level)", 50, 150)
    if hit:
        terms.fields["autocall_trigger"] = Value(hit[0], f"PDF: {hit[1][:80]}", OK)
        return
    # SG style: "Automatic Early Redemption Event ... if on a Valuation Date(i) (i from 4 to 11),
    # Performance(i) is higher than or equal to 0%", Performance = S(i)/S(0) - 100%.
    m = re.search(r"(?:Automatic\s+)?Early\s+Redemption\s+Event.{0,250}?\(i\s+from\s+(\d+)\s+to\s+\d+\).{0,120}?"
                  r"Performance\s*\(i\)\s+is\s+(?:higher|greater)\s+than\s+or\s+equal\s+to\s+(-?\d+(?:[.,]\d+)?)\s*%", flat, re.I)
    if m:
        level = round(1 + _num(m.group(2)) / 100, 6)
        terms.fields["autocall_trigger"] = Value(level, f"PDF: {m.group(0)[:80]}...", OK,
                                                 f"Performance(i) >= {m.group(2)}%, i.e. {level:.0%} of the initial level")
        freq = terms.get("frequency")
        if freq:
            terms.fields["first_call_months"] = Value(int(m.group(1)) * freq, "calculated: first observation index x frequency",
                                                      "calculated")


def _pdf_underlyings(text: str, flat: str, ts, terms: Terms) -> None:
    """Underlyings with their Bloomberg ticker (-> Yahoo symbol) and initial level.

    Term-sheet tables often lose their spacing in the PDF text ('MPUNNYSE', 'LYCATAustralian'),
    so the ticker is found as the code followed by a known exchange code, glued or not. The
    initial level is the price on the underlying's row whose ratio to another price on that row
    equals a level stated in % (strike, barrier, trigger): that consistency is the check."""
    from syz_advisory.decks.sources import EXCHANGE
    codes = [c for c in (ts.underlyings.value or "").split("-") if c]
    names = [n.strip() for n in (ts.underlying_names.value or "").split("\n") if n.strip()]
    exch_alt = "|".join(sorted(EXCHANGE, key=len, reverse=True))
    ratios = [r for r in (terms.get("strike"), terms.get("barrier"), terms.get("autocall_trigger"),
                          terms.get("coupon_trigger")) if r and 0.2 < r < 1.0]
    lines = text.splitlines()
    for i, code in enumerate(codes):
        name = names[i] if i < len(names) else code
        bbg = ""
        if code in INDEX:
            bbg = f"{code} Index"
        else:
            m = re.search(rf"(?<![A-Z0-9]){re.escape(code)}\s?({exch_alt})(?:\s?Equity)?(?=[\s\dA-Z<]|$)", flat)
            if m:
                bbg = f"{code} {m.group(1)} Equity"
        symbol = yahoo_symbol(bbg) if bbg else ""
        u = Underlying(name=name, ticker=bbg or code, symbol=symbol,
                       symbol_source="mapped from Bloomberg ticker" if symbol else "")
        # the row: the line holding the ticker (or the name) and the next two lines
        row = ""
        tests = []
        if bbg and " " in bbg:
            tests.append(lambda l: re.search(rf"(?<![A-Z0-9]){re.escape(code)}\s?{re.escape(bbg.split()[1])}", l))
        if len(name) > 3:       # fallback only: the name also appears in the product's description
            key = name[:12].replace(" ", "").upper()
            tests.append(lambda l: key in l.replace(" ", "").upper() and re.search(r"\d\.\d+\s?[A-Z]{3}", l))
        for test in tests:
            j = next((j for j, line in enumerate(lines) if test(line)), None)
            if j is not None:
                row = " ".join(lines[j:j + 5])
                break
        # a price starts after a space or a letter (the previous currency) and ends at its currency:
        # 'LTD 15.3000AUD9.1800AUD15.3000AUD' -> 15.30, 9.18, 15.30
        amounts = [(_amount(a), c) for a, c in
                   re.findall(r"(?:(?<=[A-Za-z ])|^)(\d[\d'’,]*\.\d+)\s?([A-Z]{3})(?![a-z])", row)]
        amounts = [(a, c) for a, c in amounts if a]
        found = None
        for a, c in amounts:
            for b, _ in amounts:
                if b < a and any(abs(b / a - r) < 0.004 for r in ratios):
                    found = (a, c)
                    break
            if found:
                break
        if found:
            u.initial, u.currency = found
        terms.underlyings.append(u)


def _amount(text: str) -> float | None:
    s = text.replace("'", "").replace("’", "")
    if "," in s and "." in s:
        s = s.replace(",", "")
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


# ------------------------------------------------------------------ tables (CSV / TSV / Excel / HTML)
HEADERS: dict[str, list[str]] = {
    "date": ["date", "datum", "as of", "trade date", "valuation date"],
    "symbol": ["symbol", "ticker", "yahoo", "yahoo symbol", "bloomberg", "bbg", "bloomberg ticker", "code"],
    "isin": ["isin", "isin code"],
    "valor": ["valor", "valoren", "security number"],
    "name": ["name", "description", "security", "instrument", "security name", "libellé", "libelle", "désignation",
             "designation", "titre", "bezeichnung", "product", "holding"],
    "asset_class": ["asset class", "class", "classe d'actif", "classe d’actif", "anlageklasse", "category", "type",
                    "asset type", "instrument type"],
    "currency": ["currency", "ccy", "devise", "währung", "waehrung", "curr"],
    "quantity": ["quantity", "qty", "nominal", "units", "quantité", "quantite", "anzahl", "shares", "position"],
    "price": ["price", "last", "last price", "market price", "cours", "kurs", "close price", "clean price"],
    "close": ["close", "closing price", "adj close", "px_last"],
    "adj_close": ["adj close", "adj_close", "adjusted close"],
    "value": ["market value", "value", "valuation", "montant", "valeur", "marktwert", "mv", "position value",
              "market value chf", "value chf", "amount", "evaluation", "évaluation"],
    "weight": ["weight", "weight (%)", "%", "poids", "allocation", "gewicht", "% of portfolio", "% portfolio", "weight %"],
    "sector": ["sector", "secteur", "sektor", "industry", "gics sector"],
    "region": ["region", "région", "geography", "zone"],
    "country": ["country", "pays", "land"],
    "issuer": ["issuer", "émetteur", "emetteur", "emittent"],
    "coupon": ["coupon", "coupon p.a.", "coupon rate", "coupon (%)", "rate"],
    "barrier": ["barrier", "barrier level", "knock-in", "ki"],
    "strike": ["strike", "strike level"],
    "autocall_trigger": ["autocall", "autocall trigger", "autocall level", "trigger"],
    "maturity": ["maturity", "maturity date", "échéance", "echeance", "fälligkeit", "redemption date", "final fixing"],
    "initial_fixing": ["initial fixing", "fixing date", "strike date", "issue date"],
    "underlyings": ["underlying", "underlyings", "sous-jacent", "sous-jacents", "basiswert"],
    "ytm": ["ytm", "yield", "yield to maturity", "rendement"],
    "duration": ["duration", "modified duration", "mod. duration"],
    "rating": ["rating", "notation", "s&p", "moody's"],
    "product_type": ["product type", "structure", "payoff"],
}
NUMERIC = {"quantity", "price", "close", "adj_close", "value", "weight", "coupon", "barrier", "strike",
           "autocall_trigger", "ytm", "duration"}
PERCENTISH = {"weight", "coupon", "barrier", "strike", "autocall_trigger", "ytm"}
ASSET_CLASSES = [(r"equit|action|aktie|stock|share", "Equities"), (r"bond|obligat|anleihe|fixed income|credit", "Bonds"),
                 (r"cash|liquid|money market|monétaire|deposit|current account|compte", "Cash"),
                 (r"structured|structuré|structure", "Structured products"),
                 (r"hedge|alternative|commodit|gold|or\b|private|real estate|immobili", "Alternatives"),
                 (r"fund|fonds|etf", "Funds")]


@dataclass
class Table:
    kind: str                                # holdings | products | prices | unknown
    records: list[dict] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)    # field -> original header
    unmapped: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    source: str = ""


def decimal_mark(rows: list[list[str]]) -> str:
    """',' when the file writes decimals with a comma ('80,50', '322 000,00'), else '.'.
    Decides ambiguous cells like '2,125' (2.125 in Geneva, 2125 in London) for the whole file."""
    comma = dot = 0
    for r in rows[:200]:
        for c in r:
            s = str(c)
            comma += len(re.findall(r"\d,\d{1,2}(?!\d)", s)) + len(re.findall(r"\d[ .']\d{3},\d", s))
            dot += len(re.findall(r"\d\.\d{1,2}(?!\d)", s)) + len(re.findall(r"\d[ ,']\d{3}\.\d", s))
    return "," if comma > dot else "."


def parse_number(text, decimal: str = ".") -> float | None:
    """'1'234.56', '1 234,56', '12.5%', '(1,234)', 'CHF 1,000' -> float (percent kept as the number).
    `decimal` is the file's decimal mark (see decimal_mark), used when a cell alone is ambiguous."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip().replace(" ", " ").replace("’", "'")
    if not s or s in ("-", "n/a", "N/A", "#N/A"):
        return None
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = re.sub(r"[^\d,.' ]", "", s).strip().replace("'", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        if decimal == "," or re.fullmatch(r"\d+,\d{1,2}", s):
            s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
        else:
            s = s.replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _raw_rows(path: Path) -> list[list[str]]:
    kind = detect(path)
    if kind == "html":
        return html_tables(Path(path).read_text(encoding="utf-8", errors="replace"))
    if Path(path).suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        rows = []
        for ws in wb.worksheets:
            rows = [["" if c is None else (c.isoformat() if isinstance(c, date) else str(c)) for c in r] for r in ws.iter_rows(values_only=True)]
            if any(any(c for c in r) for r in rows):
                break
        return rows
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    delim = _sniff(text) or ","
    return [r for r in csv.reader(io.StringIO(text), delimiter=delim)]


def html_tables(html: str) -> list[list[str]]:
    """Rows of every table on an HTML page (header rows included), tables separated by an empty row."""
    t = _Tree()
    t.feed(html)
    out: list[list[str]] = []
    for table in (n for n in t.root.iter() if n.tag == "table"):
        for tr in (n for n in table.iter() if n.tag == "tr"):
            cells = [c.all_text() for c in tr.children if isinstance(c, _Node) and c.tag in ("td", "th")]
            if cells:
                out.append(cells)
        out.append([])
    return out


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", str(h).strip().lower().replace("_", " "))


def _map_header(cells: list[str]) -> dict[str, int]:
    mapping = {}
    for i, c in enumerate(cells):
        h = _norm(c)
        if not h:
            continue
        best = None
        for fld, names in HEADERS.items():
            if fld in mapping:
                continue
            if h in names:
                best = fld
                break
            if best is None and any(h.startswith(n + " ") or h.startswith(n + "(") for n in names if len(n) > 2):
                best = fld
        if best:
            mapping[best] = i
    return mapping


def read_table(path: Path) -> Table:
    rows = _raw_rows(path)
    best_i, best_map = None, {}
    for i, r in enumerate(rows[:40]):
        m = _map_header(r)
        if len(m) > len(best_map):
            best_i, best_map = i, m
    t = Table("unknown", source=Path(path).name)
    wide = (best_i is not None and list(best_map) == ["date"]
            and sum(1 for h in rows[best_i] if re.fullmatch(r"[\^A-Za-z0-9.=\-]{1,15}", str(h).strip())) >= 2)
    if best_i is None or (len(best_map) < 2 and not wide):
        t.flags.append("no header row with known column names found")
        return t
    header = rows[best_i]
    dec = decimal_mark(rows[best_i + 1:])
    t.mapping = {f: header[i] for f, i in best_map.items()}
    t.unmapped = [h for j, h in enumerate(header) if h and j not in best_map.values()]
    # wide price table: a date column and one column per symbol
    if "date" in best_map and not ({"close", "value", "weight", "quantity", "isin"} & best_map.keys()):
        cols = [j for j in range(len(header)) if j != best_map["date"] and header[j]]
        t.kind = "prices"
        for r in rows[best_i + 1:]:
            if len(r) <= best_map["date"]:
                continue
            d = _date(r[best_map["date"]])
            for j in cols:
                v = parse_number(r[j], dec) if j < len(r) else None
                if d and v is not None:
                    t.records.append({"date": d.isoformat(), "symbol": header[j].strip(), "close": v, "adj_close": v})
        t.mapping = {"date": header[best_map["date"]], "symbols": ", ".join(header[j] for j in cols)}
        return t
    for r in rows[best_i + 1:]:
        if not any(str(c).strip() for c in r):
            continue
        rec = {}
        for fld, j in best_map.items():
            raw = r[j] if j < len(r) else ""
            if fld in NUMERIC:
                rec[fld] = parse_number(raw, dec)
                if "%" in str(raw):
                    rec.setdefault("_pct", set()).add(fld)
            elif fld in ("date", "maturity", "initial_fixing"):
                d = _date(raw)
                rec[fld] = d.isoformat() if d else None
            else:
                rec[fld] = str(raw).strip() or None
        if fld_count(rec) >= 2:
            t.records.append(rec)
    # A column is in percent when its header or any cell says so, or when its values could not
    # be fractions (a weight column summing past 150 %, a coupon of 3.25). Decided per column,
    # so a 0.5 % coupon written '0.5' next to '3.25' is read as 0.5 %, not 50 %.
    for fld in PERCENTISH & best_map.keys():
        vals = [r[fld] for r in t.records if r.get(fld) is not None]
        in_pct = ("%" in header[best_map[fld]] or any(fld in r.get("_pct", ()) for r in t.records)
                  or (fld == "weight" and sum(vals) > 1.5) or (fld != "weight" and vals and max(vals) > 1.5))
        if in_pct:
            for r in t.records:
                if r.get(fld) is not None:
                    r[fld] = r[fld] / 100
    for r in t.records:
        r.pop("_pct", None)
    keys = best_map.keys()
    if "date" in keys and ({"close", "price"} & keys):
        t.kind = "prices"
        t.records = [{"date": r["date"], "symbol": r.get("symbol") or Path(path).stem, "close": r.get("close") or r.get("price"),
                      "adj_close": r.get("adj_close") or r.get("close") or r.get("price")} for r in t.records if r.get("date")]
    elif ({"barrier", "strike", "autocall_trigger"} & keys) and ({"isin", "name"} & keys):
        t.kind = "products"                      # structured-product terms (a coupon alone is also a bond's)
    elif ({"value", "weight", "quantity"} & keys) and ({"name", "symbol", "isin"} & keys):
        t.kind = "holdings"
        _clean_holdings(t)
    elif "coupon" in keys and ({"isin", "name"} & keys):
        t.kind = "products"
    else:
        t.flags.append("columns found but not enough to tell holdings, products or prices apart")
    return t


def fld_count(rec: dict) -> int:
    return sum(1 for v in rec.values() if v not in (None, ""))


def _date(raw) -> date | None:
    s = str(raw).strip()[:10] if raw else ""
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return parse_date(s)


def _clean_holdings(t: Table) -> None:
    keep = []
    for r in t.records:
        label = (r.get("name") or "").lower()
        # section headers and totals ("Cash", "Total equities") carry no position
        if r.get("value") is None and r.get("weight") is None and r.get("quantity") is None:
            continue
        if re.match(r"(sub)?total\b|^sum\b|^grand total", label):
            continue
        ac = (r.get("asset_class") or "").lower()
        canon = next((name for pattern, name in ASSET_CLASSES if re.search(pattern, ac)), None) if ac else None
        if canon:
            r["asset_class"] = canon                     # 'Actions suisses' -> 'Equities'
        elif not ac:
            guess = next((name for pattern, name in ASSET_CLASSES if re.search(pattern, label)), None)
            if guess:
                r["asset_class"] = guess
                t.flags.append(f"{r.get('name')}: asset class '{guess}' inferred from the name -- check")
            else:
                t.flags.append(f"{r.get('name') or r.get('isin')}: asset class not given")
        if r.get("symbol") and re.fullmatch(r"[A-Z0-9.]+ [A-Z]{2}( Equity)?", r["symbol"]):
            r["symbol"] = yahoo_symbol(r["symbol"] + ("" if r["symbol"].endswith("Equity") else " Equity")) or r["symbol"]
        keep.append(r)
    t.records = keep
    if any(r.get("weight") is None for r in keep) and not all(r.get("value") is not None for r in keep):
        t.flags.append("some positions have neither a value nor a weight")


# ------------------------------------------------------------------ ingest
@dataclass
class Ingested:
    case: dict
    report: list[str]
    flags: list[tuple[str, str]]


def ingest(paths: list[Path], *, client: str = "C-0000", as_of: str | None = None, currency: str | None = None) -> Ingested:
    """Read every file, whatever its format, into a draft case file."""
    products, holdings, prices, report, flags = [], [], [], [], []
    for p in map(Path, paths):
        kind = detect(p)
        if kind == "pdf":
            terms = read_pdf_terms(p)
            if terms.get("isin") or terms.get("coupon") is not None or terms.underlyings:
                products.append({"source": {"pdf": str(p)}, "nominal": None, "currency": terms.get("currency")})
                report.append(f"{p.name}: PDF term sheet -- {_summary(terms)}")
            else:
                report.append(f"{p.name}: PDF without product terms -- " + _pdf_positions(p, holdings, flags))
            flags += [(p.name, f) for f in terms.flags]
        elif kind == "html":
            html = p.read_text(encoding="utf-8", errors="replace")
            terms = read_html_terms(html, p.name)
            table = read_table(p)
            if terms.get("isin") or terms.get("coupon") is not None:
                products.append({"source": {"html": str(p)}, "nominal": None, "currency": terms.get("currency")})
                report.append(f"{p.name}: HTML product page -- {_summary(terms)}")
                flags += [(p.name, f) for f in terms.flags]
            elif table.kind in ("holdings", "prices", "products"):
                _take(table, products, holdings, prices, report, flags, p)
            else:
                report.append(f"{p.name}: HTML page with no product terms or known table")
        elif kind in ("table", "text"):
            table = read_table(p)
            if table.kind == "unknown" and kind == "text":
                terms = read_text_terms(p.read_text(encoding="utf-8", errors="replace"), p.name)
                if terms.get("isin") or terms.get("coupon") is not None:
                    products.append({"source": {"text": str(p)}, "nominal": None, "currency": terms.get("currency")})
                    report.append(f"{p.name}: text term sheet -- {_summary(terms)}")
                    continue
            _take(table, products, holdings, prices, report, flags, p)
        else:
            report.append(f"{p.name}: format not recognised ({kind})")
    # nominals from the positions list, matched by ISIN
    by_isin = {h["isin"]: h for h in holdings if h.get("isin")}
    for prod in products:
        isin = _terms_isin(prod)
        h = by_isin.get(isin)
        if h:
            # the position stays in the holdings (allocation) and gives the product its nominal
            prod["nominal"] = h.get("quantity") or h.get("value")
            prod["currency"] = h.get("currency") or prod.get("currency")
            h["asset_class"] = h.get("asset_class") or "Structured products"
    for prod in products:
        if prod.get("nominal") is None:
            flags.append((Path(next(iter(prod.get("source", {"x": "?"}).values()))).name if prod.get("source") else "product",
                          "nominal not found in the inputs: add it to the case file"))
    ccys = [h.get("currency") for h in holdings if h.get("currency")] + [p.get("currency") for p in products if p.get("currency")]
    case = {"type": "client_review" if holdings else "sp_review", "client": client,
            "as_of": as_of or date.today().isoformat(),
            "currency": currency or (max(set(ccys), key=ccys.count) if ccys else "CHF")}
    if holdings:
        case["holdings"] = [{k: v for k, v in h.items() if v not in (None, "")} for h in holdings]
    if products:
        case["products"] = products
    if prices:
        case["prices"] = prices
    return Ingested(case, report, flags)


def _take(table: Table, products, holdings, prices, report, flags, p: Path) -> None:
    flags += [(p.name, f) for f in table.flags]
    if table.kind == "holdings":
        holdings += table.records
        report.append(f"{p.name}: positions table, {len(table.records)} rows; columns {table.mapping}")
    elif table.kind == "products":
        for r in table.records:
            terms = {k: r[k] for k in ("isin", "issuer", "currency", "coupon", "barrier", "strike", "autocall_trigger",
                                       "product_type") if r.get(k) not in (None, "")}
            if r.get("maturity"):
                terms["final_fixing"] = r["maturity"]
            if r.get("initial_fixing"):
                terms["initial_fixing"] = r["initial_fixing"]
            if r.get("underlyings"):
                terms["underlyings"] = [{"name": u.strip(), "ticker": u.strip()} for u in re.split(r"[/,;|]", r["underlyings"]) if u.strip()]
            products.append({"label": r.get("name") or r.get("isin"), "nominal": r.get("quantity") or r.get("value"),
                             "currency": r.get("currency"), "terms": terms})
        report.append(f"{p.name}: product list, {len(table.records)} rows; columns {table.mapping}")
    elif table.kind == "prices":
        prices.append({"file": str(p), "rows": len(table.records)})
        report.append(f"{p.name}: price history, {len(table.records)} closes for "
                      f"{len({r['symbol'] for r in table.records})} symbols")
    else:
        report.append(f"{p.name}: table not recognised -- headers mapped: {table.mapping or 'none'}")


def _pdf_positions(p: Path, holdings: list, flags: list) -> str:
    """Positions in a portfolio report PDF: lines carrying an ISIN and amounts."""
    try:
        text = pdf_text(p.read_bytes())
    except Exception:
        return "unreadable"
    found = 0
    for line in text.splitlines():
        m = ISIN_RE.search(line)
        if not m:
            continue
        nums = [parse_number(x) for x in re.findall(r"-?\(?\d[\d'’,. ]*\d\)?%?", line[m.end():]) if "%" not in x]
        nums = [n for n in nums if n is not None]
        if not nums:
            continue
        name = line[: m.start()].strip(" -|") or m.group(0)
        holdings.append({"name": name[:60], "isin": m.group(0), "value": max(nums, key=abs)})
        found += 1
    if found:
        flags.append((p.name, f"{found} positions read from PDF text lines (largest amount on each line taken as the value) -- verify"))
    return f"{found} position lines with ISINs" if found else "no positions found"


def _summary(terms: Terms) -> str:
    keys = ["isin", "issuer", "currency", "product_type", "coupon", "strike", "barrier", "autocall_trigger", "initial_fixing", "final_fixing"]
    have = [k for k in keys if terms.get(k) is not None]
    miss = [k for k in keys if terms.get(k) is None]
    return (f"found {', '.join(have) or 'nothing'}; {len(terms.underlyings)} underlyings"
            + (f"; missing {', '.join(miss)}" if miss else ""))


def _terms_isin(prod: dict) -> str | None:
    if prod.get("terms", {}).get("isin"):
        return prod["terms"]["isin"]
    src = prod.get("source") or {}
    path = Path(next(iter(src.values()))) if src else None
    if not path or not path.exists():
        return None
    t = load_terms(src)
    return t.get("isin")


def load_terms(source: dict) -> Terms:
    """Terms from a case-file `source` entry: {"html": p} | {"pdf": p} | {"text": p} | {"file": p} (auto)."""
    kind, path = next(iter(source.items()))
    path = Path(path)
    if kind == "file":
        kind = {"pdf": "pdf", "html": "html"}.get(detect(path), "text")
    if kind == "pdf":
        return read_pdf_terms(path)
    if kind == "html":
        return read_html_terms(path.read_text(encoding="utf-8", errors="replace"), path.name)
    return read_text_terms(path.read_text(encoding="utf-8", errors="replace"), path.name)
