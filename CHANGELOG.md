# Muutoshistoria

## 0.4.0

- Ohjaus: uusi moduuli `portti/ohjaus.py` ja komento `portti ohjaa`. Deterministinen päätöstaulu (rivit a–e, README)
  päättää evidencestä, testien tilasta, muuttuneista poluista, labeleista (`agentti`, `korjauskierros-<n>`,
  `malli-<nimi>`), PR:n haarasta, forkkitiedosta ja edellisestä päätöksestä, meneekö PR katselmoitavaksi, CTO:lle
  vai agentille korjauskierrokselle. Fail-closed: puuttuva evidence, puuttuva testitulos, eri head, tuntematon
  tier tai `.github/**`- ja `.portti/**`-polut vievät CTO:lle. Uusi korjauskierros vaatii kortin slugin (haara
  `feature/<slug>`) ja alkuperäisen ajon mallin (yksi sallittu label `malli-<nimi>`); muuten PR menee CTO:lle.
  Päätös-JSON on järjestetty eikä sisällä tunnuksia.
- Mallin valinta: uusi moduuli `portti/malli.py` ja komento `portti malli --kortti <polku> [--kasin <arvo>]
  [--alkuperainen <arvo>] [--json]` toteuttavat CTO:n mallipäätöksen 6.11.2026. Sallitut nimet ja tunnisteet ovat
  yhdessä vakiossa (opus, fable). Oletus on opus, käsin valittu arvo voittaa kortin rivin `- Malli:`,
  korjauskierros käyttää alkuperäisen ajon mallia, ja kielletty tai tyhjä arvo palauttaa 1 ja kirjaa syyn.
  `portti/kortti.py` lukee kortin metarivit ja komento `portti kortin-tila` tarkistaa tilarivin.
- Ohjauksen toteutus: `portti ohjaus-toteuta` (`portti/ohjaus_toteutus.py`, `portti/ohjaus_kommentti.py`) asettaa ja
  poistaa labelit (luo puuttuvat), pyytää katselmoijan roolin mukaan kuluttajarepon muuttujista (T1 puuttuu → CTO;
  CTO puuttuu → ei pyyntöä, kommentti kertoo), kirjoittaa yhden päivittyvän ohjauskommentin ja käynnistää uudessa
  korjauskierroksessa kuluttajan kortti-ajon `workflow_dispatch`-tapahtumalla (syötteinä kortti, PR:n numero ja
  alkuperäisen ajon malli). Idempotentti: `portti
  ohjaus-edellinen` lukee edellisen päätöksen ohjauskommentista ja `portti ohjaa --edellinen` toistaa tälle headille
  jo käynnistetyn kierroksen käynnistämättä uutta (`kaynnista_kortti_ajo`), joten kierroslaskuri ei kasva samasta
  tilasta eikä PR mene CTO:lle kesken korjauksen. `GitHubApi`: labelit, katselmoijapyyntö, työnkulun käynnistys.
- Uudelleenkäytettävä työnkulku `.github/workflows/ohjaus.yml` (`workflow_call`): ajetaan kuluttajan oletushaarasta
  `workflow_run`-tapahtumasta, ei hae eikä suorita PR:n koodia, hakee moottorin pinnatusta shasta
  (`job.workflow_repository`, `job.workflow_sha`), odottaa molempien työnkulkujen valmistumista samalle headille,
  lataa evidencen Portti-ajon artefaktista ja muuttuneet polut API:sta. Toimii forkin PR:ille: PR haetaan
  head-haaran omistajasta, haarasta ja shasta. Forkin PR ei koskaan käynnistä korjauskierrosta. Vähimmät oikeudet:
  contents read, pull-requests write, issues write, actions write (vain dispatch); token annetaan vain sitä
  tarvitseville askelille. concurrency on vain uudelleenkäytettävän työnkulun jobissa, ei kuluttajan mallissa.
- Uudelleenkäytettävä kortti-ajo `.github/workflows/kortti-ajo.yml` (`workflow_call`): rakentaa hyväksytyn kortin
  PR:ksi tai korjaa agentin PR:n korjauskierroksessa `anthropics/claude-code-action`illa (pinnattu v1.0.268-shaan)
  Claude GitHub Appin tokenilla. Syötteet kortti, korjaa_pr, malli_kasin, alkuperainen_malli, max_turns,
  testikomennot, kortin_tilarivit, saantolohko_polku; salaisuus ANTHROPIC_API_KEY; budjetti muuttujasta
  PORTTI_AJO_BUDJETTI_USD (puuttuessa ajo ei käynnisty). Ennen kielimallia työnkulku tarkistaa, että kortin tila on
  hyväksytty oletushaarassa, että kortin haaraa `feature/<slug>` ei ole (uusi ajo) ja että `portti malli` palauttaa
  sallitun mallin; malli annetaan agentille vain tuon askeleen tulosteesta, ja `malli_kasin` hyväksytään vain
  ihmisen käsin käynnistämässä ajossa. Prompti on versioitu tiedosto `ajo/prompti.md`, jonka `ajo/kokoa_prompti.py`
  täyttää ja johon kuluttajan sääntölohko liitetään sanatarkasti: haara `feature/<slug>`, kortin tilarivit
  (valinnaiset), kortin hyväksymiskriteeri, tarkistaja-aliagentti Opuksella puhtaalla kontekstilla ja rivi "Ei
  ajettu oikealla datalla." Aliagentit pakotetaan tarkistajan malliin ja aliakset sonnet ja haiku ohjataan siihen.
  Työkalut rajataan sallittujen listaan (tiedostot, oman haaran git ja gh, repon asennus- ja testikomennot
  sanatarkasti); repon omia `.claude`-asetuksia ei ladata, ja API-avain poistetaan agentin aliprosessien
  ympäristöstä parhaan kyvyn mukaan. Portin kopio poistetaan työtilasta ennen agenttia, labelit `agentti` ja `malli-<nimi>`
  varmistetaan ennen ajoa ja sen jälkeen, ja ajo kaatuu, jos action ohitti agentin ajon. `ajo/ajon_yhteenveto.py`
  kirjoittaa ajon yhteenvedon (malli, kortti, kesto, tokenit, kulu, käytetyt mallit) työnkulun yhteenvetoon ja PR:n
  kuvaukseen ja kaataa ajon, jos se käytti mallia, joka ei ole sallittu. Main-vahti havaitsee oletushaaran
  muutoksen ajon aikana, kaataa ajon ja kommentoi CTO:lle; se ei estä. Yksi ajo kerrallaan repoa kohden.
