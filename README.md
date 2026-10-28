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
| `tapaukset_polku` | `.portti/tapaukset.yml` | regressiotapaukset; ajetaan, jos tiedosto on olemassa |
| `tila` | `shadow` | `shadow` lukee PR:n policyn; `enforce` lukee base-haaran policyn, mutta ei vielä estä |
| `policy_lahde` | `auto` | `head`, `base` tai `auto` (shadow → head, enforce → base) |
| `github_token` | – | PR:n tilan luku ja kommentin kirjoitus |
| `python_versio` | `3.11` | moottorin tulkki |

Shadow-tilassa action ei hyväksy, ei pyydä muutoksia eikä palauta verdictistä
estävää exit-koodia. Evidence ladataan artefaktiksi `portti-evidence-pr<numero>`.
Regressiotapausten poikkeama sen sijaan kaataa askeleen, kuten rikkoutunut testi.
Kaikki Python-askeleet ajetaan `PYTHONSAFEPATH=1`, jotta PR:n checkoutin tiedostot
eivät varjosta moottorin moduuleja.

## Enforce-valmius

Shadow-tilassa PR:n oma policy ohjaa ajoa, joten PR voisi muuttaa sääntöjä, joilla se
arvioidaan. Enforce-tilassa (tai `policy_lahde: base`) policy ja tapaukset luetaan
base-haaran versiosta (`git show <base-sha>:.portti/policy.yml`). Jos basessa ei ole
policyä, enforce kaatuu näkyvästi ja shadow lukee headista merkinnällä kommentissa.
Enforce- ja shadow-ajo kirjoittavat kumpikin oman kommenttinsa.

Enforce ei vielä estä mitään: verdictin estävä osa on toteuttamatta. Kun se toteutetaan,
estäminen vaatii lisäksi GitHubissa required status checkin ja branch protectionin
base-haaralle. Ilman niitä PR voi poistaa workflow-tiedoston, eikä moottori voi sitä estää.

## Päällekkäisyyssääntö

Allow-polku ei saa leikata kova- tai pehmea-polkua. Muuten pehmeä muutos voisi olla T0
ja hyväksyttävissä kaikilla portailla. Policy ei lataudu, ja virheilmoitus nimeää polut
ja korjauksen:

```
deny pehmea/testidata polku 'fixtures/henkilot.json' leikkaa allow-polun 'fixtures/**';
lisää 'fixtures/henkilot.json' listaan allow.laajenna_paitsi
```

Tarkistus on mallitasolla: sama literaalipolku tai glob, joka sisältyy toiseen.
`paitsi`-lista poistaa leikkauksen. ei_laskennassa-lista saa leikata deny-polkuja:
generoitu tiedosto deny-kansiossa jää laskennasta pois, mutta deny osuu siihen silti,
eikä T0 synny ilman allow-osumaa.

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
