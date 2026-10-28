# Data sources and extraction

Read this when a `--terms` check shows missing or inconsistent fields, when a price series is missing, or before adding a new source format.

## HTML factsheets and pricer pages (`syz_advisory.decks.sources`)

The reader does not depend on one layout. It collects label/value pairs from:

- elements whose class contains `label`/`header`/`key`/`name`/`title` followed by an element whose class contains `value`/`main-content` (platform product pages);
- `<dt>`/`<dd>` pairs (term summaries);
- two-cell table rows (`<th>`/`<td>` or `<td>`/`<td>`);
- `Label: value` lines in the visible text.

Labels are matched to terms by the patterns in `LABELS` (e.g. "Coupon Rate", "Barrier Level", "Initial Fixing Date"). Underlyings are read from any table row carrying a Bloomberg ticker (`(NVDA UW Equity)`, `SX5E Index`); the initial level only from a column whose header names "initial".

Then it cross-checks with the B01 (Merle) term-sheet text extractor and validates:

| Check | Result |
| --- | --- |
| Two readings of a term disagree | `inconsistent`, both readings in the note |
| ISIN check digit wrong | `inconsistent` |
| Barrier above strike, strike outside 20–150 %, coupon outside 0–40 % | `inconsistent` |
| Final fixing not after initial fixing | `inconsistent` |
| Term not found | `missing` (value stays empty) |
| Coupon quoted per period | annualised with the frequency, `calculated`, with the arithmetic in the note |
| Ticker on an exchange the map does not know | no Yahoo symbol, flagged; nothing is charted for it |

Fixing a miss, in order of preference:
1. The page states it but under another label → read the value off the page (`--terms` prints every source snippet), confirm it with the user, and put it in the case file's `terms` override. In the SYZ Advisory workspace, add the label's pattern to `LABELS` in `src/syz_advisory/decks/sources.py` instead, with a fixture test.
2. The page does not state it → ask the user for the term sheet (PDF) or the value, and put it in the `terms` override.
3. Never type a value you have not seen in a source.

## PDF term sheets, factsheets and reports (`syz_advisory.decks.inputs`)

Text is extracted with pypdf (bundled). Then:

- The B01 (Merle) term-sheet rules — tuned on 65 issuer term sheets (BIL, SG, JPM, BofA, Leonteq, Raiffeisen, EFG, BNP, Citi…) — read ISIN, issuer code, currency, product type, coupon (annualised from per-period wording, flagged), initial and final fixing, frequency, strike, settlement, underlyings.
- Label patterns add barrier (+ American / European from the wording), coupon trigger, memory, participation, cap, bonus level, capital protection, denomination.
- Autocall: the issuer's observation schedule when the sheet lists it (dates and trigger levels, step-downs), else the trigger level, including SG's "Performance(i) ≥ 0 %" convention, and the non-call period.
- Underlyings: Bloomberg ticker found even when the PDF glues ticker and exchange together ("MPUNNYSE"), mapped to Yahoo; the initial level is taken only when another price on the row matches it times the strike / barrier / trigger (that is the check).
- Measured on the 65 reference sheets: ISIN, issuer, currency, type, dates 65/65; coupon 62; strike 64; trigger 53 (the rest have no autocall); symbols 65; initial levels 34 (the others fall back to the market close on the fixing date, flagged).
- A scanned PDF has no text: the reader says so; ask for the term sheet's text or type the terms.
- A portfolio report PDF: only lines carrying an ISIN and amounts are read, flagged for checking — prefer the custody CSV / Excel extract.

## CSV, TSV and Excel

- The header row is found among the first 40 rows (preamble lines such as "Portfolio 900001" are skipped); columns are mapped from English, French and German names (`Libellé`, `Valeur (CHF)`, `Poids`, `Échéance`, `Bezeichnung`, `Marktwert`…). Unmapped columns are reported.
- Delimiter (`,` `;` tab `|`) and the decimal mark are detected per file, so `2,125` reads as 2.125 in a file that writes `80,50`, and as 2125 in one that writes `1,250.00`.
- Percent columns are decided per column (a `%` in the header or a cell, weights summing past 150 %, coupons above 1.5).
- Totals and section rows without amounts are dropped; asset classes are normalised (Actions → Equities, Obligations → Bonds, Liquidités → Cash, Produits structurés → Structured products) or inferred from the name and flagged.

## Which market data is used

The build prints its choice on the first line:

| Situation | Market data | What the deck can show |
| --- | --- | --- |
| yfinance installed and online | yfinance (stdlib Yahoo client for fund returns and as fallback) | everything |
| Sandbox can reach Yahoo Finance, no yfinance | Yahoo Finance via the stdlib client | everything |
| No internet, user uploaded price files (`--prices a.csv b.csv`) | the files | everything except company facts and fund profiles (n/a) |
| No internet, no files | market prices printed on the factsheets | today's worst-of and barrier distance; no charts, no performance, barrier touches unknown — all flagged |

On claude.ai, internet access for code depends on the organisation's settings. If the first line says Yahoo is not reachable, tell the user and offer the price-file route.

**Price file format** (any number of files, one or many symbols each; Excel "Save as CSV" works):

```csv
date,symbol,close,adj_close
2026-03-16,NVDA,183.22,183.22
2026-03-17,NVDA,185.10,185.10
2026-03-16,USDCHF=X,0.8812,
```

- `symbol` must be the Yahoo symbol the deck uses (shown by `--terms`, e.g. `NESN.SW`, `^STOXX50E`); FX as `USDCHF=X`.
- `close` unadjusted (barrier monitoring); `adj_close` optional (performance; defaults to `close`).
- Daily history from the initial fixing (products) or the review period start (portfolios) to the as-of date.
- Sources: Bloomberg / platform exports, the bank's market data — state the source to the user; the deck labels these prices "price file".

## Yahoo Finance (`syz_advisory.marketdata`, standard library only)

| Need | Call | Note |
| --- | --- | --- |
| Barrier / strike monitoring | `Market.prices(symbol, start)` | **Unadjusted** closes (`chart`): levels are set on traded prices |
| Performance, volatility, drawdown | `Market.prices(symbol, start, adjusted=True)` | Dividend- and split-adjusted |
| FX | `Market.fx(ccy, base, as_of)` / `prices("USDCHF=X", …)` | Units of base per unit of ccy |
| Company facts, consensus | `Market.info(symbol)` | P/E, market cap, dividend yield, 52-week range, analyst target |
| Funds / ETFs | `Market.fund(symbol)` | Family, category, expense ratio, holdings, returns vs category |

- Series are cut at the case's `as_of`.
- A disk cache makes `--offline` rebuilds possible within a session; offline, anything not cached is missing (and flagged).
- Symbols: Swiss `NESN.SW`, German `SAP.DE`, London `SHEL.L` (quoted in GBp — returns are unaffected, levels are in pence), indices `^SSMI`, `^STOXX50E`, `^GSPC`. When a symbol has no data (e.g. after a ticker change), find the current one (`from syz_advisory.marketdata import YahooClient; YahooClient().search("Roche")`, run from `scripts/`) and give it as `symbol` in the case file.
- Check the factsheet's initial level against Yahoo's close on the fixing date: a gap above 2 % is flagged — usually the wrong listing, currency or a corporate action.

## Attribution on the slides

Every chart and table carries a caption naming its source and whether it is observed or calculated. The "Sources, method and open points" slide lists all sources, FX rates used and every open point. Do not remove captions to save space; shorten the chart instead.
