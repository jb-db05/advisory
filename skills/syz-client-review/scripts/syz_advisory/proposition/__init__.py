"""Advisory roll propositions: email wording + product table, EN and FR.

Screen 1 of the tool fills the email information (accounts, ISIN, description,
relevant date, situation); screen 2 fills the product table. `render_all`
combines both into a ready-to-send email in both languages.
"""

from .catalogue import (
    FIELDS,
    FIELDS_BY_KEY,
    SITUATIONS,
    SITUATIONS_BY_KEY,
    TEMPLATES,
    TEMPLATES_BY_KEY,
    examples,
    to_json,
)
from . import termsheet_fill
from .mail import write_eml
from .models import ACCENTS, Account, Product, Proposition, Row
from .render import render_all, render_body, render_email, render_table, render_text

__all__ = [
    "ACCENTS",
    "Account",
    "FIELDS",
    "FIELDS_BY_KEY",
    "Product",
    "Proposition",
    "Row",
    "SITUATIONS",
    "SITUATIONS_BY_KEY",
    "TEMPLATES",
    "TEMPLATES_BY_KEY",
    "examples",
    "render_all",
    "render_body",
    "render_email",
    "render_table",
    "render_text",
    "termsheet_fill",
    "to_json",
    "write_eml",
]
