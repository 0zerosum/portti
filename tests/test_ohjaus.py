"""Ohjauksen päätöstaulu riveittäin (a–e), fail-closed-tapaukset, labelien poisto ja päätös-JSONin determinismi."""

import json
from typing import Any

import pytest

from portti.ohjaus import (
    CTO,
    KATSELMOITAVAKSI,
    KORJATTAVA,
    KORJAUSKIERROS,
    LABEL_AGENTTI,
    OhjausSyote,
    kierroksia_labeleista,
    paata,
    paatos_sanakirjaksi,
    paatos_tekstiksi,
)

HEAD = "abc123abc123"
AGENTTI = (LABEL_AGENTTI,)


def evidence(verdict: str = "VAPAA", tier: str = "T1a", head: str = HEAD,
             puutteet: list[str] | None = None) -> dict[str, Any]:
    return {"evidence_muoto": 1, "verdict": verdict, "head_sha": head, "luokitus": {"tier": tier, "puutteet": puutteet or []}}


def syote(**muutokset: Any) -> OhjausSyote:
    perus: dict[str, Any] = {
        "pr_head_sha": HEAD, "testit": "success", "evidence": evidence(),
        "muuttuneet_polut": ("palvelin/sovellus/laskenta/ydin.py",), "labelit": (),
    }
    perus.update(muutokset)
    return OhjausSyote(**perus)


@pytest.mark.parametrize(
    "muutos, syy",
    [
        ({"evidence": None, "evidence_huomautus": "evidence puuttuu (artefaktia ei ole)"}, "evidence puuttuu"),
        ({"testit": "puuttuu"}, "testien tila puuttuu"),
        ({"evidence": evidence(head="muu")}, "evidence on headista"),
        ({"muuttuneet_polut": ("palvelin/x.py", ".github/workflows/testit.yml")}, "PR muuttaa polkua .github/workflows/testit.yml"),
        ({"muuttuneet_polut": (".portti/policy.yml",)}, "PR muuttaa polkua .portti/policy.yml"),
    ],
)
def test_rivi_a_fail_closed_vie_ctolle(muutos: dict[str, Any], syy: str) -> None:
    paatos = paata(syote(**muutos))
    assert paatos.toimenpide == CTO and paatos.katselmoijan_rooli == "cto"
    assert set(paatos.labelit) == {"katselmoitavaksi", "kova"}
    assert syy in paatos.perustelu


def test_rivi_a_menee_agentin_korjauskierroksen_edelle() -> None:
    paatos = paata(syote(testit="failure", evidence=None, labelit=AGENTTI))
    assert paatos.toimenpide == CTO and "evidence puuttuu" in paatos.perustelu


def test_rivi_b_kova_vie_ctolle_myos_testien_kaatuessa() -> None:
    paatos = paata(syote(evidence=evidence("KOVA", "T1b"), testit="failure", labelit=AGENTTI))
    assert paatos.toimenpide == CTO and set(paatos.labelit) == {"katselmoitavaksi", "kova"}
    assert paatos.perustelu == "portti: KOVA"


def test_rivi_c_agentin_testit_failure_korjauskierrokset_ja_jumissa() -> None:
    ensimmainen = paata(syote(testit="failure", labelit=AGENTTI))
    assert ensimmainen.toimenpide == KORJAUSKIERROS and ensimmainen.kierros == 1
    assert ensimmainen.labelit == ("korjauskierros-1",) and ensimmainen.katselmoijan_rooli is None
    toinen = paata(syote(testit="failure", labelit=(LABEL_AGENTTI, "korjauskierros-1")))
    assert toinen.toimenpide == KORJAUSKIERROS and toinen.kierros == 2 and toinen.labelit == ("korjauskierros-2",)
    kolmas = paata(syote(testit="failure", labelit=(LABEL_AGENTTI, "korjauskierros-1", "korjauskierros-2")))
    assert kolmas.toimenpide == CTO and set(kolmas.labelit) == {"katselmoitavaksi", "jumissa"}
    assert "korjauskierroksia käytetty 2" in kolmas.perustelu


def test_rivi_c_puute_konflikti() -> None:
    puute = evidence("PUUTE", "T1a", puutteet=["PR on konfliktissa"])
    agentin = paata(syote(evidence=puute, labelit=AGENTTI))
    assert agentin.toimenpide == KORJAUSKIERROS and "konfliktissa" in agentin.perustelu
    ihmisen = paata(syote(evidence=puute))
    assert ihmisen.toimenpide == KORJATTAVA and ihmisen.labelit == ("korjattava",) and ihmisen.katselmoijan_rooli is None


