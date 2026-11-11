"""Päätöksen toteutus vale-gh:lla: labelit, katselmoija, ohjauskommentti, korjauskierroksen käynnistys kerran per head
ja virhepolut (käynnistys tai katselmoijapyyntö epäonnistuu)."""

import json
from typing import Any

import pytest

from portti.kommentti import TUNNISTE_ALKU
from portti.ohjaus import OhjausSyote, paata, paatos_sanakirjaksi
from portti.ohjaus_kommentti import OHJAUKSEN_KOMMENTOIJA, TUNNISTE, lue_ohjauksen_konedata, renderoi_ohjaus
from portti.ohjaus_toteutus import (
    Asetukset,
    Katselmoijat,
    KorjausAjo,
    edellinen_paatos,
    labelin_vari,
    ratkaise_katselmoija,
    toteuta,
)
from portti.version import VERSIO
from tests.apu_gh import ValeGh

REPO = "omistaja/keksitty"
HEAD = "abc123abc123"
AJO = KorjausAjo("kortti-ajo.yml", "main")
AGENTTI = ("agentti", "malli-opus")
EI_KATSELMOIJIA = Katselmoijat(None, None)
BOTTI = {"login": OHJAUKSEN_KOMMENTOIJA}
VIERAS = {"login": "keksitty-kommentoija"}


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
         tekija: str = "keksitty-tekija", virheet: dict[str, str] | None = None) -> ValeGh:
    return ValeGh({
        "label list": [{"name": nimi} for nimi in (labelit or ["agentti"])],
        "issues/7/comments": [kommentit or []],
        "pr view": {"author": {"login": tekija}},
    }, virheet)


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
    "rooli, cto, t1, tekija, ehdokkaat, huomautus",
    [
        (None, "keksitty-cto", "keksitty-t1", "", (), None),
        ("t1", "keksitty-cto", "keksitty-t1", "", ("keksitty-t1", "keksitty-cto"), None),
        ("t1", "keksitty-cto", None, "", ("keksitty-cto",), "käytetään CTO:ta"),
        ("cto", "keksitty-cto", "keksitty-t1", "", ("keksitty-cto",), None),
        ("cto", None, "keksitty-t1", "", (), "katselmoija ei asetettu"),
        ("t1", None, None, "", (), "katselmoija ei asetettu"),
        ("t1", "keksitty-cto", "keksitty-t1", "Keksitty-T1", ("keksitty-cto",), "on PR:n tekijä, käytetään CTO:ta"),
        ("t1", "keksitty-cto", "keksitty-t1", "KEKSITTY-CTO", ("keksitty-t1",), None),
        ("cto", "keksitty-cto", None, "keksitty-cto", (), "on PR:n tekijä, pyyntöä ei tehty"),
        ("t1", None, "keksitty-t1", "keksitty-t1", (), "katselmoija ei asetettu"),
    ],
)
def test_ratkaise_katselmoija(rooli: str | None, cto: str | None, t1: str | None, tekija: str,
                              ehdokkaat: tuple[str, ...], huomautus: str | None) -> None:
    valinta = ratkaise_katselmoija(rooli, Katselmoijat(cto, t1), tekija)
    assert valinta.ehdokkaat == ehdokkaat
    if huomautus is None:
        assert valinta.huomautukset == ()
    else:
        assert any(huomautus in rivi for rivi in valinta.huomautukset)


def test_toteuta_katselmoitavaksi_luo_labelit_pyytaa_katselmoijan_ja_kirjoittaa_kommentin() -> None:
    vale_gh = vale()
    tulos = toteuta(vale_gh.api(), REPO, 7, paatos(), Asetukset(Katselmoijat("keksitty-cto", "keksitty-t1"), None))
    luonnit = [argumentit for argumentit, _ in vale_gh.kutsut if argumentit[:2] == ["label", "create"]]
    assert [argumentit[2] for argumentit in luonnit] == ["katselmoitavaksi", "tier-T0"], "agentti on jo olemassa"
    assert all("--force" in argumentit for argumentit in luonnit), "rinnakkainen luonti ei kaada ajoa"
    assert kutsu(vale_gh, "--add-label", "katselmoitavaksi,tier-T0") is not None
    assert kutsu(vale_gh, "--remove-label") is None
    assert kutsu(vale_gh, "--add-reviewer", "keksitty-t1") is not None
    runko = luotu_kommentti(vale_gh)
    assert runko.startswith(TUNNISTE) and "Katselmoija: keksitty-t1 (rooli t1)" in runko
    assert "**katselmoitavaksi**" in runko and "testiperustelu" in runko
    assert any("ohjauskommentti luotu" in toimi for toimi in tulos.toimet) and tulos.virheita is False


