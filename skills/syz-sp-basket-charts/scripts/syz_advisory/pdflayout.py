"""House-style building blocks for pdfwriter pages: the palette shades and the table used by the
G01 proposal PDFs and the P02 technical reviews."""

from __future__ import annotations

from . import brand

GRID = brand.flatten(brand.RULE, 0.12)
AXIS = brand.RULE_FLAT
MUTED = brand.flatten(brand.INK, 0.6)


def table(pg, x0: float, y: float, cols: list[tuple[str, float, str]], rows: list[list], size=7.0,
          row_h=13.0) -> float:
    """cols: (header, width, align); a header may have two lines ("a\\nb"); a cell is text or
    (text, colour, bold, second line). Returns the y under the table."""
    two = any("\n" in c[0] for c in cols)
    head_h = 20 if two else 12
    x = x0
    for label, w, align in cols:
        for k, part in enumerate(label.split("\n")):
            tx = x + w - 3 if align == "end" else x + 3
            pg.text(tx, y + 8 + 8 * k + (0 if two and "\n" in label else 8 if two else 0), part, size, True,
                    brand.INK, align)
        x += w
    y += head_h + 2
    total = sum(c[1] for c in cols)
    pg.line(x0, y, x0 + total, y, AXIS, 0.6)
    for r in rows:
        x = x0
        for (label, w, align), cell in zip(cols, r):
            text, colour, bold, sub = (cell + (None,) * 4)[:4] if isinstance(cell, tuple) else (cell, None, False, None)
            tx = x + w - 3 if align == "end" else x + 3
            pg.text(tx, y + 9, pg.fit(text, size, w - 6, bool(bold)), size, bool(bold), colour or brand.INK, align)
            if sub:
                pg.text(tx, y + 17, pg.fit(sub, size - 1, w - 6), size - 1, colour=MUTED, anchor=align)
            x += w
        y += row_h
        pg.line(x0, y, x0 + total, y, GRID, 0.4)
    return y
