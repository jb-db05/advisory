---
name: syz-client-presentations
description: Produces client-ready SYZ PowerPoint presentations and charts on the SYZ template - Structured Product Portfolio Reviews, Client Portfolio Reviews, Cross-Asset Portfolio Proposals and equity / underlying chart decks, with short headline titles, clean white slides and research-backed comments quoted with their source. Reads any mix of inputs (PDF term sheets, factsheets and portfolio reports, HTML factsheets and pricer pages, CSV / Excel positions, product lists and price files), detects the format, extracts and validates the terms and positions, uses yfinance / Yahoo Finance for prices, FX and fund data, and applies structured-product, equity and bond analysis - payoff diagrams with barrier, breakeven and autocall, barrier distances, scenarios, yield and duration, allocation and concentration. Use when asked for a structured products review, an SP portfolio deck, a client portfolio review, a payoff chart, stock or underlying chart slides for a deck, or slides built from term sheets, factsheets, a positions extract or a list of holdings. A one-page technical review with a verdict (exit / hold / buy) on a stock or currency is syz-technical-review.
---

# SYZ client presentations

A bundled pure-Python generator builds the decks on the real SYZ template (`assets/S00_template.pptx`). Your job: feed it the inputs, check what it read, write the case file and the messages, review. It computes every figure and refuses to invent missing ones.

**Where to run it.** From this skill's folder (on claude.ai typically `/mnt/skills/user/syz-client-presentations`):

```bash
pip install yfinance openpyxl      # once per session; yfinance is optional, openpyxl required
python scripts/o01.py --sample sp  # setup check: must end with "QC: no issues."
```

In the SYZ Advisory workspace (Claude Code, Windows) use `.\.venv\Scripts\python apps\O01\O01_run.py` with the same options (yfinance cannot be installed there; the built-in Yahoo client is used).

## Workflow

1. **Take whatever the user uploads** (on claude.ai: `/mnt/user-data/uploads/`) and read it all at once:
   ```bash
   python scripts/o01.py --ingest /mnt/user-data/uploads/* --client C-0042 --as-of 2026-10-14 --currency CHF
   ```
   The format is detected from the content, not the extension:

   | Input | What is extracted |
   | --- | --- |
   | PDF term sheet / factsheet / product report | ISIN, issuer, currency, product type, coupon (annualised), strike, barrier and its observation, autocall trigger and schedule, dates, underlyings with Bloomberg → Yahoo symbols and initial levels (checked against the strike), denomination, settlement |
   | PDF portfolio report | position lines carrying an ISIN (flagged: verify) |
   | HTML factsheet / product page / pricer | the same terms from any layout; tables on the page |
   | CSV / TSV / Excel | header row found (preamble skipped), columns mapped in EN / FR / DE, decimal comma and thousands separators detected per file, then classified: **positions** (value / weight / quantity), **product list** (barrier / strike / autocall), **prices** (date + close, long or wide) |
   | Text | terms from pasted term-sheet text |

   It writes a **draft case file** and prints what it found per file and every open point. Product nominals are matched from the positions by ISIN.
2. **Check before writing anything.** Read the report; for any product use `python scripts/o01.py --terms FILE` to see each field's value, `status` and `source`. `missing` / `inconsistent` → ask the user, or set it in the case file's `terms` override (labelled "case file (advisor)"). Never fill a term from memory. See [references/data-sources.md](references/data-sources.md).
3. **Complete the case file** ([references/case-file.md](references/case-file.md)): pseudonym only (`C-0042` — if the user gives a name, replace it and say so), `as_of`, `currency`, type (`sp_review`, `client_review` or `portfolio_proposal` for a cross-asset proposal with weights only), benchmark, strategic allocation, nominals the inputs did not give.
4. **Build**: `python scripts/o01.py <case>.json [--prices prices.csv]`. The first line says which market data was used (yfinance, the stdlib Yahoo client, price files, or factsheet prices only). On claude.ai the `.pptx` and an `.preview.html` go to `/mnt/user-data/outputs/`.
5. **Research**: read the research the user gave, run `python scripts/o01.py --news <SYMBOL> …` on the weakest underlyings and the largest positions, search the web for what drove the big moves. Put each view in the case file's `research` with its source and date (one sentence, ≤ 25 words). See "Research-driven comments" in [references/writing.md](references/writing.md).
6. **Write the messages** (`summary`, `risks`, `opportunities`, `next_steps`) from the printed figures and the research, using [references/analysis.md](references/analysis.md), [references/sp-knowledge.md](references/sp-knowledge.md) and [references/equity-bonds.md](references/equity-bonds.md), in the style of [references/writing.md](references/writing.md): straight to the point, one line each, three per box at most. Rebuild.
7. **Review** against [references/qc-checklist.md](references/qc-checklist.md); fix QC errors (exit code 1) and long-title warnings; resolve or keep visible every open point.
8. **Hand over** the deck (link it), the open points, what to confirm with an issuer, and the research sources used (links).

