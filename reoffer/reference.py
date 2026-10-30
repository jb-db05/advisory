"""Reference lists, aliases and FX rates kept as CSV next to the code.

The CSVs open in Excel. Edit them there; nothing in the Python needs to
change when an RM joins or an issuer is added.
"""

import difflib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DEFAULT_DIR = Path(__file__).parent / "reference"


def _key(s) -> str:
    return " ".join(str(s).split()).casefold()


@dataclass
class Reference:
    lists: dict = field(default_factory=dict)      # field -> [canonical values]
    aliases: dict = field(default_factory=dict)    # field -> {casefold alias: canonical}
    fx: pd.DataFrame = None                        # date, currency, chf_per_unit

    @classmethod
    def load(cls, folder=DEFAULT_DIR):
        folder = Path(folder)
        ref = cls()
        lists = pd.read_csv(folder / "lists.csv", dtype=str, keep_default_na=False)
        for f, grp in lists.groupby("field"):
            ref.lists[f] = [v.strip() for v in grp["value"] if v.strip()]
        aliases = pd.read_csv(folder / "aliases.csv", dtype=str, keep_default_na=False)
        for row in aliases.itertuples():
            ref.aliases.setdefault(row.field, {})[_key(row.alias)] = row.canonical.strip()
        fx = pd.read_csv(folder / "fx_rates.csv", dtype={"currency": str})
        fx["date"] = pd.to_datetime(fx["date"]).dt.date
        fx["currency"] = fx["currency"].str.strip().str.upper()
        ref.fx = fx.sort_values("date").reset_index(drop=True)
        return ref

    def resolve(self, fld, value):
        """Map a typed value to its canonical spelling.

        Returns (canonical or None, note). note is '' for an exact or alias
        match, 'corrected' for a confident fuzzy fix, else an error message.
        """
        allowed = self.lists.get(fld)
        if not allowed:
            return value, ""
        k = _key(value)
        exact = {_key(v): v for v in allowed}
        if k in exact:
            return exact[k], ""
        if k in self.aliases.get(fld, {}):
            return self.aliases[fld][k], ""
        # Fuzzy: only auto-correct when one candidate clearly wins.
        scored = sorted(((difflib.SequenceMatcher(None, k, ek).ratio(), v)
                         for ek, v in exact.items()), reverse=True)
        best = scored[0]
        runner = scored[1][0] if len(scored) > 1 else 0
        if best[0] >= 0.88 and best[0] - runner >= 0.1:
            return best[1], "corrected"
        hints = [v for score, v in scored[:3] if score >= 0.6]
        hint = f" (did you mean {' / '.join(hints)}?)" if hints else ""
        return None, f"'{value}' is not a known {fld}{hint}"

    def chf_rate(self, currency, on_date):
        """CHF per 1 unit of `currency`, latest rate on or before `on_date`."""
        if currency == "CHF":
            return 1.0
        rows = self.fx[(self.fx["currency"] == currency) & (self.fx["date"] <= on_date)]
        if rows.empty:
            return None
        return float(rows.iloc[-1]["chf_per_unit"])
