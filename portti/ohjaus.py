"""Ohjaus: päättää portin tuloksesta, testien tilasta ja muuttuneista poluista, minne PR menee.

Deterministinen ja ilman kielimallia. Fail-closed: puuttuva tai ristiriitainen tieto vie PR:n CTO:lle.
Päätöstaulun rivit a–e ovat README:n Ohjaus-osiossa; jokaisella rivillä on testi (tests/test_ohjaus.py).
Korjauskierrosten määrä luetaan PR:n labeleista `korjauskierros-<n>`, jotka ovat pysyvä laskuri eikä
niitä koskaan poisteta. Agentin PR tunnistetaan labelista `agentti`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from portti.polkumallit import ensimmainen_osuma
from portti.verdict import KOVA, LIIAN_ISO, PEHMEA, PUUTE, VAPAA
from portti.version import VERSIO

TESTIT_SUCCESS = "success"
TESTIT_FAILURE = "failure"
TESTIT_PUUTTUU = "puuttuu"
TESTIEN_TILAT = (TESTIT_SUCCESS, TESTIT_FAILURE, TESTIT_PUUTTUU)

CTO = "cto"
KATSELMOITAVAKSI = "katselmoitavaksi"
KORJAUSKIERROS = "korjauskierros"
KORJATTAVA = "korjattava"
TOIMENPITEET = (CTO, KATSELMOITAVAKSI, KORJAUSKIERROS, KORJATTAVA)

ROOLI_CTO = "cto"
ROOLI_T1 = "t1"

LABEL_AGENTTI = "agentti"
LABEL_KATSELMOITAVAKSI = "katselmoitavaksi"
LABEL_KOVA = "kova"
LABEL_JUMISSA = "jumissa"
LABEL_KORJATTAVA = "korjattava"
LABEL_LIIAN_ISO = "liian-iso"
TIER_ETULIITE = "tier-"
KIERROS_ETULIITE = "korjauskierros-"
HALLITUT_LABELIT = (LABEL_KATSELMOITAVAKSI, LABEL_KOVA, LABEL_JUMISSA, LABEL_KORJATTAVA, LABEL_LIIAN_ISO)

OHJAUKSEN_KOVAT_POLUT = (".github/**", ".portti/**")
T1_TIERIT = ("T0", "T1a", "T1b", "T1c")
KIERROKSIA_TESTEISTA = 2
KIERROKSIA_KOOSTA = 1
PAATOS_MUOTO = 1


@dataclass(frozen=True)
class OhjausSyote:
    pr_head_sha: str
    testit: str
    evidence: dict[str, Any] | None
    muuttuneet_polut: tuple[str, ...]
    labelit: tuple[str, ...]
    forkki: bool = False
    evidence_huomautus: str | None = None

    @property
    def agentti(self) -> bool:
        return LABEL_AGENTTI in self.labelit

    @property
    def kierroksia(self) -> int:
        return kierroksia_labeleista(self.labelit)


@dataclass(frozen=True)
class Paatos:
    toimenpide: str
    labelit: tuple[str, ...]
    katselmoijan_rooli: str | None
    perustelu: str
    kierros: int | None = None
    ohje: str | None = None


def kierroksia_labeleista(labelit: tuple[str, ...]) -> int:
    """Suurin n labeleista `korjauskierros-<n>`; 0, jos niitä ei ole."""
    kierrokset = [0]
    for label in labelit:
        loppu = label[len(KIERROS_ETULIITE):]
        if label.startswith(KIERROS_ETULIITE) and loppu.isdigit():
            kierrokset.append(int(loppu))
    return max(kierrokset)


def on_hallittu_label(label: str) -> bool:
    """Ohjauksen asettama tilalabel, jonka ohjaus myös poistaa, kun tila vaihtuu."""
    return label in HALLITUT_LABELIT or label.startswith(TIER_ETULIITE)


def _cto(label: str, perustelu: str) -> Paatos:
    return Paatos(CTO, (LABEL_KATSELMOITAVAKSI, label), ROOLI_CTO, perustelu)


def _rivi_a(syote: OhjausSyote) -> Paatos | None:
    """Fail-closed: puuttuva tai ristiriitainen tieto ja portin omat polut vievät CTO:lle."""
    if syote.evidence is None:
        return _cto(LABEL_KOVA, syote.evidence_huomautus or "evidence puuttuu")
    if syote.testit not in (TESTIT_SUCCESS, TESTIT_FAILURE):
        return _cto(LABEL_KOVA, f"testien tila puuttuu ({syote.testit})")
    evidencen_head = str(syote.evidence.get("head_sha"))
    if evidencen_head != syote.pr_head_sha:
        return _cto(LABEL_KOVA, f"evidence on headista {evidencen_head[:12]}, PR:n head on {syote.pr_head_sha[:12]}")
    for polku in syote.muuttuneet_polut:
        if ensimmainen_osuma(polku, OHJAUKSEN_KOVAT_POLUT) is not None:
            return _cto(LABEL_KOVA, f"PR muuttaa polkua {polku}")
    return None


def _korjauskierros_tai_cto(syote: OhjausSyote, raja: int, cto_label: str, perustelu: str, ohje: str) -> Paatos:
    """Agentin PR: korjauskierros, kun kierroksia on alle rajan. Forkin PR ei käynnistä kierrosta koskaan."""
    if syote.forkki:
        return _cto(LABEL_JUMISSA, f"{perustelu}; forkin PR ei käynnistä korjauskierrosta")
    if syote.kierroksia < raja:
        kierros = syote.kierroksia + 1
        return Paatos(KORJAUSKIERROS, (f"{KIERROS_ETULIITE}{kierros}",), None, perustelu, kierros, ohje)
    return _cto(cto_label, f"{perustelu}; korjauskierroksia käytetty {syote.kierroksia}")


def _rivi_c(syote: OhjausSyote, evidence: dict[str, Any]) -> Paatos:
    """Testit failure tai PUUTE: agentille korjauskierros (enintään 2), ihmiselle korjattava ilman katselmoijaa."""
    if syote.testit == TESTIT_FAILURE:
        perustelu = "testit epäonnistuivat"
    else:
        puutteet = [str(puute) for puute in evidence.get("luokitus", {}).get("puutteet", [])]
        perustelu = "portti: PUUTE (" + ("; ".join(puutteet) or "edellytykset eivät täyty") + ")"
    if not syote.agentti:
        return Paatos(KORJATTAVA, (LABEL_KORJATTAVA,), None, perustelu)
    ohje = "korjaa kaatuneet testit ja portin kommentin puutteet; älä laajenna muutosta"
    return _korjauskierros_tai_cto(syote, KIERROKSIA_TESTEISTA, LABEL_JUMISSA, perustelu, ohje)


def _rivi_d(syote: OhjausSyote) -> Paatos:
    """LIIAN-ISO: agentille yksi korjauskierros, muuten CTO."""
    perustelu = "portti: LIIAN-ISO"
    if not syote.agentti:
        return _cto(LABEL_LIIAN_ISO, perustelu)
    return _korjauskierros_tai_cto(syote, KIERROKSIA_KOOSTA, LABEL_LIIAN_ISO, perustelu, "pienennä muutos kortin rajaukseen")


def _rivi_e(verdict: str, tier: str) -> Paatos:
    """PEHMEÄ tai VAPAA ja testit success: katselmoitavaksi, rooli tierin mukaan."""
    rooli = ROOLI_T1 if tier in T1_TIERIT else ROOLI_CTO
    labelit = (LABEL_KATSELMOITAVAKSI, f"{TIER_ETULIITE}{tier}")
    return Paatos(KATSELMOITAVAKSI, labelit, rooli, f"portti: {verdict} tier {tier}, testit success")


def paata(syote: OhjausSyote) -> Paatos:
    """Päätöstaulu riveittäin a–e; mikään muu tila ei kelpaa vaan menee CTO:lle."""
    estava = _rivi_a(syote)
    if estava is not None:
        return estava
    evidence = syote.evidence or {}
    verdict = str(evidence.get("verdict"))
    tier = str(evidence.get("luokitus", {}).get("tier"))
    if verdict == KOVA:
        return _cto(LABEL_KOVA, "portti: KOVA")
    if syote.testit == TESTIT_FAILURE or verdict == PUUTE:
        return _rivi_c(syote, evidence)
    if verdict == LIIAN_ISO:
        return _rivi_d(syote)
    if verdict in (PEHMEA, VAPAA) and syote.testit == TESTIT_SUCCESS:
        return _rivi_e(verdict, tier)
    return _cto(LABEL_KOVA, f"tuntematon tila: verdict {verdict}, testit {syote.testit}")


def paatos_sanakirjaksi(syote: OhjausSyote, paatos: Paatos) -> dict[str, Any]:
    """Päätös-JSON: järjestetyt listat, ei nimiä eikä tunnuksia."""
    lisaa = sorted(set(paatos.labelit))
    poista = sorted(label for label in set(syote.labelit) if on_hallittu_label(label) and label not in lisaa)
    return {
        "paatos_muoto": PAATOS_MUOTO,
        "moottorin_versio": VERSIO,
        "head_sha": syote.pr_head_sha,
        "toimenpide": paatos.toimenpide,
        "lisaa_labelit": lisaa,
        "poista_labelit": poista,
        "katselmoijan_rooli": paatos.katselmoijan_rooli,
        "kierros": paatos.kierros,
        "ohje": paatos.ohje,
        "perustelu": paatos.perustelu,
        "agentti": syote.agentti,
        "forkki": syote.forkki,
        "testit": syote.testit,
    }


def paatos_tekstiksi(paatos: dict[str, Any]) -> str:
    return json.dumps(paatos, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def lue_paatos(polku: Path) -> dict[str, Any]:
    sisalto = json.loads(polku.read_text(encoding="utf-8"))
    if not isinstance(sisalto, dict) or sisalto.get("paatos_muoto") != PAATOS_MUOTO:
        raise ValueError(f"{polku}: ei ole ohjauksen päätöstiedosto (muoto {PAATOS_MUOTO})")
    return sisalto
