# Analytical frameworks

Read this before writing the messages and when judging whether a computed headline is the right key message.

## Structured products (per product, then portfolio)

1. **Is it still alive?** Final fixing passed → matured. Autocall condition met on a past observation (estimated from the coupon frequency and Yahoo closes) → "Called?": the cash and its reinvestment are the topic, not the barrier.
2. **Worst-of level** = min(last close / initial) over the underlyings. Everything else is measured from it.
3. **Distance to barrier** in points of initial (worst-of − barrier). On track > 15 pts, watch ≤ 15 pts, at risk at or below. American barriers: any close at or below since fixing means touched — then capital is at risk below the strike at maturity, whatever the level today. European: only the final fixing counts.
4. **Distance to autocall** (worst-of − trigger) and the next observation: how likely early redemption is, and the reinvestment it would trigger.
5. **Payoff at maturity** (diagram): product vs direct investment in the worst underlying, with and without barrier event. Shows the trade: capped upside (coupons) against conditional protection.
6. **Scenarios**: worst-of moves +10 / 0 / −10 / −20 / −30 % from today and stays there; total return per unit incl. coupons. Ignores autocalls and path — say so.
7. **Portfolio**: concentration by issuer (credit risk), by product type, and look-through by underlying (an equal split understates worst-of exposure). Average coupon nominal-weighted.

Key messages usually come from: a product near or through its barrier, a probable autocall (reinvestment decision), issuer concentration, a single name present in several baskets, maturities clustering.

## Single securities (stocks, ETFs)

- Performance over the review period vs the benchmark, **in the reporting currency** (chart) and local (table).
- Risk: annualised volatility of daily log returns, maximum drawdown over the period.
- Valuation and consensus from Yahoo (trailing / forward P/E, dividend yield, 52-week range, mean analyst target, number of analysts) — third-party data, never presented as SYZ's view.

## Funds

- What it is: family, category, legal type, asset mix.
- What it costs: expense ratio (and turnover). Confirm against the KID / factsheet — Yahoo can lag.
- What it holds: top holdings; overlap with direct positions is a concentration point.
- How it did: YTD, 1, 3, 5-year returns vs its category average.

## Client portfolios

- **Allocation** by asset class vs the agreed strategic allocation; the largest gap in points is usually the headline.
- **Concentration**: top position, top 5 / top 10 weight, Herfindahl (sum of squared weights), effective number of positions (1 / HHI). Below ~10 effective positions in a liquid portfolio is concentrated.
- **Currency and region** exposure: what the client actually bears in their reference currency.
- **Performance**: O01 shows today's weights applied to past prices (an illustration of the allocation, not a track record) against a benchmark, both in the reporting currency. The account's true performance (with flows and fees) comes from custody reporting; if the advisor provides it, quote it in a message with its source.
- **Opportunities** must follow from the analysis (an underweight vs strategy, an expiring product, idle cash) and carry their risks next to them.

## Observed, calculated, assumed

| Kind | Examples | On the slide |
| --- | --- | --- |
| Observed | factsheet terms, closes, fund fees | source in the caption |
| Calculated | worst-of, distances, weights, returns, volatility, scenarios | "calculated" note or caption with the method |
| Assumed | quarterly frequency when unknown, 12-month tenor when dates are missing | listed as an open point, never silent |
