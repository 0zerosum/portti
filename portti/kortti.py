"""Kortin metarivit: kuluttajarepon kortin (kortit/<slug>.md) rivien `- Avain: arvo` luku.

Moottori lukee kortista vain tilarivin ja mallirivin, esimerkiksi `- Tila: hyväksytty` ja `- Malli: fable`.
Avain ei riipu kirjainkoosta, ja arvosta luetaan pois sulkuhuomautus (`opus (oletus; ...)` on `opus`).
Sama avain kahdesti on virhe: arvoa ei arvata. Kortin haara on `feature/<slug>`.
"""

from __future__ import annotations

import re
import unicodedata

SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
HAARAN_ETULIITE = "feature/"
TILA_HYVAKSYTTY = "hyväksytty"


class KorttiVirhe(ValueError):
    """Kortin metarivi on moniselitteinen."""


def normalisoi(arvo: str) -> str:
    """Arvo ilman sulkuhuomautusta, ympäröiviä välejä ja koodimerkkejä, pienaakkosin ja NFC-muodossa."""
    ilman_huomautusta = unicodedata.normalize("NFC", arvo).split("(", 1)[0]
    return ilman_huomautusta.strip().strip("`").strip().lower()


def lue_kentta(kortin_teksti: str, avain: str) -> str | None:
    """Rivin `- <avain>: <arvo>` normalisoitu arvo, tai None, jos riviä ei ole. Kaksi riviä on KorttiVirhe."""
    rivin_malli = re.compile(rf"^\s*[-*]\s*{re.escape(avain)}\s*:(.*)$", re.IGNORECASE)
    osumat = [rivin_malli.match(rivi) for rivi in unicodedata.normalize("NFC", kortin_teksti).splitlines()]
    arvot = [osuma.group(1) for osuma in osumat if osuma is not None]
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
