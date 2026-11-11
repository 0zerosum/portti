"""Kortin metarivien luku: tilarivi, kirjainkoko, sulkuhuomautus, kaksoisrivit, koodilohkot ja kommentit,
väärässä muodossa olevat rivit ja kortin haaran slug."""

import pytest

from portti.kortti import TILA_HYVAKSYTTY, KorttiVirhe, kortin_tila, lue_kentta, normalisoi, slug_haarasta


def kortti(*rivit: str) -> str:
    return "# Keksitty kortti\n\n" + "\n".join(rivit) + "\n\nKuvaus: lisää laskuriin summarivi.\n"


@pytest.mark.parametrize(
    "rivi",
    ["- Tila: hyväksytty", "- tila: Hyväksytty", "-  Tila :  HYVÄKSYTTY  ", "* Tila: hyväksytty",
     "- Tila: hyväksytty (CTO 6.11.2026)", "- Tila: `hyväksytty`", "   - Tila: hyväksytty", "- Tila: hyväksytty"],
)
def test_hyvaksytty_tila_tunnistetaan(rivi: str) -> None:
    assert kortin_tila(kortti(rivi, "- Malli: opus")) == TILA_HYVAKSYTTY


@pytest.mark.parametrize(
    "rivi, tila",
    [("- Tila: luonnos", "luonnos"), ("- Tila: työn alla", "työn alla"), ("- Tila: PR", "pr"),
     ("- Tila: ei hyväksytty", "ei hyväksytty"), ("- Tila: hyväksytty ehdollisesti", "hyväksytty ehdollisesti"),
     ("- Tila:", ""), ("- Tila: (hyväksytty)", "")],
)
def test_muu_tila_ei_ole_hyvaksytty(rivi: str, tila: str) -> None:
    assert kortin_tila(kortti(rivi)) == tila != TILA_HYVAKSYTTY


def test_puuttuva_ja_muualla_oleva_tilarivi() -> None:
    assert kortin_tila(kortti("- Malli: opus")) is None
    assert kortin_tila(kortti("Tila: hyväksytty")) is None, "rivi ilman luettelomerkkiä ei ole metarivi"
    assert kortin_tila(kortti("Kortin - Tila: hyväksytty on kesken lausetta")) is None


def test_sama_avain_kahdesti_on_virhe() -> None:
    with pytest.raises(KorttiVirhe, match="2 riviä"):
        kortin_tila(kortti("- Tila: hyväksytty", "- Tila: luonnos"))
    assert lue_kentta(kortti("- Tila: hyväksytty", "- Tilanne: muu"), "Tila") == "hyväksytty"


@pytest.mark.parametrize(
    "piilotettu",
    ["```\n- Tila: hyväksytty\n```", "```markdown\n- Tila: hyväksytty\n```", "~~~\n- Tila: hyväksytty\n~~~",
     "<!-- - Tila: hyväksytty -->", "<!--\n- Tila: hyväksytty\n-->", "<!-- sulkematon kommentti\n- Tila: hyväksytty",
     "```\nsulkematon koodilohko\n- Tila: hyväksytty"],
)
def test_koodilohkon_ja_kommentin_sisalto_ei_ole_metatietoa(piilotettu: str) -> None:
    assert kortin_tila(kortti(piilotettu)) is None, "esimerkki tai kommentoitu rivi ei hyväksy korttia"
    assert kortin_tila(kortti("- Tila: luonnos", piilotettu)) == "luonnos"
    assert kortin_tila(kortti("- Tila: hyväksytty", piilotettu.replace("Tila: hyväksytty", "Malli: fable"))) == "hyväksytty"


@pytest.mark.parametrize(
    "rivi",
    ["- **Tila:** hyväksytty", "- **Tila**: hyväksytty", "**Tila:** hyväksytty", "- *Tila*: hyväksytty", "- `Tila`: hyväksytty",
     "1. Tila: hyväksytty", "2) Tila: hyväksytty", "+ Tila: hyväksytty", "– Tila: hyväksytty", "• Tila: hyväksytty",
     "- [x] Tila: hyväksytty", "    - Tila: hyväksytty", "\t- Tila: hyväksytty"],
)
def test_metarivi_vaarassa_muodossa_on_virhe_eika_ohitu(rivi: str) -> None:
    with pytest.raises(KorttiVirhe, match="ei ole muotoa '- Tila: <arvo>'"):
        kortin_tila(kortti(rivi))
    with pytest.raises(KorttiVirhe):
        kortin_tila(kortti("- Tila: hyväksytty", rivi))


def test_normalisoi() -> None:
    assert normalisoi("  Opus (oletus; fable vain hyväksytyllä päätöksellä) ") == "opus"
    assert normalisoi("`FABLE`") == "fable" and normalisoi("   ") == ""


@pytest.mark.parametrize(
    "haara, slug",
    [("feature/kortti-x", "kortti-x"), ("feature/laskuri_2.summa", "laskuri_2.summa"), ("kortti-x", None),
     ("feat/kortti-x", None), ("feature/", None), ("feature/Iso-Slug", None), ("feature/a/b", None),
     ("feature/-alku", None), ("refs/heads/feature/kortti-x", None)],
)
def test_slug_haarasta(haara: str, slug: str | None) -> None:
    assert slug_haarasta(haara) == slug
