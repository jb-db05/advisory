"""Turn extracted term sheet fields into the standardised SYZ file name.

Convention learned from the reference set (B01_ref02.zip):

    YYMMDD - CCY DUR ISSUER TYPE COUPON% TICK1-TICK2 - ISIN
    260914 - EUR 18M RAF AC 7.20% SX5E-NDX-RTY - CH1600433705
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

RULES_PATH = Path(__file__).with_name("rules.json")
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@lru_cache(maxsize=1)
def load_rules() -> dict:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def months_between(start: date, end: date) -> int:
    """Whole months between two dates, rounded to the nearest month.

    Fixing dates shift for weekends/holidays (e.g. 11/09/2026 -> 13/09/2027),
    so a few days either way must still count as a whole period.
    """
    months = (end.year - start.year) * 12 + (end.month - start.month)
    day_diff = end.day - start.day
    if day_diff >= 15:
        months += 1
    elif day_diff <= -15:
        months -= 1
    return months


def duration_label(start: date | None, end: date | None) -> str:
    if not start or not end or end <= start:
        return ""
    months = months_between(start, end)
    if months <= 0:
        return ""
    return f"{months // 12}Y" if months % 12 == 0 else f"{months}M"


def duration_from_values(values: dict) -> str:
    """Duration from edited field values: fixing_date as YYMMDD, final_fixing_date as DD/MM/YYYY."""
    try:
        start = datetime.strptime(values.get("fixing_date", ""), "%y%m%d").date()
        end = datetime.strptime(values.get("final_fixing_date", ""), "%d/%m/%Y").date()
    except ValueError:
        return ""
    return duration_label(start, end)


def format_coupon(rate: float | None) -> str:
    """At least two decimals, more only when significant: 5 -> 5.00%, 3.625 -> 3.625%."""
    if rate is None:
        return ""
    text = f"{rate:.4f}".rstrip("0")
    whole, _, decimals = text.partition(".")
    return f"{whole}.{decimals.ljust(2, '0')}%"


def format_level(level: float | None) -> str:
    """Protection / cap levels as in the examples: 122.00 -> 122%, 97.5 -> 97.5%."""
    if level is None:
        return ""
    return f"{level:.4f}".rstrip("0").rstrip(".") + "%"


def format_date(value: date | None, rules: dict | None = None) -> str:
    rules = rules or load_rules()
    return value.strftime(rules["date_format"]) if value else ""


NAME_FIELDS = ("fixing_date", "currency", "duration", "issuer", "product_type", "coupon", "underlyings", "identifier")


_NAME_RE = re.compile(
    r"^(?P<fixing_date>\d{6}) - (?P<currency>[A-Z]{3}) (?P<duration>\d+[YM]) (?P<issuer>[A-Z]+) "
    # The coupon sometimes appears without its "%" sign in existing names ("SG AC 10.00 RTX-RHM-HO").
    r"(?P<product_type>[A-Z]+) (?:(?P<benchmark>[A-Z][A-Z0-9]*) )?(?:(?P<coupon>\d+(?:\.\d+)?)%? )?(?:- )?"
    r"(?:(?P<protection>\d+(?:\.\d+)?)% KG - )?(?P<underlyings>.+?) - (?P<identifier>[A-Z0-9]{12})$"
)


def parse_name(name: str) -> dict | None:
    """Split an existing file name into normalised fields (tolerates the format variants in the examples)."""
    m = _NAME_RE.match(name.strip())
    if not m:
        return None
    fields = m.groupdict()
    number = float(fields["coupon"]) if fields["coupon"] else None
    # In capital protection names the first percentage is the cap, not a coupon.
    fields["coupon"], fields["cap"] = (None, number) if fields["protection"] else (number, None)
    fields["protection"] = float(fields["protection"]) if fields["protection"] else None
    fields["underlyings"] = [t for t in re.split(r"[-\s]+", fields["underlyings"]) if t]
    return fields


def build_name(values: dict, rules: dict | None = None) -> str:
    """Build the file name (without .pdf) from plain string field values."""
    rules = rules or load_rules()
    underlyings = values.get("underlyings", "")
    if isinstance(underlyings, (list, tuple)):
        underlyings = rules["underlying_separator"].join(underlyings)
    parts = {key: str(values.get(key) or "").strip() for key in NAME_FIELDS}
    parts["underlyings"] = str(underlyings).strip()
    name = rules["name_template"].format(**parts)
    name = re.sub(r" {2,}", " ", name)
    while " - - " in name:  # an empty part between two separators (e.g. CPN coupon "122% - 90% KG -")
        name = name.replace(" - - ", " - ")
    name = re.sub(r"(^\s*-\s*)|(\s*-\s*$)", "", name).strip()
    return _INVALID_FILENAME_CHARS.sub("", name)


# --------------------------------------------------------------------------- step 2: booking label


def _short_percentages(text: str) -> str:
    """'3.50%' -> '3.5%', '13.00%' -> '13%', '3.625%' unchanged."""
    return re.sub(r"\d+(?:[.,]\d+)?(?=%)", lambda m: format_level(float(m[0].replace(",", ".")))[:-1], text)


def build_label(values: dict, rules: dict | None = None) -> tuple[str, str]:
    """Short booking label 'BIL AC 3.5% MCD-RTX-SU' (at most label_max_length characters).

    If it is too long: 1. drop the product type, 2. drop the "%" signs.
    Returns (label, note explaining any shortening).
    """
    rules = rules or load_rules()
    limit = rules["label_max_length"]
    sep = rules["underlying_separator"]
    issuer = str(values.get("issuer") or "").strip()
    product = str(values.get("product_type") or "").strip()
    # The coupon slot may hold separators (CPN "122% - 90% KG -"); the label only keeps the words.
    coupon = " ".join(t for t in _short_percentages(str(values.get("coupon") or "")).split() if t != "-")
    tickers = [t for t in str(values.get("underlyings") or "").strip().split(sep) if t]

    def join(*parts: str) -> str:
        return " ".join(p for p in parts if p)

    underlyings = sep.join(tickers)
    full = join(issuer, product, coupon, underlyings)
    without_type = join(issuer, coupon, underlyings)
    for label, note in ((full, ""),
                        (without_type, "product type removed to fit"),
                        (without_type.replace("%", ""), "product type and '%' removed to fit")):
        if len(label) <= limit:
            return label, note
    return without_type.replace("%", ""), f"still longer than {limit} characters, please shorten it"


def build_instructions(label: str, rules: dict | None = None) -> str:
    rules = rules or load_rules()
    return rules["instructions_template"].replace("{label}", label)
