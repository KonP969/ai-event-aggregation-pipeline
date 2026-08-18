"""Parsowanie dat/TZ (ST-126) + smoke test end-to-end na fixture."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.normalize import WARSAW, parse_dt

W = ZoneInfo("Europe/Warsaw")


def test_parse_iso_dostaje_tz_warsaw():
    dt = parse_dt("2026-06-10 18:00")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.utcoffset() == datetime(2026, 6, 10, tzinfo=WARSAW).utcoffset()


def test_naive_datetime_dostaje_tz():
    dt = parse_dt(datetime(2026, 6, 10, 18, 0))
    assert dt.tzinfo is not None


def test_iso_utc_z_nie_myli_miesiaca_z_dniem():
    # Meetup: '2026-07-03T17:00:00.000Z' MUSI byc 3 lipca, nie 7 marca (regresja dayfirst)
    dt = parse_dt("2026-07-03T17:00:00.000Z")
    assert dt is not None and dt.month == 7 and dt.day == 3


def test_pusty_zwraca_none():
    assert parse_dt(None) is None
    assert parse_dt("") is None


def test_parse_zakres_dat_festiwalu():
    from scrapers.python_sources import _parse_date_range
    assert _parse_date_range("19 - 28 czerwca 2026 Gdynia") == ("2026-06-19", "2026-06-28")
    assert _parse_date_range("25 lipca - 16 sierpnia 2026 Gdansk") == ("2026-07-25", "2026-08-16")
    assert _parse_date_range("13 czerwca - 27 września 2026") == ("2026-06-13", "2026-09-27")


def test_parse_zakres_brak_zwraca_none():
    from scrapers.python_sources import _parse_date_range
    assert _parse_date_range("Sobota, godz. 18:00") == (None, None)


def test_fixture_relative_start_is_resolved_against_reference_date(tmp_path):
    from scrapers.fixture_source import load_fixture

    fixture = tmp_path / "relative.json"
    fixture.write_text(json.dumps([{
        "title": "Future meetup",
        "start_offset_days": 5,
        "start_time": "18:30",
    }]), encoding="utf-8")

    events = load_fixture(fixture, reference_now=datetime(2030, 1, 10, 12, tzinfo=W))
    assert events[0]["start"] == "2030-01-15 18:30"


def test_sample_fixture_remains_upcoming_for_any_reference_date():
    from scrapers.fixture_source import load_fixture

    reference = datetime(2030, 1, 10, 12, tzinfo=W)
    events = load_fixture("fixtures/sample_events.json", reference_now=reference)
    starts = [datetime.strptime(event["start"], "%Y-%m-%d %H:%M") for event in events]
    assert min(starts).date() > reference.date()


def test_e2e_fixture_wyklucza_mecz_i_buduje_digest(tmp_path):
    """Pelny pipeline na fixture: mecz znika, Sting ma marker ogolnopolski."""
    from orchestrator import main
    db = tmp_path / "e2e.db"
    report_dir = tmp_path / "reports"
    rc = main([
        "--fixtures", "fixtures/sample_events.json",
        "--dry-run",
        "--db", str(db),
        "--report-dir", str(report_dir),
    ])
    assert rc == 0
    digests = list(report_dir.glob("digest-*.md"))
    assert digests, "powinien powstac digest"
    text = digests[0].read_text(encoding="utf-8")
    assert "Mecz" not in text                 # ST-114: mecz wykluczony
    assert "Sting" in text                     # koncert world-class zachowany
    assert "\U0001F30D" in text                # marker ogolnopolski przy Stingu


def test_e2e_fixture_as_of_uses_reference_time_in_filter_and_digest(tmp_path):
    """Jawna data referencyjna musi sterowac calym runem, nie tylko filtrem."""
    from orchestrator import main

    report_dir = tmp_path / "reports"
    rc = main([
        "--fixtures", "fixtures/sample_events.json",
        "--dry-run",
        "--as-of", "2026-06-05",
        "--db", str(tmp_path / "as-of.db"),
        "--report-dir", str(report_dir),
    ])

    assert rc == 0
    text = next(report_dir.glob("digest-*.md")).read_text(encoding="utf-8")
    assert "_run 2026-06-05 00:00_" in text
    assert "Data Science Summit 2026" in text
    assert "Fri 12 Jun 09:00" in text
