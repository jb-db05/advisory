"""Fill a proposition from a term sheet PDF.

The heavy lifting is already done by `syz_advisory.termsheets`, which the
B01 automation uses: it reads the PDF text and pulls out the issuer,
currency, duration, coupon, strike, frequency, underlyings and ISIN. This
module adds the three things a roll proposition needs on top of that --
the platform product description, the autocall trigger schedule and the
non-call period -- and shapes the result for each of the two screens.

Screen 1 takes the *expiring* product; screen 2 takes the *new* product and
becomes the table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from syz_advisory.brand import DEFAULT_ACCENT
from syz_advisory.termsheets import extract
from syz_advisory.termsheets.confirmation import email_values, product_title
from syz_advisory.termsheets.naming import months_between

from .catalogue import FIELDS_BY_KEY
from .models import swiss_amount

# "20.70% p.a. Multi Reverse Convertible on Lynas, MP Materials, USA Rare Earth"
# -- the wording the platform shows, which is what the email quotes.
_DESCRIPTION = re.compile(
    r"(?P<desc>[\d][\d.,]*\s*%\s*p\.\s?a\.\s+"          # 20.70% p.a.
    r"(?:Multi\s+)?[A-Z][A-Za-z&\-® ]{3,60}?"       # Multi Reverse Convertible
    r"\s+on\s+"                                           # on
    r"[A-Z0-9][^;]{2,180}?)"                              # Lynas, MP Materials, ...
    r"\s*(?=Autocallable|Final Fixing|Issued|issued|;|Valor|ISIN|SVSP|$)",
    re.IGNORECASE,
)

# Leonteq schedules glue the rows together:
# "16/12/2026100.00%09/12/20261" = payment date, level, observation date, index
_SCHEDULE_ROW = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s*([\d.]+)\s*%\s*(\d{2}/\d{2}/\d{4})\s*(\d{1,2})\b"
)
_TRIGGER_LEVEL = re.compile(r"Autocall Trigger Level\s*\(\s*([\d.]+)\s*%\s*\)", re.I)
_ISIN = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b")


def flatten(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@dataclass(frozen=True)
class Observation:
    payment: date
    level: float
    observation: date
    index: int


def read_pdf(data: bytes) -> str:
    """PDF bytes -> text, via the shared extractor."""
    return extract.pdf_text(data)


# --- the three extras ------------------------------------------------------
def platform_description(flat: str) -> str:
    """The product description as the platform writes it, or ''."""
    match = _DESCRIPTION.search(flat)
    if not match:
        return ""
    desc = re.sub(r"\s+", " ", match.group("desc")).strip(" ,;")
    # Guard against the regex running past the name into body copy.
    return desc if len(desc) <= 200 else ""


def observations(flat: str) -> list[Observation]:
    """The autocall observation schedule, earliest observation first."""
    found: list[Observation] = []
    for payment, level, observation, index in _SCHEDULE_ROW.findall(flat):
        try:
            found.append(Observation(
                payment=datetime.strptime(payment, "%d/%m/%Y").date(),
                level=float(level),
                observation=datetime.strptime(observation, "%d/%m/%Y").date(),
                index=int(index),
            ))
        except ValueError:
            continue
    return sorted(found, key=lambda o: o.observation)


def _percent(level: float) -> str:
    text = f"{level:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def autocall_trigger(flat: str) -> str:
    """A flat trigger ('100%') or a step-down schedule ('100% ↓ 96% ↓ ...')."""
    schedule = observations(flat)
    levels = [o.level for o in schedule]
    if levels and len(set(levels)) > 1:
        # Step down: show the ends rather than every step, as the desk does.
        steps = [_percent(v) for v in levels]
        if len(steps) > 4:
            steps = steps[:2] + ["…"] + steps[-2:]
        return " ↓ ".join(steps)
    if levels:
        return _percent(levels[0])
    if match := _TRIGGER_LEVEL.search(flat):
        return _percent(float(match.group(1)))
    return ""


def non_call_period(flat: str, fixing: date | None) -> str:
    """Months between the initial fixing and the first autocall observation."""
    schedule = observations(flat)
    if not schedule or not fixing:
        return ""
    months = months_between(fixing, schedule[0].observation)
    if months <= 0:
        return ""
    return f"{months}-Month" if months == 1 else f"{months}-Months"


def initial_fixing(ts) -> date | None:
    """The fixing date, which the shared extractor stores as YYMMDD."""
    raw = ts.fixing_date.value or ""
    try:
        return datetime.strptime(raw, "%y%m%d").date()
    except ValueError:
        return None


def final_fixing(ts) -> str:
    """The final fixing date as dd.mm.yyyy, for the relevant-date field."""
    raw = ts.final_fixing_date.value or ""
    try:
        return datetime.strptime(raw, "%d/%m/%Y").date().strftime("%d.%m.%Y")
    except ValueError:
        return ""


# --- screen payloads -------------------------------------------------------
def describe(ts, flat: str) -> str:
    """Platform wording when the sheet carries it, else built from the fields."""
    if desc := platform_description(flat):
        return desc
    values = ts.values()
    coupon = values.get("coupon", "")
    wording = product_title(values).split(" ", 1)[-1] if values.get("product_type") else ""
    names = (ts.underlying_names.value or "").replace("\n", ", ")
    parts = [f"{coupon} p.a." if coupon else "", wording, f"on {names}" if names else ""]
    return " ".join(p for p in parts if p).strip()


def expiring_product(ts, flat: str) -> dict:
    """Screen 1: the ISIN, description and relevant date of the old product."""
    isin = ts.identifier.value or ""
    if not isin and (match := _ISIN.search(flat)):
        isin = match.group(1)
    return {
        "isin": isin,
        "description": describe(ts, flat),
        "relevant_date": final_fixing(ts),
        "currency": ts.currency.value or "",
    }


def normalise_delivery(settlement: str) -> str:
    """'Physical Delivery' -> 'PHYSICAL', as the reference table writes it."""
    text = settlement.strip().upper()
    if text.startswith("PHYSICAL"):
        return "PHYSICAL"
    if text.startswith("CASH"):
        return "CASH"
    return text


def _row(key: str, values: list[str]) -> dict:
    """A table row keyed to the catalogue, so labels stay bilingual."""
    field = FIELDS_BY_KEY[key]
    return {
        "key": field.key,
        "label_en": field.en,
        "label_fr": field.fr,
        "values": [v for v in values if v],
        "highlight": field.highlight,
        "accent_values": field.accent_values,
        "bold": field.bold,
    }


def product_table(ts, flat: str, size: str = "") -> dict:
    """Screen 2: the new product as a ready-to-render table.

    `size` overrides the term sheet's issue size with the size actually being
    rolled, which is what the client-facing table shows.
    """
    mail = email_values(ts)
    fixing = initial_fixing(ts)
    currency = ts.currency.value or ""
    amount = size or ts.size.value or currency

    rows = [
        _row("currency", [amount]),
        _row("maturity", [mail["maturity"]]),
        _row("underlyings", (ts.underlying_names.value or "").split("\n")),
        _row("strike", [mail["strike"]]),
        _row("autocall_trigger", [autocall_trigger(flat)]),
        _row("non_call_period", [non_call_period(flat, fixing)]),
        _row("autocall_frequency", [mail["frequency"]]),
        _row("guaranteed_coupon", [mail["coupon"]]),
    ]
    if delivery := normalise_delivery(ts.settlement.value or ""):
        rows.insert(4, _row("delivery", [delivery]))

    return {
        "template": "reverse_autocall_low_strike",
        "accent": DEFAULT_ACCENT,
        "header_en": mail["title"],
        "header_fr": "",
        "rows": rows,
        "issuer": ts.issuer.value or "",
    }


def roll_size(currency: str, accounts: list[dict] | None) -> str:
    """'CHF 70'000' from the accounts on screen 1, for the Currency row.

    The amount and the currency are taken from the same place: if the accounts
    state a currency it wins, so the row never pairs one account's size with
    the term sheet's denomination.
    """
    if not accounts:
        return ""
    stated = next((str(a.get("currency") or "").strip() for a in accounts
                   if str(a.get("currency") or "").strip()), "")
    currency = stated or currency
    total = 0.0
    for account in accounts:
        for key in ("roll_amount", "amount"):
            raw = str(account.get(key) or "").replace("'", "").replace(" ", "")
            if raw:
                try:
                    total += float(raw.replace(",", "."))
                except ValueError:
                    pass
                break
    if not total:
        return ""
    return " ".join(p for p in (currency, swiss_amount(total)) if p)


def from_text(text: str, target: str, accounts: list[dict] | None = None) -> dict:
    """Parse a term sheet -- or text copied off the platform -- for a screen."""
    from . import platform_fill

    # Text pasted from the product page or the pricer is laid out completely
    # differently from a term sheet, so it gets its own reader.
    if platform_fill.looks_like_platform(text):
        return platform_fill.from_text(text, target, accounts)

    flat = flatten(text)
    ts = extract.extract_fields(text)

    if target == "expiring":
        return {"target": target, "source": "termsheet",
                "fields": expiring_product(ts, flat)}

    currency = ts.currency.value or ""
    table = product_table(ts, flat, size=roll_size(currency, accounts))
    return {"target": target, "source": "termsheet", "product": table}


def from_bytes(data: bytes, target: str, accounts: list[dict] | None = None) -> dict:
    return from_text(read_pdf(data), target, accounts)


