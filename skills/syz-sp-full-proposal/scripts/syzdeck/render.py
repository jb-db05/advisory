"""Step 7: the pages, as one A4 HTML document in the deck's layout and visual identity.

Page order (compact deck): cover, executive summary, the portfolio table, distance to protection,
thematic rationale, the basket cards (three per page), income and stress, important information.
The closing page is drawn last, from the original background, lettering and the vector logo.
"""

from __future__ import annotations

import base64
import datetime as dt
from html import escape
from pathlib import Path

from . import charts
from .story import pct, principles

ASSETS = Path(__file__).resolve().parents[2] / "assets"   # <skill>/assets
INK, ORANGE, GREY, MUL = "#202945", "#FF6C0E", "#8A8FA0", "#AC5D85"
FAMILY = ["#4B5F80", "#FF6C0E", "#3BAF90", "#FFC545", "#79D6FF", "#E6A4AD", "#AC5D85", "#9DD9D2", "#FFA400"]
CASH = "#7A7F95"
DISCLAIMER = [
    "This communication has been sent to recipients for information purposes only and cannot be considered to constitute an advertisement, an offer or a personalised recommendation to buy or sell a financial instrument or any other investment or currency.",
    "This communication is not directed to any person in any jurisdiction where, by reason of that person’s nationality, residence or otherwise, its dissemination or use is prohibited. It cannot be quoted, reproduced, disclosed, distributed or otherwise referred to, in whole or in part, to any third party without the Bank’s prior written consent.",
    "This communication may contain information on past performances of a financial product, all kinds of economic and financial valuations and analyses, as well as opinions of the Bank or of third parties. Any market valuations, terms and calculation methods, yields and opinions expressed are subject to change without notice. The information and opinions contained herein have been compiled and provided in good faith, based on information obtained from sources believed to be trustworthy. However, such information has not been independently verified. No guarantee, representation, or warranty of any kind, whether express or implied, is provided by the Bank or by relevant data vendors and other sources with respect to the accuracy, reliability, currentness or exhaustiveness of the information communicated, the methodology employed or the prices contained herein.",
    "Past performance is not a reliable indicator of current or future results. Any reference to the past performance of an investment does not guarantee its future performance. Fluctuations in exchange rates may adversely affect the value, price or income of any investment.",
    "Nothing in the present communication constitutes investment, legal, accounting or tax advice. This information is purely objective since it does not take into consideration the personal situation (including financial knowledge and experience), the investment objectives and risk profile of any recipient. Moreover, certain financial instruments mentioned (in particular, but not exclusively, derivatives, options and futures) involve a high risk of loss and may not be suitable. Accordingly, recipients should consult their own advisors on such matters, including but not limited to the possible tax consequences of investing in any financial product mentioned herein, and make their own assessment of the suitability of such investment product.",
    "Should a recipient make an investment on the basis of the present communication, the recipient alone shall bear the consequences thereof. In no event shall the Bank, its directors, employees, affiliates or agents be held responsible for damages of any kind arising out of the use of all or part of the information provided herein.",
]
WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
         11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen", 16: "Sixteen", 17: "Seventeen",
         18: "Eighteen", 19: "Nineteen", 20: "Twenty", 21: "Twenty-one", 22: "Twenty-two", 23: "Twenty-three", 24: "Twenty-four"}


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def css() -> str:
    reg, bold = (_b64(ASSETS / "fonts" / f) for f in ("NunitoSans-Regular.ttf", "NunitoSans-Bold.ttf"))
    return f"""
@font-face{{font-family:'Nunito Sans';src:url(data:font/ttf;base64,{reg}) format('truetype')}}
@font-face{{font-family:'Nunito Sans';font-weight:700;src:url(data:font/ttf;base64,{bold}) format('truetype')}}
@page{{size:A4;margin:0}}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0;background:#fff}}
body{{font-family:'Nunito Sans',Arial,sans-serif;color:{INK};font-size:8.4pt;line-height:1.3;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.page{{width:210mm;height:297mm;position:relative;overflow:hidden;page-break-after:always;break-after:page}}
.page:last-child{{page-break-after:auto}}
.in{{position:absolute;left:14mm;right:14mm;top:11mm;bottom:16mm}}
.kick{{color:{ORANGE};font-weight:700;font-size:7pt;letter-spacing:.02em;margin-top:1.6mm}}
.logo{{position:absolute;right:0;top:-3.5mm;height:10.4mm}}
h1{{font-size:17.5pt;margin:5mm 0 0;font-weight:700;letter-spacing:-.01em}}
h2{{font-size:11.5pt;margin:0;font-weight:700}}
.sub{{color:{ORANGE};font-weight:700;font-size:9.6pt;margin-top:1mm}}
.foot{{position:absolute;left:14mm;right:14mm;bottom:9mm;border-top:.5pt solid #E4E5EA;padding-top:2.6mm;display:flex;justify-content:space-between;font-size:6.2pt;color:{GREY}}}
.foot b{{color:{ORANGE};font-size:7.6pt;margin-left:4mm}}
.mu{{color:{GREY}}}
.hit{{color:{MUL}}}
/* cover */
.cover img.photo{{position:absolute;left:0;top:0;width:210mm;height:151.5mm;object-fit:cover}}
.cover .band{{position:absolute;left:0;top:151.5mm;width:210mm;height:1.7mm;background:{ORANGE}}}
.cover .clogo{{position:absolute;left:14mm;top:167mm;height:24mm}}
.cover .ck{{position:absolute;left:14mm;top:208mm;font-size:7.6pt;font-weight:700;color:#5D6380;letter-spacing:.02em}}
.cover h1{{position:absolute;left:14mm;top:215mm;width:132mm;font-size:24pt;line-height:1.18;color:{ORANGE};margin:0}}
.cover .cs{{position:absolute;left:14mm;top:243mm;font-size:10.6pt}}
.cover .cf{{position:absolute;left:14mm;right:14mm;top:272mm;border-top:.5pt solid #DADCE3;padding-top:3mm;display:flex;justify-content:space-between;font-size:7.4pt;font-weight:700}}
.cover .cf span:last-child{{color:{GREY};font-size:6.8pt}}
/* summary */
.obj{{font-size:9.6pt;line-height:1.48;margin:7mm 0 4mm}}
.kpi{{display:grid;grid-template-columns:repeat(3,1fr);row-gap:3.2mm;column-gap:6mm}}
.kpi b{{font-size:15pt;display:block;line-height:1.1}}
.kpi span{{font-size:6.6pt;color:{GREY};display:block;max-width:50mm}}
.rule{{border-top:1.4pt solid {INK};margin:6.5mm 0 3mm}}
.bars .r,.ib .r{{display:grid;align-items:center}}
.bars .r{{grid-template-columns:56mm 1fr 44mm;height:9.15mm}}
.bars .l{{font-size:7.6pt}}
.bars .b{{height:5.6mm}}
.bars .t,.ib .t{{white-space:nowrap;padding-left:2.5mm;overflow:hidden;text-overflow:ellipsis}}
.bars .t{{font-size:7.4pt}}
/* table */
table.pt,table.sx{{width:100%;border-collapse:collapse;table-layout:fixed;font-size:7.4pt}}
table.pt{{margin-top:5mm}}
.pt th,.sx th{{text-align:left;font-weight:700;font-size:7pt;padding:0 1.5mm 1.4mm;white-space:nowrap;border-bottom:.8pt solid {INK};vertical-align:bottom;line-height:1.2}}
.pt th:first-child,.pt td:first-child,.sx th:first-child,.sx td:first-child{{padding-left:0}}
.pt th:last-child,.pt td:last-child,.sx th:last-child,.sx td:last-child{{padding-right:0}}
.pt td,.sx td{{padding:1.6mm 1.5mm;border-bottom:.5pt solid #E4E5EA;vertical-align:top;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.pt td.bk{{white-space:normal}}
.pt .r,.sx .r{{text-align:right}}
.pt td.n{{font-weight:700}}
.pt .bk b{{display:block;font-size:7.5pt}}
.pt .bk span{{font-size:6.2pt;color:{GREY};display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.pt .bk b{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.pt .cp{{color:{ORANGE}}}
.note{{font-size:7pt;color:{GREY};line-height:1.45;margin-top:5mm;border-top:.5pt solid #E4E5EA;padding-top:4mm}}
.lead{{font-size:7.4pt;color:{GREY};margin:2.5mm 0 1mm;line-height:1.4}}
/* principles */
.tiles{{display:grid;grid-template-columns:repeat(3,1fr);gap:3.5mm;margin-top:4mm}}
.tile{{background:#F3F3F5;border-top:.9mm solid {ORANGE};padding:2.6mm 3.2mm 3mm;height:28.5mm}}
.tile b{{font-size:8.6pt;display:block;margin-bottom:1.2mm}}
.tile p{{margin:0;font-size:6.8pt;line-height:1.38}}
.fam{{margin-top:7mm}}
.fam .fh{{display:flex;justify-content:space-between;align-items:center;margin-top:4.6mm;margin-bottom:1.4mm}}
.fam .fh b{{font-size:9.8pt;border-left:1.1mm solid;padding-left:2.2mm;line-height:1.1}}
.fam .fh span{{font-size:7pt;font-weight:700}}
.fam .row{{display:flex;font-size:7.5pt;margin:.9mm 0}}
.fam .row .nn{{width:6mm;font-weight:700;padding-left:3.3mm;box-sizing:content-box}}
.fam .row .th{{width:59mm;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:2mm}}
/* cards */
.card{{position:relative;height:81.5mm;border-bottom:.5pt solid #E4E5EA;margin-bottom:2.6mm;padding-left:4.3mm}}
.card .bar{{position:absolute;left:0;top:0;bottom:2.5mm;width:.9mm}}
.card .num{{position:absolute;left:3.4mm;top:2.6mm;width:6.4mm;height:6.4mm;border-radius:50%;color:#fff;font-weight:700;font-size:7.6pt;display:flex;align-items:center;justify-content:center}}
.card .hd{{margin-left:9.4mm;padding-top:.6mm;width:118mm}}
.card .hd h3{{font-size:13.2pt;margin:0;line-height:1.2}}
.card .hd span{{font-size:6.8pt;color:{GREY};display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.card .cpn{{position:absolute;right:0;top:0;width:44.5mm;border-left:.9mm solid {ORANGE};padding-left:3mm;height:11.4mm}}
.card .cpn b{{font-size:17pt;color:{ORANGE};line-height:1}}
.card .cpn i{{font-style:normal;font-size:6.8pt;margin-left:1mm}}
.card .cpn span{{display:block;font-size:6.3pt;color:{GREY};margin-top:1mm}}
.card .ths{{font-weight:700;font-size:7.6pt;margin:3.4mm 0 1.6mm 1mm}}
.chips{{margin-left:1mm;white-space:nowrap;overflow:hidden}}
.chip{{display:inline-block;border:.5pt solid #9095A6;border-radius:3mm;padding:.35mm 2.2mm;font-size:6.5pt;margin-right:1.2mm}}
.card .ch{{position:absolute;left:4.3mm;top:27.6mm;width:107mm}}
.card .st{{position:absolute;right:0;top:27.7mm;width:66mm;height:51mm;background:#FFF5EF;padding:4.6mm 3.6mm}}
.card .st .g{{display:grid;grid-template-columns:1fr 1fr;row-gap:5.2mm}}
.card .st b{{font-size:13pt;display:block;line-height:1;white-space:nowrap}}
.card .st b.sm{{font-size:10.5pt}}
.card .st span{{font-size:6pt;color:{GREY};display:block;margin-top:.9mm}}
.card .st p{{font-size:6.6pt;margin:7mm 0 0;line-height:1.38}}
.cnote{{font-size:6.3pt;color:{GREY};margin-top:-1mm}}
/* svg text */
.ax{{font-size:6.6px;fill:{GREY};font-family:'Nunito Sans'}}
.lb{{font-size:6.7px;font-weight:700;fill:{INK};font-family:'Nunito Sans'}}
.lg{{font-size:6.7px;fill:{INK};font-family:'Nunito Sans'}}
.dl{{font-size:8.4px;fill:{INK};font-family:'Nunito Sans'}}
/* income */
.ib .r{{grid-template-columns:62mm 1fr 50mm;height:4.75mm;font-size:7.4pt}}
.ib .l{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:2mm}}
.ib .b{{height:3.5mm}}
.ib .t{{font-size:7pt}}
table.sx{{margin-top:2.4mm}}
h2.s{{margin-top:6mm}}
/* closing page */
.closing{{background:#FF7A0A}}
.closing img.bg{{position:absolute;left:-179.6pt;top:0;width:1496.69pt;height:841.89pt}}
.closing img.cl{{position:absolute;left:251.64pt;top:150pt;width:92pt;height:83.07pt}}
.closing img.wel{{position:absolute;left:97.64pt;top:430pt;width:400pt;height:77.55pt}}
.closing .offices{{position:absolute;left:14mm;right:14mm;top:211.6mm;display:grid;grid-template-columns:repeat(3,1fr);row-gap:9.4mm;color:#fff}}
.closing .offices b{{display:block;font-size:9pt;margin-bottom:1.3mm}}
.closing .offices span{{display:block;font-size:6.4pt;line-height:1.45}}
.closing .pc{{position:absolute;left:0;right:0;top:284.6mm;text-align:center;color:#fff;font-size:6.6pt;font-weight:700;letter-spacing:.02em}}
/* important information */
.ii h1{{font-size:21pt;margin-top:24mm;line-height:1.15;position:relative}}
.ii h1::before{{content:'';position:absolute;left:-4.8mm;top:.4mm;bottom:.4mm;width:1.3mm;background:{ORANGE}}}
.ii p{{font-size:8.2pt;line-height:1.6;margin:0 0 3.2mm;text-align:justify;text-justify:inter-word;hyphens:none}}
.ii .txt{{margin-top:11mm}}
"""


