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


def test_base_ilman_policya_antaa_oletuksen_molemmissa_tiloissa(tmp_path: Path) -> None:
    """Headia ei lueta koskaan ilman eksplisiittistä pyyntöä, vaikka headissa olisi policy."""
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita(".portti/policy.yml", PEHMEA_LASKENTA)
    repo.commit("policy vain headissa")
    kohde = tmp_path / "lahde"
    for lahde_arg, tila in (("auto", "enforce"), ("base", "shadow"), ("base", "enforce")):
        polku, lahde = valmistele_tiedosto(repo.juuri, base, Path(".portti/policy.yml"), lahde_arg, tila, kohde)
        assert polku is None and lahde.toteutunut == "oletus"
        assert lahde.merkinta.startswith("oletus (basessa ") and "ei policy.yml-tiedostoa" in lahde.merkinta


def arvioi_json(repo: SynteettinenRepo, base: str, head: str, *lisa: str) -> dict:  # type: ignore[type-arg]
    tuloste = repo.juuri.parent / "evidence.json"
    koodi = main(["arvioi", "--base", base, "--head", head, "--repo-polku", str(repo.juuri),
                  "--evidence", str(tuloste), *lisa])
    assert koodi == 0
    return json.loads(tuloste.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_head_ja_base_antavat_eri_verdictin(tmp_path: Path) -> None:
    repo, base, head = policy_pr(tmp_path)
    oletus = arvioi_json(repo, base, head)
    assert oletus["policy_lahde"] == "base", "oletuslähde on base myös shadow-tilassa"
    shadow = arvioi_json(repo, base, head, "--policy-lahde", "head")
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


def test_ilman_base_policya_arvioidaan_oletuksella_eika_headin_policylla(tmp_path: Path) -> None:
    """PR lisää policyn, joka tekisi docs-muutoksesta pehmeän: oletus ei tunne sitä, kommentti syntyy silti."""
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("docs/ohje.md", "lisays\n")
    repo.kirjoita(".portti/policy.yml",
                  "deny:\n  pehmea:\n    ohjeet:\n      polut: ['docs/**']\nallow:\n  laajenna_paitsi: ['docs/**']\n")
    head = repo.commit()
    for tila in ("enforce", "shadow"):
        evidence = arvioi_json(repo, base, head, "--tila", tila)
        assert evidence["policy_lahde"].startswith("oletus (basessa ") and "ei policy.yml-tiedostoa" in evidence["policy_lahde"]
        kategoriat = {osuma["kategoria"] for osuma in evidence["luokitus"]["deny_osumat"]}
        assert "ohjeet" not in kategoriat and "portti_itse" in kategoriat
    headin = arvioi_json(repo, base, head, "--policy-lahde", "head")
    assert headin["policy_lahde"] == "head"
    assert "ohjeet" in {osuma["kategoria"] for osuma in headin["luokitus"]["deny_osumat"]}


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
    assert "policy: base, tapaukset: base" in capsys.readouterr().err
    assert main(["tarkista-tapaukset", ".portti/tapaukset.yml", "--repo-polku", str(repo.juuri), "--lahde", "base"]) == 2


def test_tapaukset_vain_headissa(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Tapaukset ovat valinnaisia: basesta puuttuva tiedosto ohittaa askeleen molemmissa tiloissa, headia ei lueta."""
    repo, base = perusrepo(tmp_path / "repo")
    repo.git("checkout", "-q", "main")
    repo.kirjoita(".portti/policy.yml", "invarianttitestit: []\n")
    main_sha = repo.commit("policy mainiin")
    repo.haara("lisaa-tapaukset", main_sha)
    repo.kirjoita(".portti/tapaukset.yml",
                  f"tapaukset:\n  - {{nimi: doc, base: {base}, head: {main_sha}, odotettu_verdict: KOVA}}\n")
    repo.commit("pr lisaa tapaukset")
    komento = ["tarkista-tapaukset", ".portti/tapaukset.yml", "--repo-polku", str(repo.juuri), "--base", main_sha]
    for tila in ("enforce", "shadow"):
        assert main([*komento, "--tila", tila]) == 0
        virhe = capsys.readouterr().err
        assert "ohitetaan" in virhe and "policy: base, tapaukset: oletus (basessa " in virhe
        assert "tapausta kunnossa" not in virhe
    assert main([*komento, "--lahde", "head"]) == 0
    assert "1/1 tapausta kunnossa (policy ja tapaukset: head)" in capsys.readouterr().err


KEVENTAVA_POLICY = (
    "deny:\n  pehmea:\n    laskenta:\n      polut: ['palvelin/sovellus/laskenta/arkisto/**']\n"
    "ei_laskennassa:\n  laajenna_polut: ['palvelin/sovellus/laskenta/**']\n"
)


def test_pr_ei_saa_kevyempaa_luokkaa_omalla_policymuutoksellaan(tmp_path: Path) -> None:
    """Invariantti: .portti/** -muutos on KOVA, ja base-luku ei kevene PR:n oman policyn mukaan.

    Base: laskenta on pehmeä ja laskennassa. PR kaventaa pehmeän polun ja siirtää laskennan laskennan
    ulkopuolelle, ja muuttaa samalla 150 riviä laskentaa. Head-luku antaisi T1a ilman pehmeää osumaa.
    """
    repo, base = perusrepo(tmp_path / "repo")
    repo.git("checkout", "-q", "main")
    repo.kirjoita(".portti/policy.yml", PEHMEA_LASKENTA)
    main_sha = repo.commit("pehmea laskenta mainiin")
    repo.haara("keventava", main_sha)
    repo.kirjoita(".portti/policy.yml", KEVENTAVA_POLICY)
    repo.kirjoita("palvelin/sovellus/laskenta/ydin.py", rivit(150))
    head = repo.commit("policy kevenee ja koodi muuttuu")
    head_luku = arvioi_json(repo, main_sha, head, "--policy-lahde", "head")
    base_luku = arvioi_json(repo, main_sha, head, "--policy-lahde", "base")
    assert head_luku["luokitus"]["tier"] == "T1a" and base_luku["luokitus"]["tier"] == "T1c"
    head_kategoriat = {osuma["kategoria"] for osuma in head_luku["luokitus"]["deny_osumat"]}
    base_kategoriat = {osuma["kategoria"] for osuma in base_luku["luokitus"]["deny_osumat"]}
    assert "laskenta" not in head_kategoriat and "laskenta" in base_kategoriat
    assert head_luku["verdict"] == "KOVA" and base_luku["verdict"] == "KOVA"
    assert "portti_itse" in head_kategoriat and "portti_itse" in base_kategoriat
