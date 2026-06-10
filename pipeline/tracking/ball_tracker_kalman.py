"""Tracking del balón con filtro de Kalman y validación física de la trayectoria.

Implementación inspirada en la metodología de Luca Pirotta (*"Ball Detection and
Tracking in a Basketball Scene"*, cap. 4). La tesis detecta candidatos por
movimiento (GMM) y los filtra por forma; aquí esa etapa la sustituye el detector
profundo RF-DETR, que ya entrega ``sv.Detections`` de la clase balón. Lo que se
adopta de Pirotta es la parte de **seguimiento**:

* Filtro de Kalman con modelo de velocidad constante (ecuación 4.13 de la tesis)
  para predecir la posición del balón y sobrevivir a oclusiones.
* Validación geométrica del histórico de la trayectoria: una **recta en X** frente
  al tiempo y una **parábola en Y** frente al tiempo (sección 4.2.1). Los tracklets
  de longitud < 10 se descartan a priori y los que se ajustan mal a la física se
  reinician para no propagar falsos positivos.

Mantiene la misma interfaz pública que :class:`pipeline.tracking.ball_tracker.BallTracker`
(``update(detections) -> sv.Detections`` y ``reset()``) para poder intercambiarlos
y compararlos sin tocar el resto del pipeline.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import supervision as sv

from pipeline.config import BALL_CLASSES, BASKETBALL_CLASS, BallTrackingSettings

# Mismo identificador estable que el tracker EMA: el balón es único, así el resto
# del pipeline (posesión, render) no distingue qué backend lo produjo.
BALL_TRACK_ID = 9000


class KalmanBallTracker:
    """Seguidor del balón basado en filtro de Kalman + validación de trayectoria."""

    def __init__(self, settings: Optional[BallTrackingSettings] = None) -> None:
        self._s = settings or BallTrackingSettings()

        # Modelo de evolución del estado [x, y, vx, vy] con velocidad constante
        # (matriz A) y matriz de observación H que mide solo la posición (eq. 4.13).
        self.A = np.array(
            [
                [1, 0, 1, 0],
                [0, 1, 0, 1],
                [0, 0, 1, 0],
                [0, 0, 0, 0],
            ],
            dtype=np.float64,
        )
        self.H = np.array(
            [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
            ],
            dtype=np.float64,
        )
        # Covarianzas de ruido de proceso (Q) y de medición (R).
        self.Q = np.eye(4, dtype=np.float64) * self._s.kalman_process_noise
        self.R = np.eye(2, dtype=np.float64) * self._s.kalman_measurement_noise

        self.reset()

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._box: Optional[np.ndarray] = None
        self._confidence: float = 0.0
        self._frames_missing: int = 0

        # Estado del filtro de Kalman: x = [x, y, vx, vy]^T y su covarianza P.
        self.x_state: Optional[np.ndarray] = None
        self.P_cov: Optional[np.ndarray] = None

        # Histórico de la trayectoria actual para el ajuste recta/parábola.
        self._hist_x: List[float] = []
        self._hist_y: List[float] = []
        self._hist_t: List[int] = []
        self._frame_count: int = 0

    @staticmethod
    def _center_from_box(box: np.ndarray) -> np.ndarray:
        return np.array(
            [(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0],
            dtype=np.float64,
        )

    # ------------------------------------------------------------------
    # Filtro de Kalman
    # ------------------------------------------------------------------
    def _init_kalman(self, center: np.ndarray) -> None:
        self.x_state = np.array([center[0], center[1], 0.0, 0.0], dtype=np.float64)
        self.P_cov = np.eye(4, dtype=np.float64) * self._s.kalman_initial_cov

    def _kalman_predict(self) -> np.ndarray:
        """Paso de predicción (time update). Devuelve la posición estimada (x, y)."""
        self.x_state = self.A @ self.x_state
        self.P_cov = self.A @ self.P_cov @ self.A.T + self.Q
        return self.x_state[:2]

    def _kalman_correct(self, measurement: np.ndarray) -> None:
        """Paso de corrección (measurement update) con la detección observada."""
        S = self.H @ self.P_cov @ self.H.T + self.R
        K = self.P_cov @ self.H.T @ np.linalg.inv(S)
        residual = measurement - (self.H @ self.x_state)
        self.x_state = self.x_state + K @ residual
        self.P_cov = (np.eye(4, dtype=np.float64) - K @ self.H) @ self.P_cov

    # ------------------------------------------------------------------
    # Validación física de la trayectoria (sección 4.2.1)
    # ------------------------------------------------------------------
    def _validate_trajectory(self) -> bool:
        """Ajusta una recta en X y una parábola en Y; rechaza el histórico si no
        encaja con la física del balón.

        Devuelve ``True`` si la trayectoria es plausible (o si aún no hay puntos
        suficientes para juzgarla)."""
        if len(self._hist_t) < self._s.min_tracklet_len:
            # Tracklet demasiado corto para validar: no lo damos por inválido todavía.
            return True

        t = np.asarray(self._hist_t, dtype=np.float64)
        x = np.asarray(self._hist_x, dtype=np.float64)
        y = np.asarray(self._hist_y, dtype=np.float64)
        n = len(t)

        # Recta en X: x = a·t + b ; parábola en Y: y = a·t² + b·t + c.
        _, res_x, *_ = np.polyfit(t, x, 1, full=True)
        poly_y, res_y, *_ = np.polyfit(t, y, 2, full=True)

        mse_x = float(res_x[0] / n) if res_x.size else 0.0
        mse_y = float(res_y[0] / n) if res_y.size else 0.0
        if mse_x > self._s.max_fit_residual_px or mse_y > self._s.max_fit_residual_px:
            return False

        if self._s.require_parabola:
            # En coordenadas imagen Y crece hacia abajo: la gravedad hace que la
            # parábola del vuelo del balón abra hacia arriba (coeficiente > 0).
            if poly_y[0] <= 0:
                return False

        return True

    # ------------------------------------------------------------------
    # Selección de candidato
    # ------------------------------------------------------------------
    def _pick(
        self, detections: sv.Detections, predicted_center: Optional[np.ndarray]
    ) -> Optional[int]:
        if detections is None or len(detections) == 0:
            return None
        ball_mask = np.isin(detections.class_id, list(BALL_CLASSES))
        if not ball_mask.any():
            return None

        confidences = (
            detections.confidence
            if detections.confidence is not None
            else np.ones(len(detections), dtype=np.float32)
        )
        indices = np.where(ball_mask)[0]

        gated_best: Optional[int] = None
        gated_score = -1.0
        free_best: Optional[int] = None
        free_score = -1.0
        for i in indices:
            conf = float(confidences[i])
            if conf < self._s.min_confidence:
                continue
            if conf > free_score:
                free_score = conf
                free_best = int(i)
            if predicted_center is not None:
                center = self._center_from_box(detections.xyxy[i])
                dist = float(np.linalg.norm(center - predicted_center))
                if dist > self._s.match_distance_px:
                    continue
            if conf > gated_score:
                gated_score = conf
                gated_best = int(i)

        # Preferimos un candidato dentro del radio de gating de la predicción de
        # Kalman; si no hay ninguno (pase largo, reaparición), el más confiable.
        return gated_best if gated_best is not None else free_best

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------
    def update(self, detections: sv.Detections) -> sv.Detections:
        self._frame_count += 1

        predicted_center: Optional[np.ndarray] = None
        if self.x_state is not None:
            predicted_center = self._kalman_predict()

        pick = self._pick(detections, predicted_center)

        # --- Oclusión / pérdida del candidato: holdover con la predicción ---
        if pick is None:
            self._frames_missing += 1
            if (
                self.x_state is None
                or self._box is None
                or self._frames_missing > self._s.holdover_frames
            ):
                self.reset()
                return sv.Detections.empty()
            # Reproyectamos la caja en torno al centro estimado por Kalman,
            # conservando el tamaño de la última detección real.
            half_w = (self._box[2] - self._box[0]) / 2.0
            half_h = (self._box[3] - self._box[1]) / 2.0
            cx, cy = float(self.x_state[0]), float(self.x_state[1])
            self._box = np.array(
                [cx - half_w, cy - half_h, cx + half_w, cy + half_h],
                dtype=np.float32,
            )
            return self._as_detections()

        # --- Candidato encontrado: corrección del filtro ---
        box = detections.xyxy[pick].astype(np.float32)
        conf = float(
            detections.confidence[pick] if detections.confidence is not None else 1.0
        )
        center = self._center_from_box(box)

        if self.x_state is None:
            self._init_kalman(center)
        else:
            self._kalman_correct(center)

        # El estado corregido es la mejor estimación de la posición del balón;
        # centramos la caja en él para que la salida quede suavizada por Kalman.
        cx, cy = float(self.x_state[0]), float(self.x_state[1])
        half_w = (box[2] - box[0]) / 2.0
        half_h = (box[3] - box[1]) / 2.0
        self._box = np.array(
            [cx - half_w, cy - half_h, cx + half_w, cy + half_h],
            dtype=np.float32,
        )
        self._confidence = conf
        self._frames_missing = 0

        # Histórico para la validación geométrica retrospectiva.
        self._hist_x.append(cx)
        self._hist_y.append(cy)
        self._hist_t.append(self._frame_count)

        if (
            self._s.validate_trajectory
            and len(self._hist_t) >= self._s.min_tracklet_len
            and len(self._hist_t) % max(1, self._s.validate_every) == 0
            and not self._validate_trajectory()
        ):
            # La trayectoria viola la recta/parábola física: limpiamos para evitar
            # arrastrar un tracklet de ruido (jugador, público, marcador…).
            self.reset()
            return sv.Detections.empty()

        return self._as_detections()

    def _as_detections(self) -> sv.Detections:
        if self._box is None:
            return sv.Detections.empty()
        return sv.Detections(
            xyxy=self._box.reshape(1, 4),
            confidence=np.array([self._confidence], dtype=np.float32),
            class_id=np.array([BASKETBALL_CLASS], dtype=int),
            tracker_id=np.array([BALL_TRACK_ID], dtype=int),
        )
