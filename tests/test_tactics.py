"""Tests del reconocedor de pantallas (`pipeline/tactics`).

Cubre el bloque táctico de Chen et al. 2012:
  - discriminación ataque/defensa (§4.2) por posesión y por distancia (fallback),
  - detección de pantalla por frame (Algoritmo 2),
  - clasificación front/back/down por trayectoria (Ec. 9),
  - agregación temporal de detecciones en eventos.

Las trayectorias son sintéticas en pies sobre la geometría NBA, así que no se
ejecuta ningún modelo. La canasta izquierda está cerca de x≈5.25 ft.
"""

from __future__ import annotations

import numpy as np

from pipeline.config import TacticsSettings
from pipeline.tactics.geometry import attacking_basket, basket_xy
from pipeline.tactics.recognizer import FrameTactics, ScreenRecognizer
from pipeline.tactics.types import PlayerSnapshot


def _snap(track_id, team, x, y):
    return PlayerSnapshot(track_id=track_id, team=team, xy=np.array([x, y], float))


def _frame(idx, players, possessor=None):
    return FrameTactics(idx, players, possessor)


# Canasta izquierda como referencia de "el aro atacado".
LB = basket_xy("left")


# ---------------------------------------------------------------------------
# §4.2 — discriminación ataque/defensa
# ---------------------------------------------------------------------------
def test_split_teams_prefers_possessor():
    rec = ScreenRecognizer()
    # El equipo "dark" posee el balón aunque esté más cerca del aro.
    players = [
        _snap(1, "dark", 8.0, 25.0),
        _snap(2, "dark", 9.0, 20.0),
        _snap(3, "white", 30.0, 25.0),
        _snap(4, "white", 32.0, 20.0),
    ]
    fr = _frame(0, players, possessor=1)
    off_team, offense, defense, basket = rec.split_teams(fr)
    assert off_team == "dark"
    assert {p.track_id for p in offense} == {1, 2}


def test_split_teams_distance_fallback():
    rec = ScreenRecognizer()
    # Sin poseedor: el equipo más lejos de su aro es el atacante.
    near = [_snap(1, "white", LB[0] + 5, 25.0), _snap(2, "white", LB[0] + 6, 20.0)]
    far = [_snap(3, "dark", LB[0] + 40, 25.0), _snap(4, "dark", LB[0] + 42, 20.0)]
    fr = _frame(0, near + far, possessor=None)
    off_team, offense, _, _ = rec.split_teams(fr)
    assert off_team == "dark"
    assert {p.track_id for p in offense} == {3, 4}


def test_attacking_basket_is_nearest():
    assert attacking_basket([LB + np.array([5.0, 0.0])]) == "left"
    rb = basket_xy("right")
    assert attacking_basket([rb - np.array([5.0, 0.0])]) == "right"


# ---------------------------------------------------------------------------
# §5.1 — Algoritmo 2 (detección por frame)
# ---------------------------------------------------------------------------
def test_detect_frame_identifies_screener_and_screenee():
    rec = ScreenRecognizer()
    # Dos atacantes a ~6 ft (entre ds=4 y Ds=8). Defensor entre ambos, pegado al 1.
    offense = [_snap(1, "white", 20.0, 25.0), _snap(2, "white", 26.0, 25.0)]
    defense = [_snap(9, "dark", 21.0, 25.0)]  # a 1 ft del jugador 1, sobre el eje
    det = rec.detect_frame(offense, defense)
    assert det == (1, 2)  # screener=1 (toca al defensor), screenee=2


def test_detect_frame_none_when_too_far():
    rec = ScreenRecognizer()
    offense = [_snap(1, "white", 5.0, 25.0), _snap(2, "white", 40.0, 25.0)]  # >Ds
    defense = [_snap(9, "dark", 6.0, 25.0)]
    assert rec.detect_frame(offense, defense) is None


def test_detect_frame_none_without_defender_contact():
    rec = ScreenRecognizer()
    offense = [_snap(1, "white", 20.0, 25.0), _snap(2, "white", 26.0, 25.0)]
    defense = [_snap(9, "dark", 50.0, 25.0)]  # ningún defensor cerca
    assert rec.detect_frame(offense, defense) is None


def test_detect_frame_none_when_defender_beside_not_between():
    # FP clásico: dos compañeros a ~6 ft con un defensor pegado a uno (3.5 ft)
    # pero POR DETRÁS, fuera del corredor que los une. Es proximidad incidental,
    # no un bloqueo: con el filtro "entre los dos" (§5.1) ya no dispara. (El
    # Algoritmo 2 tal cual, solo por proximidad, sí lo daba como screen.)
    rec = ScreenRecognizer()
    offense = [_snap(1, "white", 20.0, 25.0), _snap(2, "white", 26.0, 25.0)]
    defense = [_snap(9, "dark", 20.0, 21.5)]  # a 3.5 ft del 1, pero no entre 1 y 2
    assert rec.detect_frame(offense, defense) is None


def test_detect_frame_accepts_defender_on_the_lane():
    # Mismo par, pero el defensor cae en el centro del corredor → screen válido.
    rec = ScreenRecognizer()
    offense = [_snap(1, "white", 20.0, 25.0), _snap(2, "white", 26.0, 25.0)]
    defense = [_snap(9, "dark", 22.5, 25.0)]  # a mitad de camino, en contacto
    assert rec.detect_frame(offense, defense) == (1, 2)


