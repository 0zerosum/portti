"""Komennot `malli` (mallin valinta kortille mallipäätöksen mukaan) ja `kortin-tila` (kortin tilarivin tarkistus)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from portti.kortti import KorttiVirhe, kortin_tila, normalisoi
from portti.malli import MalliVirhe, valinta_sanakirjaksi, valitse_malli


def lisaa_malli_komennot(alikomennot: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    malli = alikomennot.add_parser("malli", help="valitse kortti-ajon malli mallipäätöksen mukaan; kielletty arvo palauttaa 1")
    malli.add_argument("--kortti", type=Path, required=True, help="kortin polku (kortit/<slug>.md)")
    malli.add_argument("--kasin", default=None, help="ihmisen käsin valitsema malli (opus tai fable)")
    malli.add_argument("--alkuperainen", default=None, help="korjauskierros: alkuperäisen ajon malli")
    malli.add_argument("--json", action="store_true", help="tulosta valinta JSONina pelkän mallitunnisteen sijaan")
    tila = alikomennot.add_parser("kortin-tila", help="tulosta kortin tilarivin arvo; --vaadi palauttaa 1, jos tila on muu")
    tila.add_argument("--kortti", type=Path, required=True, help="kortin polku (kortit/<slug>.md)")
    tila.add_argument("--vaadi", default=None, help="vaadittu tila, esimerkiksi hyväksytty")


def _lue_kortti(polku: Path, komento: str) -> str | None:
    try:
        return polku.read_text(encoding="utf-8")
    except OSError as virhe:
        print(f"portti: {komento}: korttia {polku} ei voi lukea: {virhe}", file=sys.stderr)
        return None


def komento_malli(argumentit: argparse.Namespace) -> int:
    teksti = _lue_kortti(argumentit.kortti, "malli")
    if teksti is None:
        return 1
    try:
        valinta = valitse_malli(teksti, argumentit.kasin, argumentit.alkuperainen)
    except MalliVirhe as virhe:
        print(f"portti: malli: {virhe}; ajo ei käynnisty", file=sys.stderr)
        return 1
    if argumentit.json:
        print(json.dumps(valinta_sanakirjaksi(valinta), ensure_ascii=False, sort_keys=True))
    else:
        print(valinta.tunniste)
    print(f"portti: malli {valinta.tunniste} ({valinta.nimi}, lähde: {valinta.lahde})", file=sys.stderr)
    return 0


def komento_kortin_tila(argumentit: argparse.Namespace) -> int:
    teksti = _lue_kortti(argumentit.kortti, "kortin-tila")
    if teksti is None:
        return 1
    try:
        tila = kortin_tila(teksti)
    except KorttiVirhe as virhe:
        print(f"portti: kortin-tila: {virhe}", file=sys.stderr)
        return 1
    print(tila or "")
    if argumentit.vaadi is not None and tila != normalisoi(argumentit.vaadi):
        print(f"portti: kortin-tila: kortin tila on {tila or 'merkitsemättä'}, vaaditaan {argumentit.vaadi}", file=sys.stderr)
        return 1
    return 0
