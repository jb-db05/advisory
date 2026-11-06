"""The calculations of SYZ_ADVISORY_VOL.xlsx, without Excel.

Every rule mirrors a formula in the workbook:
- Rank: highest IV 3M first; ties keep list order (RANK + COUNTIF).
- Rank in region: 1 + number of stocks in the same region with a higher IV 3M (COUNTIFS).
- Vol tier: Low / Medium / High / Very high from the tier thresholds on IV 3M.
- IV / HV 3M: IV 3M divided by HV 90 days.
- Region (master list): from Bloomberg country of risk (CH, US/CA, the European list, else EM & RoW).
- Ticker check (master list): Bloomberg ISIN equals the typed ISIN.
- Alerts: |change today| >= daily threshold, |move in sigma| >= sigma threshold, or
  |change 5 days| >= 5-day threshold; move in sigma = change today / (IV 3M / sqrt(252)).
"""
from __future__ import annotations

import math

EUROPE = {"GB", "FR", "DE", "NL", "IT", "ES", "BE", "PT", "SE", "DK", "FI", "NO", "AT", "IE", "LU",
          "PL", "GR", "CZ", "HU", "JE", "GG", "IM"}


def region_from_country(code: str | None) -> str:
    if not code:
        return ""
    if code == "CH":
        return "Switzerland"
    if code in ("US", "CA"):
        return "North America"
    if code in EUROPE:
        return "Europe ex-Switzerland"
    return "Emerging Markets & RoW"


def tier(iv3m, tiers) -> str:
    if not isinstance(iv3m, (int, float)):
        return ""
    if iv3m >= tiers["very_high"]:
        return "Very high"
    if iv3m >= tiers["high"]:
        return "High"
    if iv3m >= tiers["medium"]:
        return "Medium"
    return "Low"


def _rank(rows, key="iv3m"):
    """Excel RANK(desc) + COUNTIF tie-break: equal values keep their list order."""
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    for i, r in enumerate(rows):
        v = r.get(key)
        if not isinstance(v, (int, float)):
            r["rank"] = None
            continue
        higher = sum(1 for x in vals if x > v)
        same_before = sum(1 for p in rows[:i] if p.get(key) == v)
        r["rank"] = higher + same_before + 1
    for r in rows:
        v = r.get(key)
        r["rank_region"] = (None if not isinstance(v, (int, float)) else
                            1 + sum(1 for p in rows if p["region"] == r["region"]
                                    and isinstance(p.get(key), (int, float)) and p[key] > v))


def build_lists(focus, master, data, tiers):
    """focus/master: rows from the CSV lists; data: {ticker: fields}. Returns two lists of rows."""
    f_out, m_out = [], []
    for s in focus:
        d = data.get(s["ticker"], {})
        iv3, hv = d.get("iv3m"), d.get("hv90")
        f_out.append({
            "name": s["name"], "ticker": s["ticker"], "currency": d.get("currency") or "",
            "region": s.get("region", ""), "industry": s.get("industry", ""), "iv3m": iv3, "iv1m": d.get("iv1m"), "iv12m": d.get("iv12m"),
            "hv90": hv, "iv_hv": iv3 / hv if isinstance(iv3, (int, float)) and isinstance(hv, (int, float)) and hv else None,
            "tier": tier(iv3, tiers), "cons_upside": s.get("cons_upside", ""),
            "next_results": s.get("next_results", ""), "isin": d.get("isin") or "",
            "error": d.get("error"),
        })
    focus_isins = {r["isin"] for r in f_out if r["isin"]}
    for s in master:
        d = data.get(s["ticker"], {}) if s["ticker"] else {}
        iv3, hv = d.get("iv3m"), d.get("hv90")
        if not s["ticker"]:
            check = "enter ticker"
        elif d.get("error") or not d.get("isin"):
            check = "not found"
        else:
            check = "OK" if d.get("isin") == s["isin"] else "ISIN differs"
        m_out.append({
            "name": s["name"], "isin": s["isin"], "ticker": s["ticker"], "currency": d.get("currency") or "",
            "region": region_from_country(d.get("country")), "sector": d.get("sector") or "",
            "iv3m": iv3, "iv12m": d.get("iv12m"), "hv90": hv,
            "iv_hv": iv3 / hv if isinstance(iv3, (int, float)) and isinstance(hv, (int, float)) and hv else None,
            "tier": tier(iv3, tiers), "in_focus": "Yes" if s["isin"] in focus_isins else "",
            "check": check, "error": d.get("error"),
        })
    _rank(f_out)
    _rank(m_out)
    return f_out, m_out


def alerts(focus_rows, master_rows, data, th):
    """One row per stock (focus first, then master), with the alert flag and reason."""
    out = []
    for lst, rows in (("Focus", focus_rows), ("Master", master_rows)):
        for r in rows:
            if not r["ticker"]:
                continue
            d = data.get(r["ticker"], {})
            chg, chg5, iv3 = d.get("chg1d"), d.get("chg5d"), r.get("iv3m")
            exp_move = iv3 / math.sqrt(252) if isinstance(iv3, (int, float)) else None
            sigma = chg / exp_move if isinstance(chg, (int, float)) and exp_move else None
            reasons = []
            if isinstance(chg, (int, float)) and abs(chg) >= th["daily_pct"]:
                reasons.append(f"Today {chg:+.1f}%")
            if isinstance(sigma, (int, float)) and abs(sigma) >= th["sigma"]:
                reasons.append(f"{sigma:+.1f} sigma")
            if isinstance(chg5, (int, float)) and abs(chg5) >= th["five_day_pct"]:
                reasons.append(f"5 days {chg5:+.1f}%")
            out.append({"list": lst, "name": r["name"], "ticker": r["ticker"], "currency": r["currency"],
                        "last": d.get("last"),
                        "chg1d": chg, "chg5d": chg5, "iv3m": iv3, "exp_move": exp_move, "sigma": sigma,
                        "alert": bool(reasons), "reason": "   ".join(reasons)})
    return out
