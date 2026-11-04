# Muutoshistoria

## 0.4.0

- Ohjaus: uusi moduuli `portti/ohjaus.py` ja komento `portti ohjaa`. Deterministinen päätöstaulu (rivit a–e, README)
  päättää evidencestä, testien tilasta, muuttuneista poluista, labeleista (`agentti`, `korjauskierros-<n>`) ja
  forkkitiedosta, meneekö PR katselmoitavaksi, CTO:lle vai agentille korjauskierrokselle. Fail-closed: puuttuva
  evidence, puuttuva testitulos, eri head tai `.github/**`- ja `.portti/**`-polut vievät CTO:lle. Päätös-JSON on
  järjestetty eikä sisällä tunnuksia.
- Ohjauksen toteutus: `portti ohjaus-toteuta` (`portti/ohjaus_toteutus.py`, `portti/ohjaus_kommentti.py`) asettaa ja
  poistaa labelit (luo puuttuvat), pyytää katselmoijan roolin mukaan kuluttajarepon muuttujista (T1 puuttuu → CTO;
  CTO puuttuu → ei pyyntöä, kommentti kertoo), kirjoittaa yhden päivittyvän ohjauskommentin ja käynnistää
  korjauskierroksessa kuluttajan kortti-ajon `workflow_dispatch`-tapahtumalla. Idempotentti: sama päätös samalle
  headille ei käynnistä kierrosta uudelleen. `GitHubApi`: labelit, katselmoijapyyntö, työnkulun käynnistys.
- Uudelleenkäytettävä työnkulku `.github/workflows/ohjaus.yml` (`workflow_call`): ajetaan kuluttajan oletushaarasta
  `workflow_run`-tapahtumasta, ei hae eikä suorita PR:n koodia, hakee moottorin pinnatusta shasta
  (`job.workflow_repository`, `job.workflow_sha`), odottaa molempien työnkulkujen valmistumista samalle headille,
  lataa evidencen Portti-ajon artefaktista ja muuttuneet polut API:sta. Toimii forkin PR:ille (PR haetaan head-shasta);
  forkin PR ei koskaan käynnistä korjauskierrosta. Vähimmät oikeudet: contents read, pull-requests write, issues write,
  actions write (vain dispatch).
- Uudelleenkäytettävä kortti-ajo `.github/workflows/kortti-ajo.yml` (`workflow_call`): rakentaa hyväksytyn kortin
  PR:ksi tai korjaa agentin PR:n korjauskierroksessa `anthropics/claude-code-action`illa (pinnattu v1.0.268-shaan)
  Claude GitHub Appin tokenilla. Syötteet kortti, korjaa_pr, malli (oletus claude-opus-5-5), max_turns, testikomennot,
  saantolohko_polku; salaisuus ANTHROPIC_API_KEY; budjetti muuttujasta PORTTI_AJO_BUDJETTI_USD (puuttuessa ajo ei
  käynnisty). Prompti on versioitu tiedosto `ajo/prompti.md`, jonka `ajo/kokoa_prompti.py` täyttää ja johon kuluttajan
  sääntölohko liitetään sanatarkasti. Työkalut rajataan sallittujen listaan (tiedostot, oman haaran git ja gh, repon
  testikomennot sanatarkasti). Main-vahti havaitsee oletushaaran muutoksen ajon aikana, kaataa ajon ja kommentoi
  CTO:lle; se ei estä. Yksi ajo kerrallaan repoa kohden.
- Oletuspolicy: kuluttajan `.github/workflows/portti-ohjaus.yml` ja `.github/workflows/kortti-ajo.yml` lisätty
  kova-kategoriaan `portti_itse`; regressiotestit jokaiselle polulle.
- Kuluttajan mallit kansiossa `mallit/` (portti.yml, portti-ohjaus.yml, kortti-ajo.yml) ja käyttöönotto-ohje README:ssä.
- CLAUDE.md repoon: tietoturvasääntö, julkisen repon rajoitteet, moottori ilman kielimallia, main vain CTO:n PR:llä,
  testikomennot. ARCHITECTURE: arviointi-moduuli taulukkoon, uudet moduulit ja riippuvuussuunta, kortti-ajo erillisenä
  komponenttina.

## 0.3.0

