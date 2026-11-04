"""Yhden arvioinnin kokoaminen: luokitus, verdict ja evidence samasta syötteestä."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from portti.evidence import Konteksti, rakenna_evidence
from portti.git_diff import ratkaise_sha
from portti.luokittelu import Edellytykset, Luokitus, luokittele
from portti.policy import Policy
from portti.verdict import Verdict, laske_verdict


@dataclass(frozen=True)
class Arvio:
    luokitus: Luokitus
    verdict: Verdict
    evidence: dict[str, Any]


def arvioi(
    repo_polku: Path,
    base: str,
    head: str,
    policy: Policy,
    konteksti: Konteksti,
    edellytykset: Edellytykset = Edellytykset(),
) -> Arvio:
    base_sha = ratkaise_sha(repo_polku, base)
    head_sha = ratkaise_sha(repo_polku, head)
    luokitus = luokittele(repo_polku, base_sha, head_sha, policy, edellytykset)
    verdict = laske_verdict(luokitus)
    ratkaistu = Konteksti(
        konteksti.repo, konteksti.pr_numero, base_sha, head_sha, konteksti.tekija,
        konteksti.tila, konteksti.policy_lahde,
    )
    return Arvio(luokitus, verdict, rakenna_evidence(ratkaistu, policy, luokitus, verdict))
