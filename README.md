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
- `portti ohjaus-edellinen --repo <omistaja/repo> --pr <n> [--tuloste <json>]` lukee PR:n edellisen
  ohjauspäätöksen ohjauskommentin konedatasta (head, toimenpide, kierros); `null`, jos päätöstä ei ole.
- `portti ohjaa --head <sha> --testit success|failure|puuttuu --evidence <json> --polut <tiedosto>
  [--labelit a,b] [--forkki] [--edellinen <json>] [--paatos <json>]` päättää ohjauksen ilman verkkoa; tuloste on
  järjestetty päätös-JSON ilman tunnuksia. Puuttuva tai kelvoton evidence ei kaada komentoa vaan vie CTO:lle.
  `--edellinen` estää saman korjauskierroksen käynnistämisen kahdesti samalle headille.
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
2. Ohjaus hakee PR:n head-haaran omistajan, haaran ja shan perusteella (`pulls?head=<omistaja>:<haara>`, valinta
   shan mukaan; sama haku toimii forkin PR:lle), lukee molempien työnkulkujen lopputuloksen samalle headille (jos
   toinen on kesken, lopettaa ilman toimenpiteitä; sen valmistuminen ajaa ohjauksen uudelleen), lataa evidencen
   Portti-ajon artefaktista ja muuttuneet polut API:sta. Jos PR:n head on jo vaihtunut, ajo lopettaa: uudempi ajo
   ohjaa.
3. `portti ohjaus-edellinen` lukee edellisen päätöksen ohjauskommentista, `portti ohjaa` kirjoittaa päätös-JSONin
   (artefakti `portti-paatos-pr<n>`), ja `portti ohjaus-toteuta` soveltaa sen: labelit (luo puuttuvat),
   katselmoijapyyntö, yksi päivittyvä ohjauskommentti ja uudessa korjauskierroksessa `workflow_dispatch` kuluttajan
   `kortti-ajo.yml`:lle syötteillä `kortti` (PR:n haara) ja `korjaa_pr`.

### Päätöstaulu

Syötteet: evidence (tai tieto, että se puuttuu), testityönkulun lopputulos PR:n headille (success, failure,
puuttuu; keskeytetty tai muu tulos on puuttuu), PR:n muuttuneet polut, PR:n labelit (`agentti` kertoo agentin
PR:n, `korjauskierros-<n>` laskee tehdyt kierrokset), forkkitieto ja edellinen ohjauspäätös (head, toimenpide,
kierros). Rivit tarkistetaan järjestyksessä.

| Rivi | Ehto | Toimenpide | Labelit | Katselmoijan rooli |
|---|---|---|---|---|
| a | evidence puuttuu tai ei kelpaa; testien tila puuttuu; `evidence.head_sha` ≠ PR:n head; PR muuttaa polkuja `.github/**` tai `.portti/**` | CTO | `katselmoitavaksi`, `kova` | cto |
| b | verdict KOVA | CTO | `katselmoitavaksi`, `kova` | cto |
| c | testit failure tai verdict PUUTE (luonnos, konflikti): ihmisen PR | korjattava (kommentti tekijälle) | `korjattava` | – |
| c | sama, agentin PR forkista | CTO | `katselmoitavaksi`, `jumissa` | cto |
| c | sama, agentin PR, ja edellinen päätös käynnisti kierroksen n tälle samalle headille | korjauskierros n jatkuu, uutta ajoa ei käynnistetä | `korjauskierros-<n>` | – |
| c | sama, agentin PR ja kierroksia < 2 | uusi korjauskierros, kortti-ajo käynnistetään | `korjauskierros-<n>` | – |
| c | sama, agentin PR ja kierroksia ≥ 2 | CTO | `katselmoitavaksi`, `jumissa` | cto |
| d | verdict LIIAN-ISO: ihmisen PR, tai agentin PR forkista (`jumissa`) | CTO | `katselmoitavaksi`, `liian-iso` | cto |
| d | sama, agentin PR, ja edellinen päätös käynnisti kierroksen n tälle samalle headille | korjauskierros n jatkuu, uutta ajoa ei käynnistetä | `korjauskierros-<n>` | – |
| d | sama, agentin PR ja kierroksia < 1 | uusi korjauskierros, ohje "pienennä muutos kortin rajaukseen" | `korjauskierros-1` | – |
| d | sama, agentin PR ja kierroksia ≥ 1 | CTO | `katselmoitavaksi`, `liian-iso` | cto |
| e | verdict PEHMEÄ tai VAPAA ja testit success | katselmoitavaksi | `katselmoitavaksi`, `tier-<tier>` | T0–T1c → t1, muut → cto |
| – | mikä tahansa muu tila, myös tuntematon tier | CTO | `katselmoitavaksi`, `kova` | cto |

