"""Kokoaa kortti-ajon promptin pohjasta (ajo/prompti.md) ja kuluttajan sääntölohkosta sekä työkalulistat,
tarkistaja-aliagentin määrittelyn ja Claude Coden asetukset.

Erillinen komponentti, ei osa portti-pakettia: ajetaan `python -I` kuluttajan ajossa. Vain vakiokirjasto.
Sallitut työkalut rajataan tiedostojen käsittelyyn, oman haaran git- ja gh-operaatioihin sekä repon
asennus- ja testikomentoihin sanatarkasti. Kielletyt estävät salaisuuksien lukemisen ja tulostamisen
(parhaan kyvyn mukaan). Kaikki aliagentit pakotetaan tarkistajan malliin ja aliakset sonnet ja haiku
ohjataan samaan malliin, jotta ajo ei käytä valittua mallia heikompaa mallia.

Korjauskierroksessa promptiin liitetään PR:n kommenteista vain portin ja ohjauksen omat kommentit
(kirjoittajan ja tunnisteen mukaan). Muiden kommentoijien teksti ei päädy agentille, eikä agentilla ole
työkalua PR:n kommenttien lukemiseen. Sääntölohko, testikomennot ja kommentit liitetään sanatarkasti:
niiden sisältöä ei tulkita paikkamerkeiksi.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PERUSTYOKALUT = (
    "Read", "Glob", "Grep", "Edit", "Write", "MultiEdit", "Agent",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)", "Bash(git rev-parse:*)",
    "Bash(git add:*)", "Bash(git rm:*)", "Bash(git mv:*)", "Bash(git restore:*)", "Bash(git commit:*)",
    "Bash(git fetch origin:*)", "Bash(git switch:*)",
    "Bash(gh run list:*)", "Bash(gh run view:*)",
)
# Merkit, jotka rikkoisivat työkalulistan (pilkku erottaa työkalut, sulut rajaavat säännön, tähti on jokeri)
# tai joita actionin argumenttijäsennin tulkitsee (lainaukset, $, kenoviiva, ohjausmerkit).
KIELLETYT_MERKIT = "\"'`$;|&,()<>\\*"
KIELLETYT = (
    "Read(./.git/**)", "Bash(env)", "Bash(env:*)", "Bash(printenv)", "Bash(printenv:*)", "Bash(set)",
    "Bash(cat .git/config)", "Bash(git config:*)", "Bash(git remote:*)",
)
PUSH_MUODOT = ("git push -u origin", "git push origin", "git push --set-upstream origin", "git pull --ff-only origin")
SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
MALLITUNNISTE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")
MALLI_LABEL = re.compile(r"^malli-[a-z0-9-]{1,40}$")
HAARAN_ETULIITE = "feature/"
EHTOLOHKO = r"\{\{#(uusi|korjaus|tilarivit|ei_tilariveja)\}\}\n?(.*?)\{\{/\1\}\}\n?"
PAIKKAMERKKI = re.compile(r"\{\{([^}]*)\}\}")

# Samat arvot kuin moottorissa (portti/kommentti.py ja portti/ohjaus_kommentti.py); testi vertaa ne.
PORTIN_TUNNISTE = "<!-- portti-kommentti v1"
OHJAUKSEN_TUNNISTE = "<!-- portti-ohjaus v1 -->"
KOMMENTOIJA = "github-actions[bot]"
KOMMENTIN_ENIMMAISPITUUS = 20000
EI_KOMMENTTEJA = "(Portin tai ohjauksen kommenttia ei löytynyt PR:stä.)"

TARKISTAJA = "tarkistaja"
TARKISTAJAN_KUVAUS = "Tarkistaa kortti-ajon muutoksen korttia vasten puhtaalla kontekstilla ennen PR:n avaamista."
TARKISTAJAN_PROMPTI = (
    "Olet tarkistaja. Et ole nähnyt, miten muutos tehtiin. Lue vain sinulle nimetty kortti, repon CLAUDE.md ja "
    "sinulle annetun git diff -komennon tuloste. Älä muokkaa tiedostoja. Tarkista: täyttääkö muutos kortin "
    "hyväksymiskriteerin, pysyykö se kortin rajauksessa, rikkooko se CLAUDE.md:n sääntöjä, puuttuuko testejä ja "
    "onko muutoksessa virheitä. Palauta löydökset tärkeysjärjestyksessä: tiedosto ja rivi, mikä on vialla ja miksi. "
    "Jos löydöksiä ei ole, sano se suoraan."
)
TARKISTAJAN_TYOKALUT = ["Read", "Grep", "Glob", "Bash"]


class PromptiVirhe(ValueError):
    """Syöte ei kelpaa promptiin, työkalulistaan tai asetuksiin."""


def lue_testikomennot(teksti: str) -> list[str]:
    komennot = [rivi.strip() for rivi in teksti.splitlines() if rivi.strip()]
    if not komennot:
        raise PromptiVirhe("testikomennot puuttuvat")
    for komento in komennot:
        if any(merkki in komento for merkki in KIELLETYT_MERKIT):
            raise PromptiVirhe(f"testikomento ei saa sisältää lainaus-, ohjaus- eikä erotinmerkkejä: {komento}")
    return komennot


def haaran_tyokalut(haara: str) -> list[str]:
    """Push ja pull vain omaan haaraan: täsmälliset komennot ilman jokerimerkkejä."""
    return [f"Bash({muoto} {haara})" for muoto in PUSH_MUODOT]


def pr_tyokalut(korjaa_pr: str) -> list[str]:
    """Uusi kortti saa avata PR:n; korjauskierros saa kommentoida vain omaa PR:äänsä tiedostosta."""
    return [f"Bash(gh pr comment {korjaa_pr} --body-file:*)"] if korjaa_pr else ["Bash(gh pr create:*)"]


def sallitut_tyokalut(haara: str, testikomennot: list[str], korjaa_pr: str) -> list[str]:
    komennot = (f"Bash({komento})" for komento in testikomennot)
    return [*PERUSTYOKALUT, *pr_tyokalut(korjaa_pr), *haaran_tyokalut(haara), *komennot]


def _litista(sisalto: Any) -> list[dict[str, Any]]:
    """Kommenttilista sellaisenaan tai sivuittain (gh api --paginate --slurp)."""
    if not isinstance(sisalto, list):
        raise PromptiVirhe("PR:n kommenttien on oltava JSON-lista")
    kommentit: list[Any] = []
    for alkio in sisalto:
        kommentit += alkio if isinstance(alkio, list) else [alkio]
    return [kommentti for kommentti in kommentit if isinstance(kommentti, dict)]


def _on_portin_kommentti(kommentti: dict[str, Any], kommentoija: str) -> bool:
    kayttaja = kommentti.get("user")
    kirjoittaja = kayttaja.get("login") if isinstance(kayttaja, dict) else None
    return kirjoittaja == kommentoija and str(kommentti.get("body", "")).startswith((PORTIN_TUNNISTE, OHJAUKSEN_TUNNISTE))


def portin_kommentit(kommentit_json: str, kommentoija: str) -> str:
    """PR:n kommenteista vain kommentoijan kirjoittamat portin ja ohjauksen kommentit, sanatarkasti.

    Muiden kirjoittajien kommentteja ei liitetä promptiin: kuka tahansa voi kommentoida PR:ää.
    """
    try:
        sisalto = json.loads(kommentit_json)
    except json.JSONDecodeError as virhe:
        raise PromptiVirhe(f"PR:n kommentit eivät ole JSONia: {virhe}") from virhe
    omat = [str(kommentti.get("body", "")).strip() for kommentti in _litista(sisalto)
            if _on_portin_kommentti(kommentti, kommentoija)]
    if not omat:
        return EI_KOMMENTTEJA
    return "\n\n---\n\n".join(teksti[:KOMMENTIN_ENIMMAISPITUUS] for teksti in omat)


def _yksirivinen_json(data: dict[str, Any]) -> str:
    """JSON actionin syötteeseen: yksi rivi ilman heittomerkkiä, koska arvo annetaan heittomerkkien sisällä."""
    teksti = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if "'" in teksti or "\n" in teksti:
        raise PromptiVirhe("JSON ei saa sisältää heittomerkkiä eikä rivinvaihtoa")
    return teksti


def tarkistaja_agentti(malli: str) -> str:
    """Aliagentin määrittely `--agents`-lipulle: tarkistaja lukuoikeuksin tarkistajan mallilla."""
    maarittely = {"description": TARKISTAJAN_KUVAUS, "prompt": TARKISTAJAN_PROMPTI,
                  "tools": TARKISTAJAN_TYOKALUT, "model": malli}
    return _yksirivinen_json({TARKISTAJA: maarittely})


def claude_asetukset(malli: str) -> str:
    """Asetukset, jotka lukitsevat aliagenttien mallin ja ohjaavat aliakset sonnet ja haiku samaan malliin."""
    ymparisto = {
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": malli,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": malli,
        "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",
        "CLAUDE_CODE_SUBAGENT_MODEL": malli,
        "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1",
    }
    return _yksirivinen_json({"env": ymparisto})


def _ehdolliset_lohkot(pohja: str, paalla: set[str]) -> str:
    """Säilyttää lohkot, joiden nimi on päällä, ja poistaa muut. Toistetaan, koska lohkot voivat olla sisäkkäin."""
    def valitse(osuma: re.Match[str]) -> str:
        return osuma.group(2) if osuma.group(1) in paalla else ""

    while True:
        karsittu = re.sub(EHTOLOHKO, valitse, pohja, flags=re.S)
        if karsittu == pohja:
            return karsittu
        pohja = karsittu


def kokoa_prompti(pohja: str, arvot: dict[str, str], lohkot: dict[str, str]) -> str:
    """Täyttää pohjan. `arvot` ovat tarkistettuja lyhyitä arvoja; `lohkot` liitetään sanatarkasti viimeisenä.

    Lohkot (sääntölohko, testikomennot, kommentit) korvataan yhdellä läpikäynnillä, joten niiden sisältöä ei
    tulkita paikkamerkeiksi: sääntölohkossa saa olla esimerkiksi `${{ ... }}`.
    """
    paalla = {"korjaus" if arvot.get("korjaa_pr") else "uusi",
              "tilarivit" if arvot.get("tilarivit") == "true" else "ei_tilariveja"}
    teksti = _ehdolliset_lohkot(pohja, paalla)
    for avain, arvo in arvot.items():
        teksti = teksti.replace("{{" + avain + "}}", arvo)
    jaljella = [osuma.group(0) for osuma in PAIKKAMERKKI.finditer(teksti) if osuma.group(1) not in lohkot]
    if jaljella:
        raise PromptiVirhe(f"promptiin jäi täyttämättömiä paikkamerkkejä: {', '.join(jaljella)}")
    return PAIKKAMERKKI.sub(lambda osuma: lohkot[osuma.group(1)], teksti)


def _jasennin() -> argparse.ArgumentParser:
    jasennin = argparse.ArgumentParser(description="kokoa kortti-ajon prompti, työkalulistat, aliagentti ja asetukset")
    jasennin.add_argument("--pohja", type=Path, required=True)
    jasennin.add_argument("--kortti", required=True)
    jasennin.add_argument("--korjaa-pr", default="")
    jasennin.add_argument("--oletushaara", required=True)
    jasennin.add_argument("--repo", default="")
    jasennin.add_argument("--testikomennot", required=True, help="yksi komento riviä kohden, asennus ensin")
    jasennin.add_argument("--saannot", type=Path, required=True, help="kuluttajan sääntölohko, liitetään sanatarkasti")
    jasennin.add_argument("--malli-label", required=True, help="PR:n label, joka kertoo ajon mallin (malli-<nimi>)")
    jasennin.add_argument("--tarkistajan-malli", required=True, help="tarkistajan ja muiden aliagenttien mallitunniste")
    jasennin.add_argument("--tilarivit", choices=("true", "false"), required=True,
                          help="true = agentti päivittää kortin tilarivin haarassa")
    jasennin.add_argument("--kommentit", type=Path, default=None,
                          help="korjauskierros: PR:n kommentit JSONina (gh api); promptiin liitetään vain portin ja ohjauksen omat")
    jasennin.add_argument("--kommentoija", default=KOMMENTOIJA, help="tunnus, jonka kommentit ovat portin ja ohjauksen")
    jasennin.add_argument("--tulosteet", type=Path, required=True,
                          help="kansio, johon kirjoitetaan prompti.md, tyokalut.txt, kielletyt.txt, agentit.json ja asetukset.json")
    return jasennin


def _tarkista_syotteet(argumentit: argparse.Namespace) -> None:
    if not SLUG.match(argumentit.kortti):
        raise PromptiVirhe(f"kortin slug ei kelpaa: {argumentit.kortti!r}")
    if argumentit.korjaa_pr and not argumentit.korjaa_pr.isdigit():
        raise PromptiVirhe(f"korjaa_pr ei ole numero: {argumentit.korjaa_pr!r}")
    if not MALLI_LABEL.match(argumentit.malli_label):
        raise PromptiVirhe(f"mallin label ei kelpaa: {argumentit.malli_label!r}")
    if not MALLITUNNISTE.match(argumentit.tarkistajan_malli):
        raise PromptiVirhe(f"tarkistajan mallitunniste ei kelpaa: {argumentit.tarkistajan_malli!r}")
    if argumentit.korjaa_pr and argumentit.kommentit is None:
        raise PromptiVirhe("korjauskierros vaatii PR:n kommentit (--kommentit)")


def _sanatarkat_lohkot(argumentit: argparse.Namespace, testikomennot: list[str]) -> dict[str, str]:
    kommentit = ""
    if argumentit.korjaa_pr:
        kommentit = portin_kommentit(argumentit.kommentit.read_text(encoding="utf-8"), argumentit.kommentoija)
    return {
        "testikomennot": "\n".join(f"   - `{komento}`" for komento in testikomennot),
        "saantolohko": argumentit.saannot.read_text(encoding="utf-8").strip(),
        "kommentit": kommentit,
    }


def _kokoa_tulosteet(argumentit: argparse.Namespace) -> dict[str, str]:
    """Tiedostonimi ja sisältö jokaiselle tulosteelle. Mikään ei kirjoitu, jos yksikin syöte on kelvoton."""
    _tarkista_syotteet(argumentit)
    testikomennot = lue_testikomennot(argumentit.testikomennot)
    haara = HAARAN_ETULIITE + argumentit.kortti
    arvot = {"kortti": argumentit.kortti, "haara": haara, "korjaa_pr": argumentit.korjaa_pr,
             "oletushaara": argumentit.oletushaara, "repo": argumentit.repo or "(repo)",
             "malli_label": argumentit.malli_label, "tilarivit": argumentit.tilarivit}
    prompti = kokoa_prompti(argumentit.pohja.read_text(encoding="utf-8"), arvot,
                            _sanatarkat_lohkot(argumentit, testikomennot))
    return {
        "prompti.md": prompti,
        "tyokalut.txt": ",".join(sallitut_tyokalut(haara, testikomennot, argumentit.korjaa_pr)) + "\n",
        "kielletyt.txt": ",".join(KIELLETYT) + "\n",
        "agentit.json": tarkistaja_agentti(argumentit.tarkistajan_malli) + "\n",
        "asetukset.json": claude_asetukset(argumentit.tarkistajan_malli) + "\n",
    }


def main(argv: list[str] | None = None) -> int:
    argumentit = _jasennin().parse_args(argv)
    try:
        tulosteet = _kokoa_tulosteet(argumentit)
    except (PromptiVirhe, OSError) as virhe:
        print(f"kokoa_prompti: {virhe}", file=sys.stderr)
        return 2
    argumentit.tulosteet.mkdir(parents=True, exist_ok=True)
    for nimi, sisalto in tulosteet.items():
        (argumentit.tulosteet / nimi).write_text(sisalto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
