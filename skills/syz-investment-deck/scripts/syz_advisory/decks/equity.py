"""Equity / underlying charts on the SYZ template: any stock, ETF or index (an SP underlying too).

    equity_pages(ctx_like, symbol, ...)   two slides per symbol: price with 50/200-day averages and
                                          the facts; performance against a benchmark with beta
    build_chart_deck(symbols, market, out) a standalone deck of those pages (`--chart` in O01)

Statistics are calculated from daily closes: total return, annualised volatility, maximum
drawdown, beta and correlation to the benchmark (daily log returns), distance to the
52-week high and to the moving averages. Valuation and consensus come from Yahoo
(yfinance or the stdlib client) and are attributed as third-party data.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

from syz_advisory.decks import analytics as A
from syz_advisory.decks import charts as C
from syz_advisory.decks.ooxml import BLUEBERRY, BODY_B, BODY_L, BODY_T, BODY_W, GREY, MINT, ORANGE, AMBER, Deck
from syz_advisory.decks.sources import Market, Series


BENCH_NAMES = {"^GSPC": "S&P 500", "^NDX": "Nasdaq-100", "^DJI": "Dow Jones", "^RUT": "Russell 2000",
               "^SSMI": "SMI", "^STOXX50E": "Euro Stoxx 50", "^STOXX": "Stoxx Europe 600", "^GDAXI": "DAX",
               "^FCHI": "CAC 40", "^FTSE": "FTSE 100", "^N225": "Nikkei 225", "^HSI": "Hang Seng",
               "URTH": "MSCI World (iShares ETF)", "ACWI": "MSCI ACWI (iShares ETF)", "EEM": "MSCI Emerging Markets (ETF)",
               "SPY": "S&P 500 (SPDR ETF)", "AGG": "US Aggregate Bond (ETF)"}


def moving_average(closes: list[float], n: int) -> list[float | None]:
    out, run = [], 0.0
    for i, c in enumerate(closes):
        run += c
        if i >= n:
            run -= closes[i - n]
        out.append(round(run / n, 4) if i >= n - 1 else None)
    return out


def beta_corr(a: Series, b: Series) -> tuple[float | None, float | None]:
    dates, cols = A.align([a, b])
    x, y = cols
    ra, rb = [], []
    for i in range(1, len(dates)):
        if x[i] and x[i - 1] and y[i] and y[i - 1]:
            ra.append(math.log(x[i] / x[i - 1]))
            rb.append(math.log(y[i] / y[i - 1]))
    if len(ra) < 30:
        return None, None
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((p - ma) * (q - mb) for p, q in zip(ra, rb)) / (len(ra) - 1)
    va = sum((p - ma) ** 2 for p in ra) / (len(ra) - 1)
    vb = sum((q - mb) ** 2 for q in rb) / (len(rb) - 1)
    if not va or not vb:
        return None, None
    return cov / vb, cov / math.sqrt(va * vb)


def equity_stats(price: Series, total: Series, bench: Series | None, window_start: date) -> dict:
    """Figures for one security over the display window (moving averages use the longer history)."""
    shown = total.since(window_start)
    closes = price.closes
    ma50, ma200 = moving_average(closes, 50), moving_average(closes, 200)
    last = closes[-1] if closes else None
    year = price.since(date.fromisoformat(price.dates[-1]) - timedelta(days=365)) if price.dates else price
    hi, lo = (max(year.closes), min(year.closes)) if year.closes else (None, None)
    b, rho = beta_corr(shown, bench.since(window_start)) if bench and bench.closes else (None, None)
    return {"last": last, "last_date": price.dates[-1] if price.dates else None,
            "return": A.total_return(shown.closes), "vol": A.volatility(shown.closes), "mdd": A.max_drawdown(shown.closes),
            "hi52": hi, "lo52": lo, "from_high": last / hi - 1 if last and hi else None,
            "ma50": ma50[-1] if ma50 else None, "ma200": ma200[-1] if ma200 else None,
            "beta": b, "corr": rho}


def equity_pages(deck: Deck, market: Market, symbol: str, *, start: date, as_of: date, bench_symbol: str | None = None,
                 bench_name: str | None = None, name: str | None = None, content=None, flag=None, source=None) -> dict:
    """Add the pages for one symbol. `content(title, subtitle)` makes a content slide (the builder's,
    so agenda and sections work); `flag` / `source` record open points and sources."""
    from syz_advisory.decks.builder import money, pct, short_name
    flag = flag or (lambda *a: None)
    source = source or (lambda *a: None)
    content = content or (lambda t, st: _plain(deck, t, st))
    long_start = start - timedelta(days=300)            # room for the 200-day average
    price = market.prices(symbol, long_start)
    total = market.prices(symbol, long_start, adjusted=True)
    if not price.closes:
        flag(symbol, "no price history: chart pages skipped")
        return {}
    bench = market.prices(bench_symbol, long_start, adjusted=True) if bench_symbol else None
    info = market.info(symbol)
    name = name or info.get("longName") or info.get("shortName") or symbol
    ccy = info.get("currency") or ""
    st = equity_stats(price, total, bench, start)
    # --- page 1: price and trend
    shown = price.since(start)
    ma50 = moving_average(price.closes, 50)[-len(shown.closes):]
    ma200 = moving_average(price.closes, 200)[-len(shown.closes):]
    trend = ("above" if st["last"] and st["ma200"] and st["last"] > st["ma200"] else "below") if st["ma200"] else None
    message = (f"{pct(st['return'], 0, sign=True)} over the period, {pct(abs(st['from_high']), 0)} below its 52-week high"
               if st["from_high"] is not None and st["from_high"] < -0.005
               else f"{pct(st['return'], 0, sign=True)} over the period, at its 52-week high")
    s = content(short_name(name), message + (f" · {trend} its 200-day average" if trend else ""))
    series = {name: [round(c, 4) for c in shown.closes], "50-day average": ma50, "200-day average": ma200}
    styles = {name: (ORANGE, 2.0, None), "50-day average": (BLUEBERRY, 1.25, None), "200-day average": (GREY, 1.25, "dash")}
    xml, wb = C.lines_over_dates(shown.dates, series, styles=styles, fmt="#,##0.00")
    s.chart(BODY_L, BODY_T, 6.6, BODY_B - BODY_T - 0.35, xml, wb)
    s.caption(BODY_L, BODY_B - 0.3, 6.6, "Daily closes with 50- and 200-day averages.")
    dy = info.get("dividendYield")
    dy = dy / 100 if dy and dy > 1 else dy
    target = info.get("targetMeanPrice")
    facts = [["Fact", "Value"],
             ["Last close", f"{st['last']:,.2f} {ccy}".strip() + f" ({st['last_date']})" if st["last"] else "n/a"],
             ["52-week range", f"{st['lo52']:,.2f} – {st['hi52']:,.2f}" if st["hi52"] else "n/a"],
             ["vs 50 / 200-day average", " / ".join(pct(st["last"] / m - 1, 1, sign=True) if m else "n/a"
                                                    for m in (st["ma50"], st["ma200"]))],
             ["Total return (period)", pct(st["return"], 1, sign=True)],
             ["Volatility (annualised)", pct(st["vol"], 1)],
             ["Maximum drawdown", pct(st["mdd"], 1)],
             ["Market cap", money(info.get("marketCap"), ccy, short=True)],
             ["P/E trailing / forward", " / ".join(f"{info[k]:.1f}" if info.get(k) else "n/a" for k in ("trailingPE", "forwardPE"))],
             ["Dividend yield", pct(dy, 2)],
             ["Analyst target (mean)", f"{target:,.2f} ({pct(target / st['last'] - 1, 0, sign=True)})" if target and st["last"] else "n/a"],
             ["Analysts", str(info.get("numberOfAnalystOpinions") or "n/a")]]
    s.table(BODY_L + 6.85, BODY_T, BODY_W - 6.85, facts, size=11, max_h=BODY_B - BODY_T - 0.35)
    s.caption(BODY_L + 6.85, BODY_B - 0.3, BODY_W - 6.85, "Valuation and consensus: third-party data, not SYZ views.")
    # --- page 2: against the benchmark
    if bench and bench.closes:
        dates, cols = A.align([total.since(start), bench.since(start)])
        first = [next((c for c in col if c), None) for col in cols]
        bname = bench_name or BENCH_NAMES.get(bench_symbol, bench_symbol)
        series = {name: [round(c / first[0] * 100, 3) if c and first[0] else None for c in cols[0]],
                  bname: [round(c / first[1] * 100, 3) if c and first[1] else None for c in cols[1]]}
        r_own = series[name][-1] / 100 - 1 if series[name][-1] else None
        r_bench = series[bname][-1] / 100 - 1 if series[bname][-1] else None
        s2 = content(f"{short_name(name, 20)} vs {short_name(bname, 20)}",
                     (f"{pct(r_own, 0, sign=True)} vs {pct(r_bench, 0, sign=True)}, total return"
                      if r_own is not None and r_bench is not None else "Total return, rebased to 100")
                     + (f" · beta {st['beta']:.2f}, correlation {st['corr']:.2f}" if st["beta"] is not None else ""))
        xml, wb = C.lines_over_dates(dates, series, colors=[ORANGE, BLUEBERRY])
        s2.chart(BODY_L, BODY_T, BODY_W, BODY_B - BODY_T - 0.35, xml, wb)
        s2.caption(BODY_L, BODY_B - 0.3, BODY_W, "Dividend-adjusted closes, each in its own currency; beta and correlation "
                   "from daily returns.")
    source(f"{symbol}: Yahoo Finance prices and quote summary")
    return st


def _plain(deck: Deck, title: str, subtitle: str):
    s = deck.add("One Content")
    s.set_title(title)
    if subtitle:
        s.set_subtitle(subtitle)
    return s


def build_chart_deck(symbols: list[str], market: Market, out: Path, *, as_of: date | None = None, period_days: int = 365,
                     bench: str | None = None, bench_name: str | None = None) -> tuple[Path, list[tuple[str, str]]]:
    """A deck of equity pages for one or more symbols (the `--chart` command)."""
    from syz_advisory.decks.builder import Context, closing, cover, sources_slide
    as_of = as_of or date.today()
    market.as_of = market.as_of or as_of
    ctx = Context({"client": "Market charts"}, market, as_of, "")
    cover(ctx, "Equity and underlying charts")
    for sym in symbols:
        equity_pages(ctx.deck, market, sym, start=as_of - timedelta(days=period_days), as_of=as_of,
                     bench_symbol=bench, bench_name=bench_name,
                     content=lambda t, st: _section(ctx, t, st), flag=ctx.flag, source=ctx.source)
    sources_slide(ctx, ["Moving averages: simple 50- and 200-day averages of unadjusted closes.",
                        "Volatility: annualised standard deviation of daily log returns; beta and correlation vs the benchmark.",
                        "Past performance is no guide to future returns."])
    closing(ctx)
    ctx.deck.save(out)
    return out, ctx.flags


def _section(ctx, title, subtitle):
    from syz_advisory.decks.builder import content
    return content(ctx, title, subtitle, section="Charts")


def price_png(market: Market, symbol: str, out: Path, *, start: date, bench: str | None = None) -> Path | None:
    """The price chart as a PNG in the SYZ style, where matplotlib is available (claude.ai);
    None on machines where it cannot import."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    long_start = start - timedelta(days=300)
    price = market.prices(symbol, long_start)
    if not price.closes:
        return None
    shown = price.since(start)
    n = len(shown.closes)
    xs = [date.fromisoformat(d) for d in shown.dates]
    # House fonts, bundled with the skill (assets/fonts) so the chart does not depend on what is installed.
    fonts = Path(__file__).resolve().parents[3] / "assets" / "fonts"
    for ttf in fonts.glob("*.ttf"):
        matplotlib.font_manager.fontManager.addfont(str(ttf))
    plt.rcParams.update({"font.family": ["Nunito Sans", "DejaVu Sans"], "font.size": 9,
                         "axes.edgecolor": "#A6A9B5", "axes.labelcolor": "#202945", "xtick.color": "#8C8C8C",
                         "ytick.color": "#8C8C8C", "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=150)
    ax.plot(xs, shown.closes, color="#FF6C0E", lw=2, label=symbol)
    ax.plot(xs, moving_average(price.closes, 50)[-n:], color="#4B5F80", lw=1.2, label="50-day average")
    ax.plot(xs, moving_average(price.closes, 200)[-n:], color="#8C8C8C", lw=1.2, ls="--", label="200-day average")
    ax.grid(axis="y", color="#E3E5EB", lw=0.6)
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    ax.set_title(f"{symbol} - daily close", loc="left", color="#FFA400", fontsize=13, fontweight="bold",
                 fontfamily=["Nunito", "Nunito Sans", "DejaVu Sans"])
    fig.text(0.01, 0.01, "Source: Yahoo Finance, unadjusted daily closes; moving averages calculated.", color="#8C8C8C",
             fontsize=7, style="italic")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out
