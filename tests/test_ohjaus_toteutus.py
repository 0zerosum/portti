"""Päätöksen toteutus vale-gh:lla: labelit, katselmoija, ohjauskommentti ja korjauskierroksen käynnistys kerran per head."""

import json
from typing import Any

import pytest

from portti.kommentti import TUNNISTE_ALKU
from portti.ohjaus import OhjausSyote, paata, paatos_sanakirjaksi
from portti.ohjaus_kommentti import TUNNISTE, lue_ohjauksen_konedata, renderoi_ohjaus
from portti.ohjaus_toteutus import (
    Katselmoijat,
    KorjausAjo,
    edellinen_paatos,
    labelin_vari,
    ratkaise_katselmoija,
    toteuta,
)
from tests.apu_gh import ValeGh

REPO = "omistaja/keksitty"
HEAD = "abc123abc123"
AJO = KorjausAjo("kortti-ajo.yml", "main")
AGENTTI = ("agentti", "malli-opus")
EI_KATSELMOIJIA = Katselmoijat(None, None)


def paatos(toimenpide: str = "katselmoitavaksi", **muutokset: Any) -> dict[str, Any]:
    perus: dict[str, Any] = {
        "paatos_muoto": 1, "moottorin_versio": "0.4.0", "head_sha": HEAD, "toimenpide": toimenpide,
        "lisaa_labelit": ["katselmoitavaksi", "tier-T0"], "poista_labelit": [], "katselmoijan_rooli": "t1",
        "kierros": None, "kaynnista_kortti_ajo": False, "kortti": None, "alkuperainen_malli": None, "ohje": None,
        "perustelu": "testiperustelu",
        "agentti": False, "forkki": False, "testit": "success",
    }
    perus.update(muutokset)
    return perus


def korjauspaatos(**muutokset: Any) -> dict[str, Any]:
    perus: dict[str, Any] = {"lisaa_labelit": ["korjauskierros-1"], "katselmoijan_rooli": None, "kierros": 1,
                             "kortti": "kortti-x", "alkuperainen_malli": "opus"}
    perus.update(muutokset)
    return paatos("korjauskierros", **perus)


def ohjaa(labelit: tuple[str, ...], edellinen: dict[str, Any] | None = None, head: str = HEAD) -> dict[str, Any]:
    """Moottorin päätös agentin PR:lle, jonka testit kaatuivat: sama syöte kuin työnkulussa."""
    evidence = {"evidence_muoto": 1, "verdict": "VAPAA", "head_sha": head, "luokitus": {"tier": "T1a", "puutteet": []}}
    syote = OhjausSyote(head, "failure", evidence, ("palvelin/x.py",), labelit, edellinen=edellinen,
                        haara="feature/kortti-x")
    return paatos_sanakirjaksi(syote, paata(syote))


def vale(kommentit: list[dict[str, Any]] | None = None, labelit: list[str] | None = None,
         tekija: str = "keksitty-tekija") -> ValeGh:
    return ValeGh({
        "label list": [{"name": nimi} for nimi in (labelit or ["agentti"])],
        "issues/7/comments": [kommentit or []],
        "pr view": {"author": {"login": tekija}},
    })


def kutsu(vale_gh: ValeGh, *osat: str) -> list[str] | None:
    for argumentit, _ in vale_gh.kutsut:
        if all(osa in argumentit for osa in osat):
            return argumentit
    return None


def luotu_kommentti(vale_gh: ValeGh) -> str:
    for argumentit, syote in vale_gh.kutsut:
        if "POST" in argumentit and syote:
            return str(json.loads(syote)["body"])
    raise AssertionError("kommenttia ei luotu")


@pytest.mark.parametrize(
    "rooli, cto, t1, tunnus, huomautus",
    [
        (None, "keksitty-cto", "keksitty-t1", None, None),
        ("t1", "keksitty-cto", "keksitty-t1", "keksitty-t1", None),
        ("t1", "keksitty-cto", None, "keksitty-cto", "käytetään CTO:ta"),
        ("cto", "keksitty-cto", "keksitty-t1", "keksitty-cto", None),
        ("cto", None, "keksitty-t1", None, "katselmoija ei asetettu"),
        ("t1", None, None, None, "katselmoija ei asetettu"),
    ],
)
def test_ratkaise_katselmoija(rooli: str | None, cto: str | None, t1: str | None, tunnus: str | None,
                              huomautus: str | None) -> None:
    valinta = ratkaise_katselmoija(rooli, Katselmoijat(cto, t1))
    assert valinta.tunnus == tunnus
    if huomautus is None:
        assert valinta.huomautus is None
    else:
        assert valinta.huomautus is not None and huomautus in valinta.huomautus


