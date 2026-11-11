"""Ohjaus: päättää portin tuloksesta, testien tilasta ja muuttuneista poluista, minne PR menee.

Deterministinen ja ilman kielimallia. Fail-closed: puuttuva tai ristiriitainen tieto vie PR:n CTO:lle.
Päätöstaulun rivit a–e ovat README:n Ohjaus-osiossa; jokaisella rivillä on testi (tests/test_ohjaus.py).
Korjauskierrosten määrä luetaan PR:n labeleista `korjauskierros-<n>`, jotka ovat pysyvä laskuri eikä
niitä koskaan poisteta. Agentin PR tunnistetaan labelista `agentti`. Edellinen päätös (ohjauskommentin
konedata) kertoo, onko tälle headille jo käynnistetty kierros: sama tila ei käynnistä toista. Jos konedataa
ei voitu lukea, korjauskierrosta ei käynnistetä vaan PR menee CTO:lle.
Uusi korjauskierros vaatii kortin slugin (PR:n haara `feature/<slug>`) ja alkuperäisen ajon mallin
(label `malli-<nimi>`); jos jompikumpi puuttuu, PR menee CTO:lle.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from portti.kortti import HAARAN_ETULIITE, slug_haarasta
from portti.luokittelu import TIER_YLI
from portti.malli import SALLITUT_MALLIT
from portti.polkumallit import ensimmainen_osuma
from portti.verdict import KOVA, LIIAN_ISO, PEHMEA, PUUTE, TIERIT_PORTAITTAIN, VAPAA
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
MALLI_ETULIITE = "malli-"
HALLITUT_LABELIT = (LABEL_KATSELMOITAVAKSI, LABEL_KOVA, LABEL_JUMISSA, LABEL_KORJATTAVA, LABEL_LIIAN_ISO)

OHJAUKSEN_KOVAT_POLUT = (".github/**", ".portti/**")
T1_TIERIT = TIERIT_PORTAITTAIN
TUNNETUT_TIERIT = (*T1_TIERIT, TIER_YLI)
KIERROKSIA_TESTEISTA = 2
KIERROKSIA_KOOSTA = 1
KIERROSNUMERO = re.compile(r"[0-9]{1,6}")
PAATOS_MUOTO = 1
EDELLINEN_KELVOTON = "kelvoton"


@dataclass(frozen=True)
class OhjausSyote:
    pr_head_sha: str
    testit: str
    evidence: dict[str, Any] | None
    muuttuneet_polut: tuple[str, ...]
    labelit: tuple[str, ...]
    forkki: bool = False
    evidence_huomautus: str | None = None
    edellinen: dict[str, Any] | None = None
    haara: str | None = None
    polut_vajaat: bool = False

    @property
    def agentti(self) -> bool:
        return LABEL_AGENTTI in self.labelit

    @property
    def kierroksia(self) -> int:
        return kierroksia_labeleista(self.labelit)

    @property
    def kortti(self) -> str | None:
        """Kortin slug PR:n haarasta `feature/<slug>`, tai None."""
        return slug_haarasta(self.haara) if self.haara else None

    @property
    def alkuperainen_malli(self) -> str | None:
        """Alkuperäisen ajon malli labelista `malli-<nimi>`. Puuttuva, moniselitteinen tai kielletty on None."""
        nimet = {label[len(MALLI_ETULIITE):] for label in self.labelit if label.startswith(MALLI_ETULIITE)}
        if len(nimet) != 1:
            return None
        nimi = next(iter(nimet))
        return nimi if nimi in SALLITUT_MALLIT else None

    @property
    def edellinen_kelvoton(self) -> bool:
        """Ohjauskommentin konedataa ei voitu lukea: edellistä päätöstä ei tunneta eikä sitä arvata."""
        return bool((self.edellinen or {}).get(EDELLINEN_KELVOTON))

    @property
    def kaynnistetty_kierros(self) -> int | None:
        """Kierros, jonka ohjaus on jo käynnistänyt tälle headille, tai None.

        Luetaan edellisen päätöksen konedatasta. Kelvoton kierrosnumero tulkitaan käynnistetyksi
        kierrokseksi (labelien mukaan), jotta epäselvä tieto ei käynnistä maksullista ajoa kahdesti.
        """
        edellinen = self.edellinen or {}
        if edellinen.get("toimenpide") != KORJAUSKIERROS or edellinen.get("head_sha") != self.pr_head_sha:
            return None
        kierros = edellinen.get("kierros")
        if type(kierros) is int and kierros > 0:
            return kierros
        return max(self.kierroksia, 1)


@dataclass(frozen=True)
class Paatos:
    toimenpide: str
    labelit: tuple[str, ...]
    katselmoijan_rooli: str | None
    perustelu: str
    kierros: int | None = None
    ohje: str | None = None
    kaynnista: bool = False


def kierroksia_labeleista(labelit: tuple[str, ...]) -> int:
    """Suurin n labeleista `korjauskierros-<n>`; 0, jos niitä ei ole. Vain ASCII-numerot ovat kierroksia."""
    kierrokset = [0]
    for label in labelit:
        loppu = label[len(KIERROS_ETULIITE):]
        if label.startswith(KIERROS_ETULIITE) and KIERROSNUMERO.fullmatch(loppu):
            kierrokset.append(int(loppu))
    return max(kierrokset)


def on_hallittu_label(label: str) -> bool:
    """Ohjauksen asettama tilalabel, jonka ohjaus myös poistaa, kun tila vaihtuu."""
    return label in HALLITUT_LABELIT or label.startswith(TIER_ETULIITE)


def _cto(label: str, perustelu: str) -> Paatos:
    return Paatos(CTO, (LABEL_KATSELMOITAVAKSI, label), ROOLI_CTO, perustelu)


def _evidencen_muotovirhe(evidence: dict[str, Any]) -> str | None:
    """Syy, jos evidencen rakenne ei ole se, jonka päätöstaulu lukee; muuten None."""
    luokitus = evidence.get("luokitus")
    if not isinstance(luokitus, dict):
        return "luokitus puuttuu tai ei ole objekti"
    if not isinstance(luokitus.get("puutteet", []), list):
        return "luokituksen puutteet eivät ole lista"
    return None


def _rivi_a(syote: OhjausSyote) -> Paatos | None:
    """Fail-closed: puuttuva, vajaa tai ristiriitainen tieto ja portin omat polut vievät CTO:lle."""
    if syote.evidence is None:
        return _cto(LABEL_KOVA, syote.evidence_huomautus or "evidence puuttuu")
    if syote.testit not in (TESTIT_SUCCESS, TESTIT_FAILURE):
        return _cto(LABEL_KOVA, f"testien tila puuttuu ({syote.testit})")
    muotovirhe = _evidencen_muotovirhe(syote.evidence)
    if muotovirhe is not None:
        return _cto(LABEL_KOVA, f"evidence ei kelpaa: {muotovirhe}")
    evidencen_head = str(syote.evidence.get("head_sha"))
    if evidencen_head != syote.pr_head_sha:
        return _cto(LABEL_KOVA, f"evidence on headista {evidencen_head[:12]}, PR:n head on {syote.pr_head_sha[:12]}")
    if syote.polut_vajaat:
        return _cto(LABEL_KOVA, "muuttuneiden polkujen lista on vajaa: kaikkia PR:n tiedostoja ei voitu tarkistaa")
    for polku in syote.muuttuneet_polut:
        if ensimmainen_osuma(polku, OHJAUKSEN_KOVAT_POLUT) is not None:
            return _cto(LABEL_KOVA, f"PR muuttaa polkua {polku}")
    return None


def _kaynnistyksen_este(syote: OhjausSyote) -> str | None:
    """Kortti-ajo tarvitsee kortin slugin ja alkuperäisen ajon mallin. Puuttuva tieto on este, ei arvaus."""
    if syote.kortti is None:
        return f"PR:n haara ei ole muotoa {HAARAN_ETULIITE}<slug>"
    if syote.alkuperainen_malli is None:
        return f"alkuperäisen ajon malli ei ole tiedossa (yksi sallittu label {MALLI_ETULIITE}<nimi> puuttuu)"
    return None


def _korjauskierros_tai_cto(syote: OhjausSyote, raja: int, cto_label: str, perustelu: str, ohje: str) -> Paatos:
    """Agentin PR: uusi korjauskierros, kun kierroksia on alle rajan. Forkin PR ei käynnistä kierrosta koskaan.

    Jos tälle headille on jo käynnistetty kierros, päätös toistaa sen käynnistämättä uutta: sama tila ei
    kuluta toista kierrosta eikä vie PR:ää CTO:lle kesken korjauksen. Uusi kierros käynnistyy vain, kun
    kortin slug ja alkuperäisen ajon malli ovat tiedossa; muuten PR menee CTO:lle.
    """
    if syote.forkki:
        return _cto(cto_label, f"{perustelu}; forkin PR ei käynnistä korjauskierrosta")
    if syote.edellinen_kelvoton:
        return _cto(cto_label, f"{perustelu}; edellistä ohjauspäätöstä ei voitu lukea, korjauskierrosta ei käynnistetä")
    kaynnistetty = syote.kaynnistetty_kierros
    if kaynnistetty is not None:
        selite = f"{perustelu}; korjauskierros {kaynnistetty} on jo käynnistetty tälle headille"
        return Paatos(KORJAUSKIERROS, (f"{KIERROS_ETULIITE}{kaynnistetty}",), None, selite, kaynnistetty, ohje)
    if syote.kierroksia >= raja:
        return _cto(cto_label, f"{perustelu}; korjauskierroksia käytetty {syote.kierroksia}")
    este = _kaynnistyksen_este(syote)
    if este is not None:
        return _cto(cto_label, f"{perustelu}; korjauskierrosta ei voi käynnistää: {este}")
    kierros = syote.kierroksia + 1
    labelit = (f"{KIERROS_ETULIITE}{kierros}",)
    return Paatos(KORJAUSKIERROS, labelit, None, perustelu, kierros, ohje, kaynnista=True)


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
    """PEHMEÄ tai VAPAA ja testit success: katselmoitavaksi, rooli tierin mukaan. Tuntematon tier menee CTO:lle."""
    if tier not in TUNNETUT_TIERIT:
        return _cto(LABEL_KOVA, f"tuntematon tier {tier!r}")
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
    """Päätös-JSON: järjestetyt listat, ei nimiä eikä tunnuksia. Kortti ja malli vain korjauskierroksessa."""
    korjaus = paatos.toimenpide == KORJAUSKIERROS
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
        "kaynnista_kortti_ajo": paatos.kaynnista,
        "kortti": syote.kortti if korjaus else None,
        "alkuperainen_malli": syote.alkuperainen_malli if korjaus else None,
        "ohje": paatos.ohje,
        "perustelu": paatos.perustelu,
        "agentti": syote.agentti,
        "forkki": syote.forkki,
        "testit": syote.testit,
    }


def paatos_keskeytyneelle_ajolle(head_sha: str, labelit: tuple[str, ...], syy: str) -> dict[str, Any]:
    """Kortti-ajoa ei saatu käyntiin tai se epäonnistui: PR menee CTO:lle labelilla jumissa.

    Tulos on samaa muotoa kuin `paatos_sanakirjaksi`, joten toteutus soveltaa sen kuten minkä tahansa päätöksen.
    """
    syote = OhjausSyote(head_sha, TESTIT_PUUTTUU, None, (), labelit)
    return paatos_sanakirjaksi(syote, _cto(LABEL_JUMISSA, syy))


def paatos_tekstiksi(paatos: dict[str, Any]) -> str:
    return json.dumps(paatos, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def lue_paatos(polku: Path) -> dict[str, Any]:
    sisalto = json.loads(polku.read_text(encoding="utf-8"))
    if not isinstance(sisalto, dict) or sisalto.get("paatos_muoto") != PAATOS_MUOTO:
        raise ValueError(f"{polku}: ei ole ohjauksen päätöstiedosto (muoto {PAATOS_MUOTO})")
    return sisalto
