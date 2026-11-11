"""Ohjauspäätöksen toteutus GitHubissa: labelit, korjauskierroksen käynnistys, katselmoijapyyntö ja ohjauskommentti.

Kortti-ajo käynnistetään vain, kun päätös sanoo niin (`kaynnista_kortti_ajo`): moottori päättää sen
edellisestä päätöksestä, jonka `edellinen_paatos` lukee ohjauskommentin konedatasta ennen päätöstä.
Ohjauskommentiksi kelpaa vain ohjauksen oman kirjoittajan kommentti (`Asetukset.kommentoija`): muiden
kommentteja ei lueta eikä päivitetä, vaikka niissä olisi ohjauksen tunniste.

Uudessa korjauskierroksessa ohjauskommentti kirjoitetaan ennen kortti-ajon käynnistystä: kortti-ajo liittää
kommentin agentin promptiin, ja idempotenssi nojaa siihen. Käynnistys on kaksivaiheinen: ennen käynnistystä
kommentin konedatassa on `kaynnistys_kesken`, ja onnistuneen käynnistyksen jälkeen kommentti kirjoitetaan
ilman sitä. Jos jälkimmäinen kirjoitus jää tekemättä, moottori ei oleta kierroksen olevan käynnissä vaan vie
PR:n CTO:lle.

Virhepolut ovat fail-closed. Jos kortti-ajoa ei saada käyntiin, PR viedään CTO:lle labelilla `jumissa`.
Jos katselmoijapyyntö epäonnistuu, pyydetään seuraavaa ehdokasta ja virhe kirjataan kommenttiin. Varapäätöksen
labelien ja PR:n tekijän haun virheet kirjataan, eivätkä ne estä kommenttia. `Toteutus.virheita` kertoo
kutsujalle, että ajo on merkittävä epäonnistuneeksi. Katselmoijien tunnukset tulevat parametreina, eivät reposta.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any

from portti.github_api import GitHubApi
from portti.kommentti import kirjoita_tai_paivita, kommentin_kirjoittaja
from portti.ohjaus import (
    KAYNNISTYS_KESKEN,
    KIERROS_ETULIITE,
    KORJAUSKIERROS,
    LABEL_AGENTTI,
    ROOLI_T1,
    TIER_ETULIITE,
    paatos_keskeytyneelle_ajolle,
)
from portti.ohjaus_kommentti import OHJAUKSEN_KOMMENTOIJA, lue_ohjauksen_konedata, renderoi_ohjaus

LABELIEN_VARIT = {
    "katselmoitavaksi": "0e8a16",
    "kova": "b60205",
    "jumissa": "b60205",
    "korjattava": "fbca04",
    "liian-iso": "d93f0b",
    LABEL_AGENTTI: "5319e7",
}
OLETUSVARI = "c5def5"
GH_VIRHEEN_PITUUS = 200


@dataclass(frozen=True)
class Katselmoijat:
    cto: str | None
    t1: str | None


@dataclass(frozen=True)
class KatselmoijaValinta:
    """Katselmoijaehdokkaat pyyntöjärjestyksessä ja huomautukset siitä, miksi jotakuta ei pyydetä."""

    ehdokkaat: tuple[str, ...]
    huomautukset: tuple[str, ...]


@dataclass(frozen=True)
class KorjausAjo:
    """Kuluttajan kortti-ajon työnkulkutiedosto ja haara, jolta se käynnistetään (oletushaara)."""

    tyonkulku: str
    haara: str


@dataclass(frozen=True)
class Asetukset:
    """Toteutuksen ympäristö: katselmoijat, korjauskierroksen kortti-ajo ja ohjauskommentin kirjoittaja."""

    katselmoijat: Katselmoijat
    korjausajo: KorjausAjo | None
    kommentoija: str = OHJAUKSEN_KOMMENTOIJA


@dataclass(frozen=True)
class Toteutus:
    """Tehdyt toimet lokiriveinä ja tieto siitä, epäonnistuiko jokin (ajo merkitään epäonnistuneeksi)."""

    toimet: tuple[str, ...]
    virheita: bool


@dataclass(frozen=True)
class _Kaynnistys:
    huomautus: str | None
    virhe: str | None


@dataclass(frozen=True)
class _Pyynto:
    tunnus: str | None
    virheet: tuple[str, ...]


def _este(tunnus: str | None, tekija: str, muuttuja: str) -> str | None:
    """Syy, miksi tunnusta ei voi pyytää katselmoijaksi, tai None. Tunnukset eivät riipu kirjainkoosta."""
    if not tunnus:
        return f"ei asetettu ({muuttuja} puuttuu)"
    if tunnus.casefold() == tekija.casefold():
        return f"{tunnus} on PR:n tekijä"
    return None


def ratkaise_katselmoija(rooli: str | None, katselmoijat: Katselmoijat, tekija: str = "") -> KatselmoijaValinta:
    """T1-roolille T1 ja varalla CTO, CTO-roolille CTO. Puuttuvaa tunnusta ja PR:n tekijää ei pyydetä."""
    if rooli is None:
        return KatselmoijaValinta((), ())
    ehdokkaat: list[str] = []
    huomautukset: list[str] = []
    cto_este = _este(katselmoijat.cto, tekija, "PORTTI_KATSELMOIJA_CTO")
    if rooli == ROOLI_T1:
        t1_este = _este(katselmoijat.t1, tekija, "PORTTI_KATSELMOIJA_T1")
        if t1_este is None:
            ehdokkaat.append(str(katselmoijat.t1))
        else:
            huomautukset.append(f"T1-katselmoija {t1_este}" + (", käytetään CTO:ta" if cto_este is None else ""))
    if cto_este is None:
        ehdokkaat.append(str(katselmoijat.cto))
    elif not ehdokkaat:
        huomautukset.append(f"katselmoija {cto_este}, pyyntöä ei tehty")
    return KatselmoijaValinta(tuple(ehdokkaat), tuple(huomautukset))


def labelin_vari(label: str) -> str:
    if label.startswith(TIER_ETULIITE):
        return OLETUSVARI
    if label.startswith(KIERROS_ETULIITE):
        return LABELIEN_VARIT["korjattava"]
    return LABELIEN_VARIT.get(label, OLETUSVARI)


def edellinen_paatos(
    api: GitHubApi, repo: str, pr_numero: int, kommentoija: str = OHJAUKSEN_KOMMENTOIJA
) -> dict[str, Any] | None:
    """PR:n ohjauskommentin konedata (head, toimenpide, kierros) tai None, jos ohjaus ei ole vielä kommentoinut.

    Vain kommentoijan oma kommentti luetaan: muu kommentoija ei voi väärentää edellistä päätöstä.
    """
    for kommentti in api.hae_kommentit(repo, pr_numero):
        if kommentin_kirjoittaja(kommentti) != kommentoija:
            continue
        konedata = lue_ohjauksen_konedata(str(kommentti.get("body", "")))
        if konedata is not None:
            return konedata
    return None


def _gh_virhe(virhe: subprocess.CalledProcessError) -> str:
    """gh:n virheilmoituksen viimeinen rivi lyhennettynä."""
    rivit = [rivi.strip() for rivi in str(virhe.stderr or "").splitlines() if rivi.strip()]
    return (rivit[-1] if rivit else f"gh palautti koodin {virhe.returncode}")[:GH_VIRHEEN_PITUUS]


def _varmista_labelit(api: GitHubApi, repo: str, labelit: list[str]) -> list[str]:
    olemassa = set(api.hae_labelit(repo))
    luodut = [label for label in labelit if label not in olemassa]
    for label in luodut:
        api.luo_label(repo, label, labelin_vari(label), "portti-ohjaus")
    return luodut


def _paivita_labelit(api: GitHubApi, repo: str, pr_numero: int, paatos: dict[str, Any]) -> list[str]:
    lisaa = [str(label) for label in paatos["lisaa_labelit"]]
    poista = [str(label) for label in paatos["poista_labelit"]]
    toimet = []
    luodut = _varmista_labelit(api, repo, lisaa)
    if luodut:
        toimet.append(f"luotu labelit {', '.join(luodut)}")
    if lisaa:
        api.lisaa_labelit(repo, pr_numero, lisaa)
        toimet.append(f"lisätty labelit {', '.join(lisaa)}")
    if poista:
        api.poista_labelit(repo, pr_numero, poista)
        toimet.append(f"poistettu labelit {', '.join(poista)}")
    return toimet


def _kaynnista_korjaus(
    api: GitHubApi, repo: str, pr_numero: int, paatos: dict[str, Any], asetukset: Asetukset
) -> _Kaynnistys:
    """Uusi korjauskierros: ohjauskommentti ensin, sitten kortti-ajon käynnistys.

    Virhe tarkoittaa, ettei ajoa saatu käyntiin. Jo käynnistettyä kierrosta ei käynnistetä uudelleen.
    """
    if paatos["toimenpide"] != KORJAUSKIERROS:
        return _Kaynnistys(None, None)
    kierros = paatos.get("kierros")
    if not paatos.get("kaynnista_kortti_ajo"):
        return _Kaynnistys(f"kortti-ajoa ei käynnistetty uudelleen: kierros {kierros} on jo käynnistetty tälle headille", None)
    korjausajo = asetukset.korjausajo
    if korjausajo is None:
        return _Kaynnistys(None, "kortti-ajoa ei ole määritetty")
    kortti, malli = paatos.get("kortti"), paatos.get("alkuperainen_malli")
    if not kortti or not malli:
        return _Kaynnistys(None, "päätöksestä puuttuu kortti tai alkuperäisen ajon malli")
    huomautus = f"kortti-ajon käynnistys: {korjausajo.tyonkulku}, kortti {kortti}, malli {malli}, kierros {kierros}"
    syotteet = {"kortti": str(kortti), "korjaa_pr": str(pr_numero), "alkuperainen_malli": str(malli)}
    kesken = renderoi_ohjaus({**paatos, KAYNNISTYS_KESKEN: True}, None, [huomautus])
    try:
        kirjoita_tai_paivita(api, repo, pr_numero, kesken, asetukset.kommentoija)
    except subprocess.CalledProcessError as virhe:
        return _Kaynnistys(None, f"ohjauskommentin kirjoitus ennen käynnistystä epäonnistui ({_gh_virhe(virhe)})")
    try:
        api.kaynnista_tyonkulku(repo, korjausajo.tyonkulku, korjausajo.haara, syotteet)
    except subprocess.CalledProcessError as virhe:
        return _Kaynnistys(None, f"työnkulun {korjausajo.tyonkulku} käynnistys epäonnistui ({_gh_virhe(virhe)})")
    return _Kaynnistys(huomautus, None)


def _jumissa_paatos(paatos: dict[str, Any], virhe: str) -> dict[str, Any]:
    """Korjauskierrosta ei saatu käyntiin: sama PR viedään CTO:lle. Kierroslabel jää laskuriin."""
    labelit = (*(str(label) for label in paatos["lisaa_labelit"]), *((LABEL_AGENTTI,) if paatos.get("agentti") else ()))
    syy = f"{paatos['perustelu']}; korjauskierrosta ei voitu käynnistää: {virhe}"
    return paatos_keskeytyneelle_ajolle(str(paatos["head_sha"]), labelit, syy)


def _varapaatoksen_labelit(api: GitHubApi, repo: str, pr_numero: int, paatos: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Varapäätöksen labelit: tehdyt toimet ja virheet. Virhe kirjataan, jotta ohjauskommentti ehditään kirjoittaa."""
    try:
        return _paivita_labelit(api, repo, pr_numero, paatos), []
    except subprocess.CalledProcessError as virhe:
        return [], [f"labelien päivitys epäonnistui: {_gh_virhe(virhe)}"]


