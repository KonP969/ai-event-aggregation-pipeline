"""Klasyfikacja do streamow (ST-112)."""
from pipeline.classify import classify
from pipeline.models import Event


def _ev(title, **kw):
    return Event(source="x", source_url="u", title=title, **kw)


def test_ai_digital(cfg):
    ev = _ev("Meetup AI & Data Engineering")
    assert classify(ev, ["ai_digital"], cfg) == "ai_digital"


def test_concert_z_artysta(cfg):
    ev = _ev("Dawid Podsiadlo - koncert", artist="Dawid Podsiadlo")
    assert classify(ev, ["concert", "culture_family"], cfg) == "concert"


def test_culture_family_spektakl(cfg):
    ev = _ev("Spektakl dla dzieci - bajka")
    assert classify(ev, ["culture_family", "concert"], cfg) == "culture_family"


def test_brak_slow_kluczy_odrzucone_nawet_jedno_zrodlo(cfg):
    # wymagamy trafienia slowa-klucza (koniec slepego zaufania zrodlu — odsiewa szum z Meetup)
    ev = _ev("Cos nieoczywistego xyz")
    assert classify(ev, ["ai_digital"], cfg) is None


def test_wieloznaczne_bez_dopasowania_odrzucone(cfg):
    ev = _ev("Cos nieoczywistego xyz")
    assert classify(ev, ["culture_family", "concert"], cfg) is None