def test_toteuta_ilman_ctoa_ei_pyyda_ja_kommentti_kertoo() -> None:
    vale_gh = vale()
    kova = paatos("cto", katselmoijan_rooli="cto", lisaa_labelit=["katselmoitavaksi", "kova"])
    toteuta(vale_gh.api(), REPO, 7, kova, Asetukset(EI_KATSELMOIJIA, None))
    assert kutsu(vale_gh, "--add-reviewer") is None
    runko = luotu_kommentti(vale_gh)
    assert "katselmoija ei asetettu (PORTTI_KATSELMOIJA_CTO puuttuu)" in runko and "Katselmoija: ei pyydetty" in runko


def test_toteuta_ei_pyyda_tekijaa_katselmoijaksi() -> None:
    vale_gh = vale(tekija="keksitty-cto")
    toteuta(vale_gh.api(), REPO, 7, paatos(katselmoijan_rooli="cto"), Asetukset(Katselmoijat("keksitty-cto", None), None))
    assert kutsu(vale_gh, "--add-reviewer") is None
    runko = luotu_kommentti(vale_gh)
    assert "on PR:n tekijä, pyyntöä ei tehty" in runko and "Katselmoija: ei pyydetty" in runko


def test_t1_tekijan_pr_pyytaa_cton_eika_riipu_kirjainkoosta() -> None:
    vale_gh = vale(tekija="Keksitty-T1")
    tulos = toteuta(vale_gh.api(), REPO, 7, paatos(), Asetukset(Katselmoijat("keksitty-cto", "keksitty-t1"), None))
    assert tulos.virheita is False
    assert kutsu(vale_gh, "--add-reviewer", "keksitty-t1") is None, "tekijää ei pyydetä, vaikka kirjainkoko eroaa"
    assert kutsu(vale_gh, "--add-reviewer", "keksitty-cto") is not None
    runko = luotu_kommentti(vale_gh)
    assert "T1-katselmoija keksitty-t1 on PR:n tekijä, käytetään CTO:ta" in runko
    assert "Katselmoija: keksitty-cto (rooli t1)" in runko


def test_katselmoijapyynnon_virhe_kokeilee_ctota_ja_kirjataan() -> None:
    katselmoijat = Asetukset(Katselmoijat("keksitty-cto", "keksitty-t1"), None)
    vale_gh = vale(virheet={"--add-reviewer keksitty-t1": "GraphQL: Could not resolve to a User"})
    tulos = toteuta(vale_gh.api(), REPO, 7, paatos(), katselmoijat)
    assert tulos.virheita is True, "ajo merkitään epäonnistuneeksi, vaikka CTO saatiin pyydettyä"
    assert kutsu(vale_gh, "--add-reviewer", "keksitty-cto") is not None
    runko = luotu_kommentti(vale_gh)
    assert "Katselmoija: keksitty-cto (rooli t1)" in runko
    assert "katselmoijapyyntö epäonnistui (keksitty-t1): GraphQL: Could not resolve to a User" in runko
    kumpikin = vale(virheet={"--add-reviewer": "HTTP 422"})
    assert toteuta(kumpikin.api(), REPO, 7, paatos(), katselmoijat).virheita is True
    assert "Katselmoija: ei pyydetty" in luotu_kommentti(kumpikin), "kommentti kirjoitetaan virheestä huolimatta"


def test_toteuta_poistaa_labelit() -> None:
    vale_gh = vale(labelit=["katselmoitavaksi", "kova", "korjattava"])
    korjattava = paatos("korjattava", lisaa_labelit=["korjattava"], poista_labelit=["katselmoitavaksi", "kova"],
                        katselmoijan_rooli=None)
    toteuta(vale_gh.api(), REPO, 7, korjattava, Asetukset(Katselmoijat("keksitty-cto", None), None))
    assert kutsu(vale_gh, "label", "create") is None
    assert kutsu(vale_gh, "--remove-label", "katselmoitavaksi,kova") is not None
    assert kutsu(vale_gh, "--add-reviewer") is None


