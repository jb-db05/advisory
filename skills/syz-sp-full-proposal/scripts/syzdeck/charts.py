"""Vector charts (inline SVG) in the deck's style."""

from __future__ import annotations

import datetime as dt
import math
from html import escape

INK, GREY, MUL, SHADE = "#202945", "#8A8FA0", "#AC5D85", "#F4EBEF"
LEGS = ["#FF6C0E", "#4B5F80", "#3BAF90", "#FFC545", "#79D6FF"]


def _nice_step(span: float) -> int:
    for s in (5, 10, 20, 25, 50):
        if span / s <= 7:
            return s
    return 100


def basket_chart(card, w=400, h=184) -> str:
    """One year rebased to 100 today, protection dashed with the area below shaded, legend below."""
    p, legs = card.product, card.legs
    L, R, T, B = 26, 102, 5, 34          # plot box margins; legend under the x labels
    if not legs:
        return f'<svg viewBox="0 0 {w} {h}" width="100%"><text x="{w/2}" y="{h/2}" class="ax" text-anchor="middle">no prices</text></svg>'
    prot = 100 * (card.protection_today or p.protection or 1)
    lo = min(min(min(l.rebased) for l in legs), prot)
    hi = max(max(max(l.rebased) for l in legs), 100)
    step = _nice_step(hi - lo + 10)
    y0 = math.floor((lo - 3) / step) * step
    y1 = math.ceil((hi + 3) / step) * step
    dates = sorted({d for l in legs for d in l.dates})
    ix = {d: i for i, d in enumerate(dates)}
    n = max(len(dates) - 1, 1)
    X = lambda i: L + (w - L - R) * i / n
    Y = lambda v: T + (h - T - B) * (y1 - v) / (y1 - y0)
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    v = y0
    while v <= y1 + 1e-9:
        s.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{INK}" stroke-opacity=".09" stroke-width=".6"/>'
                 f'<text x="{L-4}" y="{Y(v)+2.6:.1f}" class="ax" text-anchor="end">{v:.0f}</text>')
        v += step
    # shaded area below the protection, and the protection line
    s.append(f'<rect x="{L}" y="{Y(prot):.1f}" width="{w-L-R}" height="{Y(y0)-Y(prot):.1f}" fill="{SHADE}"/>')
    s.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(prot):.1f}" y2="{Y(prot):.1f}" stroke="{MUL}" stroke-width=".9" stroke-dasharray="4 3"/>')
    s.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(y0):.1f}" y2="{Y(y0):.1f}" stroke="{INK}" stroke-opacity=".35" stroke-width=".6"/>')
    # month labels every two months
    seen = set()
    for d in dates:
        m = d[:7]
        if m in seen:
            continue
        seen.add(m)
        if (len(seen) - 1) % 2 == 0:
            lab = dt.date.fromisoformat(d).strftime("%b %y")
            s.append(f'<text x="{X(ix[d]):.1f}" y="{Y(y0)+10:.1f}" class="ax" text-anchor="middle">{lab}</text>')
    # lines
    for j, l in enumerate(legs):
        pts = " ".join(f"{X(ix[d]):.1f},{Y(v):.1f}" for d, v in zip(l.dates, l.rebased))
        s.append(f'<polyline points="{pts}" fill="none" stroke="{LEGS[j % len(LEGS)]}" stroke-width="1.15" stroke-linejoin="round"/>')
    s.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(100):.1f}" y2="{Y(100):.1f}" stroke="{INK}" stroke-width="1"/>'
             f'<circle cx="{w-R:.1f}" cy="{Y(100):.1f}" r="2.6" fill="{INK}"/>')
    barrier = p.protection_type and "barrier" in p.protection_type
    today_lab = "Today = strike 100" if barrier and (p.strike or 1) >= 0.999 else "Today 100"
    prot_lab = (f"{'European' if p.protection_type == 'european barrier' else 'American'} barrier {prot:.0f}" if barrier
                else f"Strike {prot:.0f} (protection)")
    struck = any(u.initial_level for u in p.underlyings) and p.initial_fixing
    closest = max(legs, key=lambda l: l.protection_today).short if struck and len(legs) > 1 else ""
    if struck:
        today_lab = "Today 100"
    ty, py = Y(100), Y(prot)
    if abs(ty - py) < 10:
        py = ty + 10
    s.append(f'<text x="{w-R+6}" y="{ty+2.8:.1f}" class="lb">{today_lab}</text>')
    s.append(f'<text x="{w-R+6}" y="{py+2.8:.1f}" class="lb" fill="{MUL}">{prot_lab}</text>')
    if closest:   # a product already struck: the line is the level of the name closest to its protection
        s.append(f'<text x="{w-R+6}" y="{py+10.5:.1f}" class="ax" fill="{MUL}">closest: {escape(closest)}</text>')
    # legend
    x = L - 18
    for j, l in enumerate(legs):
        col = LEGS[j % len(LEGS)]
        s.append(f'<line x1="{x}" x2="{x+9}" y1="{h-8}" y2="{h-8}" stroke="{col}" stroke-width="2"/>'
                 f'<text x="{x+13}" y="{h-5.4}" class="lg">{escape(l.short)}</text>')
        x += 22 + 4.6 * len(l.short)
    s.append("</svg>")
    return "".join(s)