Jokainen toimenpide, joka vie PR:n ihmiselle (CTO, katselmoitavaksi), asettaa labelin `katselmoitavaksi`.
Korjauskierrokset luetaan labeleista `korjauskierros-<n>` (suurin n); niitä ei koskaan poisteta, koska ne ovat
laskuri. Tilalabelit `katselmoitavaksi`, `kova`, `jumissa`, `korjattava`, `liian-iso` ja `tier-*` poistetaan,
kun tila vaihtuu; `agentti` ja vieraat labelit jäävät. Forkin PR ei koskaan käynnistä korjauskierrosta.

Katselmoijien tunnukset eivät ole repossa: ne luetaan kuluttajarepon muuttujista `PORTTI_KATSELMOIJA_CTO` ja
`PORTTI_KATSELMOIJA_T1`. Jos T1 puuttuu, käytetään CTO:ta. Jos CTO puuttuu, katselmoijaa ei pyydetä ja
ohjauskommentti kertoo "katselmoija ei asetettu". PR:n tekijää ei pyydetä katselmoijaksi. Agentin PR avataan
ilman katselmoijaa; ohjaus asettaa sen.

Idempotenssi: työnkulku lukee edellisen päätöksen ohjauskommentin konedatasta (head, toimenpide, kierros) ja antaa
sen moottorille. Jos edellinen päätös käynnisti korjauskierroksen tälle samalle headille, uusi päätös toistaa saman
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
- Ohjauskommentin väärentämistä: edellinen päätös luetaan PR:n kommentista, joten kommentointioikeudella voi estää
  korjauskierroksen käynnistymisen tai CTO:lle siirtymisen (PR jää tilaan korjauskierros). Katselmoitavaksi-päätökseen
  tai katselmoijan rooliin edellinen päätös ei vaikuta.

## Kortti-ajo

Kortti-ajo on erillinen komponentti ([ARCHITECTURE.md](ARCHITECTURE.md)): `anthropics/claude-code-action`
pinnattuna commit-shaan (v1.0.268, julkaistu 2026-11-04, sha `c0949c50a78c1ec8ce2647db36629b870e715d0c`),
prompti `ajo/prompti.md` ja kokoaja `ajo/kokoa_prompti.py` samasta shasta kuin työnkulku. Moottori ei riipu siitä.

### Kulku

1. CTO käynnistää kuluttajan `kortti-ajo.yml`:n (Actions → Run workflow, syöte `kortti`), tai ohjaus käynnistää
   sen korjauskierroksessa (`kortti` = PR:n haara, `korjaa_pr` = PR:n numero).
2. Ajo tarkistaa budjettimuuttujan `PORTTI_AJO_BUDJETTI_USD` (puuttuessa ajo ei käynnisty; oletuslukua ei ole) ja
   syötteet, hakee kuluttajarepon oletushaaran ja portin pinnatusta shasta, tallentaa oletushaaran shan
   (main-vahti), varmistaa että label `agentti` on repossa, tarkistaa että `kortit/<slug>.md` ja sääntölohko ovat
   olemassa, ja kokoaa promptin: ohjeet, repon asennus- ja testikomennot sanatarkasti ja kuluttajan yhteinen
   sääntölohko sanatarkasti (`saantolohko_polku`, oletus `.portti/saannot.md`). Portin kopio poistetaan työtilasta
   ennen agenttia, jotta se ei päädy agentin committiin.
