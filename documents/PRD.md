# Event Aggregation Agent — Product Requirements Document

> **Document status:** Draft v1.0
> **Owner:** Konrad
> **Last updated:** 2026-06-05
> **Scope:** Ad-hoc agent (phase 1) → scheduled workflow via Claude routine + remote GitHub repo (phase 2)

---

## 1. Introduction

This document specifies the requirements for an **Event Aggregation Agent**: an AI-driven pipeline that discovers, scrapes, classifies, deduplicates, and delivers curated event listings from Polish event-aggregator websites into Slack.

The agent serves three distinct event streams with different geographic and topical rules:

1. **Industry events** — AI and Digital topics (e.g. conferences, meetups, workshops).
2. **Cultural / family events** — interesting, active, and musical happenings in the Tricity area, explicitly **excluding** football matches and any league/sports matches.
3. **Concerts** — primarily in the Tricity area, expanding to all of Poland when the performing artist is world-class / internationally touring.

The purpose of this document is to give an implementing engineer or coding agent (Claude Code / Codex) enough detail to build the agent end-to-end without further requirement gathering, while leaving clearly flagged decision points to be resolved interactively at implementation time.

### 1.1 Definitions and abbreviations

| Term | Meaning |
|------|---------|
| Tricity (Trójmiasto) | Gdańsk + Gdynia + Sopot and immediate surroundings |
| Source | An external website/platform that aggregates or sells events (e.g. Crossweb, eBilet) |
| Stream / category | One of the three target event types: `ai_digital`, `culture_family`, `concert` |
| Digest | A formatted Slack message summarising selected events for a run |
| Run | A single execution of the pipeline (ad-hoc or scheduled) |
| Research agent | A pre-existing component in the repo that discovers candidate sources (see §7.2 — interface to be confirmed) |
| World-class artist | An internationally touring / globally recognised performer (heuristic, see §5.4) |

### 1.2 Out of scope (phase 1)

- Ticket purchasing or checkout automation.
- A graphical web UI or dashboard.
- Personalised recommendations beyond the rule-based filters defined here.
- User accounts / multi-tenant access (single operator: Konrad).

---

## 2. Product overview

The Event Aggregation Agent is a **hybrid scraping pipeline** (Firecrawl + Python) orchestrated as an AI agent. On each run it:

1. Loads a registry of vetted sources (and optionally runs a discovery pass via the existing research agent to find new ones).
2. Fetches event data using the appropriate technique per source (lightweight HTTP/Python for static pages, Firecrawl for JavaScript-heavy or dynamically rendered pages).
3. Normalises raw results into a single canonical event schema.
4. Classifies each event into one of the three streams and applies the stream-specific geographic, topical, and exclusion rules.
5. Deduplicates events within and across sources, and against previously delivered events (persisted state).
6. Ranks/curates the surviving events and delivers a grouped digest to Slack.

**Phase 1** is invoked **ad hoc** (manual trigger, parameterised). **Phase 2** will wrap the same core in a schedule, run from a remote GitHub repository and triggered by a Claude routine, with no architectural rewrite required.

```
                ┌──────────────────────────────────────────────┐
                │                 ORCHESTRATOR                   │
                │   (ad-hoc CLI now → Claude routine later)      │
                └───────────────┬──────────────────────────────┘
                                │
        ┌───────────────┬───────┴────────┬────────────────┐
        ▼               ▼                ▼                ▼
  Source registry   Research agent   Scrapers (hybrid)   State store
  (config/yaml)     (discovery)      Firecrawl + Python  (SQLite)
                                          │
                                          ▼
                                  Normalize → Classify
                                  → Filter → Dedup → Rank
                                          │
                                          ▼
                                   Slack digest delivery
```

---

## 3. Goals and objectives

### 3.1 Primary goals

