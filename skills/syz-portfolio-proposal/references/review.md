# Review before hand-over

Read after the build succeeds and before writing the hand-over. For O01 PowerPoint decks, also go
through `.claude/skills/syz-client-presentations/references/qc-checklist.md`.

## Figures

- Every product in the sheet is in the deck, under its own number.
- Coupons, protection levels, tenors and issuers match the sheet or term sheet exactly.
- The average coupon on the KPI page is consistent with the sheet's coupons (size-weighted).
- Strike and barrier prices equal level × last close; the currencies are plausible (JPY for the
  Nikkei, SEK for the OMX, CHF for `.SW`).
- No `–` where a value was expected. If there is one, find the cause: a missing ticker, no
  consensus for an index, no common history for the replay. Fix it or list it.
- Page count and the font line (`Font: Nunito Sans`) are as expected.

## Analysis to report, favourable or not

| From the deck | What to say |
| --- | --- |
| 1-year low at or below protection (pink) | Product, name, low vs level. It was there within a year, so it is the first question a client will ask |
| Lowest pair correlation below 0.4 | The worst-of risk is the main risk of that basket; the low strike is the answer |
| Swap test suggestion | An alternative worth pricing, never a change made to the proposal |
| Replay: capital loss frequency, average return | History of the same terms, not a forecast. Give the loss frequency as well as the average |
| Shock scenarios | At which fall the first products go below protection, and the net result at −30% |
| Issuer exposure | Largest issuer share, and how many are still TBD |
| Analyst target below today's price | Say so for that name; don't drop it |

## For a review of an existing proposal

Compare against the baseline (earlier deck or sheet):

- Moves since then for each underlying, and the change in distance to protection.
- Products whose swap test result changed.
- Names whose consensus or target upside turned negative.
- Whether each theme's story still holds; flag the ones to rewrite.
- What you recommend: keep, re-price, swap (to be priced), or drop, with one reason each. These are
  recommendations for the advisor to decide on, worded as such.

## For a new investment idea

- Why this basket rather than the alternatives: quote the swap test and the correlation.
- Fit with what the client already holds, if a positions extract was given: overlapping names,
  theme concentration, and issuer concentration.
- The coupon's source: issuer quote, date and indicative status.

## For a cross-asset proposal or review (O01)

- Weights sum to 100% (an open point otherwise); asset classes are named consistently.
- The gap to the strategic allocation is stated in the allocation title or the messages.
- The back-test or illustration is labelled as such, and compared with the benchmark, even when
  the benchmark did better.
- Concentration: the largest position and the top-5 weight; currency exposure in the reporting
  currency.
- Each research line has a source and a date; no research item is left as "not shown" by mistake.

## Readability (every deck)

- O01 titles are one-to-four-word labels (QC warns above 30 characters); the takeaway line under each states the point.
- Messages: one line each, three per box at most, no repetition of a figure already on the slide.

## Client suitability and compliance

- No client name, account number or address anywhere, including file names and document
  properties.
- Every assumption is labelled: strike at today's close, coupons before fees and taxes, issuer
  credit risk, replay is not a forecast.
- No promise of return or of capital protection beyond the product's terms.
- The *Important Information* and closing pages are present.
