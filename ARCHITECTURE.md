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
| `portti/paallekkaisyys.py` | allow vs kova/pehmea mallitasolla (literaali tai glob, joka sisältyy toiseen); ei_laskennassa saa leikata |
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
| `portti/arviointi.py` | yhden arvioinnin kokoaminen: luokitus, verdict ja evidence samasta syötteestä (`arvioi`) |
| `portti/cli.py` | komentorivin jäsennin ja ohjaus |
| `portti/cli_komennot.py` | komentojen toteutukset: `arvioi`, `kommentti`, `esto`, `tarkista-tapaukset`, `shadow-raportti` |
| `portti/ohjaus.py` | ohjauksen päätöstaulu (rivit a–e), fail-closed, jo käynnistetty kierros edellisestä päätöksestä, päätös-JSON ja päätös keskeytyneelle kortti-ajolle; ei verkkoa |
| `portti/ohjaus_kommentti.py` | ohjauskommentin renderöinti ja konedata (oma tunniste ja oma kirjoittaja; rikkinäinen konedata merkitään kelvottomaksi) |
| `portti/ohjaus_toteutus.py` | edellisen päätöksen luku ohjauksen omasta kommentista; päätöksen soveltaminen: labelit, kortti-ajon käynnistys, katselmoijapyyntö varavalintoineen, kommentti; käynnistyksen ja pyynnön virhepolut |
| `portti/cli_ohjaus.py` | komennot `ohjaus-edellinen`, `ohjaa`, `ohjaus-toteuta` ja `ohjaus-ajo-epaonnistui` |
| `portti/kortti.py` | kortin metarivien luku (`- Tila:`, `- Malli:`) ylätason luetteloriveistä ilman koodilohkoja ja kommentteja, kortin haaran slug (`feature/<slug>`) |
| `portti/malli.py` | mallipäätös 6.11.2026 funktiona: sallitut mallit yhdessä vakiossa, valinta ja sen lähde |
| `portti/cli_malli.py` | komennot `malli` ja `kortin-tila` |

Riippuvuussuunta: `cli` → (`cli_komennot`, `cli_ohjaus`, `cli_malli`) → (`arviointi`, `kommentti`, `shadow`,
`shadow_muotoilu`, `tapaukset`, `policy_lahde`, `ohjaus_toteutus`) → (`policy`, `git_diff`, `invariantit`,
`github_api`, `ohjaus_kommentti`, `ohjaus`) → (`paallekkaisyys`, `polkumallit`, `verdict`, `malli`) → `kortti`.
`malli` ja `kortti` käyttävät vain vakiokirjastoa. Alemmat eivät tunne
ylempiä. `ohjaus` käyttää verdictin ja tierin vakioita, mutta ei laske mitään diffistä: se lukee evidencen
sanakirjana, saa kaiken syötteenä ja on puhdas funktio.

## Ohjaus

Ohjaus on moottorin osa ja deterministinen: `portti ohjaa` ei käytä verkkoa eikä kielimallia. Syötteet ovat
evidence (tai tieto sen puuttumisesta), testityönkulun lopputulos PR:n headille, muuttuneet polut, PR:n labelit,
forkkitieto ja edellinen päätös; tuloste on järjestetty päätös-JSON ilman tunnuksia. Idempotenssi on moottorissa:
`ohjaus-edellinen` lukee edellisen päätöksen ohjauskommentin konedatasta (head, toimenpide, kierros), ja jos se
käynnisti korjauskierroksen tälle samalle headille, `ohjaa` toistaa kierroksen käynnistämättä uutta
(`kaynnista_kortti_ajo`). Ohjauskommentiksi kelpaa vain ohjauksen oman kirjoittajan kommentti; jos sen konedataa
ei voi lukea, korjauskierrosta odottava PR menee CTO:lle. Toteutus (`ohjaus-toteuta`) on erillinen askel, joka
puhuu GitHubille `GitHubApi`n kautta ja käynnistää kortti-ajon vain, kun päätös sanoo niin. Uusi korjauskierros
vaatii kortin slugin (PR:n haara `feature/<slug>`) ja alkuperäisen ajon mallin (label `malli-<nimi>`); puuttuva
tieto vie PR:n CTO:lle. Korjauskierros ei jää ilman ihmistä: jos kortti-ajoa ei saada käyntiin, toteutus soveltaa
moottorin päätöksen keskeytyneelle ajolle (CTO, label `jumissa`), ja kortti-ajon jälkitarkistus tekee saman
komennolla `ohjaus-ajo-epaonnistui`, kun ajo epäonnistui tai ei tuottanut committia.

## Mallin valinta

