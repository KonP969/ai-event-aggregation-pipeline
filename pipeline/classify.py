"""Klasyfikacja do streamow (F5/ST-112): ai_digital | culture_family | concert.

Deterministycznie, slowa-klucze + streamy deklarowane przez zrodlo. Event moze
trafic tylko do streamu, ktory dane zrodlo obsluguje. Brak dopasowania -> None
(wydarzenie zostanie odrzucone i policzone w raporcie).
"""
from __future__ import annotations

from typing import Optional

from pipeline.models import Event, norm


def _hits(text: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


def classify(ev: Event, source_streams: list[str], cfg: dict) -> Optional[str]:
    rules = cfg["classify"]
    text = " ".join([norm(ev.title), norm(ev.subcategory), norm(ev.description)])

    scores = {
        "concert": _hits(text, rules["concert"]) + (2 if ev.artist else 0),
        "ai_digital": _hits(text, rules["ai_digital"]),
        "culture_family": _hits(text, rules["culture_family"]),
    }
    # ogranicz do streamow obslugiwanych przez zrodlo
    candidates = {s: scores[s] for s in source_streams if s in scores}
    if not candidates:
        return None

    best = max(candidates, key=candidates.get)
    # wymagaj trafienia slowa-klucza. Bez tego zrodlo mieszane (Meetup keywords=AI zwraca
    # tez astrologie/English Meetup) zasmiecaloby stream. Brak dopasowania -> None (odrzuc).
    return best if candidates[best] > 0 else None
