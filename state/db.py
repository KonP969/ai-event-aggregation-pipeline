"""Dostep do stanu SQLite (ST-110/111). Idempotentny upsert po dedup_key.

Re-zapis tego samego dedup_key aktualizuje rekord zamiast duplikowac (ST-110 AC3).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from pipeline.models import Event

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


class StateStore:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.conn.commit()

    def get(self, dedup_key: str) -> Optional[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM events WHERE dedup_key = ?", (dedup_key,))
        return cur.fetchone()

    def upsert(self, ev: Event) -> None:
        """Idempotentny zapis. Zachowuje delivered/delivered_at jesli rekord istnieje."""
        existing = self.get(ev.dedup_key)
        delivered = existing["delivered"] if existing else 0
        delivered_at = existing["delivered_at"] if existing else None
        self.conn.execute(
            """
            INSERT INTO events (
                id, dedup_key, source, source_url, category, subcategory, title,
                description, start_datetime, end_datetime, venue_name, city, address,
                is_tricity, price_min, price_max, is_free, ticket_url, artist,
                national_scope, scope_reason, family_suitable, relevance_score,
                content_hash, scraped_at, delivered, delivered_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(dedup_key) DO UPDATE SET
                source=excluded.source, source_url=excluded.source_url,
                category=excluded.category, subcategory=excluded.subcategory,
                title=excluded.title, description=excluded.description,
                start_datetime=excluded.start_datetime, end_datetime=excluded.end_datetime,
                venue_name=excluded.venue_name, city=excluded.city, address=excluded.address,
                is_tricity=excluded.is_tricity, price_min=excluded.price_min,
                price_max=excluded.price_max, is_free=excluded.is_free,
                ticket_url=excluded.ticket_url, artist=excluded.artist,
                national_scope=excluded.national_scope, scope_reason=excluded.scope_reason,
                family_suitable=excluded.family_suitable, relevance_score=excluded.relevance_score,
                content_hash=excluded.content_hash, scraped_at=excluded.scraped_at
            """,
            (
                ev.id, ev.dedup_key, ev.source, ev.source_url, ev.category, ev.subcategory,
                ev.title, ev.description, _iso(ev.start_datetime), _iso(ev.end_datetime),
                ev.venue_name, ev.city, ev.address, int(ev.is_tricity),
                ev.price_min, ev.price_max,
                None if ev.is_free is None else int(ev.is_free),
                ev.ticket_url, ev.artist, int(ev.national_scope), ev.scope_reason,
                None if ev.family_suitable is None else int(ev.family_suitable),
                ev.relevance_score, ev.content_hash, _iso(ev.scraped_at),
                delivered, delivered_at,
            ),
        )
        self.conn.commit()

    def delivery_status(self, ev: Event) -> str:
        """'new' | 'unchanged' | 'updated' wzgledem stanu (ST-118)."""
        row = self.get(ev.dedup_key)
        if row is None or not row["delivered"]:
            return "new"
        if row["content_hash"] == ev.content_hash:
            return "unchanged"
        return "updated"

    def mark_delivered(self, ev: Event, when: Optional[datetime] = None) -> None:
        when = when or datetime.now()
        self.conn.execute(
            "UPDATE events SET delivered = 1, delivered_at = ? WHERE dedup_key = ?",
            (when.isoformat(), ev.dedup_key),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
