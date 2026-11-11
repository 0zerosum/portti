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
    "koodilohko",
    ["```\n- Tila: hyväksytty\n```", "```markdown\n- Tila: hyväksytty\n```", "~~~\n- Tila: hyväksytty\n~~~",
     "```\nsulkematon koodilohko\n- Tila: hyväksytty",
     "````markdown\n```text\n- Tila: hyväksytty\n```\n````",
     "```\n```text\n- Tila: hyväksytty\n```",
     "~~~\n```\n- Tila: hyväksytty\n```\n~~~",
     "`````\n```\n- Tila: hyväksytty\n````\n`````",
     "<!-- - Tila: hyväksytty -->"],
)
def test_koodilohkon_sisalto_ei_ole_metatietoa(koodilohko: str) -> None:
    """Aidat CommonMarkin mukaan: lohkon sulkee vain sama merkki vähintään yhtä pitkänä ilman lisätekstiä."""
    assert kortin_tila(kortti(koodilohko)) is None, "esimerkkirivi ei hyväksy korttia"
    assert kortin_tila(kortti("- Tila: luonnos", koodilohko)) == "luonnos"
    assert kortin_tila(kortti("- Tila: hyväksytty", koodilohko.replace("Tila: hyväksytty", "Malli: fable"))) == "hyväksytty"


def test_suljetun_koodilohkon_jalkeinen_rivi_on_kortin_rivi() -> None:
    assert kortin_tila(kortti("```\nesimerkki\n```", "- Tila: hyväksytty")) == "hyväksytty"
    assert kortin_tila(kortti("````\n```\n````", "- Tila: hyväksytty")) == "hyväksytty"
    assert kortin_tila(kortti("teksti ```ei aita``` rivillä", "- Tila: hyväksytty")) == "hyväksytty"


@pytest.mark.parametrize(
    "kommentoitu",
    ["<!--\n- Tila: hyväksytty\n-->", "<!-- sulkematon kommentti\n- Tila: hyväksytty",
     "teksti `<!--` koodina\n- Tila: hyväksytty", "alku <!-- kesken\n- Tila: hyväksytty\n--> loppu"],
)
def test_metarivin_nakoinen_rivi_kommentin_sisalla_on_virhe(kommentoitu: str) -> None:
    """Kommentin rajoja ei arvata: rivi ei hyväksy korttia piilosta eikä näkyvä rivi jää lukematta."""
    with pytest.raises(KorttiVirhe, match="HTML-kommentin sisällä"):
        kortin_tila(kortti(kommentoitu))
    with pytest.raises(KorttiVirhe):
        kortin_tila(kortti("- Tila: luonnos", kommentoitu))


def test_suljettu_kommentti_ei_piilota_seuraavia_riveja() -> None:
    assert kortin_tila(kortti("<!-->", "- Tila: hyväksytty", "<!-- huom -->")) == "hyväksytty"
    assert kortin_tila(kortti("<!--->", "- Tila: luonnos")) == "luonnos"
    assert kortin_tila(kortti("<!-- a --> ja <!-- b -->", "- Tila: hyväksytty")) == "hyväksytty"
    assert kortin_tila(kortti("```\n<!--\n```", "- Tila: hyväksytty")) == "hyväksytty", "koodilohkossa <!-- on tekstiä"
    assert kortin_tila(kortti("- Tila: hyväksytty <!-- huom -->")) != TILA_HYVAKSYTTY, "arvoon jäänyt kommentti ei hyväksy"


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
