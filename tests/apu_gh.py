"""Vale-gh: tallentaa kutsut, palauttaa ennalta annetut vastaukset ja kaataa pyydetyt kutsut gh:n virheenä."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from portti.github_api import GitHubApi


class ValeGh:
    def __init__(self, vastaukset: dict[str, Any] | None = None, virheet: dict[str, str] | None = None) -> None:
        self.vastaukset = vastaukset or {}
        self.virheet = virheet or {}
        self.kutsut: list[tuple[list[str], str | None]] = []

    def __call__(self, argumentit: list[str], syote: str | None) -> str:
        self.kutsut.append((argumentit, syote))
        komento = " ".join(argumentit)
        for avain, virheteksti in self.virheet.items():
            if avain in komento:
                raise subprocess.CalledProcessError(1, ["gh", *argumentit], stderr=virheteksti)
        for avain, vastaus in self.vastaukset.items():
            if avain in komento:
                return json.dumps(vastaus)
        return ""

    def api(self) -> GitHubApi:
        return GitHubApi(self)

    def metodit(self) -> list[str]:
        return [" ".join(argumentit[:2]) for argumentit, _ in self.kutsut]