def test_rivi_c_ihmisen_pr_korjattava_ilman_katselmoijaa() -> None:
    paatos = paata(syote(testit="failure"))
    assert paatos.toimenpide == KORJATTAVA and paatos.labelit == ("korjattava",)
    assert paatos.katselmoijan_rooli is None and paatos.kierros is None


def test_rivi_c_forkin_pr_ei_kaynnista_korjauskierrosta() -> None:
    paatos = paata(syote(testit="failure", labelit=AGENTTI, forkki=True))
    assert paatos.toimenpide == CTO and set(paatos.labelit) == {"katselmoitavaksi", "jumissa"}
    assert "forkin PR" in paatos.perustelu


def test_rivi_d_liian_iso() -> None:
    iso = evidence("LIIAN-ISO", "YLI")
    agentin = paata(syote(evidence=iso, labelit=AGENTTI))
    assert agentin.toimenpide == KORJAUSKIERROS and agentin.kierros == 1
    assert agentin.ohje == "pienennä muutos kortin rajaukseen"
    toinen = paata(syote(evidence=iso, labelit=(LABEL_AGENTTI, "korjauskierros-1")))
    assert toinen.toimenpide == CTO and set(toinen.labelit) == {"katselmoitavaksi", "liian-iso"}
    ihmisen = paata(syote(evidence=iso))
    assert ihmisen.toimenpide == CTO and set(ihmisen.labelit) == {"katselmoitavaksi", "liian-iso"}


@pytest.mark.parametrize(
    "verdict, tier, rooli",
    [("VAPAA", "T0", "t1"), ("VAPAA", "T1c", "t1"), ("PEHMEÄ", "T1b", "t1"), ("VAPAA", "YLI", "cto")],
)
def test_rivi_e_katselmoitavaksi_rooli_tierin_mukaan(verdict: str, tier: str, rooli: str) -> None:
    paatos = paata(syote(evidence=evidence(verdict, tier), labelit=AGENTTI))
    assert paatos.toimenpide == KATSELMOITAVAKSI and paatos.katselmoijan_rooli == rooli
    assert set(paatos.labelit) == {"katselmoitavaksi", f"tier-{tier}"}


def test_rivit_tarkistetaan_jarjestyksessa() -> None:
    kova_ja_failure = paata(syote(evidence=evidence("KOVA"), testit="failure", labelit=AGENTTI))
    assert kova_ja_failure.toimenpide == CTO and "KOVA" in kova_ja_failure.perustelu
    iso_ja_failure = paata(syote(evidence=evidence("LIIAN-ISO", "YLI"), testit="failure", labelit=AGENTTI))
    assert iso_ja_failure.toimenpide == KORJAUSKIERROS and iso_ja_failure.perustelu == "testit epäonnistuivat"


def test_tuntematon_tila_vie_ctolle() -> None:
    outo = paata(syote(evidence=evidence("OUTO")))
    assert outo.toimenpide == CTO and "tuntematon tila" in outo.perustelu
    keskeytetty = paata(syote(testit="cancelled"))
    assert keskeytetty.toimenpide == CTO and "testien tila puuttuu" in keskeytetty.perustelu


def test_ihmiselle_vieva_toimenpide_asettaa_katselmoitavaksi() -> None:
    assert "katselmoitavaksi" in paata(syote()).labelit
    assert "katselmoitavaksi" in paata(syote(evidence=evidence("KOVA"))).labelit
    assert "katselmoitavaksi" not in paata(syote(testit="failure", labelit=AGENTTI)).labelit
    assert "katselmoitavaksi" not in paata(syote(testit="failure")).labelit


def test_kierroksia_labeleista() -> None:
    assert kierroksia_labeleista(("korjauskierros-2", "korjauskierros-x", "korjauskierros-1", "agentti")) == 2
    assert kierroksia_labeleista(()) == 0


def test_paatos_json_poistaa_vain_hallitut_labelit_ja_on_deterministinen() -> None:
    labelit = ("agentti", "korjauskierros-1", "kova", "katselmoitavaksi", "tier-T1a", "muu")
    tila = syote(evidence=evidence(tier="T0"), labelit=labelit)
    paatos = paatos_sanakirjaksi(tila, paata(tila))
    assert paatos["lisaa_labelit"] == ["katselmoitavaksi", "tier-T0"]
    assert paatos["poista_labelit"] == ["kova", "tier-T1a"], "agentti, korjauskierros-n ja vieraat labelit jäävät"
    assert paatos["agentti"] is True and paatos["head_sha"] == HEAD and paatos["kierros"] is None
    teksti = paatos_tekstiksi(paatos)
    assert teksti == paatos_tekstiksi(paatos_sanakirjaksi(tila, paata(tila)))
    assert list(json.loads(teksti)) == sorted(json.loads(teksti))