# ---------------------------------------------------------------------------
# §5.2 / Ec. 9 — clasificación con eventos completos
# ---------------------------------------------------------------------------
def _screen_sequence(screener_path, screenee_path, defender_path, possessor=1):
    """Construye frames a partir de trayectorias (listas de (x,y) iguales)."""
    n = len(screener_path)
    frames = []
    for i in range(n):
        players = [
            _snap(1, "white", *screener_path[i]),
            _snap(2, "white", *screenee_path[i]),
            _snap(9, "dark", *defender_path[i]),
            # Un segundo defensor lejos, para que existan dos equipos.
            _snap(8, "dark", 70.0, 25.0),
        ]
        frames.append(_frame(i, players, possessor=possessor))
    return frames


# Down-screen: el screener BAJA del exterior al poste bajo (x→aro izq.) y deja
# el bloqueo; el screenee aguanta cerca del aro. El defensor sigue al screener.
DOWN_SCREENER = [(30, 25), (30, 25), (28, 25), (24, 25), (20, 25),
                 (17, 25), (16, 25), (16, 25), (16, 25), (16, 25)]
DOWN_SCREENEE = [(16, 20)] * 10
DOWN_DEFENDER = [(x, 24) for (x, _) in DOWN_SCREENER]


def test_classify_down_screen():
    rec = ScreenRecognizer()
    events = rec.recognize(_screen_sequence(DOWN_SCREENER, DOWN_SCREENEE, DOWN_DEFENDER))
    assert len(events) == 1
    assert events[0].screen_type == "down"
    assert events[0].basket == "left"


def test_classify_back_screen():
    rec = ScreenRecognizer()
    # El screener NO baja al aro (x≈25 fijo); tras el bloqueo el screenee corta
    # HACIA la canasta (x decrece hacia el aro izquierdo).
    screener = [(25, 28)] * 12
    screenee = [(31, 28)] * 6 + [(28, 28), (24, 28), (18, 28), (12, 28), (8, 28), (6, 28)]
    defender = [(26, 28)] * 12
    events = rec.recognize(_screen_sequence(screener, screenee, defender))
    assert len(events) == 1
    assert events[0].screen_type == "back"


def test_classify_front_screen():
    rec = ScreenRecognizer()
    # El screener no baja al aro; tras el bloqueo el screenee se ALEJA del aro
    # (sale a un espacio abierto, x crece).
    screener = [(25, 28)] * 12
    screenee = [(31, 28)] * 6 + [(34, 28), (38, 28), (42, 28), (46, 28), (50, 28), (54, 28)]
    defender = [(26, 28)] * 12
    events = rec.recognize(_screen_sequence(screener, screenee, defender))
    assert len(events) == 1
    assert events[0].screen_type == "front"


def test_event_requires_min_frames():
    rec = ScreenRecognizer(TacticsSettings(min_event_frames=5))
    # Solo 3 frames con contacto → por debajo del mínimo → sin evento.
    screener = [(25, 24)] * 3
    screenee = [(31, 24)] * 3
    defender = [(26, 24)] * 3
    events = rec.recognize(_screen_sequence(screener, screenee, defender))
    assert events == []


def test_no_event_when_players_spread():
    rec = ScreenRecognizer()
    # Ataque con espaciado normal (>Ds entre los dos) → nunca hay pantalla.
    screener = [(10, 10)] * 6
    screenee = [(40, 40)] * 6
    defender = [(11, 10)] * 6
    events = rec.recognize(_screen_sequence(screener, screenee, defender))
    assert events == []


def test_no_event_when_defender_trails_not_between():
    rec = ScreenRecognizer()
    # Dos compañeros estacionados a ~6 ft con un defensor pegado a uno pero por
    # detrás (fuera del corredor): proximidad incidental sostenida, no un screen.
    # Antes del filtro "entre los dos" esto producía un evento falso.
    screener = [(20, 25)] * 6
    screenee = [(26, 25)] * 6
    defender = [(20, 21.5)] * 6
    events = rec.recognize(_screen_sequence(screener, screenee, defender))
    assert events == []


def test_down_screen_requires_minimum_approach():
    rec = ScreenRecognizer()  # down_approach_margin_ft = 3.0
    # El screener deriva solo ~2 ft hacia el aro al fijar el bloqueo: por debajo
    # del margen → NO es down. Con el test estricto previo (cualquier deriva > 0)
    # se habría etiquetado como down. El screenee corta al aro → back.
    init = np.array([25.0, 28.0])
    screen = np.array([23.0, 28.0])      # ~2 ft más cerca del aro izquierdo
    screenee_screen = np.array([31.0, 28.0])
    screenee_last = np.array([8.0, 28.0])  # corta hacia el aro
    assert rec._classify("left", init, screen, screenee_screen, screenee_last) == "back"


def test_event_serialization_roundtrip():
    rec = ScreenRecognizer()
    events = rec.recognize(_screen_sequence(DOWN_SCREENER, DOWN_SCREENEE, DOWN_DEFENDER))
    d = events[0].to_dict()
    assert d["screener_track"] == 1 and d["screenee_track"] == 2
    assert d["team"] == "white"
    assert set(d["screener_trajectory"]) == {"init", "screen", "last"}
    assert d["start_frame"] >= 0 and d["end_frame"] >= d["start_frame"]
