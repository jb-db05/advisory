# Reading the output

Read this before writing the hand-over message, or when the user asks how to explain a chart to a
client.

## What every figure means

- **Rebased to 100 today.** Each line is `100 × close / latest close`. A point at 120 means the
  price was 20% higher than today, and a point at 70 means it was 30% lower. Every line ends at 100.
- **Struck today.** The strike and barrier are drawn as a % of today's close, as for a product
  struck now. The real levels are fixed on the trade date, so they move with the market until then.
- **Fall to protection.** `protection level − 100%`, the same for every name in a basket:
  −35% for a 65% barrier.
- **Lowest close over the period.** The lowest point of each line, as a % of today. When it is at
  or below the protection level (pink in the tables, a dot in the shaded area of the overview),
  that name was lower than today's protection level at some point in the period. It is **not** a
  backtest of the product. It says the market has already been that far below today's price.
- **Strike / barrier in price terms.** `level × latest close`, in the underlying's own currency.
- **Prices.** Raw daily closes, not adjusted for dividends (the levels a product observes).
  Indices and shares on different calendars are carried forward over holidays. The "last close"
  date can differ by a day between markets.
- **Vol.** One-year annualised volatility of daily log returns, the same in every period.

## Framing the periods

- **1 year** shows where the basket sits against recent trading. It is the default view for a client.
- **3 or 5 years** after a strong market will put most lows far below the protection level,
  because prices were much lower then. Say so in the hand-over; it is not a warning about the
  product.

## What to flag in the hand-over

- Names with no prices (printed as `WARNING … no prices`): the chart is incomplete.
- Names matched by Yahoo search: say which, and that the user should confirm them.
- Pink lows in the 1-year view: list them as `product — name: lowest close X% vs protection Y%`.
- A product with a single underlying, or a protection wording the script did not understand.

## Wording for the client

Short, factual, no forecast. For example:

> Over the past year the lowest close of Microsoft was 67% of today's level, below the 72%
> protection of product 3. The other names stayed above their protection levels.
