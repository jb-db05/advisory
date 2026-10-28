---
name: syz-portfolio-proposal
description: "SYZ Portfolio Proposal: builds client-ready SYZ presentations through a fixed intake, for structured products (SP) or cross-asset portfolios. It first asks for the type (Structured products or Cross-asset), the length (full or compact), the format (PowerPoint, Word or PDF) and the objective (proposal overview, review of an existing proposal or portfolio, or new investment idea). It then reads every document, data file and piece of research the user provides, routes to the right workspace engine (SP: the G01 thematic proposal deck as PDF, full or compact, or editable Word, or the O01 PowerPoint review of products held; cross-asset: the O01 PowerPoint proposal or client portfolio review on the SYZ template), and writes the investment rationale, risks and potential returns from calculated figures and quoted research only. Use when asked for a portfolio proposal, presentation, deck, pitch book, slides or client document on structured products or on a multi-asset / cross-asset allocation, a basket proposal, a new SP idea, a proposed allocation, or a review of a proposal, of products held or of a client portfolio."
---

# SYZ Portfolio Proposal

You are the intake and the analyst; the scripts are the factory. Ask four questions, gather and
check the inputs, write the story, run the right engine, review, hand over. Every market figure
comes from the engines (market closes, the sheet, the term sheets, the case file) or is calculated
by them. You write the words around the figures, never the figures.

## 1. Ask the four questions

Ask them together, in one message (`AskUserQuestion` when available). Skip any the request already
answers ("the compact PDF of the SP proposal" answers three), and say what you took from it.

| # | Question | Options |
| --- | --- | --- |
| 1 | Type | **Structured products** (baskets, coupons, barriers) / **Cross-asset** (equities, bonds, funds, alternatives, cash; SP as one line) |
| 2 | Length | **Full** (every product or position on its own page) / **Compact** (about half the pages) |
| 3 | Format | **PDF** / **Word** (editable) / **PowerPoint** |
| 4 | Objective | **Proposal overview** (a new set of products or a new allocation) / **Review** (a proposal made earlier, products now held, or the client's portfolio) / **New investment idea** (one to three baskets or positions) |

Then look up the combination in [references/routing.md](references/routing.md). Some do not
exist (compact Word, an SP proposal in PowerPoint, a cross-asset PDF). Say so plainly and offer the
nearest one that does, before doing any work. Never imitate a format by converting another, e.g.
PDF pages pasted into slides.

## 2. Gather and read every input

Take everything the user gave: files, pasted tables, links to earlier outputs, research notes.

| Input | How it is read |
| --- | --- |
| SP proposal sheet (CSV, or a list pasted in chat) | G01 sheet format: `.claude/skills/syz-proposal-charts/references/sheet-format.md` |
| Term sheets, factsheets, pricer pages (PDF / HTML) | `.\.venv\Scripts\python apps\O01\O01_run.py --terms FILE` (one product) or `--ingest FILES…` (many); each field comes with its status and source |
| Positions / custody extract (CSV / Excel) | `O01_run.py --ingest`: matched to products by ISIN |
| Cross-asset allocation (a list of positions with weights, pasted or in a file) | The O01 case file's `holdings`: name, Yahoo symbol, asset class, currency, region, weight ([case-file.md](../syz-client-presentations/references/case-file.md)) |
| Research, house view, broker notes | The case file's `research` items, quoted with source and date (see section 3) |
| An earlier deck or sheet (for a review) | The baseline to compare against |

Then:

1. **Anonymise.** No client name, account or portfolio number, or address anywhere: sheet, story
   file, case file, file names, slides. Use a pseudonym (`C-0042`). If an input carries one (e.g. a
   file called `Client C.csv`), write a cleaned copy, name outputs by date, and tell the user.
2. **Check what is missing.**
   - SP: every product needs underlyings, a protection level (barrier or strike), a tenor and a
     coupon. The coupon comes from the sheet, a term sheet or an issuer quote.
   - Cross-asset: every position needs a weight and an asset class; a Yahoo symbol for anything
     that has a price (cash and direct bonds may have none).
   - Ask for anything missing; do not estimate it. A coupon is never derived from volatility.
3. **Fix the tickers.** SP: write the `--tickers` JSON with the listing each product is written on
   (`ASML.AS` for EUR, `ROP.SW` for the Roche Genussschein). Cross-asset: the `symbol` of each
   holding. Check every printed match after the first build.

## 3. Research, then write the words

**Research first.** Comments must rest on available research, not on general knowledge:

- Use what the user gave first (house view, broker notes, factsheets).
- Then the latest news per name: `.\.venv\Scripts\python apps\O01\O01_run.py --news NESN.SW NVDA`,
  plus a web search for the bigger moves (results, guidance, rates, deals).
- Each comment is one sentence, about 25 words, with its source and date. Facts only, never a
  forecast written as a fact, never "we recommend" attributed to a third party.
- Keep the source links for the hand-over (for the advisor, not on the slides).

**Where the words go:**

- **G01 decks (SP proposal, PDF or Word):** the themes JSON: title, objective, principles, theme
  families and, per product, theme, thesis and investment-case bullets. Format and writing rules in
  [references/story-file.md](references/story-file.md). Start from
  `data/G01/in/G01_presentation_themes.json` when the products match; otherwise write a new file
  next to the sheet (`G01_presentation_themes_<date>.json`). Never overwrite the shared one without
  asking. A research figure goes in a bullet only with its source and date.
- **O01 decks (PowerPoint):** the case file's `messages` (summary, risks, opportunities,
  next steps) and `research` items (`about` a symbol, a product or `market`). Rules in
  `.claude/skills/syz-client-presentations/references/writing.md`.

