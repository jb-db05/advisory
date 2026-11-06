---
name: syz-sp-quick-proposal
description: Builds a quick SYZ structured products proposal, a short one-year PDF from a basket sheet. Page 1 gives the headline figures (average coupon, total amount, maturities, protection levels) and one row per basket with theme, underlyings, coupon, protection, tenor, amount and a gauge of each underlying's lowest close of the past year against the protection; above 8 baskets the rows turn compact so about 18 fit on the page. Then two baskets per page with a one-year chart rebased to 100 and a table per underlying (Bloomberg code, last close, protection price, 1y low, 1y change, volatility). Use when asked for a quick SP proposal, a 1y PDF or one-year view of baskets, a basket proposal from an Excel table (Basket, Underlying 1-3, Coupon, Downside protection, Maturity, Fees, Amount), or to redo such a PDF with other baskets, numbers or themes.
---

# SYZ quick structured product proposal

A bundled Python script turns a basket table into a short client PDF in the SYZ style. Your job:
get the table, add the themes, run the script, check, hand over. Every figure is read from the table
or calculated from one year of Yahoo Finance closes; never type one in.

## Visual identity

Follow [references/visual-guidelines.md](references/visual-guidelines.md) (Syz Visual Guidelines,
May 2024) for the logo, colours, typography, icons, boxes and page layout. It does not cover
charts: keep this skill's own chart rules. Where this skill's template or spec already fixes a
layout, that wins; use the guidelines for everything else. Its "Open points" list where the
guidelines and current house practice differ: keep current practice on those until the team decides.

## When to use

- "Could you create a 1y PDF" with a table of baskets, coupons, protection, maturity, fees, amounts.
- "Quick proposal for these six baskets", "same PDF with 15 baskets", "renumber and redo it".

Do not use it for: the full 14-page portfolio proposal with principles, stress and issuers
(`syz-sp-full-proposal`), a single stock's technical view (`syz-technical-takes`), a review of
products already held (`syz-client-review`).

## Where to run it

| Where | Command |
| --- | --- |
| Claude Code, in this repository | `python skills/syz-sp-quick-proposal/scripts/quick_proposal.py <sheet> [options]` |
| claude.ai (skill uploaded) | `python scripts/quick_proposal.py /mnt/user-data/uploads/<sheet> [options]` from the skill folder |

Dependencies: `pip install -r scripts/requirements.txt`. The PDF is printed by Playwright when
installed, otherwise Chrome or Edge in headless mode; without one the script says so and the HTML
next to the PDF can be printed from any browser.

Options: `--themes FILE` theme per basket. `--tickers FILE` checked symbols. `--title TEXT`
(default "Six thematic baskets"). `--currency CCY` when the sheet does not say (the `Amount (€)`
header gives EUR). `--asof YYYY-MM-DD`. `--out FILE`. `--offline`.

## Instructions

1. **Get the table.** An Excel or CSV file, or a table pasted in chat: write it to a CSV in the format
   of [references/sheet.md](references/sheet.md). Keep the values exactly; a missing coupon or
   protection stops the run: ask for it, never estimate it.
2. **Anonymise.** No client name or account in the sheet or file names.
3. **Themes.** Write `themes.json` with a short theme per basket, keyed by the sheet's basket numbers:
   `{"1": "Global equity core", "3": "Digital platforms"}`. Without it the script uses the sheet's
   Theme column, the Core List theme, or "Global equity indices", and lists the baskets to complete.
4. **Build:**
   ```bash
   python scripts/quick_proposal.py baskets.xlsx --themes themes.json
   ```
   Baskets are numbered 1 to n in the sheet's order (the console shows the old numbers).
5. **Check** the console: every `NAME -> SYMBOL` (a "Yahoo search (confirm)" match must be checked;
   use the listing the product is written on, e.g. `ASML.AS` shown as ASML NA), no `WARNING no prices`,
   and the "Check before sending" list of names whose one-year low was at or below the protection.
   Look at page 1 if you can (render it to an image).
6. **Hand over:** link the PDF; a short table per basket (coupon, protection, the names that went below
   protection); the points to confirm (protection type if the sheet only gives a %, listings, themes
   written automatically); compliance validates before a client sees it.

## Output

`SYZ_quick_proposal_<date>.pdf`, A4: page 1 with the headline figures and the basket rows (airy up to
8 baskets, one line each above), then two baskets per page. Nunito Sans, vector SYZ logo, house
palette, equal 14 mm margins, no boxes or colour fills. The HTML it was printed from sits next to it.

## Rules

- Coupons, protection levels, maturities, fees and amounts come from the sheet. Prices, lows,
  changes and volatility are calculated. Levels assume a strike at today's close; the PDF says so.
- A dot in the pink zone is history, not a backtest or a forecast. Keep the footnote and the
  important information.
- Protection given as a plain % is labelled "Protection"; the words "barrier" or "strike" in the
  sheet give "European barrier", "American barrier" or "Low strike".

## Example

**Input:** "Could you create a 1y PDF" with six baskets numbered 1, 3, 5, 9, 11, 14 (Nikkei/Euro Stoxx/
S&P 500 at 7% and 67%, Alphabet/Amazon/Microsoft at 8% and 75%, ...), EUR 315'000 in total.

**Steps:** sheet saved as `baskets.xlsx`; `themes.json` with the six themes; `python scripts/quick_proposal.py
baskets.xlsx --themes themes.json`.

**Output:** `SYZ_quick_proposal_2026-11-05.pdf`, 4 pages, baskets renumbered 1 to 6. Then:

> 7.56% average coupon, EUR 315k, 12–18 months, protection 65.5–75%. Below protection over the year:
> basket 2 Microsoft 63% (75%), basket 3 ASML 64% (65.5%), basket 5 Siemens 73% (75%), basket 6
> Eli Lilly 60%, McKesson 68%, Roche 69% (74%). To confirm: low strike or barrier for each basket.

## Additional resources

- [references/sheet.md](references/sheet.md): the columns read, a CSV example, the themes and tickers
  files. Read when a sheet does not parse or you write one from a pasted table.
