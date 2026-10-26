"""Shadow-raportti: portin verdict vs. PR:n lopputulos. Ei tallenna mitään."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from portti.github_api import GitHubApi
from portti.kommentti import lue_konedata
from portti.verdict import KOVA, PEHMEA, VAPAA

MERGETTY_MUUTTAMATTA = "mergetty muuttamatta"
MERGETTY_MUUTOSTEN_JALKEEN = "mergetty muutosten jälkeen"
SULJETTU = "suljettu"
EI_KOMMENTTIA = "ei portin kommenttia"


@dataclass(frozen=True)
class ShadowRivi:
    pr_numero: int
    verdict: str | None
    tier: str | None
    lopputulos: str


@dataclass(frozen=True)
class ShadowRaportti:
    rivit: list[ShadowRivi]

    @property
    def kova_tai_pehmea_mutta_mergetty_muuttamatta(self) -> int:
        return sum(
            1 for rivi in self.rivit
            if rivi.verdict in (KOVA, PEHMEA) and rivi.lopputulos == MERGETTY_MUUTTAMATTA
        )

    @property
    def vapaa_mutta_hylatty(self) -> int:
        return sum(1 for rivi in self.rivit if rivi.verdict == VAPAA and rivi.lopputulos == SULJETTU)


def _portin_konedata(kommentit: list[dict[str, Any]]) -> dict[str, Any] | None:
    for kommentti in kommentit:
        konedata = lue_konedata(str(kommentti.get("body", "")))
        if konedata is not None:
            return konedata
    return None


def _lopputulos(pr: dict[str, Any], konedata: dict[str, Any] | None) -> str:
    if konedata is None:
        return EI_KOMMENTTIA
    if not pr.get("mergedAt"):
        return SULJETTU
    if konedata.get("head_sha") == pr.get("headRefOid"):
        return MERGETTY_MUUTTAMATTA
    return MERGETTY_MUUTOSTEN_JALKEEN


def kokoa_shadow_raportti(api: GitHubApi, repo: str, alkaen: str) -> ShadowRaportti:
    rivit: list[ShadowRivi] = []
    for pr in sorted(api.hae_suljetut_prt(repo, alkaen), key=lambda pr: int(pr["number"])):
        numero = int(pr["number"])
        konedata = _portin_konedata(api.hae_kommentit(repo, numero))
        verdict = konedata.get("verdict") if konedata else None
        tier = konedata.get("tier") if konedata else None
        rivit.append(ShadowRivi(numero, verdict, tier, _lopputulos(pr, konedata)))
    return ShadowRaportti(rivit)


def muotoile_shadow_raportti(raportti: ShadowRaportti) -> str:
    rivit = ["| PR | Verdict | Tier | Lopputulos |", "|---|---|---|---|"]
    for rivi in raportti.rivit:
        rivit.append(f"| #{rivi.pr_numero} | {rivi.verdict or '–'} | {rivi.tier or '–'} | {rivi.lopputulos} |")
    rivit += [
        "",
        f"PR:iä yhteensä: {len(raportti.rivit)}",
        f"KOVA/PEHMEÄ mutta mergetty muuttamatta: {raportti.kova_tai_pehmea_mutta_mergetty_muuttamatta}",
        f"VAPAA mutta hylätty: {raportti.vapaa_mutta_hylatty}",
    ]
    return "\n".join(rivit)
