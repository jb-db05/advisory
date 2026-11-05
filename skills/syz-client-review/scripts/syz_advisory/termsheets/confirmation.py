"""Step 3: the trade confirmation email, as an Outlook draft (.eml) with the term sheet attached.

The table is filled from the term sheet; every value stays editable in the UI before the
draft is written. Wording and layout live in rules.json ("email"), so they can be changed
without touching the code.
"""

from __future__ import annotations

import re
from email.message import EmailMessage
from html import escape as _escape

from syz_advisory.termsheets.naming import load_rules

_DURATION = re.compile(r"^(\d+)([YM])$")


def escape(text: str) -> str:
    """& < > " only, so apostrophes stay readable (and match the browser version)."""
    return _escape(str(text), quote=False).replace('"', "&quot;")


def _maturity(duration: str) -> tuple[str, str]:
    """'18M' -> ('18-M', '18-Month'), '1Y' -> ('1-Y', '1-Year')."""
    m = _DURATION.match(duration or "")
    if not m:
        return duration or "", duration or ""
    unit = "Year" if m[2] == "Y" else "Month"
    return f"{m[1]}-{m[2]}", f"{m[1]}-{unit}"


def product_title(values: dict, rules: dict | None = None) -> str:
    """Headline of the email, e.g. '18-M Reverse Autocall with Low Strike'."""
    rules = rules or load_rules()
    short, _ = _maturity(values.get("duration", ""))
    code = (values.get("product_type") or "").upper()
    wording = rules["email"]["product_titles"].get(code, rules["email"]["product_titles"]["default"])
    return " ".join(part for part in (short, wording) if part).strip()


def email_values(ts, rules: dict | None = None) -> dict:
    """Everything the email needs, ready to be shown (and edited) in the UI."""
    rules = rules or load_rules()
    values = ts.values()
    short, long = _maturity(values.get("duration", ""))
    issuer = values.get("issuer", "")
    size = ts.size.value or values.get("currency", "")
    return {
        "greeting": rules["email"]["greeting"],
        "intro": rules["email"]["intro"].replace("{issuer}", issuer),
        "title": product_title(values, rules),
        "currency": f"{size} ({issuer} Issuer)" if issuer else size,
        "maturity": long,
        "underlyings": ts.underlying_names.value or values.get("underlyings", "").replace("-", "\n"),
        "strike": ts.strike.value,
        "frequency": ts.frequency.value,
        "coupon": f"{values.get('coupon', '')} p.a." if values.get("coupon") else "",
        "footer": "\n".join(part for part in ("Strike Close", ts.settlement.value or "Physical Delivery",
                                              rules["email"]["settlement_lag"]) if part),
        "subject": "",
    }


def render_html(values: dict, rules: dict | None = None) -> str:
    """The email body: title bar, details table, footer lines (see rules.json 'email')."""
    rules = rules or load_rules()
    style = rules["email"]["style"]
    rows = [(label, values.get(key, "")) for key, label in rules["email"]["rows"]]

    def cell(value: str, highlight: bool = False, accent: bool = False) -> str:
        lines = "<br>".join(escape(line) for line in str(value).splitlines() if line.strip())
        colour = f" color:{style['accent']};" if accent else ""
        background = f" background:{style['accent']}; color:#ffffff;" if highlight else ""
        return (f'<td style="padding:8px 12px; border-bottom:1px solid {style["border"]};{colour}{background}">'
                f'{lines}</td>')

    body = []
    for label, value in rows:
        accent = label == "Underlying"
        highlight = label.endswith("Coupon")
        body.append(f'<tr><td style="padding:8px 12px; border-bottom:1px solid {style["border"]}; width:180px;">'
                    f'{escape(label)}</td>{cell(value, highlight, accent)}</tr>')

    footer = "<br>".join(escape(line) for line in values.get("footer", "").splitlines() if line.strip())
    return f"""<div style="font-family:{style['font']}; font-size:14px; color:{style['text']};">
<p>{escape(values.get('greeting', ''))}</p>
<p>{escape(values.get('intro', ''))}</p>
<table style="border-collapse:collapse; width:100%; max-width:760px;">
<tr><td colspan="2" style="background:{style['title_background']}; color:{style['accent']}; font-size:18px;
 font-weight:bold; padding:12px;">{escape(values.get('title', ''))}</td></tr>
{chr(10).join(body)}
</table>
<p>{footer}</p>
</div>"""


def build_eml(values: dict, attachment: tuple[str, bytes] | None = None, rules: dict | None = None) -> bytes:
    """An Outlook draft: X-Unsent makes Outlook open it as a new message, ready to send."""
    rules = rules or load_rules()
    message = EmailMessage()
    message["Subject"] = values.get("subject", "")
    if to := values.get("to", ""):
        message["To"] = to
    message["X-Unsent"] = "1"
    text = "\n".join(part for part in (values.get("greeting", ""), values.get("intro", ""), values.get("title", ""),
                                       *(f"{label}: {values.get(key, '')}" for key, label in rules["email"]["rows"]),
                                       values.get("footer", "")) if part)
    message.set_content(text)
    message.add_alternative(render_html(values, rules), subtype="html")
    if attachment:
        filename, data = attachment
        message.add_attachment(data, maintype="application", subtype="pdf", filename=filename)
    return message.as_bytes()
