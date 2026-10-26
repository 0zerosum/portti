"""Kommentin renderöinti ja idempotentti päivitys vale-gh:lla."""

from typing import Any

from portti.kommentti import TUNNISTE, kirjoita_tai_paivita, lue_konedata, renderoi
from tests.apu_gh import ValeGh


def evidence(verdict: str = "KOVA") -> dict[str, Any]:
    return {
        "evidence_muoto": 1,
        "moottorin_versio": "0.1.0",
        "verdict": verdict,
        "tila": "shadow",
        "head_sha": "abcdef1234567890",
        "hyvaksyttavissa_portaalla": [] if verdict == "KOVA" else ["S1", "S2", "S3"],
        "luokitus": {
            "tier": "T1a",
            "rivit": 3,
            "tiedostoja": 1,
            "alueet": ["palvelin/laskenta"],
            "deny_osumat": [
                {"kategoria": "agenttiohjeet", "taso": "kova", "polku": "CLAUDE.md", "malli": "CLAUDE.md"}
            ] if verdict == "KOVA" else [],
        },
        "portit": [
            {"nimi": "kova_deny", "ok": verdict != "KOVA", "syy": "CLAUDE.md (agenttiohjeet)"},
            {"nimi": "koko", "ok": True, "syy": "3 riviä -> T1a"},
        ],
    }


def test_renderointi_on_deterministinen_ja_sisaltaa_kentat() -> None:
    teksti = renderoi(evidence(), "https://example.com/artefakti")
    assert teksti == renderoi(evidence(), "https://example.com/artefakti")
    assert teksti.startswith(TUNNISTE)
    assert "**KOVA**" in teksti and "| Tier | T1a |" in teksti
    assert "| Koskettu | palvelin/laskenta |" in teksti
    assert "kova · agenttiohjeet: `CLAUDE.md`" in teksti
    assert "✗ kova_deny" in teksti and "✓ koko" in teksti
    assert "[evidence-artefakti](https://example.com/artefakti)" in teksti
    assert "head `abcdef123456`" in teksti


def test_konedata_luetaan_takaisin() -> None:
    teksti = renderoi(evidence("VAPAA"), None)
    konedata = lue_konedata(teksti)
    assert konedata == {"verdict": "VAPAA", "tier": "T1a", "head_sha": "abcdef1234567890", "moottorin_versio": "0.1.0"}
    assert "evidence-artefakti puuttuu" in teksti
    assert lue_konedata("ihmisen kommentti") is None


def test_kommentti_luodaan_kun_ei_ole() -> None:
    vale = ValeGh({"issues/5/comments": []})
    assert kirjoita_tai_paivita(vale.api(), "omistaja/repo", 5, "teksti") == "luotu"
    assert vale.metodit() == ["api --paginate", "api -X"]
    assert vale.kutsut[1][0][2] == "POST" and '"body": "teksti"' in (vale.kutsut[1][1] or "")


def test_kommentti_paivitetaan_eika_luoda_uutta() -> None:
    vanha = {"id": 42, "body": TUNNISTE + "\nvanha"}
    vale = ValeGh({"issues/5/comments": [[{"id": 1, "body": "ihminen"}, vanha]]})
    assert kirjoita_tai_paivita(vale.api(), "omistaja/repo", 5, TUNNISTE + "\nuusi") == "päivitetty"
    patch = vale.kutsut[1][0]
    assert patch[2] == "PATCH" and patch[3].endswith("/comments/42")


def test_sama_teksti_ei_aiheuta_kutsua() -> None:
    teksti = TUNNISTE + "\nsama"
    vale = ValeGh({"issues/5/comments": [[{"id": 42, "body": teksti}]]})
    assert kirjoita_tai_paivita(vale.api(), "omistaja/repo", 5, teksti) == "ennallaan"
    assert len(vale.kutsut) == 1