- **G1 — Save discovery time:** replace manual browsing of 6–10 event sites with a single Slack digest.
- **G2 — Relevant, low-noise output:** every delivered event should match its stream's rules; minimise false positives (esp. excluded sports/league matches in the family stream).
- **G3 — No duplicates:** the same event must not appear twice in one digest, nor be re-delivered in later runs unless materially updated.
- **G4 — Freshness:** only surface upcoming events within the configured date window.
- **G5 — Extensibility:** adding a new source should require config + one parser, not a rewrite.
- **G6 — Smooth path to automation:** phase 1 must be structured so phase 2 (scheduling) is a wrapper, not a refactor.

### 3.2 Success metrics

| Metric | Target (phase 1) |
|--------|------------------|
| Relevance precision (delivered events that genuinely fit the stream) | ≥ 90% |
| Excluded-content leakage (football/league matches in family stream) | 0 in a typical run |
| Duplicate rate within a digest | 0% |
| Re-delivery of unchanged events across runs | 0% |
| Source coverage | ≥ 2 working sources per stream at launch |
| Run completion (no fatal crash even if a source fails) | 100% |
| Firecrawl credit consumption per run | within a configurable budget cap |

> **Note / uncertainty:** these targets are proposed defaults. They are not derived from existing baselines and should be revisited once real run data exists.

### 3.3 Non-goals

- Maximising the *number* of events. Curation quality outweighs volume.
- Being a real-time ticket-price tracker.

---

## 4. Target audience

| Audience | Description | Needs from the product |
|----------|-------------|------------------------|
| **Primary user (Konrad)** | Digital marketer / aspiring data engineer based in Gdynia. Tricity-focused. Interested in AI, digital, analytics, data engineering. | The `ai_digital` and `concert` streams; reliable, low-noise Slack delivery; a clean, repo-friendly codebase to learn from and extend. |
| **Secondary user (family)** | Konrad's household, including children. | The `culture_family` stream: family-suitable, active, cultural, and musical events in the Tricity, with sports/league matches removed. |
| **Maintainer (also Konrad / future contributors)** | Whoever extends the agent. | Clear source registry, modular parsers, observability, documented schema. |

---

## 5. Features and requirements

### 5.1 Functional features

| ID | Feature | Description | Priority |
|----|---------|-------------|----------|
| F1 | Source registry | A versioned config listing each source with its scrape method, URL templates, stream(s) served, and parser reference. | Must |
| F2 | Source discovery (research) | Invoke the existing research agent to propose new candidate sources before scraping; results reviewed before being added to the registry. | Should |
| F3 | Hybrid scraping | Per-source choice between Python (static/fast/cheap) and Firecrawl (JS-rendered/dynamic). Decision is declared in the registry, with Firecrawl as fallback on Python failure. | Must |
| F4 | Normalization | Map every raw event to the canonical schema (§7.4). | Must |
| F5 | Classification | Assign each event to `ai_digital`, `culture_family`, or `concert`. | Must |
| F6 | Geographic + topical filtering | Apply stream-specific rules (§5.4). | Must |
| F7 | Exclusion filtering | Remove football matches and **all** league/sports matches from the family stream. | Must |
| F8 | Family-suitability scoring | Flag events appropriate for a family with children. | Should |
| F9 | World-class detection | For concerts, decide whether to widen scope from Tricity to all of Poland. | Must |
| F10 | Deduplication | De-dupe within a run and against persisted delivered events. | Must |
| F11 | Ranking / curation | Order and optionally cap events per stream by a relevance score. | Should |
| F12 | Slack delivery | Post a grouped, readable digest to a configured Slack channel or DM. | Must |
| F13 | Ad-hoc invocation | Run with parameters: streams, date window, city scope, max items. | Must |
| F14 | State persistence | Store seen/delivered events to support cross-run dedup and "what changed" logic. | Must |
| F15 | Observability | Per-run summary: sources hit, events found/kept/dropped, failures, credits used. | Should |
| F16 | Cost guardrails | Cap Firecrawl usage per run; warn/skip when exceeded. | Should |
| F17 | Scheduling hook (phase 2) | A clean entry point the Claude routine can call on a schedule from the GH repo. | Should (phase 2) |
| F18 | Guided deployment | When deployed via Claude Code / Codex, use **AskUserQuestion** to confirm key decisions interactively (see §7.8). | Must |

