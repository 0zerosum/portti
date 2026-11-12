"""Kortin metarivit: kuluttajarepon kortin (kortit/<slug>.md) rivien `- Avain: arvo` luku.

Moottori lukee kortista vain tilarivin ja mallirivin, esimerkiksi `- Tila: hyväksytty` ja `- Malli: fable`.
Rivit luetaan kortin raakatekstistä, eikä Markdownin rakennetta tulkita:

- Metarivit ovat kortin alkuosassa: otsikon jälkeen, ennen ensimmäistä väliotsikkoa, vaakaviivaa tai riviä, joka
  voi avata koodilohkon, kaavan, HTML-lohkon tai kommentin. Alkuosan rivi ei siis voi olla sellaisen sisällä.
- Metarivi on ylätason luettelorivi: `-` tai `*`, enintään kolme välilyöntiä sisennystä. Avain ei riipu
  kirjainkoosta, ja arvosta luetaan pois sulkuhuomautus (`opus (oletus; ...)` on `opus`).
- Alkuosassa avaimen rivi muussa muodossa (korostus, numerointi, muu luettelomerkki, tehtävälistan ruutu tai
  syvempi sisennys) on virhe eikä ohitu, ja sama avain kahdesti on virhe: tilaa tai mallia ei arvata.
- Alkuosan jälkeistä tekstiä (runkoa) ei lueta metariveiksi. `rungon_arvot` palauttaa rungon avainrivien arvot,
  jotta kutsuja voi hylätä väärään paikkaan kirjoitetun rivin.
Kortin haara on `feature/<slug>`.
"""

from __future__ import annotations

import re
import unicodedata

SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
HAARAN_ETULIITE = "feature/"
TILA_HYVAKSYTTY = "hyväksytty"
LUETTELOMERKKI = r"(?:[-*+–—•]|\d+[.)])"
KOROSTUS = r"[*_`]"
RUUTU = r"(?:\[[ xX]?\]\s*)?"
OTSIKKO = re.compile(r"^ {0,3}#{1,6}(?:\s|$)")
VAAKAVIIVA = re.compile(r"^ {0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$")
# Rivi, joka voi avata koodilohkon (aita), kaavan ($$) tai HTML-lohkon, myös luettelon tai lainauksen sisällä.
RAKENTEEN_ALKU = re.compile(r"^[\s>*+\-]*(?:\d+[.)]\s*)?(?:`{3,}|~{3,}|\$\$|<[A-Za-z/!?])")
KOMMENTIN_ALKU = "<!--"


class KorttiVirhe(ValueError):
    """Kortin metarivi on moniselitteinen tai väärässä muodossa."""


def normalisoi(arvo: str) -> str:
    """Arvo ilman sulkuhuomautusta, ympäröiviä välejä ja koodimerkkejä, pienaakkosin ja NFC-muodossa."""
    ilman_huomautusta = unicodedata.normalize("NFC", arvo).split("(", 1)[0]
    return ilman_huomautusta.strip().strip("`").strip().lower()


def _paattaa_alkuosan(rivi: str, kortin_otsikko: bool) -> bool:
    """Päättääkö rivi kortin alkuosan. Kortin ensimmäinen rivi saa olla otsikko."""
    if KOMMENTIN_ALKU in rivi or RAKENTEEN_ALKU.match(rivi) or VAAKAVIIVA.match(rivi):
        return True
    return OTSIKKO.match(rivi) is not None and not kortin_otsikko


def _jaa(kortin_teksti: str) -> tuple[list[str], list[str]]:
    """Kortin alkuosan ja rungon rivit. Rivinvaihtoja ovat vain LF, CRLF ja CR, kuten Markdownissa."""
    teksti = unicodedata.normalize("NFC", kortin_teksti).lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    rivit = teksti.split("\n")
    ensimmainen = True
    for indeksi, rivi in enumerate(rivit):
        if not rivi.strip():
            continue
        if _paattaa_alkuosan(rivi, kortin_otsikko=ensimmainen):
            return rivit[:indeksi], rivit[indeksi:]
        ensimmainen = False
    return rivit, []


def _ehdokas(avain: str) -> re.Pattern[str]:
    """Rivi, joka näyttää avaimen metariviltä missä tahansa muodossa; ryhmä 1 on arvo kaksoispisteen jälkeen."""
    alku = rf"(?:{LUETTELOMERKKI}\s*{RUUTU}{KOROSTUS}*|{KOROSTUS}+)"
    return re.compile(rf"^\s*{alku}\s*{re.escape(avain)}\s*{KOROSTUS}*\s*:(.*)$", re.IGNORECASE)


def _kanoninen(avain: str) -> re.Pattern[str]:
    """Ainoa hyväksytty muoto: ylätason luettelorivi `- <avain>: <arvo>`."""
    return re.compile(rf"^ {{0,3}}[-*]\s*{re.escape(avain)}\s*:(.*)$", re.IGNORECASE)


def lue_kentta(kortin_teksti: str, avain: str) -> str | None:
    """Kortin alkuosan rivin `- <avain>: <arvo>` normalisoitu arvo, tai None, jos riviä ei ole.

    Kaksi riviä tai avaimen rivi muussa kuin hyväksytyssä muodossa on KorttiVirhe.
    """
    ehdokas, kanoninen = _ehdokas(avain), _kanoninen(avain)
    arvot: list[str] = []
    for rivi in _jaa(kortin_teksti)[0]:
        if ehdokas.match(rivi) is None:
            continue
        osuma = kanoninen.match(rivi)
        if osuma is None:
            raise KorttiVirhe(f"kortin rivi {rivi.strip()!r} ei ole muotoa '- {avain}: <arvo>' ylätason luettelorivinä")
        arvot.append(osuma.group(1))
    if len(arvot) > 1:
        raise KorttiVirhe(f"kortissa on {len(arvot)} riviä '- {avain}:'; rivejä saa olla yksi")
    return normalisoi(arvot[0]) if arvot else None


def rungon_arvot(kortin_teksti: str, avain: str) -> list[str]:
    """Kortin rungon (alkuosan jälkeisen tekstin) avainrivien normalisoidut arvot missä tahansa muodossa.

    Runkoa ei lueta metariveiksi, mutta kutsuja voi näistä todeta, että metarivi on kirjoitettu väärään paikkaan.
    """
    ehdokas = _ehdokas(avain)
    osumat = (ehdokas.match(rivi) for rivi in _jaa(kortin_teksti)[1])
    return [normalisoi(re.sub(KOROSTUS, "", osuma.group(1))) for osuma in osumat if osuma is not None]


def kortin_tila(kortin_teksti: str) -> str | None:
    """Kortin tilarivin arvo, esimerkiksi `hyväksytty`, tai None, jos tilariviä ei ole kortin alkuosassa."""
    return lue_kentta(kortin_teksti, "Tila")


def slug_haarasta(haara: str) -> str | None:
    """`feature/<slug>` on slug; muu haara tai kelvoton slug on None."""
    if not haara.startswith(HAARAN_ETULIITE):
        return None
    slug = haara[len(HAARAN_ETULIITE):]
    return slug if SLUG.match(slug) else None
