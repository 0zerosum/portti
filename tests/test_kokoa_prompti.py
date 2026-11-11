"""Kortti-ajon promptin kokoaja: ehdolliset lohkot, sääntölohko sanatarkasti, työkalulistat ja syötteiden tarkistus."""

import subprocess
import sys
from pathlib import Path

POHJA = Path(__file__).resolve().parent.parent / "ajo" / "prompti.md"
KOKOAJA = Path(__file__).resolve().parent.parent / "ajo" / "kokoa_prompti.py"
SAANNOT = "## Yhteiset säännöt\n\n1. Ei oikeita sähköposteja; käytä esimerkki@example.com.\n"


def aja(tmp_path: Path, **muutokset: str) -> tuple[int, str, Path, Path, Path]:
    saannot = tmp_path / "saannot.md"
    saannot.write_text(SAANNOT, encoding="utf-8")
    prompti, tyokalut, kielletyt = tmp_path / "prompti.md", tmp_path / "tyokalut.txt", tmp_path / "kielletyt.txt"
    argumentit = {
        "--pohja": str(POHJA), "--kortti": "kortti-x", "--korjaa-pr": "", "--oletushaara": "main",
        "--repo": "esimerkki/tilaukset", "--testikomennot": "python -m pytest -q\npython -m mypy --strict sovellus",
        "--saannot": str(saannot), "--prompti": str(prompti), "--tyokalut": str(tyokalut), "--kielletyt": str(kielletyt),
    }
    argumentit.update(muutokset)
    komento = [sys.executable, "-I", str(KOKOAJA), *[osa for pari in argumentit.items() for osa in pari]]
    tulos = subprocess.run(komento, capture_output=True, text=True)
    return tulos.returncode, tulos.stderr, prompti, tyokalut, kielletyt


def test_uuden_kortin_prompti(tmp_path: Path) -> None:
    koodi, _, prompti, tyokalut, kielletyt = aja(tmp_path)
    assert koodi == 0
    teksti = prompti.read_text(encoding="utf-8")
    assert "Rakenna kortti `kortit/kortti-x.md` PR:ksi." in teksti and "Korjauskierros" not in teksti
    assert "git switch -c kortti-x origin/main" in teksti and "--label agentti" in teksti
    assert "   - `python -m pytest -q`\n   - `python -m mypy --strict sovellus`" in teksti
    assert SAANNOT.strip() in teksti, "sääntölohko sanatarkasti"
    assert "{{" not in teksti
    lista = tyokalut.read_text(encoding="utf-8").strip().split(",")
    assert "Bash(git push -u origin kortti-x)" in lista and "Bash(python -m pytest -q)" in lista
    assert "Read" in lista and "Bash(gh run view:*)" in lista and "Bash(git rm:*)" in lista
    assert "mcp__github_ci" not in lista, "CI-työkalupalvelin ei ole käytössä workflow_dispatch-ajossa"
    assert not any(tyokalu.startswith("Bash(git push:") for tyokalu in lista)
    assert all(tyokalu.count("(") <= 1 for tyokalu in lista), "pilkku tai sulku komennossa rikkoisi listan"
    assert "Read(./.git/**)" in kielletyt.read_text(encoding="utf-8")


def test_korjauskierroksen_prompti(tmp_path: Path) -> None:
    koodi, _, prompti, _, _ = aja(tmp_path, **{"--korjaa-pr": "7"})
    assert koodi == 0
    teksti = prompti.read_text(encoding="utf-8")
    assert "Korjauskierros PR:lle #7" in teksti and "Rakenna kortti" not in teksti
    assert "gh pr view 7 --comments" in teksti and "git push origin kortti-x" in teksti
    assert "gh run list --branch kortti-x" in teksti and "gh pr comment 7" in teksti


def test_kelvoton_syote_kaataa(tmp_path: Path) -> None:
    assert aja(tmp_path, **{"--kortti": "Iso Slug"})[0] == 2
    assert aja(tmp_path, **{"--korjaa-pr": "seitsemän"})[0] == 2
    koodi, virhe, _, _, _ = aja(tmp_path, **{"--testikomennot": 'echo "x"'})
    assert koodi == 2 and "lainaus" in virhe
    for komento in ("pytest -k a,b", "pytest -k (a)", "pytest > loki.txt", "pytest $VALINNAT", "pytest \\"):
        assert aja(tmp_path, **{"--testikomennot": komento})[0] == 2, komento
    assert aja(tmp_path, **{"--testikomennot": "  \n"})[0] == 2
    assert aja(tmp_path, **{"--saannot": str(tmp_path / "ei-ole.md")})[0] == 2
