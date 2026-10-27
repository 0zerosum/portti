"""Shadow-raportin data: portin verdict vs. PR:n lopputulos, ryhmiteltynä base-haaran mukaan.

Evidence luetaan kommentin konedatasta: se säilyy PR:n mukana ja on sama jokaisella lukukerralla,
toisin kuin artefakti, joka vanhenee. Vanhemmat kommentit (ennen 0.3.0) eivät sisällä kategorioita
eivätkä portaita; ne näkyvät raportissa tyhjinä. Ei tallenna mitään.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from portti.github_api import GitHubApi
from portti.kommentti import lue_konedata
from portti.verdict import KOVA, PEHMEA, PORTAAT, VAPAA

MERGETTY_MUUTTAMATTA = "mergetty muuttamatta"
MERGETTY_MUUTOSTEN_JALKEEN = "mergetty muutosten jälkeen"
SULJETTU = "suljettu"
EI_KOMMENTTIA = "ei portin kommenttia"
RYHMA_MAIN = "main"
RYHMA_FEAT = "feat/*"
EI_PORTAITA = "ei millään"


@dataclass(frozen=True)
class ShadowRivi:
    repo: str
    pr_numero: int
    base_haara: str
    verdict: str | None
    tier: str | None
    kategoriat: tuple[str, ...]
    portaat: tuple[str, ...]
    lopputulos: str


@dataclass
class ShadowRyhma:
    nimi: str
    rivit: list[ShadowRivi] = field(default_factory=list)

    @property
    def kova_tai_pehmea_mutta_mergetty_muuttamatta(self) -> int:
        return len(self._vaarat_pysaytykset())

    @property
    def vapaa_mutta_hylatty(self) -> int:
        return sum(1 for rivi in self.rivit if rivi.verdict == VAPAA and rivi.lopputulos == SULJETTU)

    def vaarat_osumat_kategorioittain(self) -> dict[str, int]:
        laskuri: Counter[str] = Counter()
        for rivi in self._vaarat_pysaytykset():
            laskuri.update(rivi.kategoriat or ("ei tiedossa",))
        return dict(sorted(laskuri.items()))

    def jakauma_tiereittain(self) -> dict[str, int]:
        return dict(sorted(Counter(rivi.tier or "ei tiedossa" for rivi in self.rivit).items()))

    def jakauma_portaittain(self) -> dict[str, int]:
        laskuri: Counter[str] = Counter({porras: 0 for porras in PORTAAT})
        laskuri[EI_PORTAITA] = 0
        for rivi in self.rivit:
            if rivi.verdict is None:
                continue
            if rivi.portaat:
                laskuri.update(rivi.portaat)
            else:
                laskuri[EI_PORTAITA] += 1
        return dict(laskuri)

    def _vaarat_pysaytykset(self) -> list[ShadowRivi]:
        return [rivi for rivi in self.rivit
                if rivi.verdict in (KOVA, PEHMEA) and rivi.lopputulos == MERGETTY_MUUTTAMATTA]


@dataclass
class ShadowRaportti:
    repot: list[str]
    alkaen: str
    ryhmat: dict[str, ShadowRyhma]
    pudotetut_draftit: int


def ryhma_haaralle(base_haara: str) -> str:
    """main erikseen, feat/* ja feature/* yhdessä, muut omanaan."""
    if base_haara in ("main", "master"):
        return RYHMA_MAIN
    if base_haara.startswith(("feat/", "feature/")):
        return RYHMA_FEAT
    return base_haara


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


def _rivi(repo: str, pr: dict[str, Any], konedata: dict[str, Any] | None) -> ShadowRivi:
    return ShadowRivi(
        repo=repo,
        pr_numero=int(pr["number"]),
        base_haara=str(pr.get("baseRefName") or "?"),
        verdict=konedata.get("verdict") if konedata else None,
        tier=konedata.get("tier") if konedata else None,
        kategoriat=tuple(konedata.get("deny_kategoriat", [])) if konedata else (),
        portaat=tuple(konedata.get("portaat", [])) if konedata else (),
        lopputulos=_lopputulos(pr, konedata),
    )


def kokoa_shadow_raportti(api: GitHubApi, repot: list[str], alkaen: str) -> ShadowRaportti:
    ryhmat: dict[str, ShadowRyhma] = {}
    draftit = 0
    for repo in repot:
        for pr in sorted(api.hae_suljetut_prt(repo, alkaen), key=lambda pr: int(pr["number"])):
            if pr.get("isDraft"):
                draftit += 1
                continue
            konedata = _portin_konedata(api.hae_kommentit(repo, int(pr["number"])))
            rivi = _rivi(repo, pr, konedata)
            ryhmat.setdefault(ryhma_haaralle(rivi.base_haara), ShadowRyhma(ryhma_haaralle(rivi.base_haara))).rivit.append(rivi)
    jarjestetyt = dict(sorted(ryhmat.items(), key=lambda pari: (pari[0] != RYHMA_MAIN, pari[0] != RYHMA_FEAT, pari[0])))
    return ShadowRaportti(list(repot), alkaen, jarjestetyt, draftit)
