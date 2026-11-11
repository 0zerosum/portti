# Portti

Deterministinen katselmointiportti git-repoille. Yksi moottori, policy ja workflow
jokaisessa kuluttajarepossa. Ei LLM:ää, ei hyväksyntää: moottori laskee faktat,
soveltaa sääntöä ja kirjoittaa evidence-JSONin sekä yhden päivittyvän PR-kommentin.
Versiosta 0.4.0 alkaen [ohjaus](#ohjaus) päättää samoista faktoista deterministisesti, minne PR
menee (katselmoitavaksi, CTO:lle vai agentille korjattavaksi), ja erillinen [kortti-ajo](#kortti-ajo)
rakentaa hyväksytyn kortin PR:ksi ilman ihmisen istuntoa. Kortti-ajon malli valitaan deterministisesti
([mallin valinta](#mallin-valinta)): koodia ei kirjoiteta Opusta heikommalla mallilla. Agenttien ja ihmisten
PR:t kulkevat portin ja ohjauksen kautta ennen ihmisen katselmointia.

## Mitä moottori tekee

`portti arvioi --base <sha> --head <sha> --policy <polku>` lukee diffin
(`git diff base...head`, uudelleennimeämiset mukaan) ja tuottaa:

- **luokitus**: substantiiviset rivit ja tiedostot, kosketut alueet, tier
  (T0, T1a, T1b, T1c tai YLI), deny-osumat tasoittain, kielletyt uudet polut,
  invarianttitestien tila
- **portit**: jokaisen portin tulos ja syy
- **verdict**: `PUUTE > KOVA > LIIAN-ISO > PEHMEÄ > VAPAA`
- **hyvaksyttavissa_portaalla**: portaat S0–S3, joilla PR olisi automaattisesti
  hyväksyttävissä (S0 = T0, S1 = +T1a, S2 = +T1b, S3 = +T1c)

Globaalit oletusarvot ovat tiedostossa [defaults/policy.yml](defaults/policy.yml).
Moduulirajat ovat tiedostossa [ARCHITECTURE.md](ARCHITECTURE.md).

## Kuluttajarepon kolme tiedostoa

Ohjaus ja kortti-ajo lisäävät kaksi työnkulkua ja sääntölohkon; ne on kuvattu kohdassa
[Käyttöönotto kuluttajarepossa](#käyttöönotto-kuluttajarepossa).

1. `.portti/policy.yml` — täydentää oletusta. Mappingit yhdistetään avain
   kerrallaan, repon lista korvaa oletuksen listan, `laajenna_<avain>` lisää siihen.
   Tuntematon avain on latausvirhe. Kova-kategoriaa `portti_itse` ei saa korvata.
   Sen polku `CODEOWNERS` on vain luokittelua varten: tiedoston muutos on kova, mutta portti ei
   edellytä tiedostoa eikä GitHubin katselmointipakkoa, jota Free-tason yksityisrepossa ei ole.

   ```yaml
   alueen_maaritys:
     prefiksit: ["palvelin/sovellus/"]
   invarianttitestit: ["tests/test_laskutus_invariantit.py"]
   deny:
     pehmea:
       laskutus:
         polut: ["palvelin/sovellus/laskutus/**"]
         perustelu: "Laskutuksen virheet näkyvät asiakkaalle."
   laajenna_kielletyt_uudet_polut: ["**/salainen/**"]
   generoidut: ["**/*_pb2.py"]
   # laajenna_ toimii myös mapping-avainten sisällä: lisää oletuksen listaan korvaamatta sitä.
   laajenna_testit: ["palvelin/tests/**"]
   ei_laskennassa:
     laajenna_polut: ["kuvat/**"]
     laajenna_paitsi: ["fixtures/henkilot.json"]
   allow:
     laajenna_paitsi: ["fixtures/henkilot.json"]
   ```

2. `.portti/tapaukset.yml` — repon omat regressiotapaukset.
   `portti tarkista-tapaukset .portti/tapaukset.yml` kaatuu poikkeamasta. Action ajaa
   tiedoston itse, jos se on olemassa (syöte `tapaukset_polku`).

   ```yaml
   tapaukset:
     - nimi: pelkkä dokumentaatio on vapaa
       base: 0123abcd
       head: 4567ef01
       odotettu_verdict: VAPAA
       odotettu_tier: T0
   ```

3. `.github/workflows/portti.yml` — kutsuu composite actionia pinnatulla sha:lla.

   ```yaml
   name: Portti
   on:
     pull_request:
       types: [opened, synchronize, reopened, ready_for_review]
   permissions:
     contents: read
     pull-requests: write
   jobs:
     portti:
       runs-on: ubuntu-latest
       steps:
         - uses: 0zerosum/portti@<pinnattu sha>
           with:
             github_token: ${{ secrets.GITHUB_TOKEN }}
   ```

   Repo on julkinen, joten `uses: 0zerosum/portti@<sha>` toimii mistä tahansa reposta
   ilman tokenia. Actionia ei voi kutsua muodossa `uses: ./<polku>` repoon haetusta
   kopiosta: actionin oma checkout-askel siivoaa työtilan ja poistaisi kopion kesken ajon.
   Jos moottoria tarvitaan samassa työnkulussa muuhun (esimerkiksi `tarkista-tapaukset`
   ennen actionia), hae se `actions/checkout`-askeleella omaan kansioonsa ja aja
   `python -m portti.cli` ympäristömuuttujilla `PYTHONPATH=<kansio>` ja `PYTHONSAFEPATH=1`
   ennen action-askelta.

## Actionin syötteet

| Syöte | Oletus | Merkitys |
|---|---|---|
| `policy_polku` | `.portti/policy.yml` | repon policy |
| `tapaukset_polku` | `.portti/tapaukset.yml` | regressiotapaukset; ajetaan, jos tiedosto on olemassa policyn lähteessä (oletuksena base), muuten ohitetaan |
| `tila` | `shadow` | `shadow` vain kommentoi; `enforce` kaataa ajon estävästä verdictistä (PUUTE, KOVA, LIIAN-ISO) |
| `policy_lahde` | `base` | `base` (base-haaran policy ja tapaukset), `head` (PR:n oma, vain eksplisiittisesti) tai `auto` (shadow → head, enforce → base) |
| `github_token` | – | PR:n tilan luku ja kommentin kirjoitus |
| `python_versio` | `3.11` | moottorin tulkki |

Shadow-tilassa action ei hyväksy, ei pyydä muutoksia eikä palauta verdictistä
estävää exit-koodia. Enforce-tilassa viimeinen askel (`portti esto`) palauttaa 1, kun
verdict on PUUTE, KOVA tai LIIAN-ISO; kommentti ja artefakti on silloin jo kirjoitettu.
Evidence ladataan artefaktiksi `portti-evidence-pr<numero>`.
Regressiotapausten poikkeama sen sijaan kaataa askeleen, kuten rikkoutunut testi.
Kaikki Python-askeleet ajetaan `PYTHONSAFEPATH=1`, jotta PR:n checkoutin tiedostot
eivät varjosta moottorin moduuleja.

## Enforce

Policy ja tapaukset luetaan oletuksena base-haaran versiosta
(`git show <base-sha>:.portti/policy.yml`), jotta PR ei voi muuttaa sääntöjä, joilla se
arvioidaan. `policy_lahde: head` lukee PR:n oman version ja on tarkoitettu policyn
kehitys-PR:ille. Jos basessa ei ole policyä, luetaan pelkkä oletuspolicy ja kommentti
kertoo sen (`Policy: oletus (basessa … ei policy.yml-tiedostoa)`); PR:n omaa policyä ei lueta
ilman `policy_lahde: head`. Oletus tulee pinnatun moottorin mukana, joten se ei ole
kevennysreitti. Sama koskee regressiotapauksia: basesta puuttuva tapaustiedosto ohittaa
askeleen. Enforce- ja shadow-ajo kirjoittavat kumpikin oman kommenttinsa.

Enforce-tilassa estävä verdict tekee checkistä punaisen. Check on neuvoa-antava:
Free-tason yksityisrepossa ei ole pakollisia checkejä eikä branch protectionia, joten
GitHub ei estä mergeä, vaan katselmoija päättää sen punaisen checkin ja kommentin
perusteella. Moottori ei oleta näitä asetuksia mistään tasosta riippumatta.

Workflow ajetaan `pull_request`-tapahtumalla, joten workflow-tiedosto tulee PR:n
headista. PR voi siis poistaa Portti-ajon, vaihtaa moottorin shan tai asettaa
`policy_lahde: head`; moottori ei voi sitä estää. Nämä polut (`.github/**` ja
`.github/workflows/portti.yml`) ovat oletuksen kova-kategorioissa `ci` ja `portti_itse`,
ja `portti shadow-raportti` näyttää jälkikäteen PR:t, joista portin kommentti puuttuu.
Katselmoija tarkistaa, että check on ajettu ja kommentti on PR:n headista. Versiosta 0.4.0 alkaen
[ohjaus](#ohjaus) sulkee tämän rakenteellisesti: se ajetaan oletushaarasta `workflow_run`-tapahtumasta,
PR ei voi muuttaa sitä, ja puuttuva evidence tai eri head vie PR:n CTO:lle.

## Päällekkäisyyssääntö

Allow-polku ei saa leikata kova- tai pehmea-polkua. Muuten pehmeä muutos voisi olla T0
ja hyväksyttävissä kaikilla portailla. Policy ei lataudu, ja virheilmoitus nimeää polut
ja korjauksen:

```
deny pehmea/testidata polku 'fixtures/henkilot.json' leikkaa allow-polun 'fixtures/**';
lisää 'fixtures/henkilot.json' listaan allow.laajenna_paitsi
```

Tarkistus on mallitasolla: sama literaalipolku tai glob, joka sisältyy toiseen.
Kansio-glob ja pääte-glob (`kansio/**` ja `*.md`) eivät leikkaa mallitasolla, joten
arviointi sulkee aukon erikseen: tiedosto, johon deny osuu, ei koskaan ole vapaa, ja
PEHMEÄ ei ole hyväksyttävissä millään portaalla. `paitsi`-lista poistaa leikkauksen.
ei_laskennassa-lista saa leikata deny-polkuja: generoitu tiedosto deny-kansiossa jää
laskennasta pois, mutta deny osuu siihen silti, eikä T0 synny ilman allow-osumaa.

## Muut komennot

- `portti shadow-raportti --repo <omistaja/repo> [--repo <toinen>] --alkaen <VVVV-KK-PP> [--json]`
  vertaa portin verdictit suljettujen PR:ien lopputuloksiin. Ryhmittelee base-haaran mukaan
  (main erikseen, feat/* ja feature/* yhdessä, muut omanaan), pudottaa draftit ja tulostaa per
  ryhmä: "KOVA/PEHMEÄ mutta mergetty muuttamatta", "VAPAA mutta hylätty", väärät osumat
  deny-kategorioittain, jakauma tiereittäin ja portaittain. Lukee kommentin konedatan (säilyy
  PR:n mukana; artefakti vanhenee). Ei tallenna mitään.
- `portti kommentti --evidence <json> --repo <omistaja/repo> --pr <n>` kirjoittaa
  tai päivittää portin kommentin.
- `portti ohjaus-edellinen --repo <omistaja/repo> --pr <n> [--tuloste <json>] [--kommentoija <tunnus>]` lukee PR:n
  edellisen ohjauspäätöksen ohjauksen oman kommentin konedatasta (head, toimenpide, kierros); `null`, jos päätöstä
  ei ole. Vain kommentoijan (oletus `github-actions[bot]`) kirjoittama kommentti luetaan.
- `portti ohjaa --head <sha> --testit success|failure|puuttuu --evidence <json> --polut <tiedosto>
  [--polut-vajaat] [--labelit a,b] [--haara <haara>] [--forkki] [--edellinen <json>] [--paatos <json>]` päättää
  ohjauksen ilman verkkoa; tuloste on järjestetty päätös-JSON ilman tunnuksia. Puuttuva tai kelvoton evidence ei
  kaada komentoa vaan vie CTO:lle. `--edellinen` estää saman korjauskierroksen käynnistämisen kahdesti samalle
  headille. `--polut-vajaat` kertoo, ettei polkulista kata PR:n kaikkia tiedostoja.
- `portti ohjaus-toteuta --paatos <json> --repo <omistaja/repo> --pr <n> [--katselmoija-cto <tunnus>]
  [--katselmoija-t1 <tunnus>] [--kortti-ajo kortti-ajo.yml --oletushaara main] [--kommentoija <tunnus>]` soveltaa
  päätöksen: labelit, korjauskierroksen käynnistys päätöksen kortilla ja mallilla, katselmoijapyyntö ja
  ohjauskommentti. Palauttaa 1, jos kortti-ajoa ei saatu käyntiin tai katselmoijapyyntö epäonnistui; PR on
  silloinkin saanut labelit ja kommentin.
- `portti ohjaus-ajo-epaonnistui --repo <omistaja/repo> --pr <n> --syy <teksti> [--katselmoija-cto <tunnus>]` vie
  PR:n CTO:lle labeleilla `katselmoitavaksi` ja `jumissa`, kun korjauskierroksen kortti-ajo epäonnistui. Kortti-ajon
  jälkitarkistus kutsuu sitä.
- `portti malli --kortti <polku> [--kasin <arvo>] [--alkuperainen <arvo>] [--json]` valitsee kortti-ajon mallin
  [mallipäätöksen](#mallin-valinta) mukaan ja tulostaa mallitunnisteen. Kielletty tai tyhjä arvo palauttaa 1 ja
  kirjaa syyn.
- `portti kortin-tila --kortti <polku> [--vaadi hyväksytty]` tulostaa kortin tilarivin arvon; `--vaadi` palauttaa
  1, jos tila on muu.

## Ohjaus

Ohjaus päättää deterministisesti ja ilman kielimallia, meneekö PR katselmoitavaksi, CTO:lle vai takaisin
agentille. Se ajetaan kuluttajan oletushaaran työnkulkuna (`workflow_run`), jota PR ei voi muuttaa, eikä se
hae eikä suorita PR:n koodia. Moottori haetaan portti-reposta samasta shasta, johon kuluttaja on pinnannut
ohjaustyönkulun. Ohjaus on fail-closed: jos tieto puuttuu tai ei täsmää, PR menee aina CTO:lle.

### Kulku

1. Kuluttajan `portti-ohjaus.yml` käynnistyy, kun `Testit` tai `Portti` valmistuu, ja kutsuu
   `0zerosum/portti/.github/workflows/ohjaus.yml@<sha>`.
2. Ohjaus hakee PR:n head-haaran omistajan, haaran ja shan perusteella (`pulls?head=<omistaja>:<haara>`, valinta
   shan mukaan; sama haku toimii forkin PR:lle), lukee molempien työnkulkujen lopputuloksen samalle headille (jos
   toinen on kesken, lopettaa ilman toimenpiteitä; sen valmistuminen ajaa ohjauksen uudelleen), lataa evidencen
   Portti-ajon artefaktista ja muuttuneet polut API:sta. Artefakti puretaan työtilan ulkopuolelle, ja työtilaan
   kopioidaan vain yksi tavallinen JSON-tiedosto. Jos tiedostolista ei kata PR:n kaikkia tiedostoja (GitHub
   palauttaa enintään 3000), moottori saa lipun `--polut-vajaat`. Jos PR:n head on jo vaihtunut, ajo lopettaa:
   uudempi ajo ohjaa.
3. `portti ohjaus-edellinen` lukee edellisen päätöksen ohjauksen omasta kommentista, `portti ohjaa` kirjoittaa
   päätös-JSONin (artefakti `portti-paatos-pr<n>`), ja `portti ohjaus-toteuta` soveltaa sen: labelit (luo
   puuttuvat), uudessa korjauskierroksessa `workflow_dispatch` kuluttajan `kortti-ajo.yml`:lle syötteillä `kortti`
   (PR:n haarasta `feature/<slug>`), `korjaa_pr` ja `alkuperainen_malli` (PR:n labelista `malli-<nimi>`),
   katselmoijapyyntö ja yksi päivittyvä ohjauskommentti. Jos kortti-ajoa ei saada käyntiin tai katselmoijapyyntö
   epäonnistuu, PR saa silti labelit ja kommentin, ja ohjauksen ajo päättyy virheeseen.

### Päätöstaulu

Syötteet: evidence (tai tieto, että se puuttuu), testityönkulun lopputulos PR:n headille (success, failure,
puuttuu; keskeytetty tai muu tulos on puuttuu), PR:n muuttuneet polut, PR:n labelit (`agentti` kertoo agentin
PR:n, `korjauskierros-<n>` laskee tehdyt kierrokset, `malli-<nimi>` kertoo alkuperäisen ajon mallin), PR:n haara,
forkkitieto ja edellinen ohjauspäätös (head, toimenpide, kierros). Rivit tarkistetaan järjestyksessä.

| Rivi | Ehto | Toimenpide | Labelit | Katselmoijan rooli |
|---|---|---|---|---|
| a | evidence puuttuu tai ei kelpaa (myös väärä rakenne); testien tila puuttuu; `evidence.head_sha` ≠ PR:n head; PR:n tiedostolista on vajaa; PR muuttaa polkuja `.github/**` tai `.portti/**` | CTO | `katselmoitavaksi`, `kova` | cto |
| b | verdict KOVA | CTO | `katselmoitavaksi`, `kova` | cto |
| c | testit failure tai verdict PUUTE (luonnos, konflikti): ihmisen PR | korjattava (kommentti tekijälle) | `korjattava` | – |
| c | sama, agentin PR, ja edellinen päätös käynnisti kierroksen n tälle samalle headille | korjauskierros n jatkuu, uutta ajoa ei käynnistetä | `korjauskierros-<n>` | – |
| c | sama, agentin PR, kierroksia < 2 ja käynnistyksen tiedot ovat koossa | uusi korjauskierros, kortti-ajo käynnistetään alkuperäisen ajon mallilla | `korjauskierros-<n>` | – |
| c | sama, agentin PR muuten: forkista, kierroksia ≥ 2, käynnistyksen tieto puuttuu tai edellistä päätöstä ei voitu lukea | CTO | `katselmoitavaksi`, `jumissa` | cto |
| d | verdict LIIAN-ISO: agentin PR, ja edellinen päätös käynnisti kierroksen n tälle samalle headille | korjauskierros n jatkuu, uutta ajoa ei käynnistetä | `korjauskierros-<n>` | – |
| d | sama, agentin PR, kierroksia < 1 ja käynnistyksen tiedot ovat koossa | uusi korjauskierros, ohje "pienennä muutos kortin rajaukseen" | `korjauskierros-1` | – |
| d | sama muuten: ihmisen PR, forkista, kierroksia ≥ 1, käynnistyksen tieto puuttuu tai edellistä päätöstä ei voitu lukea | CTO | `katselmoitavaksi`, `liian-iso` | cto |
| e | verdict PEHMEÄ tai VAPAA ja testit success | katselmoitavaksi | `katselmoitavaksi`, `tier-<tier>` | T0–T1c → t1, muut → cto |
| – | mikä tahansa muu tila, myös tuntematon tier | CTO | `katselmoitavaksi`, `kova` | cto |

Käynnistyksen tiedot: PR:n haara on muotoa `feature/<slug>` ja PR:llä on täsmälleen yksi sallittu label
`malli-<nimi>` (opus tai fable). Jos haara on muu tai label puuttuu, on moniselitteinen tai nimeää kielletyn
mallin, uutta korjauskierrosta ei käynnistetä vaan PR menee CTO:lle.

Korjauskierros ei jää ilman ihmistä, jos ajo ei toteudu. Jos kortti-ajon käynnistys epäonnistuu (työnkulkua ei
ole, oikeus puuttuu tai päätöksestä puuttuu tieto), `ohjaus-toteuta` vie PR:n CTO:lle labeleilla
`katselmoitavaksi` ja `jumissa`; kierroslabel jää laskuriin. Jos käynnistetty kortti-ajo epäonnistuu, peruuntuu
jonosta tai ei tuota uutta committia, kortti-ajon jälkitarkistus tekee saman komennolla
`portti ohjaus-ajo-epaonnistui`.

Jokainen toimenpide, joka vie PR:n ihmiselle (CTO, katselmoitavaksi), asettaa labelin `katselmoitavaksi`.
Korjauskierrokset luetaan labeleista `korjauskierros-<n>` (suurin n, vain ASCII-numerot); niitä ei koskaan
poisteta, koska ne ovat laskuri. Tilalabelit `katselmoitavaksi`, `kova`, `jumissa`, `korjattava`, `liian-iso` ja `tier-*` poistetaan,
kun tila vaihtuu; `agentti`, `malli-<nimi>` ja vieraat labelit jäävät. Forkin PR ei koskaan käynnistä
korjauskierrosta.

Katselmoijien tunnukset eivät ole repossa: ne luetaan kuluttajarepon muuttujista `PORTTI_KATSELMOIJA_CTO` ja
`PORTTI_KATSELMOIJA_T1`. PR:n tekijää ei pyydetä katselmoijaksi, eikä tunnusten vertailu riipu kirjainkoosta.
Jos T1 puuttuu tai on PR:n tekijä, pyydetään CTO. Jos CTO puuttuu tai on PR:n tekijä eikä muuta ehdokasta ole,
katselmoijaa ei pyydetä ja ohjauskommentti kertoo syyn. Jos pyyntö epäonnistuu (esimerkiksi tunnus ei ole repon
jäsen), pyydetään seuraavaa ehdokasta, virhe kirjataan kommenttiin ja ohjauksen ajo päättyy virheeseen.
Kommentin katselmoijarivi kertoo sen, jota oikeasti pyydettiin. Agentin PR avataan ilman katselmoijaa; ohjaus
asettaa sen.

Idempotenssi: työnkulku lukee edellisen päätöksen ohjauksen oman kommentin konedatasta (head, toimenpide, kierros)
ja antaa sen moottorille. Ohjaus lukee ja päivittää vain kommentoijansa (`github-actions[bot]`) kirjoittamaa
kommenttia: muun kirjoittajan kommentti, jossa on ohjauksen tunniste, ohitetaan. Jos oman kommentin konedata
puuttuu tai ei jäsenny, korjauskierrosta odottava agentin PR menee CTO:lle; muihin riveihin edellinen päätös ei
vaikuta. Jos edellinen päätös käynnisti korjauskierroksen tälle samalle headille, uusi päätös toistaa saman
kierroksen ja päätöksen kenttä `kaynnista_kortti_ajo` on false: kortti-ajoa ei käynnistetä toista kertaa,
kierroslaskuri ei kasva eikä PR mene CTO:lle kesken korjauksen, vaikka ohjaus ajetaan samalle headille uudelleen
(Testit ja Portti valmistuvat erikseen, tai ajo käynnistetään uudelleen). Uusi head aloittaa uuden arvion.
concurrency on head-haaraa kohden ilman keskeytystä.

### Oikeudet

`contents: read`, `pull-requests: write`, `issues: write` (labelit) ja `actions: write` vain
`workflow_dispatch`-kutsua varten; se sisältää ajojen ja artefaktin lukuoikeuden. Salaisuuksia ei tarvita.

### Mitä ohjaus ei estä ilmaistasolla

- Mergeä: ei pakollisia checkejä eikä haarasuojausta. Ohjaus asettaa labelit ja katselmoijan; ihminen päättää.
- PR:ää, joka poistaa oman Portti-ajonsa tai vaihtaa shan: ohjaus vie sen CTO:lle (evidence puuttuu, eri head,
  `.github/**`), ei estä sitä.
- Katselmoijan ohittamista: pyyntö on pyyntö, ei pakko.
- Ohjauskommentin muokkaamista kirjoitusoikeudella: ohjaus lukee vain oman kommenttinsa, mutta repon ylläpitäjä
  voi muokata sitä. Jäsentymätön konedata vie korjauskierrosta odottavan PR:n CTO:lle; uskottavasti muokattu
  konedata voi estää korjauskierroksen käynnistymisen.
- Labelien `agentti` ja `korjauskierros-<n>` muuttamista: triage-oikeudella labeleita voi lisätä ja poistaa ja
  siten muuttaa, kohdellaanko PR:ää agentin PR:nä ja montako kierrosta on jäljellä.
- Labelin `malli-<nimi>` vaihtamista: triage-oikeudella labelin voi vaihtaa, jolloin korjauskierros ajetaan toisella
  sallitulla mallilla. Opusta heikompaan malliin label ei vie: moottori ja `portti malli` hyväksyvät vain sallitut nimet.

## Mallin valinta

CTO:n mallipäätös 6.11.2026 on moottorissa deterministisenä funktiona (`portti/malli.py`, komento `portti malli`).
Sallitut nimet ja tunnisteet ovat yhdessä vakiossa `SALLITUT_MALLIT`; sen muutos on portti-repossa kova.

- Koodia, kortteja ja suunnitelmia ei kirjoiteta Sonnetilla eikä Haikulla.
- Oletusmalli on Opus (`claude-opus-5-5`).
- Fable (`claude-fable-5-1`) vain kahdella tavalla: kortissa on kortin mukana hyväksytty rivi `- Malli: fable`, tai
  ihminen käynnistää ajon käsin ja valitsee fablen.
- Mikä tahansa muu arvo estää ajon, ja syy kirjataan.
- Korjauskierros käyttää samaa mallia kuin alkuperäinen ajo. Tarkistaja on aina Opus, puhtaalla kontekstilla.

| Syöte | Tulos |
|---|---|
| kortissa ei ole riviä `- Malli:` | `claude-opus-5-5`, lähde oletus |
| `- Malli: opus`, `- Malli: claude-opus-5-5` tai `- Malli: opus (oletus; fable vain hyväksytyllä päätöksellä)` | `claude-opus-5-5`, lähde kortti |
| `- Malli: fable` tai `- Malli: claude-fable-5-1` | `claude-fable-5-1`, lähde kortti |
| `--kasin opus` tai `--kasin fable` | valittu malli, lähde käsin; voittaa kortin rivin |
| `--alkuperainen opus` tai `--alkuperainen fable` | alkuperäisen ajon malli, lähde alkuperäinen ajo; voittaa kortin rivin |
| sonnet, haiku, muu mallitunniste, vanhempi Opus, tyhjä arvo, kaksi riviä `- Malli:`, mallirivi väärässä muodossa, `--kasin` ja `--alkuperainen` yhdessä | exit-koodi 1, syy virhetulosteessa, ei mallitunnistetta |

Arvo luetaan kirjainkoosta ja ympäröivistä väleistä riippumatta, ja sulkuhuomautus rivin lopussa jätetään pois.
Kortin rivi tarkistetaan aina, kun se on olemassa: kortti, jossa on kielletty malli, ei käynnistä ajoa, vaikka
malli annettaisiin käsin. `portti malli --json` kertoo lisäksi mallin lähteen, tarkistajan mallin ja sallitut
tunnisteet, joista kortti-ajo lukitsee aliagenttien mallin ja tarkistaa ajon jälkeen käytetyt mallit.

Kortin tila- ja mallirivi ovat ylätason luettelorivejä (`- Malli: <arvo>`, myös `*` käy). Aidatun koodilohkon ja
HTML-kommentin sisältöä ei lueta: esimerkkinä tai kommentoituna oleva rivi ei hyväksy korttia eikä valitse mallia.
Jos avain on kortissa muussa muodossa (korostettuna, numeroituna, muulla luettelomerkillä, tehtävälistan ruudulla
tai sisennettynä alilistaan), ajo ei käynnisty: kielletty arvo ei ohitu muotoilun takia. Rivi ilman luettelomerkkiä
kesken tekstiä ei ole metarivi.

Mitä mallin valinta ei estä: `portti malli` päättää, millä mallilla ajo käynnistetään, mutta ei valvo ajoa.
Opus 5.5:n ja Fablen turvaluokitin voi siirtää ajon kesken vanhempaan Opus-malliin. Kortti-ajon jälkitarkistus
lukee ajon käyttämät mallit ja kaataa ajon näkyvästi, jos jokin niistä ei ole sallittu tunniste tai jos käytettyjä
malleja ei voida todentaa. Tieto tulee agentin runnerilta, joten tarkistus havaitsee siirtymät ja virheet, ei
tahallista väärennöstä.

## Kortti-ajo

Kortti-ajo on erillinen komponentti ([ARCHITECTURE.md](ARCHITECTURE.md)): `anthropics/claude-code-action`
pinnattuna commit-shaan (v1.0.268, julkaistu 2026-11-04, sha `c0949c50a78c1ec8ce2647db36629b870e715d0c`),
prompti `ajo/prompti.md`, kokoaja `ajo/kokoa_prompti.py` ja yhteenveto `ajo/ajon_yhteenveto.py` samasta shasta
kuin työnkulku. Moottori ei riipu siitä. Koodia kirjoittava ajo kulkee API-reittiä yrityksen API-avaimella, ei
kenenkään henkilökohtaisella tilillä.

### Kulku

1. CTO käynnistää kuluttajan `kortti-ajo.yml`:n käsin (Actions → Run workflow, syöte `kortti` ja halutessaan
   `malli_kasin`), tai ohjaus käynnistää sen korjauskierroksessa (`kortti`, `korjaa_pr` ja `alkuperainen_malli`).
   Ajoa ei ajasteta.
2. Ennen kuin kielimallia kutsutaan, työnkulku tarkistaa: budjettimuuttuja `PORTTI_AJO_BUDJETTI_USD` on asetettu
   (oletuslukua ei ole) ja budjetti, kierrosraja, slug ja PR-numero kelpaavat koko arvoltaan; kortin tila on
   `hyväksytty` oletushaarassa (`portti kortin-tila`); uudessa ajossa kortin haaraa `feature/<slug>` ei ole vielä
   olemassa; korjauskierroksessa haara on olemassa, PR on avoin samasta haarasta, sillä on label `agentti` ja sen
   ainoa `malli-`label vastaa syötettä `alkuperainen_malli`; ja `portti malli` palauttaa sallitun mallin.
   `malli_kasin` hyväksytään vain, kun tapahtuma on `workflow_dispatch` ja käynnistäjä on ihminen, ei botti eikä
   toinen työnkulku, eikä koskaan korjauskierroksessa. Jos jokin ehto ei täyty, ajo epäonnistuu näkyvästi.
3. Työnkulku tallentaa oletushaaran shan (main-vahti), varmistaa labelit `agentti` ja `malli-<nimi>` repoon ja kokoaa
   promptin: ohjeet, repon asennus- ja testikomennot sanatarkasti ja kuluttajan yhteinen sääntölohko sanatarkasti
   (`saantolohko_polku`, oletus `.portti/saannot.md`). Korjauskierroksessa työnkulku hakee PR:n kommentit, ja
   kokoaja liittää promptiin vain portin ja ohjauksen omat kommentit (kirjoittaja `github-actions[bot]` ja
   tunniste); muiden kommentoijien teksti ei päädy agentille. Portin kopio ja kommenttien raakadata poistetaan
   ennen agenttia.
4. Agentti ajetaan mallilla, joka tulee vain `portti malli` -askeleen tulosteesta (`--max-turns` ja
   `--max-budget-usd` tarkistetuista syötteistä). Se lukee CLAUDE.md:n ja kortin, luo haaran `feature/<slug>`
   päivitetystä oletushaarasta, vaihtaa kortin tilariviksi "työn alla" ensimmäisessä commitissa ja "PR" ennen PR:ää
   (syöte `kortin_tilarivit`; arvolla false feature-PR ei muuta korttia), ajaa kortin hyväksymiskriteerin ja repon
   komennot, käynnistää tarkistaja-aliagentin (Opus, puhdas konteksti: vain kortti, CLAUDE.md ja diff), pushaa ja
   avaa PR:n (ei luonnos) labeleilla `agentti` ja `malli-<nimi>` ilman katselmoijaa. Kuvauksessa on todistepaketti,
   päätöslista ja rivi "Ei ajettu oikealla datalla." Korjauskierroksessa: sama haara, portin ja ohjauksen
   kommentit ovat promptissa, agentti lukee kaatuneiden testien lokin (`gh run view --log-failed`), korjaa vain ne
   ja pushaa. PR:n muita kommentteja agentti ei lue.
5. Push tehdään Claude GitHub Appin tokenilla (OIDC-vaihto), joten PR käynnistää kuluttajan Testit- ja
   Portti-työnkulut; GITHUB_TOKENia ei käytetä pushiin (checkout ei tallenna sitä gitin asetuksiin). Ohjaus päättää
   jatkon.
6. Agentin jälkeen samassa jobissa ajetaan vain askeleita, joilla ei ole tokeneita: suoritustiedostosta poimitaan
   tulosviestin luvut ja mallikohtainen käyttö ja ne tallennetaan artefaktiksi. Agentin keskustelua ei tallenneta.
7. Jälkitarkistus ajetaan omassa jobissaan puhtaalla runnerilla (`if: always()`), koska agentti on voinut ajaa
   ensimmäisen jobin runnerilla mitä tahansa koodia. Se hakee PR:n API:sta vain repon omasta haarasta ja tarkistaa,
   että agentti todella ajoi (action lopettaa vihreänä ilman ajoa, jos App-tokenin vaihto hylkää työnkulun, joten
   tyhjä tulos kaataa ajon) ja että PR on olemassa. Jos uuden kortin PR:ltä puuttuu label `agentti` tai
   `malli-<nimi>`, se lisätään ja ajo merkitään epäonnistuneeksi.
8. Ajon yhteenveto kirjoitetaan työnkulun yhteenvetoon ja PR:n kuvauksen merkittyyn lohkoon: malli ja sen lähde,
   kortti, kesto, kierrokset, tokenit, kulu ja ajon käyttämät mallit. Jos ajo käytti mallia, joka ei ole sallittu
   tunniste, tai käytettyjä malleja ei voida todentaa, ajo kaatuu näkyvästi. Tarkistus havaitsee eikä estä.
9. Main-vahti vertaa oletushaaran shaa ennen agenttia ja ajon jälkeen: jos se muuttui, ajo kaatuu näkyvästi ja
   jättää PR:ään kommentin CTO:lle (`PORTTI_KATSELMOIJA_CTO`). Vahti havaitsee eikä estä.
10. Jos korjauskierros epäonnistui, peruuntui jonosta tai ei tuottanut uutta committia, jälkitarkistus vie PR:n
    CTO:lle (`portti ohjaus-ajo-epaonnistui`: labelit `katselmoitavaksi` ja `jumissa`, CTO katselmoijaksi, syy
    ohjauskommenttiin). Jos haaraan tuli uusi commit, ohjaus arvioi sen itse.

### Sallitut työkalut

Tiedostot: `Read`, `Glob`, `Grep`, `Edit`, `Write`, `MultiEdit`. Aliagentti: `Agent`, jolla on käytössä vain
työnkulun määrittelemä `tarkistaja`; sisäänrakennetut aliagentit on poistettu. Git vapailla argumenteilla:
`git status`, `git diff`, `git log`, `git show`, `git rev-parse`, `git add`, `git rm`, `git mv`, `git restore`,
`git commit`, `git fetch origin`, `git switch`. Täsmälleen omaan haaraan: `git push -u origin feature/<slug>`,
`git push origin feature/<slug>`, `git push --set-upstream origin feature/<slug>`,
`git pull --ff-only origin feature/<slug>`. gh: `gh run list`, `gh run view`; uudessa kortissa `gh pr create`,
korjauskierroksessa `gh pr comment <pr> --body-file` vain omaan PR:ään. PR:n tai sen kommenttien lukemiseen ei ole
työkalua. Repon asennus- ja testikomennot sanatarkasti syötteestä `testikomennot`, asennus ensin; lainaus-,
ohjaus- ja erotinmerkit sekä jokerimerkki `*` hylätään, koska ne rikkoisivat tai laajentaisivat työkalulistan.
Kielletyt:
`Read(./.git/**)`, `env`, `printenv`, `set`, `cat .git/config`, `git config`, `git remote`. Muu Bash on pois.

Mallin lukitus ajon sisällä: kaikki aliagentit pakotetaan tarkistajan malliin (`CLAUDE_CODE_SUBAGENT_MODEL` ja
`CLAUDE_CODE_SUBAGENT_MODEL_FORCE`), sisäänrakennetut aliagentit poistetaan
(`CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS`) ja aliakset `sonnet` ja `haiku` ohjataan samaan malliin
(`ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL`). Arvot annetaan sekä työnkulun ympäristössä
että actionin asetuksina.

Repon omia `.claude`-asetuksia ei ladata (`--setting-sources user`), joten lista on täsmälleen tämä eikä repon
asetus voi laajentaa sitä; CLAUDE.md luetaan promptin ohjeesta. API-avain poistetaan agentin aliprosessien
ympäristöstä parhaan kyvyn mukaan (`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`): se pienentää vuotoriskiä mutta ei poista
sitä. GitHub-tokenit säilyvät, jotta git ja gh toimivat. Agentin
toimija ohjauksen käynnistämässä kierroksessa on `github-actions[bot]`, joka on sallittu `allowed_bots`-listassa.

### Oikeudet

Agentin job: `contents: write`, `pull-requests: write`, `issues: write`, `id-token: write` (Claude GitHub Appin
tokenin OIDC-vaihto) ja `actions: read` (actionin `additional_permissions`: agentti lukee ajojen lokit). Salaisuus
`ANTHROPIC_API_KEY`. Jälkitarkistuksen job: `contents: read`, `pull-requests: write`, `issues: write` ja
`actions: read`, ei salaisuuksia. Yksi ajo kerrallaan repoa kohden (`concurrency`): jonossa voi olla yksi
odottava ajo, ja uudempi käynnistys korvaa odottavan. Aikakatkaisu syötteestä `aikakatkaisu_min` (oletus 60
minuuttia).

### Mitä kortti-ajo ei estä ilmaistasolla

- Pushia muualle kuin omaan haaraan: työkalulista sallii vain täsmälliset push-komennot omaan haaraan ja prompti
  kieltää muun, mutta tokenilla on `contents: write` koko repoon eikä haarasuojausta ole. Main-vahti havaitsee
  oletushaaran muutoksen jälkikäteen vertaamalla shaa ennen ja jälkeen; muutosta, joka palautetaan ennen ajon
  loppua, se ei havaitse. Estävä suoja on haarasuojaus.
- Salaisuuksien lukemista: agentti ajaa repon testit eli suorittaa itse kirjoittamaansa koodia. API-avain
  poistetaan aliprosessien ympäristöstä parhaan kyvyn mukaan, mutta sama koodi voi yrittää lukea sen agentin
  prosessista, eikä verkkoliikennettä ulos ole rajattu. Claude GitHub Appin token on aliprosessien käytössä (git
  ja gh tarvitsevat sen) ja originin osoitteessa. Token on lyhytikäinen ja rajattu tähän repoon;
  `show_full_output` on pois. Avaimen vuodon vaikutusta rajaavat Consolen workspacen kuukausiraja ja
  OIDC-federaatio pysyvän avaimen sijaan.
- Jälkitarkistuksen tietojen väärentämistä: ajon tulos (mallit, kesto, kulu) ja actionin lopputulos tulevat agentin
  runnerilta. Jälkitarkistus havaitsee virheet ja mallin siirtymät, ei tahallista väärennöstä. PR:n olemassaolo,
  head ja labelit luetaan API:sta.
- Budjetin ylitystä laskussa: `--max-budget-usd` on Claude Coden asiakaspuolen arvio. Consolen workspacen
  kuukausiraja on todellinen katto.
- Odottavan ajon korvautumista: jos kortti-ajoja käynnistetään useita toisen ollessa käynnissä, vain viimeisin jää
  jonoon. Korvattu korjauskierros ei käynnisty uudelleen, mutta PR ei jää tilaan korjauskierros: jälkitarkistus vie
  sen CTO:lle labelilla `jumissa`. Korvattu uuden kortin ajo näkyy peruttuna ajona.
- Mallin vaihtumista ajon aikana: turvaluokitin voi siirtää ajon vanhempaan Opus-malliin. Ajon yhteenveto havaitsee
  sen ja kaataa ajon, mutta PR on silloin jo avattu.
- Automaatiota, joka käyttää ihmisen tokenia: `malli_kasin` tarkistaa tapahtuman ja käynnistäjän tyypin. Ihmisen
  henkilökohtaisella tokenilla tehty käynnistys näyttää ihmisen tekemältä.
- Tarkistajan kontekstin rajausta rakenteellisesti: tarkistaja alkaa puhtaalta pöydältä eikä näe agentin
  keskustelua, mutta "vain kortti, CLAUDE.md ja diff" on ohje. Sillä on samat lukutyökalut kuin agentilla.

## Käyttöönotto kuluttajarepossa

Esimerkkirepo `esimerkki/tilaukset` on keksitty. Kaikki mallit pinnataan julkaistuun shaan: korvaa
`<PINNATTU_SHA>` portti-repon julkaisun täydellä commit-shalla. Ohjaus ja kortti-ajo hakevat moottorin ja
promptin samasta shasta (`job.workflow_sha`), joten pinnaus on yksi rivi per työnkulku.

1. Kopioi [mallit/portti.yml](mallit/portti.yml) tiedostoksi `.github/workflows/portti.yml` (nimi `Portti`),
   [mallit/portti-ohjaus.yml](mallit/portti-ohjaus.yml) tiedostoksi `.github/workflows/portti-ohjaus.yml` ja
   [mallit/kortti-ajo.yml](mallit/kortti-ajo.yml) tiedostoksi `.github/workflows/kortti-ajo.yml`. Testityönkulun
   nimen on oltava `Testit` ja tiedoston `testit.yml`, tai ohjauksen syötteet päivitetään. Kortti-ajon syötteeseen
   `testikomennot` kirjoitetaan repon asennus- ja testikomennot, asennus ensin, ja syötteellä `kortin_tilarivit`
   valitaan, päivittääkö agentti kortin tilarivin haarassa. Malleihin ei lisätä concurrency-ryhmää:
   uudelleenkäytettävät työnkulut sarjoittavat ajonsa itse. Kortti-ajoa ei ajasteta.
2. Lisää `.portti/saannot.md`: kuluttajan yhteinen sääntölohko, joka liitetään kortti-ajon promptiin sanatarkasti.
   Kortit ovat tiedostoja `kortit/<slug>.md`. Lisää kortin pohjaan rivit tiedostosta
   [mallit/kortin-pohja.md](mallit/kortin-pohja.md): tilarivi `- Tila:` ja mallirivi
   `- Malli: opus (oletus; fable vain hyväksytyllä päätöksellä)`. Kortti-ajo käynnistyy vain, kun tila on
   `hyväksytty` oletushaarassa, ja työ tehdään haaraan `feature/<slug>`.
3. Asenna Claude GitHub App (`https://github.com/apps/claude`) vain valituille repoille, ei koko organisaatioon.
4. Salaisuus `ANTHROPIC_API_KEY` repoon: yrityksen API-avain omasta Console-workspacesta, ei kenenkään
   henkilökohtainen tili. Vaihtoehto on OIDC-federaatio actionin syötteillä `anthropic_federation_rule_id` ja
   `anthropic_organization_id`, jolloin avainta ei tallenneta; se vaatii muutoksen kortti-ajon työnkulkuun. Aseta
   Consolen workspacelle kuukausiraja.
5. Muuttujat (Settings → Secrets and variables → Actions → Variables): `PORTTI_KATSELMOIJA_CTO` (GitHub-tunnus),
   `PORTTI_KATSELMOIJA_T1` (valinnainen; puuttuessa käytetään CTO:ta) ja `PORTTI_AJO_BUDJETTI_USD` (pakollinen;
   ilman sitä kortti-ajo ei käynnisty).
6. Forkin PR:t yksityisrepossa (Settings → Actions → General → Fork pull request workflows): "Run workflows from
   fork pull requests" ja "Send write tokens to workflows from fork pull requests"; salaisuuksia ei anneta forkeille.
   Ohjaus toimii forkin PR:ille ilman näitä, koska se ajetaan `workflow_run`-tapahtumasta, mutta Portti-kommentti
   PR-ajosta vaatii kirjoitustokenin.
7. Labelit `katselmoitavaksi`, `kova`, `jumissa`, `korjattava`, `liian-iso`, `tier-*` ja `korjauskierros-*` ohjaus
   luo itse. Labelit `agentti` ja `malli-<nimi>` luo kortti-ajo ennen agenttia; agentti asettaa ne PR:ää
   luodessaan. Jos ne puuttuvat, jälkitarkistus lisää ne ja merkitsee ajon epäonnistuneeksi.

## Tarkistetut GitHubin käytökset (4.11. ja 11.11.2026)

- `workflow_run` käynnistää ajon vain, jos työnkulkutiedosto on oletushaarassa; `GITHUB_SHA` ja `GITHUB_REF`
  ovat oletushaaran; ajo saa salaisuudet ja kirjoitusoikeudet, vaikka edeltävä ajo (forkin PR) ei saanut; ketjua
  ei voi jatkaa yli kolmen tason (dokumentti events-that-trigger-workflows).
- Forkin PR:n haku: `repos/{repo}/commits/{sha}/pulls` palauttaa tyhjän forkin PR:n head-commitille (kokeiltu
  julkisen repon kolmella forkki-PR:llä 11.11.2026). Ohjaus hakee PR:n siksi kutsulla
  `repos/{repo}/pulls?state=open&head=<omistaja>:<haara>` ja valitsee sen, jonka head-sha täsmää (sama koe: 3/3
  löytyi; toimii myös saman repon PR:lle). Tapahtuman `pull_requests`-taulukkoa ei käytetä.
- Ohjauksen lukuaskeleet (PR:n haku, työnkulkujen tila, muuttuneet polut, evidence-artefaktin lataus, edellinen
  päätös ja `portti ohjaa`) on ajettu paikallisesti tämän repon avointa PR:ää vasten 11.11.2026. Kirjoittavia
  askeleita ja itse työnkulkuja ei ole ajettu GitHubissa.
- concurrency: sama ryhmän nimi kutsuvan työnkulun tasolla ja kutsutun työnkulun jobissa lukkiutuu, joten ryhmät
  ovat vain uudelleenkäytettävien työnkulkujen jobeissa eivätkä malleissa. Ryhmässä on yksi käynnissä oleva ja yksi
  odottava ajo; uudempi korvaa odottavan. Ei varmistettu ajamalla. Sekään ei ole varmistettu, että
  jälkitarkistuksen `if: always()` -job ajetaan, kun agentin job peruuntuu jonosta.
- Kortti-ajon jälkitarkistus nojaa dokumentoituihin ominaisuuksiin, joita ei ole ajettu GitHubissa: jobien väliset
  tulosteet (`needs.<job>.outputs`) uudelleenkäytettävässä työnkulussa ja `gh run download` saman, vielä käynnissä
  olevan ajon artefaktille.
- claude-code-actionin esimerkki (`examples/claude.yml`, v1.0.268) käyttää oikeuksia `contents: write`,
  `pull-requests: write`, `issues: write`, `id-token: write` ja `actions: read`. Agentin jobin oikeuksia ei ole
  kavennettu sen alle; se, tarvitseeko action GITHUB_TOKENin kirjoitusoikeuksia App-tokenin rinnalla, selviää
  pilotissa.
- `workflow_dispatch` GITHUB_TOKENilla: GITHUB_TOKENin aiheuttamat tapahtumat eivät käynnistä uusia ajoja,
  poikkeuksina `workflow_dispatch` ja `repository_dispatch` (dokumentti GITHUB_TOKEN). Vaatii `actions: write`.
  Käynnistetyn ajon toimija on `github-actions[bot]`; kortti-ajo sallii sen `allowed_bots`-listassa, koska
  claude-code-action hylkää muut bottitoimijat.
- Artefakti toisesta ajosta: `gh run download <run-id> --name <artefakti> --dir <kansio>` tarvitsee `actions: read`
  ja purkaa yhden nimetyn artefaktin suoraan kansioon (gh:n ohje ja kuiva-ajo 11.11.2026).
- Forkin PR: `pull_request`-ajo saa vain lukuoikeudet eikä salaisuuksia GITHUB_TOKENia lukuun ottamatta; yksityisen
  repon forkkiajot vaativat repon asetukset (kohta 6 yllä).
- `job.workflow_sha` ja `job.workflow_repository`: lisätty job-kontekstiin huhtikuussa 2026 (actions/runner#2417
  suljettu 23.4.2026) ja dokumentoitu contexts-sivulla; uudelleenkäytettävän työnkulun jobissa ne osoittavat
  kutsutun työnkulun repoon ja shaan. Ne ovat käytettävissä askelten `env`-, `with`- ja `run`-avaimissa, eivät
  jobin `env`- tai `if`-avaimissa. Ohjaus ja kortti-ajo kaatuvat näkyvästi, jos ne puuttuvat.
- Uudelleenkäytettävä työnkulku kutsutaan muodossa `owner/repo/.github/workflows/tiedosto.yml@<sha>`; repon ja
  organisaation muuttujat (`vars`) ovat kutsutun työnkulun käytössä; oikeuksia voi vain supistaa; salaisuudet
  välitetään nimetysti.
- claude-code-action v1.0.268 (lähdekoodista): `workflow_dispatch` on tuettu tapahtuma; agent-tila tarkistaa
  toimijan (`allowed_bots`); `claude_args` tokenisoidaan shell-quotella ja työkalulista jaetaan pilkuista, joten
  `--allowedTools "..."` annetaan yhtenä merkkijonona; Bash on oletuksena pois ja sallitaan komennoittain;
  `--setting-sources` rajaa ladattavat asetukset; GITHUB_TOKEN ja GH_TOKEN asetetaan Claude GitHub Appin tokeniksi
  agentin prosessille, joten `gh` ja `git push` toimivat sillä; action poistaa checkoutin tallentaman tokenin gitin
  asetuksista ja asettaa originiin App-tokenin.
- Sama lähdekoodi: CI-työkalupalvelin `mcp__github_ci` asennetaan vain PR-tapahtumissa, ei `workflow_dispatch`-ajossa,
  joten agentti lukee lokit komennolla `gh run view`. Jos App-tokenin vaihto hylkää työnkulun, action lopettaa
  onnistuneena ilman ajoa; kortti-ajo tarkistaa siksi actionin tuloksen. App-tokenin vaihtoa uudelleenkäytettävän
  työnkulun sisältä ei ole varmistettu ajamalla.
- Claude Coden dokumentaatio: `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` poistaa tunnistetiedot (esimerkiksi
  `ANTHROPIC_API_KEY`) Bash-komentojen ja muiden aliprosessien ympäristöstä ja jättää GitHub-tokenit paikalleen;
  `--max-budget-usd` pysäyttää ajon asiakaspuolen kustannusarvion perusteella. claude-code-actionin
  tietoturvadokumentti (`docs/security.md`, v1.0.268) kuvaa siivouksen parhaan kyvyn mukaiseksi: se "reduces but
  does not eliminate prompt injection risk". Saman dokumentin mukaan Linux-runnerilla, jossa on bubblewrap,
  aliprosessit saavat lisäksi oman PID-nimiavaruuden.
- Claude Coden dokumentaatio, mallit (tarkistettu 11.11.2026): `--agents` ottaa aliagentin määrittelyn JSONina
  (kuvaus, prompti, työkalut, malli); aliagentti alkaa puhtaalla kontekstilla. `CLAUDE_CODE_SUBAGENT_MODEL` yhdessä
  muuttujan `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` kanssa ajaa jokaisen aliagentin annetulla mallilla, eikä agentti voi
  antaa mallia kutsussa. `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1` poistaa sisäänrakennetut aliagentit
  ei-interaktiivisessa ajossa. `ANTHROPIC_DEFAULT_SONNET_MODEL` ja `ANTHROPIC_DEFAULT_HAIKU_MODEL` määräävät, mihin
  aliakset `sonnet` ja `haiku` ratkeavat. Opus 5.5:n ja Fablen turvaluokitin voi ajaa pyynnön uudelleen vanhemmalla
  Opus-mallilla, ja istunto jatkuu sillä.
- claude-code-actionin lähdekoodi: syöte `settings` yhdistetään käyttäjätason asetuksiin, joiden `env`-lohko
  asetetaan ajon ympäristöön. Suoritustiedosto (`execution_file`) on JSON-lista viesteistä; tulosviestissä ovat
  kesto, kierrokset, kulu ja mallikohtainen käyttö. Mallikohtaisten kenttien nimet varmistuvat pilotissa; jos ne
  puuttuvat, yhteenveto kirjaa "ei tietoa" ja jälkitarkistus kaatuu, koska käytettyjä malleja ei voida todentaa.
- Kortti-ajon tarkistus ennen kielimallia, promptin kokoaminen ja ajon yhteenveto on ajettu paikallisesti
  keksityssä hakemistossa 11.11.2026: sallitut tapaukset menivät läpi, ja botti, Sonnet, hyväksymätön kortti,
  kortin kielletty malli ja olemassa oleva haara hylättiin.
- Katselmoinnin jälkeen muutetut askeleet on kuiva-ajettu samana päivänä vale-gh:lla: syötteiden tarkistus
  (monirivinen budjetti ja slug hylätään), korjauskierroksen portti (label `agentti`, mallilabelin ja syötteen
  vastaavuus), promptin kokoaminen kommenteilla, tulosviestin poiminta, jälkitarkistuksen askeleet ja
  epäonnistuneen korjauskierroksen vienti CTO:lle. Paikallinen bash on 3.2 ja runnerin 5.x.

## Pinnaus ja versiointi

Kuluttaja pinnaa actionin täyteen commit-sha:han, ei tagiin eikä haaraan.
Moottorin versio on tiedostossa `portti/version.py` (semver) ja se kirjoitetaan
jokaiseen evidenceen. Policyn skeeman rikkova muutos nostaa major-numeron,
uusi portti tai kenttä minorin, korjaus patchin. Sha:n vaihto on kuluttajarepon
PR, joka osuu kova-kategoriaan `portti_itse`.

## Kehitys

```bash
python3.11 -m pip install -e ".[dev]"
python -m mypy --strict portti ajo/kokoa_prompti.py ajo/ajon_yhteenveto.py
python -m pytest -q
PYTHONSAFEPATH=1 portti tarkista-tapaukset .portti/tapaukset.yml --lahde head
```

Moottori luetaan checkoutista (editable-asennus tai `PYTHONPATH`), koska
oletuspolicy on repon juuressa tiedostossa `defaults/policy.yml`.
