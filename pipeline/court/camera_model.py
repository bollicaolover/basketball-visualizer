"""Estimador de homografía vía modelo de cámara paramétrico (PnP + Kalman).

Alternativa a :class:`HomographyEstimator` (findHomography). En lugar de
resolver una H 3×3 con 8 grados de libertad arbitrarios, estima la **pose
física** de la cámara con ``cv2.solvePnP`` sobre los puntos de cancha (planares,
Z=0) y reconstruye la H a partir de esa pose. Una cámara de retransmisión tiene
~4 grados de libertad reales (pan, tilt, zoom, roll≈0), así que restringir la
estimación a la pose la hace mucho más estable y físicamente plausible.

Diseño (ver ``CourtSettings`` para el porqué de cada parámetro):

1. **Intrínsecos K**: punto principal en el centro de imagen; focal ``f``
   (``fx=fy``) auto-estimada **una sola vez** al arranque a partir de varias H
   bien condicionadas (descomposición de la homografía planar, Zhang) y luego
   fijada. Asume zoom mínimo. Se puede forzar con ``pnp_focal_override``.

2. **PnP por frame** (``SOLVEPNP_IPPE``, específico para objetivos planares) +
   refinamiento LM sobre los inliers.

3. **Filtro de Kalman** (velocidad constante) sobre ``[rvec, tvec]``: suaviza el
   temblor y **predice** durante panes/oclusiones (frames sin medición PnP).

4. **Fallback**: durante la calibración de focal, cuando hay pocos keypoints, o
   cuando PnP falla más allá del holdover, se delega en el
   :class:`HomographyEstimator` clásico. Así el estimador nunca queda peor que
   la ruta probada.

Produce el mismo :class:`HomographyEstimate` (con H imagen→cancha en pies) que
consume el resto del pipeline, de modo que es intercambiable en el orquestador.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np

from pipeline.config import CourtSettings
from pipeline.court.geometry import vertices_ft_3d
from pipeline.court.homography import (
    HomographyEstimate,
    HomographyEstimator,
    _reprojection_residual_px,
)
from pipeline.court.segments import CameraSegmentTracker

_LOG = logging.getLogger(__name__)

_EPS = 1e-9


class PnPCameraEstimator:
    """Estima H vía pose de cámara (PnP) + Kalman, con fallback a RANSAC.

    Interfaz idéntica a :class:`HomographyEstimator`: ``update(kp_xy,
    valid_mask) -> HomographyEstimate`` y ``reset()``. Antes del primer
    ``update`` hay que fijar el tamaño de imagen con ``set_image_size`` para
    situar el punto principal; si no se hace, el estimador opera siempre en
    modo fallback (degradación segura).
    """

    def __init__(self, settings: CourtSettings) -> None:
        self._s = settings
        self._world_3d = vertices_ft_3d().astype(np.float64)  # (33, 3)

        # Fallback clásico (también motor de la fase de calibración de focal).
        self._fallback = HomographyEstimator(settings)
        # Detección de pan/corte → reset del Kalman.
        self._seg_tracker = CameraSegmentTracker(settings)

        # Intrínsecos (se completan en set_image_size / calibración).
        self._cx: Optional[float] = None
        self._cy: Optional[float] = None
        self._focal: Optional[float] = None
        self._K: Optional[np.ndarray] = None

        # Acumulador de candidatos de focal² durante la calibración.
        self._focal_samples: List[float] = []
        self._calib_frames: int = 0

        # Kalman (pose 6D + velocidad 6D).
        self._kf = self._build_kalman()
        self._kf_init: bool = False
        self._holdover: int = 0

        # Cache del último fit válido (para HomographyEstimate.used_cached).
        self._last_conf: float = 0.0
        self._last_inliers: int = 0
        self._last_residual: float = float("inf")

        # Matriz de proyección 3x4 P = K·[R | t] del último fit por pose. A
        # diferencia de la homografía (que descarta la columna Z para el plano
        # del suelo), P conserva la dimensión vertical y permite reconstruir
        # posiciones 3D del balón (método del cap. 5 de Pirotta).
        self._last_P: Optional[np.ndarray] = None

        if settings.pnp_focal_override > 0.0:
            self._focal = float(settings.pnp_focal_override)

    # ------------------------------------------------------------------
    def set_image_size(self, width: int, height: int) -> None:
        """Fija el punto principal (centro de imagen) y construye K si hay focal."""
        self._cx = float(width) / 2.0
        self._cy = float(height) / 2.0
        if self._focal is not None:
            self._K = self._build_K(self._focal)

    def reset(self) -> None:
        self._fallback.reset()
        self._seg_tracker.reset()
        self._kf_init = False
        self._holdover = 0
        self._last_conf = 0.0
        self._last_inliers = 0
        self._last_residual = float("inf")
        self._last_P = None
        # La focal y el punto principal NO se resetean: son globales del vídeo.

    def projection_matrix(self) -> Optional[np.ndarray]:
        """Matriz de proyección 3x4 P = K·[R|t] del último fit por pose, en
        unidades de cancha (pies). ``None`` si aún no hay pose válida (focal sin
        calibrar o PnP fallido sin holdover). Necesaria para la reconstrucción
        3D del balón (``pipeline.court.ball_3d``)."""
        return None if self._last_P is None else self._last_P.copy()

    def intrinsics(self) -> Optional[np.ndarray]:
        """Matriz de intrínsecos K (3x3) si la focal ya está calibrada."""
        return None if self._K is None else self._K.copy()

    def solve_projection(
        self, kp_xy: np.ndarray, valid_mask: np.ndarray,
    ) -> Optional[np.ndarray]:
        """Calcula P = K·[R|t] para *este* frame con un PnP plano y tolerante.

        Pensado para la reconstrucción 3D offline: a diferencia de ``update()``
        (que exige un RANSAC a ``pnp_ransac_reproj_px`` ≈ 5 px y por eso casi
        nunca se activa con keypoints de retransmisión ruidosos), aquí se usa
        ``cv2.solvePnP`` IPPE directo sobre los puntos válidos. Devuelve la P en
        unidades de cancha (pies) o ``None`` si falta calibración o hay < 4
        puntos. No modifica el estado del estimador en vivo."""
        if self._K is None or int(valid_mask.sum()) < 4:
            return None
        obj = self._world_3d[valid_mask].astype(np.float64)
        img = kp_xy[valid_mask].astype(np.float64)
        try:
            ok, rvec, tvec = cv2.solvePnP(
                obj, img, self._K, None, flags=cv2.SOLVEPNP_IPPE,
            )
        except cv2.error:
            return None
        if not ok:
            return None
        R, _ = cv2.Rodrigues(rvec)
        return (self._K @ np.column_stack([R, tvec.reshape(3)])).astype(np.float64)

    # ------------------------------------------------------------------
    def update(
        self,
        kp_xy: np.ndarray,
        valid_mask: np.ndarray,
    ) -> HomographyEstimate:
        """Estima H para este frame vía PnP+Kalman, con fallback a RANSAC."""
        # Pan/corte de cámara → el Kalman parte de cero tras el movimiento.
        if self._seg_tracker.update(kp_xy, valid_mask):
            self._kf_init = False
            self._holdover = 0

        # Sin punto principal o sin focal aún: fase de calibración / fallback.
        if self._K is None:
            return self._calibration_step(kp_xy, valid_mask)

        # Focal fijada: intentar PnP.
        pnp = self._solve_pnp(kp_xy, valid_mask)
        if pnp is None:
            return self._pnp_failed(kp_xy, valid_mask)

        rvec, tvec, num_inliers = pnp
        rvec_f, tvec_f = self._kalman_correct(rvec, tvec)
        self._holdover = 0
        return self._estimate_from_pose(
            rvec_f, tvec_f, kp_xy, valid_mask, num_inliers, used_cached=False,
        )

    # ------------------------------------------------------------------
    # Fase de calibración de focal (delega en el fallback y muestrea f²)
    # ------------------------------------------------------------------
    def _calibration_step(
        self, kp_xy: np.ndarray, valid_mask: np.ndarray,
    ) -> HomographyEstimate:
        est = self._fallback.update(kp_xy, valid_mask)

        # Si ya tenemos focal por override pero faltaba el punto principal,
        # en cuanto set_image_size construya K saldremos de aquí solos.
        if self._focal is not None:
            return est

        # Sólo muestreamos de fits nuevos y limpios.
        if (
            self._cx is not None
            and est.H is not None
            and not est.used_cached
            and np.isfinite(est.residual_px)
            and est.residual_px <= self._s.max_residual_px
        ):
            cands = self._focal_candidates(est.H)
            if cands:
                self._focal_samples.extend(cands)
                self._calib_frames += 1

        if self._calib_frames >= self._s.pnp_focal_calib_frames and self._focal_samples:
            f2 = float(np.median(self._focal_samples))
            if f2 > 0.0:
                self._focal = float(np.sqrt(f2))
                self._K = self._build_K(self._focal)
                _LOG.info(
                    "PnPCameraEstimator: focal fijada f=%.1f px tras %d frames",
                    self._focal, self._calib_frames,
                )
        return est

    def _focal_candidates(self, H_i2w: np.ndarray) -> List[float]:
        """Candidatos de focal² desde una H imagen→mundo (Zhang, plano).

        H_w2i = inv(H_i2w) = λ·K·[r1 r2 t]. Trasladando el punto principal al
        origen (T·H_w2i), con K=diag(f,f,1), las restricciones de ortonormalidad
        de r1, r2 dan dos estimaciones independientes de f².
        """
        try:
            H_w2i = np.linalg.inv(H_i2w)
        except np.linalg.LinAlgError:
            return []
        cx, cy = self._cx, self._cy
        T = np.array([[1.0, 0.0, -cx], [0.0, 1.0, -cy], [0.0, 0.0, 1.0]])
        Hp = T @ H_w2i
        h1 = Hp[:, 0]
        h2 = Hp[:, 1]

        out: List[float] = []
        # r1 ⊥ r2
        denom = h1[2] * h2[2]
        if abs(denom) > _EPS:
            f2 = -(h1[0] * h2[0] + h1[1] * h2[1]) / denom
            if np.isfinite(f2) and f2 > 0.0:
                out.append(float(f2))
        # |r1| = |r2|
        denom = h1[2] ** 2 - h2[2] ** 2
        if abs(denom) > _EPS:
            f2 = ((h2[0] ** 2 + h2[1] ** 2) - (h1[0] ** 2 + h1[1] ** 2)) / denom
            if np.isfinite(f2) and f2 > 0.0:
                out.append(float(f2))
        return out

    # ------------------------------------------------------------------
    # PnP
    # ------------------------------------------------------------------
    def _solve_pnp(
        self, kp_xy: np.ndarray, valid_mask: np.ndarray,
    ) -> Optional[Tuple[np.ndarray, np.ndarray, int]]:
        if int(valid_mask.sum()) < self._s.pnp_min_points:
            return None
        obj = self._world_3d[valid_mask]                       # (n, 3)
        img = kp_xy[valid_mask].astype(np.float64)             # (n, 2)

        try:
            ok, rvec, tvec, inliers = cv2.solvePnPRansac(
                obj, img, self._K, None,
                reprojectionError=float(self._s.pnp_ransac_reproj_px),
                flags=cv2.SOLVEPNP_IPPE,
            )
        except cv2.error:
            return None
        if not ok or rvec is None or tvec is None:
            return None

        num_inliers = int(len(inliers)) if inliers is not None else int(valid_mask.sum())
        if num_inliers < self._s.pnp_min_points:
            return None

        # Refinamiento LM sobre los inliers (más preciso que el RANSAC crudo).
        if inliers is not None and num_inliers >= 4:
            idx = inliers.ravel()
            try:
                rvec, tvec = cv2.solvePnPRefineLM(
                    obj[idx], img[idx], self._K, None, rvec, tvec,
                )
            except cv2.error:
                pass
        return rvec.reshape(3), tvec.reshape(3), num_inliers

    def _pnp_failed(
        self, kp_xy: np.ndarray, valid_mask: np.ndarray,
    ) -> HomographyEstimate:
        """PnP no resolvió: predicción del Kalman dentro del holdover, o fallback."""
        if self._kf_init and self._holdover < self._s.pnp_max_holdover_frames:
            self._holdover += 1
            rvec_f, tvec_f = self._kalman_predict_only()
            return self._estimate_from_pose(
                rvec_f, tvec_f, kp_xy, valid_mask, self._last_inliers,
                used_cached=True,
            )
        return self._fallback.update(kp_xy, valid_mask)

    # ------------------------------------------------------------------
    # Reconstrucción de H desde la pose
    # ------------------------------------------------------------------
    def _estimate_from_pose(
        self,
        rvec: np.ndarray,
        tvec: np.ndarray,
        kp_xy: np.ndarray,
        valid_mask: np.ndarray,
        num_inliers: int,
        used_cached: bool,
    ) -> HomographyEstimate:
        R, _ = cv2.Rodrigues(rvec)
        # Matriz de proyección completa mundo(pies)→imagen: P = K·[R | t] (3x4).
        self._last_P = (self._K @ np.column_stack([R, tvec])).astype(np.float64)
        H_w2i = self._K @ np.column_stack([R[:, 0], R[:, 1], tvec])
        try:
            H_i2w = np.linalg.inv(H_w2i)
        except np.linalg.LinAlgError:
            return self._fallback.update(kp_xy, valid_mask)
        if abs(H_i2w[2, 2]) < _EPS or not np.all(np.isfinite(H_i2w)):
            return self._fallback.update(kp_xy, valid_mask)
        H_i2w = H_i2w / H_i2w[2, 2]

        src = kp_xy[valid_mask].astype(np.float32)
        dst = self._world_3d[valid_mask, :2].astype(np.float32)
        residual = _reprojection_residual_px(H_i2w, src, dst)
        conf = self._fit_confidence(num_inliers, residual)

        self._last_conf = conf
        self._last_inliers = num_inliers
        self._last_residual = residual
        return HomographyEstimate(
            H=H_i2w.astype(np.float64),
            confidence=conf,
            num_inliers=num_inliers,
            residual_px=residual,
            used_cached=used_cached,
            reject_reason=None,
        )

    def _fit_confidence(self, num_inliers: int, residual_px: float) -> float:
        """Misma combinación que HomographyEstimator: inliers + residual."""
        max_kps = self._world_3d.shape[0]
        ratio = min(num_inliers / max_kps, 1.0)
        res_term = max(0.0, 1.0 - residual_px / max(1e-6, self._s.max_residual_px))
        return 0.6 * ratio + 0.4 * res_term

    # ------------------------------------------------------------------
    # Kalman (cv2.KalmanFilter, velocidad constante)
    # ------------------------------------------------------------------
    def _build_kalman(self) -> cv2.KalmanFilter:
        kf = cv2.KalmanFilter(12, 6)
        # Transición: pose_{t} = pose_{t-1} + vel_{t-1}; vel constante (dt=1).
        A = np.eye(12, dtype=np.float32)
        for i in range(6):
            A[i, i + 6] = 1.0
        kf.transitionMatrix = A
        # Medición: observamos las 6 componentes de pose, no las velocidades.
        Hm = np.zeros((6, 12), dtype=np.float32)
        for i in range(6):
            Hm[i, i] = 1.0
        kf.measurementMatrix = Hm

        q_rot = float(self._s.kf_process_noise_rot)
        q_trans = float(self._s.kf_process_noise_trans)
        q = np.empty(12, dtype=np.float32)
        q[0:3] = q_rot
        q[3:6] = q_trans
        q[6:9] = q_rot
        q[9:12] = q_trans
        kf.processNoiseCov = np.diag(q)

        r = np.empty(6, dtype=np.float32)
        r[0:3] = float(self._s.kf_measure_noise_rot)
        r[3:6] = float(self._s.kf_measure_noise_trans)
        kf.measurementNoiseCov = np.diag(r)

        kf.errorCovPost = np.eye(12, dtype=np.float32)
        return kf

    def _kalman_correct(
        self, rvec: np.ndarray, tvec: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Inicializa o corrige el Kalman con la medición de PnP.

        Caveat: el rvec se filtra linealmente. Es válido aquí porque la
        rotación inter-frame de una cámara de retransmisión es pequeña; en
        ese régimen el espacio de rotación-vector es localmente lineal.
        """
        meas = np.concatenate([rvec, tvec]).astype(np.float32).reshape(6, 1)
        if not self._kf_init:
            state = np.zeros((12, 1), dtype=np.float32)
            state[0:6, 0] = meas[:, 0]
            self._kf.statePost = state
            self._kf.errorCovPost = np.eye(12, dtype=np.float32)
            self._kf_init = True
            return rvec.copy(), tvec.copy()
        self._kf.predict()
        corrected = self._kf.correct(meas)
        return corrected[0:3, 0].astype(np.float64), corrected[3:6, 0].astype(np.float64)

    def _kalman_predict_only(self) -> Tuple[np.ndarray, np.ndarray]:
        """Avanza el Kalman sin medición (PnP fallido dentro del holdover)."""
        predicted = self._kf.predict()
        # Mantén el statePost coherente con la predicción para el siguiente paso.
        self._kf.statePost = predicted.copy()
        return predicted[0:3, 0].astype(np.float64), predicted[3:6, 0].astype(np.float64)

    # ------------------------------------------------------------------
    @staticmethod
    def _build_K_static(focal: float, cx: float, cy: float) -> np.ndarray:
        return np.array(
            [[focal, 0.0, cx], [0.0, focal, cy], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )

    def _build_K(self, focal: float) -> Optional[np.ndarray]:
        if self._cx is None or self._cy is None:
            return None
        return self._build_K_static(focal, self._cx, self._cy)
