"""Structured-product payoffs, evaluated on a worst-of path.

Every product here pays off on the worst performer of its basket, so a path is
the series ``w[t] = min_i S_i(t) / S_i(0)`` on trading days (``w[0] == 1``).
A single-underlying product is the same with one name.

Conventions -- all stated in the app and the proposal:

* 21 trading days per month; observation ``k`` falls on day ``21 * months``.
* Levels are fractions of the initial fixing (0.7 == 70%).
* An American barrier is checked on daily closes, a European one at maturity.
* Results are per unit of notional, before fees and taxes, with no issuer
  default: the issuer's credit risk comes on top of everything shown here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

DAYS_PER_MONTH = 21

RC, BRC, AUTOCALL, BONUS, CPN = "RC", "BRC", "Autocallable", "Bonus", "Capital Protected"
TRACKER, DISCOUNT, TWIN_WIN = "Tracker", "Discount", "Twin-Win"
KINDS = {
    RC: "Reverse Convertible",
    BRC: "Barrier Reverse Convertible",
    AUTOCALL: "Autocallable (Barrier) Reverse Convertible",
    BONUS: "Bonus Certificate",
    CPN: "Capital Protected Note",
    TRACKER: "Tracker Certificate",
    DISCOUNT: "Discount Certificate",
    TWIN_WIN: "Twin-Win Certificate",
}
GUARANTEED, CONDITIONAL = "guaranteed", "conditional"
AMERICAN, EUROPEAN = "american", "european"


@dataclass
class Product:
    kind: str = AUTOCALL
    underlyings: list[str] = field(default_factory=list)   # Yahoo symbols
    tenor_months: int = 12
    currency: str = ""
    issuer: str = ""
    # coupons
    coupon_pa: float = 0.0            # 0.08 == 8% p.a.
    coupon_type: str = GUARANTEED
    coupon_barrier: float | None = None    # conditional coupons only
    memory: bool = False
    frequency_months: int = 3         # coupon and observation period
    # downside
    strike: float = 1.0
    barrier: float | None = None      # None: no barrier, loss below the strike (RC)
    barrier_type: str = AMERICAN
    # early redemption
    autocall_trigger: float | None = None
    stepdown: float = 0.0             # trigger falls by this at each observation
    first_call_months: int | None = None   # non-call period; None = first observation
    # bonus / capital protection
    bonus_level: float | None = None
    cap: float | None = None
    participation: float = 1.0
    protection: float = 1.0
    fee: float = 0.0                  # upfront distribution fee, for reference only

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        product = cls(**known)
        product.validate()
        return product

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown product type {self.kind!r}")
        if not 1 <= self.tenor_months <= 120:
            raise ValueError("tenor must be 1-120 months")
        if self.frequency_months < 1:
            raise ValueError("observation frequency must be at least monthly")
        for name in ("strike", "barrier", "autocall_trigger", "coupon_barrier", "bonus_level", "cap"):
            value = getattr(self, name)
            if value is not None and not 0 < value < 3:
                raise ValueError(f"{name} must be a fraction of the initial level (0.7 = 70%)")
        if self.kind == AUTOCALL and self.autocall_trigger is None:
            self.autocall_trigger = 1.0
        if self.kind == BONUS and self.bonus_level is None:
            raise ValueError("a bonus certificate needs a bonus level")
        if self.kind == DISCOUNT and self.cap is None:
            raise ValueError("a discount certificate needs a cap")
        if self.kind == TWIN_WIN and self.barrier is None:
            raise ValueError("a twin-win certificate needs a barrier")

    @property
    def days(self) -> int:
        return self.tenor_months * DAYS_PER_MONTH

    @property
    def protection_level(self) -> float:
        """Where capital starts to be at risk at maturity: the lower of strike and barrier."""
        if self.kind == CPN:
            return 0.0
        if self.kind == TRACKER:
            return 1.0
        if self.kind == DISCOUNT:
            return self.strike            # the purchase price: below it the holder loses
        levels = [self.strike]
        if self.barrier is not None and self.kind in (BRC, AUTOCALL, BONUS, TWIN_WIN):
            levels.append(self.barrier)
        return min(levels)

    def describe(self) -> str:
        parts = [KINDS[self.kind]]
        if self.coupon_pa:
            parts.append(f"{self.coupon_pa:.2%} p.a. {self.coupon_type}")
        if self.barrier is not None:
            parts.append(f"barrier {self.barrier:.0%} {self.barrier_type}")
        if self.strike != 1.0:
            parts.append(f"strike {self.strike:.0%}")
        if self.autocall_trigger is not None and self.kind == AUTOCALL:
            parts.append(f"autocall {self.autocall_trigger:.0%}")
        return ", ".join(parts)


@dataclass
class Outcome:
    total_return: float        # over the product's life, per unit notional
    life_months: float
    called_at: int | None      # observation number (1-based) of an early redemption
    capital_loss: bool
    redemption: float          # capital returned, per unit
    coupons: float             # coupons paid, per unit
    barrier_hit: bool

    @property
    def annualised(self) -> float:
        years = max(self.life_months / 12.0, 1 / 12)
        growth = 1.0 + self.total_return
        return growth ** (1 / years) - 1 if growth > 0 else -1.0


def observation_days(p: Product) -> list[int]:
    months = list(range(p.frequency_months, p.tenor_months + 1, p.frequency_months))
    if not months or months[-1] != p.tenor_months:
        months.append(p.tenor_months)
    return [m * DAYS_PER_MONTH for m in months]


def evaluate(p: Product, w: list[float]) -> Outcome:
    """Pay the product along one worst-of path (``len(w) > p.days``)."""
    days = p.days
    if len(w) <= days:
        raise ValueError(f"path has {len(w) - 1} days, the product needs {days}")
    per_coupon = p.coupon_pa * p.frequency_months / 12.0
    coupons, owed = 0.0, 0
    running_min = 1.0
    barrier_hit = False
    last = 0
    first_call = p.first_call_months or p.frequency_months
    trigger = p.autocall_trigger if p.autocall_trigger is not None else 1.0

    for n, t in enumerate(observation_days(p), start=1):
        for day in range(last + 1, t + 1):
            if w[day] < running_min:
                running_min = w[day]
        last = t
        level = w[t]
        if p.barrier is not None and p.barrier_type == AMERICAN and running_min <= p.barrier:
            barrier_hit = True

        if per_coupon:
            if p.coupon_type == GUARANTEED:
                coupons += per_coupon
            elif level >= (p.coupon_barrier if p.coupon_barrier is not None else p.protection_level):
                coupons += per_coupon * (1 + owed if p.memory else 1)
                owed = 0
            else:
                owed += 1

        month = t // DAYS_PER_MONTH
        if (p.kind == AUTOCALL and t < days and month >= first_call
                and level >= trigger - p.stepdown * (n - 1)):
            return Outcome(coupons, month, n, False, 1.0, coupons, barrier_hit)

    final = w[days]
    if p.barrier is not None and p.barrier_type == EUROPEAN and final <= p.barrier:
        barrier_hit = True
    redemption = _redemption(p, final, barrier_hit)
    return Outcome(redemption - 1.0 + coupons, p.tenor_months, None,
                   redemption < 1.0 - 1e-12, redemption, coupons, barrier_hit)


def _redemption(p: Product, final: float, barrier_hit: bool) -> float:
    if p.kind == RC or (p.kind == AUTOCALL and p.barrier is None):
        return 1.0 if final >= p.strike else final / p.strike
    if p.kind in (BRC, AUTOCALL):
        return final / p.strike if barrier_hit and final < p.strike else 1.0
    if p.kind == BONUS:
        value = final if barrier_hit else max(p.bonus_level, final)
        return min(value, p.cap) if p.cap else value
    if p.kind == CPN:
        upside = p.participation * max(final - p.strike, 0.0)
        if p.cap:
            upside = min(upside, p.cap - p.protection)
        return p.protection + upside
    if p.kind == TRACKER:
        return final * p.participation
    if p.kind == DISCOUNT:
        # bought at `strike` (the discounted price, a fraction of the initial level), pays min(final, cap)
        return min(final, p.cap) / p.strike
    if p.kind == TWIN_WIN:
        if barrier_hit:
            return final
        value = 1.0 + p.participation * abs(final - 1.0)
        return min(value, p.cap) if p.cap else value
    raise ValueError(p.kind)


def payoff_curve(p: Product, levels: list[float] | None = None) -> list[dict]:
    """Redemption plus coupons at maturity against the final worst-of level,
    with and without a barrier event -- the payoff diagram. Ignores autocalls."""
    levels = levels or [x / 100 for x in range(20, 161, 5)]
    rows = []
    for level in levels:
        coupons = p.coupon_pa * p.tenor_months / 12.0
        if p.coupon_type == CONDITIONAL:
            floor = p.coupon_barrier if p.coupon_barrier is not None else p.protection_level
            coupons = coupons if level >= floor else 0.0
        hit = _redemption(p, level, True) + coupons - 1.0
        if p.barrier is None or p.kind in (RC, CPN, TRACKER, DISCOUNT):
            clean = hit
        elif level <= p.barrier:      # ending below the barrier means it was hit
            clean = None
        else:
            clean = _redemption(p, level, False) + coupons - 1.0
        rows.append({"level": level, "barrier_hit": hit, "no_barrier_hit": clean})
    return rows
