"""gh-komennot yhden rajapinnan takana. Testeissä suoritin vaihdetaan."""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable

Suoritin = Callable[[list[str], str | None], str]


def suorita_gh(argumentit: list[str], syote: str | None) -> str:
    tulos = subprocess.run(
        ["gh", *argumentit],
        check=True,
        capture_output=True,
        text=True,
        input=syote,
    )
    return tulos.stdout


class GitHubApi:
    def __init__(self, suorita: Suoritin = suorita_gh) -> None:
        self._suorita = suorita

    def _json(self, argumentit: list[str], syote: str | None = None) -> Any:
        tuloste = self._suorita(argumentit, syote)
        return json.loads(tuloste) if tuloste.strip() else None

    def hae_kommentit(self, repo: str, pr_numero: int) -> list[dict[str, Any]]:
        polku = f"repos/{repo}/issues/{pr_numero}/comments"
        tulos = self._json(["api", "--paginate", "--slurp", polku])
        sivut = tulos or []
        return [kommentti for sivu in sivut for kommentti in sivu]

    def luo_kommentti(self, repo: str, pr_numero: int, teksti: str) -> None:
        polku = f"repos/{repo}/issues/{pr_numero}/comments"
        self._json(["api", "-X", "POST", polku, "--input", "-"], json.dumps({"body": teksti}))

    def paivita_kommentti(self, repo: str, kommentti_id: int, teksti: str) -> None:
        polku = f"repos/{repo}/issues/comments/{kommentti_id}"
        self._json(["api", "-X", "PATCH", polku, "--input", "-"], json.dumps({"body": teksti}))

    def hae_pr(self, repo: str, pr_numero: int) -> dict[str, Any]:
        kentat = "isDraft,mergeable,headRefOid,baseRefOid,author"
        tulos = self._json(["pr", "view", str(pr_numero), "--repo", repo, "--json", kentat])
        return dict(tulos) if isinstance(tulos, dict) else {}

    def hae_suljetut_prt(self, repo: str, alkaen: str) -> list[dict[str, Any]]:
        kentat = "number,state,mergedAt,closedAt,headRefOid"
        argumentit = [
            "pr", "list", "--repo", repo, "--state", "closed", "--limit", "500",
            "--search", f"closed:>={alkaen}", "--json", kentat,
        ]
        return self._json(argumentit) or []
