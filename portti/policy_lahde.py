"""Policyn ja tapausten lukeminen PR:n headista tai base-haarasta.

Oletus on base kaikissa tiloissa, jotta PR ei voi muuttaa sääntöjä, joilla se itse arvioidaan.
Head valitaan eksplisiittisesti (policyn kehitys-PR:t); auto valitsee tilan mukaan. Jos basessa ei
ole tiedostoa, luetaan pelkkä oletuspolicy (merkintä "oletus"), ei koskaan headia: oletus tulee
pinnatun moottorin mukana eikä ole PR:n käsissä, joten se ei ole kevennysreitti.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from portti.git_diff import nayta_tiedosto

LAHTEET = ("auto", "head", "base")
TILAT = ("shadow", "enforce")
OLETUS = "oletus"


class PolicyLahdeVirhe(ValueError):
    """Pyydettyä lähdettä ei voi käyttää."""


@dataclass(frozen=True)
class PolicyLahde:
    pyydetty: str
    toteutunut: str
    huomautus: str | None = None

    @property
    def merkinta(self) -> str:
        return self.toteutunut if self.huomautus is None else f"{self.toteutunut} ({self.huomautus})"


def ratkaise_lahde(pyydetty: str, tila: str) -> str:
    """auto: enforce lukee basesta, shadow headista."""
    if pyydetty not in LAHTEET:
        raise PolicyLahdeVirhe(f"tuntematon policyn lähde {pyydetty!r}")
    if tila not in TILAT:
        raise PolicyLahdeVirhe(f"tuntematon tila {tila!r}")
    if pyydetty != "auto":
        return pyydetty
    return "base" if tila == "enforce" else "head"


def valmistele_tiedosto(
    repo: Path, base_sha: str, polku: Path, lahde: str, tila: str, kohdekansio: Path
) -> tuple[Path | None, PolicyLahde]:
    """Palauttaa luettavan tiedoston polun (tai None, jos tiedostoa ei ole) ja toteutuneen lähteen.

    Base-luku kirjoittaa basen version kohdekansioon, jotta loput moottorista lukee tavallisen tiedoston.
    Basesta puuttuva tiedosto antaa None ja lähteen "oletus": policylle se tarkoittaa pelkkää oletuspolicyä.
    """
    toteutunut = ratkaise_lahde(lahde, tila)
    head_polku = repo / polku
    if toteutunut == "head":
        return (head_polku if head_polku.exists() else None), PolicyLahde(lahde, "head")
    sisalto = nayta_tiedosto(repo, base_sha, polku.as_posix())
    if sisalto is None:
        return None, PolicyLahde(lahde, OLETUS, f"basessa {base_sha[:12]} ei {polku.name}-tiedostoa")
    kohdekansio.mkdir(parents=True, exist_ok=True)
    kohde = kohdekansio / polku.name
    kohde.write_text(sisalto, encoding="utf-8")
    return kohde, PolicyLahde(lahde, "base")
