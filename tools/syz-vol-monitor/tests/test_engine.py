"""Checks the calculations against the results saved in SYZ_ADVISORY_VOL.xlsx (demo snapshot).

    python -m pytest tests          (or: python tests/test_engine.py)
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vol_monitor import engine  # noqa: E402


def load():
    rd = lambda n: list(csv.DictReader(open(ROOT / "data" / n, encoding="utf-8")))
    data = json.loads((ROOT / "data" / "demo_snapshot.json").read_text())["securities"]
    f, m = engine.build_lists(rd("focus_list.csv"), rd("master_list.csv"), data,
                              {"medium": 20, "high": 30, "very_high": 40})
    return f, m, data


def test_matches_excel():
    f, m, data = load()
    assert len(f) == 48 and len(m) == 535
    top = min((r for r in f if r["rank"]), key=lambda r: r["rank"])
    assert (top["name"], top["tier"]) == ("Palo Alto Networks", "Very high")      # Excel Ranking row 1
    assert next(r for r in f if r["name"] == "Alphabet")["rank"] == 18            # Excel Focus list
    assert next(r for r in m if r["name"] == "ZURICH INSURANCE")["rank_region"] == 32
    assert sum(r["check"] == "ISIN differs" for r in m) == 14
    al = engine.alerts(f, m, data, {"daily_pct": 5, "sigma": 2.5, "five_day_pct": 10})
    assert sum(a["alert"] for a in al) == 150                                     # Excel Alerts count


def test_currency_in_demo():
    from vol_monitor.sources import ccy_from_ticker
    assert [ccy_from_ticker(t) for t in ("PANW US Equity", "ZURN SW Equity", "AAL LN Equity",
                                         "2513 HK Equity", "ASML NA Equity")] == ["USD", "CHF", "GBp", "HKD", "EUR"]


def test_region_and_tier_rules():
    assert engine.region_from_country("CH") == "Switzerland"
    assert engine.region_from_country("CA") == "North America"
    assert engine.region_from_country("JE") == "Europe ex-Switzerland"
    assert engine.region_from_country("JP") == "Emerging Markets & RoW"
    t = {"medium": 20, "high": 30, "very_high": 40}
    assert [engine.tier(x, t) for x in (19.9, 20, 30, 40, None)] == ["Low", "Medium", "High", "Very high", ""]


if __name__ == "__main__":
    test_matches_excel(); test_region_and_tier_rules(); test_currency_in_demo(); print("all checks passed")
