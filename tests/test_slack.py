"""Formatowanie Slack: konwersja classic mrkdwn -> standard markdown dla MCP + split."""
from delivery.slack import split_for_slack, to_mcp_markdown


def test_link_conversion():
    assert to_mcp_markdown("<https://x.pl|Info>") == "[Info](https://x.pl)"


def test_bold_conversion():
    assert to_mcp_markdown("*Tytul*") == "**Tytul**"


def test_pelna_linia_digestu():
    line = "• *Devoxx 2026* · Wed 17 Jun · <https://crossweb.pl/d|Info>"
    out = to_mcp_markdown(line)
    assert "**Devoxx 2026**" in out
    assert "[Info](https://crossweb.pl/d)" in out
    assert "<" not in out and "|Info" not in out


def test_split_krotki_tekst_jeden_kawalek():
    assert split_for_slack("linia 1\nlinia 2", limit=100) == ["linia 1\nlinia 2"]


def test_split_dlugi_tekst_wiele_kawalkow():
    text = "\n".join(f"wydarzenie numer {i}" for i in range(50))
    chunks = split_for_slack(text, limit=100)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
    # zadna linia nie zostala zgubiona ani rozbita
    assert "\n".join(chunks).count("wydarzenie numer") == 50
