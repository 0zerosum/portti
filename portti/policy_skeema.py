"""Policyn tiukka skeema.

Skeema on puu: mapping -> {avain: alaskeema}, lista -> [alkiotyyppi],
skalaari -> tyyppi. `KATEGORIAT` on vapaanimisten deny-kategorioiden mapping.
Repon policyssa sallitaan lisäksi `laajenna_<avain>` jokaiselle lista-avaimelle.
"""

from __future__ import annotations

from typing import Any

LAAJENNA = "laajenna_"
SUOJATTU_KATEGORIA = "portti_itse"


class PolicyVirhe(ValueError):
    """Policy ei täytä skeemaa tai rikkoo suojattua sääntöä."""


class _Kategoriat:
    """Merkki: vapaanimisten deny-kategorioiden mapping."""


KATEGORIA = {"polut": [str], "perustelu": str}
TIER = {"max_rivit": int, "max_tiedostot": int, "max_alueet": int}
POLKUSAANTO = {"polut": [str], "paitsi": [str]}

SKEEMA: dict[str, Any] = {
    "versio": int,
    "lukkotiedostot": [str],
    "deny": {"kova": _Kategoriat, "pehmea": _Kategoriat},
    "kielletyt_uudet_polut": [str],
    "allow": POLKUSAANTO,
    "ei_laskennassa": POLKUSAANTO,
    "testit": [str],
    "generoidut": [str],
    "size_gate": {"max_rivit": int, "max_tiedostot": int},
    "tiers": {"T1a": TIER, "T1b": TIER, "T1c": TIER},
    "alueen_maaritys": {"prefiksit": [str]},
    "invarianttitestit": [str],
}


def _virhe(polku: str, viesti: str) -> PolicyVirhe:
    return PolicyVirhe(f"policy {polku or '(juuri)'}: {viesti}")


def _tarkista_lista(arvo: Any, alkiotyyppi: type, polku: str) -> None:
    if not isinstance(arvo, list):
        raise _virhe(polku, f"odotettiin listaa, saatiin {type(arvo).__name__}")
    for indeksi, alkio in enumerate(arvo):
        if not isinstance(alkio, alkiotyyppi) or isinstance(alkio, bool):
            raise _virhe(f"{polku}[{indeksi}]", f"odotettiin {alkiotyyppi.__name__}")


def _tarkista_skalaari(arvo: Any, tyyppi: type, polku: str) -> None:
    if isinstance(arvo, bool) or not isinstance(arvo, tyyppi):
        raise _virhe(polku, f"odotettiin {tyyppi.__name__}, saatiin {type(arvo).__name__}")


def _ratkaise_alaskeema(avain: str, skeema: dict[str, Any], polku: str, repo: bool) -> Any:
    if avain in skeema:
        return skeema[avain]
    if repo and avain.startswith(LAAJENNA):
        perusavain = avain[len(LAAJENNA):]
        if perusavain in skeema and isinstance(skeema[perusavain], list):
            return skeema[perusavain]
    raise _virhe(f"{polku}.{avain}".lstrip("."), "tuntematon avain")


def _tarkista_kategoriat(arvo: Any, polku: str, repo: bool) -> None:
    if not isinstance(arvo, dict):
        raise _virhe(polku, "deny-tason on oltava mapping kategorioista")
    for nimi, kategoria in arvo.items():
        if not isinstance(nimi, str):
            raise _virhe(polku, "kategorian nimen on oltava merkkijono")
        if repo and nimi == SUOJATTU_KATEGORIA:
            raise _virhe(f"{polku}.{nimi}", "suojattua kategoriaa ei saa korvata repon policyssa")
        tarkista(kategoria, KATEGORIA, f"{polku}.{nimi}", repo)


def tarkista(arvo: Any, skeema: Any, polku: str = "", repo: bool = False) -> None:
    """Tarkistaa arvon skeemaa vasten. Repon policy saa olla osittainen."""
    if skeema is _Kategoriat:
        _tarkista_kategoriat(arvo, polku, repo)
    elif isinstance(skeema, dict):
        if not isinstance(arvo, dict):
            raise _virhe(polku, f"odotettiin mappingia, saatiin {type(arvo).__name__}")
        for avain, aliarvo in arvo.items():
            if not isinstance(avain, str):
                raise _virhe(polku, "avaimen on oltava merkkijono")
            alaskeema = _ratkaise_alaskeema(avain, skeema, polku, repo)
            tarkista(aliarvo, alaskeema, f"{polku}.{avain}".lstrip("."), repo)
    elif isinstance(skeema, list):
        _tarkista_lista(arvo, skeema[0], polku)
    else:
        _tarkista_skalaari(arvo, skeema, polku)


def tarkista_pakolliset(yhdistetty: dict[str, Any]) -> None:
    """Yhdistetyssä policyssa on oltava kaikki juuritason avaimet ja suojattu kategoria."""
    puuttuvat = [avain for avain in SKEEMA if avain not in yhdistetty]
    if puuttuvat:
        raise PolicyVirhe(f"policy: puuttuvat avaimet {', '.join(puuttuvat)}")
    kova = yhdistetty["deny"].get("kova", {})
    if SUOJATTU_KATEGORIA not in kova or not kova[SUOJATTU_KATEGORIA].get("polut"):
        raise PolicyVirhe(f"policy: kova-kategoria {SUOJATTU_KATEGORIA} puuttuu")
