"""Fill a proposition from text copied off the platform or the pricer.

A screenshot cannot be read on these machines (no OCR -- see the automation's
README), but everything in those screenshots is real text on the page. Select
it and copy, and this reads it: the product page for the expiring product, the
pricer for the new one.

Both layouts are label-driven, and the copy order varies with how the selection
was made, so every field is found by its own label rather than by position.
Anything absent is left empty for the user to fill.
"""

from __future__ import annotations

import re

from syz_advisory.brand import DEFAULT_ACCENT
from syz_advisory.termsheets.confirmation import product_title

from .catalogue import FIELDS_BY_KEY
from .models import swiss_amount

ISIN = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b")

# Words that end a free-text value: the next field's label.
_LABELS = (
    "ISIN", "VALOR", "ISSUER", "PRODUCT TYPE", "CURRENCY", "OUTSTANDING",
    "STATUS", "BID", "ASK", "TENOR", "COUPON RATE", "DENOMINATION",
    "ISSUE PRICE", "SETTLEMENT TYPE", "BARRIER TYPE", "STRIKE LEVEL",
    "INITIAL FIXING DATE", "ISSUE DATE", "FINAL FIXING DATE",
    "REDEMPTION DATE", "At a glance", "Lifecycle", "Historical Chart",
    "Performance", "Analytics", "Coupons", "INVESTMENT SIZE",
    "DISTRIBUTION FEE", "AUTOCALL TRIGGER LEVEL", "FIRST OBSERVATION",
    "FREQUENCY", "MATURITY", "COUPON AMOUNT", "COUPON P.A.", "COUPON TYPE",
    "DOWNSIDE PROTECTION", "EARLY REDEMPTIONS", "MECHANISM", "SCHEDULE",
    "UNDERLYINGS", "DATES",
)
_STOP = "|".join(re.escape(label) for label in _LABELS)


def flatten(text: str) -> str:
    return re.sub(r"[ \t ]+", " ", text).strip()


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# Chrome from the platform's own screens. Field labels alone are no use as a
# signal: a term sheet talks about strike levels and fixing dates too, and
# misrouting one would break the PDF path that already works. These are things
# only the web UI says, so one is conclusive.
_PLATFORM_MARKERS = (
    "AT A GLANCE",
    "PASTE YOUR PRICING TAG",
    "AUTO QUOTE",
    "BASKET OPTIMIZER",
    "OPEN IN QUOTE MODULE",
    "INVESTMENT PARAMETERS",
    "DOWNSIDE PROTECTION",
    "EARLY REDEMPTIONS",
    "HISTORICAL CHART",
    "ACTIVITY MONITOR",
    "EQUITY SCREENER",
    "SUCCESSFUL PRICES OUT OF",
    "LOWEST STRIKE",
    "HOW ARE PERFORMANCES CALCULATED",
)


def looks_like_platform(text: str) -> bool:
    """True when this is a copied product page or pricer, not a term sheet."""
    flat = squash(text).upper()
    return any(marker in flat for marker in _PLATFORM_MARKERS)


def field(text: str, label: str, pattern: str = r"(.+?)") -> str:
    """The value that follows a label, stopping at the next label or line end.

    Copying puts the value on the line after its label, so the gap after the
    label may contain newlines, but the value itself may not -- without that
    the match runs on and swallows the rest of the page.
    """
    after = re.search(
        rf"{re.escape(label)}\s*:?\s*{pattern}[ \t]*(?={_STOP}|\n|$)",
        text, re.IGNORECASE,
    )
    if after and after.group(1).strip():
        return squash(after.group(1))
    before = re.search(rf"{pattern}[ \t]*{re.escape(label)}\b", text, re.IGNORECASE)
    return squash(before.group(1)) if before else ""


def one_of(text: str, label: str, options: tuple[str, ...]) -> str:
    """A value from a fixed set, but only when the choice is unambiguous.

    A pricer control copies as every option it offers -- "Semi-Annually
    Quarterly Bi-Monthly Monthly" -- because which one is selected is shown
    visually, not in the text. Guessing here would put a wrong frequency or
    coupon type in a client email, so an ambiguous group returns nothing and
    the field is left for the user.
    """
    window = re.search(
        rf"{re.escape(label)}\s*:?\s*((?:[^\n]*\n?){{0,2}})", text, re.IGNORECASE,
    )
    haystack = window.group(1) if window else ""
    found = [o for o in options if re.search(rf"\b{re.escape(o)}\b", haystack, re.I)]
    return found[0] if len(found) == 1 else ""


def date_field(text: str, label: str) -> str:
    """A dd.mm.yyyy or dd/mm/yyyy date next to a label, normalised to dots."""
    raw = field(text, label, r"(\d{2}[./]\d{2}[./]\d{4})")
    return raw.replace("/", ".") if raw else ""


