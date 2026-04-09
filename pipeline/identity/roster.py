"""Carga de rosters (dorsal → nombre) y colores desde un fichero JSON externo.

Formato esperado del JSON:
{
  "Boston Celtics": {
    "colors": "#007A33",
    "players": {"0": "Tatum", "7": "Brown", ...}
  },
  ...
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

_rosters: Dict[str, Dict[str, str]] = {}
_colors: Dict[str, str] = {}


def load(path: str | Path) -> None:
    """Carga rosters y colores desde *path* (sobreescribe los anteriores)."""
    global _rosters, _colors
    data: dict = json.loads(Path(path).read_text(encoding="utf-8"))
    _rosters = {team: entry["players"] for team, entry in data.items()}
    _colors = {team: entry.get("colors", "") for team, entry in data.items()}


def team_color(team_name: Optional[str]) -> Optional[str]:
    if team_name is None:
        return None
    return _colors.get(team_name)


def player_name(team_name: Optional[str], number: Optional[int]) -> Optional[str]:
    """Devuelve el nombre del jugador para (equipo, dorsal), o None."""
    if team_name is None or number is None:
        return None
    roster = _rosters.get(team_name)
    if roster is None:
        return None
    return roster.get(str(int(number)))
