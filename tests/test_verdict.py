"""Verdict-sääntö: järjestys ja portaat rakennetuilla luokituksilla."""

from portti.invariantit import InvarianttiTulos
from portti.luokittelu import DenyOsuma, Luokitus
from portti.verdict import KOVA, LIIAN_ISO, PEHMEA, PUUTE, VAPAA, hyvaksyttavissa_portaalla, laske_verdict


def luokitus(**muutokset: object) -> Luokitus:
    pohja: dict[str, object] = {
        "tiedostot": [],
        "substantiiviset": ["a/b/x.py"],
        "rivit": 5,
        "alueet": ["a/b"],
        "deny_osumat": [],
        "kielletyt_uudet": [],
        "tier": "T1a",
        "invariantit": [],
        "testimaara": None,
        "puutteet": [],
    }
    pohja.update(muutokset)
    return Luokitus(**pohja)  # type: ignore[arg-type]


KOVA_OSUMA = DenyOsuma("agenttiohjeet", "kova", "CLAUDE.md", "CLAUDE.md")
PEHMEA_OSUMA = DenyOsuma("varasto", "pehmea", "a/b/x.py", "a/**")


def test_vapaa_kun_mikaan_portti_ei_laukea() -> None:
    tulos = laske_verdict(luokitus())
    assert tulos.verdict == VAPAA
    assert all(portti.ok for portti in tulos.portit)
    assert tulos.hyvaksyttavissa_portaalla == ["S1", "S2", "S3"]


def test_puute_voittaa_kaiken() -> None:
    tulos = laske_verdict(
        luokitus(puutteet=["PR on luonnos"], deny_osumat=[KOVA_OSUMA], tier="YLI")
    )
    assert tulos.verdict == PUUTE
    assert tulos.hyvaksyttavissa_portaalla == []


def test_kova_voittaa_koon_ja_pehmean() -> None:
    tulos = laske_verdict(luokitus(deny_osumat=[KOVA_OSUMA, PEHMEA_OSUMA], tier="YLI"))
    assert tulos.verdict == KOVA
    assert next(portti for portti in tulos.portit if portti.nimi == "kova_deny").syy == "CLAUDE.md (agenttiohjeet)"


def test_kielletty_uusi_polku_on_kova() -> None:
    tulos = laske_verdict(luokitus(kielletyt_uudet=[("src/posti/x.py", "**/posti/**")]))
    assert tulos.verdict == KOVA


def test_rikkoutunut_invariantti_on_kova() -> None:
    tulos = laske_verdict(luokitus(invariantit=[InvarianttiTulos("tests/test_x.py", False, "puuttuu headista")]))
    assert tulos.verdict == KOVA
    assert "tests/test_x.py: puuttuu headista" in next(p.syy for p in tulos.portit if p.nimi == "invariantit")


def test_liian_iso_voittaa_pehmean() -> None:
    tulos = laske_verdict(luokitus(tier="YLI", deny_osumat=[PEHMEA_OSUMA], rivit=400))
    assert tulos.verdict == LIIAN_ISO
    assert tulos.hyvaksyttavissa_portaalla == []


def test_pehmea_t1_ei_ole_hyvaksyttavissa_millaan_portaalla() -> None:
    tulos = laske_verdict(luokitus(deny_osumat=[PEHMEA_OSUMA]))
    assert tulos.verdict == PEHMEA
    assert tulos.hyvaksyttavissa_portaalla == []


def test_pehmea_t0_on_hyvaksyttavissa_kaikilla_portailla() -> None:
    tulos = laske_verdict(luokitus(deny_osumat=[PEHMEA_OSUMA], tier="T0", substantiiviset=[], rivit=0))
    assert tulos.verdict == PEHMEA
    assert tulos.hyvaksyttavissa_portaalla == ["S0", "S1", "S2", "S3"]


def test_portaat_tierin_mukaan() -> None:
    assert hyvaksyttavissa_portaalla(VAPAA, "T0") == ["S0", "S1", "S2", "S3"]
    assert hyvaksyttavissa_portaalla(VAPAA, "T1b") == ["S2", "S3"]
    assert hyvaksyttavissa_portaalla(VAPAA, "T1c") == ["S3"]
    assert hyvaksyttavissa_portaalla(VAPAA, "YLI") == []
    assert hyvaksyttavissa_portaalla(KOVA, "T0") == []
