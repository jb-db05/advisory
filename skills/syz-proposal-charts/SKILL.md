---
name: syz-proposal-charts
description: "Turns a structured products investment proposal, given as a CSV file or as a list pasted in the chat (each product's basket of underlyings with its barrier or low strike, and optionally coupon, tenor, weight and size), into SYZ-styled client charts. Each basket is rebased to 100 at today's close, with the strike and barrier drawn across, and each underlying's distance to protection is shown. Produces one interactive HTML page and A4 PDFs per period (1 year, 3 years, 5 years) with an overview of every product's buffer and a table of strike and barrier levels in price terms. Uses Yahoo Finance closes. Use when asked to visualise, chart or turn into a PDF a structured products proposal, a list of baskets with strikes and barriers, normalised or rebased performance of underlyings against strike and barrier, or to swap an underlying in such a proposal and redo the charts."
---

# SYZ proposal charts

The input is one of two things: a CSV file, or a list pasted in the chat. A bundled pure-Python
script reads it, loads five years of Yahoo Finance closes and draws everything. Your job: turn the
input into a sheet, check the name matches, apply the user's changes, build, review and hand over.
Do not compute levels or draw charts yourself.

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

## When to use

- "Visualise this proposal / Proposal.csv", "chart each basket against its strike and barrier".
- A pasted table or list of baskets with their barriers or low strikes, and a request to chart it.
- "Make it a PDF, 1 year and 3 years", "same with 5 years".
- "Replace one underlying with another in product 4", then redo the charts. This happens only
  when the user asks; never change the proposal on your own.

Do not use this skill for: a review of products the client already holds, with their own initial
fixings; PDF term sheets or factsheets; or a PowerPoint deck. Use `syz-client-presentations` for
those, and for chart slides of one stock. A one-page technical review of a stock or a currency pair
(verdict, levels, catalysts) is `syz-technical-review`.

## Where to run it

| Where | Command |
| --- | --- |
| SYZ Advisory workspace (Claude Code, Windows) | `.\.venv\Scripts\python apps\G01\G01_proposal.py <sheet.csv> [options]` |
| This skill's folder (claude.ai, or any machine with Python 3.10+) | `python scripts/proposal_charts.py <sheet.csv> [options]` |

There are no dependencies to install (standard library only). Setup check, from the skill folder:
`python scripts/proposal_charts.py assets/samples/proposal_sample.csv --pdf`. It must print
three `Wrote …` lines. In the workspace, the packaged `scripts/` folder is not present; use the
first command.

Options: `--pdf` writes a 1-year and a 3-year PDF (`--pdf 1y,3y,5y` for all three).
`--tickers FILE` takes checked symbols. `--out-dir DIR` sets where files go (default: claude.ai's
`/mnt/user-data/outputs`, or `data/G01/out` in the workspace). `--offline` uses cached prices only.
`--open` opens the files on Windows.

## Instructions

1. **Get the proposal.** It comes in one of two ways.
   - **A CSV file.** On claude.ai it is in `/mnt/user-data/uploads/`. Use it as is.
   - **A list pasted in the chat.**
     - A table copied from Excel, with a header row starting with `Basket`: save it verbatim as
       `proposal.txt` (tabs and semicolons are detected).
     - Anything looser, such as `1. Nikkei / Euro Stoxx / S&P - 7% - European barrier 65% - 18m`:
       write `proposal.csv` in the format of [references/sheet-format.md](references/sheet-format.md).
       Write one row per product, copy the values exactly, and leave a cell empty when it was not
       given.
   - Ask only when a product has no underlying or no protection level. Never guess one.
   - For any other input (an Excel file, PDF term sheets), ask for a CSV or a paste instead.
2. **Check the sheet is anonymous.** Remove any client name, account or portfolio number from the
   sheet before building, and tell the user you did. Name files after the date, never the client.
3. **Apply only the changes the user asks for**, to a copy of the sheet. Usually that means
   swapping one underlying's cell; keep everything else (coupon, protection, weight, size)
   unchanged. Say which product changed. With no change requested, build the sheet as given.
4. **Build** with `--pdf` (or the periods asked for):
   ```bash
   python scripts/proposal_charts.py proposal.csv --pdf 1y,3y
   ```
5. **Check every match** in the printed list (`NAME -> SYMBOL (how)`).
   - A name matched by `search` may be wrong: an ETF, a leveraged product, another listing.
   - Use the listing the product is written on, e.g. `ASML.AS` for a EUR product.
   - If any is wrong or `?`, write a tickers file ([references/sheet-format.md](references/sheet-format.md))
     and rebuild with `--tickers tickers.json`.
   - Any `WARNING … no prices` line means a name is missing from the chart. Fix it or report it.
     Never type prices in.
6. **Review the output.** Open the PDFs or the page if you can, and read the per-product tables:
   - Every product is present.
   - Strike and barrier prices equal `level × last close`.
   - The currencies are plausible (SEK for OMX, JPY for Nikkei).
7. **Hand over:**
   - Link the files.
   - One line per changed product.
   - The 1-year lows that are at or below the protection level, as listed by
     [references/reading-the-output.md](references/reading-the-output.md).
   - Names to confirm.
   - When the period is 3 or 5 years, the framing note from that reference.

## Output

- `G01_proposal_<date>.html`: one self-contained page. It has the distance-to-protection overview,
  the summary table, and one card per product with a 1, 3 or 5-year switch, hover values and a
  table per underlying.
- `G01_proposal_<date>_1y.pdf`, `_3y.pdf`, `_5y.pdf`: A4 portrait PDFs. Page 1 has the
  title, KPIs and overview, then comes the summary table, then two products per page. The charts
  are vector. Lows and changes follow the period; vol is always one year.

## Rules

- Every price comes from Yahoo Finance closes. Every level is calculated by the script. Nothing is
  filled from memory or typed in.
- Levels assume each product is struck at today's close. Keep the footer disclaimer and never
  present the chart as a backtest or a forecast.
- No client names, account numbers or addresses in sheets, file names or messages. Use a
  pseudonym such as `C-0042` if one is needed.

## Example

**Input:** "Visualise Proposal.csv: each basket normalised to 100 today against its strike and
barrier, as PDFs for 1 year and 3 years."

**Output:** The two PDFs are linked (`G01_proposal_<date>_1y.pdf` and `_3y.pdf`), with the HTML
page beside them. Then:

> 18 products. Over the past year, three names had a lowest close at or below their product's
> protection level: product 3, Microsoft, 67% vs 72%; product 6, VAT, 51% vs 65%; product 7,
> Palo Alto, 41% vs 63%. To confirm: `VACN.SW` for VAT (matched by search). In the 3-year view most
> lows sit below protection because markets were much lower then; this is not a warning about
> the products.

## Additional resources

- [references/sheet-format.md](references/sheet-format.md): read when a CSV does not parse,
  when turning a pasted list into a sheet, or when writing a tickers file.
- [references/reading-the-output.md](references/reading-the-output.md): read before writing
  the hand-over, or when asked how to explain the charts to a client.
- [assets/samples/proposal_sample.csv](assets/samples/proposal_sample.csv): a fictional
  three-product sheet for the setup check.