def test_toteuta_katselmoitavaksi_luo_labelit_pyytaa_katselmoijan_ja_kirjoittaa_kommentin() -> None:
    vale_gh = vale()
    toimet = toteuta(vale_gh.api(), REPO, 7, paatos(), Katselmoijat("keksitty-cto", "keksitty-t1"), None)
    luonnit = [argumentit for argumentit, _ in vale_gh.kutsut if argumentit[:2] == ["label", "create"]]
    assert [argumentit[2] for argumentit in luonnit] == ["katselmoitavaksi", "tier-T0"], "agentti on jo olemassa"
    assert all("--force" in argumentit for argumentit in luonnit), "rinnakkainen luonti ei kaada ajoa"
    assert kutsu(vale_gh, "--add-label", "katselmoitavaksi,tier-T0") is not None
    assert kutsu(vale_gh, "--remove-label") is None
    assert kutsu(vale_gh, "--add-reviewer", "keksitty-t1") is not None
    runko = luotu_kommentti(vale_gh)
    assert runko.startswith(TUNNISTE) and "Katselmoija: keksitty-t1 (rooli t1)" in runko
    assert "**katselmoitavaksi**" in runko and "testiperustelu" in runko
    assert any("ohjauskommentti luotu" in toimi for toimi in toimet)


def test_toteuta_ilman_ctoa_ei_pyyda_ja_kommentti_kertoo() -> None:
    vale_gh = vale()
    kova = paatos("cto", katselmoijan_rooli="cto", lisaa_labelit=["katselmoitavaksi", "kova"])
    toteuta(vale_gh.api(), REPO, 7, kova, EI_KATSELMOIJIA, None)
    assert kutsu(vale_gh, "--add-reviewer") is None
    runko = luotu_kommentti(vale_gh)
    assert "katselmoija ei asetettu (PORTTI_KATSELMOIJA_CTO puuttuu)" in runko and "Katselmoija: ei pyydetty" in runko


def test_toteuta_ei_pyyda_tekijaa_katselmoijaksi() -> None:
    vale_gh = vale(tekija="keksitty-cto")
    toteuta(vale_gh.api(), REPO, 7, paatos(katselmoijan_rooli="cto"), Katselmoijat("keksitty-cto", None), None)
    assert kutsu(vale_gh, "--add-reviewer") is None
    assert "on PR:n tekijä" in luotu_kommentti(vale_gh)


def test_toteuta_poistaa_labelit() -> None:
    vale_gh = vale(labelit=["katselmoitavaksi", "kova", "korjattava"])
    korjattava = paatos("korjattava", lisaa_labelit=["korjattava"], poista_labelit=["katselmoitavaksi", "kova"],
                        katselmoijan_rooli=None)
    toteuta(vale_gh.api(), REPO, 7, korjattava, Katselmoijat("keksitty-cto", None), None)
    assert kutsu(vale_gh, "label", "create") is None
    assert kutsu(vale_gh, "--remove-label", "katselmoitavaksi,kova") is not None
    assert kutsu(vale_gh, "--add-reviewer") is None


def test_korjauskierros_kaynnistaa_kortti_ajon() -> None:
    vale_gh = vale()
    korjaus = korjauspaatos(kaynnista_kortti_ajo=True, ohje="pienennä")
    toimet = toteuta(vale_gh.api(), REPO, 7, korjaus, Katselmoijat("keksitty-cto", None), AJO)
    assert kutsu(vale_gh, "workflow", "run") == ["workflow", "run", "kortti-ajo.yml", "--repo", REPO, "--ref", "main",
                                                 "-f", "alkuperainen_malli=opus", "-f", "korjaa_pr=7",
                                                 "-f", "kortti=kortti-x"]
    assert any("kortti-ajo käynnistetty" in toimi for toimi in toimet)
    assert "Ohje agentille: pienennä" in luotu_kommentti(vale_gh)
    assert kutsu(vale_gh, "--add-reviewer") is None, "korjauskierroksessa ei pyydetä katselmoijaa"


