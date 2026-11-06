"""SYZ vol monitor: the implied-vol ranking and big-move alerts of SYZ_ADVISORY_VOL.xlsx, without Excel.

    python -m vol_monitor.app            # live Bloomberg (Desktop API, terminal logged in)
    python -m vol_monitor.app --demo     # demo data, no terminal needed

Opens http://localhost:8765 . The page refreshes itself; alerts are checked every
`alerts.check_seconds`, logged once per stock per day in data/alert_log.csv, shown as a browser
pop-up while the page is open, and e-mailed through Outlook when `alerts.email_to` is set.
The server listens on this PC only (127.0.0.1): Bloomberg Desktop API data is for the terminal user.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import engine
from .sources import BloombergSource, DemoSource, Store

ROOT = Path(__file__).resolve().parents[1]
DATA, STATIC = ROOT / "data", ROOT / "static"
CONFIG = ROOT / "config.json"
LOG = DATA / "alert_log.csv"
LOG_FIELDS = ["time", "list", "name", "ticker", "chg1d", "sigma", "chg5d", "reason"]


def read_list(name):
    with open(DATA / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_list(name, rows):
    with open(DATA / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


class Monitor:
    def __init__(self, demo: bool):
        self.cfg = json.loads(CONFIG.read_text())
        self.store = Store()
        self.lock = threading.Lock()
        self.focus, self.master = read_list("focus_list.csv"), read_list("master_list.csv")
        self.new_alerts: list[dict] = []          # since last page poll, for pop-ups
        if demo:
            self.source = DemoSource(self.store, DATA / "demo_snapshot.json")
        else:
            try:
                self.source = BloombergSource(self.store)
            except ImportError:
                sys.exit("blpapi is not installed: run setup (see README) or start with --demo")
        self.source.start(self.tickers(), self.cfg)
        threading.Thread(target=self._alert_loop, daemon=True).start()

    def tickers(self):
        return [r["ticker"] for r in self.focus + self.master if r.get("ticker")]

    # ---------------------------------------------------------------- state
    def state(self):
        data, updated, status = self.store.snapshot()
        with self.lock:
            f, m = engine.build_lists(self.focus, self.master, data, self.cfg["tiers"])
            al = engine.alerts(f, m, data, self.cfg["alerts"])
            popups, self.new_alerts = self.new_alerts, []
        return {"source": self.source.name, "status": status, "updated": updated, "config": self.cfg,
                "focus": f, "master": m, "alerts": [a for a in al if a["alert"]],
                "alerts_total": sum(a["alert"] for a in al), "log": self._read_log_today(),
                "popups": popups}

    # ---------------------------------------------------------------- alerts
    def _read_log_today(self):
        if not LOG.exists():
            return []
        today = dt.date.today().isoformat()
        with open(LOG, newline="", encoding="utf-8") as fh:
            return [r for r in csv.DictReader(fh) if r["time"].startswith(today)]

    def _alert_loop(self):
        while True:
            try:
                self.check_alerts()
            except Exception as e:                 # keep the loop alive
                print("alert check failed:", e, file=sys.stderr)
            time.sleep(max(10, float(self.cfg["alerts"]["check_seconds"])))

    def check_alerts(self):
        data, _, _ = self.store.snapshot()
        with self.lock:
            f, m = engine.build_lists(self.focus, self.master, data, self.cfg["tiers"])
            al = [a for a in engine.alerts(f, m, data, self.cfg["alerts"]) if a["alert"]]
        done = {r["ticker"] for r in self._read_log_today()}
        new = [a for a in al if a["ticker"] not in done]
        if not new:
            return
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        first = not LOG.exists()
        with open(LOG, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
            if first:
                w.writeheader()
            for a in new:
                w.writerow({"time": now, "list": a["list"], "name": a["name"], "ticker": a["ticker"],
                            "chg1d": _fmt(a["chg1d"]), "sigma": _fmt(a["sigma"]), "chg5d": _fmt(a["chg5d"]),
                            "reason": a["reason"]})
        with self.lock:
            self.new_alerts.extend(new)
        print(f"{now}  {len(new)} new alert(s): " + ", ".join(a["name"] for a in new[:8]))
        if self.cfg["alerts"].get("email_to"):
            send_email(self.cfg["alerts"]["email_to"], new)

    # ---------------------------------------------------------------- edits
    def save_settings(self, body):
        with self.lock:
            for grp in ("tiers", "alerts"):
                for k, v in body.get(grp, {}).items():
                    if k in self.cfg[grp]:
                        self.cfg[grp][k] = v if isinstance(self.cfg[grp][k], (str, bool)) else float(v)
            CONFIG.write_text(json.dumps(self.cfg, indent=2))

    def add_stock(self, body):
        lst, name, ticker = body.get("list"), (body.get("name") or "").strip(), (body.get("ticker") or "").strip()
        if not name or not ticker:
            return "name and Bloomberg ticker are required"
        if not ticker.lower().endswith(("equity", "index")):
            ticker += " Equity"
        with self.lock:
            if lst == "focus":
                self.focus.append({"name": name, "ticker": ticker, "region": body.get("region", ""),
                                   "industry": body.get("industry", ""), "cons_upside": "", "next_results": ""})
                write_list("focus_list.csv", self.focus)
            else:
                self.master.append({"name": name, "isin": (body.get("isin") or "").strip(), "ticker": ticker})
                write_list("master_list.csv", self.master)
        self.source.set_tickers(self.tickers(), self.cfg)
        return "ok"


def _fmt(x):
    return f"{x:+.2f}" if isinstance(x, (int, float)) else ""


def send_email(to, alerts):
    """E-mail through the Outlook installed on the terminal PC (needs pywin32)."""
    try:
        import win32com.client  # type: ignore
    except ImportError:
        print("e-mail skipped: pywin32 not installed (pip install pywin32)", file=sys.stderr)
        return
    rows = "".join(f"<tr><td>{a['name']}</td><td>{a['ticker']}</td><td>{a['reason']}</td></tr>" for a in alerts)
    mail = win32com.client.Dispatch("Outlook.Application").CreateItem(0)
    mail.To = to
    mail.Subject = f"SYZ vol monitor: {len(alerts)} new alert(s)"
    mail.HTMLBody = (f"<p>New big-move alerts ({dt.datetime.now():%H:%M}):</p>"
                     f"<table border='0' cellpadding='4'>{rows}</table>")
    mail.Send()


# -------------------------------------------------------------------- HTTP
def make_handler(mon: Monitor):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/state":
                return self._send(200, json.dumps(mon.state()).encode(), "application/json")
            target = (STATIC / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
            if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
                return self._send(404, b"not found", "text/plain")
            ctype = {".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".ttf": "font/ttf",
                     ".js": "text/javascript", ".css": "text/css"}.get(target.suffix, "application/octet-stream")
            self._send(200, target.read_bytes(), ctype)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/settings":
                mon.save_settings(body)
                return self._send(200, b'{"result":"ok"}', "application/json")
            if self.path == "/api/add":
                return self._send(200, json.dumps({"result": mon.add_stock(body)}).encode(), "application/json")
            self._send(404, b"not found", "text/plain")
    return H


def main(argv=None):
    ap = argparse.ArgumentParser(description="SYZ vol monitor")
    ap.add_argument("--demo", action="store_true", help="use the values saved in the Excel file")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    mon = Monitor(demo=a.demo)
    port = int(mon.cfg["server"]["port"])
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(mon))
    url = f"http://localhost:{port}"
    print(f"SYZ vol monitor running on {url}  ({mon.source.name}). Ctrl+C to stop.")
    if not a.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
