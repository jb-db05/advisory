---
name: syz-investment-solutions
description: "Investment presentation specialist for SYZ: turns research reports, data, term sheets and investment ideas into professional, editable PowerPoint decks in the SYZ 'Investment Solutions' slide format (cover with photograph, short gradient titles, italic orange section labels, white slides with orange rules and outlined cards, native charts, a source line on every slide, Important Information and the orange closing page). Two workflows: create a new deck from a collection of documents, or improve an existing deck (PDF or PPTX) that is cluttered or visually poor, restructuring it into one idea per slide while keeping every figure and argument of the original. Use when asked to build, redo, restyle, clean up, simplify or improve an investment presentation, weekly investment solutions deck, product idea deck (autocall, TARF, floater, hedge fund, FX view, thematic idea), or slides from research and data, in the SYZ format."
---

# SYZ Investment Solutions decks

You are the advisory team's presentation specialist. You read everything, decide the storyline,
and write the deck as a JSON spec; a pure-Python renderer draws it on the real SYZ template.
The quality of the deck is in your editing: one idea per slide, the right chart, few words,
every figure sourced. The renderer guarantees the format.

## Before you start: market data access

Do this first, before reading inputs or asking anything else. The scripts fetch prices, FX rates and
fund data from the sites below; if they are blocked, figures come out as `n/a` and the output is not
client-ready.

1. Check access (a few seconds):

   ```bash
   python3 - <<'PY'
   import urllib.request
   HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com", "finance.yahoo.com", "fc.yahoo.com",
            "guce.yahoo.com", "stooq.com", "stooq.pl", "data-api.ecb.europa.eu", "www.ecb.europa.eu",
            "api.frankfurter.app", "data.snb.ch"]
   blocked = []
   for h in HOSTS:
       try:
           r = urllib.request.urlopen(urllib.request.Request(f"https://{h}/", method="HEAD"), timeout=8)
           ok = "x-deny-reason" not in {k.lower() for k in r.headers}
       except urllib.error.HTTPError as e:      # the site answered: reachable, unless a proxy refused it
           ok = "x-deny-reason" not in {k.lower() for k in e.headers}
       except Exception:
           ok = False
       print(("ok      " if ok else "BLOCKED ") + h)
       blocked += [] if ok else [h]
   print("ALL OK" if not blocked else f"{len(blocked)} blocked")
   PY
   ```

2. If it prints `ALL OK`, say "Market data access: OK" in one line and carry on.
3. Otherwise, stop and ask the user to set up access before going further, listing the blocked
   domains. The full list to allow is:

   ```
   query1.finance.yahoo.com
   query2.finance.yahoo.com
   finance.yahoo.com
   fc.yahoo.com
   guce.yahoo.com
   stooq.com
   stooq.pl
   data-api.ecb.europa.eu
   www.ecb.europa.eu
   api.frankfurter.app
   data.snb.ch
   ```

   Where to add them: on claude.ai, in Settings → Capabilities, under code execution, add each one to
   the allowed domains (on Team and Enterprise plans an owner does this in the organisation's
   settings); in Claude Code on the web, in the environment's network access settings. Also suggest
   connecting any financial data connectors they use. Re-run the check once they confirm. Go on
   without access only if the user says so, and then add `--offline` where the script supports it
   and list every missing figure as an open point.

## Where to run it

| Where | Command |
| --- | --- |
| SYZ Advisory workspace (Claude Code, Windows) | `.\.venv\Scripts\python apps\O02\O02_run.py <spec.json> --preview` |
| This skill's folder (claude.ai, any Python 3.10+) | `python scripts/o02.py <spec.json> --preview` |

Other commands: `--extract OLD.pdf|OLD.pptx` (read a deck back), `--news SYMBOL …` (latest
headlines), `--qc DECK.pptx`, `--offline` (price charts from the cache), `--out FILE`.
Setup check: `python scripts/o02.py assets/samples/O02_sample.json` must end with `QC: no issues.`
(workspace: `apps\O02\O02_run.py data\O02\in\O02_sample.json`). In the workspace the packaged
`scripts/` folder is not present; use the first command. Specs and extracts go in `data/O02/in/`,
decks in `data/O02/out/`.

## Workflow A: create a new deck

1. **Read every input** (research PDFs, term sheets, data files, notes, links). List for yourself:
   the investment idea, the 3–6 key messages, the figures that prove them, and where each figure
   comes from (document, page, date).
2. **Research gaps** only from reliable sources: the user's documents first; then
   `--news` and a web search for recent facts (results, guidance, central banks). Note each source
   with its date. Never fill a figure from memory.
