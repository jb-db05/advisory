"""Row fields, product-life situations and product-table templates.

The field and template lists are derived from the 128 payoff blocks in the
former advisory-proposition automation's ``Payoff.xlsx`` (since removed); the
extracted examples are kept in ``data/payoff_examples.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .models import Row

DATA_DIR = Path(__file__).resolve().parent / "data"
EXAMPLES_PATH = DATA_DIR / "payoff_examples.json"


@dataclass(frozen=True)
class Field:
    """A row that may appear in a product table."""

    key: str
    en: str
    fr: str
    # "text" | "percent" | "amount" | "list" -- drives the input widget only.
    kind: str = "text"
    highlight: bool = False
    accent_values: bool = False
    bold: bool = False
    placeholder: str = ""

    def to_row(self, values: list[str] | None = None) -> Row:
        return Row(
            label_en=self.en,
            label_fr=self.fr,
            values=list(values or []),
            highlight=self.highlight,
            accent_values=self.accent_values,
            bold=self.bold,
            key=self.key,
        )


def _f(key, en, fr, kind="text", **kw) -> Field:
    return Field(key=key, en=en, fr=fr, kind=kind, **kw)


# --- Field catalogue -------------------------------------------------------
# Order here is the order the "add a row" picker offers.
FIELDS: tuple[Field, ...] = (
    _f("issuer", "Issuer", "Émetteur"),
    _f("currency", "Currency", "Devise", "amount", bold=True, placeholder="CHF 70'000"),
    _f("nominal", "Nominal Amount", "Montant nominal", "amount"),
    _f("premium_amount", "Premium Amount", "Montant de la prime", "amount"),
    _f("indic_amount", "Indic. Amount", "Montant indicatif", "amount"),
    _f("issue_price", "Issue Price", "Prix d'émission", "percent"),
    _f("maturity", "Maturity", "Échéance", placeholder="18-Month"),
    _f("expiry", "Expiry", "Expiration", placeholder="3-Month"),
    _f("underlyings", "Underlying", "Sous-jacent", "list", accent_values=True),
    _f("strike", "Strike", "Strike", "percent"),
    _f("discounted_strike", "Discounted Strike", "Strike décoté", "percent"),
    _f("strike_level", "Strike Level", "Niveau de strike", "percent"),
    _f("barrier_level", "Barrier Level", "Niveau de barrière", "percent"),
    _f("barrier_type", "Barrier Type", "Type de barrière",
       placeholder="European (at Maturity)"),
    _f("delivery", "Delivery", "Livraison", placeholder="PHYSICAL"),
    _f("settlement_type", "Settlement Type", "Type de règlement"),
    _f("autocall_trigger", "Autocall Trigger", "Seuil d'autocall", "percent"),
    _f("step_down_trigger", "Step Down Autocall Trigger", "Seuil d'autocall dégressif",
       placeholder="100% ↓96% ↓92% ↓ … 68% ↓64% ↓"),
    _f("non_call_period", "Non call period", "Période de non-call",
       placeholder="4-Months"),
    _f("autocall_frequency", "Frequency", "Fréquence", placeholder="Monthly"),
    _f("guaranteed_coupon", "Guaranteed Coupon", "Coupon garanti", "percent",
       highlight=True, placeholder="7.00% p.a."),
    _f("coupon_pa", "Coupon p.a.", "Coupon p.a.", "percent", highlight=True),
    _f("coupon_flat", "Coupon FLAT", "Coupon FLAT", "percent", highlight=True),
    _f("coupon_frequency", "Coupon Frequency", "Fréquence des coupons"),
    _f("coupon_trigger", "Coupon Trigger", "Seuil de coupon", "percent"),
    _f("coupon_observation", "Coupon Observation", "Observation du coupon"),
    _f("memory_effect", "Memory Effect", "Effet mémoire", placeholder="Yes"),
    _f("lock_in_observation", "Lock-In Observation", "Observation du lock-in"),
    _f("lock_in_level", "Lock-In Level", "Niveau de lock-in", "percent"),
    _f("one_star_level", "ONE-Star Level", "Niveau ONE-Star", "percent"),
    _f("coupon_type", "Coupon Type", "Type de coupon", placeholder="Guaranteed"),
    _f("min_coupon", "Min coupon", "Coupon minimum", "percent"),
    _f("autocall_observations", "Autocall Observations", "Observations d'autocall"),
    _f("participation", "Participation", "Participation", highlight=True),
    _f("upside_participation", "Upside Participation", "Participation à la hausse",
       "percent"),
    _f("downside_participation", "Downside Participation",
       "Participation à la baisse", "percent"),
    _f("bonus_level", "Bonus Level", "Niveau du bonus", "percent"),
    _f("cap_level", "Cap Level", "Niveau du cap", "percent"),
    _f("leverage", "Leverage", "Levier"),
    _f("initial_delta", "Initial Delta indic.", "Delta initial indic.", "percent"),
    _f("principal_protection", "Principal Protection", "Protection du capital",
       "percent"),
    _f("gearing_downside", "Gearing on the downside", "Levier à la baisse"),
    _f("bonus_trigger", "Bonus trigger", "Seuil du bonus", "percent"),
    _f("bonus_coupon", "Bonus coupon", "Coupon bonus", "percent"),
    _f("balloon_coupon", "Balloon Coupon", "Coupon balloon", "percent"),
    _f("benchmark", "Benchmark", "Indice de référence"),
    _f("rainbow_basket", "Rainbow Basket", "Panier rainbow", "list"),
    _f("put_strike", "Put strike", "Strike du put", "percent"),
    _f("long_put_strike", "Long Put strike", "Strike du put acheté", "percent"),
    _f("short_put_strike", "Short Put strike", "Strike du put vendu", "percent"),
    _f("long_call_strike", "Long Call strike", "Strike du call acheté", "percent"),
    _f("short_call_strike", "Short Call strike", "Strike du call vendu", "percent"),
    _f("lookback_period", "Lookback period", "Période de lookback"),
    _f("lookback_frequency", "Lookback frequency", "Fréquence de lookback"),
    _f("lookback_observation", "Lookback observation", "Observation du lookback"),
    _f("observation_on", "Observation on", "Observation sur"),
    _f("min_barrier_hit", "Min barrier Hit", "Barrière minimale touchée", "percent"),
    _f("callable", "Callable", "Rappelable"),
    _f("recovery", "Recovery", "Recouvrement", "percent"),
    _f("wrapper", "Wrapper", "Enveloppe"),
    _f("redemption", "Redemption", "Remboursement"),
    _f("redemption_scenario", "Redemption scenario at Maturity",
       "Scénarios de remboursement à l'échéance", "list"),
    _f("profit", "Profit", "Profit", highlight=True),
    _f("offer", "Offer", "Prix d'offre", "percent", highlight=True),
    _f("fees", "Fees", "Frais", "percent"),
    _f("valor", "Valor", "Valor"),
)

FIELDS_BY_KEY = {f.key: f for f in FIELDS}


# --- Product-life situations ----------------------------------------------
@dataclass(frozen=True)
class Situation:
    """A point in the product's life, and how to say it in the email."""

    key: str
    en: str
    fr: str
    # Wording for the paragraph after the product line.
    event_en: str
    event_fr: str
    # How the product is qualified in the opening sentence.
    subject_en: str
    subject_fr: str
    date_label_en: str
    date_label_fr: str


