"""Formatowanie i dostarczanie digestu na Slack (F12/ST-119/120).

Faza 1 (wybor uzytkownika): dostarczanie przez Slack MCP. Python buduje gotowa
tresc; faktyczny post wykonuje agent Claude wolajac narzedzie Slack MCP na
zawartosci zapisanej w reports/. Dla fazy 2 (nieinteraktywny cron) jest
opcjonalny poster przez bot token (slack_sdk), aktywny gdy ustawiony SLACK_BOT_TOKEN.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")

from pipeline.models import Event

log = logging.getLogger("eaa.slack")

SECTION_META = {
    "ai_digital": ("\U0001F916", "AI / DIGITAL"),
    "culture_family": ("\U0001F3AD", "KULTURA & RODZINA (Trojmiasto)"),
    "concert": ("\U0001F3B5", "KONCERTY"),
}


def _fmt_price(ev: Event) -> str:
    if ev.is_free:
        return "free"
    if ev.price_min:
        return f"{int(ev.price_min)} zl+"
    return "?"


def _fmt_event(ev: Event) -> str:
    marks = ""
    if ev.national_scope:
        marks += " \U0001F30D"
    if ev.family_suitable:
        marks += " \U0001F468‍\U0001F469‍\U0001F467"
    if getattr(ev, "delivery_state", "new") == "updated":
        marks += " \U0001F504"
    # wydarzenie cykliczne/wielodniowe ktore juz trwa -> pokaz "trwa do", nie przeszla date startu
    now = datetime.now(WARSAW)
    if (ev.start_datetime and ev.end_datetime
            and ev.start_datetime.date() < now.date() <= ev.end_datetime.date()):
        when = f"trwa do {ev.end_datetime:%d %b}"
    elif ev.start_datetime:
        when = ev.start_datetime.strftime("%a %d %b %H:%M")
    else:
        when = "termin ?"
    place = ev.city or ev.venue_name or "?"
    if ev.venue_name and ev.city:
        place = f"{ev.city}, {ev.venue_name}"
    link = ev.ticket_url or ev.source_url or ""
    # prefix "- " => prawdziwa lista markdown (GitHub lamie kazdy event w osobna linie)
    return f"- *{ev.title}*{marks} · {when} · {place} · {_fmt_price(ev)} · <{link}|Info>"


def format_digest(by_stream: dict[str, list[Event]], window_label: str, run_meta: dict) -> str:
    # Poprawny markdown: ## naglowek, ### sekcje, listy "- ", puste linie -> renderuje sie na GitHubie.
    lines = [f"## \U0001F4C5 Kalendarz imprez: {window_label}", f"_run {datetime.now():%Y-%m-%d %H:%M}_", ""]
    any_events = False
    for stream, (emoji, label) in SECTION_META.items():
        items = by_stream.get(stream, [])
        if not items:
            continue
        any_events = True
        lines.append(f"### {emoji} {label}")
        lines.append("")
        lines.extend(_fmt_event(ev) for ev in items)
        lines.append("")

    if not any_events:
        return f"## \U0001F4C5 Kalendarz imprez: {window_label}\n\nBrak nowych wydarzen w oknie."

    lines.append("---")
    lines.append(f"_{run_meta.get('kept', 0)} wydarzen · {run_meta.get('sources', 0)} zrodel "
                 f"· {run_meta.get('skipped', 0)} pominietych · {run_meta.get('credits', 0)} kredytow Firecrawl_")
    return "\n".join(lines)


def to_mcp_markdown(text: str) -> str:
    """Konwersja digestu z classic Slack mrkdwn -> standard markdown dla Slack MCP.

    format_digest produkuje classic (*bold*, <url|label>) pod chat.postMessage (bot token, faza 2).
    Slack MCP (faza 1, gdy agent Claude wysyla) oczekuje standard markdown (**bold**, [label](url)).
    Zweryfikowane na zywej wysylce 2026-06-07.
    """
    text = re.sub(r"<([^|>]+)\|([^>]+)>", r"[\2](\1)", text)        # <url|label> -> [label](url)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"**\1**", text)    # *bold* -> **bold**
    return text


def split_for_slack(text: str, limit: int = 4500) -> list[str]:
    """Podziel digest na kawalki <= limit znakow po liniach (nie lamie wydarzen).
    Slack: max 5000 znakow/wiadomosc -> dluzszy digest idzie jako watek (PRD §7.6)."""
    chunks: list[str] = []
    cur = ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > limit:
            chunks.append(cur.rstrip("\n"))
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur.rstrip("\n"))
    return chunks


def post_via_bot_token(text: str, channel: str) -> bool:
    """Faza 2 / nieinteraktywnie. Wymaga SLACK_BOT_TOKEN w env. Zwraca True przy sukcesie."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        log.info("brak SLACK_BOT_TOKEN — pomijam post przez bota (uzyj Slack MCP w fazie 1)")
        return False
    try:
        from slack_sdk import WebClient
        WebClient(token=token).chat_postMessage(channel=channel, text=text, mrkdwn=True)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("post na Slack nieudany: %s", exc)
        return False
