"""Data model for an advisory roll proposition (email + product table)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from syz_advisory import brand

# The house palette is the accent set; older payloads that say "orange" or
# "blue" still resolve, so saved propositions keep working.
ACCENTS = dict(brand.PALETTE)
DEFAULT_ACCENT = brand.DEFAULT_ACCENT
_LEGACY = {
    "orange": "tiger_orange",
    "blue": "blueberry_blue",
    "cyan": "sky_blue",
}


def accent_hex(name: str) -> str:
    """Resolve an accent name (or a literal #rrggbb) to a hex colour."""
    return brand.accent(_LEGACY.get(name, name))


def swiss_amount(value: float) -> str:
    """Format 70000 as 70'000, the house thousands separator."""
    whole = round(value)
    if abs(value - whole) < 0.005:
        return f"{whole:,}".replace(",", "'")
    return f"{value:,.2f}".replace(",", "'")


def short_amount(value: float) -> str:
    """Format 70000 as 70K, 1500000 as 1.5M -- used in the recommendation line."""
    for cutoff, suffix in ((1_000_000, "M"), (1_000, "K")):
        if abs(value) >= cutoff:
            scaled = value / cutoff
            text = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return swiss_amount(value)


def parse_date(value: str | date | None) -> date | None:
    """Accept dd.mm.yyyy, yyyy-mm-dd or a date; return None for blanks."""
    if value is None or isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date: {value!r}")


def format_date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


@dataclass(frozen=True)
class Account:
    """A client account holding the expiring product."""

    number: str
    amount: float | None = None
    currency: str = ""
    # Size to roll into the new product; falls back to the holding amount.
    roll_amount: float | None = None

    @property
    def size(self) -> float | None:
        return self.roll_amount if self.roll_amount is not None else self.amount

    @property
    def holding_text(self) -> str:
        """The bold part of the holding line: \"70'000 CHF\"."""
        if self.amount is None:
            return ""
        return " ".join(p for p in (swiss_amount(self.amount), self.currency) if p)

    def holding_line(self) -> str:
        """'S4336600 - 70'000 CHF' as shown under the product paragraph."""
        if not self.holding_text:
            return self.number
        return f"{self.number} – {self.holding_text}"

    def roll_line(self) -> str:
        """'S4336600 70K CHF' as shown in the recommendation sentence."""
        if self.size is None:
            return self.number
        parts = [p for p in (short_amount(self.size), self.currency) if p]
        return f"{self.number} {' '.join(parts)}"

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        return cls(
            number=str(data.get("number", "")).strip(),
            amount=_opt_float(data.get("amount")),
            currency=str(data.get("currency", "")).strip().upper(),
            roll_amount=_opt_float(data.get("roll_amount")),
        )


@dataclass
class Row:
    """One line of the product table: a label and one or more values."""

    label_en: str
    label_fr: str
    values: list[str] = field(default_factory=list)
    # Full-width accent background (the coupon / offer line).
    highlight: bool = False
    # Values printed in the accent colour (underlyings, baskets).
    accent_values: bool = False
    bold: bool = False
    key: str = ""

    @property
    def is_empty(self) -> bool:
        return not any(v.strip() for v in self.values)

    def label(self, lang: str) -> str:
        return self.label_fr if lang == "fr" else self.label_en

    @classmethod
    def from_dict(cls, data: dict) -> "Row":
        raw = data.get("values", data.get("value", []))
        if isinstance(raw, str):
            values = [line for line in raw.splitlines()]
        elif raw is None:
            values = []
        else:
            values = [str(v) for v in raw]
        label_en = str(data.get("label_en", data.get("label", ""))).strip()
        return cls(
            label_en=label_en,
            label_fr=str(data.get("label_fr", "") or label_en).strip(),
            values=[v.strip() for v in values],
            highlight=bool(data.get("highlight")),
            accent_values=bool(data.get("accent_values")),
            bold=bool(data.get("bold")),
            key=str(data.get("key", "")),
        )


@dataclass
class Product:
    """The product being proposed, i.e. the contents of the table."""

    header_en: str = ""
    header_fr: str = ""
    rows: list[Row] = field(default_factory=list)
    accent: str = DEFAULT_ACCENT
    template: str = ""

    def header(self, lang: str) -> str:
        if lang == "fr":
            return self.header_fr or self.header_en
        return self.header_en or self.header_fr

    def visible_rows(self) -> list[Row]:
        """Rows with content -- this is what makes the table grow and shrink."""
        return [r for r in self.rows if not r.is_empty]

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(
            header_en=str(data.get("header_en", "")).strip(),
            header_fr=str(data.get("header_fr", "")).strip(),
            rows=[Row.from_dict(r) for r in data.get("rows", [])],
            accent=str(data.get("accent", DEFAULT_ACCENT)),
            template=str(data.get("template", "")),
        )


@dataclass
class Proposition:
    """Everything screen 1 and screen 2 collect, ready to render."""

    # Screen 1 -- email information
    accounts: list[Account] = field(default_factory=list)
    isin: str = ""
    description: str = ""
    situation: str = "autocalled"
    relevant_date: date | None = None
    # Overrides the situation's own wording when situation == "custom".
    custom_event_en: str = ""
    custom_event_fr: str = ""
    custom_date_label_en: str = ""
    custom_date_label_fr: str = ""
    status: str = ""
    notes_en: str = ""
    notes_fr: str = ""
    # Screen 2 -- product table
    product: Product = field(default_factory=Product)

    @classmethod
    def from_dict(cls, data: dict) -> "Proposition":
        return cls(
            accounts=[Account.from_dict(a) for a in data.get("accounts", [])],
            isin=str(data.get("isin", "")).strip().upper(),
            description=str(data.get("description", "")).strip(),
            situation=str(data.get("situation", "autocalled")),
            relevant_date=parse_date(data.get("relevant_date")),
            custom_event_en=str(data.get("custom_event_en", "")).strip(),
            custom_event_fr=str(data.get("custom_event_fr", "")).strip(),
            custom_date_label_en=str(data.get("custom_date_label_en", "")).strip(),
            custom_date_label_fr=str(data.get("custom_date_label_fr", "")).strip(),
            status=str(data.get("status", "")).strip(),
            notes_en=str(data.get("notes_en", "")).strip(),
            notes_fr=str(data.get("notes_fr", "")).strip(),
            product=Product.from_dict(data.get("product", {})),
        )


def _opt_float(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("'", "").replace(" ", "").replace(",", ".")
    if not text:
        return None
    return float(text)