def _foot(story, date_long, page, last=False):
    right = f"<span>{'' if last else 'Please see important information at the end of the document'}<b>{page}</b></span>"
    return f'<div class="foot"><span>SYZ · {escape(story["title"])} · {date_long}</span>{right}</div>'


def _head(kicker, logo):
    return f'<img class="logo" src="data:image/svg+xml;base64,{logo}"><div class="kick">{escape(kicker)}</div>'


def _fall(x):
    return "–" if x is None else "below" if x >= 0 else f"{x * 100:.0f}%"


def _struck(p, asof):
    return bool(p.initial_fixing and p.initial_fixing <= asof.isoformat() and any(u.initial_level for u in p.underlyings))


def _pp(x, d=2):
    return "–" if x is None else f"{x * 100:.{d}f}%"


def build(products, cards, pf, story, asof: dt.date, auto: list[int]) -> str:
    logo = _b64(ASSETS / "logo.svg")
    photo = _b64(ASSETS / "cover.jpg")
    date_long = f"{asof.day} {asof.strftime('%B %Y')}"
    fam_of, fam_col = {}, {}
    for i, (fam, nums) in enumerate(story["clusters"].items()):
        fam_col[fam] = FAMILY[i % len(FAMILY)]
        for n in nums:
            fam_of[n] = fam
    col = lambda n: fam_col.get(fam_of.get(n), FAMILY[0])
    theme = lambda n: story["products"].get(str(n), {}).get("theme", f"Product {n}")
    thesis = lambda n: story["products"].get(str(n), {}).get("thesis", "")
    pages, pg = [], 1

    # 1 cover
    pages.append(f'''<div class="page cover"><img class="photo" src="data:image/jpeg;base64,{photo}"><div class="band"></div>
<img class="clogo" src="data:image/svg+xml;base64,{logo}"><div class="ck">{escape(story.get("kicker", ""))}</div>
<h1>{escape(story["title"])}</h1><div class="cs">{escape(story["subtitle"])}</div>
<div class="cf"><span>{date_long}</span><span>PRIVATE &amp; CONFIDENTIAL</span></div></div>''')

    # 2 executive summary
    pg += 1
    n = pf["n"]
    house = story.get("house_min_index")
    kpis = [(str(n), "Structured products, one theme each"),
            (_pp(pf["coupon_invested"]), "Average coupon p.a. on the invested part"),
            (_pp(pf["coupon_total"]), "Coupon p.a. on the whole portfolio, cash included"),
            (pct(pf["index_weight"]), "On global equity indices" + (f" (house minimum {pct(house)})" if house and pf["index_weight"] else "")),
            (pct(pf["cash"]), "Kept in cash"),
            (pct(pf["fall"]), "Average fall to protection, weighted")]
    fams = [(fam, pf["cluster_weights"].get(fam, 0), fam_col[fam], nums) for fam, nums in story["clusters"].items()]
    if pf["cash"]:
        fams.append(("Cash", pf["cash"], CASH, []))
    mx = max(w for _, w, _, _ in fams) or 1
    bars = "".join(f'<div class="r"><div class="l">{escape(f)}</div><div><div class="b" style="width:{100 * w / mx:.1f}%;background:{c}"></div></div>'
                   f'<div class="t">{pct(w)}{"&nbsp; products " + ", ".join(map(str, nums)) if nums else ""}</div></div>'
                   for f, w, c, nums in fams)
    pages.append(f'''<div class="page"><div class="in">{_head("EXECUTIVE SUMMARY", logo)}
<h1>The portfolio at a glance</h1><div class="sub">{n} thematic structured products &nbsp;·&nbsp; prices as of {asof.isoformat()}</div>
<p class="obj">{escape(story["objective"])}</p>
<div class="kpi">{"".join(f"<div><b>{v}</b><span>{escape(t)}</span></div>" for v, t in kpis)}</div>
<div class="rule"></div><h2>The portfolio by theme</h2><div class="bars" style="margin-top:3mm">{bars}</div>
</div>{_foot(story, date_long, pg)}</div>''')

    struck = [c.product.number for c in cards if _struck(c.product, asof)]
    level_note = ("Levels assume a strike at today's close" + (f"; products {', '.join(map(str, struck))} are placed at the initial fixing levels of their term sheets" if struck else "") + ".") \
        if len(struck) < len(cards) else "Protection levels are placed at the initial fixing levels of the term sheets."

    # 3 table
    pg += 1
    rows = []
    for c in cards:
        p = c.product
        names = " / ".join(l.short for l in c.legs) or " / ".join(u.name for u in p.underlyings)
        rows.append(f'''<tr><td class="n" style="color:{col(p.number)}">{p.number}</td>
<td class="bk"><b>{escape(theme(p.number))}</b><span>{escape(names)}</span></td>
<td class="cp r">{_pp(p.coupon)}</td><td>{escape(p.protection_label(short=True))}</td>
<td class="r">{p.tenor_months or "–"} m</td><td class="r">{pct(p.weight or 0)}</td><td>{escape(p.issuer or "TBD")}</td>
<td class="r">{_pp(c.coupon_to_maturity, 1)}</td><td class="r"><b class="{"hit" if (c.fall or -1) >= 0 else ""}">{_fall(c.fall)}</b></td>
<td class="r{" hit" if c.hit else ""}">{"–" if c.worst_low is None else f"{c.worst_low * 100:.0f}%"}</td></tr>''')
    if pf["cash"]:
        rows.append(f'<tr><td></td><td class="mu">Cash</td><td></td><td></td><td></td><td class="r mu">{pct(pf["cash"])}</td><td></td><td></td><td></td><td></td></tr>')
    title_n = WORDS.get(n, str(n))
    pages.append(f'''<div class="page"><div class="in">{_head("THE PORTFOLIO", logo)}
<h1>{title_n} products at a glance</h1>
<table class="pt"><colgroup><col style="width:6mm"><col style="width:47mm"><col style="width:12mm"><col style="width:32mm"><col style="width:10mm"><col style="width:11mm"><col style="width:27mm"><col style="width:13mm"><col style="width:13mm"><col style="width:11mm"></colgroup><tr><th>#</th><th>Basket</th><th class="r">Coupon</th><th>Protection</th><th class="r">Tenor</th><th class="r">Weight</th>
<th>Issuer</th><th class="r">Coupon to<br>maturity</th><th class="r">Fall to<br>protection</th><th class="r">1y low<br>% today</th></tr>{"".join(rows)}</table>
<p class="note">Fall to protection: how far every underlying can fall from today before capital is at risk at maturity. 1y low: the weakest underlying's lowest close of the past year, as a % of today; in pink when it was at or below the protection level. Weight: share of the model portfolio, from the proposal sheet. {level_note}</p>
</div>{_foot(story, date_long, pg)}</div>''')

    # 4 distance to protection
    pg += 1
    pages.append(f'''<div class="page"><div class="in">{_head("PROTECTION", logo)}
<h1>Distance to protection</h1>
<p class="lead">Today = 100%. The pink tick is the protection level (the barrier, or a low strike); the shaded area is below it. Dots show each underlying's lowest close of the past year, as a % of today: a dot in the shaded area means that name was below the protection level at some point.</p>
{charts.distance_chart(cards)}</div>{_foot(story, date_long, pg)}</div>''')

    # 5 rationale
    pg += 1
    tiles = "".join(f'<div class="tile"><b>{escape(t)}</b><p>{escape(x)}</p></div>' for t, x in principles(story, pf))
    famhtml = []
    for fam, nums in story["clusters"].items():
        c = fam_col[fam]
        r = "".join(f'<div class="row"><span class="nn" style="color:{c}">{n_}</span><span class="th">{escape(theme(n_))}</span><span>{escape(thesis(n_))}</span></div>'
                    for n_ in nums)
        famhtml.append(f'<div class="fh"><b style="border-color:{c}">{escape(fam)}</b><span style="color:{c}">{pct(pf["cluster_weights"].get(fam, 0))} of the portfolio</span></div>{r}')
    n_words = WORDS.get(n, str(n)).lower()
    prs = principles(story, pf)
    pr_words = WORDS.get(len(prs), str(len(prs)))
    pages.append(f'''<div class="page"><div class="in">{_head("THEMATIC RATIONALE", logo)}
<h1>{pr_words} principles, {n_words} conviction{"s" if n != 1 else ""}</h1><div class="tiles">{tiles}</div><div class="fam">{"".join(famhtml)}</div>
</div>{_foot(story, date_long, pg)}</div>''')

    # 6.. cards, three per page
    for i in range(0, len(cards), 3):
        pg += 1
        chunk = cards[i:i + 3]
        nums = f"{chunk[0].product.number}-{chunk[-1].product.number}" if len(chunk) > 1 else str(chunk[0].product.number)
        body = "".join(_card(c, col(c.product.number), theme(c.product.number), thesis(c.product.number)) for c in chunk)
        last = i + 3 >= len(cards)
        tail = f'<p class="cnote">Charts: one year, rebased to 100 at today\'s close; shaded area below the protection level. {level_note}</p>' if last else ""
        pages.append(f'''<div class="page"><div class="in">{_head(f"THE BASKETS · PRODUCTS {nums}", logo)}<div style="margin-top:8.8mm">{body}</div>{tail}
</div>{_foot(story, date_long, pg)}</div>''')

    # income, stress, issuers
    pg += 1
    mxc = max((c.product.coupon or 0) for c in cards) or 1
    inc = "".join(f'<div class="r"><div class="l">{c.product.number}&nbsp; {escape(theme(c.product.number))}</div>'
                  f'<div><div class="b" style="width:{100 * (c.product.coupon or 0) / mxc:.1f}%;background:{col(c.product.number)}"></div></div>'
                  f'<div class="t">{_pp(c.product.coupon)}&nbsp; p.a. &nbsp;·&nbsp; {_pp(c.coupon_to_maturity, 1)} over {c.product.tenor_months} months</div></div>'
                  for c in cards)
    srows = []
    for s in pf["stress"]:
        below = "none" if not s["below"] else "all" if len(s["below"]) == n else ", ".join(map(str, s["below"]))
        move = "Unchanged" if s["move"] == 0 else f"{s['move'] * 100:.0f}%"
        loss = "–" if s["loss"] == 0 else f"{s['loss'] * 100:.1f}%"
        net_cls = "hit" if s["net"] < 0 else ""
        srows.append(f'<tr><td>{move}</td><td class="r">+{s["coupons"] * 100:.1f}%</td><td class="r">{loss}</td>'
                     f'<td class="r"><b class="{net_cls}">{s["net"] * 100:+.1f}%</b></td><td style="padding-left:6mm">{below}</td></tr>')
    iss = sorted(pf["issuers"].items(), key=lambda kv: (kv[0] == "TBD", -kv[1], kv[0]))
    mxi = max(v for _, v in iss) or 1
    ibars = "".join(f'<div class="r"><div class="l">{escape(k)}</div><div><div class="b" style="width:{100 * v / mxi:.1f}%;background:{"#A9ABBA" if k == "TBD" else INK}"></div></div>'
                    f'<div class="t">{pct(v)}&nbsp; of the portfolio</div></div>' for k, v in iss)
    pages.append(f'''<div class="page"><div class="in">{_head("COUPON GENERATION", logo)}
<h1>Income per product, and what a fall would cost</h1>
<p class="lead">Coupon per product, % p.a. of nominal, and in total if the product runs to maturity. On average {_pp(pf["coupon_invested"])} p.a. on the invested part, {_pp(pf["coupon_total"])} p.a. on the whole portfolio including cash.</p>
<div class="ib">{inc}</div>
<h2 class="s">At maturity, if every underlying moves by the same amount</h2>
<table class="sx"><colgroup><col style="width:30mm"><col style="width:28mm"><col style="width:28mm"><col style="width:28mm"><col></colgroup><tr><th>Move of every<br>underlying</th><th class="r">Coupons,<br>% of portfolio</th><th class="r">Capital loss,<br>% of portfolio</th><th class="r">Net result,<br>% of portfolio</th><th style="padding-left:6mm">Products below protection</th></tr>{"".join(srows)}</table>
<p class="lead">Coupons counted in full; a symmetric stress, in reality the worst name of each basket falls more.</p>
<h2 class="s">Issuer credit: share of the portfolio per issuer</h2><div class="ib" style="margin-top:2mm">{ibars}</div>
</div>{_foot(story, date_long, pg)}</div>''')

    # important information
    pg += 1
    pages.append(f'''<div class="page ii"><div class="in"><img class="logo" src="data:image/svg+xml;base64,{logo}" style="right:0;top:-3.5mm">
<h1>Important Information</h1><div class="txt">{"".join(f"<p>{escape(t)}</p>" for t in DISCLAIMER)}</div>
</div>{_foot(story, date_long, pg, last=True)}</div>''')

    # closing page
    offices = [("Geneva", ["Banque Syz SA", "Quai des Bergues 1", "CH – 1201 Geneva", "T +41 58 799 10 00"]),
               ("Zurich", ["Banque Syz AG", "Freigutstrasse 14", "CH – 8002 Zurich", "T +41 58 799 77 37"]),
               ("Lugano", ["Banca Syz SA", "Via Nassa 42", "CH – 6900 Lugano", "T +41 58 799 67 20"]),
               ("Locarno", ["Banque Syz SA", "Via Cattori 4", "CH – 6601 Locarno", "T +41 58 799 66 66"]),
               ("Istanbul", ["Banque Syz SA", "Zorlu Center, Levazim, Koru Sokagi No:2", "34340 Besiktas / Istanbul – Turkey", "T +90 212 703 77 99"]),
               ("Johannesburg", ["Banque Syz SA", "First Floor, Future Space, 61 Katherine Street", "RSA – Sandton 2146", "T +27 (0)10 300 6040"])]
    off = "".join(f"<div><b>{c}</b>{''.join(f'<span>{escape(l)}</span>' for l in lines)}</div>" for c, lines in offices)
    pages.append(f'''<div class="page closing"><img class="bg" src="data:image/jpeg;base64,{_b64(ASSETS / "closing_bg.jpg")}">
<img class="cl" src="data:image/svg+xml;base64,{logo}"><img class="wel" src="data:image/png;base64,{_b64(ASSETS / "welcome.png")}">
<div class="offices">{off}</div><div class="pc">PRIVATE &amp; CONFIDENTIAL</div></div>''')

    return f'<!doctype html><html><head><meta charset="utf-8"><title>{escape(story["title"])}</title><style>{css()}</style></head><body>{"".join(pages)}</body></html>'


