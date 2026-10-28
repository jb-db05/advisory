# Design: the SYZ format and how to use it

Read before choosing layouts, and when improving a deck.

## The format (reference: the weekly "Investment Solutions by your Advisory Team" decks)

| Element | Rule |
| --- | --- |
| Cover | Template "Cover Slide 2": title bottom-left (orange gradient), date above it, a photograph on the right half; the idea's name in orange over the photo |
| Title | Template title: bold, orange-to-amber gradient, one line, under 30 characters |
| Section label | Italic orange line under the title: what kind of slide this is ("Market context", "Indicative terms", "Leverage") |
| Page | White. No grey or filled text boxes. Blocks are separated by space, outlined cards (rounded, orange or ink), thin rules |
| Text | Ink `#202945`, Open Sans, 11–13 pt; orange → bullets; **bold** for the key words; orange bold for the one phrase that matters |
| Figures | Big and bold: orange (key figures), amber in outlined boxes (limits, coupons), ink in a strip (secondary facts) |
| Tables | Orange bold header, orange rule under it and at the end, light rules between rows, first column bold, highlighted values in orange |
| Charts | Native and editable. Orange line with round markers for payoffs; blueberry columns with the key bars in amber / orange; data labels bold; light gridlines; no frames, no 3D |
| Foot | ➢ takeaway (bold italic), then grey italic note, then grey "Source: …"; the template adds "Please see important information…" and the page number |
| End | Important Information, then "Welcome to Syzerland" |

## Which block for which message

| The message is… | Use |
| --- | --- |
| A comparison of two or three sides (is / is not, needs / risks / mechanics) | `cards` |
| A few numbers that make the case | `kpis` (`rule`), with a short `text` beside or below |
| How a product pays at each level | `line` chart from the terms + 2 reading bullets |
| What accumulates or steps over time | `column` chart, the decisive bars highlighted |
| Who is inside an ETF / index | `bar` chart of the top holdings |
| Where a price has been | `price` chart from market data, to the deck date |
| The terms | `terms` table, the coupon or strike highlighted; alternatives as `kpis` `box` |
| Limits, eligibility, checks | `kpis` `box` row |
| A process or timeline | `steps` |
| Risks, warnings, things to say | `flags` (or one `callout` for a single key point) |
| Market levels | `levels` beside the trading view |
| Instrument A vs B vs C | `table`, the recommended column in orange |

Layouts: text left / visual right (`columns` 0.45 / 0.55) for an argument with its proof; `top`
figures + `columns` for an underlying page; full-width `cards` or `table` for one comparison.

## Writing

- Title: the topic in 1–4 words. Section label: the angle. Takeaway: the point, with a figure.
- One idea per slide. If a slide needs two takeaways, it is two slides.
- Bullets: one line, starting with the bold key words. At most five per block, two blocks of text
  per slide.
- Cut: introductions ("This slide shows"), repetitions of a figure already in a chart, adjectives
  without a fact ("amazing", "GREATLY"), shouting capitals, exclamation marks.
- Numbers: units and dates always ("18% p.a.", "USD 15'000", "as of 30 Jun 2026"); one decimal
  unless the source gives more and it matters (volatility 54.47% as stated).
- Third-party views are quoted as such; forecasts are "expected", "estimated", never facts.
- Client-facing tone: factual, balanced. Every product slide shows its risk next to its return.

## Before → after patterns (from real decks)

| Before | After |
| --- | --- |
| Four slides each with one huge question and one box ("What client needs…?", "What are the risks?", "How does it work?", "Impact on economics?") | One "idea in one page" slide: three cards (what it solves / what it costs / how it pays) and a takeaway |
| A pasted screenshot of a stepdown schedule | `column` chart: coupon paid if called at each observation (calculated from the terms) + the trigger in a one-row table |
| A paragraph of 150 words on an ETF | 3 `kpis` (volatility, key level, concentration) + 4 one-line bullets + a `bar` chart of the holdings |
| An "investment conclusion" banner, a Bloomberg screenshot, a 300-word text box and a holdings list on one slide | `kpis` for the four key numbers, five bullets (incl. key risks), holdings `bar` chart; the screenshot dropped because its message is in the figures (say so) |
| Two slides per product (terms, then the payoff chart) | One slide: `terms` left, payoff `line` chart right with two reading bullets |
| "Internal risk management" five orange boxes, notes overflowing | `kpis` `box` row with short notes (the limits stay as given) |
| A contradiction in the source (EUR "strong" vs "break below 1.14 confirms bearish") | Rephrased as a condition ("a break below 1.14 … would confirm") and flagged in the hand-over |

## Sources

- On the slide: one grey line, specific and dated: "Goldman Sachs indicative terms, 12 Aug 2026";
  "Millennium International factsheet, 30 Jun 2026"; "Syz CIO view, 5 Aug 2026; EUR/USD daily closes".
- A figure you calculated: "Syz Advisory calculation: 18% p.a. x time elapsed".
- In the hand-over: the full list, with links for web sources.