def test_jo_kaynnistettu_kierros_ei_kaynnista_kortti_ajoa() -> None:
    vale_gh = vale()
    toteuta(vale_gh.api(), REPO, 7, korjauspaatos(), EI_KATSELMOIJIA, AJO)
    assert kutsu(vale_gh, "workflow", "run") is None
    assert "kierros 1 on jo käynnistetty tälle headille" in luotu_kommentti(vale_gh)


def test_korjauskierros_ilman_kortti_ajoa_ei_kaynnista() -> None:
    vale_gh = vale()
    toteuta(vale_gh.api(), REPO, 7, korjauspaatos(kaynnista_kortti_ajo=True), EI_KATSELMOIJIA, None)
    assert kutsu(vale_gh, "workflow", "run") is None
    assert "kortti-ajoa ei ole määritetty" in luotu_kommentti(vale_gh)
    ilman_mallia = vale()
    toteuta(ilman_mallia.api(), REPO, 7, korjauspaatos(kaynnista_kortti_ajo=True, alkuperainen_malli=None), EI_KATSELMOIJIA, AJO)
    assert kutsu(ilman_mallia, "workflow", "run") is None
    assert "päätöksestä puuttuu kortti tai alkuperäisen ajon malli" in luotu_kommentti(ilman_mallia)


def test_sama_head_kahdesti_kaynnistaa_kortti_ajon_vain_kerran() -> None:
    """Koko kulku kuten työnkulussa: Testit ja Portti valmistuvat erikseen, joten ohjaus ajetaan samalle headille kahdesti."""
    eka = ohjaa(AGENTTI)
    assert eka["kierros"] == 1 and eka["kaynnista_kortti_ajo"] is True
    vale_eka = vale()
    toteuta(vale_eka.api(), REPO, 7, eka, EI_KATSELMOIJIA, AJO)
    assert kutsu(vale_eka, "workflow", "run") is not None
    kommentoitu = vale(kommentit=[{"id": 3, "body": luotu_kommentti(vale_eka)}], labelit=[*AGENTTI, "korjauskierros-1"])
    toka = ohjaa((*AGENTTI, "korjauskierros-1"), edellinen_paatos(kommentoitu.api(), REPO, 7))
    assert toka["kierros"] == 1 and toka["kaynnista_kortti_ajo"] is False
    assert toka["lisaa_labelit"] == ["korjauskierros-1"], "kierroslaskuri ei kasva samasta tilasta"
    toteuta(kommentoitu.api(), REPO, 7, toka, EI_KATSELMOIJIA, AJO)
    assert kutsu(kommentoitu, "workflow", "run") is None, "sama tila ei käynnistä toista korjauskierrosta"
    assert kutsu(kommentoitu, "PATCH") is not None, "kommentti päivittyy paikallaan"
    uusi_head = ohjaa((*AGENTTI, "korjauskierros-1"), edellinen_paatos(kommentoitu.api(), REPO, 7), head="def456def456")
    assert uusi_head["kierros"] == 2 and uusi_head["kaynnista_kortti_ajo"] is True


def test_edellinen_paatos_luetaan_vain_ohjauskommentista() -> None:
    teksti = renderoi_ohjaus(korjauspaatos(), None, [])
    odotettu = {"head_sha": HEAD, "toimenpide": "korjauskierros", "kierros": 1, "moottorin_versio": "0.4.0"}
    assert lue_ohjauksen_konedata(teksti) == odotettu
    assert lue_ohjauksen_konedata("ihmisen kommentti") is None
    portin_kommentti = f"{TUNNISTE_ALKU} -->\n<!-- portti {{}} -->\n"
    assert lue_ohjauksen_konedata(portin_kommentti) is None
    kommentit = [{"id": 1, "body": "ihmisen kommentti"}, {"id": 2, "body": portin_kommentti}, {"id": 3, "body": teksti}]
    assert edellinen_paatos(vale(kommentit=kommentit).api(), REPO, 7) == odotettu
    assert edellinen_paatos(vale().api(), REPO, 7) is None


def test_labelin_vari_on_deterministinen() -> None:
    assert labelin_vari("kova") == "b60205" and labelin_vari("tier-T1a") == labelin_vari("tuntematon")
    assert labelin_vari("korjauskierros-2") == labelin_vari("korjattava")
