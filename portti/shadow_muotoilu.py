"""Shadow-raportin tuloste: markdown-taulukot per ryhmä tai JSON."""

from __future__ import annotations

import json
from typing import Any

from portti.shadow import ShadowRaportti, ShadowRyhma


def _laskuritaulukko(otsikko: str, arvot: dict[str, int]) -> list[str]:
    rivit = [f"**{otsikko}**", "", "| | PR:iä |", "|---|---|"]
    rivit += [f"| {avain} | {maara} |" for avain, maara in arvot.items()] or ["| – | 0 |"]
    rivit.append("")
    return rivit


def _ryhma_markdown(ryhma: ShadowRyhma) -> list[str]:
    rivit = [f"### Base {ryhma.nimi} ({len(ryhma.rivit)} PR:ää)", ""]
    rivit += ["| Repo | PR | Verdict | Tier | Lopputulos |", "|---|---|---|---|---|"]
    rivit += [f"| {rivi.repo} | #{rivi.pr_numero} | {rivi.verdict or '–'} | {rivi.tier or '–'} | {rivi.lopputulos} |"
              for rivi in ryhma.rivit]
    rivit += [
        "",
        f"- KOVA/PEHMEÄ mutta mergetty muuttamatta: {ryhma.kova_tai_pehmea_mutta_mergetty_muuttamatta}",
        f"- VAPAA mutta hylätty: {ryhma.vapaa_mutta_hylatty}",
        "",
    ]
    rivit += _laskuritaulukko("Väärät KOVA/PEHMEÄ-osumat deny-kategorioittain", ryhma.vaarat_osumat_kategorioittain())
    rivit += _laskuritaulukko("Jakauma tiereittäin", ryhma.jakauma_tiereittain())
    rivit += _laskuritaulukko("Hyväksyttävissä portaalla", ryhma.jakauma_portaittain())
    return rivit


def muotoile_shadow_raportti(raportti: ShadowRaportti) -> str:
    rivit = [
        f"## Shadow-raportti: {', '.join(raportti.repot)} alkaen {raportti.alkaen}",
        "",
        f"Suljettuja PR:iä {sum(len(ryhma.rivit) for ryhma in raportti.ryhmat.values())}, "
        f"draftit pudotettu: {raportti.pudotetut_draftit}.",
        "",
    ]
    for ryhma in raportti.ryhmat.values():
        rivit += _ryhma_markdown(ryhma)
    return "\n".join(rivit).rstrip() + "\n"


def shadow_raportti_jsoniksi(raportti: ShadowRaportti) -> str:
    def ryhma(ryhma: ShadowRyhma) -> dict[str, Any]:
        return {
            "prt": [rivi.__dict__ | {"kategoriat": list(rivi.kategoriat), "portaat": list(rivi.portaat)} for rivi in ryhma.rivit],
            "kova_tai_pehmea_mutta_mergetty_muuttamatta": ryhma.kova_tai_pehmea_mutta_mergetty_muuttamatta,
            "vapaa_mutta_hylatty": ryhma.vapaa_mutta_hylatty,
            "vaarat_osumat_kategorioittain": ryhma.vaarat_osumat_kategorioittain(),
            "jakauma_tiereittain": ryhma.jakauma_tiereittain(),
            "jakauma_portaittain": ryhma.jakauma_portaittain(),
        }
    data = {
        "repot": raportti.repot,
        "alkaen": raportti.alkaen,
        "pudotetut_draftit": raportti.pudotetut_draftit,
        "ryhmat": {nimi: ryhma(sisalto) for nimi, sisalto in raportti.ryhmat.items()},
    }
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
