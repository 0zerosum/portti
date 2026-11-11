"""Kortin metarivien luku: tilarivi, kirjainkoko, sulkuhuomautus, kaksoisrivit, kortin alkuosa ja runko,
väärässä muodossa olevat rivit ja kortin haaran slug."""

import pytest

from portti.kortti import TILA_HYVAKSYTTY, KorttiVirhe, kortin_tila, lue_kentta, normalisoi, rungon_arvot, slug_haarasta


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


ALKU = "# Keksitty kortti\n\n- Tila: luonnos\n- Malli: opus\n\n"
RAKENTEEN_AVAAJAT = [
    "## Tausta", "### Meta", "---", "- - -", "***", "___", "```", "```markdown", "~~~", "  ```", "- ```", "> ```", "1. ```",
    "$$", "<details>", "- <details>", "<div>", "</div>", "<!--", "<!-->", "teksti <!-- kommentti -->", "> <!-- x", "<?php",
]


@pytest.mark.parametrize("avaaja", RAKENTEEN_AVAAJAT)
def test_valiotsikko_tai_rakenteen_avaava_rivi_paattaa_alkuosan(avaaja: str) -> None:
    """Rivin näkyvyyttä ei arvata: koodilohkon, kaavan, HTML:n tai kommentin jälkeinen rivi ei ole metarivi."""
    assert kortin_tila(f"# Keksitty kortti\n\n{avaaja}\n- Tila: hyväksytty\n") is None
    assert kortin_tila(f"{ALKU}{avaaja}\n- Tila: hyväksytty\n") == "luonnos", "rungon rivi ei muuta alkuosan tilaa"
    assert rungon_arvot(f"{ALKU}{avaaja}\n- Tila: hyväksytty\n", "Tila") == ["hyväksytty"]


def test_kortin_otsikko_ja_johdanto_kuuluvat_alkuosaan() -> None:
    assert kortin_tila("# Kortti\n\nJohdantokappale, jossa on `koodia` ja <slug>.\n\n- Tila: hyväksytty\n") == "hyväksytty"
    assert kortin_tila("## Kortti toisen tason otsikolla\n- Tila: hyväksytty\n") == "hyväksytty"
    assert kortin_tila("- Tila: hyväksytty\n# Otsikko vasta tämän jälkeen\n") == "hyväksytty"
    assert kortin_tila("\ufeff# Kortti\r\n- Tila: hyväksytty\r\n") == "hyväksytty"
    assert kortin_tila("Kortti\n======\n- Tila: hyväksytty\n") == "hyväksytty", "alleviivattu pääotsikko"
    assert kortin_tila("# Kortti\n# Toinen otsikko\n- Tila: hyväksytty\n") is None
    assert kortin_tila("---\ntila: hyväksytty\n---\n- Tila: hyväksytty\n") is None, "etumateriaali päättää alkuosan"
    assert kortin_tila("# <!-- kommentti otsikossa\n- Tila: hyväksytty\n") is None


def test_vain_markdownin_rivinvaihdot_katkaisevat_rivin() -> None:
    assert kortin_tila(kortti("- Ok: 1\u2028- Tila: hyväksytty")) is None
    assert kortin_tila(kortti("- Ok: 1\x0b- Tila: hyväksytty")) is None
    assert kortin_tila(kortti("x\x0b```", "- Tila: hyväksytty")) == "hyväksytty", "rivin keskellä oleva aita on tekstiä"
    assert kortin_tila("# Kortti\r- Tila: hyväksytty\r") == "hyväksytty"


def test_rungon_arvot_kaikissa_muodoissa() -> None:
    runko = "## Tausta\n- Malli: Fable\n1. **Malli:** `sonnet`\n    - Malli: tilausmalliin uusi kenttä (huom)\nMalli: ei rivi\n"
    assert rungon_arvot(ALKU + runko, "Malli") == ["fable", "sonnet", "tilausmalliin uusi kenttä"]
    assert rungon_arvot(ALKU, "Malli") == [], "alkuosan rivi ei ole rungon rivi"


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
