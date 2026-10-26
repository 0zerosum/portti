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
   ```

2. `.portti/tapaukset.yml` — repon omat regressiotapaukset.
   `portti tarkista-tapaukset .portti/tapaukset.yml` kaatuu poikkeamasta.

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

   Yksityistä action-repoa voi käyttää vain saman omistajan repoista, kun tämän
   repon asetus *Actions → Access* sallii sen. Muun omistajan repo hakee moottorin
   erikseen `actions/checkout`-askeleella (`repository: 0zerosum/portti`,
   `path: .portti-moottori`, lukutoken) ja kutsuu `uses: ./.portti-moottori`.

## Actionin syötteet

| Syöte | Oletus | Merkitys |
|---|---|---|
| `policy_polku` | `.portti/policy.yml` | repon policy |
| `tila` | `shadow` | `shadow` kommentoi; `enforce` kaatuu "ei toteutettu" |
| `github_token` | – | PR:n tilan luku ja kommentin kirjoitus |
| `python_versio` | `3.11` | moottorin tulkki |

Shadow-tilassa action ei hyväksy, ei pyydä muutoksia eikä palauta estävää
exit-koodia. Evidence ladataan artefaktiksi `portti-evidence-pr<numero>`.

## Muut komennot

- `portti shadow-raportti --repo <omistaja/repo> --alkaen <VVVV-KK-PP>` vertaa
  portin verdictit suljettujen PR:ien lopputuloksiin. Ei tallenna mitään.
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