def percent_field(text: str, label: str) -> str:
    # The page writes "6.76 % P.A."; the trailing unit must be consumed or the
    # value never reaches the end of its line.
    raw = field(text, label, r"([\d.,]+)[ \t]*%?(?:[ \t]*[Pp]\.[ \t]?[Aa]\.)?")
    if not raw:
        return ""
    number = raw.replace(",", ".").rstrip(".")
    try:
        value = float(number)
    except ValueError:
        return ""
    return f"{value:g}%"


# --- durations -------------------------------------------------------------
def months_from_tenor(text: str) -> int:
    """'1 Year, 6 Months' -> 18; '1.25 Years' -> 15; '18-Month' -> 18."""
    total = 0.0
    for value, unit in re.findall(r"([\d.,]+)\s*[-\s]*(Years?|Months?)", text, re.I):
        amount = float(value.replace(",", "."))
        total += amount * 12 if unit.lower().startswith("year") else amount
    return round(total)


def duration_label(months: int) -> str:
    """18 -> '18-Month', 24 -> '2-Year' -- the long form the table shows."""
    if months <= 0:
        return ""
    if months % 12 == 0:
        years = months // 12
        return f"{years}-Year"
    return f"{months}-Month"


def duration_code(months: int) -> str:
    """18 -> '18M', 24 -> '2Y' -- what the title builder expects."""
    if months <= 0:
        return ""
    return f"{months // 12}Y" if months % 12 == 0 else f"{months}M"


PRODUCT_CODES = (
    ("barrier reverse", "BRC"),
    ("autocallable", "AC"),
    ("autocall", "AC"),
    ("reverse convertible", "RC"),
    ("beat the benchmark", "BTB"),
    ("capital protection", "CPN"),
    ("shark", "SN"),
)


def product_code(description: str) -> str:
    text = (description or "").lower()
    for needle, code in PRODUCT_CODES:
        if needle in text:
            return code
    return ""


def tidy_description(text: str) -> str:
    """The platform title-cases its heading; the email uses house casing."""
    out = squash(text)
    out = re.sub(r"\bP\.\s?A\.", "p.a.", out)
    out = re.sub(r"\bOn\b", "on", out)
    return out


def description_of(text: str) -> str:
    """The product name line, e.g. '6.76% p.a. Multi Reverse Convertible on ...'."""
    # The product name is a whole line of its own: take it to the line end
    # rather than guessing where the list of underlyings stops.
    match = re.search(
        r"^[ \t]*([\d][\d.,]*\s*%\s*[Pp]\.\s?[Aa]\.[ \t]+(?:Multi[ \t]+)?"
        r"[A-Z][^\n]{3,140}?[ \t]+[Oo]n[ \t]+[^\n]{3,160})[ \t]*$",
        text, re.MULTILINE,
    )
    if match:
        return tidy_description(match.group(1))
    for line in text.splitlines():
        if re.search(r"%\s*[Pp]\.\s?[Aa]\.", line) and re.search(r"\b[Oo]n\b", line):
            return tidy_description(line)
    return ""


# --- underlyings -----------------------------------------------------------
_TICKERED = re.compile(r"([A-Z][A-Za-z0-9&.À-ſ' -]{2,40}?)\s*\(([A-Z0-9]{1,6})\s+[A-Z]{2}\s+Equity\)")
_PRICER_ROW = re.compile(
    r"^\s*([A-Z][A-Z0-9&.\-' ]{2,40})\s*(?:AUTO QUOTE\s*\+?\s*OPTIMIZER|AUTO QUOTE)\s*$",
    re.MULTILINE,
)


def underlyings_of(text: str) -> list[str]:
    """Underlying names, in the order the page lists them."""
    # Pricer: each basket line ends with the AUTO QUOTE + OPTIMIZER control.
    rows = [squash(m) for m in _PRICER_ROW.findall(text)]
    if rows:
        return dedupe(rows)

    # Product page performance table: "Hannover Rück (HNR1 GY Equity)".
    tickered = [squash(name) for name, _ in _TICKERED.findall(text)]
    if tickered:
        return dedupe(tickered)

    # Otherwise the comma list under the heading, after "... on X, Y, Z".
    match = re.search(r"\s[Oo]n\s+([^\n]{3,160})", text)
    if match:
        names = [squash(p) for p in match.group(1).split(",")]
        return dedupe([n for n in names if n and len(n) < 60])
    return []


def dedupe(names: list[str]) -> list[str]:
    seen, out = set(), []
    for name in names:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return out


