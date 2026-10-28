# Writing and design standards

Read this when writing messages or titles, or when changing the generator's layouts.

## One slide, one message

- The **title is a short label**, one to four words: "Exposure", "Portfolio status", "NESN / NOVN / ZURN". Under 30 characters: QC warns above that.
- The **line under the title is the takeaway**, 14 pt ink, with the figure in it: "Bank B is the largest issuer at 46%", "34 pts above the 70% barrier". The generator writes it; override with `titles` only when another message matters more, and keep it to one short line.
- Scope and method (dates, currency, rebasing) go in the caption, not in the title or the takeaway.
- Get to the point: no introductions ("This slide shows…"), no sentence that repeats a figure already on the slide, no adjectives that carry no fact.
- Summary: at most three bullets, each ≤ 15 words, each a fact plus its consequence. Example: "NVDA/MSFT/AAPL note probably redeemed on 16 Sep: CHF 210k to reinvest."
- Risks, opportunities, next steps: at most three each, one line each.
- Captions: one line, the basis only ("Before fees, taxes and issuer risk."). The full method is on the sources slide.

## Research-driven comments

Comments rest on research, not on general knowledge. Before writing the messages:

1. Read what the user gave: house view, broker notes, factsheets.
2. Get the latest headlines for the underlyings and largest positions:
   `python scripts/o01.py --news NESN.SW ZURN.SW NVDA` (workspace: `apps\O01\O01_run.py --news …`), and search
   the web for what explains the bigger moves (results, guidance, rates, deals).
3. Put each view in the case file's `research` (see case-file.md): one sentence, ≤ 25 words, with
   `source` and `date`. It shows as **Research view** on the product's performance page or the stock's
   page, or as **Market view** on the summary (`about: "market"`). An item without a source is not shown.
4. The advisor's own conclusions go in `messages`; a third party's view stays in `research`, worded
   as that source's view. Never turn a research forecast into a fact or a figure on a chart.
5. Give the user the links you used (in the hand-over, not on the slides).

## Tone

- Factual, plain English, short sentences. No superlatives, no exclamation marks, no "guaranteed", "safe", "risk-free", "will".
- Balanced: every opportunity sits next to its risk; downside scenarios are shown, not only the base case.
- Past performance is described as past ("returned", "would have returned"), never extrapolated.
- Forward-looking analyst figures are attributed ("consensus target, Yahoo Finance").
- Issuer credit risk is mentioned whenever structured products are discussed.
- Suitability: the deck informs; it does not recommend a specific transaction unless the advisor's message does, and then with its risks.

## Confidentiality (FINMA / Swiss banking secrecy)

- Pseudonyms only (`C-0042`) on the cover, in file names and in the case file. No client names, account or portfolio numbers, addresses or relationship details.
- Uploads and outputs are working copies. Remind the user to file the finished deck in the bank's approved storage.

## Visual identity (from `assets/S00_template.pptx`)

| Element | Rule |
| --- | --- |
| Page | A4 landscape 29.70 × 21.00 cm, the template's own master: logo top right, compliance footer, page number |
| Body area | 0.73 → 11.01 in wide, 2.55 → 7.55 in high; nothing below 7.55 in (footer at 7.76 in) |
| Titles | template title style: amber `#FFA400`, 24 pt, bold; a short label (under 30 characters) |
| Takeaway | the subtitle line under the title: ink, 14 pt, one line |
| Text | ink `#202945`; body 11–14 pt; tables 11–12 pt (10 for wide tables); chart ticks and legends 10 pt; captions 8 pt grey |
| Boxes | none filled: white background throughout. Blocks are set off by a short coloured rule and a bold heading, not by grey boxes |
| Font | **Open Sans** everywhere (theme patched). Nunito Sans is the brand face but is not installed, and PowerPoint would substitute it silently |
| Colours | theme order: orange `#FF6C0E`, blueberry `#4B5F80`, amber `#FFA400`, mulberry `#AC5D85`, mint `#3BAF90`, sky `#79D6FF`; red `#C62828` for barriers and losses, green `#2E7D32` for positive status, rust `#C2500A` for orange text |
| Charts | native, editable PowerPoint charts with data embedded; no frames, no 3D, no gradients; light gridlines on value axes only |
| Payoff diagram | x = final level of the worst underlying (% of initial), y = return incl. coupons; product with barrier breached (red) and not breached (orange), direct investment dashed grey |
| Performance chart | rebased to 100 at the initial fixing (products) or period start (portfolios); barrier red dashed, strike grey dashed, autocall trigger mint dashed |
| Status colours | On track green tint, Watch amber tint, At risk red tint, Called? blue tint |
| KPI figures | on white: short accent rule, value large and bold, label under it, a note only when it changes the reading ("to confirm"); figures in a row share one size |

Avoid: grey or filled text boxes, decorative icons and images, more than one chart type per message, legends that repeat axis labels, truncated product names, text over the footer, paragraphs where a figure or a table would do.
