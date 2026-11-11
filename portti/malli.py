"""Mallin valinta kortti-ajolle: CTO:n mallipäätös 6.11.2026 deterministisenä funktiona.

Koodia, kortteja ja suunnitelmia ei kirjoiteta Sonnetilla eikä Haikulla. Oletus on Opus. Fable vain, kun
kortissa on kortin mukana hyväksytty rivi `- Malli: fable` tai ihminen valitsee sen käsin käynnistämässään
ajossa. Korjauskierros käyttää alkuperäisen ajon mallia. Tarkistaja on aina Opus. Mikä tahansa muu arvo on
virhe, eikä ajo käynnisty. Sallitut nimet ja tunnisteet ovat vain vakiossa SALLITUT_MALLIT.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from portti.kortti import KorttiVirhe, lue_kentta, normalisoi

OPUS = "opus"
FABLE = "fable"
SALLITUT_MALLIT: dict[str, str] = {
    OPUS: "claude-opus-5-5",
    FABLE: "claude-fable-5-1",
}
OLETUSNIMI = OPUS
TARKISTAJAN_NIMI = OPUS

LAHDE_OLETUS = "oletus"
LAHDE_KORTTI = "kortti"
LAHDE_KASIN = "käsin"
LAHDE_ALKUPERAINEN = "alkuperäinen ajo"


class MalliVirhe(ValueError):
    """Mallia ei sallita: ajo ei saa käynnistyä."""


@dataclass(frozen=True)
class Mallivalinta:
    nimi: str
    tunniste: str
    lahde: str


def sallittu_nimi(arvo: str, lahde: str) -> str:
    """Sallitun mallin nimi annetulle nimelle tai tunnisteelle. Muu arvo, myös tyhjä, on MalliVirhe."""
    puhdas = normalisoi(arvo)
    if not puhdas:
        raise MalliVirhe(f"malli on tyhjä ({lahde})")
    for nimi, tunniste in SALLITUT_MALLIT.items():
        if puhdas in (nimi, tunniste):
            return nimi
    sallitut = ", ".join(sorted({*SALLITUT_MALLIT, *SALLITUT_MALLIT.values()}))
    raise MalliVirhe(f"malli {arvo.strip()!r} ei ole sallittu ({lahde}); sallitut: {sallitut}")


def _valinta(nimi: str, lahde: str) -> Mallivalinta:
    return Mallivalinta(nimi, SALLITUT_MALLIT[nimi], lahde)


def _kortin_malli(kortin_teksti: str) -> str | None:
    """Kortin mallirivin sallittu nimi tai None, jos riviä ei ole. Kielletty tai tyhjä rivi on MalliVirhe."""
    try:
        arvo = lue_kentta(kortin_teksti, "Malli")
    except KorttiVirhe as virhe:
        raise MalliVirhe(str(virhe)) from virhe
    return None if arvo is None else sallittu_nimi(arvo, LAHDE_KORTTI)


def valitse_malli(kortin_teksti: str, kasin: str | None = None, alkuperainen: str | None = None) -> Mallivalinta:
    """Etusija: korjauskierroksen alkuperäinen malli, käsin valittu, kortin rivi, oletus.

    Kortin rivi tarkistetaan aina, kun se on olemassa: kortti, jossa on kielletty malli, ei käynnistä ajoa,
    vaikka malli annettaisiin muuta kautta.
    """
    if kasin is not None and alkuperainen is not None:
        raise MalliVirhe("käsin valittua mallia ei voi antaa korjauskierrokselle: se käyttää alkuperäisen ajon mallia")
    kortin_malli = _kortin_malli(kortin_teksti)
    if alkuperainen is not None:
        return _valinta(sallittu_nimi(alkuperainen, LAHDE_ALKUPERAINEN), LAHDE_ALKUPERAINEN)
    if kasin is not None:
        return _valinta(sallittu_nimi(kasin, LAHDE_KASIN), LAHDE_KASIN)
    if kortin_malli is not None:
        return _valinta(kortin_malli, LAHDE_KORTTI)
    return _valinta(OLETUSNIMI, LAHDE_OLETUS)


def valinta_sanakirjaksi(valinta: Mallivalinta) -> dict[str, Any]:
    """Kortti-ajon tarvitsemat tiedot: valittu malli, sen lähde, tarkistajan malli ja sallitut tunnisteet."""
    return {
        "malli": valinta.tunniste,
        "nimi": valinta.nimi,
        "lahde": valinta.lahde,
        "tarkistajan_malli": SALLITUT_MALLIT[TARKISTAJAN_NIMI],
        "sallitut_tunnisteet": sorted(set(SALLITUT_MALLIT.values())),
    }