# --- screen 1: the expiring product ---------------------------------------
def expiring_product(text: str) -> dict:
    flat = flatten(text)
    isin = field(flat, "ISIN", r"([A-Z]{2}[A-Z0-9]{9}\d)")
    if not isin and (match := ISIN.search(flat)):
        isin = match.group(1)

    # The platform shows the final fixing date; that is the date the email
    # quotes for an autocall, an expiry or a maturity.
    relevant = (date_field(flat, "FINAL FIXING DATE")
                or date_field(flat, "REDEMPTION DATE"))

    status = field(flat, "STATUS", r"([A-Za-z]+)")
    return {
        "isin": isin,
        "description": description_of(text),
        "relevant_date": relevant,
        "currency": field(flat, "CURRENCY", r"([A-Z]{3})"),
        "status": status.upper() if status else "",
        "issuer": field(flat, "ISSUER"),
        "valor": field(flat, "VALOR", r"(\d{5,12})"),
    }


# --- screen 2: the new product --------------------------------------------
def _row(key: str, values: list[str]) -> dict:
    f = FIELDS_BY_KEY[key]
    return {
        "key": f.key,
        "label_en": f.en,
        "label_fr": f.fr,
        "values": [v for v in values if v],
        "highlight": f.highlight,
        "accent_values": f.accent_values,
        "bold": f.bold,
    }


def roll_size(currency: str, accounts: list[dict] | None, fallback: str) -> str:
    """The size for the Currency row: the accounts first, else the page."""
    if accounts:
        stated = next((str(a.get("currency") or "").strip() for a in accounts
                       if str(a.get("currency") or "").strip()), "")
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
        if total:
            return " ".join(p for p in (stated or currency, swiss_amount(total)) if p)
    return " ".join(p for p in (currency, fallback) if p)


def product_table(text: str, accounts: list[dict] | None = None) -> dict:
    flat = flatten(text)

    currency = field(flat, "CURRENCY", r"([A-Z]{3})")
    size = field(flat, "INVESTMENT SIZE", r"([\d'’,. ]+)")
    if not size:
        size = field(flat, "OUTSTANDING", r"([\d'’,. ]+)")
    size = squash(size.replace("’", "'"))

    months = months_from_tenor(field(flat, "MATURITY") or field(flat, "TENOR"))
    description = description_of(text)

    # Coupon: the pricer states a bare number, the product page a percentage.
    coupon = percent_field(flat, "COUPON P.A.") or percent_field(flat, "COUPON RATE")
    coupon_type = one_of(flat, "COUPON TYPE", ("Guaranteed", "Conditional"))

    strike = percent_field(flat, "STRIKE LEVEL") or percent_field(flat, "LOWEST STRIKE")
    trigger = percent_field(flat, "AUTOCALL TRIGGER LEVEL")
    first_call = field(flat, "FIRST OBSERVATION", r"([\d]+\s*[-\s]*Months?)")
    frequency = one_of(flat, "FREQUENCY", (
        "Monthly", "Quarterly", "Quaterly", "Semi-Annually", "Bi-Monthly",
        "Annually",
    ))
    barrier = percent_field(flat, "BARRIER LEVEL")
    barrier_type = field(flat, "BARRIER TYPE")
    settlement = field(flat, "SETTLEMENT TYPE", r"(Physical|Cash)")

    coupon_key = "coupon_pa"
    if coupon_type and coupon_type.lower().startswith("guaranteed"):
        coupon_key = "guaranteed_coupon"

    rows = [
        _row("currency", [roll_size(currency, accounts, size)]),
        _row("maturity", [duration_label(months)]),
        _row("underlyings", underlyings_of(text)),
        _row("strike", [strike]),
    ]
    if barrier:
        rows.append(_row("barrier_level", [barrier]))
    if barrier_type and "no barrier" not in barrier_type.lower():
        rows.append(_row("barrier_type", [barrier_type]))
    if settlement:
        rows.append(_row("delivery", [settlement.upper()]))
    rows += [
        _row("autocall_trigger", [trigger]),
        _row("non_call_period", [squash(first_call).replace(" ", "-") if first_call else ""]),
        _row("autocall_frequency", [frequency.replace("Quaterly", "Quarterly")]),
        _row(coupon_key, [f"{coupon} p.a." if coupon else ""]),
    ]

    # "Autocallable Reverse Convertible" is an autocall, so the stated product
    # type has to win over the wording of the name.
    code = product_code(f"{field(flat, 'PRODUCT TYPE')} {description}") or "AC"
    header = product_title({"duration": duration_code(months), "product_type": code})

    return {
        "template": "reverse_autocall_low_strike",
        "accent": DEFAULT_ACCENT,
        "header_en": header,
        "header_fr": "",
        "rows": rows,
        "issuer": field(flat, "ISSUER"),
    }


def from_text(text: str, target: str, accounts: list[dict] | None = None) -> dict:
    if target == "expiring":
        return {"target": target, "source": "platform",
                "fields": expiring_product(text)}
    return {"target": target, "source": "platform",
            "product": product_table(text, accounts)}
