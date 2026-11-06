# Syz visual guidelines: a resource for icons, fonts and ideas

Source: *Syz Visual Guidelines*, WIP 28/05/24 (`SyzVisualGuidelines_WIP_V2_2.pdf`, 46 pages).

**How to use it.** This is a resource to draw on, not a rulebook that overrides the house style.
Use it for **icons**, **fonts** and **design ideas** (logo use, palette, boxes, layouts for slides
and one-pagers). Each skill's current house style, template or spec stays in charge: where they
differ from this document (see "Open points" at the end), keep the house style.
It does not cover charts or data tables (section 7, Data display): each skill keeps its own
chart rules.

## Assets in this repo

- **Icons**: the 40 Syz icons from the guidelines (p. 24), extracted as vector SVGs in
  `brand/icons/` in three colourways: `gradient/` (the preferred orange gradient), `flat/`
  (Tiger Orange, for PowerPoint and Word, which cannot fill icons with a gradient) and `white/`
  (for dark or busy backgrounds). `brand/icons/overview.png` shows them all. Names:
  cloud, play, presentation, home, bank, folder, archive, stack, bookmark, crown, lock, clock, key,
  microphone, phone, location, bell, send, speaker, calculator, dollar, strategy, chess-queen,
  megaphone, ship, drop, hourglass, truck, bag, moon, lightning, headphones, brain, apple, star,
  bar-chart, paperclip, contrast, image, sun. Insert SVGs into PowerPoint with Insert → Pictures.
- **Finance icons** (not part of the official library): 24 icons drawn in the same style, in
  `brand/icons-finance/` with the same three colourways: coins, wallet, piggy-bank, chart-up,
  chart-down, pie-chart, candlestick, shield, umbrella, percent, briefcase, safe, globe,
  balance-scale, target, calendar, document, exchange, gold-bars, credit-card, euro, growth,
  analysis, banknote. `brand/icons-finance/overview.png` shows them; `brand/make_finance_icons.py`
  redraws them. Have the brand team approve them before external use.
- **Fonts**: Nunito Light, Regular and Bold in `brand/fonts/` (SIL Open Font License, from Google
  Fonts), the web-safe family the guidelines name. Maison Neue, the primary family, is licensed
  and is not included: ask the brand team for it.

## 1. Logo

- **The logo is the "Sunburnt Signature"**: the handwritten "Syz" in the orange gradient
  (Tiger Orange → Mango Amber → Gold Yellow). It is the primary logo; use it by default.
- **Secondary colour ways**, only when the primary does not work: solid Mango Orange, Black,
  or White (white on a coloured or photographic background).
- **Lock-ups**: the signature with a business-line name set to its right in spaced capitals:
  PRIVATE BANKING, ASSET MANAGEMENT, ALTERNATIVE INVESTMENTS, PRIVATE MARKETS, CAPITAL,
  INDEPENDENT MANAGERS. Advisory documents use **Syz Private Banking**.
- **Clear space**: keep empty space around the logo of at least **half the logo's size** on every
  side, free of other logos, text and graphic elements.
- **Minimum size**: **8 mm** wide in print, **40 px** wide on screen.
- The wide signage variant (signature with large PRIVATE BANKING beside it) is for signage only.
- Use the official files (RGB library for screen, CMYK for print), named
  `Syz-<line>-logo-<RGB|CMYK>-<vignette|black|white>`. Never redraw, stretch, recolour or
  rasterise the logo; in a PDF it must stay vector.

## 2. Isotype

- The isotype is the "Syz" signature on its own: favicon, avatar, or a secondary graphic element.
- It can sit in a light grey square or circle, or stand alone. Minimum size 20 × 20 px / 0.5 cm.

## 3. Typography

| Use | Primary (licensed) | Web-safe substitute |
|---|---|---|
| Titles, headlines, emphasis | Maison Neue Bold | Nunito Bold |
| Body, subheads, labels | Maison Neue Light | Nunito Light |

Maison Neue is licensed and not installed on most machines; documents that must open anywhere use
the web-safe family. (The approved SYZ PowerPoint template names Nunito Sans; see "Open points".)

**Type scale** (reference sizes from the guidelines):

| Element | Face | Colour | Case and tracking | Size |
|---|---|---|---|---|
| Section label | Light | Blueberry Blue (grey blue) | UPPERCASE, tracking 400 | 6 pt |
| Headline | Bold | Orange gradient | Sentence case, tracking 0 | 25 pt |
| Subhead 1 | Light | Black | Sentence case | 12 pt |
| Subhead 2 | Bold | Tiger Orange | Sentence case | 10 pt |
| Paragraph | Light | Black | Sentence case | 8 pt |
| Button | Bold | White | UPPERCASE, tracking 100 | 9 pt |

