# advisory

Agent Skills for SYZ advisory work. Names follow one pattern: `syz-` + area + what
the skill makes. Structured-products skills share `syz-sp-`, so they sort together.

## Skills

| Skill | What it does | Output |
|---|---|---|
| [`syz-proposal-intake`](skills/syz-proposal-intake) | Entry point for proposals. Asks four questions (structured products or cross-asset, length, format, objective), reads the documents and routes to the right engine. The engines live in the SYZ Windows workspace. | PDF, Word or PowerPoint |
| [`syz-sp-quick-proposal`](skills/syz-sp-quick-proposal) | Quick one-year proposal from a basket sheet: headline figures, one row per basket with each name's 1-year low against the protection, then two baskets per page with a chart and a table per underlying. | Short A4 PDF |
| [`syz-sp-full-proposal`](skills/syz-sp-full-proposal) | The full "Thematic structured products portfolio" deck from a proposal sheet, term sheets or pricer pages: summary and KPIs, distance to protection, theme families, basket cards with chart, vol, correlation and swap test, income, stress and issuers. | About 14-page A4 PDF |
| [`syz-sp-basket-charts`](skills/syz-sp-basket-charts) | Charts only: each basket rebased to 100 with its strike and barrier, each name's distance to protection, levels in price terms. | HTML page and A4 PDFs (1, 3, 5 years) |
| [`syz-client-review`](skills/syz-client-review) | PowerPoint on the SYZ template: reviews of structured products held (payoffs, barrier distances, scenarios), client portfolio reviews, cross-asset proposals and stock chart decks. | PowerPoint |
| [`syz-investment-deck`](skills/syz-investment-deck) | "Investment Solutions" decks: a new deck from research, data and term sheets, or an existing cluttered deck restyled to one idea per slide. | PowerPoint |
| [`syz-technical-takes`](skills/syz-technical-takes) | The Syz Research "Technical Takes" for one stock, index, commodity or currency, from its ticker: verdict, levels, price / stochastic / relative-strength chart, breakout and momentum page. | 3-page A4 PDF |

### Which one when

| You want… | Skill |
|---|---|
| Help choosing the format, or a cross-asset proposal | `syz-proposal-intake` |
| A fast PDF of a few baskets | `syz-sp-quick-proposal` |
| The full SP portfolio proposal deck | `syz-sp-full-proposal` |
| Just the basket charts against strike and barrier | `syz-sp-basket-charts` |
| A review of products or a portfolio a client holds | `syz-client-review` |
| A product-idea or research deck in PowerPoint | `syz-investment-deck` |
| A technical view on one stock, index or currency | `syz-technical-takes` |

## Renamed skills (November 2026)

| Old name | New name |
|---|---|
| `syz-portfolio-proposal` | `syz-proposal-intake` |
| `syz-quick-sp-proposal` | `syz-sp-quick-proposal` |
| `syz-sp-portfolio-proposal` | `syz-sp-full-proposal` |
| `syz-proposal-charts` | `syz-sp-basket-charts` |
| `syz-client-presentations` | `syz-client-review` |
| `syz-investment-solutions` | `syz-investment-deck` |
| `syz-technical-takes` | unchanged |

Skills already uploaded to Claude under an old name keep that name until they are
re-uploaded from this repo.

## Visual guidelines, icons and fonts

[`brand/visual-guidelines.md`](brand/visual-guidelines.md) is the written version of the
*Syz Visual Guidelines* (WIP 28/05/24, source PDF in `brand/`). It is a resource for icons, fonts
and design ideas, not a rulebook: each skill's house style, template or spec stays in charge.
It leaves out the data display section (charts and tables).

- `brand/icons/`: the 40 Syz icons as vector SVGs, in `gradient/`, `flat/` (Tiger Orange, for
  PowerPoint and Word) and `white/`; `overview.png` shows them all.
- `brand/icons-finance/`: 24 finance icons drawn in the same style (coins, wallet, charts,
  candlestick, shield, umbrella, percent, safe, globe, gold bars, euro and more), same three
  colourways. Not part of the official library: have the brand team approve them before
  external use.
- `brand/fonts/`: Nunito Light, Regular and Bold (SIL Open Font License).

Every skill carries a copy of the guidelines in `references/visual-guidelines.md`. After editing
the file in `brand/`, run `brand/sync.sh` from the repo root to update the copies.

## House rules for presentations

- **Fonts, by default in every skill and every output** (PowerPoint, PDF, HTML,
  chart images): Nunito Sans for all text, Nunito Bold for titles and for
  everything on a cover (first) page. No other face. The fonts are bundled in
  each skill's `assets/fonts` (SIL Open Font License), so PDFs and chart images
  embed them without anything being installed. PowerPoint files name the fonts,
  so Nunito and Nunito Sans must be installed where the decks are opened.
- **Font sizes**: titles aside, only three sizes: 16 pt (lead lines, key
  figures), 12 pt (body text, tables) and 8 pt (notes, sources, chart labels).

## Market data access

Every skill starts by checking that it can reach the market data sites below,
and asks you to allow any that are blocked before it does anything else:

```
query1.finance.yahoo.com    query2.finance.yahoo.com    finance.yahoo.com
fc.yahoo.com                guce.yahoo.com              stooq.com
stooq.pl                    data-api.ecb.europa.eu      www.ecb.europa.eu
api.frankfurter.app         data.snb.ch
```

On claude.ai add them under Settings → Capabilities (allowed domains for code
execution; an owner does this on Team and Enterprise plans). In Claude Code on
the web, add them to the environment's network access settings.

## Layout

```
templates/
  S00_template.pptx # master SYZ PowerPoint template
skills/
  <skill-name>/
    SKILL.md        # frontmatter (name, description) and instructions
    references/     # detail loaded on demand
    assets/         # fonts, logos, templates and sample inputs
    scripts/        # Python helpers (where the skill has code)
```

Each skill folder is self-contained, so it can be zipped and uploaded on its
own. That is why `syz-client-review` and `syz-investment-deck` each
carry their own copy of `scripts/syz_advisory` and `scripts/pypdf`. If you
change the shared code, update both copies.
`syz-investment-deck` has two extra modules, `decks/extract.py` and
`decks/solutions.py`.

The master PowerPoint template is `templates/S00_template.pptx`. Both deck
skills carry an identical copy in `assets/`. If the template changes, replace
all three files.

## Installing a skill

Zip the skill folder (for example `skills/syz-sp-basket-charts`) and upload it in
Claude under Settings → Capabilities → Skills.
