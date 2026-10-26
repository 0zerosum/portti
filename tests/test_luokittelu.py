"""Luokittelu keksityillä diffeillä: jokaiselle portille positiivinen ja negatiivinen tapaus."""

from pathlib import Path

import pytest

from portti.luokittelu import Edellytykset, alue, luokittele
from portti.policy import Policy, lataa_policy
from tests.apu_git import SynteettinenRepo, perusrepo, rivit, luo_testitiedosto


@pytest.fixture
def policy(tmp_path: Path) -> Policy:
    repon_policy = tmp_path / "repo-policy.yml"
    repon_policy.write_text(
        "alueen_maaritys:\n  prefiksit: ['palvelin/sovellus/']\n"
        "invarianttitestit: ['tests/test_kanta.py']\n"
        "deny:\n  pehmea:\n    varasto:\n      polut: ['palvelin/sovellus/varasto/**']\n",
        encoding="utf-8",
    )
    return lataa_policy(repon_policy)


def test_alue_prefiksilla_ja_ilman() -> None:
    prefiksit = ("palvelin/sovellus/",)
    assert alue("palvelin/sovellus/laskenta/ydin.py", prefiksit) == "palvelin/sovellus/laskenta"
    assert alue("palvelin/sovellus/asetukset.py", prefiksit) == "palvelin/sovellus"
    assert alue("kayttoliittyma/nakymat/etusivu.ts", prefiksit) == "kayttoliittyma/nakymat"
    assert alue("kayttoliittyma/etusivu.ts", prefiksit) == "kayttoliittyma"
    assert alue("asetukset.py", prefiksit) == "(juuri)"


def test_pieni_koodimuutos_on_t1a_ilman_osumia(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("palvelin/sovellus/laskenta/ydin.py", rivit(30) + "uusi rivi\n")
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    assert luokitus.tier == "T1a"
    assert luokitus.rivit == 1
    assert luokitus.alueet == ["palvelin/sovellus/laskenta"]
    assert luokitus.deny_osumat == [] and luokitus.kielletyt_uudet == []
    assert all(tulos.ok for tulos in luokitus.invariantit)


def test_dokumentaatio_ja_testien_lisays_on_t0(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("docs/ohje.md", "ohje\nlisays\n")
    repo.kirjoita("README.md", "# Keksitty projekti\nlisays\n")
    repo.kirjoita("tests/test_ydin.py", luo_testitiedosto(5))
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    assert luokitus.tier == "T0"
    assert luokitus.substantiiviset == [] and luokitus.rivit == 0
    assert luokitus.testimaara is not None and not luokitus.testimaara.laskee


def test_testien_poisto_pudottaa_t0_sta(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("tests/test_ydin.py", luo_testitiedosto(1))
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    assert luokitus.tier == "T1a"
    assert luokitus.substantiiviset == ["tests/test_ydin.py"]
    assert luokitus.testimaara is not None and luokitus.testimaara.laskee


def test_kova_deny_osuu_agenttiohjeisiin_ja_lukkotiedostoon(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("CLAUDE.md", "uudet ohjeet\n")
    repo.kirjoita("requirements.txt", "pyyaml==6.1\n")
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    kategoriat = sorted(osuma.kategoria for osuma in luokitus.osumat_tasolla("kova"))
    assert kategoriat == ["agenttiohjeet", "lukkotiedostot"]
    assert luokitus.osumat_tasolla("pehmea") == []


def test_kova_deny_osuu_myos_poisnimettyyn_polkuun(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.nimea("CLAUDE.md", "ohjeet/vanhat.md")
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    assert [osuma.polku for osuma in luokitus.osumat_tasolla("kova")] == ["CLAUDE.md"]


def test_pehmea_deny_repon_kategoriasta(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("palvelin/sovellus/varasto/kanta.py", rivit(31))
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    assert [osuma.kategoria for osuma in luokitus.osumat_tasolla("pehmea")] == ["varasto"]
    assert luokitus.osumat_tasolla("kova") == []


def test_kielletty_uusi_polku_vain_lisayksissa(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("palvelin/sovellus/posti/laheta.py", rivit(3))
    repo.kirjoita("palvelin/sovellus/prompts/ohje.txt", "x\n")
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    polut = sorted(polku for polku, _ in luokitus.kielletyt_uudet)
    assert polut == ["palvelin/sovellus/posti/laheta.py", "palvelin/sovellus/prompts/ohje.txt"]
    seuraava = repo.commit("ei muutosta")
    repo.kirjoita("palvelin/sovellus/posti/laheta.py", rivit(4))
    head2 = repo.commit()
    assert luokittele(repo.juuri, seuraava, head2, policy).kielletyt_uudet == []


def test_koko_yli_t1c_on_yli(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    for indeksi in range(11):
        repo.kirjoita(f"palvelin/sovellus/laskenta/osa_{indeksi}.py", rivit(1))
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    assert luokitus.tier == "YLI" and len(luokitus.substantiiviset) == 11


def test_tierit_rivien_ja_alueiden_mukaan(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("palvelin/sovellus/laskenta/ydin.py", rivit(30) + rivit(50, "uusi"))
    repo.kirjoita("kayttoliittyma/nakymat/etusivu.ts", rivit(30) + rivit(10, "uusi"))
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    assert luokitus.tier == "T1b" and luokitus.rivit == 60 and len(luokitus.alueet) == 2
    repo.kirjoita("palvelin/sovellus/varasto/kanta.py", rivit(31))
    head3 = repo.commit()
    assert luokittele(repo.juuri, base, head3, policy).tier == "T1c"


def test_invariantti_rikkoutuu_luokituksessa(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    repo.kirjoita("tests/test_kanta.py", luo_testitiedosto(1))
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    assert [tulos.ok for tulos in luokitus.invariantit] == [False]
    assert luokitus.substantiiviset == ["tests/test_kanta.py"]


def test_edellytykset_tuottavat_puutteet(tmp_path: Path, policy: Policy) -> None:
    repo, base = perusrepo(tmp_path / "repo")
    head = repo.commit("tyhja")
    luokitus = luokittele(repo.juuri, base, head, policy, Edellytykset(draft=True, konflikti=True))
    assert luokitus.puutteet == ["PR on luonnos", "PR on konfliktissa"]
    assert luokitus.tier == "T0" and luokitus.tiedostot == []


def test_vain_public_muutos_ei_ole_t0(tmp_path: Path, policy: Policy) -> None:
    repo = SynteettinenRepo(tmp_path / "repo")
    repo.kirjoita("public/logo.svg", "<svg/>\n")
    base = repo.commit("alku")
    repo.kirjoita("public/logo.svg", "<svg></svg>\n")
    head = repo.commit()
    luokitus = luokittele(repo.juuri, base, head, policy)
    assert luokitus.substantiiviset == [] and luokitus.tier == "T1a"
