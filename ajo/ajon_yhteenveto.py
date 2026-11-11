"""Kortti-ajon yhteenveto: malli, kortti, kesto, tokenit ja kulu actionin suoritustiedostosta.

Erillinen komponentti, ei osa portti-pakettia: ajetaan `python -I` kuluttajan ajossa. Vain vakiokirjasto.
Kirjoittaa yhteenvedon työnkulun yhteenvetoon ja lisää rivin PR:n kuvauksen merkittyyn lohkoon. Palauttaa 1,
jos ajo käytti mallia, joka ei ole sallittujen tunnisteiden joukossa: tarkistus havaitsee, ei estä.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

LOHKON_ALKU = "<!-- portti-ajot:alku -->"
LOHKON_LOPPU = "<!-- portti-ajot:loppu -->"
TAULUKON_OTSIKKO = (
    "**Kortti-ajot**",
    "",
    "| Ajo | Malli | Mallin lähde | Kesto | Kierroksia | Tokenit sisään / ulos | Kulu USD | Käytetyt mallit |",
    "|---|---|---|---|---|---|---|---|",
)
EI_TIETOA = "ei tietoa"
SISAAN_AVAIMET = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
SISAAN_AVAIMET_YHTEENSA = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def lue_tulos(suoritus: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Suoritustiedoston viimeinen result-viesti ja huomautus, jos sitä ei saatu."""
    if not suoritus.is_file():
        return None, "suoritustiedostoa ei ole: agentti ei ajanut tai action ei kirjoittanut sitä"
    try:
        viestit = json.loads(suoritus.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as virhe:
        return None, f"suoritustiedostoa ei voitu lukea: {virhe}"
    tulokset = [viesti for viesti in viestit if isinstance(viesti, dict) and viesti.get("type") == "result"] \
        if isinstance(viestit, list) else []
    if not tulokset:
        return None, "suoritustiedostossa ei ole tulosviestiä"
    return tulokset[-1], None


def kaytetyt_mallit(tulos: dict[str, Any] | None) -> list[str]:
    kaytto = tulos.get("modelUsage") if tulos else None
    return sorted(kaytto) if isinstance(kaytto, dict) else []


def luvattomat_mallit(mallit: list[str], sallitut: list[str]) -> list[str]:
    """Mallit, jotka eivät ala millään sallitulla tunnisteella (tunnisteen perässä saa olla versiopääte)."""
    return [malli for malli in mallit if not any(malli.startswith(tunniste) for tunniste in sallitut)]


def _summa(lahteet: list[dict[str, Any]], avaimet: tuple[str, ...]) -> int | None:
    arvot = [lahde[avain] for lahde in lahteet for avain in avaimet if isinstance(lahde.get(avain), int)]
    return sum(arvot) if arvot else None


def tokenit(tulos: dict[str, Any] | None) -> str:
    """Sisään menneet (myös välimuistin) ja ulos tulleet tokenit mallien yli; kenttien puuttuessa ei tietoa."""
    if not tulos:
        return EI_TIETOA
    mallit = [kaytto for kaytto in (tulos.get("modelUsage") or {}).values() if isinstance(kaytto, dict)]
    sisaan, ulos = _summa(mallit, SISAAN_AVAIMET), _summa(mallit, ("outputTokens",))
    if sisaan is None or ulos is None:
        yhteensa = [tulos["usage"]] if isinstance(tulos.get("usage"), dict) else []
        sisaan, ulos = _summa(yhteensa, SISAAN_AVAIMET_YHTEENSA), _summa(yhteensa, ("output_tokens",))
    return EI_TIETOA if sisaan is None or ulos is None else f"{sisaan} / {ulos}"


def kesto(tulos: dict[str, Any] | None) -> str:
    millisekunnit = tulos.get("duration_ms") if tulos else None
    if not isinstance(millisekunnit, (int, float)):
        return EI_TIETOA
    minuutit, sekunnit = divmod(int(millisekunnit) // 1000, 60)
    return f"{minuutit} min {sekunnit} s"


def _kentta(tulos: dict[str, Any] | None, avain: str, muoto: str) -> str:
    arvo = tulos.get(avain) if tulos else None
    return format(arvo, muoto) if isinstance(arvo, (int, float)) and not isinstance(arvo, bool) else EI_TIETOA


def taulukon_rivi(argumentit: argparse.Namespace, tulos: dict[str, Any] | None) -> str:
    solut = [
        f"{argumentit.ajo}, kortti {argumentit.kortti}", argumentit.malli, argumentit.lahde, kesto(tulos),
        _kentta(tulos, "num_turns", "d"), tokenit(tulos), _kentta(tulos, "total_cost_usd", ".2f"),
        ", ".join(kaytetyt_mallit(tulos)) or EI_TIETOA,
    ]
    return "| " + " | ".join(solut) + " |"


def paivita_kuvaus(kuvaus: str, rivi: str) -> str:
    """Lisää rivin PR:n kuvauksen kortti-ajolohkoon tai luo lohkon kuvauksen loppuun. Muu kuvaus säilyy."""
    if LOHKON_ALKU in kuvaus and LOHKON_LOPPU in kuvaus.split(LOHKON_ALKU, 1)[1]:
        alkuosa, loppuosa = kuvaus.rsplit(LOHKON_LOPPU, 1)
        return alkuosa.rstrip("\n") + "\n" + rivi + "\n" + LOHKON_LOPPU + loppuosa
    lohko = "\n".join([LOHKON_ALKU, *TAULUKON_OTSIKKO, rivi, LOHKON_LOPPU]) + "\n"
    return kuvaus.rstrip("\n") + "\n\n" + lohko if kuvaus.strip() else lohko


def _jasennin() -> argparse.ArgumentParser:
    jasennin = argparse.ArgumentParser(description="kirjoita kortti-ajon yhteenveto ja tarkista käytetyt mallit")
    jasennin.add_argument("--suoritus", type=Path, required=True, help="actionin execution_file; saa puuttua")
    jasennin.add_argument("--kortti", required=True)
    jasennin.add_argument("--ajo", required=True, help="esimerkiksi 'uusi kortti' tai 'korjauskierros PR 7'")
    jasennin.add_argument("--malli", required=True, help="portti malli -askeleen valitsema mallitunniste")
    jasennin.add_argument("--lahde", required=True, help="mallin lähde: oletus, kortti, käsin tai alkuperäinen ajo")
    jasennin.add_argument("--sallitut", required=True, help="sallitut mallitunnisteet pilkuilla eroteltuna")
    jasennin.add_argument("--yhteenveto", type=Path, required=True, help="tiedosto, jonka loppuun yhteenveto lisätään")
    jasennin.add_argument("--kuvaus", type=Path, default=None, help="PR:n nykyinen kuvaus tiedostona")
    jasennin.add_argument("--kuvaus-ulos", type=Path, default=None, help="tiedosto päivitetylle kuvaukselle")
    return jasennin


def main(argv: list[str] | None = None) -> int:
    argumentit = _jasennin().parse_args(argv)
    tulos, huomautus = lue_tulos(argumentit.suoritus)
    rivi = taulukon_rivi(argumentit, tulos)
    sallitut = [tunniste.strip() for tunniste in argumentit.sallitut.split(",") if tunniste.strip()]
    luvattomat = luvattomat_mallit(kaytetyt_mallit(tulos), sallitut)
    osat = ["## Kortti-ajo", "", *TAULUKON_OTSIKKO[2:], rivi, ""]
    osat += [f"Huomautus: {huomautus}.", ""] if huomautus else []
    osat += [f"Ajo käytti mallia, joka ei ole sallittu: {', '.join(luvattomat)}.", ""] if luvattomat else []
    with argumentit.yhteenveto.open("a", encoding="utf-8") as tiedosto:
        tiedosto.write("\n".join(osat) + "\n")
    if argumentit.kuvaus is not None and argumentit.kuvaus_ulos is not None:
        vanha = argumentit.kuvaus.read_text(encoding="utf-8") if argumentit.kuvaus.is_file() else ""
        argumentit.kuvaus_ulos.write_text(paivita_kuvaus(vanha, rivi), encoding="utf-8")
    if luvattomat:
        print(f"::error::Kortti-ajo käytti mallia, joka ei ole sallittu: {', '.join(luvattomat)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