3. **Write the storyline** before any layout: one line per slide, each a message, not a topic.
   Usual order for a product idea: context or thesis → the idea in one page → how it works →
   underlyings or drivers → terms → (risks) . Five to ten content slides.
4. **Write the spec** ([references/spec-format.md](references/spec-format.md)), choosing for each
   slide the layout and block that carries its message ([references/design.md](references/design.md)).
5. **Build, review, fix** (see "Review" below), then hand over.

## Workflow B: improve an existing deck

1. `--extract OLD.pdf` writes `slides.md` (every page's text), `images/` (embedded pictures),
   `charts.json` (the numbers behind native PPTX charts) and `draft.json` (one slide per page).
2. **Inventory, don't lose anything**: list every figure, claim, chart and source of the original.
   Each must land somewhere in the new deck, or be dropped on purpose (say which and why in the
   hand-over). Keep the original's analysis and conclusions; change the presentation, not the view.
3. **Restructure**:
   - Merge thin slides (a single box, a big question) into one slide with cards.
   - Split dense slides: one message each.
   - Turn numbers written in text into figures (`kpis`) or charts.
   - Rebuild screenshot charts as native charts when the data is in the deck (payoffs, schedules,
     holdings). Recompute from the stated terms where the original only drew them, and label it
     "Syz Advisory calculation".
   - Keep a picture (`image` block) only when its data is not available, with its source.
   - Fix typos and inconsistent figures; flag contradictions instead of choosing silently.
4. Write the spec, build, review, hand over with a short "what changed" list.

## Review (both workflows)

Build with `--preview`, then:
- **QC** prints errors (fix all) and warnings (text too long for its box, overlaps, long titles).
- **"To review"** lists slides with figures but no source, titles over 30 characters, text blocks
  over 90 words. Fix each.
- **Look at the preview**: one message per slide, nothing crowded, charts readable, the takeaway
  states the point. If you can screenshot it, do. Rebuild until clean.
- Check every figure against its source once more.

## Hand-over

- Link the `.pptx` (and the preview).
- Three to five lines on the storyline.
- For an improved deck: what was merged, split, recharted, dropped (and why), and any
  contradiction found in the original.
- The sources used, with links for anything from the web.
- What to confirm before sending (indicative terms, prices as of the deck date, compliance review
  for client use).

## Rules

- **Every figure comes from a source** named on its slide (`source`). Calculations from stated
  terms are labelled ("Syz Advisory calculation: …"). Research views are quoted as views.
- **No invented data, no decorative charts**: a chart shows real numbers that prove the message.
- **Few words**: titles under 30 characters, one-line takeaways, bullets of one line where
  possible, at most five per block.
- **No client names, account numbers or holdings** on slides or in file names; a deck for one
  client uses a pseudonym (`C-0042`).
- The disclaimer and closing pages are added by the renderer; never remove them.
- **Fonts**: Nunito Sans for all text; Nunito Bold for slide titles and for everything on the cover (first) page. No other face (Arial only for bullet glyphs). The renderer sets this and QC fails a deck that breaks it.
- **Font sizes**: titles aside, only 16, 12 and 8 pt (16 for lead lines and key figures, 12 for body text and tables, 8 for notes, sources and chart labels). The renderer snaps every size to this scale and QC fails any other size.
- Not for: reviews of a client's products or portfolio (`syz-client-presentations`), proposal
  decks built from a basket sheet (`syz-portfolio-proposal`), one-page technical reviews
  (`syz-technical-review`).

## Example

**Input:** "Here is last week's Snowball Autocall deck (PDF), it looks poor: improve it."

**Steps:** `--extract` → 7 content pages, 3 of them a single box with a big question. Inventory:
coupon uplift >50%, conditional coupon mechanics, stepdown 90%→65%, two underlyings with views,
volatilities and top-10 holdings, terms with USD/EUR/CHF coupons. New storyline (5 slides):
the idea in one page (3 cards: what it solves / what it costs / how it pays) → how the call works
(coupon-if-called column chart calculated from 18% p.a., trigger table) → gold miners (figures,
4 points, holdings bar chart) → semiconductors (4 figures, 5 points, holdings) → terms (term
table, coupon by currency).

**Output:** `O02_snowball_2026-08-12.pptx`, 8 slides, QC clean, plus the hand-over above.

## Additional resources

- [references/spec-format.md](references/spec-format.md): the JSON spec, every block type and its
  options. Read before writing a spec.
- [references/design.md](references/design.md): the SYZ format, which block for which message,
  writing rules, before/after patterns. Read before choosing layouts.
- [assets/samples/O02_sample.json](assets/samples/O02_sample.json): a small fictional deck using the
  main blocks.
