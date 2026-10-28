# advisory

Agent Skills for SYZ advisory work: client presentations, portfolio proposals,
investment-solutions decks and structured-product charts.

## Skills

| Skill | What it does | Output |
|---|---|---|
| [`syz-portfolio-proposal`](skills/syz-portfolio-proposal) | Entry point for proposals. Runs a fixed intake (type, length, format, objective), reads the documents provided and routes to the right engine. | PowerPoint, Word or PDF |
| [`syz-client-presentations`](skills/syz-client-presentations) | SP portfolio reviews, client portfolio reviews, cross-asset proposals and underlying chart decks on the SYZ template, built from term sheets, factsheets and positions. | PowerPoint |
| [`syz-investment-solutions`](skills/syz-investment-solutions) | Builds new decks in the SYZ "Investment Solutions" format from research and data, or restructures an existing cluttered deck. | PowerPoint |
| [`syz-proposal-charts`](skills/syz-proposal-charts) | Charts a structured-products proposal: baskets rebased to 100 with strike and barrier, and each underlying's distance to protection. | HTML and A4 PDF |

## House rules for presentations

- **Fonts**: Nunito Sans for all text. Nunito Bold for slide titles and for
  everything on the cover (first) page. No other face. The deck renderers set
  this and their QC fails any deck that breaks it.
- **Font sizes**: titles aside, only three sizes: 16 pt (lead lines, key
  figures), 12 pt (body text, tables) and 8 pt (notes, sources, chart labels).

## Layout

```
templates/
  S00_template.pptx # master SYZ PowerPoint template
skills/
  <skill-name>/
    SKILL.md        # frontmatter (name, description) and instructions
    references/     # detail loaded on demand
    assets/         # template and sample inputs
    scripts/        # Python helpers (where the skill has code)
```

Each skill folder is self-contained, so it can be zipped and uploaded on its
own. That is why `syz-client-presentations` and `syz-investment-solutions` each
carry their own copy of `scripts/syz_advisory` and `scripts/pypdf`. If you
change the shared code, update both copies.
`syz-investment-solutions` has two extra modules, `decks/extract.py` and
`decks/solutions.py`.

The master PowerPoint template is `templates/S00_template.pptx`. Both deck
skills carry an identical copy in `assets/`. If the template changes, replace
all three files.

## Installing a skill

Zip the skill folder (for example `skills/syz-proposal-charts`) and upload it in
Claude under Settings → Capabilities → Skills.
