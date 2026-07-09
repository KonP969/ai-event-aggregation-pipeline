"""Dedup w obrebie runu i miedzy runami (ST-118)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.dedup import cross_run_filter, within_run_dedup
from pipeline.models import Event
from state.db import StateStore

W = ZoneInfo("Europe/Warsaw")
START = datetime(2026, 6, 10, 19, tzinfo=W)


def _ev(source, **kw):
    return Event(source=source, source_url="u", title="Dawid Podsiadlo - koncert",
                 city="Sopot", start_datetime=START, category="concert", **kw)


def test_within_run_collapse_i_merge(cfg):
    a = _ev("going")                       # mniej zaufane, ale ma cene
    a.price_min = 120
    b = _ev("ticketmaster", venue_name="Opera Lesna")  # bardziej zaufane, ma venue
    out = within_run_dedup([a, b], cfg)
    assert len(out) == 1
    base = out[0]
    assert base.source == "ticketmaster"   # zachowano bardziej zaufane zrodlo
    assert base.venue_name == "Opera Lesna"
    assert base.price_min == 120           # uzupelniono brakujace pole z mniej zaufanego


def test_cross_run_unchanged_suppressed(tmp_path, cfg):
    store = StateStore(tmp_path / "t.db")
    ev = _ev("ticketmaster", price_min=120)
    store.upsert(ev)
    store.mark_delivered(ev)
    out = cross_run_filter([ev], store)
    assert out == []                       # bez zmian -> nie wysylamy ponownie
    assert getattr(ev, "delivery_state") == "unchanged"
    store.close()


def test_cross_run_material_change_redelivered(tmp_path, cfg):
    store = StateStore(tmp_path / "t.db")
    ev = _ev("ticketmaster", price_min=120)
    store.upsert(ev)
    store.mark_delivered(ev)
    changed = _ev("ticketmaster", price_min=99)   # zmiana ceny -> inny content_hash
    out = cross_run_filter([changed], store)
    assert len(out) == 1
    assert getattr(changed, "delivery_state") == "updated"
    store.close()
