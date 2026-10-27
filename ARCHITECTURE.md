# Portti — arkkitehtuuri

Yhden sivun muistio. Moottori on yhdessä repossa; policy ja workflow ovat
jokaisessa kuluttajarepossa. Kuluttaja kutsuu moottoria composite actionina
pinnatulla sha:lla.

## Moduulit ja vastuut

| Moduuli | Vastuu |
|---|---|
| `portti/polkumallit.py` | gitignore-tyyliset polkumallit → regex, osumat ja `paitsi`-poikkeukset |
| `portti/policy_skeema.py` | tiukka skeema: tuntematon avain, väärä tyyppi, `portti_itse`-suoja |
| `portti/policy.py` | oletus- ja repopolicyn yhdistäminen (`laajenna_<avain>`), `Policy`-olio, päällekkäisyystarkistuksen kutsu |
| `portti/paallekkaisyys.py` | allow/ei_laskennassa vs kova/pehmea mallitasolla (literaali tai glob, joka sisältyy toiseen) |
| `portti/policy_lahde.py` | policyn ja tapausten luku headista tai basesta (`git show <base-sha>:polku`) tilan mukaan |
| `portti/git_diff.py` | `git diff base...head` numstat ja name-status (renamet mukaan), tiedoston sisältö revisiosta |
| `portti/invariantit.py` | testifunktioiden laskenta, invarianttitestien tarkistus |
| `portti/luokittelu.py` | substantiiviset rivit ja tiedostot, alueet, deny-osumat, kielletyt uudet polut, tier |
| `portti/verdict.py` | sääntö koodissa: PUUTE > KOVA > LIIAN-ISO > PEHMEÄ > VAPAA, portaat S0–S3 |
| `portti/evidence.py` | evidence-JSON ilman nimiä tai sähköposteja |
| `portti/kommentti.py` | yhden PR-kommentin renderöinti ja idempotentti päivitys |
| `portti/github_api.py` | `gh`-kutsut yhden rajapinnan takana (vaihdettava testeissä) |
| `portti/shadow.py` | shadow-raportin data: ryhmittely base-haaran mukaan, mittarit, kategoriat, jakaumat |
| `portti/shadow_muotoilu.py` | shadow-raportin markdown- ja JSON-tuloste |
| `portti/tapaukset.py` | kuluttajarepon regressiotapaukset |
| `portti/cli.py` | komentorivin jäsennin ja ohjaus |
| `portti/cli_komennot.py` | komentojen toteutukset: `arvioi`, `tarkista-tapaukset`, `shadow-raportti`, `kommentti` |

Riippuvuussuunta: `cli` → `cli_komennot` → (`arviointi`, `kommentti`, `shadow`,
`shadow_muotoilu`, `tapaukset`, `policy_lahde`) → (`policy`, `git_diff`, `invariantit`,
`github_api`) → (`paallekkaisyys`, `polkumallit`). Alemmat eivät tunne ylempiä.

## Evidence-lähde shadow-raportille

Shadow-raportti lukee PR-kommentin konedatan (HTML-kommentti JSONina), ei artefaktia.
Perustelu: kommentti säilyy PR:n mukana ja on sama jokaisella lukukerralla; artefakti vanhenee
(90 päivää) ja sen lataus vaatii ajon tunnisteen. Konedata sisältää verdictin, tierin, head-shan,
versiot, tilan, policyn lähteen, deny-kategoriat, portaat ja puute-lipun. Ennen 0.3.0 kirjoitetut
kommentit eivät sisällä kategorioita eivätkä portaita; raportti näyttää ne tyhjinä.

## Policyn lähde

Shadow lukee policyn ja tapaukset PR:n headista, enforce base-shasta (`policy_lahde: auto`).
Enforce ilman base-policyä kaatuu; shadow lukee headista ja merkitsee sen evidenceen ja
kommenttiin. Enforcen estävä osa (verdict kaataa ajon) on tarkoituksella toteuttamatta.

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
