"""Regressiotapaukset: portin, ohjauksen ja kortti-ajon työnkulut ovat kova-kategoriaa oletuspolicyssä."""

from pathlib import Path

import pytest

from portti.luokittelu import luokittele
from portti.policy import lataa_policy
from portti.verdict import laske_verdict
from tests.apu_git import perusrepo


@pytest.mark.parametrize(
    "polku, kategoria",
    [
        (".github/workflows/portti.yml", "portti_itse"),
        (".github/workflows/portti-ohjaus.yml", "portti_itse"),
        (".github/workflows/kortti-ajo.yml", "portti_itse"),
        (".portti/policy.yml", "portti_itse"),
        (".portti/saannot.md", "portti_itse"),
        (".github/workflows/ohjaus.yml", "ci"),
        (".github/workflows/testit.yml", "ci"),
    ],
)
def test_portin_omat_polut_ovat_kovia(tmp_path: Path, polku: str, kategoria: str) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita(polku, "name: keksitty\n")
    head = repo.commit("portin tiedosto")
    luokitus = luokittele(repo.juuri, base, head, lataa_policy(None))
    osumat = {(osuma.taso, osuma.kategoria) for osuma in luokitus.deny_osumat if osuma.polku == polku}
    assert ("kova", kategoria) in osumat
    assert laske_verdict(luokitus).verdict == "KOVA"


def test_kuluttajan_ohjaus_ja_kortti_ajo_eivat_ole_vapaita_edes_pelkkina(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita(".github/workflows/portti-ohjaus.yml", "name: Portti-ohjaus\n")
    repo.kirjoita(".github/workflows/kortti-ajo.yml", "name: Kortti-ajo\n")
    head = repo.commit("ohjaus ja kortti-ajo")
    verdict = laske_verdict(luokittele(repo.juuri, base, head, lataa_policy(None)))
    assert verdict.verdict == "KOVA" and verdict.hyvaksyttavissa_portaalla == []
