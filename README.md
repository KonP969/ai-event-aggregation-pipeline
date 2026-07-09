# AI Event Aggregation Pipeline

[![tests](https://github.com/KonP969/ai-event-aggregation-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/KonP969/ai-event-aggregation-pipeline/actions/workflows/tests.yml)

A configurable, AI-assisted pipeline that turns raw event listings into a ranked,
deduplicated digest. It normalizes, classifies, filters, deduplicates and ranks
events into three streams, then renders a Markdown digest:

- **ai_digital** — industry AI / data / digital meetups and conferences
- **culture_family** — culture and family events (excludes sport / league fixtures)
- **concert** — concerts, with world-class national tours flagged

The pipeline was built and tested against real Polish event sources (both JSON-LD
and JS-rendered pages). See a rendered example in
[`examples/sample_digest.md`](examples/sample_digest.md), the design in
[`docs/architecture.md`](docs/architecture.md), and the full spec in
[`documents/PRD.md`](documents/PRD.md).

## Quick start (offline demo — no network, no keys)

Requirements: **Python 3.9+**.

```bash
pip install -r requirements.txt
python orchestrator.py --fixtures fixtures/sample_events.json --dry-run
```

This runs the **full pipeline** on sample data: normalization, classification,
filtering (the sample football match is dropped, Sting is flagged as a national
tour), deduplication, ranking and digest rendering. No external site is touched.

The rendered digest is written to `DIGEST.md`, and per-run artifacts (a JSON run
report and a copy of the digest) land in `reports/`.

> **Note on the demo output:** the sample events carry fixed dates, while the
> pipeline only keeps events inside its forward-looking time windows (14 days by
> default, longer for concerts). Depending on the current date, the demo may show
> only the future-dated events (e.g. the Sting tour). For a fully populated digest
> across all three streams, see [`examples/sample_digest.md`](examples/sample_digest.md).

The same offline demo runs in CI on every push (see the badge above).

## How it works

```
scheduler / agent  ->  orchestrator.py  ->  source adapters (scrape enabled sources)
                                        ->  normalize -> classify -> filter
                                        ->  deduplicate -> rank
                                        ->  DIGEST.md (Markdown digest)
```

On a cadence (e.g. daily), a scheduler or an AI coding agent runs the same
`orchestrator.py` entrypoint: it scrapes the enabled sources, finds new events,
runs them through the pipeline, and writes `DIGEST.md`. Python-native parsers handle
JSON-LD and HTML; a Firecrawl adapter handles JS-rendered pages and acts as a
fallback when a direct request returns no usable content. Optional source discovery
(`--discover`) proposes new sources for manual review instead of scraping them
automatically.

> This public repository is a portfolio demonstration. It does **not** include an
> active scheduled integration. Its "proof of life" is the CI job running the
> offline fixtures demo.

## Live scraping (opt-in)

The scraper is fully functional. External sources are simply **disabled by default**
in [`config/sources.yaml`](config/sources.yaml) (`enabled: false`). To run live:

1. Enable only the sources you are authorized to use.
2. For JS-rendered sources, provide a `FIRECRAWL_API_KEY` (see `.env.example`).
3. Run `python orchestrator.py --dry-run` (build without delivering) or drop
   `--dry-run` to deliver.

Please read [`docs/responsible-use.md`](docs/responsible-use.md) first — you are
responsible for each source's terms of service, `robots.txt` and applicable data
licensing.

## Configuration

| File | What you set |
|---|---|
| `config/sources.yaml` | Source registry: method (python/firecrawl), streams, `enabled`, fallback |
| `config/filters.yaml` | Time windows, caps, Firecrawl budget, keyword and exclusion rules |
| `.env` (from `.env.example`) | Optional `FIRECRAWL_API_KEY`, optional `SLACK_BOT_TOKEN` |

Default window is 14 days. World-class concerts (`national_scope`) use a longer
window (`national_concert_window_days`, default 365) because tickets go on sale far
in advance.

## Structure

```
orchestrator.py     CLI entrypoint
config/             sources.yaml, filters.yaml
scrapers/           base + python parsers + firecrawl adapter + fixture loader + registry
scrapers/firecrawl_cli.py   thin CLI over the Firecrawl API (JS-rendered pages)
pipeline/           models, normalize, classify, filter_rules, dedup, rank
state/              SQLite: schema.sql + db.py (dedup and state between runs)
delivery/           slack.py (digest formatting + optional Slack delivery)
discovery/          research_bridge.py (optional --discover: candidates for review)
docs/               architecture, responsible use
examples/           sample_digest.md (rendered digest example)
fixtures/           sample_events.json (offline demo data)
tests/              pytest
```

## Tests

```bash
python -m pytest -q
```

## Responsible use

This repository demonstrates an event-processing pipeline and runs offline on sample
fixtures by default. External sources are disabled by default. You are responsible
for verifying source terms, `robots.txt` rules and applicable data licenses before
enabling live extraction. Details: [`docs/responsible-use.md`](docs/responsible-use.md).

## License

MIT — see [`LICENSE`](LICENSE).