def test_korjauskierros_kaynnistaa_kortti_ajon() -> None:
    vale_gh = vale()
    korjaus = korjauspaatos(kaynnista_kortti_ajo=True, ohje="pienennä")
    tulos = toteuta(vale_gh.api(), REPO, 7, korjaus, Asetukset(Katselmoijat("keksitty-cto", None), AJO))
    assert kutsu(vale_gh, "workflow", "run") == ["workflow", "run", "kortti-ajo.yml", "--repo", REPO, "--ref", "main",
                                                 "-f", "alkuperainen_malli=opus", "-f", "korjaa_pr=7",
                                                 "-f", "kortti=kortti-x"]
    assert any("kortti-ajo käynnistetty" in toimi for toimi in tulos.toimet) and tulos.virheita is False
    assert "Ohje agentille: pienennä" in luotu_kommentti(vale_gh)
    assert kutsu(vale_gh, "--add-reviewer") is None, "korjauskierroksessa ei pyydetä katselmoijaa"


def test_jo_kaynnistettu_kierros_ei_kaynnista_kortti_ajoa() -> None:
    vale_gh = vale()
    toteuta(vale_gh.api(), REPO, 7, korjauspaatos(), Asetukset(EI_KATSELMOIJIA, AJO))
    assert kutsu(vale_gh, "workflow", "run") is None
    assert "kierros 1 on jo käynnistetty tälle headille" in luotu_kommentti(vale_gh)


def test_korjauskierros_ilman_kortti_ajoa_tai_tietoja_vie_ctolle() -> None:
    vale_gh = vale()
    tulos = toteuta(vale_gh.api(), REPO, 7, korjauspaatos(kaynnista_kortti_ajo=True), Asetukset(EI_KATSELMOIJIA, None))
    assert kutsu(vale_gh, "workflow", "run") is None and tulos.virheita is True
    runko = luotu_kommentti(vale_gh)
    assert "**CTO:lle**" in runko and "korjauskierrosta ei voitu käynnistää: kortti-ajoa ei ole määritetty" in runko
    ilman_mallia = vale()
    toteuta(ilman_mallia.api(), REPO, 7, korjauspaatos(kaynnista_kortti_ajo=True, alkuperainen_malli=None), Asetukset(EI_KATSELMOIJIA, AJO))
    assert kutsu(ilman_mallia, "workflow", "run") is None
    assert "päätöksestä puuttuu kortti tai alkuperäisen ajon malli" in luotu_kommentti(ilman_mallia)


def test_kaynnistyksen_virhe_vie_prn_ctolle_jumissa() -> None:
    """gh workflow run epäonnistuu: PR ei jää tilaan korjauskierros, vaan CTO saa sen labelilla jumissa."""
    vale_gh = vale(virheet={"workflow run": "HTTP 404: workflow kortti-ajo.yml not found"})
    korjaus = korjauspaatos(kaynnista_kortti_ajo=True, agentti=True)
    tulos = toteuta(vale_gh.api(), REPO, 7, korjaus, Asetukset(Katselmoijat("keksitty-cto", None), AJO))
    assert tulos.virheita is True
    assert kutsu(vale_gh, "--add-label", "korjauskierros-1") is not None, "kierros jää laskuriin, vaikka ajo ei käynnistynyt"
    assert kutsu(vale_gh, "--add-label", "jumissa,katselmoitavaksi") is not None
    assert kutsu(vale_gh, "--add-reviewer", "keksitty-cto") is not None
    runko = luotu_kommentti(vale_gh)
    assert "**CTO:lle**" in runko and "korjauskierrosta ei voitu käynnistää" in runko and "HTTP 404" in runko
    assert lue_ohjauksen_konedata(runko) == {"head_sha": HEAD, "toimenpide": "cto", "kierros": None, "moottorin_versio": VERSIO}


