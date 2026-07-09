"""Wspolny setup pytest: sciezka do roota + zaladowany config + ustalony 'teraz'."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

WARSAW = ZoneInfo("Europe/Warsaw")


@pytest.fixture
def cfg():
    return yaml.safe_load((ROOT / "config" / "filters.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def now():
    return datetime(2026, 6, 5, 12, 0, tzinfo=WARSAW)
