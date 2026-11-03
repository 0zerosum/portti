# Portti

Deterministinen katselmointiportti git-repoille. Yksi moottori, policy ja workflow
jokaisessa kuluttajarepossa. Ei LLM:ää, ei hyväksyntää: moottori laskee faktat,
soveltaa sääntöä ja kirjoittaa evidence-JSONin sekä yhden päivittyvän PR-kommentin.

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
kehitys-PR:ille. Jos basessa ei ole policyä, enforce kaatuu näkyvästi ja shadow lukee
headista merkinnällä kommentissa. Enforce- ja shadow-ajo kirjoittavat kumpikin oman
kommenttinsa.

Enforce-tilassa estävä verdict tekee checkistä punaisen. Check on neuvoa-antava:
Free-tason yksityisrepossa ei ole pakollisia checkejä eikä branch protectionia, joten
GitHub ei estä mergeä, vaan katselmoija päättää sen punaisen checkin ja kommentin
perusteella. Moottori ei oleta näitä asetuksia mistään tasosta riippumatta.

Workflow ajetaan `pull_request`-tapahtumalla, joten workflow-tiedosto tulee PR:n
headista. PR voi siis poistaa Portti-ajon, vaihtaa moottorin shan tai asettaa
`policy_lahde: head`; moottori ei voi sitä estää. Nämä polut (`.github/**` ja
`.github/workflows/portti.yml`) ovat oletuksen kova-kategorioissa `ci` ja `portti_itse`,
ja `portti shadow-raportti` näyttää jälkikäteen PR:t, joista portin kommentti puuttuu.
Katselmoija tarkistaa, että check on ajettu ja kommentti on PR:n headista.

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

## Pinnaus ja versiointi

Kuluttaja pinnaa actionin täyteen commit-sha:han, ei tagiin eikä haaraan.
Moottorin versio on tiedostossa `portti/version.py` (semver) ja se kirjoitetaan
jokaiseen evidenceen. Policyn skeeman rikkova muutos nostaa major-numeron,
uusi portti tai kenttä minorin, korjaus patchin. Sha:n vaihto on kuluttajarepon
PR, joka osuu kova-kategoriaan `portti_itse`.

## Kehitys

```bash
python3.11 -m pip install -e ".[dev]"
python -m mypy --strict portti
python -m pytest -q
```

Moottori luetaan checkoutista (editable-asennus tai `PYTHONPATH`), koska
oletuspolicy on repon juuressa tiedostossa `defaults/policy.yml`.
