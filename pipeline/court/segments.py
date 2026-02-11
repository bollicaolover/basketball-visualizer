"""Detección de movimiento de cámara a partir de los keypoints de la cancha.

En retransmisiones de baloncesto la cámara es mayormente estática con
paneo/zoom ocasionales. Detectar cuándo la cámara se mueve permite al
`HomographyEstimator` distinguir dos regímenes:

- **Cámara estable**: se pueden acumular keypoints de múltiples frames
  consecutivos y ajustar UNA homografía con todos ellos (mucho más estable
  que RANSAC frame a frame).
- **Cámara en movimiento**: el buffer se descarta y se vuelve a construir
  desde cero hasta recuperar la estabilidad.

Se aplican dos chequeos complementarios:

1. **Frame a frame** (paneos bruscos): mediana del desplazamiento entre el
   frame actual y el inmediatamente anterior.  Umbral: ``h_move_threshold_px``.

2. **Acumulado** (paneos lentos): mediana del desplazamiento entre el frame
   actual y el frame más antiguo de una ventana deslizante de
   ``h_move_window_frames`` frames.  Umbral: ``h_move_cumulative_threshold_px``.
   Un paneo de 5 px/frame que el chequeo frame-a-frame no detecta acumula
   ~25 px en 5 frames y dispara este segundo umbral.

En ambos casos se usa la mediana sobre el subconjunto de keypoints comunes,
lo que evita falsos positivos por:
* Cambios en el subconjunto válido (el centroide salta porque hoy hay 18
  keypoints y ayer había 25, no porque la cámara se moviera).
* Outliers individuales (un keypoint que "salta" a otra intersección
  visualmente similar); la mediana los ignora.

Si no hay suficientes keypoints comunes para comparar (típico tras un
corte de cámara o un reset del estabilizador), se asume pan: es más seguro
descartar puntos viejos potencialmente incompatibles que mezclarlos con
los del nuevo plano y producir una H degradada.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Tuple

import numpy as np

from pipeline.config import CourtSettings


class CameraSegmentTracker:
    """Detecta panes/cortes de cámara por desplazamiento mediano de keypoints."""

    def __init__(self, settings: CourtSettings) -> None:
        self._threshold_px: float = settings.h_move_threshold_px
        self._cumulative_threshold_px: float = settings.h_move_cumulative_threshold_px
        self._window_frames: int = settings.h_move_window_frames
        self._prev_xy: Optional[np.ndarray] = None
        self._prev_valid: Optional[np.ndarray] = None
        # Ventana deslizante de los últimos frames estables (xy, valid).
        self._window: Deque[Tuple[np.ndarray, np.ndarray]] = deque()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._prev_xy = None
        self._prev_valid = None
        self._window.clear()

    # ------------------------------------------------------------------
    def update(self, kp_xy: np.ndarray, valid_mask: np.ndarray) -> bool:
        """Actualiza el estado y devuelve ``True`` si se detectó un movimiento."""
        if not valid_mask.any():
            return False

        if self._prev_xy is None or self._prev_valid is None:
            self._prev_xy = kp_xy.copy()
            self._prev_valid = valid_mask.copy()
            self._window.append((kp_xy.copy(), valid_mask.copy()))
            return False

        common = valid_mask & self._prev_valid
        n_common = int(common.sum())

        if n_common < 3:
            # Sin suficientes keypoints comunes para comparar de manera
            # fiable; asumir pan para forzar un reset del buffer.
            self._prev_xy = kp_xy.copy()
            self._prev_valid = valid_mask.copy()
            self._window.clear()
            return True

        displacements = np.linalg.norm(
            kp_xy[common] - self._prev_xy[common], axis=1
        )
        median_shift = float(np.median(displacements))
        moved = median_shift > self._threshold_px

        # Chequeo acumulado: detecta paneos lentos que no superan el umbral
        # frame-a-frame pero sí acumulan un desplazamiento significativo
        # a lo largo de la ventana.
        if not moved and len(self._window) >= self._window_frames:
            oldest_xy, oldest_valid = self._window[0]
            common_old = valid_mask & oldest_valid
            if int(common_old.sum()) >= 3:
                diffs = np.linalg.norm(
                    kp_xy[common_old] - oldest_xy[common_old], axis=1
                )
                if float(np.median(diffs)) > self._cumulative_threshold_px:
                    moved = True

        self._prev_xy = kp_xy.copy()
        self._prev_valid = valid_mask.copy()

        if moved:
            # Limpiar la ventana para que el siguiente chequeo acumulado
            # parta desde la posición post-paneo, no de antes del paneo.
            self._window.clear()
        else:
            if len(self._window) >= self._window_frames:
                self._window.popleft()
            self._window.append((kp_xy.copy(), valid_mask.copy()))

        return moved
