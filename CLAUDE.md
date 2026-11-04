# Portti: ohjeet agenteille ja ihmisille

## Tietoturva (pakollinen, ei poikkeuksia)

1. Muiden järjestelmien infra-, pääsy- tai heikkoustietoja ei kirjoiteta tähän repoon.
2. Ei oikeita sähköposteja, nimiä, käyttäjätunnuksia, repojen nimiä, asiakas- tai
   liiketoimintalukuja koodiin, dokumentteihin, testeihin, esimerkkeihin eikä commit-viesteihin.
   Vain keksittyä dataa: sähköpostit example.com- tai .test-domainissa, repot muotoa
   `esimerkki/tilaukset`, tunnukset muotoa `keksitty-tunnus`.
3. Ennen jokaista pushia tarkistetaan `git status` ja koko `git diff` tältä kannalta.
4. Repo on julkinen: ei kuluttajarepojen nimiä, käyttäjätunnuksia, organisaatioiden nimiä eikä
   muiden järjestelmien tietoja. Katselmoijien tunnukset ja budjetit ovat kuluttajarepon
   muuttujissa ja salaisuuksissa, eivät tässä repossa.

## Periaatteet

- Moottori (`portti/`) ei käytä kielimallia. Luokitus, verdict, evidence ja ohjaus ovat
  deterministisiä: sama syöte antaa saman tulosteen, ja tulosteiden avaimet ovat järjestetyt.
- Kortti-ajo (`.github/workflows/kortti-ajo.yml` ja `ajo/`) on erillinen komponentti, joka
  käyttää kielimallia kuluttajarepossa. Moottori ei riipu siitä, eikä kortti-ajo muuta moottoria.
- Ohjaus on fail-closed: jos tieto puuttuu tai ei täsmää, PR menee CTO:lle.
- Muutos mainiin vain CTO:n hyväksymällä PR:llä. Ei pushia mainiin, ei tageja, ei julkaisuja
  ilman CTO:ta. Työ tehdään feature-haaroihin.
- Riippuvuudet ja actionit pinnataan versioon tai commit-shaan.
- Rakenne ja moduulirajat ovat tiedostossa ARCHITECTURE.md. Tiedosto enintään 400 riviä,
  funktio enintään 60 riviä, yksi vastuu per moduuli, ei globaalia muuttuvaa tilaa.

## Testikomennot

Samat kuin `.github/workflows/testit.yml`; kaikkien on mentävä läpi ennen commitia.

```bash
python3.11 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m mypy --strict portti
.venv/bin/python -m pytest -q
PYTHONSAFEPATH=1 .venv/bin/portti tarkista-tapaukset .portti/tapaukset.yml --lahde head
```
