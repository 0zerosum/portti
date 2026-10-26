"""Yksi PR-kommentti per PR: tunnistemerkki, päivitetään paikallaan, ei kerry."""

from __future__ import annotations

import json
from typing import Any

from portti.github_api import GitHubApi

TUNNISTE = "<!-- portti-kommentti v1 -->"
KONEDATA_ALKU = "<!-- portti "
KONEDATA_LOPPU = " -->"


def konedata(evidence: dict[str, Any]) -> dict[str, Any]:
    """Shadow-raportin lukema tiivistelmä."""
    return {
        "verdict": evidence["verdict"],
        "tier": evidence["luokitus"]["tier"],
        "head_sha": evidence["head_sha"],
        "moottorin_versio": evidence["moottorin_versio"],
    }


def lue_konedata(kommentin_teksti: str) -> dict[str, Any] | None:
    """Palauttaa kommenttiin upotetun konedatan tai None, jos kommentti ei ole portin."""
    if not kommentin_teksti.startswith(TUNNISTE):
        return None
    for rivi in kommentin_teksti.splitlines():
        if rivi.startswith(KONEDATA_ALKU) and rivi.endswith(KONEDATA_LOPPU):
            sisalto = rivi[len(KONEDATA_ALKU):-len(KONEDATA_LOPPU)]
            tulos = json.loads(sisalto)
            return tulos if isinstance(tulos, dict) else None
    return None


def _deny_rivit(luokitus: dict[str, Any]) -> list[str]:
    osumat = luokitus["deny_osumat"]
    if not osumat:
        return ["- ei osumia"]
    return [f"- {osuma['taso']} · {osuma['kategoria']}: `{osuma['polku']}`" for osuma in osumat]


def _portti_rivit(portit: list[dict[str, Any]]) -> list[str]:
    return [f"- {'✓' if portti['ok'] else '✗'} {portti['nimi']}: {portti['syy']}" for portti in portit]


def renderoi(evidence: dict[str, Any], artefakti_url: str | None) -> str:
    luokitus = evidence["luokitus"]
    koskettu = ", ".join(luokitus["alueet"]) or "–"
    portaat = ", ".join(evidence["hyvaksyttavissa_portaalla"]) or "–"
    evidence_linkki = f"[evidence-artefakti]({artefakti_url})" if artefakti_url else "evidence-artefakti puuttuu"
    rivit = [
        TUNNISTE,
        KONEDATA_ALKU + json.dumps(konedata(evidence), sort_keys=True) + KONEDATA_LOPPU,
        f"## Portti: **{evidence['verdict']}** ({evidence['tila']})",
        "",
        "| | |",
        "|---|---|",
        f"| Tier | {luokitus['tier']} |",
        f"| Rivit / tiedostot / alueet | {luokitus['rivit']} / {luokitus['tiedostoja']} / {len(luokitus['alueet'])} |",
        f"| Koskettu | {koskettu} |",
        f"| Hyväksyttävissä portaalla | {portaat} |",
        "",
        "**Deny-osumat**",
        *_deny_rivit(luokitus),
        "",
        "**Portit**",
        *_portti_rivit(evidence["portit"]),
        "",
        f"{evidence_linkki} · moottori {evidence['moottorin_versio']} · head `{evidence['head_sha'][:12]}`",
    ]
    return "\n".join(rivit) + "\n"


def kirjoita_tai_paivita(api: GitHubApi, repo: str, pr_numero: int, teksti: str) -> str:
    """Luo portin kommentin tai päivittää olemassa olevan. Palauttaa tehdyn toimen."""
    omat = [kommentti for kommentti in api.hae_kommentit(repo, pr_numero)
            if str(kommentti.get("body", "")).startswith(TUNNISTE)]
    if not omat:
        api.luo_kommentti(repo, pr_numero, teksti)
        return "luotu"
    ensimmainen = omat[0]
    if ensimmainen.get("body") == teksti:
        return "ennallaan"
    api.paivita_kommentti(repo, int(ensimmainen["id"]), teksti)
    return "päivitetty"
