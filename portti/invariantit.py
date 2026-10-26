"""Testifunktioiden laskenta ja invarianttitestien tarkistus."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from portti.git_diff import MuutettuTiedosto, nayta_tiedosto

TESTIFUNKTIO = re.compile(r"^\s*(?:async\s+)?def\s+test_\w*|\bit\(|\btest\(", re.MULTILINE)


@dataclass(frozen=True)
class InvarianttiTulos:
    polku: str
    ok: bool
    syy: str


@dataclass(frozen=True)
class TestiMaara:
    base: int
    head: int

    @property
    def laskee(self) -> bool:
        return self.head < self.base


def laske_testifunktiot(sisalto: str | None) -> int:
    if sisalto is None:
        return 0
    return len(TESTIFUNKTIO.findall(sisalto))


def testimaara_tiedostoille(repo: Path, base: str, head: str, polut: list[str]) -> TestiMaara:
    base_summa = sum(laske_testifunktiot(nayta_tiedosto(repo, base, polku)) for polku in polut)
    head_summa = sum(laske_testifunktiot(nayta_tiedosto(repo, head, polku)) for polku in polut)
    return TestiMaara(base_summa, head_summa)


def testimaara_muutoksille(
    repo: Path, base: str, head: str, testit: list[MuutettuTiedosto]
) -> TestiMaara:
    """Muutettujen testitiedostojen yhteismäärä; poistettu tai nimetty tiedosto lasketaan vanhasta polusta."""
    base_summa = 0
    head_summa = 0
    for tiedosto in testit:
        vanha = tiedosto.vanha_polku or tiedosto.polku
        base_summa += laske_testifunktiot(nayta_tiedosto(repo, base, vanha))
        head_summa += laske_testifunktiot(nayta_tiedosto(repo, head, tiedosto.polku))
    return TestiMaara(base_summa, head_summa)


def tarkista_invariantit(
    repo: Path, base: str, head: str, invarianttitestit: tuple[str, ...]
) -> list[InvarianttiTulos]:
    """Jokainen invarianttitesti on headissa eikä sen testimäärä laske."""
    tulokset: list[InvarianttiTulos] = []
    for polku in invarianttitestit:
        head_sisalto = nayta_tiedosto(repo, head, polku)
        if head_sisalto is None:
            tulokset.append(InvarianttiTulos(polku, False, "puuttuu headista"))
            continue
        maara = TestiMaara(
            laske_testifunktiot(nayta_tiedosto(repo, base, polku)),
            laske_testifunktiot(head_sisalto),
        )
        if maara.laskee:
            syy = f"testifunktioita {maara.base} -> {maara.head}"
            tulokset.append(InvarianttiTulos(polku, False, syy))
        else:
            tulokset.append(InvarianttiTulos(polku, True, f"testifunktioita {maara.head}"))
    return tulokset