- Action ja CLI: syöte `policy_lahde` (base, head, auto), oletus `base` kaikissa tiloissa: policy ja tapaukset
  luetaan base-haarasta, jotta PR ei voi keventää omaa luokitustaan. `head` vain eksplisiittisesti (policyn
  kehitys-PR:t). Jos basessa ei ole policyä, luetaan pelkkä oletuspolicy kaikissa tiloissa ja kommentti
  kertoo sen ("oletus (basessa … ei policy.yml-tiedostoa)"); headia ei lueta ilman eksplisiittistä valintaa.
  Evidenceen kenttä `policy_lahde`. Tapaukset ovat valinnaisia: basesta puuttuva tapaustiedosto ohittaa
  askeleen, ja `tarkista-tapaukset` kertoo policyn ja tapausten lähteet erikseen.
- Enforce-tila: uusi komento `portti esto --evidence <json>` palauttaa 1, kun tila on enforce ja verdict on PUUTE,
  KOVA tai LIIAN-ISO; action ajaa sen viimeisenä askeleena kommentin ja artefaktin jälkeen. Shadow ei kaada koskaan.
  Punainen check on neuvoa-antava: moottori, README ja workflow-mallit eivät oleta pakollisia checkejä, branch
  protectionia eivätkä CODEOWNERS-pakkoa. Enforce-kommentti on oma kommenttinsa (tunniste sisältää tilan).
  README kuvaa `pull_request`-tapahtuman rajoitteen: PR voi poistaa ajon tai vaihtaa shan, shadow-raportti näyttää sen.
- Moottorin oma workflow ajaa yhden jobin enforce-tilassa.
- Policy: allow-polku, joka leikkaa kova- tai pehmea-polun, on latausvirhe (T0-aukko). Virheilmoitus nimeää
  polut ja `allow.laajenna_paitsi`-korjauksen. ei_laskennassa saa leikata deny-polkuja (generoidut tiedostot). Oletuksesta poistettu `ei_laskennassa_lukkotiedostot` (lukkotiedostot
  lasketaan, ovat kova) ja allow-poikkeuksiin lisätty CLAUDE.md ja .claude/**.
- Arviointi: deny-osuma (kova tai pehmea) ei koskaan ole vapaa tiedosto, vaikka polku osuisi allow-globiin tai
  testimalliin, ja PEHMEÄ ei ole hyväksyttävissä millään portaalla. Sulkee aukon, jota päällekkäisyystarkistus ei
  näe mallitasolla (kansio-glob `kansio/**` vastaan pääte-glob `*.md`). Invarianttitestit keksityin poluin.
- Kommentin konedata laajennettu: tila, policy_lahde, deny-kategoriat, portaat, puute. Shadow-raportti lukee nämä;
  vanhasta (0.2.0) konedatasta portaat johdetaan verdictistä ja tieristä, kategoriat näkyvät "ei tiedossa".
  Kun PR:llä on shadow- ja enforce-kommentti rinnakkain, raportti valitsee PR:n headiin täsmäävän, muuten viimeisimmän.
- `portti shadow-raportti`: useita `--repo`, ryhmittely base-haaran mukaan (main, feat/* ja feature/* yhdessä,
  muut omanaan), draftit pudotetaan, per ryhmä mittarit, väärät KOVA/PEHMEÄ-osumat kategorioittain, jakauma
  tiereittäin ja portaittain; `--json`.
- Komentorivi jaettu jäsentimeen (cli.py) ja komentoihin (cli_komennot.py).
- Oletuspolicyn kommentti ja README: kova-kategoria on neuvoa-antava; nimettyä katselmoijaa tai CODEOWNERS-pakkoa
  ei oleteta, koska Free-tason yksityisrepossa niitä ei ole. Invarianttitestit: base-luku ei kevene PR:n omasta
  policymuutoksesta; deny-literaali `.md`-tiedosto oletuksen allow-listalla on latausvirhe.

## 0.2.0

- Action: `PYTHONSAFEPATH=1` kaikissa Python-askelissa, jotta PR:n checkoutin tiedostot eivät varjosta moottorin moduuleja.
- Action: luonnostila luetaan tapahtumasta (`github.event.pull_request.draft`); vain mergeable-tila haetaan API:sta.
- Action: uusi syöte `tapaukset_polku` (oletus `.portti/tapaukset.yml`); repon regressiotapaukset ajetaan actionissa, jos tiedosto on olemassa.
- README: `laajenna_`-esimerkki mapping-avainten sisällä (`ei_laskennassa.laajenna_polut`, `allow.laajenna_paitsi`) ja huomautus, että actionia ei voi kutsua `uses: ./<polku>`-muodossa.

## 0.1.0

- Ensimmäinen versio: policy, luokittelu, verdict, evidence, kommentti, shadow-raportti, tapaukset ja composite action.
- Synteettinen PR testaa actionin ja kommentin päivityksen.
