"""Komentorivi: arvioi, kommentti, tarkista-tapaukset, shadow-raportti. Toteutukset cli_komennot.py:ssä."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from portti.cli_komennot import komento_arvioi, komento_kommentti, komento_shadow, komento_tapaukset
from portti.github_api import GitHubApi
from portti.policy_lahde import LAHTEET, TILAT
from portti.version import VERSIO


def _lisaa_arvioi(alikomennot: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    komento = alikomennot.add_parser("arvioi", help="luokittele diff, laske verdict, kirjoita evidence")
    komento.add_argument("--base", required=True)
    komento.add_argument("--head", required=True)
    komento.add_argument("--policy", type=Path, default=Path(".portti/policy.yml"))
    komento.add_argument("--policy-lahde", choices=LAHTEET, default="auto",
                         help="head = PR:n oma policy, base = base-haaran policy, auto = tilan mukaan")
    komento.add_argument("--repo-polku", type=Path, default=Path("."))
    komento.add_argument("--repo", default="paikallinen")
    komento.add_argument("--pr", type=int, default=None)
    komento.add_argument("--tekija", default=None, help="GitHub-tunnus sellaisenaan")
    komento.add_argument("--draft", action="store_true")
    komento.add_argument("--konflikti", action="store_true")
    komento.add_argument("--tila", choices=TILAT, default="shadow")
    komento.add_argument("--evidence", type=Path, default=None, help="evidence-JSONin kohdetiedosto")


def _lisaa_kommentti(alikomennot: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    komento = alikomennot.add_parser("kommentti", help="kirjoita tai päivitä portin PR-kommentti")
    komento.add_argument("--evidence", type=Path, required=True)
    komento.add_argument("--repo", required=True)
    komento.add_argument("--pr", type=int, required=True)
    komento.add_argument("--artefakti-url", default=None)


def _lisaa_tapaukset(alikomennot: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    komento = alikomennot.add_parser("tarkista-tapaukset", help="aja repon regressiotapaukset")
    komento.add_argument("tapaukset", type=Path)
    komento.add_argument("--policy", type=Path, default=Path(".portti/policy.yml"))
    komento.add_argument("--repo-polku", type=Path, default=Path("."))
    komento.add_argument("--lahde", choices=LAHTEET, default="auto", help="mistä policy ja tapaukset luetaan")
    komento.add_argument("--tila", choices=TILAT, default="shadow")
    komento.add_argument("--base", default=None, help="base-viite, kun lähde on base")


def _lisaa_shadow(alikomennot: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    komento = alikomennot.add_parser("shadow-raportti", help="vertaa portin verdictit PR:ien lopputuloksiin")
    komento.add_argument("--repo", action="append", required=True, help="omistaja/repo; toistettavissa")
    komento.add_argument("--alkaen", required=True, help="päivämäärä VVVV-KK-PP")
    komento.add_argument("--json", action="store_true", help="tuloste JSONina markdownin sijaan")


def rakenna_jasennin() -> argparse.ArgumentParser:
    jasennin = argparse.ArgumentParser(prog="portti", description=f"Portti {VERSIO}")
    jasennin.add_argument("--versio", action="version", version=VERSIO)
    alikomennot = jasennin.add_subparsers(dest="komento", required=True)
    _lisaa_arvioi(alikomennot)
    _lisaa_kommentti(alikomennot)
    _lisaa_tapaukset(alikomennot)
    _lisaa_shadow(alikomennot)
    return jasennin


def main(argv: list[str] | None = None, api: GitHubApi | None = None) -> int:
    argumentit = rakenna_jasennin().parse_args(argv)
    api = api or GitHubApi()
    if argumentit.komento == "arvioi":
        return komento_arvioi(argumentit)
    if argumentit.komento == "kommentti":
        return komento_kommentti(argumentit, api)
    if argumentit.komento == "tarkista-tapaukset":
        return komento_tapaukset(argumentit)
    return komento_shadow(argumentit, api)


if __name__ == "__main__":
    sys.exit(main())
