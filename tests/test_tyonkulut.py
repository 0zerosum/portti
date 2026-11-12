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


@pytest.mark.parametrize("nimi", ["ohjaus.yml", "kortti-ajo.yml", "kortti-ajo-jalkitarkistus.yml"])
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


def test_ohjaus_vie_vajaan_tiedostolistan_ctolle_ja_purkaa_evidencen_tyotilan_ulkopuolelle() -> None:
    job = lue(TYONKULUT / "ohjaus.yml")["jobs"]["ohjaus"]
    tiedot = askel(job, "Hae PR:n head")["run"]
    assert "changedFiles" in tiedot and "polut_vajaat=$polut_vajaat" in tiedot
    paatos = askel(job, "Päätä ohjaus")
    assert paatos["env"]["POLUT_VAJAAT"] == "${{ steps.pr.outputs.polut_vajaat }}"
    assert "liput+=(--polut-vajaat)" in paatos["run"]
    evidence = askel(job, "Hae evidence")["run"]
    assert 'mktemp -d "$RUNNER_TEMP/' in evidence and '--dir "$purku"' in evidence, "artefaktia ei pureta työtilaan"
    assert '[ ! -L "$tiedosto" ]' in evidence and 'cp "$tiedosto" evidence/portti-evidence.json' in evidence


def test_kortti_ajo_on_workflow_call_budjetilla_ja_kahdella_jobilla() -> None:
    data = lue(TYONKULUT / "kortti-ajo.yml")
    syotteet = data["on"]["workflow_call"]["inputs"]
    assert set(syotteet) == {"kortti", "korjaa_pr", "malli_kasin", "alkuperainen_malli", "max_turns", "testikomennot",
                             "kortin_tilarivit", "saantolohko_polku", "aikakatkaisu_min", "python_versio"}
    assert syotteet["kortti"]["required"] is True and syotteet["max_turns"]["required"] is True
    assert syotteet["malli_kasin"]["default"] == "" and syotteet["alkuperainen_malli"]["default"] == ""
    assert syotteet["kortin_tilarivit"] == {**syotteet["kortin_tilarivit"], "type": "boolean", "default": True}
    assert data["on"]["workflow_call"]["secrets"]["ANTHROPIC_API_KEY"]["required"] is True
    assert list(data["jobs"]) == ["kortti-ajo", "jalkitarkistus"]
    job = data["jobs"]["kortti-ajo"]
    assert job["permissions"] == {"contents": "write", "pull-requests": "write", "issues": "write",
                                  "id-token": "write", "actions": "read"}
    assert job["concurrency"]["group"] == "kortti-ajo-${{ github.repository }}"
    assert job["timeout-minutes"] == "${{ inputs.aikakatkaisu_min }}"
    assert job["env"]["HAARA"] == "feature/${{ inputs.kortti }}"
    assert set(job["outputs"]) == {"malli", "nimi", "lahde", "sallitut", "vahti_sha", "agentti", "lopputulos"}
    assert job["steps"][0]["name"].startswith("Tarkista syötteet ja budjetti")
    teksti = (TYONKULUT / "kortti-ajo.yml").read_text(encoding="utf-8")
    assert "# v1.0.268" in teksti and "PORTTI_AJO_BUDJETTI_USD puuttuu" in teksti


