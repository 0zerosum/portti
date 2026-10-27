"""Evidence-JSON: kaikki portin faktat ilman nimiä tai sähköposteja."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from portti.luokittelu import Luokitus
from portti.policy import Policy
from portti.verdict import Verdict
from portti.version import VERSIO

EVIDENCE_MUOTO = 1


@dataclass(frozen=True)
class Konteksti:
    repo: str
    pr_numero: int | None
    base_sha: str
    head_sha: str
    tekija: str | None
    tila: str = "shadow"
    policy_lahde: str = "head"


def _tiedostot(luokitus: Luokitus) -> list[dict[str, Any]]:
    return [
        {
            "polku": tiedosto.polku,
            "tila": tiedosto.tila,
            "vanha_polku": tiedosto.vanha_polku,
            "lisatty": tiedosto.lisatty,
            "poistettu": tiedosto.poistettu,
            "binaari": tiedosto.binaari,
            "substantiivinen": tiedosto.polku in luokitus.substantiiviset,
        }
        for tiedosto in luokitus.tiedostot
    ]


def _luokitus(luokitus: Luokitus) -> dict[str, Any]:
    testimaara = None if luokitus.testimaara is None else asdict(luokitus.testimaara)
    return {
        "tier": luokitus.tier,
        "rivit": luokitus.rivit,
        "tiedostoja": len(luokitus.substantiiviset),
        "alueet": luokitus.alueet,
        "tiedostot": _tiedostot(luokitus),
        "deny_osumat": [asdict(osuma) for osuma in luokitus.deny_osumat],
        "kielletyt_uudet_polut": [
            {"polku": polku, "malli": malli} for polku, malli in luokitus.kielletyt_uudet
        ],
        "invariantit": [asdict(tulos) for tulos in luokitus.invariantit],
        "testimaara": testimaara,
        "puutteet": luokitus.puutteet,
    }


def rakenna_evidence(
    konteksti: Konteksti, policy: Policy, luokitus: Luokitus, verdict: Verdict
) -> dict[str, Any]:
    return {
        "evidence_muoto": EVIDENCE_MUOTO,
        "moottorin_versio": VERSIO,
        "policy": {"oletuksen_sha256": policy.oletuksen_sha, "repon_sha256": policy.repon_sha},
        "repo": konteksti.repo,
        "pr_numero": konteksti.pr_numero,
        "base_sha": konteksti.base_sha,
        "head_sha": konteksti.head_sha,
        "tekija": konteksti.tekija,
        "tila": konteksti.tila,
        "policy_lahde": konteksti.policy_lahde,
        "luokitus": _luokitus(luokitus),
        "portit": [asdict(portti) for portti in verdict.portit],
        "verdict": verdict.verdict,
        "hyvaksyttavissa_portaalla": verdict.hyvaksyttavissa_portaalla,
    }


def evidence_tekstiksi(evidence: dict[str, Any]) -> str:
    return json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def kirjoita_evidence(evidence: dict[str, Any], polku: Path) -> None:
    polku.write_text(evidence_tekstiksi(evidence), encoding="utf-8")


def lue_evidence(polku: Path) -> dict[str, Any]:
    sisalto = json.loads(polku.read_text(encoding="utf-8"))
    if not isinstance(sisalto, dict) or sisalto.get("evidence_muoto") != EVIDENCE_MUOTO:
        raise ValueError(f"{polku}: ei ole portin evidence-tiedosto (muoto {EVIDENCE_MUOTO})")
    return sisalto
