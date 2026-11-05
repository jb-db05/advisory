# Review and hand-over

Read before handing over, or when asked how a figure is made.

## How each figure is made

| Figure | Calculation |
| --- | --- |
| Chart | daily closes over one year, not adjusted for dividends, rebased to 100 at the latest close |
| Volatility | one-year annualised volatility of daily log returns, averaged over the names |
| Correlation avg / min | pairs of one-year daily log returns; weekly returns when the basket mixes regions (Asia, Europe, Americas), because markets close at different hours |
| Analyst target upside | mean analyst target price over the latest price, averaged over the shares; "–" for indices and ETFs |
| Worst 1y low / protection | the name whose lowest close of the year came closest to (or below) its protection; pink when at or below |
| Fall to protection | how far every name can fall from today before capital is at risk at maturity; "below" when a struck product is already under its protection |
| Coupon to maturity | coupon × tenor in months / 12 (an autocall can end it earlier) |
| KPIs | weighted by the sheet's weights: average coupon on the invested part and on the whole portfolio (cash at 0), share in index-only baskets, cash, weighted fall to protection |
| Stress | every name moves by the same amount at maturity; coupons counted in full; below a low strike the loss is 1 − level / strike, below a barrier the worst performance |
| Swap test | each Core List name of the basket's theme, not already in the proposal, tried in place of each name; suggested only when the weakest correlation rises by 0.15 or more, to at least 0.40 |
| Basket reading | weakest pair ≥ 0.60 "names move together"; < 0.40 "one low-correlation pair"; between "moderate dispersion" |

## Review list

1. The console's KPIs match the sheet: number of products, average coupon, cash.
2. Every `NAME -> SYMBOL` is right; any "Yahoo search (confirm)" match is checked; no `WARNING ... no prices`.
3. Each product has a coupon, a protection and a tenor (no `missing coupon` line).
4. Auto-written themes (listed at step 6) have proper words, or are flagged to the user.
5. The pages look right: render a few pages to images and look at the cover, the table, a card page.
6. The price date on page 2 is the one intended (`--asof` or today).

## Hand-over

- Link the PDF (and the HTML if the PDF could not be printed).
- One line: inputs used and price date.
- The KPIs in one line.
- Every product whose weakest name's one-year low was at or below its protection, with both levels.
  This is history, not a backtest or a forecast: say so if the client may read it.
- The swap-test suggestions, as alternatives worth pricing, not changes to the proposal.
- Open points: missing terms, names to confirm, themes to write, issuers still TBD.
- Compliance must validate the deck before it goes to a client.