def _pyyda_katselmoija(api: GitHubApi, repo: str, pr_numero: int, ehdokkaat: tuple[str, ...]) -> _Pyynto:
    """Pyytää ensimmäisen ehdokkaan, jolle pyyntö onnistuu; epäonnistuneet pyynnöt palautetaan virheinä."""
    virheet: list[str] = []
    for tunnus in ehdokkaat:
        try:
            api.pyyda_katselmoija(repo, pr_numero, tunnus)
        except subprocess.CalledProcessError as virhe:
            virheet.append(f"katselmoijapyyntö epäonnistui ({tunnus}): {_gh_virhe(virhe)}")
            continue
        return _Pyynto(tunnus, tuple(virheet))
    return _Pyynto(None, tuple(virheet))


def _katselmointi(
    api: GitHubApi, repo: str, pr_numero: int, paatos: dict[str, Any], katselmoijat: Katselmoijat
) -> tuple[KatselmoijaValinta, _Pyynto]:
    rooli = paatos.get("katselmoijan_rooli")
    if rooli is None:
        return KatselmoijaValinta((), ()), _Pyynto(None, ())
    try:
        tekija = str(api.hae_pr(repo, pr_numero).get("author", {}).get("login", ""))
    except subprocess.CalledProcessError as virhe:
        return KatselmoijaValinta((), ()), _Pyynto(None, (f"PR:n tekijää ei saatu, katselmoijaa ei pyydetty: {_gh_virhe(virhe)}",))
    valinta = ratkaise_katselmoija(str(rooli), katselmoijat, tekija)
    return valinta, _pyyda_katselmoija(api, repo, pr_numero, valinta.ehdokkaat)


