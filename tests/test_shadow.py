"""Shadow-raportti vale-gh:lla: kaksi repoa, kaksi base-haaraa, draftit pois, kategoriat ja jakaumat."""

import json

from portti.kommentti import KONEDATA_ALKU, KONEDATA_LOPPU, tunniste
from portti.shadow import (
    EI_KOMMENTTIA,
    MERGETTY_MUUTOSTEN_JALKEEN,
    MERGETTY_MUUTTAMATTA,
    SULJETTU,
    kokoa_shadow_raportti,
    ryhma_haaralle,
)
from portti.shadow_muotoilu import muotoile_shadow_raportti, shadow_raportti_jsoniksi
from tests.apu_gh import ValeGh


def portin_kommentti(verdict: str, head_sha: str, tier: str = "T1a", kategoriat: list[str] | None = None,
                     portaat: list[str] | None = None) -> dict[str, object]:
    konedata = {"verdict": verdict, "tier": tier, "head_sha": head_sha, "moottorin_versio": "0.3.0",
                "deny_kategoriat": kategoriat or [], "portaat": portaat or []}
    teksti = tunniste("shadow") + "\n" + KONEDATA_ALKU + json.dumps(konedata) + KONEDATA_LOPPU + "\nrunko\n"
    return {"id": 1, "body": teksti}


def pr(numero: int, base: str, merged: bool, head: str, draft: bool = False) -> dict[str, object]:
    return {"number": numero, "baseRefName": base, "mergedAt": "2026-10-20T10:00:00Z" if merged else None,
            "headRefOid": head, "isDraft": draft}


def test_ryhma_haaralle() -> None:
    assert ryhma_haaralle("main") == "main" and ryhma_haaralle("master") == "main"
    assert ryhma_haaralle("feat/x") == "feat/*" and ryhma_haaralle("feature/y") == "feat/*"
    assert ryhma_haaralle("julkaisu/se") == "julkaisu/se"


def vale_kahdella_repolla() -> ValeGh:
    return ValeGh({
        "pr list --repo omistaja/eka": [
            pr(1, "main", True, "aaa"), pr(2, "main", False, "bbb"), pr(3, "feat/x", True, "ccc"),
            pr(4, "main", True, "ddd", draft=True),
        ],
        "pr list --repo omistaja/toka": [pr(7, "feature/y", True, "eee-uusi"), pr(8, "julkaisu/se", True, "fff")],
        "repos/omistaja/eka/issues/1/comments": [[portin_kommentti("KOVA", "aaa", "T1b", ["kova:ci", "kova:portti_itse"])]],
        "repos/omistaja/eka/issues/2/comments": [[{"id": 9, "body": "ihminen"}, portin_kommentti("VAPAA", "bbb", "T0", [], ["S0", "S1", "S2", "S3"])]],
        "repos/omistaja/eka/issues/3/comments": [[portin_kommentti("PEHMEÄ", "ccc", "T1a", ["pehmea:runko"])]],
        "repos/omistaja/toka/issues/7/comments": [[portin_kommentti("KOVA", "eee-vanha", "YLI", ["kova:ci"])]],
        "repos/omistaja/toka/issues/8/comments": [],
    })


def test_ryhmittely_mittarit_ja_kategoriat() -> None:
    vale = vale_kahdella_repolla()
    raportti = kokoa_shadow_raportti(vale.api(), ["omistaja/eka", "omistaja/toka"], "2026-10-01")
    assert list(raportti.ryhmat) == ["main", "feat/*", "julkaisu/se"]
    assert raportti.pudotetut_draftit == 1
    main_ryhma = raportti.ryhmat["main"]
    assert [rivi.lopputulos for rivi in main_ryhma.rivit] == [MERGETTY_MUUTTAMATTA, SULJETTU]
    assert main_ryhma.kova_tai_pehmea_mutta_mergetty_muuttamatta == 1
    assert main_ryhma.vapaa_mutta_hylatty == 1
    assert main_ryhma.vaarat_osumat_kategorioittain() == {"kova:ci": 1, "kova:portti_itse": 1}
    assert main_ryhma.jakauma_tiereittain() == {"T0": 1, "T1b": 1}
    portaat = main_ryhma.jakauma_portaittain()
    assert portaat["S0"] == 1 and portaat["S3"] == 1 and portaat["ei millään"] == 1
    feat = raportti.ryhmat["feat/*"]
    assert {rivi.repo for rivi in feat.rivit} == {"omistaja/eka", "omistaja/toka"}
    assert [rivi.lopputulos for rivi in feat.rivit] == [MERGETTY_MUUTTAMATTA, MERGETTY_MUUTOSTEN_JALKEEN]
    assert feat.vaarat_osumat_kategorioittain() == {"pehmea:runko": 1}
    assert raportti.ryhmat["julkaisu/se"].rivit[0].lopputulos == EI_KOMMENTTIA
    assert not any("-X" in argumentit for argumentit, _ in vale.kutsut)
    assert not any("issues/4/" in " ".join(argumentit) for argumentit, _ in vale.kutsut)


def test_markdown_ja_json() -> None:
    raportti = kokoa_shadow_raportti(vale_kahdella_repolla().api(), ["omistaja/eka", "omistaja/toka"], "2026-10-01")
    teksti = muotoile_shadow_raportti(raportti)
    assert "### Base main (2 PR:ää)" in teksti and "### Base feat/* (2 PR:ää)" in teksti
    assert "| omistaja/eka | #1 | KOVA | T1b | mergetty muuttamatta |" in teksti
    assert "- KOVA/PEHMEÄ mutta mergetty muuttamatta: 1" in teksti
    assert "| kova:portti_itse | 1 |" in teksti and "draftit pudotettu: 1" in teksti
    data = json.loads(shadow_raportti_jsoniksi(raportti))
    assert data["ryhmat"]["main"]["vapaa_mutta_hylatty"] == 1
    assert data["ryhmat"]["feat/*"]["prt"][0]["kategoriat"] == ["pehmea:runko"]
    assert data["pudotetut_draftit"] == 1


def test_vanha_konedata_ilman_kategorioita() -> None:
    vanha = {"id": 1, "body": tunniste("shadow") + "\n" + KONEDATA_ALKU
             + json.dumps({"verdict": "KOVA", "tier": "T1a", "head_sha": "aaa", "moottorin_versio": "0.2.0"})
             + KONEDATA_LOPPU + "\n"}
    vale = ValeGh({"pr list": [pr(1, "main", True, "aaa")], "issues/1/comments": [[vanha]]})
    raportti = kokoa_shadow_raportti(vale.api(), ["omistaja/eka"], "2026-10-01")
    assert raportti.ryhmat["main"].vaarat_osumat_kategorioittain() == {"ei tiedossa": 1}


def test_haku_kayttaa_alkaen_paivaa() -> None:
    vale = ValeGh({"pr list": []})
    kokoa_shadow_raportti(vale.api(), ["omistaja/repo"], "2026-09-30")
    [(argumentit, _)] = vale.kutsut
    assert "closed:>=2026-09-30" in argumentit and "baseRefName,isDraft" in argumentit[-1]
