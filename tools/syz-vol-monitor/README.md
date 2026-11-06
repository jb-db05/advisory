# SYZ Vol Monitor

The implied-vol ranking and big-move alerts of `SYZ_ADVISORY_VOL.xlsx`, without Excel. It runs on
the Bloomberg terminal PC, reads Bloomberg through the Desktop API, and shows everything on a local
web page in the Syz house style.

- **Ranking**: focus and master lists by 3-month ATM implied vol, with IV / HV and vol tier.
- **Alerts**: a stock is flagged on a daily move of 5 % or more, a move of 2.5 σ or more against its
  3-month implied vol, or a 5-day move of 10 % or more (all editable). Checked every 60 s, logged
  once per stock per day, shown as a pop-up and, if set, e-mailed through Outlook. Excel no longer
  needs to be open.
- **Focus list / Master list**: every figure per stock, including its trading currency, sortable
  and filterable; ticker check against the ISIN.
- **Settings**: vol tiers, alert thresholds, e-mail; add a stock to the focus or master list.
  Remove a stock with the **Remove** link on its row (a second click confirms).

The calculations reproduce the workbook exactly: on the values saved in the file, ranks, tiers,
regions, ticker checks and the 150 alerts all match (`tests/test_engine.py`).

## What you need

- The Bloomberg terminal running and logged in on this PC (the Desktop API answers on
  `localhost:8194`).
- Python 3.10 or later (Software Center or python.org).
- Internet access to `blpapi.bloomberg.com` once, to install the Bloomberg Python package. If it is
  blocked, ask IT to install `blpapi` for you.

## Set up (once)

1. Copy this folder to the terminal PC.
2. Double-click `setup.bat`. It creates a private Python environment and installs `blpapi` (and
   `pywin32` for Outlook e-mails).

## Use

- Double-click `run_vol_monitor.bat`. The page opens at <http://localhost:8765>. Leave the black
  window open: closing it stops the tool.
- Click **Enable pop-ups** once in the browser to get desktop notifications while the page is open.
  For e-mails, enter an address under **Settings**.
- To try it without Bloomberg, double-click `run_demo.bat`: it uses the values saved in the Excel
  file. The workbook did not store currencies, so demo mode infers them from the exchange code
  (SW = CHF, LN = GBp, ...); live mode reads Bloomberg's `CRNCY`.

## How it reads Bloomberg

| Data | Bloomberg field | How often |
|---|---|---|
| Last price, change today | `LAST_PRICE`, `RT_PX_CHG_PCT_1D` | live subscription |
| IV 1M / 3M / 12M ATM, HV 3M, change 5 days | see `config.json`, `VOLATILITY_90D`, `CHG_PCT_5D` | every 30 min (`vol_refresh_minutes`) |
| ISIN, country of risk, GICS sector, trading currency | `ID_ISIN`, `CNTRY_OF_RISK`, `GICS_SECTOR_NAME`, `CRNCY` | once a day |

Prices come by subscription, as Excel's BDP does for live fields, so they do not use up the
terminal's daily data limit; vols are refreshed every 30 minutes for the same reason.

**IV 1M field.** In the workbook, `1MTH_IMPVOL_100.0%MNY_DF` returned *Invalid Field* for every
stock. The tool uses `30DAY_IMPVOL_100.0%MNY_DF` instead: check it on the terminal with
`FLDS <GO>` and change it in `config.json` if needed. All field names live there.

## Licence

The Desktop API gives data to the user logged in on this terminal. The page only listens on this PC
(`127.0.0.1`): do not open it to the network or share its data with other people. A shared, multi-user
version needs Bloomberg B-PIPE or Data License.

## Files

| Path | What it is |
|---|---|
| `data/focus_list.csv`, `data/master_list.csv` | The stock lists (taken from the workbook). Add and remove stocks from the page, or edit in a text editor. |
| `data/alert_log.csv` | The alert log, written by the tool (one line per stock per day). |
| `data/demo_snapshot.json` | Bloomberg values saved in the workbook, for demo mode. |
| `config.json` | Tiers, alert thresholds, e-mail, Bloomberg fields and refresh times, port. |
| `vol_monitor/engine.py` | The calculations (one rule per workbook formula). |
| `vol_monitor/sources.py` | Bloomberg Desktop API connection and demo source. |
| `vol_monitor/app.py` | Local web server, alert checker, e-mail. |
| `static/` | The page, Syz logo and Nunito fonts. |

## If something is wrong

- *"cannot connect to Bloomberg"*: the terminal is not running or not logged in.
- A stock shows *not found* or *ISIN differs* under **Ticker check**: fix its Bloomberg ticker in
  `data/master_list.csv` (14 tickers in the workbook already had this problem).
- Empty IV for a stock: Bloomberg has no implied vol for it (no listed options); it is left out of
  the ranking, as in Excel.
- This first version has been checked against the workbook's saved values but not yet on a live
  terminal: report anything odd on the first run.
