"""Where the numbers come from: live Bloomberg (Desktop API on the terminal) or the demo snapshot.

Both sources fill the same store: {ticker: {"iv3m", "iv1m", "iv12m", "hv90", "isin", "country",
"sector", "currency", "last", "chg1d", "chg5d", "error"}}.

Bloomberg use, mirroring the Excel workbook:
- LAST_PRICE and RT_PX_CHG_PCT_1D: live subscription (//blp/mktdata), as Excel's BDP does for
  real-time fields; this does not count against the daily reference-data limit.
- Vols and CHG_PCT_5D: reference data request every `vol_refresh_minutes`.
- ID_ISIN, CNTRY_OF_RISK, GICS_SECTOR_NAME, CRNCY (trading currency): reference data request once a day.

The Desktop API serves the user logged in to this terminal only: keep the tool on this PC.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import time
from pathlib import Path


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.data: dict[str, dict] = {}
        self.updated: dict[str, str] = {}      # what -> timestamp
        self.status = "starting"

    def update(self, ticker, **fields):
        with self.lock:
            self.data.setdefault(ticker, {}).update({k: v for k, v in fields.items()})

    def stamp(self, what):
        with self.lock:
            self.updated[what] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def snapshot(self):
        with self.lock:
            return {k: dict(v) for k, v in self.data.items()}, dict(self.updated), self.status


# Demo mode only: the workbook did not store currencies, so infer the usual trading currency from the
# Bloomberg exchange code. Live mode reads CRNCY from Bloomberg instead.
EXCHANGE_CCY = {
    "US": "USD", "CN": "CAD", "SW": "CHF", "LN": "GBp", "GY": "EUR", "GR": "EUR", "FP": "EUR", "NA": "EUR",
    "IM": "EUR", "SM": "EUR", "BB": "EUR", "PL": "EUR", "FH": "EUR", "ID": "EUR", "AV": "EUR", "DC": "DKK",
    "SS": "SEK", "PW": "PLN", "HK": "HKD", "JP": "JPY", "TT": "TWD", "KS": "KRW", "IN": "INR", "CH": "CNY",
    "AU": "AUD", "SP": "SGD", "IJ": "IDR", "PM": "PHP", "BZ": "BRL", "MM": "MXN", "SJ": "ZAr", "UH": "AED",
    "DH": "AED", "AB": "SAR",
}


def ccy_from_ticker(ticker: str) -> str | None:
    parts = ticker.split()
    return EXCHANGE_CCY.get(parts[-2]) if len(parts) >= 3 else None


class DemoSource:
    """The values Bloomberg returned when the Excel file was saved. For testing without a terminal."""
    name = "demo (values saved in SYZ_ADVISORY_VOL.xlsx)"

    def __init__(self, store: Store, path: Path):
        self.store, self.path = store, path

    def start(self, tickers, cfg):
        snap = json.loads(self.path.read_text())["securities"]
        for tk in tickers:
            if tk in snap:
                self.store.update(tk, **snap[tk])
                if not snap[tk].get("currency"):
                    self.store.update(tk, currency=ccy_from_ticker(tk))
            else:
                self.store.update(tk, error="not in demo snapshot")
        self.store.stamp("prices"); self.store.stamp("vols"); self.store.stamp("reference")
        self.store.status = "demo data"

    def set_tickers(self, tickers, cfg):
        self.start(tickers, cfg)


class BloombergSource:
    name = "Bloomberg (Desktop API)"

    def __init__(self, store: Store):
        import blpapi  # noqa: F401  (fails early when the package is missing)
        self.blpapi = blpapi
        self.store = store
        self.session = None
        self.tickers: list[str] = []
        self.cfg: dict = {}
        self._req_id = 0
        self._pending: dict = {}      # correlation id -> kind ("vols" / "reference")

    # ---------------------------------------------------------------- session
    def start(self, tickers, cfg):
        b = self.blpapi
        self.cfg = cfg
        opts = b.SessionOptions()
        opts.setServerHost(cfg["bloomberg"]["host"])
        opts.setServerPort(int(cfg["bloomberg"]["port"]))
        self.session = b.Session(opts)
        if not self.session.start():
            raise RuntimeError("cannot connect to Bloomberg: is the terminal running and logged in?")
        for svc in ("//blp/refdata", "//blp/mktdata"):
            if not self.session.openService(svc):
                raise RuntimeError(f"cannot open {svc}")
        self.store.status = "connected"
        self.set_tickers(tickers, cfg)
        threading.Thread(target=self._loop, daemon=True).start()

    def set_tickers(self, tickers, cfg):
        """(Re)subscribe and reload everything for a new list of tickers."""
        b = self.blpapi
        self.cfg = cfg
        if self.tickers:
            old = b.SubscriptionList()
            for tk in self.tickers:
                old.add(tk, "LAST_PRICE,RT_PX_CHG_PCT_1D", "", b.CorrelationId(tk))
            try:
                self.session.unsubscribe(old)
            except Exception:
                pass
        self.tickers = list(dict.fromkeys(t for t in tickers if t))
        subs = b.SubscriptionList()
        for tk in self.tickers:
            subs.add(tk, "LAST_PRICE,RT_PX_CHG_PCT_1D", "", b.CorrelationId(tk))
        self.session.subscribe(subs)
        self.request("reference"); self.request("vols")

    # ---------------------------------------------------------------- requests
    def request(self, kind):
        b = self.blpapi
        f = self.cfg["bloomberg"]["fields"]
        fields = ([f["iv3m"], f["iv1m"], f["iv12m"], f["hv90"], "CHG_PCT_5D"] if kind == "vols"
                  else ["ID_ISIN", "CNTRY_OF_RISK", "GICS_SECTOR_NAME", "CRNCY"])
        svc = self.session.getService("//blp/refdata")
        for i in range(0, len(self.tickers), 400):
            req = svc.createRequest("ReferenceDataRequest")
            for tk in self.tickers[i:i + 400]:
                req.getElement("securities").appendValue(tk)
            for fld in fields:
                req.getElement("fields").appendValue(fld)
            self._req_id += 1
            cid = b.CorrelationId(f"{kind}-{self._req_id}")
            self._pending[cid.value()] = kind
            self.session.sendRequest(req, correlationId=cid)

    def _parse_reference(self, msg, kind):
        f = self.cfg["bloomberg"]["fields"]
        names = ({f["iv3m"]: "iv3m", f["iv1m"]: "iv1m", f["iv12m"]: "iv12m", f["hv90"]: "hv90",
                  "CHG_PCT_5D": "chg5d"} if kind == "vols"
                 else {"ID_ISIN": "isin", "CNTRY_OF_RISK": "country", "GICS_SECTOR_NAME": "sector",
                       "CRNCY": "currency"})
        arr = msg.asElement().getElement("securityData")
        for i in range(arr.numValues()):
            sd = arr.getValueAsElement(i)
            tk = sd.getElementAsString("security")
            if sd.hasElement("securityError"):
                self.store.update(tk, error=sd.getElement("securityError").getElementAsString("message"))
                continue
            fd = sd.getElement("fieldData")
            vals = {}
            for bbg, key in names.items():
                if fd.hasElement(bbg):
                    el = fd.getElement(bbg)
                    try:
                        vals[key] = el.getValueAsFloat() if key not in ("isin", "country", "sector", "currency") \
                            else el.getValueAsString()
                    except Exception:
                        vals[key] = None
                else:
                    vals[key] = None
            vals["error"] = None
            self.store.update(tk, **vals)

    # ---------------------------------------------------------------- event loop
    def _loop(self):
        b = self.blpapi
        next_vols = time.time() + 60 * float(self.cfg["bloomberg"]["vol_refresh_minutes"])
        next_ref = time.time() + 24 * 3600
        while True:
            ev = self.session.nextEvent(1000)
            et = ev.eventType()
            for msg in ev:
                if et in (b.Event.RESPONSE, b.Event.PARTIAL_RESPONSE):
                    cid = msg.correlationIds()[0].value()
                    kind = self._pending.get(cid)
                    if kind and msg.asElement().hasElement("securityData"):
                        self._parse_reference(msg, kind)
                    if et == b.Event.RESPONSE and kind:
                        self._pending.pop(cid, None)
                        self.store.stamp(kind)
                elif et == b.Event.SUBSCRIPTION_DATA:
                    tk = msg.correlationIds()[0].value()
                    el, vals = msg.asElement(), {}
                    if el.hasElement("LAST_PRICE", True):
                        vals["last"] = el.getElementAsFloat("LAST_PRICE")
                    if el.hasElement("RT_PX_CHG_PCT_1D", True):
                        vals["chg1d"] = el.getElementAsFloat("RT_PX_CHG_PCT_1D")
                    if vals:
                        self.store.update(tk, **vals)
                        self.store.stamp("prices")
                elif et == b.Event.SUBSCRIPTION_STATUS and msg.messageType() == b.Name("SubscriptionFailure"):
                    self.store.update(msg.correlationIds()[0].value(), error="no live price (subscription failed)")
                elif et == b.Event.SESSION_STATUS and msg.messageType() in (b.Name("SessionTerminated"),
                                                                            b.Name("SessionConnectionDown")):
                    self.store.status = "connection lost: restart the tool"
            now = time.time()
            if now >= next_vols:
                self.request("vols")
                next_vols = now + 60 * float(self.cfg["bloomberg"]["vol_refresh_minutes"])
            if now >= next_ref:
                self.request("reference")
                next_ref = now + 24 * 3600