def test_sama_head_kahdesti_kaynnistaa_kortti_ajon_vain_kerran() -> None:
    """Koko kulku kuten työnkulussa: Testit ja Portti valmistuvat erikseen, joten ohjaus ajetaan samalle headille kahdesti."""
    eka = ohjaa(AGENTTI)
    assert eka["kierros"] == 1 and eka["kaynnista_kortti_ajo"] is True
    vale_eka = vale()
    toteuta(vale_eka.api(), REPO, 7, eka, Asetukset(EI_KATSELMOIJIA, AJO))
    assert kutsu(vale_eka, "workflow", "run") is not None
    kommentoitu = vale(kommentit=[{"id": 3, "body": luotu_kommentti(vale_eka), "user": BOTTI}], labelit=[*AGENTTI, "korjauskierros-1"])
    toka = ohjaa((*AGENTTI, "korjauskierros-1"), edellinen_paatos(kommentoitu.api(), REPO, 7))
    assert toka["kierros"] == 1 and toka["kaynnista_kortti_ajo"] is False
    assert toka["lisaa_labelit"] == ["korjauskierros-1"], "kierroslaskuri ei kasva samasta tilasta"
    toteuta(kommentoitu.api(), REPO, 7, toka, Asetukset(EI_KATSELMOIJIA, AJO))
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
    kommentit = [{"id": 1, "body": "ihmisen kommentti", "user": VIERAS}, {"id": 2, "body": portin_kommentti, "user": BOTTI},
                 {"id": 3, "body": teksti, "user": BOTTI}]
    assert edellinen_paatos(vale(kommentit=kommentit).api(), REPO, 7) == odotettu
    assert edellinen_paatos(vale().api(), REPO, 7) is None


def test_vieraan_kirjoittama_ohjauskommentti_ei_ole_edellinen_paatos() -> None:
    """Kuka tahansa voi kirjoittaa kommentin, jossa on ohjauksen tunniste: sitä ei lueta eikä päivitetä."""
    vaarennos = renderoi_ohjaus(korjauspaatos(), None, [])
    rikki = f"{TUNNISTE}\n<!-- ohjaus {{rikki -->\n"
    vieraat = [{"id": 1, "body": rikki, "user": VIERAS}, {"id": 2, "body": vaarennos, "user": VIERAS},
               {"id": 3, "body": vaarennos}]
    assert edellinen_paatos(vale(kommentit=vieraat).api(), REPO, 7) is None
    assert edellinen_paatos(vale(kommentit=vieraat).api(), REPO, 7, "keksitty-kommentoija") == {"kelvoton": True}
    paatos_nyt = ohjaa(AGENTTI, edellinen_paatos(vale(kommentit=vieraat).api(), REPO, 7))
    assert paatos_nyt["kaynnista_kortti_ajo"] is True, "väärennös ei estä korjauskierrosta"
    vale_gh = vale(kommentit=vieraat)
    toteuta(vale_gh.api(), REPO, 7, paatos_nyt, Asetukset(EI_KATSELMOIJIA, AJO))
    assert kutsu(vale_gh, "PATCH") is None, "vieraan kommenttia ei päivitetä"
    assert luotu_kommentti(vale_gh).startswith(TUNNISTE), "ohjaus luo oman kommenttinsa"


@pytest.mark.parametrize("konedata", ["<!-- ohjaus {rikki -->", "<!-- ohjaus [1] -->", "konedatarivi puuttuu"])
def test_oman_kommentin_rikkinainen_konedata_on_kelvoton_eika_kaada(konedata: str) -> None:
    kommentit = [{"id": 1, "body": f"{TUNNISTE}\n{konedata}\n", "user": BOTTI}]
    edellinen = edellinen_paatos(vale(kommentit=kommentit).api(), REPO, 7)
    assert edellinen == {"kelvoton": True}
    paatos_nyt = ohjaa(AGENTTI, edellinen)
    assert paatos_nyt["toimenpide"] == "cto" and paatos_nyt["kaynnista_kortti_ajo"] is False
    assert "edellistä ohjauspäätöstä ei voitu lukea" in paatos_nyt["perustelu"]


def test_labelin_vari_on_deterministinen() -> None:
    assert labelin_vari("kova") == "b60205" and labelin_vari("tier-T1a") == labelin_vari("tuntematon")
    assert labelin_vari("korjauskierros-2") == labelin_vari("korjattava")
