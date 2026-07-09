"""Adapter Firecrawl. Wola firecrawl_cli.py (CLI over API — ~2/3 mniej tokenow).

CLI: scrapers/firecrawl_cli.py

Zwraca surowy markdown jako jeden 'pseudo-event' z flaga needs_extraction=True.
Strukturalne wyciaganie eventow z markdown to robota dla per-source parsera lub
opcjonalnego kroku LLM (PRD §7.1) — celowo NIE zgadujemy tutaj struktury.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("eaa.scrapers.firecrawl")

CLI_PATH = Path(__file__).resolve().parent / "firecrawl_cli.py"


def _run_cli(args: list[str]) -> dict:
    cmd = [sys.executable, str(CLI_PATH), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"firecrawl_cli exit {proc.returncode}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def generic_firecrawl(source: dict) -> list[dict]:
    """Pobierz listing przez Firecrawl. Zwraca pojedynczy wpis z markdownem do dalszej obrobki."""
    if not CLI_PATH.exists():
        raise FileNotFoundError(f"brak firecrawl_cli.py pod {CLI_PATH}")
    data = _run_cli(["scrape", source["listing_url"]])
    markdown = data.get("markdown", "") if isinstance(data, dict) else ""
    log.info("firecrawl %s: %d znakow markdown", source["id"], len(markdown))
    if not markdown:
        return []
    return [{
        "title": f"[do ekstrakcji] {source['name']}",
        "url": source["listing_url"],
        "description": markdown[:2000],
        "needs_extraction": True,
    }]
