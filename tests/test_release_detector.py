"""Tests del detector de suelta (estado puro, sin modelo de pose)."""

from __future__ import annotations

import numpy as np

from pipeline.config import PoseSettings, ReleaseSettings, Settings
from pipeline.scoring.release_detector import ReleaseDetector, ReleaseEvent


def _settings() -> ReleaseSettings:
    s = ReleaseSettings()
    s.enabled = True
    return s


def test_disabled_returns_none():
    det = ReleaseDetector(ReleaseSettings())  # enabled=False por defecto
    out = det.update(0, [np.array([100.0, 100.0])], np.array([100.0, 100.0]))
    assert out is None


def test_detects_release_when_ball_separates_upward():
    det = ReleaseDetector(_settings())
    wrist = np.array([500.0, 400.0])
    events = []
    # Fase 1: balón en la mano (pegado a la muñeca), unos frames.
    for f in range(0, 6):
        e = det.update(f, [wrist], np.array([505.0, 398.0]))
        if e:
            events.append(e)
    # Fase 2: suelta — el balón se aleja de la mano y sube (Y decrece).
    for k, f in enumerate(range(6, 12), start=1):
        ball = np.array([505.0 + 10 * k, 398.0 - 25 * k])  # se separa y sube
        e = det.update(f, [wrist], ball)
        if e:
            events.append(e)
    assert len(events) >= 1
    assert isinstance(events[0], ReleaseEvent)
    assert 0.0 < events[0].confidence <= 1.0


def test_no_release_while_dribbling_downward():
    det = ReleaseDetector(_settings())
    wrist = np.array([500.0, 400.0])
    fired = False
    for f in range(0, 12):
        # El balón baja (bote) y permanece cerca de la mano: no es suelta.
        ball = np.array([505.0, 400.0 + 5 * (f % 3)])
        if det.update(f, [wrist], ball):
            fired = True
    assert not fired


def test_no_release_if_never_held():
    det = ReleaseDetector(_settings())
    wrist = np.array([500.0, 400.0])
    fired = False
    # El balón siempre lejos de la mano (otro jugador) y subiendo: no hubo posesión.
    for k, f in enumerate(range(0, 10)):
        ball = np.array([900.0 + 10 * k, 600.0 - 25 * k])
        if det.update(f, [wrist], ball):
            fired = True
    assert not fired


def test_cooldown_prevents_double_fire():
    s = _settings()
    s.cooldown_frames = 20
    det = ReleaseDetector(s)
    wrist = np.array([500.0, 400.0])
    for f in range(0, 5):
        det.update(f, [wrist], np.array([502.0, 399.0]))
    n = 0
    for k, f in enumerate(range(5, 25), start=1):
        ball = np.array([500.0 + 12 * k, 399.0 - 28 * k])
        if det.update(f, [wrist], ball):
            n += 1
    assert n == 1  # una sola suelta pese a seguir separándose


def test_missing_ball_or_wrist_does_not_crash():
    det = ReleaseDetector(_settings())
    assert det.update(0, [], None) is None
    assert det.update(1, [np.array([100.0, 100.0])], None) is None
    assert det.update(2, [], np.array([100.0, 100.0])) is None


def test_settings_wired_into_global():
    s = Settings.default()
    assert isinstance(s.pose, PoseSettings)
    assert isinstance(s.release, ReleaseSettings)
    assert s.pose.enabled is False and s.release.enabled is False
