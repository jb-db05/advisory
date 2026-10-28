# Routing: which engine for which request

Read after the four questions are answered. Commands run from the workspace root with
`.\.venv\Scripts\python`. `<sheet>` is the SP proposal sheet, `<tickers>` the checked-symbols JSON,
`<story>` the themes JSON (default `data/G01/in/G01_presentation_themes.json`), `<case>` an O01
case file.

## Structured products

| Objective | PDF | Word | PowerPoint |
| --- | --- | --- | --- |
| Proposal overview | **G01 deck**, full or `--compact` | **G01 Word**, full only | not available: offer PDF or Word |
| Review of an existing proposal (not yet bought) | **G01 deck** on the original sheet, today's prices | **G01 Word**, full only | not available: offer PDF or Word |
| Review of products now held (have fixings, term sheets, positions) | not available: offer PowerPoint | not available: offer PowerPoint | **O01 `sp_review`** |
| New investment idea | **G01 deck** on a one-to-three-product sheet | **G01 Word**, full only | not available: offer PDF or Word |

Compact applies to the G01 PDF only. For compact Word, offer the full Word document (sections can be
deleted in Word) or the compact PDF. The O01 deck has no length switch: its length follows the
products held. Say so if the user asked for compact.

How to tell the two reviews apart: a proposal that was only presented has no initial fixing.
Products that were bought have an ISIN, a fixing date and initial levels in a term sheet or
positions extract. Ask if unclear.

## Cross-asset

| Objective | PDF | Word | PowerPoint |
| --- | --- | --- | --- |
| Proposal overview (a new allocation) | not available: offer PowerPoint | not available: offer PowerPoint | **O01 `portfolio_proposal`** |
| Review of the client's portfolio | not available: offer PowerPoint | not available: offer PowerPoint | **O01 `client_review`** (structured products held get their own pages) |
| New investment idea (one to three positions) | not available: offer PowerPoint | not available: offer PowerPoint | **O01 `portfolio_proposal`** with those positions, or `--chart` slides for a single stock |

The O01 decks have no length switch: one page per spotlighted stock or fund, plus the allocation,
concentration, performance and assessment pages. For a shorter deck, spotlight fewer positions.
The advisor can save the PowerPoint as PDF; do not build a PDF another way.

A cross-asset proposal that includes structured products: list each SP as one holding (asset
class `Structured products`, weight, no symbol). For their detail, build the SP proposal with G01
alongside, and say so.

## Commands

### G01 thematic deck, PDF

```powershell
.\.venv\Scripts\python apps\G01\G01_presentation.py <sheet> --tickers <tickers> --themes <story> `
    [--compact] --out data\G01\out\G01_presentation_<date>[_compact]_vN.pdf
```

- **Full**, about 26 pages: cover; executive summary (KPIs, theme families, three messages);
  protection; approach; coupons and issuers; vol-vs-correlation map and summary table; one page
  per product (case, why this basket, chart, underlyings with consensus, correlation matrix,
  coupon and ten-year replay); disclaimer; closing page.
- **Compact**, about 14 pages for 18 products: cover; executive summary; one portfolio table
  (with each product's weight); protection; thematic rationale; three product cards per page;
  coupons, shock scenarios and issuers; disclaimer; closing page.

### G01 thematic deck, Word

```powershell
.\.venv\Scripts\python apps\G01\G01_presentation_word.py <sheet> --tickers <tickers> --themes <story> `
    --out data\G01\out\G01_presentation_<date>_vN.docx
```

This is the full content as editable text; the charts are pictures. It opens an Edge window for a
few seconds and needs internet access for pdf.js. Warn the user before running it.

### O01 PowerPoint (SP review, client review, cross-asset proposal)

```powershell
.\.venv\Scripts\python apps\O01\O01_run.py --ingest <files…> --client C-0042 --as-of <date> --currency <CCY>
.\.venv\Scripts\python apps\O01\O01_run.py --news <SYMBOL> <SYMBOL> …
.\.venv\Scripts\python apps\O01\O01_run.py <case.json> --preview --out data\O01\out\O01_<type>_C-0042_<date>_vN.pptx
```

`--ingest` drafts the case file from term sheets and positions (reviews). For a cross-asset
proposal, write the case file directly from `data/O01/in/O01_case_proposal_sample.json`. Then follow
`.claude/skills/syz-client-presentations/SKILL.md` steps 2–7: check the terms, complete the case
file, research and write the messages, run QC.

- **`portfolio_proposal`**, about 9 to 12 slides: cover; agenda; summary (asset classes, positions,
  top-5 weight, effective positions, 12-month back-test; key messages and the market view);
  allocation vs the strategy; largest positions, currencies, regions; back-test vs the benchmark
  with each position's return, vol and drawdown; one page per spotlighted stock or fund (with its
  research view); why this allocation (risks, opportunities, next steps); sources and open points;
  disclaimer; offices.
- **`client_review`**: the same pages on the portfolio as held, with its value; plus a bond page
  and the structured products held.
- **`sp_review`**: summary; status of each product; issuer, type and underlying exposure; two pages
  per product (terms and payoff; performance since fixing with its research view); scenarios;
  assessment; sources and open points.

## Inputs each engine needs

| Engine | Required | Optional |
| --- | --- | --- |
| G01 deck / Word | Sheet with, per product: underlyings, coupon, protection, maturity. Tickers JSON for every name. Story file covering every product number | `Issuer` column (empty = TBD), `Stepdown`, a `CASH` row |
| O01 `sp_review` | Terms per product (term sheet, factsheet or pricer page), a pseudonym, an as-of date, a currency | Positions extract, research, price files |
| O01 `client_review` | Holdings with values (or weights) and asset classes, a pseudonym, an as-of date, a currency | Benchmark, strategic allocation, research, bond details, products held |
| O01 `portfolio_proposal` | Holdings with weights and asset classes, a pseudonym, an as-of date, a currency | Benchmark, strategic allocation (the client's profile), research, spotlights |

For an **SP new investment idea**, write the sheet yourself from the idea, in the format of
`.claude/skills/syz-proposal-charts/references/sheet-format.md`: one row per product, values
copied exactly. The coupon must come from an issuer quote, a term sheet or the user. If the quote
is a saved LYNQS or Visibility page, the Workbench's *Term Sheet* tab reads it. With no coupon, stop
and ask; the income figures would otherwise be wrong.
