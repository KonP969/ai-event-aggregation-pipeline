"""Zrodlo fixture — wczytuje wydarzenia z pliku JSON.

Fixture moze zawierac zwykle daty (``start``/``end``) albo wzgledne pola
``*_offset_days`` + ``*_time``. Te drugie sa rozwijane wzgledem daty
referencyjnej i pozwalaja offline demo zawsze pokazywac nadchodzace eventy.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")


def _resolve_relative_datetimes(raw: dict, reference_now: datetime) -> dict:
    event = dict(raw)
    for prefix in ("start", "end"):
        offset_key = f"{prefix}_offset_days"
        if offset_key not in event:
            continue
        offset_days = int(event.pop(offset_key))
        time_text = event.pop(f"{prefix}_time", "00:00")
        clock = datetime.strptime(time_text, "%H:%M").time()
        resolved = (reference_now + timedelta(days=offset_days)).replace(
            hour=clock.hour, minute=clock.minute, second=0, microsecond=0,
        )
        event[prefix] = resolved.strftime("%Y-%m-%d %H:%M")
    return event


def load_fixture(path: str | Path, reference_now: datetime | None = None) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raws = data if isinstance(data, list) else data.get("events", [])
    reference_now = reference_now or datetime.now(WARSAW)
    return [_resolve_relative_datetimes(raw, reference_now) for raw in raws]
