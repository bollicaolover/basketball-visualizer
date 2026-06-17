"""Tests del resolutor de posesión (`pipeline/possession/resolver.py`).

Cubre la máquina de estados con histéresis: hace falta ganar ``switch_frames``
frames seguidos para arrebatar la posesión, perderla tras ``loose_frames`` sin
candidato, y la prioridad de la señal `player-in-possession` (clase 5) sobre la
proximidad del balón.
"""

from __future__ import annotations

import numpy as np
import supervision as sv

from pipeline.config import PossessionSettings
from pipeline.possession.resolver import PossessionResolver
from pipeline.tracking.types import TrackedEntity


def _player(track_id: int, bbox) -> TrackedEntity:
    return TrackedEntity(
        track_id=track_id,
        class_id=4,  # PLAYER_CLASS
        confidence=0.9,
        bbox_xyxy=np.array(bbox, dtype=np.float32),
    )


def _ball(cx: float, cy: float) -> sv.Detections:
    return sv.Detections(xyxy=np.array([[cx - 5, cy - 5, cx + 5, cy + 5]], dtype=np.float32))


def test_histeresis_requiere_switch_frames_para_fijar_poseedor():
    s = PossessionSettings(switch_frames=3)
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200])]
    ball = _ball(25, 100)  # balón dentro del bbox del jugador 1

    # No fija al poseedor hasta acumular switch_frames frames consecutivos.
    assert r.update(ball, players) is None
    assert r.update(ball, players) is None
    assert r.update(ball, players) == 1


def test_balon_suelto_tras_loose_frames_sin_candidato():
    s = PossessionSettings(switch_frames=1, loose_frames=3)
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200])]

    r.update(_ball(25, 100), players)  # con switch_frames=1, queda poseedor ya
    assert r.update(_ball(25, 100), players) == 1

    # Sin balón → tras loose_frames frames la posesión se declara suelta (None).
    assert r.update(None, players) == 1
    assert r.update(None, players) == 1
    assert r.update(None, players) is None


def test_clase5_sin_balon_cerca_usa_proximidad():
    """Clase 5 en un jugador lejano al balón se ignora; gana la proximidad."""
    s = PossessionSettings(switch_frames=3, class5_iou=0.3, class5_requires_ball=True)
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200]), _player(2, [300, 0, 350, 200])]
    ball = _ball(25, 100)  # cerca del jugador 1
    class5 = sv.Detections(xyxy=np.array([[300, 0, 350, 200]], dtype=np.float32))

    r.update(ball, players, class5)
    r.update(ball, players, class5)
    assert r.update(ball, players, class5) == 1


def test_clase5_con_balon_cerca_tiene_prioridad():
    s = PossessionSettings(switch_frames=3, class5_iou=0.3, class5_requires_ball=True)
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200]), _player(2, [300, 0, 350, 200])]
    ball = _ball(325, 100)  # cerca del jugador 2
    class5 = sv.Detections(xyxy=np.array([[300, 0, 350, 200]], dtype=np.float32))

    r.update(ball, players, class5)
    r.update(ball, players, class5)
    assert r.update(ball, players, class5) == 2


def test_clase5_rechazada_si_class5_requires_ball_desactivado_sin_balon():
    """Con ``class5_requires_ball=False`` la clase 5 manda aunque el balón esté lejos."""
    s = PossessionSettings(
        switch_frames=3, class5_iou=0.3, class5_requires_ball=False,
    )
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200]), _player(2, [100, 0, 150, 200])]
    ball = _ball(25, 100)
    class5 = sv.Detections(xyxy=np.array([[100, 0, 150, 200]], dtype=np.float32))

    r.update(ball, players, class5)
    r.update(ball, players, class5)
    assert r.update(ball, players, class5) == 2


def test_possession_frames_acumula_estadistica():
    s = PossessionSettings(switch_frames=1)
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200])]
    for _ in range(4):
        r.update(_ball(25, 100), players)
    # 1 frame "gana" la posesión, los 3 siguientes la mantienen y se cuentan.
    assert r.possession_frames().get(1, 0) == 4


def test_proximidad_suprimida_cerca_del_aro():
    s = PossessionSettings(switch_frames=1, max_ball_distance_heights=0.6)
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200])]
    ball = _ball(25, 100)
    rim = sv.Detections(xyxy=np.array([[10, 80, 40, 120]], dtype=np.float32))
    assert r.update(ball, players, hoop_detections=rim) is None


def test_reset_limpia_el_estado():
    r = PossessionResolver(PossessionSettings(switch_frames=1))
    players = [_player(1, [0, 0, 50, 200])]
    r.update(_ball(25, 100), players)
    r.reset()
    assert r.possession_frames() == {}
