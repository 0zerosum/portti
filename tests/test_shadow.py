"""Shadow-raportti vale-gh:n antamilla PR:illä ja kommenteilla."""

import json

from portti.kommentti import KONEDATA_ALKU, KONEDATA_LOPPU, TUNNISTE
from portti.shadow import (
    EI_KOMMENTTIA,
    MERGETTY_MUUTOSTEN_JALKEEN,
    MERGETTY_MUUTTAMATTA,
    SULJETTU,
    kokoa_shadow_raportti,
    muotoile_shadow_raportti,
)
from tests.apu_gh import ValeGh


def portin_kommentti(verdict: str, head_sha: str) -> dict[str, object]:
    konedata = {"verdict": verdict, "tier": "T1a", "head_sha": head_sha, "moottorin_versio": "0.1.0"}
    teksti = TUNNISTE + "\n" + KONEDATA_ALKU + json.dumps(konedata) + KONEDATA_LOPPU + "\nrunko\n"
    return {"id": 1, "body": teksti}


def test_raportti_luokittelee_lopputulokset_ja_laskee_mittarit() -> None:
    prt = [
        {"number": 3, "mergedAt": "2026-10-20T10:00:00Z", "headRefOid": "aaa"},
        {"number": 1, "mergedAt": "2026-10-21T10:00:00Z", "headRefOid": "bbb-uusi"},
        {"number": 2, "mergedAt": None, "headRefOid": "ccc"},
        {"number": 4, "mergedAt": None, "headRefOid": "ddd"},
    ]
    vale = ValeGh(
        {
            "pr list": prt,
            "issues/3/comments": [[portin_kommentti("KOVA", "aaa")]],
            "issues/1/comments": [[portin_kommentti("PEHMEÄ", "bbb-vanha")]],
            "issues/2/comments": [[{"id": 9, "body": "ihmisen kommentti"}, portin_kommentti("VAPAA", "ccc")]],
            "issues/4/comments": [],
        }
    )
    raportti = kokoa_shadow_raportti(vale.api(), "omistaja/repo", "2026-10-01")
    assert [rivi.pr_numero for rivi in raportti.rivit] == [1, 2, 3, 4]
    lopputulokset = {rivi.pr_numero: rivi.lopputulos for rivi in raportti.rivit}
    assert lopputulokset == {
        1: MERGETTY_MUUTOSTEN_JALKEEN,
        2: SULJETTU,
        3: MERGETTY_MUUTTAMATTA,
        4: EI_KOMMENTTIA,
    }
    assert raportti.kova_tai_pehmea_mutta_mergetty_muuttamatta == 1
    assert raportti.vapaa_mutta_hylatty == 1
    teksti = muotoile_shadow_raportti(raportti)
    assert "| #3 | KOVA | T1a | mergetty muuttamatta |" in teksti
    assert "KOVA/PEHMEÄ mutta mergetty muuttamatta: 1" in teksti
    assert "VAPAA mutta hylätty: 1" in teksti
    assert all(argumentit[0] in ("pr", "api") for argumentit, _ in vale.kutsut)
    assert not any("-X" in argumentit for argumentit, _ in vale.kutsut)


def test_haku_kayttaa_alkaen_paivaa() -> None:
    vale = ValeGh({"pr list": []})
    kokoa_shadow_raportti(vale.api(), "omistaja/repo", "2026-09-30")
    [(argumentit, _)] = vale.kutsut
    assert "closed:>=2026-09-30" in argumentit and "--state" in argumentit
