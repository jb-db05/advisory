# advisory

Agent Skills for SYZ advisory work.

## Skills

| Skill | What it does | Output |
|---|---|---|
| [`syz-quick-sp-proposal`](skills/syz-quick-sp-proposal) | Quick structured-products proposal from a basket sheet: headline figures and one row per basket with a gauge of each name's 1-year low against the protection, then two baskets per page with a one-year chart and a table per underlying. | Short A4 PDF |
| [`syz-sp-portfolio-proposal`](skills/syz-sp-portfolio-proposal) | Full "Thematic structured products portfolio" deck from a proposal sheet, term sheets or pricer pages: summary and KPIs, portfolio table, distance to protection, theme families, basket cards with chart, vol, correlation and swap test, income, stress and issuers. | About 14-page A4 PDF |
| [`syz-technical-takes`](skills/syz-technical-takes) | Builds the Syz Research "Technical Takes" for one instrument from its ticker: verdict box with support, resistance and implied-target levels, price/stochastic/relative-strength chart, breakout and momentum signal page, disclaimer. | 3-page A4 PDF |

## Layout

```
skills/
  <skill-name>/
    SKILL.md        # frontmatter (name, description) and instructions
    references/     # detail loaded on demand
    scripts/        # Python helpers
    assets/         # fonts, logos, samples
```

Each skill folder is self-contained, so it can be zipped and uploaded on its own.
Run outputs (`.output/`, `.input/`) are gitignored: client data stays local.
