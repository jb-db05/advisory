---
name: syz-brand-kit
description: "The Syz brand kit for every presentation and document: the official vector logo (Private Banking lock-up and signature, gradient, mango, black and white), the 40 Syz icons plus 24 finance icons in the same style (gradient, flat Tiger Orange, white), the Nunito and Nunito Sans fonts, the Syz colour palette, and the Syz Visual Guidelines as a resource for design ideas. Includes helpers to find and recolour icons, export them as PNG for PowerPoint or Word, and place the logo sharply on PDFs. Use whenever building or restyling a Syz deck, slide, PDF, one-pager, report, factsheet or client document, when an icon, the logo, the Syz fonts or colours are needed, or when another SYZ skill produces a branded output."
---

# Syz brand kit

One place for the Syz logo, icons, fonts, colours and design ideas. Call it alongside any skill
that produces a Syz document (deck, PDF, one-pager, Word report) or on its own to fetch an icon or
the logo. It is a resource, not a rulebook: the calling skill's house style, template or spec stays
in charge, and charts keep their own rules.

## What is inside

| Folder | Content |
|---|---|
| `assets/logo/` | Vector logo: `syz-private-banking.svg` (signature + PRIVATE BANKING, the default for advisory documents) and `syz-signature.svg` (signature alone), each also `-mango`, `-black`, `-white` |
| `assets/icons/syz/` | The 40 official Syz icons (Visual Guidelines p. 24) in `gradient/`, `flat/`, `white/`; `overview.png` |
| `assets/icons/finance/` | 24 finance icons drawn in the same style (coins, wallet, piggy bank, charts, candlestick, shield, umbrella, percent, safe, globe, gold bars, euro, ...): same three colour ways; **not official, get brand approval before external use** |
| `assets/fonts/` | Nunito Light / Regular / Bold, Nunito Sans Regular / Bold (SIL OFL) |
| `references/visual-guidelines.md` | The Syz Visual Guidelines in writing (logo, type, colour, icons, boxes, slides, one-pagers), minus charts |
| `assets/source/` | The guidelines PDF |
| `scripts/` | `icons.py` (find, recolour, export PNG), `stamp_logo.py` (vector logo on PDFs), maintenance scripts |

Open `assets/icons/*/overview.png` to pick an icon by eye.

## How to use it

**Find an icon**

```bash
python scripts/icons.py list --search chart          # name, set and file
python scripts/icons.py path piggy-bank --way flat   # the SVG path
```

Names: see the overview sheets. A name that does not exist prints the closest matches.

**By output type**

- **HTML / WeasyPrint PDF**: use the SVG files directly (`<img src="...svg">`), fonts via
  `@font-face` from `assets/fonts/`. For the logo, leave an empty box in the HTML and place it
  afterwards with `python scripts/stamp_logo.py in.pdf out.pdf --width-mm 27 --top-mm 12
  --right-mm 12`: an SVG gradient written by WeasyPrint looks pixelated in most viewers.
- **PowerPoint by hand**: Insert → Pictures → the SVG. Use `flat/` (or `white/` on dark slides):
  PowerPoint cannot fill icons with a gradient.
- **python-pptx / python-docx**: they cannot insert SVG; export a PNG first:
  `python scripts/icons.py png bank --way flat --size 512 --out bank.png`, and for the logo
  `python scripts/icons.py logo --way gradient --width 1200 --out logo.png`.
- **Another palette colour**: `--colour blueberry-blue` (or any palette name or hex) recolours a
  flat icon, e.g. to tell categories apart.
- **matplotlib**: register the fonts with
  `matplotlib.font_manager.fontManager.addfont(path)` for each file in `assets/fonts/`.

PNG export and logo stamping need `pip install cairosvg pypdf`.

## Quick reference

- **Palette**: Tiger Orange `#FF6C0E`, Mango Amber `#FFA400`, Gold Yellow `#FFC545`,
  Blueberry Blue `#4B5F80`, Space Blue `#202945`; secondary Mint Green `#3BAF90`,
  Teal Green `#9DD9D2`, Sky Blue `#79D6FF`, Peach Pink `#E6A4AD`, Mulberry Pink `#AC5D85`.
  Orange gradient: Tiger Orange → Mango Amber → Gold Yellow.
- **Logo**: vector only, never redrawn, stretched or recoloured outside the four colour ways;
  clear space of half the logo's size around it; at least 8 mm wide in print, 40 px on screen.
- **Icons**: filled with round corners; one icon per idea, the same colour way across a document;
  white icons on dark or busy backgrounds.
- **Fonts**: Nunito Sans for text and Nunito Bold for titles in the advisory house style; the
  guidelines name Nunito (Light for body). Maison Neue is licensed and not included.

More ideas (boxes, buttons, slide and one-pager layouts) are in
`references/visual-guidelines.md`. Its "Open points" list where it differs from current house
practice: keep current practice on those.

## Maintenance

- `scripts/make_finance_icons.py assets/icons/finance` redraws the finance icons: add a new icon
  to its `ICONS` table, rerun, and regenerate the overview.
- `scripts/extract_icons.py` rebuilds the official icons from the guidelines PDF.
- Other skills carry a copy of `references/visual-guidelines.md`. After editing it, run
  `skills/syz-brand-kit/scripts/sync_guidelines.sh` from the repo root.

## Not for

Charts and data tables: each skill keeps its own chart rules. Replacing a skill's own template or
build spec: the kit supplies assets, it does not restyle a document on its own.
