"""Place the Syz logo on a PDF as true vector art, with a smooth gradient.

HTML-to-PDF tools such as WeasyPrint write the logo's SVG gradient as a tiling pattern, which many
viewers (browsers, the Claude app, phones) draw as a low-resolution bitmap, so the logo looks
pixelated. Build the page without the logo (keep an empty box where it goes), then run this:
Cairo writes the gradient as an axial shading, which every viewer draws sharp.

    python scripts/stamp_logo.py IN.pdf OUT.pdf [--logo assets/logo/syz-private-banking.svg]
           [--width-mm 27] [--top-mm 12] [--right-mm 12] [--pages 1]

--pages: "1" (default), "all", or a comma list such as "1,3". Needs cairosvg and pypdf.
"""
import argparse
import io
from pathlib import Path

import cairosvg
from pypdf import PdfReader, PdfWriter, Transformation

KIT = Path(__file__).resolve().parents[1]
MM = 72 / 25.4

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--logo", default=str(KIT / "assets" / "logo" / "syz-private-banking.svg"))
ap.add_argument("--width-mm", type=float, default=27)
ap.add_argument("--top-mm", type=float, default=12)
ap.add_argument("--right-mm", type=float, default=12)
ap.add_argument("--pages", default="1")
a = ap.parse_args()

w_pt = a.width_mm * MM
logo_pdf = cairosvg.svg2pdf(bytestring=Path(a.logo).read_bytes(), output_width=w_pt / 0.75)  # CSS px
logo = PdfReader(io.BytesIO(logo_pdf)).pages[0]
lw, lh = float(logo.mediabox.width), float(logo.mediabox.height)

out = PdfWriter(clone_from=PdfReader(a.src))
pages = range(len(out.pages)) if a.pages == "all" else [int(p) - 1 for p in a.pages.split(",")]
for i in pages:
    page = out.pages[i]
    pw, ph = float(page.mediabox.width), float(page.mediabox.height)
    page.merge_transformed_page(logo, Transformation().translate(pw - a.right_mm * MM - lw,
                                                                 ph - a.top_mm * MM - lh))
out.write(a.dst)
print(f"logo {lw:.1f} x {lh:.1f} pt on page(s) {a.pages} -> {a.dst}")
