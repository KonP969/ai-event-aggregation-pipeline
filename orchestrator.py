"""Event Aggregation Agent — entrypoint (§7.2, §8.2).

Faza 1: ad-hoc, parametryzowany. Faza 2: te same wywolanie z configowymi
domyslnymi wartosciami, bez promptow (ST-128). Kod wyjscia: 0 ok, 1 partial
(jakies zrodlo padlo), 2 blad krytyczny.

Przyklady:
  python orchestrator.py --dry-run
  python orchestrator.py --streams ai_digital,concert --window 14 --max-per-stream 8
  python orchestrator.py --fixtures fixtures/sample_events.json --dry-run
  python orchestrator.py --discover --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from delivery.slack import format_digest, post_via_bot_token, to_mcp_markdown
from discovery.research_bridge import discover
from pipeline.classify import classify
from pipeline.dedup import cross_run_filter, within_run_dedup
from pipeline.filter_rules import apply_filters
from pipeline.normalize import normalize
from pipeline.rank import STREAMS, rank_and_cap
from scrapers.fixture_source import load_fixture
from scrapers.registry import load_yaml, scrape_all
from state.db import StateStore

ROOT = Path(__file__).resolve().parent
WARSAW = ZoneInfo("Europe/Warsaw")
log = logging.getLogger("eaa")

# Windows domyslnie cp1250 -> emoji w digescie wywala UnicodeEncodeError. Wymus UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="orchestrator", description="Event Aggregation Agent")
    p.add_argument("--streams", help="lista po przecinku: ai_digital,culture_family,concert")
    p.add_argument("--window", type=int, help="okno w dniach (override filters.yaml)")
    p.add_argument("--max-per-stream", type=int, help="cap per stream (override)")
    p.add_argument("--slack-dest", help="kanal/DM Slack (id) — zapisywane do raportu")
    p.add_argument("--discover", action="store_true", help="najpierw uruchom discovery (F2)")
    p.add_argument("--dry-run", action="store_true", help="zbuduj digest, nie wysylaj")
    p.add_argument("--fixtures", help="sciezka do JSON z eventami (offline/test, omija scraping)")
    p.add_argument("--sources", default=str(ROOT / "config" / "sources.yaml"))
    p.add_argument("--filters", default=str(ROOT / "config" / "filters.yaml"))
    p.add_argument("--db", default=str(ROOT / "data" / "events.db"))
    p.add_argument("--report-dir", default=str(ROOT / "reports"))
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def collect_raw(args, sources, selected, budget):
    """Zwraca (items, run_sources_meta, credits). items: (raw, source_id, source_streams)."""
    items, meta, credits = [], {}, 0

    if args.fixtures:
        raws = load_fixture(args.fixtures)
        for raw in raws:
            sid = raw.get("source", "fixture")
            items.append((raw, sid, selected))
        meta["fixture"] = {"found": len(raws), "ok": True}
        return items, meta, 0

    results, credits = scrape_all(sources, selected, budget)
    by_id = {s["id"]: s for s in sources}
    for res in results:
        src = by_id.get(res.source_id, {})
        src_streams = [s for s in src.get("streams", []) if s in selected]
        for raw in res.raw_events:
            items.append((raw, res.source_id, src_streams))
        meta[res.source_id] = {"found": len(res.raw_events), "ok": res.ok,
                               "error": res.error, "method": res.method_used}
    return items, meta, credits


def run(args) -> int:
    t0 = time.time()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    cfg = load_yaml(args.filters)
    sources = load_yaml(args.sources).get("sources", [])
    if args.window:
        cfg["date_window_days"] = args.window
    if args.max_per_stream:
        cfg["max_per_stream"] = args.max_per_stream
    selected = ([s.strip() for s in args.streams.split(",")] if args.streams else list(STREAMS))
    budget = cfg["firecrawl_budget_per_run"]
    now = datetime.now(WARSAW)

    # --- discovery (opcjonalnie, nie scrapuje; ST-104) ---
    discovered = []
    if args.discover:
        discovered = discover(selected)
        log.info("discovery: %d kandydatow (do recznego przegladu)", len(discovered))

    # --- scraping ---
    items, src_meta, credits = collect_raw(args, sources, selected, budget)
    failures = [sid for sid, m in src_meta.items() if not m.get("ok")]

    # --- normalize + classify ---
    events = []
    for raw, sid, src_streams in items:
        ev = normalize(raw, sid)
        if ev is None:
            continue
        # force_category ze zrodla (dedykowana lista kategorii) ma pierwszenstwo nad zgadywaniem
        ev.category = raw.get("force_category") or classify(ev, src_streams or selected, cfg)
        events.append(ev)

    # --- filter -> dedup within-run -> stan + dedup cross-run ---
    kept, drops = apply_filters(events, cfg, now)
    kept = within_run_dedup(kept, cfg)

    store = StateStore(args.db)
    for ev in kept:
        store.upsert(ev)
    to_deliver = cross_run_filter(kept, store)

    # --- ranking + capy ---
    by_stream = rank_and_cap(to_deliver, cfg, now)
    delivered_count = sum(len(v) for v in by_stream.values())

    # --- digest ---
    end_main = now + timedelta(days=cfg["date_window_days"])
    concert_days = cfg.get("concert_window_days", cfg["date_window_days"])
    window_label = (f"najblizsze {cfg['date_window_days']} dni "
                    f"({now:%d.%m}-{end_main:%d.%m.%Y}), koncerty do {concert_days} dni")
    run_meta = {"kept": delivered_count, "sources": len([m for m in src_meta.values() if m.get('ok')]),
                "skipped": len(failures), "credits": credits}
    digest = format_digest(by_stream, window_label, run_meta)

    # --- raport (ST-124) ---
    drop_reasons = Counter(reason for _, reason in drops)
    report = {
        "run_at": now.isoformat(),
        "streams": selected,
        "window_days": cfg["date_window_days"],
        "sources": src_meta,
        "failures": failures,
        "events_found": len(events),
        "events_kept": len(kept),
        "events_delivered": delivered_count,
        "drop_reasons": dict(drop_reasons),
        "firecrawl_credits": credits,
        "discovered_candidates": discovered,
        "runtime_seconds": round(time.time() - t0, 2),
        "slack_dest": args.slack_dest,
        "dry_run": bool(args.dry_run),
    }
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    (report_dir / f"run-{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / f"digest-{stamp}.md").write_text(digest, encoding="utf-8")

    # Stabilny, commitowalny raport w korzeniu repo (faza 2: routine publikuje go na GitHub).
    # Standard markdown -> ladnie renderuje sie na GitHubie.
    (ROOT / "DIGEST.md").write_text(to_mcp_markdown(digest), encoding="utf-8")

    # Zwiezle podsumowanie do stdout (NIE caly digest - zeby routine commitowala PLIK DIGEST.md,
    # a nie kopiowala tresci ze stdout w zlym formacie).
    print(f"\nDIGEST.md zaktualizowany: {delivered_count} wydarzen w oknie "
          f"({', '.join(f'{s}:{len(v)}' for s, v in by_stream.items() if v)}).\n")

    # --- dostarczenie ---
    empty = delivered_count == 0
    if args.dry_run:
        log.info("dry-run: digest zapisany do reports/, nie wyslano")
    elif empty and not cfg.get("empty_run_message", True):
        log.info("pusty run — komunikat wylaczony, nie wysylam")
    else:
        posted = post_via_bot_token(digest, args.slack_dest or "")
        if not posted:
            log.info("Slack MCP: agent Claude ma wyslac tresc z reports/digest-%s.md", stamp)
        if not empty:
            for items_ in by_stream.values():
                for ev in items_:
                    store.mark_delivered(ev, now)

    store.close()
    log.info("zrodla: %d ok, %d padlo · found %d · kept %d · delivered %d · %ds",
             run_meta["sources"], len(failures), len(events), len(kept),
             delivered_count, report["runtime_seconds"])

    return 1 if failures else 0


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("eaa").exception("blad krytyczny: %s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
