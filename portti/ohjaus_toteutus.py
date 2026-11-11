"""Ohjauspäätöksen toteutus GitHubissa: labelit, katselmoijapyyntö, ohjauskommentti ja korjauskierroksen käynnistys.

Kortti-ajo käynnistetään vain, kun päätös sanoo niin (`kaynnista_kortti_ajo`): moottori päättää sen
edellisestä päätöksestä, jonka `edellinen_paatos` lukee ohjauskommentin konedatasta ennen päätöstä.
Katselmoijien tunnukset tulevat parametreina, eivät reposta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from portti.github_api import GitHubApi
from portti.kommentti import kirjoita_tai_paivita
from portti.ohjaus import KIERROS_ETULIITE, KORJAUSKIERROS, LABEL_AGENTTI, ROOLI_T1, TIER_ETULIITE
from portti.ohjaus_kommentti import lue_ohjauksen_konedata, renderoi_ohjaus

LABELIEN_VARIT = {
    "katselmoitavaksi": "0e8a16",
    "kova": "b60205",
    "jumissa": "b60205",
    "korjattava": "fbca04",
    "liian-iso": "d93f0b",
    LABEL_AGENTTI: "5319e7",
}
OLETUSVARI = "c5def5"


@dataclass(frozen=True)
class Katselmoijat:
    cto: str | None
    t1: str | None


@dataclass(frozen=True)
class KatselmoijaValinta:
    tunnus: str | None
    huomautus: str | None


@dataclass(frozen=True)
class KorjausAjo:
    tyonkulku: str
    kortti: str
    haara: str


def ratkaise_katselmoija(rooli: str | None, katselmoijat: Katselmoijat) -> KatselmoijaValinta:
    """T1 puuttuu → CTO. CTO puuttuu → ei pyyntöä ja huomautus."""
    if rooli is None:
        return KatselmoijaValinta(None, None)
    if rooli == ROOLI_T1 and katselmoijat.t1:
        return KatselmoijaValinta(katselmoijat.t1, None)
    if katselmoijat.cto:
        huomautus = "T1-katselmoijaa ei ole asetettu (PORTTI_KATSELMOIJA_T1), käytetään CTO:ta" if rooli == ROOLI_T1 else None
        return KatselmoijaValinta(katselmoijat.cto, huomautus)
    return KatselmoijaValinta(None, "katselmoija ei asetettu (PORTTI_KATSELMOIJA_CTO puuttuu)")


def labelin_vari(label: str) -> str:
    if label.startswith(TIER_ETULIITE):
        return OLETUSVARI
    if label.startswith(KIERROS_ETULIITE):
        return LABELIEN_VARIT["korjattava"]
    return LABELIEN_VARIT.get(label, OLETUSVARI)


def edellinen_paatos(api: GitHubApi, repo: str, pr_numero: int) -> dict[str, Any] | None:
    """PR:n ohjauskommentin konedata (head, toimenpide, kierros) tai None, jos ohjaus ei ole vielä kommentoinut."""
    for kommentti in api.hae_kommentit(repo, pr_numero):
        konedata = lue_ohjauksen_konedata(str(kommentti.get("body", "")))
        if konedata is not None:
            return konedata
    return None


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


def _pyyda_katselmoija(api: GitHubApi, repo: str, pr_numero: int, valinta: KatselmoijaValinta) -> str | None:
    if valinta.tunnus is None:
        return None
    tekija = str(api.hae_pr(repo, pr_numero).get("author", {}).get("login", ""))
    if tekija == valinta.tunnus:
        return f"katselmoija {valinta.tunnus} on PR:n tekijä, pyyntöä ei tehty"
    api.pyyda_katselmoija(repo, pr_numero, valinta.tunnus)
    return f"katselmoija pyydetty: {valinta.tunnus}"


def _kaynnista_korjaus(
    api: GitHubApi, repo: str, pr_numero: int, paatos: dict[str, Any], korjausajo: KorjausAjo | None
) -> str | None:
    if paatos["toimenpide"] != KORJAUSKIERROS:
        return None
    if not paatos.get("kaynnista_kortti_ajo"):
        return f"kortti-ajoa ei käynnistetty uudelleen: kierros {paatos.get('kierros')} on jo käynnistetty tälle headille"
    if korjausajo is None:
        return "korjauskierrosta ei käynnistetty: kortti-ajoa ei ole määritetty"
    syotteet = {"kortti": korjausajo.kortti, "korjaa_pr": str(pr_numero)}
    api.kaynnista_tyonkulku(repo, korjausajo.tyonkulku, korjausajo.haara, syotteet)
    return f"kortti-ajo käynnistetty: {korjausajo.tyonkulku}, kortti {korjausajo.kortti}, kierros {paatos.get('kierros')}"


def toteuta(
    api: GitHubApi, repo: str, pr_numero: int, paatos: dict[str, Any], katselmoijat: Katselmoijat,
    korjausajo: KorjausAjo | None,
) -> list[str]:
    """Soveltaa päätöksen ja palauttaa tehdyt toimet lokiriveinä."""
    toimet = _paivita_labelit(api, repo, pr_numero, paatos)
    valinta = ratkaise_katselmoija(paatos.get("katselmoijan_rooli"), katselmoijat)
    pyynto = _pyyda_katselmoija(api, repo, pr_numero, valinta)
    kaynnistys = _kaynnista_korjaus(api, repo, pr_numero, paatos, korjausajo)
    huomautukset = [huomautus for huomautus in (valinta.huomautus, pyynto, kaynnistys) if huomautus]
    teksti = renderoi_ohjaus(paatos, valinta.tunnus, huomautukset)
    toimet += [huomautus for huomautus in (pyynto, kaynnistys) if huomautus]
    toimet.append(f"ohjauskommentti {kirjoita_tai_paivita(api, repo, pr_numero, teksti)}")
    return toimet
