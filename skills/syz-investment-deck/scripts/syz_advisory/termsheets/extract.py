"""Extract the naming fields from structured product term sheet PDFs.

The extractors are label-driven and work on a whitespace-flattened copy of
the PDF text, so they cope with the main layouts seen in the reference set:

* "Label value" sheets (Goldman Sachs, SG, BNP, BofA/Merrill Lynch, EFG).
* Leonteq-platform sheets (BIL, TCM, Raiffeisen), where pypdf returns the
  value glued *before* the label ("14/09/2026Initial Fixing Date") and table
  cells glued together ("AIRFPEuronextParis").

Every field records where it came from and any warning, so the UI can show
what needs a human check.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date

from syz_advisory.termsheets.naming import (
    build_label, build_instructions, build_name, duration_label, format_coupon, format_date, format_level, load_rules,
)

# --------------------------------------------------------------------------- PDF text


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    # pypdf logs noisy font-encoding warnings that don't affect the text we need.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# --------------------------------------------------------------------------- data model


@dataclass
class Field:
    value: str = ""
    source: str = ""  # text snippet the value was read from
    warning: str = ""


@dataclass
class TermSheet:
    fixing_date: Field = field(default_factory=Field)
    final_fixing_date: Field = field(default_factory=Field)
    currency: Field = field(default_factory=Field)
    duration: Field = field(default_factory=Field)
    issuer: Field = field(default_factory=Field)
    product_type: Field = field(default_factory=Field)
    coupon: Field = field(default_factory=Field)  # the coupon slot of the name; special products fill it differently
    underlyings: Field = field(default_factory=Field)
    identifier: Field = field(default_factory=Field)
    # Used by the confirmation email (step 3), not by the file name.
    underlying_names: Field = field(default_factory=Field)
    strike: Field = field(default_factory=Field)
    frequency: Field = field(default_factory=Field)
    settlement: Field = field(default_factory=Field)
    size: Field = field(default_factory=Field)

    def values(self) -> dict[str, str]:
        return {key: f.value for key, f in self.__dict__.items()}

    @property
    def name(self) -> str:
        return build_name(self.values())

    @property
    def label(self) -> tuple[str, str]:
        return build_label(self.values())

    def to_dict(self) -> dict:
        label, label_note = self.label
        return {"fields": {key: asdict(f) for key, f in self.__dict__.items()}, "name": self.name,
                "label": label, "label_note": label_note, "instructions": build_instructions(label)}


# --------------------------------------------------------------------------- dates

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_RE = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
             r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)")
_ORD = r"(?:\s?(?:st|nd|rd|th))?"
_YEAR = r"(?:19|20)\d{2}"  # a plausible year, so glued table cells don't produce dates like "October20261"
DATE_RE = (
    rf"(?:(?<!\d)\d{{1,2}}[./]\d{{1,2}}[./]{_YEAR}"
    rf"|(?<!\d){_YEAR}-\d{{2}}-\d{{2}}"
    rf"|(?<!\d)\d{{1,2}}{_ORD}[ -]?{_MONTH_RE}\.?[ ,-]?{_YEAR}"
    rf"|{_MONTH_RE}\.? ?\d{{1,2}}{_ORD} ?,? ?{_YEAR})"
)


def parse_date(text: str) -> date | None:
    text = text.strip()
    try:
        if m := re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", text):
            return date(int(m[3]), int(m[2]), int(m[1]))
        if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := re.fullmatch(rf"(\d{{1,2}}){_ORD}[ -]?([A-Za-z]+)\.?[ ,-]?(\d{{4}})", text):
            return date(int(m[3]), _MONTHS[m[2][:3].lower()], int(m[1]))
        if m := re.fullmatch(rf"([A-Za-z]+)\.? ?(\d{{1,2}}){_ORD} ?,? ?(\d{{4}})", text):
            return date(int(m[3]), _MONTHS[m[1][:3].lower()], int(m[2]))
    except (KeyError, ValueError):
        return None
    return None


def _label(words: str) -> str:
    """'Initial Fixing Date' -> regex that also matches 'InitialFixingDate'."""
    return r"\s*".join(re.escape(w) for w in words.split())


def _snippet(flat: str, start: int, end: int, pad: int = 30) -> str:
    return flat[max(0, start - pad): end + pad].strip()


def find_labeled_date(flat: str, labels: list[str]) -> tuple[date, str] | None:
    """Return the first date attached to one of `labels` (checked in priority order).

    A date glued directly in front of the label (no space, optional
    parenthetical) is taken first: that is the Leonteq layout, where the value
    after the label belongs to the *next* row.
    """
    for label in labels:
        pattern = label if label.startswith("(?") or "\\" in label else _label(label)
        for m in re.finditer(pattern, flat, re.IGNORECASE):
            before = flat[max(0, m.start() - 90): m.start()]
            if (b := re.search(rf"({DATE_RE})(?:\s?\([^)]*\))?$", before, re.IGNORECASE)) and (d := parse_date(b[1])):
                return d, _snippet(flat, m.start() - len(b[0]), m.end(), 0)
            if (a := re.match(rf"\s*[:|]?\s*({DATE_RE})", flat[m.end(): m.end() + 45], re.IGNORECASE)) and (d := parse_date(a[1])):
                return d, _snippet(flat, m.start(), m.end() + a.end(), 0)
    return None


INITIAL_LABELS = [
    "Initial Fixing Date", "Initial Fixing", "Initial Valuation Date", "Strike Date",
    r"Valuation\s*Date\s*\(\s*0\s*\)", "Pricing Date", "Trade Date", "Launch Date",
]
FINAL_LABELS = [
    "Final Fixing Date", "Final Fixing", "Final Valuation Date", "Redemption Valuation Date",
    "Final Observation Date", r"Exercise\s*Date\s*\|\s*Valuation\s*Date", "Expiry Date", "Expiration Date",
    # Wrapped labels: "Redemption Valuation / Date", "Exercise Date | <value> / Valuation Date".
    "Redemption Valuation", r"Exercise\s*Date\s*\|",
]
MATURITY_LABELS = ["Redemption Date", "Maturity Date", "Repayment Date", "Settlement Date"]


def _dates(flat: str, ts: TermSheet) -> None:
    if found := find_labeled_date(flat, INITIAL_LABELS):
        ts.fixing_date = Field(format_date(found[0]), found[1])
        initial = found[0]
    else:
        initial = None
        ts.fixing_date.warning = "Initial fixing date not found"

    final = None
    # SG: "Valuation Date(12) 9 September 2027 (i.e. "last Valuation Date")"
    if m := re.search(rf"({DATE_RE})\s*\(i\.e\.\s*[\"“”]?last\s*Valuation\s*Date", flat, re.IGNORECASE):
        final = (parse_date(m[1]), m[0])
    if not (final and final[0]):
        final = find_labeled_date(flat, FINAL_LABELS)
    if not final and (final := find_labeled_date(flat, MATURITY_LABELS)):
        ts.final_fixing_date.warning = "No final fixing date found; used the redemption/maturity date"
    if final and final[0]:
        ts.final_fixing_date.value = final[0].strftime("%d/%m/%Y")
        ts.final_fixing_date.source = final[1]
    else:
        ts.final_fixing_date.warning = "Final fixing date not found"

    if initial and final and final[0]:
        ts.duration = Field(duration_label(initial, final[0]), f"{initial:%d/%m/%Y} → {final[0]:%d/%m/%Y}")
    if not ts.duration.value:
        ts.duration.warning = "Could not compute duration"


# --------------------------------------------------------------------------- currency


def _currency(flat: str, ts: TermSheet, rules: dict) -> None:
    iso = "|".join(rules["currencies"])
    code = rf"(?<![A-Z])({iso})(?![A-Z])"
    candidates = [
        (rf"issued\s*in\s*{code}", None),
        (rf"{code}\s*Settlement\s*Currency", None),  # Leonteq: value before label
        (_label("Settlement Currency"), 60),
        (_label("Specified Currency"), 60),
        (_label("Reference Currency"), 40),
        (_label("Product Currency"), 40),
        (_label("Issue Currency"), 40),
        (r"Denomination|Nominal(?:\s*Value|\s*Amount)?", 25),
        (r"(?<![A-Za-z])Currency", 25),
    ]
    for pattern, window in candidates:
        for m in re.finditer(pattern, flat, re.IGNORECASE if window else 0):
            if window is None:
                ts.currency = Field(m[1], _snippet(flat, m.start(), m.end(), 0))
                return
            # Value glued in front of the label: 'EURO("EUR")SpecifiedCurrency:'
            if b := re.search(code + r"[^A-Za-z0-9]{0,3}$", flat[max(0, m.start() - 12): m.start()]):
                ts.currency = Field(b[1], _snippet(flat, m.start() - 12, m.end(), 0))
                return
            if c := re.search(code, flat[m.end(): m.end() + window]):
                ts.currency = Field(c[1], _snippet(flat, m.start(), m.end() + c.end(), 0))
                return
    if c := re.search(code, flat[:400]):
        ts.currency = Field(c[1], _snippet(flat, c.start(), c.end()), "Guessed from the title")
    else:
        ts.currency.warning = "Currency not found"


# --------------------------------------------------------------------------- issuer


def _issuer(flat: str, ts: TermSheet, rules: dict) -> None:
    issuers = rules["issuers"]
    for rule in (r for r in issuers if r.get("priority")):
        for pattern in rule["patterns"]:
            if m := re.search(pattern, flat, re.IGNORECASE):
                ts.issuer = Field(rule["code"], _snippet(flat, m.start(), m.end()))
                return

    # Pick the known issuer whose mention sits closest to an "Issuer" label,
    # so lead managers / calculation agents (e.g. Vontobel on EFG paper) are ignored.
    best: tuple[int, str, str] | None = None
    # No leading \b: some sheets glue the value to the label ("...principal office in LondonIssuer:").
    labels = list(re.finditer(r"Issuer\b(?!['’]s|\s*Rating|\s*and\b|\s*or\b)", flat))
    for rule in issuers:
        for pattern in rule["patterns"]:
            for m in re.finditer(pattern, flat, re.IGNORECASE):
                for lab in labels:
                    distance = m.start() - lab.end() if m.start() >= lab.end() else lab.start() - m.end()
                    if 0 <= distance <= 300 and (best is None or distance < best[0]):
                        best = (distance, rule["code"], _snippet(flat, min(m.start(), lab.start()), max(m.end(), lab.end()), 10), lab)
    if best:
        ts.issuer = Field(best[1], best[2])
        # The Leonteq issuer text sits just before the label (pypdf) or just after it (pdf.js layout).
        if re.search(r"Leonteq", flat[max(0, best[3].start() - 200): best[3].end() + 40], re.IGNORECASE):
            ts.issuer.warning = "Issued by Leonteq; abbreviation taken from the guarantor. Please confirm"
        return

    counts = {r["code"]: sum(len(re.findall(p, flat, re.IGNORECASE)) for p in r["patterns"]) for r in issuers}
    code, hits = max(counts.items(), key=lambda kv: kv[1])
    if hits:
        ts.issuer = Field(code, "", "Issuer inferred from mentions in the document; please check")
    else:
        issuer_line = re.search(r"\bIssuer\b\s*:?\s*(.{0,80})", flat)
        ts.issuer = Field("", issuer_line[0] if issuer_line else "",
                          "Unknown issuer: enter the abbreviation and add it to rules.json")


# --------------------------------------------------------------------------- product type


def _product_type(flat: str, ts: TermSheet, rules: dict) -> None:
    """The code in the file name, from the first matching rule -- the order is the rule.

    See "_product_types_comment" in rules.json: the desk names a sheet after its
    early-redemption feature, so AC outranks the SSPA base payoff (45 of its
    witnesses are SSPA 1220, 5 are 1230 and 2 are 1260).
    """
    for rule in rules["product_types"]:
        for pattern in rule["patterns"]:
            if m := re.search(pattern, flat, re.IGNORECASE):
                warning = "" if rule.get("verified") else f"'{rule['code']}' is not confirmed by the reference examples"
                ts.product_type = Field(rule["code"], _snippet(flat, m.start(), m.end()), warning)
                _flag_issuer_call(flat, ts, rules)
                return
    ts.product_type.warning = "Product type not recognised"


def _flag_issuer_call(flat: str, ts: TermSheet, rules: dict) -> None:
    """Ask about a sheet the issuer may call but that has no autocall trigger.

    The desk has named the three in the reference set AC, BRC and RC, two of them
    the same structure, so the code is a genuine question rather than a rule.
    """
    call = rules.get("issuer_call") or {}
    if ts.product_type.value not in call.get("applies_to", ()):
        return
    for pattern in call["patterns"]:
        if m := re.search(pattern, flat, re.IGNORECASE):
            ts.product_type.warning = call["warning"]
            ts.product_type.source = _snippet(flat, m.start(), m.end())
            return


# --------------------------------------------------------------------------- coupon

_PCT = r"(\d{1,2}(?:[.,]\d{1,6})?)\s*%"
_PA = r"\s*(?:p\.?\s*a\.?(?![a-z])|per\s*annum)"  # "p.a." / "per annum", but not "% payable"
_FREQ = {"monthly": 12, "per month": 12, "quarterly": 4, "per quarter": 4, "semi-annual": 2, "semi annual": 2,
         "semiannual": 2, "half-yearly": 2, "per semester": 2, "annual": 1, "yearly": 1}


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def _months(duration: str) -> int | None:
    if m := re.fullmatch(r"(\d+)([YM])", duration or ""):
        return int(m[1]) * (12 if m[2] == "Y" else 1)
    return None


def _coupon(flat: str, ts: TermSheet) -> None:
    # 1. Headline "9.50% p.a. Multi Reverse Convertible ..." at the top of the sheet.
    if m := re.search(_PCT + _PA, flat[:400], re.IGNORECASE):
        ts.coupon = Field(format_coupon(_num(m[1])), _snippet(flat, m.start(), m.end()))
        _cross_check(flat, ts, _num(m[1]))
        return
    # 2. "Coupon (Rate) 11.3100% p.a.", "Rate of Interest 12.56% per annum"
    if m := re.search(r"(?:Coupon(?:\s*Rate)?|Rate\s*of\s*Interest|Interest\s*Rate)\s*:?\s*" + _PCT + _PA, flat, re.IGNORECASE):
        ts.coupon = Field(format_coupon(_num(m[1])), _snippet(flat, m.start(), m.end()))
        _cross_check(flat, ts, _num(m[1]))
        return
    # 2b. Contingent coupon quoted with its annual equivalent (Citi: "2.825% per quarter (corresponding to
    #     approximately 11.30% per annum)"). Named after the contingent coupon, not the minimum coupon.
    for m in re.finditer(r"(?:Contingent|Conditional)\s*Coupon(?:\s*Amount)?", flat, re.IGNORECASE):
        if a := re.search(_PCT + _PA, flat[m.end(): m.end() + 250], re.IGNORECASE):
            ts.coupon = Field(format_coupon(_num(a[1])), _snippet(flat, m.start(), m.end() + a.end(), 0),
                              "Contingent coupon: the sheet may also quote a lower minimum coupon, please check")
            return
    # 3. Swiss tax split: "4.03% p.a. interest payment" + "9.87% p.a. option premium".
    interest = re.search(_PCT + _PA + r"\s*(?:\(?\s*)?interest", flat, re.IGNORECASE)
    premium = re.search(_PCT + _PA + r"\s*(?:\(?\s*)?option\s*premium", flat, re.IGNORECASE)
    if interest and premium:
        total = round(_num(interest[1]) + _num(premium[1]), 4)
        ts.coupon = Field(format_coupon(total), f"{interest[0]} + {premium[0]}")
        if not _confirmed_by_sheet(flat, total):
            ts.coupon.warning = ("Added up from the tax split (interest + option premium); "
                                 "no annual rate stated on the sheet, please check")
        return
    # 4. Per-period coupons (conditional/Express "3.625%" quarterly, fixed "Rate of Interest 0.8334%" monthly, ...)
    #    are annualised by simple multiplication with the number of coupon periods per year.
    if m := re.search(r"Conditional\s*Coupon(?:\s*Amount)?\s*:?\s*" + _PCT, flat, re.IGNORECASE) or \
            re.search(_PCT + r"\s*Conditional\s*Coupon", flat, re.IGNORECASE):
        _annualise(flat, ts, m[1], m.end(), _snippet(flat, m.start(), m.end(), 0))
        return
    for label in (r"Rate\s*of\s*Interest", r"Interest\s*Rate", r"Interest\s*Amount", r"Coupon\s*Rate", r"Fixed\s*Coupon",
                  r"Coupon(?!\s*(?:Trigger|Observation|Payment|Period))"):
        for m in re.finditer(label, flat, re.IGNORECASE):
            window = flat[m.end(): m.end() + 220]
            rate = re.search(_PCT + r"(?!" + _PA + ")", window)
            if rate:
                _annualise(flat, ts, rate[1], m.end(), _snippet(flat, m.start(), m.end() + rate.end(), 0))
                return
    ts.coupon.warning = "Coupon not found"


_COMPONENT_CONTEXT = r"interest\s*(?:payment|component|rate\s*of)|option\s*premium|component|bondfloor|implied\s*yield|taxable"


def _annual_rates(flat: str) -> list[float]:
    """Annual rates stated on the sheet ("12.56% p.a.", "annualized ... 8.004%"), tax components aside."""
    rates = []
    # Explicitly annual wording: taken as stated.
    for pattern in (r"annuali[sz]ed[^%]{0,60}?" + _PCT, r"equivalent\s*to[^%]{0,40}?" + _PCT):
        rates += [_num(m[1]) for m in re.finditer(pattern, flat, re.IGNORECASE)]
    # Plain "x% p.a.": skip the Swiss tax split components ("3.36% p.a. interest payment").
    for m in re.finditer(_PCT + _PA, flat, re.IGNORECASE):
        if not re.search(_COMPONENT_CONTEXT, flat[max(0, m.start() - 40): m.end() + 40], re.IGNORECASE):
            rates.append(_num(m[1]))
    return rates


def _confirmed_by_sheet(flat: str, value: float) -> bool:
    return any(abs(rate - value) <= 0.05 for rate in _annual_rates(flat))


def _cross_check(flat: str, ts: TermSheet, value: float) -> None:
    """Flag when the sheet states another annual rate as well (minimum vs conditional coupon, ...)."""
    others = sorted({rate for rate in _annual_rates(flat) if abs(rate - value) > 0.05})
    if others:
        shown = ", ".join(format_coupon(rate) for rate in others[:3])
        ts.coupon.warning = f"The sheet also states {shown} p.a.; please check which coupon applies"


def _annualise(flat: str, ts: TermSheet, rate: str, pos: int, source: str) -> None:
    per_year, how = _payments_per_year(flat, pos, ts.duration.value)
    if per_year:
        # Periodic rates are rounded (10% p.a. monthly -> 0.8334%), so round the annual rate back to 2 decimals
        # unless the sheet's own precision needs more (3.625% x 1).
        annual = _num(rate) * per_year
        annual = round(annual, 2) if abs(annual - round(annual, 2)) < 0.005 else round(annual, 4)
        ts.coupon = Field(format_coupon(annual), f"{source} × {per_year} per year ({how})")
        if _confirmed_by_sheet(flat, annual):
            ts.coupon.source += ", confirmed by the sheet"
        else:
            ts.coupon.warning = (f"Calculated: {rate}% × {per_year} ({how}). The sheet states no annual rate, "
                                 "please check the frequency")
    else:
        ts.coupon = Field(format_coupon(_num(rate)), source,
                          "Coupon payment frequency not found: rate is per period, please annualise")


_SCHEDULE_LABELS = (
    r"(?:Coupon|Interest|Additional\s*Amount)\s*Payment\s*Date",
    r"(?:Coupon|Interest)\s*Observation\s*Date",
    r"paid\s*on",  # "EUR 6.00 paid on 21/10/2026 EUR 6.00 paid on 23/11/2026 …"
)
_PERIOD_MONTHS = (1, 2, 3, 4, 6, 12)


def _schedule_period(flat: str) -> int | None:
    """Coupon period in months from the spacing of the dates in the coupon schedule."""
    for label in _SCHEDULE_LABELS:
        for m in re.finditer(label, flat, re.IGNORECASE):
            window = flat[m.end(): m.end() + 1500]
            dates = sorted({d for s in re.findall(DATE_RE, window, re.IGNORECASE) if (d := parse_date(s))})
            # Rows often pair an observation date with a payment date a few days later: ignore those gaps.
            gaps = sorted((b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days >= 20)
            if len(gaps) >= 2:
                median = gaps[len(gaps) // 2]
                return min(_PERIOD_MONTHS, key=lambda p: abs(p * 30.44 - median))
    return None


_IN_FINE_WORDING = (
    r"Coupon\s*is\s*paid\s*out\s*at\s*(?:the\s*)?(?:Repayment|Redemption|Maturity)\s*Date",
    r"\bin\s*fine\b",
    r"Coupon\s*(?:is\s*)?(?:payable|paid)\s*(?:only\s*)?at\s*(?:the\s*)?maturity",
)


def _in_fine(flat: str) -> str | None:
    """One single coupon, paid when the product is repaid; None if not certain.

    Worth its own answer rather than a blank frequency. The portfolio deck spreads
    the annual rate over the payment frequency, so an in-fine coupon that falls
    through to the quarterly default is shown as four payments instead of one --
    the right annual total, but every individual coupon amount and date wrong.
    """
    for pattern in _IN_FINE_WORDING:
        if m := re.search(pattern, flat, re.IGNORECASE):
            return _snippet(flat, m.start(), m.end(), 0)
    # Otherwise only on the evidence of the schedule itself: the most dates found
    # near any coupon-schedule label has to be exactly one. A single label whose
    # window happens to hold one date proves nothing, since the labels recur in
    # the definitions; the maximum over all of them does.
    most = 0
    for label in _SCHEDULE_LABELS[:2]:  # not "paid on", which repeats once per row
        for m in re.finditer(label, flat, re.IGNORECASE):
            window = flat[m.end(): m.end() + 1200]
            most = max(most, len({d for s in re.findall(DATE_RE, window, re.IGNORECASE) if (d := parse_date(s))}))
    return "one coupon payment date in the schedule" if most == 1 else None


def _payments_per_year(flat: str, pos: int, duration: str) -> tuple[int | None, str]:
    near = flat[pos: pos + 400].lower()
    for word, n in _FREQ.items():
        if re.search(rf"\b{word}(?:ly)?\b", near):
            return n, word
    if period := _schedule_period(flat):
        return 12 // period, f"coupon dates every {period}M"
    months = _months(duration)
    if not months:
        return None, ""
    # "Interest Payment Date(s) 19 October 2026, 17 November 2026, ... and the Maturity Date"
    if m := re.search(r"(?:Interest|Coupon)\s*Payment\s*Date\(?s?\)?(.{0,900}?)(?=[A-Z][a-z]+\s+[A-Z][a-z]+\s+Convention|$)", flat):
        count = len(re.findall(DATE_RE, m[1], re.IGNORECASE))
        if re.search(r"and\s+(?:on\s+)?the\s+(?:Maturity|Redemption)\s+Date", m[1], re.IGNORECASE):
            count += 1
        if count > 1:
            return round(count * 12 / months), f"{count} payment dates over {months}M"
    return None, ""


# --------------------------------------------------------------------------- structure (BTB / CPN)


def _index_in(window: str, rules: dict) -> tuple[str, int] | None:
    """First index named or coded in `window` -> (ticker, position)."""
    hits = []
    for index in rules["indices"]:
        for pattern in index["patterns"]:
            if m := re.search(pattern, window, re.IGNORECASE):
                hits.append((m.start(), index["ticker"]))
    if m := re.search(r"(?<![A-Za-z0-9])([A-Z0-9]{2,8})\s+<?Index\b", window):
        hits.append((m.start(), m[1]))
    return (min(hits)[1], min(hits)[0]) if hits else None


def _benchmark(flat: str, rules: dict) -> tuple[str, str] | None:
    """BTB benchmark index -> (ticker, source snippet)."""
    for m in re.finditer(r"BENCHMARK\s*UNDERLYING|Name\s*of\s*the\s*Benchmark|The\s*Benchmark\b|Benchmark\s*Underlying", flat):
        if hit := _index_in(flat[m.end(): m.end() + 400], rules):
            return hit[0], _snippet(flat, m.start(), m.end() + hit[1] + 20, 0)
    return None


_LEVEL_PCT = r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,4})?)\s*%"  # up to 3 integer digits: "122.00%"


def _level(flat: str, value_first: str, label_first: str) -> tuple[float, str] | None:
    """Percentage attached to a label, either glued before it (Leonteq) or after it."""
    if m := re.search(_LEVEL_PCT + r"\s*" + value_first, flat, re.IGNORECASE):
        return _num(m[1]), _snippet(flat, m.start(), m.end(), 0)
    if m := re.search(label_first + r"\s*:?\s*\(?\s*(?:of\s*)?" + _LEVEL_PCT, flat, re.IGNORECASE):
        return _num(m[1]), _snippet(flat, m.start(), m.end(), 0)
    return None


def _capital_protection_coupon(flat: str, ts: TermSheet) -> None:
    """CPN coupon slot: 'CAP% - PROTECTION% KG -' (e.g. '122% - 90% KG -')."""
    notes, sources = ["Capital protection: coupon line is 'cap - protection KG', please check"], []
    protection = _level(flat, r"Capital\s*(?:Protection|Guarantee)(?!\s*Products)", r"Capital\s*(?:Protection|Guarantee)(?:\s*Level)?")
    cap = _level(flat, r"Cap(?![a-z])", r"Cap(?:\s*Level)?(?![a-z])")
    if not cap and (cap := _level(flat, r"Participation", r"Participation(?:\s*Rate)?")):
        notes.append("no cap found, participation used")
    if not protection:
        notes.append("capital protection level not found")
    parts = []
    if cap:
        parts.append(format_level(cap[0]))
        sources.append(cap[1])
    if protection:
        parts.append(f"{format_level(protection[0])} KG")
        sources.append(protection[1])
    # Trailing " -" separates the slot from the underlyings: "CPN 122% - 90% KG - GDXJ".
    value = " - ".join(parts) + " -" if parts else ""
    ts.coupon = Field(value, " | ".join(sources), "; ".join(notes))


# --------------------------------------------------------------------------- underlyings


# The underlyings section heading, on a line of its own. Issuers word it
# differently and an unrecognised heading drops the whole glued-row layout.
_UNDERLYING_HEADING = re.compile(
    r"\s*(?:UNDERLYINGS?|Underlyings?"
    r"|UNDERLYING\(S\)|Underlying\(s\)"
    r"|UNDERLYING\s+SHARES?|Underlying\s+Shares?"
    r"|REFERENCE\s+ITEMS?|Reference\s+Items?"
    r"|BASISWERTE?|Basiswerte?)\s*"
)


def _underlyings(text: str, flat: str, ts: TermSheet, rules: dict, benchmark: str = "") -> None:
    codes = "|".join(sorted(rules["exchange_codes"], key=len, reverse=True))
    index_tickers = {i["ticker"] for i in rules["indices"]}
    # A BTB benchmark goes in the coupon slot, never in the underlyings.
    found: list[tuple[int, str]] = []

    def add(pos: int, ticker: str) -> None:
        if ticker != benchmark:
            found.append((pos, ticker))

    # 1. Explicit Bloomberg codes: "SMCI UW Equity", "<KTOS UW Equity>", "NOC UN <Equity>",
    #    "AVGO UW <EQUITY>" (Julius Baer shouts it), "APHUNEQUITY", "SX5E Index".
    #    Only the keyword is case-insensitive; the ticker itself stays upper-case.
    for m in re.finditer(rf"(?<![A-Za-z0-9])([A-Z0-9][A-Z0-9./]{{0,11}})\s+(?:{codes})\s*<?\s*(?:Equity|EQUITY)\b", flat):
        add(m.start(), m[1])
    for m in re.finditer(rf"(?<![A-Za-z0-9])([A-Z0-9]{{1,10}}?)(?:{codes})EQUITY(?![A-Z])", flat):
        add(m.start(), m[1])
    for m in re.finditer(r"(?<![A-Za-z0-9])([A-Z0-9]{2,8})\s+<?Index>?", flat):
        if m[1] in index_tickers:
            add(m.start(), m[1])

    # 2. "Bloomberg Ticker" tables with separate cells: "Palo Alto Networks Inc PANW UW Nasdaq", "ABBN SE SIX Swiss".
    #    The exchange must be followed by a letter, not a digit: on Raiffeisen sheets
    #    "SCHNEIDER ELECTRIC SE 285.7500EUR" otherwise reads as ticker ELECTRIC on
    #    exchange SE, because a company name can end in an exchange code.
    if not found:
        for b in re.finditer(r"Bloomberg", flat):
            section = flat[b.end(): b.end() + 1500]
            for m in re.finditer(rf"(?<![A-Za-z0-9])([A-Z0-9]{{1,10}})\s+(?:{codes})\s+(?=[A-Z])", section):
                add(b.end() + m.start(), m[1])
            if found:
                break

    # 3. Leonteq glued rows: "TBA**6370JTTokyoStock", "MLIUNNYSEMUELLER...", "SX5ESTOXXLimited".
    if not found:
        lines = text.splitlines()
        start = next((i for i, l in enumerate(lines) if _UNDERLYING_HEADING.fullmatch(l)), None)
        if start is not None:
            for i, line in enumerate(lines[start + 1:], start + 1):
                if re.search(r"PRODUCT\s*DETAILS|Product\s*Details|levels\s*are\s*expressed", line, re.IGNORECASE):
                    break
                row = re.sub(r"^\s*TBA\*\*", "", line)
                if m := re.match(r"(" + "|".join(sorted(index_tickers, key=len, reverse=True)) + r")(?=[A-Z][a-z]|[A-Z]{2,}[a-z]|\s|S&P|STOXX|NASDAQ|Nikkei|Frank)", row):
                    add(i, m[1])
                # Raiffeisen leaves a space before the exchange code that Leonteq glues:
                # "TBA**APH UNNYSEAMPHENOL CORP A ..." against "MLIUNNYSEMUELLER...".
                elif m := re.match(rf"([A-Z0-9]+?)\s?(?:{codes})(?=NASDAQ|NYSE|SIX|Xetra|Euronext|Tokyo|Australian|London|Borsa|Hong|Toronto|Deutsche|Nasdaq|Bolsa|Madrid|Oslo|Stockholm|Copenhagen|Helsinki|Vienna|Wiener|Korea|Taiwan|Singapore|Shanghai|Shenzhen|National|Johannesburg|Cboe|[A-Z][a-z])", row):
                    add(i, m[1])

    # 4. A ticker column that does not carry the "Equity" keyword, as Swiss sheets
    #    often print it: "Nestle SA NESN SW CH0038863350 85.42". Deliberately
    #    narrow, because "TICKER EXCH" on its own is a weak signal: it is read only
    #    from the rows of a table whose heading mentions Bloomberg, a ticker or a
    #    symbol, only one ticker per row, and only from rows that also carry a
    #    number, so a line of prose in capitals cannot match. It runs last among
    #    the ticker strategies, so it cannot displace any layout above.
    if not found:
        lines = text.splitlines()
        heading = next((i for i, l in enumerate(lines)
                        if re.search(r"Bloomberg|\bTicker\b|\bSymbol\b", l, re.IGNORECASE)), None)
        if heading is not None:
            for i, line in enumerate(lines[heading: heading + 25], heading):
                if not re.search(r"\d", line):
                    continue
                if m := re.search(rf"(?<![A-Za-z0-9])([A-Z][A-Z0-9]{{1,9}})\s+(?:{codes})(?![A-Za-z0-9])", line):
                    add(i, m[1])

    # 5. Index names without a code (fallback, title area only).
    if not found:
        head = flat[:600]
        for idx in rules["indices"]:
            for pattern in idx["patterns"]:
                if m := re.search(pattern, head, re.IGNORECASE):
                    add(m.start(), idx["ticker"])
                    break

    tickers: list[str] = []
    for _, ticker in sorted(found, key=lambda t: t[0]):
        if ticker not in tickers:
            tickers.append(ticker)
    if tickers:
        ts.underlyings = Field(rules["underlying_separator"].join(tickers), ", ".join(tickers))
        if len(tickers) > 6:
            ts.underlyings.warning = "Unusually many underlyings detected; please check"
    else:
        ts.underlyings.warning = "Underlyings not found"


# --------------------------------------------------------------------------- confirmation email details

_FREQUENCY_NAMES = {12: "Monthly", 4: "Quarterly", 3: "Every 4 months", 2: "Semi-annual", 1: "Annual"}
# "… Reverse Convertible on Airbus, Siemens, STMicroelectronics", "… linked to a Basket of Indices",
# "… Notes Based Upon the Worst Performing of ABB Ltd, Galderma Group AG and UBS Group AG"
_TITLE_UNDERLYINGS = (r"Worst\s*Performing\s*of\s+(.{5,150})", r"\bon\s+(.{5,150})", r"linked\s*to\s+(.{5,150})")
# Where the product title ends and the boilerplate starts.
_TITLE_END = (r"Product\s*Type|Document\s*Type|SSPA|Final\s*Terms|Summary\s*of\s*Terms|This\s+(?:document|Term)"
              r"|Autocallable|Multi\s*Barrier|Capital\s*Protection|\(|\bin\s+[A-Z]{3}\b|Note\s*linked|\d{1,3}[.,]\d{2}\s*%")
# Title lines worth reading: they name the product.
_TITLE_LINE = r"Reverse\s*Convertible|Autocall|Certificate|Note|Phoenix|Express|Barrier|Capital\s*Protection|Worst[-\s]*Of"
# "linked to Shares", "on a Basket of Indices": no real names, fall back to the tickers.
_GENERIC_NAME = re.compile(r"^(?:a\s+)?(?:basket\s*of\s*)?(?:shares?|indices|index|equities|underlyings?|"
                           r"reference\s*(?:items?|assets?)|securities)$", re.IGNORECASE)
# Sentence fragments picked up from disclaimers ("… Notes on behalf of the Issuer …").
_NOT_A_NAME = re.compile(r"^(?:the|of|behalf|any|such|its|their|a|an|this|these|which|whose|each)\b", re.IGNORECASE)
# Fragments that belong to the previous name rather than being a name of their own.
_COMPANY_SUFFIX = re.compile(r"^(?:Inc|Inc\.|Ltd|Ltd\.|AG|SA|S\.A\.|NV|N\.V\.|PLC|plc|Corp|Corp\.|SE|LLC|ADR|CL\s*A|Class\s*A|"
                             r"-\s*CL\s*A|REG|the\s*Notes)\.?$", re.IGNORECASE)


def _underlying_names(text: str) -> tuple[list[str], str] | None:
    """Full company / index names from the product title ("… on Airbus, Siemens, STMicroelectronics")."""
    lines = text.splitlines()[:40]
    for i, line in enumerate(lines):
        if not re.search(_TITLE_LINE, line, re.IGNORECASE):
            continue
        candidate = re.sub(r"\s+", " ", " ".join(lines[i: i + 3])).strip()  # titles wrap over 2-3 lines
        for pattern in _TITLE_UNDERLYINGS:
            if not (m := re.search(pattern, candidate, re.IGNORECASE)):
                continue
            title = re.split(_TITLE_END, m[1], maxsplit=1, flags=re.IGNORECASE)[0]
            names: list[str] = []
            for part in re.split(r",|\band\b", title.replace("®", "")):
                part = part.strip(" .;:-")
                if not part:
                    continue
                # Some extractions glue the words together ("NASDAQ-100Index", "Russell2000").
                part = re.sub(r"(?<=\d)(?=[A-Z])", " ", re.sub(r"(?<=[a-z])(?=\d{3,})", " ", part))
                if names and _COMPANY_SUFFIX.match(part):  # "Super Micro Computer, Inc."
                    names[-1] += f", {part}"
                else:
                    names.append(part)
            if names and not any(_GENERIC_NAME.match(n) or _NOT_A_NAME.match(n) or len(n.split()) > 8 for n in names):
                return names, m[0].strip()[:120]
    return None


# Strike level, as each issuer's layout states it. Each pattern has to tie the
# percentage to the word "Strike" through wording that cannot also introduce the
# barrier, the autocall trigger or the initial level -- in a wide table those
# columns drift apart and become indistinguishable, and a wrong strike is worse
# than a flagged blank one. The layouts, in the order they are tried:
#
#   Leonteq, RAF, BIL   "Strike Level 60.00%", "Strike (Level) : 60%"
#   SG                  "Strike(k) (k from 1 to 3) 66.39% x S(0,k)"
#   Citi                "Strike Level For each Underlying, 75.00% of its ... Initial Level"
#   EFG, Julius Baer    "Strike Price USD 23.37 (50.00%*)", "Strike USD 222.2772 (65.47%)"
#   BNP                 "Strike Price Chevron Corp - 163.3275 (75% of Share1Initial)"
#
# Goldman Sachs ("Strike 1 Trigger 1 ... 50% 100%") and J.P. Morgan
# ("SPX Index 7,585.73 7,585.73 100.00% 4,551.44 60.00%") state the level only in
# a wide table whose header has drifted away from its values; those stay flagged.
_STRIKE_PATTERNS = (
    r"Strike\s*(?:Level|Price)?\s*(?:\([^)]{0,6}\))?\s*[:(]?\s*" + _LEVEL_PCT,
    r"Strike\s*\(\s*k\s*\)[^%]{0,40}?" + _LEVEL_PCT + r"\s*x",
    r"Strike\s*Level\s*For\s*each\s*Underlying\s*,?\s*" + _LEVEL_PCT,
    r"Strike\s*(?:Level|Price)?\s*[A-Z]{3}\s*[\d'’,.]+\s*\(\s*" + _LEVEL_PCT,
    r"Strike\s*Price\b[^%]{0,60}?\(\s*" + _LEVEL_PCT + r"\s*of\b",
)


def _strike(flat: str) -> tuple[float, str] | None:
    """The strike as a percentage of the initial level, or None to ask the user."""
    for pattern in _STRIKE_PATTERNS:
        for m in re.finditer(pattern, flat, re.IGNORECASE):
            value = _num(m[1])
            # A strike is a share of the initial level: a few points either side of
            # par at most. Anything else is a coupon, a tax rate or a ratio.
            if 20 <= value <= 150:
                return value, _snippet(flat, m.start(), m.end(), 0)
    return None


def _email_details(text: str, flat: str, ts: TermSheet) -> None:
    """Extra values for the confirmation email: full underlying names, strike, frequency, settlement, size."""
    if found := _underlying_names(text):
        ts.underlying_names = Field("\n".join(found[0]), found[1])
    if not ts.underlying_names.value:
        ts.underlying_names = Field(ts.underlyings.value.replace("-", "\n"),
                                    "", "Full names not found in the title; tickers used, please check")

    if found := _strike(flat):
        ts.strike = Field(format_level(found[0]), found[1])
    else:
        # In a wide table the columns drift apart and the neighbouring levels (barrier, autocall
        # trigger, initial) are indistinguishable, so rather than guess, ask.
        ts.strike.warning = "Strike level not found; please enter it"

    period = _schedule_period(flat)
    per_year = 12 // period if period else None
    # The gap between dates in the schedule is not always a standard frequency: the
    # Citi sheet's dates average two months apart (-> 6 a year) while its coupon is
    # stated "per quarter". Fall back to the wording instead of dropping the field.
    if per_year not in _FREQUENCY_NAMES:
        per_year = None
    if per_year is None:
        for word, n in _FREQ.items():
            if re.search(rf"\b{word}(?:ly)?\b", flat, re.IGNORECASE):
                per_year = n
                break
    if per_year in _FREQUENCY_NAMES:
        ts.frequency = Field(_FREQUENCY_NAMES[per_year], f"{per_year} coupon payment(s) per year")
    elif source := _in_fine(flat):
        ts.frequency = Field("In fine", source, "Single coupon at maturity; please confirm")
    else:
        ts.frequency.warning = "Coupon frequency not found"

    physical = re.search(r"Physical\s*(?:Delivery|Settlement)|Delivery\s*of\s*(?:the\s*)?Underlying|number\s*of\s*shares", flat, re.IGNORECASE)
    cash = re.search(r"Cash\s*Settlement", flat, re.IGNORECASE)
    ts.settlement = Field("Physical Delivery" if physical else ("Cash Settlement" if cash else ""))
    if not ts.settlement.value:
        ts.settlement.warning = "Settlement type not found"

    size_label = r"Issue\s*Size|Aggregate\s*Nominal(?:\s*Amount)?|Issue\s*Amount|Total\s*Size"
    amount = r"([A-Z]{3})\s*([\d'’,.]{3,20}\d)"
    # The amount usually follows the label, sometimes with other cells in between; on Leonteq sheets it is
    # glued in front of it ("EUR10’000’000(can be increased…)Issue Size").
    for label in re.finditer(size_label, flat, re.IGNORECASE):
        # Glued in front of the label (Leonteq) wins; otherwise the value follows the label.
        before = re.search(amount + r"\s*(?:\([^)]*\))?\s*$", flat[max(0, label.start() - 120): label.start()])
        after = re.search(amount, flat[label.end(): label.end() + 150])
        if found := (before or after):
            ts.size = Field(f"{found[1]} {found[2].strip()}", _snippet(flat, label.start(), label.end(), 0),
                            "Issue size of the whole product, not the amount traded; please correct")
            return
    ts.size.warning = "Issue size not found; please enter the traded amount"


# --------------------------------------------------------------------------- identifier

# The code may be glued to the label that follows it ("XS3464686297ISIN:", "CH1601887461ISIN").
_ISIN_RE = (r"(?<![A-Z0-9])([A-Z]{2}[A-Z0-9]{9}\d)"
            r"(?:(?![A-Z0-9])|(?=ISIN|Valor|Swiss|Common|Symbol|Security))")


def isin_is_valid(isin: str) -> bool:
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", isin):
        return False
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            n = n - 9 if n > 9 else n
        total += n
    return (10 - total % 10) % 10 == int(isin[-1])


# Labels that introduce the product's own codes, as opposed to an underlying's.
_PRODUCT_CODE_LABELS = (r"ISIN(?:\s*Code)?", r"Security\s*Numbers?", r"Instrument\s*Codes?", r"Valor(?:en)?",
                        r"Swiss\s*Security\s*Number", r"Common\s*Code", r"Symbol")
# Wording that marks the surroundings as an underlying / reference asset description.
_UNDERLYING_CONTEXT = r"Bloomberg|Underlying|Reference\s*(?:Item|Asset)|Related\s*Exchange|<?Equity>?|Index\s*Sponsor|Share\b"


def _identifier(flat: str, ts: TermSheet) -> None:
    """Pick the product's own ISIN, never an underlying's, and say how sure we are."""
    occurrences = [(m.start(), m[1]) for m in re.finditer(_ISIN_RE, flat) if isin_is_valid(m[1])]
    if not occurrences:
        ts.identifier.warning = "ISIN not found"
        return

    tickers = [t for t in ts.underlyings.value.split("-") if t]
    counts: dict[str, int] = {}
    for _, isin in occurrences:
        counts[isin] = counts.get(isin, 0) + 1

    scores: dict[str, int] = {}
    best_at: dict[str, int] = {}
    for start, isin in occurrences:
        before, after = flat[max(0, start - 90): start], flat[start + 12: start + 90]
        score = 0
        if re.search(rf"(?:{'|'.join(_PRODUCT_CODE_LABELS)})\s*[:.\-]?\s*$", before, re.IGNORECASE):
            score += 3  # "ISIN: XS…", "Instrument Codes: ISIN: XS…"
        if re.search(rf"^\s*[:.\-]?\s*(?:{'|'.join(_PRODUCT_CODE_LABELS)})", after, re.IGNORECASE):
            score += 3  # Leonteq layout: "CH1601887461ISIN"
        if re.search(_UNDERLYING_CONTEXT, before + after, re.IGNORECASE) or \
                any(re.search(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", before + after) for t in tickers):
            score -= 5  # "MSFT UW Equity; ISIN: US5949181045"
        if start < 1500:
            score += 1  # term sheet header
        if counts[isin] > 1:
            score += 2  # repeated: header + body
        if score > scores.get(isin, -99):
            scores[isin], best_at[isin] = score, start
    best = max(scores, key=lambda i: (scores[i], -best_at[i]))
    runner_up = sorted((s for i, s in scores.items() if i != best), reverse=True)

    warning = ""
    if scores[best] <= 0:
        warning = "No ISIN clearly identified as the product's; please check"
    elif runner_up and runner_up[0] >= scores[best]:
        others = ", ".join(i for i in scores if i != best and scores[i] >= scores[best])
        warning = f"Several possible product ISINs ({others}); please check"
    ts.identifier = Field(best, _snippet(flat, best_at[best], best_at[best] + 12), warning)


# --------------------------------------------------------------------------- entry point


def extract_fields(text: str, rules: dict | None = None) -> TermSheet:
    rules = rules or load_rules()
    flat = re.sub(r"\s+", " ", text)
    ts = TermSheet()
    _dates(flat, ts)
    _currency(flat, ts, rules)
    _issuer(flat, ts, rules)
    _product_type(flat, ts, rules)
    rule = next((r for r in rules["product_types"] if r["code"] == ts.product_type.value), {})
    benchmark = ""
    if rule.get("coupon_style") == "capital_protection":
        _capital_protection_coupon(flat, ts)
    else:
        _coupon(flat, ts)
    if rule.get("coupon_style") == "benchmark":
        found = _benchmark(flat, rules)
        benchmark = found[0] if found else ""
        ts.coupon.value = f"{benchmark} {ts.coupon.value}".strip()
        ts.coupon.source = " | ".join(s for s in ((found[1] if found else ""), ts.coupon.source) if s)
        _flag(ts.coupon, "Beat the Benchmark: coupon line is 'benchmark coupon', please check"
              + ("" if found else " (benchmark not found)"))
    if note := rule.get("coupon_note"):
        _flag(ts.coupon, note)
    _underlyings(text, flat, ts, rules, benchmark)
    _identifier(flat, ts)
    _email_details(text, flat, ts)
    return ts


def _flag(f: Field, warning: str) -> None:
    f.warning = f"{warning}; {f.warning}" if f.warning else warning
