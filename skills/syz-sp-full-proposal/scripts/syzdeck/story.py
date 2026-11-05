"""Step 6: the words of the deck (the story file).

The story file holds words only: title, objective, the six principles, the theme families and, per
product, a theme name and a one-line thesis. Every number on the pages is calculated, never read
from here. Principles may use placeholders that are filled from the analysis, e.g.
"{index_weight}" -> "20%". See assets/stories/thematic_proposal.json.

Products the story file does not cover get a theme from the sheet's Theme column, the Core List or
the kind of underlying, and a thesis listing the names. They are flagged in the hand-over so the
advisor writes the words.
"""

from __future__ import annotations

import json
from pathlib import Path

from .names import CoreList

DEFAULT = {
    "title": "Thematic structured products portfolio",
    "subtitle": "Proposal by the Syz advisory team",
    "kicker": "STRUCTURED PRODUCTS · ADVISORY",
    "objective": "Generate a regular, high coupon from the companies and markets we have the strongest "
                 "convictions on, with a defined level of protection on every product and no single story "
                 "dominating the portfolio.",
    "principles": [
        ["One theme per product", "Every basket holds names from a single investment theme. The client knows what each product is a bet on, and names that share a story tend to move together, which reduces the worst-of risk."],
        ["Indices as the anchor", "{index_products_words} make up {index_weight} of the portfolio{house_min}. They diversify single-company risk and carry the deepest European barriers."],
        ["Protection before coupon", "{protection_words}: each name can fall by {fall_min} to {fall_max} before capital is at risk."],
        ["Short and staggered", "Tenors of {tenor_min} to {tenor_max} months{stepdown_words}, so capital comes back regularly to be reinvested in the themes that remain attractive."],
        ["Spread the credit", "{n_issuers_words} named so far, none above {max_issuer} of the portfolio{tbd_words}."],
        ["Keep dry powder", "{cash} in cash to add to a theme after a market setback or to replace a product that is called early."],
    ],
    "house_min_index": 0.20,
    "clusters": {},
    "products": {},
}

WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine",
         10: "Ten", 11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen", 16: "Sixteen",
         17: "Seventeen", 18: "Eighteen", 19: "Nineteen", 20: "Twenty"}


def load(path: Path | None) -> dict:
    story = json.loads(json.dumps(DEFAULT))
    if path and Path(path).exists():
        story.update(json.loads(Path(path).read_text(encoding="utf-8")))
    return story


def complete(story: dict, products, core: CoreList, kinds: dict[int, str]) -> list[int]:
    """Give every product a theme and a family; return the products written automatically."""
    auto = []
    prods = story.setdefault("products", {})
    for p in products:
        if p.product_type == "cash":
            continue
        key = str(p.number)
        if key in prods and prods[key].get("theme"):
            continue
        k = kinds.get(p.number, "share")
        themes = [core.theme_of(u.symbol) for u in p.underlyings if u.symbol]
        themes = [t for t in themes if t]
        if not themes:
            from .market import profile
            themes = [profile(u.symbol).get("sector") for u in p.underlyings if u.symbol]
            themes = [t for t in themes if t]
        theme = p.theme or ("Global indices" if k == "index" else "Real assets" if k == "etf"
                            else max(set(themes), key=themes.count) if themes else "Equity basket")
        names = " / ".join(u.short_name or u.name for u in p.underlyings)
        prods[key] = {"theme": theme, "thesis": prods.get(key, {}).get("thesis") or f"Worst-of basket on {names}.",
                      "family": theme}
        auto.append(p.number)
    clusters = story.get("clusters") or {}
    placed = {n for nums in clusters.values() for n in nums}
    for p in products:
        if p.product_type == "cash" or p.number in placed:
            continue
        fam = prods[str(p.number)].get("family") or prods[str(p.number)]["theme"]
        clusters.setdefault(fam, []).append(p.number)
    numbers = {p.number for p in products if p.product_type != "cash"}
    story["clusters"] = {k: [n for n in v if n in numbers] for k, v in clusters.items() if any(n in numbers for n in v)}
    return auto


def pct(x, d=0):
    return f"{x * 100:.{d}f}%"


def principles(story: dict, pf: dict) -> list[tuple[str, str]]:
    n_idx = pf["n_index"]
    house = story.get("house_min_index")
    barriers = pf["barriers"]
    strikes = (pf["strike_min"], pf["strike_max"])
    parts = []
    if strikes[0] is not None:
        parts.append(f"Low strikes of {pct(strikes[0])} to {pct(strikes[1])}" if strikes[0] != strikes[1] else f"Low strikes of {pct(strikes[0])}")
    if barriers:
        b = [f"{x * 100:.1f}".rstrip("0").rstrip(".") + "%" for x in (barriers[0], barriers[-1])]
        parts.append(("European barriers at " + (f"{b[0]} and {b[1]}" if len(barriers) > 1 else b[0])))
    falls = [1 - x for x in ([*barriers] + [s for s in strikes if s is not None])]
    fall_words = lambda x: "a quarter" if abs(x - 0.25) < 0.015 else "almost 40%" if 0.37 <= x < 0.40 else pct(x)
    vals = {
        "index_products_words": f"{WORDS.get(n_idx, n_idx)} index basket{'s' if n_idx != 1 else ''}",
        "index_weight": pct(pf["index_weight"]),
        "house_min": f", the house minimum for index exposure" if house and abs(pf["index_weight"] - house) < 0.005 else
                     f", above the house minimum of {pct(house)}" if house and pf["index_weight"] > house else "",
        "protection_words": " and ".join(parts) or "Defined protection on every product",
        "fall_min": fall_words(min(falls)) if falls else "n/a", "fall_max": fall_words(max(falls)) if falls else "n/a",
        "tenor_min": pf["tenor_min"], "tenor_max": pf["tenor_max"],
        "stepdown_words": f", {WORDS.get(pf['n_stepdown'], pf['n_stepdown']).lower()} of them with step-down autocalls" if pf["n_stepdown"] else "",
        "n_issuers_words": f"{WORDS.get(pf['n_issuers'], pf['n_issuers'])} issuer{'s' if pf['n_issuers'] != 1 else ''}",
        "max_issuer": pct(pf["max_issuer"]),
        "tbd_words": f"; the issuers of {WORDS.get(pf['issuers_tbd'], pf['issuers_tbd']).lower()} product{'s are' if pf['issuers_tbd'] != 1 else ' is'} still to be chosen" if pf["issuers_tbd"] else "",
        "cash": pct(pf["cash"]),
    }
    out = []
    for title, text in story["principles"]:
        if ("{index_weight}" in text and not pf["n_index"]) or ("{cash}" in text and not pf["cash"]) \
                or ("{n_issuers_words}" in text and not pf["n_issuers"]) or ("{tenor_min}" in text and not pf["tenor_min"]):
            continue
        try:
            out.append((title, text.format(**vals)))
        except (KeyError, IndexError):
            out.append((title, text))
    return out
