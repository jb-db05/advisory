"""Read trades from whatever arrives: Excel, CSV or an HTML page.

Every source is first loaded as a raw grid of cells, then the header row is
found by looking for known column names, so title rows, logos and blank
lines above the table do not matter.
"""

import csv
import io
from pathlib import Path

import pandas as pd

from .schema import KEYS, match_header

SUPPORTED = {".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".html", ".htm"}
HEADER_SCAN_ROWS = 60
MIN_MATCHED_COLUMNS = 4


def read_file(path) -> pd.DataFrame:
    """Return every trade-like table in the file, mapped to schema keys.

    Columns: the schema keys present in the source, plus `source_file` and
    `source_row` (1-based row number as the user sees it in the source).
    """
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"{path.name}: unsupported file type {ext}")

    frames = []
    for label, grid in _grids(path, ext):
        table = _extract_table(grid)
        if table is not None:
            table["source_file"] = path.name if not label else f"{path.name} [{label}]"
            frames.append(table)
    if not frames:
        raise ValueError(f"{path.name}: no table with trade columns (ISIN, Size, ...) found")
    return pd.concat(frames, ignore_index=True)


def _grids(path, ext):
    """Yield (sheet/table label, raw DataFrame with header=None)."""
    if ext in {".xlsx", ".xlsm", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
        for name, grid in sheets.items():
            yield (name if len(sheets) > 1 else ""), grid
    elif ext in {".csv", ".txt"}:
        yield "", _read_csv(path)
    else:
        html = path.read_bytes().decode("utf-8", errors="replace")
        tables = pd.read_html(io.StringIO(html), header=None)
        for i, grid in enumerate(tables, 1):
            grid = grid.astype(object)
            # read_html sometimes lifts the header into the column index.
            if not all(isinstance(c, int) for c in grid.columns):
                head = pd.DataFrame([list(map(_flat, grid.columns))], columns=range(grid.shape[1]))
                grid.columns = range(grid.shape[1])
                grid = pd.concat([head, grid], ignore_index=True)
            yield (f"table {i}" if len(tables) > 1 else ""), grid


def _flat(col):
    return " ".join(str(c) for c in col) if isinstance(col, tuple) else col


def _read_csv(path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        delim = csv.Sniffer().sniff(text[:5000], delimiters=";,\t|").delimiter
    except csv.Error:
        delim = ";" if text.count(";") > text.count(",") else ","
    # Exports often carry a title line above the table, so rows are ragged.
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    width = max((len(r) for r in rows), default=0)
    return pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=object)


def _extract_table(grid: pd.DataFrame):
    header_idx, mapping = None, {}
    for i in range(min(HEADER_SCAN_ROWS, len(grid))):
        found = {}
        for col, cell in grid.iloc[i].items():
            if cell is None or (isinstance(cell, float) and pd.isna(cell)):
                continue
            key = match_header(cell)
            if key and key not in found.values():
                found[col] = key
        if "isin" in found.values() and len(found) >= MIN_MATCHED_COLUMNS:
            header_idx, mapping = i, found
            break
    if header_idx is None:
        return None

    body = grid.iloc[header_idx + 1:]
    out = pd.DataFrame({key: body[col].values for col, key in mapping.items()})
    for key in KEYS:
        if key not in out:
            out[key] = None
    out["source_row"] = [header_idx + 2 + n for n in range(len(body))]
    out = out[KEYS + ["source_row"]]

    blank = out[KEYS].map(_is_blank).all(axis=1)
    return out[~blank].reset_index(drop=True)


def _is_blank(v):
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    return isinstance(v, str) and not v.strip()
