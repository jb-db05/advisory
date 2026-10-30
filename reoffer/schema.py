"""The one definition of a Reoffer trade row.

Every other module imports the column list and the header synonyms from
here, so adding a column means editing this file only.
"""

import re

# (key, header shown in Excel, required?)
COLUMNS = [
    ("trade_date", "Trade date", True),
    ("isin", "ISIN", True),
    ("issuer", "Issuer", True),
    ("payoff", "Pay-off", True),
    ("nclidos", "nclidos", True),
    ("size", "Size", True),
    ("currency", "Currency", True),
    ("fee_pct", "Fees (%)", True),
    ("fee_amount", "Fees (Amount)", False),
    ("apl", "APL", True),
    ("rm", "RM", True),
    ("region", "Region", True),
    ("management_style", "Management Style", True),
    ("comments", "Comments", False),
]

KEYS = [k for k, _, _ in COLUMNS]
HEADERS = {k: h for k, h, _ in COLUMNS}
REQUIRED = [k for k, _, req in COLUMNS if req]

# Fields checked against reference/lists.csv (skipped while a list is empty).
LIST_FIELDS = ["issuer", "payoff", "currency", "apl", "rm", "region",
               "management_style"]

# Columns the tool adds to the register.
AUDIT_COLUMNS = ["trade_id", "source_file", "imported_at", "warnings"]

# Header spellings seen in the wild, after normalise_header().
SYNONYMS = {
    "trade_date": ["tradedate", "date", "tradedt", "datetrade", "traded",
                   "dateoftrade", "datedetransaction"],
    "isin": ["isin", "isincode", "codeisin"],
    "issuer": ["issuer", "emitter", "emetteur", "issuingbank"],
    "payoff": ["payoff", "product", "producttype", "structure", "typeproduit"],
    "nclidos": ["nclidos", "nclido", "clientid", "client", "account",
                "accountid", "accountno", "portfolio", "dossier"],
    "size": ["size", "notional", "nominal", "quantity", "notionalamount"],
    "currency": ["currency", "ccy", "curr", "currenc", "devise", "cur"],
    "fee_pct": ["fees", "fee", "feespct", "feepct", "feespercent", "feerate",
                "feesrate", "fees%", "retro", "reoffer"],
    "fee_amount": ["feesamount", "feeamount", "feesamt", "feeamt",
                   "feesamoun", "feesvalue"],
    "apl": ["apl"],
    "rm": ["rm", "relationshipmanager", "banker", "rmname"],
    "region": ["region", "desk", "market"],
    "management_style": ["managementstyle", "mgmtstyle", "mandate",
                         "mandatetype", "style"],
    "comments": ["comments", "comment", "remarks", "notes", "invoice"],
}

_LOOKUP = {syn: key for key, syns in SYNONYMS.items() for syn in syns}


def normalise_header(text) -> str:
    """'Fees (Amount)' -> 'feesamount', 'Fees (%)' -> 'fees'."""
    s = str(text).strip().lower()
    s = re.sub(r"\(%\)|%", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def match_header(text):
    """Return the column key for a header cell, or None."""
    n = normalise_header(text)
    if not n:
        return None
    if n in _LOOKUP:
        return _LOOKUP[n]
    # Truncated headers from narrow Excel columns ('Currenc', 'Fees (Amoun').
    for syn, key in _LOOKUP.items():
        if len(n) >= 5 and syn.startswith(n):
            return key
    return None
