"""Diffin luokittelu policyn mukaan: substantiiviset rivit, alueet, deny-osumat, tier."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from portti.git_diff import MuutettuTiedosto, lue_diff
from portti.invariantit import (
    InvarianttiTulos,
    TestiMaara,
    tarkista_invariantit,
    testimaara_muutoksille,
)
from portti.policy import DenyKategoria, Policy
from portti.polkumallit import ensimmainen_osuma, saanto_osuu

TIER_T0 = "T0"
TIER_YLI = "YLI"
JUURIALUE = "(juuri)"


@dataclass(frozen=True)
class DenyOsuma:
    kategoria: str
    taso: str
    polku: str
    malli: str


@dataclass(frozen=True)
class Edellytykset:
    draft: bool = False
    konflikti: bool = False

    @property
    def puutteet(self) -> list[str]:
        puutteet: list[str] = []
        if self.draft:
            puutteet.append("PR on luonnos")
        if self.konflikti:
            puutteet.append("PR on konfliktissa")
        return puutteet


@dataclass(frozen=True)
class Luokitus:
    tiedostot: list[MuutettuTiedosto]
    substantiiviset: list[str]
    rivit: int
    alueet: list[str]
    deny_osumat: list[DenyOsuma]
    kielletyt_uudet: list[tuple[str, str]]
    tier: str
    invariantit: list[InvarianttiTulos]
    testimaara: TestiMaara | None
    puutteet: list[str] = field(default_factory=list)

    def osumat_tasolla(self, taso: str) -> list[DenyOsuma]:
        return [osuma for osuma in self.deny_osumat if osuma.taso == taso]


def alue(polku: str, prefiksit: tuple[str, ...]) -> str:
    """Prefiksin alla seuraava kansio; muuten polun kaksi ensimmäistä hakemistotasoa."""
    for prefiksi in prefiksit:
        if polku.startswith(prefiksi):
            loppu = polku[len(prefiksi):].split("/")
            return prefiksi + loppu[0] if len(loppu) > 1 else prefiksi.rstrip("/")
    osat = polku.split("/")
    if len(osat) == 1:
        return JUURIALUE
    return "/".join(osat[: min(2, len(osat) - 1)])


def _deny_osumat(tiedostot: list[MuutettuTiedosto], kategoriat: tuple[DenyKategoria, ...]) -> list[DenyOsuma]:
    osumat: list[DenyOsuma] = []
    for tiedosto in tiedostot:
        polut = [tiedosto.polku] + ([tiedosto.vanha_polku] if tiedosto.vanha_polku else [])
        for kategoria in kategoriat:
            for polku in polut:
                malli = ensimmainen_osuma(polku, kategoria.polut)
                if malli is not None:
                    osumat.append(DenyOsuma(kategoria.nimi, kategoria.taso, polku, malli))
                    break
    return osumat


def _kielletyt_uudet(tiedostot: list[MuutettuTiedosto], mallit: tuple[str, ...]) -> list[tuple[str, str]]:
    osumat: list[tuple[str, str]] = []
    for tiedosto in tiedostot:
        if not tiedosto.on_uusi_polku:
            continue
        malli = ensimmainen_osuma(tiedosto.polku, mallit)
        if malli is not None:
            osumat.append((tiedosto.polku, malli))
    return osumat


def on_testi(polku: str, policy: Policy) -> bool:
    if polku in policy.invarianttitestit:
        return False
    return ensimmainen_osuma(polku, policy.testit) is not None


def on_laskennan_ulkopuolella(polku: str, policy: Policy) -> bool:
    return on_testi(polku, policy) or saanto_osuu(polku, policy.ei_laskennassa) is not None


def _valitse_tier(rivit: int, tiedostot: int, alueet: int, policy: Policy) -> str:
    for tier in policy.tiers:
        if rivit <= tier.max_rivit and tiedostot <= tier.max_tiedostot and alueet <= tier.max_alueet:
            return tier.nimi
    return TIER_YLI


def _on_vapaa_tiedosto(tiedosto: MuutettuTiedosto, policy: Policy) -> bool:
    return on_testi(tiedosto.polku, policy) or saanto_osuu(tiedosto.polku, policy.allow) is not None


def _substantiiviset(
    tiedostot: list[MuutettuTiedosto], policy: Policy, testit_laskentaan: bool
) -> list[MuutettuTiedosto]:
    valitut: list[MuutettuTiedosto] = []
    for tiedosto in tiedostot:
        if testit_laskentaan and on_testi(tiedosto.polku, policy):
            valitut.append(tiedosto)
        elif not on_laskennan_ulkopuolella(tiedosto.polku, policy):
            valitut.append(tiedosto)
    return valitut


def _tier(tiedostot: list[MuutettuTiedosto], substantiiviset: list[MuutettuTiedosto], alueet: list[str], policy: Policy) -> str:
    if not substantiiviset and all(_on_vapaa_tiedosto(tiedosto, policy) for tiedosto in tiedostot):
        return TIER_T0
    rivit = sum(tiedosto.rivit for tiedosto in substantiiviset)
    return _valitse_tier(rivit, len(substantiiviset), len(alueet), policy)


def luokittele(
    repo: Path, base: str, head: str, policy: Policy, edellytykset: Edellytykset = Edellytykset()
) -> Luokitus:
    """Laskee diffin faktat. Ei tulkintaa: verdict tehdään erikseen."""
    tiedostot = lue_diff(repo, base, head)
    testit = [tiedosto for tiedosto in tiedostot if on_testi(tiedosto.polku, policy)]
    testimaara = testimaara_muutoksille(repo, base, head, testit) if testit else None
    testit_laskentaan = testimaara is not None and testimaara.laskee
    substantiiviset = _substantiiviset(tiedostot, policy, testit_laskentaan)
    alueet = sorted({alue(tiedosto.polku, policy.alueprefiksit) for tiedosto in substantiiviset})
    return Luokitus(
        tiedostot=tiedostot,
        substantiiviset=[tiedosto.polku for tiedosto in substantiiviset],
        rivit=sum(tiedosto.rivit for tiedosto in substantiiviset),
        alueet=alueet,
        deny_osumat=_deny_osumat(tiedostot, policy.kova + policy.pehmea),
        kielletyt_uudet=_kielletyt_uudet(tiedostot, policy.kielletyt_uudet_polut),
        tier=_tier(tiedostot, substantiiviset, alueet, policy),
        invariantit=tarkista_invariantit(repo, base, head, policy.invarianttitestit),
        testimaara=testimaara,
        puutteet=edellytykset.puutteet,
    )
