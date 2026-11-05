"""Step 1 and 2: recognise each input document and extract the product terms.

Three kinds of input are understood:
  * a proposal sheet (Excel .xlsx/.xlsm or .csv): one row per product, the desk's G01 format or any
    sheet whose headers say what the columns are (Underlying 1..n, Coupon, Barrier, Strike, ...);
  * a term sheet or final terms (PDF);
  * a pricer, factsheet or product page (HTML, saved from LYNQS, Visibility, an issuer site...).

PDF and HTML are both turned into plain text and read by the same term-sheet parser, so a field is
found the same way whatever the source.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path

from .model import Product, Underlying
from .names import from_bloomberg, issuer_short

# ---------------------------------------------------------------------------------------------
# recognition

def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".zip":
        return "zip"
    if ext in (".xlsx", ".xlsm", ".xls"):
        return "sheet"
    if ext == ".csv":
        return "sheet"
    if ext == ".pdf":
        return "termsheet-pdf"
    if ext in (".html", ".htm", ".mhtml"):
        return "pricer-html"
    if ext in (".txt", ".md"):
        return "text"
    raise ValueError(f"{path.name}: unknown format (use Excel, CSV, PDF or HTML)")


def unzip(path: Path, log=print) -> list[Path]:
    """Extract a ZIP of term sheets into its own folder and return the documents it holds."""
    import tempfile
    import zipfile
    out = Path(tempfile.mkdtemp(prefix="syz_ts_"))
    found = []
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            name = Path(info.filename)
            if info.is_dir() or name.name.startswith((".", "~$")) or "__MACOSX" in name.parts:
                continue
            if name.suffix.lower() not in (".pdf", ".html", ".htm", ".xlsx", ".xlsm", ".csv"):
                continue
            target = out / name.name                      # flatten: no paths from inside the archive
            target.write_bytes(z.read(info))
            found.append(target)
    log(f"  {path.name}: ZIP, {len(found)} document(s) inside")
    return sorted(found)


def read(paths: list[Path], log=print) -> list[Product]:
    products: list[Product] = []
    expanded: list[Path] = []
    for path in paths:
        expanded += unzip(path, log) if kind_of(path) == "zip" else [path]
    for path in expanded:
        kind = kind_of(path)
        if kind == "sheet":
            found = read_sheet(path)
        else:
            text = pdf_text(path) if kind == "termsheet-pdf" else html_text(path) if kind == "pricer-html" \
                else path.read_text(encoding="utf-8", errors="ignore")
            found = [parse_terms(text, path.name)]
        log(f"  {path.name}: {kind}, {len(found)} product(s)")
        for p in found:
            p.number = len(products) + 1 if kind != "sheet" else p.number
            products.append(p)
    # renumber when several documents are mixed and none is a sheet (a sheet keeps its numbers)
    has_sheet = any(p.source_file and p.source_file.lower().endswith((".xlsx", ".xlsm", ".csv")) for p in products)
    if len({p.source_file for p in products}) > 1 and not has_sheet:
        for i, p in enumerate(products, 1):
            p.number = i
    return products


# ---------------------------------------------------------------------------------------------
# sheets

SYN = {  # header synonyms -> field
    "basket": "number", "product": "number", "#": "number", "no": "number", "nr": "number",
    "coupon": "coupon", "coupon p.a.": "coupon", "coupon rate": "coupon",
    "downside protection": "protection", "protection": "protection",
    "barrier": "barrier", "barrier level": "barrier", "strike": "strike", "strike level": "strike",
    "maturity": "tenor", "tenor": "tenor", "duration": "tenor",
    "weight": "weight", "weighting": "weight", "fees": "fees", "fee": "fees",
    "stepdown": "stepdown", "step-down": "stepdown", "autocall": "stepdown",
    "issuer": "issuer", "currency": "currency", "ccy": "currency", "isin": "isin",
    "theme": "theme", "initial fixing": "initial_fixing", "initial fixing date": "initial_fixing",
    "final fixing": "final_fixing", "final fixing date": "final_fixing", "size": "size",
}


def _rows(path: Path) -> list[list]:
    if path.suffix.lower() == ".csv":
        raw = path.read_text(encoding="utf-8-sig", errors="ignore")
        dialect = csv.Sniffer().sniff(raw[:4000], delimiters=",;\t") if raw.strip() else csv.excel
        return [list(r) for r in csv.reader(raw.splitlines(), dialect)]
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _pct(v) -> float | None:
    """'7.00%', 0.07, '7', 7 -> 0.07"""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v) / 100 if v > 1.5 else float(v)
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v))
    if not m:
        return None
    x = float(m.group().replace(",", "."))
    return x / 100 if ("%" in str(v) or x > 1.5) else x


def _months(v) -> int | None:
    if v is None or v == "":
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(y|year|yr|an|jahr)?", str(v), re.I)
    if not m:
        return None
    x = float(m.group(1).replace(",", "."))
    return int(round(x * 12)) if m.group(2) else int(round(x))


def parse_protection(text: str | None) -> tuple[str | None, float | None, float | None]:
    """'European Barrière 61.31%' / 'Low strike 72%' / 'American barrier 60%' -> (type, strike, barrier)."""
    if not text:
        return None, None, None
    t = str(text)
    lvl = _pct(t)
    if re.search(r"barri", t, re.I):
        kind = "american barrier" if re.search(r"american|daily|continuous|am[eé]ricaine", t, re.I) else "european barrier"
        return kind, 1.0, lvl
    if re.search(r"strike", t, re.I):
        return "low strike", lvl, None
    return None, None, None


def read_sheet(path: Path) -> list[Product]:
    rows = _rows(path)
    head_i = next((i for i, r in enumerate(rows) if r and str(r[0] or "").strip().lower() in ("basket", "product", "#")), None)
    if head_i is None:
        raise ValueError(f"{path.name}: no header row starting with 'Basket' or 'Product'")
    header = [str(c or "").strip() for c in rows[head_i]]
    cols: dict[str, int] = {}
    under_cols: list[int] = []
    for j, h in enumerate(header):
        key = h.lower()
        if re.match(r"^(underlying|sous-jacent|name)\s*\d*$", key):
            under_cols.append(j)
        elif key in SYN and SYN[key] not in cols:
            cols[SYN[key]] = j
    products: list[Product] = []
    for r in rows[head_i + 1:]:
        if not r or r[0] is None:
            continue
        first = str(r[0]).strip()
        get = lambda f: r[cols[f]] if f in cols and cols[f] < len(r) else None
        if first.upper() == "CASH":
            products.append(Product(number=0, weight=_pct(get("weight")), product_type="cash", source_file=path.name))
            continue
        if not re.match(r"^\d+$", first.split(".")[0]):
            continue
        names = [str(r[j]).strip() for j in under_cols if j < len(r) and r[j] not in (None, "")]
        p = Product(number=int(float(first)), source_file=path.name,
                    underlyings=[Underlying(name=n) for n in names if n])
        p.coupon = _pct(get("coupon"))
        kind, strike, barrier = parse_protection(get("protection"))
        if kind is None and get("barrier") is not None:
            kind, strike, barrier = "european barrier", _pct(get("strike")) or 1.0, _pct(get("barrier"))
        elif kind is None and get("strike") is not None:
            kind, strike = "low strike", _pct(get("strike"))
        p.protection_type, p.strike, p.barrier = kind, strike, barrier
        p.tenor_months = _months(get("tenor"))
        p.weight = _pct(get("weight"))
        p.fees = _pct(get("fees"))
        p.stepdown = str(get("stepdown")).strip() if get("stepdown") not in (None, "") else None
        p.issuer = issuer_short(str(get("issuer"))) if get("issuer") not in (None, "") else None
        p.currency = str(get("currency")).strip().upper() if get("currency") else None
        p.isin = str(get("isin")).strip() if get("isin") else None
        p.theme = str(get("theme")).strip() if get("theme") else None
        p.initial_fixing = _date(get("initial_fixing"))
        p.final_fixing = _date(get("final_fixing"))
        for f in ("coupon", "protection_type", "tenor_months", "weight", "issuer", "currency", "isin"):
            p.sources[f] = "sheet" if getattr(p, f) is not None else "missing"
        products.append(p)
    return products


# ---------------------------------------------------------------------------------------------
# PDF and HTML to text

def pdf_text(path: Path) -> str:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join((page.extract_text(x_tolerance=1.5) or "") for page in pdf.pages[:8])


def html_text(path: Path) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    lines = []
    # label / value pairs (pricer pages)
    for lab in soup.find_all(["label", "dt", "th"]):
        val = lab.find_next(class_=re.compile("value")) if lab.name == "label" else lab.find_next(["dd", "td"])
        if val:
            lines.append(f"{lab.get_text(' ', strip=True)}   {val.get_text(' ', strip=True)}")
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if cells:
            lines.append("   ".join(cells))
    title = soup.find(["h1", "h2", "h3", "h4", "h5", "title"])
    head = title.get_text(" ", strip=True) if title else ""
    body = soup.get_text("\n", strip=True)
    return "\n".join([head, *lines, body])


# ---------------------------------------------------------------------------------------------
# term-sheet parser

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _date(v) -> str | None:
    if v in (None, ""):
        return None
    if isinstance(v, (dt.date, dt.datetime)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})\s+([A-Za-zéû]{3,})\.?\s+(\d{4})", s)
    if m and m.group(2)[:3].lower() in MONTHS:
        return f"{int(m.group(3)):04d}-{MONTHS[m.group(2)[:3].lower()]:02d}-{int(m.group(1)):02d}"
    return None


def _field(text: str, *labels: str, value: str = r"(.+)") -> str | None:
    for lab in labels:
        m = re.search(rf"(?im)^\s*{lab}\b[\s:]*{value}", text)
        if m:
            return m.group(1).strip()
    return None


def _isin_ok(isin: str) -> bool:
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch) * (2 if i % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (10 - total % 10) % 10 == int(isin[-1])


def parse_terms(text: str, source: str) -> Product:
    p = Product(number=1, source_file=source)
    src = lambda f, how="document": p.sources.__setitem__(f, how)
    flat = re.sub(r"[ \t]+", " ", text)

    # ISIN
    for m in re.finditer(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b", text):
        if m.group(1)[:2] in ("CH", "XS", "DE", "FR", "LU", "NL", "GB", "IE", "JE", "GG", "AT", "IT", "ES", "US") \
                and (_isin_ok(m.group(1)) or "O" in m.group(1)):
            p.isin = m.group(1); src("isin"); break

    # title line: "20.70% p.a. Multi Reverse Convertible on Lynas, MP Materials, USA Rare Earth"
    title = re.search(r"(?im)^\s*(?:[\w ]*?)?(\d+(?:[.,]\d+)?)\s*%\s*p\.?\s?a\.?\s+(.+?)\s+on\s+(.+)$", text)
    title2 = re.search(r"(?im)^.*?(barrier reverse convertible|reverse convertible|phoenix|autocallable[\w ]*|express)[\w ]*\s+on\s+(.+)$", text)

    cp = _field(flat, r"Coupon Rate", r"Coupon", r"Kupon", value=r"[^\d\n]{0,25}(\d+(?:[.,]\d+)?\s*%)")
    if cp is None and title:
        cp = title.group(1) + "%"
    if cp:
        p.coupon = _pct(cp); src("coupon")
    freq = re.search(r"(?i)\b(monthly|quarterly|semi-?annual(?:ly)?|annual(?:ly)?)\b", flat)
    p.frequency = freq.group(1).lower() if freq else None

    # product type
    ptype = _field(flat, r"Product Type", r"Product type", r"SSPA Product Type")
    if title:
        p.product_type = title.group(2).strip()
    elif ptype:
        p.product_type = ptype

    # currency
    ccy = _field(flat, r"Settlement Currency", r"Currency", r"Product Currency", r"Issue Currency", value=r"([A-Z]{3})\b")
    if not ccy:
        m = re.search(r"issued in ([A-Z]{3})", flat) or re.search(r"Denomination\s+([A-Z]{3})", flat)
        ccy = m.group(1) if m else None
    if ccy:
        p.currency = ccy; src("currency")

    # issuer
    iss = _field(flat, r"Issuer", r"Emittent", r"Emetteur", r"Émetteur")
    if iss and not re.match(r"(?i)risk", iss):
        p.issuer = issuer_short(iss); src("issuer")

    # strike, barrier
    strike = re.search(r"(?i)Strike(?: Level| Price)?\s*\(?\s*(\d+(?:[.,]\d+)?)\s*%", flat)
    barrier = re.search(r"(?i)(?:Barrier|Knock-?In)(?: Level)?\s*\(?\s*(\d+(?:[.,]\d+)?)\s*%", flat)
    btype = re.search(r"(?i)barrier (?:type|observation)\s+(\w+)", flat)
    if barrier:
        p.barrier = _pct(barrier.group(1) + "%")
        american = (btype and btype.group(1).lower().startswith("american")) or re.search(r"(?i)american|daily close|continuous", flat)
        european = (btype and btype.group(1).lower().startswith("european")) or re.search(r"(?i)european|at maturity only", flat)
        p.protection_type = "european barrier" if european and not (btype and btype.group(1).lower().startswith("american")) else \
            "american barrier" if american else "european barrier"
        p.strike = _pct(strike.group(1) + "%") if strike else 1.0
        src("protection_type")
    elif strike:
        p.strike = _pct(strike.group(1) + "%")
        p.protection_type = "low strike"; src("protection_type")

    # autocall
    trig = re.search(r"(?i)Autocall Trigger Level\s*\(?\s*(\d+(?:[.,]\d+)?)\s*%", flat)
    if trig:
        p.autocall_trigger = _pct(trig.group(1) + "%")
    levels = [float(x.replace(",", ".")) for x in re.findall(r"(?m)^\s*\d+\s+\d{2}[./]\d{2}[./]\d{4}\s+(\d{2,3}(?:[.,]\d+)?)%", text)]
    if len(levels) >= 2 and len(set(levels)) > 1:
        p.stepdown = "→".join(f"{x:g}%" for x in levels[:3]) + ("→…→" + f"{levels[-1]:g}%" if len(levels) > 3 else "")

    # dates
    for f, labs in (("initial_fixing", (r"Initial Fixing Date", r"Trade Date", r"Pricing Date", r"Strike Date")),
                    ("final_fixing", (r"Final Fixing Date", r"Valuation Date", r"Final Valuation Date")),
                    ("redemption_date", (r"Redemption Date", r"Maturity Date", r"Final Redemption Date"))):
        v = _date(_field(flat, *labs))
        if v:
            setattr(p, f, v); src(f)
    if p.initial_fixing and p.final_fixing:
        a, b = dt.date.fromisoformat(p.initial_fixing), dt.date.fromisoformat(p.final_fixing)
        p.tenor_months = round((b - a).days / 30.44); src("tenor_months", "calculated from the fixing dates")

    # underlyings: Bloomberg codes in order, with names from the same line or from the title
    unders: list[Underlying] = []
    for m in re.finditer(r"(?m)^(.*?)\b([A-Z0-9/]{1,8})\s+(UW|UQ|UN|US|SW|SE|VX|LN|FP|GY|GR|NA|IM|SM|BB|AT|AU|HK|JP|JT|CN|CT|SS|DC|NO|FH|ID|PL|KS|TT)\b(?:\s+Equity)?(.*)$", text):
        code = f"{m.group(2)} {m.group(3)}"
        # which price column is the initial level: the header above says (e.g. "Market price | Initial fixing level")
        head = next((l for l in reversed(text[:m.start()].splitlines()[-12:]) if re.search(r"(?i)initial", l)), "")
        col = 1 if re.search(r"(?i)(market|last|current|spot)\s*(price|level)?.*initial", head) else 0
        pairs = re.findall(r"\b([A-Z]{3})\s*([\d’',]+\.\d+)", m.group(4))
        lvl = pairs[col] if len(pairs) > col else None
        level = float(re.sub(r"[’',]", "", lvl[1])) if lvl else None
        old = next((u for u in unders if u.bloomberg == code), None)
        if old:
            if old.initial_level is None and level is not None:
                old.initial_level, old.currency = level, lvl[0]
            continue
        before = re.sub(r"\s{2,}.*$", "", m.group(1).strip())
        name = re.sub(r"[(\s]+$", "", before) or m.group(2)
        unders.append(Underlying(name=name.title() if name.isupper() else name, bloomberg=code,
                                 symbol=from_bloomberg(code), match="Bloomberg ticker in the document",
                                 initial_level=level, currency=lvl[0] if lvl else None))
    for m in re.finditer(r"\b(NKY|SX5E|SPX|SMI|DAX|CAC|UKX|HSI|OMX|NDX|RTY)\s+Index\b", text):
        code = f"{m.group(1)} Index"
        if not any(u.bloomberg == code for u in unders):
            unders.append(Underlying(name=m.group(1), bloomberg=code, symbol=from_bloomberg(code), match="Bloomberg ticker in the document"))
    title_names = []
    t = title or title2
    if t:
        tail = t.group(t.lastindex).split(" - ")[0]
        title_names = [n.strip() for n in re.split(r",| and | & ", tail) if n.strip()]
    if not unders:
        unders = [Underlying(name=n) for n in title_names]
    elif title_names and len(title_names) == len(unders):
        for u, n in zip(unders, title_names):
            u.name = n
    p.underlyings = unders
    src("underlyings")
    for f in ("coupon", "protection_type", "issuer", "currency", "isin", "tenor_months"):
        p.sources.setdefault(f, "missing" if getattr(p, f) is None else "document")
    return p


# ---------------------------------------------------------------------------------------------
# merging a product sheet with term sheets

TERMS = ("issuer", "currency", "isin", "product_type", "initial_fixing", "final_fixing", "redemption_date",
         "frequency", "autocall_trigger")


def merge(products: list[Product], log=print) -> list[Product]:
    """When an Excel sheet and term sheets describe the same products, keep one record per product.

    A term sheet is matched to a sheet row by ISIN, else by the same set of underlyings (symbols).
    The sheet decides coupon, strike, barrier and names; the term sheet adds the issuer, currency,
    ISIN, dates, initial levels and Bloomberg codes, and fills anything the sheet left empty.
    """
    rows = [p for p in products if p.source_file and p.source_file.lower().endswith((".xlsx", ".xlsm", ".csv"))]
    docs = [p for p in products if p not in rows]
    if not rows or not docs:
        return products
    key = lambda p: frozenset(u.symbol for u in p.underlyings if u.symbol)
    used = set()
    for d in docs:
        row = next((r for r in rows if r.product_type != "cash" and d.isin and r.isin == d.isin), None) or \
              next((r for r in rows if r.product_type != "cash" and key(r) and key(r) == key(d) and id(r) not in used), None)
        if not row:
            continue
        used.add(id(row)); d.number = -1
        for f in TERMS:
            if getattr(row, f) in (None, "") and getattr(d, f) not in (None, ""):
                setattr(row, f, getattr(d, f)); row.sources[f] = f"term sheet {d.source_file}"
        for f in ("coupon", "strike", "barrier", "protection_type", "stepdown"):
            if getattr(row, f) is None and getattr(d, f) is not None:
                setattr(row, f, getattr(d, f)); row.sources[f] = f"term sheet {d.source_file}"
        if row.tenor_months is None and d.tenor_months:
            row.tenor_months, row.sources["tenor_months"] = d.tenor_months, d.sources.get("tenor_months", "term sheet")
        if row.coupon is not None and d.coupon is not None and abs(row.coupon - d.coupon) > 1e-6:
            log(f"     product {row.number}: coupon {row.coupon*100:.2f}% in the sheet, {d.coupon*100:.2f}% in {d.source_file}: the sheet's is used")
        by_sym = {u.symbol: u for u in d.underlyings if u.symbol}
        for u in row.underlyings:
            t = by_sym.get(u.symbol)
            if t:
                u.bloomberg = u.bloomberg or t.bloomberg
                u.initial_level = u.initial_level or t.initial_level
                u.currency = u.currency or t.currency
        row.sources["merged with"] = d.source_file
        log(f"     product {row.number} ({' / '.join(u.name for u in row.underlyings)}) completed from {d.source_file}")
    left = [d for d in docs if d.number != -1]
    n = max((r.number for r in rows), default=0)
    for d in left:
        n += 1; d.number = n
        log(f"     {d.source_file}: not in the sheet, added as product {n}")
    return rows + left
