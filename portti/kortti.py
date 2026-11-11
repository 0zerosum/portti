"""Kortin metarivit: kuluttajarepon kortin (kortit/<slug>.md) rivien `- Avain: arvo` luku.

Moottori lukee kortista vain tilarivin ja mallirivin, esimerkiksi `- Tila: hyväksytty` ja `- Malli: fable`.
Metarivi on ylätason luettelorivi: `-` tai `*`, enintään kolme välilyöntiä sisennystä. Avain ei riipu
kirjainkoosta, ja arvosta luetaan pois sulkuhuomautus (`opus (oletus; ...)` on `opus`).

Kortin tilaa tai mallia ei arvata:
- Aidatun koodilohkon sisältö ei ole metatietoa. Aidat tulkitaan CommonMarkin mukaan: lohkon sulkee vain sama
  merkki vähintään yhtä pitkänä ilman lisätekstiä, ja sulkematon lohko jatkuu kortin loppuun.
- Rivi, joka näyttää saman avaimen metariviltä muussa muodossa (korostus, numerointi, muu luettelomerkki,
  tehtävälistan ruutu tai syvempi sisennys) tai HTML-kommentin sisällä, on virhe eikä ohitu.
- Sama avain kahdesti on virhe.
Kortin haara on `feature/<slug>`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
HAARAN_ETULIITE = "feature/"
TILA_HYVAKSYTTY = "hyväksytty"
AITA = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
KOMMENTIN_ALKU = "<!--"
KOMMENTIN_LOPPU = "-->"
LUETTELOMERKKI = r"(?:[-*+–—•]|\d+[.)])"
KOROSTUS = r"[*_`]"
RUUTU = r"(?:\[[ xX]?\]\s*)?"


class KorttiVirhe(ValueError):
    """Kortin metarivi on moniselitteinen tai väärässä muodossa."""


@dataclass(frozen=True)
class _Rivi:
    teksti: str
    koodilohkossa: bool
    kommentissa: bool


def normalisoi(arvo: str) -> str:
    """Arvo ilman sulkuhuomautusta, ympäröiviä välejä ja koodimerkkejä, pienaakkosin ja NFC-muodossa."""
    ilman_huomautusta = unicodedata.normalize("NFC", arvo).split("(", 1)[0]
    return ilman_huomautusta.strip().strip("`").strip().lower()


def _aidan_avaus(rivi: str) -> tuple[str, int] | None:
    """Avaavan aidan merkki ja pituus, tai None. Gravisaidan lisätekstissä ei saa olla gravista."""
    osuma = AITA.match(rivi)
    if osuma is None or (osuma.group(1)[0] == "`" and "`" in osuma.group(2)):
        return None
    return osuma.group(1)[0], len(osuma.group(1))


def _sulkee_aidan(rivi: str, aita: tuple[str, int]) -> bool:
    osuma = AITA.match(rivi)
    return osuma is not None and osuma.group(1)[0] == aita[0] and len(osuma.group(1)) >= aita[1] and not osuma.group(2).strip()


def _kommentin_loppu(teksti: str, alku: int, rivin_loppu: int, nykyinen: int) -> int:
    """Viimeisen tällä rivillä alkavan HTML-kommentin loppukohta; nykyinen, jos rivillä ei ala kommenttia.

    Kommentti päättyy seuraavaan `-->` (myös `<!-->` ja `<!--->` ovat valmiita kommentteja) tai kortin loppuun.
    """
    loppu = nykyinen
    kohta = teksti.find(KOMMENTIN_ALKU, alku, rivin_loppu)
    while kohta != -1:
        sulku = teksti.find(KOMMENTIN_LOPPU, kohta + 2)
        loppu = len(teksti) if sulku == -1 else sulku + len(KOMMENTIN_LOPPU)
        kohta = teksti.find(KOMMENTIN_ALKU, loppu, rivin_loppu)
    return loppu


def _rivit(kortin_teksti: str) -> list[_Rivi]:
    """Kortin rivit ja tieto siitä, onko rivi aidatussa koodilohkossa tai alkaako se HTML-kommentin sisältä.

    Koodilohkon sisällä `<!--` on tekstiä, ja kommentin sisällä aita ei avaa koodilohkoa.
    """
    teksti = unicodedata.normalize("NFC", kortin_teksti)
    rivit: list[_Rivi] = []
    aita: tuple[str, int] | None = None
    kommentin_loppu = 0
    alku = 0
    for raakarivi in teksti.splitlines(keepends=True):
        rivi = raakarivi.rstrip("\r\n")
        kommentissa = alku < kommentin_loppu
        avaus = None if kommentissa or aita is not None else _aidan_avaus(rivi)
        if aita is not None:
            rivit.append(_Rivi(rivi, True, False))
            aita = None if _sulkee_aidan(rivi, aita) else aita
        elif avaus is not None:
            rivit.append(_Rivi(rivi, True, False))
            aita = avaus
        else:
            rivit.append(_Rivi(rivi, False, kommentissa))
            kommentin_loppu = _kommentin_loppu(teksti, max(alku, kommentin_loppu), alku + len(rivi), kommentin_loppu)
        alku += len(raakarivi)
    return rivit


def _ehdokas(avain: str) -> re.Pattern[str]:
    """Rivi, joka näyttää avaimen metariviltä missä tahansa muodossa: luettelomerkki tai korostus ennen avainta."""
    alku = rf"(?:{LUETTELOMERKKI}\s*{RUUTU}{KOROSTUS}*|{KOROSTUS}+)"
    return re.compile(rf"^\s*{alku}\s*{re.escape(avain)}\s*{KOROSTUS}*\s*:", re.IGNORECASE)


def _kanoninen(avain: str) -> re.Pattern[str]:
    """Ainoa hyväksytty muoto: ylätason luettelorivi `- <avain>: <arvo>`."""
    return re.compile(rf"^ {{0,3}}[-*]\s*{re.escape(avain)}\s*:(.*)$", re.IGNORECASE)


def lue_kentta(kortin_teksti: str, avain: str) -> str | None:
    """Rivin `- <avain>: <arvo>` normalisoitu arvo, tai None, jos riviä ei ole.

    Kaksi riviä, avaimen rivi muussa kuin hyväksytyssä muodossa tai HTML-kommentin sisällä on KorttiVirhe.
    """
    ehdokas, kanoninen = _ehdokas(avain), _kanoninen(avain)
    arvot: list[str] = []
    for rivi in _rivit(kortin_teksti):
        if rivi.koodilohkossa or ehdokas.match(rivi.teksti) is None:
            continue
        if rivi.kommentissa:
            raise KorttiVirhe(f"kortin rivi {rivi.teksti.strip()!r} on HTML-kommentin sisällä; poista se tai kommentti")
        osuma = kanoninen.match(rivi.teksti)
        if osuma is None:
            raise KorttiVirhe(f"kortin rivi {rivi.teksti.strip()!r} ei ole muotoa '- {avain}: <arvo>' ylätason luettelorivinä")
        arvot.append(osuma.group(1))
    if len(arvot) > 1:
        raise KorttiVirhe(f"kortissa on {len(arvot)} riviä '- {avain}:'; rivejä saa olla yksi")
    return normalisoi(arvot[0]) if arvot else None


def kortin_tila(kortin_teksti: str) -> str | None:
    """Kortin tilarivin arvo, esimerkiksi `hyväksytty`, tai None, jos tilariviä ei ole."""
    return lue_kentta(kortin_teksti, "Tila")


def slug_haarasta(haara: str) -> str | None:
    """`feature/<slug>` on slug; muu haara tai kelvoton slug on None."""
    if not haara.startswith(HAARAN_ETULIITE):
        return None
    slug = haara[len(HAARAN_ETULIITE):]
    return slug if SLUG.match(slug) else None
