"""Policyn lähde: head vs base synteettisessä repossa, jonka PR muuttaa omaa policyään."""

import json
from pathlib import Path

import pytest

from portti.cli import main
from portti.policy_lahde import PolicyLahdeVirhe, ratkaise_lahde, valmistele_tiedosto
from tests.apu_git import SynteettinenRepo, perusrepo, rivit

PEHMEA_LASKENTA = (
    "deny:\n  pehmea:\n    laskenta:\n      polut: ['palvelin/sovellus/laskenta/**']\n"
    "      perustelu: 'keksitty'\n"
)


def test_ratkaise_lahde() -> None:
    assert ratkaise_lahde("auto", "shadow") == "head"
    assert ratkaise_lahde("auto", "enforce") == "base"
    assert ratkaise_lahde("base", "shadow") == "base"
    assert ratkaise_lahde("head", "enforce") == "head"
    with pytest.raises(PolicyLahdeVirhe):
        ratkaise_lahde("muu", "shadow")
    with pytest.raises(PolicyLahdeVirhe):
        ratkaise_lahde("auto", "tuntematon")


def policy_pr(tmp_path: Path) -> tuple[SynteettinenRepo, str, str]:
    """Base: tyhjä policy. Head: policy lisää pehmeän kategorian ja PR koskee sen polkua."""
    repo, base = perusrepo(tmp_path / "repo")
    repo.git("checkout", "-q", "main")
    repo.kirjoita(".portti/policy.yml", "invarianttitestit: []\n")
    base = repo.commit("policy mainiin")
    repo.haara("policy-muutos", base)
    repo.kirjoita(".portti/policy.yml", PEHMEA_LASKENTA)
    repo.kirjoita("palvelin/sovellus/laskenta/ydin.py", rivit(30) + "lisays\n")
    head = repo.commit("policy ja koodi")
    return repo, base, head


def test_valmistele_head_ja_base(tmp_path: Path) -> None:
    repo, base, head = policy_pr(tmp_path)
    kohde = tmp_path / "lahde"
    head_polku, lahde = valmistele_tiedosto(repo.juuri, base, Path(".portti/policy.yml"), "head", "shadow", kohde)
    assert head_polku == repo.juuri / ".portti/policy.yml" and lahde.merkinta == "head"
    base_polku, lahde = valmistele_tiedosto(repo.juuri, base, Path(".portti/policy.yml"), "auto", "enforce", kohde)
    assert base_polku == kohde / "policy.yml" and lahde.merkinta == "base"
    assert base_polku is not None and base_polku.read_text(encoding="utf-8") == "invarianttitestit: []\n"


def test_base_ilman_policya(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    head = repo.commit("tyhja")
    kohde = tmp_path / "lahde"
    with pytest.raises(PolicyLahdeVirhe, match="enforce"):
        valmistele_tiedosto(repo.juuri, base, Path(".portti/policy.yml"), "auto", "enforce", kohde)
    polku, lahde = valmistele_tiedosto(repo.juuri, base, Path(".portti/policy.yml"), "base", "shadow", kohde)
    assert polku is None and lahde.toteutunut == "head" and "basessa ei" in (lahde.huomautus or "")
    assert lahde.merkinta.startswith("head (")


def arvioi_json(repo: SynteettinenRepo, base: str, head: str, *lisa: str) -> dict:  # type: ignore[type-arg]
    tuloste = repo.juuri.parent / "evidence.json"
    koodi = main(["arvioi", "--base", base, "--head", head, "--repo-polku", str(repo.juuri),
                  "--evidence", str(tuloste), *lisa])
    assert koodi == 0
    return json.loads(tuloste.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_head_ja_base_antavat_eri_verdictin(tmp_path: Path) -> None:
    repo, base, head = policy_pr(tmp_path)
    shadow = arvioi_json(repo, base, head)
    enforce = arvioi_json(repo, base, head, "--tila", "enforce")
    assert shadow["policy_lahde"] == "head" and shadow["verdict"] == "KOVA"
    assert enforce["policy_lahde"] == "base" and enforce["verdict"] == "KOVA"
    shadow_kategoriat = {osuma["kategoria"] for osuma in shadow["luokitus"]["deny_osumat"]}
    enforce_kategoriat = {osuma["kategoria"] for osuma in enforce["luokitus"]["deny_osumat"]}
    assert "laskenta" in shadow_kategoriat and "laskenta" not in enforce_kategoriat
    assert "portti_itse" in shadow_kategoriat and "portti_itse" in enforce_kategoriat
    assert shadow["tila"] == "shadow" and enforce["tila"] == "enforce"


def test_pelkka_koodi_eri_verdict_lahteen_mukaan(tmp_path: Path) -> None:
    """Base-policy ei tunne pehmeää kategoriaa, head-policy tuntee: VAPAA vs PEHMEÄ."""
    repo, base, head = policy_pr(tmp_path)
    repo.git("checkout", "-q", "policy-muutos")
    vain_policy = head
    repo.kirjoita("kayttoliittyma/nakymat/etusivu.ts", rivit(31))
    head2 = repo.commit("koodi")
    repo.kirjoita(".portti/policy.yml", PEHMEA_LASKENTA)
    pehmea_base = repo.git("rev-parse", "HEAD")
    assert pehmea_base == head2
    tulos_head = arvioi_json(repo, vain_policy, head2, "--policy-lahde", "head")
    tulos_base = arvioi_json(repo, base, head2, "--policy-lahde", "base")
    assert tulos_head["verdict"] == "VAPAA" and tulos_head["policy_lahde"] == "head"
    assert tulos_base["policy_lahde"] == "base"


def test_enforce_ilman_base_policya_kaatuu_cli(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    head = repo.commit("tyhja")
    with pytest.raises(PolicyLahdeVirhe):
        main(["arvioi", "--base", base, "--head", head, "--repo-polku", str(repo.juuri), "--tila", "enforce"])


def test_shadow_base_fallback_nakyy_evidencessa(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("docs/ohje.md", "lisays\n")
    head = repo.commit()
    evidence = arvioi_json(repo, base, head, "--policy-lahde", "base")
    assert evidence["policy_lahde"].startswith("head (basessa ei")
    assert evidence["verdict"] == "VAPAA"


def test_tapaukset_basesta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.git("checkout", "-q", "main")
    repo.kirjoita("docs/ohje.md", "lisays\n")
    vapaa = repo.commit("doc")
    repo.kirjoita(".portti/tapaukset.yml",
                  f"tapaukset:\n  - {{nimi: doc, base: {base}, head: {vapaa}, odotettu_verdict: VAPAA}}\n")
    repo.kirjoita(".portti/policy.yml", "invarianttitestit: []\n")
    main_sha = repo.commit("tapaukset mainiin")
    repo.haara("rikkova", main_sha)
    repo.kirjoita(".portti/tapaukset.yml",
                  f"tapaukset:\n  - {{nimi: doc, base: {base}, head: {vapaa}, odotettu_verdict: KOVA}}\n")
    repo.commit("pr muuttaa tapaukset")
    assert main(["tarkista-tapaukset", ".portti/tapaukset.yml", "--repo-polku", str(repo.juuri), "--lahde", "head"]) == 1
    assert main(["tarkista-tapaukset", ".portti/tapaukset.yml", "--repo-polku", str(repo.juuri),
                 "--tila", "enforce", "--base", main_sha]) == 0
    assert "policy ja tapaukset: base" in capsys.readouterr().err
    assert main(["tarkista-tapaukset", ".portti/tapaukset.yml", "--repo-polku", str(repo.juuri), "--lahde", "base"]) == 2
