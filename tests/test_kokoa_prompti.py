"""Kortti-ajon promptin kokoaja: ehdolliset lohkot, sääntölohko sanatarkasti, työkalulistat, aliagentti ja asetukset."""

import json
import subprocess
import sys
from pathlib import Path

POHJA = Path(__file__).resolve().parent.parent / "ajo" / "prompti.md"
KOKOAJA = Path(__file__).resolve().parent.parent / "ajo" / "kokoa_prompti.py"
SAANNOT = "## Yhteiset säännöt\n\n1. Ei oikeita sähköposteja; käytä esimerkki@example.com.\n"
OPUS = "claude-opus-5-5"


def aja(tmp_path: Path, **muutokset: str) -> tuple[int, str, Path]:
    saannot = tmp_path / "saannot.md"
    saannot.write_text(SAANNOT, encoding="utf-8")
    tulosteet = tmp_path / "tulosteet"
    argumentit = {
        "--pohja": str(POHJA), "--kortti": "kortti-x", "--korjaa-pr": "", "--oletushaara": "main",
        "--repo": "esimerkki/tilaukset", "--testikomennot": "python -m pytest -q\npython -m mypy --strict sovellus",
        "--saannot": str(saannot), "--malli-label": "malli-opus", "--tarkistajan-malli": OPUS,
        "--tilarivit": "true", "--tulosteet": str(tulosteet),
    }
    argumentit.update(muutokset)
    komento = [sys.executable, "-I", str(KOKOAJA), *[osa for pari in argumentit.items() for osa in pari]]
    tulos = subprocess.run(komento, capture_output=True, text=True)
    return tulos.returncode, tulos.stderr, Path(argumentit["--tulosteet"])


def lue(tulosteet: Path, nimi: str) -> str:
    return (tulosteet / nimi).read_text(encoding="utf-8")


def test_uuden_kortin_prompti(tmp_path: Path) -> None:
    koodi, _, tulosteet = aja(tmp_path)
    assert koodi == 0
    teksti = lue(tulosteet, "prompti.md")
    assert "Rakenna kortti `kortit/kortti-x.md` PR:ksi." in teksti and "Korjauskierros" not in teksti
    assert "git switch -c feature/kortti-x origin/main" in teksti
    assert "--label agentti" in teksti and "--label malli-opus" in teksti
    assert "   - `python -m pytest -q`\n   - `python -m mypy --strict sovellus`" in teksti
    assert "tyyppi `tarkistaja`" in teksti and "git diff origin/main...HEAD" in teksti
    assert 'rivi "Ei ajettu oikealla datalla."' in teksti and "hyväksymiskriteeri" in teksti
    assert SAANNOT.strip() in teksti, "sääntölohko sanatarkasti"
    assert "{{" not in teksti


def test_tilarivit_ovat_valinnaiset(tmp_path: Path) -> None:
    _, _, paalla = aja(tmp_path)
    teksti = lue(paalla, "prompti.md")
    assert "`- Tila: työn alla`" in teksti and "`- Tila: PR`" in teksti
    assert "Älä muuta korttia" not in teksti
    koodi, _, pois = aja(tmp_path, **{"--tilarivit": "false", "--tulosteet": str(tmp_path / "ilman")})
    assert koodi == 0
    ilman = lue(pois, "prompti.md")
    assert "- Tila: työn alla" not in ilman and "- Tila: PR" not in ilman
    assert "Älä muuta korttia `kortit/kortti-x.md`" in ilman and "{{" not in ilman


def test_tyokalulistat_rajaavat_pushin_omaan_haaraan(tmp_path: Path) -> None:
    _, _, tulosteet = aja(tmp_path)
    lista = lue(tulosteet, "tyokalut.txt").strip().split(",")
    assert "Bash(git push -u origin feature/kortti-x)" in lista and "Bash(python -m pytest -q)" in lista
    assert "Read" in lista and "Agent" in lista and "Bash(gh run view:*)" in lista and "Bash(git rm:*)" in lista
    assert "mcp__github_ci" not in lista, "CI-työkalupalvelin ei ole käytössä workflow_dispatch-ajossa"
    assert not any(tyokalu.startswith("Bash(git push:") for tyokalu in lista)
    assert all(tyokalu.count("(") <= 1 for tyokalu in lista), "pilkku tai sulku komennossa rikkoisi listan"
    assert "Read(./.git/**)" in lue(tulosteet, "kielletyt.txt")


def test_aliagentti_ja_asetukset_lukitsevat_mallin(tmp_path: Path) -> None:
    _, _, tulosteet = aja(tmp_path)
    agentit_teksti = lue(tulosteet, "agentit.json")
    assert agentit_teksti.count("\n") == 1 and "'" not in agentit_teksti, "annetaan heittomerkkien sisällä yhtenä rivinä"
    agentit = json.loads(agentit_teksti)
    assert list(agentit) == ["tarkistaja"]
    assert agentit["tarkistaja"]["model"] == OPUS and agentit["tarkistaja"]["tools"] == ["Read", "Grep", "Glob", "Bash"]
    assert "Et ole nähnyt, miten muutos tehtiin" in agentit["tarkistaja"]["prompt"]
    asetukset_teksti = lue(tulosteet, "asetukset.json")
    assert asetukset_teksti.count("\n") == 1 and "'" not in asetukset_teksti
    assert json.loads(asetukset_teksti) == {"env": {
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": OPUS, "ANTHROPIC_DEFAULT_SONNET_MODEL": OPUS,
        "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",
        "CLAUDE_CODE_SUBAGENT_MODEL": OPUS, "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1",
    }}


def test_korjauskierroksen_prompti(tmp_path: Path) -> None:
    koodi, _, tulosteet = aja(tmp_path, **{"--korjaa-pr": "7"})
    assert koodi == 0
    teksti = lue(tulosteet, "prompti.md")
    assert "Korjauskierros PR:lle #7 (haara `feature/kortti-x`" in teksti and "Rakenna kortti" not in teksti
    assert "gh pr view 7 --comments" in teksti and "git push origin feature/kortti-x" in teksti
    assert "gh run list --branch feature/kortti-x" in teksti and "gh pr comment 7" in teksti
    assert "- Tila: työn alla" not in teksti and "{{" not in teksti


def test_kelvoton_syote_kaataa_eika_kirjoita_mitaan(tmp_path: Path) -> None:
    kelvottomat: list[dict[str, str]] = [
        {"--kortti": "Iso Slug"}, {"--korjaa-pr": "seitsemän"}, {"--testikomennot": "  \n"},
        {"--saannot": str(tmp_path / "ei-ole.md")}, {"--malli-label": "opus"}, {"--malli-label": "malli-Opus 5"},
        {"--tarkistajan-malli": "claude opus"}, {"--tarkistajan-malli": ""},
    ]
    kelvottomat += [{"--testikomennot": komento} for komento in
                    ('echo "x"', "pytest -k a,b", "pytest -k (a)", "pytest > loki.txt", "pytest $VALINNAT", "pytest \\")]
    for indeksi, muutos in enumerate(kelvottomat):
        koodi, virhe, tulosteet = aja(tmp_path, **{**muutos, "--tulosteet": str(tmp_path / f"kelvoton-{indeksi}")})
        assert koodi == 2 and "kokoa_prompti:" in virhe, muutos
        assert not tulosteet.exists(), muutos
    koodi, virhe, _ = aja(tmp_path, **{"--testikomennot": 'echo "x"'})
    assert koodi == 2 and "lainaus" in virhe
