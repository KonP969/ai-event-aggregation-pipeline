"""Reguly geo + wykluczenia + family + world-class + okno czasowe (§5.4, F6/F7/F9).

apply_filters zwraca (kept, drops) gdzie drops to lista (Event, powod) — kazde
odrzucenie jest wytlumaczalne z raportu (ST-124, zasada 'explainable drop').
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from pipeline.models import Event, norm

WARSAW = ZoneInfo("Europe/Warsaw")


def _text(ev: Event) -> str:
    return " ".join([norm(ev.title), norm(ev.subcategory), norm(ev.description),
                     norm(ev.venue_name), norm(ev.address), norm(ev.artist)])


def is_excluded_sports(ev: Event, cfg: dict) -> bool:
    text = _text(ev)
    exc = cfg["exclusions"]
    if any(kw in text for kw in exc["keywords"]):
        return True
    if norm(ev.subcategory) in [norm(s) for s in exc["subcategories"]]:
        return True
    return False


def is_large_event(ev: Event, cfg: dict) -> tuple[bool, str]:
    le = cfg["large_event"]
    text = _text(ev)
    for brand in le["known_brands"]:
        if brand in text:
            return True, f"known_brand:{brand}"
    if ev.start_datetime and ev.end_datetime:
        days = (ev.end_datetime.date() - ev.start_datetime.date()).days + 1
        if days >= le["min_days"]:
            return True, f"multiday:{days}d"
    return False, ""


def is_world_class(ev: Event, cfg: dict) -> tuple[bool, str]:
    wc = cfg["world_class"]
    # zrodlo zaufane jako ogolnopolskie (kuratorowana lista TOP, np. eBilet)
    if ev.source in wc.get("trusted_sources", []):
        return True, f"trusted_source:{ev.source}"
    text = _text(ev)
    for name in wc["allowlist"]:
        if name in text:
            return True, f"allowlist:{name}"
    for venue in wc["large_venues"]:
        if venue in text:
            return True, f"large_venue:{venue}"
    return False, ""


def family_suitability(ev: Event, cfg: dict) -> Optional[bool]:
    text = _text(ev)
    if any(a in text for a in cfg["exclusions"]["adult_only"]):
        return False
    # slowa-klucze rodzinne z kontekstu EA (config family.kids_keywords), z fallbackiem
    kids = cfg.get("family", {}).get("kids_keywords") or [
        "dla dzieci", "rodzinny", "rodzinne", "bajka", "familijny", "maluch"]
    if any(k in text for k in kids):
        return True
    return None


def _window_end(ev: Event, cfg: dict, now: datetime) -> datetime:
    if ev.category == "concert":
        if ev.national_scope:
            days = cfg["national_concert_window_days"]      # world-class -> daleki horyzont
        else:
            days = cfg.get("concert_window_days", cfg["date_window_days"])  # lokalne koncerty
    else:
        days = cfg["date_window_days"]                       # ai_digital, culture_family
    return now + timedelta(days=days)


def _apply_geo(ev: Event, cfg: dict) -> Optional[str]:
    """Ustawia national_scope/scope_reason i family_suitable. Zwraca powod odrzucenia albo None."""
    city = ev.city_norm

    if ev.category == "ai_digital":
        if city in [norm(c) for c in cfg["tricity_surroundings"]]:
            return None
        large, reason = is_large_event(ev, cfg)
        if city in [norm(c) for c in cfg["major_cities"]] and large:
            ev.national_scope = True
            ev.scope_reason = f"large_event:{reason}"
            return None
        return "geo:ai_digital_outside_tricity_not_large"

    if ev.category == "culture_family":
        ev.family_suitable = family_suitability(ev, cfg)
        if ev.is_tricity:
            return None
        return "geo:culture_family_outside_tricity"

    if ev.category == "concert":
        if ev.is_tricity:
            return None
        wc, reason = is_world_class(ev, cfg)
        if wc:
            ev.national_scope = True
            ev.scope_reason = f"world_class:{reason}"
            return None
        return "geo:concert_outside_tricity_not_world_class"

    return "no_category"


def apply_filters(events: list[Event], cfg: dict, now: Optional[datetime] = None):
    now = now or datetime.now(WARSAW)
    kept: list[Event] = []
    drops: list[tuple[Event, str]] = []

    for ev in events:
        if ev.category is None:
            drops.append((ev, "no_category"))
            continue

        # 1. wykluczenia (tylko culture_family): mecze i rozgrywki ligowe (F7/ST-114)
        if ev.category == "culture_family" and is_excluded_sports(ev, cfg):
            drops.append((ev, "excluded:sports_or_league_match"))
            continue

        # 2. geo + scope (ustawia national_scope, family_suitable)
        geo_drop = _apply_geo(ev, cfg)
        if geo_drop:
            drops.append((ev, geo_drop))
            continue

        # 3. okno czasowe — overlap dla wydarzen wielodniowych (DST-correct; ST-126)
        if ev.start_datetime:
            last_day = ev.end_datetime or ev.start_datetime
            if last_day.date() < now.date():
                drops.append((ev, "date:past"))            # juz sie skonczylo
                continue
            if ev.start_datetime > _window_end(ev, cfg, now):
                drops.append((ev, "date:beyond_window"))   # jeszcze nie zaczelo, poza oknem
                continue

        kept.append(ev)

    return kept, drops
