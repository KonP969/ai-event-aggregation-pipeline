"""Kanoniczny model wydarzenia (PRD §7.4) + deterministyczne helpery.

Jeden Event reprezentuje pojedyncze wydarzenie po normalizacji. Klucze dedup
i content_hash sa liczone deterministycznie z pol materialnych, zeby dzialaly
dedup w obrebie runu i miedzy runami (ST-110, ST-118).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# Trojmiasto wlasciwe (culture_family: scisle te miasta). "trojmiasto" = agregat,
# czesto podawany wprost przez zrodla (np. Crossweb) -> tez liczymy jako Trojmiasto.
TRICITY = {"gdansk", "gdynia", "sopot", "trojmiasto"}


def strip_accents(text: str) -> str:
    """usun polskie znaki diakrytyczne -> porownywalny ASCII (do kluczy/matchu)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def norm(text: Optional[str]) -> str:
    """lowercase + bez akcentow + zwiniete spacje. Pusty string dla None."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", strip_accents(text).lower()).strip()


def norm_city(city: Optional[str]) -> str:
    """Znormalizowana nazwa miasta (do is_tricity i dedup)."""
    c = norm(city)
    # czesto miasto przychodzi jako "Gdansk, Galeria Metropolia" itp.
    for known in ("gdansk", "gdynia", "sopot", "trojmiasto", "warszawa", "krakow",
                  "wroclaw", "poznan", "katowice", "lodz"):
        if known in c:
            return known
    return c


@dataclass
class Event:
    source: str
    source_url: str
    title: str
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    city: Optional[str] = None
    venue_name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    is_free: Optional[bool] = None
    ticket_url: Optional[str] = None
    artist: Optional[str] = None
    category: Optional[str] = None          # ai_digital | culture_family | concert
    subcategory: Optional[str] = None
    national_scope: bool = False
    scope_reason: str = ""
    family_suitable: Optional[bool] = None
    relevance_score: float = 0.0
    scraped_at: Optional[datetime] = None

    @property
    def city_norm(self) -> str:
        return norm_city(self.city)

    @property
    def is_tricity(self) -> bool:
        return self.city_norm in TRICITY

    @property
    def dedup_key(self) -> str:
        """normalized(title) + start_date + miasto/venue. Stabilny miedzy runami."""
        day = self.start_datetime.strftime("%Y-%m-%d") if self.start_datetime else "no-date"
        place = self.city_norm or norm(self.venue_name)
        title_slug = "-".join(norm(self.title).split())
        return f"{title_slug}|{day}|{place}"

    @property
    def id(self) -> str:
        return hashlib.sha1(self.dedup_key.encode("utf-8")).hexdigest()[:16]

    @property
    def content_hash(self) -> str:
        """Hash pol materialnych — zmiana => wydarzenie 'updated' (ST-118 AC2/3)."""
        material = "|".join([
            self.start_datetime.isoformat() if self.start_datetime else "",
            self.end_datetime.isoformat() if self.end_datetime else "",
            self.city_norm,
            norm(self.venue_name),
            str(self.price_min), str(self.price_max),
            self.ticket_url or "",
        ])
        return hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]
