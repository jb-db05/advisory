# Deck spec (JSON)

Read before writing a spec. Paths (images) are relative to the spec file.

## Deck

```json
{
  "title": "Investment Solutions\nby your Advisory Team",
  "date": "2026-08-12",
  "cover_caption": "Snowball Stepdown\nAutocall",
  "cover_image": "images/page01_1.jpg",
  "closing": "orange",
  "slides": [ ... ]
}
```

| Key | Meaning |
| --- | --- |
| `title` | Cover title; `\n` for the second line. Default "Investment Solutions / by your Advisory Team" |
| `date` | ISO date: shown on the cover as "12 August 2026"; price charts stop at it |
| `cover_caption` | The idea's name, orange, bottom-right over the photo (optional) |
| `cover_image` | JPEG/PNG for the cover's right half (cropped to fit); default: the template photo |
| `closing` | `orange` ("Welcome to Syzerland", default) or `offices` |

## Slide

```json
{
  "title": "How the call works",
  "subtitle": "Stepdown trigger and snowball coupon",
  "statement": "optional big centred line",
  "lead": "optional line under the statement",
  "top":     [ blocks, full width ],
  "columns": [ {"width": 0.42, "blocks": [ ... ]}, {"width": 0.58, "blocks": [ ... ]} ],
  "bottom":  [ blocks, full width ],
  "blocks":  [ blocks: one column, when there are no "columns" ],
  "takeaway": "One line, the message with its figure.",
  "note": "Illustrative, not a forecast.",
  "source": "Goldman Sachs indicative terms, 12 Aug 2026"
}
```

- `title`: under 30 characters, the topic or the idea ("Early knockout", "Semiconductors").
- `subtitle`: the italic orange section label ("Market context", "Indicative terms",
  "Underlying 1 · GDXJ US").
- `takeaway`: bold italic line with ➢ at the foot; the slide's point. Optional but recommended.
- `note`: grey italic line (illustrative, assumptions). `source`: grey line, always when there
  are figures ("Source: " is added).
- Layout: blocks in a column stack top to bottom. Charts, images and tables share the free height;
  text, figures, cards and callouts take what they need. `"height": 1.2` (inches) forces a
  block's height.

## Blocks

All blocks take an optional `"heading"` (bold line above; `"heading_color": "orange"`,
`"heading_size"`).

### text
```json
{"type": "text", "items": ["**Bold** words, __orange emphasis__", "- a sub-point", "> a plain paragraph"], "size": 12}
```
Orange → bullets. `"bullets": false` for plain paragraphs. The size shrinks to fit (floor 9.5 pt).
Warns above 90 words.

### card / cards
```json
{"type": "cards", "cards": [
  {"icon": "check", "heading": "What it is", "items": ["…"]},
  {"icon": "cross", "tone": "ink", "heading": "What it is not", "items": ["…"]}]}
```
Outlined, rounded, white. `tone`: `orange` (default), `amber`, `ink`, `green`, `light`.
`icon`: `check`, `cross`, `question`, `warning`, `money`, `shield`, `arrow`. Cards in one `cards`
block share one height.

### kpis
```json
{"type": "kpis", "style": "rule", "items": [{"value": "+108%", "label": "Sector EPS 2026e", "note": "revised from +37%"}]}
```
`style`: `rule` (big orange figure under a thin rule, default), `box` (amber figure in an orange
outline, for limits or terms), `strip` (small ink figures, for secondary facts). Item `color`:
`ink`, `orange`, `amber`, `red`, `green`. Two to five items.

### table
```json
{"type": "table", "header": ["", "Forward", "Option", "TARF"], "rows": [["Leverage", "None", "None", "2x"]],
 "widths": [1, 1.3, 1.5, 1.6], "highlight_rows": [0], "highlight_cols": [3], "color_numbers": true, "size": 12, "row_h": 0.45}
```
Orange header and rules, first column bold. `color_numbers`: negatives red, positives green
(returns tables). `color_negative`: negatives red only. `align`: list of `l`/`r`/`c`.

### terms
```json
{"type": "terms", "rows": [["Strike", "65%"], ["Conditional coupon", "18% p.a., paid only if called"]], "highlight": ["Conditional coupon"]}
```
A two-column term sheet; `header` defaults to Term / Detail.

### chart
| `chart` | Data | Use for |
| --- | --- | --- |
| `column` | `categories`, `series` {name: values}, `highlight` {"index": "orange"} | values by period, accumulation, coupon by observation |
| `bar` | same, horizontal | rankings, top-10 holdings |
| `line` | `categories` (text), `series`; `x_title`, `y_title`, `markers` | payoffs by spot level, profiles |
| `dates` | `categories` ISO dates, `series` | your own time series |
| `price` | `symbols` (Yahoo), `names`, `period` (6m/1y/2y/3y/5y) or `start`; `end`; `rebase` | prices from market data, cut at the deck date |
| `pie` / `doughnut` | `categories`, one series | allocations (legend with % is drawn beside) |

Options: `fmt` (Excel number format: `0.0%`, `#,##0`, `0.00`), `colors` (`orange`, `blueberry`,
`amber`, `mint`, `ink`, `grey` or hex), `labels` (data labels, on by default for bars),
`value_labels` (pie legend text).

### image
```json
{"type": "image", "path": "images/page07_1.png", "caption": "SOX price vs forward EPS, Bloomberg"}
```
PNG or JPEG, fitted to the box without distortion. Only for charts whose data you do not have.

### levels
```json
{"type": "levels", "groups": [{"label": "Resistance", "values": ["1.1568", "1.1600"]}, {"label": "Support", "values": ["1.1495"]}]}
```

### steps
```json
{"type": "steps", "highlight": 1, "items": [{"title": "Sign the commitment", "text": "Minimum USD 100k", "tag": "By 07.09.2026"}]}
```
Numbered circles joined by a rule; up to 5.

### flags
```json
{"type": "flags", "items": [{"label": "Illiquid fund", "text": "Quarterly redemption, 90 days' notice, 5% gate"}]}
```
Orange label, text beside, rules between: risks, "things to say before going in".

### callout
```json
{"type": "callout", "label": "Key point:", "text": "the better strike is not free."}
```
One outlined line. One per slide at most.
