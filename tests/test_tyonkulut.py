"""Työnkulkujen ja mallien rakenne: pinnaus shaan, workflow_call, vähimmät oikeudet, portti ennen kielimallia."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from portti.kortti import kortin_tila
from portti.malli import LAHDE_KORTTI, valitse_malli

JUURI = Path(__file__).resolve().parent.parent
TYONKULUT = JUURI / ".github" / "workflows"
MALLIT = JUURI / "mallit"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
PAIKKAMERKKI = "<PINNATTU_SHA>"
RUN_LOHKO = re.compile(r"run: \|\n((?:          .*\n)+)")


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


def askel(job: dict[str, Any], nimen_alku: str) -> dict[str, Any]:
    osumat = [askel for askel in job["steps"] if str(askel.get("name", "")).startswith(nimen_alku)]
    assert len(osumat) == 1, f"askel {nimen_alku!r}: {len(osumat)} osumaa"
    return dict(osumat[0])


def jarjestys(job: dict[str, Any], *nimien_alut: str) -> list[int]:
    nimet = [str(askel.get("name", "")) for askel in job["steps"]]
    return [nimet.index(askel(job, alku)["name"]) for alku in nimien_alut]


@pytest.mark.parametrize("polku", sorted(TYONKULUT.glob("*.yml")) + sorted(MALLIT.glob("*.yml")))
def test_actionit_ja_tyonkulut_on_pinnattu_shaan(polku: Path) -> None:
    for viite in uses_viitteet(lue(polku)):
        if viite.startswith("./"):
            continue
        _, ref = viite.split("@", 1)
        assert SHA40.match(ref) or ref == PAIKKAMERKKI, f"{polku.name}: {viite} ei ole pinnattu shaan"


@pytest.mark.parametrize("nimi", ["ohjaus.yml", "kortti-ajo.yml"])
def test_run_lohkot_kayttavat_ymparistomuuttujia_eivat_lausekkeita(nimi: str) -> None:
    teksti = (TYONKULUT / nimi).read_text(encoding="utf-8")
    lohkot = RUN_LOHKO.findall(teksti)
    assert lohkot, "run-lohkoja ei löytynyt: sisennys on muuttunut"
    for lohko in lohkot:
        assert "${{" not in lohko, f"{nimi}: lauseke run-lohkossa"


def test_ohjaus_on_workflow_call_eika_hae_prn_koodia() -> None:
    data = lue(TYONKULUT / "ohjaus.yml")
    assert set(data["on"]["workflow_call"]["inputs"]) >= {"testit_tyonkulku", "portti_tyonkulku", "kortti_ajo_tyonkulku"}
    job = data["jobs"]["ohjaus"]
    assert job["permissions"] == {"contents": "read", "pull-requests": "write", "issues": "write", "actions": "write"}
    assert job["concurrency"]["cancel-in-progress"] is False
    assert "GH_TOKEN" not in job["env"], "token annetaan vain sitä tarvitseville askelille"
    checkoutit = [askel for askel in job["steps"] if str(askel.get("uses", "")).startswith("actions/checkout@")]
    assert len(checkoutit) == 1
    assert checkoutit[0]["with"]["repository"] == "${{ job.workflow_repository }}"
    assert checkoutit[0]["with"]["ref"] == "${{ job.workflow_sha }}"
    assert checkoutit[0]["with"]["persist-credentials"] is False


def test_ohjaus_hakee_prn_head_haarasta_ja_antaa_edellisen_paatoksen_moottorille() -> None:
    job = lue(TYONKULUT / "ohjaus.yml")["jobs"]["ohjaus"]
    assert job["env"]["HEAD_OMISTAJA"] == "${{ github.event.workflow_run.head_repository.owner.login }}"
    assert job["env"]["HEAD_HAARA"] == "${{ github.event.workflow_run.head_branch }}"
    haku = askel(job, "Ratkaise PR")["run"]
    assert '-f head="$HEAD_OMISTAJA:$HEAD_HAARA"' in haku and "select(.head.sha == $sha)" in haku
    assert "repos/$REPO/commits/" not in haku, "commits/<sha>/pulls ei palauta forkin PR:ää"
    edellinen, paata, toteuta = jarjestys(job, "Lue edellinen ohjauspäätös", "Päätä ohjaus", "Toteuta päätös")
    assert edellinen < paata < toteuta
    assert "ohjaus-edellinen" in job["steps"][edellinen]["run"] and "--tuloste portti-edellinen.json" in job["steps"][edellinen]["run"]
    paatos = job["steps"][paata]["run"]
    assert "--edellinen portti-edellinen.json" in paatos and '--haara "$HAARA"' in paatos
    assert "--kortti " not in job["steps"][toteuta]["run"], "kortin slug ja malli tulevat päätöksestä"


def test_kortti_ajo_on_workflow_call_budjetilla_ja_vahdilla() -> None:
    data = lue(TYONKULUT / "kortti-ajo.yml")
    syotteet = data["on"]["workflow_call"]["inputs"]
    assert set(syotteet) == {"kortti", "korjaa_pr", "malli_kasin", "alkuperainen_malli", "max_turns", "testikomennot",
                             "kortin_tilarivit", "saantolohko_polku", "aikakatkaisu_min", "python_versio"}
    assert syotteet["kortti"]["required"] is True and syotteet["max_turns"]["required"] is True
    assert syotteet["malli_kasin"]["default"] == "" and syotteet["alkuperainen_malli"]["default"] == ""
    assert syotteet["kortin_tilarivit"] == {**syotteet["kortin_tilarivit"], "type": "boolean", "default": True}
    assert data["on"]["workflow_call"]["secrets"]["ANTHROPIC_API_KEY"]["required"] is True
    job = data["jobs"]["kortti-ajo"]
    assert job["permissions"] == {"contents": "write", "pull-requests": "write", "issues": "write",
                                  "id-token": "write", "actions": "read"}
    assert job["concurrency"]["group"] == "kortti-ajo-${{ github.repository }}"
    assert job["timeout-minutes"] == "${{ inputs.aikakatkaisu_min }}"
    assert job["env"]["HAARA"] == "feature/${{ inputs.kortti }}"
    nimet = [askel.get("name", "") for askel in job["steps"]]
    assert nimet[0].startswith("Tarkista syötteet ja budjetti") and nimet[-1].startswith("Main-vahti")
    assert job["steps"][-1]["if"] == "always()"
    teksti = (TYONKULUT / "kortti-ajo.yml").read_text(encoding="utf-8")
    assert "# v1.0.268" in teksti and "PORTTI_AJO_BUDJETTI_USD puuttuu" in teksti


def test_kortti_ajon_portti_on_ennen_kielimallia_ja_malli_tulee_vain_siita() -> None:
    job = lue(TYONKULUT / "kortti-ajo.yml")["jobs"]["kortti-ajo"]
    portti, labelit, prompti, agentti, tarkistus, yhteenveto = jarjestys(
        job, "Portti ennen kielimallia", "Varmista labelit", "Kokoa prompti", "Aja agentti", "Tarkista agentin lopputulos",
        "Ajon yhteenveto")
    assert portti < labelit < prompti < agentti < tarkistus < yhteenveto
    askeleet = job["steps"]
    tarkistukset = askeleet[portti]["run"]
    for vaatimus in ('kortin-tila --kortti "$kortti_polku" --vaadi hyväksytty', "matching-refs/heads/$HAARA",
                     "portti.cli malli --kortti", '"$TAPAHTUMA" = "workflow_dispatch"', 'gh api "users/$tunnus"',
                     "korjauskierros vaatii alkuperäisen ajon mallin", "on jo olemassa"):
        assert vaatimus in tarkistukset, vaatimus
    assert askeleet[portti]["env"]["MALLI_KASIN"] == "${{ inputs.malli_kasin }}"
    teksti = (TYONKULUT / "kortti-ajo.yml").read_text(encoding="utf-8")
    assert teksti.count("inputs.malli_kasin") == 1, "käsin valittu malli kulkee vain portin kautta"
    assert "--model ${{ inputs." not in teksti and "inputs.malli }}" not in teksti
    argumentit = askeleet[agentti]["with"]["claude_args"]
    for lippu in ("--model ${{ steps.portti.outputs.malli }}", "--max-budget-usd ${{ vars.PORTTI_AJO_BUDJETTI_USD }}",
                  "--max-turns ${{ inputs.max_turns }}", "--setting-sources user",
                  "--agents '${{ steps.prompti.outputs.agentit }}'", '--allowedTools "${{ steps.prompti.outputs.tyokalut }}"'):
        assert lippu in argumentit, lippu
    assert askeleet[agentti]["with"]["settings"] == "${{ steps.prompti.outputs.asetukset }}"
    for muuttuja in ("ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1",
                     "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1"):
        assert muuttuja in tarkistukset, muuttuja


def test_kortti_ajon_agentti_on_rajattu_ja_sen_ajo_varmistetaan() -> None:
    job = lue(TYONKULUT / "kortti-ajo.yml")["jobs"]["kortti-ajo"]
    assert job["env"]["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] == "1", "aliprosessit eivät saa API-avainta"
    assert "GH_TOKEN" not in job["env"]
    assert askel(job, "Hae kuluttajarepo")["with"]["persist-credentials"] is False, "GITHUB_TOKEN ei jää gitin asetuksiin"
    agentti = askel(job, "Aja agentti")
    assert str(agentti["uses"]).startswith("anthropics/claude-code-action@")
    assert "github_token" not in agentti["with"], "pushit Claude GitHub Appin tokenilla, ei GITHUB_TOKENilla"
    kokoa = askel(job, "Kokoa prompti")["run"].rstrip()
    assert kokoa.endswith("rm -rf portti-moottori"), "portin kopio pois ennen agenttia"
    assert kokoa.index("cp portti-moottori/ajo/ajon_yhteenveto.py") < kokoa.index("rm -rf portti-moottori")
    tarkistus = askel(job, "Tarkista agentin lopputulos")
    assert tarkistus["env"]["LOPPUTULOS"] == "${{ steps.agentti.outputs.conclusion }}"
    assert '"$LOPPUTULOS" != "success"' in tarkistus["run"] and '--add-label "agentti,$MALLI_LABEL"' in tarkistus["run"]
    yhteenveto = askel(job, "Ajon yhteenveto")
    assert yhteenveto["if"] == "always() && steps.prompti.outcome == 'success'"
    assert "ajon_yhteenveto.py" in yhteenveto["run"] and '--sallitut "$SALLITUT"' in yhteenveto["run"]
    assert yhteenveto["run"].rstrip().endswith('exit "$tulos"'), "luvaton malli kaataa ajon näkyvästi"


def test_mallit_kutsuvat_pinnattua_shaa() -> None:
    ohjaus = lue(MALLIT / "portti-ohjaus.yml")
    assert ohjaus["on"]["workflow_run"] == {"workflows": ["Testit", "Portti"], "types": ["completed"]}
    assert ohjaus["jobs"]["ohjaus"]["uses"] == f"0zerosum/portti/.github/workflows/ohjaus.yml@{PAIKKAMERKKI}"
    assert ohjaus["permissions"] == lue(TYONKULUT / "ohjaus.yml")["jobs"]["ohjaus"]["permissions"]
    assert "concurrency" not in ohjaus, "sama ryhmä kutsujassa ja kutsutussa jobissa lukkiutuu"
    kortti = lue(MALLIT / "kortti-ajo.yml")
    syotteet = kortti["on"]["workflow_dispatch"]["inputs"]
    assert set(syotteet) == {"kortti", "korjaa_pr", "malli_kasin", "alkuperainen_malli", "max_turns"}
    assert syotteet["malli_kasin"]["options"] == ["kortin mukaan", "opus", "fable"]
    assert "schedule" not in kortti["on"], "ajoa ei ajasteta"
    kutsu = kortti["jobs"]["kortti-ajo"]
    assert kutsu["secrets"] == {"ANTHROPIC_API_KEY": "${{ secrets.ANTHROPIC_API_KEY }}"}
    assert "malli" not in kutsu["with"] and kutsu["with"]["kortin_tilarivit"] is True
    assert set(kutsu["with"]) <= set(lue(TYONKULUT / "kortti-ajo.yml")["on"]["workflow_call"]["inputs"])
    assert kortti["permissions"] == lue(TYONKULUT / "kortti-ajo.yml")["jobs"]["kortti-ajo"]["permissions"]
    assert "concurrency" not in kortti
    portti = lue(MALLIT / "portti.yml")
    assert portti["name"] == "Portti" and portti["jobs"]["portti"]["steps"][0]["with"]["policy_lahde"] == "base"


def test_kortin_pohjan_rivit_kelpaavat_moottorille() -> None:
    pohja = (MALLIT / "kortin-pohja.md").read_text(encoding="utf-8")
    assert "- Malli: opus (oletus; fable vain hyväksytyllä päätöksellä)" in pohja
    koodilohko = pohja.split("```markdown\n", 1)[1].split("```", 1)[0]
    assert kortin_tila(koodilohko) == "luonnos"
    valinta = valitse_malli(koodilohko)
    assert (valinta.nimi, valinta.lahde) == ("opus", LAHDE_KORTTI)
