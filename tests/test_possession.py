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


# ---------------------------------------------------------------------------
# P1(a) — balón extrapolado (oclusión): no se crea poseedor nuevo
# ---------------------------------------------------------------------------
def test_predicted_ball_no_crea_poseedor_nuevo():
    s = PossessionSettings(switch_frames=1)
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200]), _player(2, [300, 0, 350, 200])]

    # El jugador 1 es el poseedor con balón real.
    r.update(_ball(25, 100), players)
    assert r._possessor == 1

    # El tracker arrastra (extrapola) el balón hasta el jugador 2 durante una
    # oclusión: con ``ball_predicted`` NO debe robarle la posesión al 1.
    out = r.update(_ball(325, 100), players, ball_predicted=True)
    assert out == 1


def test_predicted_ball_mantiene_al_poseedor_actual_si_sigue_cerca():
    s = PossessionSettings(switch_frames=1, loose_frames=2)
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200])]
    r.update(_ball(25, 100), players)
    # Balón extrapolado pero aún sobre el jugador 1 → se conserva, no se suelta.
    assert r.update(_ball(25, 100), players, ball_predicted=True) == 1


# ---------------------------------------------------------------------------
# P1(b) — balón en vuelo (rápido): no asigna posesión por proximidad
# ---------------------------------------------------------------------------
def test_balon_en_vuelo_no_asigna_por_proximidad():
    s = PossessionSettings(switch_frames=1, inflight_speed_heights=0.5)
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200])]  # altura 200 px
    ball = _ball(25, 100)                    # dentro del bbox
    # Velocidad 150 px/frame → 150/200 = 0.75 > 0.5 → en vuelo → sin poseedor.
    fast = np.array([150.0, 0.0], dtype=np.float32)
    assert r.update(ball, players, ball_velocity=fast) is None
    # La misma posición a velocidad baja sí asigna posesión.
    slow = np.array([10.0, 0.0], dtype=np.float32)
    assert r.update(ball, players, ball_velocity=slow) == 1


# ---------------------------------------------------------------------------
# P2 — clase 5 vale sola cuando no hay balón real (recorte/fuera de cuadro)
# ---------------------------------------------------------------------------
def test_clase5_sin_balon_real_se_acepta_sola():
    s = PossessionSettings(
        switch_frames=1, class5_iou=0.3,
        class5_requires_ball=True, class5_standalone_when_ball_missing=True,
    )
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200]), _player(2, [300, 0, 350, 200])]
    class5 = sv.Detections(xyxy=np.array([[300, 0, 350, 200]], dtype=np.float32))
    # Sin caja de balón: la clase 5 (jugador 2) manda por sí sola.
    assert r.update(None, players, class5) == 2


def test_clase5_balon_extrapolado_se_acepta_sola():
    s = PossessionSettings(
        switch_frames=1, class5_iou=0.3,
        class5_requires_ball=True, class5_standalone_when_ball_missing=True,
    )
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200]), _player(2, [300, 0, 350, 200])]
    ball = _ball(25, 100)  # caja del balón lejos del jugador 2...
    class5 = sv.Detections(xyxy=np.array([[300, 0, 350, 200]], dtype=np.float32))
    # ...pero está extrapolada (no real) → no se exige "balón cerca" → gana clase 5.
    assert r.update(ball, players, class5, ball_predicted=True) == 2


def test_clase5_standalone_desactivado_recupera_comportamiento_estricto():
    s = PossessionSettings(
        switch_frames=1, class5_iou=0.3,
        class5_requires_ball=True, class5_standalone_when_ball_missing=False,
    )
    r = PossessionResolver(s)
    players = [_player(1, [0, 0, 50, 200]), _player(2, [300, 0, 350, 200])]
    class5 = sv.Detections(xyxy=np.array([[300, 0, 350, 200]], dtype=np.float32))
    # Sin balón y sin modo standalone → clase 5 rechazada → sin poseedor.
    assert r.update(None, players, class5) is None


# ---------------------------------------------------------------------------
# P3 — desempate de proximidad: pegajosidad del poseedor en multitudes
# ---------------------------------------------------------------------------
def test_empate_proximidad_mantiene_al_poseedor_actual():
    s = PossessionSettings(switch_frames=1, tie_margin_heights=0.1)
    r = PossessionResolver(s)
    # Dos jugadores solapados; el balón equidista de ambos bordes.
    players = [_player(1, [0, 0, 100, 200]), _player(2, [100, 0, 200, 200])]
    # Frame 1: balón pegado al jugador 1 → poseedor 1.
    assert r.update(_ball(20, 100), players) == 1
    # Frame 2: balón justo en la frontera (empate de bordes). Sin pegajosidad el
    # nearest podría saltar al 2; con P3 el poseedor actual gana el empate.
    assert r.update(_ball(100, 100), players) == 1
