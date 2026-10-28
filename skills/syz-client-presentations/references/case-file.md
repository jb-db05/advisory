# Case file reference

Read this when writing or editing a case file. One JSON file per deck, saved next to the factsheets (on claude.ai a working folder such as `/tmp/case/`, in the workspace `data/O01/in/`). HTML paths inside it are relative to the case file, or absolute (e.g. `/mnt/user-data/uploads/factsheet.html`).

## Common fields

| Field | Required | Meaning |
| --- | --- | --- |
| `type` | yes | `sp_review`, `client_review` or `portfolio_proposal` (cross-asset proposal) |
| `client` | yes | Pseudonym, e.g. `C-0042`. Appears on the cover and in the file name. Never a real name. |
| `as_of` | yes | ISO date. Market data is cut at this date, so an older deck can be rebuilt as it was. |
| `currency` | yes | Reporting currency (`CHF`, `EUR`, `USD`). Weights and portfolio performance are in it. |
| `title` | no | Cover title. Defaults to the deck type's name. |
| `fx` | no | `{"USD": 0.83}` = units of the reporting currency per unit. Overrides Yahoo FX (state the source in the messages if it is the custody statement's). |
| `messages` | no | `summary`, `risks`, `opportunities`, `next_steps`: lists of short sentences, see writing.md. |
| `titles` | no | Override a computed takeaway (the line under the title, one short line): keys `summary`, `overview`, `allocation`, `concentration`, `performance`, `bonds`, `scenarios`, `assessment`, a product `label` (its terms page) or `label + " performance"`, or a Yahoo symbol for its spotlight page. |
| `research` | no | Research quoted on the slides: `[{"about": "NESN.SW", "text": "One sentence.", "source": "Syz house view", "date": "Oct 2026"}]`. `about` is a symbol, Bloomberg ticker, name, product label or ISIN (or a list of them), or `market` for the summary's market view. Without `source` an item is not shown; one that matches nothing is an open point. |
| `inputs` | no | Files of any format (PDF, HTML, CSV, Excel) read at build time like `--ingest`: positions → `holdings`, term sheets → `products`, price tables → `prices`. What the case file states itself wins. |
| `prices` | no | Price files (CSV / Excel, long `date,symbol,close[,adj_close]` or wide: a date column and one column per symbol), used where yfinance / Yahoo has no data. |

`--ingest` writes a draft with all of these filled from the uploads; complete it rather than starting from scratch.

## `sp_review`

```json
{
  "type": "sp_review", "client": "C-0042", "as_of": "2026-10-14", "currency": "CHF",
  "products": [
    {"source": {"html": "O01_factsheet01.html"}, "nominal": 250000, "currency": "USD"},
    {"source": {"html": "pricer_bank_b.html"}, "nominal": 300000, "currency": "CHF",
     "terms": {"barrier_type": "european"}},
    {"label": "RC on Euro Stoxx 50", "nominal": 150000, "currency": "EUR",
     "terms": {"issuer": "Bank C", "isin": "XS0000000000", "product_type": "Reverse Convertible",
               "coupon": 0.07, "frequency": 12, "strike": 0.9,
               "initial_fixing": "01.12.2025", "final_fixing": "01.12.2026",
               "underlyings": [{"name": "Euro Stoxx 50", "ticker": "SX5E Index", "initial": 5600.12}]}}
  ]
}
```

- `source`: `{"pdf": "termsheet.pdf"}`, `{"html": "factsheet.html"}`, `{"text": "terms.txt"}` or `{"file": "anything"}` (format detected). `terms` next to it **override** what was read (shown as "case file (advisor)").
- Without `source`, `terms` is the whole product. Levels are fractions (`0.6` = 60 %), dates `DD.MM.YYYY` or ISO, `frequency` in months (`0` = in fine).
- Term keys: `isin, issuer, currency, product_type, coupon, frequency, coupon_trigger, memory, strike, barrier, barrier_type (american|european|none), autocall_trigger, first_call_months, stepdown, participation, cap, bonus_level, protection, denomination, settlement, initial_fixing, final_fixing, maturity`.
- `product_type` decides the payoff family: Autocallable / Phoenix / Express, Barrier Reverse Convertible, Reverse Convertible, Discount Certificate (needs `cap`; `strike` = purchase price as % of initial), Bonus Certificate (`bonus_level`, optional `cap`), Capital Protected (`protection`, `participation`, optional `cap`), Twin-Win (`barrier`, `participation`), Tracker, Credit Linked Note (no payoff diagram).
- Underlyings: `name`, `ticker` (Bloomberg, mapped to Yahoo) or `symbol` (Yahoo, wins), `initial` (the fixing level; without it the Yahoo close on the fixing date is used and flagged).
- `label`: the product's short name on the slides; default `issuer coupon tickers`.

## `client_review`

```json
{
  "type": "client_review", "client": "C-0043", "as_of": "2026-10-14", "currency": "CHF",
  "period_days": 365,
  "benchmark": {"symbol": "URTH", "name": "MSCI World (iShares ETF)"},
  "target_allocation": {"Equities": 0.55, "Bonds": 0.30, "Cash": 0.05, "Alternatives": 0.10},
  "holdings": [
    {"name": "iShares Core S&P 500 ETF", "symbol": "IVV", "asset_class": "Equities", "currency": "USD",
     "region": "North America", "value": 900000, "fund_detail": true},
    {"name": "Nestle", "symbol": "NESN.SW", "asset_class": "Equities", "currency": "CHF",
     "region": "Switzerland", "value": 400000, "spotlight": true},
    {"name": "Cash CHF", "asset_class": "Cash", "currency": "CHF", "value": 200000}
  ],
  "products": []
}
```

- `value` in the reporting currency (from the custody statement), or `weight` (fractions summing to 1). With values for every position, weights are recalculated from them (a disagreeing weight column is flagged).
- Direct bonds: add `coupon` (fraction), `maturity` (ISO date) and `price` (per 100) or `ytm`; optional `duration`, `rating`, `frequency` (coupons per year, default 1) → the bond slide.
- No `symbol`? Equities and funds with an `isin` are looked up on Yahoo by ISIN (flagged for checking).
- `asset_class` labels must match `target_allocation` keys exactly to be compared.
- `spotlight: true` → a page for a single stock / ETF (chart vs benchmark, valuation facts). `fund_detail: true` → a fund page (fees, category, holdings, returns vs category).
- `products`: structured products held, in the `sp_review` format — they get an overview table and their product pages.
- Holdings without `symbol` (cash, private assets) count in weights but not in performance; the slide states the share covered.

## `portfolio_proposal` (cross-asset)

The `client_review` format with `weight` instead of `value` (sample: `O01_case_proposal_sample.json`).

```json
{
  "type": "portfolio_proposal", "client": "C-0044", "as_of": "2026-10-14", "currency": "CHF",
  "benchmark": {"symbol": "URTH", "name": "MSCI World (iShares ETF)"},
  "target_allocation": {"Equities": 0.5, "Bonds": 0.35, "Alternatives": 0.1, "Cash": 0.05},
  "holdings": [
    {"name": "iShares Core S&P 500 ETF", "symbol": "IVV", "asset_class": "Equities", "currency": "USD", "weight": 0.2},
    {"name": "Nestle", "symbol": "NESN.SW", "asset_class": "Equities", "currency": "CHF", "weight": 0.1, "spotlight": true},
    {"name": "Cash CHF", "asset_class": "Cash", "currency": "CHF", "weight": 0.05}
  ],
  "research": [{"about": "market", "text": "…", "source": "Syz house view", "date": "Oct 2026"}]
}
```

- No amounts on any slide, even when `value` is given (the weights are then derived from it and an open point says so).
- `target_allocation` is the client's strategic profile; the allocation slide shows the proposal against it.
- Performance is a **back-test** of the proposed weights (labelled so), not a forecast or a track record.
- The assessment slide is titled "Why this allocation"; write `risks`, `opportunities`, `next_steps` for it.
