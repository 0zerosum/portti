"""Komennot `ohjaus-edellinen`, `ohjaa` ja `ohjaus-toteuta` päästä päähän: evidence synteettisestä reposta, vale-gh GitHubina."""

import json
from pathlib import Path

import pytest

from portti.cli import main
from portti.ohjaus_kommentti import renderoi_ohjaus
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
    assert main([*perus, "--head", head, "--evidence", str(evidence), "--polut-vajaat"]) == 0
    vajaa = json.loads(capsys.readouterr().out)
    assert vajaa["toimenpide"] == "cto" and "polkujen lista on vajaa" in vajaa["perustelu"]
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
             "--labelit", "agentti,malli-opus", "--haara", "feature/kortti-x"]
    assert main(perus) == 0
    assert json.loads(capsys.readouterr().out)["toimenpide"] == "korjauskierros"
    assert main([*perus, "--forkki"]) == 0
    paatos = json.loads(capsys.readouterr().out)
    assert paatos["toimenpide"] == "cto" and paatos["forkki"] is True and "jumissa" in paatos["lisaa_labelit"]


def test_ohjaus_toteuta_komento(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paatos = {
        "paatos_muoto": 1, "moottorin_versio": "0.4.0", "head_sha": "abc123abc123", "toimenpide": "korjauskierros",
        "lisaa_labelit": ["korjauskierros-1"], "poista_labelit": ["katselmoitavaksi"], "katselmoijan_rooli": None,
        "kierros": 1, "kaynnista_kortti_ajo": True, "kortti": "kortti-x", "alkuperainen_malli": "fable",
        "ohje": "pienennä", "perustelu": "testit epäonnistuivat",
        "agentti": True, "forkki": False,
        "testit": "failure",
    }
    kohde = tmp_path / "paatos.json"
    kohde.write_text(json.dumps(paatos), encoding="utf-8")
    vale = ValeGh({"label list": [], "issues/7/comments": [[]], "pr view": {"author": {"login": "keksitty-tekija"}}})
    koodi = main(["ohjaus-toteuta", "--paatos", str(kohde), "--repo", "omistaja/keksitty", "--pr", "7",
                  "--katselmoija-cto", "keksitty-cto", "--kortti-ajo", "kortti-ajo.yml",
                  "--oletushaara", "paahaara"], api=vale.api())
    assert koodi == 0
    assert ["workflow", "run", "kortti-ajo.yml", "--repo", "omistaja/keksitty", "--ref", "paahaara",
            "-f", "alkuperainen_malli=fable", "-f", "korjaa_pr=7", "-f", "kortti=kortti-x"] in [
        argumentit for argumentit, _ in vale.kutsut]
    virhetuloste = capsys.readouterr().err
    assert "luotu labelit korjauskierros-1" in virhetuloste and "kortti-ajo käynnistetty" in virhetuloste
    kaatuva = ValeGh({"label list": [], "issues/7/comments": [[]], "pr view": {"author": {"login": "keksitty-tekija"}}},
                     {"workflow run": "HTTP 403: Resource not accessible by integration"})
    assert main(["ohjaus-toteuta", "--paatos", str(kohde), "--repo", "omistaja/keksitty", "--pr", "7",
                 "--kortti-ajo", "kortti-ajo.yml"], api=kaatuva.api()) == 1, "käynnistyksen virhe näkyy ajon tuloksessa"
    assert "korjauskierrosta ei voitu käynnistää" in capsys.readouterr().err
    kelvoton = tmp_path / "kelvoton.json"
    kelvoton.write_text('{"paatos_muoto": 9}', encoding="utf-8")
    with pytest.raises(ValueError):
        main(["ohjaus-toteuta", "--paatos", str(kelvoton), "--repo", "omistaja/keksitty", "--pr", "7"], api=vale.api())


def test_ohjaus_edellinen_estaa_saman_kierroksen_kaynnistamisen_kahdesti(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    evidence, head = evidence_tiedosto(tmp_path, "repo")
    polut = polut_tiedosto(tmp_path, POLKU)
    ohjaa = ["ohjaa", "--head", head, "--testit", "failure", "--evidence", str(evidence), "--polut", str(polut),
             "--haara", "feature/kortti-x"]
    assert main([*ohjaa, "--labelit", "agentti,malli-opus"]) == 0
    eka = json.loads(capsys.readouterr().out)
    assert eka["kierros"] == 1 and eka["kaynnista_kortti_ajo"] is True
    kommentit = [{"id": 1, "body": "ihmisen kommentti", "user": {"login": "keksitty-tekija"}},
                 {"id": 2, "body": renderoi_ohjaus(eka, None, []), "user": {"login": "github-actions[bot]"}}]
    vale = ValeGh({"issues/7/comments": [kommentit]})
    edellinen = tmp_path / "edellinen.json"
    assert main(["ohjaus-edellinen", "--repo", "omistaja/keksitty", "--pr", "7", "--kommentoija", "keksitty-botti"],
                api=vale.api()) == 0
    assert capsys.readouterr().out == "null\n", "vain kommentoijan oma ohjauskommentti luetaan"
    assert main(["ohjaus-edellinen", "--repo", "omistaja/keksitty", "--pr", "7", "--tuloste", str(edellinen)], api=vale.api()) == 0
    assert "korjauskierros headille" in capsys.readouterr().err
    assert json.loads(edellinen.read_text(encoding="utf-8")) == {
        "head_sha": head, "toimenpide": "korjauskierros", "kierros": 1, "moottorin_versio": eka["moottorin_versio"],
    }
    assert main([*ohjaa, "--labelit", "agentti,malli-opus,korjauskierros-1", "--edellinen", str(edellinen)]) == 0
    toka = json.loads(capsys.readouterr().out)
    assert toka["kierros"] == 1 and toka["kaynnista_kortti_ajo"] is False and toka["lisaa_labelit"] == ["korjauskierros-1"]


def test_ohjaus_edellinen_ilman_kommenttia_ja_kelvoton_tiedosto(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tyhja = ValeGh({"issues/7/comments": [[]]})
    assert main(["ohjaus-edellinen", "--repo", "omistaja/keksitty", "--pr", "7"], api=tyhja.api()) == 0
    tuloste = capsys.readouterr()
    assert tuloste.out == "null\n" and "ei aiempaa päätöstä" in tuloste.err
    evidence, head = evidence_tiedosto(tmp_path, "repo")
    ohjaa = ["ohjaa", "--head", head, "--testit", "failure", "--evidence", str(evidence),
             "--polut", str(polut_tiedosto(tmp_path, POLKU)), "--labelit", "agentti,malli-opus",
             "--haara", "feature/kortti-x"]
    ei_paatosta = tmp_path / "null.json"
    ei_paatosta.write_text("null\n", encoding="utf-8")
    assert main([*ohjaa, "--edellinen", str(ei_paatosta)]) == 0
    assert json.loads(capsys.readouterr().out)["kaynnista_kortti_ajo"] is True
    with pytest.raises(ValueError, match="tiedostoa ei ole"):
        main([*ohjaa, "--edellinen", str(tmp_path / "puuttuu.json")])
    lista = tmp_path / "lista.json"
    lista.write_text("[1]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON-objekti tai null"):
        main([*ohjaa, "--edellinen", str(lista)])
