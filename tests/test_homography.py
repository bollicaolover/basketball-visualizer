"""Tests de la geometría de cancha (`pipeline/court/homography.py`).

Verifican la proyección imagen → mundo y que el estimador robusto recupera una
homografía conocida a partir de los 33 keypoints de la cancha. Usan datos
sintéticos perfectamente consistentes (sin ruido), así que el ajuste RANSAC
debe reconstruir la transformación con error de reproyección ~0.
"""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.config import CourtSettings
from pipeline.court.geometry import vertices_ft
from pipeline.court.homography import HomographyEstimator, project_image_points


def test_project_image_points_identidad():
    H = np.eye(3, dtype=np.float64)
    pts = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32)
    out = project_image_points(H, pts)
    assert np.allclose(out, pts, atol=1e-4)


def test_project_image_points_lista_vacia():
    H = np.eye(3, dtype=np.float64)
    out = project_image_points(H, np.zeros((0, 2), dtype=np.float32))
    assert out.shape == (0, 2)


def test_project_image_points_coincide_con_perspective_transform():
    # Homografía arbitraria con componente de perspectiva.
    H = np.array(
        [[8.0, 0.4, 100.0], [0.3, 9.0, 80.0], [1e-3, 5e-4, 1.0]], dtype=np.float64
    )
    pts = np.array([[5.0, 7.0], [40.0, 22.0], [70.0, 45.0]], dtype=np.float32)
    expected = cv2.perspectiveTransform(pts.reshape(-1, 1, 2), H).reshape(-1, 2)
    out = project_image_points(H, pts)
    assert np.allclose(out, expected, atol=1e-3)


def test_estimador_recupera_homografia_conocida():
    world = vertices_ft().astype(np.float64)        # (33, 2) cancha en pies
    assert world.shape[0] == 33

    # Homografía verdad mundo → imagen; los keypoints "detectados" son la
    # proyección perfecta de los vértices de la cancha a la imagen.
    H_world_to_img = np.array(
        [[8.0, 0.5, 120.0], [0.4, 9.0, 90.0], [1e-3, 8e-4, 1.0]], dtype=np.float64
    )
    img_kps = cv2.perspectiveTransform(
        world.reshape(-1, 1, 2).astype(np.float32), H_world_to_img
    ).reshape(-1, 2)

    estimator = HomographyEstimator(CourtSettings())
    estimate = estimator.update(img_kps.astype(np.float32), np.ones(33, dtype=bool))

    assert estimate.H is not None
    assert estimate.used_cached is False
    assert estimate.num_inliers >= CourtSettings().min_inliers
    assert estimate.residual_px < 1.0  # datos exactos → error de reproyección ~0

    # La H estimada (imagen → mundo) debe devolver los keypoints a los vértices.
    recovered_world = project_image_points(estimate.H, img_kps.astype(np.float32))
    assert np.allclose(recovered_world, world, atol=0.5)


def test_estimador_sin_keypoints_validos_no_da_homografia():
    estimator = HomographyEstimator(CourtSettings())
    estimate = estimator.update(
        np.zeros((33, 2), dtype=np.float32), np.zeros(33, dtype=bool)
    )
    assert estimate.H is None
    assert estimate.reject_reason is not None
