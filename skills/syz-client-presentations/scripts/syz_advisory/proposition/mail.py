"""Write a proposition out as an .eml that opens straight in Outlook."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from . import render, sentences
from .models import Proposition


def build_message(prop: Proposition, lang: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = sentences.subject_line(prop, lang)
    msg.set_content(render.render_text(prop, lang))
    msg.add_alternative(render.render_email(prop, lang), subtype="html")
    return msg


def write_eml(prop: Proposition, lang: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_message(prop, lang).as_bytes())
    return path
