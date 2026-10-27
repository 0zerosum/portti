"""Evidence-JSON: sisältö, determinismi ja lukeminen."""

from pathlib import Path

import pytest

from portti.evidence import Konteksti, evidence_tekstiksi, kirjoita_evidence, lue_evidence, rakenna_evidence
from portti.luokittelu import luokittele
from portti.policy import lataa_policy
from portti.verdict import laske_verdict
from portti.version import VERSIO
from tests.apu_git import perusrepo, rivit


def test_evidence_sisaltaa_faktat_ja_on_deterministinen(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("palvelin/sovellus/laskenta/ydin.py", rivit(30) + "lisays\n")
    repo.kirjoita("CLAUDE.md", "muutos\n")
    head = repo.commit()
    policy = lataa_policy(None)
    luokitus = luokittele(repo.juuri, base, head, policy)
    konteksti = Konteksti("omistaja/keksitty", 7, base, head, "keksitty-tunnus")
    evidence = rakenna_evidence(konteksti, policy, luokitus, laske_verdict(luokitus))
    assert evidence["moottorin_versio"] == VERSIO
    assert evidence["verdict"] == "KOVA" and evidence["luokitus"]["tier"] == "T1b"
    assert evidence["tekija"] == "keksitty-tunnus" and evidence["pr_numero"] == 7
    assert evidence["policy_lahde"] == "head" and evidence["tila"] == "shadow"
    assert evidence["policy"]["oletuksen_sha256"] == policy.oletuksen_sha
    assert {portti["nimi"] for portti in evidence["portit"]} >= {"kova_deny", "koko"}
    assert evidence["luokitus"]["alueet"] == ["(juuri)", "palvelin/sovellus"]
    polut = {tiedosto["polku"]: tiedosto for tiedosto in evidence["luokitus"]["tiedostot"]}
    assert polut["CLAUDE.md"]["substantiivinen"] is True
    teksti = evidence_tekstiksi(evidence)
    toinen = rakenna_evidence(konteksti, policy, luokitus, laske_verdict(luokitus))
    assert evidence_tekstiksi(toinen) == teksti
    assert "@" not in teksti


def test_kirjoita_ja_lue(tmp_path: Path) -> None:
    polku = tmp_path / "evidence.json"
    kirjoita_evidence({"evidence_muoto": 1, "verdict": "VAPAA"}, polku)
    assert lue_evidence(polku)["verdict"] == "VAPAA"


def test_vaara_muoto_kaatuu(tmp_path: Path) -> None:
    polku = tmp_path / "evidence.json"
    polku.write_text('{"evidence_muoto": 99}', encoding="utf-8")
    with pytest.raises(ValueError):
        lue_evidence(polku)