3. Agentti (`malli`, oletus `claude-opus-5-5`; `--max-turns` syötteestä `max_turns`; `--max-budget-usd`
   budjettimuuttujasta) lukee CLAUDE.md:n ja kortin, varmistaa kortin hyväksynnän repon omien sääntöjen mukaan
   (muuten lopettaa ja raportoi), työskentelee haarassa `<slug>` päivitetystä oletushaarasta, ajaa repon komennot,
   pushaa ja avaa PR:n (ei luonnos) labelilla `agentti` ilman katselmoijaa; kuvauksessa todistepaketti ja
   päätöslista. Korjauskierroksessa: sama haara, lukee portin ja ohjauksen kommentit sekä kaatuneiden testien lokin
   (`gh run view --log-failed`), korjaa vain ne ja pushaa.
4. Push tehdään Claude GitHub Appin tokenilla (OIDC-vaihto), joten PR käynnistää kuluttajan Testit- ja
   Portti-työnkulut; GITHUB_TOKENia ei käytetä pushiin (checkout ei tallenna sitä gitin asetuksiin). Ohjaus päättää
   jatkon.
5. Ajon jälkeen työnkulku tarkistaa, että agentti todella ajoi: action lopettaa vihreänä ilman ajoa, jos App-tokenin
   vaihto hylkää työnkulun, joten tyhjä tulos kaataa ajon. Lisäksi se varmistaa labelin `agentti` haaran avoimeen
   PR:ään.
6. Main-vahti vertaa oletushaaran shaa ajon jälkeen (`if: always()`): jos se muuttui, ajo kaatuu näkyvästi ja
   jättää PR:ään kommentin CTO:lle (`PORTTI_KATSELMOIJA_CTO`). Vahti havaitsee eikä estä.

### Sallitut työkalut

Tiedostot: `Read`, `Glob`, `Grep`, `Edit`, `Write`, `MultiEdit`. Git vapailla argumenteilla: `git status`,
`git diff`, `git log`, `git show`, `git rev-parse`, `git add`, `git rm`, `git mv`, `git restore`, `git commit`,
`git fetch origin`, `git switch`. Täsmälleen omaan haaraan: `git push -u origin <slug>`, `git push origin <slug>`,
`git push --set-upstream origin <slug>`, `git pull --ff-only origin <slug>`. gh: `gh pr view`, `gh pr list`,
`gh pr create`, `gh pr comment`, `gh run list`, `gh run view`. Repon asennus- ja testikomennot sanatarkasti
syötteestä `testikomennot`, asennus ensin; lainaus-, ohjaus- ja erotinmerkit hylätään, koska pilkku ja sulut
rikkoisivat työkalulistan. Kielletyt: `Read(./.git/**)`, `env`, `printenv`, `set`, `cat .git/config`, `git config`,
`git remote`. Muu Bash on pois.

Repon omia `.claude`-asetuksia ei ladata (`--setting-sources user`), joten lista on täsmälleen tämä eikä repon
asetus voi laajentaa sitä; CLAUDE.md luetaan promptin ohjeesta. Agentin aliprosessit eivät saa API-avainta
ympäristöönsä (`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`); GitHub-tokenit säilyvät, jotta git ja gh toimivat. Agentin
toimija ohjauksen käynnistämässä kierroksessa on `github-actions[bot]`, joka on sallittu `allowed_bots`-listassa.

### Oikeudet