CTO:n mallipäätös 6.11.2026 on `portti/malli.py`:n puhdas funktio: syötteinä kortin teksti, käsin valittu arvo ja
korjauskierroksen alkuperäinen malli, tuloksena mallitunniste ja sen lähde tai virhe. Sallitut nimet ja tunnisteet
ovat yhdessä vakiossa, ja tiedoston muutos on portin omassa policyssä kova. Moottori ei kutsu mallia: se vain
päättää, mikä malli kortti-ajolle annetaan. Ohjaus käyttää samaa vakiota labelin `malli-<nimi>` tarkistukseen.
Katselmoijien tunnukset tulevat parametreina kuluttajarepon muuttujista; moottori ei tunne niitä.
Työnkulku `.github/workflows/ohjaus.yml` ajetaan kuluttajan oletushaarasta (`workflow_run`), ei hae PR:n koodia
ja hakee moottorin pinnatusta shasta.

## Kortti-ajo on erillinen komponentti

`.github/workflows/kortti-ajo.yml`, `ajo/prompti.md`, `ajo/kokoa_prompti.py` ja `ajo/ajon_yhteenveto.py`
muodostavat kortti-ajon, joka käyttää kielimallia (claude-code-action) kuluttajarepossa. Moottori (`portti/`) ei
tuo mitään kortti-ajosta eivätkä kortti-ajon skriptit tuo moottoria: kokoaja ja yhteenveto ovat vakiokirjaston
skriptejä, joita ajetaan `python -I`. Työnkulussa on kaksi jobia. Ensimmäinen kutsuu moottoria komentoina
ennen kielimallia (`portti kortin-tila`, `portti malli`), antaa agentille mallin vain `portti malli` -askeleen
tulosteesta ja ajaa agentin; agentin jälkeen siinä on vain askeleita ilman tokeneita. Toinen, jälkitarkistus,
ajetaan puhtaalla runnerilla, koska agentti on voinut ajaa ensimmäisen jobin runnerilla mitä tahansa koodia: se
lukee PR:n tilan GitHubin API:sta, ajaa yhteenvedon ja main-vahdin ja kutsuu moottorin komentoa
`portti ohjaus-ajo-epaonnistui`, jos korjauskierros jäi tuloksetta. Ajon tulos (mallit, kesto, kulu) kulkee
jobien välillä artefaktina ja on dataa agentin runnerilta.
Kortti-ajon tuotos on PR, jonka Portti ja ohjaus arvioivat kuten minkä tahansa PR:n. Riippuvuussuunta: kortti-ajo
→ (prompti, kokoaja, yhteenveto) ja kortti-ajo → moottorin komennot; ohjaus → kortti-ajo vain
`workflow_dispatch`-kutsuna, ei koodiriippuvuutena.

## Evidence-lähde shadow-raportille

Shadow-raportti lukee PR-kommentin konedatan (HTML-kommentti JSONina), ei artefaktia.
Perustelu: kommentti säilyy PR:n mukana ja on sama jokaisella lukukerralla; artefakti vanhenee
(90 päivää) ja sen lataus vaatii ajon tunnisteen. Konedata sisältää verdictin, tierin, head-shan,
versiot, tilan, policyn lähteen, deny-kategoriat, portaat ja puute-lipun. PR:llä voi olla shadow- ja
enforce-kommentti rinnakkain, kun repo vaihtoi tilaa PR:n ollessa auki: raportti valitsee PR:n headiin
täsmäävän kommentin, muuten viimeisimmän. Ennen 0.3.0 kirjoitetut kommentit eivät sisällä kategorioita
("ei tiedossa") eivätkä portaita; portaat johdetaan verdictistä ja tieristä.

## Policyn lähde

Policy ja tapaukset luetaan oletuksena base-shasta kaikissa tiloissa (`policy_lahde: base`);
head vain eksplisiittisesti, auto tilan mukaan. Jos basessa ei ole policyä, luetaan pelkkä
oletuspolicy ja evidence sekä kommentti kertovat sen ("oletus"); headia ei lueta koskaan ilman
eksplisiittistä valintaa, koska oletus ei ole PR:n käsissä mutta head on. Enforce-tilassa actionin
viimeinen askel (`esto`) palauttaa 1, kun verdict on
PUUTE, KOVA tai LIIAN-ISO; kommentti ja artefakti on jo kirjoitettu. Shadow ei kaada koskaan.
Punainen check on neuvoa-antava: moottori ei oleta pakollisia checkejä eikä branch
protectionia, koska Free-tason yksityisrepossa niitä ei ole.

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
ja kaatavat ajon näkyvästi. Poikkeus on ohjauksen toteutus: kortti-ajon käynnistyksen ja katselmoijapyynnön
gh-virhe käsitellään (PR CTO:lle tai seuraava ehdokas), kirjataan ohjauskommenttiin ja palautetaan kutsujalle
virheenä, jolloin komento palauttaa 1. Mitään ei nielaista.

## Nimeäminen

Suomenkieliset tunnisteet ilman ääkkösiä, Pythonin snake_case ja PascalCase.
Verdictien ja tierien arvot ovat kiinteitä merkkijonoja (`portti/verdict.py`).
