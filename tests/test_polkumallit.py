"""Polkumallien vastaavuus keksityillä poluilla."""

import pytest

from portti.polkumallit import PolkuSaanto, ensimmainen_osuma, saanto_osuu, vastaa


@pytest.mark.parametrize(
    ("polku", "malli"),
    [
        ("CLAUDE.md", "CLAUDE.md"),
        ("alihakemisto/CLAUDE.md", "CLAUDE.md"),
        (".claude/asetukset.json", ".claude/**"),
        (".claude/syva/polku/x.md", ".claude/**"),
        ("docs/ohje.md", "docs/**"),
        ("docs/specs/vaatimus.md", "docs/specs/**"),
        ("README.md", "README*"),
        ("palvelu/README-dev.md", "README*"),
        ("Dockerfile.prod", "Dockerfile*"),
        ("docker-compose.override.yml", "docker-compose*"),
        ("requirements-dev.txt", "requirements*.txt"),
        ("backend/requirements.lock", "requirements*.lock"),
        ("posti/laheta.py", "**/posti/**"),
        ("src/posti/jono.py", "**/posti/**"),
        ("src/laheta_kaikki.py", "**/*laheta*"),
        ("notify_hook.ts", "**/*notify*"),
        ("src/komponentti.test.ts", "*.test.*"),
        ("tests/test_jotain.py", "test_*.py"),
        ("a/b/__snapshots__/kuva.snap", "**/__snapshots__/**"),
        (".github/workflows/portti.yml", ".github/**"),
    ],
)
def test_osuu(polku: str, malli: str) -> None:
    assert vastaa(polku, malli)


@pytest.mark.parametrize(
    ("polku", "malli"),
    [
        ("docs.md", "docs/**"),
        ("dokumentit/docs/x.md", "docs/**"),
        ("src/postitus.py", "**/posti/**"),
        ("src/jono.py", "**/*laheta*"),
        ("tests/apu.py", "test_*.py"),
        ("CLAUDE.md.bak", "CLAUDE.md"),
        ("requirements.txt.old", "requirements*.txt"),
    ],
)
def test_ei_osu(polku: str, malli: str) -> None:
    assert not vastaa(polku, malli)


def test_tyhja_malli_kaatuu() -> None:
    with pytest.raises(ValueError):
        vastaa("x", "  ")


def test_ensimmainen_osuma_palauttaa_mallin() -> None:
    assert ensimmainen_osuma("docs/x.md", ["README*", "docs/**", "*.md"]) == "docs/**"
    assert ensimmainen_osuma("src/x.py", ["README*", "docs/**"]) is None


def test_saanto_paitsi_estaa_osuman() -> None:
    saanto = PolkuSaanto.luo(["docs/**", "*.md"], ["docs/specs/**", "CLAUDE.md"])
    assert saanto_osuu("docs/ohje.md", saanto) == "docs/**"
    assert saanto_osuu("docs/specs/vaatimus.md", saanto) is None
    assert saanto_osuu("CLAUDE.md", saanto) is None
    assert saanto_osuu("src/x.py", saanto) is None