def _card(c, colour, theme, thesis) -> str:
    p = c.product
    longs = " / ".join(l.long for l in c.legs) or " / ".join(u.name for u in p.underlyings)
    chips = [p.protection_label(short=True), f"{p.tenor_months} months" if p.tenor_months else None]
    if p.stepdown:
        chips.append("Autocall step-down " + p.stepdown.replace("→", ">").replace("…", "..."))
    if p.currency and p.sources.get("currency") != "missing":
        chips.append(p.currency)
    if p.initial_fixing:
        chips.append("Initial fixing " + dt.date.fromisoformat(p.initial_fixing).strftime("%d.%m.%Y"))
    if p.final_fixing:
        chips.append("Final fixing " + dt.date.fromisoformat(p.final_fixing).strftime("%d.%m.%Y"))
    chips.append(f"Issuer {p.issuer or 'TBD'}")
    if p.isin:
        chips.append(p.isin)
    corr = "–" if c.corr_avg is None else f"{c.corr_avg:.2f} / {c.corr_min:.2f}"
    up = "–" if c.upside is None else ("0%" if round(c.upside * 100) == 0 else f"{c.upside * 100:+.0f}%")
    low = "–" if c.worst_low is None else f"{c.worst_low * 100:.0f}% vs {(c.protection_today or p.protection or 1) * 100:.0f}%"
    ctm = f"{c.coupon_to_maturity * 100:.1f}% over {p.tenor_months} months to maturity" if c.coupon_to_maturity is not None else "coupon to be quoted"
    return f'''<div class="card"><div class="bar" style="background:{colour}"></div><div class="num" style="background:{colour}">{p.number}</div>
<div class="hd"><h3>{escape(theme)}</h3><span>{escape(longs)}</span></div>
<div class="cpn"><b>{_pp(p.coupon)}</b><i>p.a. coupon</i><span>{ctm}</span></div>
<div class="ths">{escape(thesis)}</div><div class="chips">{"".join(f'<span class="chip">{escape(x)}</span>' for x in chips if x)}</div>
<div class="ch">{charts.basket_chart(c)}</div>
<div class="st"><div class="g"><div><b>{"–" if c.vol is None else f"{c.vol * 100:.0f}%"}</b><span>Volatility, 1y average</span></div><div><b>{corr}</b><span>Correlation avg / min</span></div>
<div><b>{up}</b><span>Analyst target upside</span></div><div><b class="{"hit" if c.hit else ""}{" sm" if len(low) > 11 else ""}">{low}</b><span>Worst 1y low / protection</span></div></div>
<p>{"<br>".join(escape(x) for x in c.notes)}</p></div></div>'''
