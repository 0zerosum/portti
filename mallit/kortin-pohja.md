# Kortin pohjan rivit kortti-ajoa varten

Kortti on kuluttajarepon tiedosto `kortit/<slug>.md`. Kortti-ajo lukee siitä kaksi riviä oletushaarasta ennen
kuin kielimallia kutsutaan. Lisää nämä rivit repon kortin pohjaan:

```markdown
- Tila: luonnos
- Malli: opus (oletus; fable vain hyväksytyllä päätöksellä)
```

## Rivien muoto

Tila- ja mallirivi kirjoitetaan kortin alkuosaan: otsikon jälkeen, ennen ensimmäistä väliotsikkoa, vaakaviivaa,
koodilohkoa, kaavaa, HTML:ää tai kommenttia. Ne ovat ylätason luettelorivejä muodossa `- Avain: arvo` (myös `*`
käy, sisennystä enintään kolme välilyöntiä). Jos sama avain on alkuosassa muussa muodossa, esimerkiksi
`- **Malli:** fable`, `1. Tila: hyväksytty` tai sisennettynä alilistaan, tai kahdesti, ajo ei käynnisty: moottori
ei arvaa, mitä rivillä tarkoitettiin.

Alkuosan jälkeistä tekstiä ei lueta metariveiksi, joten kortin rungossa saa olla esimerkiksi hyväksymiskriteeri
`- Tila: maksettu`. Poikkeus on rivi, jonka avain on Malli ja arvo mallin nimi tai tunniste (esimerkiksi
`- Malli: sonnet`): se estää ajon myös rungossa, koska mallirivi on silloin väärässä paikassa. Rivi ilman
luettelomerkkiä kesken tekstiä (`Malli: ...`) ei ole metarivi.

## Tila

Kortti-ajo käynnistyy vain, kun rivi on `- Tila: hyväksytty` oletushaarassa. Sulkuhuomautus rivin lopussa on
sallittu, esimerkiksi `- Tila: hyväksytty (CTO 6.11.2026)`. Rivi saa olla kortissa vain kerran.

## Malli

Mallipäätös 6.11.2026: koodia, kortteja ja suunnitelmia ei kirjoiteta Sonnetilla eikä Haikulla.

| Rivi | Tulos |
|---|---|
| riviä ei ole | opus |
| `- Malli: opus` tai `- Malli: opus (oletus; fable vain hyväksytyllä päätöksellä)` | opus |
| `- Malli: fable`, kun CTO tai CEO on hyväksynyt sen kortin mukana | fable |
| mikä tahansa muu arvo, myös tyhjä | ajo ei käynnisty |

Ihminen voi valita mallin myös käynnistäessään ajon käsin (syöte `malli_kasin`); käsin valittu arvo voittaa
kortin rivin. Korjauskierros käyttää aina alkuperäisen ajon mallia. Sallitut arvot ovat moottorin vakiossa
`portti/malli.py`, ja niiden muutos on kova.
