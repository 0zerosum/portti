"""Testifunktioiden laskenta ja invarianttitarkistus."""

from pathlib import Path

from portti.invariantit import laske_testifunktiot, tarkista_invariantit
from tests.apu_git import perusrepo, luo_testitiedosto


def test_laske_testifunktiot_python_ja_js() -> None:
    python = "def test_a():\n  pass\nasync def test_b():\n  pass\ndef apu():\n  pass\n"
    javascript = "describe('x', () => {\n  it('toimii', () => {});\n  test('myos', () => {});\n});\n"
    assert laske_testifunktiot(python) == 2
    assert laske_testifunktiot(javascript) == 2
    assert laske_testifunktiot(None) == 0


def test_invariantti_ok_kun_maara_ei_laske(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path)
    repo.kirjoita("tests/test_ydin.py", luo_testitiedosto(4))
    head = repo.commit()
    [tulos] = tarkista_invariantit(repo.juuri, base, head, ("tests/test_ydin.py",))
    assert tulos.ok and "4" in tulos.syy


def test_invariantti_rikkoutuu_kun_maara_laskee(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path)
    repo.kirjoita("tests/test_ydin.py", luo_testitiedosto(1))
    head = repo.commit()
    [tulos] = tarkista_invariantit(repo.juuri, base, head, ("tests/test_ydin.py",))
    assert not tulos.ok and tulos.syy == "testifunktioita 3 -> 1"


def test_invariantti_rikkoutuu_kun_tiedosto_puuttuu(tmp_path: Path) -> None:
    repo, base = perusrepo(tmp_path)
    repo.poista("tests/test_kanta.py")
    head = repo.commit()
    tulokset = tarkista_invariantit(repo.juuri, base, head, ("tests/test_kanta.py", "tests/test_ydin.py"))
    assert [tulos.ok for tulos in tulokset] == [False, True]
    assert tulokset[0].syy == "puuttuu headista"
