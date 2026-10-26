"""Regressiotapaukset synteettisessä repossa."""

from pathlib import Path

import pytest

from portti.policy import lataa_policy
from portti.tapaukset import TapausVirhe, aja_tapaukset, lue_tapaukset, muotoile_tulokset
from tests.apu_git import perusrepo, rivit


def test_tapaukset_ajetaan_ja_verrataan(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("docs/ohje.md", "ohje\nlisays\n")
    vapaa = repo.commit("dokumentaatio")
    repo.kirjoita("CLAUDE.md", "muutos\n")
    kova = repo.commit("ohjeet")
    yml = tmp_path / "tapaukset.yml"
    yml.write_text(
        "tapaukset:\n"
        f"  - {{nimi: dokumentaatio, base: {base}, head: {vapaa}, odotettu_verdict: VAPAA, odotettu_tier: T0}}\n"
        f"  - {{nimi: ohjeet, base: {base}, head: {kova}, odotettu_verdict: KOVA}}\n"
        f"  - {{nimi: vaarin odotettu, base: {base}, head: {kova}, odotettu_verdict: VAPAA}}\n",
        encoding="utf-8",
    )
    tulokset = aja_tapaukset(repo.juuri, lue_tapaukset(yml), lataa_policy(None))
    assert [tulos.ok for tulos in tulokset] == [True, True, False]
    teksti = muotoile_tulokset(tulokset)
    assert "OK   dokumentaatio" in teksti and "EROAA vaarin odotettu" in teksti


def test_tyhja_tapaustiedosto_on_sallittu(tmp_path: Path) -> None:
    yml = tmp_path / "tapaukset.yml"
    yml.write_text("tapaukset: []\n", encoding="utf-8")
    assert lue_tapaukset(yml) == []


@pytest.mark.parametrize(
    "teksti",
    [
        "muu: 1\n",
        "tapaukset: {a: 1}\n",
        "tapaukset:\n  - {nimi: x, base: a, head: b}\n",
        "tapaukset:\n  - {nimi: x, base: a, head: b, odotettu_verdict: VAPAA, ylimaarainen: 1}\n",
        "tapaukset:\n  - {nimi: x, base: a, head: b, odotettu_verdict: EHKA}\n",
    ],
)
def test_vaara_muoto_kaatuu(tmp_path: Path, teksti: str) -> None:
    yml = tmp_path / "tapaukset.yml"
    yml.write_text(teksti, encoding="utf-8")
    with pytest.raises(TapausVirhe):
        lue_tapaukset(yml)


def test_rivit_apuri_pitaa_maaran() -> None:
    assert rivit(3).count("\n") == 3
