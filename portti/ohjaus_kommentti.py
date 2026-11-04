"""Ohjauskommentti: yksi päivittyvä kommentti per PR, konedata JSONina tunnisteen jälkeen.

Tunniste eroaa portin kommentista, jotta shadow-raportti ei lue ohjauksen konedataa portin verdictinä.
"""

from __future__ import annotations

import json
from typing import Any

from portti.ohjaus import CTO, KATSELMOITAVAKSI, KORJATTAVA, KORJAUSKIERROS

TUNNISTE = "<!-- portti-ohjaus v1 -->"
KONEDATA_ALKU = "<!-- ohjaus "
KONEDATA_LOPPU = " -->"
OTSIKOT = {
    CTO: "CTO:lle",
    KATSELMOITAVAKSI: "katselmoitavaksi",
    KORJAUSKIERROS: "korjauskierros",
    KORJATTAVA: "korjattava, tekijä korjaa",
}


def konedata(paatos: dict[str, Any]) -> dict[str, Any]:
    """Toteutuksen idempotenssiin tarvittava tiivistelmä: sama head ja sama päätös ei käynnistä kierrosta uudelleen."""
    return {
        "head_sha": paatos["head_sha"],
        "toimenpide": paatos["toimenpide"],
        "kierros": paatos.get("kierros"),
        "moottorin_versio": paatos["moottorin_versio"],
    }


def lue_ohjauksen_konedata(kommentin_teksti: str) -> dict[str, Any] | None:
    """Palauttaa ohjauskommentin konedatan tai None, jos kommentti ei ole ohjauksen."""
    if not kommentin_teksti.startswith(TUNNISTE):
        return None
    for rivi in kommentin_teksti.splitlines():
        if rivi.startswith(KONEDATA_ALKU) and rivi.endswith(KONEDATA_LOPPU):
            tulos = json.loads(rivi[len(KONEDATA_ALKU):-len(KONEDATA_LOPPU)])
            return tulos if isinstance(tulos, dict) else None
    return None


def _otsikko(paatos: dict[str, Any]) -> str:
    otsikko = OTSIKOT.get(str(paatos["toimenpide"]), str(paatos["toimenpide"]))
    if paatos["toimenpide"] == KORJAUSKIERROS:
        otsikko += f" {paatos.get('kierros')}"
    return f"## Ohjaus: **{otsikko}**"


def _katselmoija_rivi(paatos: dict[str, Any], katselmoija: str | None) -> str:
    if katselmoija is None:
        return "- Katselmoija: ei pyydetty"
    return f"- Katselmoija: {katselmoija} (rooli {paatos.get('katselmoijan_rooli')})"


def renderoi_ohjaus(paatos: dict[str, Any], katselmoija: str | None, huomautukset: list[str]) -> str:
    """Kommentin runko: tunniste, konedata, päätös, perustelu, labelit, katselmoija ja huomautukset."""
    rivit = [
        TUNNISTE,
        KONEDATA_ALKU + json.dumps(konedata(paatos), sort_keys=True, ensure_ascii=False) + KONEDATA_LOPPU,
        _otsikko(paatos),
        "",
        f"- Perustelu: {paatos['perustelu']}",
        f"- Labelit: {', '.join(paatos['lisaa_labelit']) or '–'}",
        _katselmoija_rivi(paatos, katselmoija),
    ]
    if paatos.get("ohje"):
        rivit.append(f"- Ohje agentille: {paatos['ohje']}")
    rivit += [f"- {huomautus}" for huomautus in huomautukset]
    rivit += ["", f"ohjaus {paatos['moottorin_versio']} · head `{str(paatos['head_sha'])[:12]}`"]
    return "\n".join(rivit) + "\n"
