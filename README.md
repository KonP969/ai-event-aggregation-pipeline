# AI Event Aggregation Pipeline

[![tests](https://github.com/KonP969/ai-event-aggregation-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/KonP969/ai-event-aggregation-pipeline/actions/workflows/tests.yml)

**🇬🇧 English** · [🇵🇱 Polski](README.pl.md)

The pipeline collects events from multiple sources, converts them into a common
format, removes duplicates and irrelevant results, and produces a structured
Markdown or **Slack** digest. It can also run on a schedule as a
**Claude Code routine** (see [Works best as a Claude Code routine](#works-best-as-a-claude-code-routine)).

Events are grouped into three configurable streams:

- **ai_digital** for industry AI / data / digital meetups and conferences
- **culture_family** for culture and family events, minus sport and league fixtures
- **concert** for concerts, with world-class national tours flagged

The pipeline has been tested against Polish event sources, including JSON-LD and
JS-rendered pages. See a rendered example in
[`examples/sample_digest.md`](examples/sample_digest.md), the design in
[`docs/architecture.md`](docs/architecture.md), and the full spec in
[`documents/PRD.md`](documents/PRD.md).

I used Claude Code and Codex for implementation, debugging and testing.

## Quick start (offline demo, no network, no keys)

Requirements: **Python 3.9+**.

```bash
pip install -r requirements.txt
python orchestrator.py --fixtures fixtures/sample_events.json --dry-run
```

This runs the **full pipeline** on sample data: normalize, classify, filter (the
pipeline drops the sample football match and flags Sting as a national tour),
deduplicate, rank and render the digest. The demo touches no external site.

The run writes the digest to `DIGEST.md`, plus per-run artifacts (a JSON report and a
copy of the digest) to `reports/`.

> **Note on the demo output:** the sample events carry fixed dates, and the pipeline
> keeps only events inside its forward-looking time windows (14 days by default, longer
> for concerts). Depending on today's date, the demo may surface only the future-dated
> events, such as the Sting tour. For a fully populated digest across all three streams,
> see [`examples/sample_digest.md`](examples/sample_digest.md).

The same offline demo runs in CI on every push (see the badge above).

## How it works

```
scheduler / agent  ->  orchestrator.py  ->  source adapters (scrape enabled sources)
                                        ->  normalize -> classify -> filter
                                        ->  deduplicate -> rank
                                        ->  DIGEST.md  +  Slack digest
```

On a cadence such as daily, a scheduler or an AI coding agent runs the same
`orchestrator.py` entrypoint. It scrapes the enabled sources, finds new events, runs
them through the pipeline, and produces the digest, which it writes to `DIGEST.md`
and delivers to **Slack**. Python-native parsers handle JSON-LD and HTML. A Firecrawl
adapter handles JS-rendered pages and takes over when a direct request returns no
usable content. Optional source discovery (`--discover`) proposes new sources for you
to review instead of scraping them automatically.

> The repository does not include an active scheduled integration. The CI job runs
> the offline fixtures demo on every push.

## Works best as a Claude Code routine

Run the pipeline unattended on a schedule, for example as a
[Claude Code](https://www.anthropic.com/claude-code) routine that fires daily,
refreshes the digest, and pushes it back to the repository or posts it to Slack.

**Sample routine prompt:**

```text
Connect to the repository.

Run: python orchestrator.py --dry-run
Commit and push the refreshed report:
  git add DIGEST.md
  git commit -m "chore: update event calendar (routine)"
  git push
If orchestrator exits with a non-zero code, note which source failed
(from reports/run-*.json).
```

**Routine environment:**

- **Setup script** installs the dependencies by name, before the agent starts:
  ```bash
  pip install httpx beautifulsoup4 python-dateutil pyyaml firecrawl-py
  ```
- **Environment variables:** `FIRECRAWL_API_KEY` for JS-rendered sources, and optionally
  `SLACK_BOT_TOKEN` for Slack delivery. Keep secrets in a secure secret store, never in
  the prompt, the source config or committed files.
- **Connectors:** Slack, if you want the digest delivered to a channel.

To deliver to Slack instead of committing `DIGEST.md`, drop `--dry-run` so the run
delivers the digest. Enable only the sources you are authorized to use, and read
[Responsible use](#responsible-use) first.

## Live scraping (opt-in)

The scraper works. External sources ship disabled by default in
[`config/sources.yaml`](config/sources.yaml) (`enabled: false`). To run live:

1. Enable only the sources you are authorized to use.
2. For JS-rendered sources, provide a `FIRECRAWL_API_KEY` (see `.env.example`).
3. Run `python orchestrator.py --dry-run` to build without delivering, or drop
   `--dry-run` to deliver.

Read [`docs/responsible-use.md`](docs/responsible-use.md) first. You are responsible
for each source's terms of service, `robots.txt` and applicable data licensing.

## Configuration

| File | What you set |
|---|---|
| `config/sources.yaml` | Source registry: method (python/firecrawl), streams, `enabled`, fallback |
| `config/filters.yaml` | Time windows, caps, Firecrawl budget, keyword and exclusion rules |
| `.env` (from `.env.example`) | Optional `FIRECRAWL_API_KEY`, optional `SLACK_BOT_TOKEN` |

The default window is 14 days. World-class concerts (`national_scope`) get a longer
window (`national_concert_window_days`, default 365), because tickets go on sale far in
advance.

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

This repo demonstrates an event-processing pipeline and runs offline on sample fixtures
by default. External sources ship disabled. Verify each source's terms, `robots.txt`
rules and data licenses before you enable live extraction. Details:
[`docs/responsible-use.md`](docs/responsible-use.md).

## License

MIT. See [`LICENSE`](LICENSE).
