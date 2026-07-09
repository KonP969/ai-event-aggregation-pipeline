"""Most do discovery nowych zrodel.

Korzysta z firecrawl_cli.py (search) — scrapers/firecrawl_cli.py.
Discovery NIE scrapuje znalezionych zrodel automatycznie — zwraca strukturalna
liste kandydatow (name, url, why, stream) do recznego przegladu i dodania do
sources.yaml. Gdy CLI/klucz niedostepne -> [] + warning.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("eaa.discovery")

CLI_PATH = Path(__file__).resolve().parents[1] / "scrapers" / "firecrawl_cli.py"

QUERIES = {
    "ai_digital": "konferencja meetup AI data digital Trojmiasto Gdansk 2026 wydarzenia",
    "culture_family": "wydarzenia kulturalne rodzinne dla dzieci Trojmiasto kalendarz imprez",
    "concert": "koncerty Trojmiasto Gdansk Gdynia Sopot bilety nadchodzace",
}


def discover(streams: list[str], limit: int = 5) -> list[dict]:
    if not CLI_PATH.exists():
        log.warning("brak firecrawl_cli.py (%s) — discovery pominiete", CLI_PATH)
        return []

    candidates: list[dict] = []
    for stream in streams:
        query = QUERIES.get(stream)
        if not query:
            continue
        try:
            out = subprocess.run(
                [sys.executable, str(CLI_PATH), "search", query, "--limit", str(limit)],
                capture_output=True, text=True, encoding="utf-8", timeout=120,
            )
            if out.returncode != 0:
                log.warning("discovery %s: %s", stream, out.stderr.strip())
                continue
            data = json.loads(out.stdout)
        except Exception as exc:  # noqa: BLE001
            log.warning("discovery %s padlo: %s", stream, exc)
            continue

        for item in (data.get("web") or []):
            candidates.append({
                "name": item.get("title", ""),
                "url": item.get("url", ""),
                "why": item.get("description", "")[:160],
                "suggested_stream": stream,
            })
    return candidates
