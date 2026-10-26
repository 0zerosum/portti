"""Komentorivi: arvioi, kommentti, tarkista-tapaukset, shadow-raportti."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from portti.arviointi import arvioi
from portti.evidence import Konteksti, evidence_tekstiksi, kirjoita_evidence, lue_evidence
from portti.github_api import GitHubApi
from portti.kommentti import kirjoita_tai_paivita, renderoi
from portti.luokittelu import Edellytykset
from portti.policy import lataa_policy
from portti.shadow import kokoa_shadow_raportti, muotoile_shadow_raportti
from portti.tapaukset import aja_tapaukset, lue_tapaukset, muotoile_tulokset
from portti.version import VERSIO

TILAT = ("shadow", "enforce")


def _lisaa_arvioi(alikomennot: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    komento = alikomennot.add_parser("arvioi", help="luokittele diff, laske verdict, kirjoita evidence")
    komento.add_argument("--base", required=True)
    komento.add_argument("--head", required=True)
    komento.add_argument("--policy", type=Path, default=Path(".portti/policy.yml"))
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


def _lisaa_shadow(alikomennot: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    komento = alikomennot.add_parser("shadow-raportti", help="vertaa portin verdictit PR:ien lopputuloksiin")
    komento.add_argument("--repo", required=True, help="omistaja/repo")
    komento.add_argument("--alkaen", required=True, help="päivämäärä VVVV-KK-PP")


def rakenna_jasennin() -> argparse.ArgumentParser:
    jasennin = argparse.ArgumentParser(prog="portti", description=f"Portti {VERSIO}")
    jasennin.add_argument("--versio", action="version", version=VERSIO)
    alikomennot = jasennin.add_subparsers(dest="komento", required=True)
    _lisaa_arvioi(alikomennot)
    _lisaa_kommentti(alikomennot)
    _lisaa_tapaukset(alikomennot)
    _lisaa_shadow(alikomennot)
    return jasennin


def komento_arvioi(argumentit: argparse.Namespace) -> int:
    if argumentit.tila == "enforce":
        print("portti: tila enforce ei toteutettu", file=sys.stderr)
        return 2
    policy = lataa_policy(argumentit.policy)
    konteksti = Konteksti(argumentit.repo, argumentit.pr, argumentit.base, argumentit.head, argumentit.tekija, argumentit.tila)
    edellytykset = Edellytykset(draft=argumentit.draft, konflikti=argumentit.konflikti)
    arvio = arvioi(argumentit.repo_polku, argumentit.base, argumentit.head, policy, konteksti, edellytykset)
    if argumentit.evidence is not None:
        kirjoita_evidence(arvio.evidence, argumentit.evidence)
    else:
        print(evidence_tekstiksi(arvio.evidence), end="")
    print(f"portti: {arvio.verdict.verdict} tier={arvio.luokitus.tier} "
          f"portaat={','.join(arvio.verdict.hyvaksyttavissa_portaalla) or '-'}", file=sys.stderr)
    return 0


def komento_kommentti(argumentit: argparse.Namespace, api: GitHubApi) -> int:
    evidence = lue_evidence(argumentit.evidence)
    teksti = renderoi(evidence, argumentit.artefakti_url)
    toimi = kirjoita_tai_paivita(api, argumentit.repo, argumentit.pr, teksti)
    print(f"portti: kommentti {toimi}", file=sys.stderr)
    return 0


def komento_tapaukset(argumentit: argparse.Namespace) -> int:
    policy = lataa_policy(argumentit.policy)
    tulokset = aja_tapaukset(argumentit.repo_polku, lue_tapaukset(argumentit.tapaukset), policy)
    print(muotoile_tulokset(tulokset))
    eroavat = [tulos for tulos in tulokset if not tulos.ok]
    print(f"portti: {len(tulokset) - len(eroavat)}/{len(tulokset)} tapausta kunnossa", file=sys.stderr)
    return 1 if eroavat else 0


def komento_shadow(argumentit: argparse.Namespace, api: GitHubApi) -> int:
    print(muotoile_shadow_raportti(kokoa_shadow_raportti(api, argumentit.repo, argumentit.alkaen)))
    return 0


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
