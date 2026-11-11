"""Kortin metarivit: kuluttajarepon kortin (kortit/<slug>.md) rivien `- Avain: arvo` luku.

Moottori lukee kortista vain tilarivin ja mallirivin, esimerkiksi `- Tila: hyväksytty` ja `- Malli: fable`.
Metarivi on ylätason luettelorivi: `-` tai `*`, enintään kolme välilyöntiä sisennystä. Avain ei riipu
kirjainkoosta, ja arvosta luetaan pois sulkuhuomautus (`opus (oletus; ...)` on `opus`).

Aidattujen koodilohkojen ja HTML-kommenttien sisältö ei ole kortin metatietoa: sieltä ei lueta mitään.
Rivi, joka näyttää saman avaimen metariviltä muussa muodossa (korostus, numerointi, muu luettelomerkki,
tehtävälistan ruutu tai syvempi sisennys), on virhe eikä ohitu: kortin tilaa tai mallia ei arvata.
Sama avain kahdesti on virhe. Kortin haara on `feature/<slug>`.
"""

from __future__ import annotations

import re
import unicodedata

SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
HAARAN_ETULIITE = "feature/"
TILA_HYVAKSYTTY = "hyväksytty"
HTML_KOMMENTTI = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
AITA = re.compile(r"^ {0,3}(`{3,}|~{3,})")
LUETTELOMERKKI = r"(?:[-*+–—•]|\d+[.)])"
KOROSTUS = r"[*_`]"
RUUTU = r"(?:\[[ xX]?\]\s*)?"


class KorttiVirhe(ValueError):
    """Kortin metarivi on moniselitteinen tai väärässä muodossa."""


def normalisoi(arvo: str) -> str:
    """Arvo ilman sulkuhuomautusta, ympäröiviä välejä ja koodimerkkejä, pienaakkosin ja NFC-muodossa."""
    ilman_huomautusta = unicodedata.normalize("NFC", arvo).split("(", 1)[0]
    return ilman_huomautusta.strip().strip("`").strip().lower()


def _metarivit(kortin_teksti: str) -> list[str]:
    """Kortin rivit ilman HTML-kommentteja ja aidattuja koodilohkoja. Sulkematon lohko jatkuu kortin loppuun."""
    rivit: list[str] = []
    aita: str | None = None
    for rivi in HTML_KOMMENTTI.sub("", unicodedata.normalize("NFC", kortin_teksti)).splitlines():
        osuma = AITA.match(rivi)
        merkki = osuma.group(1)[0] if osuma else None
        if aita is None and merkki is None:
            rivit.append(rivi)
        elif aita is None:
            aita = merkki
        elif merkki == aita:
            aita = None
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

    Kaksi riviä, tai avaimen rivi muussa kuin hyväksytyssä muodossa, on KorttiVirhe.
    """
    ehdokas, kanoninen = _ehdokas(avain), _kanoninen(avain)
    arvot: list[str] = []
    for rivi in _metarivit(kortin_teksti):
        if ehdokas.match(rivi) is None:
            continue
        osuma = kanoninen.match(rivi)
        if osuma is None:
            raise KorttiVirhe(f"kortin rivi {rivi.strip()!r} ei ole muotoa '- {avain}: <arvo>' ylätason luettelorivinä")
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
