"""Reguly filtrowania (§5.4). Kluczowy test ST-114 AC3: mecz/sport wykluczony."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pipeline.filter_rules import apply_filters
from pipeline.models import Event

W = ZoneInfo("Europe/Warsaw")


_NOW = datetime(2026, 6, 5, 12, tzinfo=W)


def _ev(category, city, days, end_days=None, **kw):
    base = _NOW + timedelta(days=days)
    end = _NOW + timedelta(days=end_days) if end_days is not None else None
    return Event(source=kw.pop("source", "trojmiasto"), source_url="u", title=kw.pop("title", "Wydarzenie"),
                 category=category, city=city, start_datetime=base, end_datetime=end, **kw)


def test_mecz_wykluczony(cfg, now):
    ev = _ev("culture_family", "Gdansk", 3, title="Mecz Lechia - Legia (Ekstraklasa)", subcategory="sport")
    kept, drops = apply_filters([ev], cfg, now)
    assert kept == []
    assert drops[0][1] == "excluded:sports_or_league_match"


def test_culture_poza_trojmiastem_odrzucony(cfg, now):
    ev = _ev("culture_family", "Warszawa", 3, title="Spektakl")
    kept, drops = apply_filters([ev], cfg, now)
    assert kept == []
    assert drops[0][1] == "geo:culture_family_outside_tricity"


def test_koncert_worldclass_ogolnopolski(cfg, now):
    ev = _ev("concert", "Warszawa", 100, title="Sting 3.0", artist="Sting", venue_name="PGE Narodowy")
    kept, drops = apply_filters([ev], cfg, now)
    assert len(kept) == 1
    assert kept[0].national_scope is True
    assert "world_class" in kept[0].scope_reason


def test_koncert_lokalny_poza_trojmiastem_odrzucony(cfg, now):
    ev = _ev("concert", "Poznan", 5, title="Cover Band")
    kept, drops = apply_filters([ev], cfg, now)
    assert kept == []
    assert drops[0][1] == "geo:concert_outside_tricity_not_world_class"


def test_ai_niewielkie_poza_trojmiastem_odrzucone(cfg, now):
    ev = _ev("ai_digital", "Krakow", 5, title="Power BI spotkanie")
    kept, drops = apply_filters([ev], cfg, now)
    assert kept == []


def test_ai_duze_ogolnopolskie_zachowane(cfg, now):
    ev = _ev("ai_digital", "Warszawa", 7, title="Data Science Summit 2026")
    ev.end_datetime = ev.start_datetime + timedelta(days=1)
    kept, _ = apply_filters([ev], cfg, now)
    assert len(kept) == 1 and kept[0].national_scope is True


def test_wydarzenie_w_przeszlosci_odrzucone(cfg, now):
    ev = _ev("concert", "Gdansk", -2, title="Stary koncert")
    kept, drops = apply_filters([ev], cfg, now)
    assert kept == [] and drops[0][1] == "date:past"


def test_koncert_trojmiasto_w_oknie_zachowany(cfg, now):
    ev = _ev("concert", "Sopot", 10, title="Lokalny koncert")
    kept, _ = apply_filters([ev], cfg, now)
    assert len(kept) == 1 and kept[0].national_scope is False


def test_festiwal_trwajacy_teraz_zachowany(cfg, now):
    # zaczal sie 3 dni temu, trwa jeszcze 5 dni -> nachodzi na okno (nie 'past')
    ev = _ev("culture_family", "Gdansk", -3, end_days=5, title="Festiwal trwajacy")
    kept, drops = apply_filters([ev], cfg, now)
    assert len(kept) == 1


def test_festiwal_wielodniowy_poza_oknem_odrzucony(cfg, now):
    # Jarmark sw. Dominika: zaczyna sie za 50 dni (poza oknem 14) -> beyond_window
    ev = _ev("culture_family", "Gdansk", 50, end_days=70, title="Jarmark sw. Dominika")
    kept, drops = apply_filters([ev], cfg, now)
    assert kept == [] and drops[0][1] == "date:beyond_window"


def test_festiwal_zakonczony_odrzucony(cfg, now):
    ev = _ev("culture_family", "Gdansk", -10, end_days=-2, title="Festiwal zakonczony")
    kept, drops = apply_filters([ev], cfg, now)
    assert kept == [] and drops[0][1] == "date:past"
