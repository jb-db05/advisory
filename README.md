# advisory

## Reoffer trade register

Replaces manual entry into the Reoffer Excel file with one repeatable step:

```
drop files in workspace/inbox  →  python -m reoffer run  →  register + reports updated
```

### What it does on every run

1. **Reads any format.** It accepts Excel (any sheet, any header row), CSV (`;` or `,`, Swiss or US
   number formats, title lines above the table) and HTML confirmations. It finds the columns by
   name, so `Notional`, `Ccy`, `Client ID`, `Mandate` and truncated headers like `Currenc` all work.
2. **Fixes what is safe to fix, and logs each fix:**
   - `ubs` becomes `UBS`, `GS` becomes `Goldman Sachs` and `BRC` becomes `Barrier Reverse Convertible` (aliases).
   - `Goldmann Sachs` becomes `Goldman Sachs` (close spelling, only when one name clearly matches).
   - `130'000`, `1.5m` and `1,84%` are read correctly. `1.84` and `0.0184` are both read as 1.84%.
   - A missing fee amount is calculated as `Size × Fees (%)`.
3. **Refuses what would need a guess, and says why.** This covers bad ISIN check digits, unknown
   RMs, issuers or regions, empty required fields, fee amounts that don't match `Size × Fees (%)`
   with no comment, future dates and duplicates (same date, ISIN, nclidos and size).
4. **Appends** accepted rows to `workspace/register.xlsx` with a trade ID, the source file and the import date.
5. **Rebuilds** `workspace/output/reoffer_report.xlsx`. It contains a summary, breakdowns by month,
   issuer, RM, region, currency, management style, pay-off and APL, an RM × month grid and the full
   data with CHF columns.

Refused rows go to `output/exceptions_<time>.xlsx`, which uses the same columns as the input plus the
reason. Correct the rows in that file, save it into `inbox/` and run again.

### Setup (once)

```bash
pip install -r requirements.txt
```

```bash
python -m reoffer template
```

This writes `workspace/reoffer_input_template.xlsx`. Its dropdowns come from the reference lists
and it includes the fee formula. Use it for anything typed by hand.

### Daily use

On Windows, double-click `run_reoffer.bat`. On a Mac, double-click `run_reoffer.command`.
From a terminal:

```bash
python -m reoffer run
```

To check a file without importing it:

```bash
python -m reoffer check some_file.csv
```

To migrate the existing Reoffer workbook, run it once on that file. The reference block in rows
2–22 is skipped automatically.

```bash
python -m reoffer run "Reoffer 2026.xlsx"
```

### Reference data: `reoffer/reference/` (edit in Excel)

| File | Purpose |
|---|---|
| `lists.csv` | Allowed values per field: issuer, payoff, currency, apl, rm, region, management_style. **Fill in `rm` and `region`.** A field with no values is not checked. |
| `aliases.csv` | Shorthand and common misspellings mapped to the right value. |
| `fx_rates.csv` | CHF per 1 unit of currency. The latest rate on or before each trade date is used. **The rates in it are placeholders.** Add month-end rates. |

The client data in `workspace/` is git-ignored and never committed.

### Tests

```bash
python -m pytest -q
```