def distance_chart(cards, w=700) -> str:
    """Per product: shaded up to the protection, the protection tick, each name's 1y low, today."""
    lows = [l.low for c in cards for l in c.legs] + [c.protection_today or 1 for c in cards]
    x0 = min(0.30, math.floor(min(lows) * 10) / 10 - 0.0)
    x1 = max(1.0, math.ceil(max(c.protection_today or 1 for c in cards) * 10 - 1e-9) / 10)
    L, R, T, rh = 210, 6, 22, 22.4
    h = T + rh * len(cards) + 6
    X = lambda v: L + (w - L - R) * (v - x0) / (x1 - x0)
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    t = x0
    while t <= x1 + 1e-4:
        s.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{T-6}" y2="{h}" stroke="{INK}" stroke-opacity=".08" stroke-width=".7"/>'
                 f'<text x="{X(t):.1f}" y="{T-9}" class="ax" text-anchor="middle">{t*100:.0f}%</text>')
        t = round(t + 0.1, 2)
    for i, c in enumerate(cards):
        y = T + rh * i + rh / 2
        names = " / ".join(l.short for l in c.legs) or " / ".join(u.name for u in c.product.underlyings)
        lab = f"{c.product.number}  {names}"
        if len(lab) > 44:
            lab = lab[:43].rstrip() + "…"
        prot = c.protection_today or c.product.protection or 1
        s.append(f'<text x="0" y="{y+3:.1f}" class="dl">{escape(lab)}</text>')
        s.append(f'<rect x="{X(x0):.1f}" y="{y-6:.1f}" width="{X(prot)-X(x0):.1f}" height="12" fill="{SHADE}"/>')
        if c.legs:
            lo = min(l.low for l in c.legs)
            s.append(f'<line x1="{X(min(lo, prot)):.1f}" x2="{X(max(1, prot)):.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GREY}" stroke-width=".8"/>')
        s.append(f'<rect x="{X(prot)-1.3:.1f}" y="{y-7:.1f}" width="2.6" height="14" fill="{MUL}"/>')
        for j, l in enumerate(c.legs):
            s.append(f'<circle cx="{X(max(l.low, x0)):.1f}" cy="{y:.1f}" r="3.6" fill="{LEGS[j % len(LEGS)]}" stroke="#fff" stroke-width=".8"/>')
        s.append(f'<circle cx="{X(1):.1f}" cy="{y:.1f}" r="3.6" fill="{INK}"/>')
    s.append("</svg>")
    return "".join(s)


def hbars(rows, max_value, bar_w=300, label_w=0, row_h=18, text=lambda r: "", h_bar=11) -> str:
    """Horizontal bars: rows of (label, value, colour). Labels are drawn in HTML around it."""
    h = row_h * len(rows)
    s = [f'<svg viewBox="0 0 {bar_w + 160} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for i, r in enumerate(rows):
        y = i * row_h + (row_h - h_bar) / 2
        bw = bar_w * r[1] / max_value if max_value else 0
        s.append(f'<rect x="0" y="{y:.1f}" width="{bw:.1f}" height="{h_bar}" fill="{r[2]}"/>'
                 f'<text x="{bw+6:.1f}" y="{y+h_bar-2.5:.1f}" class="bt">{escape(text(r))}</text>')
    s.append("</svg>")
    return "".join(s)
