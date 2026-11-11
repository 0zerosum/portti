"""Mallin valinta: mallipäätöksen 6.11.2026 jokainen sallittu ja kielletty arvo, kirjainkoko, välit, tunnisteet ja etusija."""

import json

import pytest

from portti.malli import (
    LAHDE_ALKUPERAINEN,
    LAHDE_KASIN,
    LAHDE_KORTTI,
    LAHDE_OLETUS,
    SALLITUT_MALLIT,
    MalliVirhe,
    sallittu_nimi,
    valinta_sanakirjaksi,
    valitse_malli,
)

OPUS_TUNNISTE = "claude-opus-5-5"
FABLE_TUNNISTE = "claude-fable-5-1"
KIELLETYT = [
    "sonnet", "haiku", "Sonnet", "HAIKU", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-sonnet-5", "claude-haiku-4-5",
    "claude-opus-5", "claude-opus-4-8", "claude-opus-5-5-20260101", "claude-opus-5-5[1m]", "claude-fable-5", "opus-5-5",
    "opusplan", "best", "default", "inherit", "keksitty-malli-9", "opus fable", "opus,fable", "o pus", "", "   ", "(fable)",
]


def kortti(*metarivit: str) -> str:
    return "# Keksitty kortti\n\n- Tila: hyväksytty\n" + "".join(f"{rivi}\n" for rivi in metarivit) + "\nKuvaus.\n"


def test_sallitut_mallit_ovat_vain_opus_ja_fable() -> None:
    assert SALLITUT_MALLIT == {"opus": OPUS_TUNNISTE, "fable": FABLE_TUNNISTE}


@pytest.mark.parametrize(
    "arvo, nimi",
    [("opus", "opus"), ("fable", "fable"), (OPUS_TUNNISTE, "opus"), (FABLE_TUNNISTE, "fable"),
     ("Opus", "opus"), ("FABLE", "fable"), ("  opus  ", "opus"), ("\tFable ", "fable"),
     ("CLAUDE-OPUS-5-5", "opus"), (" claude-fable-5-1 ", "fable"), ("`fable`", "fable"),
     ("opus (oletus; fable vain hyväksytyllä päätöksellä)", "opus")],
)
def test_sallittu_arvo_kirjainkoosta_ja_valeista_riippumatta(arvo: str, nimi: str) -> None:
    assert sallittu_nimi(arvo, "testi") == nimi


@pytest.mark.parametrize("arvo", KIELLETYT)
def test_kielletty_arvo_on_virhe(arvo: str) -> None:
    with pytest.raises(MalliVirhe):
        sallittu_nimi(arvo, "testi")
    with pytest.raises(MalliVirhe):
        valitse_malli(kortti(), kasin=arvo)
    with pytest.raises(MalliVirhe):
        valitse_malli(kortti(), alkuperainen=arvo)
    with pytest.raises(MalliVirhe):
        valitse_malli(kortti(f"- Malli: {arvo}"))


def test_oletus_on_opus_kun_kortissa_ei_ole_mallirivia() -> None:
    valinta = valitse_malli(kortti())
    assert (valinta.nimi, valinta.tunniste, valinta.lahde) == ("opus", OPUS_TUNNISTE, LAHDE_OLETUS)
    ilman_luettelomerkkia = valitse_malli(kortti("Malli: fable"))
    assert ilman_luettelomerkkia.lahde == LAHDE_OLETUS, "vain rivi '- Malli:' on mallirivi"


@pytest.mark.parametrize(
    "rivi, tunniste",
    [("- Malli: fable", FABLE_TUNNISTE), ("- malli:   FABLE  ", FABLE_TUNNISTE), ("* Malli: fable", FABLE_TUNNISTE),
     ("- Malli: claude-fable-5-1", FABLE_TUNNISTE), ("- Malli: opus", OPUS_TUNNISTE),
     ("- Malli: opus (oletus; fable vain hyväksytyllä päätöksellä)", OPUS_TUNNISTE)],
)
def test_kortin_mallirivi(rivi: str, tunniste: str) -> None:
    valinta = valitse_malli(kortti(rivi))
    assert valinta.tunniste == tunniste and valinta.lahde == LAHDE_KORTTI


def test_kaksi_mallirivia_on_virhe() -> None:
    with pytest.raises(MalliVirhe, match="2 riviä"):
        valitse_malli(kortti("- Malli: opus", "- Malli: fable"))


def test_kasin_valittu_voittaa_kortin_rivin() -> None:
    ylos = valitse_malli(kortti(), kasin="fable")
    assert (ylos.tunniste, ylos.lahde) == (FABLE_TUNNISTE, LAHDE_KASIN)
    alas = valitse_malli(kortti("- Malli: fable"), kasin=" Opus ")
    assert (alas.tunniste, alas.lahde) == (OPUS_TUNNISTE, LAHDE_KASIN)


def test_korjauskierros_kayttaa_alkuperaisen_ajon_mallia() -> None:
    fable = valitse_malli(kortti(), alkuperainen="fable")
    assert (fable.tunniste, fable.lahde) == (FABLE_TUNNISTE, LAHDE_ALKUPERAINEN)
    opus = valitse_malli(kortti("- Malli: fable"), alkuperainen="opus")
    assert opus.tunniste == OPUS_TUNNISTE, "alkuperäinen ajo voittaa kortin rivin"
    with pytest.raises(MalliVirhe, match="korjauskierrokselle"):
        valitse_malli(kortti(), kasin="opus", alkuperainen="opus")


def test_kortin_kielletty_rivi_estaa_ajon_vaikka_malli_annetaan_muuta_kautta() -> None:
    for rivi in ("- Malli: sonnet", "- Malli:", "- Malli: (oletus)"):
        with pytest.raises(MalliVirhe):
            valitse_malli(kortti(rivi), kasin="opus")
        with pytest.raises(MalliVirhe):
            valitse_malli(kortti(rivi), alkuperainen="opus")


def test_valinta_sanakirjaksi_on_deterministinen_ja_tarkistaja_on_aina_opus() -> None:
    fable = valinta_sanakirjaksi(valitse_malli(kortti("- Malli: fable")))
    assert fable == {"malli": FABLE_TUNNISTE, "nimi": "fable", "lahde": LAHDE_KORTTI,
                     "tarkistajan_malli": OPUS_TUNNISTE, "sallitut_tunnisteet": [FABLE_TUNNISTE, OPUS_TUNNISTE]}
    assert json.dumps(fable, sort_keys=True) == json.dumps(valinta_sanakirjaksi(valitse_malli(kortti("- Malli: fable"))), sort_keys=True)
    assert valinta_sanakirjaksi(valitse_malli(kortti()))["tarkistajan_malli"] == OPUS_TUNNISTE
