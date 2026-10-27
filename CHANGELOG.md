# Muutoshistoria

## 0.2.0

- Action: `PYTHONSAFEPATH=1` kaikissa Python-askelissa, jotta PR:n checkoutin tiedostot eivät varjosta moottorin moduuleja.
- Action: luonnostila luetaan tapahtumasta (`github.event.pull_request.draft`); vain mergeable-tila haetaan API:sta.
- Action: uusi syöte `tapaukset_polku` (oletus `.portti/tapaukset.yml`); repon regressiotapaukset ajetaan actionissa, jos tiedosto on olemassa.
- README: `laajenna_`-esimerkki mapping-avainten sisällä (`ei_laskennassa.laajenna_polut`, `allow.laajenna_paitsi`) ja huomautus, että actionia ei voi kutsua `uses: ./<polku>`-muodossa.

## 0.1.0

- Ensimmäinen versio: policy, luokittelu, verdict, evidence, kommentti, shadow-raportti, tapaukset ja composite action.
- Synteettinen PR testaa actionin ja kommentin päivityksen.