**Style, for every deck:** in O01 decks, titles are short labels of one to four words ("Exposure",
"NESN / NOVN / ZURN") and the takeaway sits on the line under them ("Bank B is the largest issuer at
46%"); in G01 decks, keep headlines short; messages of one line each, three per box at most; no sentence where a
figure says it.

Apply the frameworks in `.claude/skills/syz-client-presentations/references/`:
`sp-knowledge.md` (payoffs, barriers, autocalls, risks to state), `equity-bonds.md` (equity
and bond analysis), `analysis.md` (observed, calculated, assumed) and `writing.md` (tone,
confidentiality, visual identity).

## 4. Build

Run the command from [references/routing.md](references/routing.md) for the chosen combination.
Rules for every build:

- Use `.\.venv\Scripts\python`. Add `--offline` only when the user asks or market data is
  unreachable, and say the prices are cached.
- Never overwrite an earlier output. Pass `--out` with the next free `_vN` suffix in `data/<code>/out/`.
- Read the console: `Font: Nunito Sans` (G01, the brand face, from `apps/S00/fonts/`), every
  `NAME -> SYMBOL` match, every `WARNING … no prices`. A wrong match or missing price is fixed
  and rebuilt, never typed in.
- O01 exits with code 1 when its QC finds an error: fix it before going on. A QC warning
  `title is NN characters` means a title from the case file is too long: shorten it.

## 5. Review, then write the messages

Go through [references/review.md](references/review.md): the figures to check, what to compare in
a review, the risks that must appear, and the client-suitability checks. Where the engine
produces analysis (swap test, replay, scenarios, lows against protection, gaps to the strategy,
back-test), report what it says, including what is unfavourable.

## 6. Hand over

- Start with one line naming the audience (e.g. "Written for: the client, via the advisor").
- Link each file with its full path.
- Say which combination was built, and any you could not build and why.
- List the open points: names to confirm, missing terms, products whose 1-year low was at or
  below protection, research items not shown, and anything taken from research rather than
  calculated.
- List the research sources used, with links.
- For a review, give what changed since the baseline in three to five lines.

## Rules that are never relaxed

- **No invented figures.** Coupons, strikes, barriers, issuers and weights come from the user's
  inputs. Prices, vol, correlation, consensus, replay, back-test and scenarios come from the engines.
  Anything else is left out or marked `n/a` and listed as an open point.
- **Research is quoted, not absorbed.** A research view appears with its source and date ("Syz
  house view, Oct 2026: …"), worded as that source's view. It is never mixed into a calculated figure.
- **No assumption is presented as a fact.** SP levels assume a strike at today's close; the replay
  and the cross-asset back-test are history, not a forecast; coupons are before fees and taxes and
  depend on the issuer's credit. The decks carry these notes: keep them.
- **No sizes or amounts** in a general proposal; weights only. The O01 proposal shows no amounts
  even when values are given.
- The template's *Important Information* and closing pages end every deck.

## Examples

**SP.** "Make a compact PDF presenting Proposal_2026-10-21.csv to the client."

1. Type, length and format are given; ask only the objective. Answer: proposal overview.
2. Routing: G01 compact PDF. The sheet is anonymous; tickers are in `Proposal_tickers.json`; the
   story file matches its 18 products.
3. Build:
   ```powershell
   .\.venv\Scripts\python apps\G01\G01_presentation.py data\G01\in\Proposal_2026-10-21.csv `
       --tickers data\G01\in\Proposal_tickers.json --compact `
       --out data\G01\out\G01_presentation_2026-10-21_compact_v13.pdf
   ```
4. Review: 14 pages, 18 cards, the average coupon on the KPI page matches the sheet's coupons.
   Each product whose weakest name's 1-year low sits at or below its protection goes into the open
   points, with both levels.
5. Hand over the link, the audience line, the open points, and the swap test's one suggestion
   (an alternative worth pricing, not a change to the proposal).

**Cross-asset.** "Proposal for C-0042: 50% equities, 35% bonds, 10% gold, 5% cash, here is the list
and our house view PDF."

1. Type and objective are given; ask length and format. PowerPoint is the only cross-asset format;
   compact has no effect (the deck follows the positions).
2. Write `data/O01/in/O01_case_C-0042_proposal.json` (`"type": "portfolio_proposal"`, weights,
   strategic allocation, benchmark); `--news` on the largest names; quote three house-view lines as
   `research` (one `about: "market"`); three summary messages; risks, opportunities, next steps.
3. Build: `.\.venv\Scripts\python apps\O01\O01_run.py data\O01\in\O01_case_C-0042_proposal.json --preview --out data\O01\out\O01_portfolio_proposal_C-0042_<date>.pptx`
4. Review: weights sum to 100%, the gap to the strategy, the back-test against the benchmark,
   QC clean; hand over with the sources used.

## Not for

- Weekly market updates and *The Week in 7 Charts* (separate skills).
- Charts only, with no deck: use `syz-proposal-charts`.
- A weekly Investment Solutions deck, a product idea (TARF, autocall, floater, fund) built from
  research, or an existing deck to restyle and restructure: use `syz-investment-solutions`.
- A one-page technical review of a stock or a currency pair (exit / hold / buy, levels,
  catalysts): use `syz-technical-review`.
- A single-product client fact sheet: use the Advisory Workbench's *Term Sheet › Fact sheet*
  (`apps/G01`, browser), which builds it from a LYNQS or Visibility quote.
