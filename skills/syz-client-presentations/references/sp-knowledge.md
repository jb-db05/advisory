# Structured products: families, payoffs, risks

Read this when analysing a structured product, checking that its payoff diagram is right, or writing about it. Levels are % of the initial fixing; "worst-of" = the weakest underlying's level.

## Contents
- Families and payoff formulas
- Reading and drawing the payoff diagram
- Autocall mechanics
- Barriers, strikes, coupons
- What moves the value before maturity
- Risks to state, and how
- SSPA categories

## Families and payoff formulas (at maturity, per 100 nominal)

| Family (desk code) | Redemption at maturity | Coupons | The trade the client makes |
| --- | --- | --- | --- |
| Reverse convertible (RC) | 100 if worst ≥ strike, else 100 × worst / strike (or shares) | guaranteed | sells a put at the strike for the coupon |
| Barrier RC (BRC) | 100 unless the barrier was breached **and** worst < strike; then 100 × worst / strike | guaranteed | sells a down-and-in put: protection until the barrier, full downside after |
| Autocallable (AC, Phoenix, Express) | as RC/BRC at maturity; early: 100 + coupon if worst ≥ trigger on an observation | guaranteed or conditional (coupon barrier), memory possible | sells a put and the upside above the trigger; short maturity when markets rise |
| Low-strike autocall | as RC with strike 50–75 %, no barrier | as AC | the strike *is* the protection: loss starts below it, from the strike, not from 100 |
| Discount certificate (DC) | min(final, cap); bought at a discount (purchase price < 100) | none (the discount is the yield) | sells a call at the cap; loss below the purchase price |
| Bonus certificate (BC) | max(bonus, final) if barrier intact, else final (cap optional) | none | gives up dividends for a minimum return while the barrier holds |
| Capital protected (CPN/CPC) | protection + participation × max(final − strike, 0), capped | sometimes a fixed coupon | buys a call with the coupon a bond would pay; protection only at maturity and subject to issuer credit |
| Twin-Win | 1 + participation × |final − 1| if barrier intact, else final | none | gains on moderate falls too, until the barrier |
| Tracker (TRK) | final × participation | none (dividends often passed on) | a delta-one position with issuer risk |
| Credit-linked note (CLN) | 100 unless a credit event on the reference entity; then recovery | coupon = credit spread | sells credit protection: no equity payoff diagram |
| Beat the Benchmark (BTB) | coupon paid if the basket beats a benchmark index | conditional | relative-performance bet |

The generator implements RC, BRC, autocall, DC, BC, CPN, Twin-Win and Tracker (`syz_advisory.structuring.payoffs`). A CLN gets no payoff diagram, on purpose.

## Reading and drawing the payoff diagram

The diagram shows **return at maturity incl. coupons (y) against the final level of the worst underlying (x)**, next to holding that underlying directly (grey dashed).

- **Two product lines for barrier products**: orange = barrier never breached (flat at 100 + coupons down to the barrier), red = barrier breached (follows the underlying from the strike down). Between the barrier and the strike the client's outcome depends on the path — the most important thing to explain.
- **Markers** (vertical dashed lines): today's worst-of (ink), the barrier (red), the breakeven (mulberry). Today's marker tells the client where they stand on their own payoff.
- **Breakeven** = the worst-of level at maturity where capital plus coupons equals 100, barrier assumed breached: `strike × (1 − coupons received)` for an RC-type. It is the real cushion, lower than the strike because coupons absorb part of the loss. State it in the message ("can fall to 59 % before capital is lost").
- Capital protected: floor at the protection level, slope = participation above the strike, flat above the cap.
- Discount: rises 1:1 to the cap, then flat; loss starts below the purchase price, not at 100.
- Twin-Win: V shape around 100 while the barrier holds; ordinary 1:1 line once breached.
- The diagram ignores early redemption, fees, taxes and issuer default; the caption says so. For autocalls the early-redemption strip (if called at observation n → return) shows the other half of the story.

Check a diagram against the term sheet before sending: the flat part equals 100 + all coupons over the full life; the kink sits at the strike; the barrier marker sits where the two product lines split.

## Autocall mechanics

- **Observation**: on each autocall observation date, if every underlying (worst-of) closes ≥ the trigger, the product redeems at 100 + the coupon(s) due, and the position ends.
- **Non-call period**: no early redemption before the first call date (e.g. "(i from 4 to 11)" monthly = first call after 4 months).
- **Step-down**: the trigger falls each observation (100 % → 95 % → 90 %…), raising the chance of early redemption.
- **Conditional coupon** (Phoenix): paid only if the worst-of ≥ the coupon barrier on that date; **memory** pays missed coupons later when the condition is met again.
- **Expected life** is short when markets rise: a 3-year autocall usually ends after 6–12 months. Talk about reinvestment risk: the client gets the cash back when markets are high.
- The generator checks past observations against daily closes; a met condition is shown as "Called?" — always confirm with the issuer (fixing conventions, holidays, exact levels).

## Barriers, strikes, coupons

- **American (continuous / daily close)** barrier: breached if any close (sometimes any intraday price — check the wording) touches it during the life. Once breached it stays breached.
- **European** barrier: observed only at the final fixing. Much safer for the client at the same level; the coupon is lower.
- **Strike** below 100 % (low-strike): the loss is measured from the strike — at a 60 % strike and a 45 % final, the client gets 45/60 = 75 %, not 45 %.
- **Physical settlement**: below the strike the client receives shares (denomination / strike price, fractions in cash) — the loss is not realised until they sell.
- **Coupon per period vs p.a.**: always annualise for comparison; the coupon amount per payment = nominal × coupon p.a. × months between payments / 12 ("every 4 months" is three payments a year, not four).
- **Quanto**: underlying in another currency, product in the reference currency, FX risk removed (cost embedded in the coupon).

## What moves the value before maturity

| Driver | Effect on a BRC / autocall held by the client |
| --- | --- |
| Underlying falls | value falls, faster as the worst-of nears the barrier (negative gamma near the barrier) |
| Volatility rises | value falls (the client is short volatility) |
| Correlation between underlyings falls | value falls (worst-of gets worse) |
| Dividends higher than expected | value falls (lower forward) |
| Rates rise | value falls slightly (discounting), new issues pay more |
| Issuer credit spread widens | value falls; at default the client is an unsecured creditor |
| Time passes with the worst-of well above the barrier | value rises towards 100 + accrued coupons |

Secondary-market prices include the issuer's bid-ask spread; the "price" on a factsheet is indicative.

## Risks to state, and how

- **Issuer credit risk** on every product, with the issuer named; concentration by issuer is a portfolio risk.
- **Capital at risk** below the barrier/strike: say from which level and how much (e.g. "a 30 % fall in the weakest stock means a loss of 30 % at maturity once the barrier is breached").
- **Worst-of**: the client bears the weakest name; diversification across the basket does not help them.
- **Liquidity**: the issuer usually makes a market, but not always at fair value; early sale may cost.
- **Reinvestment** for autocalls; **currency** if not quanto and the underlying differs from the reference currency.
- No promise of coupons that are conditional; past barrier distances do not predict the future.

## SSPA categories (Swiss Structured Products Association)

1100 Capital protection (1100 with participation, 1130 with coupon, 1140 with participation in two directions…); 1200 Yield enhancement (1210 discount certificate, 1220 reverse convertible, 1230 barrier discount, 1260 barrier RC, 1250 express); 1300 Participation (1300 tracker, 1320 bonus, 1340 twin-win…); 1400 Investment products with additional credit risk (credit-linked); 2000 Leverage (warrants, mini-futures). Use the category to describe the product family in plain words.
