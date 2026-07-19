# AI Event Aggregation Pipeline

[![tests](https://github.com/KonP969/ai-event-aggregation-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/KonP969/ai-event-aggregation-pipeline/actions/workflows/tests.yml)

[🇬🇧 English](README.md) · **🇵🇱 Polski**

Pipeline zbiera wydarzenia z wielu źródeł, sprowadza je do wspólnego formatu, usuwa
duplikaty i nietrafione wyniki, a następnie tworzy uporządkowany digest w Markdownie
lub na **Slacku**. Może również działać cyklicznie jako **rutyna Claude Code**
(patrz [Najlepiej działa jako rutyna Claude Code](#najlepiej-działa-jako-rutyna-claude-code)).

Wydarzenia są dzielone na trzy konfigurowalne strumienie:

- **ai_digital** - branżowe wydarzenia AI / data / digital (konferencje, meetupy)
- **culture_family** - wydarzenia kulturalne i rodzinne, bez sportu i rozgrywek ligowych
- **concert** - koncerty, z oznaczeniem tras world-class o zasięgu ogólnopolskim

Pipeline został przetestowany na polskich źródłach wydarzeń, zarówno JSON-LD, jak i
stronach renderowanych JS. Wyrenderowany przykład:
[`examples/sample_digest.md`](examples/sample_digest.md), architektura:
[`docs/architecture.md`](docs/architecture.md), pełna specyfikacja:
[`documents/PRD.md`](documents/PRD.md).

Przy implementacji, debugowaniu i testach korzystałem z Claude Code i Codex.

## Szybki start (demo offline, bez sieci i kluczy)

Wymagania: **Python 3.9+**.

```bash
pip install -r requirements.txt
python orchestrator.py --fixtures fixtures/sample_events.json --dry-run
```

Uruchamia **pełny pipeline** na danych przykładowych: normalizacja, klasyfikacja,
filtrowanie (pipeline odsiewa przykładowy mecz i oznacza Stinga jako trasę
ogólnopolską), deduplikacja, ranking i renderowanie digestu. Demo nie odpytuje żadnej
zewnętrznej strony.

Run zapisuje digest do `DIGEST.md`, a artefakty runu (raport JSON i kopię digestu) do
`reports/`.

> **Uwaga o wyniku demo:** przykładowe wydarzenia mają stałe daty, a pipeline zostawia
> tylko te w oknach czasowych patrzących w przód (domyślnie 14 dni, dłużej dla
> koncertów). Zależnie od dzisiejszej daty demo pokaże czasem tylko wydarzenia z
> przyszłą datą, jak trasa Stinga. Pełny, zapełniony digest we wszystkich trzech
> strumieniach zobaczysz w [`examples/sample_digest.md`](examples/sample_digest.md).

To samo demo offline działa w CI przy każdym pushu (patrz badge u góry).

## Jak to działa

```
scheduler / agent  ->  orchestrator.py  ->  adaptery zrodel (scrape wlaczonych zrodel)
                                        ->  normalize -> classify -> filter
                                        ->  deduplicate -> rank
                                        ->  DIGEST.md  +  digest na Slacka
```

Cyklicznie, na przykład codziennie, scheduler lub agent AI uruchamia ten sam entrypoint
`orchestrator.py`. Scrapuje włączone źródła, znajduje nowe wydarzenia, przepuszcza je
przez pipeline i tworzy digest, który zapisuje do `DIGEST.md` i dostarcza na **Slacka**.
Parsery w Pythonie obsługują JSON-LD i HTML. Adapter Firecrawl obsługuje strony
renderowane JS i przejmuje robotę, gdy bezpośredni request nie zwraca użytecznej treści.
Opcjonalne discovery źródeł (`--discover`) proponuje nowe źródła do Twojego przeglądu,
zamiast scrapować je automatycznie.

> Repozytorium nie zawiera aktywnej integracji z harmonogramem. Przy każdym pushu CI
> uruchamia demo offline na danych przykładowych.

## Najlepiej działa jako rutyna Claude Code

Uruchamiasz pipeline bez nadzoru, na harmonogramie, na przykład jako rutynę
[Claude Code](https://www.anthropic.com/claude-code), która odpala się codziennie,
odświeża digest i wypycha go z powrotem do repozytorium albo publikuje na Slacku.

**Przykładowy prompt rutyny:**

```text
Połącz się z repozytorium.

Uruchom: python orchestrator.py --dry-run
Zacommituj i wypchnij zaktualizowany raport:
  git add DIGEST.md
  git commit -m "chore: aktualizacja kalendarza imprez (routine)"
  git push
Jeśli orchestrator zwróci kod != 0, napisz które źródło padło
(z reports/run-*.json).
```

**Środowisko rutyny:**

- **Setup script** instaluje zależności po nazwie, zanim agent wystartuje:
  ```bash
  pip install httpx beautifulsoup4 python-dateutil pyyaml firecrawl-py
  ```
- **Zmienne środowiskowe:** `FIRECRAWL_API_KEY` dla źródeł renderowanych JS, opcjonalnie
  `SLACK_BOT_TOKEN` dla dostarczania na Slacka. Sekrety trzymaj w bezpiecznym magazynie
  sekretów, nigdy w promptcie, konfiguracji źródeł ani commitowanych plikach.
- **Konektory:** Slack, jeśli chcesz dostarczać digest na kanał.

Żeby dostarczać na Slacka zamiast commitować `DIGEST.md`, zrzuć `--dry-run`, a run
dostarczy digest. Włączaj tylko źródła, do których masz uprawnienia, i najpierw
przeczytaj [Odpowiedzialne użycie](#odpowiedzialne-użycie).

## Scraping na żywo (opcjonalny)

Scraper działa. Zewnętrzne źródła są domyślnie wyłączone w
[`config/sources.yaml`](config/sources.yaml) (`enabled: false`). Żeby uruchomić na żywo:

1. Włącz tylko źródła, do których masz uprawnienia.
2. Dla źródeł renderowanych JS podaj `FIRECRAWL_API_KEY` (patrz `.env.example`).
3. Uruchom `python orchestrator.py --dry-run`, żeby zbudować bez dostarczania, albo
   zrzuć `--dry-run`, żeby dostarczyć.

Najpierw przeczytaj [`docs/responsible-use.md`](docs/responsible-use.md). To Ty
odpowiadasz za regulamin, `robots.txt` i licencjonowanie danych każdego źródła.

## Konfiguracja

| Plik | Co ustawiasz |
|---|---|
| `config/sources.yaml` | Rejestr źródeł: metoda (python/firecrawl), strumienie, `enabled`, fallback |
| `config/filters.yaml` | Okna czasowe, capy, budżet Firecrawl, słowa kluczowe i wykluczenia |
| `.env` (z `.env.example`) | Opcjonalny `FIRECRAWL_API_KEY`, opcjonalny `SLACK_BOT_TOKEN` |

Domyślne okno to 14 dni. Koncerty world-class (`national_scope`) dostają dłuższe okno
(`national_concert_window_days`, domyślnie 365), bo bilety sprzedają się z dużym
wyprzedzeniem.

## Struktura

```
orchestrator.py     entrypoint CLI
config/             sources.yaml, filters.yaml
scrapers/           base + parsery python + adapter firecrawl + loader fixtures + registry
scrapers/firecrawl_cli.py   cienki CLI wokol Firecrawl API (strony renderowane JS)
pipeline/           models, normalize, classify, filter_rules, dedup, rank
state/              SQLite: schema.sql + db.py (dedup i stan miedzy runami)
delivery/           slack.py (formatowanie digestu + opcjonalne dostarczanie na Slacka)
discovery/          research_bridge.py (opcjonalne --discover: kandydaci do przegladu)
docs/               architektura, odpowiedzialne uzycie
examples/           sample_digest.md (przyklad wyrenderowanego digestu)
fixtures/           sample_events.json (dane demo offline)
tests/              pytest
```

## Testy

```bash
python -m pytest -q
```

## Odpowiedzialne użycie

To repo demonstruje pipeline przetwarzania wydarzeń i domyślnie działa offline na
przykładowych fixtures. Zewnętrzne źródła są domyślnie wyłączone. Zweryfikuj regulamin,
reguły `robots.txt` i licencje danych każdego źródła, zanim włączysz scrapowanie na
żywo. Szczegóły: [`docs/responsible-use.md`](docs/responsible-use.md).

## Licencja

MIT. Patrz [`LICENSE`](LICENSE).
