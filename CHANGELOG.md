# Muutoshistoria

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
