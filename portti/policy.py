"""Policyn lataus: oletus + repon policy yhdistettynä, tyypitetty Policy-olio."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from portti.paallekkaisyys import etsi_leikkaukset
from portti.policy_skeema import LAAJENNA, SKEEMA, PolicyVirhe, tarkista, tarkista_pakolliset
from portti.polkumallit import PolkuSaanto

OLETUSPOLICY = Path(__file__).resolve().parent.parent / "defaults" / "policy.yml"


@dataclass(frozen=True)
class DenyKategoria:
    nimi: str
    taso: str
    polut: tuple[str, ...]
    perustelu: str | None


@dataclass(frozen=True)
class TierRaja:
    nimi: str
    max_rivit: int
    max_tiedostot: int
    max_alueet: int


@dataclass(frozen=True)
class Policy:
    kova: tuple[DenyKategoria, ...]
    pehmea: tuple[DenyKategoria, ...]
    kielletyt_uudet_polut: tuple[str, ...]
    allow: PolkuSaanto
    ei_laskennassa: PolkuSaanto
    testit: tuple[str, ...]
    invarianttitestit: tuple[str, ...]
    size_gate_max_rivit: int
    size_gate_max_tiedostot: int
    tiers: tuple[TierRaja, ...]
    alueprefiksit: tuple[str, ...]
    oletuksen_sha: str
    repon_sha: str | None


def lue_yaml(polku: Path) -> dict[str, Any]:
    try:
        sisalto = yaml.safe_load(polku.read_text(encoding="utf-8"))
    except yaml.YAMLError as virhe:
        raise PolicyVirhe(f"policy {polku}: YAML-virhe: {virhe}") from virhe
    if sisalto is None:
        return {}
    if not isinstance(sisalto, dict):
        raise PolicyVirhe(f"policy {polku}: juuren on oltava mapping")
    return sisalto


def tiedoston_sha256(polku: Path) -> str:
    return hashlib.sha256(polku.read_bytes()).hexdigest()


def yhdista(oletus: dict[str, Any], repo: dict[str, Any]) -> dict[str, Any]:
    """Avain kerrallaan: mapping yhdistyy, lista korvautuu, `laajenna_x` lisää listaan x."""
    tulos: dict[str, Any] = dict(oletus)
    for avain, arvo in repo.items():
        if avain.startswith(LAAJENNA):
            perusavain = avain[len(LAAJENNA):]
            tulos[perusavain] = list(tulos.get(perusavain, [])) + list(arvo)
        elif isinstance(arvo, dict) and isinstance(tulos.get(avain), dict):
            tulos[avain] = yhdista(tulos[avain], arvo)
        else:
            tulos[avain] = arvo
    return tulos


def _kategoriat(taso: str, mapping: dict[str, Any]) -> tuple[DenyKategoria, ...]:
    return tuple(
        DenyKategoria(nimi, taso, tuple(arvo.get("polut", [])), arvo.get("perustelu"))
        for nimi, arvo in mapping.items()
    )


def _tierit(mapping: dict[str, Any]) -> tuple[TierRaja, ...]:
    return tuple(
        TierRaja(nimi, raja["max_rivit"], raja["max_tiedostot"], raja["max_alueet"])
        for nimi, raja in mapping.items()
    )


def _ei_laskennassa(yhdistetty: dict[str, Any]) -> PolkuSaanto:
    polut = list(yhdistetty["ei_laskennassa"]["polut"]) + list(yhdistetty["generoidut"])
    return PolkuSaanto.luo(polut, yhdistetty["ei_laskennassa"]["paitsi"])


def tarkista_paallekkaisyydet(policy: Policy) -> None:
    """allow- tai ei_laskennassa-polku ei saa leikata kova- tai pehmea-polkua (T0-aukko)."""
    deny_polut = [
        (kategoria.taso, kategoria.nimi, polku)
        for kategoria in policy.kova + policy.pehmea
        for polku in kategoria.polut
    ]
    virheet = etsi_leikkaukset(deny_polut, {"allow": policy.allow, "ei_laskennassa": policy.ei_laskennassa})
    if virheet:
        raise PolicyVirhe("policy: päällekkäiset polut:\n  " + "\n  ".join(virheet))


def rakenna_policy(yhdistetty: dict[str, Any], oletuksen_sha: str, repon_sha: str | None) -> Policy:
    tarkista_pakolliset(yhdistetty)
    policy = Policy(
        kova=_kategoriat("kova", yhdistetty["deny"]["kova"]),
        pehmea=_kategoriat("pehmea", yhdistetty["deny"]["pehmea"]),
        kielletyt_uudet_polut=tuple(yhdistetty["kielletyt_uudet_polut"]),
        allow=PolkuSaanto.luo(yhdistetty["allow"]["polut"], yhdistetty["allow"]["paitsi"]),
        ei_laskennassa=_ei_laskennassa(yhdistetty),
        testit=tuple(yhdistetty["testit"]),
        invarianttitestit=tuple(yhdistetty["invarianttitestit"]),
        size_gate_max_rivit=yhdistetty["size_gate"]["max_rivit"],
        size_gate_max_tiedostot=yhdistetty["size_gate"]["max_tiedostot"],
        tiers=_tierit(yhdistetty["tiers"]),
        alueprefiksit=tuple(yhdistetty["alueen_maaritys"]["prefiksit"]),
        oletuksen_sha=oletuksen_sha,
        repon_sha=repon_sha,
    )
    tarkista_paallekkaisyydet(policy)
    return policy


def lataa_policy(repon_policy: Path | None, oletus: Path = OLETUSPOLICY) -> Policy:
    """Lataa oletuspolicyn ja repon policyn (jos annettu ja olemassa) ja yhdistää ne."""
    oletusdata = lue_yaml(oletus)
    tarkista(oletusdata, SKEEMA, repo=False)
    repodata: dict[str, Any] = {}
    repon_sha: str | None = None
    if repon_policy is not None and repon_policy.exists():
        repodata = lue_yaml(repon_policy)
        tarkista(repodata, SKEEMA, repo=True)
        repon_sha = tiedoston_sha256(repon_policy)
    yhdistetty = yhdista(oletusdata, repodata)
    tarkista(yhdistetty, SKEEMA, repo=False)
    return rakenna_policy(yhdistetty, tiedoston_sha256(oletus), repon_sha)
