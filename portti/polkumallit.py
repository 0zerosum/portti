"""Gitignore-tyyliset polkumallit.

Mallin säännöt:
- `*` vastaa mitä tahansa paitsi kauttaviivaa, `?` yhtä merkkiä.
- `**/` alussa tai kauttaviivan jälkeen vastaa nollaa tai useampaa hakemistoa.
- `/**` lopussa vastaa kaikkea hakemiston alla.
- Malli ilman kauttaviivaa vastaa tiedostonimeä millä tahansa syvyydellä.
- Malli, jossa on kauttaviiva, ankkuroidaan repon juureen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class PolkuSaanto:
    """Lista malleja ja lista poikkeuksia, joita ei lasketa osumiksi."""

    polut: tuple[str, ...] = ()
    paitsi: tuple[str, ...] = field(default=())

    @classmethod
    def luo(cls, polut: list[str], paitsi: list[str] | None = None) -> "PolkuSaanto":
        return cls(tuple(polut), tuple(paitsi or []))


def _kaanna_osa(malli: str) -> str:
    osat: list[str] = []
    indeksi = 0
    while indeksi < len(malli):
        merkki = malli[indeksi]
        if malli.startswith("**/", indeksi) and (indeksi == 0 or malli[indeksi - 1] == "/"):
            osat.append("(?:.*/)?")
            indeksi += 3
        elif malli.startswith("/**", indeksi) and indeksi + 3 == len(malli):
            osat.append("(?:/.*)?")
            indeksi += 3
        elif malli.startswith("**", indeksi):
            osat.append(".*")
            indeksi += 2
        elif merkki == "*":
            osat.append("[^/]*")
            indeksi += 1
        elif merkki == "?":
            osat.append("[^/]")
            indeksi += 1
        else:
            osat.append(re.escape(merkki))
            indeksi += 1
    return "".join(osat)


@lru_cache(maxsize=4096)
def malli_regexiksi(malli: str) -> re.Pattern[str]:
    """Kääntää yhden polkumallin kokonaisvastaavuuden regexiksi."""
    puhdas = malli.strip()
    if not puhdas:
        raise ValueError("tyhjä polkumalli")
    ankkuroitu = puhdas.startswith("/")
    runko = puhdas.lstrip("/").rstrip("/")
    sisaltaa_kauttaviivan = "/" in runko
    kaannos = _kaanna_osa(runko)
    if not ankkuroitu and not sisaltaa_kauttaviivan:
        kaannos = "(?:.*/)?" + kaannos
    return re.compile("^" + kaannos + "$")


def vastaa(polku: str, malli: str) -> bool:
    """Vastaako polku yhtä mallia."""
    return malli_regexiksi(malli).match(polku) is not None


def ensimmainen_osuma(polku: str, mallit: tuple[str, ...] | list[str]) -> str | None:
    """Palauttaa ensimmäisen mallin, johon polku osuu, tai None."""
    for malli in mallit:
        if vastaa(polku, malli):
            return malli
    return None


def saanto_osuu(polku: str, saanto: PolkuSaanto) -> str | None:
    """Palauttaa osuneen mallin, ellei polku kuulu sääntöön `paitsi`-listan kautta."""
    osuma = ensimmainen_osuma(polku, saanto.polut)
    if osuma is None:
        return None
    if ensimmainen_osuma(polku, saanto.paitsi) is not None:
        return None
    return osuma
