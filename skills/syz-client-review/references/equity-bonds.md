# Equities and bonds: analysis and charts

Read this when a deck covers single stocks, ETFs, indices, bonds or bond funds, or when the user asks for a chart of an equity or an underlying.

## Contents
- Equity and underlying charts (yfinance)
- Equity analysis
- Bond analysis
- Funds and ETFs

## Equity and underlying charts (yfinance)

```bash
pip install yfinance            # once per session; the generator falls back to its own Yahoo client otherwise
python scripts/o01.py --chart NVDA PANW --vs ^GSPC --period 1y --png
```

- One deck, two slides per symbol: (1) unadjusted price with 50- and 200-day simple moving averages and a facts table (last close, 52-week range, distance to the averages, return, volatility, drawdown, market cap, P/E, dividend yield, analyst target with implied upside); (2) total return against the benchmark, rebased to 100, with beta and correlation.
- `--png` also writes a PNG per symbol in the SYZ style (needs matplotlib, available on claude.ai) — for an email or a chat answer.
- Periods: 6m, 1y, 2y, 3y, 5y. Benchmarks: `^GSPC` S&P 500, `^NDX` Nasdaq-100, `^SSMI` SMI, `^STOXX50E` Euro Stoxx 50, `^GDAXI` DAX, `^FTSE` FTSE 100, `^N225` Nikkei 225, `URTH` MSCI World ETF, `ACWI`, `EEM`.
- The same pages work for a structured product's underlying: pass its Yahoo symbol (shown by `--terms`).
- Yahoo symbols: Swiss `NESN.SW`, German `SAP.DE`, Paris `MC.PA`, London `SHEL.L` (GBp), Tokyo `6370.T`, Hong Kong `0700.HK`, Australia `LYC.AX`.

## Equity analysis

| Figure | Definition used | Read it as |
| --- | --- | --- |
| Total return | adjusted closes, first to last of the window | what an investor earned incl. dividends |
| Volatility | annualised st. dev. of daily log returns (× √252) | 20 % is a typical large cap; > 40 % is high |
| Max drawdown | worst peak-to-trough fall in the window | the pain an investor actually went through |
| Beta | cov(stock, bench) / var(bench), daily log returns | > 1 amplifies the market |
| Correlation | of daily log returns | < 0.5: the benchmark explains little of the moves |
| vs 50 / 200-day average | last close / average − 1 | above the 200-day: long-term uptrend; a 50-day cross is a momentum signal, not a forecast |
| 52-week position | last / 52-week high − 1 | how far from the recent peak |
| P/E trailing / forward | price / past or expected EPS | compare with the sector and the stock's own history, not in isolation |
| Analyst target | mean consensus target (third-party) | implied upside; always attribute, never present as SYZ's view |

For a worst-of basket, compare the underlyings' volatilities and their correlation: high volatility and low correlation are why the coupon is high, and why the risk is.

## Bond analysis

The client review's bond slide uses direct bond positions with a maturity and a price or yield (CSV columns `coupon`, `maturity`, `price` / `ytm`, `duration`, `rating`).

| Figure | How | Note |
| --- | --- | --- |
| Yield to maturity | solved from price, coupon, maturity (annual coupons) when not given | clean price used as dirty: accrued interest ignored — say so if precision matters |
| Modified duration | Macaulay / (1 + y) | price change ≈ −duration × change in yield |
| Convexity | second-order term | matters for long durations and large rate moves |
| +1 % in yields | ≈ −modified duration × 1 % | first-order estimate shown on the slide |
| Maturity ladder | weights by maturity year | clusters = reinvestment risk at one date |
| Credit | rating, issuer, seniority | concentration by issuer; sub-investment grade below BBB− |

Messages that matter: portfolio yield vs the reference currency's government curve (the spread paid for credit), duration vs the client's horizon and rate view, maturities to reinvest in the next 12 months, issuer and rating concentration, currency of bonds not in the reference currency (hedged or not).

## Funds and ETFs

The fund page uses Yahoo fund data (via yfinance when installed): family, category, legal type, expense ratio, turnover, asset mix, top holdings, returns vs the category average. Check fees against the KID / factsheet; flag overlap between a fund's top holdings and direct positions (hidden concentration).
