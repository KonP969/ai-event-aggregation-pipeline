"""Ranking i capy per stream (F11/ST-117).

Score = blizkosc daty + dopasowanie tematyczne + zaufanie zrodla (wagi w filters.yaml).
Sortowanie malejaco po score, potem rosnaco po dacie; cap max_per_stream.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.models import Event, norm

WARSAW = ZoneInfo("Europe/Warsaw")

STREAMS = ["ai_digital", "culture_family", "concert"]


def score(ev: Event, cfg: dict, now: datetime) -> float:
    w = cfg["scoring"]
    trust = cfg.get("source_trust", {})

    # blizkosc daty: im blizej, tym wyzej (1.0 dzis -> maleje)
    if ev.start_datetime:
        days = max((ev.start_datetime.date() - now.date()).days, 0)
        proximity = 1.0 / (1.0 + days)
    else:
        proximity = 0.3  # brak daty -> srodek stawki

    # dopasowanie tematyczne: trafienia slow-kluczy dla wlasnej kategorii
    kws = cfg["classify"].get(ev.category, [])
    text = " ".join([norm(ev.title), norm(ev.subcategory), norm(ev.description)])
    topical = min(sum(1 for kw in kws if kw in text) / 3.0, 1.0)

    trust_score = trust.get(ev.source, 0.5)

    return (proximity * w["date_proximity_weight"]
            + topical * w["topical_match_weight"]
            + trust_score * w["source_trust_weight"])


def rank_and_cap(events: list[Event], cfg: dict, now: datetime | None = None) -> dict[str, list[Event]]:
    now = now or datetime.now(WARSAW)
    by_stream: dict[str, list[Event]] = {s: [] for s in STREAMS}
    for ev in events:
        ev.relevance_score = round(score(ev, cfg, now), 4)
        if ev.category in by_stream:
            by_stream[ev.category].append(ev)

    cap = cfg["max_per_stream"]
    for stream, items in by_stream.items():
        items.sort(key=lambda e: (-e.relevance_score,
                                  e.start_datetime or datetime.max.replace(tzinfo=WARSAW)))
        by_stream[stream] = items if cap <= 0 else items[:cap]
    return by_stream