### 5.2 Non-functional requirements

| ID | Requirement |
|----|-------------|
| NF1 | **Resilience:** a single source failing (timeout, layout change, rate limit) must not abort the run; it is logged and skipped. |
| NF2 | **Idempotency:** running twice with the same window must not produce duplicate Slack messages or duplicate stored events. |
| NF3 | **Compliance:** respect each source's `robots.txt`, terms of service, and reasonable rate limits; identify with a sane User-Agent; prefer official feeds/APIs where available. |
| NF4 | **Secrets hygiene:** all API keys/tokens loaded from environment / secret store, never committed. |
| NF5 | **Timezone correctness:** all dates parsed and stored in `Europe/Warsaw`; comparisons account for DST. |
| NF6 | **Cost control:** Firecrawl is the more expensive path; default to Python where viable. |
| NF7 | **Portability:** runnable locally (phase 1) and from a CI/cron-style environment in the GH repo (phase 2) with no code change beyond config. |
| NF8 | **Observability:** structured logs; a machine-readable run report artifact. |

### 5.3 Candidate source landscape (validated)

The following sources were validated as active and relevant during requirements research (2026). The registry should start from this set; F2 may extend it.

| Source | Primary stream(s) | Notable structure | Suggested method |
|--------|-------------------|-------------------|------------------|
| **Crossweb.pl** | `ai_digital` | City filters (incl. Gdańsk/Trójmiasto), `AI/ML` tags, free/paid, date labels; online & on-site | Python first (structured listing), Firecrawl fallback |
| **Evenea (app.evenea.pl)** | `ai_digital` | Organiser-hosted event pages (e.g. VibeConf); per-event detail | Firecrawl (per-event, JS) |
| **Meetup.com** (optional) | `ai_digital` | Group/event listings; may need auth/JS | Firecrawl |
| **Trojmiasto.pl `/imprezy/`** | `culture_family`, `concert` | Rich categories incl. *Imprezy dla dzieci*, *Sport, rekreacja* (tagged `mecz` → used for exclusion), *Koncerty*, *Spektakle*; city + date-range + price filters | Python first |
| **Going (goingapp.pl)** | `culture_family`, `concert` | Tricity supported; curated city calendar | Firecrawl (reported flaky/JS-heavy API) |
| **eBilet.pl** | `concert`, `culture_family` | `/miasto/trojmiasto`, category pages, venue data | Python first, Firecrawl fallback |
| **Ticketmaster.pl / LiveNation.pl** | `concert` (world-class → national) | International touring artists, arenas | Firecrawl |
| **Eventim.pl / Kupbilecik / koncertyw.pl** (supplementary) | `concert` | National concert listings | Python/Firecrawl per page |
| **pikgdansk.pl / atrakcje.pl** (supplementary) | `culture_family`, `concert` | Tricity culture & concerts | Python |

> **Uncertainty flag:** scrape-ability and ToS can change. Each parser must be written defensively and the registry must allow disabling a source quickly.

### 5.4 Stream rules (filtering specification)

| Stream | Geographic rule | Inclusion (topics/categories) | Exclusion |
|--------|-----------------|-------------------------------|-----------|
| **`ai_digital`** | Tricity + surroundings **by default**; expand to any major Polish city (Warszawa, Kraków, Wrocław, Poznań, Katowice/Śląsk, Łódź) **only if the event is "large"** | AI, ML, GenAI, data, analytics, data engineering, digital/performance marketing, product, dev/tech conferences & meetups | Purely non-technical business events with no AI/digital angle |
| **`culture_family`** | **Tricity only** (Gdańsk/Gdynia/Sopot) | Concerts (small/local), theatre & spectacles, kids' events, festivals, exhibitions, workshops, active/outdoor/recreational, family-oriented happenings | **Football matches and ALL league/sports matches** (`mecz`, ligowe rozgrywki); 18+/adult-only content |
| **`concert`** | **Tricity by default**; expand to **all of Poland** when the artist is world-class / internationally touring | Live music across genres | Tribute-only/very local open-mic style events may be downranked (config) |

