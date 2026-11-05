# Inputs

Read when an input does not parse, a field is missing, or you write a sheet from typed baskets.

## Proposal sheet (Excel or CSV)

The tool looks for a header row whose first cell is `Basket` (or `Product`, `#`) and reads columns by
name, case-insensitively, in any order. Unknown columns are ignored.

| Column | Read as | Example |
| --- | --- | --- |
| `Basket` | product number; `CASH` for the cash line | `3` |
| `Underlying 1`, `Underlying 2`, ... | names as the desk writes them; empty cells skipped | `ALPHABET` |
| `Coupon` | % p.a. | `8.00%` or `0.08` |
| `Downside protection` | `European Barrière 61.31%`, `American barrier 60%`, `Low strike 72%` | |
| `Barrier`, `Strike` | alternative to `Downside protection` | `65%` |
| `Maturity` | months, or years | `18 months`, `1.5y` |
| `Weight` | share of the model portfolio | `6%` |
| `Stepdown` | autocall step-down wording | `100%→98%→96%→…→84%` |
| `Issuer` | short or full name; empty = TBD | `Société Générale` |
| `Currency`, `ISIN`, `Theme`, `Initial fixing`, `Final fixing` | optional | |

Without a `Weight` column the invested part is split equally. Rows whose first cell is neither a
number nor `CASH` (totals, blanks) are skipped.

```csv
Basket,Underlying 1,Underlying 2,Underlying 3,Coupon,Downside protection,Maturity,Weight,Stepdown,Issuer
CASH,,,,,,,10%,,
1,NIKKEI 225,EURO STOXX 50,S&P 500,7.00%,European Barrière 62%,18 months,30%,,JPMorgan
2,ASML,NVIDIA,,8.00%,Low strike 64%,15 months,20%,100%→98%→96%→…→84%,
```

A fictional sheet to try the tool: `assets/samples/proposal_sample.csv`.

## Term sheets (PDF) and pricer pages (HTML)

Both are turned into text and read by the same parser. One document = one product. Fields read:

| Field | Typical wording found |
| --- | --- |
| Coupon | `Coupon Rate 20.70% p.a.`, the title `9.00% p.a. ... on A, B, C` |
| Protection | `Strike Level (60.00%)`, `Barrier Level 60 %`, `Barrier Type American`, `European (at maturity only)` |
| Autocall | `Autocall Trigger Level 100%`, the observation table (a step-down when levels vary) |
| Dates | `Initial Fixing Date`, `Final Fixing Date`, `Redemption Date` (dd/mm/yyyy, dd.mm.yyyy, 20 January 2026) |
| Maturity | months between the fixing dates |
| Issuer | `Issuer` line, shortened (`Banque Internationale à Luxembourg` → `BIL`) |
| Currency | `Settlement Currency`, `Currency`, `issued in USD` |
| ISIN | first valid ISIN |
| Underlyings | Bloomberg codes (`NVDA UW`, `NESN SW Equity`, `SX5E Index`) with the name and initial level on the same line; names from the title when the counts match |

When the table has a market-price column before the initial level (pricer pages), the header decides
which number is the initial level.

## ZIP of term sheets

A `.zip` is unpacked into its own temporary folder; the PDF, HTML, Excel and CSV files inside are read
like any other input (folders inside the archive are ignored).

## Excel and term sheets together

Each term sheet is matched to one Excel row: by ISIN when the Excel has an `ISIN` column, otherwise by
the same set of underlyings (after symbol matching). Then:

- the Excel's coupon, strike, barrier, step-down and names are kept; when the term sheet's coupon
  differs, the console says so;
- the term sheet fills the issuer, currency, ISIN, product type, fixing and redemption dates, the
  maturity, and each underlying's Bloomberg code and initial level;
- a term sheet that matches no row is added as a new product after the Excel's last number.

## Basket coupon

`--coupon 8%` gives 8% p.a. to every product still without a coupon; `--coupon 3=7.5%` sets product 3
(and replaces a coupon read from the documents, with a console line). Repeat the option for several
products. The source shows as "given by the user" in the products file.

## Symbols

Order: `--tickers` file, the Bloomberg code in the document, the built-in table (indices, ETFs and the
desk's usual names), the Core List (`assets/core_list.csv`), Yahoo search (printed "confirm").

```json
{"ROCHE": "RO.SW", "ASML": "ASML.AS", "VAT": "VACN.SW"}
```

Keys are the names exactly as written. Use the listing the product is written on (`ASML.AS` for EUR).

## The products file

Every run writes `<output>_products.json`: one record per product with all fields and `sources`
(`document`, `sheet`, `market data`, `calculated from the fixing dates`, `missing`). Correct a field
there and rebuild with `--products FILE` (same `--asof` and `--story`).
