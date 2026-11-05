"""Build the SYZ thematic structured-products deck from any mix of inputs.

    python proposal-deck/build_deck.py INPUT [INPUT ...] [options]

INPUT: a proposal sheet (.xlsx / .csv), term sheets (.pdf, or a .zip of them), pricer or product
pages (.html). A sheet and term sheets for the same products are merged into one record each.

The run goes step by step and prints what it did at each step:
  1  recognise each document           (sheet, term sheet, pricer page)
  2  extract the product terms         (underlyings, strike, barrier, coupon, dates, issuer, currency)
  3  match every name to a symbol      (tickers file, Bloomberg code, built-in table, Core List, Yahoo)
  4  fill the gaps with market data    (names, currencies, initial levels, tenor), flag what is missing
  5  analyse                           (vol, correlation, 1y lows, protection, upside, swap test, KPIs)
  6  write the words                   (story file; themes written automatically are flagged)
  7  draw the pages                    (HTML, A4, SYZ layout)
  8  print the PDF

Options:
  --story FILE      the words of the deck (default: assets/stories/thematic_proposal.json when it covers the products)
  --tickers FILE    checked symbols, {"NAME AS WRITTEN": "YAHOO"}
  --coupon C        the basket coupon given by the user: "8%" for every product without a coupon,
                    "3=7.5%" for product 3 (repeat the option for several products)
  --asof DATE       price date, YYYY-MM-DD (default: today)
  --out FILE        output PDF (default: /mnt/user-data/outputs on claude.ai, else ./out/SYZ_proposal_<date>.pdf)
  --stop-after N    stop after step N (2 = extraction only); products.json is always written
  --products FILE   start from an edited products.json instead of the documents
  --no-swap         skip the swap test
  --offline         use cached market data only
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # scripts/
ROOT = HERE.parent                                # the skill folder
ASSETS = ROOT / "assets"
sys.path.insert(0, str(HERE))

from syzdeck import analytics, ingest, market, render, story as storymod  # noqa: E402
from syzdeck.model import Product  # noqa: E402
from syzdeck.names import CoreList  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="*", type=Path)
    ap.add_argument("--story", type=Path)
    ap.add_argument("--tickers", type=Path)
    ap.add_argument("--asof")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--stop-after", type=int, default=8)
    ap.add_argument("--products", type=Path)
    ap.add_argument("--universe", type=Path, default=ASSETS / "core_list.csv")
    ap.add_argument("--no-swap", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--coupon", action="append", default=[])
    a = ap.parse_args(argv)

    asof = dt.date.fromisoformat(a.asof) if a.asof else dt.date.today()
    default_dir = Path("/mnt/user-data/outputs") if Path("/mnt/user-data/outputs").is_dir() else Path.cwd() / "out"
    out = a.out or default_dir / f"SYZ_proposal_{asof.isoformat()}.pdf"
    work = out.with_suffix("")
    market.use_cache(out.parent / ".market_cache.json", a.offline)   # next to the output: the skill folder may be read-only
    core = CoreList(a.universe)

    if a.products:
        print(f"1-2  Products read from {a.products}")
        products = [Product.from_dict(d) for d in json.loads(a.products.read_text(encoding="utf-8"))]
    else:
        if not a.inputs:
            ap.error("give at least one input document, or --products")
        print("1    Recognising the documents")
        print("2    Extracting the product terms")
        products = ingest.read(a.inputs)
    real = [p for p in products if p.product_type != "cash"]
    print(f"     {len(real)} product(s){', plus a cash line' if len(real) < len(products) else ''}")

    print("3    Matching names to Yahoo symbols")
    tickers = json.loads(a.tickers.read_text(encoding="utf-8")) if a.tickers else {}
    market.resolve(real, tickers, core)
    if not a.products:
        n_before = len(real)
        products = ingest.merge(products)
        real = [p for p in products if p.product_type != "cash"]
        if len(real) != n_before:
            print(f"     {len(real)} product(s) after merging the sheet with the term sheets")
    _coupons(real, a.coupon)

    print("4    Filling the gaps with market data")
    market.complete(real, asof)
    work.parent.mkdir(parents=True, exist_ok=True)
    pj = work.parent / f"{work.name}_products.json"
    pj.write_text(json.dumps([p.to_dict() for p in products], indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"     Extracted terms written to {pj} (edit and rerun with --products to correct a field)")
    _missing(real)
    market.save_cache()
    if a.stop_after <= 4:
        return 0

    print("5    Analysing")
    cards = analytics.analyse(real, asof, core, swap_test=not a.no_swap)
    market.save_cache()

    print("6    Writing the words")
    default_story = ASSETS / "stories" / "thematic_proposal.json"
    story_path = a.story or (default_story if _covers(default_story, real) else None)
    story = storymod.load(story_path)
    kinds = {c.product.number: (c.legs[0].kind if c.legs and all(l.kind == c.legs[0].kind for l in c.legs) else "share") for c in cards}
    auto = storymod.complete(story, products, core, kinds)
    print(f"     story: {story_path.name if story_path else 'written automatically'}"
          + (f"; themes written automatically for product(s) {', '.join(map(str, auto))}: check the words" if auto else ""))
    pf = analytics.portfolio(products, cards, story["clusters"])

    print("7    Drawing the pages")
    html = work.parent / f"{work.name}.html"
    html.write_text(render.build(products, cards, pf, story, asof, auto), encoding="utf-8")
    print(f"     {html}")
    if a.stop_after <= 7:
        return 0

    print("8    Printing the PDF")
    from syzdeck.pdf import to_pdf
    engine = to_pdf(html, out)
    print(f"     Wrote {out} ({engine})")
    _summary(cards, pf)
    return 0


def _coupons(products, given: list[str]) -> None:
    """Apply the basket coupon(s) the user gave: '8%' fills every product without one, '3=7.5%' sets product 3."""
    for g in given:
        num, _, val = g.rpartition("=")
        c = ingest._pct(val)
        if c is None:
            raise SystemExit(f"--coupon {g!r}: give a rate such as 8% or 3=7.5%")
        for p in products:
            if (num and p.number == int(num)) or (not num and p.coupon is None):
                if p.coupon is not None and abs(p.coupon - c) > 1e-9:
                    print(f"     product {p.number}: coupon {p.coupon*100:.2f}% replaced by {c*100:.2f}% (given by the user)")
                p.coupon, p.sources["coupon"] = c, "given by the user"
    for p in products:
        if p.coupon is None:
            print(f"     WARNING product {p.number}: no coupon. Ask for it (--coupon {p.number}=X%); it is never estimated.")


def _covers(path: Path, products) -> bool:
    if not path.exists():
        return False
    s = json.loads(path.read_text(encoding="utf-8"))
    nums = {str(p.number) for p in products}
    return nums <= set(s.get("products", {})) and len(nums) >= len(s.get("products", {})) - 2


def _missing(products) -> None:
    """Missing terms, grouped: a sheet rarely has ISINs or currencies, a term sheet should."""
    groups: dict[str, list[int]] = {}
    for p in products:
        for k, v in p.sources.items():
            if str(v).startswith("missing") and not (k == "isin" and p.source_file and p.source_file.endswith((".xlsx", ".csv", ".xlsm"))):
                groups.setdefault(k, []).append(p.number)
    for k, nums in groups.items():
        print(f"     missing {k}: product(s) {', '.join(map(str, nums))}")


def _summary(cards, pf) -> None:
    print("\nCheck before sending")
    print(f"  average coupon {pf['coupon_invested']*100:.2f}% on the invested part, {pf['coupon_total']*100:.2f}% overall; "
          f"{pf['index_weight']*100:.0f}% on indices; cash {pf['cash']*100:.0f}%")
    hits = [c for c in cards if c.hit]
    for c in hits:
        print(f"  product {c.product.number}: {c.worst_name} 1y low {c.worst_low*100:.0f}% vs protection "
              f"{(c.protection_today or 0)*100:.0f}%")
    for c in cards:
        for n in c.notes:
            if n.startswith("Alternative"):
                print(f"  product {c.product.number}: {n}")


if __name__ == "__main__":
    raise SystemExit(main())
