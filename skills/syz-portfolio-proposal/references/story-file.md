# The story file (G01 themes JSON)

Read before writing or editing the words of a G01 deck. The file holds words only: every number on
the pages is calculated by the script, never read from here.

## Format

```json
{
  "title": "Thematic structured products portfolio",
  "subtitle": "Proposal by the Syz advisory team",
  "objective": "One or two sentences: what the portfolio is for.",
  "principles": [
    ["One theme per product", "Why, in two or three sentences."],
    ["...", "..."]
  ],
  "clusters": {
    "Global indices": [1, 2],
    "Technology & AI": [3, 4, 5]
  },
  "products": {
    "1": {
      "theme": "Global equity core",
      "thesis": "One line, shown on the compact deck's rationale page and cards.",
      "story": [
        "What the basket is, in plain words.",
        "Why these names belong together.",
        "What drives them over the product's life.",
        "Role in the portfolio."
      ]
    }
  }
}
```

- Keys under `products` are the sheet's product numbers, as strings. Every product needs an entry.
- Every product number appears in exactly one `clusters` family. Families are coloured in order.
- The compact deck shows six principles as tiles (three per row, about six lines each). Keep each
  one under about 45 words.
- `thesis` is cut to one line on the cards: keep it under about 110 characters.
- `story`: three to five bullets in the full deck. Make the first bullet stand alone, because it
  becomes the thesis when `thesis` is missing.

## Writing the investment case

- **One message per bullet.** Lead with the point, then the reason.
- **What the basket is a bet on**, in client language: "the three largest developed markets",
  not "a worst-of on SPX/SX5E/NKY".
- **Why the names belong together.** The shared driver is what keeps the worst-of risk down. The
  deck computes the correlation, so don't quote it here.
- **What could go wrong**, at least once per product: the risk that would hit the weakest name.
  The deck's "why this basket" adds the numbers.
- **Role in the portfolio**: anchor, income engine, diversifier, conviction.
- **Product mechanics**: describe a step-down autocall, a low strike or a European barrier in one
  sentence when the product has one. Use `.claude/skills/syz-client-presentations/references/sp-knowledge.md`
  for correct wording.
- **For a new idea**, add why now: the catalyst or the valuation argument. If it comes from
  research, cite it ("Syz house view, Oct 2026").
- **For a review**, keep the original story where it still holds, and say plainly where it no
  longer does.

## Never in the story file

- Prices, targets, P/E, growth rates or returns typed in from memory or the web. The deck shows
  the live figures next to the words, and a stale figure would contradict them.
- Research figures without their source and date.
- Client names, sizes, amounts or weights (the compact table takes weights from the sheet).
- Promises: "will", "guaranteed", "safe". Write "is designed to", "pays as long as", "protected
  down to".
