# Portti — arkkitehtuuri

Yhden sivun muistio. Moottori on yhdessä repossa; policy ja workflow ovat
jokaisessa kuluttajarepossa. Kuluttaja kutsuu moottoria composite actionina
pinnatulla sha:lla.

## Moduulit ja vastuut

| Moduuli | Vastuu |
|---|---|
| `portti/polkumallit.py` | gitignore-tyyliset polkumallit → regex, osumat ja `paitsi`-poikkeukset |
| `portti/policy_skeema.py` | tiukka skeema: tuntematon avain, väärä tyyppi, `portti_itse`-suoja |
| `portti/policy.py` | oletus- ja repopolicyn yhdistäminen (`laajenna_<avain>`), `Policy`-olio |
| `portti/git_diff.py` | `git diff base...head` numstat ja name-status (renamet mukaan), tiedoston sisältö revisiosta |
| `portti/invariantit.py` | testifunktioiden laskenta, invarianttitestien tarkistus |
| `portti/luokittelu.py` | substantiiviset rivit ja tiedostot, alueet, deny-osumat, kielletyt uudet polut, tier |
| `portti/verdict.py` | sääntö koodissa: PUUTE > KOVA > LIIAN-ISO > PEHMEÄ > VAPAA, portaat S0–S3 |
| `portti/evidence.py` | evidence-JSON ilman nimiä tai sähköposteja |
| `portti/kommentti.py` | yhden PR-kommentin renderöinti ja idempotentti päivitys |
| `portti/github_api.py` | `gh`-kutsut yhden rajapinnan takana (vaihdettava testeissä) |
| `portti/shadow.py` | shadow-raportti: portin verdict vs. PR:n lopputulos |
| `portti/tapaukset.py` | kuluttajarepon regressiotapaukset |
| `portti/cli.py` | komentorivi: `arvioi`, `tarkista-tapaukset`, `shadow-raportti`, `kommentti` |

Riippuvuussuunta: `cli` → (`luokittelu`, `verdict`, `evidence`, `kommentti`,
`shadow`, `tapaukset`) → (`policy`, `git_diff`, `invariantit`, `github_api`)
→ `polkumallit`. Alemmat eivät tunne ylempiä.

## Datamalli

- `MuutettuTiedosto`: polku, vanha polku, tila (A/M/D/R/C), lisätyt, poistetut, binaari.
- `Luokitus`: tiedostot, substantiiviset polut, rivit, alueet, deny-osumat tasoittain,
  kielletyt uudet polut, tier, invarianttitulokset, testimäärät, puutteet.
- `Verdict`: verdict, porttien tulokset (nimi, tulos, syy), `hyvaksyttavissa_portaalla`.
- Evidence on näiden JSON-esitys plus moottorin versio, policyn sha, repo, PR, shat ja tekijän GitHub-tunnus.

## Tila ja virheet

Ei globaalia tilaa. Kaikki funktiot saavat riippuvuutensa parametreina
(repo-polku, policy, `GitHubApi`). Policyn virheet nostavat `PolicyVirhe`-poikkeuksen
latauksessa; git- ja gh-virheet nousevat `subprocess.CalledProcessError`-poikkeuksena
ja kaatavat ajon näkyvästi. Mitään ei nielaista.

## Nimeäminen

Suomenkieliset tunnisteet ilman ääkkösiä, Pythonin snake_case ja PascalCase.
Verdictien ja tierien arvot ovat kiinteitä merkkijonoja (`portti/verdict.py`).
