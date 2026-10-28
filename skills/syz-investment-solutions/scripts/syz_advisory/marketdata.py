"""Live market data from Yahoo Finance, on the standard library alone.

The `yfinance` package cannot be used on these machines: it imports numpy and
pandas, whose compiled extensions are blocked by group policy. This module talks
to the same Yahoo endpoints yfinance uses (quote, chart, quoteSummary, search)
through `urllib`, and keeps a JSON cache on disk so repeated runs are fast and
work through short outages.

Everything returned is plain dicts and lists of floats.
"""

from __future__ import annotations

import http.cookiejar
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from syz_advisory import config

log = config.get_logger("marketdata")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
QUERY1 = "https://query1.finance.yahoo.com"
QUERY2 = "https://query2.finance.yahoo.com"

# Cache lifetimes, in seconds.
TTL_QUOTE = 4 * 3600
TTL_HISTORY = 12 * 3600
TTL_PROFILE = 30 * 86400
TTL_SEARCH = 30 * 86400
TTL_INFO = 3600
TTL_INTRADAY = 60
TTL_EARNINGS = 7 * 86400

# quoteSummary modules merged into `info`, in priority order (first non-empty
# value wins), as yfinance's Ticker.info does.
INFO_MODULES = ("price", "summaryDetail", "defaultKeyStatistics", "financialData", "assetProfile",
                "quoteType", "calendarEvents")

# Quote currencies Yahoo gives in minor units. Market caps for these listings
# come back in the major unit (SHEL.L: price in GBp, market cap in GBP).
MINOR_UNITS = {"GBp": ("GBP", 100.0), "GBX": ("GBP", 100.0),
               "ZAc": ("ZAR", 100.0), "ILA": ("ILS", 100.0)}

DEFAULT_CACHE = config.DATA / "S00" / "cache" / "marketdata.json"
_LOADED: dict[Path, tuple[int, dict]] = {}     # cache file -> (mtime, parsed content)


def major_currency(currency: str | None) -> tuple[str | None, float]:
    """'GBp' -> ('GBP', 100.0); 'EUR' -> ('EUR', 1.0)."""
    if currency in MINOR_UNITS:
        return MINOR_UNITS[currency]
    return currency, 1.0


