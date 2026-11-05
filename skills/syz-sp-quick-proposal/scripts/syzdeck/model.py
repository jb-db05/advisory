"""The product record every reader fills in, whatever the input format.

Each field keeps where it came from (`sources`), so the hand-over can say what was read from the
document, what was looked up in market data and what is still missing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Underlying:
    name: str                        # as written in the document
    symbol: str | None = None        # Yahoo symbol
    bloomberg: str | None = None     # e.g. "NVDA UW"
    initial_level: float | None = None
    currency: str | None = None
    long_name: str | None = None     # filled from market data
    short_name: str | None = None    # legend label
    match: str | None = None         # how the symbol was found


@dataclass
class Product:
    number: int
    underlyings: list[Underlying] = field(default_factory=list)
    coupon: float | None = None          # p.a., 0.08 = 8%
    protection_type: str | None = None   # "low strike" | "european barrier" | "american barrier"
    strike: float | None = None          # 0.72 = 72% of initial
    barrier: float | None = None
    tenor_months: int | None = None
    weight: float | None = None          # share of the model portfolio
    fees: float | None = None
    stepdown: str | None = None          # autocall step-down wording
    autocall_trigger: float | None = None
    issuer: str | None = None
    currency: str | None = None
    isin: str | None = None
    product_type: str | None = None
    initial_fixing: str | None = None    # ISO dates
    final_fixing: str | None = None
    redemption_date: str | None = None
    frequency: str | None = None
    theme: str | None = None
    source_file: str | None = None
    sources: dict = field(default_factory=dict)   # field -> "document" | "market data" | "default" | "missing"

    @property
    def protection(self) -> float | None:
        """The level at which capital is at risk, as a share of the initial level."""
        if self.protection_type and "barrier" in self.protection_type:
            return self.barrier
        return self.strike

    def protection_label(self, short: bool = False) -> str:
        p = self.protection
        if p is None:
            return "n/a"
        pct = f"{p * 100:.0f}%" if short else _pct(p)
        if self.protection_type == "european barrier":
            return f"European barrier {pct}"
        if self.protection_type == "american barrier":
            return f"American barrier {pct}"
        return f"Low strike {pct}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Product":
        d = dict(d)
        d["underlyings"] = [Underlying(**u) for u in d.get("underlyings", [])]
        return cls(**d)


def _pct(x: float) -> str:
    s = f"{x * 100:.2f}".rstrip("0").rstrip(".")
    return f"{s}%"