**"Large event" heuristic (`ai_digital` national expansion):** multi-day OR conference-type OR clearly major/known brand (e.g. Infoshare-scale) OR estimated large attendance. Implemented as a scored heuristic; ambiguous cases default to Tricity-only.

**"World-class artist" heuristic (`concert` national expansion):** artist appears on Ticketmaster/LiveNation international tour listings OR plays a large arena (e.g. Ergo Arena, Tauron Arena, PGE Narodowy, large stadiums) OR matches a maintained allowlist. Ambiguous cases default to Tricity-only.

> **Uncertainty flag:** both heuristics are inherently fuzzy. The design should allow an optional LLM-assisted judgment call for borderline events, and must log *why* an event was expanded to national scope so the rule can be tuned.

---

## 6. User stories and acceptance criteria

> All stories are testable. IDs are stable for traceability. AC = acceptance criteria.

### 6.1 Security, access, and configuration

**ST-101 — Secure credential loading**
*As the operator, I want all API keys and tokens loaded from a secret store / environment so that nothing sensitive is committed to the repo.*
- AC1: Firecrawl key, Slack token, and any source credentials are read from env vars / a secrets file ignored by git.
- AC2: The repo contains a `.env.example` with placeholder keys and no real secrets.
- AC3: Starting the agent without required secrets fails fast with a clear, non-leaking error message.

**ST-102 — Source registry configuration**
*As the maintainer, I want sources defined in a single config so I can add, disable, or re-route a source without touching core logic.*
- AC1: Each entry declares: id, display name, stream(s), base URL/templates, scrape method (`python` | `firecrawl`), parser reference, enabled flag, rate-limit.
- AC2: Setting `enabled: false` removes the source from the next run with no code change.
- AC3: Invalid/malformed entries are reported at startup and skipped, not crashed on.

