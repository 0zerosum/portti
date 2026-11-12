"""Komennot `malli` ja `kortin-tila`: tuloste, exit-koodit ja JSONin deterministisyys."""

import json
from pathlib import Path

import pytest

from portti.cli import main


def kortti(tmp_path: Path, *metarivit: str) -> str:
    polku = tmp_path / "kortti-x.md"
    polku.write_text("# Keksitty kortti\n\n" + "".join(f"{rivi}\n" for rivi in metarivit) + "\nKuvaus.\n", encoding="utf-8")
    return str(polku)


def test_malli_tulostaa_tunnisteen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["malli", "--kortti", kortti(tmp_path, "- Tila: hyväksytty")]) == 0
    tuloste = capsys.readouterr()
    assert tuloste.out == "claude-opus-5-5\n" and "lähde: oletus" in tuloste.err
    assert main(["malli", "--kortti", kortti(tmp_path, "- Malli: Fable")]) == 0
    assert capsys.readouterr().out == "claude-fable-5-1\n"
    assert main(["malli", "--kortti", kortti(tmp_path), "--kasin", "fable"]) == 0
    assert capsys.readouterr().out == "claude-fable-5-1\n"
    assert main(["malli", "--kortti", kortti(tmp_path, "- Malli: fable"), "--alkuperainen", "claude-opus-5-5"]) == 0
    assert capsys.readouterr().out == "claude-opus-5-5\n"


def test_malli_json_on_deterministinen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    komento = ["malli", "--kortti", kortti(tmp_path, "- Malli: fable"), "--json"]
    assert main(komento) == 0
    eka = capsys.readouterr().out
    assert main(komento) == 0 and capsys.readouterr().out == eka
    valinta = json.loads(eka)
    assert list(valinta) == sorted(valinta)
    assert valinta["malli"] == "claude-fable-5-1" and valinta["lahde"] == "kortti" and valinta["nimi"] == "fable"
    assert valinta["tarkistajan_malli"] == "claude-opus-5-5"
    assert valinta["sallitut_tunnisteet"] == ["claude-fable-5-1", "claude-opus-5-5"]


@pytest.mark.parametrize(
    "metarivit, liput, syy",
    [((), ["--kasin", "sonnet"], "ei ole sallittu (käsin)"),
     ((), ["--kasin", ""], "malli on tyhjä (käsin)"),
     ((), ["--alkuperainen", "haiku"], "ei ole sallittu (alkuperäinen ajo)"),
     ((), ["--kasin", "opus", "--alkuperainen", "opus"], "korjauskierrokselle"),
     (("- Malli: claude-sonnet-5-5",), [], "ei ole sallittu (kortti)"),
     (("- Malli:",), [], "malli on tyhjä (kortti)"),
     (("- Malli: opus", "- Malli: fable"), [], "2 riviä")],
)
def test_kielletty_malli_palauttaa_1_ja_kirjaa_syyn(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                                    metarivit: tuple[str, ...], liput: list[str], syy: str) -> None:
    assert main(["malli", "--kortti", kortti(tmp_path, *metarivit), *liput]) == 1
    tuloste = capsys.readouterr()
    assert tuloste.out == "", "kielletty arvo ei tulosta mallitunnistetta"
    assert syy in tuloste.err and "ajo ei käynnisty" in tuloste.err


def test_malli_puuttuva_kortti_palauttaa_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["malli", "--kortti", str(tmp_path / "ei-ole.md")]) == 1
    tuloste = capsys.readouterr()
    assert tuloste.out == "" and "ei voi lukea" in tuloste.err


def test_kortin_tila(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    hyvaksytty = kortti(tmp_path, "- Tila: Hyväksytty (CTO)", "- Malli: opus")
    assert main(["kortin-tila", "--kortti", hyvaksytty, "--vaadi", "hyväksytty"]) == 0
    assert capsys.readouterr().out == "hyväksytty\n"
    luonnos = kortti(tmp_path, "- Tila: luonnos")
    assert main(["kortin-tila", "--kortti", luonnos]) == 0 and capsys.readouterr().out == "luonnos\n"
    assert main(["kortin-tila", "--kortti", luonnos, "--vaadi", "hyväksytty"]) == 1
    assert "kortin tila on luonnos, vaaditaan hyväksytty" in capsys.readouterr().err
    assert main(["kortin-tila", "--kortti", kortti(tmp_path), "--vaadi", "hyväksytty"]) == 1
    assert "merkitsemättä" in capsys.readouterr().err
    assert main(["kortin-tila", "--kortti", kortti(tmp_path, "- Tila: hyväksytty", "- Tila: luonnos"), "--vaadi", "hyväksytty"]) == 1
    assert "2 riviä" in capsys.readouterr().err
    assert main(["kortin-tila", "--kortti", str(tmp_path / "ei-ole.md"), "--vaadi", "hyväksytty"]) == 1
