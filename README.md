# advisory

Agent Skills for SYZ advisory work.

## Skills

| Skill | What it does | Output |
|---|---|---|
| [`syz-technical-takes`](skills/syz-technical-takes) | Builds the Syz Research "Technical Takes" for one instrument from its ticker: verdict box with support, resistance and implied-target levels, price/stochastic/relative-strength chart, breakout and momentum signal page, disclaimer. | 3-page A4 PDF |

## Layout

```
skills/
  <skill-name>/
    SKILL.md        # frontmatter (name, description) and instructions
    references/     # detail loaded on demand
    scripts/        # Python helpers
```

Each skill folder is self-contained, so it can be zipped and uploaded on its own.
Run outputs (`.output/`, `.input/`) are gitignored: client data stays local.
