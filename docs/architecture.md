# Architecture

A configurable, mostly-deterministic pipeline that turns raw event listings into a
ranked, deduplicated digest. AI (Firecrawl / optional LLM extraction) is used only
where it earns its keep: rendering JS-heavy pages and extracting structure from
messy markup. Everything else is plain Python rules.

## Flow

```
  Sources (config/sources.yaml)          Fixtures (fixtures/*.json)
        |  enabled: false by default            |  offline demo / CI
        +------------------+---------------------+
                           v
                   Source adapters            scrapers/
                   - python parsers (JSON-LD, HTML)
                   - Firecrawl adapter (JS-rendered pages)
                   - fixture loader (offline)
                           v
                   Normalization             pipeline/normalize.py
                   (dates, cities, prices -> canonical Event)
                           v
                   Classification            pipeline/classify.py
                   (stream: ai_digital | culture_family | concert)
                           v
                   Filtering                 pipeline/filter_rules.py
                   (time windows, keywords, exclude sport, national scope)
                           v
                   Deduplication             pipeline/dedup.py
                   (same event across sources -> one entry)
                           v
                   Ranking                   pipeline/rank.py
                           v
                   State (SQLite)            state/db.py, state/schema.sql
                   (new vs. updated across runs)
                           v
                   Delivery                  delivery/slack.py
                   (Markdown DIGEST.md / Slack)
```

## Modules

| Path | Responsibility |
|---|---|
| `orchestrator.py` | CLI entrypoint, wires the stages together |
| `scrapers/` | Source adapters: Python parsers, Firecrawl adapter, fixture loader, registry |
| `scrapers/firecrawl_cli.py` | Thin CLI over the Firecrawl API (JS-rendered page extraction) |
| `pipeline/` | `normalize`, `classify`, `filter_rules`, `dedup`, `rank`, `models` |
| `state/` | SQLite persistence, tracks new vs. updated events between runs |
| `delivery/` | Digest formatting and delivery (Markdown / Slack) |
| `discovery/` | Optional source discovery (`--discover`), returns candidates for review |
| `config/sources.yaml` | Source registry; add/disable a source without touching code |
| `config/filters.yaml` | Time windows, keywords, world-class list |

## Deterministic vs. probabilistic

- **Deterministic (Python):** normalization, classification rules, filtering,
  deduplication, ranking, state, delivery. Fully unit-tested.
- **Probabilistic / AI (opt-in):** Firecrawl for JS-rendered listings and optional
  LLM extraction of events from unstructured markup. Never required for the demo.

## Scheduled execution

The same `orchestrator.py` entrypoint can be driven by a scheduler or an AI coding
agent on a cadence (e.g. daily): it scrapes enabled sources, builds the digest, and
writes `DIGEST.md`. This public repository does not include an active scheduled
integration. Its "proof of life" is the CI job running the offline fixtures demo.
