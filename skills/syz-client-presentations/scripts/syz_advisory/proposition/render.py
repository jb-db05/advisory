"""Render the product table and the ready-to-send email, in EN and FR.

Everything is inline-styled and table-based so that it survives a paste into
Outlook. Sizes are kept in points to match the Payoff.xlsx reference exactly
(labels 12pt, highlighted coupon line 14pt, header 18pt).
"""

from __future__ import annotations

from html import escape

from syz_advisory import brand

from . import sentences
from .models import Proposition, Row, accent_hex, format_date

# House style, from syz_advisory.brand: Nunito, ink #202945, flat colour only.
FONT = brand.FONT_STACK
TEXT = brand.INK
LABEL_TEXT = brand.INK
HEADER_BG = brand.INK
# #202945 at 40%, pre-flattened: mail clients cannot be trusted with alpha,
# and the house rule is flat solid colour anyway.
HAIRLINE = brand.RULE_FLAT
HIGHLIGHT_TEXT = brand.INK
LABEL_WEIGHT = brand.LIGHT
TITLE_WEIGHT = brand.BOLD
TABLE_WIDTH = 640
LABEL_WIDTH = 240

LANGS = ("en", "fr")


# --- product table ---------------------------------------------------------
def _value_cell(row: Row, accent: str) -> str:
    """Values stack one per line; multi-value rows are how baskets render."""
    values = [v for v in row.values if v.strip()]
    colour = accent if row.accent_values else TEXT
    weight = TITLE_WEIGHT if (row.bold or row.accent_values) else 400
    style = f"margin:0;color:{colour};font-weight:{weight};"
    return "".join(f'<p style="{style}">{escape(v)}</p>' for v in values)


def render_row(row: Row, accent: str) -> str:
    cell = (
        f"padding:7px 14px;font-family:{FONT};"
        f"border-bottom:1px solid {HAIRLINE};vertical-align:middle;"
    )
    # Labels are Nunito Light throughout; values carry the emphasis.
    label_td = (
        f'<td style="{cell}font-size:12pt;font-weight:{LABEL_WEIGHT};'
        f'color:{LABEL_TEXT};width:{LABEL_WIDTH}px;">{escape(row.label_en)}</td>'
    )
    if row.highlight:
        value_td = (
            f'<td style="{cell}font-size:14pt;font-weight:{TITLE_WEIGHT};'
            f'background-color:{accent};color:{HIGHLIGHT_TEXT};">'
            f"{_highlight_values(row)}</td>"
        )
    else:
        value_td = f'<td style="{cell}font-size:12pt;">{_value_cell(row, accent)}</td>'
    return f"<tr>{label_td}{value_td}</tr>"


def _highlight_values(row: Row) -> str:
    values = [escape(v) for v in row.values if v.strip()]
    return "<br>".join(values)


def render_table(prop: Proposition, lang: str) -> str:
    """The product table: a full copy of the reference layout and styling."""
    product = prop.product
    accent = accent_hex(product.accent)
    rows = product.visible_rows()
    if not rows and not product.header(lang):
        return ""

    body = "".join(_localised_row(r, lang, accent) for r in rows)
    header = ""
    if title := product.header(lang):
        header = (
            f'<tr><td colspan="2" style="padding:12px 14px;'
            f"background-color:{HEADER_BG};font-family:{FONT};font-size:18pt;"
            f'font-weight:{TITLE_WEIGHT};color:{accent};">{escape(title)}</td></tr>'
        )
    return (
        f'<table cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;width:{TABLE_WIDTH}px;'
        f'background-color:{brand.WHITE};'
        f'font-family:{FONT};color:{TEXT};">'
        f"{header}{body}</table>"
    )


def _localised_row(row: Row, lang: str, accent: str) -> str:
    """render_row keeps the English label; swap it for the requested language."""
    label = row.label(lang)
    localised = Row(
        label_en=label,
        label_fr=label,
        values=row.values,
        highlight=row.highlight,
        accent_values=row.accent_values,
        bold=row.bold,
        key=row.key,
    )
    return render_row(localised, accent)


# --- email body ------------------------------------------------------------
def _p(content: str, size: str = "12pt") -> str:
    return (
        f'<p style="margin:0 0 12px 0;font-family:{FONT};font-size:{size};'
        f'color:{TEXT};">{content}</p>'
    )


