# The basket sheet

Read when a sheet does not parse, or when you write one from a table pasted in chat.

## Columns

The header row starts with `Basket` (or `Product`, `#`). Columns are found by the start of their name,
in any order; others are ignored. Rows whose first cell is not a number (totals, blanks) are skipped.

| Column | Read as | Example |
| --- | --- | --- |
| `Basket` | number; the PDF renumbers 1 to n in sheet order | `9` |
| `Underlying 1`, `Underlying 2`, ... | names as the desk writes them | `JP MORGAN` |
| `Coupon` | % p.a. | `8.00%` |
| `Downside protection` (or `Protection`, `Strike`, `Barrier`) | level, with optional wording | `70.00%`, `European barrier 65%`, `Low strike 72%` |
| `Maturity` (or `Tenor`) | months or years | `15 months` |
| `Fees` | % | `1.50%` |
| `Amount (€)` (or `Size`, `Nominal`) | amount; the sign in brackets gives the currency | `€ 50’000.00` |
| `Theme` | optional theme per basket | `Global banks` |
| `Currency` | optional, overrides the header | `CHF` |
| `Weight` | used for the average coupon when there are no amounts | `10%` |

```csv
Basket,Underlying 1,Underlying 2,Underlying 3,Coupon,Downside protection,Maturity,Fees,Amount (€)
1,NIKKEI 225,EURO STOXX 50,S&P 500,7.00%,67.00%,18 months,1.50%,65000
3,ALPHABET,AMAZON,MICROSOFT,8.00%,75.00%,18 months,1.50%,50000
```

## Themes file

```json
{"1": "Global equity core", "3": "Digital platforms", "5": "AI semiconductors"}
```

Keys are the sheet's basket numbers (the renumbered ones also work). Two to five words each.

## Tickers file

```json
{"ASML": "ASML.AS", "ROCHE": "RO.SW", "VAT": "VACN.SW"}
```

Keys are the names exactly as written. Without it, names are matched by the built-in table (indices,
ETFs, the desk's usual names), then the Core List, then Yahoo search. The tables show Bloomberg codes
derived from the symbol: `ASML.AS` → ASML NA, `SIE.DE` → SIE GY, `RO.SW` → RO SW, US shares by
exchange (UW Nasdaq, UN NYSE), indices as `NKY Index`, `SX5E Index`, `SPX Index`.
