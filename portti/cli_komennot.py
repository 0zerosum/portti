"""Komentorivikomentojen toteutukset. Jäsennin on cli.py:ssä."""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from portti.arviointi import arvioi
from portti.evidence import Konteksti, evidence_tekstiksi, kirjoita_evidence, lue_evidence
from portti.git_diff import ratkaise_sha
from portti.github_api import GitHubApi
from portti.kommentti import kirjoita_tai_paivita, renderoi
from portti.luokittelu import Edellytykset
from portti.policy import Policy, lataa_policy
from portti.policy_lahde import PolicyLahde, valmistele_tiedosto
from portti.shadow import kokoa_shadow_raportti
from portti.shadow_muotoilu import muotoile_shadow_raportti, shadow_raportti_jsoniksi
from portti.tapaukset import aja_tapaukset, lue_tapaukset, muotoile_tulokset
from portti.verdict import estaa


def _tyokansio() -> Path:
    return Path(tempfile.mkdtemp(prefix="portti-lahde-"))


def _lataa_policy_lahteesta(
    repo_polku: Path, base_sha: str, policy_polku: Path, lahde: str, tila: str
) -> tuple[Policy, PolicyLahde]:
    tiedosto, toteutunut = valmistele_tiedosto(repo_polku, base_sha, policy_polku, lahde, tila, _tyokansio())
    return lataa_policy(tiedosto), toteutunut


def komento_arvioi(argumentit: argparse.Namespace) -> int:
    base_sha = ratkaise_sha(argumentit.repo_polku, argumentit.base)
    policy, lahde = _lataa_policy_lahteesta(
        argumentit.repo_polku, base_sha, argumentit.policy, argumentit.policy_lahde, argumentit.tila
    )
    konteksti = Konteksti(
        argumentit.repo, argumentit.pr, base_sha, argumentit.head, argumentit.tekija, argumentit.tila, lahde.merkinta
    )
    edellytykset = Edellytykset(draft=argumentit.draft, konflikti=argumentit.konflikti)
    arvio = arvioi(argumentit.repo_polku, base_sha, argumentit.head, policy, konteksti, edellytykset)
    if argumentit.evidence is not None:
        kirjoita_evidence(arvio.evidence, argumentit.evidence)
    else:
        print(evidence_tekstiksi(arvio.evidence), end="")
    print(f"portti: {arvio.verdict.verdict} tier={arvio.luokitus.tier} "
          f"portaat={','.join(arvio.verdict.hyvaksyttavissa_portaalla) or '-'} policy={lahde.merkinta}", file=sys.stderr)
    if argumentit.tila == "enforce":
        print("portti: enforce: estävä verdict (PUUTE, KOVA, LIIAN-ISO) kaataa esto-askeleen", file=sys.stderr)
    return 0


def komento_esto(argumentit: argparse.Namespace) -> int:
    """Enforce-tilan viimeinen askel: estävä verdict palauttaa 1. Shadow ei estä koskaan."""
    evidence = lue_evidence(argumentit.evidence)
    tila = evidence.get("tila", "shadow")
    verdict = str(evidence["verdict"])
    if tila != "enforce":
        print(f"portti: esto: tila {tila}, ei estoa ({verdict})", file=sys.stderr)
        return 0
    if estaa(verdict):
        print(f"portti: esto: {verdict} estää; neuvoa-antava ilman GitHubin pakollista checkiä", file=sys.stderr)
        return 1
    print(f"portti: esto: {verdict} ei estä", file=sys.stderr)
    return 0


def komento_kommentti(argumentit: argparse.Namespace, api: GitHubApi) -> int:
    evidence = lue_evidence(argumentit.evidence)
    teksti = renderoi(evidence, argumentit.artefakti_url)
    toimi = kirjoita_tai_paivita(api, argumentit.repo, argumentit.pr, teksti)
    print(f"portti: kommentti {toimi}", file=sys.stderr)
    return 0


@dataclass(frozen=True)
class _TapausSyote:
    policy: Policy
    tapaukset: Path | None
    merkinta: str
    ohitetaan: bool = False


def _tapaukset_headista(argumentit: argparse.Namespace, repo_polku: Path) -> _TapausSyote:
    # Suhteelliset polut ovat repon polkuja, eivät työhakemiston.
    policy = lataa_policy(repo_polku / argumentit.policy)
    return _TapausSyote(policy, repo_polku / argumentit.tapaukset, "policy ja tapaukset: head")


def _tapaukset_basesta(argumentit: argparse.Namespace, repo_polku: Path) -> _TapausSyote:
    """Tapaukset ovat valinnaisia: basesta puuttuva tapaustiedosto ohittaa askeleen, ei kaada sitä."""
    base_sha = ratkaise_sha(repo_polku, argumentit.base)
    policy, lahde = _lataa_policy_lahteesta(repo_polku, base_sha, argumentit.policy, argumentit.lahde, argumentit.tila)
    tapaukset, tapausten_lahde = valmistele_tiedosto(
        repo_polku, base_sha, argumentit.tapaukset, argumentit.lahde, argumentit.tila, _tyokansio()
    )
    merkinta = f"policy: {lahde.merkinta}, tapaukset: {tapausten_lahde.merkinta}"
    return _TapausSyote(policy, tapaukset, merkinta, ohitetaan=tapaukset is None)


def komento_tapaukset(argumentit: argparse.Namespace) -> int:
    repo_polku: Path = argumentit.repo_polku
    if argumentit.lahde == "head" or (argumentit.lahde == "auto" and argumentit.tila == "shadow"):
        syote = _tapaukset_headista(argumentit, repo_polku)
    elif argumentit.base is None:
        print("portti: --base tarvitaan, kun tapaukset luetaan basesta", file=sys.stderr)
        return 2
    else:
        syote = _tapaukset_basesta(argumentit, repo_polku)
    if syote.ohitetaan:
        print(f"portti: tapaustiedostoa {argumentit.tapaukset} ei ole ({syote.merkinta}), ohitetaan", file=sys.stderr)
        return 0
    if syote.tapaukset is None or not syote.tapaukset.exists():
        print(f"portti: tapaustiedostoa {argumentit.tapaukset} ei ole ({syote.merkinta})", file=sys.stderr)
        return 2
    tulokset = aja_tapaukset(repo_polku, lue_tapaukset(syote.tapaukset), syote.policy)
    print(muotoile_tulokset(tulokset))
    eroavat = [tulos for tulos in tulokset if not tulos.ok]
    print(f"portti: {len(tulokset) - len(eroavat)}/{len(tulokset)} tapausta kunnossa ({syote.merkinta})", file=sys.stderr)
    return 1 if eroavat else 0


def komento_shadow(argumentit: argparse.Namespace, api: GitHubApi) -> int:
    raportti = kokoa_shadow_raportti(api, argumentit.repo, argumentit.alkaen)
    if argumentit.json:
        print(shadow_raportti_jsoniksi(raportti), end="")
    else:
        print(muotoile_shadow_raportti(raportti), end="")
    return 0
