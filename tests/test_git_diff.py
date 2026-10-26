"""Diffin luku synteettisestä repostaa: lisäys, muutos, poisto, uudelleennimeäminen, binaari."""

from pathlib import Path

from portti.git_diff import lue_diff, nayta_tiedosto, ratkaise_sha
from tests.apu_git import perusrepo, rivit


def test_lisays_muutos_poisto_ja_rename(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path)
    repo.kirjoita("palvelin/sovellus/laskenta/uusi.py", rivit(5))
    repo.kirjoita("palvelin/sovellus/laskenta/ydin.py", rivit(30) + "lisays\n")
    repo.poista("docs/ohje.md")
    repo.nimea("palvelin/sovellus/varasto/kanta.py", "palvelin/sovellus/varasto/tietokanta.py")
    head = repo.commit()
    tiedostot = {tiedosto.polku: tiedosto for tiedosto in lue_diff(repo.juuri, base, head)}
    assert tiedostot["palvelin/sovellus/laskenta/uusi.py"].tila == "A"
    assert tiedostot["palvelin/sovellus/laskenta/uusi.py"].lisatty == 5
    assert tiedostot["palvelin/sovellus/laskenta/ydin.py"].tila == "M"
    assert tiedostot["palvelin/sovellus/laskenta/ydin.py"].rivit == 1
    assert tiedostot["docs/ohje.md"].tila == "D"
    nimetty = tiedostot["palvelin/sovellus/varasto/tietokanta.py"]
    assert nimetty.tila == "R"
    assert nimetty.vanha_polku == "palvelin/sovellus/varasto/kanta.py"
    assert nimetty.rivit == 0
    assert "palvelin/sovellus/varasto/kanta.py" not in tiedostot


def test_binaari_merkitaan(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path)
    (repo.juuri / "kuva.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02")
    head = repo.commit()
    [tiedosto] = lue_diff(repo.juuri, base, head)
    assert tiedosto.binaari and tiedosto.rivit == 0 and tiedosto.tila == "A"


def test_kolmen_pisteen_alue_ohittaa_basen_omat_muutokset(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path)
    repo.kirjoita("kayttoliittyma/nakymat/etusivu.ts", rivit(31))
    head = repo.commit()
    repo.git("checkout", "-q", "main")
    repo.kirjoita("README.md", "# muuttunut mainissa\n")
    main_uusi = repo.commit("main etenee")
    polut = [tiedosto.polku for tiedosto in lue_diff(repo.juuri, main_uusi, head)]
    assert polut == ["kayttoliittyma/nakymat/etusivu.ts"]


def test_nayta_tiedosto_ja_ratkaise_sha(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path)
    assert nayta_tiedosto(repo.juuri, base, "README.md") == "# Keksitty projekti\n"
    assert nayta_tiedosto(repo.juuri, base, "ei/ole.py") is None
    assert ratkaise_sha(repo.juuri, "main") == base
