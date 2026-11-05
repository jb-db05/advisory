"""The O01 command line, shared by apps/O01/O01_run.py (workspace) and scripts/o01.py (packaged skill).

    CASE.json [--prices CSV ...] [--offline] [--preview]     build a deck from a case file
    --ingest FILE ... [--client C-0042] [--as-of DATE]       read any PDF / HTML / CSV / Excel inputs
                                                             into a draft case file + a report
    --terms FILE                                             one product's terms (PDF, HTML or text)
    --chart SYMBOL ... [--vs BENCH] [--period 1y] [--png]    equity / underlying chart deck (+ PNG)
    --qc DECK.pptx                                           check a deck
    --news SYMBOL ...                                        latest headlines, to research the comments
    --sample sp|client|proposal                              build a bundled sample (packaged skill)

Market data: yfinance when it imports, else the standard-library Yahoo client; price files
(--prices) fill what neither has; offline, the market prices printed on factsheets.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path

from syz_advisory.decks import builder, equity, preview, qc, yf
from syz_advisory.decks.inputs import detect, ingest, load_terms
from syz_advisory.decks.sources import CsvPrices, FirstOf, Market
from syz_advisory.marketdata import YahooClient

PERIODS = {"6m": 183, "1y": 365, "2y": 730, "3y": 1095, "5y": 1826}


def market_client(offline: bool, prices: list[Path] | None):
    """(client for Market, description, stdlib client to save the cache of)."""
    yahoo = YahooClient(offline=offline)
    used, chain = [], []
    if not offline:
        if yf.available():
            chain.append(yf.YFinanceClient(fallback=yahoo))
            used.append("yfinance")
        else:
            chain.append(yahoo)
            used.append("Yahoo Finance (stdlib client)")
    else:
        chain.append(yahoo)                       # offline: the cache only
    if prices:
        chain.append(CsvPrices(prices))
        used.append("price files")
    return FirstOf(*chain), ", ".join(used) or "cache only", yahoo


def main(argv: list[str] | None, out_dir: Path, samples: Path | None = None, always_preview: bool = False) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("case", nargs="?", type=Path)
    p.add_argument("--out", type=Path, help="output .pptx")
    p.add_argument("--offline", action="store_true", help="no internet calls; cached data and price files only")
    p.add_argument("--prices", type=Path, nargs="+", metavar="CSV", help="price files: date,symbol,close[,adj_close] (or wide)")
    p.add_argument("--preview", action="store_true", help="also write an HTML preview of the deck")
    p.add_argument("--terms", type=Path, metavar="FILE", help="read one product's terms (PDF, HTML or text)")
    p.add_argument("--ingest", type=Path, nargs="+", metavar="FILE", help="read inputs of any format into a draft case")
    p.add_argument("--client", default="C-0000", help="pseudonym for --ingest")
    p.add_argument("--as-of", dest="as_of", help="as-of date (YYYY-MM-DD) for --ingest / --chart")
    p.add_argument("--currency", help="reporting currency for --ingest")
    p.add_argument("--chart", nargs="+", metavar="SYMBOL", help="equity / underlying chart deck for these Yahoo symbols")
    p.add_argument("--vs", metavar="BENCH", help="benchmark symbol for --chart (e.g. ^GSPC, URTH, ^SSMI)")
    p.add_argument("--period", default="1y", choices=sorted(PERIODS), help="window for --chart")
    p.add_argument("--png", action="store_true", help="--chart: also a PNG per symbol (needs matplotlib)")
    p.add_argument("--qc", type=Path, metavar="PPTX")
    p.add_argument("--sample", choices=["sp", "client", "proposal"], help="build a bundled sample case")
    p.add_argument("--news", nargs="+", metavar="SYMBOL", help="print the latest headlines per Yahoo symbol and stop")
    args = p.parse_args(argv)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.news:
        yahoo = YahooClient(offline=args.offline)
        for sym in args.news:
            print(f"===== {sym}")
            try:
                items = yahoo.news(sym, 15)
            except Exception as exc:              # no network, unknown symbol: say so, go on
                print(f"  (no headlines: {exc})")
                continue
            for n in items or []:
                print(f"{n['date']} | {n['publisher']} | {n['title']} | {n.get('link', '')}")
        return 0

    if args.qc:
        issues = qc.check(args.qc)
        print(qc.report(issues))
        return 1 if any(s == "error" for s, *_ in issues) else 0
    if args.terms:
        kind = detect(args.terms)
        t = load_terms({"pdf" if kind == "pdf" else "html" if kind == "html" else "text": args.terms})
        print(json.dumps(t.to_dict(), indent=2, default=str, ensure_ascii=False))
        return 0
    if args.ingest:
        found = ingest(args.ingest, client=args.client, as_of=args.as_of, currency=args.currency)
        draft = out_dir / f"O01_case_{re.sub(r'[^A-Za-z0-9-]', '', args.client)}_draft.json"
        draft.write_text(json.dumps(found.case, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
        print("Inputs:")
        for line in found.report:
            print("  - " + line)
        if found.flags:
            print(f"Open points ({len(found.flags)}):")
            for where, what in found.flags:
                print(f"  - {where}: {what}")
        print(f"Draft case file: {draft}\n(type guessed: {found.case['type']}; check the client pseudonym, as_of, "
              "currency and nominals, add messages, then build it)")
        return 0

    client, used, yahoo = market_client(args.offline, args.prices)
    print(f"Market data: {used}")
    try:
        if args.chart:
            as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
            out = args.out or out_dir / f"O01_chart_{'_'.join(re.sub(r'[^A-Za-z0-9]', '', s) for s in args.chart)[:40]}_{as_of}.pptx"
            market = Market(client, as_of)
            path, flags = equity.build_chart_deck(args.chart, market, out, as_of=as_of, period_days=PERIODS[args.period],
                                                  bench=args.vs)
            print(f"Deck: {path}")
            if args.png:
                for sym in args.chart:
                    png = equity.price_png(market, sym, out_dir / f"O01_chart_{re.sub(r'[^A-Za-z0-9]', '', sym)}.png",
                                           start=as_of - timedelta(days=PERIODS[args.period]))
                    print(f"PNG: {png}" if png else f"PNG for {sym}: matplotlib not available here (the deck has the chart)")
            _report(path, flags, args.preview or always_preview)
            return 0
        case = args.case or (samples / f"O01_case_{args.sample}_sample.json" if args.sample and samples else None)
        if not case:
            p.error("give a case file, --ingest, --terms, --chart, --qc" + (" or --sample" if samples else ""))
        data = json.loads(case.read_text(encoding="utf-8"))
        code = re.sub(r"[^A-Za-z0-9-]", "", str(data.get("client", "client")))[:20] or "client"
        out = args.out or out_dir / f"O01_{data.get('type', 'deck')}_{code}_{data.get('as_of', 'today')}.pptx"
        path, ctx = builder.build(case, Market(client), out)
        print(f"Deck: {path} ({len(ctx.deck.slides)} slides)")
        return _report(path, ctx.flags, args.preview or always_preview)
    finally:
        yahoo.save()


def _report(path: Path, flags, with_preview: bool) -> int:
    if with_preview:
        print(f"Preview: {preview.write(path)}")
    issues = qc.check(path)
    print(qc.report(issues))
    if flags:
        print(f"Open points ({len(flags)}) -- also on the 'Sources' slide:")
        for where, what in flags:
            print(f"  - {where}: {what}")
    return 1 if any(s == "error" for s, *_ in issues) else 0
