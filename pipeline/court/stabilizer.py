"""Estabilización temporal de los 33 keypoints de la cancha.

Trabaja por punto, en dos pasos por frame:

1.  **Filtro de outliers temporales.** Si un keypoint con confianza alta
    salta más de `outlier_max_jump_px` respecto a su posición estabilizada
    en el frame anterior, se considera ruido y se descarta para ESE frame.
    Esto es importante porque el modelo a veces "salta" un keypoint a otra
    intersección visualmente similar; si dejásemos pasar el salto al EMA,
    el suavizado solo lo amortiguaría parcialmente y la homografía
    resultante seguiría siendo mala.

2.  **EMA por punto** sobre los keypoints que sobreviven. El estado interno
    se actualiza solo con los puntos válidos, así que un punto que
    desaparece momentáneamente mantiene su última estimación congelada.

El estabilizador no decide si hay suficientes puntos para una H: eso es
responsabilidad del `HomographyEstimator`. Sólo se ocupa de entregar
keypoints temporalmente coherentes con una máscara de validez.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from pipeline.config import CourtSettings


@dataclass
class StabilizedKeypoints:
    """Salida del estabilizador para un frame."""

    xy: np.ndarray              # (N, 2) keypoints estabilizados
    confidence: np.ndarray      # (N,)   confianza original (sin alterar)
    valid_mask: np.ndarray      # (N,)   bool, qué keypoints son usables este frame


class KeypointStabilizer:
    """EMA por punto + rechazo de saltos bruscos entre frames consecutivos."""

    def __init__(self, settings: CourtSettings) -> None:
        self._s = settings
        self._prev_xy: Optional[np.ndarray] = None       # (N, 2) ema acumulado
        self._prev_valid: Optional[np.ndarray] = None    # (N,)  qué puntos teníamos en EMA

    def reset(self) -> None:
        self._prev_xy = None
        self._prev_valid = None

    def update(
        self,
        xy: Optional[np.ndarray],
        confidence: Optional[np.ndarray],
    ) -> StabilizedKeypoints:
        # Sin nueva observación (cadencia kp_every > 1): holdover puro.
        if xy is None or confidence is None:
            if self._prev_xy is not None:
                n = self._prev_xy.shape[0]
                return StabilizedKeypoints(
                    xy=self._prev_xy.copy(),
                    confidence=np.zeros(n, dtype=np.float32),
                    valid_mask=(
                        self._prev_valid.copy()
                        if self._prev_valid is not None
                        else np.zeros(n, dtype=bool)
                    ),
                )
            raise ValueError(
                "kp_stabilizer.update(None) llamado antes de tener estado previo"
            )

        n = xy.shape[0]
        high_conf = confidence > self._s.min_confidence

        # En el primer frame válido inicializamos el EMA con los puntos de alta
        # confianza tal cual y marcamos como válidos sólo esos.
        if self._prev_xy is None:
            ema = xy.copy()
            valid = high_conf.copy()
            self._prev_xy = ema.copy()
            self._prev_valid = valid.copy()
            return StabilizedKeypoints(xy=ema, confidence=confidence, valid_mask=valid)

        prev_xy = self._prev_xy
        prev_valid = self._prev_valid if self._prev_valid is not None else np.zeros(n, dtype=bool)

        # Paso 1: filtro de saltos para puntos que ya teníamos.
        diffs = np.linalg.norm(xy - prev_xy, axis=1)
        big_jump = diffs > self._s.outlier_max_jump_px
        rejected = high_conf & prev_valid & big_jump

        # Paso 2: EMA por punto sobre los puntos aceptados.
        accepted = high_conf & ~rejected
        a = self._s.ema_alpha

        ema = prev_xy.copy()
        # Puntos que ya teníamos y siguen viniendo: EMA clásico.
        warm = accepted & prev_valid
        ema[warm] = a * xy[warm] + (1 - a) * prev_xy[warm]
        # Puntos nuevos (no había estado previo válido): aceptamos la
        # detección actual como inicialización.
        cold = accepted & ~prev_valid
        ema[cold] = xy[cold]

        # Para los puntos rechazados o de baja confianza, mantenemos el valor
        # previo pero los marcamos como NO válidos en este frame.
        valid = warm | cold

        # Para keypoints que llevan mucho tiempo sin venir, evitamos mantener
        # una posición desfasada eternamente: si el punto no aparece y antes
        # tampoco era válido, su EMA se queda como está y `valid` ya es False.
        # No hace falta más.

        self._prev_xy = ema.copy()
        self._prev_valid = valid.copy()

        return StabilizedKeypoints(xy=ema, confidence=confidence, valid_mask=valid)
