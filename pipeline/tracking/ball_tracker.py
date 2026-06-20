"""Tracking dedicado del balón en espacio imagen.

ByteTrack no es fiable con objetos pequeños que compiten con jugadores
cercanos. Este módulo elige la mejor detección por confianza, suaviza el
centro con EMA, mantiene holdover y asigna un ``tracker_id`` estable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import supervision as sv

from pipeline.config import BALL_CLASSES, BASKETBALL_CLASS, BallTrackingSettings

BALL_TRACK_ID = 9000


class BallTracker:
    def __init__(self, settings: Optional[BallTrackingSettings] = None) -> None:
        self._s = settings or BallTrackingSettings()
        self._box: Optional[np.ndarray] = None
        self._center: Optional[np.ndarray] = None
        self._confidence: float = 0.0
        self._frames_missing: int = 0
        # Velocidad (px/frame) y flag de extrapolación, para el resolutor de
        # posesión (P1). Misma interfaz que ``KalmanBallTracker``.
        self._velocity: Optional[np.ndarray] = None
        self._predicted: bool = False

    def reset(self) -> None:
        self._box = None
        self._center = None
        self._confidence = 0.0
        self._frames_missing = 0
        self._velocity = None
        self._predicted = False

    def last_predicted(self) -> bool:
        return self._predicted

    def last_velocity(self) -> Optional[np.ndarray]:
        return None if self._velocity is None else self._velocity.copy()

    @staticmethod
    def _center_from_box(box: np.ndarray) -> np.ndarray:
        return np.array(
            [(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0],
            dtype=np.float32,
        )

    def _pick_detection(self, detections: sv.Detections) -> Optional[int]:
        if detections is None or len(detections) == 0:
            return None

        ball_mask = np.isin(detections.class_id, list(BALL_CLASSES))
        if not ball_mask.any():
            return None

        indices = np.where(ball_mask)[0]
        confidences = (
            detections.confidence
            if detections.confidence is not None
            else np.ones(len(detections), dtype=np.float32)
        )

        best_idx: Optional[int] = None
        best_score = -1.0
        for i in indices:
            conf = float(confidences[i])
            if conf < self._s.min_confidence:
                continue
            box = detections.xyxy[i]
            center = self._center_from_box(box)

            if self._center is not None:
                dist = float(np.linalg.norm(center - self._center))
                if dist > self._s.match_distance_px:
                    continue

            if conf > best_score:
                best_score = conf
                best_idx = int(i)

        if best_idx is not None:
            return best_idx

        # Sin candidato cercano: la detección más confiable (pase largo / reaparición).
        valid = [
            int(i)
            for i in indices
            if float(confidences[i]) >= self._s.min_confidence
        ]
        if not valid:
            return None
        return max(valid, key=lambda i: float(confidences[i]))

    def _pick_highest_confidence(self, detections: sv.Detections) -> Optional[int]:
        """Modo simple: mejor detección por confianza, sin memoria temporal."""
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
        best_idx: Optional[int] = None
        best_conf = -1.0
        for i in np.where(ball_mask)[0]:
            conf = float(confidences[i])
            if conf < self._s.min_confidence or conf <= best_conf:
                continue
            best_conf = conf
            best_idx = int(i)
        return best_idx

    def update(self, detections: sv.Detections) -> sv.Detections:
        if self._s.simple:
            return self._update_simple(detections)

        self._predicted = False
        pick = self._pick_detection(detections)

        if pick is None:
            self._frames_missing += 1
            if (
                self._box is None
                or self._frames_missing > self._s.holdover_frames
            ):
                return sv.Detections.empty()
            self._predicted = True  # holdover: caja conservada, sin detección
            return self._as_detections()

        box = detections.xyxy[pick].astype(np.float32)
        conf = float(
            detections.confidence[pick]
            if detections.confidence is not None
            else 1.0
        )
        center = self._center_from_box(box)

        if self._center is not None:
            jump = float(np.linalg.norm(center - self._center))
            if jump > self._s.max_jump_px:
                self._frames_missing += 1
                if self._frames_missing > self._s.holdover_frames:
                    self._box = None
                    self._center = None
                    return sv.Detections.empty()
                self._predicted = True  # salto descartado: se conserva la caja
                return self._as_detections()

            a = self._s.ema_alpha
            smooth_center = a * center + (1.0 - a) * self._center
            half_w = (box[2] - box[0]) / 2.0
            half_h = (box[3] - box[1]) / 2.0
            box = np.array(
                [
                    smooth_center[0] - half_w,
                    smooth_center[1] - half_h,
                    smooth_center[0] + half_w,
                    smooth_center[1] + half_h,
                ],
                dtype=np.float32,
            )
            self._velocity = (smooth_center - self._center).astype(np.float32)
            self._center = smooth_center
        else:
            self._center = center.copy()

        self._box = box
        self._confidence = conf
        self._frames_missing = 0
        return self._as_detections()

    def _update_simple(self, detections: sv.Detections) -> sv.Detections:
        pick = self._pick_highest_confidence(detections)
        if pick is None:
            self.reset()
            return sv.Detections.empty()
        box = detections.xyxy[pick].astype(np.float32)
        self._box = box
        new_center = self._center_from_box(box)
        if self._center is not None:
            self._velocity = (new_center - self._center).astype(np.float32)
        self._center = new_center
        self._predicted = False
        self._confidence = float(
            detections.confidence[pick]
            if detections.confidence is not None
            else 1.0
        )
        self._frames_missing = 0
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
