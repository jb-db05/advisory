"""Turn raw rows into clean trades, or explain exactly why a row is refused.

Rule of thumb: anything that can be fixed without guessing is fixed and
noted as a warning; anything that would need a guess is rejected with a
message saying what to change.
"""

import datetime as dt
import re

import pandas as pd

from .schema import HEADERS, KEYS, LIST_FIELDS, REQUIRED

FEE_TOLERANCE_ABS = 1.0       # currency units
FEE_TOLERANCE_REL = 0.005     # 0.5 % of the expected fee
MAX_FEE_RATE = 0.06           # anything above 6 % is treated as a typo
FRACTION_CUTOFF = 0.05        # 0.0184 is a fraction, 1.84 is percent points
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


class RowError(ValueError):
    pass


# --------------------------------------------------------------------------
# Value parsers
# --------------------------------------------------------------------------

def blank(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    return isinstance(v, str) and not v.strip()


def parse_date(v) -> dt.date:
    if isinstance(v, pd.Timestamp):
        return v.date()
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and 20000 < v < 80000:     # Excel serial
        return (dt.datetime(1899, 12, 30) + dt.timedelta(days=float(v))).date()
    s = str(v).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return dt.date.fromisoformat(s[:10])
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%y", "%d/%m/%y",
                "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%b-%y", "%Y%m%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise RowError(f"cannot read trade date '{s}' (use DD.MM.YYYY)")


def parse_number(v, what="number") -> float:
    if isinstance(v, bool):
        raise RowError(f"{what} '{v}' is not a number")
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(" ", "")
    s = re.sub(r"^[A-Za-z]{3}(?=[\d.,-])|(?<=[\d.])[A-Za-z]{3}$", "", s)  # USD130000
    s = s.replace("'", "").replace("’", "")
    mult = 1.0
    m = re.match(r"^(.*?)(k|m|mio|mn|mm)$", s, re.I)
    if m:
        s, unit = m.group(1), m.group(2).lower()
        mult = 1e3 if unit == "k" else 1e6
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):                       # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:                                                 # 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s):            # 130,000
            s = s.replace(",", "")
        else:                                                 # 1,84
            s = s.replace(",", ".")
    try:
        return float(s) * mult
    except ValueError:
        raise RowError(f"{what} '{v}' is not a number") from None


def parse_fee_rate(v, size=None, fee_amount=None):
    """Return (fraction, warning). Accepts 1.84%, '1,84', 1.84 or 0.0184."""
    if isinstance(v, str) and "%" in v:
        return parse_number(v.replace("%", ""), "fee rate") / 100, ""
    x = parse_number(v, "fee rate")
    as_fraction, as_points = x, x / 100
    # When the fee amount is filled in it tells us which reading is right.
    if size and fee_amount:
        implied = fee_amount / size
        if abs(as_points - implied) < abs(as_fraction - implied):
            return as_points, ""
        return as_fraction, ""
    return (as_fraction, "") if x <= FRACTION_CUTOFF else (as_points, "")


def isin_valid(isin: str) -> bool:
    if not ISIN_RE.match(isin):
        return False
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10 == int(isin[-1])


def clean_text(v) -> str:
    if blank(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v).split())


# --------------------------------------------------------------------------
# Row cleaning
# --------------------------------------------------------------------------

