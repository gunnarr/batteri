"""Väntar in enheter som Hitta ännu inte hunnit få svar från.

Hittas första svar bygger på vad Apples server hade sparat. Har ingen frågat på ett tag
kan enheter som är påslagna stå som offline tills de hunnit rapportera in, vilket tar
några sekunder. Enheter som var offline redan vid förra körningen (en urladdad klocka,
hörlurar i etui) väntar vi däremot inte på, så normala körningar blir inte långsammare.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

ONLINE = "200"
Raw = list[dict[str, Any]]


def offline_ids(raw: Raw) -> set[str]:
    return {str(d.get("id")) for d in raw if d.get("id") and str(d.get("deviceStatus")) != ONLINE}


def settle(
    raw: Raw,
    known_offline: set[str] | None,
    refetch: Callable[[], Raw],
    sleep: Callable[[float], None],
    attempts: int = 3,
    delay: float = 2.5,
) -> Raw:
    """Hämtar om tills oväntat offline-enheter rapporterat in, eller försöken tar slut.

    `known_offline=None` betyder att vi inte vet något sedan förra gången (första körningen)."""
    known = known_offline or set()
    for _ in range(attempts):
        if not offline_ids(raw) - known:
            break
        sleep(delay)
        raw = refetch()
    return raw


def load_known_offline(path: Path) -> set[str] | None:
    try:
        return set(json.loads(path.read_text())["offline"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_known_offline(path: Path, raw: Raw) -> None:
    try:
        path.write_text(json.dumps({"offline": sorted(offline_ids(raw))}))
        path.chmod(0o600)
    except OSError:
        pass
