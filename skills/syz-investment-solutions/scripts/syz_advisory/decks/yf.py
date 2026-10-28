"""yfinance behind the interface the decks use (chart / history / info / fund / search).

Used when `yfinance` imports (claude.ai: `pip install yfinance`). On SYZ machines it cannot
(numpy and pandas are blocked by group policy), and syz_advisory.marketdata -- the same Yahoo
endpoints through the standard library -- is used instead. Either way the decks see the same
shapes. `fallback` answers whatever yfinance does not (fund returns, search, failures).
"""

from __future__ import annotations


def available() -> bool:
    try:
        import yfinance  # noqa: F401
        return True
    except Exception:
        return False


class YFinanceClient:
    def __init__(self, fallback=None):
        import yfinance as yf
        self.yf = yf
        self.fallback = fallback

    @staticmethod
    def _rows(df, column: str) -> list[tuple[str, float]]:
        if df is None or len(df) == 0 or column not in df:
            return []
        out = []
        for idx, value in zip(df.index, df[column]):
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue
            if v == v:                                  # drop NaN
                out.append((str(idx)[:10], v))
        return out

    def chart(self, symbol, rng="1y", interval="1d", max_age=None):
        df = self.yf.Ticker(symbol).history(period=rng, interval=interval, auto_adjust=False)
        rows = self._rows(df, "Close")
        if not rows and self.fallback:
            return self.fallback.chart(symbol, rng, interval)
        return [{"date": d, "close": c} for d, c in rows]

    def history(self, symbol, rng="2y"):
        df = self.yf.Ticker(symbol).history(period=rng, auto_adjust=True)
        rows = self._rows(df, "Close")
        if not rows and self.fallback:
            return self.fallback.history(symbol, rng)
        return rows

    def info(self, symbol, max_age=None):
        try:
            data = dict(self.yf.Ticker(symbol).info or {})
        except Exception:
            data = {}
        if not data and self.fallback:
            return self.fallback.info(symbol)
        return data

    def fund(self, symbol, max_age=None):
        # Returns against the category come from the quote summary, which yfinance does not expose
        # in one place: the stdlib client is asked first, yfinance's funds_data fills the rest.
        base = {}
        if self.fallback:
            try:
                base = self.fallback.fund(symbol) or {}
            except Exception:
                base = {}
        try:
            fd = self.yf.Ticker(symbol).funds_data
            overview = dict(getattr(fd, "fund_overview", {}) or {})
            ops = getattr(fd, "fund_operations", None)
            expense = None
            if ops is not None and len(ops) and "Annual Report Expense Ratio" in ops.index:
                expense = float(ops.loc["Annual Report Expense Ratio"].iloc[0])
            top = getattr(fd, "top_holdings", None)
            holdings = []
            if top is not None and len(top):
                for sym, row in top.iterrows():
                    holdings.append({"symbol": sym, "name": row.get("Name"), "weight": float(row.get("Holding Percent", 0))})
            extra = {"family": overview.get("family"), "category": overview.get("categoryName"),
                     "legal_type": overview.get("legalType"), "expense_ratio": expense,
                     "top_holdings": holdings, "asset_mix": dict(getattr(fd, "asset_classes", {}) or {})}
        except Exception:
            extra = {}
        for k, v in extra.items():
            if v and not base.get(k):
                base[k] = v
        return base

    def search(self, query):
        try:
            quotes = self.yf.Search(query, max_results=5).quotes
            return [{"symbol": q.get("symbol"), "quoteType": q.get("quoteType")} for q in quotes]
        except Exception:
            return self.fallback.search(query) if self.fallback and hasattr(self.fallback, "search") else []

    def save(self):
        if self.fallback and hasattr(self.fallback, "save"):
            self.fallback.save()
