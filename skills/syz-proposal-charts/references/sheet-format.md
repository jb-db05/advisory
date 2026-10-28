# Proposal sheet format

Read this when a CSV does not parse, when you turn a list pasted in the chat into a sheet, or when
you need to write a tickers file.

## Columns

The script looks for a header row whose first cell is `Basket`. It then reads these columns by
name, case-insensitively and in any order. Only `Basket`, the `Underlying` columns and
`Downside protection` are required. The others may be missing or empty; the charts are the same,
and the missing terms show as `–`. Extra columns (e.g. `Taille`) are ignored. Commas, semicolons
and tabs all work as separators.

| Column | Read as | Example |
| --- | --- | --- |
| `Basket` | product number 1, 2, …; or `CASH` for the cash line | `3` |
| `Underlying 1`, `Underlying 2`, `Underlying 3` | names as the desk writes them; empty cells are skipped | `ALPHABET` |
| `Coupon` | % p.a. | `8.00%` |
| `Downside protection` | the protection wording (below) | `Low strike 72%` |
| `Maturity` | months | `18 months` |
| `Weight` | % of the proposal | `6%` |
| `Fees` | % | `1.50%` |
| `Stepdown` | free text, shown as an "Autocall step-down" chip | `100%→98%→…→84%` |
| `Size` | amount; currency signs, `’` and `,` thousands separators are fine | `€ 624’000.00` |

Rows whose first cell is neither a number nor `CASH` (totals, blanks) are ignored. The sheet may
start with empty rows.

## From a list pasted in the chat

A table copied from Excel arrives tab-separated. If its header row starts with `Basket`, save it
unchanged as `proposal.txt` and build from that.

A looser list becomes a CSV with the header below, one row per product, the values copied exactly
as written:

```text
1. Nikkei 225 / Euro Stoxx 50 / S&P 500 — 7% — European barrier 65% — 18 months — 10%
2. Alphabet, Apple, Microsoft: low strike 72%, coupon 8%, 18m
```

becomes

```csv
Basket,Underlying 1,Underlying 2,Underlying 3,Coupon,Downside protection,Maturity,Weight,Fees,Stepdown,Size
1,Nikkei 225,Euro Stoxx 50,S&P 500,7.00%,European barrier 65%,18 months,10%,,,
2,Alphabet,Apple,Microsoft,8.00%,Low strike 72%,18 months,,,,
```

- Number the products as the user did, or 1, 2, … in the order given.
- A basket with more than three names gets `Underlying 4`, `Underlying 5` columns.
- Write the protection in one of the wordings below. "Barrier 65%" with no type means a
  barrier observed at maturity only if the user said so; otherwise ask whether it is European or
  American.
- Leave a cell empty when the user did not give the value. Never fill a coupon, size or weight in.

## Protection wording

| Written | Strike | Barrier | Protection level drawn |
| --- | --- | --- | --- |
| `European Barrière 65%` / `European barrier 65%` | 100% | 65%, observed at maturity | 65% |
| `American barrier 60%` | 100% | 60%, observed during the life | 60% |
| `Low strike 72%` | 72% | none | 72% (the strike) |

Anything else is drawn with a 100% strike and no barrier; tell the user it was not understood.

## Names and tickers

Names are matched in this order:

1. The tickers file (`--tickers`).
2. A built-in table of common indices: Nikkei 225, Euro Stoxx 50, S&P 500, SMI, DAX, FTSE 100,
   Hang Seng, OMX Stockholm 30, CAC 40, Nasdaq 100, Russell 2000.
3. Fixes for names that are often mismatched: TSM, JP Morgan, Roche → `ROP.SW`, the Genussschein.
4. In the SYZ Advisory workspace only, the Core List. Otherwise, Yahoo search.

Write a tickers file for every name the run printed with a wrong or missing symbol. Keys are the
names exactly as written in the sheet:

```json
{"VAT": "VACN.SW", "TSM": "TSM", "ROCHE": "ROP.SW", "ABBN": "ABBN.SW"}
```

A two-column CSV (`SHEET NAME,SYMBOL`, no header) works too. Use the line the products are
written on, which is usually the home listing: `ASML.AS` rather than `ASML` for a EUR product.
Indices use Yahoo's `^` codes.
