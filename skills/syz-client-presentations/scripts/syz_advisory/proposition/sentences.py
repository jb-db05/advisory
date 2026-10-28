"""Automatic EN/FR email wording, driven by the product's situation."""

from __future__ import annotations

from .catalogue import DEFAULT_SITUATION, SITUATIONS_BY_KEY
from .models import Proposition, format_date

GREETING = {"en": "Dear team,", "fr": "Bonjour la team,"}

_INTRO = {
    "en": "Please find below the roll proposal for the following {subject}:",
    "fr": "Veuillez trouver ci-dessous la proposition de roll pour le {subject} "
          "suivant :",
}

_RECOMMEND = {
    "en": {
        1: "We recommend rolling into the following conditions for account {accounts}",
        2: "We recommend rolling into the following conditions for accounts {accounts}",
    },
    "fr": {
        1: "Nous vous recommandons de roller selon les conditions suivantes pour le "
           "compte {accounts}",
        2: "Nous vous recommandons de roller selon les conditions suivantes pour les "
           "comptes {accounts}",
    },
}

_STATUS = {"en": "Status", "fr": "Statut"}

SIGN_OFF = {
    "en": "Best regards,",
    "fr": "Meilleures salutations,",
}


def situation_of(prop: Proposition):
    return SITUATIONS_BY_KEY.get(prop.situation, DEFAULT_SITUATION)


def subject(prop: Proposition, lang: str) -> str:
    sit = situation_of(prop)
    return sit.subject_fr if lang == "fr" else sit.subject_en


def date_label(prop: Proposition, lang: str) -> str:
    """Label for the relevant date -- autocall, expiry, maturity, ..."""
    custom = prop.custom_date_label_fr if lang == "fr" else prop.custom_date_label_en
    if custom:
        return custom
    sit = situation_of(prop)
    return sit.date_label_fr if lang == "fr" else sit.date_label_en


def intro(prop: Proposition, lang: str) -> str:
    return _INTRO[lang].format(subject=subject(prop, lang))


def product_sentence(prop: Proposition, lang: str) -> str:
    """'The product CH1455388368 - 6.76% p.a. ... was autocalled on 21.09.2026.'"""
    sit = situation_of(prop)
    custom = prop.custom_event_fr if lang == "fr" else prop.custom_event_en
    template = custom or (sit.event_fr if lang == "fr" else sit.event_en)
    event = template.format(date=format_date(prop.relevant_date))

    head = "Le produit" if lang == "fr" else "The product"
    name = " - ".join(p for p in (prop.isin, prop.description) if p)
    parts = [p for p in (head, name) if p]
    sentence = " ".join(parts)
    if event:
        sentence = f"{sentence} {event}" if sentence else event
    return sentence


def status_line(prop: Proposition, lang: str) -> str:
    if not prop.status:
        return ""
    return f"{_STATUS[lang]}: {prop.status}"


def account_lines(prop: Proposition) -> list[str]:
    return [a.holding_line() for a in prop.accounts if a.number]


def recommendation(prop: Proposition, lang: str) -> str:
    accounts = [a for a in prop.accounts if a.number]
    if not accounts:
        return ""
    joined = " - ".join(a.roll_line() for a in accounts)
    variant = _RECOMMEND[lang][1 if len(accounts) == 1 else 2]
    return variant.format(accounts=joined)


def notes(prop: Proposition, lang: str) -> str:
    return prop.notes_fr if lang == "fr" else prop.notes_en


def subject_line(prop: Proposition, lang: str) -> str:
    """Suggested email subject."""
    sit = situation_of(prop)
    label = sit.fr if lang == "fr" else sit.en
    bits = [p for p in (prop.isin, prop.description) if p]
    head = "Proposition de roll" if lang == "fr" else "Roll proposal"
    return f"{head} – {' - '.join(bits)} ({label})" if bits else head


def blocks(prop: Proposition, lang: str) -> list[str | list[str]]:
    """Paragraphs of the email body, in order. A list item is a line group."""
    out: list[str | list[str]] = [GREETING[lang], intro(prop, lang)]
    out.append(product_sentence(prop, lang))
    if status := status_line(prop, lang):
        out.append(status)
    if lines := account_lines(prop):
        out.append(lines)
    if rec := recommendation(prop, lang):
        out.append(rec)
    return out
