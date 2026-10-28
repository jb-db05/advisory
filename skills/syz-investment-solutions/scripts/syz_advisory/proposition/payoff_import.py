"""Read the reference tables out of Payoff.xlsx.

Each sheet holds one or more payoff blocks: an 18pt bold header followed by
label/value pairs, with the coupon-style line filled in an accent colour and
multi-value rows (underlyings, baskets, scenarios) continuing on unlabelled
rows underneath. This turns every block into the same row structure the tool
renders, so the workbook doubles as the example library.
"""

from __future__ import annotations

import json
from pathlib import Path

import openpyxl

from syz_advisory.brand import DEFAULT_ACCENT

from .catalogue import EXAMPLES_PATH, FIELDS

SKIP_SHEETS = {"ACCUEIL", "Sheet1"}
HEADER_MIN_SIZE = 16
# The workbook predates the current palette, so its two accent colours are
# mapped onto their house equivalents.
ACCENT_BY_HEX = {
    "FFEC5700": "tiger_orange",
    "FF0079C2": "blueberry_blue",
    "FF31ADD1": "sky_blue",
}

# Workbook labels are inconsistent ("Guaranted Coupon", "Coupon p.a. ", ...);
# map them onto the catalogue keys so examples can seed a template.
_ALIASES = {
    "underlyings": "underlyings",
    "underlyings (worst of)": "underlyings",
    "underlying": "underlyings",
    "guaranted coupon": "guaranteed_coupon",
    "guaranteed coupon": "guaranteed_coupon",
    "guaranted coupon p.a.": "guaranteed_coupon",
    "guaranteed coupon p.a.": "guaranteed_coupon",
    "guaranted coupon": "guaranteed_coupon",
    "coupon": "coupon_pa",
    "coupon p.a.": "coupon_pa",
    "coupon flat": "coupon_flat",
    "coupon frequency": "coupon_frequency",
    "coupon observation": "coupon_observation",
    "coupon trigger": "coupon_trigger",
    "autocall level": "autocall_trigger",
    "autocall frequency": "autocall_frequency",
    "non-call period": "non_call_period",
    "lock in observation": "lock_in_observation",
    "lockin level": "lock_in_level",
    "nominal amount": "nominal",
    "settlement": "settlement_type",
    "strike level": "strike_level",
    "recovery level if called": "recovery",
    "autocall": "autocall_trigger",
    "autocallable": "autocall_trigger",
    "autocall trigger level": "autocall_trigger",
    "coupon trigger level": "coupon_trigger",
    "stepdown": "step_down_trigger",
    "protection": "principal_protection",
    "observation": "coupon_observation",
    "strikes": "strike",
    "lookback min period": "lookback_period",
    "redemption scenario at maturity (for illustration purpose only)":
        "redemption_scenario",
}
_BY_LABEL = {f.en.lower(): f.key for f in FIELDS}


def field_key_for(label: str) -> str:
    text = label.strip().lower().rstrip(":")
    return _ALIASES.get(text) or _BY_LABEL.get(text, "")


def _rgb(colour) -> str | None:
    value = getattr(colour, "rgb", None)
    return value if isinstance(value, str) else None


def _fill_hex(cell) -> str | None:
    fill = cell.fill
    if not fill or not fill.fill_type:
        return None
    return _rgb(fill.start_color)


def _accent_name(hex_value: str | None) -> str:
    if not hex_value:
        return ""
    return ACCENT_BY_HEX.get(hex_value.upper(), "")


def _format_value(cell) -> str:
    """Excel stores 0.7 for a 70% strike; render it the way the sheet shows it."""
    value = cell.value
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        fmt = cell.number_format or ""
        if "%" in fmt:
            return _trim(value * 100) + "%"
        return _trim(value)
    return str(value).strip()


def _trim(number: float) -> str:
    text = f"{number:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _is_header(cell) -> bool:
    return (
        isinstance(cell.value, str)
        and cell.font
        and cell.font.bold
        and (cell.font.sz or 0) >= HEADER_MIN_SIZE
        and cell.value.strip() != "ACCUEIL"
    )


def extract_block(ws, header_cell) -> dict | None:
    """Walk down from a header cell, collecting label/value rows."""
    label_col, value_col = header_cell.column, header_cell.column + 1
    rows: list[dict] = []
    blanks = 0
    r = header_cell.row + 1
    accent = _accent_name(_rgb(header_cell.font.color)) or _accent_name(
        _fill_hex(header_cell)
    )

    while r <= ws.max_row and blanks < 3:
        label_cell = ws.cell(row=r, column=label_col)
        value_cell = ws.cell(row=r, column=value_col)
        label = label_cell.value
        value = _format_value(value_cell)

        if label is None and not value:
            blanks += 1
            r += 1
            continue
        blanks = 0

        if label is None and rows:
            # Continuation of the previous row (extra underlying, extra scenario).
            if value:
                rows[-1]["values"].append(value)
            r += 1
            continue

        fill = _fill_hex(value_cell)
        fill_accent = _accent_name(fill)
        font_accent = _accent_name(_rgb(value_cell.font.color) if value_cell.font else None)
        label_text = str(label).strip() if label is not None else ""
        rows.append(
            {
                "key": field_key_for(label_text),
                "label_en": label_text,
                "values": [value] if value else [],
                "highlight": bool(fill),
                "accent_values": bool(font_accent),
                "bold": bool(value_cell.font and value_cell.font.bold),
            }
        )
        accent = accent or fill_accent or font_accent
        r += 1

    rows = [r for r in rows if r["values"]]
    if not rows:
        return None
    return {
        "sheet": ws.title,
        "cell": header_cell.coordinate,
        "header": header_cell.value.strip(),
        "accent": accent or DEFAULT_ACCENT,
        "rows": rows,
    }


def extract(xlsx: Path) -> list[dict]:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    blocks: list[dict] = []
    for ws in wb.worksheets:
        if ws.title in SKIP_SHEETS:
            continue
        for row in ws.iter_rows():
            for cell in row:
                if _is_header(cell):
                    if block := extract_block(ws, cell):
                        blocks.append(block)
    return blocks


def rebuild(xlsx: Path, out: Path = EXAMPLES_PATH) -> int:
    """Regenerate the example library; returns the number of blocks written."""
    blocks = extract(xlsx)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(blocks, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return len(blocks)


