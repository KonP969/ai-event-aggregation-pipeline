# AI Event Aggregation Pipeline

[![tests](https://github.com/KonP969/ai-event-aggregation-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/KonP969/ai-event-aggregation-pipeline/actions/workflows/tests.yml)

[🇬🇧 English](README.md) · **🇵🇱 Polski**

**Co to robi, po ludzku:** znajduje wydarzenia pasujące do tematów, lokalizacji i
przedziału czasowego, które Cię interesują, sortuje je do kategorii i cyklicznie
dostarcza uporządkowany digest na **Slacka** - gotową krótką listę pomysłów na miłe
spędzenie czasu. Zaprojektowany do uruchamiania jako **rutyna Claude Code**
(patrz [Najlepiej działa jako rutyna Claude Code](#najlepiej-działa-jako-rutyna-claude-code)).

Pod maską to konfigurowalny, wspierany przez AI pipeline, który zamienia surowe listy
wydarzeń w uszeregowany, zdeduplikowany digest w trzech strumieniach:

- **ai_digital** - branżowe wydarzenia AI / data / digital (konferencje, meetupy)
- **culture_family** - wydarzenia kulturalne i rodzinne (bez sportu / rozgrywek ligowych)
- **concert** - koncerty, z oznaczeniem tras world-class o zasięgu ogólnopolskim

Pipeline zbudowany i przetestowany na realnych polskich źródłach wydarzeń (zarówno
JSON-LD, jak i strony renderowane JS). Wyrenderowany przykład:
[`examples/sample_digest.md`](examples/sample_digest.md), architektura:
[`docs/architecture.md`](docs/architecture.md), pełna specyfikacja:
[`documents/PRD.md`](documents/PRD.md).

## Szybki start (demo offline, bez sieci i kluczy)

Wymagania: **Python 3.9+**.

```bash
pip install -r requirements.txt
python orchestrator.py --fixtures fixtures/sample_events.json --dry-run
```

Uruchamia **pełny pipeline** na danych przykładowych: normalizacja, klasyfikacja,
filtrowanie (przykładowy mecz zostaje odsiany, Sting oznaczony jako trasa ogólnopolska),
deduplikacja, ranking i renderowanie digestu. Żadna zewnętrzna strona nie jest odpytywana.

Wyrenderowany digest trafia do `DIGEST.md`, a artefakty runu (raport JSON i kopia
digestu) do `reports/`.

> **Uwaga o wyniku demo:** przykładowe wydarzenia mają stałe daty, a pipeline zostawia
> tylko te w oknach czasowych patrzących w przód (domyślnie 14 dni, dłużej dla
> koncertów). Zależnie od bieżącej daty demo może pokazać tylko wydarzenia z przyszłą
> datą (np. trasę Stinga). Pełny, zapełniony digest we wszystkich trzech strumieniach
> zobaczysz w [`examples/sample_digest.md`](examples/sample_digest.md).

To samo demo offline działa w CI przy każdym pushu (patrz badge u góry).

## Jak to działa

```
scheduler / agent  ->  orchestrator.py  ->  adaptery zrodel (scrape wlaczonych zrodel)
                                        ->  normalize -> classify -> filter
                                        ->  deduplicate -> rank
                                        ->  DIGEST.md  +  digest na Slacka
```

Cyklicznie (np. codziennie) scheduler lub agent AI uruchamia ten sam entrypoint
`orchestrator.py`: scrapuje włączone źródła, znajduje nowe wydarzenia, przepuszcza je
przez pipeline i tworzy digest - zapisany do `DIGEST.md` i/lub dostarczony na **Slacka**.
Parsery w Pythonie obsługują JSON-LD i HTML; adapter Firecrawl obsługuje strony
renderowane JS i działa jako fallback, gdy bezpośredni request nie zwraca użytecznej
treści. Opcjonalne discovery źródeł (`--discover`) proponuje nowe źródła do ręcznego
przeglądu, zamiast scrapować je automatycznie.

> To publiczne repozytorium jest demonstracją portfolio. **Nie** zawiera aktywnej
> integracji harmonogramu. Jego "dowodem życia" jest zadanie CI uruchamiające demo
> offline na fixtures.

## Najlepiej działa jako rutyna Claude Code

Pipeline jest zaprojektowany do pracy bez nadzoru, na harmonogramie - na przykład jako
rutyna [Claude Code](https://www.anthropic.com/claude-code), która odpala się codziennie,
odświeża digest i wypycha go z powrotem do repozytorium i/lub publikuje na Slacku.

**Przykładowy prompt rutyny:**

```text
Połącz się z repozytorium.

Uruchom: python orchestrator.py --dry-run
Zacommituj i wypchnij zaktualizowany raport:
  git add DIGEST.md
  git commit -m "chore: aktualizacja kalendarza imprez (routine)"
  git push
Jeśli orchestrator zwróci kod != 0, napisz krótko które źródło padło
(z reports/run-*.json).
```

**Środowisko rutyny:**

- **Setup script** (instaluje zależności po nazwie, zanim agent wystartuje):
  ```bash
  pip install httpx beautifulsoup4 python-dateutil pyyaml firecrawl-py
  ```
- **Zmienne środowiskowe:** `FIRECRAWL_API_KEY` dla źródeł renderowanych JS; opcjonalnie
  `SLACK_BOT_TOKEN` dla dostarczania na Slacka. Sekrety trzymaj w bezpiecznym magazynie
  sekretów - nigdy w promptcie, konfiguracji źródeł ani commitowanych plikach.
- **Konektory:** Slack, jeśli chcesz dostarczać digest na kanał.

Żeby dostarczać na Slacka zamiast (lub oprócz) commitowania `DIGEST.md`, zrzuć
`--dry-run`, a run dostarczy digest. Włączaj tylko źródła, do których masz uprawnienia -
patrz [Odpowiedzialne użycie](#odpowiedzialne-użycie).

## Scraping na żywo (opcjonalny)

Scraper jest w pełni funkcjonalny. Zewnętrzne źródła są po prostu **domyślnie wyłączone**
w [`config/sources.yaml`](config/sources.yaml) (`enabled: false`). Żeby uruchomić na żywo:

1. Włącz tylko źródła, do których masz uprawnienia.
2. Dla źródeł renderowanych JS podaj `FIRECRAWL_API_KEY` (patrz `.env.example`).
3. Uruchom `python orchestrator.py --dry-run` (buduje bez dostarczania) albo zrzuć
   `--dry-run`, żeby dostarczyć.

Najpierw przeczytaj [`docs/responsible-use.md`](docs/responsible-use.md) - to Ty
odpowiadasz za regulamin, `robots.txt` i licencjonowanie danych każdego źródła.

## Konfiguracja

| Plik | Co ustawiasz |
|---|---|
| `config/sources.yaml` | Rejestr źródeł: metoda (python/firecrawl), strumienie, `enabled`, fallback |
| `config/filters.yaml` | Okna czasowe, capy, budżet Firecrawl, słowa kluczowe i wykluczenia |
| `.env` (z `.env.example`) | Opcjonalny `FIRECRAWL_API_KEY`, opcjonalny `SLACK_BOT_TOKEN` |

Domyślne okno to 14 dni. Koncerty world-class (`national_scope`) mają dłuższe okno
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

To repozytorium demonstruje pipeline przetwarzania wydarzeń i domyślnie działa offline
na przykładowych fixtures. Zewnętrzne źródła są domyślnie wyłączone. To Ty odpowiadasz
za weryfikację regulaminów źródeł, reguł `robots.txt` i obowiązujących licencji danych
przed włączeniem scrapowania na żywo. Szczegóły:
[`docs/responsible-use.md`](docs/responsible-use.md).

## Licencja

MIT - patrz [`LICENSE`](LICENSE).
