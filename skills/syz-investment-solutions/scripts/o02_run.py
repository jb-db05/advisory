"""O02 -- Investment Solutions decks (orange): client-ready PowerPoint in the SYZ slide format.

    .\\.venv\\Scripts\\python apps\\O02\\O02_run.py data\\O02\\in\\O02_sample.json --preview
    .\\.venv\\Scripts\\python apps\\O02\\O02_run.py SPEC.json --out data\\O02\\out\\deck_v2.pptx --offline
    .\\.venv\\Scripts\\python apps\\O02\\O02_run.py --extract OLD_DECK.pdf        (or .pptx)
    .\\.venv\\Scripts\\python apps\\O02\\O02_run.py --news NVDA SOXX               (headlines to research)
    .\\.venv\\Scripts\\python apps\\O02\\O02_run.py --qc DECK.pptx

A spec (JSON) holds the storyline: slides with a title, a section label, blocks (text, cards,
figures, tables, terms, charts, images, levels, steps, flags) and a source. The format is in
.claude/skills/syz-investment-solutions/references/spec-format.md. Outputs go to data/O02/out/.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

from syz_advisory import config
from syz_advisory.decks import extract, preview, qc, solutions
from syz_advisory.decks.cli import market_client
from syz_advisory.decks.sources import Market
from syz_advisory.marketdata import YahooClient


def main(argv: list[str] | None = None, out_dir: Path | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("spec", nargs="?", type=Path, help="deck spec (JSON)")
    p.add_argument("--out", type=Path, help="output .pptx (default: next free name in the output folder)")
    p.add_argument("--out-dir", type=Path, help="output folder (default data/O02/out)")
    p.add_argument("--preview", action="store_true", help="also write an HTML preview")
    p.add_argument("--offline", action="store_true", help="price charts from the cache only")
    p.add_argument("--open", action="store_true", help="open the deck (Windows)")
    p.add_argument("--extract", type=Path, metavar="DECK", help="read an existing PDF / PPTX deck into text, images, "
                                                                "chart data and a draft spec")
    p.add_argument("--news", nargs="+", metavar="SYMBOL", help="print the latest headlines and stop")
    p.add_argument("--qc", type=Path, metavar="PPTX", help="check a deck")
    args = p.parse_args(argv)
    out_dir = args.out_dir or out_dir or config.outputs("O02")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.qc:
        issues = qc.check(args.qc)
        print(qc.report(issues))
        return 1 if any(s == "error" for s, *_ in issues) else 0
    if args.news:
        yahoo = YahooClient(offline=args.offline)
        for sym in args.news:
            print(f"===== {sym}")
            try:
                for n in yahoo.news(sym, 15) or []:
                    print(f"{n['date']} | {n['publisher']} | {n['title']} | {n.get('link', '')}")
            except Exception as exc:
                print(f"  (no headlines: {exc})")
        return 0
    if args.extract:
        stem = re.sub(r"[^A-Za-z0-9-]+", "_", args.extract.stem)[:50]
        got = extract.extract(args.extract, out_dir / f"O02_extract_{stem}")
        print(f"Read {args.extract.name}: {got['pages']} pages, {got['images']} images, {got['charts']} native charts")
        print(f"  {got['out'] / 'slides.md'}   the text of every page")
        print(f"  {got['out'] / 'draft.json'}  a draft spec ({got['draft_slides']} content slides) to restructure")
        if got["charts"]:
            print(f"  {got['out'] / 'charts.json'} the numbers behind the native charts")
        if got["images"]:
            print(f"  {got['out'] / 'images'}      embedded pictures")
        return 0
    if not args.spec:
        p.error("give a deck spec, --extract, --news or --qc")

    client, used, yahoo = market_client(args.offline, None)
    try:
        stem = re.sub(r"[^A-Za-z0-9-]+", "_", args.spec.stem).removeprefix("O02_")
        out = args.out or _next_free(out_dir / f"O02_{stem}.pptx")
        path, b = solutions.build(args.spec, out, Market(client))
    finally:
        yahoo.save()
    print(f"Deck: {path} ({len(b.deck.slides)} slides)")
    if args.preview:
        print(f"Preview: {preview.write(path)}")
    issues = qc.check(path)
    print(qc.report(issues))
    if b.warnings:
        print(f"To review ({len(b.warnings)}):")
        for w in b.warnings:
            print(f"  - {w}")
    if args.open and os.name == "nt":
        os.startfile(path)                                # noqa: S606 -- opens the deck for the user
    return 1 if any(s == "error" for s, *_ in issues) else 0


def _next_free(path: Path) -> Path:
    if not path.exists():
        return path
    k = 2
    while path.with_name(f"{path.stem}_v{k}{path.suffix}").exists():
        k += 1
    return path.with_name(f"{path.stem}_v{k}{path.suffix}")


if __name__ == "__main__":
    sys.exit(main())
