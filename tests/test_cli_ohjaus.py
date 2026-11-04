"""Komennot `ohjaa` ja `ohjaus-toteuta` päästä päähän: evidence synteettisestä reposta, vale-gh toteutukseen."""

import json
from pathlib import Path

import pytest

from portti.cli import main
from tests.apu_gh import ValeGh
from tests.apu_git import perusrepo, rivit

POLKU = "palvelin/sovellus/laskenta/ydin.py"


def evidence_tiedosto(tmp_path: Path, nimi: str) -> tuple[Path, str]:
    repo, base = perusrepo(tmp_path / nimi)
    repo.kirjoita(POLKU, rivit(30) + "lisays\n")
    head = repo.commit()
    polku = tmp_path / f"{nimi}.json"
    main(["arvioi", "--base", base, "--head", head, "--repo-polku", str(repo.juuri), "--policy-lahde", "head",
          "--policy", str(tmp_path / "ei-ole.yml"), "--evidence", str(polku)])
    return polku, head


def polut_tiedosto(tmp_path: Path, *polut: str) -> Path:
    tiedosto = tmp_path / "polut.txt"
    tiedosto.write_text("".join(f"{polku}\n" for polku in polut), encoding="utf-8")
    return tiedosto


def test_ohjaa_paatos_on_deterministinen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    evidence, head = evidence_tiedosto(tmp_path, "repo")
    polut = polut_tiedosto(tmp_path, POLKU)
    komento = ["ohjaa", "--head", head, "--testit", "success", "--evidence", str(evidence), "--polut", str(polut),
               "--labelit", "agentti"]
    assert main(komento) == 0
    tuloste = capsys.readouterr()
    paatos = json.loads(tuloste.out)
    assert paatos["toimenpide"] == "katselmoitavaksi" and paatos["katselmoijan_rooli"] == "t1"
    assert paatos["lisaa_labelit"] == ["katselmoitavaksi", "tier-T1a"] and paatos["agentti"] is True
    assert "portti: ohjaus katselmoitavaksi" in tuloste.err
    assert main(komento) == 0 and capsys.readouterr().out == tuloste.out
    assert list(paatos) == sorted(paatos)


def test_ohjaa_fail_closed_tapaukset(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    evidence, head = evidence_tiedosto(tmp_path, "repo")
    polut = polut_tiedosto(tmp_path, POLKU)
    perus = ["ohjaa", "--testit", "success", "--polut", str(polut)]
    assert main([*perus, "--head", "0" * 12, "--evidence", str(evidence)]) == 0
    assert "evidence on headista" in json.loads(capsys.readouterr().out)["perustelu"]
    assert main([*perus, "--head", head, "--evidence", str(tmp_path / "ei.json")]) == 0
    assert "evidence puuttuu (ei.json ei ole)" in json.loads(capsys.readouterr().out)["perustelu"]
    assert main([*perus, "--head", head]) == 0
    assert "evidence puuttuu (ei annettu)" in json.loads(capsys.readouterr().out)["perustelu"]
    kelvoton = tmp_path / "kelvoton.json"
    kelvoton.write_text("{}", encoding="utf-8")
    assert main([*perus, "--head", head, "--evidence", str(kelvoton)]) == 0
    assert "evidence ei kelpaa" in json.loads(capsys.readouterr().out)["perustelu"]
    kohde = tmp_path / "paatos.json"
    polut_kova = polut_tiedosto(tmp_path, POLKU, ".github/workflows/portti.yml")
    assert main(["ohjaa", "--testit", "success", "--head", head, "--evidence", str(evidence), "--polut", str(polut_kova),
                 "--paatos", str(kohde)]) == 0
    paatos = json.loads(kohde.read_text(encoding="utf-8"))
    assert paatos["toimenpide"] == "cto" and paatos["lisaa_labelit"] == ["katselmoitavaksi", "kova"]


def test_ohjaa_forkki_ja_testit_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    evidence, head = evidence_tiedosto(tmp_path, "repo")
    polut = polut_tiedosto(tmp_path, POLKU)
    perus = ["ohjaa", "--head", head, "--testit", "failure", "--evidence", str(evidence), "--polut", str(polut),
             "--labelit", "agentti"]
    assert main(perus) == 0
    assert json.loads(capsys.readouterr().out)["toimenpide"] == "korjauskierros"
    assert main([*perus, "--forkki"]) == 0
    paatos = json.loads(capsys.readouterr().out)
    assert paatos["toimenpide"] == "cto" and paatos["forkki"] is True and "jumissa" in paatos["lisaa_labelit"]


def test_ohjaus_toteuta_komento(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paatos = {
        "paatos_muoto": 1, "moottorin_versio": "0.4.0", "head_sha": "abc123abc123", "toimenpide": "korjauskierros",
        "lisaa_labelit": ["korjauskierros-1"], "poista_labelit": ["katselmoitavaksi"], "katselmoijan_rooli": None,
        "kierros": 1, "ohje": "pienennä", "perustelu": "testit epäonnistuivat", "agentti": True, "forkki": False,
        "testit": "failure",
    }
    kohde = tmp_path / "paatos.json"
    kohde.write_text(json.dumps(paatos), encoding="utf-8")
    vale = ValeGh({"label list": [], "issues/7/comments": [[]], "pr view": {"author": {"login": "keksitty-tekija"}}})
    koodi = main(["ohjaus-toteuta", "--paatos", str(kohde), "--repo", "omistaja/keksitty", "--pr", "7",
                  "--katselmoija-cto", "keksitty-cto", "--kortti-ajo", "kortti-ajo.yml", "--kortti", "kortti-x",
                  "--oletushaara", "paahaara"], api=vale.api())
    assert koodi == 0
    assert ["workflow", "run", "kortti-ajo.yml", "--repo", "omistaja/keksitty", "--ref", "paahaara",
            "-f", "korjaa_pr=7", "-f", "kortti=kortti-x"] in [argumentit for argumentit, _ in vale.kutsut]
    virhetuloste = capsys.readouterr().err
    assert "luotu labelit korjauskierros-1" in virhetuloste and "kortti-ajo käynnistetty" in virhetuloste
    kelvoton = tmp_path / "kelvoton.json"
    kelvoton.write_text('{"paatos_muoto": 9}', encoding="utf-8")
    with pytest.raises(ValueError):
        main(["ohjaus-toteuta", "--paatos", str(kelvoton), "--repo", "omistaja/keksitty", "--pr", "7"], api=vale.api())