def _product_paragraph(prop: Proposition, lang: str) -> str:
    """The product line, with the ISIN and description in bold as in the house
    template, followed by the event sentence."""
    head = "Le produit" if lang == "fr" else "The product"
    name = " - ".join(p for p in (prop.isin, prop.description) if p)
    sit = sentences.situation_of(prop)
    custom = prop.custom_event_fr if lang == "fr" else prop.custom_event_en
    template = custom or (sit.event_fr if lang == "fr" else sit.event_en)
    event = template.format(date=f"<b>{escape(format_date(prop.relevant_date))}</b>")

    parts = []
    if name:
        parts.append(f"{escape(head)} <b>{escape(name)}</b>")
    if event:
        parts.append(event)
    return _p("<br>".join(parts)) if parts else ""


def render_body(prop: Proposition, lang: str) -> str:
    """The email body fragment: greeting, sentences, accounts, table, notes."""
    out: list[str] = [
        _p(escape(sentences.GREETING[lang])),
        _p(escape(sentences.intro(prop, lang))),
        _product_paragraph(prop, lang),
    ]

    if status := sentences.status_line(prop, lang):
        out.append(_p(escape(status)))

    # Account lines keep the house emphasis: number plain, size in bold.
    accounts = [a for a in prop.accounts if a.number]
    if accounts:
        lines = []
        for account in accounts:
            if account.holding_text:
                lines.append(
                    f"{escape(account.number)} – "
                    f"<b>{escape(account.holding_text)}</b>"
                )
            else:
                lines.append(escape(account.number))
        out.append(_p("<br>".join(lines)))

    if rec := sentences.recommendation(prop, lang):
        out.append(_p(escape(rec)))

    if table := render_table(prop, lang):
        out.append(table)

    if extra := sentences.notes(prop, lang):
        body = "<br>".join(escape(line) for line in extra.splitlines())
        out.append(f'<div style="height:16px;"></div>{_p(body)}')

    out.append(f'<div style="height:12px;"></div>{_p(escape(sentences.SIGN_OFF[lang]))}')
    return "\n".join(p for p in out if p)


def render_email(prop: Proposition, lang: str) -> str:
    """A standalone HTML document -- what gets saved and previewed."""
    subject = escape(sentences.subject_line(prop, lang))
    return (
        "<!doctype html>\n"
        f'<html lang="{lang}"><head><meta charset="utf-8">'
        f"<title>{subject}</title></head>"
        f'<body style="margin:0;padding:24px;background-color:#FFFFFF;">'
        f"{render_body(prop, lang)}"
        "</body></html>\n"
    )


# --- plain text fallback ---------------------------------------------------
def render_text(prop: Proposition, lang: str) -> str:
    """Plain-text version, for the multipart alternative in the .eml."""
    out: list[str] = [sentences.GREETING[lang], "", sentences.intro(prop, lang), ""]
    out += [sentences.product_sentence(prop, lang), ""]
    if status := sentences.status_line(prop, lang):
        out += [status, ""]
    if lines := sentences.account_lines(prop):
        out += lines + [""]
    if rec := sentences.recommendation(prop, lang):
        out += [rec, ""]

    product = prop.product
    if title := product.header(lang):
        out += [title.upper(), ""]
    width = max(
        (len(r.label(lang)) for r in product.visible_rows()), default=0
    )
    for row in product.visible_rows():
        values = [v for v in row.values if v.strip()]
        out.append(f"{row.label(lang).ljust(width)}  {values[0]}")
        for extra in values[1:]:
            out.append(f"{' ' * width}  {extra}")
    if extra := sentences.notes(prop, lang):
        out += ["", extra]
    out += ["", sentences.SIGN_OFF[lang]]
    return "\n".join(out) + "\n"


def render_all(prop: Proposition) -> dict:
    """Both languages at once -- what the browser app asks for."""
    return {
        lang: {
            "subject": sentences.subject_line(prop, lang),
            "html": render_email(prop, lang),
            "body": render_body(prop, lang),
            "text": render_text(prop, lang),
            "table": render_table(prop, lang),
            "date_label": sentences.date_label(prop, lang),
        }
        for lang in LANGS
    }
