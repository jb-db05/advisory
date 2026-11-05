"""Names, tickers and issuers: turning what a document says into Yahoo symbols.

Order of matching for an underlying name:
  1. the --tickers file given by the user,
  2. a Bloomberg ticker found next to the name in the document ("NVDA UW", "NESN SW Equity"),
  3. the built-in table below (indices and the names the desk writes most often),
  4. the Core List (assets/core_list.csv),
  5. Yahoo Finance search.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

# Short names shown in legends, and Yahoo symbols, for the names the desk writes most often.
# Keys are normalised (upper case, no accents, single spaces).
BUILTIN: dict[str, str] = {
    # indices
    "NIKKEI 225": "^N225", "NIKKEI": "^N225", "NKY": "^N225",
    "EURO STOXX 50": "^STOXX50E", "EUROSTOXX 50": "^STOXX50E", "SX5E": "^STOXX50E",
    "S&P 500": "^GSPC", "S&P500": "^GSPC", "SPX": "^GSPC",
    "SMI": "^SSMI", "SWISS MARKET INDEX": "^SSMI",
    "DAX": "^GDAXI", "CAC 40": "^FCHI", "CAC": "^FCHI", "FTSE 100": "^FTSE", "UKX": "^FTSE",
    "HANG SENG": "^HSI", "HSI": "^HSI",
    "OMX": "^OMX", "OMX INDEX": "^OMX", "OMX STOCKHOLM 30": "^OMX", "OMXS30": "^OMX",
    "NASDAQ 100": "^NDX", "NASDAQ 100 INDEX": "^NDX", "NASDAQ-100": "^NDX", "NDX": "^NDX",
    "RUSSELL 2000": "^RUT", "RUSSELL 2000 INDEX": "^RUT", "RTY": "^RUT",
    # ETFs
    "VANECK GOLD MINERS": "GDX", "VANECK GOLD MINERS ETF": "GDX", "GDX": "GDX",
    "GLOBAL X COPPER MINERS": "COPX", "GLOBAL X COPPER MINERS ETF": "COPX", "COPX": "COPX",
    "GLOBAL X URANIUM": "URA", "GLOBAL X URANIUM ETF": "URA", "URA": "URA",
    # shares
    "ALPHABET": "GOOGL", "GOOGLE": "GOOGL", "APPLE": "AAPL", "MICROSOFT": "MSFT", "META": "META",
    "META PLATFORMS": "META", "AMAZON": "AMZN", "TSM": "TSM", "TSMC": "TSM", "NVIDIA": "NVDA",
    "BROADCOM": "AVGO", "ASML": "ASML.AS", "VAT": "VACN.SW", "VAT GROUP": "VACN.SW",
    "PALO ALTO": "PANW", "PALO ALTO NETWORKS": "PANW", "GOLDMAN SACHS": "GS", "JP MORGAN": "JPM",
    "JPMORGAN": "JPM", "MORGAN STANLEY": "MS", "BNP": "BNP.PA", "BNP PARIBAS": "BNP.PA",
    "UBS": "UBSG.SW", "JULIUS BAER": "BAER.SW", "JULIUS BAR": "BAER.SW", "AMPHENOL": "APH",
    "ARISTA": "ANET", "ARISTA NETWORK": "ANET", "ARISTA NETWORKS": "ANET", "SCHNEIDER": "SU.PA",
    "SCHNEIDER ELECTRIC": "SU.PA", "SIEMENS": "SIE.DE", "ABB": "ABBN.SW", "ABBN": "ABBN.SW",
    "RWE": "RWE.DE", "CHEVRON": "CVX", "TOTAL ENERGIES": "TTE.PA", "TOTALENERGIES": "TTE.PA",
    "ELI LILLY": "LLY", "LILLY": "LLY", "MCKESSON": "MCK", "ROCHE": "RO.SW", "COCA-COLA": "KO",
    "COCA COLA": "KO", "WALMART": "WMT", "NESTLE": "NESN.SW", "ROLLS ROYCE": "RR.L",
    "ROLLS-ROYCE": "RR.L", "AIRBUS": "AIR.PA", "SAFRAN": "SAF.PA", "LVMH": "MC.PA",
    "HERMES": "RMS.PA", "FERRARI": "RACE.MI", "BLACKROCK": "BLK", "VISA": "V", "MASTERCARD": "MA",
    "NOVARTIS": "NOVN.SW", "ZURICH INSURANCE": "ZURN.SW", "ZURICH": "ZURN.SW", "TESLA": "TSLA",
    "UBER": "UBER", "SERVICENOW": "NOW", "SALESFORCE": "CRM", "ORACLE": "ORCL", "NETFLIX": "NFLX",
}

# Display names for the legend (short) when Yahoo's own is long or odd.
SHORT: dict[str, str] = {
    "^N225": "Nikkei 225", "^STOXX50E": "EURO STOXX 50", "^GSPC": "S&P 500", "^SSMI": "SMI",
    "^GDAXI": "DAX", "^FCHI": "CAC 40", "^FTSE": "FTSE 100", "^HSI": "Hang Seng", "^OMX": "OMX Index",
    "^NDX": "NASDAQ-100", "^RUT": "Russell 2000 Index", "GDX": "VanEck Gold Miners",
    "COPX": "Global X Copper Miners", "URA": "Global X Uranium", "GOOGL": "Alphabet", "AAPL": "Apple",
    "MSFT": "Microsoft", "META": "Meta Platforms", "AMZN": "Amazon.com", "TSM": "TSM", "NVDA": "NVIDIA",
    "AVGO": "Broadcom", "ASML.AS": "ASML", "VACN.SW": "VAT", "PANW": "Palo Alto Networks",
    "GS": "Goldman Sachs", "JPM": "JP Morgan", "MS": "Morgan Stanley", "BNP.PA": "BNP Paribas",
    "UBSG.SW": "UBS", "BAER.SW": "Julius Bär", "APH": "Amphenol", "ANET": "Arista Networks",
    "SU.PA": "Schneider", "SIE.DE": "Siemens", "ABBN.SW": "ABB", "RWE.DE": "RWE", "CVX": "Chevron",
    "TTE.PA": "TotalEnergies", "LLY": "Eli Lilly", "MCK": "McKesson", "RO.SW": "Roche",
    "ROG.SW": "Roche", "KO": "Coca-Cola", "WMT": "Walmart", "NESN.SW": "Nestlé", "RR.L": "Rolls-Royce",
    "AIR.PA": "Airbus", "SAF.PA": "Safran", "MC.PA": "LVMH", "RMS.PA": "Hermes", "RACE.MI": "Ferrari",
    "BLK": "BlackRock", "V": "Visa", "MA": "Mastercard", "NOVN.SW": "Novartis", "ZURN.SW": "Zurich Insurance",
}

INDICES = {"^N225", "^STOXX50E", "^GSPC", "^SSMI", "^GDAXI", "^FCHI", "^FTSE", "^HSI", "^OMX", "^NDX", "^RUT"}
ETFS = {"GDX", "COPX", "URA"}

# Bloomberg exchange codes -> Yahoo suffixes.
BBG_EXCHANGE = {
    "UW": "", "UQ": "", "UN": "", "US": "", "UA": "", "UR": "", "UP": "", "UV": "",
    "SW": ".SW", "SE": ".SW", "VX": ".SW", "LN": ".L", "FP": ".PA", "GY": ".DE", "GR": ".DE",
    "GF": ".F", "NA": ".AS", "IM": ".MI", "SM": ".MC", "SQ": ".MC", "BB": ".BR", "AT": ".AX",
    "AU": ".AX", "HK": ".HK", "JP": ".T", "JT": ".T", "CN": ".TO", "CT": ".TO", "SS": ".ST",
    "DC": ".CO", "NO": ".OL", "FH": ".HE", "ID": ".IR", "PL": ".LS", "KS": ".KS", "TT": ".TW",
}
BBG_INDEX = {"NKY": "^N225", "SX5E": "^STOXX50E", "SPX": "^GSPC", "SMI": "^SSMI", "DAX": "^GDAXI",
             "CAC": "^FCHI", "UKX": "^FTSE", "HSI": "^HSI", "OMX": "^OMX", "NDX": "^NDX", "RTY": "^RUT"}
# Share-class quirks: Bloomberg root -> Yahoo root
BBG_ROOT = {"ROG": "RO", "BRK/B": "BRK-B", "UHR": "UHR", "SREN": "SREN"}

ISSUERS = [  # (pattern, short name used in the deck)
    (r"banque internationale [aà] luxembourg|\bBIL\b", "BIL"),
    (r"j\.?\s?p\.?\s?morgan|jpmorgan", "JPMorgan"),
    (r"bank of america|\bbofa\b|merrill", "BofA"),
    (r"bnp paribas|\bbnp\b", "BNP"),
    (r"raiffeisen", "Raiffeisen"),
    (r"citigroup|citibank|\bciti\b", "Citigroup"),
    (r"goldman sachs", "Goldman Sachs"),
    (r"soci[eé]t[eé] g[eé]n[eé]rale|\bSG\b", "Société Générale"),
    (r"julius b[aä]e?r", "Julius Baer"),
    (r"natixis", "Natixis"),
    (r"vontobel", "Vontobel"),
    (r"ubs\b", "UBS"),
    (r"leonteq", "Leonteq"),
    (r"efg", "EFG"),
    (r"barclays", "Barclays"),
    (r"morgan stanley", "Morgan Stanley"),
    (r"standard chartered", "Standard Chartered"),
    (r"credit agricole|cr[eé]dit agricole|\bCACIB\b", "Crédit Agricole"),
    (r"hsbc", "HSBC"),
    (r"deutsche bank", "Deutsche Bank"),
    (r"royal bank of canada|\bRBC\b", "RBC"),
    (r"zürcher kantonalbank|zurcher kantonalbank|\bZKB\b", "ZKB"),
    (r"swissquote", "Swissquote"),
    (r"marex", "Marex"),
]


def norm(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    text = re.sub(r"\s+", " ", text.replace("’", "'")).strip().upper()
    return re.sub(r"\s+(INC|CORP|CORPORATION|PLC|AG|SA|SE|NV|N\.V\.|LTD|LIMITED|HOLDINGS?|GROUP|CO)\.?$", "", text)


def issuer_short(text: str | None) -> str | None:
    if not text:
        return None
    for pattern, short in ISSUERS:
        if re.search(pattern, text, re.I):
            return short
    return text.split(",")[0].strip() or None


def from_bloomberg(code: str) -> str | None:
    """'NVDA UW' / 'NESN SW Equity' / 'SX5E Index' -> Yahoo symbol."""
    m = re.match(r"^\s*([A-Z0-9/.\-]{1,12})(?:\s+([A-Z]{2}))?(?:\s+(Equity|Index))?\s*$", code.strip(), re.I)
    if not m:
        return None
    root, exch, kind = m.group(1).upper(), (m.group(2) or "").upper(), (m.group(3) or "").lower()
    if kind == "index" or (not exch and root in BBG_INDEX):
        return BBG_INDEX.get(root)
    if exch not in BBG_EXCHANGE:
        return None
    root = BBG_ROOT.get(root, root).replace("/", "-")
    return root + BBG_EXCHANGE[exch]


class CoreList:
    """The Core List: company names, Yahoo symbols and themes (used for matching and the swap test)."""

    YAHOO = {"US": "", "USA": "", "SWX": ".SW", "CH": ".SW", "PAR": ".PA", "FR": ".PA", "ETR": ".DE",
             "DE": ".DE", "AMS": ".AS", "GB": ".L", "IT": ".MI", "MAD": ".MC", "PT": ".LS", "SE": ".ST",
             "BR": ".SA", "KRX": ".KS"}
    FIX = {"ROP": "RO.SW", "LVMH": "MC.PA", "RWE": "RWE.DE", "EPI.A-SE": "EPI-A.ST", "ATCO.A-SE": "ATCO-A.ST",
           "STMMI-IT": "STMMI.MI", "AAL-GB": "AAL.L", "LLOY-GB": "LLOY.L", "RR-GB": "RR.L"}

    def __init__(self, path: Path | None):
        self.rows: list[dict] = []
        if not path or not Path(path).exists():
            return
        with open(path, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                code = (r.get("Core List") or "").strip()
                if not code:
                    continue
                self.rows.append({"symbol": self.to_yahoo(code), "name": r.get("Company Name", "").strip(),
                                  "theme": (r.get("Theme / Sector") or "").strip()})

    def to_yahoo(self, code: str) -> str:
        if code in self.FIX:
            return self.FIX[code]
        if "-" not in code:
            return code
        root, market = code.rsplit("-", 1)
        return root + self.YAHOO.get(market, "")

    def find(self, name: str) -> dict | None:
        key = norm(name)
        for r in self.rows:
            if norm(r["name"]) == key or norm(r["name"]).startswith(key + " ") or r["symbol"].upper() == key:
                return r
        return None

    def theme_of(self, symbol: str) -> str | None:
        return next((r["theme"] for r in self.rows if r["symbol"] == symbol), None)

    def by_theme(self, theme: str) -> list[dict]:
        return [r for r in self.rows if r["theme"] == theme]
