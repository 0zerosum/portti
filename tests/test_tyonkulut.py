"""Työnkulkujen ja mallien rakenne: pinnaus shaan, workflow_call, vähimmät oikeudet, ei PR:n koodia ohjauksessa."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

JUURI = Path(__file__).resolve().parent.parent
TYONKULUT = JUURI / ".github" / "workflows"
MALLIT = JUURI / "mallit"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
PAIKKAMERKKI = "<PINNATTU_SHA>"


def lue(polku: Path) -> dict[str, Any]:
    data = yaml.safe_load(polku.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    data["on"] = data.get("on", data.get(True))
    return data


def uses_viitteet(data: dict[str, Any]) -> list[str]:
    viitteet = []
    for job in data["jobs"].values():
        if "uses" in job:
            viitteet.append(str(job["uses"]))
        for askel in job.get("steps", []):
            if "uses" in askel:
                viitteet.append(str(askel["uses"]))
    return viitteet


@pytest.mark.parametrize("polku", sorted(TYONKULUT.glob("*.yml")) + sorted(MALLIT.glob("*.yml")))
def test_actionit_ja_tyonkulut_on_pinnattu_shaan(polku: Path) -> None:
    for viite in uses_viitteet(lue(polku)):
        if viite.startswith("./"):
            continue
        _, ref = viite.split("@", 1)
        assert SHA40.match(ref) or ref == PAIKKAMERKKI, f"{polku.name}: {viite} ei ole pinnattu shaan"


def test_ohjaus_on_workflow_call_eika_hae_prn_koodia() -> None:
    data = lue(TYONKULUT / "ohjaus.yml")
    assert set(data["on"]["workflow_call"]["inputs"]) >= {"testit_tyonkulku", "portti_tyonkulku", "kortti_ajo_tyonkulku"}
    job = data["jobs"]["ohjaus"]
    assert job["permissions"] == {"contents": "read", "pull-requests": "write", "issues": "write", "actions": "write"}
    assert job["concurrency"]["cancel-in-progress"] is False
    checkoutit = [askel for askel in job["steps"] if str(askel.get("uses", "")).startswith("actions/checkout@")]
    assert len(checkoutit) == 1
    assert checkoutit[0]["with"]["repository"] == "${{ job.workflow_repository }}"
    assert checkoutit[0]["with"]["ref"] == "${{ job.workflow_sha }}"
    teksti = (TYONKULUT / "ohjaus.yml").read_text(encoding="utf-8")
    assert "head_sha" not in "".join(str(askel.get("with", "")) for askel in checkoutit)
    for lohko in re.findall(r"run: \|\n((?:          .*\n)+)", teksti):
        assert "${{" not in lohko, "run-lohkot käyttävät ympäristömuuttujia, eivät lausekkeita"


def test_kortti_ajo_on_workflow_call_budjetilla_ja_vahdilla() -> None:
    data = lue(TYONKULUT / "kortti-ajo.yml")
    syotteet = data["on"]["workflow_call"]["inputs"]
    assert syotteet["kortti"]["required"] is True and syotteet["max_turns"]["required"] is True
    assert syotteet["malli"]["default"] == "claude-opus-5-5" and syotteet["testikomennot"]["required"] is True
    assert data["on"]["workflow_call"]["secrets"]["ANTHROPIC_API_KEY"]["required"] is True
    job = data["jobs"]["kortti-ajo"]
    assert job["permissions"] == {"contents": "write", "pull-requests": "write", "issues": "write",
                                  "id-token": "write", "actions": "read"}
    assert job["concurrency"]["group"] == "kortti-ajo-${{ github.repository }}"
    assert job["timeout-minutes"] == "${{ inputs.aikakatkaisu_min }}"
    nimet = [askel.get("name", "") for askel in job["steps"]]
    assert nimet[0].startswith("Tarkista syötteet ja budjetti") and nimet[-1].startswith("Main-vahti")
    assert job["steps"][-1]["if"] == "always()"
    agentti = next(askel for askel in job["steps"] if str(askel.get("uses", "")).startswith("anthropics/claude-code-action@"))
    assert "--max-budget-usd ${{ vars.PORTTI_AJO_BUDJETTI_USD }}" in agentti["with"]["claude_args"]
    assert "--max-turns ${{ inputs.max_turns }}" in agentti["with"]["claude_args"]
    assert "github_token" not in agentti["with"], "pushit Claude GitHub Appin tokenilla, ei GITHUB_TOKENilla"
    teksti = (TYONKULUT / "kortti-ajo.yml").read_text(encoding="utf-8")
    assert "# v1.0.268" in teksti and "PORTTI_AJO_BUDJETTI_USD puuttuu" in teksti


def test_mallit_kutsuvat_pinnattua_shaa() -> None:
    ohjaus = lue(MALLIT / "portti-ohjaus.yml")
    assert ohjaus["on"]["workflow_run"] == {"workflows": ["Testit", "Portti"], "types": ["completed"]}
    assert ohjaus["jobs"]["ohjaus"]["uses"] == f"0zerosum/portti/.github/workflows/ohjaus.yml@{PAIKKAMERKKI}"
    assert ohjaus["permissions"] == lue(TYONKULUT / "ohjaus.yml")["jobs"]["ohjaus"]["permissions"]
    kortti = lue(MALLIT / "kortti-ajo.yml")
    assert set(kortti["on"]["workflow_dispatch"]["inputs"]) == {"kortti", "korjaa_pr", "max_turns"}
    assert kortti["jobs"]["kortti-ajo"]["secrets"] == {"ANTHROPIC_API_KEY": "${{ secrets.ANTHROPIC_API_KEY }}"}
    assert kortti["permissions"] == lue(TYONKULUT / "kortti-ajo.yml")["jobs"]["kortti-ajo"]["permissions"]
    portti = lue(MALLIT / "portti.yml")
    assert portti["name"] == "Portti" and portti["jobs"]["portti"]["steps"][0]["with"]["policy_lahde"] == "base"
