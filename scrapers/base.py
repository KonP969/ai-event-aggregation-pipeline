"""Kontrakt scrapera (§7.3). Scraper ZAWSZE zwraca liste (moze pusta) i nigdy
nie rzuca poza swoja granice (NF1/ST-109). Surowy event to luzny dict —
normalizacja do Event dzieje sie pozniej w pipeline/normalize.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger("eaa.scrapers")

# Kontrakt surowego eventu (klucze opcjonalne poza title/url):
#   title, url, start, end, city, venue, address, description,
#   price_min, price_max, is_free, ticket_url, artist, subcategory
RawEvent = dict


@dataclass
class ScrapeResult:
    source_id: str
    raw_events: list[RawEvent] = field(default_factory=list)
    method_used: str = ""          # python | firecrawl | fixture
    firecrawl_credits: int = 0
    ok: bool = True
    error: str = ""


def safe_scrape(fn, source_id: str, method: str) -> ScrapeResult:
    """Uruchom scraper z izolacja bledow. Jedno padajace zrodlo nie przerywa runu."""
    try:
        raw = fn() or []
        return ScrapeResult(source_id, raw, method_used=method, ok=True)
    except Exception as exc:  # noqa: BLE001 — celowo lapiemy wszystko
        log.warning("zrodlo %s (%s) padlo: %s", source_id, method, exc)
        return ScrapeResult(source_id, [], method_used=method, ok=False, error=str(exc))
