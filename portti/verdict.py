"""Verdict-sääntö koodissa, ei tulkintaa.

Järjestys: PUUTE > KOVA > LIIAN-ISO > PEHMEÄ > VAPAA.
Portaat: S0 hyväksyy T0:n, S1 lisäksi T1a:n, S2 T1b:n, S3 T1c:n.
"""

from __future__ import annotations

from dataclasses import dataclass

from portti.luokittelu import TIER_T0, TIER_YLI, Luokitus

PUUTE = "PUUTE"
KOVA = "KOVA"
LIIAN_ISO = "LIIAN-ISO"
PEHMEA = "PEHMEÄ"
VAPAA = "VAPAA"
VERDICTIT = (PUUTE, KOVA, LIIAN_ISO, PEHMEA, VAPAA)

PORTAAT = ("S0", "S1", "S2", "S3")
TIERIT_PORTAITTAIN = (TIER_T0, "T1a", "T1b", "T1c")


@dataclass(frozen=True)
class PortinTulos:
    nimi: str
    ok: bool
    syy: str


@dataclass(frozen=True)
class Verdict:
    verdict: str
    portit: list[PortinTulos]
    hyvaksyttavissa_portaalla: list[str]


def _portti_edellytykset(luokitus: Luokitus) -> PortinTulos:
    if luokitus.puutteet:
        return PortinTulos("edellytykset", False, "; ".join(luokitus.puutteet))
    return PortinTulos("edellytykset", True, "ei luonnos, ei konfliktia")


def _portti_kova_deny(luokitus: Luokitus) -> PortinTulos:
    osumat = luokitus.osumat_tasolla("kova")
    if osumat:
        kuvaus = ", ".join(f"{osuma.polku} ({osuma.kategoria})" for osuma in osumat)
        return PortinTulos("kova_deny", False, kuvaus)
    return PortinTulos("kova_deny", True, "ei osumia")


def _portti_kielletyt_uudet(luokitus: Luokitus) -> PortinTulos:
    if luokitus.kielletyt_uudet:
        kuvaus = ", ".join(f"{polku} ({malli})" for polku, malli in luokitus.kielletyt_uudet)
        return PortinTulos("kielletyt_uudet_polut", False, kuvaus)
    return PortinTulos("kielletyt_uudet_polut", True, "ei uusia kiellettyjä polkuja")


def _portti_invariantit(luokitus: Luokitus) -> PortinTulos:
    rikkoutuneet = [tulos for tulos in luokitus.invariantit if not tulos.ok]
    if rikkoutuneet:
        kuvaus = ", ".join(f"{tulos.polku}: {tulos.syy}" for tulos in rikkoutuneet)
        return PortinTulos("invariantit", False, kuvaus)
    return PortinTulos("invariantit", True, f"{len(luokitus.invariantit)} invarianttitestiä kunnossa")


def _portti_koko(luokitus: Luokitus) -> PortinTulos:
    kuvaus = (
        f"{luokitus.rivit} riviä, {len(luokitus.substantiiviset)} tiedostoa, "
        f"{len(luokitus.alueet)} aluetta -> {luokitus.tier}"
    )
    return PortinTulos("koko", luokitus.tier != TIER_YLI, kuvaus)


def _portti_pehmea_deny(luokitus: Luokitus) -> PortinTulos:
    osumat = luokitus.osumat_tasolla("pehmea")
    if osumat:
        kuvaus = ", ".join(f"{osuma.polku} ({osuma.kategoria})" for osuma in osumat)
        return PortinTulos("pehmea_deny", False, kuvaus)
    return PortinTulos("pehmea_deny", True, "ei osumia")


def _paattele(portit: dict[str, PortinTulos]) -> str:
    if not portit["edellytykset"].ok:
        return PUUTE
    kovat = ("kova_deny", "kielletyt_uudet_polut", "invariantit")
    if any(not portit[nimi].ok for nimi in kovat):
        return KOVA
    if not portit["koko"].ok:
        return LIIAN_ISO
    if not portit["pehmea_deny"].ok:
        return PEHMEA
    return VAPAA


def hyvaksyttavissa_portaalla(verdict: str, tier: str) -> list[str]:
    """Portaat, joilla PR olisi automaattisesti hyväksyttävissä."""
    if verdict == VAPAA and tier in TIERIT_PORTAITTAIN:
        alin = TIERIT_PORTAITTAIN.index(tier)
        return list(PORTAAT[alin:])
    if verdict == PEHMEA and tier == TIER_T0:
        return list(PORTAAT)
    return []


def laske_verdict(luokitus: Luokitus) -> Verdict:
    portit = [
        _portti_edellytykset(luokitus),
        _portti_kova_deny(luokitus),
        _portti_kielletyt_uudet(luokitus),
        _portti_invariantit(luokitus),
        _portti_koko(luokitus),
        _portti_pehmea_deny(luokitus),
    ]
    verdict = _paattele({portti.nimi: portti for portti in portit})
    return Verdict(verdict, portit, hyvaksyttavissa_portaalla(verdict, luokitus.tier))