def test_kortti_ajon_jalkeen_agentin_jobissa_ei_ole_tokeneita() -> None:
    """Agentti on voinut ajaa jobin runnerilla mitä tahansa: tokenia käyttävät tarkistukset eivät ole siellä."""
    data = lue(TYONKULUT / "kortti-ajo.yml")
    agenttijob = data["jobs"]["kortti-ajo"]
    nimet = [str(askel.get("name", "")) for askel in agenttijob["steps"]]
    agentin_jalkeen = agenttijob["steps"][nimet.index(askel(agenttijob, "Aja agentti")["name"]) + 1:]
    assert [str(askel["name"]).split(" (")[0] for askel in agentin_jalkeen] == [
        "Poimi ajon tulos suoritustiedostosta", "Tallenna ajon tulos artefaktiksi jälkitarkistusta varten"]
    for jalkiaskel in agentin_jalkeen:
        assert "GH_TOKEN" not in jalkiaskel.get("env", {}) and "secrets." not in str(jalkiaskel)
    assert "claude-execution-output.json" in agentin_jalkeen[0]["run"] and "modelUsage" in agentin_jalkeen[0]["run"]
    assert agentin_jalkeen[1]["with"]["name"] == "kortti-ajon-tulos"
    kutsu = data["jobs"]["jalkitarkistus"]
    assert kutsu["uses"] == "./.github/workflows/kortti-ajo-jalkitarkistus.yml", "sama sha kuin kutsuvalla työnkululla"
    assert kutsu["needs"] == "kortti-ajo" and kutsu["if"] == "always()"
    assert kutsu["permissions"] == {"contents": "read", "pull-requests": "write", "issues": "write", "actions": "read"}
    assert "secrets" not in kutsu, "jälkitarkistus ei saa API-avainta"
    jalki = lue(TYONKULUT / "kortti-ajo-jalkitarkistus.yml")
    assert set(kutsu["with"]) == set(jalki["on"]["workflow_call"]["inputs"]), "jokainen syöte välitetään"
    assert kutsu["with"]["ajon_tulos"] == "${{ needs.kortti-ajo.result }}"
    assert kutsu["with"]["vahti_sha"] == "${{ needs.kortti-ajo.outputs.vahti_sha }}"
    assert kutsu["permissions"] == jalki["jobs"]["jalkitarkistus"]["permissions"]


def test_jalkitarkistus_lukee_tilan_apista_ja_vie_tuloksettoman_kierroksen_ctolle() -> None:
    teksti = (TYONKULUT / "kortti-ajo-jalkitarkistus.yml").read_text(encoding="utf-8")
    jalki = lue(TYONKULUT / "kortti-ajo-jalkitarkistus.yml")["jobs"]["jalkitarkistus"]
    assert "ANTHROPIC_API_KEY" not in teksti and "secrets." not in teksti, "jälkitarkistus ei saa API-avainta"
    assert not any("claude-code-action" in str(jalkiaskel.get("uses", "")) for jalkiaskel in jalki["steps"])
    assert jalki["env"]["AJON_TULOS"] == "${{ inputs.ajon_tulos }}" and jalki["env"]["LOPPUTULOS"] == "${{ inputs.lopputulos }}"
    assert jalki["if"] == "always()", "kutsuvan jobin ehto ei yksin riitä, jos koko ajo perutaan"
    assert all(jalkiaskel.get("if", "").startswith("always()") for jalkiaskel in jalki["steps"]), \
        "jälkitarkistus ajetaan, vaikka agentin job epäonnistui tai peruttiin"
    haku = askel(jalki, "Etsi ajon PR")["run"]
    assert "select(.head.repo.full_name == $repo)" in haku, "forkin PR samalla haaran nimellä ei ole ajon PR"
    assert "gh pr list" not in teksti and "gh pr list" not in (TYONKULUT / "kortti-ajo.yml").read_text(encoding="utf-8")
    tarkistus = askel(jalki, "Tarkista ajon lopputulos")["run"]
    for vaatimus in ('"$AJON_TULOS" != "success"', '"$LOPPUTULOS" != "success"', 'repos/$REPO/issues/$PR/labels'):
        assert vaatimus in tarkistus, vaatimus
    yhteenveto = askel(jalki, "Ajon yhteenveto")
    assert yhteenveto["if"] == "always() && inputs.agentti != '' && inputs.agentti != 'skipped'"
    assert "portti-moottori/ajo/ajon_yhteenveto.py" in yhteenveto["run"] and '--sallitut "$SALLITUT"' in yhteenveto["run"]
    assert yhteenveto["run"].rstrip().endswith('exit "$tulos"'), "luvaton tai todentamaton malli kaataa ajon näkyvästi"
    assert askel(jalki, "Main-vahti")["env"]["SHA_ENNEN"] == "${{ inputs.vahti_sha }}"
    paattyi = askel(jalki, "Korjauskierros päättyi")
    assert paattyi["if"] == "always() && inputs.korjaa_pr != ''"
    assert 'portti.cli ohjaus-ajo-paattyi --repo "$REPO" --pr "$KORJAA_PR" --haara "$HAARA"' in paattyi["run"], \
        "moottori päättää PR:n tilasta, jääkö kierros ilman ihmistä"


