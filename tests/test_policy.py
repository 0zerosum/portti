"""Policyn lataus, yhdistäminen ja skeemavirheet keksityillä policyilla."""

from pathlib import Path

import pytest

from portti.policy import OLETUSPOLICY, lataa_policy, yhdista
from portti.policy_skeema import PolicyVirhe


def kirjoita(polku: Path, teksti: str) -> Path:
    polku.write_text(teksti, encoding="utf-8")
    return polku


def test_oletus_latautuu_ilman_repon_policya() -> None:
    policy = lataa_policy(None)
    nimet = {kategoria.nimi for kategoria in policy.kova}
    assert "portti_itse" in nimet and "agenttiohjeet" in nimet
    assert policy.pehmea == ()
    assert policy.size_gate_max_rivit == 300
    assert [tier.nimi for tier in policy.tiers] == ["T1a", "T1b", "T1c"]
    assert policy.repon_sha is None
    assert len(policy.oletuksen_sha) == 64


def test_puuttuva_repon_policy_ohitetaan(tmp_path: Path) -> None:
    policy = lataa_policy(tmp_path / "ei_ole.yml")
    assert policy.repon_sha is None


def test_repon_lista_korvaa_ja_laajenna_lisaa(tmp_path: Path) -> None:
    repo = kirjoita(
        tmp_path / "policy.yml",
        "deny:\n  kova:\n    ci:\n      polut: ['ci/**']\n"
        "laajenna_kielletyt_uudet_polut: ['**/salainen/**']\n"
        "alueen_maaritys:\n  prefiksit: ['palvelin/sovellus/']\n",
    )
    policy = lataa_policy(repo)
    ci = next(kategoria for kategoria in policy.kova if kategoria.nimi == "ci")
    assert ci.polut == ("ci/**",)
    assert policy.kielletyt_uudet_polut[-1] == "**/salainen/**"
    assert policy.kielletyt_uudet_polut[0] == "**/posti/**"
    assert policy.alueprefiksit == ("palvelin/sovellus/",)
    assert policy.repon_sha is not None


def test_repo_lisaa_pehmean_kategorian_perusteluineen(tmp_path: Path) -> None:
    repo = kirjoita(
        tmp_path / "policy.yml",
        "deny:\n  pehmea:\n    laskutus:\n      polut: ['laskutus/**']\n"
        "      perustelu: 'historiallinen'\n",
    )
    policy = lataa_policy(repo)
    assert policy.pehmea[0].nimi == "laskutus"
    assert policy.pehmea[0].perustelu == "historiallinen"


def test_generoidut_tulevat_ei_laskennassa_listaan(tmp_path: Path) -> None:
    repo = kirjoita(tmp_path / "policy.yml", "generoidut: ['**/*_generoitu.py']\n")
    policy = lataa_policy(repo)
    assert "**/*_generoitu.py" in policy.ei_laskennassa.polut


@pytest.mark.parametrize(
    "teksti",
    [
        "tuntematon_avain: 1\n",
        "deny:\n  kova:\n    ci:\n      polut: ['x']\n      vaara: 1\n",
        "size_gate:\n  max_rivit: 'paljon'\n",
        "kielletyt_uudet_polut: 'ei-lista'\n",
        "laajenna_size_gate: [1]\n",
        "tiers:\n  T1d: {max_rivit: 1, max_tiedostot: 1, max_alueet: 1}\n",
    ],
)
def test_skeemavirhe_kaataa_latauksen(tmp_path: Path, teksti: str) -> None:
    repo = kirjoita(tmp_path / "policy.yml", teksti)
    with pytest.raises(PolicyVirhe):
        lataa_policy(repo)


@pytest.mark.parametrize(
    "teksti",
    [
        "deny:\n  kova:\n    portti_itse:\n      polut: []\n",
        "deny:\n  kova:\n    portti_itse:\n      polut: ['.portti/**']\n",
        "deny:\n  pehmea:\n    portti_itse:\n      polut: ['.portti/**']\n",
    ],
)
def test_portti_itse_korvaus_kaataa_latauksen(tmp_path: Path, teksti: str) -> None:
    repo = kirjoita(tmp_path / "policy.yml", teksti)
    with pytest.raises(PolicyVirhe, match="portti_itse"):
        lataa_policy(repo)


def test_oletus_ilman_portti_itse_kaatuu(tmp_path: Path) -> None:
    teksti = OLETUSPOLICY.read_text(encoding="utf-8").replace("portti_itse:", "muu_nimi:")
    rikki = kirjoita(tmp_path / "oletus.yml", teksti)
    with pytest.raises(PolicyVirhe, match="portti_itse"):
        lataa_policy(None, oletus=rikki)


def test_rikkinainen_yaml_kaatuu(tmp_path: Path) -> None:
    repo = kirjoita(tmp_path / "policy.yml", "deny: [\n")
    with pytest.raises(PolicyVirhe, match="YAML"):
        lataa_policy(repo)


def test_yhdista_ei_muuta_oletusta() -> None:
    oletus = {"a": [1], "b": {"c": [2], "d": 3}}
    tulos = yhdista(oletus, {"laajenna_a": [9], "b": {"c": [7]}})
    assert tulos == {"a": [1, 9], "b": {"c": [7], "d": 3}}
    assert oletus == {"a": [1], "b": {"c": [2], "d": 3}}