Headlines are short and in sentence case. The section label runs small and spaced, often
vertically along the left edge of a page or slide.

## 4. Colour

**Primary palette** (tints at 75 / 50 / 25 % are allowed):

| Name | HEX | RGB | CMYK | Pantone |
|---|---|---|---|---|
| Tiger Orange | `#FF6C0E` | 255 108 14 | 0 55 95 0 | 1585 C |
| Mango Amber | `#FFA400` | 255 164 0 | 0 35 95 0 | 137 C |
| Gold Yellow | `#FFC545` | 255 197 69 | 0 25 75 0 | 135 C |
| Blueberry Blue | `#4B5F80` | 75 95 128 | 78 55 25 25 | 2374 C |
| Space Blue | `#202945` | 32 41 69 | 95 72 15 55 | 533 C |

**Secondary palette** (tints at 75 / 50 / 25 % allowed): Mint Green `#3BAF90`,
Teal Green `#9DD9D2`, Sky Blue `#79D6FF`, Peach Pink `#E6A4AD`, Mulberry Pink `#AC5D85`.

**Gradients**:
- **Orange gradient**: Tiger Orange (0 %) → Mango Amber (50 %) → Gold Yellow (100 %).
- **Blue gradient**: Space Blue (0 %) → Blueberry Blue (100 %).

## 5. Iconography

- Icons are **filled, not outlined**, with **rounded corners**, never pointy or sharp.
- Preferred fill: the orange gradient. Inside a circle (a button), the icon turns white on the
  gradient. Where gradients are not possible (PowerPoint and Word cannot fill icons with a
  gradient), use a solid primary colour. On dark or busy backgrounds, use white icons.
- In PowerPoint: Insert → Icons, search, insert, then recolour with the Syz palette.
- Icons must be clear and have an obvious meaning.

## 6. Photography

Not yet defined in the guidelines (to be added once a photography style is approved).

## 8. Graphic elements

**Boxes**: white, all corners rounded (**35 px**), no outline, with a soft drop shadow. Two styles:
- **Orange-yellow box**: shadow in Gold Yellow on top / Tiger Orange underneath.
- **Blue-grey box**: shadow in Blueberry Blue on top / Space Blue underneath.
- Shadow settings in design software: opacity 20 %, distance 15 px, size 20 px; top shadow angle
  −90° (Y offset −15 px), bottom shadow angle 90° (Y offset 15 px).
- In PowerPoint or Word: Rounded rectangle, white fill, no outline; Outer shadow, second preset
  (centred under the box); colour Mango Amber; transparency 70 %, size 100 %, blur 50 pt,
  angle 90°, distance 0.

**Buttons**: fully rounded (100 px corners). Primary: orange gradient, white text, soft blue shadow
(20 %), bold type on small buttons and light type on large ones. Secondary, where gradients don't
work: solid Tiger Orange with white text, or white with a Tiger Orange outline and text.

**Blurred backgrounds**: soft blurred blends of orange, amber, gold and white, used for title,
section and closing pages.

## 9. Best practice

**PowerPoint**
- Always start from the approved Syz template.
- Title slide: the photographic version for external communications, the gradient version for
  corporate ones.
- Be as minimalistic as possible: **one message per slide**.
- Use boxes to organise and separate content; alternate orange and blue gradients in boxes for
  colour interest; add rounded corners and shapes to lift the composition.
- Use sleek diagrams and flowcharts, organise content in boxes, and support messages with icons.

**One-pagers**
- With a lot of content in little space, use **boxes and lines** to separate sections and give the
  reader breathing room.
- Keep margins as wide as possible.
- Use strong colour boxes (e.g. Space Blue) for call-out messages and key figures.
- Page furniture seen in the examples: logo top right, small vertical section label
  (e.g. PRIVATE BANKING) on the left edge, orange headline, Bold orange subheads.

**Social media**: use the gradient and palette boldly, but keep messages clear and to the point.

## Open points between the guidelines and current house practice

These differ between the guidelines and what the advisory skills or the team do today. The
skills keep their current behaviour until the team decides:

1. **Web-safe font**: the guidelines name **Nunito**; the approved PowerPoint template and the
   advisory house rule use **Nunito Sans** for text (Nunito Bold for titles).
2. **Type sizes**: the guidelines' reference scale is 25 / 12 / 10 / 8 / 6 pt; the advisory house
   rule for presentations is 16 / 12 / 8 pt.
3. **Gradients and boxes**: the guidelines use the orange gradient for headlines, buttons and
   icons, and shadowed rounded boxes to structure content. The advisory PDF style used since
   November 2026 has flat colour and thin rules, with no shaded text boxes.
4. **Body text colour**: the guidelines set body text in Black; the advisory skills set all type
   in Space Blue `#202945`.