`contents: write`, `pull-requests: write`, `issues: write`, `id-token: write` (Claude GitHub Appin tokenin
OIDC-vaihto) ja `actions: read` (actionin `additional_permissions`: agentti lukee ajojen lokit). Salaisuus
`ANTHROPIC_API_KEY`. Yksi ajo kerrallaan repoa kohden (`concurrency`): jonossa voi olla yksi odottava ajo, ja
uudempi käynnistys korvaa odottavan. Aikakatkaisu syötteestä `aikakatkaisu_min` (oletus 60 minuuttia).

### Mitä kortti-ajo ei estä ilmaistasolla

- Pushia muualle kuin omaan haaraan: työkalulista sallii vain täsmälliset push-komennot omaan haaraan ja prompti
  kieltää muun, mutta tokenilla on `contents: write` koko repoon eikä haarasuojausta ole. Main-vahti havaitsee
  oletushaaran muutoksen jälkikäteen.
- Salaisuuksien lukemista kokonaan: agentti ajaa repon testit eli suorittaa itse kirjoittamaansa koodia. API-avain
  on poistettu aliprosessien ympäristöstä, mutta Claude GitHub Appin token on niiden käytössä (git ja gh tarvitsevat
  sen) ja originin osoitteessa. Token on lyhytikäinen ja rajattu tähän repoon; `show_full_output` on pois.
- Budjetin ylitystä laskussa: `--max-budget-usd` on Claude Coden asiakaspuolen arvio. Consolen workspacen
  kuukausiraja on todellinen katto.
- Odottavan ajon korvautumista: jos kortti-ajoja käynnistetään useita toisen ollessa käynnissä, vain viimeisin jää
  jonoon. Korvattu korjauskierros ei käynnisty uudelleen samalle headille; PR jää tilaan korjauskierros, kunnes
  haaraan tulee uusi commit tai CTO käynnistää ajon käsin.

## Käyttöönotto kuluttajarepossa

Esimerkkirepo `esimerkki/tilaukset` on keksitty. Kaikki mallit pinnataan julkaistuun shaan: korvaa
`<PINNATTU_SHA>` portti-repon julkaisun täydellä commit-shalla. Ohjaus ja kortti-ajo hakevat moottorin ja
promptin samasta shasta (`job.workflow_sha`), joten pinnaus on yksi rivi per työnkulku.

1. Kopioi [mallit/portti.yml](mallit/portti.yml) tiedostoksi `.github/workflows/portti.yml` (nimi `Portti`),
   [mallit/portti-ohjaus.yml](mallit/portti-ohjaus.yml) tiedostoksi `.github/workflows/portti-ohjaus.yml` ja
   [mallit/kortti-ajo.yml](mallit/kortti-ajo.yml) tiedostoksi `.github/workflows/kortti-ajo.yml`. Testityönkulun
   nimen on oltava `Testit` ja tiedoston `testit.yml`, tai ohjauksen syötteet päivitetään. Kortti-ajon syötteeseen
   `testikomennot` kirjoitetaan repon asennus- ja testikomennot, asennus ensin. Malleihin ei lisätä
   concurrency-ryhmää: uudelleenkäytettävät työnkulut sarjoittavat ajonsa itse.
2. Lisää `.portti/saannot.md`: kuluttajan yhteinen sääntölohko, joka liitetään kortti-ajon promptiin sanatarkasti.
   Kortit ovat tiedostoja `kortit/<slug>.md`. Agentti varmistaa kortin hyväksynnän repon omien sääntöjen mukaan,
   joten CLAUDE.md:n on kerrottava, miten hyväksyntä merkitään (esimerkiksi tilarivi kortissa tai hyväksyntäcommit).
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
   luo itse. Labelin `agentti` luo kortti-ajo ennen agenttia; agentti asettaa sen PR:ää luodessaan, ja kortti-ajo
   varmistaa sen ajon lopuksi.

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
  odottava ajo; uudempi korvaa odottavan. Ei varmistettu ajamalla.
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
  `--max-budget-usd` pysäyttää ajon asiakaspuolen kustannusarvion perusteella.

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
