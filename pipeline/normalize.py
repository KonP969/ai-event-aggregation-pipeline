"""Mapowanie surowych dictow ze scraperow -> kanoniczny Event (F4/ST-110).

Daty zawsze interpretowane/zapisywane w Europe/Warsaw (NF5/ST-126). Brakujace
pola opcjonalne sa dozwolone jako None.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from pipeline.models import Event

WARSAW = ZoneInfo("Europe/Warsaw")


def parse_dt(value: Any) -> Optional[datetime]:
    """datetime | ISO str | luzny PL string -> aware datetime (Europe/Warsaw)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        try:
            # ISO (YYYY-MM-DD [HH:MM]) — miesiac przed dniem. NIE uzywaj dayfirst.
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            try:
                from dateutil import parser as dtparser
                # ISO (rok na poczatku, np. Meetup '2026-07-03T...Z') -> miesiac przed dniem;
                # europejskie luzne formaty (np. '10.06.2026', '10 czerwca') -> dayfirst.
                day_first = not re.match(r"\d{4}-", s)
                dt = dtparser.parse(s, dayfirst=day_first, fuzzy=True)
            except Exception:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=WARSAW)
    return dt.astimezone(WARSAW)


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ".").replace("zl", "").strip())
    except ValueError:
        return None


def normalize(raw: dict, source_id: str) -> Optional[Event]:
    """Zwraca Event albo None gdy brak minimum (tytul)."""
    title = (raw.get("title") or "").strip()
    if not title:
        return None

    price_min = _to_float(raw.get("price_min"))
    price_max = _to_float(raw.get("price_max"))
    is_free = raw.get("is_free")
    if is_free is None and (price_min == 0 or price_max == 0):
        is_free = True

    return Event(
        source=source_id,
        source_url=raw.get("url") or raw.get("source_url") or "",
        title=title,
        start_datetime=parse_dt(raw.get("start") or raw.get("start_datetime")),
        end_datetime=parse_dt(raw.get("end") or raw.get("end_datetime")),
        city=raw.get("city"),
        venue_name=raw.get("venue") or raw.get("venue_name"),
        address=raw.get("address"),
        description=(raw.get("description") or "").strip() or None,
        price_min=price_min,
        price_max=price_max,
        is_free=is_free,
        ticket_url=raw.get("ticket_url") or raw.get("url"),
        artist=raw.get("artist"),
        subcategory=raw.get("subcategory"),
        scraped_at=datetime.now(WARSAW),
    )
