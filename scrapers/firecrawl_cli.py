#!/usr/bin/env python3
"""Cienki CLI wokol Firecrawl API (SDK firecrawl-py v4).

Cel: dac agentowi 'researcher' deterministyczne, taniej-tokenowe narzedzie do
wyszukiwania i scrapowania, bez laczenia sie z MCP.

Komendy:
  search  <query> [--limit N] [--include dom,dom] [--exclude dom,dom] [--scrape] [--md]
  scrape  <url> [--no-main] [--timeout MS] [--md]
  map     <url> [--search term] [--limit N] [--md]

Klucz API: czytany z env FIRECRAWL_API_KEY; jesli brak, szukany w CLAUDE.local.md
(linia odkomentowana 'FIRECRAWL_API_KEY=...') w katalogach nadrzednych.

Output: domyslnie JSON na stdout (agent parsuje). --md = czytelny markdown.
Bledy: komunikat na stderr + niezerowy exit code (nigdy nie udajemy sukcesu).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Wymuś UTF-8 na wyjściu. Windows domyślnie używa cp1250 -> scrape treści z emoji
# (np. oficjalne blogi Google) wywala UnicodeEncodeError. To naprawia to u źródła.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

KEY_NAME = "FIRECRAWL_API_KEY"


def load_api_key() -> str:
    """Env ma pierwszenstwo; fallback: CLAUDE.local.md w drzewie nadrzednym."""
    key = os.environ.get(KEY_NAME)
    if key:
        return key.strip()
    here = Path(__file__).resolve()
    pat = re.compile(rf"^\s*{KEY_NAME}\s*=\s*(.+?)\s*$")
    for parent in [here, *here.parents]:
        candidate = parent / "CLAUDE.local.md"
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.lstrip().startswith("#"):
                    continue  # zakomentowany placeholder - pomijamy
                m = pat.match(line)
                if m:
                    val = m.group(1).strip().strip('"').strip("'")
                    if val and not val.startswith("<"):
                        return val
    die(
        f"Brak klucza API. Ustaw env {KEY_NAME} albo dodaj odkomentowana linie "
        f"'{KEY_NAME}=twoj_klucz' do CLAUDE.local.md."
    )


def die(msg: str, code: int = 1) -> "None":
    print(f"[firecrawl_cli] BLAD: {msg}", file=sys.stderr)
    sys.exit(code)


def to_jsonable(obj):
    """Serializacja modeli pydantic v2 (Firecrawl SDK) do czystych struktur."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj


def get_client(api_key: str):
    import warnings
    warnings.filterwarnings("ignore")  # SDK firecrawl emituje UserWarning przy imporcie
    try:
        from firecrawl import Firecrawl
    except ImportError:
        die("Brak SDK. Zainstaluj: pip install firecrawl-py")
    return Firecrawl(api_key=api_key)


def emit(data, as_md: bool, md_render) -> "None":
    if as_md:
        print(md_render(data))
    else:
        print(json.dumps(to_jsonable(data), ensure_ascii=False, indent=2))


# --- renderery markdown (zwiezle, do podgladu dla czlowieka) ---

def _md_search(data) -> str:
    d = to_jsonable(data)
    out = []
    for src in ("web", "news", "images"):
        items = d.get(src) or []
        if not items:
            continue
        out.append(f"## {src} ({len(items)})")
        for it in items:
            title = it.get("title") or it.get("url") or "(bez tytulu)"
            url = it.get("url", "")
            desc = it.get("description") or it.get("snippet") or ""
            out.append(f"- [{title}]({url})\n  {desc}")
    return "\n".join(out) or "(brak wynikow)"


def _md_scrape(data) -> str:
    d = to_jsonable(data)
    meta = d.get("metadata") or {}
    head = f"# {meta.get('title','(bez tytulu)')}\n<{meta.get('sourceURL') or meta.get('url','')}>\n"
    return head + "\n" + (d.get("markdown") or "(brak tresci markdown)")


def _md_map(data) -> str:
    d = to_jsonable(data)
    links = d.get("links") or []
    rows = []
    for l in links:
        if isinstance(l, dict):
            rows.append(f"- {l.get('url','')}  {l.get('title','')}".rstrip())
        else:
            rows.append(f"- {l}")
    return "\n".join(rows) or "(brak linkow)"


def cmd_search(client, args) -> "None":
    kwargs = {"query": args.query, "limit": args.limit}
    if args.include:
        kwargs["include_domains"] = [d.strip() for d in args.include.split(",") if d.strip()]
    if args.exclude:
        kwargs["exclude_domains"] = [d.strip() for d in args.exclude.split(",") if d.strip()]
    if args.scrape:
        from firecrawl.v2.types import ScrapeOptions
        kwargs["scrape_options"] = ScrapeOptions(formats=["markdown"], only_main_content=True)
    try:
        res = client.search(**kwargs)
    except Exception as e:  # noqa: BLE001 - chcemy czytelny komunikat, nie traceback
        die(f"search nieudany: {e}")
    emit(res, args.md, _md_search)


def cmd_scrape(client, args) -> "None":
    kwargs = {"url": args.url, "formats": ["markdown"], "only_main_content": not args.no_main}
    if args.timeout:
        kwargs["timeout"] = args.timeout
    try:
        res = client.scrape(**kwargs)
    except Exception as e:  # noqa: BLE001
        die(f"scrape nieudany: {e}")
    emit(res, args.md, _md_scrape)


def cmd_map(client, args) -> "None":
    kwargs = {"url": args.url, "limit": args.limit}
    if args.search:
        kwargs["search"] = args.search
    try:
        res = client.map(**kwargs)
    except Exception as e:  # noqa: BLE001
        die(f"map nieudany: {e}")
    emit(res, args.md, _md_map)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="firecrawl_cli", description="Firecrawl CLI dla agenta researcher")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="Wyszukiwanie web/news")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--include", help="domeny tylko-te, po przecinku")
    s.add_argument("--exclude", help="domeny wykluczone, po przecinku")
    s.add_argument("--scrape", action="store_true", help="pobierz tez tresc wynikow")
    s.add_argument("--md", action="store_true")
    s.set_defaults(func=cmd_search)

    sc = sub.add_parser("scrape", help="Pobierz pojedynczy URL jako markdown")
    sc.add_argument("url")
    sc.add_argument("--no-main", action="store_true", help="nie ograniczaj do glownej tresci")
    sc.add_argument("--timeout", type=int, help="timeout w ms")
    sc.add_argument("--md", action="store_true")
    sc.set_defaults(func=cmd_scrape)

    m = sub.add_parser("map", help="Zmapuj URL-e z domeny")
    m.add_argument("url")
    m.add_argument("--search", help="filtruj linki po fraze")
    m.add_argument("--limit", type=int, default=50)
    m.add_argument("--md", action="store_true")
    m.set_defaults(func=cmd_map)
    return p


def main(argv=None) -> "None":
    args = build_parser().parse_args(argv)
    client = get_client(load_api_key())
    args.func(client, args)


if __name__ == "__main__":
    main()
