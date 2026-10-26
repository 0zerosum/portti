"""Synteettiset git-repot testeihin. Kaikki sisältö keksittyä."""

from __future__ import annotations

import subprocess
from pathlib import Path


class SynteettinenRepo:
    """Pieni apuri: kirjoita tiedostoja, committaa, hae shat."""

    def __init__(self, juuri: Path) -> None:
        self.juuri = juuri
        juuri.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "testi@example.com")
        self.git("config", "user.name", "Testi Tekija")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *argumentit: str) -> str:
        tulos = subprocess.run(
            ["git", "-C", str(self.juuri), *argumentit],
            check=True,
            capture_output=True,
            text=True,
        )
        return tulos.stdout.strip()

    def kirjoita(self, polku: str, sisalto: str) -> None:
        kohde = self.juuri / polku
        kohde.parent.mkdir(parents=True, exist_ok=True)
        kohde.write_text(sisalto, encoding="utf-8")

    def poista(self, polku: str) -> None:
        (self.juuri / polku).unlink()

    def nimea(self, vanha: str, uusi: str) -> None:
        kohde = self.juuri / uusi
        kohde.parent.mkdir(parents=True, exist_ok=True)
        (self.juuri / vanha).rename(kohde)

    def commit(self, viesti: str = "muutos") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", viesti)
        return self.git("rev-parse", "HEAD")

    def haara(self, nimi: str, lahto: str) -> None:
        self.git("checkout", "-q", "-b", nimi, lahto)


def rivit(maara: int, etuliite: str = "rivi") -> str:
    return "".join(f"{etuliite} {indeksi}\n" for indeksi in range(maara))


def luo_testitiedosto(maara: int) -> str:
    return "".join(f"def test_tapaus_{indeksi}():\n    assert True\n\n" for indeksi in range(maara))


def perusrepo(juuri: Path) -> tuple[SynteettinenRepo, str]:
    """Repo, jossa on lähdekoodia, testejä ja dokumentaatiota. Palauttaa base-shan."""
    repo = SynteettinenRepo(juuri)
    repo.kirjoita("README.md", "# Keksitty projekti\n")
    repo.kirjoita("CLAUDE.md", "ohjeet\n")
    repo.kirjoita("palvelin/sovellus/laskenta/ydin.py", rivit(30))
    repo.kirjoita("palvelin/sovellus/varasto/kanta.py", rivit(30))
    repo.kirjoita("kayttoliittyma/nakymat/etusivu.ts", rivit(30))
    repo.kirjoita("tests/test_ydin.py", luo_testitiedosto(3))
    repo.kirjoita("tests/test_kanta.py", luo_testitiedosto(2))
    repo.kirjoita("docs/ohje.md", "ohje\n")
    repo.kirjoita("requirements.txt", "pyyaml==6.0\n")
    base = repo.commit("alku")
    repo.haara("muutos", base)
    return repo, base
