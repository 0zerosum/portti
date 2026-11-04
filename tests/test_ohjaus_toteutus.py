"""Päätöksen toteutus vale-gh:lla: labelit, katselmoija, ohjauskommentti ja korjauskierroksen idempotentti käynnistys."""

import json
from typing import Any

import pytest

from portti.kommentti import TUNNISTE_ALKU
from portti.ohjaus_kommentti import TUNNISTE, lue_ohjauksen_konedata, renderoi_ohjaus
from portti.ohjaus_toteutus import Katselmoijat, KorjausAjo, labelin_vari, ratkaise_katselmoija, toteuta
from tests.apu_gh import ValeGh

REPO = "omistaja/keksitty"


def paatos(toimenpide: str = "katselmoitavaksi", lisaa: list[str] | None = None, poista: list[str] | None = None,
           rooli: str | None = "t1", kierros: int | None = None, ohje: str | None = None) -> dict[str, Any]:
    return {
        "paatos_muoto": 1, "moottorin_versio": "0.4.0", "head_sha": "abc123abc123", "toimenpide": toimenpide,
        "lisaa_labelit": lisaa if lisaa is not None else ["katselmoitavaksi", "tier-T0"],
        "poista_labelit": poista or [], "katselmoijan_rooli": rooli, "kierros": kierros, "ohje": ohje,
        "perustelu": "testiperustelu", "agentti": False, "forkki": False, "testit": "success",
    }


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
    luodut = [argumentit[2] for argumentit, _ in vale_gh.kutsut if argumentit[:2] == ["label", "create"]]
    assert luodut == ["katselmoitavaksi", "tier-T0"], "agentti on jo olemassa"
    assert kutsu(vale_gh, "--add-label", "katselmoitavaksi,tier-T0") is not None
    assert kutsu(vale_gh, "--remove-label") is None
    assert kutsu(vale_gh, "--add-reviewer", "keksitty-t1") is not None
    runko = luotu_kommentti(vale_gh)
    assert runko.startswith(TUNNISTE) and "Katselmoija: keksitty-t1 (rooli t1)" in runko
    assert "**katselmoitavaksi**" in runko and "testiperustelu" in runko
    assert any("ohjauskommentti luotu" in toimi for toimi in toimet)


def test_toteuta_ilman_ctoa_ei_pyyda_ja_kommentti_kertoo() -> None:
    vale_gh = vale()
    toteuta(vale_gh.api(), REPO, 7, paatos(rooli="cto", lisaa=["katselmoitavaksi", "kova"]), Katselmoijat(None, None), None)
    assert kutsu(vale_gh, "--add-reviewer") is None
    runko = luotu_kommentti(vale_gh)
    assert "katselmoija ei asetettu (PORTTI_KATSELMOIJA_CTO puuttuu)" in runko and "Katselmoija: ei pyydetty" in runko


def test_toteuta_ei_pyyda_tekijaa_katselmoijaksi() -> None:
    vale_gh = vale(tekija="keksitty-cto")
    toteuta(vale_gh.api(), REPO, 7, paatos(rooli="cto"), Katselmoijat("keksitty-cto", None), None)
    assert kutsu(vale_gh, "--add-reviewer") is None
    assert "on PR:n tekijä" in luotu_kommentti(vale_gh)


def test_toteuta_poistaa_labelit() -> None:
    vale_gh = vale(labelit=["katselmoitavaksi", "kova", "korjattava"])
    toteuta(vale_gh.api(), REPO, 7, paatos("korjattava", ["korjattava"], ["katselmoitavaksi", "kova"], None),
            Katselmoijat("keksitty-cto", None), None)
    assert kutsu(vale_gh, "label", "create") is None
    assert kutsu(vale_gh, "--remove-label", "katselmoitavaksi,kova") is not None
    assert kutsu(vale_gh, "--add-reviewer") is None


def test_korjauskierros_kaynnistaa_kortti_ajon_vain_kerran() -> None:
    korjaus = paatos("korjauskierros", ["korjauskierros-1"], rooli=None, kierros=1, ohje="pienennä")
    ajo = KorjausAjo("kortti-ajo.yml", "kortti-x", "main")
    vale_gh = vale()
    toimet = toteuta(vale_gh.api(), REPO, 7, korjaus, Katselmoijat("keksitty-cto", None), ajo)
    kaynnistys = kutsu(vale_gh, "workflow", "run")
    assert kaynnistys == ["workflow", "run", "kortti-ajo.yml", "--repo", REPO, "--ref", "main",
                          "-f", "korjaa_pr=7", "-f", "kortti=kortti-x"]
    assert any("kortti-ajo käynnistetty" in toimi for toimi in toimet)
    assert "Ohje agentille: pienennä" in luotu_kommentti(vale_gh)
    toistettu = vale(kommentit=[{"id": 3, "body": renderoi_ohjaus(korjaus, None, [])}])
    toteuta(toistettu.api(), REPO, 7, korjaus, Katselmoijat("keksitty-cto", None), ajo)
    assert kutsu(toistettu, "workflow", "run") is None, "sama päätös samalle headille ei käynnistä uudelleen"
    assert kutsu(toistettu, "PATCH") is not None, "kommentti päivittyy paikallaan"


def test_korjauskierros_ilman_kortti_ajoa_ei_kaynnista() -> None:
    vale_gh = vale()
    toteuta(vale_gh.api(), REPO, 7, paatos("korjauskierros", ["korjauskierros-1"], rooli=None, kierros=1),
            Katselmoijat(None, None), None)
    assert kutsu(vale_gh, "workflow", "run") is None
    assert "kortti-ajoa ei ole määritetty" in luotu_kommentti(vale_gh)


def test_uusi_head_kaynnistaa_uuden_kierroksen() -> None:
    vanha = paatos("korjauskierros", ["korjauskierros-1"], rooli=None, kierros=1)
    uusi = dict(vanha, head_sha="def456def456", kierros=2, lisaa_labelit=["korjauskierros-2"])
    vale_gh = vale(kommentit=[{"id": 3, "body": renderoi_ohjaus(vanha, None, [])}])
    toteuta(vale_gh.api(), REPO, 7, uusi, Katselmoijat(None, None), KorjausAjo("kortti-ajo.yml", "kortti-x", "main"))
    assert kutsu(vale_gh, "workflow", "run") is not None


def test_konedata_luetaan_vain_ohjauskommentista() -> None:
    teksti = renderoi_ohjaus(paatos("korjauskierros", ["korjauskierros-1"], rooli=None, kierros=1), None, [])
    assert lue_ohjauksen_konedata(teksti) == {"head_sha": "abc123abc123", "toimenpide": "korjauskierros",
                                              "kierros": 1, "moottorin_versio": "0.4.0"}
    assert lue_ohjauksen_konedata("ihmisen kommentti") is None
    assert lue_ohjauksen_konedata(f"{TUNNISTE_ALKU} -->\n<!-- portti {{}} -->\n") is None


def test_labelin_vari_on_deterministinen() -> None:
    assert labelin_vari("kova") == "b60205" and labelin_vari("tier-T1a") == labelin_vari("tuntematon")
    assert labelin_vari("korjauskierros-2") == labelin_vari("korjattava")
