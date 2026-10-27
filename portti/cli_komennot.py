"""Komentorivikomentojen toteutukset. Jäsennin on cli.py:ssä."""

from __future__ import annotations

import argparse
import sys
import tempfile
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
        print("portti: enforce lukee policyn basesta; esto ei toteutettu, verdict ei vaikuta exit-koodiin", file=sys.stderr)
    return 0


def komento_kommentti(argumentit: argparse.Namespace, api: GitHubApi) -> int:
    evidence = lue_evidence(argumentit.evidence)
    teksti = renderoi(evidence, argumentit.artefakti_url)
    toimi = kirjoita_tai_paivita(api, argumentit.repo, argumentit.pr, teksti)
    print(f"portti: kommentti {toimi}", file=sys.stderr)
    return 0


def komento_tapaukset(argumentit: argparse.Namespace) -> int:
    repo_polku: Path = argumentit.repo_polku
    if argumentit.lahde == "head" or (argumentit.lahde == "auto" and argumentit.tila == "shadow"):
        # Suhteelliset polut ovat repon polkuja, eivät työhakemiston.
        policy = lataa_policy(repo_polku / argumentit.policy)
        tapaukset_polku: Path | None = repo_polku / argumentit.tapaukset
        merkinta = "head"
    else:
        if argumentit.base is None:
            print("portti: --base tarvitaan, kun tapaukset luetaan basesta", file=sys.stderr)
            return 2
        base_sha = ratkaise_sha(repo_polku, argumentit.base)
        policy, lahde = _lataa_policy_lahteesta(repo_polku, base_sha, argumentit.policy, argumentit.lahde, argumentit.tila)
        tapaukset_polku, _ = valmistele_tiedosto(
            repo_polku, base_sha, argumentit.tapaukset, argumentit.lahde, argumentit.tila, _tyokansio()
        )
        merkinta = lahde.merkinta
    if tapaukset_polku is None or not tapaukset_polku.exists():
        print(f"portti: tapaustiedostoa {argumentit.tapaukset} ei ole ({merkinta})", file=sys.stderr)
        return 2
    tulokset = aja_tapaukset(repo_polku, lue_tapaukset(tapaukset_polku), policy)
    print(muotoile_tulokset(tulokset))
    eroavat = [tulos for tulos in tulokset if not tulos.ok]
    print(f"portti: {len(tulokset) - len(eroavat)}/{len(tulokset)} tapausta kunnossa (policy ja tapaukset: {merkinta})",
          file=sys.stderr)
    return 1 if eroavat else 0


def komento_shadow(argumentit: argparse.Namespace, api: GitHubApi) -> int:
    raportti = kokoa_shadow_raportti(api, argumentit.repo, argumentit.alkaen)
    if argumentit.json:
        print(shadow_raportti_jsoniksi(raportti), end="")
    else:
        print(muotoile_shadow_raportti(raportti), end="")
    return 0