def test_kortti_ajon_portti_on_ennen_kielimallia_ja_malli_tulee_vain_siita() -> None:
    job = lue(TYONKULUT / "kortti-ajo.yml")["jobs"]["kortti-ajo"]
    syotteet, portti, labelit, prompti, agentti = jarjestys(
        job, "Tarkista syötteet ja budjetti", "Portti ennen kielimallia", "Varmista labelit", "Kokoa prompti", "Aja agentti")
    assert syotteet < portti < labelit < prompti < agentti
    askeleet = job["steps"]
    tarkistukset = askeleet[portti]["run"]
    for vaatimus in ('kortin-tila --kortti "$kortti_polku" --vaadi hyväksytty', "matching-refs/heads/$HAARA",
                     "portti.cli malli --kortti", '"$TAPAHTUMA" = "workflow_dispatch"', 'gh api "users/$tunnus"',
                     "korjauskierros vaatii alkuperäisen ajon mallin", "on jo olemassa",
                     "label agentti puuttuu", '"$pr_mallilabelit" != "malli-$nimi"', "(syy yllä)"):
        assert vaatimus in tarkistukset, vaatimus
    assert askeleet[portti]["env"]["MALLI_KASIN"] == "${{ inputs.malli_kasin }}"
    teksti = (TYONKULUT / "kortti-ajo.yml").read_text(encoding="utf-8")
    assert teksti.count("inputs.malli_kasin") == 1, "käsin valittu malli kulkee vain portin kautta"
    assert "--model ${{ inputs." not in teksti and "inputs.malli }}" not in teksti
    syotetarkistus = askeleet[syotteet]["run"]
    assert '[[ "$BUDJETTI" =~ ^[0-9]+(\\.[0-9]+)?$ ]]' in syotetarkistus and "| grep" not in syotetarkistus, \
        "koko arvon täsmäys: monirivinen arvo ei pääse agentin komentoriville"
    assert teksti.count("vars.PORTTI_AJO_BUDJETTI_USD") == 1 and teksti.count("inputs.max_turns") == 1
    argumentit = askeleet[agentti]["with"]["claude_args"]
    for lippu in ("--model ${{ steps.portti.outputs.malli }}", "--max-budget-usd ${{ steps.syotteet.outputs.budjetti }}",
                  "--max-turns ${{ steps.syotteet.outputs.max_turns }}", "--setting-sources user",
                  "--agents '${{ steps.prompti.outputs.agentit }}'", '--allowedTools "${{ steps.prompti.outputs.tyokalut }}"'):
        assert lippu in argumentit, lippu
    assert askeleet[agentti]["with"]["settings"] == "${{ steps.prompti.outputs.asetukset }}"
    for muuttuja in ("ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1",
                     "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1"):
        assert muuttuja in tarkistukset, muuttuja


def test_kortti_ajon_agentti_on_rajattu() -> None:
    job = lue(TYONKULUT / "kortti-ajo.yml")["jobs"]["kortti-ajo"]
    assert job["env"]["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] == "1", "API-avain pois aliprosessien ympäristöstä parhaan kyvyn mukaan"
    assert "GH_TOKEN" not in job["env"]
    assert askel(job, "Hae kuluttajarepo")["with"]["persist-credentials"] is False, "GITHUB_TOKEN ei jää gitin asetuksiin"
    agentti = askel(job, "Aja agentti")
    assert str(agentti["uses"]).startswith("anthropics/claude-code-action@")
    assert "github_token" not in agentti["with"], "pushit Claude GitHub Appin tokenilla, ei GITHUB_TOKENilla"
    kokoa = askel(job, "Kokoa prompti")["run"].rstrip()
    assert kokoa.endswith("rm -rf portti-moottori"), "portin kopio pois ennen agenttia"
    assert 'repos/$REPO/issues/$KORJAA_PR/comments' in kokoa and '--kommentit "$tulosteet/kommentit.json"' in kokoa
    assert kokoa.index('rm -f "$tulosteet/kommentit.json"') < kokoa.index("rm -rf portti-moottori"), \
        "PR:n kommenttien raakadata ei jää agentin luettavaksi"
    assert "secrets.token_hex" in kokoa and 'echo "prompti<<$erotin"' in kokoa, "promptin sisältö ei voi päättää tulostetta"


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
