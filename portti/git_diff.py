"""Diffin luku gitistä: numstat ja name-status, uudelleennimeämiset mukaan."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MuutettuTiedosto:
    polku: str
    tila: str
    vanha_polku: str | None
    lisatty: int
    poistettu: int
    binaari: bool

    @property
    def rivit(self) -> int:
        return self.lisatty + self.poistettu

    @property
    def on_uusi_polku(self) -> bool:
        return self.tila in ("A", "R", "C")


def aja_git(repo: Path, *argumentit: str) -> str:
    tulos = subprocess.run(
        ["git", "-C", str(repo), *argumentit],
        check=True,
        capture_output=True,
    )
    return tulos.stdout.decode("utf-8", errors="replace")


def ratkaise_sha(repo: Path, viite: str) -> str:
    return aja_git(repo, "rev-parse", "--verify", f"{viite}^{{commit}}").strip()


def nayta_tiedosto(repo: Path, viite: str, polku: str) -> str | None:
    """Tiedoston sisältö revisiossa, None jos tiedostoa ei ole."""
    tulos = subprocess.run(
        ["git", "-C", str(repo), "show", f"{viite}:{polku}"],
        capture_output=True,
    )
    if tulos.returncode != 0:
        return None
    return tulos.stdout.decode("utf-8", errors="replace")


def _jasenna_tilat(teksti: str) -> dict[str, tuple[str, str | None]]:
    """name-status -z: polku -> (tila, vanha polku)."""
    tilat: dict[str, tuple[str, str | None]] = {}
    osat = teksti.split("\0")
    indeksi = 0
    while indeksi < len(osat) and osat[indeksi]:
        tila = osat[indeksi][0]
        if tila in ("R", "C"):
            tilat[osat[indeksi + 2]] = (tila, osat[indeksi + 1])
            indeksi += 3
        else:
            tilat[osat[indeksi + 1]] = (tila, None)
            indeksi += 2
    return tilat


def _luku(kentta: str) -> tuple[int, bool]:
    if kentta == "-":
        return 0, True
    return int(kentta), False


def _jasenna_numstat(teksti: str) -> list[tuple[str, int, int, bool]]:
    """numstat -z: lista (polku, lisätty, poistettu, binaari)."""
    rivit: list[tuple[str, int, int, bool]] = []
    osat = teksti.split("\0")
    indeksi = 0
    while indeksi < len(osat) and osat[indeksi]:
        lisatty_kentta, poistettu_kentta, polku = osat[indeksi].split("\t", 2)
        lisatty, binaari_a = _luku(lisatty_kentta)
        poistettu, binaari_b = _luku(poistettu_kentta)
        if polku == "":
            polku = osat[indeksi + 2]
            indeksi += 3
        else:
            indeksi += 1
        rivit.append((polku, lisatty, poistettu, binaari_a or binaari_b))
    return rivit


def lue_diff(repo: Path, base: str, head: str) -> list[MuutettuTiedosto]:
    """Muutetut tiedostot välillä merge-base(base, head)..head."""
    alue = f"{base}...{head}"
    tilat = _jasenna_tilat(aja_git(repo, "diff", "--name-status", "-M", "-z", alue))
    tiedostot: list[MuutettuTiedosto] = []
    for polku, lisatty, poistettu, binaari in _jasenna_numstat(
        aja_git(repo, "diff", "--numstat", "-M", "-z", alue)
    ):
        tila, vanha = tilat.get(polku, ("M", None))
        tiedostot.append(MuutettuTiedosto(polku, tila, vanha, lisatty, poistettu, binaari))
    return sorted(tiedostot, key=lambda tiedosto: tiedosto.polku)
