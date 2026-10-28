"""Päällekkäisyystarkistus: allow/ei_laskennassa vs deny, positiivinen ja negatiivinen."""

from pathlib import Path

import pytest

from portti.paallekkaisyys import edustaja, leikkaavat, sisaltyy
from portti.policy import lataa_policy
from portti.policy_skeema import PolicyVirhe


def test_edustaja() -> None:
    assert edustaja("docs/**") == "docs/a/b"
    assert edustaja("**/posti/**") == "a/posti/a/b"
    assert edustaja("*.md") == "a.md"
    assert edustaja("Dockerfile*") == "Dockerfilea"


@pytest.mark.parametrize(
    ("sisempi", "ulompi"),
    [
        ("fixtures/henkilot.json", "fixtures/**"),
        ("docs/julkaisu/ohje.md", "docs/**"),
        ("docs/julkaisu/**", "docs/**"),
        ("CLAUDE.md", "*.md"),
        ("palvelin/tests/x.test.ts", "*.test.*"),
        ("docs/**", "docs/**"),
    ],
)
def test_sisaltyy(sisempi: str, ulompi: str) -> None:
    assert sisaltyy(sisempi, ulompi) and leikkaavat(ulompi, sisempi)


@pytest.mark.parametrize(
    ("malli_a", "malli_b"),
    [
        ("palvelin/sovellus/**", "docs/**"),
        ("*.md", ".claude/**"),
        ("migrations/**", "fixtures/**"),
        ("wrangler.toml", "*.md"),
    ],
)
def test_ei_leikkaa(malli_a: str, malli_b: str) -> None:
    assert not leikkaavat(malli_a, malli_b)


def kirjoita(polku: Path, teksti: str) -> Path:
    polku.write_text(teksti, encoding="utf-8")
    return polku


def test_pehmea_polku_allow_listalla_kaatuu_ja_nimeaa_korjauksen(tmp_path: Path) -> None:
    repo = kirjoita(tmp_path / "policy.yml",
                    "deny:\n  pehmea:\n    testidata:\n      polut: ['fixtures/henkilot.json']\n")
    with pytest.raises(PolicyVirhe) as virhe:
        lataa_policy(repo)
    viesti = str(virhe.value)
    assert "pehmea/testidata" in viesti and "'fixtures/henkilot.json'" in viesti
    assert "allow-polun 'fixtures/**'" in viesti and "allow.laajenna_paitsi" in viesti
    assert "ei_laskennassa" not in viesti


def test_laajenna_paitsi_korjaa(tmp_path: Path) -> None:
    repo = kirjoita(tmp_path / "policy.yml",
                    "deny:\n  pehmea:\n    testidata:\n      polut: ['fixtures/henkilot.json']\n"
                    "allow:\n  laajenna_paitsi: ['fixtures/henkilot.json']\n")
    policy = lataa_policy(repo)
    assert policy.pehmea[0].nimi == "testidata"


def test_kova_glob_docs_alla_kaatuu(tmp_path: Path) -> None:
    repo = kirjoita(tmp_path / "policy.yml",
                    "deny:\n  kova:\n    rekisteri:\n      polut: ['docs/rekisteri/**']\n")
    with pytest.raises(PolicyVirhe, match="kova/rekisteri"):
        lataa_policy(repo)


def test_poikkeus_globilla_korjaa(tmp_path: Path) -> None:
    repo = kirjoita(tmp_path / "policy.yml",
                    "deny:\n  kova:\n    rekisteri:\n      polut: ['docs/rekisteri/**', 'docs/paatokset.md']\n"
                    "allow:\n  laajenna_paitsi: ['docs/rekisteri/**', 'docs/paatokset.md']\n")
    assert lataa_policy(repo).kova[-1].nimi == "rekisteri"


def test_ei_laskennassa_leikkaus_sallitaan(tmp_path: Path) -> None:
    """Generoitu tiedosto saa olla deny-kansiossa: se ei lasketa, mutta deny osuu silti."""
    repo = kirjoita(tmp_path / "policy.yml",
                    "deny:\n  pehmea:\n    avustaja:\n      polut: ['palvelin/avustaja/**']\n"
                    "generoidut: ['palvelin/avustaja/tietopohja.gen.ts']\n")
    policy = lataa_policy(repo)
    assert "palvelin/avustaja/tietopohja.gen.ts" in policy.ei_laskennassa.polut


def test_deny_koodipolku_ei_leikkaa(tmp_path: Path) -> None:
    repo = kirjoita(tmp_path / "policy.yml",
                    "deny:\n  pehmea:\n    palvelin:\n      polut: ['palvelin/sovellus/**', 'wrangler.toml']\n")
    assert lataa_policy(repo).pehmea[0].nimi == "palvelin"


def test_oletuspolicy_lapaisee() -> None:
    policy = lataa_policy(None)
    assert "CLAUDE.md" in policy.allow.paitsi and ".claude/**" in policy.allow.paitsi
    assert not any("lock" in malli for malli in policy.ei_laskennassa.polut)
