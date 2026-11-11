"""Kokoaa kortti-ajon promptin pohjasta (ajo/prompti.md) ja kuluttajan sääntölohkosta sekä työkalulistat.

Erillinen komponentti, ei osa portti-pakettia: ajetaan `python -I` kuluttajan ajossa. Vain vakiokirjasto.
Sallitut työkalut rajataan tiedostojen käsittelyyn, oman haaran git- ja gh-operaatioihin sekä repon
asennus- ja testikomentoihin sanatarkasti. Kielletyt estävät salaisuuksien lukemisen ja tulostamisen
(parhaan kyvyn mukaan).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PERUSTYOKALUT = (
    "Read", "Glob", "Grep", "Edit", "Write", "MultiEdit",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)", "Bash(git rev-parse:*)",
    "Bash(git add:*)", "Bash(git rm:*)", "Bash(git mv:*)", "Bash(git restore:*)", "Bash(git commit:*)",
    "Bash(git fetch origin:*)", "Bash(git switch:*)",
    "Bash(gh pr view:*)", "Bash(gh pr list:*)", "Bash(gh pr create:*)", "Bash(gh pr comment:*)",
    "Bash(gh run list:*)", "Bash(gh run view:*)",
)
# Merkit, jotka rikkoisivat työkalulistan (pilkku erottaa työkalut, sulut rajaavat säännön) tai joita
# actionin argumenttijäsennin tulkitsee (lainaukset, $, kenoviiva, ohjausmerkit).
KIELLETYT_MERKIT = "\"'`$;|&,()<>\\"
KIELLETYT = (
    "Read(./.git/**)", "Bash(env)", "Bash(env:*)", "Bash(printenv)", "Bash(printenv:*)", "Bash(set)",
    "Bash(cat .git/config)", "Bash(git config:*)", "Bash(git remote:*)",
)
PUSH_MUODOT = ("git push -u origin", "git push origin", "git push --set-upstream origin", "git pull --ff-only origin")
SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
EHTOLOHKO = r"\{\{#(uusi|korjaus)\}\}\n?(.*?)\{\{/\1\}\}\n?"


class PromptiVirhe(ValueError):
    """Syöte ei kelpaa promptiin tai työkalulistaan."""


def lue_testikomennot(teksti: str) -> list[str]:
    komennot = [rivi.strip() for rivi in teksti.splitlines() if rivi.strip()]
    if not komennot:
        raise PromptiVirhe("testikomennot puuttuvat")
    for komento in komennot:
        if any(merkki in komento for merkki in KIELLETYT_MERKIT):
            raise PromptiVirhe(f"testikomento ei saa sisältää lainaus-, ohjaus- eikä erotinmerkkejä: {komento}")
    return komennot


def haaran_tyokalut(kortti: str) -> list[str]:
    """Push ja pull vain omaan haaraan: täsmälliset komennot ilman jokerimerkkejä."""
    return [f"Bash({muoto} {kortti})" for muoto in PUSH_MUODOT]


def sallitut_tyokalut(kortti: str, testikomennot: list[str]) -> list[str]:
    return [*PERUSTYOKALUT, *haaran_tyokalut(kortti), *(f"Bash({komento})" for komento in testikomennot)]


def _ehdolliset_lohkot(pohja: str, tila: str) -> str:
    return re.sub(EHTOLOHKO, lambda osuma: osuma.group(2) if osuma.group(1) == tila else "", pohja, flags=re.S)


def kokoa_prompti(pohja: str, arvot: dict[str, str], testikomennot: list[str], saannot: str) -> str:
    tila = "korjaus" if arvot.get("korjaa_pr") else "uusi"
    teksti = _ehdolliset_lohkot(pohja, tila)
    komentolista = "\n".join(f"   - `{komento}`" for komento in testikomennot)
    taytto = dict(arvot, testikomennot=komentolista, saantolohko=saannot.strip())
    for avain, arvo in taytto.items():
        teksti = teksti.replace("{{" + avain + "}}", arvo)
    jaljella = re.findall(r"\{\{[^}]*\}\}", teksti)
    if jaljella:
        raise PromptiVirhe(f"promptiin jäi täyttämättömiä paikkamerkkejä: {', '.join(jaljella)}")
    return teksti


def _jasennin() -> argparse.ArgumentParser:
    jasennin = argparse.ArgumentParser(description="kokoa kortti-ajon prompti ja työkalulistat")
    jasennin.add_argument("--pohja", type=Path, required=True)
    jasennin.add_argument("--kortti", required=True)
    jasennin.add_argument("--korjaa-pr", default="")
    jasennin.add_argument("--oletushaara", required=True)
    jasennin.add_argument("--repo", default="")
    jasennin.add_argument("--testikomennot", required=True, help="yksi komento riviä kohden")
    jasennin.add_argument("--saannot", type=Path, required=True, help="kuluttajan sääntölohko, liitetään sanatarkasti")
    jasennin.add_argument("--prompti", type=Path, required=True, help="kohdetiedosto promptille")
    jasennin.add_argument("--tyokalut", type=Path, required=True, help="kohdetiedosto sallituille työkaluille")
    jasennin.add_argument("--kielletyt", type=Path, required=True, help="kohdetiedosto kielletyille työkaluille")
    return jasennin


def main(argv: list[str] | None = None) -> int:
    argumentit = _jasennin().parse_args(argv)
    try:
        if not SLUG.match(argumentit.kortti):
            raise PromptiVirhe(f"kortin slug ei kelpaa: {argumentit.kortti!r}")
        if argumentit.korjaa_pr and not argumentit.korjaa_pr.isdigit():
            raise PromptiVirhe(f"korjaa_pr ei ole numero: {argumentit.korjaa_pr!r}")
        testikomennot = lue_testikomennot(argumentit.testikomennot)
        arvot = {"kortti": argumentit.kortti, "korjaa_pr": argumentit.korjaa_pr,
                 "oletushaara": argumentit.oletushaara, "repo": argumentit.repo or "(repo)"}
        prompti = kokoa_prompti(argumentit.pohja.read_text(encoding="utf-8"), arvot, testikomennot,
                                argumentit.saannot.read_text(encoding="utf-8"))
    except (PromptiVirhe, OSError) as virhe:
        print(f"kokoa_prompti: {virhe}", file=sys.stderr)
        return 2
    argumentit.prompti.write_text(prompti, encoding="utf-8")
    argumentit.tyokalut.write_text(",".join(sallitut_tyokalut(argumentit.kortti, testikomennot)) + "\n", encoding="utf-8")
    argumentit.kielletyt.write_text(",".join(KIELLETYT) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
