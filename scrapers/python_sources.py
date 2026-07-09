"""Parsery Python dla zrodel statycznych (ST-105). Best-effort, defensywne.

UWAGA (uncertainty flag z PRD §5.3): uklad stron zmienia sie. Selektory ponizej
sa rozsadnym startem, ale wymagaja realnego dostrojenia na zywych stronach.
Kazdy parser zwraca [] przy bledzie zamiast rzucac (NF1).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.models import strip_accents

log = logging.getLogger("eaa.scrapers.python")

WARSAW = ZoneInfo("Europe/Warsaw")

# Polskie miesiace w dopelniaczu (festiwale: "25 lipca - 16 sierpnia 2026")
_PL_MONTHS_FULL = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
                   "czerwca": 6, "lipca": 7, "sierpnia": 8, "wrzesnia": 9,
                   "pazdziernika": 10, "listopada": 11, "grudnia": 12}


def _parse_date_range(text: str) -> tuple[str | None, str | None]:
    """'19 - 28 czerwca 2026' / '25 lipca - 16 sierpnia 2026' -> (start_iso, end_iso).
    Festiwale wielodniowe maja zakres zamiast pojedynczego dnia (rok jawny w tekscie)."""
    m = re.search(r"(\d{1,2})\s+([a-zA-Ząćęłńóśźż]+)?\s*[-–]\s*(\d{1,2})\s+([a-zA-Ząćęłńóśźż]+)\s+(\d{4})",
                  text)
    if not m:
        return None, None
    d1, mo1, d2, mo2, year = m.groups()
    mo2n = _PL_MONTHS_FULL.get(strip_accents(mo2.lower()))
    mo1n = _PL_MONTHS_FULL.get(strip_accents(mo1.lower())) if mo1 else mo2n
    if not mo1n or not mo2n:
        return None, None
    return f"{year}-{mo1n:02d}-{int(d1):02d}", f"{year}-{mo2n:02d}-{int(d2):02d}"

_HEADERS = {
    "User-Agent": "EventAggregationAgent/0.1 (+https://github.com/; ad-hoc digest)",
    "Accept-Language": "pl-PL,pl;q=0.9",
}


def _get_soup(url: str, timeout: float = 15.0):
    import httpx
    from bs4 import BeautifulSoup
    resp = httpx.get(url, headers=_HEADERS, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _crossweb_date(text: str, now: datetime) -> str | None:
    """'10.06 Sr' -> ISO 'YYYY-MM-DD'. Listing nie ma roku: bierz biezacy,
    a jesli data juz minela -> nastepny rok (kalendarz cykliczny)."""
    m = re.search(r"(\d{1,2})\.(\d{1,2})", text)
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    try:
        cand = datetime(now.year, month, day, tzinfo=WARSAW)
    except ValueError:
        return None
    if cand.date() < now.date():
        cand = cand.replace(year=now.year + 1)
    return cand.strftime("%Y-%m-%d")


def python_crossweb(source: dict) -> list[dict]:
    """Listing wydarzen IT/AI z Crossweb (statyczny HTML). Selektory zweryfikowane na zywo 2026-06."""
    soup = _get_soup(source["listing_url"])
    now = datetime.now(WARSAW)
    events: list[dict] = []
    for a in soup.select('a.clearfix[href*="/wydarzenia/"]'):
        href = a.get("href", "")
        if not href:
            continue
        url = href if href.startswith("http") else source["base_url"].rstrip("/") + href

        title_el = a.select_one(".colTab.title")
        topics_el = title_el.select_one(".topics") if title_el else None
        topics = topics_el.get_text(" ", strip=True) if topics_el else ""
        if topics_el:
            topics_el.extract()  # odetnij tematy od tytulu
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            continue

        date_el = a.select_one(".colTab.date") or a.select_one(".num")
        start = _crossweb_date(date_el.get_text(" ", strip=True), now) if date_el else None

        city_el = a.select_one(".colTab.city")
        cost_el = a.select_one(".colTab.cost")
        type_el = a.select_one(".colTab.type")
        cost_txt = cost_el.get_text(" ", strip=True).lower() if cost_el else ""

        events.append({
            "title": title,
            "url": url,
            "start": start,
            "city": city_el.get_text(" ", strip=True) if city_el else None,
            "subcategory": (type_el.get_text(" ", strip=True) if type_el else "") + (f" | {topics}" if topics else ""),
            "description": topics,
            "is_free": "bezp" in cost_txt,
        })
    log.info("crossweb: %d surowych pozycji", len(events))
    return events


_PL_MONTHS = {"sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6,
              "lip": 7, "sie": 8, "wrz": 9, "paz": 10, "lis": 11, "gru": 12}


def _troj_date(month_txt: str, day_txt: str, hour_txt: str, now: datetime) -> str | None:
    """'cze' + '7' + 'godz. 18:00' -> ISO 'YYYY-MM-DDTHH:MM'. Rok z kontekstu (jak Crossweb)."""
    mo = _PL_MONTHS.get(month_txt.strip().lower().replace("ź", "z")[:3])
    dm = re.search(r"\d{1,2}", day_txt or "")
    if not mo or not dm:
        return None
    day = int(dm.group())
    hm = re.search(r"(\d{1,2}):(\d{2})", hour_txt or "")
    hour, minute = (int(hm.group(1)), int(hm.group(2))) if hm else (0, 0)
    try:
        cand = datetime(now.year, mo, day, hour, minute, tzinfo=WARSAW)
    except ValueError:
        return None
    if cand.date() < now.date():
        cand = cand.replace(year=now.year + 1)
    return cand.strftime("%Y-%m-%dT%H:%M")


def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def python_meetup(source: dict) -> list[dict]:
    """Meetupy AI/tech z Meetup.com (JSON-LD; listing filtrowany keywords=AI&location=Gdansk).
    Listing jest juz Trojmiasto-filtered -> brak lokalizacji = traktuj jako Trojmiasto (virtual/lokalne)."""
    import json
    import httpx
    from bs4 import BeautifulSoup
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36", "Accept-Language": "pl-PL,pl;q=0.9"}
    resp = httpx.get(source["listing_url"], headers=ua, timeout=25, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events, seen = [], set()
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [data]
        while stack:  # JSON-LD bywa zagniezdzony -> przejdz rekurencyjnie
            o = stack.pop()
            if isinstance(o, dict):
                if o.get("name") and o.get("startDate"):
                    key = (o["name"], str(o["startDate"])[:10])
                    if key not in seen:
                        seen.add(key)
                        loc = o.get("location") if isinstance(o.get("location"), dict) else {}
                        addr = loc.get("address") if isinstance(loc.get("address"), dict) else {}
                        # loc.name to SALA (Inkubator Starter), nie miasto -> city z addressLocality,
                        # fallback "Trojmiasto" (listing jest Gdansk-filtered)
                        city = addr.get("addressLocality") or "Trojmiasto"
                        events.append({
                            "title": o["name"], "start": o["startDate"],
                            "city": city, "venue": loc.get("name"),
                            "url": o.get("url"), "subcategory": "meetup",
                        })
                stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)
    log.info("meetup: %d wydarzen AI/tech", len(events))
    return events


def _firecrawl_fix_year(start: str | None, now: datetime) -> str | None:
    """LLM czesto zgaduje zly rok dla dat bez roku na stronie (np. Meetup 'Jul 3' -> 2023).
    Jesli data wypada w przeszlosci, podbij rok do biezacego, a jak nadal w tyle -> +1 (cykliczny kalendarz)."""
    if not start:
        return start
    from pipeline.normalize import parse_dt
    dt = parse_dt(start)
    if not dt:
        return start
    if dt.date() < now.date():
        try:
            dt = dt.replace(year=now.year)
            if dt.date() < now.date():
                dt = dt.replace(year=now.year + 1)
        except ValueError:
            return start
    return dt.isoformat()


def firecrawl_json_events(source: dict) -> list[dict]:
    """Uniwersalny ekstraktor wydarzen przez Firecrawl JSON extraction (strony renderowane JS).
    Uzywany jako glowna metoda dla zrodel JS-rendered ORAZ fallback, gdy bezposredni request
    Pythonem nie zwraca uzytecznej tresci. Parametry ze zrodla:
      firecrawl_prompt, default_city, firecrawl_subcategory.
    Wymaga FIRECRAWL_API_KEY; brak -> wyjatek (safe_scrape pominie zrodlo, run nie pada)."""
    import os
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        raise RuntimeError(f"brak FIRECRAWL_API_KEY — {source.get('id', '?')} pominiete")
    from firecrawl import Firecrawl
    from firecrawl.v2.types import JsonFormat

    schema = {"type": "object", "properties": {"events": {"type": "array", "items": {
        "type": "object", "properties": {
            "name": {"type": "string"}, "date": {"type": "string"},
            "city": {"type": "string"}, "venue": {"type": "string"}, "url": {"type": "string"}}}}}}
    prompt = source.get("firecrawl_prompt", "Wyciagnij liste wszystkich wydarzen: nazwa, data, "
                        "miasto, nazwa obiektu i link do wydarzenia.")
    app = Firecrawl(api_key=key)
    doc = app.scrape(source["listing_url"], formats=[JsonFormat(prompt=prompt, schema=schema)], wait_for=8000)
    data = getattr(doc, "json", None) or {}
    default_city = source.get("default_city")
    force_city = source.get("force_default_city", False)  # Meetup: listing Gdansk-filtered, ignoruj "Online"
    subcat = source.get("firecrawl_subcategory", "")
    now = datetime.now(WARSAW)
    events: list[dict] = []
    for e in data.get("events", []):
        if not e.get("name"):
            continue
        city = default_city if force_city else (e.get("city") or default_city)
        events.append({
            "title": e["name"],
            "start": _firecrawl_fix_year(e.get("date"), now),
            "city": city,
            "venue": e.get("venue"),
            "artist": e["name"],
            "subcategory": subcat,
            "url": e.get("url") or source.get("base_url"),
        })
    log.info("firecrawl[%s]: %d wydarzen (JSON extraction)", source.get("id", "?"), len(events))
    return events


def python_ebilet(source: dict) -> list[dict]:
    """Ogolnopolskie koncerty z eBilet (JSON-LD ItemList — ustrukturyzowane, stabilne).
    Kuratorowana lista TOP koncertow/festiwali -> zrodlo zaufane national (patrz world_class.trusted_sources)."""
    import json
    soup = _get_soup(source["listing_url"])
    events: list[dict] = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if not (isinstance(data, dict) and data.get("@type") == "ItemList"):
            continue
        for el in data.get("itemListElement", []):
            n = el.get("item", el) if isinstance(el, dict) else {}
            if not isinstance(n, dict) or not n.get("name"):
                continue
            loc = n.get("location") if isinstance(n.get("location"), dict) else {}
            addr = loc.get("address") if isinstance(loc.get("address"), dict) else {}
            loc_name = loc.get("name") or ""
            # eBilet location.name to miasto/lista miast (nie konkretna sala) -> uzyj jako city, nie venue
            city = addr.get("addressLocality") or (loc_name.split(",")[0].strip() if loc_name else None)
            events.append({
                "title": n.get("name"),
                "start": n.get("startDate"),
                "city": city,
                "venue": None,
                "url": n.get("url"),
                "ticket_url": n.get("url"),
                "artist": n.get("name"),
                "subcategory": "koncert",
            })
        break
    log.info("ebilet: %d koncertow z JSON-LD", len(events))
    return events


def python_trojmiasto(source: dict) -> list[dict]:
    """Listing imprez z Trojmiasto.pl (statyczny). Selektory zweryfikowane na zywo 2026-06."""
    soup = _get_soup(source["listing_url"])
    now = datetime.now(WARSAW)
    events: list[dict] = []
    for row in soup.select("div.event__item"):
        title = _txt(row.select_one(".event__item__title__name")) or _txt(row.select_one(".event__item__title"))
        title = re.sub(r"\s*\(\s*\d+\s*opini[ae]\w*\s*\)", "", title).strip()  # usun "( 1 opinia)"
        if not title or title.lower() == "kup bilety":
            continue
        # link tytulu = strona wydarzenia (zawsze jest); /impreza/ to tylko bilety
        link_el = row.select_one("a.event__item__title") or row.select_one('a[href*="/impreza/"]')
        href = link_el.get("href", "") if link_el else ""
        url = href if href.startswith("http") else source["base_url"].rstrip("/") + "/" + href.lstrip("/")

        start = _troj_date(
            _txt(row.select_one(".calendar-icon__icon__month")),
            _txt(row.select_one(".calendar-icon__icon__day")),
            _txt(row.select_one(".event__item__date__hour")),
            now,
        )
        end = None
        if not start:  # festiwal wielodniowy -> zakres dat
            cal = row.select_one('[class*="info__calendar"]') or row
            start, end = _parse_date_range(cal.get_text(" ", strip=True))
        city = _txt(row.select_one(".event__item__location__city")).rstrip(",")
        place = _txt(row.select_one(".event__item__location__place"))
        price_txt = _txt(row.select_one(".event__price__info")).lower()
        price_label = _txt(row.select_one(".event__price__label")).lower()
        is_free = "wolny" in price_txt or "wolny" in price_label or "bezp" in (price_txt + price_label)
        price_m = re.search(r"(\d+)", price_txt)

        events.append({
            "title": title,
            "url": url,
            "start": start,
            "end": end,
            "city": city or "Trojmiasto",
            "venue": place,
            "price_min": int(price_m.group(1)) if price_m else None,
            "is_free": is_free,
            "force_category": source.get("force_category"),  # pewna kategoria ze zrodla
        })
    log.info("trojmiasto[%s]: %d surowych pozycji", source.get("id", "?"), len(events))
    return events
