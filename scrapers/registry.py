"""Ladowanie rejestru zrodel + dyspozytor scraperow (F1/F3/§7.3).

Wybor metody per zrodlo, fallback python->firecrawl (ST-107), twardy budzet
Firecrawl per run (ST-125): gdy wyczerpany, pozostale zrodla firecrawl sa
pomijane, ale zrodla python dzialaja dalej.
"""
from __future__ import annotations

import logging

import yaml

from scrapers.base import ScrapeResult, safe_scrape
from scrapers.firecrawl_source import generic_firecrawl
from scrapers.python_sources import (firecrawl_json_events, python_crossweb,
                                     python_ebilet, python_meetup, python_trojmiasto)

log = logging.getLogger("eaa.registry")

PARSERS = {
    "python_crossweb": python_crossweb,
    "python_trojmiasto": python_trojmiasto,
    "python_ebilet": python_ebilet,
    "python_meetup": python_meetup,
    "firecrawl_json_events": firecrawl_json_events,
    "generic_firecrawl": generic_firecrawl,
}

FIRECRAWL_COST_PER_SOURCE = 1  # przyblizony koszt jednego scrape (guardrail)


def load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _serves(source: dict, selected: list[str]) -> bool:
    return bool(set(source.get("streams", [])) & set(selected))


def scrape_all(sources: list[dict], selected_streams: list[str], budget: int):
    """Zwraca (results, credits_used). results: lista ScrapeResult z surowymi eventami."""
    results: list[ScrapeResult] = []
    credits = 0

    for source in sources:
        if not source.get("enabled"):
            continue
        if not _serves(source, selected_streams):
            continue

        sid = source["id"]
        method = source.get("method", "python")
        parser = PARSERS.get(source.get("parser", ""))

        if method == "firecrawl":
            if credits + FIRECRAWL_COST_PER_SOURCE > budget:
                log.warning("budzet Firecrawl wyczerpany (%d/%d) — pomijam %s", credits, budget, sid)
                results.append(ScrapeResult(sid, [], "firecrawl", ok=False, error="budget_exceeded"))
                continue
            fc_parser = PARSERS.get(source.get("parser", ""), generic_firecrawl)
            res = safe_scrape(lambda p=fc_parser, s=source: p(s), sid, "firecrawl")
            credits += FIRECRAWL_COST_PER_SOURCE
        else:  # python (+ ewentualny fallback)
            res = safe_scrape(lambda p=parser, s=source: p(s) if p else [], sid, "python")
            need_fallback = (not res.ok or not res.raw_events)
            if need_fallback and source.get("fallback") == "firecrawl":
                if credits + FIRECRAWL_COST_PER_SOURCE <= budget:
                    fb = PARSERS.get(source.get("fallback_parser", "generic_firecrawl"), generic_firecrawl)
                    log.info("fallback firecrawl (%s) dla %s", fb.__name__, sid)
                    res = safe_scrape(lambda p=fb, s=source: p(s), sid, "firecrawl")
                    credits += FIRECRAWL_COST_PER_SOURCE
                else:
                    log.warning("fallback %s pominiety — budzet", sid)

        results.append(res)

    return results, credits
