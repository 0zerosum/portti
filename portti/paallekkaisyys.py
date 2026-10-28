"""Päällekkäisyystarkistus: allow-polku ei saa leikata deny-polkua.

Miksi: pehmeä polku, joka on myös T0-listalla, saa verdictin PEHMEÄ tierillä T0 ja olisi
hyväksyttävissä kaikilla portailla. Tarkistus on mallitasolla: sama literaalipolku tai glob, joka
sisältyy toiseen. Poikkeuslista (`paitsi`) poistaa leikkauksen. Kutsuja päättää, mitkä säännöt
tarkistetaan (policy.py: vain allow).
"""

from __future__ import annotations

from portti.polkumallit import PolkuSaanto, vastaa

JOKERIT = "*?"


def on_literaali(malli: str) -> bool:
    return not any(merkki in malli for merkki in JOKERIT)


def edustaja(malli: str) -> str:
    """Konkreettinen polku, joka osuu malliin: jokerit korvataan nimillä."""
    tulos = malli
    tulos = tulos.replace("**/", "a/").replace("/**", "/a/b").replace("**", "a/b")
    tulos = tulos.replace("*", "a").replace("?", "a")
    return tulos


def sisaltyy(sisempi: str, ulompi: str) -> bool:
    """Sisältyykö sisempi malli ulompaan: sama malli, tai ulompi osuu sisemmän edustajaan."""
    if sisempi == ulompi:
        return True
    kohde = sisempi if on_literaali(sisempi) else edustaja(sisempi)
    return vastaa(kohde, ulompi)


def leikkaavat(malli_a: str, malli_b: str) -> bool:
    return sisaltyy(malli_a, malli_b) or sisaltyy(malli_b, malli_a)


def poikkeus_kattaa(deny_polku: str, paitsi: tuple[str, ...]) -> bool:
    return any(sisaltyy(deny_polku, poikkeus) for poikkeus in paitsi)


def etsi_leikkaukset(
    deny_polut: list[tuple[str, str, str]], saannot: dict[str, PolkuSaanto]
) -> list[str]:
    """deny_polut: (taso, kategoria, polku). saannot: nimi -> PolkuSaanto. Palauttaa virherivit."""
    virheet: list[str] = []
    for taso, kategoria, deny_polku in deny_polut:
        for nimi, saanto in saannot.items():
            if poikkeus_kattaa(deny_polku, saanto.paitsi):
                continue
            for sallittu in saanto.polut:
                if leikkaavat(deny_polku, sallittu):
                    virheet.append(
                        f"deny {taso}/{kategoria} polku '{deny_polku}' leikkaa {nimi}-polun '{sallittu}'; "
                        f"lisää '{deny_polku}' listaan {nimi}.laajenna_paitsi"
                    )
    return virheet
