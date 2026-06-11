"""Detección de la **suelta** del tiro a partir de la muñeca del poseedor y el balón.

Idea: mientras el jugador sostiene el balón, el balón está pegado a una muñeca
(distancia pequeña). En la suelta, el balón se **separa** de la mano y empieza a
**subir** (Δy-imagen negativo). Detectar ese instante da el frame de release, útil
para (a) sembrar la reconstrucción 3D del tiro con el inicio del vuelo libre y
(b) reforzar el trigger del :class:`ShotTracker`.

Estado puro y determinista (sin modelo): se alimenta por frame con la(s) muñeca(s)
del poseedor (de ``pipeline.pose``) y el centro del balón en imagen. Testeable en
aislamiento.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

import numpy as np

from pipeline.config import ReleaseSettings


@dataclass
class ReleaseEvent:
    """Suelta detectada en un frame."""

    frame_index: int
    ball_xy: np.ndarray   # centro del balón en imagen (px) en el instante de suelta
    confidence: float     # 0..1, según la nitidez de la separación + subida


@dataclass
class _Sample:
    frame_index: int
    ball_xy: Optional[np.ndarray]
    hand_dist: Optional[float]   # distancia a la muñeca más cercana (px) o None


class ReleaseDetector:
    def __init__(self, settings: Optional[ReleaseSettings] = None) -> None:
        self._s = settings or ReleaseSettings()
        self.reset()

    def reset(self) -> None:
        # Buffer suficiente para cubrir "sostenido recientemente" + ventana de confirmación.
        maxlen = max(self._s.held_lookback, self._s.confirm_frames) + 2
        self._hist: Deque[_Sample] = deque(maxlen=maxlen)
        self._cooldown = 0

    @staticmethod
    def _nearest_hand_dist(
        ball_xy: Optional[np.ndarray], wrists: List[np.ndarray]
    ) -> Optional[float]:
        if ball_xy is None or not wrists:
            return None
        return min(float(np.linalg.norm(np.asarray(w) - ball_xy)) for w in wrists)

    def update(
        self,
        frame_index: int,
        wrists: List[np.ndarray],
        ball_xy: Optional[np.ndarray],
    ) -> Optional[ReleaseEvent]:
        """Procesa un frame; devuelve un :class:`ReleaseEvent` si hay suelta.

        Args:
            frame_index: índice de frame.
            wrists: muñecas válidas del poseedor en coords de imagen (0, 1 o 2).
            ball_xy: centro del balón en imagen, o ``None`` si no se detecta.
        """
        if not self._s.enabled:
            return None
        if self._cooldown > 0:
            self._cooldown -= 1

        ball = None if ball_xy is None else np.asarray(ball_xy, dtype=np.float32)
        dist = self._nearest_hand_dist(ball, list(wrists))
        self._hist.append(_Sample(frame_index, ball, dist))

        if self._cooldown > 0:
            return None
        return self._evaluate(frame_index)

    def _evaluate(self, frame_index: int) -> Optional[ReleaseEvent]:
        cf = self._s.confirm_frames
        if len(self._hist) < cf + 1:
            return None

        window = list(self._hist)[-(cf + 1):]
        # La ventana de confirmación necesita balón y distancia válidos en todos
        # los frames (si la pose o el balón se pierden, no decidimos este frame).
        if any(s.ball_xy is None or s.hand_dist is None for s in window):
            return None

        dists = [s.hand_dist for s in window]
        ys = [float(s.ball_xy[1]) for s in window]

        # 1) El balón estuvo "en la mano" hace poco (antes de separarse).
        held_recent = any(
            s.hand_dist is not None and s.hand_dist <= self._s.held_px
            for s in self._hist
        )
        # 2) Separación: la distancia crece de forma monótona y supera el umbral.
        separating = all(b > a for a, b in zip(dists, dists[1:])) and dists[-1] >= self._s.separation_px
        # 3) El balón sube: Y-imagen decrece lo suficiente en la ventana.
        upward_px = ys[0] - ys[-1]  # positivo = ha subido
        rising = upward_px >= self._s.min_upward_px

        if held_recent and separating and rising:
            # Confianza: combina cuánto supera la separación y la subida.
            conf = min(
                1.0,
                0.5 * (dists[-1] / max(self._s.separation_px, 1.0))
                + 0.5 * (upward_px / max(self._s.min_upward_px, 1.0)) / 2.0,
            )
            self._cooldown = self._s.cooldown_frames
            return ReleaseEvent(
                frame_index=frame_index,
                ball_xy=window[-1].ball_xy.copy(),
                confidence=float(conf),
            )
        return None