SITUATIONS: tuple[Situation, ...] = (
    Situation(
        "autocalled", "Autocalled", "Autocallé",
        "was autocalled on {date}.", "a été autocallé le {date}.",
        "autocalled product", "produit autocallé",
        "Autocall date", "Date d'autocall",
    ),
    Situation(
        "matured", "Matured / expired", "Arrivé à échéance",
        "matured on {date}.", "est arrivé à échéance le {date}.",
        "matured product", "produit arrivé à échéance",
        "Maturity date", "Date d'échéance",
    ),
    Situation(
        "expiring", "Expiring (option / warrant)", "Expiration (option / warrant)",
        "expired on {date}.", "a expiré le {date}.",
        "expired product", "produit expiré",
        "Expiry date", "Date d'expiration",
    ),
    Situation(
        "early_redemption", "Early redemption", "Remboursement anticipé",
        "was redeemed early on {date}.",
        "a été remboursé par anticipation le {date}.",
        "early-redeemed product", "produit remboursé par anticipation",
        "Early redemption date", "Date de remboursement anticipé",
    ),
    Situation(
        "called_by_issuer", "Called by the issuer", "Rappelé par l'émetteur",
        "was called by the issuer on {date}.",
        "a été rappelé par l'émetteur le {date}.",
        "called product", "produit rappelé",
        "Call date", "Date de rappel",
    ),
    Situation(
        "approaching_maturity", "Approaching maturity", "Échéance proche",
        "will mature on {date}.", "arrivera à échéance le {date}.",
        "product approaching maturity", "produit arrivant à échéance",
        "Maturity date", "Date d'échéance",
    ),
    Situation(
        "barrier_breached", "Barrier breached", "Barrière franchie",
        "breached its barrier on {date}.", "a franchi sa barrière le {date}.",
        "product below its barrier", "produit sous sa barrière",
        "Observation date", "Date d'observation",
    ),
    Situation(
        "coupon_paid", "Coupon paid", "Coupon versé",
        "paid its coupon on {date}.", "a versé son coupon le {date}.",
        "product", "produit",
        "Coupon payment date", "Date de paiement du coupon",
    ),
    Situation(
        "physical_delivery", "Physically delivered", "Livraison physique",
        "was physically delivered on {date}.",
        "a fait l'objet d'une livraison physique le {date}.",
        "delivered product", "produit livré physiquement",
        "Delivery date", "Date de livraison",
    ),
    Situation(
        "custom", "Other / custom", "Autre / personnalisé",
        "{date}.", "{date}.",
        "product", "produit",
        "Relevant date", "Date pertinente",
    ),
)

