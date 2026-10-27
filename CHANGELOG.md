# Muutoshistoria

## 0.3.0

- Action ja CLI: syöte `policy_lahde` (head, base, auto). Enforce lukee policyn ja tapaukset base-haarasta,
  shadow PR:n headista. Jos basessa ei ole policyä, enforce kaatuu ja shadow merkitsee kommenttiin "head (basessa
  ei policy.yml-tiedostoa, luettu headista)". Evidenceen kenttä `policy_lahde`.
- Enforce-tila ei enää kaadu "ei toteutettu": luentapolku on toteutettu, verdictin estävä osa ei. Enforce-kommentti
  on oma kommenttinsa (tunniste sisältää tilan), joten shadow- ja enforce-ajo samassa PR:ssä eivät sekoitu.
- Policy: allow- tai ei_laskennassa-polku, joka leikkaa kova- tai pehmea-polun, on latausvirhe. Virheilmoitus nimeää
  polut ja `laajenna_paitsi`-korjauksen. Oletuksesta poistettu `ei_laskennassa_lukkotiedostot` (lukkotiedostot
  lasketaan, ovat kova) ja allow-poikkeuksiin lisätty CLAUDE.md ja .claude/**.
- Kommentin konedata laajennettu: tila, policy_lahde, deny-kategoriat, portaat, puute. Shadow-raportti lukee nämä.
- `portti shadow-raportti`: useita `--repo`, ryhmittely base-haaran mukaan (main, feat/* ja feature/* yhdessä,
  muut omanaan), draftit pudotetaan, per ryhmä mittarit, väärät KOVA/PEHMEÄ-osumat kategorioittain, jakauma
  tiereittäin ja portaittain; `--json`.
- Komentorivi jaettu jäsentimeen (cli.py) ja komentoihin (cli_komennot.py).

## 0.2.0

- Action: `PYTHONSAFEPATH=1` kaikissa Python-askelissa, jotta PR:n checkoutin tiedostot eivät varjosta moottorin moduuleja.
- Action: luonnostila luetaan tapahtumasta (`github.event.pull_request.draft`); vain mergeable-tila haetaan API:sta.
- Action: uusi syöte `tapaukset_polku` (oletus `.portti/tapaukset.yml`); repon regressiotapaukset ajetaan actionissa, jos tiedosto on olemassa.
- README: `laajenna_`-esimerkki mapping-avainten sisällä (`ei_laskennassa.laajenna_polut`, `allow.laajenna_paitsi`) ja huomautus, että actionia ei voi kutsua `uses: ./<polku>`-muodossa.

## 0.1.0

- Ensimmäinen versio: policy, luokittelu, verdict, evidence, kommentti, shadow-raportti, tapaukset ja composite action.
- Synteettinen PR testaa actionin ja kommentin päivityksen.
- Synteettinen policy-PR testaa policyn lähteen (head vs base).
