# The story file

Read before writing the words for new baskets. The story file holds words only; every number on the
pages is calculated.

## Format

```json
{
  "title": "Thematic structured products portfolio",
  "subtitle": "Proposal by the Syz advisory team",
  "kicker": "STRUCTURED PRODUCTS · ADVISORY",
  "objective": "One or two sentences: what the portfolio is for.",
  "house_min_index": 0.20,
  "clusters": {"Global indices": [1, 2], "Technology & AI": [3, 4, 5]},
  "products": {
    "1": {"theme": "Global equity core", "thesis": "Three largest developed markets: diversified market risk, no single-company risk."}
  }
}
```

- `products` keys are the product numbers as strings. Every product needs a theme and a thesis.
- `clusters` are the theme families, coloured in order (blueberry, orange, mint, gold, sky, peach...).
  Every product number belongs to exactly one family.
- `principles` (optional) replaces the six default principles: a list of `[title, text]`. Texts may use
  placeholders filled from the analysis: `{index_products_words}`, `{index_weight}`, `{house_min}`,
  `{protection_words}`, `{fall_min}`, `{fall_max}`, `{tenor_min}`, `{tenor_max}`, `{stepdown_words}`,
  `{n_issuers_words}`, `{max_issuer}`, `{tbd_words}`, `{cash}`. A principle whose placeholder has
  nothing to say (no index basket, no cash, no issuer) is dropped, and the page title counts the rest.
- `house_min_index`: shown next to the index KPI; `null` to hide it.

`assets/stories/thematic_proposal.json` is the October 2026 proposal: start from a copy.

## Writing

- **Theme**: two to five words, client language ("AI semiconductors", not "TSM/NVDA/AVGO worst-of").
  The portfolio table cuts it at about 45 characters.
- **Thesis**: one line, under about 110 characters: what the basket is a bet on and why the names
  belong together. It appears in bold on the card and on the rationale page.
- No prices, targets, P/E, returns or dates typed in: the deck shows the live figures next to the words.
- No promises ("will", "guaranteed", "safe"). Write "is designed to", "pays as long as".
- A view taken from research is quoted with its source and date ("Syz house view, Oct 2026: ...").
- No client names, sizes or amounts.
