"""Tests del seguidor del balón con filtro de Kalman (método Pirotta) y del
selector entre las variantes ema / kalman."""

from __future__ import annotations

import numpy as np
import supervision as sv

from pipeline.config import BASKETBALL_CLASS, Settings
from pipeline.strategy.factory import build_ball_tracker
from pipeline.tracking.ball_tracker import BallTracker
from pipeline.tracking.ball_tracker_kalman import BALL_TRACK_ID, KalmanBallTracker


def _ball_det(cx: float, cy: float, conf: float = 0.9, size: float = 12.0) -> sv.Detections:
    half = size / 2.0
    return sv.Detections(
        xyxy=np.array([[cx - half, cy - half, cx + half, cy + half]], dtype=np.float32),
        confidence=np.array([conf], dtype=np.float32),
        class_id=np.array([BASKETBALL_CLASS], dtype=int),
    )


def _center(det: sv.Detections) -> np.ndarray:
    box = det.xyxy[0]
    return np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0])


# ---------------------------------------------------------------------------
# Selector
# ---------------------------------------------------------------------------
def test_factory_default_is_ema():
    s = Settings.default()
    assert s.ball_tracking.method == "ema"
    assert isinstance(build_ball_tracker(s), BallTracker)


def test_factory_returns_kalman():
    s = Settings.default()
    s.ball_tracking.method = "kalman"
    assert isinstance(build_ball_tracker(s), KalmanBallTracker)


def test_factory_rejects_unknown_method():
    s = Settings.default()
    s.ball_tracking.method = "bogus"
    try:
        build_ball_tracker(s)
    except ValueError:
        return
    raise AssertionError("se esperaba ValueError para method inválido")


# ---------------------------------------------------------------------------
# Comportamiento del filtro de Kalman
# ---------------------------------------------------------------------------
def test_tracks_moving_ball_and_assigns_stable_id():
    tracker = KalmanBallTracker()
    out = sv.Detections.empty()
    for i in range(8):
        out = tracker.update(_ball_det(100.0 + 5.0 * i, 200.0))
    assert len(out) == 1
    assert int(out.tracker_id[0]) == BALL_TRACK_ID
    assert int(out.class_id[0]) == BASKETBALL_CLASS
    # El centro estimado debe estar cerca de la última medición real.
    assert _center(out)[0] > 120.0


def test_holdover_extrapolates_during_occlusion():
    s = Settings.default().ball_tracking
    s.method = "kalman"
    s.holdover_frames = 5
    tracker = KalmanBallTracker(s)

    # Movimiento horizontal constante para fijar la velocidad del estado.
    last = sv.Detections.empty()
    for i in range(6):
        last = tracker.update(_ball_det(100.0 + 10.0 * i, 200.0))
    x_before = _center(last)[0]

    # Oclusión: sin detecciones, el tracker debe seguir devolviendo el balón
    # extrapolado por Kalman y avanzando en la dirección de la velocidad.
    occ = tracker.update(sv.Detections.empty())
    assert len(occ) == 1
    assert _center(occ)[0] > x_before


def test_holdover_expires_after_limit():
    s = Settings.default().ball_tracking
    s.method = "kalman"
    s.holdover_frames = 2
    tracker = KalmanBallTracker(s)
    for i in range(5):
        tracker.update(_ball_det(100.0 + 5.0 * i, 200.0))
    # Más frames vacíos que holdover_frames ⇒ se pierde el balón.
    for _ in range(s.holdover_frames + 1):
        out = tracker.update(sv.Detections.empty())
    assert len(out) == 0


def test_validation_rejects_noise_trajectory():
    s = Settings.default().ball_tracking
    s.method = "kalman"
    s.validate_trajectory = True
    s.validate_every = 5
    s.min_tracklet_len = 10
    s.max_fit_residual_px = 25.0
    s.match_distance_px = 1e9  # desactivamos el gating para forzar la validación
    tracker = KalmanBallTracker(s)

    rng = np.random.default_rng(0)
    n = 20
    for _ in range(n):
        # Posiciones aleatorias dispersas: no se ajustan a recta/parábola.
        cx = float(rng.uniform(0, 1000))
        cy = float(rng.uniform(0, 1000))
        tracker.update(_ball_det(cx, cy))
    # La validación reinicia el tracklet de ruido: tras un reset ``_frame_count``
    # vuelve a 0, por lo que debe quedar por debajo del nº de frames procesados.
    assert tracker._frame_count < n


def test_validation_accepts_parabolic_trajectory():
    s = Settings.default().ball_tracking
    s.method = "kalman"
    s.validate_trajectory = True
    s.validate_every = 5
    tracker = KalmanBallTracker(s)

    out = sv.Detections.empty()
    for t in range(20):
        # Recta en X, parábola en Y (vuelo de balón en coordenadas imagen).
        cx = 100.0 + 8.0 * t
        cy = 300.0 - 6.0 * t + 0.5 * t * t
        out = tracker.update(_ball_det(cx, cy))
    # Una trayectoria física limpia no debe reiniciarse: el balón sigue presente.
    assert len(out) == 1


def test_empty_input_returns_empty():
    tracker = KalmanBallTracker()
    assert len(tracker.update(sv.Detections.empty())) == 0
