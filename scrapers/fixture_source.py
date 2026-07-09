"""Zrodlo fixture — wczytuje wydarzenia z pliku JSON. Sluzy do testow i demo
offline (pelny pipeline bez sieci). Plik: lista surowych dictow (kontrakt RawEvent),
kazdy z dodatkowym kluczem 'source' wskazujacym id zrodla.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_fixture(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("events", [])
