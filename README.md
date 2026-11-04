# Portti

Deterministinen katselmointiportti git-repoille. Yksi moottori, policy ja workflow
jokaisessa kuluttajarepossa. Ei LLM:ää, ei hyväksyntää: moottori laskee faktat,
soveltaa sääntöä ja kirjoittaa evidence-JSONin sekä yhden päivittyvän PR-kommentin.
Versiosta 0.4.0 alkaen [ohjaus](#ohjaus) päättää samoista faktoista deterministisesti, minne PR
menee (katselmoitavaksi, CTO:lle vai agentille korjattavaksi), ja erillinen [kortti-ajo](#kortti-ajo)
rakentaa hyväksytyn kortin PR:ksi ilman ihmisen istuntoa. Agenttien ja ihmisten PR:t kulkevat portin
ja ohjauksen kautta ennen ihmisen katselmointia.

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
- `portti ohjaa --head <sha> --testit success|failure|puuttuu --evidence <json> --polut <tiedosto>
  [--labelit a,b] [--forkki] [--paatos <json>]` päättää ohjauksen ilman verkkoa; tuloste on järjestetty
  päätös-JSON ilman tunnuksia. Puuttuva tai kelvoton evidence ei kaada komentoa vaan vie CTO:lle.
- `portti ohjaus-toteuta --paatos <json> --repo <omistaja/repo> --pr <n> [--katselmoija-cto <tunnus>]
  [--katselmoija-t1 <tunnus>] [--kortti-ajo kortti-ajo.yml --kortti <slug> --oletushaara main]` soveltaa
  päätöksen: labelit, katselmoijapyyntö, ohjauskommentti ja korjauskierroksen käynnistys.

## Ohjaus

Ohjaus päättää deterministisesti ja ilman kielimallia, meneekö PR katselmoitavaksi, CTO:lle vai takaisin
agentille. Se ajetaan kuluttajan oletushaaran työnkulkuna (`workflow_run`), jota PR ei voi muuttaa, eikä se
hae eikä suorita PR:n koodia. Moottori haetaan portti-reposta samasta shasta, johon kuluttaja on pinnannut
ohjaustyönkulun. Ohjaus on fail-closed: jos tieto puuttuu tai ei täsmää, PR menee aina CTO:lle.

### Kulku

1. Kuluttajan `portti-ohjaus.yml` käynnistyy, kun `Testit` tai `Portti` valmistuu, ja kutsuu
   `0zerosum/portti/.github/workflows/ohjaus.yml@<sha>`.
2. Ohjaus ratkaisee PR:n ajon head-shasta (forkin PR:lle API:sta, koska tapahtuman `pull_requests` on tyhjä),
   lukee molempien työnkulkujen lopputuloksen samalle headille (jos toinen on kesken, lopettaa ilman toimenpiteitä;
   sen valmistuminen ajaa ohjauksen uudelleen), lataa evidencen Portti-ajon artefaktista ja muuttuneet polut
   API:sta. Jos PR:n head on jo vaihtunut, ajo lopettaa: uudempi ajo ohjaa.
3. `portti ohjaa` kirjoittaa päätös-JSONin (artefakti `portti-paatos-pr<n>`), ja `portti ohjaus-toteuta`
   soveltaa sen: labelit (luo puuttuvat), katselmoijapyyntö, yksi päivittyvä ohjauskommentti ja korjauskierroksessa
   `workflow_dispatch` kuluttajan `kortti-ajo.yml`:lle syötteillä `kortti` (PR:n haara) ja `korjaa_pr`.

### Päätöstaulu

Syötteet: evidence (tai tieto, että se puuttuu), testityönkulun lopputulos PR:n headille (success, failure,
puuttuu; keskeytetty tai muu tulos on puuttuu), PR:n muuttuneet polut, PR:n labelit (`agentti` kertoo agentin
PR:n, `korjauskierros-<n>` laskee tehdyt kierrokset) ja forkkitieto. Rivit tarkistetaan järjestyksessä.

| Rivi | Ehto | Toimenpide | Labelit | Katselmoijan rooli |
|---|---|---|---|---|
| a | evidence puuttuu tai ei kelpaa; testien tila puuttuu; `evidence.head_sha` ≠ PR:n head; PR muuttaa polkuja `.github/**` tai `.portti/**` | CTO | `katselmoitavaksi`, `kova` | cto |
| b | verdict KOVA | CTO | `katselmoitavaksi`, `kova` | cto |
| c | testit failure tai verdict PUUTE (luonnos, konflikti): agentin PR ja kierroksia < 2 | korjauskierros | `korjauskierros-<n>` | – |
| c | sama, agentin PR ja kierroksia ≥ 2, tai forkin PR | CTO | `katselmoitavaksi`, `jumissa` | cto |
| c | sama, ihmisen PR | korjattava (kommentti tekijälle) | `korjattava` | – |
| d | verdict LIIAN-ISO: agentin PR ja kierroksia < 1 | korjauskierros, ohje "pienennä muutos kortin rajaukseen" | `korjauskierros-1` | – |
| d | verdict LIIAN-ISO, muuten | CTO | `katselmoitavaksi`, `liian-iso` | cto |
| e | verdict PEHMEÄ tai VAPAA ja testit success | katselmoitavaksi | `katselmoitavaksi`, `tier-<tier>` | T0–T1c → t1, muut → cto |
| – | mikä tahansa muu tila | CTO | `katselmoitavaksi`, `kova` | cto |

Jokainen toimenpide, joka vie PR:n ihmiselle (CTO, katselmoitavaksi), asettaa labelin `katselmoitavaksi`.
Korjauskierrokset luetaan labeleista `korjauskierros-<n>` (suurin n); niitä ei koskaan poisteta, koska ne ovat
laskuri. Tilalabelit `katselmoitavaksi`, `kova`, `jumissa`, `korjattava`, `liian-iso` ja `tier-*` poistetaan,
kun tila vaihtuu; `agentti` ja vieraat labelit jäävät. Forkin PR ei koskaan käynnistä korjauskierrosta.

Katselmoijien tunnukset eivät ole repossa: ne luetaan kuluttajarepon muuttujista `PORTTI_KATSELMOIJA_CTO` ja
`PORTTI_KATSELMOIJA_T1`. Jos T1 puuttuu, käytetään CTO:ta. Jos CTO puuttuu, katselmoijaa ei pyydetä ja
ohjauskommentti kertoo "katselmoija ei asetettu". PR:n tekijää ei pyydetä katselmoijaksi. Agentin PR avataan
ilman katselmoijaa; ohjaus asettaa sen.

Idempotenssi: toteutus lukee edellisen ohjauskommentin konedatan (head, toimenpide, kierros) ennen päivitystä.
Sama päätös samalle headille ei käynnistä toista kortti-ajoa, vaikka ohjaus ajettaisiin uudelleen (molemmat
työnkulut valmistuvat erikseen). concurrency on head-haaraa kohden ilman keskeytystä.

### Oikeudet

`contents: read`, `pull-requests: write`, `issues: write` (labelit) ja `actions: write` vain
`workflow_dispatch`-kutsua varten; se sisältää ajojen ja artefaktin lukuoikeuden. Salaisuuksia ei tarvita.

### Mitä ohjaus ei estä ilmaistasolla

- Mergeä: ei pakollisia checkejä eikä haarasuojausta. Ohjaus asettaa labelit ja katselmoijan; ihminen päättää.
- PR:ää, joka poistaa oman Portti-ajonsa tai vaihtaa shan: ohjaus vie sen CTO:lle (evidence puuttuu, eri head,
  `.github/**`), ei estä sitä.
- Katselmoijan ohittamista: pyyntö on pyyntö, ei pakko.

## Kortti-ajo

Kortti-ajo on erillinen komponentti ([ARCHITECTURE.md](ARCHITECTURE.md)): `anthropics/claude-code-action`
pinnattuna commit-shaan (v1.0.268, julkaistu 2026-11-04, sha `c0949c50a78c1ec8ce2647db36629b870e715d0c`),
prompti `ajo/prompti.md` ja kokoaja `ajo/kokoa_prompti.py` samasta shasta kuin työnkulku. Moottori ei riipu siitä.

### Kulku

1. CTO käynnistää kuluttajan `kortti-ajo.yml`:n (Actions → Run workflow, syöte `kortti`), tai ohjaus käynnistää
   sen korjauskierroksessa (`kortti` = PR:n haara, `korjaa_pr` = PR:n numero).
2. Ajo tarkistaa budjettimuuttujan `PORTTI_AJO_BUDJETTI_USD` (puuttuessa ajo ei käynnisty; oletuslukua ei ole),
   syötteet, hakee kuluttajarepon oletushaaran ja portin pinnatusta shasta, tallentaa oletushaaran shan
   (main-vahti), tarkistaa että `kortit/<slug>.md` ja sääntölohko ovat olemassa, ja kokoaa promptin: ohjeet, repon
   testikomennot sanatarkasti ja kuluttajan yhteinen sääntölohko sanatarkasti (`saantolohko_polku`, oletus
   `.portti/saannot.md`).
3. Agentti (`malli`, oletus `claude-opus-5-5`; `--max-turns` syötteestä `max_turns`; `--max-budget-usd`
   budjettimuuttujasta) lukee CLAUDE.md:n ja kortin, varmistaa että kortin tila on hyväksytty (muuten lopettaa ja
   raportoi), työskentelee haarassa `<slug>` päivitetystä oletushaarasta, ajaa repon testit, pushaa ja avaa PR:n
   (ei luonnos) labelilla `agentti` ilman katselmoijaa; kuvauksessa todistepaketti ja päätöslista.
   Korjauskierroksessa: sama haara, lukee portin ja ohjauksen kommentit sekä kaatuneiden testien lokit, korjaa vain
   ne ja pushaa.
4. Push tehdään Claude GitHub Appin tokenilla (OIDC-vaihto), joten PR käynnistää kuluttajan Testit- ja
   Portti-työnkulut; GITHUB_TOKENia ei käytetä pushiin. Ohjaus päättää jatkon.
5. Main-vahti vertaa oletushaaran shaa ajon jälkeen (`if: always()`): jos se muuttui, ajo kaatuu näkyvästi ja
   jättää PR:ään kommentin CTO:lle (`PORTTI_KATSELMOIJA_CTO`). Vahti havaitsee eikä estä.

### Sallitut työkalut

Tiedostot: `Read`, `Glob`, `Grep`, `Edit`, `Write`, `MultiEdit`. CI-lokit: `mcp__github_ci` (vaatii `actions: read`).
Git vapailla argumenteilla: `git status`, `git diff`, `git log`, `git show`, `git rev-parse`, `git add`,
`git commit`, `git fetch origin`, `git switch`. Täsmälleen omaan haaraan: `git push -u origin <slug>`,
`git push origin <slug>`, `git push --set-upstream origin <slug>`, `git pull --ff-only origin <slug>`.
gh: `gh pr view`, `gh pr list`, `gh pr create`, `gh pr comment`. Repon testikomennot sanatarkasti syötteestä
`testikomennot` (ei lainaus- eikä ohjausmerkkejä). Kielletyt: `Read(./.git/**)`, `env`, `printenv`, `set`,
`cat .git/config`, `git config`, `git remote`. Muu Bash on pois. Agentin toimija ohjauksen käynnistämässä
kierroksessa on `github-actions[bot]`, joka on sallittu `allowed_bots`-listassa.

### Oikeudet

`contents: write`, `pull-requests: write`, `issues: write`, `id-token: write` (Claude GitHub Appin tokenin
OIDC-vaihto) ja `actions: read` (lokit). Salaisuus `ANTHROPIC_API_KEY`. Yksi ajo kerrallaan repoa kohden
(`concurrency`), aikakatkaisu syötteestä `aikakatkaisu_min` (oletus 60 minuuttia).

### Mitä kortti-ajo ei estä ilmaistasolla

- Pushia muualle kuin omaan haaraan: työkalulista sallii vain täsmälliset push-komennot omaan haaraan ja prompti
  kieltää muun, mutta tokenilla on `contents: write` koko repoon eikä haarasuojausta ole. Main-vahti havaitsee
  oletushaaran muutoksen jälkikäteen.
- Salaisuuksien päätymistä tulosteisiin täysin: kielletyt työkalut ja prompti rajaavat, `show_full_output` on pois,
  mutta `Read` ja `Grep` muihin polkuihin ovat sallittuja.
- Budjetin ylitystä laskussa: `--max-budget-usd` on Claude Coden asiakaspuolen arvio. Consolen workspacen
  kuukausiraja on todellinen katto.

## Käyttöönotto kuluttajarepossa

Esimerkkirepo `esimerkki/tilaukset` on keksitty. Kaikki mallit pinnataan julkaistuun shaan: korvaa
`<PINNATTU_SHA>` portti-repon julkaisun täydellä commit-shalla. Ohjaus ja kortti-ajo hakevat moottorin ja
promptin samasta shasta (`job.workflow_sha`), joten pinnaus on yksi rivi per työnkulku.

1. Kopioi [mallit/portti.yml](mallit/portti.yml) tiedostoksi `.github/workflows/portti.yml` (nimi `Portti`),
   [mallit/portti-ohjaus.yml](mallit/portti-ohjaus.yml) tiedostoksi `.github/workflows/portti-ohjaus.yml` ja
   [mallit/kortti-ajo.yml](mallit/kortti-ajo.yml) tiedostoksi `.github/workflows/kortti-ajo.yml`. Testityönkulun
   nimen on oltava `Testit` ja tiedoston `testit.yml`, tai ohjauksen syötteet päivitetään.
2. Lisää `.portti/saannot.md`: kuluttajan yhteinen sääntölohko, joka liitetään kortti-ajon promptiin sanatarkasti.
   Kortit ovat tiedostoja `kortit/<slug>.md`, joissa on rivi `tila: hyväksytty`, kun CTO on hyväksynyt kortin.
3. Asenna Claude GitHub App (`https://github.com/apps/claude`) vain valituille repoille, ei koko organisaatioon.
4. Salaisuus `ANTHROPIC_API_KEY` repoon (yrityksen avain). Vaihtoehto on OIDC-federaatio actionin syötteillä
   `anthropic_federation_rule_id` ja `anthropic_organization_id`, jolloin avainta ei tallenneta; se vaatii muutoksen
   kortti-ajon työnkulkuun. Aseta Consolen workspacelle kuukausiraja.
5. Muuttujat (Settings → Secrets and variables → Actions → Variables): `PORTTI_KATSELMOIJA_CTO` (GitHub-tunnus),
   `PORTTI_KATSELMOIJA_T1` (valinnainen; puuttuessa käytetään CTO:ta) ja `PORTTI_AJO_BUDJETTI_USD` (pakollinen;
   ilman sitä kortti-ajo ei käynnisty).
6. Forkin PR:t yksityisrepossa (Settings → Actions → General → Fork pull request workflows): "Run workflows from
   fork pull requests" ja "Send write tokens to workflows from fork pull requests"; salaisuuksia ei anneta forkeille.
   Ohjaus toimii forkin PR:ille ilman näitä, koska se ajetaan `workflow_run`-tapahtumasta, mutta Portti-kommentti
   PR-ajosta vaatii kirjoitustokenin.
7. Labelit `katselmoitavaksi`, `kova`, `jumissa`, `korjattava`, `liian-iso`, `tier-*` ja `korjauskierros-*` ohjaus
   luo itse; `agentti`-labelin agentti asettaa PR:ää luodessaan (ohjaus luo senkin tarvittaessa).

## Tarkistetut GitHubin käytökset (4.11.2026)

- `workflow_run` käynnistää ajon vain, jos työnkulkutiedosto on oletushaarassa; `GITHUB_SHA` ja `GITHUB_REF`
  ovat oletushaaran; ajo saa salaisuudet ja kirjoitusoikeudet, vaikka edeltävä ajo (forkin PR) ei saanut; ketjua
  ei voi jatkaa yli kolmen tason (dokumentti events-that-trigger-workflows). Tapahtuman `pull_requests`-taulukko on
  tyhjä forkin PR:lle, joten ohjaus hakee PR:n head-shan perusteella (`repos/{repo}/commits/{sha}/pulls`, joka
  palauttaa avoimet PR:t, kun commit ei ole oletushaarassa). Tyhjän taulukon käytös perustuu aiempiin havaintoihin,
  ei dokumentaation sivuun tässä tarkistuksessa; se vahvistetaan synteettisellä forkin PR:llä.
- `workflow_dispatch` GITHUB_TOKENilla: GITHUB_TOKENin aiheuttamat tapahtumat eivät käynnistä uusia ajoja,
  poikkeuksina `workflow_dispatch` ja `repository_dispatch` (dokumentti GITHUB_TOKEN). Vaatii `actions: write`.
  Käynnistetyn ajon toimija on `github-actions[bot]`; kortti-ajo sallii sen `allowed_bots`-listassa, koska
  claude-code-action hylkää muut bottitoimijat.
- Artefakti toisesta ajosta: `gh run download <run-id> --name <artefakti>` tai `actions/download-artifact` syötteillä
  `run-id` ja `github-token` tarvitsee `actions: read`.
- Forkin PR: `pull_request`-ajo saa vain lukuoikeudet eikä salaisuuksia GITHUB_TOKENia lukuun ottamatta; yksityisen
  repon forkkiajot vaativat repon asetukset (kohta 6 yllä).
- `job.workflow_sha` ja `job.workflow_repository`: lisätty job-kontekstiin huhtikuussa 2026 (actions/runner#2417
  suljettu 23.4.2026); uudelleenkäytettävän työnkulun jobissa ne osoittavat kutsutun työnkulun repoon ja shaan.
  Ohjaus ja kortti-ajo kaatuvat näkyvästi, jos ne puuttuvat.
- Uudelleenkäytettävä työnkulku kutsutaan muodossa `owner/repo/.github/workflows/tiedosto.yml@<sha>`; repon ja
  organisaation muuttujat (`vars`) ovat kutsutun työnkulun käytössä; oikeuksia voi vain supistaa; salaisuudet
  välitetään nimetysti.
- claude-code-action v1.0.268 (lähdekoodista): `workflow_dispatch` on tuettu tapahtuma; agent-tila tarkistaa
  toimijan (`allowed_bots`); `claude_args` tokenisoidaan shell-quotella, joten `--allowedTools "..."` annetaan yhtenä
  merkkijonona; Bash on oletuksena pois ja sallitaan komennoittain; GITHUB_TOKEN ja GH_TOKEN asetetaan Claude GitHub
  Appin tokeniksi agentin prosessille, joten `gh` ja `git push` toimivat sillä; `mcp__github_ci` vaatii
  `actions: read` ja `additional_permissions`.

## Pinnaus ja versiointi

Kuluttaja pinnaa actionin täyteen commit-sha:han, ei tagiin eikä haaraan.
Moottorin versio on tiedostossa `portti/version.py` (semver) ja se kirjoitetaan
jokaiseen evidenceen. Policyn skeeman rikkova muutos nostaa major-numeron,
uusi portti tai kenttä minorin, korjaus patchin. Sha:n vaihto on kuluttajarepon
PR, joka osuu kova-kategoriaan `portti_itse`.

## Kehitys

```bash
python3.11 -m pip install -e ".[dev]"
python -m mypy --strict portti ajo/kokoa_prompti.py
python -m pytest -q
PYTHONSAFEPATH=1 portti tarkista-tapaukset .portti/tapaukset.yml --lahde head
```

Moottori luetaan checkoutista (editable-asennus tai `PYTHONPATH`), koska
oletuspolicy on repon juuressa tiedostossa `defaults/policy.yml`.