- Oletuspolicy: kuluttajan `.github/workflows/portti-ohjaus.yml` ja `.github/workflows/kortti-ajo.yml` lisätty
  kova-kategoriaan `portti_itse`; regressiotestit jokaiselle polulle. Portin oma policy: `portti/malli.py`
  kova-kategoriaan `mallipaatos`.
- Kuluttajan mallit kansiossa `mallit/` (portti.yml, portti-ohjaus.yml, kortti-ajo.yml, kortin-pohja.md) ja
  käyttöönotto-ohje README:ssä.
- CLAUDE.md repoon: tietoturvasääntö, julkisen repon rajoitteet, moottori ilman kielimallia, mallipäätös 6.11.2026,
  main vain CTO:n PR:llä, testikomennot. ARCHITECTURE: arviointi-moduuli taulukkoon, uudet moduulit ja
  riippuvuussuunta, kortti-ajo erillisenä komponenttina.
- Katselmoinnin korjaukset (11.11.2026, kaksi puhtaan kontekstin tarkistajaa ja rivikohtainen luku):
  - Ohjaus lukee ja päivittää vain oman kirjoittajansa (`github-actions[bot]`, `--kommentoija`) ohjauskommenttia.
    Rikkinäinen konedata ei kaada ohjausta: korjauskierrosta odottava agentin PR menee CTO:lle.
  - Rivi a: väärän muotoinen evidence ja vajaa tiedostolista (`ohjaa --polut-vajaat`) vievät CTO:lle. Outo
    kierroslabel ei kaada ohjausta; kierroksiksi lasketaan vain ASCII-numerot.
  - Toteutus: kortti-ajon käynnistyksen virhe vie PR:n CTO:lle labelilla `jumissa`. Katselmoijapyynnön virhe
    kirjataan kommenttiin ja pyydetään seuraavaa ehdokasta; kun T1 on PR:n tekijä, pyydetään CTO; tunnusten
    vertailu ei riipu kirjainkoosta. `ohjaus-toteuta` palauttaa virheessä 1. Uudessa korjauskierroksessa
    ohjauskommentti kirjoitetaan ennen kortti-ajon käynnistystä. Uusi komento `ohjaus-ajo-paattyi` ajetaan
    korjauskierroksen kortti-ajon jälkeen: se vie PR:n CTO:lle vain, jos PR on kortin avoin agentin PR ja odottaa
    yhä samaa kierrosta samalla headilla. CTO:lle jumissa viety PR ei saa uutta kierrosta samalla headilla
    (konedatan merkintä `kierrokset_pysaytetty`).
  - Portin oma kommentti: vain kirjoittajan (`kommentti --kommentoija`, oletus `github-actions[bot]`) kommenttia
    päivitetään, ja konedata, joka ei jäsenny, ohitetaan luettaessa.
  - Kortin metarivit: aidattujen koodilohkojen sisältöä ei lueta (aidat CommonMarkin mukaan), ja tila- tai
    mallirivi väärässä muodossa tai HTML-kommentin sisällä estää ajon.
  - `ohjaus.yml`: evidence-artefakti puretaan työtilan ulkopuolelle; tiedostolistan kattavuus tarkistetaan.
  - `kortti-ajo.yml` ja uusi `kortti-ajo-jalkitarkistus.yml`: agentin jälkeiset tarkistukset ovat omassa
    jobissaan ja tiedostossaan puhtaalla runnerilla (lopputulos, labelit, yhteenveto, käytetyt mallit,
    main-vahti), ja agentin jobiin jää agentin jälkeen vain tokenittomat askeleet. Korjauskierroksen PR:ltä vaaditaan label `agentti` ja syötettä vastaava mallilabel; syötteet
    tarkistetaan koko arvoltaan; PR haetaan vain repon omasta haarasta. Korjauskierros, joka epäonnistui,
    peruuntui tai ei tuottanut committia, viedään CTO:lle.
  - Prompti: korjauskierrokseen liitetään vain portin ja ohjauksen omat kommentit, eikä agentilla ole työkalua
    PR:n kommenttien lukemiseen. Sääntölohkon `{{ }}` ei kaada kokoamista, promptin tulosteen erotin on
    satunnainen, eikä testikomennossa saa olla jokerimerkkiä `*`.
  - Ajon yhteenveto: mallitarkistus kaatuu, kun käytettyjä malleja ei voida todentaa, ja hyväksyy tunnisteen vain
    sellaisenaan tai päätteillä `-VVVVKKPP` ja `[1m]`.

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
