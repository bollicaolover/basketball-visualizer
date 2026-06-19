"""Tests de la carga de rosters (`pipeline/identity/roster.py`).

Resolución dorsal → nombre y color de equipo desde el JSON externo, incluido
el comportamiento ante entradas faltantes (None).
"""

from __future__ import annotations

import json

import pytest

from pipeline.identity import roster

ROSTER = {
    "Boston Celtics": {"colors": "#007A33", "players": {"0": "Tatum", "7": "Brown"}},
    "New York Knicks": {"colors": "#1D428A", "players": {"11": "Brunson"}},
}


@pytest.fixture()
def loaded_roster(tmp_path):
    path = tmp_path / "roster.json"
    path.write_text(json.dumps(ROSTER), encoding="utf-8")
    roster.load(path)
    yield
    # Limpia el estado global del módulo entre tests.
    roster._rosters = {}
    roster._colors = {}


def test_player_name_resuelve_equipo_y_dorsal(loaded_roster):
    assert roster.player_name("Boston Celtics", 7) == "Brown"
    assert roster.player_name("New York Knicks", 11) == "Brunson"


def test_player_name_acepta_dorsal_int_o_str_equivalente(loaded_roster):
    # El roster indexa por string; la función normaliza int → str.
    assert roster.player_name("Boston Celtics", 0) == "Tatum"


def test_player_name_devuelve_none_sin_coincidencia(loaded_roster):
    assert roster.player_name("Boston Celtics", 99) is None  # dorsal inexistente
    assert roster.player_name("Equipo Fantasma", 7) is None  # equipo inexistente
    assert roster.player_name(None, 7) is None
    assert roster.player_name("Boston Celtics", None) is None


def test_team_color(loaded_roster):
    assert roster.team_color("Boston Celtics") == "#007A33"
    assert roster.team_color("New York Knicks") == "#1D428A"
    assert roster.team_color("Equipo Fantasma") is None
    assert roster.team_color(None) is None
