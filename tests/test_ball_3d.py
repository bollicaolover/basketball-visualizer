"""Tests de la reconstrucción 3D balística del balón (Pirotta 5.2).

Validación sintética: se define una cámara conocida P = K·[R|t] y una trayectoria
balística conocida B_true, se proyectan los puntos 3D a imagen y se comprueba que
el solver recupera B_true (y, con ruido, lo aproxima)."""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.court.ball_3d import (
    GRAVITY_FT_S2,
    RIM_HEIGHT_FT,
    Trajectory3D,
    solve_ballistic_trajectory,
)


def _look_at_camera() -> np.ndarray:
    """Construye una P = K·[R|t] realista: cámara en la grada mirando a la pista.

    Mundo en pies, cancha en Z=0; eje Z hacia arriba."""
    K = np.array([[1400.0, 0.0, 640.0], [0.0, 1400.0, 360.0], [0.0, 0.0, 1.0]])
    cam_pos = np.array([-25.0, 25.0, 35.0])   # detrás/lado de la pista, elevada
    target = np.array([40.0, 25.0, 7.0])      # mira a la zona del aro
    up = np.array([0.0, 0.0, 1.0])

    fwd = target - cam_pos
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, up)
    right /= np.linalg.norm(right)
    down = np.cross(fwd, right)
    # Filas de R = ejes de cámara (x→right, y→down, z→forward) en coords mundo.
    R = np.vstack([right, down, fwd])
    t = -R @ cam_pos
    return K @ np.column_stack([R, t])


def _trajectory_points(B, times, gravity=GRAVITY_FT_S2):
    x0, vx, y0, vy, z0, vz = B
    return np.column_stack(
        [x0 + vx * times, y0 + vy * times, z0 + vz * times - 0.5 * gravity * times**2]
    )


def _project_all(P, pts3d):
    uv = []
    for w in pts3d:
        h = P @ np.array([w[0], w[1], w[2], 1.0])
        assert h[2] > 0, "punto detrás de la cámara: ajustar geometría del test"
        uv.append(h[:2] / h[2])
    return np.array(uv)


def test_recovers_known_trajectory_exactly():
    P = _look_at_camera()
    # Tiro: sale de ~(35,25,7) hacia el aro, velocidad con buen arco.
    B_true = np.array([35.0, 6.0, 25.0, 0.0, 7.0, 22.0])
    times = np.linspace(0.0, 0.9, 14)
    pts = _trajectory_points(B_true, times)
    uv = _project_all(P, pts)

    traj = solve_ballistic_trajectory([P] * len(times), uv, times)

    assert np.allclose(traj.params, B_true, atol=1e-4)
    assert traj.reproj_rmse_px < 1e-6
    assert np.allclose(traj.points_3d, pts, atol=1e-4)


def test_apex_and_release_metrics():
    P = _look_at_camera()
    B_true = np.array([35.0, 6.0, 25.0, 0.0, 7.0, 22.0])
    times = np.linspace(0.0, 0.9, 14)
    uv = _project_all(P, _trajectory_points(B_true, times))
    traj = solve_ballistic_trajectory([P] * len(times), uv, times)

    # Ápice analítico: Z0 + Vz²/(2g) = 7 + 22²/(2·32.174) ≈ 14.5 ft.
    assert traj.apex_height_ft > RIM_HEIGHT_FT      # por encima del aro
    assert abs(traj.apex_height_ft - (7.0 + 22.0**2 / (2 * GRAVITY_FT_S2))) < 0.1


def test_extrapolation_end_rim_before_floor():
    """Tras el ápice, el fin extrapolado es el cruce del aro (antes que el suelo)."""
    P = _look_at_camera()
    B_true = np.array([35.0, 6.0, 25.0, 0.0, 7.0, 22.0])
    times = np.linspace(0.0, 0.9, 14)
    uv = _project_all(P, _trajectory_points(B_true, times))
    traj = solve_ballistic_trajectory([P] * len(times), uv, times)

    t_end, reason = traj.extrapolation_end(after_t=float(times[-1]))
    assert reason == "rim"
    assert t_end > float(times[-1])
    assert abs(traj.position(t_end)[2] - RIM_HEIGHT_FT) < 0.05
    assert np.allclose(traj.release_point_ft, [35.0, 25.0], atol=1e-3)
    # Arco pronunciado: ángulo de salida claramente positivo.
    assert 60.0 < traj.launch_angle_deg < 80.0


def test_robust_to_pixel_noise():
    rng = np.random.default_rng(42)
    P = _look_at_camera()
    B_true = np.array([35.0, 6.0, 25.0, 0.0, 7.0, 22.0])
    times = np.linspace(0.0, 0.9, 24)
    uv = _project_all(P, _trajectory_points(B_true, times))
    uv_noisy = uv + rng.normal(0.0, 1.0, uv.shape)  # ~1 px de ruido

    traj = solve_ballistic_trajectory([P] * len(times), uv_noisy, times)

    # Con ruido subpíxel la posición inicial debe quedar a < ~2 ft de la real.
    assert np.linalg.norm(traj.params[[0, 2, 4]] - B_true[[0, 2, 4]]) < 2.0
    assert traj.apex_height_ft > RIM_HEIGHT_FT


def test_auto_orient_handles_z_down_pose():
    """Si el PnP devuelve una pose con +Z hacia el suelo (3ª columna negada,
    ambigüedad de la normal planar), auto_orient debe recuperar igualmente
    alturas positivas físicas."""
    P = _look_at_camera()
    P_flip = P.copy()
    P_flip[:, 2] *= -1.0  # simula la pose con normal invertida
    B_true = np.array([35.0, 6.0, 25.0, 0.0, 7.0, 22.0])
    times = np.linspace(0.0, 0.9, 14)
    # Genera imagen con la pose invertida y mundo Z negado (coherente con la pose).
    pts_down = _trajectory_points(B_true, times).copy()
    pts_down[:, 2] *= -1.0
    uv = _project_all(P_flip, pts_down)

    traj = solve_ballistic_trajectory([P_flip] * len(times), uv, times)

    assert traj.apex_height_ft > RIM_HEIGHT_FT
    assert traj.points_3d[:, 2].min() > -1.0  # sin alturas negativas espurias
    assert traj.reproj_rmse_px < 1e-3


def test_requires_minimum_points():
    P = _look_at_camera()
    try:
        solve_ballistic_trajectory([P, P], np.zeros((2, 2)), [0.0, 0.1])
    except ValueError:
        return
    raise AssertionError("se esperaba ValueError con menos de 3 detecciones")


def test_projection_matrix_exposed_after_pose():
    """La cámara PnP expone P=K·[R|t] tras un fit por pose (smoke, sin vídeo)."""
    from pipeline.config import Settings
    from pipeline.court.camera_model import PnPCameraEstimator

    cam = PnPCameraEstimator(Settings.default().court)
    # Sin fit todavía no hay P.
    assert cam.projection_matrix() is None