SITUATIONS_BY_KEY = {s.key: s for s in SITUATIONS}
DEFAULT_SITUATION = SITUATIONS_BY_KEY["autocalled"]


# --- Product-table templates ----------------------------------------------
@dataclass(frozen=True)
class Template:
    """Default row set for a product family."""

    key: str
    en: str
    fr: str
    header_en: str
    header_fr: str
    fields: tuple[str, ...] = ()
    extras: tuple[str, ...] = ()  # offered first in the "add a row" picker

    def rows(self) -> list[Row]:
        return [FIELDS_BY_KEY[k].to_row() for k in self.fields if k in FIELDS_BY_KEY]


def _t(key, en, fr, header_en, header_fr, fields, extras=()) -> Template:
    return Template(key, en, fr, header_en, header_fr, tuple(fields), tuple(extras))


_AC_CORE = ("currency", "maturity", "underlyings", "strike", "autocall_trigger",
            "non_call_period", "autocall_frequency", "guaranteed_coupon")

TEMPLATES: tuple[Template, ...] = (
    _t("reverse_autocall_low_strike",
       "Reverse Autocall with Low Strike", "Reverse Autocall à strike bas",
       "{tenor} Reverse Autocall with Low Strike",
       "Reverse Autocall à strike bas {tenor}",
       _AC_CORE,
       ("barrier_level", "barrier_type", "delivery", "issuer", "step_down_trigger")),
    _t("reverse_autocall_discounted_strike",
       "Reverse Autocall with Discounted Strike",
       "Reverse Autocall à strike décoté",
       "{tenor} Reverse Autocall with Discounted Strike",
       "Reverse Autocall à strike décoté {tenor}",
       ("currency", "maturity", "underlyings", "discounted_strike", "delivery",
        "autocall_trigger", "autocall_frequency", "non_call_period",
        "guaranteed_coupon"),
       ("barrier_level", "barrier_type", "memory_effect")),
    _t("stepdown_reverse_autocall",
       "Step Down Reverse Autocall", "Reverse Autocall dégressif",
       "{tenor} Reverse Autocall Step Down with Discounted Strike",
       "Reverse Autocall dégressif {tenor} à strike décoté",
       ("currency", "maturity", "underlyings", "discounted_strike", "delivery",
        "step_down_trigger", "autocall_frequency", "non_call_period",
        "guaranteed_coupon"),
       ("barrier_level", "barrier_type", "memory_effect", "coupon_trigger")),
    _t("barrier_reverse_convertible",
       "Barrier Reverse Convertible", "Barrier Reverse Convertible",
       "{tenor} Barrier Reverse Convertible",
       "Barrier Reverse Convertible {tenor}",
       ("currency", "maturity", "underlyings", "strike", "barrier_level",
        "barrier_type", "delivery", "coupon_frequency", "coupon_pa"),
       ("issuer", "issue_price", "min_barrier_hit")),
    _t("barrier_reverse_bullet",
       "Barrier Reverse with Bullet Coupon",
       "Barrier Reverse à coupon bullet",
       "{tenor} Barrier Reverse with Bullet Coupon",
       "Barrier Reverse à coupon bullet {tenor}",
       ("currency", "maturity", "underlyings", "strike", "barrier_level",
        "barrier_type", "delivery", "coupon_frequency", "coupon_flat"),
       ("min_barrier_hit",)),
    _t("autocall_memory",
       "Autocall with Memory effect", "Autocall à effet mémoire",
       "{tenor} Autocall with Memory effect",
       "Autocall à effet mémoire {tenor}",
       ("currency", "maturity", "underlyings", "strike", "barrier_level",
        "barrier_type", "delivery", "autocall_trigger", "autocall_frequency",
        "non_call_period", "coupon_pa", "coupon_trigger", "memory_effect"),
       ("issue_price", "step_down_trigger")),
    _t("discount_autocall_memory",
       "Discount Autocall with Memory effect",
       "Discount Autocall à effet mémoire",
       "{tenor} Discount Autocall with Memory effect",
       "Discount Autocall à effet mémoire {tenor}",
       ("currency", "issue_price", "maturity", "underlyings", "barrier_level",
        "barrier_type", "delivery", "autocall_trigger", "autocall_frequency",
        "non_call_period", "coupon_pa", "coupon_trigger", "memory_effect"),
       ("recovery", "strike")),
    _t("one_star_autocall",
       "ONE-Star Autocall", "Autocall ONE-Star",
       "{tenor} ONE-Star ☆ Autocall with Memory effect",
       "Autocall ONE-Star ☆ {tenor} à effet mémoire",
       ("currency", "maturity", "underlyings", "strike_level", "barrier_level",
        "barrier_type", "autocall_trigger", "autocall_frequency",
        "non_call_period", "guaranteed_coupon", "one_star_level"),
       ("memory_effect", "coupon_trigger", "delivery")),
    _t("athena_autocall",
       "Athena Autocall", "Autocall Athena",
       "{tenor} Autocall Athena", "Autocall Athena {tenor}",
       ("currency", "maturity", "underlyings", "strike_level", "barrier_level",
        "barrier_type", "autocall_trigger", "autocall_frequency",
        "non_call_period", "coupon_pa"),
       ("principal_protection", "one_star_level", "memory_effect")),
    _t("phoenix_twinwin",
       "Phoenix / Twin Win Autocall", "Autocall Phoenix / Twin Win",
       "{tenor} Phoenix Twin Win Autocall with Discounted Strike",
       "Autocall Phoenix Twin Win {tenor} à strike décoté",
       ("currency", "maturity", "underlyings", "discounted_strike",
        "barrier_level", "barrier_type", "autocall_trigger",
        "autocall_frequency", "non_call_period", "coupon_pa"),
       ("gearing_downside", "memory_effect")),
    _t("daily_autocall",
       "Daily Autocallable", "Autocall quotidien",
       "{tenor} Daily Autocallable", "Autocall quotidien {tenor}",
       ("currency", "maturity", "underlyings", "strike", "barrier_level",
        "barrier_type", "autocall_trigger", "autocall_frequency",
        "non_call_period", "coupon_pa"),
       ("observation_on", "principal_protection")),
    _t("asynchronous_autocall",
       "Asynchronous Autocall", "Autocall asynchrone",
       "{tenor} Asynchronous Autocall", "Autocall asynchrone {tenor}",
       ("currency", "maturity", "underlyings", "barrier_level", "barrier_type",
        "delivery", "coupon_observation", "coupon_pa", "autocall_frequency",
        "non_call_period", "redemption"),
       ("memory_effect",)),
    _t("participation_autocall",
       "Participation Autocall", "Autocall à participation",
       "{tenor} Participation Autocall with Memory effect",
       "Autocall à participation {tenor} à effet mémoire",
       ("currency", "maturity", "underlyings", "strike", "barrier_level",
        "barrier_type", "autocall_trigger", "autocall_frequency",
        "non_call_period", "coupon_pa", "participation"),
       ("memory_effect",)),
    _t("beat_the_benchmark",
       "Beat the Benchmark Autocall", "Autocall Beat the Benchmark",
       "“Beat the Benchmark” Autocall with discounted Strike",
       "Autocall “Beat the Benchmark” à strike décoté",
       ("issuer", "currency", "maturity", "underlyings", "strike", "delivery",
        "autocall_trigger", "autocall_frequency", "non_call_period",
        "guaranteed_coupon", "benchmark", "bonus_trigger", "bonus_coupon")),
    _t("us_barrier_reverse_lock_in",
       "US Barrier Reverse Lock-In Bond", "US Barrier Reverse Lock-In Bond",
       "{tenor} US Barrier Reverse Lock-In Bond",
       "US Barrier Reverse Lock-In Bond {tenor}",
       ("currency", "maturity", "underlyings", "strike", "coupon_frequency",
        "coupon_pa", "barrier_level", "barrier_type", "lock_in_observation",
        "lock_in_level")),
    _t("digital_note",
       "Digital Note", "Digital Note",
       "{tenor} 100% Principal Protected Digital Note",
       "Digital Note {tenor} à capital protégé 100%",
       ("currency", "maturity", "underlyings", "strike", "coupon_trigger",
        "coupon_pa", "principal_protection"),
       ("coupon_observation", "memory_effect")),
    _t("growth_note",
       "Growth Note", "Growth Note",
       "{tenor} Growth Note", "Growth Note {tenor}",
       ("currency", "maturity", "underlyings", "participation",
        "principal_protection", "redemption_scenario")),
    _t("outperformance_certificate",
       "Outperformance Certificate", "Certificat d'outperformance",
       "{tenor} Outperformance Certificate",
       "Certificat d'outperformance {tenor}",
       ("currency", "maturity", "underlyings", "strike", "participation",
        "principal_protection"),
       ("barrier_level", "barrier_type")),
    _t("bonus_certificate",
       "Bonus Certificate", "Certificat bonus",
       "{tenor} Bonus Certificate", "Certificat bonus {tenor}",
       ("currency", "maturity", "underlyings", "strike", "barrier_level",
        "barrier_type", "bonus_trigger", "bonus_coupon", "participation")),
    _t("credit_linked_note",
       "Credit Linked Note", "Credit Linked Note",
       "{tenor} Credit Linked Note", "Credit Linked Note {tenor}",
       ("currency", "nominal", "maturity", "underlyings", "wrapper",
        "settlement_type", "profit"),
       ("callable", "balloon_coupon", "recovery")),
    _t("warrant",
       "Warrant / option strategy", "Warrant / stratégie optionnelle",
       "{tenor} Warrant", "Warrant {tenor}",
       ("currency", "premium_amount", "underlyings", "put_strike", "expiry",
        "offer"),
       ("long_put_strike", "short_put_strike", "long_call_strike",
        "short_call_strike", "rainbow_basket", "lookback_period",
        "lookback_frequency", "lookback_observation", "observation_on")),
    _t("custom", "Custom (empty table)", "Personnalisé (table vide)",
       "", "", ("currency", "maturity", "underlyings")),
)

TEMPLATES_BY_KEY = {t.key: t for t in TEMPLATES}


@lru_cache(maxsize=1)
def examples() -> list[dict]:
    """Reference tables extracted from Payoff.xlsx, for the UI example picker."""
    if not EXAMPLES_PATH.exists():
        return []
    return json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))


def to_json() -> dict:
    """The whole catalogue, as the browser app consumes it."""
    from syz_advisory import brand

    return {
        "palette": [
            {"key": key, "name": brand.PALETTE_NAMES[key], "hex": value}
            for key, value in brand.PALETTE.items()
        ],
        "default_accent": brand.DEFAULT_ACCENT,
        "fields": [vars(f) for f in FIELDS],
        "situations": [vars(s) for s in SITUATIONS],
        "templates": [
            {**vars(t), "fields": list(t.fields), "extras": list(t.extras)}
            for t in TEMPLATES
        ],
        "examples": examples(),
    }