def toteuta(api: GitHubApi, repo: str, pr_numero: int, paatos: dict[str, Any], asetukset: Asetukset) -> Toteutus:
    """Soveltaa päätöksen: labelit, korjauskierroksen käynnistys, katselmoijapyyntö ja ohjauskommentti."""
    toimet = _paivita_labelit(api, repo, pr_numero, paatos)
    virheet: list[str] = []
    kaynnistys = _kaynnista_korjaus(api, repo, pr_numero, paatos, asetukset)
    if kaynnistys.virhe is not None:
        paatos = _jumissa_paatos(paatos, kaynnistys.virhe)
        labelitoimet, virheet = _varapaatoksen_labelit(api, repo, pr_numero, paatos)
        toimet += [f"korjauskierrosta ei voitu käynnistää: {kaynnistys.virhe}", *labelitoimet]
    valinta, pyynto = _katselmointi(api, repo, pr_numero, paatos, asetukset.katselmoijat)
    virheet += pyynto.virheet
    huomautukset = [*valinta.huomautukset, *virheet, *([kaynnistys.huomautus] if kaynnistys.huomautus else [])]
    teksti = renderoi_ohjaus(paatos, pyynto.tunnus, huomautukset)
    toimet += [*huomautukset, *([f"katselmoija pyydetty: {pyynto.tunnus}"] if pyynto.tunnus else [])]
    toimet.append(f"ohjauskommentti {kirjoita_tai_paivita(api, repo, pr_numero, teksti, asetukset.kommentoija)}")
    return Toteutus(tuple(toimet), kaynnistys.virhe is not None or bool(virheet))
