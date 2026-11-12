"""Kortti-ajon yhteenveto: suoritustiedoston luku, PR:n kuvauksen lohko ja käytettyjen mallien tarkistus."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SKRIPTI = Path(__file__).resolve().parent.parent / "ajo" / "ajon_yhteenveto.py"
OPUS = "claude-opus-5-5"
SALLITUT = "claude-fable-5-1,claude-opus-5-5"
OPUKSEN_KAYTTO = {"inputTokens": 1000, "outputTokens": 300, "cacheReadInputTokens": 400, "cacheCreationInputTokens": 100,
                  "costUSD": 3.21, "contextWindow": 1000000, "maxOutputTokens": 128000}


def suoritustiedosto(tmp_path: Path, mallien_kaytto: dict[str, Any] | None = None, **tulos: Any) -> Path:
    tulosviesti = {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 723456, "num_turns": 41,
                   "total_cost_usd": 3.2149, "modelUsage": mallien_kaytto if mallien_kaytto is not None else {OPUS: OPUKSEN_KAYTTO}}
    tulosviesti.update(tulos)
    viestit = [{"type": "system", "subtype": "init", "model": OPUS}, {"type": "assistant", "message": {"content": []}}, tulosviesti]
    polku = tmp_path / "claude-execution-output.json"
    polku.write_text(json.dumps(viestit), encoding="utf-8")
    return polku


def aja(tmp_path: Path, suoritus: Path, kuvaus: str | None = None, ajo: str = "uusi kortti") -> tuple[int, str, str, str | None]:
    yhteenveto, ulos = tmp_path / "yhteenveto.md", tmp_path / "kuvaus-jalkeen.md"
    komento = [sys.executable, "-I", str(SKRIPTI), "--suoritus", str(suoritus), "--kortti", "kortti-x", "--ajo", ajo,
               "--malli", OPUS, "--lahde", "oletus", "--sallitut", SALLITUT, "--yhteenveto", str(yhteenveto)]
    if kuvaus is not None:
        ennen = tmp_path / "kuvaus-ennen.md"
        ennen.write_text(kuvaus, encoding="utf-8")
        komento += ["--kuvaus", str(ennen), "--kuvaus-ulos", str(ulos)]
    tulos = subprocess.run(komento, capture_output=True, text=True)
    paivitetty = ulos.read_text(encoding="utf-8") if ulos.exists() else None
    return tulos.returncode, tulos.stderr, yhteenveto.read_text(encoding="utf-8"), paivitetty


def test_yhteenveto_ja_uusi_lohko_kuvaukseen(tmp_path: Path) -> None:
    koodi, _, yhteenveto, kuvaus = aja(tmp_path, suoritustiedosto(tmp_path), "Kortti kortti-x.\n\nEi ajettu oikealla datalla.\n")
    assert koodi == 0
    rivi = f"| uusi kortti, kortti kortti-x | {OPUS} | oletus | 12 min 3 s | 41 | 1500 / 300 | 3.21 | {OPUS} |"
    assert "## Kortti-ajo" in yhteenveto and rivi in yhteenveto
    assert kuvaus is not None and kuvaus.startswith("Kortti kortti-x.\n\nEi ajettu oikealla datalla.\n\n<!-- portti-ajot:alku -->")
    assert rivi in kuvaus and kuvaus.rstrip().endswith("<!-- portti-ajot:loppu -->")
    _, _, _, tyhjaan = aja(tmp_path, suoritustiedosto(tmp_path), "")
    assert tyhjaan is not None and tyhjaan.startswith("<!-- portti-ajot:alku -->")


def test_korjauskierros_lisaa_rivin_samaan_lohkoon(tmp_path: Path) -> None:
    _, _, _, eka = aja(tmp_path, suoritustiedosto(tmp_path), "Kuvaus.\n")
    assert eka is not None
    _, _, _, toka = aja(tmp_path, suoritustiedosto(tmp_path, duration_ms=61000, num_turns=7), eka + "\nIhmisen lisäys.\n",
                        ajo="korjauskierros PR 7")
    assert toka is not None
    assert toka.count("<!-- portti-ajot:alku -->") == 1 and toka.count("**Kortti-ajot**") == 1
    assert "| uusi kortti, kortti kortti-x |" in toka and "| korjauskierros PR 7, kortti kortti-x |" in toka
    assert "1 min 1 s | 7 |" in toka and toka.rstrip().endswith("Ihmisen lisäys."), "muu kuvaus säilyy"
    assert toka.index("uusi kortti") < toka.index("korjauskierros PR 7") < toka.index("<!-- portti-ajot:loppu -->")


def test_luvaton_malli_kaataa_mutta_kuvaus_paivittyy(tmp_path: Path) -> None:
    kaytto = {OPUS: OPUKSEN_KAYTTO, "claude-haiku-5-5": {"inputTokens": 10, "outputTokens": 5}}
    koodi, virhe, yhteenveto, kuvaus = aja(tmp_path, suoritustiedosto(tmp_path, kaytto), "Kuvaus.\n")
    assert koodi == 1 and "::error::" in virhe and "claude-haiku-5-5" in virhe and OPUS not in virhe.split("sallittu:")[1]
    assert "Ajo käytti mallia, joka ei ole sallittu: claude-haiku-5-5." in yhteenveto
    assert kuvaus is not None and f"claude-haiku-5-5, {OPUS} |" in kuvaus


def test_versiopaate_sallitun_tunnisteen_perassa_kelpaa(tmp_path: Path) -> None:
    kaytto = {"claude-opus-5-5-20260601": OPUKSEN_KAYTTO, "claude-fable-5-1[1m]": {"inputTokens": 1, "outputTokens": 1}}
    koodi, virhe, _, _ = aja(tmp_path, suoritustiedosto(tmp_path, kaytto))
    assert koodi == 0 and virhe == ""
    assert aja(tmp_path, suoritustiedosto(tmp_path, {"claude-opus-5-5-20260601[1m]": OPUKSEN_KAYTTO}))[0] == 0
    for muu in ("claude-opus-5", "claude-opus-5-5-x", "claude-opus-5-50", "claude-opus-5-5-2026", "claude-opus-5-5[2m]"):
        assert aja(tmp_path, suoritustiedosto(tmp_path, {muu: OPUKSEN_KAYTTO}))[0] == 1, f"{muu} ei ole sallittu tunniste"


def test_puuttuva_tai_rikkinainen_suoritustiedosto_kirjataan_ja_kaataa(tmp_path: Path) -> None:
    """Jos käytettyjä malleja ei voi todentaa, tarkistus ei mene läpi: tieto ei puutu hiljaa."""
    koodi, virhe, yhteenveto, kuvaus = aja(tmp_path, tmp_path / "ei-ole.json", "Kuvaus.\n")
    assert koodi == 1 and "suoritustiedostoa ei ole" in yhteenveto
    assert "::error::Käytettyjä malleja ei voitu todentaa" in virhe and "Käytettyjä malleja ei voitu todentaa" in yhteenveto
    assert kuvaus is not None and f"| {OPUS} | oletus | ei tietoa | ei tietoa | ei tietoa | ei tietoa | ei tietoa |" in kuvaus
    rikki = tmp_path / "rikki.json"
    rikki.write_text("{ei jsonia", encoding="utf-8")
    koodi_rikki, _, yhteenveto_rikki, _ = aja(tmp_path, rikki)
    assert koodi_rikki == 1 and "suoritustiedostoa ei voitu lukea" in yhteenveto_rikki
    ilman_tulosta = tmp_path / "ilman.json"
    ilman_tulosta.write_text('[{"type": "system"}]', encoding="utf-8")
    koodi_ilman, _, yhteenveto_ilman, _ = aja(tmp_path, ilman_tulosta)
    assert koodi_ilman == 1 and "ei ole tulosviestiä" in yhteenveto_ilman
    koodi_tyhja, virhe_tyhja, _, _ = aja(tmp_path, suoritustiedosto(tmp_path, {}))
    assert koodi_tyhja == 1 and "ei voitu todentaa" in virhe_tyhja, "tulosviesti ilman mallikohtaista käyttöä ei kelpaa"


def test_tokenit_yhteiskentasta_kun_mallikohtaiset_puuttuvat(tmp_path: Path) -> None:
    kaytto = {OPUS: {"contextWindow": 1000000, "maxOutputTokens": 128000}}
    yhteensa = {"input_tokens": 20, "cache_read_input_tokens": 70, "cache_creation_input_tokens": 10, "output_tokens": 9}
    _, _, yhteenveto, _ = aja(tmp_path, suoritustiedosto(tmp_path, kaytto, usage=yhteensa))
    assert "| 100 / 9 |" in yhteenveto
    _, _, ilman, _ = aja(tmp_path, suoritustiedosto(tmp_path, kaytto))
    assert "| 41 | ei tietoa | 3.21 |" in ilman
