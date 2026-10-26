"""Vale-gh: tallentaa kutsut ja palauttaa ennalta annetut vastaukset."""

from __future__ import annotations

import json
from typing import Any

from portti.github_api import GitHubApi


class ValeGh:
    def __init__(self, vastaukset: dict[str, Any] | None = None) -> None:
        self.vastaukset = vastaukset or {}
        self.kutsut: list[tuple[list[str], str | None]] = []

    def __call__(self, argumentit: list[str], syote: str | None) -> str:
        self.kutsut.append((argumentit, syote))
        for avain, vastaus in self.vastaukset.items():
            if avain in " ".join(argumentit):
                return json.dumps(vastaus)
        return ""

    def api(self) -> GitHubApi:
        return GitHubApi(self)

    def metodit(self) -> list[str]:
        return [" ".join(argumentit[:2]) for argumentit, _ in self.kutsut]
