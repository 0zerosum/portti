"""Komentorivi päästä päähän synteettisellä repolla ja vale-gh:lla."""

import json
from pathlib import Path

import pytest

from portti.cli import main
from portti.kommentti import tunniste

TUNNISTE = tunniste("shadow")
from tests.apu_gh import ValeGh
from tests.apu_git import perusrepo, rivit


def test_arvioi_kirjoittaa_evidencen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("palvelin/sovellus/laskenta/ydin.py", rivit(30) + "lisays\n")
    head = repo.commit()
    evidence_polku = tmp_path / "evidence.json"
    koodi = main([
        "arvioi", "--base", "main", "--head", head, "--repo-polku", str(repo.juuri),
        "--policy", str(tmp_path / "ei-ole.yml"), "--repo", "omistaja/keksitty", "--pr", "3",
        "--tekija", "keksitty-tunnus", "--evidence", str(evidence_polku),
    ])
    assert koodi == 0
    evidence = json.loads(evidence_polku.read_text(encoding="utf-8"))
    assert evidence["verdict"] == "VAPAA" and evidence["base_sha"] == base
    assert evidence["head_sha"] == head and evidence["tekija"] == "keksitty-tunnus"
    assert "portti: VAPAA tier=T1a portaat=S1,S2,S3" in capsys.readouterr().err


def test_arvioi_draft_on_puute_ja_tulostaa_jsonin(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    head = repo.commit("tyhja")
    koodi = main(["arvioi", "--base", base, "--head", head, "--repo-polku", str(repo.juuri),
                  "--policy", str(tmp_path / "ei-ole.yml"), "--draft"])
    tuloste = capsys.readouterr()
    assert koodi == 0
    assert json.loads(tuloste.out)["verdict"] == "PUUTE"


def test_enforce_lukee_basesta_eika_esta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.git("checkout", "-q", "main")
    repo.kirjoita(".portti/policy.yml", "invarianttitestit: []\n")
    main_sha = repo.commit("policy")
    repo.haara("pr", main_sha)
    repo.kirjoita("docs/ohje.md", "lisays\n")
    head = repo.commit()
    koodi = main(["arvioi", "--base", main_sha, "--head", head, "--repo-polku", str(repo.juuri), "--tila", "enforce"])
    tuloste = capsys.readouterr()
    assert koodi == 0 and "esto ei toteutettu" in tuloste.err
    evidence = json.loads(tuloste.out)
    assert evidence["tila"] == "enforce" and evidence["policy_lahde"] == "base" and evidence["verdict"] == "VAPAA"


def test_kommentti_komento_luo_kommentin(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("docs/ohje.md", "lisays\n")
    head = repo.commit()
    evidence_polku = tmp_path / "evidence.json"
    main(["arvioi", "--base", base, "--head", head, "--repo-polku", str(repo.juuri),
          "--policy", str(tmp_path / "ei-ole.yml"), "--evidence", str(evidence_polku)])
    vale = ValeGh({"issues/8/comments": []})
    koodi = main([
        "kommentti", "--evidence", str(evidence_polku), "--repo", "omistaja/keksitty", "--pr", "8",
        "--artefakti-url", "https://example.com/artefakti",
    ], api=vale.api())
    assert koodi == 0
    runko = json.loads(vale.kutsut[1][1] or "{}")["body"]
    assert runko.startswith(TUNNISTE) and "**VAPAA**" in runko and "| Tier | T0 |" in runko


def test_tarkista_tapaukset_kaatuu_poikkeamasta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("CLAUDE.md", "muutos\n")
    head = repo.commit()
    yml = tmp_path / "tapaukset.yml"
    yml.write_text(f"tapaukset:\n  - {{nimi: ohjeet, base: {base}, head: {head}, odotettu_verdict: KOVA}}\n", encoding="utf-8")
    assert main(["tarkista-tapaukset", str(yml), "--repo-polku", str(repo.juuri), "--policy", str(tmp_path / "ei-ole.yml")]) == 0
    yml.write_text(f"tapaukset:\n  - {{nimi: ohjeet, base: {base}, head: {head}, odotettu_verdict: VAPAA}}\n", encoding="utf-8")
    assert main(["tarkista-tapaukset", str(yml), "--repo-polku", str(repo.juuri), "--policy", str(tmp_path / "ei-ole.yml")]) == 1
    assert "EROAA ohjeet" in capsys.readouterr().out


def test_shadow_raportti_komento(capsys: pytest.CaptureFixture[str]) -> None:
    vale = ValeGh({"pr list": []})
    assert main(["shadow-raportti", "--repo", "omistaja/keksitty", "--repo", "omistaja/toinen",
                 "--alkaen", "2026-10-01"], api=vale.api()) == 0
    tuloste = capsys.readouterr().out
    assert "omistaja/keksitty, omistaja/toinen" in tuloste and "Suljettuja PR:iä 0" in tuloste
    assert main(["shadow-raportti", "--repo", "omistaja/keksitty", "--alkaen", "2026-10-01", "--json"], api=vale.api()) == 0
    assert json.loads(capsys.readouterr().out)["pudotetut_draftit"] == 0
