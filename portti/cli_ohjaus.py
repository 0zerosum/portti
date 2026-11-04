"""Ohjauksen komennot: `ohjaa` (päätös ilman verkkoa) ja `ohjaus-toteuta` (päätöksen soveltaminen gh:lla)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from portti.evidence import lue_evidence
from portti.github_api import GitHubApi
from portti.ohjaus import TESTIEN_TILAT, OhjausSyote, lue_paatos, paata, paatos_sanakirjaksi, paatos_tekstiksi
from portti.ohjaus_toteutus import Katselmoijat, KorjausAjo, toteuta


def lisaa_ohjaus_komennot(alikomennot: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    ohjaa = alikomennot.add_parser("ohjaa", help="päätä PR:n ohjaus evidencestä, testien tilasta ja muuttuneista poluista")
    ohjaa.add_argument("--head", required=True, help="PR:n head-sha")
    ohjaa.add_argument("--testit", choices=TESTIEN_TILAT, required=True, help="testityönkulun lopputulos PR:n headille")
    ohjaa.add_argument("--evidence", type=Path, default=None, help="Portti-ajon evidence-JSON; puuttuva tiedosto on puute")
    ohjaa.add_argument("--polut", type=Path, required=True, help="PR:n muuttuneet polut, yksi riviä kohden")
    ohjaa.add_argument("--labelit", default="", help="PR:n nykyiset labelit pilkuilla eroteltuna")
    ohjaa.add_argument("--forkki", action="store_true", help="PR tulee forkista: korjauskierrosta ei käynnistetä")
    ohjaa.add_argument("--paatos", type=Path, default=None, help="päätös-JSONin kohdetiedosto (oletus stdout)")
    toteuta = alikomennot.add_parser("ohjaus-toteuta", help="sovella päätös: labelit, katselmoija, kommentti, kortti-ajo")
    toteuta.add_argument("--paatos", type=Path, required=True)
    toteuta.add_argument("--repo", required=True)
    toteuta.add_argument("--pr", type=int, required=True)
    toteuta.add_argument("--katselmoija-cto", default="", help="CTO:n GitHub-tunnus (kuluttajarepon muuttuja)")
    toteuta.add_argument("--katselmoija-t1", default="", help="T1-katselmoijan GitHub-tunnus; puuttuessa käytetään CTO:ta")
    toteuta.add_argument("--kortti-ajo", default="", help="kuluttajan kortti-ajon työnkulkutiedosto korjauskierrosta varten")
    toteuta.add_argument("--kortti", default="", help="kortin slug, sama kuin PR:n haara")
    toteuta.add_argument("--oletushaara", default="main", help="haara, jolta kortti-ajo käynnistetään")


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


def _lue_polut(polku: Path) -> tuple[str, ...]:
    return tuple(rivi.strip() for rivi in polku.read_text(encoding="utf-8").splitlines() if rivi.strip())


def _labelit(teksti: str) -> tuple[str, ...]:
    return tuple(sorted({osa.strip() for osa in teksti.split(",") if osa.strip()}))


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
    korjausajo = None
    if argumentit.kortti_ajo and argumentit.kortti:
        korjausajo = KorjausAjo(argumentit.kortti_ajo, argumentit.kortti, argumentit.oletushaara)
    for toimi in toteuta(api, argumentit.repo, argumentit.pr, paatos, katselmoijat, korjausajo):
        print(f"portti: ohjaus-toteuta: {toimi}", file=sys.stderr)
    return 0
