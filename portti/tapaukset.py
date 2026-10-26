"""Kuluttajarepon regressiotapaukset: base, head, odotettu verdict (ja tier)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from portti.arviointi import arvioi
from portti.evidence import Konteksti
from portti.policy import Policy
from portti.verdict import VERDICTIT

SALLITUT_AVAIMET = {"nimi", "base", "head", "odotettu_verdict", "odotettu_tier"}
PAKOLLISET_AVAIMET = {"nimi", "base", "head", "odotettu_verdict"}


class TapausVirhe(ValueError):
    """Tapaustiedosto ei täytä muotoa."""


@dataclass(frozen=True)
class Tapaus:
    nimi: str
    base: str
    head: str
    odotettu_verdict: str
    odotettu_tier: str | None


@dataclass(frozen=True)
class TapausTulos:
    tapaus: Tapaus
    verdict: str
    tier: str

    @property
    def ok(self) -> bool:
        if self.verdict != self.tapaus.odotettu_verdict:
            return False
        return self.tapaus.odotettu_tier is None or self.tier == self.tapaus.odotettu_tier


def _tapaus(raaka: Any, indeksi: int) -> Tapaus:
    if not isinstance(raaka, dict):
        raise TapausVirhe(f"tapaus {indeksi}: odotettiin mappingia")
    tuntemattomat = set(raaka) - SALLITUT_AVAIMET
    if tuntemattomat:
        raise TapausVirhe(f"tapaus {indeksi}: tuntemattomat avaimet {sorted(tuntemattomat)}")
    puuttuvat = PAKOLLISET_AVAIMET - set(raaka)
    if puuttuvat:
        raise TapausVirhe(f"tapaus {indeksi}: puuttuvat avaimet {sorted(puuttuvat)}")
    if raaka["odotettu_verdict"] not in VERDICTIT:
        raise TapausVirhe(f"tapaus {indeksi}: tuntematon verdict {raaka['odotettu_verdict']!r}")
    return Tapaus(
        str(raaka["nimi"]), str(raaka["base"]), str(raaka["head"]),
        str(raaka["odotettu_verdict"]), raaka.get("odotettu_tier"),
    )


def lue_tapaukset(polku: Path) -> list[Tapaus]:
    sisalto = yaml.safe_load(polku.read_text(encoding="utf-8")) or {}
    if not isinstance(sisalto, dict) or set(sisalto) - {"tapaukset"}:
        raise TapausVirhe(f"{polku}: juuressa sallitaan vain avain 'tapaukset'")
    lista = sisalto.get("tapaukset") or []
    if not isinstance(lista, list):
        raise TapausVirhe(f"{polku}: 'tapaukset' on oltava lista")
    return [_tapaus(raaka, indeksi) for indeksi, raaka in enumerate(lista)]


def aja_tapaukset(repo_polku: Path, tapaukset: list[Tapaus], policy: Policy) -> list[TapausTulos]:
    tulokset: list[TapausTulos] = []
    for tapaus in tapaukset:
        konteksti = Konteksti("tapaus", None, tapaus.base, tapaus.head, None, "tapaukset")
        arvio = arvioi(repo_polku, tapaus.base, tapaus.head, policy, konteksti)
        tulokset.append(TapausTulos(tapaus, arvio.verdict.verdict, arvio.luokitus.tier))
    return tulokset


def muotoile_tulokset(tulokset: list[TapausTulos]) -> str:
    rivit = []
    for tulos in tulokset:
        merkki = "OK  " if tulos.ok else "EROAA"
        odotus = tulos.tapaus.odotettu_verdict
        if tulos.tapaus.odotettu_tier:
            odotus += f"/{tulos.tapaus.odotettu_tier}"
        rivit.append(f"{merkki} {tulos.tapaus.nimi}: odotettu {odotus}, saatu {tulos.verdict}/{tulos.tier}")
    return "\n".join(rivit)