## Charts of an equity or an underlying

```bash
python scripts/o01.py --chart NVDA NESN.SW --vs ^GSPC --period 1y --png
```

Two slides per symbol (price with 50/200-day averages and facts; total return vs the benchmark with beta and correlation) and, with `--png`, a SYZ-style PNG per symbol. Details: [references/equity-bonds.md](references/equity-bonds.md).

## What each deck shows

- **SP review**: summary KPIs; overview with status (On track / Watch / At risk / Called?); allocation by product type, issuer and underlying; per product the terms with their source, the **payoff diagram** (product with and without barrier event vs the underlying, markers for today, barrier and breakeven) and the early-redemption strip for autocalls, then performance since the initial fixing with barrier / strike / trigger lines; scenarios at maturity; assessment; sources and open points.
- **Client review**: summary; allocation vs strategy; concentration, currency, region; **bond slide** (yield, duration, maturity ladder) when positions carry bond details; performance of the current allocation vs benchmark in the reporting currency; single-security and fund pages; structured products held (as above); assessment; sources and open points.
- **Cross-asset proposal** (`portfolio_proposal`): the client-review pages on the proposed weights, with no amounts; performance is a labelled back-test against the benchmark; the assessment is "Why this allocation".
- **Every deck**: short label titles of one to four words ("Portfolio status", "NESN / NOVN / ZURN"; QC warns above 30 characters) with the takeaway on the line under them in 12 pt ("34 pts above the 70% barrier"), white slides with no filled boxes, figures set off by a short coloured rule, tables at 11–12 pt, chart text at 10 pt, one-line captions. Research shows as **Research view** (product and stock pages) or **Market view** (summary), always with source and date.

## Rules that are never relaxed

- Every number comes from a named source (input file, case file, yfinance / Yahoo, a price file) or is calculated from them; observed, calculated and assumed figures are labelled on the slide.
- Missing data shows as `n/a` and is an open point. Do not look up prices or terms on the web and type them in.
- Barrier and strike monitoring uses **unadjusted** closes; performance uses adjusted closes **in the reporting currency**.
- A product whose autocall condition was met on a past observation is "Called?" until confirmed with the issuer.
- Research is quoted with its source and date, worded as that source's view; never blended into a calculated figure.
- The template's Important Information and offices pages close every deck.
- **Fonts**: Nunito Sans for all text; Nunito Bold for slide titles and for everything on the cover (first) page. No other face (Arial only for bullet glyphs). The renderer sets this and QC fails a deck that breaks it.
- **Font sizes**: titles aside, only 16, 12 and 8 pt (16 for lead lines and key figures, 12 for body text and tables, 8 for notes, sources and chart labels). The renderer snaps every size to this scale and QC fails any other size.

## Example

Request: "Here are the term sheets and the custody extract for client C-0042. Prepare the review as of 14 October."

1. `--ingest` on the uploads → 3 PDF term sheets, 1 HTML factsheet, positions CSV (French headers, 10 rows); nominals matched by ISIN; open point: "initial fixing level of Palo Alto Networks not found".
2. Complete the draft: benchmark `URTH`, strategic allocation from the user, `spotlight` on the largest stock.
3. Build → 19 slides, QC clean; bond slide: yield 2.6 %, duration 3.5; a low-strike autocall 0.4 pts below its 60 % strike.
4. `--news` on that autocall's underlyings and the largest stock; two `research` items with source and date, one `market` line from the house view.
5. Write three summary messages and the risks, rebuild, review, hand over the deck, the open points and the sources used.

Reached through `syz-portfolio-proposal` (the intake for SP and cross-asset presentations) or directly.

## Not for

Weekly market updates and "week in 7 charts" (separate skills), Excel-only exports, and anything that needs a real client name on the slides. A one-page technical review of a stock or a currency pair (verdict, levels, catalysts, PDF) is `syz-technical-review`; structured-product baskets against strike and barrier are `syz-proposal-charts`; an Investment Solutions deck from research or an old deck to restructure is `syz-investment-solutions`.