class YahooClient:
    """Thin Yahoo Finance client with a crumb session and a disk cache."""

    def __init__(self, cache_path: Path | None = DEFAULT_CACHE, offline: bool = False,
                 timeout: float = 20.0, workers: int = 8):
        self.cache_path = cache_path
        self.offline = offline
        self.timeout = timeout
        self.workers = workers
        self._cache: dict[str, dict] = {}
        self._dirty = False
        self._lock = threading.Lock()
        self._crumb: str | None = None
        jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        # No Accept header: the quote endpoint answers 406 to application/json.
        self._opener.addheaders = [("User-Agent", USER_AGENT)]
        if cache_path and cache_path.is_file():
            # The app makes a client per request: reuse the parsed file while it
            # is unchanged on disk rather than parsing megabytes of JSON again.
            stamp = cache_path.stat().st_mtime_ns
            kept = _LOADED.get(cache_path)
            if kept and kept[0] == stamp:
                self._cache = dict(kept[1])
            else:
                try:
                    self._cache = json.loads(cache_path.read_text(encoding="utf-8"))
                    _LOADED[cache_path] = (stamp, dict(self._cache))
                except (OSError, json.JSONDecodeError):
                    log.warning("Ignoring unreadable cache %s", cache_path)

    # --- cache --------------------------------------------------------------
    def _cached(self, key: str, ttl: float):
        entry = self._cache.get(key)
        if entry and (self.offline or time.time() - entry["t"] < ttl):
            return entry["v"]
        return None

    def _store(self, key: str, value) -> None:
        with self._lock:
            self._cache[key] = {"t": time.time(), "v": value}
            self._dirty = True

    def save(self) -> None:
        if not self.cache_path or not self._dirty:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = json.dumps(self._cache, separators=(",", ":"))
            snapshot = dict(self._cache)
            self._dirty = False
        self.cache_path.write_text(payload, encoding="utf-8")
        _LOADED[self.cache_path] = (self.cache_path.stat().st_mtime_ns, snapshot)

    # --- http ---------------------------------------------------------------
    def _get(self, url: str, crumb: bool = False) -> dict:
        if crumb:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}crumb={urllib.parse.quote(self._get_crumb())}"
        last: Exception | None = None
        for attempt in range(3):
            try:
                with self._opener.open(url, timeout=self.timeout) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code == 401 and crumb:   # crumb expired: renew once
                    self._crumb = None
                    url = url.rsplit("crumb=", 1)[0] + "crumb=" + urllib.parse.quote(self._get_crumb())
                elif exc.code == 404:
                    raise
                # 429 = rate limited: back off properly before the next try.
                time.sleep(3.0 * 2 ** attempt if exc.code == 429 else 0.6 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError) as exc:
                last = exc
                time.sleep(0.6 * (attempt + 1))
        raise RuntimeError(f"Yahoo request failed: {last}")

    def _get_crumb(self) -> str:
        with self._lock:
            if self._crumb:
                return self._crumb
            try:  # sets the session cookie; the page itself is a 404
                self._opener.open("https://fc.yahoo.com", timeout=self.timeout)
            except Exception:
                pass
            with self._opener.open(f"{QUERY1}/v1/test/getcrumb", timeout=self.timeout) as r:
                self._crumb = r.read().decode().strip()
            return self._crumb

    # --- quotes -------------------------------------------------------------
    def quotes(self, symbols: list[str], max_age: float | None = None) -> dict[str, dict]:
        """Snapshot quote per symbol: price, currency, market cap, volume, 52w.
        `max_age` (seconds) overrides the cache lifetime; 0 always asks Yahoo."""
        out: dict[str, dict] = {}
        missing = []
        for symbol in dict.fromkeys(symbols):
            hit = self._cached(f"quote:{symbol}", TTL_QUOTE if max_age is None else max_age)
            if hit is not None:
                out[symbol] = hit
            else:
                missing.append(symbol)
        if missing and not self.offline:
            for i in range(0, len(missing), 40):
                chunk = missing[i:i + 40]
                url = f"{QUERY1}/v7/finance/quote?symbols=" + urllib.parse.quote(",".join(chunk))
                try:
                    rows = self._get(url, crumb=True)["quoteResponse"]["result"]
                except Exception as exc:
                    log.warning("Quote request failed for %d symbols: %s", len(chunk), exc)
                    continue
                for row in rows:
                    quote = _shape_quote(row)
                    out[quote["symbol"]] = quote
                    self._store(f"quote:{quote['symbol']}", quote)
                for symbol in chunk:   # remember misses so we do not re-ask
                    if symbol not in out:
                        self._store(f"quote:{symbol}", {})
                        out[symbol] = {}
        return out

    def fx_to_usd(self, currencies: set[str], max_age: float | None = None) -> dict[str, float]:
        """Multiplier from each major currency to USD (USD -> 1.0)."""
        rates = {"USD": 1.0}
        pairs = {c: f"{c}USD=X" for c in currencies if c and c != "USD"}
        quotes = self.quotes(list(pairs.values()), max_age)
        for currency, pair in pairs.items():
            price = quotes.get(pair, {}).get("price")
            if price:
                rates[currency] = price
        return rates

    # --- history ------------------------------------------------------------
    def history(self, symbol: str, range_: str = "2y") -> list[tuple[str, float]]:
        """Daily (ISO date, adjusted close) pairs, oldest first."""
        key = f"hist:{range_}:{symbol}"
        hit = self._cached(key, TTL_HISTORY)
        if hit is not None:
            return [tuple(x) for x in hit]
        if self.offline:
            return []
        url = (f"{QUERY2}/v8/finance/chart/{urllib.parse.quote(symbol)}"
               f"?range={range_}&interval=1d&includeAdjustedClose=true")
        try:
            result = self._get(url)["chart"]["result"][0]
        except Exception as exc:
            log.warning("No history for %s: %s", symbol, exc)
            if _is_not_found(exc):      # a real miss; transient errors are retried next run
                self._store(key, [])
            return []
        stamps = result.get("timestamp") or []
        indicators = result.get("indicators", {})
        closes = (indicators.get("adjclose") or [{}])[0].get("adjclose") \
            or indicators.get("quote", [{}])[0].get("close") or []
        series = [
            (datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(), float(c))
            for t, c in zip(stamps, closes) if c is not None
        ]
        self._store(key, series)
        return series

    def long_history(self, symbol: str) -> list[tuple[str, float]]:
        """Ten years of daily closes, for backtesting product terms."""
        return self.history(symbol, "10y")

    def histories(self, symbols: list[str], range_: str = "2y") -> dict[str, list]:
        unique = list(dict.fromkeys(symbols))
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            return dict(zip(unique, pool.map(lambda s: self.history(s, range_), unique)))

    def chart(self, symbol: str, range_: str = "1mo", interval: str = "1d",
              max_age: float | None = None) -> list[dict]:
        """OHLCV bars, oldest first: what yfinance's Ticker.history returns.
        Dates are exchange-local; intraday bars carry the time as well."""
        intraday = interval[-1] in "mh"
        key = f"chart:{range_}:{interval}:{symbol}"
        hit = self._cached(key, (TTL_INTRADAY if intraday else TTL_HISTORY) if max_age is None else max_age)
        if hit is not None:
            return hit
        if self.offline:
            return []
        url = (f"{QUERY2}/v8/finance/chart/{urllib.parse.quote(symbol)}?range={urllib.parse.quote(range_)}"
               f"&interval={urllib.parse.quote(interval)}&includeAdjustedClose=true&events=div,split")
        result = self._get(url)["chart"]["result"][0]
        offset = (result.get("meta") or {}).get("gmtoffset") or 0
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        adj = ((result.get("indicators", {}).get("adjclose") or [{}])[0]).get("adjclose")
        bars = []
        for i, stamp in enumerate(result.get("timestamp") or []):
            close = _at(quote.get("close"), i)
            if close is None:
                continue
            local = datetime.fromtimestamp(stamp + offset, tz=timezone.utc)
            bars.append({
                "date": local.strftime("%Y-%m-%d %H:%M") if intraday else local.date().isoformat(),
                "open": _at(quote.get("open"), i), "high": _at(quote.get("high"), i),
                "low": _at(quote.get("low"), i), "close": close,
                "adj_close": _at(adj, i) if adj else close, "volume": _at(quote.get("volume"), i),
            })
        self._store(key, bars)
        return bars

    def news(self, symbol: str, count: int = 15) -> list[dict]:
        """Latest headlines about a symbol, newest first: [{'date', 'publisher', 'title', 'link'}]."""
        url = (f"{QUERY1}/v1/finance/search?q={urllib.parse.quote(symbol)}&newsCount={count}"
               "&quotesCount=0&enableFuzzyQuery=false")
        try:
            rows = self._get(url).get("news") or []
        except Exception as exc:
            log.warning("No news for %s: %s", symbol, exc)
            return []
        return [{"date": datetime.fromtimestamp(n.get("providerPublishTime") or 0, tz=timezone.utc).date().isoformat(),
                 "publisher": n.get("publisher") or "", "title": n.get("title") or "", "link": n.get("link") or ""}
                for n in rows]

    def info(self, symbol: str, max_age: float | None = None) -> dict:
        """Everything Yahoo knows about one symbol, flattened like yfinance's
        Ticker.info: price, valuation, financials, profile, next events.
        Values are raw numbers; dates are epoch seconds, as in yfinance."""
        key = f"info:{symbol}"
        hit = self._cached(key, TTL_INFO if max_age is None else max_age)
        if hit is not None:
            return hit
        if self.offline:
            return {}
        url = (f"{QUERY2}/v10/finance/quoteSummary/{urllib.parse.quote(symbol)}"
               f"?modules={','.join(INFO_MODULES)}")
        try:
            result = self._get(url, crumb=True)["quoteSummary"]["result"][0]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                self._store(key, {})
                return {}
            raise
        value: dict = {"symbol": symbol}
        for module in INFO_MODULES:
            data = _unwrap(result.get(module)) or {}      # Yahoo leaves out modules it has nothing for
            if module == "calendarEvents":
                earnings = data.get("earnings") or {}
                data = {"earningsDates": earnings.get("earningsDate"),
                        "earningsAverage": earnings.get("earningsAverage"),
                        "revenueAverage": earnings.get("revenueAverage"),
                        "exDividendDate": data.get("exDividendDate"),
                        "dividendDate": data.get("dividendDate")}
            for k, v in data.items():
                if k != "maxAge" and value.get(k) is None:
                    value[k] = v
        self._store(key, value)
        return value

    def infos(self, symbols: list[str], max_age: float | None = None) -> dict[str, dict]:
        """`info` for many symbols in parallel; a symbol that fails maps to {}."""
        def one(symbol):
            try:
                return self.info(symbol, max_age)
            except Exception as exc:
                log.warning("No info for %s: %s", symbol, exc)
                return {}
        unique = list(dict.fromkeys(symbols))
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            return dict(zip(unique, pool.map(one, unique)))

    def fund(self, symbol: str, max_age: float | None = None) -> dict:
        """Fund / ETF facts: family, category, fees, assets, top holdings, returns
        against the category. Fractions as Yahoo gives them (0.0009 = 0.09%)."""
        key = f"fund:{symbol}"
        hit = self._cached(key, TTL_INFO if max_age is None else max_age)
        if hit is not None:
            return hit
        if self.offline:
            return {}
        url = (f"{QUERY2}/v10/finance/quoteSummary/{urllib.parse.quote(symbol)}"
               "?modules=fundProfile,topHoldings,fundPerformance,price")
        try:
            result = self._get(url, crumb=True)["quoteSummary"]["result"][0]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                self._store(key, {})
                return {}
            raise
        profile = _unwrap(result.get("fundProfile")) or {}
        fees = profile.get("feesExpensesInvestment") or {}
        holdings = _unwrap(result.get("topHoldings")) or {}
        perf = _unwrap(result.get("fundPerformance")) or {}
        overview, category = perf.get("performanceOverview") or {}, perf.get("performanceOverviewCat") or {}
        price = _unwrap(result.get("price")) or {}
        value = {
            "symbol": symbol, "name": price.get("longName") or price.get("shortName"),
            "currency": price.get("currency"), "family": profile.get("family"),
            "category": profile.get("categoryName"), "legal_type": profile.get("legalType"),
            "expense_ratio": fees.get("annualReportExpenseRatio") or fees.get("netExpRatio"),
            "turnover": fees.get("annualHoldingsTurnover"), "total_assets": fees.get("totalNetAssets"),
            "asset_mix": {k: holdings.get(f"{k}Position") for k in ("stock", "bond", "cash", "other")},
            "top_holdings": [{"symbol": h.get("symbol"), "name": h.get("holdingName"), "weight": h.get("holdingPercent")}
                             for h in holdings.get("holdings") or []],
            "sectors": {k: v for d in holdings.get("sectorWeightings") or [] for k, v in d.items()},
            "returns": {k: overview.get(k) for k in ("ytdReturnPct", "oneYearTotalReturn", "threeYearTotalReturn", "fiveYrAvgReturnPct")},
            "category_returns": {k: category.get(k) for k in ("ytdReturnPct", "oneYearTotalReturn", "threeYearTotalReturn", "fiveYrAvgReturnPct")},
            "as_of": overview.get("asOfDate"),
        }
        self._store(key, value)
        return value

    # --- reference ----------------------------------------------------------
    def profile(self, symbol: str) -> dict:
        """Sector and industry, for classifying names nobody has mapped yet."""
        key = f"profile:{symbol}"
        hit = self._cached(key, TTL_PROFILE)
        if hit is not None or self.offline:
            return hit or {}
        url = f"{QUERY2}/v10/finance/quoteSummary/{urllib.parse.quote(symbol)}?modules=assetProfile"
        try:
            data = self._get(url, crumb=True)["quoteSummary"]["result"][0]["assetProfile"]
            value = {"sector": data.get("sector"), "industry": data.get("industry"),
                     "country": data.get("country")}
        except Exception as exc:
            log.debug("No profile for %s: %s", symbol, exc)
            if not _is_not_found(exc):
                return {}
            value = {}
        self._store(key, value)
        return value

    def earnings_dates(self, symbol: str, size: int = 250) -> list[dict] | None:
        """Past and announced earnings events, newest first: what yfinance's get_earnings_dates reads.
        Each: {"when": ISO UTC timestamp, "time_type": "BMO" / "AMC" / "TAS" / "TNS" / ...,
        "eps_estimate", "eps_actual", "surprise_pct"}. Yahoo's coverage is uneven: thin outside the
        US and it can lag recent quarters. None when the request failed (not cached, retried next run)."""
        key = f"earnings:{symbol}"
        hit = self._cached(key, TTL_EARNINGS)
        if hit is not None or self.offline:
            return hit
        body = {"size": size, "offset": 0, "sortField": "startdatetime", "sortType": "DESC", "entityIdType": "earnings",
                "query": {"operator": "and", "operands": [{"operator": "eq", "operands": ["ticker", symbol]},
                                                          {"operator": "eq", "operands": ["eventtype", "2"]}]},
                "includeFields": ["startdatetime", "startdatetimetype", "epsestimate", "epsactual", "epssurprisepct"]}
        url = f"{QUERY1}/v1/finance/visualization?lang=en-US&region=US&crumb=" + urllib.parse.quote(self._get_crumb())
        last: Exception | None = None
        for attempt in range(3):
            request = urllib.request.Request(url, data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"})
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    result = json.load(response)["finance"]["result"]
                break
            except urllib.error.HTTPError as exc:
                last = exc
                time.sleep(3.0 * 2 ** attempt if exc.code == 429 else 0.6 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
                last = exc
                time.sleep(0.6 * (attempt + 1))
        else:
            log.warning("No earnings dates for %s: %s", symbol, last)
            return None
        rows = (result[0]["documents"][0].get("rows") or []) if result and result[0].get("documents") else []
        value = [{"when": r[0], "time_type": r[1], "eps_estimate": r[2], "eps_actual": r[3], "surprise_pct": r[4]}
                 for r in rows if r and r[0]]
        self._store(key, value)
        return value

    def earnings_reported(self, symbol: str) -> list[dict] | None:
        """The last four reported quarters from quoteSummary's `earnings` module, oldest first:
        {"when": ISO UTC timestamp of the report, "eps_estimate", "eps_actual", "surprise_pct"}.
        Fills the recent quarters that earnings_dates() can lag. None when the request failed."""
        key = f"earnings-reported:{symbol}"
        hit = self._cached(key, TTL_EARNINGS)
        if hit is not None or self.offline:
            return hit
        try:
            result = self._get(f"{QUERY2}/v10/finance/quoteSummary/{urllib.parse.quote(symbol)}?modules=earnings",
                               crumb=True)["quoteSummary"]["result"] or [{}]
        except Exception as exc:
            if not _is_not_found(exc):
                log.warning("No reported earnings for %s: %s", symbol, exc)
                return None
            result = [{}]
        value = []
        for q in ((result[0].get("earnings") or {}).get("earningsChart") or {}).get("quarterly") or []:
            stamp = _unwrap(q.get("reportedDate"))
            if not stamp:
                continue
            value.append({"when": datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                          "eps_estimate": _unwrap(q.get("estimate")), "eps_actual": _unwrap(q.get("actual")),
                          "surprise_pct": float(q["surprisePct"]) if q.get("surprisePct") not in (None, "") else None})
        self._store(key, value)
        return value

    def search(self, query: str) -> list[dict]:
        """Yahoo symbol search. Loose -- callers must filter what they accept."""
        key = f"search:{query.upper()}"
        hit = self._cached(key, TTL_SEARCH)
        if hit is not None or self.offline:
            return hit or []
        url = (f"{QUERY2}/v1/finance/search?q={urllib.parse.quote(query)}"
               "&quotesCount=10&newsCount=0&listsCount=0")
        try:
            rows = self._get(url).get("quotes", [])
        except Exception as exc:
            log.debug("Search failed for %s: %s", query, exc)
            return []     # not cached: a rate-limited search must be retried
        value = [{"symbol": r.get("symbol"), "type": r.get("quoteType"),
                  "exchange": r.get("exchange"), "name": r.get("longname") or r.get("shortname")}
                 for r in rows if r.get("symbol")]
        self._store(key, value)
        return value


def snapshot(client: "YahooClient", symbols: list[str], max_age: float | None = None) -> dict[str, dict]:
    """Quotes plus the figures every screen needs, in USD where it matters:
    market cap (bn), traded value per day (m), days to earnings, distance from
    the 52-week high and from the 200-day average."""
    symbols = list(dict.fromkeys(s for s in symbols if s))
    fresh = {} if max_age is None else {"max_age": max_age}    # keeps simpler clients (test fakes) working
    quotes = client.quotes(symbols, **fresh)
    currencies = {major_currency(q.get("currency"))[0] for q in quotes.values() if q}
    fx = client.fx_to_usd({c for c in currencies if c}, **fresh)
    now = time.time()
    rows = {}
    for symbol in symbols:
        quote = quotes.get(symbol) or {}
        ccy, divisor = major_currency(quote.get("currency"))
        rate = fx.get(ccy) if ccy else None
        price = quote.get("price")
        row = {"symbol": symbol, **quote, "ccy": ccy}
        row["mcap_usd_bn"] = quote["market_cap"] * rate / 1e9 if quote.get("market_cap") and rate else None
        row["adv_musd"] = (quote["avg_volume"] * price / divisor * rate / 1e6
                           if quote.get("avg_volume") and price and rate else None)
        stamp = quote.get("earnings")
        row["earnings_in_days"] = int((stamp - now) // 86400) if stamp and stamp > now - 86400 else None
        row["vs_high_52w"] = price / quote["high_52w"] - 1 if price and quote.get("high_52w") else None
        row["vs_ma200"] = price / quote["ma_200"] - 1 if price and quote.get("ma_200") else None
        change = quote.get("change_52w")
        row["change_52w"] = change / 100 if change is not None else None     # Yahoo gives percent
        rows[symbol] = row
    return rows


def _is_not_found(exc: Exception) -> bool:
    return isinstance(exc, urllib.error.HTTPError) and exc.code == 404


def _at(values, i):
    return values[i] if values and i < len(values) else None


def _unwrap(value):
    """Yahoo's {"raw": 1.2, "fmt": "1.20"} -> 1.2, recursively; {} -> None."""
    if isinstance(value, dict):
        if "raw" in value:
            return value["raw"]
        if not value:
            return None
        return {k: _unwrap(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unwrap(v) for v in value]
    return value


def _shape_quote(row: dict) -> dict:
    return {
        "symbol": row.get("symbol"),
        "name": row.get("longName") or row.get("shortName"),
        "type": row.get("quoteType"),
        "currency": row.get("currency"),
        "exchange": row.get("fullExchangeName") or row.get("exchange"),
        "market_state": row.get("marketState"),
        "time": row.get("regularMarketTime"),
        "price": row.get("regularMarketPrice"),
        "change": row.get("regularMarketChange"),
        "change_pct": row.get("regularMarketChangePercent"),
        "previous_close": row.get("regularMarketPreviousClose"),
        "open": row.get("regularMarketOpen"),
        "day_high": row.get("regularMarketDayHigh"),
        "day_low": row.get("regularMarketDayLow"),
        "volume": row.get("regularMarketVolume"),
        "bid": row.get("bid"),
        "ask": row.get("ask"),
        "market_cap": row.get("marketCap"),
        "avg_volume": row.get("averageDailyVolume3Month"),
        "high_52w": row.get("fiftyTwoWeekHigh"),
        "low_52w": row.get("fiftyTwoWeekLow"),
        "pe": row.get("trailingPE"),
        "forward_pe": row.get("forwardPE"),
        "change_52w": row.get("fiftyTwoWeekChangePercent"),
        "ma_50": row.get("fiftyDayAverage"),
        "ma_200": row.get("twoHundredDayAverage"),
        "sector": row.get("sector"),
        "dividend_yield": row.get("trailingAnnualDividendYield"),
        # Next (or latest) results date, epoch seconds.
        "earnings": row.get("earningsTimestampStart") or row.get("earningsTimestamp"),
    }


# --- yfinance-style facade ---------------------------------------------------
# For code and notebooks written against yfinance: the same names, live data,
# no numpy. Results are dicts and lists instead of pandas objects.

PERIODS = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
INTERVALS = ("1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo")

_shared: YahooClient | None = None


def _client() -> YahooClient:
    global _shared
    if _shared is None:
        _shared = YahooClient(cache_path=None)    # in memory only: always live
    return _shared


class Ticker:
    """yfinance.Ticker look-alike: Ticker("NESN.SW").info, .fast_info, .history()."""

    def __init__(self, symbol: str, client: YahooClient | None = None):
        self.ticker = symbol.strip().upper()
        self._c = client or _client()

    def __repr__(self) -> str:
        return f"Ticker({self.ticker!r})"

    @property
    def info(self) -> dict:
        return self._c.info(self.ticker, max_age=0)

    @property
    def fast_info(self) -> dict:
        """Live quote: price, change, day range, volume, market cap, 52w range."""
        return self._c.quotes([self.ticker], max_age=0).get(self.ticker) or {}

    def history(self, period: str = "1mo", interval: str = "1d") -> list[dict]:
        if period not in PERIODS or interval not in INTERVALS:
            raise ValueError(f"period must be one of {PERIODS}, interval one of {INTERVALS}")
        return self._c.chart(self.ticker, period, interval, max_age=0)


class Tickers:
    """yfinance.Tickers look-alike: Tickers("AAPL MSFT").tickers["AAPL"].info."""

    def __init__(self, symbols: str | list[str], client: YahooClient | None = None):
        names = symbols.replace(",", " ").split() if isinstance(symbols, str) else symbols
        client = client or _client()
        self.tickers = {t.ticker: t for t in (Ticker(s, client) for s in names)}

    def quotes(self) -> dict[str, dict]:
        """One live quote request for all of them (40 symbols per call)."""
        return next(iter(self.tickers.values()))._c.quotes(list(self.tickers), max_age=0) if self.tickers else {}


def download(symbols: str | list[str], period: str = "1mo", interval: str = "1d") -> dict[str, list[dict]]:
    """yfinance.download look-alike: {symbol: OHLCV bars}, fetched in parallel."""
    tickers = Tickers(symbols).tickers
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(tickers, pool.map(lambda t: t.history(period, interval), tickers.values())))