**ST-103 — Tunable filters and thresholds**
*As the operator, I want filter parameters (date window, per-stream caps, heuristics' thresholds, Firecrawl budget) in config.*
- AC1: Changing the date window or per-stream cap changes output without code edits.
- AC2: Defaults are documented.

### 6.2 Source discovery (research)

**ST-104 — Discover candidate sources**
*As the operator, I want to invoke the existing research agent to propose new candidate sources before a run.*
- AC1: Discovery output is a structured list (name, URL, why relevant, suggested stream).
- AC2: Discovered sources are **not** auto-scraped; they are surfaced for review and manual addition to the registry.
- AC3: If the research agent is unavailable, the run proceeds with the existing registry and logs a warning.

> **Dependency / uncertainty flag:** the research agent already exists in the repo, but its exact invocation interface (CLI, function, I/O contract) is unknown to this document and must be confirmed at implementation time (see ST-123).

### 6.3 Scraping (hybrid)

**ST-105 — Scrape a static source via Python**
*As the system, I want to fetch and parse listing pages of static sources with Python so that cost and latency stay low.*
- AC1: A configured `python` source returns a list of raw events with at least: title, date(s), URL, location text.
- AC2: HTTP errors and empty results are handled without raising fatal exceptions.

**ST-106 — Scrape a JS-rendered source via Firecrawl**
*As the system, I want to use Firecrawl for sources requiring JS rendering so that I still get their data.*
- AC1: A configured `firecrawl` source returns structured content for listing and/or detail pages.
- AC2: Firecrawl usage is counted toward the per-run budget.

**ST-107 — Method fallback**
*As the system, when a Python scrape yields nothing or errors, I want to optionally fall back to Firecrawl per source config.*
- AC1: Fallback only triggers when `fallback: firecrawl` is set for that source.
- AC2: The fallback attempt is logged distinctly from the primary attempt.

**ST-108 — Respect robots and rate limits**
*As a responsible client, I want to honour robots.txt and rate limits.*
- AC1: Requests use a configured delay/limit per source.
- AC2: Disallowed paths are not fetched.
- AC3: A sane, identifiable User-Agent is sent.

**ST-109 — Source failure isolation (edge case)**
*As the operator, I want one failing source to never abort the whole run.*
- AC1: A timeout/exception in source A still allows sources B…N to complete.
- AC2: The run report lists which sources failed and why.

### 6.4 Data modelling and persistence

**ST-110 — Canonical event schema & storage**
*As the system, I want every event normalised into one schema and persisted so dedup and cross-run state work.*
- AC1: All scraped events are mapped to the schema in §7.4 (missing optional fields allowed as null).
- AC2: Events are stored in the state store (SQLite) keyed by a deterministic `dedup_key`.
- AC3: Re-storing an event with the same `dedup_key` updates rather than duplicates the record.
- AC4: The schema migration/init is reproducible from a script in the repo.

**ST-111 — Track delivery state**
*As the system, I want to record which events were delivered to Slack and when.*
- AC1: Each event row carries `delivered` and `delivered_at`.
- AC2: A re-run does not re-deliver an already-delivered, unchanged event (see ST-118).

### 6.5 Classification and filtering

**ST-112 — Classify into streams**
*As the system, I want each event tagged with exactly one of the three streams.*
- AC1: Every kept event has `category ∈ {ai_digital, culture_family, concert}`.
- AC2: Events matching none of the streams are dropped and counted in the report.

**ST-113 — AI/Digital geographic rule**
*As the user, I want AI/Digital events filtered to Tricity unless the event is large.*
- AC1: Non-large `ai_digital` events outside Tricity are dropped.
- AC2: Large events in other major Polish cities are kept and flagged `national_scope=true` with a logged reason.

**ST-114 — Family stream: Tricity + exclusions**
*As a family user, I want only Tricity cultural/active/musical events, with no football or league/sports matches.*
- AC1: `culture_family` events outside Tricity are dropped.
- AC2: Any event identified as a football match or any league/sports match is excluded.
- AC3: A test fixture containing a `mecz`/sports entry results in that entry being excluded.

**ST-115 — Family-suitability flag**
*As a family user, I want events flagged for family suitability.*
- AC1: Events explicitly tagged for children/family are flagged `family_suitable=true`.
- AC2: Clearly adult-only events are flagged `family_suitable=false` (or dropped per config).

**ST-116 — Concert world-class expansion**
*As the user, I want Tricity concerts plus nationwide concerts only for world-class artists.*
- AC1: `concert` events in Tricity are kept regardless of artist.
- AC2: Non-Tricity concerts are kept only if the world-class heuristic passes, flagged `national_scope=true` with a logged reason.
- AC3: Borderline cases default to Tricity-only and are logged.

**ST-117 — Relevance ranking and caps**
*As the user, I want each stream ordered by relevance and optionally capped.*
- AC1: Each stream's events are sorted by a documented score (e.g. date proximity, topical match, source trust).
- AC2: A configurable max-per-stream truncates the list, keeping the top items.

### 6.6 Deduplication

**ST-118 — Within-run and cross-run dedup**
*As the user, I want no duplicates in a digest and no re-sends across runs.*
- AC1: Two records for the same real event (same/similar title + date + venue/city) collapse into one in the digest.
- AC2: An event already delivered in a previous run is not re-sent unless a material field (date, venue, price) changed.
- AC3: If a delivered event changed materially, it is re-sent and clearly marked as "updated".

### 6.7 Delivery (Slack)

**ST-119 — Formatted Slack digest**
*As the user, I want a readable Slack digest grouped by stream.*
- AC1: The message has three labelled sections (AI/Digital, Culture & Family, Concerts), each only shown if it has events.
- AC2: Each event line shows: title, date/time, city/venue, price (or "free"/"unknown"), and a link.
- AC3: National-scope and "updated" events are visually marked.

**ST-120 — Deliver to configured destination**
*As the operator, I want the digest posted to a chosen Slack channel or DM.*
- AC1: Destination is set in config (channel ID or DM target).
- AC2: A successful post is recorded (timestamp / message ref) for the run report.

**ST-121 — Empty-result handling (edge case)**
*As the user, I want a clear signal when nothing relevant was found.*
- AC1: If a stream has zero events, it is omitted from the digest.
- AC2: If all streams are empty, a short "no new events in window" message is sent (configurable on/off).

### 6.8 Invocation and operations

**ST-122 — Ad-hoc parameterised run**
*As the operator, I want to run on demand with parameters.*
- AC1: I can specify streams (any subset), date window, city scope override, and max-per-stream at invocation.
- AC2: Omitted parameters fall back to documented defaults.

**ST-123 — Guided deployment via Claude Code / Codex**
*As the operator deploying through Claude Code or Codex, I want the agent to confirm key decisions interactively using AskUserQuestion.*
- AC1: During setup the tool asks (via AskUserQuestion) at minimum: Slack destination, which sources/streams to enable, Firecrawl budget, and the research agent's invocation interface.
- AC2: It does not silently assume these where they are unknown.
- AC3: Answers are written into config, not hard-coded.

**ST-124 — Run report and observability**
*As the maintainer, I want a per-run summary.*
- AC1: The report lists, per source: events found, kept, dropped (with reasons), failures.
- AC2: It records total Firecrawl credits used and total runtime.
- AC3: The report is both logged and saved as a machine-readable artifact.

**ST-125 — Firecrawl budget guardrail (edge case)**
*As the operator, I want to avoid runaway scraping cost.*
- AC1: When the per-run Firecrawl budget is reached, remaining Firecrawl sources are skipped and noted.
- AC2: Python-only sources still complete.

**ST-126 — Timezone & date parsing (edge case)**
*As the user, I want correct local dates.*
- AC1: All dates are interpreted/stored as `Europe/Warsaw`.
- AC2: Date-window filtering is inclusive of the boundary days and DST-correct.

**ST-127 — Parser-break detection (edge case)**
*As the maintainer, I want to know when a source layout likely changed.*
- AC1: A source that historically returned events but now returns zero (while others succeed) is flagged "possible parser break" in the report.

**ST-128 — Scheduled run readiness (phase 2)**
*As the operator, I want a clean entry point a Claude routine can call on a schedule from the GH repo.*
- AC1: There is a single documented command/function that performs a full run with config-driven defaults.
- AC2: It runs non-interactively (no prompts) and exits with a status code reflecting success/partial/failure.
- AC3: State persists between scheduled runs so dedup works over time.

---

## 7. Technical requirements / stack

### 7.1 Recommended stack

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Language | **Python 3.11+** | Matches the hybrid requirement and the maintainer's data-engineering trajectory. |
| Static scraping | `requests` / `httpx` + `BeautifulSoup` / `selectolax` | Cheap, fast for structured listing pages (e.g. Crossweb, Trojmiasto.pl, eBilet). |
| Dynamic scraping | **Firecrawl** (MCP and/or API) | JS rendering for Evenea, Going, Ticketmaster/LiveNation. |
| Orchestration | Plain Python entrypoint (phase 1) → Claude routine wrapper (phase 2) | Keeps phase 1 simple; phase 2 is a thin wrapper. |
| State store | **SQLite** (file in repo-ignored data dir) | Lightweight, no server, perfect for dedup/state and portable to CI. |
| Config | YAML/TOML for source registry + filters; `.env` for secrets | Human-editable, diff-friendly. |
| Delivery | **Slack** (Bot token via Web API, or the Slack MCP connector) | Chosen output channel. |
| Optional LLM step | Claude (via API) for borderline classification / world-class judgment | Only for fuzzy cases; keep deterministic rules first. |
| Repo / CI (phase 2) | GitHub + Claude routine schedule | Per the stated phase-2 plan. |

> **Uncertainty flag:** Slack delivery can use either a Bot token + Web API directly (best for unattended phase-2 cron) or the Slack MCP connector (convenient during agent-driven phase 1). The final choice should be confirmed at deployment (ST-123). For non-interactive scheduled runs, a Bot token is generally the more robust path.

### 7.2 Component architecture

```
repo/
├── orchestrator.py          # entrypoint: full run (interactive + non-interactive)
├── config/
│   ├── sources.yaml         # source registry (ST-102)
│   └── filters.yaml         # date window, caps, heuristic thresholds, budget
├── discovery/
│   └── research_agent.*     # EXISTING component — interface TBD (ST-104, ST-123)
├── scrapers/
│   ├── base.py              # scraper interface
│   ├── python_<source>.py   # per static source
│   └── firecrawl_<source>.py# per dynamic source
├── pipeline/
│   ├── normalize.py         # → canonical schema (§7.4)
│   ├── classify.py          # stream assignment (ST-112)
│   ├── filter_rules.py      # geo + exclusion + family + world-class (§5.4)
│   ├── dedup.py             # within/cross-run (ST-118)
│   └── rank.py              # scoring + caps (ST-117)
├── delivery/
│   └── slack.py             # digest formatting + post (ST-119/120)
├── state/
│   ├── db.py                # SQLite access
│   └── schema.sql           # init/migration (ST-110)
├── reports/                 # per-run artifacts (ST-124)
├── .env.example
└── README.md
```

### 7.3 Hybrid scrape decision logic

1. Read source's declared `method` from the registry.
2. If `python`: fetch + parse; on empty/error and `fallback: firecrawl` set → retry via Firecrawl.
3. If `firecrawl`: fetch via Firecrawl, count credits, stop scheduling new Firecrawl jobs once budget cap is hit (Python sources unaffected).
4. Always return a list (possibly empty); never raise out of the scraper boundary.

### 7.4 Canonical event schema (data model)

| Field | Type | Notes |
|-------|------|-------|
| `id` | text (PK) | UUID or hash of `dedup_key` |
| `dedup_key` | text (unique) | normalised(title) + start_date + city/venue |
| `source` | text | registry id |
| `source_url` | text | original/detail URL |
| `category` | text | `ai_digital` \| `culture_family` \| `concert` |
| `subcategory` | text | e.g. `meetup`, `conference`, `theatre`, `kids`, `rock` |
| `title` | text | |
| `description` | text | trimmed |
| `start_datetime` | timestamp | `Europe/Warsaw` |
| `end_datetime` | timestamp | nullable |
| `venue_name` | text | nullable |
| `city` | text | normalised (Gdańsk/Gdynia/Sopot/…) |
| `address` | text | nullable |
| `is_tricity` | boolean | derived |
| `price_min` / `price_max` | numeric | nullable |
| `is_free` | boolean | derived |
| `ticket_url` | text | nullable |
| `artist` | text | concerts; nullable |
| `national_scope` | boolean | true if expanded beyond Tricity |
| `scope_reason` | text | why national (heuristic trace) |
| `family_suitable` | boolean | nullable |
| `relevance_score` | numeric | for ranking |
| `scraped_at` | timestamp | |
| `delivered` | boolean | default false |
| `delivered_at` | timestamp | nullable |
| `content_hash` | text | to detect material updates (ST-118 AC2/3) |

### 7.5 Deduplication strategy

- **Within run:** group by `dedup_key`; if collisions, keep the record from the most trusted source and merge missing fields.
- **Cross run:** compare incoming `dedup_key` against stored; if present and `content_hash` unchanged → suppress. If `content_hash` changed on a material field → mark "updated" and allow re-delivery.

### 7.6 Slack digest format (delivery contract)

- One message per run (or threaded per stream if it exceeds Slack length limits).
- Sections only rendered when non-empty.
- Each event: `*Title*` · date/time · city/venue · price · `<link|Bilety/Info>`; markers for `🌍 national` and `🔄 updated`.

### 7.7 Compliance and ethics

- Honour `robots.txt`, ToS, and rate limits (NF3); prefer official feeds/APIs.
- No login-walled or paywalled content circumvention.
- Store only event metadata, not personal data.

### 7.8 Deployment via Claude Code / Codex (process requirement)

When an implementing coding agent sets this up, it **must** use **AskUserQuestion** to resolve, at minimum:

1. **Slack destination** — which channel ID or DM, and Bot token vs MCP path.
2. **Sources & streams** — which sources to enable at launch per stream.
3. **Firecrawl budget** — per-run credit cap.
4. **Research agent interface** — how to invoke the existing in-repo discovery agent (command/function, inputs, output shape).
5. **Date window & caps** — default look-ahead and max events per stream.

It must not hard-code these or silently assume defaults for unknown items.

### 7.9 Phase 2 — scheduling (forward-looking)

- The same `orchestrator.py` full-run command runs non-interactively (ST-128).
- A **Claude routine** triggers it on a schedule against the **remote GitHub repo**; SQLite state persists between runs to keep dedup working.
- No core refactor expected — only secrets/config wiring for the CI/cron environment.

---

## 8. Design and user interface

This is an agent/CLI product with **Slack as its only end-user surface** (phase 1). "UI" therefore covers: (a) the Slack digest, (b) the invocation interface, and (c) configuration files.

### 8.1 Slack digest — example layout

```
📅  Event digest — 5–19 Jun 2026 (Tricity)         run 2026-06-05 18:00

🤖  AI / DIGITAL
• *Puzzle Kompetencji 2026 — AI Agent*  · Wed 10 Jun · Online · free · <link|Info>
• *Infoshare 2026*  🌍 · 27–28 May · Gdańsk · paid · <link|Info>

🎭  CULTURE & FAMILY (Tricity)
• *Bal dla dzieci — W krainie mórz*  👨‍👩‍👧 · Sat 7 Jun 10:00 · Gdańsk, Galeria Metropolia · free · <link|Info>
• *The Blues Brothers "Soul Mission"*  · Fri 6 Jun 19:00 · Gdynia · 80 zł+ · <link|Bilety>

🎵  CONCERTS
• *Dawid Podsiadło*  · Sat 20 Jun 17:30 · Sopot · <link|Bilety>
• *Sting — 3.0*  🌍 · Opera Leśna, Sopot · <link|Bilety>

— 9 events · 7 sources · 2 skipped (Going: timeout) · 14 Firecrawl credits
```

(Markers: `🌍` national-scope expansion, `👨‍👩‍👧` family-suitable, `🔄` updated since last run.)

### 8.2 Invocation interface (phase 1)

```
python orchestrator.py \
  --streams ai_digital,culture_family,concert \
  --window 14d \
  --max-per-stream 8 \
  --slack-dest <channel_id> \
  [--discover]            # run research agent first
  [--dry-run]             # build digest, do not post
```

- `--dry-run` prints the digest to stdout/report without posting (useful for tuning).
- Non-interactive scheduled mode (phase 2) uses config defaults and no flags.

### 8.3 Configuration UX principles

- One file to add a source (`sources.yaml`), one file to tune behaviour (`filters.yaml`), one file for secrets (`.env`).
- Every dropped event is explainable from the run report (which rule dropped it), supporting the operator's data-driven tuning.
- Defaults documented in `README.md`; `.env.example` ships with placeholders only.

### 8.4 Accessibility / readability

- Digest uses short lines, clear section emoji, and consistent ordering (date-ascending within stream) for fast scanning on mobile Slack.

---

## Appendix A — Open questions to confirm at implementation (via AskUserQuestion)

1. Research agent invocation contract (inputs/outputs/command). *(blocking for F2/ST-104)*
2. Slack delivery mechanism: Bot token (Web API) vs Slack MCP connector. *(affects phase-2 robustness)*
3. Exact Tricity "surroundings" radius for `ai_digital` (e.g. include Tczew/Wejherowo?).
4. Default per-stream caps and look-ahead window.
5. Whether to enable the optional LLM-assisted borderline classifier from day one.
6. Firecrawl per-run credit budget.