def clean_row(raw: dict, ref, today=None):
    """Return (clean dict, errors list, warnings list)."""
    today = today or dt.date.today()
    errors, warnings = [], []
    out = {}

    for key in REQUIRED:
        if key == "fee_pct" and not blank(raw.get("fee_amount")):
            continue                     # rate can be derived from the amount
        if blank(raw.get(key)):
            errors.append(f"{HEADERS[key]} is empty")

    def attempt(key, fn):
        if blank(raw.get(key)):
            return None
        try:
            return fn(raw[key])
        except RowError as e:
            errors.append(str(e))
            return None

    # Dates
    d = attempt("trade_date", parse_date)
    if d:
        if d > today + dt.timedelta(days=7):
            errors.append(f"trade date {d:%d.%m.%Y} is in the future")
        elif d.year < 2000:
            errors.append(f"trade date {d:%d.%m.%Y} looks wrong")
    out["trade_date"] = d

    # ISIN
    isin = re.sub(r"\s", "", clean_text(raw.get("isin"))).upper()
    if isin and not isin_valid(isin):
        errors.append(f"ISIN '{isin}' is invalid (format or check digit)")
    out["isin"] = isin

    # Client / account id: keep as text, never as a float.
    out["nclidos"] = clean_text(raw.get("nclidos"))

    # Amounts
    size = attempt("size", lambda v: parse_number(v, "size"))
    if size is not None and size <= 0:
        errors.append("size must be positive")
    fee_amount = attempt("fee_amount", lambda v: parse_number(v, "fee amount"))
    fee_pct = None
    if not blank(raw.get("fee_pct")):
        try:
            fee_pct, w = parse_fee_rate(raw["fee_pct"], size, fee_amount)
            if w:
                warnings.append(w)
        except RowError as e:
            errors.append(str(e))
    elif fee_amount is not None and size:
        fee_pct = fee_amount / size
        warnings.append(f"fee rate derived from amount: {fee_pct:.4%}")

    if fee_pct is not None and not (0 <= fee_pct <= MAX_FEE_RATE):
        errors.append(f"fee rate {fee_pct:.2%} is outside 0–{MAX_FEE_RATE:.0%}")

    comments = clean_text(raw.get("comments"))
    if size and fee_pct is not None:
        expected = round(size * fee_pct, 2)
        if fee_amount is None:
            fee_amount = expected
        else:
            diff = abs(fee_amount - expected)
            if diff > max(FEE_TOLERANCE_ABS, FEE_TOLERANCE_REL * expected):
                msg = (f"fee amount {fee_amount:,.2f} ≠ size × rate "
                       f"{expected:,.2f} (diff {fee_amount - expected:+,.2f})")
                if comments:
                    warnings.append(msg + " — kept, see comment")
                else:
                    errors.append(msg + " — fix it or explain in Comments")
    out["size"], out["fee_pct"], out["fee_amount"] = size, fee_pct, fee_amount

    # Reference-list fields
    for key in LIST_FIELDS:
        val = clean_text(raw.get(key))
        if key == "currency":
            val = val.upper()
        if not val:
            out[key] = ""
            continue
        canon, note = ref.resolve(key, val)
        if canon is None:
            errors.append(note)
            out[key] = val
        else:
            if note == "corrected":
                warnings.append(f"{HEADERS[key]} '{val}' corrected to '{canon}'")
            out[key] = canon

    out["comments"] = comments
    return out, errors, warnings


def clean_frame(raw: pd.DataFrame, ref, today=None):
    """Split a raw frame into (accepted, rejected) DataFrames."""
    accepted, rejected = [], []
    for rec in raw.to_dict("records"):
        out, errors, warnings = clean_row(rec, ref, today)
        meta = {"source_file": rec.get("source_file", ""),
                "source_row": rec.get("source_row", "")}
        if errors:
            # Keep what the user typed so the exceptions file can be fixed in place.
            orig = {k: rec.get(k) for k in KEYS}
            rejected.append({**orig, **meta, "errors": "; ".join(errors)})
        else:
            accepted.append({**out, **meta, "warnings": "; ".join(warnings)})
    cols_ok = KEYS + ["source_file", "source_row", "warnings"]
    cols_bad = KEYS + ["source_file", "source_row", "errors"]
    return (pd.DataFrame(accepted, columns=cols_ok),
            pd.DataFrame(rejected, columns=cols_bad))


def dedupe_key(df: pd.DataFrame) -> pd.Series:
    return (pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d") + "|" +
            df["isin"].astype(str) + "|" + df["nclidos"].astype(str) + "|" +
            df["size"].astype(float).round(2).astype(str))
