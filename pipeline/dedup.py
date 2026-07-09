"""Deduplikacja w obrebie runu i miedzy runami (F10/ST-118).

Within-run: grupuj po dedup_key, zostaw rekord z najbardziej zaufanego zrodla,
uzupelnij brakujace pola z pozostalych. Cross-run: porownaj z StateStore i ustaw
ev.delivery_state = 'new' | 'unchanged' | 'updated'.
"""
from __future__ import annotations

from dataclasses import fields
from typing import Optional

from pipeline.models import Event


def _merge(base: Event, other: Event) -> None:
    """Uzupelnij None-owe pola base wartosciami z other (in place)."""
    for f in fields(Event):
        if getattr(base, f.name) in (None, "", 0.0) and getattr(other, f.name) not in (None, ""):
            setattr(base, f.name, getattr(other, f.name))


def within_run_dedup(events: list[Event], cfg: dict) -> list[Event]:
    trust = cfg.get("source_trust", {})
    groups: dict[str, list[Event]] = {}
    for ev in events:
        groups.setdefault(ev.dedup_key, []).append(ev)

    result: list[Event] = []
    for group in groups.values():
        group.sort(key=lambda e: trust.get(e.source, 0.5), reverse=True)
        base = group[0]
        for other in group[1:]:
            _merge(base, other)
        result.append(base)
    return result


def cross_run_filter(events: list[Event], store, deliver_unchanged: bool = False) -> list[Event]:
    """Zwraca liste do dostarczenia; ustawia delivery_state na kazdym evencie."""
    to_deliver: list[Event] = []
    for ev in events:
        state = store.delivery_status(ev) if store else "new"
        setattr(ev, "delivery_state", state)
        if state == "unchanged" and not deliver_unchanged:
            continue
        to_deliver.append(ev)
    return to_deliver
