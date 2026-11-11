"""Ohjauksen komennot: `ohjaus-edellinen` (edellisen päätöksen luku PR:n kommentista), `ohjaa` (päätös ilman
verkkoa) ja `ohjaus-toteuta` (päätöksen soveltaminen gh:lla)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from portti.evidence import lue_evidence
from portti.github_api import GitHubApi
from portti.ohjaus import TESTIEN_TILAT, OhjausSyote, lue_paatos, paata, paatos_sanakirjaksi, paatos_tekstiksi
from portti.ohjaus_kommentti import OHJAUKSEN_KOMMENTOIJA
from portti.ohjaus_toteutus import Asetukset, Katselmoijat, KorjausAjo, edellinen_paatos, toteuta


def _lisaa_kommentoija(komento: argparse.ArgumentParser) -> None:
    komento.add_argument("--kommentoija", default=OHJAUKSEN_KOMMENTOIJA,
                         help="tunnus, jonka kirjoittama ohjauskommentti luetaan ja päivitetään; muiden kommentit ohitetaan")


def _lisaa_edellinen(alikomennot: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    komento = alikomennot.add_parser("ohjaus-edellinen", help="lue PR:n edellinen ohjauspäätös ohjauskommentin konedatasta")
    komento.add_argument("--repo", required=True)
    komento.add_argument("--pr", type=int, required=True)
    komento.add_argument("--tuloste", type=Path, default=None, help="kohdetiedosto (oletus stdout); null, jos päätöstä ei ole")
    _lisaa_kommentoija(komento)


def _lisaa_ohjaa(alikomennot: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    komento = alikomennot.add_parser("ohjaa", help="päätä PR:n ohjaus evidencestä, testien tilasta ja muuttuneista poluista")
    komento.add_argument("--head", required=True, help="PR:n head-sha")
    komento.add_argument("--testit", choices=TESTIEN_TILAT, required=True, help="testityönkulun lopputulos PR:n headille")
    komento.add_argument("--evidence", type=Path, default=None, help="Portti-ajon evidence-JSON; puuttuva tiedosto on puute")
    komento.add_argument("--polut", type=Path, required=True, help="PR:n muuttuneet polut, yksi riviä kohden")
    komento.add_argument("--polut-vajaat", action="store_true",
                         help="polkulista ei kata kaikkia PR:n tiedostoja (GitHub palauttaa enintään 3000): PR menee CTO:lle")
    komento.add_argument("--labelit", default="", help="PR:n nykyiset labelit pilkuilla eroteltuna")
    komento.add_argument("--forkki", action="store_true", help="PR tulee forkista: korjauskierrosta ei käynnistetä")
    komento.add_argument("--haara", default="", help="PR:n haara; kortin slug luetaan muodosta feature/<slug>")
    komento.add_argument("--edellinen", type=Path, default=None,
                         help="edellinen päätös (ohjaus-edellinen): tälle headille jo käynnistetty kierros ei käynnisty uudelleen")
    komento.add_argument("--paatos", type=Path, default=None, help="päätös-JSONin kohdetiedosto (oletus stdout)")


def _lisaa_toteuta(alikomennot: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    komento = alikomennot.add_parser("ohjaus-toteuta", help="sovella päätös: labelit, katselmoija, kommentti, kortti-ajo")
    komento.add_argument("--paatos", type=Path, required=True)
    komento.add_argument("--repo", required=True)
    komento.add_argument("--pr", type=int, required=True)
    komento.add_argument("--katselmoija-cto", default="", help="CTO:n GitHub-tunnus (kuluttajarepon muuttuja)")
    komento.add_argument("--katselmoija-t1", default="", help="T1-katselmoijan GitHub-tunnus; puuttuessa käytetään CTO:ta")
    komento.add_argument("--kortti-ajo", default="", help="kuluttajan kortti-ajon työnkulkutiedosto korjauskierrosta varten")
    komento.add_argument("--oletushaara", default="main", help="haara, jolta kortti-ajo käynnistetään")
    _lisaa_kommentoija(komento)


def lisaa_ohjaus_komennot(alikomennot: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    _lisaa_edellinen(alikomennot)
    _lisaa_ohjaa(alikomennot)
    _lisaa_toteuta(alikomennot)


def _lue_evidence_tai_puute(polku: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    """Puuttuva tai kelvoton evidence ei kaada ohjausta: se on fail-closed-syy, joka kirjataan perusteluun."""
    if polku is None:
        return None, "evidence puuttuu (ei annettu)"
    if not polku.exists():
        return None, f"evidence puuttuu ({polku.name} ei ole)"
    try:
        return lue_evidence(polku), None
    except (ValueError, OSError) as virhe:
        return None, f"evidence ei kelpaa: {virhe}"


def _lue_edellinen(polku: Path | None) -> dict[str, Any] | None:
    """Edellinen päätös tai None. Annettu mutta puuttuva tai kelvoton tiedosto kaataa komennon: sitä ei arvata."""
    if polku is None:
        return None
    if not polku.exists():
        raise ValueError(f"{polku}: edellisen päätöksen tiedostoa ei ole")
    sisalto = json.loads(polku.read_text(encoding="utf-8"))
    if sisalto is not None and not isinstance(sisalto, dict):
        raise ValueError(f"{polku}: edellisen päätöksen on oltava JSON-objekti tai null")
    return sisalto


def _lue_polut(polku: Path) -> tuple[str, ...]:
    return tuple(rivi.strip() for rivi in polku.read_text(encoding="utf-8").splitlines() if rivi.strip())


def _labelit(teksti: str) -> tuple[str, ...]:
    return tuple(sorted({osa.strip() for osa in teksti.split(",") if osa.strip()}))


def komento_ohjaus_edellinen(argumentit: argparse.Namespace, api: GitHubApi) -> int:
    edellinen = edellinen_paatos(api, argumentit.repo, argumentit.pr, argumentit.kommentoija)
    teksti = json.dumps(edellinen, ensure_ascii=False, sort_keys=True) + "\n"
    if argumentit.tuloste is not None:
        argumentit.tuloste.write_text(teksti, encoding="utf-8")
    else:
        print(teksti, end="")
    kuvaus = "ei aiempaa päätöstä" if edellinen is None else f"{edellinen.get('toimenpide')} headille {edellinen.get('head_sha')}"
    print(f"portti: ohjaus-edellinen: {kuvaus}", file=sys.stderr)
    return 0


def komento_ohjaa(argumentit: argparse.Namespace) -> int:
    evidence, huomautus = _lue_evidence_tai_puute(argumentit.evidence)
    syote = OhjausSyote(
        pr_head_sha=argumentit.head,
        testit=argumentit.testit,
        evidence=evidence,
        muuttuneet_polut=_lue_polut(argumentit.polut),
        labelit=_labelit(argumentit.labelit),
        forkki=argumentit.forkki,
        evidence_huomautus=huomautus,
        edellinen=_lue_edellinen(argumentit.edellinen),
        haara=argumentit.haara or None,
        polut_vajaat=argumentit.polut_vajaat,
    )
    paatos = paatos_sanakirjaksi(syote, paata(syote))
    teksti = paatos_tekstiksi(paatos)
    if argumentit.paatos is not None:
        argumentit.paatos.write_text(teksti, encoding="utf-8")
    else:
        print(teksti, end="")
    print(f"portti: ohjaus {paatos['toimenpide']}: {paatos['perustelu']}", file=sys.stderr)
    return 0


def komento_ohjaus_toteuta(argumentit: argparse.Namespace, api: GitHubApi) -> int:
    paatos = lue_paatos(argumentit.paatos)
    katselmoijat = Katselmoijat(argumentit.katselmoija_cto or None, argumentit.katselmoija_t1 or None)
    korjausajo = KorjausAjo(argumentit.kortti_ajo, argumentit.oletushaara) if argumentit.kortti_ajo else None
    asetukset = Asetukset(katselmoijat, korjausajo, argumentit.kommentoija)
    for toimi in toteuta(api, argumentit.repo, argumentit.pr, paatos, asetukset):
        print(f"portti: ohjaus-toteuta: {toimi}", file=sys.stderr)
    return 0
